"""API plików: przesyłanie, pobieranie, miniatury."""

from __future__ import annotations

import asyncio
import io
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pymupdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select

from nexus.api.auth import require_session, wlasciciel
from nexus.api.conversations import file_payload
from nexus.db import Conversation, Database, StoredFile
from nexus.platnosci.uprawnienia import limity_uzytkownika, opis_przestrzeni
from nexus.storage import FileStorage, guess_mime, safe_filename
from nexus.tools.common import open_image

router = APIRouter(prefix="/api/files", tags=["files"], dependencies=[Depends(require_session)])

THUMBNAIL_SIDE = 320
INLINE_MIME_PREFIXES = ("image/", "application/pdf", "text/plain", "audio/", "video/")
# Dokumenty, które przeglądarka wykonuje jak stronę (skrypt, odsyłacz zewnętrzny), nigdy
# nie wyświetlają się w oknie aplikacji — idą wyłącznie jako pobranie.
INLINE_ZABRONIONE = frozenset({"image/svg+xml", "image/svg", "text/html", "text/xml", "application/xml"})


def typ_nosnika(mime: str) -> str:
    """Sam typ nośnika, bez parametrów: ``image/svg+xml; charset=utf-8`` → ``image/svg+xml``."""
    return mime.split(";", 1)[0].strip().lower()


def _content_disposition(name: str, inline: bool) -> str:
    """Nagłówek Content-Disposition z nazwą w UTF-8 (RFC 6266 / RFC 5987)."""
    ascii_name = name.encode("ascii", "replace").decode("ascii").replace('"', "")
    kind = "inline" if inline else "attachment"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


async def _record(request: Request, file_id: uuid.UUID, owner: uuid.UUID) -> StoredFile:
    """Plik należący do ``owner``; cudzy plik daje 404 jak nieistniejący."""
    database: Database = request.app.state.database
    async with database.session() as session:
        record = await session.get(StoredFile, file_id)
    if record is None or record.owner_id != owner:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono pliku.")
    return record


