"""API plików: przesyłanie, pobieranie, miniatury."""

from __future__ import annotations

import asyncio
import io
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
    # ma 100 MB, plan Osobisty 1 GB, Pro 2 GB, Zespół 10 GB.
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
        mime=guess_mime(name)
        if (file.content_type or "").startswith("application/octet") or not file.content_type
        else file.content_type,
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
    show_inline = inline and record.mime.startswith(INLINE_MIME_PREFIXES) and record.mime != "image/svg+xml"
    return FileResponse(
        path,
        media_type=record.mime if show_inline else "application/octet-stream",
        headers={
            "Content-Disposition": _content_disposition(record.name, show_inline),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )


def _thumbnail(path: Path, mime: str, target: Path) -> bytes | None:
    try:
        if mime == "application/pdf" or path.suffix.lower() == ".pdf":
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


@router.get("/{file_id}/thumbnail")
async def thumbnail(
    file_id: uuid.UUID, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> Response:
    """Miniatura obrazu lub pierwszej strony PDF (JPEG, z pamięci podręcznej)."""
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
