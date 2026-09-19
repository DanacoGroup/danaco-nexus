"""Narzędzia chmury osobistej (Nextcloud przez WebDAV): przeglądanie, pobieranie, zapis.

Nexus łączy się z Nextcloud na pętli zwrotnej hasłem aplikacji konta
właściciela (plik ``chmura_token_file``). Ścieżki w chmurze są względne
wobec katalogu głównego użytkownika i nie mogą wychodzić poza niego.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx
from pydantic import Field

from nexus.config import Settings
from nexus.storage import safe_filename
from nexus.tools.base import OutputFile, ToolContext, ToolError, ToolInput, ToolResult, registry
from nexus.tools.common import unique_name

DAV = "{DAV:}"
PROPFIND_BODY = """<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:prop><d:resourcetype/><d:getcontentlength/><d:getlastmodified/><d:getcontenttype/>
  <oc:size/></d:prop>
</d:propfind>"""
MAX_LIST_ENTRIES = 500
MAX_IMPORT_FILES = 200
MAX_IMPORT_BYTES = 8 * 1024**3
CHUNK = 1024 * 1024
TIMEOUT = httpx.Timeout(60.0, read=600.0, write=600.0)


class CloudNotConfigured(ToolError):
    """Chmura osobista nie jest skonfigurowana."""


def normalize_cloud_path(path: str) -> str:
    """Ścieżka w chmurze w postaci ``/a/b`` (bez ``..``, bez powtórzonych ukośników)."""
    parts = []
    for part in PurePosixPath("/" + (path or "").replace("\\", "/")).parts[1:]:
        if part in ("", "."):
            continue
        if part == "..":
            raise ToolError("Ścieżka w chmurze nie może zawierać „..”.")
        if any(ord(char) < 32 for char in part):
            raise ToolError("Ścieżka w chmurze zawiera niedozwolone znaki.")
        parts.append(part)
    return "/" + "/".join(parts)


class CloudClient:
    """Klient WebDAV konta Nextcloud właściciela."""

    def __init__(self, settings: Settings) -> None:
        token_file = settings.chmura_token_file
        try:
            token = token_file.read_text(encoding="utf-8").strip()
        except OSError:
            token = ""
        if not settings.chmura_url or not token:
            raise CloudNotConfigured(
                "Chmura osobista nie jest skonfigurowana (brak adresu Nextcloud lub hasła aplikacji)."
            )
        self.user = settings.chmura_user
        self.base = f"{settings.chmura_url.rstrip('/')}/remote.php/dav/files/{quote(self.user)}"
        self._root_path = urlsplit(self.base).path
        self.http = httpx.Client(auth=(self.user, token), timeout=TIMEOUT, follow_redirects=False)

    def close(self) -> None:
        self.http.close()

    def url(self, path: str) -> str:
        return self.base + quote(normalize_cloud_path(path))

    def _check(self, response: httpx.Response, action: str, path: str) -> None:
        if response.status_code == 401:
            raise ToolError("Chmura odrzuciła hasło aplikacji Nexusa (401).")
        if response.status_code == 404:
            raise ToolError(f"W chmurze nie ma: {path}")
        if response.status_code == 507:
            raise ToolError("Brak miejsca w chmurze.")
        if response.status_code >= 400:
            raise ToolError(f"Chmura: {action} {path} nie powiodło się (HTTP {response.status_code}).")

    def list(self, path: str) -> list[dict[str, Any]]:
        """Zawartość katalogu (bez rekursji)."""
        path = normalize_cloud_path(path)
        response = self.http.request(
            "PROPFIND",
            self.url(path),
            headers={"Depth": "1", "Content-Type": "application/xml"},
            content=PROPFIND_BODY,
        )
        self._check(response, "odczyt katalogu", path)
        entries = []
        for item in ET.fromstring(response.content).findall(f"{DAV}response"):
            href = unquote(item.findtext(f"{DAV}href", ""))
            relative = normalize_cloud_path(href.removeprefix(self._root_path))
            if relative == path:
                continue
            props = item.find(f"{DAV}propstat/{DAV}prop")
            if props is None:
                continue
            is_dir = props.find(f"{DAV}resourcetype/{DAV}collection") is not None
            size = props.findtext("{http://owncloud.org/ns}size") or props.findtext(f"{DAV}getcontentlength")
            modified = props.findtext(f"{DAV}getlastmodified")
            entries.append(
                {
                    "path": relative,
                    "name": PurePosixPath(relative).name,
                    "type": "folder" if is_dir else "file",
                    "size_bytes": int(size) if size and size.isdigit() else None,
                    "modified": _iso(modified),
                    "mime": None if is_dir else props.findtext(f"{DAV}getcontenttype"),
                }
            )
        entries.sort(key=lambda entry: (entry["type"] != "folder", entry["name"].lower()))
        return entries

    def is_folder(self, path: str) -> bool:
        response = self.http.request(
            "PROPFIND",
            self.url(path),
            headers={"Depth": "0", "Content-Type": "application/xml"},
            content=PROPFIND_BODY,
        )
        if response.status_code == 404:
            return False
        self._check(response, "odczyt", path)
        return b"collection" in response.content

    def download(self, ctx: ToolContext, path: str, target: Any) -> int:
        """Pobiera plik strumieniowo; zwraca liczbę bajtów."""
        written = 0
        with self.http.stream("GET", self.url(path)) as response:
            self._check(response, "pobranie", path)
            with open(target, "wb") as handle:
                for chunk in response.iter_bytes(CHUNK):
                    ctx.check_cancelled()
                    handle.write(chunk)
                    written += len(chunk)
                    if written > MAX_IMPORT_BYTES:
                        raise ToolError("Łączny rozmiar pobieranych plików przekracza 8 GB.")
        return written

    def ensure_folder(self, path: str) -> None:
        """Tworzy katalog (z nadrzędnymi), jeśli nie istnieje."""
        current = ""
        for part in normalize_cloud_path(path).split("/")[1:]:
            current += "/" + part
            response = self.http.request("MKCOL", self.url(current))
            if response.status_code not in (201, 405):
                self._check(response, "utworzenie katalogu", current)

    def upload(self, source: Any, path: str) -> None:
        with open(source, "rb") as handle:
            response = self.http.put(self.url(path), content=_chunks(handle))
        self._check(response, "zapis", path)


def _chunks(handle: Any) -> Any:
    while chunk := handle.read(CHUNK):
        yield chunk


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone().isoformat(timespec="minutes")
    except (TypeError, ValueError):
        return value


def _client(ctx: ToolContext) -> CloudClient:
    return CloudClient(ctx.settings)


class CloudBrowseInput(ToolInput):
    path: str = Field("/", description="Katalog w chmurze, np. '/', '/Dokumenty/Faktury 2026'.")


class CloudImportInput(ToolInput):
    paths: list[str] = Field(
        min_length=1,
        max_length=MAX_IMPORT_FILES,
        description="Pliki lub katalogi w chmurze do pobrania (katalogi bez podkatalogów).",
    )


class CloudSaveInput(ToolInput):
    file_ids: list[str] = Field(
        min_length=1, max_length=500, description="Pliki rozmowy do zapisania w chmurze."
    )
    folder: str = Field(
        "/Nexus",
        description="Katalog docelowy w chmurze (tworzony, jeśli nie istnieje), np. '/Dokumenty/Skany OCR'.",
    )
    overwrite: bool = Field(False, description="Nadpisz pliki o tej samej nazwie (domyślnie dopisz numer).")


@registry.register(
    "cloud_browse",
    """Wyświetla zawartość katalogu w chmurze osobistej użytkownika (Nextcloud): podkatalogi
