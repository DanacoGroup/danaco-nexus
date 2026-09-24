"""Izolacja kont: rozmowy, pliki i przebiegi widzi wyłącznie ich właściciel.

Aplikacja przyjmuje logowanie administratora serwera i kont klientów założonych w portalu.
Każde konto ma własną przestrzeń — bez tego każdy, komu przekazano dostęp do testów,
czytałby cudzą historię rozmów i cudze pliki.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_api import HEADERS, PASSWORD, client, set_password, settings  # noqa: F401

from nexus.api.app import create_app
from nexus.config import Settings
from nexus.db import ADMIN_OWNER, Database, StoredFile
from nexus.platnosci.plany import PLAN_DOMYSLNY
from nexus.platnosci.uprawnienia import limity_planu, opis_przestrzeni
from nexus.portal.konta import utworz_konto

KLIENT_HASLO = "Haslo-Testera-2026!"


def zaloz_konto(ustawienia: Settings, email: str) -> None:  # noqa: F811
    """Konto klienta portalu — takie samo, jakie powstaje przy rejestracji na stronie."""

    async def run() -> None:
        database = Database(ustawienia.database_url)
        await database.create_schema()
        async with database.session() as session:
            await utworz_konto(session, email=email, haslo=KLIENT_HASLO, name="Tester")
        await database.close()

    asyncio.run(run())


def zapelnij_przestrzen(ustawienia: Settings, plik: uuid.UUID, rozmiar: int) -> None:
    """Podnosi zapisany rozmiar pliku do rozmiaru całej przestrzeni planu.

    Zajęte miejsce liczone jest z kolumny ``files.size``, więc konto da się „zapełnić”
    bez zapisywania na dysku stu megabajtów w każdym przebiegu testów.
    """

    async def run() -> None:
        database = Database(ustawienia.database_url)
        async with database.session() as session:
            await session.execute(update(StoredFile).where(StoredFile.id == plik).values(size=rozmiar))
        await database.close()

    asyncio.run(run())


def zaloguj(klient: TestClient, login: str, haslo: str) -> None:
    odpowiedz = klient.post("/api/auth/login", json={"username": login, "password": haslo}, headers=HEADERS)
    assert odpowiedz.status_code == 200, odpowiedz.text


def test_konto_portalu_loguje_sie_do_aplikacji(client: TestClient, settings: Settings) -> None:  # noqa: F811
    set_password(settings)
    zaloz_konto(settings, "tester@example.com")
    zaloguj(client, "tester@example.com", KLIENT_HASLO)
    assert client.get("/api/conversations").json() == []


def test_rozmowy_nie_przeciekaja_miedzy_kontami(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    set_password(settings)
    zaloz_konto(settings, "pierwszy@example.com")
    zaloz_konto(settings, "drugi@example.com")

    zaloguj(client, "pierwszy@example.com", KLIENT_HASLO)
    utworzona = client.post("/api/conversations", json={"title": "Sprawy pierwszego"}, headers=HEADERS)
    assert utworzona.status_code == 201, utworzona.text
    identyfikator = utworzona.json()["id"]
    assert [pozycja["title"] for pozycja in client.get("/api/conversations").json()] == ["Sprawy pierwszego"]

    client.post("/api/auth/logout", headers=HEADERS)
    zaloguj(client, "drugi@example.com", KLIENT_HASLO)
    assert client.get("/api/conversations").json() == [], "drugie konto nie może widzieć cudzych rozmów"
    assert client.get(f"/api/conversations/{identyfikator}").status_code == 404
    zmiana = client.patch(
        f"/api/conversations/{identyfikator}", json={"title": "Przejęte"}, headers=HEADERS
    )
    assert zmiana.status_code == 404
    assert client.delete(f"/api/conversations/{identyfikator}", headers=HEADERS).status_code == 404

    client.post("/api/auth/logout", headers=HEADERS)
    zaloguj(client, "pierwszy@example.com", KLIENT_HASLO)
    assert client.get(f"/api/conversations/{identyfikator}").status_code == 200, "właściciel dalej ma dostęp"


def test_pliki_nie_przeciekaja_miedzy_kontami(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    set_password(settings)
    zaloz_konto(settings, "wlasciciel@example.com")
    zaloz_konto(settings, "obcy@example.com")

    zaloguj(client, "wlasciciel@example.com", KLIENT_HASLO)
    wyslany = client.post(
        "/api/files",
        files={"file": ("notatka.txt", io.BytesIO(b"tresc prywatna"), "text/plain")},
        headers=HEADERS,
    )
    assert wyslany.status_code == 201, wyslany.text
    plik = wyslany.json()["id"]
    assert client.get(f"/api/files/{plik}/download").status_code == 200

    client.post("/api/auth/logout", headers=HEADERS)
    zaloguj(client, "obcy@example.com", KLIENT_HASLO)
    assert client.get(f"/api/files/{plik}/download").status_code == 404
    assert client.get(f"/api/files/{plik}/thumbnail").status_code == 404


def test_administrator_nie_widzi_rozmow_klientow(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Konto administratora serwera jest osobną przestrzenią, nie widokiem na wszystkie."""
    set_password(settings)
    zaloz_konto(settings, "klient@example.com")
    zaloguj(client, "klient@example.com", KLIENT_HASLO)
    client.post("/api/conversations", json={"title": "Sprawy klienta"}, headers=HEADERS)

    client.post("/api/auth/logout", headers=HEADERS)
    zaloguj(client, "admin", PASSWORD)
    assert client.get("/api/conversations").json() == []


