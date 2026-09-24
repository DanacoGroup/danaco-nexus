"""Testy API: logowanie, ochrona CSRF, pliki, rozmowy, kolejka zadań i strumień zdarzeń."""

from __future__ import annotations

import asyncio
import io
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from nexus.api.app import create_app
from nexus.api.auth import set_admin_credentials
from nexus.config import Settings
from nexus.db import Base, Database

PASSWORD = "bardzo-tajne-haslo-2026"
HEADERS = {"X-Nexus-Request": "1"}


def _reset_postgres(url: str) -> None:
    async def run() -> None:
        database = Database(url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await database.close()

    asyncio.run(run())


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Ustawienia testowe: SQLite albo PostgreSQL (gdy ustawiono NEXUS_TEST_POSTGRES_URL)."""
    postgres = os.environ.get("NEXUS_TEST_POSTGRES_URL", "")
    if postgres:
        _reset_postgres(postgres)
    return Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=postgres or f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        cookie_secure=False,
        cookie_domain="",
        public_url="",
        chmura_public_url="",
        redis_url="",
        voice_warm_up=False,
        voice_stt_model_dir=tmp_path / "brak-modelu",
        voice_tts_dir=tmp_path / "brak-glosow",
        voice_google_key_file=tmp_path / "brak-klucza-google",
        login_attempts_per_15_min=3,
        qdrant_url="http://127.0.0.1:1",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def set_password(settings: Settings) -> None:
    async def run() -> None:
        database = Database(settings.database_url)
        await database.create_schema()
        await set_admin_credentials(database, "admin", PASSWORD)
        await database.close()

    asyncio.run(run())


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200, response.text


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_requires_configured_password(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "x"}, headers=HEADERS)
    assert response.status_code == 503
    assert "set-password" in response.json()["detail"]


def test_login_flow_and_throttling(client: TestClient, settings: Settings) -> None:
    set_password(settings)
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD}).status_code == 403
    for _ in range(3):
        bad = client.post("/api/auth/login", json={"username": "admin", "password": "zle"}, headers=HEADERS)
        assert bad.status_code == 401
    blocked = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert blocked.status_code == 429


def test_session_cookie_and_csrf(client: TestClient, settings: Settings) -> None:
    set_password(settings)
    login(client)
    cookie = client.cookies.get("nexus_session")
    assert cookie and len(cookie) > 30
    assert client.get("/api/auth/me").json() == {"username": "admin", "cloud_url": "", "gosc": ""}
    assert client.post("/api/conversations", json={}).status_code == 403
    assert client.post("/api/conversations", json={}, headers=HEADERS).status_code == 201
    client.post("/api/auth/logout", headers=HEADERS)
    assert client.get("/api/auth/me").status_code == 401


def test_cloud_single_sign_on(settings: Settings) -> None:
    settings.public_url = "https://nexus.example.pl"
    settings.cookie_domain = "testserver.local"
    set_password(settings)
    with TestClient(create_app(settings), base_url="http://app.testserver.local") as client:
        anonymous = client.get("/api/auth/sso", headers={"X-Forwarded-Uri": "/apps/files/"})
        assert anonymous.status_code == 204 and "x-nexus-user" not in anonymous.headers
        to_login = client.get(
            "/api/auth/sso",
            headers={"X-Forwarded-Uri": "/login?redirect_url=/apps/files"},
            follow_redirects=False,
        )
        assert to_login.status_code == 302
        assert to_login.headers["location"] == "https://nexus.example.pl/?next=cloud"
        direct = client.get("/api/auth/sso", headers={"X-Forwarded-Uri": "/login?direct=1"})
        assert direct.status_code == 204
        response = client.post(
            "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
        )
        assert "domain=testserver.local" in response.headers["set-cookie"].lower()
        signed = client.get("/api/auth/sso", headers={"X-Forwarded-Uri": "/login"})
        assert signed.status_code == 204 and signed.headers["x-nexus-user"] == "admin"
        client.post("/api/auth/logout", headers=HEADERS)
        assert "x-nexus-user" not in client.get("/api/auth/sso").headers


def test_conversation_message_run_and_events(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    set_password(settings)
    login(client)
    conversation = client.post("/api/conversations", json={}, headers=HEADERS).json()
    upload = client.post(
        "/api/files",
        files={"file": ("Umowa najmu – skan.pdf", b"%PDF-1.4\n%test\n", "application/pdf")},
        headers=HEADERS,
    )
    assert upload.status_code == 201, upload.text
    file_info = upload.json()
    assert file_info["name"] == "Umowa najmu – skan.pdf"

    sent = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"text": "Wykonaj OCR tego skanu", "file_ids": [file_info["id"]]},
        headers=HEADERS,
    )
    assert sent.status_code == 202, sent.text
    run_id = sent.json()["run_id"]

    busy = client.post(
        f"/api/conversations/{conversation['id']}/messages", json={"text": "Drugie"}, headers=HEADERS
    )
    assert busy.status_code == 409

    detail = client.get(f"/api/conversations/{conversation['id']}").json()
    assert detail["title"] == "Wykonaj OCR tego skanu"
    assert detail["active_run"] == {"id": run_id, "status": "queued"}
    assert detail["turns"][0]["files"][0]["id"] == file_info["id"]
    listed = client.get("/api/conversations").json()
    assert listed[0]["active"] is True

    assert client.post(f"/api/runs/{run_id}/cancel", headers=HEADERS).json() == {"status": "cancelled"}
    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        body = "".join(stream.iter_text())
    assert "event: run.cancelled" in body

    download = client.get(f"/api/files/{file_info['id']}/download")
    assert download.status_code == 200
    assert "filename*=UTF-8''Umowa%20najmu%20%E2%80%93%20skan.pdf" in download.headers["content-disposition"]
    assert download.headers["content-type"] == "application/octet-stream"

    stored = list((settings.files_dir).rglob("*.pdf"))
    assert len(stored) == 1
    assert client.delete(f"/api/conversations/{conversation['id']}", headers=HEADERS).json() == {"ok": True}
    assert not stored[0].exists()
    assert client.get(f"/api/conversations/{conversation['id']}").status_code == 404


def test_upload_limit(client: TestClient, settings: Settings) -> None:
    set_password(settings)
    login(client)
    client.app.state.settings.upload_limit_mb = 1  # type: ignore[attr-defined]
    response = client.post(
        "/api/files", files={"file": ("duzy.bin", b"0" * (1024 * 1024 + 10))}, headers=HEADERS
    )
    assert response.status_code == 413
    assert not any(settings.files_dir.rglob("*.bin"))


def test_security_headers(client: TestClient) -> None:
    headers = client.get("/api/health").headers
    assert headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in headers["content-security-policy"]


def test_pwa_files_served_with_cache_rules(settings: Settings) -> None:
    static = settings.static_dir
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>Nexus</title>", encoding="utf-8")
    (static / "sw.js").write_text("self.addEventListener('fetch', () => {});", encoding="utf-8")
    (static / "manifest.webmanifest").write_text('{"name": "Danaco Nexus"}', encoding="utf-8")
    (static / "assets" / "index-abc123.js").write_text("console.log(1);", encoding="utf-8")
    with TestClient(create_app(settings)) as client:
        worker = client.get("/sw.js")
        assert worker.headers["cache-control"] == "no-cache"
        assert worker.headers["content-type"].startswith("text/javascript")
        manifest = client.get("/manifest.webmanifest")
        assert manifest.headers["content-type"].startswith("application/manifest+json")
        assert manifest.headers["cache-control"] == "no-cache"
        asset = client.get("/assets/index-abc123.js")
        assert "immutable" in asset.headers["cache-control"]
        spa = client.get("/c/00000000-0000-0000-0000-000000000000")
        assert spa.status_code == 200 and "Nexus" in spa.text
        assert "worker-src 'self'" in spa.headers["content-security-policy"]
        # Brakujący plik to 404, a nie strona aplikacji z kodem 200.
        brak = client.get("/ruch/stany/nie-ma-takiego.webm")
        assert brak.status_code == 404 and brak.json()["detail"] == "Nie znaleziono pliku."
        # Adresy aplikacji (bez kropki w ostatnim członie) nadal dostają stronę.
        assert client.get("/m/pliki").status_code == 200
        assert client.get("/jakis-nieznany-ekran").status_code == 200
        # Plik, który istnieje, wraca plikiem — reguła nie może zjeść prawdziwych zasobów.
        assert client.get("/assets/index-abc123.js").status_code == 200

        # Bez treści: wracamy na stronę główną, tak jak dotąd.
        shared = client.post("/share-target", follow_redirects=False)
        assert shared.status_code == 303 and shared.headers["location"] == "/"
        # Z treścią: tekst jedzie adresem, zamiast zniknąć. Service worker stoi dopiero od
        # drugiego uruchomienia, a pierwsza próba udostępnienia zdarza się zwykle wcześniej.
        z_tekstem = client.post(
            "/share-target",
            data={"title": "Notatka", "text": "Zrób z tego kartkę", "url": "https://przyklad.pl/a"},
            follow_redirects=False,
        )
        assert z_tekstem.status_code == 303
        cel = z_tekstem.headers["location"]
        assert cel.startswith("/?tekst=")
        from urllib.parse import unquote

        assert unquote(cel.removeprefix("/?tekst=")) == "Notatka\nZrób z tego kartkę\nhttps://przyklad.pl/a"


def test_voice_endpoints_without_models(client: TestClient, settings: Settings) -> None:
    set_password(settings)
    login(client)
    config = client.get("/api/voice/config").json()
    assert config == {"available": False, "voices": [], "default_voice": ""}
    response = client.post(
        "/api/voice/transcribe",
        files={"audio": ("wypowiedz.webm", bytes(16), "audio/webm")},
        data={"language": "pl"},
        headers=HEADERS,
    )
    assert response.status_code == 503
    assert client.post("/api/voice/speak", json={"text": "Dzień dobry"}, headers=HEADERS).status_code == 503
    assert client.post("/api/voice/speak", json={"text": ""}, headers=HEADERS).status_code == 422
    assert "microphone=(self)" in client.get("/api/health").headers["permissions-policy"]


def test_device_tokens(client: TestClient, settings: Settings) -> None:
    set_password(settings)
    login(client)
    created = client.post("/api/urzadzenia", json={"name": "Telefon", "kind": "android"}, headers=HEADERS)
    assert created.status_code == 201
    token = created.json()["token"]
    assert token.startswith("nxd_")
    assert "token" not in client.get("/api/urzadzenia").json()[0]
    browser_cookies = dict(client.cookies)
    client.cookies.clear()
    bearer = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/conversations", headers=bearer).status_code == 200
    # Urządzenie nie potrzebuje nagłówka CSRF, ale nie może wydawać nowych kluczy.
    assert client.post("/api/conversations", json={}, headers=bearer).status_code == 201
    assert client.post("/api/urzadzenia", json={"name": "x"}, headers=bearer).status_code == 403
    assert client.get("/api/conversations", headers={"Authorization": "Bearer nxd_zly"}).status_code == 401
    client.cookies.update(browser_cookies)
    client.delete(f"/api/urzadzenia/{created.json()['id']}", headers=HEADERS)
    client.cookies.clear()
    assert client.get("/api/conversations", headers=bearer).status_code == 401


def _sesja_telefonu_i_przegladarki(client: TestClient, settings: Settings) -> tuple[dict, dict]:
    """Dwie niezależne sesje tego samego konta: okno aplikacji na telefonie i przeglądarka."""
    set_password(settings)
    login(client)
    telefon = dict(client.cookies)
    client.cookies.clear()
    login(client)
    przegladarka = dict(client.cookies)
    client.cookies.clear()
    return telefon, przegladarka


def test_cofniecie_klucza_konczy_sesje_ktora_go_zalozyla(client: TestClient, settings: Settings) -> None:
    """Zgubiony telefon po „Cofnij” nie może dalej pracować w oknie ani założyć nowego klucza.

    Okno aplikacji Android (i Nexus Desktop) ma własną sesję i zakłada klucz sam z tej sesji.
    Samo unieważnienie klucza zostawiało sesję, a aplikacja po odrzuceniu klucza prosiła
    o nowy — i dostawała go z tej samej, wciąż ważnej sesji.
    """
    telefon, przegladarka = _sesja_telefonu_i_przegladarki(client, settings)
    client.cookies.update(telefon)
    created = client.post("/api/urzadzenia", json={"name": "Telefon", "kind": "android"}, headers=HEADERS)
    assert created.status_code == 201, created.text
    assert created.json()["wylogowuje_okno"] is True
    bearer = {"Authorization": f"Bearer {created.json()['token']}"}
    client.cookies.clear()

    client.cookies.update(przegladarka)
    assert client.delete(f"/api/urzadzenia/{created.json()['id']}", headers=HEADERS).status_code == 200
    assert client.get("/api/conversations").status_code == 200, "przeglądarka, która cofa klucz, zostaje"
    client.cookies.clear()

    assert client.get("/api/conversations", headers=bearer).status_code == 401
    client.cookies.update(telefon)
    assert client.get("/api/conversations").status_code == 401
    nowy = client.post("/api/urzadzenia", json={"name": "Telefon", "kind": "android"}, headers=HEADERS)
    assert nowy.status_code == 401


def test_klucz_po_wygasnieciu_sesji_nie_obiecuje_wylogowania_okna(
    client: TestClient, settings: Settings
) -> None:
    """Telefon zalogowany ponownie po wygaśnięciu sesji zatrzymuje stary klucz. Klucz zna tylko
    starą sesję, więc lista nie może twierdzić, że jego cofnięcie wyloguje obecne okno."""
    telefon, przegladarka = _sesja_telefonu_i_przegladarki(client, settings)
    client.cookies.update(telefon)
    created = client.post("/api/urzadzenia", json={"name": "Telefon", "kind": "android"}, headers=HEADERS)
    assert created.status_code == 201, created.text
    client.post("/api/auth/logout", headers=HEADERS)
    client.cookies.clear()

    client.cookies.update(przegladarka)
    lista = client.get("/api/urzadzenia").json()
    wpis = next(pozycja for pozycja in lista if pozycja["id"] == created.json()["id"])
    assert wpis["wylogowuje_okno"] is False


def test_klucz_dla_innego_urzadzenia_nie_wiaze_sesji_przegladarki(
    client: TestClient, settings: Settings
) -> None:
    """Klucz z formularza w module Sprzęt jest dla innego urządzenia (rozszerzenie, wklejony
    klucz w Nexus Desktop) — jego cofnięcie nie może wylogować przeglądarki, która go wydała."""
    _, przegladarka = _sesja_telefonu_i_przegladarki(client, settings)
    client.cookies.update(przegladarka)
    created = client.post(
        "/api/urzadzenia",
        json={"name": "Chrome – biuro", "kind": "rozszerzenie", "dla_innego_urzadzenia": True},
        headers=HEADERS,
    )
    assert created.status_code == 201, created.text
    assert created.json()["wylogowuje_okno"] is False
    assert client.delete(f"/api/urzadzenia/{created.json()['id']}", headers=HEADERS).status_code == 200
    assert client.get("/api/conversations").status_code == 200
    bearer = {"Authorization": f"Bearer {created.json()['token']}"}
    assert client.get("/api/conversations", headers=bearer).status_code == 401


def test_klucz_sprzed_zmiany_bez_sesji_cofa_sie_jak_dotad(client: TestClient, settings: Settings) -> None:
    """Klucze założone przed zapisywaniem sesji nie mają jej w bazie — cofnięcie unieważnia
    wyłącznie klucz i nie dotyka żadnej sesji."""
    from sqlalchemy import update

    from nexus.db import DeviceToken

    telefon, przegladarka = _sesja_telefonu_i_przegladarki(client, settings)
    client.cookies.update(telefon)
    created = client.post("/api/urzadzenia", json={"name": "Telefon", "kind": "android"}, headers=HEADERS)
    assert created.status_code == 201, created.text
    client.cookies.clear()

    async def odlacz_sesje() -> None:
        database = Database(settings.database_url)
        async with database.session() as session:
            await session.execute(update(DeviceToken).values(sesja_hash=None))
        await database.close()

    asyncio.run(odlacz_sesje())
    client.cookies.update(przegladarka)
    assert client.delete(f"/api/urzadzenia/{created.json()['id']}", headers=HEADERS).status_code == 200
    client.cookies.clear()
    client.cookies.update(telefon)
    assert client.get("/api/conversations").status_code == 200
    bearer = {"Authorization": f"Bearer {created.json()['token']}"}
    client.cookies.clear()
    assert client.get("/api/conversations", headers=bearer).status_code == 401


def test_kolumna_sesji_klucza_dochodzi_do_istniejacej_bazy(tmp_path: Path) -> None:
    """Wdrożona baza ma już tabelę ``device_tokens`` bez nowej kolumny — ``create_schema``
    ma ją dopisać, a istniejące klucze zostawić bez powiązanej sesji."""
    from sqlalchemy import text

    url = f"sqlite+aiosqlite:///{(tmp_path / 'stara.db').as_posix()}"

    async def run() -> tuple[set[str], list[tuple[str, object]]]:
        database = Database(url)
        async with database.engine.begin() as connection:
            await connection.execute(
                text(
                    "CREATE TABLE device_tokens (id CHAR(32) PRIMARY KEY, token_hash VARCHAR(64) UNIQUE, "
                    "name VARCHAR(100), kind VARCHAR(20), created_at DATETIME, last_used_at DATETIME, "
                    "revoked BOOLEAN)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO device_tokens VALUES ('0123456789abcdef0123456789abcdef', 'skrot', "
                    "'Telefon', 'android', '2026-09-01 10:00:00', NULL, 0)"
                )
            )
        await database.create_schema()
        async with database.engine.connect() as connection:
            opis = await connection.execute(text("PRAGMA table_info(device_tokens)"))
            kolumny = {wiersz[1] for wiersz in opis}
            wynik = await connection.execute(text("SELECT name, sesja_hash FROM device_tokens"))
            wiersze = [tuple(wiersz) for wiersz in wynik]
        await database.close()
        return kolumny, wiersze

    kolumny, wiersze = asyncio.run(run())
    assert {"sesja_hash", "owner_id"} <= kolumny
    assert wiersze == [("Telefon", None)]


def test_nieistniejacy_wpis_portalu_daje_404(settings: Settings) -> None:
    """Adres wpisu, którego nie ma, ma zwrócić 404, a nie 200 z powłoką aplikacji.

    Kod 200 na nieistniejącym wpisie to „miękkie 404”: wyszukiwarka trzyma taki adres
    w indeksie i pokazuje go zamiast działającej strony. Adresy aplikacji (`/m/…`,
    `/c/…`) i stałe strony portalu zostają przy 200 — one istnieją po stronie klienta.
    """
    static = settings.static_dir
    static.mkdir(parents=True, exist_ok=True)
    (static / "index.html").write_text("<!doctype html><title>Nexus</title>", encoding="utf-8")
    with TestClient(create_app(settings)) as client:
        assert client.get("/portal/blog/nie-ma-takiego-wpisu").status_code == 404
        assert client.get("/portal/dokumentacja/nie-ma-takiej-strony").status_code == 404
        # Nieistniejąca strona portalu — tak samo 404, a nie powłoka z kodem 200.
        assert client.get("/portal/nie-ma-takiej-strony").status_code == 404
        assert client.get("/portal/cennik").status_code == 200
        # Strony zamknięte przed robotami istnieją, więc zostają przy 200.
        for adres in ("/portal/szukaj", "/portal/konto", "/portal/panel", "/portal/admin"):
            assert client.get(adres).status_code == 200, adres
        assert client.get("/m/kod").status_code == 200
        assert client.get("/").status_code == 200


def test_head_odpowiada_jak_get_bez_tresci(settings: Settings) -> None:
    """HEAD na pliku i na stronie: ten sam status i nagłówki, puste ciało.

    Trasa zbiorcza przyjmowała wyłącznie GET, więc sprawdzarki odsyłaczy i monitoring
    dostępności dostawały 405 na zasób, który normalnie się pobiera (RFC 9110 §9.3.2).
    """
    static = settings.static_dir
    static.mkdir(parents=True, exist_ok=True)
    (static / "index.html").write_text("<!doctype html><title>Nexus</title>", encoding="utf-8")
    (static / "zasob.css").write_text("body{}", encoding="utf-8")
    with TestClient(create_app(settings)) as client:
        pobranie = client.get("/zasob.css")
        naglowek = client.head("/zasob.css")
        assert naglowek.status_code == pobranie.status_code == 200
        assert naglowek.content == b""
        assert naglowek.headers["content-length"] == pobranie.headers["content-length"]
        assert naglowek.headers["etag"] == pobranie.headers["etag"]
        assert naglowek.headers["cache-control"] == pobranie.headers["cache-control"]
        strona = client.head("/portal/cennik")
        assert strona.status_code == 200 and strona.content == b""


def test_if_none_match_gwiazdka_daje_304(tmp_path: Path) -> None:  # noqa: F811
    """„*” znaczy „dowolna wersja” (RFC 9110 §13.1.2) — plik istnieje, więc 304.

    Wcześniej gwiazdka wpadała w porównanie znaczników, nie pasowała do żadnego
    i serwer odsyłał pełną treść przy każdym odświeżeniu.
    """
    from fastapi import Request

    from nexus.api.app import plik_z_warunkiem

    plik = tmp_path / "zasob.css"
    plik.write_text("body{}", encoding="utf-8")

    def zadanie(naglowki: dict[str, str]) -> Request:
        zakodowane = [(k.lower().encode(), v.encode()) for k, v in naglowki.items()]
        return Request({"type": "http", "method": "GET", "headers": zakodowane, "path": "/"})

    assert plik_z_warunkiem(plik, "public", zadanie({})).status_code == 200
    warunkowa = plik_z_warunkiem(plik, "public", zadanie({"if-none-match": "*"}))
    assert warunkowa.status_code == 304
    assert warunkowa.headers.get("etag")


def test_adres_publiczny_dostaje_wlasne_znaczniki(settings: Settings) -> None:
    """Robot bez JavaScriptu ma zobaczyć tytuł tego ekranu, a nie tytuł z index.html."""
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    (settings.static_dir / "index.html").write_text(
        "<!doctype html><html><head><title>Danaco Nexus</title>"
        '<meta name="description" content="stary"></head><body></body></html>',
        encoding="utf-8",
    )

    # Trasa zastępcza powstaje tylko wtedy, gdy katalog interfejsu istnieje przy budowie
    # aplikacji — dlatego własny klient, a nie wspólna oprawa testowa.
    with TestClient(create_app(settings)) as klient:
        cennik = klient.get("/portal/cennik")
        aplikacja = klient.get("/m/pliki")

    assert cennik.status_code == 200
    assert "Cennik Danaco Nexus" in cennik.text
    assert 'property="og:title"' in cennik.text
    assert "stary" not in cennik.text
    # Adres aplikacji idzie bez podmiany — zostaje dokument wyjściowy.
    assert aplikacja.status_code == 200
    assert "<title>Danaco Nexus</title>" in aplikacja.text
    assert "Cennik Danaco Nexus" not in aplikacja.text


def test_miniatura_filmu_powstaje_z_klatki(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    """Film bez miniatury to w wykazie plików i w storyboardzie montażu szary prostokąt."""
    set_password(settings)
    login(client)
    film = tmp_path / "ujecie.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=size=320x240:rate=25:duration=3", "-pix_fmt", "yuv420p", str(film)],
        check=True,
        timeout=60,
    )

    wyslany = client.post(
        "/api/files",
        files={"file": ("ujecie.mp4", film.read_bytes(), "video/mp4")},
        headers=HEADERS,
    )
    assert wyslany.status_code == 201, wyslany.text

    miniatura = client.get(f"/api/files/{wyslany.json()['id']}/thumbnail")

    assert miniatura.status_code == 200
    assert miniatura.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(miniatura.content)) as obraz:
        assert max(obraz.size) <= 640
        # Klatka z „testsrc” jest kolorowa; czarny kadr znaczyłby, że nic nie wyszło.
        assert obraz.convert("L").getextrema()[1] > 40


def test_miniatura_pliku_bez_obrazu_zwraca_404(client: TestClient, settings: Settings) -> None:
    set_password(settings)
    login(client)
    wyslany = client.post(
        "/api/files",
        files={"file": ("notatka.txt", io.BytesIO(b"sam tekst"), "text/plain")},
        headers=HEADERS,
    )

    assert client.get(f"/api/files/{wyslany.json()['id']}/thumbnail").status_code == 404


def test_bledne_dane_odpowiadaja_po_polsku(client: TestClient) -> None:  # noqa: F811
    """Odpowiedź 422 ma mówić po polsku i wskazywać pole, a nie „Input should be…”.

    Domyślna odpowiedź FastAPI to lista obiektów z angielskim opisem. Interfejs bierze
    `detail` tylko wtedy, gdy jest napisem, więc użytkownik widział z tego „Błąd serwera
    (422)” — komunikat nieprawdziwy (to nie serwer się pomylił) i nic nie mówiący.
    """
    odpowiedz = client.get("/api/portal/tresci", params={"strona": "abc"})
    assert odpowiedz.status_code == 422
    tresc = odpowiedz.json()
    assert isinstance(tresc["detail"], str)
    assert "strona" in tresc["detail"]
    assert "Input should" not in tresc["detail"]
    # Wykaz pól zostaje osobno — przydaje się przy diagnozie, ale nie jest komunikatem.
    assert tresc["pola"] == ["strona"]
    # Powód też jest po polsku i mówi, co poprawić.
    assert tresc["detail"] == "Pole „strona” musi być liczbą."


def test_health_odpowiada_takze_na_head(client: TestClient) -> None:  # noqa: F811
    """Sondy dostępności pytają metodą ``HEAD`` — i dostawały 404.

    Starlette dokłada ``HEAD`` do tras ``GET`` samoczynnie, ale trasy FastAPI już nie.
    Żądanie nie pasowało więc do żadnej trasy API, spadało do zapasu SPA (też tylko
    ``GET``) i kończyło jako 404 — choć ``GET`` na tym samym adresie zwracał 200.
    Monitor skonfigurowany na ``HEAD`` zgłaszałby usługę jako niedziałającą.
    """
    assert client.get("/api/health").status_code == 200
    odpowiedz = client.head("/api/health")
    assert odpowiedz.status_code == 200
    # `HEAD` nie niesie ciała — sprawdzamy sam kod i to, że nagłówki są te same co przy `GET`.
    assert odpowiedz.headers["content-type"].startswith("application/json")


def test_dwa_brakujace_pola_to_brak_a_nie_bledna_wartosc(client: TestClient) -> None:  # noqa: F811
    """Przy jednym polu mówiliśmy „Brakuje pola”, przy dwóch nagle „Nieprawidłowe wartości”.

    Pole, którego nie przysłano, nie ma wartości — więc nie może mieć nieprawidłowej.
    Użytkownik czyta z takiego zdania, że wpisał coś źle, i szuka błędu tam, gdzie go nie ma.
    """
    odpowiedz = client.post("/api/auth/login", json={}, headers=HEADERS)
    assert odpowiedz.status_code == 422
    tresc = odpowiedz.json()
    assert tresc["detail"] == "Brakuje pól: „username”, „password”."
    assert tresc["pola"] == ["username", "password"]