async def zajete_miejsce(database: Database, owner: uuid.UUID) -> int:
    """Suma rozmiarów plików konta w bajtach."""
    async with database.session() as session:
        return int(
            await session.scalar(
                select(func.coalesce(func.sum(StoredFile.size), 0)).where(StoredFile.owner_id == owner)
            )
            or 0
        )


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    conversation_id: uuid.UUID | None = Form(None),
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Przesyła plik (opcjonalnie od razu przypisany do rozmowy)."""
    settings = request.app.state.settings
    storage: FileStorage = request.app.state.storage
    database: Database = request.app.state.database
    if conversation_id is not None:
        async with database.session() as session:
            rozmowa = await session.get(Conversation, conversation_id)
            if rozmowa is None or rozmowa.owner_id != owner:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono rozmowy.")
    # Przestrzeń rozstrzyga plan konta, nie jedna wartość dla wszystkich: okres próbny
    # ma 100 MB, plan Osobisty 1 GB, Pro 2 GB, Grupa 10 GB.
    limity = await limity_uzytkownika(database, str(owner))
    limit = limity.przestrzen_mb * 1024 * 1024
    zajete = await zajete_miejsce(database, owner)
    if limit > 0 and zajete >= limit:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Przestrzeń konta ({opis_przestrzeni(limity.przestrzen_mb)}) jest pełna. "
            "Usuń niepotrzebne pliki albo przejdź na wyższy plan.",
        )
    name = safe_filename(file.filename or "plik")
    zadeklarowany = typ_nosnika(file.content_type or "")
    try:
        file_id, relative, size, digest = await asyncio.to_thread(
            storage.save_stream, file.file, name, settings.upload_limit_mb * 1024 * 1024
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(error)) from error
    finally:
        await file.close()
    record = StoredFile(
        id=file_id,
        conversation_id=conversation_id,
        owner_id=owner,
        origin="upload",
        name=name,
        # Rodzaj zapisujemy bez parametrów podanych przez klienta: w bazie ma zostać sam
        # typ nośnika, bo po nim rozstrzyga się podgląd, miniatura i konwersje.
        mime=zadeklarowany
        if zadeklarowany and not zadeklarowany.startswith("application/octet")
        else guess_mime(name),
        size=size,
        sha256=digest,
        storage_path=relative,
        meta={},
    )
    async with database.session() as session:
        session.add(record)
    return file_payload(record)


@router.get("/{file_id}/download")
async def download(
    file_id: uuid.UUID,
    request: Request,
    inline: bool = False,
    owner: uuid.UUID = Depends(wlasciciel),
) -> FileResponse:
    """Pobiera plik (``inline=1`` – wyświetlenie w przeglądarce, gdy to bezpieczne)."""
    record = await _record(request, file_id, owner)
    storage: FileStorage = request.app.state.storage
    path = storage.path_of(record)
    if not path.is_file():
        raise HTTPException(status.HTTP_410_GONE, "Plik nie jest już dostępny.")
    # Rodzaj pliku rozstrzyga sam typ nośnika: z parametrem (``; charset=utf-8``) porównanie
    # z pełną wartością przepuszczało dokument SVG do wyświetlenia w domenie aplikacji.
    typ = typ_nosnika(record.mime)
    show_inline = inline and typ.startswith(INLINE_MIME_PREFIXES) and typ not in INLINE_ZABRONIONE
    return FileResponse(
        path,
        media_type=typ if show_inline else "application/octet-stream",
        headers={
            "Content-Disposition": _content_disposition(record.name, show_inline),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )


#: Ile sekund od początku bierzemy na miniaturę filmu. Pierwsza klatka bywa czarna
#: (zaciemnienie, plansza), więc sięgamy głębiej — a przy krótszym pliku ffmpeg i tak
#: odda ostatnią klatkę.
MINIATURA_FILMU_S = "00:00:01"


def _klatka_filmu(path: Path) -> Path | None:
    """Klatka wyjęta z filmu do pliku tymczasowego — albo ``None``, gdy się nie udało."""
    klatka = Path(tempfile.mkdtemp()) / "klatka.jpg"
    try:
        wynik = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", MINIATURA_FILMU_S,
             "-i", str(path), "-frames:v", "1", "-q:v", "3", str(klatka)],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if wynik.returncode != 0 or not klatka.is_file() or klatka.stat().st_size == 0:
        return None
    return klatka


def _thumbnail(path: Path, mime: str, target: Path) -> bytes | None:
    tymczasowa: Path | None = None
    try:
        if mime.startswith("video/"):
            # Film bez miniatury to w wykazie plików szary prostokąt; w storyboardzie
            # montażu (Studio → Montaż) po takim ujęciu nie widać, co w nim jest.
            tymczasowa = _klatka_filmu(path)
            if tymczasowa is None:
                return None
            image = open_image(tymczasowa)
        elif mime == "application/pdf" or path.suffix.lower() == ".pdf":
            with pymupdf.open(path) as document:
                page = document[0]
                scale = THUMBNAIL_SIDE * 2 / max(page.rect.width, page.rect.height)
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                from PIL import Image

                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        elif mime.startswith("image/"):
            image = open_image(path)
        else:
            return None
        image = image.convert("RGB")
        image.thumbnail((THUMBNAIL_SIDE * 2, THUMBNAIL_SIDE * 2))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=80)
        data = buffer.getvalue()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return data
    except Exception:  # noqa: BLE001 - brak miniatury nie jest błędem
        return None
    finally:
        if tymczasowa is not None:
            shutil.rmtree(tymczasowa.parent, ignore_errors=True)


@router.get("/{file_id}/thumbnail")
async def thumbnail(
    file_id: uuid.UUID, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> Response:
    """Miniatura obrazu, klatki filmu albo pierwszej strony PDF (JPEG, z pamięci podręcznej)."""
    record = await _record(request, file_id, owner)
    settings = request.app.state.settings
    storage: FileStorage = request.app.state.storage
    cached = settings.cache_dir / "thumbnails" / f"{record.id.hex}.jpg"
    data = (
        cached.read_bytes()
        if cached.is_file()
        else await asyncio.to_thread(_thumbnail, storage.path_of(record), record.mime, cached)
    )
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brak miniatury dla tego pliku.")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
