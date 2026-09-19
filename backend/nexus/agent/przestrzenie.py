"""Przestrzenie projektów modułu Kod (``<data_dir>/kod/<nazwa>``) i bezpieczne ścieżki w nich."""

from __future__ import annotations

import re
from pathlib import Path

from nexus.config import Settings

PROJECT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
DRIVE = re.compile(r"[A-Za-z]:")


class WorkspaceError(ValueError):
    """Niepoprawna nazwa projektu lub ścieżka spoza projektu."""


def valid_project_name(name: str) -> bool:
    """Nazwa katalogu projektu: litery, cyfry, ``._-``, bez ``..`` i ukrytych katalogów."""
    return bool(PROJECT_NAME.fullmatch(name)) and ".." not in name


def project_dir(settings: Settings, name: str) -> Path:
    """Katalog projektu (bez sprawdzania istnienia); błąd dla niepoprawnej nazwy."""
    if not valid_project_name(name):
        raise WorkspaceError("Niepoprawna nazwa projektu (litery, cyfry, kropka, podkreślnik, myślnik).")
    return settings.kod_dir / name


def existing_project(settings: Settings, name: str) -> Path | None:
    """Katalog istniejącego projektu albo ``None``."""
    try:
        path = project_dir(settings, name)
    except WorkspaceError:
        return None
    return path if path.is_dir() and not path.is_symlink() else None


def safe_path(root: Path, relative: str) -> Path:
    """Ścieżka wewnątrz projektu; odrzuca ścieżki bezwzględne, ``..`` i dowiązania na zewnątrz."""
    relative = (relative or "").replace("\\", "/").rstrip("/")
    if "\x00" in relative:
        raise WorkspaceError("Niepoprawna ścieżka.")
    candidate = Path(relative)
    if (
        relative.startswith("/")
        or DRIVE.match(relative)
        or candidate.is_absolute()
        or any(part == ".." for part in candidate.parts)
    ):
        raise WorkspaceError("Ścieżka musi leżeć wewnątrz projektu.")
    base = root.resolve()
    resolved = (base / candidate).resolve()
    if resolved != base and not resolved.is_relative_to(base):
        raise WorkspaceError("Ścieżka musi leżeć wewnątrz projektu.")
    return resolved
