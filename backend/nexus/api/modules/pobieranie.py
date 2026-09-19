"""Publiczne pobieranie instalatorów: ``/pobierz/<plik>`` (bez logowania).

Pliki leżą w ``<data_dir>/pobieranie``; serwowane są wyłącznie nazwy z białej listy,
więc katalog nie może posłużyć do udostępnienia niczego innego.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

router = APIRouter(prefix="/pobierz", tags=["pobieranie"])

# Nazwa pliku -> (typ MIME, opis).
DOWNLOADS: dict[str, tuple[str, str]] = {
    "nexus-android.apk": ("application/vnd.android.package-archive", "Aplikacja Android"),
    "nexus-desktop-setup.exe": ("application/vnd.microsoft.portable-executable", "Nexus Desktop (Windows)"),
    "nexus-rozszerzenie.zip": ("application/zip", "Rozszerzenie przeglądarki"),
}
_digests: dict[str, tuple[float, int, str]] = {}


def _path(request: Request, name: str) -> Path | None:
    if name not in DOWNLOADS:
        return None
    candidate = request.app.state.settings.downloads_dir / name
    return candidate if candidate.is_file() else None


def _sha256(path: Path) -> str:
    stat = path.stat()
    cached = _digests.get(str(path))
    if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return cached[2]
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    _digests[str(path)] = (stat.st_mtime, stat.st_size, digest.hexdigest())
    return digest.hexdigest()


@router.get("")
async def list_downloads(request: Request) -> list[dict[str, Any]]:
    """Dostępne instalatory (strona startowa pokazuje brakujące jako „wkrótce”)."""
    result = []
    for name, (_mime, label) in DOWNLOADS.items():
        path = _path(request, name)
        entry: dict[str, Any] = {"name": name, "label": label, "available": path is not None}
        if path is not None:
            stat = path.stat()
            entry["size"] = stat.st_size
            entry["updated_at"] = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
            entry["sha256"] = await asyncio.to_thread(_sha256, path)
        result.append(entry)
    return result


@router.api_route("/{name}", methods=["GET", "HEAD"])
async def download(name: str, request: Request) -> FileResponse:
    """Plik instalatora jako załącznik."""
    path = _path(request, name)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ten plik nie jest jeszcze dostępny do pobrania.")
    return FileResponse(
        path,
        media_type=DOWNLOADS[name][0],
        headers={
            "Content-Disposition": f"attachment; filename=\"{name}\"; filename*=UTF-8''{quote(name)}",
            "Cache-Control": "no-cache",
        },
    )
