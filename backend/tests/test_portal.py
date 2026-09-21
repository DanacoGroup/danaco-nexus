"""Testy portalu produktowego: treści, ochrona punktów edycyjnych, kanały SEO i konta klientów."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from nexus.api.app import create_app
from nexus.api.auth import set_admin_credentials
from nexus.config import Settings
from nexus.db import Database, utcnow
from nexus.models.portal import PortalContent, PortalEmailConfirmation, PortalSession
from nexus.portal import kanaly, konta, poczta_portalu, repozytorium, tresc
from nexus.portal.materialy import POMIJANE, BladMaterialu, wczytaj_katalog, zapisz
from nexus.portal.ustawienia import portal_settings

HASLO_ADMINISTRATORA = "bardzo-tajne-haslo-2026"
HASLO_KLIENTA = "klient-portalu-2026"
HEADERS = {"X-Nexus-Request": "1"}
ZMIENNE_PORTALU = (
    "NEXUS_PORTAL_PUBLIC_URL",
    "NEXUS_PORTAL_MAIL_NADAWCA",
    "NEXUS_PORTAL_MAIL_FROM",
    "NEXUS_PORTAL_RESET_TTL_MINUTES",
    "NEXUS_PORTAL_SESSION_DAYS",
    "NEXUS_PORTAL_REJESTRACJA",
    "NEXUS_PORTAL_LOGIN_PROBY_15MIN",
    "NEXUS_PORTAL_RESET_PROBY_15MIN",
    "NEXUS_PORTAL_KONTAKT_PROBY_15MIN",
)


class NadawcaTestowy:
    """Nadawca zapamiętujący wiadomości zamiast je wysyłać."""

    def __init__(self) -> None:
        self.wiadomosci: list[tuple[str, str, str]] = []

    def wyslij(self, odbiorca: str, temat: str, tresc_wiadomosci: str) -> None:
        self.wiadomosci.append((odbiorca, temat, tresc_wiadomosci))

    @property
    def ostatni_token(self) -> str:
        _, _, ostatnia = self.wiadomosci[-1]
        return ostatnia.split("token=")[1].split()[0]

    def token_potwierdzenia(self, odbiorca: str) -> str:
        """Token z ostatniego odsyłacza potwierdzającego adres wysłanego pod wskazany adres."""
        for adres, _, tresc_wiadomosci in reversed(self.wiadomosci):
            if adres == odbiorca and "potwierdzenie=" in tresc_wiadomosci:
                return tresc_wiadomosci.split("potwierdzenie=")[1].split()[0]
        raise AssertionError(f"Brak wiadomości z potwierdzeniem adresu dla {odbiorca}.")


@pytest.fixture(autouse=True)
def _srodowisko_portalu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testy nie zależą od zmiennych portalu ustawionych na serwerze."""
    for nazwa in ZMIENNE_PORTALU:
        monkeypatch.delenv(nazwa, raising=False)
    monkeypatch.setenv("NEXUS_PORTAL_PUBLIC_URL", "https://danaco-nexus.pl")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'portal.db').as_posix()}",
        cookie_secure=False,
        cookie_domain="",
        public_url="",
        chmura_public_url="",
        redis_url="",
        voice_warm_up=False,
        login_attempts_per_15_min=3,
        qdrant_url="http://127.0.0.1:1",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def nadawca(monkeypatch: pytest.MonkeyPatch) -> NadawcaTestowy:
    zapis = NadawcaTestowy()
    monkeypatch.setattr(poczta_portalu, "nadawca", lambda *_: zapis)
    return zapis


def zaloguj_administratora(client: TestClient, settings: Settings) -> None:
    async def ustaw() -> None:
        database = Database(settings.database_url)
        await database.create_schema()
        await set_admin_credentials(database, "admin", HASLO_ADMINISTRATORA)
        await database.close()

    asyncio.run(ustaw())
    odpowiedz = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": HASLO_ADMINISTRATORA},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 200, odpowiedz.text


def utworz_tresc(client: TestClient, **pola: Any) -> dict[str, Any]:
    dane = {"kind": "blog", "title": "Pierwszy wpis", "body": "Treść wpisu o pompach ciepła."} | pola
    odpowiedz = client.post("/api/portal/admin/tresci", json=dane, headers=HEADERS)
    assert odpowiedz.status_code == 201, odpowiedz.text
    return odpowiedz.json()