def test_limit_przestrzeni_konta(client: TestClient, settings: Settings, tmp_path: Path) -> None:  # noqa: F811
    """Po wypełnieniu przestrzeni konta kolejny plik ma zostać odrzucony z czytelnym powodem.

    Przestrzeń wyznacza plan konta, nie jedna wartość wspólna dla wszystkich: konto bez
    opłaconej subskrypcji ma zakres okresu próbnego planu wejściowego. Komunikat podaje tę
    samą liczbę, o której mówi polityka prywatności (rozdz. 2).
    """
    set_password(settings)
    zaloz_konto(settings, "pelne@example.com")
    zaloguj(client, "pelne@example.com", KLIENT_HASLO)
    limity = limity_planu(PLAN_DOMYSLNY, "brak")
    assert limity.przestrzen_mb == 100

    pierwszy = client.post(
        "/api/files",
        files={"file": ("notatka.txt", io.BytesIO(b"x" * 10), "text/plain")},
        headers=HEADERS,
    )
    assert pierwszy.status_code == 201, pierwszy.text
    zapelnij_przestrzen(settings, uuid.UUID(pierwszy.json()["id"]), limity.przestrzen_mb * 1024 * 1024)

    odrzucony = client.post(
        "/api/files",
        files={"file": ("duzy.txt", io.BytesIO(b"x" * 10), "text/plain")},
        headers=HEADERS,
    )
    assert odrzucony.status_code == 413, odrzucony.text
    detail = odrzucony.json()["detail"]
    assert "Przestrzeń konta" in detail
    assert opis_przestrzeni(limity.przestrzen_mb) in detail


def test_skrzynki_pocztowe_sa_osobne_dla_kont(settings: Settings) -> None:  # noqa: F811
    """Plik z hasłami skrzynki należy do konta, nie do serwera."""
    import uuid

    from nexus.mail import config_path

    konto = uuid.uuid4()
    assert config_path(settings, ADMIN_OWNER) != config_path(settings, konto)
    assert str(konto) in config_path(settings, konto).name


@pytest.mark.parametrize("sciezka", ["/api/conversations", "/api/files/upload"])
def test_bez_logowania_nie_ma_dostepu(client: TestClient, sciezka: str) -> None:  # noqa: F811
    assert client.get(sciezka).status_code in (401, 404, 405)


