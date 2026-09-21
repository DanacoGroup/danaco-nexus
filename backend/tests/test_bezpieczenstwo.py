"""Testy poprawek bezpieczeństwa nowych powierzchni publicznych: konta, płatności, pokaz.

Każdy test opisuje jedno nadużycie, które przed poprawką było możliwe: wejście konta
klienta do panelu redakcyjnego portalu, obejście liczników prób nagłówkiem przekazania,
przejęcie cudzej rozmowy przez import z chmury, przyjęcie webhooka o dowolnym rozmiarze,
przypisanie planu z cudzej sesji zakupu i wyciek treści błędu serwera do gościa pokazu.
"""

from __future__ import annotations

import asyncio
import io
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from biuro_pomoc import HEADERS as HEADERS_BIURO
from biuro_pomoc import api, biuro_settings  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_api import HEADERS, PASSWORD, client, set_password, settings  # noqa: F401
from test_biuro_cloud import FakeNextcloud
from test_izolacja_kont import KLIENT_HASLO, zaloguj, zaloz_konto, zapelnij_przestrzen  # noqa: F401

from nexus import model_krotki as model_pokazu
from nexus.api.auth import SSO_USER_HEADER
from nexus.config import Settings
from nexus.db import ADMIN_OWNER, Conversation, Database, StoredFile
from nexus.demo.gotowosc import NA_ZYWO
from nexus.demo.przebieg import (
    BLAD_DLA_GOSCIA,
    WLASCICIEL_POKAZU,
    Przebieg,
    Wykonanie,
    _kontekst,
    uruchom,
    ustawienia_demo,
)
from nexus.demo.scenariusze import Krok, Scenariusz
from nexus.demo.sesje import BladPiaskownicy, Piaskownica
from nexus.platnosci.klient import BladStripe
from nexus.platnosci.plany import PLAN_DOMYSLNY
from nexus.platnosci.uprawnienia import limity_planu, opis_przestrzeni
from nexus.platnosci.uslugi import zsynchronizuj_po_powrocie
from nexus.pulpit import MEMORY_BROKER, online_computers
from nexus.tools import pc as narzedzia_pc
from nexus.tools.base import ToolContext, ToolError

# Adres, który przed poprawką wystarczyło podać w nagłówku, aby licznik prób liczył
# każde żądanie osobno.
PODSZYCIE = "203.0.113.%s"
KLIENT_POCZTA = "klient@example.com"


# --- panel redakcyjny portalu: sesja to za mało, potrzebny właściciel instalacji ---


@pytest.mark.parametrize(
    "sciezka", ["/api/portal/admin/klienci", "/api/portal/admin/wiadomosci", "/api/portal/admin/tresci"]
)
def test_panel_portalu_zamkniety_dla_konta_klienta(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
    sciezka: str,
) -> None:
    """Konto klienta loguje się do aplikacji, ale nie do panelu redakcyjnego portalu."""
    set_password(settings)
    zaloz_konto(settings, KLIENT_POCZTA)
    zaloguj(client, KLIENT_POCZTA, KLIENT_HASLO)
    assert client.get(sciezka).status_code == 403, "konto klienta widziało dane wszystkich klientów"


