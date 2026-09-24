"""Moduł Cloud: przeglądarka plików chmury osobistej (Nextcloud) w aplikacji Nexusa.

Nexus pośredniczy w dostępie do chmury hasłem aplikacji konta właściciela –
przeglądarka nie łączy się z Nextcloud bezpośrednio. Duże pliki przesyłane są
kawałkami (przeglądarka → Nexus → chunked upload v2 Nextcloud).
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

import httpx
import segno
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from nexus.api import conversations
from nexus.api.auth import require_session
from nexus.api.conversations import file_payload
from nexus.api.files import (
    INLINE_MIME_PREFIXES,
    INLINE_ZABRONIONE,
    _content_disposition,
    typ_nosnika,
    zajete_miejsce,
)
from nexus.cloud_service import CloudError, CloudService, check_name, clean_path
from nexus.config import Settings
from nexus.db import ADMIN_OWNER, Conversation, Database, StoredFile
from nexus.platnosci.uprawnienia import limity_uzytkownika, opis_przestrzeni
from nexus.storage import FileStorage, guess_mime, safe_filename

_dziennik = logging.getLogger(__name__)

# Treść wyjątku httpx potrafi nieść adres i port usługi chmury. Do rozmowy wraca jedno
# zdanie o tym, co się stało; szczegół zostaje w dzienniku serwera.
BRAK_POLACZENIA = "Chmura nie odpowiedziała. Spróbuj ponownie za chwilę."

router = APIRouter(prefix="/api/cloud", tags=["cloud"], dependencies=[Depends(require_session)])

MAX_CHUNK_BYTES = 100 * 1024 * 1024
MAX_TO_CONVERSATION = 20
PREVIEW_SIZES = (64, 128, 256, 512, 1024)
DEFAULT_PUBLIC_CLOUD = "https://cloud.danaco-nexus.pl"


def _settings(request: Request) -> Settings:
    return request.app.state.settings


async def _service(request: Request) -> CloudService:
    """Klient chmury zawężony do przestrzeni konta, które wykonuje to żądanie.

    Instalacja ma w Nextcloud jedno konto techniczne, więc rozdział robi ścieżka:
    ``/Konta/<owner>``. Folder zakładamy przy pierwszym wejściu — inaczej pierwsze
    listowanie kończyłoby się błędem 404 zamiast pustym katalogiem.
    """
    sesja = await require_session(request)
    try:
        service = CloudService(
            _settings(request),
            transport=getattr(request.app.state, "cloud_transport", None),
            owner=sesja.owner_id,
        )
    except CloudError as error:
        raise HTTPException(error.status, str(error)) from error
    try:
        await service.przygotuj_przestrzen()
    except CloudError as error:
        await service.close()
        raise HTTPException(error.status, str(error)) from error
    except httpx.HTTPError as error:
        await service.close()
        _dziennik.warning("chmura nie odpowiedziała: %s", error)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, BRAK_POLACZENIA) from error
    return service


async def _call(request: Request, operation: Any) -> Any:
    """Wykonuje operację na kliencie chmury, zamienia błędy na odpowiedzi HTTP."""
    service = await _service(request)
    try:
        return await operation(service)
    except CloudError as error:
        raise HTTPException(error.status, str(error)) from error
    except httpx.HTTPError as error:
        _dziennik.warning("chmura nie odpowiedziała: %s", error)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, BRAK_POLACZENIA) from error
    finally:
        await service.close()


def _length(request: Request) -> int | None:
    value = request.headers.get("content-length")
    return int(value) if value and value.isdigit() else None


class PathBody(BaseModel):
    path: str = Field(max_length=4000)


class RenameBody(BaseModel):
    path: str = Field(max_length=4000)
    name: str = Field(min_length=1, max_length=250)


class MoveBody(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=500)
    destination: str = Field(max_length=4000, description="Folder docelowy.")
    copy_only: bool = Field(False, alias="copy")
    overwrite: bool = False

    model_config = {"populate_by_name": True}


class PathsBody(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=500)


class FavoriteBody(BaseModel):
    path: str = Field(max_length=4000)
    favorite: bool


class VersionBody(BaseModel):
    path: str = Field(max_length=4000)
    version: str = Field(max_length=30)


class TrashRestoreBody(BaseModel):
    id: str = Field(max_length=500)


class ShareCreate(BaseModel):
    path: str = Field(max_length=4000)
    password: str | None = Field(None, max_length=200)
    expires: date | None = None
    allow_upload: bool = False
    label: str = Field("", max_length=250)


class ShareUpdate(BaseModel):
    password: str | None = Field(None, max_length=200, description="'' usuwa hasło.")
    expires: date | None = None
    clear_expiration: bool = False
    label: str | None = Field(None, max_length=250)


class UploadStart(BaseModel):
    path: str = Field(max_length=4000)


class UploadFinish(BaseModel):
    path: str = Field(max_length=4000)
    size: int = Field(ge=0)
    mtime: int | None = Field(None, ge=0)


class ToConversation(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=MAX_TO_CONVERSATION)
    conversation_id: uuid.UUID | None = None
    text: str = Field("", max_length=20_000)
    send: bool = Field(True, description="Od razu wyślij wiadomość z plikami do asystenta.")


# --- przeglądanie ---


@router.get("/lista")
async def list_folder(request: Request, path: str = "/") -> dict[str, Any]:
    """Zawartość folderu."""
    return await _call(request, lambda cloud: cloud.list(path))


@router.get("/info")
async def info(request: Request, path: str) -> dict[str, Any]:
    """Opis jednego pliku lub folderu."""
    return await _call(request, lambda cloud: cloud.stat(path))


@router.get("/miejsce")
async def quota(request: Request) -> dict[str, Any]:
    """Zajęte i wolne miejsce w chmurze."""
    return await _call(request, lambda cloud: cloud.quota())


@router.get("/szukaj")
async def search(request: Request, q: str = Query(min_length=2, max_length=200)) -> list[dict[str, Any]]:
    """Wyszukiwanie po nazwie w całej chmurze."""
    return await _call(request, lambda cloud: cloud.search(q))


@router.get("/ulubione")
async def favorites(request: Request) -> list[dict[str, Any]]:
    """Ulubione pliki i foldery."""
    return await _call(request, lambda cloud: cloud.favorites())


@router.post("/ulubione")
async def set_favorite(payload: FavoriteBody, request: Request) -> dict[str, bool]:
    """Dodaje do ulubionych albo z nich usuwa."""
    await _call(request, lambda cloud: cloud.set_favorite(payload.path, payload.favorite))
    return {"ok": True, "favorite": payload.favorite}


# --- pobieranie i podgląd ---


async def _stream(request: Request, path: str, inline: bool, version: str | None = None) -> StreamingResponse:
    service = await _service(request)
    try:
        version_url = await service.version_url(path, version) if version else None
        response = await service.open_download(path, version_url)
    except CloudError as error:
        await service.close()
        raise HTTPException(error.status, str(error)) from error
    except httpx.HTTPError as error:
        await service.close()
        _dziennik.warning("chmura nie odpowiedziała: %s", error)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, BRAK_POLACZENIA) from error

    async def cleanup() -> None:
        await response.aclose()
        await service.close()

    name = PurePosixPath(clean_path(path)).name or "plik"
    if version:
        stem, dot, suffix = name.rpartition(".")
        name = f"{stem} (wersja){dot}{suffix}" if dot else f"{name} (wersja)"
    mime = typ_nosnika(response.headers.get("content-type") or guess_mime(name))
    show_inline = inline and mime.startswith(INLINE_MIME_PREFIXES) and mime not in INLINE_ZABRONIONE
    headers = {
        "Content-Disposition": _content_disposition(name, show_inline),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }
    if show_inline:
        # Podgląd PDF w ramce okna podglądu (ta sama domena); pozostałe strony nie mogą osadzać plików.
        headers["X-Frame-Options"] = "SAMEORIGIN"
        headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    if response.headers.get("content-length"):
        headers["Content-Length"] = response.headers["content-length"]
    return StreamingResponse(
        response.aiter_bytes(),
        media_type=mime if show_inline else "application/octet-stream",
        headers=headers,
        background=BackgroundTask(cleanup),
    )


@router.get("/pobierz")
async def download(request: Request, path: str, inline: bool = False) -> StreamingResponse:
    """Pobiera plik strumieniowo (``inline=1`` – podgląd w przeglądarce, gdy bezpieczny)."""
    return await _stream(request, path, inline)


@router.get("/miniatura")
async def thumbnail(request: Request, fileid: int = Query(ge=1), size: int = 256) -> Response:
    """Miniatura pliku generowana przez chmurę."""
    size = min(PREVIEW_SIZES, key=lambda candidate: abs(candidate - size))
    result = await _call(request, lambda cloud: cloud.preview(fileid, size))
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brak miniatury.")
    data, mime = result
    return Response(data, media_type=mime, headers={"Cache-Control": "private, max-age=3600"})


# --- zmiany ---


@router.post("/folder", status_code=status.HTTP_201_CREATED)
async def create_folder(payload: PathBody, request: Request) -> dict[str, Any]:
    """Tworzy folder."""
    return await _call(request, lambda cloud: cloud.mkdir(payload.path))


@router.post("/zmien-nazwe")
async def rename(payload: RenameBody, request: Request) -> dict[str, Any]:
    """Zmienia nazwę pliku lub folderu."""
    name = _checked(check_name, payload.name)
    source = _checked(clean_path, payload.path)
    target = str(PurePosixPath(source).parent / name)

    async def run(cloud: CloudService) -> dict[str, Any]:
        await cloud.move(source, target)
        return await cloud.stat(target)

    return await _call(request, run)


def _checked(function: Any, value: str) -> str:
    try:
        return function(value)
    except CloudError as error:
        raise HTTPException(error.status, str(error)) from error


@router.post("/przenies")
async def move(payload: MoveBody, request: Request) -> dict[str, Any]:
    """Przenosi (albo kopiuje) pliki i foldery do wskazanego folderu."""
    destination = _checked(clean_path, payload.destination)

    async def run(cloud: CloudService) -> dict[str, Any]:
        done = []
        for raw in payload.paths:
            source = clean_path(raw)
            target = str(PurePosixPath(destination) / PurePosixPath(source).name)
            if payload.copy_only:
                await cloud.copy(source, target, payload.overwrite)
            else:
                await cloud.move(source, target, payload.overwrite)
            done.append(target)
        return {"ok": True, "paths": done}

    return await _call(request, run)


@router.post("/usun")
async def delete(payload: PathsBody, request: Request) -> dict[str, Any]:
    """Przenosi pliki i foldery do kosza chmury."""

    async def run(cloud: CloudService) -> dict[str, Any]:
        for path in payload.paths:
            await cloud.delete(path)
        return {"ok": True, "deleted": len(payload.paths)}

    return await _call(request, run)


@router.get("/kosz")
async def trash(request: Request) -> list[dict[str, Any]]:
    """Zawartość kosza."""
    return await _call(request, lambda cloud: cloud.trash())


@router.post("/kosz/przywroc")
async def restore_trash(payload: TrashRestoreBody, request: Request) -> dict[str, bool]:
    """Przywraca element z kosza na dawne miejsce."""
    await _call(request, lambda cloud: cloud.restore_trash(payload.id))
    return {"ok": True}


# --- wersje ---


@router.get("/wersje")
async def versions(request: Request, path: str) -> list[dict[str, Any]]:
    """Poprzednie wersje pliku."""
    return await _call(request, lambda cloud: cloud.versions(path))


@router.get("/wersje/pobierz")
async def download_version(request: Request, path: str, version: str) -> StreamingResponse:
    """Pobiera poprzednią wersję pliku."""
    return await _stream(request, path, inline=False, version=version)


@router.post("/wersje/przywroc")
async def restore_version(payload: VersionBody, request: Request) -> dict[str, Any]:
    """Przywraca poprzednią wersję (bieżąca zostaje zachowana jako wersja)."""

    async def run(cloud: CloudService) -> dict[str, Any]:
        await cloud.restore_version(payload.path, payload.version)
        return await cloud.stat(payload.path)

    return await _call(request, run)


# --- udostępnianie ---


@router.get("/udostepnienia")
async def shares(request: Request, path: str) -> list[dict[str, Any]]:
    """Linki publiczne do pliku lub folderu."""
    return await _call(request, lambda cloud: cloud.shares(path))


@router.post("/udostepnienia", status_code=status.HTTP_201_CREATED)
async def create_share(payload: ShareCreate, request: Request) -> dict[str, Any]:
    """Tworzy link publiczny (opcjonalnie z hasłem i datą wygaśnięcia)."""
    if payload.expires and payload.expires <= date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Data wygaśnięcia musi być w przyszłości.")
    return await _call(
        request,
        lambda cloud: cloud.create_share(
            payload.path, payload.password or None, payload.expires, payload.allow_upload, payload.label
        ),
    )


@router.patch("/udostepnienia/{share_id}")
async def update_share(share_id: str, payload: ShareUpdate, request: Request) -> dict[str, Any]:
    """Zmienia hasło, datę wygaśnięcia lub etykietę linku."""
    expires: date | str | None = "" if payload.clear_expiration else payload.expires
    if isinstance(expires, date) and expires <= date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Data wygaśnięcia musi być w przyszłości.")
    return await _call(
        request, lambda cloud: cloud.update_share(share_id, payload.password, expires, payload.label)
    )


@router.delete("/udostepnienia/{share_id}")
async def delete_share(share_id: str, request: Request) -> dict[str, bool]:
    """Usuwa link publiczny."""
    await _call(request, lambda cloud: cloud.delete_share(share_id))
    return {"ok": True}


# --- przesyłanie ---


def _body(request: Request) -> AsyncIterator[bytes]:
    return request.stream()


@router.put("/plik")
async def upload_file(request: Request, path: str) -> dict[str, Any]:
    """Zapisuje mały plik jednym żądaniem (treść żądania = zawartość pliku)."""
    length = _length(request)
    if length is not None and length > MAX_CHUNK_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Duże pliki przesyłaj kawałkami.")

    async def run(cloud: CloudService) -> dict[str, Any]:
        await cloud.put(path, _body(request), length)
        return await cloud.stat(path)

    return await _call(request, run)


@router.post("/przesylanie", status_code=status.HTTP_201_CREATED)
async def upload_start(payload: UploadStart, request: Request) -> dict[str, str]:
    """Rozpoczyna przesyłanie kawałkami; zwraca identyfikator przesyłania."""
    upload_id = f"nexus-{secrets.token_hex(12)}"
    await _call(request, lambda cloud: cloud.upload_start(upload_id, payload.path))
    return {"upload_id": upload_id}


@router.put("/przesylanie/{upload_id}/{number}")
async def upload_chunk(upload_id: str, number: int, request: Request, path: str) -> dict[str, bool]:
    """Przyjmuje kawałek pliku (numeracja od 1) i przekazuje go do chmury."""
    length = _length(request)
    if length is None:
        raise HTTPException(status.HTTP_411_LENGTH_REQUIRED, "Brak nagłówka Content-Length.")
    if length > MAX_CHUNK_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Kawałek jest za duży (najwyżej 100 MB).")
    await _call(request, lambda cloud: cloud.upload_chunk(upload_id, number, path, _body(request), length))
    return {"ok": True}


@router.post("/przesylanie/{upload_id}/zakoncz")
async def upload_finish(upload_id: str, payload: UploadFinish, request: Request) -> dict[str, Any]:
    """Składa przesłane kawałki w plik."""
    return await _call(
        request, lambda cloud: cloud.upload_finish(upload_id, payload.path, payload.size, payload.mtime)
    )


@router.delete("/przesylanie/{upload_id}")
async def upload_abort(upload_id: str, request: Request) -> dict[str, bool]:
    """Anuluje przesyłanie i usuwa przesłane kawałki."""
    await _call(request, lambda cloud: cloud.upload_abort(upload_id))
    return {"ok": True}


# --- plik z chmury do rozmowy ---


async def _przestrzen_konta(database: Database, owner: uuid.UUID) -> tuple[int, str]:
    """Przydział przestrzeni planu konta w bajtach i jego opis dla komunikatu."""
    limity = await limity_uzytkownika(database, str(owner))
    return limity.przestrzen_mb * 1024 * 1024, opis_przestrzeni(limity.przestrzen_mb)


async def _import(
    request: Request,
    cloud: CloudService,
    path: str,
    conversation_id: uuid.UUID | None,
    *,
    przydzial: int,
    zajete: int,
    opis_przydzialu: str,
) -> StoredFile:
    settings = _settings(request)
    storage: FileStorage = request.app.state.storage
    entry = await cloud.stat(path)
    if entry["type"] != "file":
        raise CloudError(400, f"{entry['name']} jest folderem – wybierz pliki.")
    limit = settings.upload_limit_mb * 1024 * 1024
    if (entry["size"] or 0) > limit:
        raise CloudError(413, f"{entry['name']} przekracza limit {settings.upload_limit_mb} MB.")
    # Plik z chmury zajmuje magazyn Nexusa tak samo jak wgrany z dysku, więc liczy się
    # do przydziału planu. Bez tego import omijał limit przestrzeni.
    if przydzial > 0 and zajete + (entry["size"] or 0) > przydzial:
        raise CloudError(
            413,
            f"Przestrzeń konta ({opis_przydzialu}) jest pełna. "
            "Usuń niepotrzebne pliki albo przejdź na wyższy plan.",
        )
    name = safe_filename(entry["name"])
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="chmura_", dir=settings.work_dir))
    target = directory / name
    try:
        response = await cloud.open_download(entry["path"])
        written = 0
        try:
            with target.open("wb") as handle:
                async for chunk in response.aiter_bytes():
                    written += len(chunk)
                    if written > limit:
                        raise CloudError(
                            413, f"{entry['name']} przekracza limit {settings.upload_limit_mb} MB."
                        )
                    await asyncio.to_thread(handle.write, chunk)
        finally:
            await response.aclose()
        file_id, relative, size, digest = await asyncio.to_thread(storage.import_file, target, name)
    finally:
        await asyncio.to_thread(lambda: [p.unlink(missing_ok=True) for p in directory.iterdir()])
        directory.rmdir()
    return StoredFile(
        id=file_id,
        conversation_id=conversation_id,
        origin="cloud",
        name=name,
        mime=guess_mime(name),
        size=size,
        sha256=digest,
        storage_path=relative,
        meta={"description": f"Z chmury: {entry['path']}", "cloud_path": entry["path"]},
    )


@router.post("/do-rozmowy")
async def to_conversation(payload: ToConversation, request: Request) -> dict[str, Any]:
    """Dołącza pliki z chmury do rozmowy (nowej albo wskazanej) i opcjonalnie wysyła wiadomość."""
    database: Database = request.app.state.database
    wlasciciel_konta = (await require_session(request)).owner_id
    if payload.conversation_id is not None:
        async with database.session() as session:
            rozmowa = await session.get(Conversation, payload.conversation_id)
        # Cudza rozmowa odpowiada tak samo jak nieistniejąca: sam identyfikator nie może
        # wystarczyć do dołożenia plików do rozmowy innego konta.
        if rozmowa is None or rozmowa.owner_id != wlasciciel_konta:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono rozmowy.")

    async def run(cloud: CloudService) -> list[StoredFile]:
        przydzial, opis = await _przestrzen_konta(database, wlasciciel_konta)
        zajete = await zajete_miejsce(database, wlasciciel_konta)
        pobrane: list[StoredFile] = []
        for path in payload.paths:
            rekord = await _import(
                request,
                cloud,
                path,
                payload.conversation_id,
                przydzial=przydzial,
                zajete=zajete,
                opis_przydzialu=opis,
            )
            zajete += rekord.size
            pobrane.append(rekord)
        return pobrane

    records = await _call(request, run)
    conversation_id = payload.conversation_id
    if conversation_id is None:
        created = await conversations.create_conversation(
            conversations.CreateConversation(), request, wlasciciel_konta
        )
        conversation_id = uuid.UUID(created["id"])
    async with database.session() as session:
        for record in records:
            record.conversation_id = conversation_id
            # Bez tego plik z przestrzeni klienta zapisywał się na koncie domyślnym
            # (właściciela instalacji) i trafiał do cudzego wykazu plików.
            record.owner_id = wlasciciel_konta
            session.add(record)
    run_id = None
    if payload.send:
        names = ", ".join(record.name for record in records)
        text = (
            payload.text.strip() or f"Przeanalizuj plik{'i' if len(records) > 1 else ''} z chmury: {names}."
        )
        result = await conversations.send_message(
            conversation_id,
            conversations.SendMessage(text=text, file_ids=[record.id for record in records]),
            request,
            wlasciciel_konta,
        )
        run_id = result["run_id"]
    return {
        "conversation_id": str(conversation_id),
        "run_id": run_id,
        "files": [file_payload(record) for record in records],
    }


# --- synchronizacja ---


@router.get("/synchronizacja")
async def sync_info(request: Request) -> dict[str, Any]:
    """Adres serwera dla aplikacji Nextcloud (Windows, Android, iOS) z kodem QR.

    Tylko dla właściciela instalacji: konto Nextcloud jest jedno i należy do niego. Klient
    dostawał tu login ``admin``, którym nie zaloguje się i którego nie powinien znać.
    """
    if (await require_session(request)).owner_id != ADMIN_OWNER:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Synchronizacja z aplikacjami Nextcloud nie jest jeszcze dostępna dla Twojego konta. "
            "Pliki przesyłasz i pobierasz w module Pliki.",
        )
    settings = _settings(request)
    server = (settings.chmura_public_url or DEFAULT_PUBLIC_CLOUD).rstrip("/")
    qr = segno.make(server, error="m")
    return {
        "server_url": server,
        "user": settings.chmura_user,
        "qr": qr.svg_data_uri(scale=6, border=2, dark="#111113", light="#ffffff"),
        "webdav_url": f"{server}/remote.php/dav/files/{settings.chmura_user}/",
        "clients": {
            "windows": "https://nextcloud.com/install/#install-clients",
            "android": "https://play.google.com/store/apps/details?id=com.nextcloud.client",
            "android_fdroid": "https://f-droid.org/packages/com.nextcloud.client/",
            "ios": "https://apps.apple.com/app/nextcloud/id1125420102",
        },
    }