def test_baza_wiedzy_nie_przecieka_miedzy_kontami(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Kolekcje bazy wiedzy to prywatne dokumenty — wyszukiwanie po cudzych byłoby wyciekiem."""
    set_password(settings)
    zaloz_konto(settings, "autor@example.com")
    zaloz_konto(settings, "ciekawski@example.com")

    zaloguj(client, "autor@example.com", KLIENT_HASLO)
    utworzona = client.post(
        "/api/research/kolekcje", json={"name": "Umowy", "description": ""}, headers=HEADERS
    )
    assert utworzona.status_code == 201, utworzona.text
    kolekcja = utworzona.json()["id"]
    assert [pozycja["name"] for pozycja in client.get("/api/research/kolekcje").json()] == ["Umowy"]

    client.post("/api/auth/logout", headers=HEADERS)
    zaloguj(client, "ciekawski@example.com", KLIENT_HASLO)
    assert client.get("/api/research/kolekcje").json() == []
    assert client.get(f"/api/research/kolekcje/{kolekcja}/zrodla").status_code == 404
    assert client.get(f"/api/research/kolekcje/{kolekcja}/notatki").status_code == 404
    zmiana = client.patch(
        f"/api/research/kolekcje/{kolekcja}", json={"name": "Przejęte"}, headers=HEADERS
    )
    assert zmiana.status_code == 404
    assert client.delete(f"/api/research/kolekcje/{kolekcja}", headers=HEADERS).status_code == 404


def test_wyszukiwanie_wektorowe_ma_warunek_na_konto() -> None:
    """Indeks Qdranta jest wspólny dla instalacji, więc rozdziela konta wyłącznie filtr.

    Bez warunku na `owner_id` zapytanie jednego konta trafiałoby we fragmenty dokumentów
    wszystkich pozostałych — wyciek gorszy niż cudza rozmowa, bo zwraca treść bez śladu,
    skąd pochodzi.
    """
    import inspect

    from nexus.knowledge import KnowledgeBase

    zrodlo_search = inspect.getsource(KnowledgeBase.search)
    assert "owner_id" in inspect.signature(KnowledgeBase.search).parameters
    assert 'key="owner_id"' in zrodlo_search, "wyszukiwanie nie filtruje po koncie"

    zrodlo_index = inspect.getsource(KnowledgeBase.index)
    assert "owner_id" in inspect.signature(KnowledgeBase.index).parameters
    assert '"owner_id"' in zrodlo_index, "indeksowanie nie zapisuje konta w ładunku"


def test_narzedzia_agenta_szukaja_tylko_w_dokumentach_konta() -> None:
    """Narzędzie `search_documents` przekazuje konto przebiegu do bazy wektorowej."""
    import inspect

    from nexus.tools import knowledge as narzedzia_wiedzy

    zrodlo = inspect.getsource(narzedzia_wiedzy.search_documents)
    assert "ctx.owner_id" in zrodlo, "narzędzie szuka bez ograniczenia do konta"


def test_klucze_urzadzen_nie_przeciekaja_miedzy_kontami(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Klucz urządzenia otwiera przestrzeń konta, więc musi należeć do konta.

    Bez właściciela telefon jednego użytkownika logowałby się do cudzych rozmów i plików,
    a lista urządzeń pokazywałaby wszystkim wszystko.
    """
    set_password(settings)
    zaloz_konto(settings, "wlasciciel-telefonu@example.com")
    zaloz_konto(settings, "obcy-telefon@example.com")

    zaloguj(client, "wlasciciel-telefonu@example.com", KLIENT_HASLO)
    utworzone = client.post(
        "/api/urzadzenia", json={"name": "Telefon", "kind": "android"}, headers=HEADERS
    )
    assert utworzone.status_code == 201, utworzone.text
    urzadzenie = utworzone.json()["id"]
    assert [pozycja["name"] for pozycja in client.get("/api/urzadzenia").json()] == ["Telefon"]

    client.post("/api/auth/logout", headers=HEADERS)
    zaloguj(client, "obcy-telefon@example.com", KLIENT_HASLO)
    assert client.get("/api/urzadzenia").json() == [], "drugie konto nie może widzieć cudzych kluczy"
    assert client.delete(f"/api/urzadzenia/{urzadzenie}", headers=HEADERS).status_code == 404


def test_klient_nie_dostaje_chmury_wlasciciela(tmp_path: Path) -> None:
    """Nextcloud ma jedno konto — właściciela. Klient nie dostaje ani odsyłacza, ani loginu."""
    ustawienia = Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        cookie_secure=False,
        cookie_domain="",
        public_url="",
        chmura_public_url="https://cloud.example.pl",
        redis_url="",
        voice_warm_up=False,
        qdrant_url="http://127.0.0.1:1",
    )
    set_password(ustawienia)
    zaloz_konto(ustawienia, "klient@example.com")
    with TestClient(create_app(ustawienia)) as klient:
        zaloguj(klient, "admin", PASSWORD)
        assert klient.get("/api/auth/me").json()["cloud_url"] == "https://cloud.example.pl"
        assert klient.get("/api/cloud/synchronizacja").json()["user"] == ustawienia.chmura_user

        klient.post("/api/auth/logout", headers=HEADERS)
        zaloguj(klient, "klient@example.com", KLIENT_HASLO)
        assert klient.get("/api/auth/me").json()["cloud_url"] == ""
        odmowa = klient.get("/api/cloud/synchronizacja")
        assert odmowa.status_code == 403
        assert ustawienia.chmura_user not in odmowa.text
        kalendarz = klient.get("/api/kalendarz/synchronizacja")
        assert kalendarz.status_code == 403
        assert ustawienia.chmura_user not in kalendarz.text


