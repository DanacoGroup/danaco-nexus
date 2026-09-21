"""Magazyn stron WWW tworzonych przez asystenta (Twórca stron).

Układ katalogu ``<dane>/strony``:

- ``<adres>/`` – szkic strony (edytowany przez agenta i podglądany na żywo),
- ``.opublikowane/<adres>/`` – zamrożona kopia opublikowana pod ``/s/<adres>/``,
- ``.wersje/<adres>/<wersja>/`` – migawki szkicu (przywracanie),
- ``.meta/<adres>.json`` – tytuł, opis, rozmowa, wersje, stan publikacji.

Adres i ścieżki plików są ściśle walidowane: bez ``..``, ukrytych segmentów,
ścieżek bezwzględnych i znaków spoza bezpiecznego zestawu.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from nexus.db import ADMIN_OWNER

ADDRESS = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,46}[a-z0-9])?$")
SEGMENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,99}$")
TEXT_SUFFIXES = frozenset(
    {".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg", ".txt", ".md", ".xml", ".webmanifest", ".csv"}
)
BINARY_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".avif",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".mp4",
        ".webm",
        ".mp3",
        ".ogg",
        ".pdf",
    }
)
ALLOWED_SUFFIXES = TEXT_SUFFIXES | BINARY_SUFFIXES
MAX_DEPTH = 8
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_FILES = 2000
MAX_VERSIONS = 50
PLACEHOLDER = """<!doctype html>
<html lang="pl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;font-family:system-ui,sans-serif;
background:#f4f4f5;color:#52525b}}</style></head>
<body><p>Strona „{title}” jest w przygotowaniu…</p></body>
</html>
"""


class SiteError(ValueError):
    """Nieprawidłowa operacja na stronie (komunikat dla użytkownika lub modelu)."""


def wlasciciel_strony(meta: dict[str, Any]) -> uuid.UUID:
    """Konto, do którego należy strona; strony sprzed wykazu należą do właściciela instalacji."""
    try:
        return uuid.UUID(str(meta.get("owner_id")))
    except ValueError:
        return ADMIN_OWNER


def now_iso() -> str:
    """Bieżący czas UTC w formacie ISO 8601."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def check_address(address: str) -> str:
    """Zwraca poprawny adres strony (małe litery, cyfry, łączniki) albo zgłasza ``SiteError``."""
    value = (address or "").strip().lower()
    if not ADDRESS.fullmatch(value):
        raise SiteError(
            f"Nieprawidłowy adres strony: {address!r}. Dozwolone: małe litery a–z, cyfry i łączniki "
            "(do 48 znaków, bez łącznika na początku i końcu)."
        )
    return value


def check_path(path: str, allow_empty: bool = False) -> str:
    """Normalizuje ścieżkę pliku strony (``css/style.css``); odrzuca niebezpieczne ścieżki."""
    raw = (path or "").strip()
    if "\\" in raw or "\x00" in raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise SiteError(f"Nieprawidłowa ścieżka pliku: {path!r} (tylko ścieżki względne z ukośnikiem '/').")
    parts = [part for part in PurePosixPath(raw).parts if part not in ("", ".")]
    if not parts:
        if allow_empty:
            return ""
        raise SiteError("Podaj ścieżkę pliku, np. index.html albo css/style.css.")
    if len(parts) > MAX_DEPTH:
        raise SiteError(f"Ścieżka {path!r} jest zbyt głęboka (najwyżej {MAX_DEPTH} poziomów).")
    for part in parts:
        if part == ".." or not SEGMENT.fullmatch(part):
            raise SiteError(
                f"Nieprawidłowa ścieżka pliku: {path!r}. Dozwolone znaki: litery a–z, cyfry, '.', '_', '-'; "
                "bez '..' i plików ukrytych."
            )
    return "/".join(parts)


def check_file_path(path: str) -> str:
    """Ścieżka pliku z dozwolonym rozszerzeniem."""
    normalized = check_path(path)
    suffix = PurePosixPath(normalized).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        raise SiteError(f"Niedozwolony typ pliku {suffix or '(brak rozszerzenia)'}. Dozwolone: {allowed}.")
    return normalized


