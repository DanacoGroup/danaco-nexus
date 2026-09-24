"""Chmura osobista dla modułu Cloud: asynchroniczny klient Nextcloud (WebDAV i OCS).

Uzupełnia klienta narzędzi agenta (``nexus.tools.cloud``) o operacje interfejsu:
przenoszenie, kosz, wersje, udostępnianie linkiem, ulubione, wyszukiwanie
i przesyłanie dużych plików kawałkami (chunked upload v2). Ścieżki są
normalizowane tą samą funkcją co w narzędziach i nie wychodzą poza konto.
"""

from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from datetime import date
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx

from nexus.chmura_konta import KontoChmury
from nexus.config import Settings
from nexus.db import ADMIN_OWNER
from nexus.tools.base import ToolError
from nexus.tools.cloud import KATALOG_KONT, _iso, katalog_konta, normalize_cloud_path

DAV = "{DAV:}"
OC = "{http://owncloud.org/ns}"
NC = "{http://nextcloud.org/ns}"
TIMEOUT = httpx.Timeout(60.0, read=600.0, write=600.0)
ENTRY_PROPS = """<d:prop><d:resourcetype/><d:getcontentlength/><d:getlastmodified/><d:getcontenttype/>
<d:getetag/><oc:size/><oc:fileid/><oc:favorite/><oc:permissions/><nc:has-preview/><oc:share-types/></d:prop>"""
PROPFIND_ENTRIES = f"""<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
{ENTRY_PROPS}</d:propfind>"""
PROPFIND_QUOTA = """<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:"><d:prop><d:quota-available-bytes/><d:quota-used-bytes/></d:prop></d:propfind>"""
PROPFIND_VERSIONS = """<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:" xmlns:nc="http://nextcloud.org/ns"><d:prop><d:getcontentlength/>
<d:getlastmodified/><d:getcontenttype/><nc:version-label/><nc:version-author/></d:prop></d:propfind>"""
PROPFIND_TRASH = """<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns"><d:prop>
<d:resourcetype/><d:getcontentlength/><oc:size/><nc:trashbin-filename/><nc:trashbin-original-location/>
<nc:trashbin-deletion-time/></d:prop></d:propfind>"""
REPORT_FAVORITES = f"""<?xml version="1.0"?>
<oc:filter-files xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
{ENTRY_PROPS}<oc:filter-rules><oc:favorite>1</oc:favorite></oc:filter-rules></oc:filter-files>"""
SEARCH_BODY = """<?xml version="1.0" encoding="UTF-8"?>
<d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
  <d:basicsearch>
    <d:select>{props}</d:select>
    <d:from><d:scope><d:href>{zakres}</d:href><d:depth>infinity</d:depth></d:scope></d:from>
    <d:where><d:like><d:prop><d:displayname/></d:prop><d:literal>%{term}%</d:literal></d:like></d:where>
    <d:orderby><d:order><d:prop><d:getlastmodified/></d:prop><d:descending/></d:order></d:orderby>
    <d:limit><d:nresults>{limit}</d:nresults></d:limit>
  </d:basicsearch>
</d:searchrequest>"""
UPLOAD_ID = re.compile(r"^nexus-[0-9a-f]{16,40}$")
MAX_CHUNKS = 10_000
SHARE_LINK = 3
SHARE_READ = 1
SHARE_UPLOAD_EDIT = 15