i pliki z rozmiarem i datą zmiany. Użyj, gdy użytkownik odwołuje się do plików „w chmurze”
albo gdy trzeba wybrać katalog do zapisu wyników.""",
    CloudBrowseInput,
)
def cloud_browse(ctx: ToolContext, args: CloudBrowseInput) -> ToolResult:
    client = _client(ctx)
    try:
        path = normalize_cloud_path(args.path)
        entries = client.list(path)
    finally:
        client.close()
    shown = entries[:MAX_LIST_ENTRIES]
    folders = sum(entry["type"] == "folder" for entry in entries)
    data: dict[str, Any] = {"path": path, "entries": shown, "total": len(entries)}
    if len(entries) > len(shown):
        data["note"] = f"Pokazano {len(shown)} z {len(entries)} pozycji."
    return ToolResult(data, f"Chmura {path}: {folders} katalogów, {len(entries) - folders} plików")


@registry.register(
    "cloud_import",
    """Pobiera pliki z chmury osobistej do rozmowy (każdy plik dostaje file_id do dalszej
obróbki). Wskazanie katalogu pobiera wszystkie pliki z tego katalogu (bez podkatalogów).""",
    CloudImportInput,
)
def cloud_import(ctx: ToolContext, args: CloudImportInput) -> ToolResult:
    client = _client(ctx)
    outputs: list[OutputFile] = []
    used: set[str] = set()
    total = 0
    try:
        wanted: list[str] = []
        for raw in args.paths:
            path = normalize_cloud_path(raw)
            if path == "/" or client.is_folder(path):
                wanted.extend(entry["path"] for entry in client.list(path) if entry["type"] == "file")
            else:
                wanted.append(path)
        if len(wanted) > MAX_IMPORT_FILES:
            raise ToolError(f"Za dużo plików ({len(wanted)}); pobierz najwyżej {MAX_IMPORT_FILES} naraz.")
        for index, path in enumerate(wanted, 1):
            ctx.progress(f"Pobieranie z chmury {index}/{len(wanted)}: {PurePosixPath(path).name}")
            name = unique_name(safe_filename(PurePosixPath(path).name), used)
            used.add(name.lower())
            target = ctx.output_path(name)
            total += client.download(ctx, path, target)
            if total > MAX_IMPORT_BYTES:
                raise ToolError("Łączny rozmiar pobieranych plików przekracza 8 GB.")
            outputs.append(OutputFile(target, name, f"Z chmury: {path}"))
    finally:
        client.close()
    return ToolResult(
        {
            "imported": [
                {"cloud_path": o.description.removeprefix("Z chmury: "), "name": o.name} for o in outputs
            ]
        },
        f"Pobrano z chmury {len(outputs)} plików",
        files=outputs,
    )


@registry.register(
    "cloud_save",
    """Zapisuje pliki rozmowy (np. wyniki OCR, poprawione zdjęcia) w chmurze osobistej