def test_klient_z_wlasnym_kontem_chmury_wchodzi_na_nie_przez_sso(tmp_path: Path) -> None:
    """Plan z synchronizacją daje konto Nextcloud — SSO i /me prowadzą na nie, nie na konto techniczne."""
    from nexus.chmura_konta import _zapisz_haslo, uid_konta
    from nexus.portal.konta import znajdz_konto

    ustawienia = Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        cookie_secure=False,
        cookie_domain="",
        public_url="",
        chmura_public_url="https://cloud.example.pl",
        chmura_token_file=tmp_path / "app" / "chmura-token",
        redis_url="",
        voice_warm_up=False,
        qdrant_url="http://127.0.0.1:1",
    )
    set_password(ustawienia)
    zaloz_konto(ustawienia, "pro@example.com")

    async def wlasciciel() -> uuid.UUID:
        database = Database(ustawienia.database_url)
        async with database.session() as session:
            konto = await znajdz_konto(session, "pro@example.com")
        await database.close()
        assert konto is not None
        return konto.id

    owner = asyncio.run(wlasciciel())
    with TestClient(create_app(ustawienia)) as klient:
        zaloguj(klient, "pro@example.com", KLIENT_HASLO)
        assert klient.get("/api/auth/sso").headers.get("x-nexus-user") is None
        assert klient.get("/api/auth/me").json()["cloud_url"] == ""

        _zapisz_haslo(ustawienia, uid_konta(owner), "haslo-konta")
        assert klient.get("/api/auth/sso").headers.get("x-nexus-user") == uid_konta(owner)
        assert klient.get("/api/auth/me").json()["cloud_url"] == "https://cloud.example.pl"
        # Kalendarz z telefonu łączy się z tym samym kontem Nextcloud, nie z kontem technicznym.
        kalendarz = klient.get("/api/kalendarz/synchronizacja")
        assert kalendarz.status_code == 200 and kalendarz.json()["user"] == uid_konta(owner)