def test_panel_portalu_otwarty_dla_administratora(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Ta sama ścieżka działa dla właściciela instalacji — poprawka niczego mu nie odbiera."""
    set_password(settings)
    zaloguj(client, "admin", PASSWORD)
    assert client.get("/api/portal/admin/klienci").status_code == 200


def test_konto_probne_nie_redaguje_portalu(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Gość bez rejestracji dostaje sesję aplikacji — i nadal żadnego wpływu na portal."""
    set_password(settings)
    assert client.post("/api/auth/gosc", headers=HEADERS).status_code == 200
    nowa = client.post(
        "/api/portal/admin/tresci",
        json={"kind": "blog", "title": "Wpis gościa", "status": "opublikowany"},
        headers=HEADERS,
    )
    assert nowa.status_code == 403, "konto próbne publikowało treść na stronie publicznej"
    assert client.get("/api/portal/stan").json()["admin"] is False


# --- liczniki prób: nagłówek przekazania nie może pochodzić od klienta ---


def test_naglowek_przekazania_nie_omija_limitu_kont_probnych(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Zmienny ``X-Forwarded-For`` nie rozdziela limitu kont próbnych na wiele adresów."""
    set_password(settings)
    for numer in range(settings.goscie_na_adres):
        naglowki = {**HEADERS, "X-Forwarded-For": PODSZYCIE % numer}
        assert client.post("/api/auth/gosc", headers=naglowki).status_code == 200
    odmowa = client.post("/api/auth/gosc", headers={**HEADERS, "X-Forwarded-For": PODSZYCIE % 99})
    assert odmowa.status_code == 429, "każdy nagłówek zakładał konta próbne od nowa"


def test_naglowek_przekazania_nie_omija_licznika_logowan(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Zmienny ``X-Forwarded-For`` nie zeruje licznika nieudanych logowań."""
    set_password(settings)
    for numer in range(settings.login_attempts_per_15_min):
        naglowki = {**HEADERS, "X-Forwarded-For": PODSZYCIE % numer}
        odpowiedz = client.post(
            "/api/auth/login", json={"username": "admin", "password": "zle"}, headers=naglowki
        )
        assert odpowiedz.status_code == 401
    zablokowane = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "zle"},
        headers={**HEADERS, "X-Forwarded-For": PODSZYCIE % 99},
    )
    assert zablokowane.status_code == 429, "zgadywanie hasła szło bez ograniczenia"


# --- import z chmury: plik i rozmowa należą do konta, które go zleciło ---


@pytest.fixture
def chmura(api: TestClient) -> FakeNextcloud:  # noqa: F811
    atrapa = FakeNextcloud()
    api.app.state.cloud_transport = atrapa.transport()
    return atrapa


def _rozmowa_admina(ustawienia: Settings) -> uuid.UUID:
    """Rozmowa właściciela instalacji — cel próby dołożenia plików z cudzego konta."""

    async def run() -> uuid.UUID:
        database = Database(ustawienia.database_url)
        async with database.session() as session:
            rozmowa = Conversation(owner_id=ADMIN_OWNER, title="Sprawy właściciela")
            session.add(rozmowa)
            await session.flush()
            identyfikator = rozmowa.id
        await database.close()
        return identyfikator

    return asyncio.run(run())


def _pliki_konta(ustawienia: Settings, owner: uuid.UUID) -> list[str]:
    async def run() -> list[str]:
        database = Database(ustawienia.database_url)
        async with database.session() as session:
            rekordy = (await session.scalars(select(StoredFile).where(StoredFile.owner_id == owner))).all()
            nazwy = [rekord.name for rekord in rekordy]
        await database.close()
        return nazwy

    return asyncio.run(run())


def _klient_w_chmurze(api: TestClient, ustawienia: Settings) -> uuid.UUID:  # noqa: F811
    """Loguje konto klienta w kliencie testowym i zwraca jego identyfikator."""
    zaloz_konto(ustawienia, KLIENT_POCZTA)
    api.post("/api/auth/logout", headers=HEADERS_BIURO)
    api.post(
        "/api/auth/login",
        json={"username": KLIENT_POCZTA, "password": KLIENT_HASLO},
        headers=HEADERS_BIURO,
    )

    async def run() -> uuid.UUID:
        from nexus.models.portal import PortalUser

        database = Database(ustawienia.database_url)
        async with database.session() as session:
            user = await session.scalar(select(PortalUser).where(PortalUser.email == KLIENT_POCZTA))
            assert user is not None
            identyfikator = user.id
        await database.close()
        return identyfikator

    return asyncio.run(run())


def test_plik_z_chmury_nalezy_do_konta_klienta(
    api: TestClient,  # noqa: F811
    biuro_settings: Settings,  # noqa: F811
    chmura: FakeNextcloud,
) -> None:
    """Plik wzięty z chmury zapisuje się na koncie klienta, nie na koncie właściciela."""
    konto = _klient_w_chmurze(api, biuro_settings)
    api.put("/api/cloud/plik", params={"path": "/Notatka.txt"}, content=b"Tekst", headers=HEADERS_BIURO)
    odpowiedz = api.post(
        "/api/cloud/do-rozmowy", json={"paths": ["/Notatka.txt"], "send": False}, headers=HEADERS_BIURO
    )
    assert odpowiedz.status_code == 200, odpowiedz.text
    assert _pliki_konta(biuro_settings, konto) == ["Notatka.txt"]
    assert _pliki_konta(biuro_settings, ADMIN_OWNER) == [], "plik klienta trafiał do wykazu właściciela"