użytkownika, we wskazanym katalogu. Pliki od razu są widoczne w Nextcloud i synchronizują
się na urządzenia użytkownika.""",
    CloudSaveInput,
)
def cloud_save(ctx: ToolContext, args: CloudSaveInput) -> ToolResult:
    client = _client(ctx)
    saved: list[str] = []
    try:
        folder = normalize_cloud_path(args.folder)
        client.ensure_folder(folder)
        existing = {entry["name"].lower() for entry in client.list(folder)} if not args.overwrite else set()
        for index, file_id in enumerate(args.file_ids, 1):
            ctx.check_cancelled()
            file = ctx.file(file_id)
            name = safe_filename(file.name)
            if not args.overwrite:
                name = unique_name(name, existing)
                existing.add(name.lower())
            ctx.progress(f"Zapis w chmurze {index}/{len(args.file_ids)}: {name}")
            target = normalize_cloud_path(f"{folder}/{name}")
            client.upload(file.path, target)
            saved.append(target)
    finally:
        client.close()
    data: dict[str, Any] = {"folder": folder, "saved": saved}
    if ctx.settings.chmura_public_url:
        data["folder_link"] = f"{ctx.settings.chmura_public_url.rstrip('/')}/apps/files/?dir={quote(folder)}"
    return ToolResult(data, f"Zapisano w chmurze {len(saved)} plików w {folder}")