def opublikuj(client: TestClient, identyfikator: str) -> dict[str, Any]:
    odpowiedz = client.post(
        f"/api/portal/admin/tresci/{identyfikator}/publikacja",
        json={"status": "opublikowany"},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 200, odpowiedz.text
    return odpowiedz.json()


def postarz_sesje(settings: Settings, dni: int) -> None:
    """Cofa datę ostatniej aktywności sesji klienta – symuluje bezczynność."""

    async def zmien() -> None:
        database = Database(settings.database_url)
        async with database.session() as session:
            await session.execute(
                update(PortalSession).values(last_seen_at=utcnow() - timedelta(days=dni))
            )
        await database.close()

    asyncio.run(zmien())


def postarz_potwierdzenia(settings: Settings) -> None:
    """Cofa termin ważności tokenów potwierdzenia adresu – symuluje przeterminowany odsyłacz."""

    async def zmien() -> None:
        database = Database(settings.database_url)
        async with database.session() as session:
            await session.execute(
                update(PortalEmailConfirmation).values(expires_at=utcnow() - timedelta(minutes=1))
            )
        await database.close()

    asyncio.run(zmien())


def liczba_sesji(settings: Settings) -> int:
    """Liczba rekordów sesji klienta w bazie."""

    async def policz() -> int:
        database = Database(settings.database_url)
        async with database.session() as session:
            wynik = await session.scalar(select(func.count()).select_from(PortalSession))
        await database.close()
        return int(wynik or 0)

    return asyncio.run(policz())


def zarejestruj(client: TestClient, email: str = "klient@example.com") -> dict[str, Any]:
    odpowiedz = client.post(
        "/api/portal/konto/rejestracja",
        json={"email": email, "password": HASLO_KLIENTA, "name": "Jan Kowalski"},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 201, odpowiedz.text
    return odpowiedz.json()


# --- przetwarzanie treści -------------------------------------------------------------------------


def test_slug_usuwa_znaki_diakrytyczne() -> None:
    assert tresc.slug("Pierwsze kroki w Nexusie") == "pierwsze-kroki-w-nexusie"
    assert tresc.slug("Zażółć gęślą jaźń!") == "zazolc-gesla-jazn"
    with pytest.raises(tresc.BladTresci):
        tresc.sprawdz_slug("///")


def test_zajawka_i_tekst_wyszukiwania() -> None:
    markdown = "# Nagłówek\n\nTreść z [odsyłaczem](https://example.com) i ```kod```."
    assert "odsyłaczem" in tresc.zajawka("", markdown)
    assert "example.com" not in tresc.zajawka("", markdown)
    indeks = tresc.tekst_wyszukiwania("Pompy ciepła", "Zajawka", markdown, ["Dom", "Ogrzewanie"])
    assert "pompy ciepla" in indeks
    assert "ogrzewanie" in indeks


def test_slowa_zapytania_pomijaja_powtorzenia() -> None:
    assert tresc.slowa_zapytania("Pompy, pompy CIEPŁA!") == ["pompy", "ciepla"]
    assert tresc.slowa_zapytania("   ") == []


def test_adres_pocztowy_walidowany() -> None:
    assert tresc.sprawdz_adres_poczty(" Jan@Example.COM ") == "jan@example.com"
    for zly in ("bez-małpy", "a@b", "a b@example.com"):
        with pytest.raises(tresc.BladTresci):
            tresc.sprawdz_adres_poczty(zly)


# --- ochrona punktów edycyjnych -------------------------------------------------------------------


def test_edycja_wymaga_sesji_administratora(client: TestClient) -> None:
    assert client.get("/api/portal/admin/tresci").status_code == 401
    assert client.post("/api/portal/admin/tresci", json={"kind": "blog", "title": "X"}).status_code == 401


def test_edycja_wymaga_naglowka_csrf(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    bez_naglowka = client.post("/api/portal/admin/tresci", json={"kind": "blog", "title": "Wpis"})
    assert bez_naglowka.status_code == 403
    z_naglowkiem = client.post(
        "/api/portal/admin/tresci", json={"kind": "blog", "title": "Wpis"}, headers=HEADERS
    )
    assert z_naglowkiem.status_code == 201


# --- treści i publikacja --------------------------------------------------------------------------


def test_szkic_jest_niewidoczny_publicznie(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    wpis = utworz_tresc(client)
    assert wpis["status"] == "szkic"
    assert wpis["published_at"] is None
    assert client.get("/api/portal/tresci", params={"typ": "blog"}).json()["total"] == 0
    assert client.get(f"/api/portal/tresci/blog/{wpis['slug']}").status_code == 404
    opublikowany = opublikuj(client, wpis["id"])
    assert opublikowany["published_at"] is not None
    assert client.get("/api/portal/tresci", params={"typ": "blog"}).json()["total"] == 1
    assert client.get(f"/api/portal/tresci/blog/{wpis['slug']}").status_code == 200


def test_adres_pozycji_jest_unikalny_w_rodzaju(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    pierwszy = utworz_tresc(client, title="Pierwsze kroki")
    drugi = utworz_tresc(client, title="Pierwsze kroki")
    assert pierwszy["slug"] == "pierwsze-kroki"
    assert drugi["slug"] == "pierwsze-kroki-2"
    # Ten sam adres w innym rodzaju treści jest dozwolony.
    dokumentacja = utworz_tresc(client, kind="dokumentacja", title="Pierwsze kroki")
    assert dokumentacja["slug"] == "pierwsze-kroki"


def test_zmiana_tresci_aktualizuje_zajawke_i_metadane(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    wpis = utworz_tresc(client)
    zmiana = client.patch(
        f"/api/portal/admin/tresci/{wpis['id']}",
        json={
            "body": "Nowa treść o instalacji fotowoltaiki.",
            "tags": ["Energia", "Energia", "Dom"],
            "seo": {"meta_title": "Fotowoltaika", "meta_description": "Opis", "canonical": "/portal/blog"},
        },
        headers=HEADERS,
    )
    assert zmiana.status_code == 200, zmiana.text
    dane = zmiana.json()
    assert "fotowoltaiki" in dane["excerpt"]
    assert dane["tags"] == ["Energia", "Dom"]
    assert dane["seo"]["meta_title"] == "Fotowoltaika"


def test_metadane_seo_odrzucaja_obcy_schemat(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    wpis = utworz_tresc(client)
    odpowiedz = client.patch(
        f"/api/portal/admin/tresci/{wpis['id']}",
        json={"seo": {"canonical": "javascript:alert(1)"}},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 422


def test_nieznany_rodzaj_i_status_sa_odrzucane(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    assert client.post(
        "/api/portal/admin/tresci", json={"kind": "cennik", "title": "X"}, headers=HEADERS
    ).status_code == 422
    wpis = utworz_tresc(client)
    assert client.post(
        f"/api/portal/admin/tresci/{wpis['id']}/publikacja", json={"status": "gotowe"}, headers=HEADERS
    ).status_code == 422


def test_usuniecie_pozycji(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    wpis = utworz_tresc(client)
    assert client.delete(f"/api/portal/admin/tresci/{wpis['id']}", headers=HEADERS).status_code == 200
    assert client.get(f"/api/portal/admin/tresci/{wpis['id']}").status_code == 404
    assert client.delete("/api/portal/admin/tresci/nie-uuid", headers=HEADERS).status_code == 404


# --- wyszukiwanie ---------------------------------------------------------------------------------


def test_wyszukiwanie_pelnotekstowe(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    pierwszy = utworz_tresc(client, title="Pompy ciepła w domu", body="Współczynnik COP i koszty.")
    drugi = utworz_tresc(
        client, kind="wiedza", title="Fotowoltaika", body="Panele i magazyn energii dla domu."
    )
    trzeci = utworz_tresc(client, title="Szkic o pompach", body="Pompy ciepła – wersja robocza.")
    for wpis in (pierwszy, drugi):
        opublikuj(client, wpis["id"])
    wyniki = client.get("/api/portal/szukaj", params={"q": "pompy ciepła"}).json()
    assert [pozycja["slug"] for pozycja in wyniki["items"]] == [pierwszy["slug"]]
    assert trzeci["slug"] not in [pozycja["slug"] for pozycja in wyniki["items"]]
    # Zapytanie bez znaków diakrytycznych trafia w ten sam wpis.
    assert client.get("/api/portal/szukaj", params={"q": "pompy cieplA"}).json()["total"] == 1
    assert client.get("/api/portal/szukaj", params={"q": "dom", "typ": "wiedza"}).json()["total"] == 1
    assert client.get("/api/portal/szukaj", params={"q": ""}).json()["total"] == 0


def test_wyszukiwanie_nie_trafia_w_srodek_wyrazu(client: TestClient, settings: Settings) -> None:
    """„or” nie jest trafieniem w „który”.

    Dopasowanie ``LIKE '%slowo%'`` wchodziło w środek wyrazów, więc dwuliterowe zapytanie
    wyciągało z bazy wszystko — a wynik wyglądał, jakby wyszukiwarka zgadywała.
    """
    zaloguj_administratora(client, settings)
    wpis = utworz_tresc(
        client, title="Który moduł wybrać", body="Opis modułu, który podpowiada wybór."
    )
    opublikuj(client, wpis["id"])

    assert client.get("/api/portal/szukaj", params={"q": "or"}).json()["total"] == 0
    # Początek wyrazu nadal jest trafieniem — na tym stoi wyszukiwanie po rdzeniu słowa.
    assert client.get("/api/portal/szukaj", params={"q": "modul"}).json()["total"] == 1
    assert client.get("/api/portal/szukaj", params={"q": "ktory"}).json()["total"] == 1


def test_lista_z_filtrem_znacznika(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    wpis = utworz_tresc(client, tags=["Energia"])
    opublikuj(client, wpis["id"])
    assert client.get("/api/portal/tresci", params={"tag": "Energia"}).json()["total"] == 1
    assert client.get("/api/portal/tresci", params={"tag": "Podatki"}).json()["total"] == 0
    assert client.get("/api/portal/znaczniki").json() == [{"tag": "Energia", "count": 1}]


# --- kanały SEO -----------------------------------------------------------------------------------


def test_robots_zamyka_aplikacje(client: TestClient) -> None:
    odpowiedz = client.get("/robots.txt")
    assert odpowiedz.status_code == 200
    assert "Disallow: /api/" in odpowiedz.text
    assert "Allow: /portal" in odpowiedz.text
    assert "Sitemap: https://danaco-nexus.pl/sitemap.xml" in odpowiedz.text


def test_mapa_witryny_i_kanal_atom(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    wpis = utworz_tresc(client, title="Wpis w kanale")
    opublikuj(client, wpis["id"])
    mapa = client.get("/sitemap.xml")
    assert mapa.status_code == 200
    assert "https://danaco-nexus.pl/portal/cennik" in mapa.text
    assert f"https://danaco-nexus.pl/portal/blog/{wpis['slug']}" in mapa.text
    atom = client.get("/portal/atom.xml")
    assert atom.headers["content-type"].startswith("application/atom+xml")
    assert "<title>Wpis w kanale</title>" in atom.text
    assert client.get("/portal/rss.xml").text == atom.text


def test_mapa_witryny_pomija_pozycje_noindex(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    wpis = utworz_tresc(client, title="Strona techniczna", seo={"noindex": True})
    opublikuj(client, wpis["id"])
    assert f"/portal/blog/{wpis['slug']}" not in client.get("/sitemap.xml").text


def test_kanal_escapuje_znaki_xml(settings: Settings) -> None:
    pozycje = [
        type(
            "Pozycja",
            (),
            {
                "title": "Ceny < 100 zł & więcej",
                "slug": "ceny",
                "kind": "blog",
                "excerpt": "Zajawka",
                "author": "",
                "tags": [],
                "seo": {},
                "published_at": None,
                "updated_at": None,
            },
        )()
    ]
    wynik = kanaly.atom("https://danaco-nexus.pl", pozycje)  # type: ignore[arg-type]
    assert "&lt; 100 zł &amp; więcej" in wynik


# --- konta klientów -------------------------------------------------------------------------------


def test_rejestracja_logowanie_i_profil(client: TestClient) -> None:
    dane = zarejestruj(client)
    assert dane["email"] == "klient@example.com"
    assert client.get("/api/portal/konto/ja").json()["name"] == "Jan Kowalski"
    zmiana = client.patch(
        "/api/portal/konto/profil", json={"name": "Jan Nowak", "company": "Danaco"}, headers=HEADERS
    )
    assert zmiana.json()["company"] == "Danaco"
    assert client.post("/api/portal/konto/wylogowanie", headers=HEADERS).status_code == 200
    assert client.get("/api/portal/konto/ja").status_code == 401
    zalogowanie = client.post(
        "/api/portal/konto/logowanie",
        json={"email": "klient@example.com", "password": HASLO_KLIENTA},
        headers=HEADERS,
    )
    assert zalogowanie.status_code == 200
    assert zalogowanie.json()["last_login_at"] is not None


def test_rejestracja_odrzuca_zajety_adres_i_krotkie_haslo(client: TestClient) -> None:
    zarejestruj(client)
    powtorzona = client.post(
        "/api/portal/konto/rejestracja",
        json={"email": "klient@example.com", "password": HASLO_KLIENTA},
        headers=HEADERS,
    )
    assert powtorzona.status_code == 422
    krotkie = client.post(
        "/api/portal/konto/rejestracja",
        json={"email": "inny@example.com", "password": "krotkie"},
        headers=HEADERS,
    )
    assert krotkie.status_code == 422


def test_rejestracje_mozna_wylaczyc(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_PORTAL_REJESTRACJA", "wylaczona")
    odpowiedz = client.post(
        "/api/portal/konto/rejestracja",
        json={"email": "klient@example.com", "password": HASLO_KLIENTA},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 403
    assert client.get("/api/portal/stan").json()["registration_open"] is False


def test_logowanie_klienta_ma_ograniczone_tempo(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEXUS_PORTAL_LOGIN_PROBY_15MIN", "2")
    zarejestruj(client)
    zle = {"email": "klient@example.com", "password": "zle-haslo-2026"}
    assert client.post("/api/portal/konto/logowanie", json=zle, headers=HEADERS).status_code == 401
    assert client.post("/api/portal/konto/logowanie", json=zle, headers=HEADERS).status_code == 401
    assert client.post("/api/portal/konto/logowanie", json=zle, headers=HEADERS).status_code == 429


def test_naglowek_przekierowania_nie_obchodzi_limitu(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Klient spoza proxy nie zmienia klucza licznika nagłówkiem ``X-Forwarded-For``."""
    monkeypatch.setenv("NEXUS_PORTAL_LOGIN_PROBY_15MIN", "2")
    monkeypatch.setenv("NEXUS_PORTAL_RESET_PROBY_15MIN", "2")
    zarejestruj(client)
    zle = {"email": "klient@example.com", "password": "zle-haslo-2026"}
    kody = []
    for numer in range(4):
        naglowki = HEADERS | {"X-Forwarded-For": f"203.0.113.{numer}"}
        kody.append(client.post("/api/portal/konto/logowanie", json=zle, headers=naglowki).status_code)
    assert kody == [401, 401, 429, 429]

    prosby = []
    for numer in range(4):
        naglowki = HEADERS | {"X-Forwarded-For": f"198.51.100.{numer}, 203.0.113.9"}
        prosby.append(
            client.post(
                "/api/portal/konto/odzyskiwanie", json={"email": "klient@example.com"}, headers=naglowki
            ).status_code
        )
    assert prosby == [200, 200, 429, 429]


def test_za_proxy_liczy_sie_ostatni_wpis_przekierowania(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Za własnym proxy licznik rozróżnia klientów po adresie dopisanym przez proxy na końcu."""
    monkeypatch.setenv("NEXUS_PORTAL_LOGIN_PROBY_15MIN", "3")
    dane = {"email": "nieznany@example.com", "password": "zle-haslo-2026"}
    with TestClient(create_app(settings), client=("127.0.0.1", 9000)) as lokalny:
        # Pierwszy wpis podstawia klient, ostatni dopisuje proxy – liczy się ostatni.
        rozni = [
            lokalny.post(
                "/api/portal/konto/logowanie",
                json=dane,
                headers=HEADERS | {"X-Forwarded-For": f"203.0.113.7, 198.51.100.{numer}"},
            ).status_code
            for numer in range(3)
        ]
        assert rozni == [401, 401, 401]
        ten_sam = [
            lokalny.post(
                "/api/portal/konto/logowanie",
                json=dane,
                headers=HEADERS | {"X-Forwarded-For": f"203.0.113.{numer}, 198.51.100.9"},
            ).status_code
            for numer in range(4)
        ]
        assert ten_sam == [401, 401, 401, 429]


def test_zmiana_limitu_prob_dziala_bez_restartu(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEXUS_PORTAL_LOGIN_PROBY_15MIN", "1")
    zarejestruj(client)
    zle = {"email": "klient@example.com", "password": "zle-haslo-2026"}
    assert client.post("/api/portal/konto/logowanie", json=zle, headers=HEADERS).status_code == 401
    assert client.post("/api/portal/konto/logowanie", json=zle, headers=HEADERS).status_code == 429
    monkeypatch.setenv("NEXUS_PORTAL_LOGIN_PROBY_15MIN", "50")
    assert client.post("/api/portal/konto/logowanie", json=zle, headers=HEADERS).status_code == 401


def test_zmiana_hasla_konczy_sesje(client: TestClient) -> None:
    zarejestruj(client)
    zla = client.post(
        "/api/portal/konto/haslo",
        json={"current_password": "nie-to-haslo", "new_password": "nowe-haslo-portalu"},
        headers=HEADERS,
    )
    assert zla.status_code == 401
    zmiana = client.post(
        "/api/portal/konto/haslo",
        json={"current_password": HASLO_KLIENTA, "new_password": "nowe-haslo-portalu"},
        headers=HEADERS,
    )
    assert zmiana.status_code == 200
    assert client.get("/api/portal/konto/ja").status_code == 401
    ponowne = client.post(
        "/api/portal/konto/logowanie",
        json={"email": "klient@example.com", "password": "nowe-haslo-portalu"},
        headers=HEADERS,
    )
    assert ponowne.status_code == 200


def test_odzyskiwanie_hasla_tokenem(client: TestClient, nadawca: NadawcaTestowy) -> None:
    zarejestruj(client)
    client.post("/api/portal/konto/wylogowanie", headers=HEADERS)
    prosba = client.post(
        "/api/portal/konto/odzyskiwanie", json={"email": "klient@example.com"}, headers=HEADERS
    )
    assert prosba.status_code == 200
    token = nadawca.ostatni_token
    ustawienie = client.post(
        "/api/portal/konto/odzyskiwanie/potwierdz",
        json={"token": token, "password": "odzyskane-haslo-2026"},
        headers=HEADERS,
    )
    assert ustawienie.status_code == 200
    # Token jest jednorazowy.
    assert client.post(
        "/api/portal/konto/odzyskiwanie/potwierdz",
        json={"token": token, "password": "inne-haslo-2026"},
        headers=HEADERS,
    ).status_code == 422
    zalogowanie = client.post(
        "/api/portal/konto/logowanie",
        json={"email": "klient@example.com", "password": "odzyskane-haslo-2026"},
        headers=HEADERS,
    )
    assert zalogowanie.status_code == 200


def test_odzyskiwanie_nie_zdradza_istnienia_konta(client: TestClient, nadawca: NadawcaTestowy) -> None:
    odpowiedz = client.post(
        "/api/portal/konto/odzyskiwanie", json={"email": "nieznany@example.com"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 200
    assert nadawca.wiadomosci == []


def test_odzyskiwanie_ma_ograniczone_tempo(
    client: TestClient, nadawca: NadawcaTestowy, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEXUS_PORTAL_RESET_PROBY_15MIN", "1")
    dane = {"email": "klient@example.com"}
    assert client.post("/api/portal/konto/odzyskiwanie", json=dane, headers=HEADERS).status_code == 200
    assert client.post("/api/portal/konto/odzyskiwanie", json=dane, headers=HEADERS).status_code == 429


def test_zmiana_hasla_ma_ograniczone_tempo(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_PORTAL_LOGIN_PROBY_15MIN", "2")
    zarejestruj(client)
    zle = {"current_password": "nie-to-haslo", "new_password": "nowe-haslo-portalu"}
    assert client.post("/api/portal/konto/haslo", json=zle, headers=HEADERS).status_code == 401
    assert client.post("/api/portal/konto/haslo", json=zle, headers=HEADERS).status_code == 401
    assert client.post("/api/portal/konto/haslo", json=zle, headers=HEADERS).status_code == 429


def test_zmiana_hasla_powiadamia_poczta(client: TestClient, nadawca: NadawcaTestowy) -> None:
    zarejestruj(client)
    zmiana = client.post(
        "/api/portal/konto/haslo",
        json={"current_password": HASLO_KLIENTA, "new_password": "nowe-haslo-portalu"},
        headers=HEADERS,
    )
    assert zmiana.status_code == 200
    odbiorca, temat, tresc_wiadomosci = nadawca.wiadomosci[-1]
    assert odbiorca == "klient@example.com"
    assert "hasło" in temat.lower()
    assert "https://danaco-nexus.pl/portal/konto" in tresc_wiadomosci


def test_zmiana_hasla_kasuje_ciasteczko_sesji(client: TestClient) -> None:
    zarejestruj(client)
    assert client.cookies.get(konta.COOKIE_NAME)
    zmiana = client.post(
        "/api/portal/konto/haslo",
        json={"current_password": HASLO_KLIENTA, "new_password": "nowe-haslo-portalu"},
        headers=HEADERS,
    )
    assert zmiana.status_code == 200
    assert konta.COOKIE_NAME in zmiana.headers.get("set-cookie", "")
    assert client.cookies.get(konta.COOKIE_NAME) is None


def test_nowe_haslo_musi_sie_roznic_od_obecnego(client: TestClient) -> None:
    zarejestruj(client)
    odpowiedz = client.post(
        "/api/portal/konto/haslo",
        json={"current_password": HASLO_KLIENTA, "new_password": HASLO_KLIENTA},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 422
    assert "różnić od obecnego" in odpowiedz.json()["detail"]
    # Sesja trwa dalej – odrzucona zmiana niczego nie kasuje.
    assert client.get("/api/portal/konto/ja").status_code == 200


def test_haslo_nie_moze_powtarzac_adresu(client: TestClient) -> None:
    odpowiedz = client.post(
        "/api/portal/konto/rejestracja",
        json={"email": "dlugi.adres@example.com", "password": "dlugi.adres@example.com"},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 422
    assert "adresu e-mail" in odpowiedz.json()["detail"]


def test_komunikaty_bledow_mowia_co_zrobic(client: TestClient) -> None:
    zarejestruj(client)
    zajety = client.post(
        "/api/portal/konto/rejestracja",
        json={"email": "klient@example.com", "password": HASLO_KLIENTA},
        headers=HEADERS,
    )
    assert "Zaloguj się albo odzyskaj hasło" in zajety.json()["detail"]
    krotkie = client.post(
        "/api/portal/konto/rejestracja",
        json={"email": "inny@example.com", "password": "krotkie"},
        headers=HEADERS,
    )
    assert "co najmniej 12" in krotkie.json()["detail"]
    client.post("/api/portal/konto/wylogowanie", headers=HEADERS)
    zle = client.post(
        "/api/portal/konto/logowanie",
        json={"email": "klient@example.com", "password": "zle-haslo-2026"},
        headers=HEADERS,
    )
    assert "ustaw nowe hasło" in zle.json()["detail"]
    assert "Zaloguj się do portalu" in client.get("/api/portal/konto/ja").json()["detail"]


def test_sesja_gasnie_po_bezczynnosci(client: TestClient, settings: Settings) -> None:
    zarejestruj(client)
    assert client.get("/api/portal/konto/ja").status_code == 200
    postarz_sesje(settings, konta.BEZCZYNNOSC.days + 1)
    odpowiedz = client.get("/api/portal/konto/ja")
    assert odpowiedz.status_code == 401
    assert "Sesja wygasła" in odpowiedz.json()["detail"]
    assert liczba_sesji(settings) == 1
    # Kolejne logowanie sprząta bezczynne sesje – w bazie zostaje wyłącznie sesja świeża.
    zalogowanie = client.post(
        "/api/portal/konto/logowanie",
        json={"email": "klient@example.com", "password": HASLO_KLIENTA},
        headers=HEADERS,
    )
    assert zalogowanie.status_code == 200
    assert liczba_sesji(settings) == 1
    assert client.get("/api/portal/konto/ja").status_code == 200


# --- usunięcie konta ------------------------------------------------------------------------------


def test_usuniecie_konta_wymaga_sesji_i_naglowka(client: TestClient) -> None:
    dane = {"password": HASLO_KLIENTA, "confirmation": "USUWAM"}
    assert client.post("/api/portal/konto/usuniecie", json=dane).status_code == 401
    zarejestruj(client)
    assert client.post("/api/portal/konto/usuniecie", json=dane).status_code == 403


def test_usuniecie_konta_wymaga_hasla_i_slowa_potwierdzenia(client: TestClient) -> None:
    zarejestruj(client)
    bez_slowa = client.post(
        "/api/portal/konto/usuniecie",
        json={"password": HASLO_KLIENTA, "confirmation": "tak"},
        headers=HEADERS,
    )
    assert bez_slowa.status_code == 422
    assert "USUWAM" in bez_slowa.json()["detail"]
    zle_haslo = client.post(
        "/api/portal/konto/usuniecie",
        json={"password": "nie-to-haslo", "confirmation": "USUWAM"},
        headers=HEADERS,
    )
    assert zle_haslo.status_code == 401
    assert client.get("/api/portal/konto/ja").status_code == 200


def test_usuniecie_konta_kasuje_dane_i_konczy_sesje(
    client: TestClient, settings: Settings, nadawca: NadawcaTestowy
) -> None:
    zarejestruj(client)
    usuniecie = client.post(
        "/api/portal/konto/usuniecie",
        json={"password": HASLO_KLIENTA, "confirmation": "usuwam"},
        headers=HEADERS,
    )
    assert usuniecie.status_code == 200
    assert nadawca.wiadomosci[-1][0] == "klient@example.com"
    assert client.get("/api/portal/konto/ja").status_code == 401
    assert liczba_sesji(settings) == 0
    ponowne = client.post(
        "/api/portal/konto/logowanie",
        json={"email": "klient@example.com", "password": HASLO_KLIENTA},
        headers=HEADERS,
    )
    assert ponowne.status_code == 401
    zaloguj_administratora(client, settings)
    assert client.get("/api/portal/admin/klienci").json() == []
    # Adres jest znowu wolny – można założyć konto od nowa.
    assert zarejestruj(client)["email"] == "klient@example.com"


def test_konto_i_administrator_to_osobne_sesje(client: TestClient, settings: Settings) -> None:
    zaloguj_administratora(client, settings)
    assert client.get("/api/portal/konto/ja").status_code == 401
    assert client.get("/api/portal/stan").json()["admin"] is True


# --- formularz kontaktu ---------------------------------------------------------------------------


def test_formularz_kontaktu_trafia_do_panelu(client: TestClient, settings: Settings) -> None:
    wiadomosc = {
        "name": "Anna Kowalska",
        "email": "anna@example.com",
        "subject": "Pytanie o wdrożenie",
        "message": "Proszę o kontakt w sprawie wdrożenia dla zespołu.",
    }
    assert client.post("/api/portal/kontakt", json=wiadomosc, headers=HEADERS).status_code == 201
    assert client.post("/api/portal/kontakt", json=wiadomosc).status_code == 403
    assert client.get("/api/portal/admin/wiadomosci").status_code == 401
    zaloguj_administratora(client, settings)
    skrzynka = client.get("/api/portal/admin/wiadomosci").json()
    assert skrzynka[0]["email"] == "anna@example.com"


def test_formularz_kontaktu_ma_ograniczone_tempo(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEXUS_PORTAL_KONTAKT_PROBY_15MIN", "1")
    wiadomosc = {"name": "Anna", "email": "anna@example.com", "message": "Treść zapytania o ofertę."}
    assert client.post("/api/portal/kontakt", json=wiadomosc, headers=HEADERS).status_code == 201
    assert client.post("/api/portal/kontakt", json=wiadomosc, headers=HEADERS).status_code == 429


# --- konfiguracja ---------------------------------------------------------------------------------


def test_ustawienia_portalu_maja_bezpieczne_wartosci(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEXUS_PORTAL_RESET_TTL_MINUTES", "9999")
    monkeypatch.setenv("NEXUS_PORTAL_MAIL_NADAWCA", "nieznany")
    portal = portal_settings(settings)
    assert portal.reset_ttl_minutes == 240
    assert portal.mail_sender == "dziennik"
    assert portal.base_url == "https://danaco-nexus.pl"


def test_nadawca_zastepczy_zapisuje_w_dzienniku(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    portal = portal_settings(settings)
    with caplog.at_level("INFO", logger="nexus.portal.poczta"):
        poczta_portalu.nadawca(settings, portal).wyslij("klient@example.com", "Temat", "Treść")
    assert "klient@example.com" in caplog.text


def test_wyslij_oddaje_wiadomosc_nadawcy(
    settings: Settings, nadawca: NadawcaTestowy
) -> None:
    poczta_portalu.wyslij(settings, portal_settings(settings), "klient@example.com", "Temat", "Treść")
    assert nadawca.wiadomosci == [("klient@example.com", "Temat", "Treść")]


def test_wyslij_zapisuje_w_dzienniku_gdy_wysylka_zawiedzie(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class NadawcaAwaryjny:
        def wyslij(self, odbiorca: str, temat: str, tresc_wiadomosci: str) -> None:
            raise poczta_portalu.BladWysylki("Serwer poczty nie odpowiada.")

    monkeypatch.setattr(poczta_portalu, "nadawca", lambda *_: NadawcaAwaryjny())
    with caplog.at_level("INFO", logger="nexus.portal.poczta"):
        poczta_portalu.wyslij(
            settings, portal_settings(settings), "klient@example.com", "Temat", "Treść"
        )
    assert "nie powiodła się" in caplog.text
    assert "klient@example.com" in caplog.text


def test_wysylka_poczty_nie_blokuje_petli_zdarzen(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nadawca jest synchroniczny (smtplib), więc API musi wołać go w wątku, nie na pętli."""

    class NadawcaSprawdzajacyPetle:
        def __init__(self) -> None:
            self.poza_petla = False

        def wyslij(self, odbiorca: str, temat: str, tresc_wiadomosci: str) -> None:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                self.poza_petla = True

    sprawdzajacy = NadawcaSprawdzajacyPetle()
    monkeypatch.setattr(poczta_portalu, "nadawca", lambda *_: sprawdzajacy)
    zarejestruj(client)
    zmiana = client.post(
        "/api/portal/konto/haslo",
        json={"current_password": HASLO_KLIENTA, "new_password": "nowe-haslo-portalu"},
        headers=HEADERS,
    )
    assert zmiana.status_code == 200
    assert sprawdzajacy.poza_petla is True


# --- potwierdzenie adresu poczty ------------------------------------------------------------------


def test_rejestracja_wysyla_odsylacz_potwierdzenia(
    client: TestClient, nadawca: NadawcaTestowy
) -> None:
    dane = zarejestruj(client)
    assert dane["email_confirmed"] is False
    odbiorca, temat, tresc_wiadomosci = nadawca.wiadomosci[0]
    assert odbiorca == "klient@example.com"
    assert "potwierdź adres" in temat.lower()
    assert "https://danaco-nexus.pl/portal/konto?potwierdzenie=" in tresc_wiadomosci


def test_potwierdzenie_adresu_dziala_tylko_raz(
    client: TestClient, nadawca: NadawcaTestowy
) -> None:
    zarejestruj(client)
    token = nadawca.token_potwierdzenia("klient@example.com")
    pierwsze = client.post("/api/portal/konto/potwierdzenie", json={"token": token}, headers=HEADERS)
    assert pierwsze.status_code == 200
    assert client.get("/api/portal/konto/ja").json()["email_confirmed"] is True
    powtorne = client.post("/api/portal/konto/potwierdzenie", json={"token": token}, headers=HEADERS)
    assert powtorne.status_code == 422
    assert "wygasł albo został już użyty" in powtorne.json()["detail"]


def test_przeterminowany_odsylacz_potwierdzenia_jest_odrzucany(
    client: TestClient, settings: Settings, nadawca: NadawcaTestowy
) -> None:
    zarejestruj(client)
    token = nadawca.token_potwierdzenia("klient@example.com")
    postarz_potwierdzenia(settings)
    odpowiedz = client.post("/api/portal/konto/potwierdzenie", json={"token": token}, headers=HEADERS)
    assert odpowiedz.status_code == 422
    assert client.get("/api/portal/konto/ja").json()["email_confirmed"] is False


def test_konto_dziala_bez_skonfigurowanej_wysylki(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Bez nadawcy SMTP odsyłacz trafia do dziennika, a konto działa ze stanem „niepotwierdzony”."""
    with caplog.at_level("INFO", logger="nexus.portal.poczta"):
        dane = zarejestruj(client)
    assert dane["email_confirmed"] is False
    assert "potwierdzenie=" in caplog.text
    assert client.get("/api/portal/konto/ja").status_code == 200
    zalogowanie = client.post(
        "/api/portal/konto/logowanie",
        json={"email": "klient@example.com", "password": HASLO_KLIENTA},
        headers=HEADERS,
    )
    assert zalogowanie.status_code == 200
    assert zalogowanie.json()["email_confirmed"] is False


def test_ponowna_wysylka_potwierdzenia_wymaga_sesji_i_ma_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, nadawca: NadawcaTestowy
) -> None:
    monkeypatch.setenv("NEXUS_PORTAL_RESET_PROBY_15MIN", "2")
    assert client.post("/api/portal/konto/potwierdzenie/wyslij", headers=HEADERS).status_code == 401
    zarejestruj(client)
    assert client.post("/api/portal/konto/potwierdzenie/wyslij").status_code == 403
    assert client.post("/api/portal/konto/potwierdzenie/wyslij", headers=HEADERS).status_code == 200
    assert client.post("/api/portal/konto/potwierdzenie/wyslij", headers=HEADERS).status_code == 200
    assert client.post("/api/portal/konto/potwierdzenie/wyslij", headers=HEADERS).status_code == 429
    # Nowy odsyłacz unieważnia poprzedni – działa wyłącznie token z ostatniej wiadomości.
    stary = nadawca.wiadomosci[0][2].split("potwierdzenie=")[1].split()[0]
    assert client.post(
        "/api/portal/konto/potwierdzenie", json={"token": stary}, headers=HEADERS
    ).status_code == 422
    nowy = nadawca.token_potwierdzenia("klient@example.com")
    assert client.post(
        "/api/portal/konto/potwierdzenie", json={"token": nowy}, headers=HEADERS
    ).status_code == 200


def test_usuniecie_konta_kasuje_tokeny_potwierdzenia(
    client: TestClient, settings: Settings, nadawca: NadawcaTestowy
) -> None:
    zarejestruj(client)
    token = nadawca.token_potwierdzenia("klient@example.com")
    usuniecie = client.post(
        "/api/portal/konto/usuniecie",
        json={"password": HASLO_KLIENTA, "confirmation": "USUWAM"},
        headers=HEADERS,
    )
    assert usuniecie.status_code == 200
    assert client.post(
        "/api/portal/konto/potwierdzenie", json={"token": token}, headers=HEADERS
    ).status_code == 422


def test_siec_prywatna_nie_jest_zaufanym_proxy(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proxy wdrożenia stoi na pętli zwrotnej; maszyna z sieci prywatnej nie rozsypuje licznika."""
    monkeypatch.setenv("NEXUS_PORTAL_LOGIN_PROBY_15MIN", "2")
    dane = {"email": "nieznany@example.com", "password": "zle-haslo-2026"}
    with TestClient(create_app(settings), client=("10.0.0.5", 9000)) as z_sieci:
        kody = [
            z_sieci.post(
                "/api/portal/konto/logowanie",
                json=dane,
                headers=HEADERS | {"X-Forwarded-For": f"198.51.100.{numer}"},
            ).status_code
            for numer in range(3)
        ]
    assert kody == [401, 401, 429]


def test_stan_sesji_nie_jest_bledem_dla_goscia(client: TestClient) -> None:
    """Pytanie „czy ktoś jest zalogowany” to stan, nie zasób chroniony.

    Portal pytał o to przez `/konto/ja`, które gościowi odpowiada 401 — przeglądarka
    zapisywała wtedy błąd w konsoli na każdej stronie publicznej, choć nic złego się nie
    działo. Ten punkt odpowiada gościowi zwyczajnie.
    """
    odpowiedz = client.get("/api/portal/konto/sesja", headers=HEADERS)
    assert odpowiedz.status_code == 200, odpowiedz.text
    assert odpowiedz.json() == {"konto": None}
    # Zasób chroniony nadal odmawia — to nie jest obejście uwierzytelnienia.
    assert client.get("/api/portal/konto/ja", headers=HEADERS).status_code == 401


KORZEN = Path(__file__).resolve().parents[2]
MATERIAL = """# Pierwsze uruchomienie

Pierwszy akapit materiału.

## Sekcja

Treść sekcji.
"""


def test_material_bierze_tytul_z_naglowka_i_nie_powiela_go_w_tresci(tmp_path: Path) -> None:
    """Stronę pozycji rysuje tytuł osobno, więc treść zaczyna się pod nagłówkiem."""
    katalog = tmp_path / "materialy"
    katalog.mkdir()
    (katalog / "03-pierwsze-uruchomienie.md").write_text(MATERIAL, encoding="utf-8")
    (katalog / "README.md").write_text("# Opis katalogu\n\nNie jest materiałem.\n", encoding="utf-8")

    materialy = wczytaj_katalog(katalog, "dokumentacja")

    assert len(materialy) == 1, "README nie jest materiałem"
    pozycja = materialy[0]
    assert (pozycja.slug, pozycja.tytul, pozycja.pozycja) == (
        "pierwsze-uruchomienie",
        "Pierwsze uruchomienie",
        3,
    )
    assert not pozycja.tresc_md.startswith("# ")
    assert pozycja.tresc_md.startswith("Pierwszy akapit")


@pytest.mark.parametrize(
    ("nazwa", "tresc_pliku"),
    [
        ("bez-numeru.md", MATERIAL),
        ("04-bez-naglowka.md", "Sam akapit, bez nagłówka.\n"),
        ("05-sam-naglowek.md", "# Tytuł\n"),
    ],
)
def test_wadliwy_plik_jest_odrzucany_z_nazwa_pliku(tmp_path: Path, nazwa: str, tresc_pliku: str) -> None:
    """Błąd wskazuje plik — przy wczytywaniu katalogu to jedyna wskazówka dla człowieka."""
    katalog = tmp_path / "materialy"
    katalog.mkdir()
    (katalog / nazwa).write_text(tresc_pliku, encoding="utf-8")

    with pytest.raises(BladMaterialu, match=nazwa):
        wczytaj_katalog(katalog, "dokumentacja")


def test_powtorne_wczytanie_nadpisuje_pozycje_zamiast_ja_powielac(
    settings: Settings, tmp_path: Path
) -> None:
    """Poprawiony plik wczytuje się ponownie; adres pozycji zostaje ten sam."""
    katalog = tmp_path / "materialy"
    katalog.mkdir()
    plik = katalog / "01-pierwsze-uruchomienie.md"
    plik.write_text(MATERIAL, encoding="utf-8")

    async def wczytaj(opublikuj: bool) -> list[tuple[str, str]]:
        database = Database(settings.database_url)
        await database.create_schema()
        try:
            return await zapisz(
                database, wczytaj_katalog(katalog, "dokumentacja"), opublikuj=opublikuj
            )
        finally:
            await database.close()

    assert asyncio.run(wczytaj(False)) == [("dokumentacja/pierwsze-uruchomienie", "nowa")]
    plik.write_text(MATERIAL.replace("Pierwszy akapit", "Poprawiony akapit"), encoding="utf-8")
    assert asyncio.run(wczytaj(True)) == [("dokumentacja/pierwsze-uruchomienie", "zmieniona")]

    async def stan() -> tuple[int, str, str]:
        database = Database(settings.database_url)
        try:
            async with database.session() as session:
                ile = await session.scalar(select(func.count()).select_from(PortalContent))
                rekord = await repozytorium.pobierz(session, "dokumentacja", "pierwsze-uruchomienie")
                return int(ile or 0), rekord.status, rekord.body
        finally:
            await database.close()

    ile, status, body = asyncio.run(stan())
    assert ile == 1
    assert status == "opublikowany"
    assert body.startswith("Poprawiony akapit")


def test_szkice_z_repozytorium_wczytuja_sie_bez_poprawek() -> None:
    """Materiały w `docs/portal/tresci-startowe` mają nadawać się do wczytania takie, jakie są."""
    materialy = wczytaj_katalog(KORZEN / "docs" / "portal" / "tresci-startowe", "dokumentacja")

    assert len(materialy) >= 5
    assert [pozycja.pozycja for pozycja in materialy] == sorted(
        pozycja.pozycja for pozycja in materialy
    )
    assert all(pozycja.tytul and pozycja.tresc_md for pozycja in materialy)


def test_szkice_nie_maja_zawinietych_akapitow() -> None:
    """Portal renderuje treść przez `marked` z `breaks: true` — złamany wiersz staje się `<br>`.

    Akapit rozbity na dwa wiersze wygląda w przeglądarce jak zdanie przecięte w połowie,
    a w pliku nie widać niczego podejrzanego. Stąd ten test: akapit ma być jednym wierszem.
    """
    # Wiersze zaczynające się od tych znaków to nagłówki, wypunktowania, tabele, cytaty
    # i bloki kodu — tam złamanie wiersza jest częścią składni, nie przypadkiem.
    skladnia = ("#", "-", "|", ">", "`", "*", "1.", "2.", "3.")
    zawiniete: list[str] = []
    katalog = KORZEN / "docs" / "portal" / "tresci-startowe"
    # README opisuje katalog człowiekowi i nie trafia do portalu, więc zawijanie mu wolno.
    for plik in sorted(p for p in katalog.glob("*.md") if p.name not in POMIJANE):
        poprzedni = ""
        for numer, wiersz in enumerate(plik.read_text(encoding="utf-8").splitlines(), start=1):
            proza = bool(wiersz.strip()) and not wiersz.startswith(skladnia)
            if proza and poprzedni.strip() and not poprzedni.startswith(skladnia):
                zawiniete.append(f"{plik.name}:{numer}")
            poprzedni = wiersz

    assert zawiniete == [], f"akapity złamane na dwa wiersze: {zawiniete}"


def test_katalog_materialow_dziala_takze_z_katalogu_uslugi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Usługa pracuje w `backend/`, a materiały leżą w `docs/` — ścieżka z dokumentacji ma trafiać.

    Bez tego polecenie z README („--katalog docs/portal/tresci-startowe”) kończyło się
    „nie ma takiego katalogu”, zależnie od tego, skąd je uruchomiono.
    """
    monkeypatch.chdir(KORZEN / "backend")

    materialy = wczytaj_katalog(Path("docs/portal/tresci-startowe"), "dokumentacja")

    assert len(materialy) >= 5


def test_dwa_pliki_o_tym_samym_adresie_sa_bledem(tmp_path: Path) -> None:
    """Portal nadałby drugiemu adres „start-2” — cichy rozjazd nazwy pliku z adresem pozycji."""
    katalog = tmp_path / "materialy"
    katalog.mkdir()
    (katalog / "01-start.md").write_text(MATERIAL, encoding="utf-8")
    (katalog / "02-start.md").write_text(MATERIAL, encoding="utf-8")

    with pytest.raises(BladMaterialu, match="start"):
        wczytaj_katalog(katalog, "dokumentacja")


def test_diagnostyka_ostrzega_gdy_poczta_portalu_nie_dochodzi(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rejestracja otwarta plus nadawca „dziennik” = klient czeka na wiadomość, która nie przyjdzie.

    Ekran i tak mówi „wysłaliśmy odsyłacz”, więc po stronie użytkownika nic tego nie zdradza.
    """
    from nexus.doctor import check_poczta_portalu

    monkeypatch.setenv("NEXUS_PORTAL_REJESTRACJA", "true")
    monkeypatch.delenv("NEXUS_PORTAL_MAIL_NADAWCA", raising=False)

    wynik = asyncio.run(check_poczta_portalu(settings))

    assert wynik.ok is False
    assert "nie dotrą" in wynik.detail

    # Zamknięta rejestracja i pusta baza kont: nikt nie czeka na wiadomość.
    monkeypatch.setenv("NEXUS_PORTAL_REJESTRACJA", "false")
    assert asyncio.run(check_poczta_portalu(settings)).ok is True

    # Ale gdy konta już są, odzyskanie hasła dotyczy ich niezależnie od rejestracji.
    async def zaloz_konto() -> None:
        database = Database(settings.database_url)
        await database.create_schema()
        async with database.session() as session:
            await konta.utworz_konto(session, email="klient@example.com", haslo=HASLO_KLIENTA, name="Klient")
        await database.close()

    asyncio.run(zaloz_konto())
    z_kontami = asyncio.run(check_poczta_portalu(settings))
    assert z_kontami.ok is False
    assert "odzyskanie hasła" in z_kontami.detail


def test_mapa_modulow_wymienia_wszystkie_moduly_okna() -> None:
    """Artykuł „Co gdzie znajdziesz” ma nadążać za paskiem modułów.

    Artykuł jest pierwszym miejscem, do którego klient zagląda, kiedy czegoś nie może
    znaleźć. Pasek modułów rośnie w kodzie i nikt nie pamięta, żeby dopisać nową pozycję
    do tekstu na portalu — tak wypadły z niego „Płatności”, czyli akurat ten moduł,
    w którym klient załatwia subskrypcję i faktury. Ten test pilnuje, żeby każdy moduł
    z rejestru interfejsu miał swój wiersz w artykule.
    """
    artykul = (KORZEN / "docs" / "portal" / "tresci-startowe" / "05-mapa-modulow.md").read_text(
        encoding="utf-8"
    )
    wymienione = set(re.findall(r"^- \*\*(.+?)\*\*", artykul, re.MULTILINE))

    # Opis modułu leży przy jego stronie: `export const module: NexusModule = { … }`.
    opis = re.compile(r"export const module: NexusModule = \{(.*?)\n\};", re.DOTALL)
    etykieta = re.compile(r'\blabel:\s*"([^"]+)"')
    nazwy: set[str] = set()
    for plik in (KORZEN / "frontend" / "src").rglob("index.tsx"):
        for blok in opis.findall(plik.read_text(encoding="utf-8")):
            znaleziona = etykieta.search(blok)
            if znaleziona:
                nazwy.add(znaleziona.group(1))

    assert nazwy, "nie znaleziono żadnego opisu modułu — zmienił się kształt rejestru"
    brakujace = sorted(nazwy - wymienione)
    assert brakujace == [], f"moduły bez wiersza w mapie modułów portalu: {brakujace}"


def test_rdzenie_slowa_obejmuja_polska_odmiane() -> None:
    """Wyszukiwarka dopasowuje początek wyrazu, a polszczyzna odmienia końcówki.

    Klient piszący „faktury” nie znajdował artykułu, w którym stoi „fakturach”: żadne
    z tych słów nie jest początkiem drugiego. Rdzenie zasypują tę dziurę, ale nie wolno
    im skracać w nieskończoność — inaczej wyszukiwanie zamienia się w zgadywanie.
    """
    from nexus.portal.repozytorium import MIN_RDZEN, _rdzenie

    # Warunek wyszukiwania brzmi „w tekście jest wyraz zaczynający się od wariantu”,
    # więc sprawdzamy to, co naprawdę rozstrzyga: czy któryś wariant zapytania jest
    # początkiem słowa zapisanego w treści.
    def trafia(zapytanie: str, w_tekscie: str) -> bool:
        return any(w_tekscie.startswith(wariant) for wariant in _rdzenie(zapytanie))

    assert trafia("faktury", "fakturach")
    assert trafia("faktura", "fakturami")
    assert trafia("umowa", "umowy")
    assert trafia("umowy", "umowie")
    # Bez rdzeni żadne z tych zapytań nie trafiało: „faktury” nie jest początkiem
    # „fakturach”, a „umowa” nie jest początkiem „umowy”.
    assert not "fakturach".startswith("faktury")
    assert not "umowy".startswith("umowa")

    # Całe słowo zawsze zostaje jako pierwszy wariant.
    assert _rdzenie("faktury")[0] == "faktury"

    # Krótkich słów nie skracamy wcale: „ai”, „ocr”, „kody”.
    for krotkie in ("ai", "ocr", "kody", "plik"):
        assert _rdzenie(krotkie) == [krotkie]

    # Żaden wariant nie schodzi poniżej progu.
    for slowo in ("dokumentach", "ustawienia", "faktury", "strona"):
        assert all(len(rdzen) >= MIN_RDZEN for rdzen in _rdzenie(slowo))


def test_znacznik_z_procentem_nie_pasuje_do_wszystkiego() -> None:
    """Znacznik idzie do wzorca `LIKE` prosto z adresu — wieloznaczniki muszą być zasłonięte.

    Słowa zapytania przechodzą przez `slowa_zapytania`, które przepuszcza wyłącznie litery
    i cyfry. Znacznik nie: `?tag=%` trafiał tą samą drogą do wzorca i pasował do każdej
    pozycji w bazie.
    """
    from nexus.portal.repozytorium import _zaslon

    assert _zaslon("%") == "\\%"
    assert _zaslon("a_b") == "a\\_b"
    assert _zaslon("100%") == "100\\%"
    # Sam znak zasłaniający też trzeba zasłonić, inaczej „\\%” przeszłoby jako wieloznacznik.
    assert _zaslon("\\") == "\\\\"
    # Zwykły znacznik zostaje bez zmian.
    assert _zaslon("cennik") == "cennik"