class CloudError(Exception):
    """Błąd chmury z kodem HTTP dla API."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def clean_path(path: str) -> str:
    """Znormalizowana ścieżka w chmurze (błąd – ``CloudError`` 400)."""
    try:
        return normalize_cloud_path(path)
    except ToolError as error:
        raise CloudError(400, str(error)) from error


def check_name(name: str) -> str:
    """Nazwa pliku lub folderu (bez ukośników i nazw zabronionych w Nextcloud)."""
    name = (name or "").strip()
    if not name or name in (".", "..") or "/" in name or "\\" in name or any(ord(c) < 32 for c in name):
        raise CloudError(400, "Nieprawidłowa nazwa.")
    if name.lower() == ".htaccess" or name.lower().endswith((".part", ".filepart")):
        raise CloudError(400, "Chmura nie pozwala na taką nazwę pliku.")
    if len(name) > 250:
        raise CloudError(400, "Nazwa jest za długa.")
    return name


class CloudService:
    """Klient Nextcloud instalacji, zawężony do przestrzeni jednego konta.

    Instalacja loguje się do Nextcloud jednym hasłem aplikacji — konta klientów nie mają
    tam własnych loginów. Rozdział robi więc ścieżka: korzeniem widocznym dla konta jest
    ``/Konta/<owner>``, a poza niego nie wychodzi ani listowanie, ani wyszukiwanie, ani
    zapis. Bez tego każdy tester widziałby pliki wszystkich pozostałych.
    """

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
        owner: uuid.UUID | None = None,
        konto: KontoChmury | None = None,
    ) -> None:
        try:
            token = settings.chmura_token_file.read_text(encoding="utf-8").strip()
        except OSError:
            token = ""
        if konto is not None:
            token = konto.haslo
        if not settings.chmura_url or not token:
            raise CloudError(
                503, "Chmura osobista nie jest skonfigurowana (brak adresu Nextcloud lub hasła aplikacji)."
            )
        # Konto z własnym kontem Nextcloud (plan z synchronizacją) pracuje w jego korzeniu;
        # pozostałe — w folderze /Konta/<owner> konta technicznego.
        self.user = konto.uid if konto is not None else settings.chmura_user
        self.owner = owner
        self.konto = konto
        self._przedrostek = "" if konto is not None else katalog_konta(owner)
        self.base_url = settings.chmura_url.rstrip("/")
        self.public_url = (settings.chmura_public_url or "").rstrip("/")
        self.dav = f"{self.base_url}/remote.php/dav"
        przedrostek = quote(self._przedrostek)
        self.files_root = f"{self.dav}/files/{quote(self.user)}{przedrostek}"
        self._files_path = urlsplit(self.files_root).path
        self._zakres_szukania = f"/files/{quote(self.user)}{przedrostek}"
        self.http = httpx.AsyncClient(
            auth=(self.user, token), timeout=TIMEOUT, follow_redirects=False, transport=transport
        )

    async def przygotuj_przestrzen(self) -> None:
        """Zakłada folder konta, gdy jeszcze go nie ma (pierwsze wejście do chmury)."""
        if self.owner is None or self.konto is not None:
            return
        for sciezka in (f"{self.dav}/files/{quote(self.user)}/{quote(KATALOG_KONT)}", self.files_root):
            response = await self.http.request("MKCOL", sciezka)
            # 405 znaczy „już jest” — to nie błąd, tylko drugie wejście tego samego konta.
            if response.status_code >= 400 and response.status_code != 405:
                self._check(response, "przygotowanie przestrzeni konta")

    async def close(self) -> None:
        await self.http.aclose()

    async def __aenter__(self) -> CloudService:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    # --- pomocnicze ---

    def url(self, path: str) -> str:
        """Adres WebDAV pliku lub folderu."""
        return self.files_root + quote(clean_path(path))

    def sciezka_konta(self, path: str) -> str:
        """Ścieżka liczona od korzenia konta Nextcloud — tego oczekuje API udostępnień.

        WebDAV adresujemy pełnym adresem (``files_root`` zawiera już folder konta), ale
        OCS przyjmuje samą ścieżkę, więc przedrostek trzeba dołożyć tutaj.
        """
        return f"{self._przedrostek}{clean_path(path)}" or "/"

    def sciezka_wzgledna(self, path: str) -> str:
        """Odwrotność :meth:`sciezka_konta` — ścieżka pokazywana użytkownikowi."""
        przedrostek = self._przedrostek
        if przedrostek and path.startswith(przedrostek):
            return normalize_cloud_path(path.removeprefix(przedrostek))
        return path

    def _check(self, response: httpx.Response, action: str, path: str = "") -> None:
        code = response.status_code
        if code < 400:
            return
        where = f" {path}" if path else ""
        if code == 401:
            raise CloudError(502, "Chmura odrzuciła hasło aplikacji Nexusa.")
        if code == 404:
            raise CloudError(404, f"W chmurze nie ma{where or ' takiego elementu'}.")
        if code in (409, 412):
            raise CloudError(
                409, f"Chmura: {action}{where} – konflikt (element już istnieje lub brak folderu)."
            )
        if code == 403:
            raise CloudError(403, f"Chmura: {action}{where} – brak uprawnień lub niedozwolona nazwa.")
        if code == 423:
            # Blokada przy odczycie katalogu nie jest „plikiem używanym w innej aplikacji”:
            # Nextcloud trzyma ją przez chwilę także wtedy, gdy sam zakłada albo skanuje
            # przestrzeń świeżego konta. Komunikat o zablokowanym pliku wyskakiwał wtedy
            # na pustym module i wyglądał jak awaria.
            if action == "odczyt":
                raise CloudError(423, "Chmura jest zajęta porządkowaniem tej przestrzeni. Odśwież za chwilę.")
            raise CloudError(423, f"Plik{where} jest zablokowany (używany w innej aplikacji).")
        if code == 507:
            raise CloudError(507, "Brak miejsca w chmurze.")
        raise CloudError(502, f"Chmura: {action}{where} nie powiodło się (HTTP {code}).")

    async def _propfind(self, url: str, body: str, depth: str = "1") -> ET.Element:
        response = await self.http.request(
            "PROPFIND",
            url,
            headers={"Depth": depth, "Content-Type": "application/xml; charset=utf-8"},
            content=body,
        )
        self._check(response, "odczyt")
        return ET.fromstring(response.content)

    def _relative(self, href: str) -> str | None:
        path = unquote(urlsplit(href).path)
        if not path.startswith(self._files_path):
            return None
        return normalize_cloud_path(path.removeprefix(self._files_path))

    def _entry(self, item: ET.Element) -> dict[str, Any] | None:
        relative = self._relative(item.findtext(f"{DAV}href", ""))
        props = item.find(f"{DAV}propstat/{DAV}prop")
        if relative is None or props is None:
            return None
        is_dir = props.find(f"{DAV}resourcetype/{DAV}collection") is not None
        size = props.findtext(f"{OC}size") or props.findtext(f"{DAV}getcontentlength")
        fileid = props.findtext(f"{OC}fileid")
        share_types = [
            int(t.text) for t in props.findall(f"{OC}share-types/{OC}share-type") if (t.text or "").isdigit()
        ]
        return {
            "path": relative,
            "name": PurePosixPath(relative).name or "/",
            "type": "folder" if is_dir else "file",
            "size": int(size) if size and size.isdigit() else None,
            "modified": _iso(props.findtext(f"{DAV}getlastmodified")),
            "mime": None if is_dir else props.findtext(f"{DAV}getcontenttype"),
            "etag": (props.findtext(f"{DAV}getetag") or "").strip('"'),
            "fileid": int(fileid) if fileid and fileid.isdigit() else None,
            "favorite": (props.findtext(f"{OC}favorite") or "0") == "1",
            "permissions": props.findtext(f"{OC}permissions") or "",
            "has_preview": (props.findtext(f"{NC}has-preview") or "") == "true",
            "shared_link": SHARE_LINK in share_types,
            "shared": bool(share_types),
        }

    @staticmethod
    def _sort(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(entries, key=lambda entry: (entry["type"] != "folder", entry["name"].lower()))

    # --- przeglądanie ---

    async def list(self, path: str) -> dict[str, Any]:
        """Folder: opis samego folderu i jego zawartość (bez rekursji)."""
        path = clean_path(path)
        root = await self._propfind(self.url(path), PROPFIND_ENTRIES)
        entries = [entry for item in root.findall(f"{DAV}response") if (entry := self._entry(item))]
        current = next((entry for entry in entries if entry["path"] == path), None)
        if current is not None and current["type"] != "folder":
            raise CloudError(400, f"{path} nie jest folderem.")
        children = [entry for entry in entries if entry["path"] != path]
        return {"path": path, "folder": current, "entries": self._sort(children)}

    async def stat(self, path: str) -> dict[str, Any]:
        """Opis jednego pliku lub folderu."""
        path = clean_path(path)
        root = await self._propfind(self.url(path), PROPFIND_ENTRIES, depth="0")
        for item in root.findall(f"{DAV}response"):
            entry = self._entry(item)
            if entry:
                return entry
        raise CloudError(404, f"W chmurze nie ma {path}.")

    async def exists(self, path: str) -> bool:
        try:
            await self.stat(path)
        except CloudError as error:
            if error.status == 404:
                return False
            raise
        return True

    async def quota(self) -> dict[str, int | None]:
        """Zajęte i wolne miejsce na koncie (bajty; ``None`` = bez limitu)."""
        root = await self._propfind(self.url("/"), PROPFIND_QUOTA, depth="0")
        props = root.find(f"{DAV}response/{DAV}propstat/{DAV}prop")
        used = props.findtext(f"{DAV}quota-used-bytes") if props is not None else None
        free = props.findtext(f"{DAV}quota-available-bytes") if props is not None else None

        def number(value: str | None) -> int | None:
            return int(value) if value and value.lstrip("-").isdigit() and int(value) >= 0 else None

        return {"used": number(used), "available": number(free)}

    async def search(self, term: str, limit: int = 100) -> list[dict[str, Any]]:
        """Pliki i foldery, których nazwa zawiera ``term`` (od najnowszych)."""
        term = term.strip()
        if len(term) < 2:
            raise CloudError(400, "Wpisz co najmniej 2 znaki.")
        escaped = term.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        props = ENTRY_PROPS.removeprefix("<d:prop>").removesuffix("</d:prop>")
        body = SEARCH_BODY.format(
            props=f"<d:prop>{props}</d:prop>", zakres=self._zakres_szukania, term=escaped, limit=limit
        )
        response = await self.http.request(
            "SEARCH", f"{self.dav}/", headers={"Content-Type": "text/xml; charset=utf-8"}, content=body
        )
        self._check(response, "wyszukiwanie")
        root = ET.fromstring(response.content)
        return [
            entry
            for item in root.findall(f"{DAV}response")
            if (entry := self._entry(item)) and entry["path"] != "/"
        ]

    async def favorites(self) -> list[dict[str, Any]]:
        """Ulubione pliki i foldery."""
        response = await self.http.request(
            "REPORT",
            self.url("/"),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            content=REPORT_FAVORITES,
        )
        self._check(response, "ulubione")
        root = ET.fromstring(response.content)
        return self._sort([entry for item in root.findall(f"{DAV}response") if (entry := self._entry(item))])

    async def set_favorite(self, path: str, favorite: bool) -> None:
        body = (
            '<?xml version="1.0"?><d:propertyupdate xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
            f"<d:set><d:prop><oc:favorite>{1 if favorite else 0}</oc:favorite></d:prop></d:set>"
            "</d:propertyupdate>"
        )
        response = await self.http.request(
            "PROPPATCH",
            self.url(path),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            content=body,
        )
        self._check(response, "ulubione", path)

    # --- pobieranie i podgląd ---

    async def open_download(self, path: str, version_url: str | None = None) -> httpx.Response:
        """Otwarta odpowiedź strumieniowa (wywołujący zamyka ją ``aclose``)."""
        # Bez kompresji: strumień trafia do przeglądarki bajt w bajt (z Content-Length).
        request = self.http.build_request(
            "GET", version_url or self.url(path), headers={"Accept-Encoding": "identity"}
        )
        response = await self.http.send(request, stream=True)
        if response.status_code >= 400:
            await response.aclose()
            self._check(response, "pobranie", path)
        return response

    async def preview(self, fileid: int, size: int) -> tuple[bytes, str] | None:
        """Miniatura pliku z Nextcloud (``None``, gdy chmura jej nie ma)."""
        response = await self.http.get(
            f"{self.base_url}/index.php/core/preview",
            params={"fileId": fileid, "x": size, "y": size, "a": "1", "mode": "cover"},
        )
        if response.status_code != 200 or not response.headers.get("content-type", "").startswith("image/"):
            return None
        return response.content, response.headers["content-type"]

    # --- zmiany ---

    async def mkdir(self, path: str) -> dict[str, Any]:
        path = clean_path(path)
        if path == "/":
            raise CloudError(400, "Nieprawidłowa nazwa folderu.")
        check_name(PurePosixPath(path).name)
        response = await self.http.request("MKCOL", self.url(path))
        if response.status_code == 405:
            raise CloudError(409, f"{PurePosixPath(path).name} już istnieje.")
        self._check(response, "utworzenie folderu", path)
        return await self.stat(path)

    async def _move_or_copy(self, method: str, source: str, target: str, overwrite: bool) -> None:
        source, target = clean_path(source), clean_path(target)
        if source == "/" or target == "/":
            raise CloudError(400, "Nie można przenieść katalogu głównego.")
        if target == source or target.startswith(source.rstrip("/") + "/"):
            raise CloudError(400, "Nie można przenieść folderu do niego samego.")
        response = await self.http.request(
            method,
            self.url(source),
            headers={"Destination": self.url(target), "Overwrite": "T" if overwrite else "F"},
        )
        if response.status_code == 412:
            raise CloudError(409, f"W miejscu docelowym jest już {PurePosixPath(target).name}.")
        self._check(response, "przeniesienie" if method == "MOVE" else "kopiowanie", source)

    async def move(self, source: str, target: str, overwrite: bool = False) -> None:
        await self._move_or_copy("MOVE", source, target, overwrite)

    async def copy(self, source: str, target: str, overwrite: bool = False) -> None:
        await self._move_or_copy("COPY", source, target, overwrite)

    async def delete(self, path: str) -> None:
        """Usuwa plik lub folder (Nextcloud przenosi go do kosza)."""
        path = clean_path(path)
        if path == "/":
            raise CloudError(400, "Nie można usunąć katalogu głównego.")
        response = await self.http.request("DELETE", self.url(path))
        self._check(response, "usunięcie", path)

    # --- kosz ---

    def _kosz_konta(self) -> str:
        """Przedrostek kosza, do którego zawęża się konto klienta (pusty = cały kosz).

        Kosz Nextcloud jest jeden dla konta technicznego. Bez zawężenia klient widział
        nazwy i ścieżki plików usuniętych przez właściciela i inne konta, i mógł je
        przywrócić. Właściciel instalacji widzi kosz w całości, jak w samej chmurze.
        """
        if self.owner is None or self.owner == ADMIN_OWNER or self.konto is not None:
            return ""
        return katalog_konta(self.owner).lstrip("/") + "/"

    async def trash(self) -> list[dict[str, Any]]:
        """Elementy w koszu (od ostatnio usuniętych), tylko z przestrzeni konta."""
        zakres = self._kosz_konta()
        url = f"{self.dav}/trashbin/{quote(self.user)}/trash"
        root = await self._propfind(url, PROPFIND_TRASH)
        base = urlsplit(url).path.rstrip("/")
        result = []
        for item in root.findall(f"{DAV}response"):
            href = unquote(urlsplit(item.findtext(f"{DAV}href", "")).path).rstrip("/")
            if href == base:
                continue
            props = item.find(f"{DAV}propstat/{DAV}prop")
            if props is None:
                continue
            size = props.findtext(f"{OC}size") or props.findtext(f"{DAV}getcontentlength")
            deleted = props.findtext(f"{NC}trashbin-deletion-time")
            polozenie = (props.findtext(f"{NC}trashbin-original-location") or "").lstrip("/")
            if zakres and not polozenie.startswith(zakres):
                continue
            result.append(
                {
                    "id": href.rsplit("/", 1)[-1],
                    "name": props.findtext(f"{NC}trashbin-filename") or href.rsplit("/", 1)[-1],
                    "original": "/" + polozenie.removeprefix(zakres),
                    "type": "folder"
                    if props.find(f"{DAV}resourcetype/{DAV}collection") is not None
                    else "file",
                    "size": int(size) if size and size.isdigit() else None,
                    "deleted": int(deleted) if deleted and deleted.isdigit() else None,
                }
            )
        result.sort(key=lambda entry: entry["deleted"] or 0, reverse=True)
        return result

    async def restore_trash(self, item_id: str) -> None:
        if not item_id or "/" in item_id or item_id in (".", ".."):
            raise CloudError(400, "Nieprawidłowy element kosza.")
        if self._kosz_konta() and item_id not in {element["id"] for element in await self.trash()}:
            raise CloudError(404, "W koszu nie ma takiego elementu.")
        base = f"{self.dav}/trashbin/{quote(self.user)}"
        response = await self.http.request(
            "MOVE",
            f"{base}/trash/{quote(item_id)}",
            headers={"Destination": f"{base}/restore/{quote(item_id)}"},
        )
        self._check(response, "przywrócenie z kosza")

    # --- wersje ---

    async def _fileid(self, path: str) -> int:
        entry = await self.stat(path)
        if entry["type"] != "file" or entry["fileid"] is None:
            raise CloudError(400, "Wersje mają tylko pliki.")
        return entry["fileid"]

    def _version_url(self, fileid: int, version: str = "") -> str:
        base = f"{self.dav}/versions/{quote(self.user)}/versions/{fileid}"
        if version:
            if not version.isdigit():
                raise CloudError(400, "Nieprawidłowa wersja.")
            return f"{base}/{version}"
        return base

    async def versions(self, path: str) -> list[dict[str, Any]]:
        """Poprzednie wersje pliku (od najnowszej)."""
        fileid = await self._fileid(path)
        root = await self._propfind(self._version_url(fileid), PROPFIND_VERSIONS)
        result = []
        for item in root.findall(f"{DAV}response"):
            version = unquote(urlsplit(item.findtext(f"{DAV}href", "")).path).rstrip("/").rsplit("/", 1)[-1]
            if not version.isdigit() or version == str(fileid):
                continue
            props = item.find(f"{DAV}propstat/{DAV}prop")
            size = props.findtext(f"{DAV}getcontentlength") if props is not None else None
            result.append(
                {
                    "id": version,
                    "modified": _iso(props.findtext(f"{DAV}getlastmodified")) if props is not None else None,
                    "size": int(size) if size and size.isdigit() else None,
                    "label": (props.findtext(f"{NC}version-label") if props is not None else "") or "",
                    "author": (props.findtext(f"{NC}version-author") if props is not None else "") or "",
                }
            )
        result.sort(key=lambda entry: int(entry["id"]), reverse=True)
        return result

    async def version_url(self, path: str, version: str) -> str:
        return self._version_url(await self._fileid(path), version)

    async def restore_version(self, path: str, version: str) -> None:
        """Przywraca wersję (bieżąca zawartość staje się kolejną wersją)."""
        url = await self.version_url(path, version)
        response = await self.http.request(
            "MOVE", url, headers={"Destination": f"{self.dav}/versions/{quote(self.user)}/restore/target"}
        )
        self._check(response, "przywrócenie wersji", path)

    # --- udostępnianie linkiem (OCS) ---

    async def _ocs(self, method: str, suffix: str = "", **kwargs: Any) -> Any:
        response = await self.http.request(
            method,
            f"{self.base_url}/ocs/v2.php/apps/files_sharing/api/v1/shares{suffix}",
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            **kwargs,
        )
        try:
            payload = response.json()["ocs"]
        except (ValueError, KeyError, TypeError) as error:
            self._check(response, "udostępnianie")
            raise CloudError(502, "Chmura zwróciła nieoczekiwaną odpowiedź udostępniania.") from error
        meta = payload.get("meta", {})
        if response.status_code >= 400 or meta.get("status") != "ok":
            message = meta.get("message") or f"HTTP {response.status_code}"
            code = 404 if response.status_code == 404 else 400
            raise CloudError(code, f"Udostępnianie: {message}")
        return payload.get("data")

    def _share(self, data: dict[str, Any]) -> dict[str, Any]:
        token = data.get("token") or ""
        url = data.get("url") or ""
        if self.public_url and token:
            url = f"{self.public_url}/s/{token}"
        expiration = (data.get("expiration") or "")[:10] or None
        return {
            "id": str(data.get("id")),
            "url": url,
            "token": token,
            "path": self.sciezka_wzgledna(str(data.get("path") or "")),
            "expires": expiration,
            "has_password": bool(data.get("password") or data.get("share_with")),
            "permissions": int(data.get("permissions") or 1),
            "label": data.get("label") or "",
            "created": data.get("stime"),
        }

    async def shares(self, path: str) -> list[dict[str, Any]]:
        """Linki publiczne do pliku lub folderu."""
        data = await self._ocs(
            "GET", params={"path": self.sciezka_konta(path), "reshares": "false", "subfiles": "false"}
        )
        return [self._share(item) for item in data or [] if int(item.get("share_type", -1)) == SHARE_LINK]

    async def create_share(
        self,
        path: str,
        password: str | None = None,
        expires: date | None = None,
        allow_upload: bool = False,
        label: str = "",
    ) -> dict[str, Any]:
        """Tworzy link publiczny (tylko do odczytu albo z wgrywaniem dla folderu)."""
        form: dict[str, str] = {
            "path": self.sciezka_konta(path),
            "shareType": str(SHARE_LINK),
            "permissions": str(SHARE_UPLOAD_EDIT if allow_upload else SHARE_READ),
        }
        if password:
            form["password"] = password
        if expires:
            form["expireDate"] = expires.isoformat()
        if label:
            form["label"] = label[:250]
        return self._share(await self._ocs("POST", data=form))

    async def update_share(
        self,
        share_id: str,
        password: str | None = None,
        expires: date | None | str = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        """Zmienia hasło (``""`` usuwa), datę wygaśnięcia (``""`` usuwa) albo etykietę linku."""
        if not share_id.isdigit():
            raise CloudError(400, "Nieprawidłowy identyfikator udostępnienia.")
        result: dict[str, Any] | None = None
        changes: list[dict[str, str]] = []
        if password is not None:
            changes.append({"password": password})
        if expires is not None:
            changes.append({"expireDate": expires.isoformat() if isinstance(expires, date) else ""})
        if label is not None:
            changes.append({"label": label[:250]})
        for change in changes:
            result = await self._ocs("PUT", f"/{share_id}", data=change)
        if result is None:
            result = await self._ocs("GET", f"/{share_id}")
            result = result[0] if isinstance(result, list) and result else result
        return self._share(result or {})

    async def delete_share(self, share_id: str) -> None:
        if not share_id.isdigit():
            raise CloudError(400, "Nieprawidłowy identyfikator udostępnienia.")
        await self._ocs("DELETE", f"/{share_id}")

    # --- przesyłanie ---

    async def put(self, path: str, stream: AsyncIterator[bytes] | bytes, length: int | None) -> None:
        """Zapisuje plik jednym żądaniem (nadpisanie tworzy nową wersję)."""
        path = clean_path(path)
        check_name(PurePosixPath(path).name)
        headers = {"Content-Length": str(length)} if length is not None else {}
        response = await self.http.put(self.url(path), content=stream, headers=headers)
        self._check(response, "zapis", path)

    def _upload_url(self, upload_id: str, part: str = "") -> str:
        if not UPLOAD_ID.fullmatch(upload_id):
            raise CloudError(400, "Nieprawidłowy identyfikator przesyłania.")
        url = f"{self.dav}/uploads/{quote(self.user)}/{upload_id}"
        return f"{url}/{part}" if part else url

    async def upload_start(self, upload_id: str, path: str) -> None:
        """Zakłada katalog przesyłania kawałkami (chunked upload v2)."""
        path = clean_path(path)
        check_name(PurePosixPath(path).name)
        response = await self.http.request(
            "MKCOL", self._upload_url(upload_id), headers={"Destination": self.url(path)}
        )
        self._check(response, "rozpoczęcie przesyłania", path)

    async def upload_chunk(
        self, upload_id: str, number: int, path: str, stream: AsyncIterator[bytes] | bytes, length: int | None
    ) -> None:
        if not 1 <= number <= MAX_CHUNKS:
            raise CloudError(400, "Nieprawidłowy numer kawałka.")
        headers = {"Destination": self.url(path)}
        if length is not None:
            headers["Content-Length"] = str(length)
        response = await self.http.put(
            self._upload_url(upload_id, f"{number:05d}"), content=stream, headers=headers
        )
        self._check(response, "przesyłanie kawałka", path)

    async def upload_finish(
        self, upload_id: str, path: str, total: int, mtime: int | None = None
    ) -> dict[str, Any]:
        """Składa kawałki w plik docelowy."""
        headers = {"Destination": self.url(path), "OC-Total-Length": str(total), "Overwrite": "T"}
        if mtime:
            headers["X-OC-Mtime"] = str(mtime)
        response = await self.http.request("MOVE", self._upload_url(upload_id, ".file"), headers=headers)
        self._check(response, "złożenie pliku", path)
        return await self.stat(path)

    async def upload_abort(self, upload_id: str) -> None:
        response = await self.http.request("DELETE", self._upload_url(upload_id))
        if response.status_code not in (404,):
            self._check(response, "anulowanie przesyłania")
