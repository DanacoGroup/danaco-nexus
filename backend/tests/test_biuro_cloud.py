"""Testy modułu Cloud: API na atrapie Nextcloud (WebDAV, chunked upload, OCS) i prawdziwy Nextcloud."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import httpx
import pytest
from biuro_pomoc import HEADERS, api, biuro_settings  # noqa: F401
from fastapi.testclient import TestClient

from nexus.cloud_service import CloudError, CloudService, check_name
from nexus.config import Settings

TOKEN_FILE = os.environ.get("NEXUS_TEST_CHMURA_TOKEN_FILE", "")
CHMURA_URL = os.environ.get("NEXUS_TEST_CHMURA_URL", "http://127.0.0.1:8940")
FILES = "/remote.php/dav/files/admin"
UPLOADS = "/remote.php/dav/uploads/admin/"


class FakeNextcloud:
    """Pliki w pamięci obsługiwane przez httpx.MockTransport (podzbiór WebDAV i OCS Nextcloud)."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.folders: set[str] = {"/"}
        self.uploads: dict[str, dict[str, bytes]] = {}
        self.upload_targets: dict[str, str] = {}
        self.shares: dict[int, dict[str, object]] = {}
        self.favorites: set[str] = set()
        self.requests: list[tuple[str, str]] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    @staticmethod
    def _path(url_path: str) -> str:
        return "/" + unquote(url_path).removeprefix(FILES).strip("/")

    def _destination(self, request: httpx.Request) -> str:
        return self._path(urlsplit(request.headers["destination"]).path)

    def _entry(self, path: str) -> str:
        folder = path in self.folders
        href = FILES + quote(path if path == "/" else path + ("/" if folder else ""))
        size = len(self.files.get(path, b""))
        kind = "<d:collection/>" if folder else ""
        mime = "" if folder else "<d:getcontenttype>text/plain</d:getcontenttype>"
        return (
            f"<d:response><d:href>{href}</d:href><d:propstat><d:prop><d:resourcetype>{kind}</d:resourcetype>"
            f"<d:getlastmodified>Fri, 18 Sep 2026 10:00:00 GMT</d:getlastmodified>{mime}"
            f"<oc:size>{size}</oc:size><oc:fileid>{abs(hash(path)) % 10**6}</oc:fileid>"
            f'<oc:favorite>{int(path in self.favorites)}</oc:favorite><d:getetag>"e{size}"</d:getetag>'
            "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        )

    def _multistatus(self, paths: list[str]) -> httpx.Response:
        body = (
            '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" '
            'xmlns:nc="http://nextcloud.org/ns">'
            + "".join(self._entry(p) for p in paths)
            + "</d:multistatus>"
        )
        return httpx.Response(207, content=body.encode("utf-8"))

    def _children(self, path: str) -> list[str]:
        prefix = path.rstrip("/") + "/"
        items = [p for p in [*self.folders, *self.files] if p != path and p.startswith(prefix)]
        return [p for p in items if "/" not in p.removeprefix(prefix)]

    def handle(self, request: httpx.Request) -> httpx.Response:
        url_path = request.url.raw_path.decode("ascii").split("?")[0]
        self.requests.append((request.method, unquote(url_path)))
        if url_path.startswith("/ocs/"):
            return self._ocs(request, url_path)
        if url_path.startswith(UPLOADS):
            return self._upload(request, unquote(url_path.removeprefix(UPLOADS)))
        if url_path.startswith("/index.php/core/preview"):
            return httpx.Response(200, content=b"\xff\xd8JPEG", headers={"content-type": "image/jpeg"})
        path = self._path(url_path)
        method = request.method
        exists = path in self.files or path in self.folders
        if method == "PROPFIND":
            if not exists:
                return httpx.Response(404)
            depth = request.headers.get("depth", "1")
            return self._multistatus(
                [path] + (self._children(path) if depth == "1" and path in self.folders else [])
            )
        if method == "REPORT":
            return self._multistatus(sorted(self.favorites))
        if method == "PROPPATCH":
            if b"<oc:favorite>1" in request.content:
                self.favorites.add(path)
            else:
                self.favorites.discard(path)
            return httpx.Response(207)
        if method == "GET":
            if path not in self.files:
                return httpx.Response(404)
            data = self.files[path]
            return httpx.Response(
                200, content=data, headers={"content-type": "text/plain", "content-length": str(len(data))}
            )
        if method == "PUT":
            if str(Path(path).parent.as_posix()) not in self.folders:
                return httpx.Response(409)
            self.files[path] = request.read()
            return httpx.Response(201)
        if method == "MKCOL":
            if exists:
                return httpx.Response(405)
            self.folders.add(path)
            return httpx.Response(201)
        if method in ("MOVE", "COPY"):
            target = self._destination(request)
            if not exists:
                return httpx.Response(404)
            if (target in self.files or target in self.folders) and request.headers.get("overwrite") == "F":
                return httpx.Response(412)
            if path in self.files:
                self.files[target] = self.files[path]
                if method == "MOVE":
                    del self.files[path]
            else:
                self.folders.add(target)
                if method == "MOVE":
                    self.folders.discard(path)
            return httpx.Response(201)
        if method == "DELETE":
            if not exists:
                return httpx.Response(404)
            self.files.pop(path, None)
            self.folders.discard(path)
            return httpx.Response(204)
        return httpx.Response(405)

    def _upload(self, request: httpx.Request, relative: str) -> httpx.Response:
        upload_id, _, part = relative.partition("/")
        if request.method == "MKCOL":
            self.uploads[upload_id] = {}
            self.upload_targets[upload_id] = self._destination(request)
            return httpx.Response(201)
        if upload_id not in self.uploads:
            return httpx.Response(404)
        if request.method in ("PUT", "MOVE"):
            assert self._destination(request) == self.upload_targets[upload_id], "Destination przy PUT i MOVE"
        if request.method == "PUT":
            self.uploads[upload_id][part] = request.read()
            return httpx.Response(201)
        if request.method == "MOVE" and part == ".file":
            data = b"".join(self.uploads[upload_id][name] for name in sorted(self.uploads[upload_id]))
            assert int(request.headers["oc-total-length"]) == len(data)
            self.files[self._destination(request)] = data
            del self.uploads[upload_id]
            return httpx.Response(201)
        if request.method == "DELETE":
            del self.uploads[upload_id]
            return httpx.Response(204)
        return httpx.Response(405)

    def _ocs(self, request: httpx.Request, url_path: str) -> httpx.Response:
        assert request.headers["ocs-apirequest"] == "true"

        def ok(data: object) -> httpx.Response:
            return httpx.Response(
                200, json={"ocs": {"meta": {"status": "ok", "statuscode": 200}, "data": data}}
            )

        share_id = url_path.rsplit("/", 1)[-1]
        if request.method == "GET":
            path = request.url.params.get("path")
            return ok([share for share in self.shares.values() if share["path"] == path])
        if request.method == "POST":
            form = dict(httpx.QueryParams(request.content.decode()))
            if form["path"] not in self.files and form["path"] not in self.folders:
                return httpx.Response(
                    404, json={"ocs": {"meta": {"status": "failure", "message": "Wrong path"}}}
                )
            new_id = len(self.shares) + 1
            share = {
                "id": new_id,
                "share_type": 3,
                "path": form["path"],
                "token": f"tok{new_id}",
                "url": f"https://127.0.0.1:8940/s/tok{new_id}",
                "permissions": int(form["permissions"]),
                "expiration": f"{form['expireDate']} 00:00:00" if form.get("expireDate") else None,
                "password": "***" if form.get("password") else None,
                "label": form.get("label", ""),
            }
            self.shares[new_id] = share
            return ok(share)
        if request.method == "PUT":
            share = self.shares[int(share_id)]
            form = dict(httpx.QueryParams(request.content.decode()))
            if "password" in form:
                share["password"] = "***" if form["password"] else None
            if "expireDate" in form:
                share["expiration"] = f"{form['expireDate']} 00:00:00" if form["expireDate"] else None
            return ok(share)
        if request.method == "DELETE":
            self.shares.pop(int(share_id), None)
            return ok([])
        return httpx.Response(405)


@pytest.fixture
def cloud(api: TestClient) -> FakeNextcloud:  # noqa: F811
    fake = FakeNextcloud()
    api.app.state.cloud_transport = fake.transport()
    return fake


def test_check_name() -> None:
    assert check_name(" Raport 2026.pdf ") == "Raport 2026.pdf"
    for bad in ("", "..", "a/b", "plik.part", ".htaccess", "x" * 300, "a\x01"):
        with pytest.raises(CloudError):
            check_name(bad)


def test_requires_login_and_configuration(biuro_settings: Settings, tmp_path: Path) -> None:  # noqa: F811
    from nexus.api.app import create_app

    with TestClient(create_app(biuro_settings)) as anonymous:
        assert anonymous.get("/api/cloud/lista").status_code == 401
    biuro_settings.chmura_token_file = tmp_path / "brak"
    with pytest.raises(CloudError, match="nie jest skonfigurowana"):
        CloudService(biuro_settings)


def test_browse_folders_and_files(api: TestClient, cloud: FakeNextcloud) -> None:  # noqa: F811
    assert api.post("/api/cloud/folder", json={"path": "/Dokumenty"}).status_code == 403, "CSRF"
    created = api.post("/api/cloud/folder", json={"path": "/Dokumenty"}, headers=HEADERS)
    assert created.status_code == 201 and created.json()["type"] == "folder"
    assert api.post("/api/cloud/folder", json={"path": "/Dokumenty"}, headers=HEADERS).status_code == 409
    upload = api.put(
        "/api/cloud/plik", params={"path": "/Dokumenty/Notatka żółta.txt"}, content=b"Tekst", headers=HEADERS
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["size"] == 5
    listing = api.get("/api/cloud/lista", params={"path": "/Dokumenty"}).json()
    assert listing["path"] == "/Dokumenty"
    assert [(e["name"], e["type"]) for e in listing["entries"]] == [("Notatka żółta.txt", "file")]
    root = api.get("/api/cloud/lista").json()
    assert [e["name"] for e in root["entries"]] == ["Dokumenty"]
    assert api.get("/api/cloud/lista", params={"path": "/../etc"}).status_code == 400
    assert api.get("/api/cloud/lista", params={"path": "/Brak"}).status_code == 404

    download = api.get("/api/cloud/pobierz", params={"path": "/Dokumenty/Notatka żółta.txt"})
    assert download.content == b"Tekst"
    assert download.headers["content-type"] == "application/octet-stream"
    assert "filename*=UTF-8''Notatka%20%C5%BC%C3%B3%C5%82ta.txt" in download.headers["content-disposition"]
    inline = api.get("/api/cloud/pobierz", params={"path": "/Dokumenty/Notatka żółta.txt", "inline": 1})
    assert inline.headers["content-type"].startswith("text/plain")
    assert inline.headers["x-frame-options"] == "SAMEORIGIN"
    assert download.headers["x-frame-options"] == "DENY"

    renamed = api.post(
        "/api/cloud/zmien-nazwe",
        json={"path": "/Dokumenty/Notatka żółta.txt", "name": "Notatka.txt"},
        headers=HEADERS,
    )
    assert renamed.json()["path"] == "/Dokumenty/Notatka.txt"
    assert (
        api.post(
            "/api/cloud/zmien-nazwe", json={"path": "/Dokumenty/Notatka.txt", "name": "a/b"}, headers=HEADERS
        ).status_code
        == 400
    )
    api.post("/api/cloud/folder", json={"path": "/Archiwum"}, headers=HEADERS)
    moved = api.post(
        "/api/cloud/przenies",
        json={"paths": ["/Dokumenty/Notatka.txt"], "destination": "/Archiwum"},
        headers=HEADERS,
    )
    assert moved.json()["paths"] == ["/Archiwum/Notatka.txt"]
    copied = api.post(
        "/api/cloud/przenies",
        json={"paths": ["/Archiwum/Notatka.txt"], "destination": "/Dokumenty", "copy": True},
        headers=HEADERS,
    )
    assert copied.status_code == 200 and "/Dokumenty/Notatka.txt" in cloud.files
    into_itself = api.post(
        "/api/cloud/przenies", json={"paths": ["/Archiwum"], "destination": "/Archiwum"}, headers=HEADERS
    )
    assert into_itself.status_code == 400
    favorite = api.post("/api/cloud/ulubione", json={"path": "/Archiwum", "favorite": True}, headers=HEADERS)
    assert favorite.status_code == 200
    assert [e["path"] for e in api.get("/api/cloud/ulubione").json()] == ["/Archiwum"]
    deleted = api.post("/api/cloud/usun", json={"paths": ["/Archiwum/Notatka.txt"]}, headers=HEADERS)
    assert deleted.json()["deleted"] == 1 and "/Archiwum/Notatka.txt" not in cloud.files
    assert api.post("/api/cloud/usun", json={"paths": ["/"]}, headers=HEADERS).status_code == 400
    thumb = api.get("/api/cloud/miniatura", params={"fileid": 5, "size": 200})
    assert thumb.headers["content-type"] == "image/jpeg"
    assert ("GET", "/index.php/core/preview") in cloud.requests


def test_chunked_upload(api: TestClient, cloud: FakeNextcloud) -> None:  # noqa: F811
    started = api.post("/api/cloud/przesylanie", json={"path": "/Film.mp4"}, headers=HEADERS)
    assert started.status_code == 201
    upload_id = started.json()["upload_id"]
    parts = [b"a" * 1000, b"b" * 1000, b"c" * 10]
    for number, part in enumerate(parts, 1):
        response = api.put(
            f"/api/cloud/przesylanie/{upload_id}/{number}",
            params={"path": "/Film.mp4"},
            content=part,
            headers=HEADERS,
        )
        assert response.status_code == 200, response.text
    finished = api.post(
        f"/api/cloud/przesylanie/{upload_id}/zakoncz",
        json={"path": "/Film.mp4", "size": 2010},
        headers=HEADERS,
    )
    assert finished.status_code == 200, finished.text
    assert cloud.files["/Film.mp4"] == b"".join(parts)
    assert finished.json()["size"] == 2010
    bad = api.put("/api/cloud/przesylanie/zly-id/1", params={"path": "/x"}, content=b"x", headers=HEADERS)
    assert bad.status_code == 400
    other = api.post("/api/cloud/przesylanie", json={"path": "/Anulowany.bin"}, headers=HEADERS).json()[
        "upload_id"
    ]
    assert api.delete(f"/api/cloud/przesylanie/{other}", headers=HEADERS).json() == {"ok": True}
    assert other not in cloud.uploads


def test_shares(api: TestClient, cloud: FakeNextcloud) -> None:  # noqa: F811
    cloud.files["/Umowa.pdf"] = b"%PDF"
    expires = (date.today() + timedelta(days=7)).isoformat()
    created = api.post(
        "/api/cloud/udostepnienia",
        json={"path": "/Umowa.pdf", "password": "Haslo-do-linku-1", "expires": expires},
        headers=HEADERS,
    )
    assert created.status_code == 201, created.text
    share = created.json()
    assert share["url"] == "https://cloud.example.pl/s/tok1", "adres publiczny zamiast wewnętrznego"
    assert share["has_password"] is True and share["expires"] == expires
    past = api.post(
        "/api/cloud/udostepnienia", json={"path": "/Umowa.pdf", "expires": "2020-01-01"}, headers=HEADERS
    )
    assert past.status_code == 422
    assert [s["id"] for s in api.get("/api/cloud/udostepnienia", params={"path": "/Umowa.pdf"}).json()] == [
        "1"
    ]
    updated = api.patch(
        "/api/cloud/udostepnienia/1", json={"password": "", "clear_expiration": True}, headers=HEADERS
    ).json()
    assert updated["has_password"] is False and updated["expires"] is None
    assert api.delete("/api/cloud/udostepnienia/1", headers=HEADERS).json() == {"ok": True}
    assert api.delete("/api/cloud/udostepnienia/abc", headers=HEADERS).status_code == 400
    missing = api.post("/api/cloud/udostepnienia", json={"path": "/Brak.pdf"}, headers=HEADERS)
    assert missing.status_code == 404 and "Wrong path" in missing.json()["detail"]


def test_send_to_conversation(api: TestClient, cloud: FakeNextcloud) -> None:  # noqa: F811
    cloud.folders.add("/Faktury")
    cloud.files["/Faktury/FV 1.txt"] = b"Faktura 1"
    cloud.files["/Faktury/FV 2.txt"] = b"Faktura 2"
    response = api.post(
        "/api/cloud/do-rozmowy",
        json={"paths": ["/Faktury/FV 1.txt", "/Faktury/FV 2.txt"], "text": "Zsumuj kwoty"},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert [f["name"] for f in result["files"]] == ["FV 1.txt", "FV 2.txt"]
    assert result["run_id"]
    conversation = api.get(f"/api/conversations/{result['conversation_id']}").json()
    turn = conversation["turns"][0]
    assert turn["text"] == "Zsumuj kwoty"
    assert [f["name"] for f in turn["files"]] == ["FV 1.txt", "FV 2.txt"]
    file_id = turn["files"][0]["id"]
    assert api.get(f"/api/files/{file_id}/download").content == b"Faktura 1"
    folder = api.post("/api/cloud/do-rozmowy", json={"paths": ["/Faktury"]}, headers=HEADERS)
    assert folder.status_code == 400 and "folderem" in folder.json()["detail"]
    unknown = api.post(
        "/api/cloud/do-rozmowy",
        json={"paths": ["/Faktury/FV 1.txt"], "conversation_id": str(uuid.uuid4())},
        headers=HEADERS,
    )
    assert unknown.status_code == 404
    attach_only = api.post(
        "/api/cloud/do-rozmowy",
        json={"paths": ["/Faktury/FV 2.txt"], "conversation_id": result["conversation_id"], "send": False},
        headers=HEADERS,
    ).json()
    assert attach_only["run_id"] is None


def test_sync_info(api: TestClient) -> None:  # noqa: F811
    info = api.get("/api/cloud/synchronizacja").json()
    assert info["server_url"] == "https://cloud.example.pl"
    assert info["qr"].startswith("data:image/svg+xml")
    assert info["webdav_url"] == "https://cloud.example.pl/remote.php/dav/files/admin/"


@pytest.mark.skipif(
    not TOKEN_FILE or not Path(TOKEN_FILE).is_file(), reason="Brak NEXUS_TEST_CHMURA_TOKEN_FILE"
)
def test_real_nextcloud_roundtrip() -> None:
    """Pełny obieg na prawdziwym Nextcloud w katalogu testowym (sprzątanym na końcu)."""
    settings = Settings(
        chmura_url=CHMURA_URL,
        chmura_token_file=Path(TOKEN_FILE),
        chmura_public_url="https://cloud.danaco-nexus.pl",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    root = f"/Nexus-testy-{uuid.uuid4().hex[:8]}"

    async def scenario() -> None:
        async with CloudService(settings) as service:
            try:
                await service.mkdir(root)
                await service.mkdir(f"{root}/Źródła")
                path = f"{root}/Źródła/raport żółty.txt"
                await service.put(path, b"wersja 1", 8)
                await asyncio.sleep(1.1)
                await service.put(path, b"wersja druga", 12)
                listing = await service.list(f"{root}/Źródła")
                entry = listing["entries"][0]
                assert (entry["name"], entry["size"], entry["type"]) == ("raport żółty.txt", 12, "file")
                assert entry["fileid"]

                versions = await service.versions(path)
                assert versions, "Nextcloud zapisał poprzednią wersję"
                older = next(v for v in versions if v["size"] == 8)
                await service.restore_version(path, older["id"])
                response = await service.open_download(path)
                assert await response.aread() == b"wersja 1"
                await response.aclose()

                upload_id = f"nexus-{uuid.uuid4().hex[:16]}"
                big = f"{root}/duży plik.bin"
                chunks = [os.urandom(5 * 1024 * 1024), os.urandom(5 * 1024 * 1024), os.urandom(1234)]
                await service.upload_start(upload_id, big)
                for number, chunk in enumerate(chunks, 1):
                    await service.upload_chunk(upload_id, number, big, chunk, len(chunk))
                stat = await service.upload_finish(upload_id, big, sum(len(c) for c in chunks))
                assert stat["size"] == sum(len(c) for c in chunks)
                response = await service.open_download(big)
                assert await response.aread() == b"".join(chunks)
                await response.aclose()

                share = await service.create_share(
                    path, password="Nexus-test-Haslo-2026!", expires=date.today() + timedelta(days=3)
                )
                assert share["url"].startswith("https://cloud.danaco-nexus.pl/s/")
                assert (
                    share["has_password"]
                    and share["expires"] == (date.today() + timedelta(days=3)).isoformat()
                )
                updated = await service.update_share(share["id"], expires="")
                assert updated["expires"] is None
                assert [s["id"] for s in await service.shares(path)] == [share["id"]]
                await service.delete_share(share["id"])
                assert await service.shares(path) == []

                await service.set_favorite(path, True)
                assert path in [e["path"] for e in await service.favorites()]
                await service.set_favorite(path, False)
                found = await service.search("raport żółty")
                assert path in [e["path"] for e in found]

                await service.move(path, f"{root}/raport.txt")
                assert await service.exists(f"{root}/raport.txt")
                await service.delete(f"{root}/raport.txt")
                trash = await service.trash()
                item = next(t for t in trash if t["name"] == "raport.txt" and t["original"].startswith(root))
                await service.restore_trash(item["id"])
                assert await service.exists(f"{root}/raport.txt")
                quota = await service.quota()
                assert quota["used"] is not None
            finally:
                try:
                    await service.delete(root)
                    for entry in await service.trash():
                        if entry["original"].startswith(root):
                            await service.http.request(
                                "DELETE",
                                f"{service.dav}/trashbin/{quote(service.user)}/trash/{quote(entry['id'])}",
                            )
                except CloudError:
                    pass

    asyncio.run(scenario())


def test_ocs_error_is_reported(biuro_settings: Settings) -> None:  # noqa: F811
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"ocs": {"meta": {"status": "failure", "message": "Hasło jest za słabe"}, "data": []}}
        )

    async def run() -> None:
        async with CloudService(biuro_settings, transport=httpx.MockTransport(handler)) as service:
            with pytest.raises(CloudError, match="Hasło jest za słabe"):
                await service.create_share("/a.txt", password="1")

    asyncio.run(run())
