"""Magazyn plików: zapis na dysku i metadane w bazie."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import shutil
import unicodedata
import uuid
from pathlib import Path
from typing import BinaryIO

from nexus.db import StoredFile

CHUNK = 1024 * 1024
EXTRA_MIME_TYPES: dict[str, str] = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".md": "text/markdown",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
    ".zip": "application/zip",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def guess_mime(name: str) -> str:
    """Typ MIME na podstawie rozszerzenia nazwy pliku."""
    suffix = Path(name).suffix.lower()
    if suffix in EXTRA_MIME_TYPES:
        return EXTRA_MIME_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(name)
    return guessed or "application/octet-stream"


def safe_filename(name: str, default: str = "plik") -> str:
    """Bezpieczna nazwa pliku (bez ścieżek i znaków sterujących), z polskimi literami."""
    name = unicodedata.normalize("NFC", Path(name.replace("\\", "/")).name)
    name = re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "_", name).strip(" .")
    if not name:
        return default
    stem, suffix = os.path.splitext(name)
    return stem[:180] + suffix[:20]


class FileStorage:
    """Zapis plików w katalogu danych, rozproszonych w podkatalogach."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_of(self, record: StoredFile) -> Path:
        """Ścieżka pliku na dysku."""
        return self.root / record.storage_path

    def _new_location(self, file_id: uuid.UUID, name: str) -> tuple[Path, str]:
        suffix = Path(name).suffix.lower()[:20]
        relative = f"{file_id.hex[:2]}/{file_id.hex}{suffix}"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        return target, relative

    def save_stream(self, stream: BinaryIO, name: str, limit_bytes: int) -> tuple[uuid.UUID, str, int, str]:
        """Zapisuje strumień; zwraca identyfikator, ścieżkę względną, rozmiar i SHA-256.

        Przekroczenie ``limit_bytes`` usuwa częściowy plik i zgłasza ``ValueError``.
        """
        file_id = uuid.uuid4()
        target, relative = self._new_location(file_id, name)
        digest = hashlib.sha256()
        size = 0
        try:
            with target.open("wb") as output:
                while chunk := stream.read(CHUNK):
                    size += len(chunk)
                    if size > limit_bytes:
                        raise ValueError(f"Plik przekracza limit {limit_bytes // CHUNK} MB.")
                    digest.update(chunk)
                    output.write(chunk)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return file_id, relative, size, digest.hexdigest()

    def import_file(self, source: Path, name: str) -> tuple[uuid.UUID, str, int, str]:
        """Przenosi gotowy plik (np. wynik narzędzia) do magazynu."""
        file_id = uuid.uuid4()
        target, relative = self._new_location(file_id, name)
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            while chunk := handle.read(CHUNK):
                digest.update(chunk)
        shutil.move(str(source), target)
        return file_id, relative, target.stat().st_size, digest.hexdigest()

    def delete(self, record: StoredFile) -> None:
        """Usuwa plik z dysku (brak pliku nie jest błędem)."""
        self.path_of(record).unlink(missing_ok=True)