def test_chmura_nie_dolaczy_plikow_do_cudzej_rozmowy(
    api: TestClient,  # noqa: F811
    biuro_settings: Settings,  # noqa: F811
    chmura: FakeNextcloud,
) -> None:
    """Sam identyfikator cudzej rozmowy nie wystarcza, aby dołożyć do niej pliki."""
    cudza = _rozmowa_admina(biuro_settings)
    _klient_w_chmurze(api, biuro_settings)
    api.put("/api/cloud/plik", params={"path": "/Notatka.txt"}, content=b"Tekst", headers=HEADERS_BIURO)
    odpowiedz = api.post(
        "/api/cloud/do-rozmowy",
        json={"paths": ["/Notatka.txt"], "conversation_id": str(cudza), "send": False},
        headers=HEADERS_BIURO,
    )
    assert odpowiedz.status_code == 404, "pliki dopisywały się do rozmowy innego konta"


# --- webhook płatności: rozmiar treści ograniczony przed sprawdzeniem podpisu ---


def test_webhook_odrzuca_zbyt_duza_tresc(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Nieuwierzytelnione żądanie nie wprowadza do pamięci procesu dowolnej ilości danych."""
    set_password(settings)
    odpowiedz = client.post(
        "/api/platnosci/webhook",
        content=b"x" * (2 * 1024 * 1024),
        headers={"Stripe-Signature": "t=1,v1=nieprawda"},
    )
    assert odpowiedz.status_code == 413, odpowiedz.text


# --- powrót z Checkoutu: sesja zakupu musi wskazywać konto ---


class _SesjaBezKonta:
    """Atrapa Stripe zwracająca sesję Checkout bez oznaczenia konta."""

    async def pobierz_sesje_checkout(self, identyfikator: str) -> dict[str, Any]:
        return {"id": identyfikator, "subscription": "sub_obce"}


def test_powrot_wymaga_oznaczenia_konta() -> None:
    """Sesja zakupu bez ``client_reference_id`` nie przypisuje planu do konta pytającego."""

    async def run() -> None:
        await zsynchronizuj_po_powrocie(None, _SesjaBezKonta(), None, str(uuid.uuid4()), "cs_obce")

    with pytest.raises(BladStripe) as blad:
        asyncio.run(run())
    assert blad.value.status == 403


# --- pokaz: komunikat dla gościa bez treści z serwera ---


def test_model_pokazu_nie_podaje_sciezki_programu(tmp_path: Path) -> None:
    """Nieudane uruchomienie programu opisuje fakt, a nie ścieżkę na serwerze."""
    uruchamiacz = model_pokazu._domyslny_uruchamiacz(5)
    brakujacy = str(tmp_path / "nie-ma-takiego-programu")
    with pytest.raises(model_pokazu.BladModelu) as blad:
        uruchamiacz([brakujacy], {}, tmp_path)
    assert brakujacy not in str(blad.value)


def test_model_pokazu_nie_powtarza_bledu_silnika() -> None:
    """Treść błędu silnika zostaje w dzienniku — gość dostaje samo stwierdzenie faktu."""
    with pytest.raises(model_pokazu.BladModelu) as blad:
        model_pokazu.odczytaj_odpowiedz('{"is_error": true, "result": "klucz sk_live_tajny odrzucony"}')
    assert "sk_live_tajny" not in str(blad.value)


def _scenariusz_z_bledem(komunikat: str, wyjatek: type[Exception] = RuntimeError) -> Scenariusz:
    def polecenie(_postep: Any) -> str:
        raise wyjatek(komunikat)

    return Scenariusz(
        id="test-bledu",
        tytul="Scenariusz testowy",
        opis="Krok, który kończy się nieprzewidzianym wyjątkiem.",
        wiadomosc="",
        przyklady=(),
        kroki=(Krok(etykieta="Krok", polecenie=polecenie),),
    )


def test_przebieg_pokazu_nie_ujawnia_tresci_wyjatku(settings: Settings) -> None:  # noqa: F811
    """Nieprzewidziany wyjątek przebiegu nie wraca do przeglądarki gościa swoją treścią."""
    tajemnica = "/danaco/dane/haslo-bazy"
    piaskownica = Piaskownica(settings)
    sesja = piaskownica.utworz("198.51.100.7")
    wykonanie = Wykonanie(settings=settings, piaskownica=piaskownica, pauza=False)

    async def run() -> Przebieg:
        przebieg = uruchom(wykonanie, sesja, _scenariusz_z_bledem(tajemnica), NA_ZYWO, [])
        assert przebieg.zadanie is not None
        await przebieg.zadanie
        return przebieg

    przebieg = asyncio.run(run())
    assert przebieg.stan == "blad"
    assert tajemnica not in przebieg.blad


# --- logowanie jednokrotne do chmury: tylko właściciel instalacji ---


def test_sso_nie_wpuszcza_konta_probnego_do_chmury(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Sesja konta próbnego nie wydaje nagłówka, którym Caddy loguje konto w Nextcloud."""
    set_password(settings)
    assert client.post("/api/auth/gosc", headers=HEADERS).status_code == 200
    odpowiedz = client.get("/api/auth/sso")
    assert odpowiedz.status_code == 204
    assert SSO_USER_HEADER.lower() not in odpowiedz.headers, "gość wchodził do chmury właściciela"


def test_sso_nie_wpuszcza_konta_klienta_do_chmury(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Konto klienta portalu loguje się do aplikacji, ale nie do chmury osobistej właściciela."""
    set_password(settings)
    zaloz_konto(settings, KLIENT_POCZTA)
    zaloguj(client, KLIENT_POCZTA, KLIENT_HASLO)
    odpowiedz = client.get("/api/auth/sso")
    assert odpowiedz.status_code == 204
    assert SSO_USER_HEADER.lower() not in odpowiedz.headers


def test_sso_wpuszcza_wlasciciela_instalacji(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Ta sama ścieżka nadal loguje właściciela instalacji — poprawka niczego mu nie odbiera."""
    set_password(settings)
    zaloguj(client, "admin", PASSWORD)
    odpowiedz = client.get("/api/auth/sso")
    assert odpowiedz.headers[SSO_USER_HEADER] == settings.chmura_user


# --- przekaźnik komputera: komputer należy do konta, które wydało klucz ---


def test_konto_probne_nie_widzi_komputera_wlasciciela(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Wykaz komputerów pokazuje maszyny konta, nie wszystkie podłączone do instalacji."""
    MEMORY_BROKER._online.clear()
    set_password(settings)
    zaloguj(client, "admin", PASSWORD)
    klucz = client.post("/api/urzadzenia", json={"name": "Laptop", "kind": "desktop"}, headers=HEADERS)
    assert klucz.status_code == 201, klucz.text
    with client.websocket_connect("/api/pulpit/ws") as gniazdo:
        gniazdo.send_json({"type": "auth", "token": klucz.json()["token"], "host": "BIURO-PC"})
        assert gniazdo.receive_json()["type"] == "ready"
        assert [item["host"] for item in client.get("/api/pulpit/komputery").json()] == ["BIURO-PC"]
        assert client.post("/api/auth/gosc", headers=HEADERS).status_code == 200
        widziane = client.get("/api/pulpit/komputery")
        assert widziane.status_code == 200, widziane.text
        assert widziane.json() == [], "konto próbne sięgało do komputera właściciela instalacji"


def test_wykaz_komputerow_rozdziela_konta() -> None:
    """Funkcja wykazu oddaje maszyny wskazanego konta, nie wszystkie podłączone."""
    wpis = {"name": "Laptop", "host": "BIURO-PC", "seen": time.time(), "connected_at": 1.0}

    class Rejestr:
        def online_sync(self) -> dict[str, str]:
            return {"urzadzenie-1": json.dumps({**wpis, "owner": str(ADMIN_OWNER)})}

    rejestr = Rejestr()
    assert [c["host"] for c in online_computers(rejestr, owner=str(ADMIN_OWNER))] == ["BIURO-PC"]  # type: ignore[arg-type]
    assert online_computers(rejestr, owner=str(uuid.uuid4())) == []  # type: ignore[arg-type]


def test_narzedzie_pc_pyta_o_komputery_swojego_konta(
    settings: Settings,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dowód dla samego narzędzia: ``pc_info`` podaje przekaźnikowi konto przebiegu.

    Poprzedni test sprawdzał funkcję wykazu, więc podmiana konta w ``tools/pc.py`` na stałą
    przechodziła niezauważona. Tutaj liczy się wartość, którą narzędzie naprawdę przekazuje.
    """
    konto = uuid.uuid4()
    przekazane: dict[str, Any] = {}

    def falszywe_wywolanie(_broker: Any, _tool: str, _payload: Any, **nazwane: Any) -> Any:
        przekazane.update(nazwane)
        return {"data": {}}, {"name": "Laptop", "host": "BIURO-PC"}

    monkeypatch.setattr(narzedzia_pc, "sync_broker", lambda _settings: MEMORY_BROKER)
    monkeypatch.setattr(narzedzia_pc, "call_computer", falszywe_wywolanie)
    kontekst = ToolContext(
        settings,
        uuid.uuid4(),
        resolve_file=lambda _id: None,  # type: ignore[arg-type,return-value]
        cancel=threading.Event(),
        progress=lambda _tekst: None,
        owner_id=konto,
    )
    narzedzia_pc.pc_info(kontekst, narzedzia_pc.PcInfoInput())
    assert przekazane["owner"] == str(konto), "narzędzie pytało o cudze komputery"
    assert przekazane["owner"] != str(ADMIN_OWNER)


# --- pokaz: błąd narzędzia i modelu bez treści z serwera ---


def test_przebieg_pokazu_nie_ujawnia_bledu_narzedzia(settings: Settings) -> None:  # noqa: F811
    """Błąd narzędzia niesie ścieżkę programu i stderr — gość dostaje sam fakt błędu."""
    tajemnica = "/danaco/programy/qpdf zakończył się błędem (2)"
    piaskownica = Piaskownica(settings)
    sesja = piaskownica.utworz("198.51.100.8")
    wykonanie = Wykonanie(settings=settings, piaskownica=piaskownica, pauza=False)

    async def run() -> Przebieg:
        scenariusz = _scenariusz_z_bledem(tajemnica, ToolError)
        przebieg = uruchom(wykonanie, sesja, scenariusz, NA_ZYWO, [])
        assert przebieg.zadanie is not None
        await przebieg.zadanie
        return przebieg

    przebieg = asyncio.run(run())
    assert przebieg.stan == "blad"
    assert tajemnica not in przebieg.blad
    assert przebieg.blad == BLAD_DLA_GOSCIA


def test_przebieg_pokazu_nie_ujawnia_bledu_modelu(settings: Settings) -> None:  # noqa: F811
    """To samo dotyczy błędu silnika modelu, który w treści niesie dane uruchomienia."""
    tajemnica = "klucz sk_live_tajny odrzucony"
    piaskownica = Piaskownica(settings)
    sesja = piaskownica.utworz("198.51.100.9")
    wykonanie = Wykonanie(settings=settings, piaskownica=piaskownica, pauza=False)

    async def run() -> Przebieg:
        scenariusz = _scenariusz_z_bledem(tajemnica, model_pokazu.BladModelu)
        przebieg = uruchom(wykonanie, sesja, scenariusz, NA_ZYWO, [])
        assert przebieg.zadanie is not None
        await przebieg.zadanie
        return przebieg

    przebieg = asyncio.run(run())
    assert przebieg.stan == "blad" and tajemnica not in przebieg.blad


def test_przebieg_pokazu_powtarza_komunikat_piaskownicy(settings: Settings) -> None:  # noqa: F811
    """Komunikaty piaskownicy pisane są dla gościa, więc mają wracać dosłownie."""
    powod = "Poczekaj na zakończenie bieżącego przebiegu."
    piaskownica = Piaskownica(settings)
    sesja = piaskownica.utworz("198.51.100.10")
    wykonanie = Wykonanie(settings=settings, piaskownica=piaskownica, pauza=False)

    async def run() -> Przebieg:
        scenariusz = _scenariusz_z_bledem(powod, BladPiaskownicy)
        przebieg = uruchom(wykonanie, sesja, scenariusz, NA_ZYWO, [])
        assert przebieg.zadanie is not None
        await przebieg.zadanie
        return przebieg

    assert asyncio.run(run()).blad == powod


# --- import z chmury: przydział przestrzeni planu obowiązuje tak samo jak przy wgraniu ---


def test_import_z_chmury_respektuje_przestrzen_planu(
    api: TestClient,  # noqa: F811
    biuro_settings: Settings,  # noqa: F811
    chmura: FakeNextcloud,
) -> None:
    """Pełna przestrzeń konta odrzuca plik z chmury tak samo jak plik wgrany z dysku."""
    _klient_w_chmurze(api, biuro_settings)
    limity = limity_planu(PLAN_DOMYSLNY, "brak")
    pierwszy = api.post(
        "/api/files",
        files={"file": ("notatka.txt", io.BytesIO(b"x" * 10), "text/plain")},
        headers=HEADERS_BIURO,
    )
    assert pierwszy.status_code == 201, pierwszy.text
    zapelnij_przestrzen(biuro_settings, uuid.UUID(pierwszy.json()["id"]), limity.przestrzen_mb * 1024 * 1024)

    api.put("/api/cloud/plik", params={"path": "/Notatka.txt"}, content=b"Tekst", headers=HEADERS_BIURO)
    odrzucony = api.post(
        "/api/cloud/do-rozmowy", json={"paths": ["/Notatka.txt"], "send": False}, headers=HEADERS_BIURO
    )
    assert odrzucony.status_code == 413, odrzucony.text
    detail = odrzucony.json()["detail"]
    assert "Przestrzeń konta" in detail and opis_przestrzeni(limity.przestrzen_mb) in detail


# --- pliki: dokument SVG nie wyświetla się w domenie aplikacji ---


def test_svg_z_parametrem_nie_wyswietla_sie_w_przegladarce(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Parametr przy typie nośnika nie omija zakazu wyświetlania dokumentów SVG."""
    set_password(settings)
    zaloguj(client, "admin", PASSWORD)
    wgrany = client.post(
        "/api/files",
        files={
            "file": (
                "rysunek.svg",
                io.BytesIO(b"<svg xmlns='http://www.w3.org/2000/svg'/>"),
                "image/svg+xml; charset=utf-8",
            )
        },
        headers=HEADERS,
    )
    assert wgrany.status_code == 201, wgrany.text
    assert wgrany.json()["mime"] == "image/svg+xml"
    pobrany = client.get(f"/api/files/{wgrany.json()['id']}/download", params={"inline": 1})
    assert pobrany.status_code == 200, pobrany.text
    assert pobrany.headers["content-type"] == "application/octet-stream"
    assert pobrany.headers["content-disposition"].startswith("attachment"), "SVG szedł do wyświetlenia"


# --- moduł Kod: projekt to cudza przestrzeń wykonywania programów ---


def _projekt_wlasciciela(
    klient: TestClient, ustawienia: Settings, nazwa: str = "projekt-wlasciciela"
) -> None:
    """Właściciel instalacji zakłada projekt modułu Kod."""
    set_password(ustawienia)
    zaloguj(klient, "admin", PASSWORD)
    utworzony = klient.post("/api/kod/projekty", json={"name": nazwa}, headers=HEADERS)
    assert utworzony.status_code == 201, utworzony.text


def test_konto_probne_nie_siega_do_projektu_wlasciciela(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Gość zakładał projekt, widział cudze i uruchamiał w nich programy prawami serwera."""
    _projekt_wlasciciela(client, settings)
    assert client.post("/api/auth/gosc", headers=HEADERS).status_code == 200
    assert client.get("/api/kod/projekty").json() == [], "konto próbne widziało cudzy projekt"
    assert client.get("/api/kod/projekty/projekt-wlasciciela/drzewo").status_code == 404
    polecenie = client.post(
        "/api/kod/projekty/projekt-wlasciciela/polecenie",
        json={"polecenie": "cat README.md"},
        headers=HEADERS,
    )
    assert polecenie.status_code == 404, polecenie.text
    assert client.delete("/api/kod/projekty/projekt-wlasciciela", headers=HEADERS).status_code == 404


def test_zadanie_w_tle_nie_wchodzi_do_cudzego_projektu(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Tryb Kod uruchamia agenta w katalogu projektu — nazwa cudzego projektu jest odrzucana."""
    _projekt_wlasciciela(client, settings)
    assert client.post("/api/auth/gosc", headers=HEADERS).status_code == 200
    zlecone = client.post(
        "/api/agenci/zadania",
        json={"text": "Zbuduj projekt", "mode": "code", "workspace": "projekt-wlasciciela"},
        headers=HEADERS,
    )
    assert zlecone.status_code == 422, zlecone.text


@pytest.mark.parametrize(
    "polecenie", ["cat /etc/hostname", "python ../../ucieczka.py", "ruff check --config=/etc/ruff.toml ."]
)
def test_terminal_projektu_nie_czyta_plikow_serwera(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
    polecenie: str,
) -> None:
    """Wykaz programów pilnował, co wolno uruchomić; argumenty wskazywały dowolny plik serwera."""
    _projekt_wlasciciela(client, settings, "projekt-terminal")
    odmowa = client.post(
        "/api/kod/projekty/projekt-terminal/polecenie", json={"polecenie": polecenie}, headers=HEADERS
    )
    assert odmowa.status_code == 422, f"{polecenie} → {odmowa.status_code}"
    assert "poza projekt" in odmowa.json()["detail"]


# --- Twórca stron: strona należy do konta, które ją założyło ---


def test_konto_probne_nie_kasuje_strony_wlasciciela(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Gość widział wszystkie strony instalacji i mógł skasować witrynę właściciela."""
    set_password(settings)
    zaloguj(client, "admin", PASSWORD)
    strona = client.post("/api/strony", json={"title": "Strona właściciela"}, headers=HEADERS)
    assert strona.status_code == 201, strona.text
    adres = strona.json()["address"]

    assert client.post("/api/auth/gosc", headers=HEADERS).status_code == 200
    assert client.get("/api/strony").json() == [], "konto próbne widziało cudzą stronę"
    assert client.get(f"/api/strony/{adres}").status_code == 404
    zmiana = client.patch(f"/api/strony/{adres}", json={"title": "Przejęta"}, headers=HEADERS)
    assert zmiana.status_code == 404
    assert client.post(f"/api/strony/{adres}/publikuj", headers=HEADERS).status_code == 404
    skasowana = client.delete(f"/api/strony/{adres}", headers=HEADERS)
    assert skasowana.status_code == 404, skasowana.text

    zaloguj(client, "admin", PASSWORD)
    assert [item["address"] for item in client.get("/api/strony").json()] == [adres], "strona zniknęła"


# --- wykazy zadań: tytuły rozmów i postęp to treść konta ---


def test_wykazy_zadan_nie_pokazuja_cudzych_rozmow(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Gość czytał tytuły rozmów, opisy podagentów i błędy zadań całej instalacji."""
    set_password(settings)
    zaloguj(client, "admin", PASSWORD)
    rozmowa = client.post("/api/conversations", json={}, headers=HEADERS).json()
    wyslane = client.post(
        f"/api/conversations/{rozmowa['id']}/messages",
        json={"text": "Tajne rozliczenie kwartału"},
        headers=HEADERS,
    )
    assert wyslane.status_code == 202, wyslane.text
    zadania = client.get("/api/agenci/zadania").json()
    assert [item["title"] for item in zadania["active"]] == ["Tajne rozliczenie kwartału"]
    assert zadania["config"]["queued"] == 1

    assert client.post("/api/auth/gosc", headers=HEADERS).status_code == 200
    goscia = client.get("/api/agenci/zadania").json()
    assert goscia["active"] == [] and goscia["finished"] == []
    assert goscia["config"]["queued"] == 0
    assert client.get("/api/w-toku").json() == [], "konto próbne widziało cudze zadania w toku"


# --- pokaz: narzędzia piaskownicy nie pracują jako właściciel instalacji ---


def test_narzedzia_pokazu_pracuja_na_koncie_pokazu(settings: Settings) -> None:  # noqa: F811
    """Kontekst narzędzia bez konta przyjmuje właściciela instalacji — pokaz ma własne."""
    piaskownica = Piaskownica(settings)
    sesja = piaskownica.utworz("198.51.100.11")
    kontekst = _kontekst(ustawienia_demo(settings), sesja, threading.Event())
    assert kontekst.owner_id == WLASCICIEL_POKAZU
    assert kontekst.owner_id != ADMIN_OWNER, "narzędzia pokazu pracowały jako właściciel instalacji"


# --- chmura osobista: podgląd pliku z tą samą normalizacją typu, co pliki rozmowy ---


class ChmuraZeSvg(FakeNextcloud):
    """Atrapa chmury oddająca typ nośnika z wielkimi literami — tak zapisał go serwer plików."""

    def handle(self, request: httpx.Request) -> httpx.Response:
        odpowiedz = super().handle(request)
        if request.method == "GET" and request.url.path.endswith(".svg"):
            return httpx.Response(
                200, content=odpowiedz.content, headers={"content-type": "image/SVG+xml"}
            )
        return odpowiedz


def test_podglad_z_chmury_nie_wyswietla_svg_z_wielkich_liter(
    api: TestClient,  # noqa: F811
    biuro_settings: Settings,  # noqa: F811
) -> None:
    """Podgląd pliku z chmury porównywał typ bez zmiany wielkości liter, więc ``image/SVG+xml``
    omijało wykaz dokumentów zakazanych i szło do wyświetlenia w domenie aplikacji."""
    api.app.state.cloud_transport = ChmuraZeSvg().transport()
    wgrany = api.put(
        "/api/cloud/plik",
        params={"path": "/rysunek.svg"},
        content=b"<svg xmlns='http://www.w3.org/2000/svg'/>",
        headers=HEADERS_BIURO,
    )
    assert wgrany.status_code == 200, wgrany.text
    podglad = api.get("/api/cloud/pobierz", params={"path": "/rysunek.svg", "inline": 1})
    assert podglad.status_code == 200, podglad.text
    assert podglad.headers["content-type"] == "application/octet-stream"
    assert podglad.headers["content-disposition"].startswith("attachment"), "SVG szedł do wyświetlenia"


def test_uszkodzony_wykaz_wlascicieli_nie_przepisuje_projektow(tmp_path: Path) -> None:
    """Uszkodzony plik nie może po cichu oddać cudzych projektów właścicielowi instalacji.

    `_wykaz` zwracał pusty słownik przy każdym błędzie odczytu, a pusty wykaz znaczy
    „wszystko należy do administratora”. Jedna nieudana operacja na pliku przepisywała
    więc projekty wszystkich kont. Brak pliku nadal znaczy pusty wykaz — to stan normalny
    na świeżej instalacji.
    """
    from nexus.agent.przestrzenie import (
        WLASCICIELE,
        WykazNieczytelny,
        przypisz_projekt,
        wlasciciel_projektu,
    )
    from nexus.config import Settings

    ustawienia = Settings(data_dir=tmp_path, database_url="sqlite+aiosqlite:///:memory:")
    konto = uuid.uuid4()
    przypisz_projekt(ustawienia, "projekt", konto)
    assert wlasciciel_projektu(ustawienia, "projekt") == konto

    (ustawienia.kod_dir / WLASCICIELE).write_text("{to nie jest json", encoding="utf-8")
    with pytest.raises(WykazNieczytelny):
        wlasciciel_projektu(ustawienia, "projekt")

    (ustawienia.kod_dir / WLASCICIELE).unlink()
    assert wlasciciel_projektu(ustawienia, "projekt") == ADMIN_OWNER