def _write_atomic(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".zapis-")
    try:
        with os.fdopen(handle, "wb") as output:
            output.write(data)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _tree_size(root: Path) -> tuple[int, int]:
    size = count = 0
    if root.is_dir():
        for item in root.rglob("*"):
            if item.is_file() and not item.is_symlink():
                size += item.stat().st_size
                count += 1
    return size, count


class SiteStore:
    """Strony użytkownika na dysku serwera.

    ``owner`` zawęża magazyn do jednego konta: metadane, pliki, wersje i publikacja cudzej
    strony są wtedy nieosiągalne — jak strona, której nie ma. Bez ``owner`` (serwowanie
    opublikowanych stron) zawężenia nie ma, bo te pliki są publiczne z założenia.
    """

    def __init__(self, root: Path, max_site_mb: int = 200, owner: uuid.UUID | None = None) -> None:
        self.root = root
        self.max_site_bytes = max_site_mb * 1024 * 1024
        self.owner = owner

    # --- katalogi i metadane ---------------------------------------------------------------------

    def draft_dir(self, address: str) -> Path:
        return self.root / check_address(address)

    def published_dir(self, address: str) -> Path:
        return self.root / ".opublikowane" / check_address(address)

    def _versions_dir(self, address: str) -> Path:
        return self.root / ".wersje" / check_address(address)

    def _meta_file(self, address: str) -> Path:
        return self.root / ".meta" / f"{check_address(address)}.json"

    def exists(self, address: str) -> bool:
        return self._meta_file(address).is_file()

    def meta(self, address: str) -> dict[str, Any]:
        """Metadane strony konta; ``SiteError``, gdy strona nie istnieje albo należy do innego konta."""
        path = self._meta_file(address)
        try:
            dane = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise SiteError(f"Strona {address!r} nie istnieje.") from None
        if self.owner is not None and wlasciciel_strony(dane) != self.owner:
            raise SiteError(f"Strona {address!r} nie istnieje.")
        return dane

    def _save_meta(self, address: str, meta: dict[str, Any]) -> dict[str, Any]:
        meta["updated_at"] = now_iso()
        _write_atomic(
            self._meta_file(address), json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8")
        )
        return meta

    def update_meta(self, address: str, **values: Any) -> dict[str, Any]:
        meta = self.meta(address)
        meta.update(values)
        return self._save_meta(address, meta)

    def create(self, address: str, title: str, description: str = "") -> dict[str, Any]:
        """Zakłada stronę z tymczasową stroną główną."""
        address = check_address(address)
        if self.exists(address) or self.draft_dir(address).exists():
            raise SiteError(f"Strona o adresie {address!r} już istnieje.")
        title = title.strip()[:200] or address
        draft = self.draft_dir(address)
        draft.mkdir(parents=True)
        safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        (draft / "index.html").write_text(PLACEHOLDER.format(title=safe_title), encoding="utf-8")
        meta = {
            "address": address,
            "owner_id": str(self.owner) if self.owner else None,
            "title": title,
            "description": description.strip()[:4000],
            "created_at": now_iso(),
            "conversation_id": None,
            "published_at": None,
            "publish_request": None,
            "versions": [],
            "next_version": 1,
        }
        return self._save_meta(address, meta)

    def list_sites(self) -> list[dict[str, Any]]:
        """Metadane wszystkich stron (od ostatnio zmienianej)."""
        folder = self.root / ".meta"
        sites = []
        if folder.is_dir():
            for path in folder.glob("*.json"):
                try:
                    dane = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if self.owner is None or wlasciciel_strony(dane) == self.owner:
                    sites.append(dane)
        return sorted(sites, key=lambda item: item.get("updated_at", ""), reverse=True)

    def delete_site(self, address: str) -> None:
        """Usuwa stronę razem z wersjami i publikacją."""
        self.meta(address)
        for folder in (self.draft_dir(address), self.published_dir(address), self._versions_dir(address)):
            shutil.rmtree(folder, ignore_errors=True)
        self._meta_file(address).unlink(missing_ok=True)

    # --- pliki szkicu ----------------------------------------------------------------------------

    def _file(self, address: str, path: str, published: bool = False) -> Path:
        base = self.published_dir(address) if published else self.draft_dir(address)
        target = (base / check_path(path)).resolve()
        if not target.is_relative_to(base.resolve()):
            raise SiteError(f"Ścieżka {path!r} wychodzi poza katalog strony.")
        return target

    def resolve(self, address: str, path: str, published: bool) -> Path | None:
        """Plik do wyświetlenia (``""`` i katalogi → ``index.html``); ``None``, gdy brak."""
        try:
            normalized = check_path(path, allow_empty=True)
            base = self.published_dir(address) if published else self.draft_dir(address)
        except SiteError:
            return None
        candidate = base / normalized if normalized else base
        if candidate.is_dir():
            candidate = candidate / "index.html"
        try:
            resolved = candidate.resolve()
        except OSError:
            return None
        if not resolved.is_relative_to(base.resolve()) or not resolved.is_file():
            return None
        if resolved.suffix.lower() not in ALLOWED_SUFFIXES:
            return None
        return resolved

    def _check_capacity(self, address: str, target: Path, new_size: int) -> None:
        size, count = _tree_size(self.draft_dir(address))
        previous = target.stat().st_size if target.is_file() else 0
        if not target.exists() and count >= MAX_FILES:
            raise SiteError(f"Strona ma już {MAX_FILES} plików – usuń zbędne.")
        if size - previous + new_size > self.max_site_bytes:
            raise SiteError(f"Przekroczony limit rozmiaru strony ({self.max_site_bytes // 1024 // 1024} MB).")

    def write_bytes(self, address: str, path: str, data: bytes) -> dict[str, Any]:
        """Zapisuje plik szkicu (tworzy katalogi)."""
        self.meta(address)
        normalized = check_file_path(path)
        if len(data) > MAX_FILE_BYTES:
            raise SiteError(f"Plik jest zbyt duży (limit {MAX_FILE_BYTES // 1024 // 1024} MB).")
        target = self._file(address, normalized)
        if target.is_dir():
            raise SiteError(f"{normalized} jest katalogiem.")
        self._check_capacity(address, target, len(data))
        _write_atomic(target, data)
        self.update_meta(address)
        return {"path": normalized, "size": len(data)}

    def write_text(self, address: str, path: str, content: str) -> dict[str, Any]:
        """Zapisuje plik tekstowy (HTML, CSS, JS…) w UTF-8."""
        normalized = check_file_path(path)
        if PurePosixPath(normalized).suffix.lower() not in TEXT_SUFFIXES:
            raise SiteError(
                f"{normalized}: treść tekstową zapisuj do plików {', '.join(sorted(TEXT_SUFFIXES))}."
            )
        data = content.encode("utf-8")
        if len(data) > MAX_TEXT_BYTES:
            raise SiteError("Plik tekstowy jest zbyt duży (limit 2 MB) – podziel go na mniejsze.")
        return self.write_bytes(address, normalized, data)

    def read_text(self, address: str, path: str) -> str:
        """Treść pliku tekstowego szkicu."""
        self.meta(address)
        target = self._file(address, check_file_path(path))
        if not target.is_file():
            raise SiteError(f"Plik {path!r} nie istnieje.")
        if target.suffix.lower() not in TEXT_SUFFIXES:
            raise SiteError(f"{path!r} nie jest plikiem tekstowym.")
        return target.read_text(encoding="utf-8", errors="replace")

    def list_files(self, address: str, published: bool = False) -> list[dict[str, Any]]:
        """Pliki strony: ścieżka, rozmiar, czas modyfikacji."""
        self.meta(address)
        base = self.published_dir(address) if published else self.draft_dir(address)
        files = []
        if base.is_dir():
            for item in sorted(base.rglob("*")):
                relative = item.relative_to(base).as_posix()
                if (
                    item.is_file()
                    and not item.is_symlink()
                    and not any(p.startswith(".") for p in relative.split("/"))
                ):
                    stat = item.stat()
                    modified = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(timespec="seconds")
                    files.append({"path": relative, "size": stat.st_size, "modified": modified})
        return files

    def delete_file(self, address: str, path: str) -> None:
        """Usuwa plik szkicu (i puste katalogi nad nim)."""
        self.meta(address)
        target = self._file(address, check_path(path))
        if not target.is_file():
            raise SiteError(f"Plik {path!r} nie istnieje.")
        target.unlink()
        base = self.draft_dir(address).resolve()
        parent = target.parent
        while parent != base and parent.is_relative_to(base) and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        self.update_meta(address)

    # --- wersje ----------------------------------------------------------------------------------

    def snapshot(self, address: str, note: str = "") -> dict[str, Any]:
        """Zapisuje migawkę szkicu jako nową wersję (najstarsze ponad limit są usuwane)."""
        meta = self.meta(address)
        number = int(meta.get("next_version", 1))
        version_id = f"v{number:04d}"
        target = self._versions_dir(address) / version_id
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(self.draft_dir(address), target, symlinks=False)
        size, count = _tree_size(target)
        entry = {
            "id": version_id,
            "created_at": now_iso(),
            "note": note.strip()[:300],
            "files": count,
            "size": size,
        }
        versions = [*meta.get("versions", []), entry]
        while len(versions) > MAX_VERSIONS:
            oldest = versions.pop(0)
            shutil.rmtree(self._versions_dir(address) / oldest["id"], ignore_errors=True)
        meta.update(versions=versions, next_version=number + 1)
        self._save_meta(address, meta)
        return entry

    def restore(self, address: str, version_id: str) -> dict[str, Any]:
        """Przywraca szkic z wersji; bieżący stan zapisuje wcześniej jako nową wersję."""
        meta = self.meta(address)
        if not any(item["id"] == version_id for item in meta.get("versions", [])):
            raise SiteError(f"Nie ma wersji {version_id!r}.")
        source = self._versions_dir(address) / version_id
        if not source.is_dir():
            raise SiteError(f"Pliki wersji {version_id!r} nie są dostępne.")
        self.snapshot(address, f"Przed przywróceniem {version_id}")
        draft = self.draft_dir(address)
        staging = draft.with_name(f".{draft.name}.przywracanie")
        shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(source, staging, symlinks=False)
        shutil.rmtree(draft)
        staging.rename(draft)
        return self.update_meta(address)

    # --- publikacja ------------------------------------------------------------------------------

    def request_publish(self, address: str, note: str = "") -> dict[str, Any]:
        """Prośba agenta o publikację – wymaga potwierdzenia użytkownika w interfejsie."""
        return self.update_meta(
            address, publish_request={"requested_at": now_iso(), "note": note.strip()[:500]}
        )

    def publish(self, address: str) -> dict[str, Any]:
        """Publikuje bieżący szkic (kopia zamrożona) i zapisuje go jako wersję."""
        self.meta(address)
        draft = self.draft_dir(address)
        if not (draft / "index.html").is_file():
            raise SiteError("Strona nie ma pliku index.html – nie ma czego opublikować.")
        target = self.published_dir(address)
        staging = target.with_name(f".{target.name}.nowa")
        shutil.rmtree(staging, ignore_errors=True)
        staging.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(draft, staging, symlinks=False)
        if target.exists():
            old = target.with_name(f".{target.name}.stara")
            shutil.rmtree(old, ignore_errors=True)
            target.rename(old)
            staging.rename(target)
            shutil.rmtree(old, ignore_errors=True)
        else:
            staging.rename(target)
        version = self.snapshot(address, "Publikacja")
        return self.update_meta(
            address, published_at=now_iso(), published_version=version["id"], publish_request=None
        )

    def unpublish(self, address: str) -> dict[str, Any]:
        """Wycofuje publikację (strona przestaje być dostępna publicznie)."""
        self.meta(address)
        shutil.rmtree(self.published_dir(address), ignore_errors=True)
        return self.update_meta(address, published_at=None, published_version=None, publish_request=None)


def site_store(settings: Any, owner: uuid.UUID | None = None) -> SiteStore:
    """Magazyn stron według ustawień aplikacji, zawężony do konta, gdy podano ``owner``."""
    return SiteStore(settings.data_dir / "strony", getattr(settings, "tworczy_site_max_mb", 200), owner)
