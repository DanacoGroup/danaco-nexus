"""Testy modułu płatności: cennik, zakup, portal, kupony, faktury, webhook i limity planów.

Testy nie łączą się z siecią – Stripe zastępuje atrapa protokołu ``KlientStripe``,
a zdarzenia webhooka to utrwalone ładunki podpisane sekretem testowym.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from nexus.api.app import create_app
from nexus.api.auth import set_admin_credentials
from nexus.config import Settings, get_settings
from nexus.db import ADMIN_OWNER, Database
from nexus.platnosci import kredyty
from nexus.platnosci.klient import KlientHttpStripe, koduj_formularz
from nexus.platnosci.konfiguracja import (
    UstawieniaPlatnosci,
    adresy_powrotu,
    ustawienia_platnosci,
)
from nexus.platnosci.model import Faktura, Plan, Subskrypcja, ZdarzenieStripe
from nexus.platnosci.plany import KATALOG, limity_pozycji
from nexus.platnosci.podpis import podpisz_ladunek
from nexus.platnosci.stany import KOMUNIKAT_SPRZEDAZ_WYLACZONA, stan_sprzedazy
from nexus.platnosci.uprawnienia import LimitPrzekroczony, limity_planu, sprawdz_limit
from nexus.platnosci.uslugi import subskrypcja_uzytkownika
from nexus.platnosci.zdarzenia import POMINIETE_CENA_NEXUSA, POMINIETE_OBCE

PASSWORD = "bardzo-tajne-haslo-2026"
HEADERS = {"X-Nexus-Request": "1"}
# Subskrypcja jest kluczowana kontem, nie loginem instalacji: zakup jednego
# użytkownika nie może obejmować wszystkich.
KONTO_ADMINA = str(ADMIN_OWNER)
# Wartości jawnie testowe – w repozytorium nie ma żadnego prawdziwego klucza ani ceny.
KLUCZ_TESTOWY = "sk_test_atrapa"
SEKRET_TESTOWY = "whsec_atrapa_testowa"
CENA_MIESIAC = "price_test_pro_miesiac"
CENA_ROK = "price_test_pro_rok"
# Pakiet kredytów nie ma okresu rozliczeniowego — jego cena stoi w cenniku pod „pakiet:<kod>”.
CENA_PAKIETU_MALY = "price_test_pakiet_maly"
KLIENT_STRIPE = "cus_test_1"
SUBSKRYPCJA_STRIPE = "sub_test_1"
# Koniec opłaconego okresu daleko w przyszłości – stan „aktywna” nie zależy od dnia uruchomienia testu.
OKRES_DO_BIEZACY = 4_102_444_800

ZMIENNE = {
    "NEXUS_PLATNOSCI_STRIPE_KLUCZ": KLUCZ_TESTOWY,
    "NEXUS_PLATNOSCI_WEBHOOK_SEKRET": SEKRET_TESTOWY,
    "NEXUS_PLATNOSCI_CENY": f"pro:miesiac={CENA_MIESIAC};pro:rok={CENA_ROK};pakiet:maly={CENA_PAKIETU_MALY}",
    "NEXUS_PLATNOSCI_KWOTY": "pro:miesiac=4900;pro:rok=49000",
    "NEXUS_PLATNOSCI_ADRES_POWROTU": "https://danaco-nexus.test",
}


def subskrypcja_stripe(
    status: str = "active", cena: str = CENA_MIESIAC, anuluj: bool = False
) -> dict[str, Any]:
    """Utrwalony ładunek subskrypcji Stripe (skrócony do pól używanych przez moduł)."""
    return {
        "id": SUBSKRYPCJA_STRIPE,
        "object": "subscription",
        "customer": KLIENT_STRIPE,
        "status": status,
        "cancel_at_period_end": anuluj,
        "current_period_start": 1_771_200_000,
        "current_period_end": 1_773_878_400,
        "metadata": {"uzytkownik": KONTO_ADMINA, "plan": "pro", "okres": "miesiac"},
        "items": {"object": "list", "data": [{"id": "si_test_1", "price": {"id": cena}}]},
    }


def subskrypcja_biezaca(
    status: str = "active", cena: str = CENA_MIESIAC, anuluj: bool = False
) -> dict[str, Any]:
    """Subskrypcja Stripe z opłaconym okresem, który jeszcze trwa."""
    return {**subskrypcja_stripe(status, cena, anuluj), "current_period_end": OKRES_DO_BIEZACY}


def faktura_stripe(status: str = "paid", identyfikator: str = "in_test_1") -> dict[str, Any]:
    """Utrwalony ładunek faktury Stripe."""
    return {
        "id": identyfikator,
        "object": "invoice",
        "customer": KLIENT_STRIPE,
        "number": "NEXUS-2026-0001",
        "amount_due": 4900,
        "total": 4900,
        "currency": "pln",
        "status": status,
        "created": 1_771_200_000,
        "invoice_pdf": f"https://stripe.test/faktury/{identyfikator}.pdf",
        "hosted_invoice_url": f"https://stripe.test/faktury/{identyfikator}",
        "status_transitions": {"paid_at": 1_771_200_100 if status == "paid" else None},
        "metadata": {"uzytkownik": KONTO_ADMINA},
    }


def zdarzenie(typ: str, obiekt: dict[str, Any], identyfikator: str = "evt_test_1") -> dict[str, Any]:
    """Koperta zdarzenia webhooka Stripe."""
    return {
        "id": identyfikator,
        "object": "event",
        "type": typ,
        "created": 1_771_200_200,
        "data": {"object": obiekt},
    }


class AtrapaStripe:
    """Atrapa protokołu ``KlientStripe`` – zapamiętuje żądania, nie rusza sieci."""

    def __init__(self) -> None:
        self.sesje_checkout: list[dict[str, Any]] = []
        self.portale: list[tuple[str, str]] = []
        self.przeplywy: list[dict[str, Any]] = []
        self.utworzeni_klienci: list[str] = []
        self.faktury: list[dict[str, Any]] = [faktura_stripe()]
        self.subskrypcja = subskrypcja_stripe()
        self.kupony = {
            "LATO2026": {
                "id": "promo_test_1",
                "active": True,
                "expires_at": None,
                "coupon": {"id": "cpn_test_1", "percent_off": 20, "name": "Lato 2026"},
            },
            "ZIMA2025": {
                "id": "promo_test_2",
                "active": True,
                # Kod znaleziony w Stripe, ale z datą ważności w przeszłości.
                "expires_at": 1_740_000_000,
                "coupon": {"id": "cpn_test_2", "percent_off": 30, "name": "Zima 2025"},
            },
            "WYCZERPANY": {
                "id": "promo_test_3",
                "active": True,
                "expires_at": None,
                "max_redemptions": 5,
                "times_redeemed": 5,
                "coupon": {"id": "cpn_test_3", "percent_off": 10, "name": "Pierwsze pięć osób"},
            },
        }
        self.zamkniety = False

    async def utworz_klienta(self, email: str, nazwa: str, metadane: Mapping[str, str]) -> dict[str, Any]:
        self.utworzeni_klienci.append(nazwa)
        return {"id": KLIENT_STRIPE, "email": email, "metadata": dict(metadane)}

    async def utworz_sesje_checkout(self, dane: Mapping[str, Any]) -> dict[str, Any]:
        self.sesje_checkout.append(dict(dane))
        return {"id": "cs_test_1", "url": "https://checkout.stripe.test/cs_test_1"}

    async def pobierz_sesje_checkout(self, identyfikator: str) -> dict[str, Any]:
        return {
            "id": identyfikator,
            "client_reference_id": KONTO_ADMINA,
            "customer": KLIENT_STRIPE,
            "subscription": SUBSKRYPCJA_STRIPE,
        }

    async def utworz_sesje_portalu(
        self, klient: str, adres_powrotu: str, przeplyw: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        self.portale.append((klient, adres_powrotu))
        self.przeplywy.append(dict(przeplyw or {}))
        return {"id": "bps_test_1", "url": "https://billing.stripe.test/bps_test_1"}

    async def pobierz_subskrypcje(self, identyfikator: str) -> dict[str, Any]:
        return self.subskrypcja

    async def lista_faktur(self, klient: str, limit: int = 24) -> list[dict[str, Any]]:
        return self.faktury

    async def znajdz_kod_promocyjny(self, kod: str) -> dict[str, Any] | None:
        return self.kupony.get(kod.strip().upper())

    async def zamknij(self) -> None:
        self.zamkniety = True


@pytest.fixture(autouse=True)
def srodowisko(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Konfiguracja sprzedaży wyłącznie na czas testu (wartości testowe)."""
    for nazwa, wartosc in ZMIENNE.items():
        monkeypatch.setenv(nazwa, wartosc)
    ustawienia_platnosci.cache_clear()
    yield
    ustawienia_platnosci.cache_clear()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        cookie_secure=False,
        cookie_domain="",
        public_url="https://danaco-nexus.test",
        chmura_public_url="",
        redis_url="",
        voice_warm_up=False,
        voice_stt_model_dir=tmp_path / "brak-modelu",
        voice_tts_dir=tmp_path / "brak-glosow",
        voice_google_key_file=tmp_path / "brak-klucza-google",
        qdrant_url="http://127.0.0.1:1",
        push_enabled=False,
    )


@pytest.fixture
def atrapa() -> AtrapaStripe:
    return AtrapaStripe()


@pytest.fixture
def client(settings: Settings, atrapa: AtrapaStripe, srodowisko: None) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        test_client.app.state.platnosci_klient = atrapa
        _zaloz_konto_klienta(settings)
        yield test_client


def _zaloz_konto_klienta(settings: Settings) -> None:
    """Konto portalu ``KONTO_KLIENTA``: webhook przypisuje zdarzenia tylko istniejącym kontom
    (identyfikatory UUID zapisują w Stripe także inne produkty na wspólnym koncie)."""
    from nexus.models.portal import PortalUser

    async def run() -> None:
        database = Database(settings.database_url)
        async with database.session() as session:
            session.add(
                PortalUser(id=uuid.UUID(KONTO_KLIENTA), email="klient-kasy@example.com", password_hash="-")
            )
        await database.close()

    asyncio.run(run())


def zaloguj(client: TestClient, settings: Settings) -> None:
    """Ustawia hasło administratora i loguje klienta testowego."""

    async def run() -> None:
        database = Database(settings.database_url)
        await set_admin_credentials(database, "admin", PASSWORD)
        await database.close()

    asyncio.run(run())
    odpowiedz = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert odpowiedz.status_code == 200, odpowiedz.text


def wyslij_zdarzenie(client: TestClient, tresc: dict[str, Any]) -> Any:
    """Wysyła podpisane zdarzenie na webhook."""
    ladunek = json.dumps(tresc).encode("utf-8")
    return client.post(
        "/api/platnosci/webhook",
        content=ladunek,
        headers={
            "Stripe-Signature": podpisz_ladunek(ladunek, SEKRET_TESTOWY),
            "Content-Type": "application/json",
        },
    )


def test_cennik_wymaga_logowania(client: TestClient) -> None:
    assert client.get("/api/platnosci/plany").status_code == 401


def test_cennik_zawiera_plany_z_katalogu(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    dane = client.get("/api/platnosci/plany").json()
    kody = [pozycja["kod"] for pozycja in dane["plany"]]
    assert kody == ["osobisty", "pro", "zespol"]
    osobisty, pro, zespol = dane["plany"]
    # Najniższy plan jest płatny i zaczyna się okresem próbnym: testerzy mają przejść
    # pełną ścieżkę zakupu, a po 7 dniach subskrypcja przechodzi w płatną sama.
    assert not osobisty["bezplatny"]
    # Kwoty rozstrzyga serwer na podstawie konfiguracji środowiska.
    assert pro["cena_miesiac_gr"] == 4900 and pro["cena_rok_gr"] == 49000
    assert pro["do_kupienia"] == {"miesiac": True, "rok": True}
    # Plan bez skonfigurowanej ceny pozostaje „Wkrótce”.
    assert zespol["do_kupienia"] == {"miesiac": False, "rok": False}
    assert dane["subskrypcja"]["plan"] == "osobisty"
    assert dane["subskrypcja"]["limity"]["automatyzacje"] == 0


def test_plany_zapisane_w_bazie(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)

    async def run() -> list[Plan]:
        database = Database(settings.database_url)
        async with database.session() as session:
            wynik = list((await session.scalars(select(Plan))).all())
        await database.close()
        return wynik

    rekordy = {rekord.kod: rekord for rekord in asyncio.run(run())}
    assert rekordy["pro"].limity["zadania_rownolegle"] == 4
    assert rekordy["pro"].cena_rok_gr == 49000


def test_zakup_wymaga_naglowka_aplikacji(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/checkout", json={"plan": "pro", "okres": "miesiac"})
    assert odpowiedz.status_code == 403


def test_zakup_uzywa_ceny_z_konfiguracji(
    client: TestClient, settings: Settings, atrapa: AtrapaStripe
) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post(
        "/api/platnosci/checkout",
        # Kwota podana przez klienta jest pomijana – serwer bierze cenę z konfiguracji.
        json={"plan": "pro", "okres": "rok", "cena_gr": 1},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 200, odpowiedz.text
    assert odpowiedz.json()["url"].startswith("https://checkout.stripe.test/")
    sesja = atrapa.sesje_checkout[-1]
    assert sesja["line_items"] == [{"price": CENA_ROK, "quantity": 1}]
    assert sesja["mode"] == "subscription" and sesja["client_reference_id"] == KONTO_ADMINA
    assert "1" not in json.dumps(sesja.get("amount", ""))
    assert sesja["success_url"].startswith("https://danaco-nexus.test/m/platnosci?zakup=udany")
    assert atrapa.utworzeni_klienci == [KONTO_ADMINA]


def test_zakup_odrzuca_nieznany_plan(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post(
        "/api/platnosci/checkout", json={"plan": "zloty", "okres": "miesiac"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 400


def test_zakup_odrzuca_plan_bez_ceny(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post(
        "/api/platnosci/checkout", json={"plan": "zespol", "okres": "miesiac"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 409


def test_zakup_odrzuca_nieznany_okres(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post(
        "/api/platnosci/checkout", json={"plan": "pro", "okres": "tydzien"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 400


def test_kupon_trafia_do_sesji_zakupu(client: TestClient, settings: Settings, atrapa: AtrapaStripe) -> None:
    zaloguj(client, settings)
    sprawdzenie = client.post("/api/platnosci/kupon", json={"kod": "LATO2026"}, headers=HEADERS)
    assert sprawdzenie.status_code == 200
    assert sprawdzenie.json()["rabat_procent"] == 20
    odpowiedz = client.post(
        "/api/platnosci/checkout",
        json={"plan": "pro", "okres": "miesiac", "kupon": "LATO2026"},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 200
    assert atrapa.sesje_checkout[-1]["discounts"] == [{"promotion_code": "promo_test_1"}]


def test_kupon_nieznany_odrzucony(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/kupon", json={"kod": "NIEMA"}, headers=HEADERS)
    assert odpowiedz.status_code == 400


def test_portal_bez_zakupu_odmawia(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/portal", headers=HEADERS)
    assert odpowiedz.status_code == 409


def test_portal_po_zakupie(client: TestClient, settings: Settings, atrapa: AtrapaStripe) -> None:
    zaloguj(client, settings)
    client.post("/api/platnosci/checkout", json={"plan": "pro", "okres": "miesiac"}, headers=HEADERS)
    odpowiedz = client.post("/api/platnosci/portal", headers=HEADERS)
    assert odpowiedz.status_code == 200
    assert odpowiedz.json()["url"].startswith("https://billing.stripe.test/")
    assert atrapa.portale[-1][0] == KLIENT_STRIPE


def test_webhook_bez_podpisu_odrzucony(client: TestClient) -> None:
    odpowiedz = client.post("/api/platnosci/webhook", json=zdarzenie("invoice.paid", faktura_stripe()))
    assert odpowiedz.status_code == 400


def test_webhook_z_blednym_podpisem_odrzucony(client: TestClient) -> None:
    ladunek = json.dumps(zdarzenie("invoice.paid", faktura_stripe())).encode("utf-8")
    odpowiedz = client.post(
        "/api/platnosci/webhook",
        content=ladunek,
        headers={"Stripe-Signature": podpisz_ladunek(ladunek, "whsec_inny_sekret")},
    )
    assert odpowiedz.status_code == 400


def test_webhook_nie_wymaga_sesji_i_zapisuje_subskrypcje(client: TestClient, settings: Settings) -> None:
    odpowiedz = wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_stripe()))
    assert odpowiedz.status_code == 200, odpowiedz.text
    assert odpowiedz.json() == {"otrzymano": True, "obsluzone": True, "typ": "customer.subscription.created"}
    zaloguj(client, settings)
    stan = client.get("/api/platnosci/subskrypcja").json()
    assert stan["plan"] == "pro" and stan["status"] == "aktywna" and stan["okres"] == "miesiac"
    assert stan["limity"]["automatyzacje"] == 20
    assert stan["okres_do"].startswith("2026-")


def test_webhook_jest_idempotentny(client: TestClient, settings: Settings) -> None:
    tresc = zdarzenie("customer.subscription.created", subskrypcja_stripe())
    assert wyslij_zdarzenie(client, tresc).json()["obsluzone"] is True
    powtorka = wyslij_zdarzenie(client, tresc)
    assert powtorka.status_code == 200
    assert powtorka.json()["duplikat"] is True

    async def run() -> int:
        database = Database(settings.database_url)
        async with database.session() as session:
            liczba = await session.scalar(select(func.count()).select_from(ZdarzenieStripe))
        await database.close()
        return int(liczba or 0)

    assert asyncio.run(run()) == 1


def test_webhook_zdarzenie_zapisane_przed_zmiana_stanu(client: TestClient, settings: Settings) -> None:
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.updated", subskrypcja_stripe("past_due")))

    async def run() -> tuple[ZdarzenieStripe, Subskrypcja]:
        database = Database(settings.database_url)
        async with database.session() as session:
            wpis = await session.get(ZdarzenieStripe, "evt_test_1")
            stan = await session.scalar(select(Subskrypcja))
        await database.close()
        assert wpis is not None and stan is not None
        return wpis, stan

    wpis, stan = asyncio.run(run())
    assert wpis.status == "przetworzone" and wpis.ladunek["type"] == "customer.subscription.updated"
    assert wpis.przetworzone_at is not None
    assert stan.status == "zalegla"


def test_webhook_uzgadnia_chmure_dopiero_po_odpowiedzi(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uzgodnienie chmury (occ dla założyciela i każdego członka grupy) trwa sekundy, przy
    zawieszeniu minuty. Stripe ma dostać odpowiedź od razu, a limit dogania plan w tle."""
    from types import SimpleNamespace

    from fastapi import BackgroundTasks
    from starlette.requests import Request

    import nexus.api.modules.platnosci as modul

    uzgodnione: list[object] = []

    async def zapisz(_ustawienia: object, _baza: object, owner: object) -> None:
        uzgodnione.append(owner)

    monkeypatch.setattr(modul, "uzgodnij_limit_po_zmianie_planu", zapisz)
    ladunek = json.dumps(zdarzenie("customer.subscription.created", subskrypcja_stripe())).encode("utf-8")

    async def run() -> None:
        database = Database(settings.database_url)
        await database.create_schema()
        aplikacja = SimpleNamespace(state=SimpleNamespace(database=database, settings=settings))

        async def odbierz() -> dict[str, Any]:
            return {"type": "http.request", "body": ladunek, "more_body": False}

        zakres = {"type": "http", "method": "POST", "path": "/api/platnosci/webhook", "headers": []}
        zadania = BackgroundTasks()
        try:
            wynik = await modul.webhook(
                Request({**zakres, "query_string": b"", "app": aplikacja}, odbierz),
                zadania,
                stripe_signature=podpisz_ladunek(ladunek, SEKRET_TESTOWY),
            )
            assert wynik["obsluzone"] is True
            assert uzgodnione == [], "odpowiedź dla Stripe nie czeka na chmurę"
            await zadania()
        finally:
            await database.close()

    asyncio.run(run())
    assert uzgodnione == [ADMIN_OWNER]


def test_webhook_nieobslugiwany_typ_jest_pomijany(client: TestClient) -> None:
    odpowiedz = wyslij_zdarzenie(client, zdarzenie("customer.created", {"id": KLIENT_STRIPE}))
    assert odpowiedz.status_code == 200 and odpowiedz.json()["obsluzone"] is False


def test_webhook_anulowanie_wraca_do_planu_bezplatnego(client: TestClient, settings: Settings) -> None:
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_stripe()))
    wyslij_zdarzenie(
        client,
        zdarzenie("customer.subscription.deleted", subskrypcja_stripe("canceled"), "evt_test_2"),
    )
    zaloguj(client, settings)
    stan = client.get("/api/platnosci/subskrypcja").json()
    assert stan["plan"] == "osobisty" and stan["status"] == "anulowana"
    assert stan["limity"]["zadania_rownolegle"] == 1


def test_webhook_faktury_trafiaja_na_liste(client: TestClient, settings: Settings) -> None:
    wyslij_zdarzenie(client, zdarzenie("invoice.paid", faktura_stripe()))
    wyslij_zdarzenie(
        client, zdarzenie("invoice.payment_failed", faktura_stripe("open", "in_test_2"), "evt_test_3")
    )
    zaloguj(client, settings)
    faktury = client.get("/api/platnosci/faktury").json()
    assert {pozycja["status"] for pozycja in faktury} == {"paid", "open"}
    oplacona = next(pozycja for pozycja in faktury if pozycja["status"] == "paid")
    assert oplacona["kwota_gr"] == 4900 and oplacona["numer"] == "NEXUS-2026-0001"
    assert oplacona["pdf_url"].endswith(".pdf")


def test_faktury_odswiezane_ze_stripe(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    client.post("/api/platnosci/checkout", json={"plan": "pro", "okres": "miesiac"}, headers=HEADERS)
    faktury = client.get("/api/platnosci/faktury?odswiez=1").json()
    assert len(faktury) == 1 and faktury[0]["numer"] == "NEXUS-2026-0001"


def test_powrot_z_checkoutu_uzgadnia_stan(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/powrot", json={"sesja": "cs_test_1"}, headers=HEADERS)
    assert odpowiedz.status_code == 200, odpowiedz.text
    assert odpowiedz.json()["plan"] == "pro" and odpowiedz.json()["status"] == "aktywna"


def test_limity_planu_egzekwowane(settings: Settings) -> None:
    """Funkcja ``sprawdz_limit`` rozstrzyga na podstawie zapisanej subskrypcji."""

    async def run() -> None:
        database = Database(settings.database_url)
        await database.create_schema()
        await set_admin_credentials(database, "admin", PASSWORD)
        limity = await sprawdz_limit(database, "zadania_rownolegle", 1)
        assert limity.plan == "osobisty"
        with pytest.raises(LimitPrzekroczony):
            await sprawdz_limit(database, "zadania_rownolegle", 2)
        with pytest.raises(LimitPrzekroczony) as blad:
            await sprawdz_limit(database, "automatyzacje", 1)
        assert blad.value.status == 402
        assert "Osobisty" in str(blad.value)
        rekord = await subskrypcja_uzytkownika(database, KONTO_ADMINA)
        async with database.session() as session:
            rekord.plan_kod, rekord.status = "pro", "aktywna"
            await session.merge(rekord)
        limity = await sprawdz_limit(database, "zadania_rownolegle", 4)
        assert limity.plan == "pro"
        await sprawdz_limit(database, "automatyzacje", 20)
        with pytest.raises(LimitPrzekroczony):
            await sprawdz_limit(database, "automatyzacje", 21)
        await database.close()

    asyncio.run(run())


def test_kodowanie_formularza_stripe() -> None:
    """Dane zagnieżdżone trafiają do Stripe w zapisie ``a[b][0][c]``."""
    pary = dict(
        koduj_formularz(
            {
                "mode": "subscription",
                "line_items": [{"price": CENA_MIESIAC, "quantity": 1}],
                "metadata": {"uzytkownik": KONTO_ADMINA},
                "allow_promotion_codes": True,
                "pominiete": None,
            }
        )
    )
    assert pary["line_items[0][price]"] == CENA_MIESIAC
    assert pary["line_items[0][quantity]"] == "1"
    assert pary["metadata[uzytkownik]"] == KONTO_ADMINA
    assert pary["allow_promotion_codes"] == "true"
    assert "pominiete" not in pary


def stan_konta(client: TestClient) -> dict[str, Any]:
    """Stan sprzedaży widziany przez interfejs (moduł Płatności)."""
    return client.get("/api/platnosci/subskrypcja").json()


def test_cennik_publiczny_dostepny_bez_logowania(client: TestClient) -> None:
    """Portal pokazuje cennik przed zalogowaniem – to ta sama definicja planów."""
    odpowiedz = client.get("/api/platnosci/cennik")
    assert odpowiedz.status_code == 200, odpowiedz.text
    dane = odpowiedz.json()
    assert [pozycja["kod"] for pozycja in dane["plany"]] == ["osobisty", "pro", "zespol"]
    assert dane["sprzedaz_aktywna"] is True and dane["waluta"] == "pln"
    # Publiczny cennik nie niesie żadnych danych konta.
    assert "subskrypcja" not in dane


def test_cennik_publiczny_zgodny_z_modulem(client: TestClient, settings: Settings) -> None:
    publiczny = client.get("/api/platnosci/cennik").json()
    zaloguj(client, settings)
    modul = client.get("/api/platnosci/plany").json()
    assert publiczny["plany"] == modul["plany"]
    assert publiczny["waluta"] == modul["waluta"]


def test_stan_planu_bezplatnego_wskazuje_wybor_planu(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    stan = stan_konta(client)["stan"]
    assert stan["kod"] == "plan_bezplatny" and stan["dzialanie"] == "wybierz_plan"
    assert stan["etykieta_dzialania"] == "Wybierz plan"


def test_stan_planu_aktywnego(client: TestClient, settings: Settings) -> None:
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_biezaca()))
    zaloguj(client, settings)
    dane = stan_konta(client)
    assert dane["stan"]["kod"] == "plan_aktywny" and dane["stan"]["ton"] == "sukces"
    assert dane["ma_platny_plan"] is True and dane["faktura_do_zaplaty"] is None


def test_platnosc_odrzucona_prowadzi_do_faktury(client: TestClient, settings: Settings) -> None:
    """Zaległa płatność: stan błędu i wskazanie nieopłaconej faktury."""
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.updated", subskrypcja_biezaca("past_due")))
    wyslij_zdarzenie(
        client, zdarzenie("invoice.payment_failed", faktura_stripe("open", "in_test_9"), "evt_test_9")
    )
    zaloguj(client, settings)
    dane = stan_konta(client)
    assert dane["status"] == "zalegla"
    assert dane["stan"]["kod"] == "platnosc_odrzucona" and dane["stan"]["ton"] == "blad"
    assert dane["stan"]["dzialanie"] == "zaplac_fakture"
    assert dane["faktura_do_zaplaty"]["strona_url"].endswith("in_test_9")
    assert "Popraw dane karty" in dane["stan"]["komunikat"]


def test_platnosc_niedokonczona_ma_komunikat(client: TestClient, settings: Settings) -> None:
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_biezaca("incomplete")))
    zaloguj(client, settings)
    stan = stan_konta(client)["stan"]
    assert stan["kod"] == "platnosc_niedokonczona"
    # Bez zaległej faktury jedynym wyjściem jest portal rozliczeniowy.
    assert stan["dzialanie"] == "portal" and "Dokończ płatność" in stan["komunikat"]


def test_subskrypcja_wygasla_prowadzi_do_cennika(client: TestClient, settings: Settings) -> None:
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_biezaca()))
    wyslij_zdarzenie(
        client, zdarzenie("customer.subscription.deleted", subskrypcja_biezaca("canceled"), "evt_test_8")
    )
    zaloguj(client, settings)
    dane = stan_konta(client)
    assert dane["plan"] == "osobisty" and dane["ma_platny_plan"] is False
    assert dane["stan"]["kod"] == "subskrypcja_wygasla"
    assert dane["stan"]["dzialanie"] == "wybierz_plan"


def test_oplacony_okres_minal(client: TestClient, settings: Settings) -> None:
    """Aktywna subskrypcja z zamkniętym okresem: konto widzi, że brak potwierdzenia odnowienia."""
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.updated", subskrypcja_stripe()))
    zaloguj(client, settings)
    stan = stan_konta(client)["stan"]
    assert stan["kod"] == "subskrypcja_wygasla" and stan["dzialanie"] == "portal"


def test_rezygnacja_zlozona_widoczna_w_stanie(client: TestClient, settings: Settings) -> None:
    wyslij_zdarzenie(
        client, zdarzenie("customer.subscription.updated", subskrypcja_biezaca(anuluj=True))
    )
    zaloguj(client, settings)
    stan = stan_konta(client)["stan"]
    assert stan["kod"] == "rezygnacja_zlozona" and stan["etykieta_dzialania"] == "Wznów plan"


def test_zmiana_planu_idzie_przez_portal(
    client: TestClient, settings: Settings, atrapa: AtrapaStripe
) -> None:
    """Przy opłaconym planie zakup nie zakłada drugiej subskrypcji, tylko otwiera zmianę planu."""
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_biezaca()))
    zaloguj(client, settings)
    odpowiedz = client.post(
        "/api/platnosci/checkout", json={"plan": "pro", "okres": "rok"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 200, odpowiedz.text
    wynik = odpowiedz.json()
    assert wynik["tryb"] == "portal" and wynik["plan"] == "pro" and wynik["okres"] == "rok"
    assert wynik["url"].startswith("https://billing.stripe.test/")
    zmiana = atrapa.przeplywy[-1]
    assert zmiana["type"] == "subscription_update_confirm"
    potwierdzenie = zmiana["subscription_update_confirm"]
    assert potwierdzenie["subscription"] == SUBSKRYPCJA_STRIPE
    # Wybrany plan dociera do Stripe: portal otwiera się na potwierdzeniu, nie na liście planów.
    assert potwierdzenie["items"] == [{"id": "si_test_1", "price": CENA_ROK, "quantity": 1}]
    assert "discounts" not in potwierdzenie
    assert atrapa.sesje_checkout == []


def test_zmiana_planu_niesie_kod_rabatowy(
    client: TestClient, settings: Settings, atrapa: AtrapaStripe
) -> None:
    """Kod rabatowy podany przy zmianie planu idzie do Stripe, a nie znika po drodze."""
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_biezaca()))
    zaloguj(client, settings)
    odpowiedz = client.post(
        "/api/platnosci/checkout",
        json={"plan": "pro", "okres": "rok", "kupon": "LATO2026"},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 200, odpowiedz.text
    potwierdzenie = atrapa.przeplywy[-1]["subscription_update_confirm"]
    assert potwierdzenie["discounts"] == [{"promotion_code": "promo_test_1"}]


def test_zmiana_planu_odrzuca_niewazny_kod_rabatowy(client: TestClient, settings: Settings) -> None:
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_biezaca()))
    zaloguj(client, settings)
    odpowiedz = client.post(
        "/api/platnosci/checkout",
        json={"plan": "pro", "okres": "rok", "kupon": "ZIMA2025"},
        headers=HEADERS,
    )
    assert odpowiedz.status_code == 400
    assert "stracił ważność" in odpowiedz.json()["detail"]


def test_zakup_tego_samego_planu_odrzucony(client: TestClient, settings: Settings) -> None:
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_biezaca()))
    zaloguj(client, settings)
    odpowiedz = client.post(
        "/api/platnosci/checkout", json={"plan": "pro", "okres": "miesiac"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 409
    assert "jest już aktywny" in odpowiedz.json()["detail"]


def test_rezygnacja_otwiera_portal_na_rezygnacji(
    client: TestClient, settings: Settings, atrapa: AtrapaStripe
) -> None:
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_biezaca()))
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/rezygnacja", headers=HEADERS)
    assert odpowiedz.status_code == 200, odpowiedz.text
    assert atrapa.przeplywy[-1]["type"] == "subscription_cancel"
    assert atrapa.portale[-1][1].endswith("?powrot=rozliczenia")


def test_rezygnacja_bez_platnego_planu_odmawia(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/rezygnacja", headers=HEADERS)
    assert odpowiedz.status_code == 409
    # Plan Osobisty nie jest już bezpłatny — bez zakupu nie ma z czego rezygnować.
    assert "Nie masz wykupionego planu" in odpowiedz.json()["detail"]


def test_rezygnacja_juz_zlozona_odmawia(client: TestClient, settings: Settings) -> None:
    wyslij_zdarzenie(
        client, zdarzenie("customer.subscription.updated", subskrypcja_biezaca(anuluj=True))
    )
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/rezygnacja", headers=HEADERS)
    assert odpowiedz.status_code == 409
    assert "już złożona" in odpowiedz.json()["detail"]


def test_kupon_wygasly_odrzucony_z_podpowiedzia(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/kupon", json={"kod": "ZIMA2025"}, headers=HEADERS)
    assert odpowiedz.status_code == 400
    tresc = odpowiedz.json()["detail"]
    assert "stracił ważność" in tresc and "19.02.2025" in tresc


def test_kupon_wyczerpany_odrzucony(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/kupon", json={"kod": "WYCZERPANY"}, headers=HEADERS)
    assert odpowiedz.status_code == 400
    assert "już wykorzystany" in odpowiedz.json()["detail"]


def test_kupon_nieznany_podpowiada_zakup_bez_kodu(client: TestClient, settings: Settings) -> None:
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/kupon", json={"kod": "NIEMA"}, headers=HEADERS)
    assert odpowiedz.status_code == 400
    assert "bez kodu" in odpowiedz.json()["detail"]


def test_sprzedaz_niewlaczona_zatrzymuje_zakup(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Serwer bez klucza Stripe: cennik informuje, a zakup kończy się komunikatem, nie błędem."""
    zaloguj(client, settings)
    monkeypatch.delenv("NEXUS_PLATNOSCI_STRIPE_KLUCZ")
    monkeypatch.delenv("NEXUS_PLATNOSCI_CENY")
    ustawienia_platnosci.cache_clear()
    cennik = client.get("/api/platnosci/cennik").json()
    assert cennik["sprzedaz_aktywna"] is False
    assert all(not any(pozycja["do_kupienia"].values()) for pozycja in cennik["plany"])
    stan = stan_konta(client)["stan"]
    assert stan["kod"] == "sprzedaz_wylaczona" and stan["dzialanie"] == "brak"
    odpowiedz = client.post(
        "/api/platnosci/checkout", json={"plan": "pro", "okres": "miesiac"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 409
    assert "Sprzedaż nie jest jeszcze włączona" in odpowiedz.json()["detail"]
    assert client.post("/api/platnosci/kupon", json={"kod": "LATO2026"}, headers=HEADERS).status_code == 409


def test_sprzedaz_bez_klucza_mimo_cennika_nie_pokazuje_planu_jako_dostepnego(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Konfiguracja niepełna: są ceny i kwoty, nie ma klucza Stripe (np. plik nie do odczytu)."""
    zaloguj(client, settings)
    monkeypatch.delenv("NEXUS_PLATNOSCI_STRIPE_KLUCZ")
    ustawienia_platnosci.cache_clear()
    cennik = client.get("/api/platnosci/cennik").json()
    pro = next(pozycja for pozycja in cennik["plany"] if pozycja["kod"] == "pro")
    # Kwota nadal przychodzi z konfiguracji, ale zakupu nie da się zacząć.
    assert cennik["sprzedaz_aktywna"] is False and pro["cena_miesiac_gr"] == 4900
    assert pro["do_kupienia"] == {"miesiac": False, "rok": False}
    odpowiedz = client.post(
        "/api/platnosci/checkout", json={"plan": "pro", "okres": "miesiac"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 409


def test_katalog_nie_sprzedaje_limitow_bez_egzekwowania(client: TestClient, settings: Settings) -> None:
    """Zakres planu obiecuje wyłącznie to, co serwer naprawdę egzekwuje.

    Zadania równoległe wolno sprzedawać, odkąd `api/conversations.py` odrzuca zlecenie
    ponad limit planu. Pierwszeństwo w kolejce nie jest egzekwowane niczym, więc nadal
    nie ma prawa pojawić się w zakresie.
    """
    zaloguj(client, settings)
    dane = client.get("/api/platnosci/plany").json()
    zawartosc = [zdanie for pozycja in dane["plany"] for zdanie in pozycja["zawartosc"]]
    assert not any("Pierwszeństwo" in zdanie for zdanie in zawartosc)
    # Modułu automatyzacji w repozytorium nie ma, więc katalog nie ma prawa ich obiecywać:
    # użytkownik kupowałby Pro między innymi za funkcję, której nie dostanie.
    assert not any("utomatyzac" in zdanie for zdanie in zawartosc)


def test_cennik_podaje_zakres_okresu_probnego(client: TestClient, settings: Settings) -> None:
    """Cennik niesie zakres okresu próbnego wzięty stamtąd, skąd bierze go egzekwowanie.

    Karta planu obiecuje 1 GB, a przez pierwsze dni `api/files.py` przyjmuje 100 MB.
    Cennik musi podać tę węższą liczbę, żeby interfejs miał co pokazać obok obietnicy.
    """
    zaloguj(client, settings)
    plany = {pozycja["kod"]: pozycja for pozycja in client.get("/api/platnosci/plany").json()["plany"]}
    probny = plany["osobisty"]["probny"]
    assert probny["dni"] == 7
    assert probny["kredyty"] == 300
    # Ta sama liczba, którą zwraca egzekwowanie limitów dla konta w okresie próbnym.
    assert probny["przestrzen_mb"] == limity_planu("osobisty", "probna").przestrzen_mb
    assert probny["przestrzen_mb"] < plany["osobisty"]["przestrzen_mb"]
    # Poczta, synchronizacja i wersje plików są w okresie próbnym wyłączone.
    assert probny["skrzynki"] == 0
    assert probny["synchronizacja"] == 0
    assert probny["wersjonowanie"] == 0
    # Plan bez okresu próbnego nie niesie żadnego zakresu próbnego.
    assert plany["pro"]["probny"]["dni"] == 0


def test_cennik_podaje_kredyty_i_okres_probny(client: TestClient, settings: Settings) -> None:
    """Cennik niesie jedyny egzekwowany limit planu i warunki okresu próbnego."""
    zaloguj(client, settings)
    plany = {pozycja["kod"]: pozycja for pozycja in client.get("/api/platnosci/plany").json()["plany"]}
    assert plany["osobisty"]["kredyty_okresowo"] == 2_000
    assert plany["pro"]["kredyty_okresowo"] == 20_000
    assert plany["zespol"]["kredyty_okresowo"] == 60_000
    # Okres próbny ma tylko najniższy plan; cennik publiczny podaje to samo co moduł.
    assert plany["osobisty"]["okres_probny_dni"] == 7
    assert plany["pro"]["okres_probny_dni"] == 0
    publiczny = {pozycja["kod"]: pozycja for pozycja in client.get("/api/platnosci/cennik").json()["plany"]}
    assert publiczny["osobisty"]["okres_probny_dni"] == 7
    assert publiczny["osobisty"]["kredyty_okresowo"] == 2_000


def test_limit_pliku_pochodzi_z_ustawien_instalacji(client: TestClient, settings: Settings) -> None:
    """Rozmiar pliku bierze się z ``NEXUS_UPLOAD_LIMIT_MB``, a nie z pozycji katalogu."""
    assert not any("plik_mb" in pozycja.limity for pozycja in KATALOG)
    zaloguj(client, settings)
    dane = client.get("/api/platnosci/plany").json()
    limity = {pozycja["limity"]["plik_mb"] for pozycja in dane["plany"]}
    assert limity == {get_settings().upload_limit_mb}


def test_zmiana_limitu_pliku_widac_we_wszystkich_planach(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jedna zmiana ustawienia zmienia limit w każdym planie — katalog go nie powiela."""
    monkeypatch.setenv("NEXUS_UPLOAD_LIMIT_MB", "512")
    get_settings.cache_clear()
    try:
        assert {limity_pozycji(pozycja)["plik_mb"] for pozycja in KATALOG} == {512}
        assert limity_planu("pro", "aktywna").plik_mb == 512
    finally:
        get_settings.cache_clear()


def test_zaden_plan_nie_jest_bezplatny_a_komunikaty_nie_mowia_o_kredytach() -> None:
    """Wszystkie trzy plany są płatne, a komunikaty nie obiecują planu bez opłat.

    Słowo „kredyty” nie pada w komunikatach dla użytkownika: jednostka rozliczeniowa jest
    nasza, nie jego. Na zewnątrz mówimy o zakresie pracy i dostępie w okresie rozliczeniowym
    (ta sama zasada co w cenniku i w module płatności).
    """
    assert not any(pozycja.bezplatny for pozycja in KATALOG)
    bez_planu = stan_sprzedazy(
        Subskrypcja(uzytkownik=KONTO_ADMINA, plan_kod="osobisty", status="brak"), True
    )
    assert "zakresie przydzielonym do konta" in bez_planu.komunikat
    teksty = f"{bez_planu.tytul} {bez_planu.komunikat} {KOMUNIKAT_SPRZEDAZ_WYLACZONA}"
    assert "bez opłat" not in teksty
    assert "kredyt" not in teksty.lower()


def test_adres_powrotu_z_portalu_wraca_na_ekran_platnosci() -> None:
    adresy = adresy_powrotu(ustawienia_platnosci(), "https://danaco-nexus.test")
    assert adresy.portal == "https://danaco-nexus.test/m/platnosci?powrot=rozliczenia"
    assert adresy.anulowanie.endswith("?zakup=anulowany")


def test_stan_sprzedazy_rozpoznaje_kazdy_przypadek() -> None:
    """Stany brzegowe rozstrzygane bez bazy – jedna funkcja dla serwera i interfejsu."""
    bezplatna = Subskrypcja(uzytkownik=KONTO_ADMINA, plan_kod="osobisty", status="brak")
    assert stan_sprzedazy(bezplatna, True).kod == "plan_bezplatny"
    assert stan_sprzedazy(bezplatna, False).kod == "sprzedaz_wylaczona"
    probna = Subskrypcja(uzytkownik=KONTO_ADMINA, plan_kod="pro", status="probna")
    assert stan_sprzedazy(probna, True).kod == "okres_probny"
    zalegla = Subskrypcja(uzytkownik=KONTO_ADMINA, plan_kod="pro", status="zalegla")
    stan = stan_sprzedazy(zalegla, True, Faktura(status="open", strona_url="https://stripe.test/f"))
    assert stan.kod == "platnosc_odrzucona" and stan.dzialanie == "zaplac_fakture"


def test_rezygnacja_po_oplaconym_okresie_nie_udaje_braku_odnowienia() -> None:
    """Złożona rezygnacja wyprzedza „opłacony okres minął” – odnowienia nie miało być."""
    teraz = datetime(2026, 3, 1, tzinfo=UTC)
    koniec = datetime(2026, 2, 15, tzinfo=UTC)
    po_rezygnacji = Subskrypcja(
        uzytkownik=KONTO_ADMINA,
        plan_kod="pro",
        status="aktywna",
        anuluj_na_koniec=True,
        okres_do=koniec,
    )
    stan = stan_sprzedazy(po_rezygnacji, True, None, teraz)
    assert stan.kod == "rezygnacja_zlozona" and stan.dzialanie == "wybierz_plan"
    assert "zgodnie ze złożoną rezygnacją" in stan.komunikat
    bez_rezygnacji = Subskrypcja(
        uzytkownik=KONTO_ADMINA, plan_kod="pro", status="aktywna", okres_do=koniec
    )
    assert stan_sprzedazy(bez_rezygnacji, True, None, teraz).kod == "subskrypcja_wygasla"


def test_cennik_przyjmuje_cene_pakietu_kredytow() -> None:
    """Parser cennika rozpoznaje pozycję pakietu obok pozycji planu.

    Pakiet kupuje się jednorazowo, więc drugim członem klucza jest kod pakietu, a nie
    okres rozliczeniowy. Wcześniej parser odrzucał taką pozycję i dokupienie kredytów
    nie mogło zadziałać w żadnej konfiguracji.
    """
    ustawienia = UstawieniaPlatnosci(
        ceny=f"pro:miesiac={CENA_MIESIAC};pakiet:maly={CENA_PAKIETU_MALY};pakiet:nieznany=price_x"
    )
    assert ustawienia.cennik["pakiet:maly"] == CENA_PAKIETU_MALY
    assert ustawienia.cennik["pro:miesiac"] == CENA_MIESIAC
    # Kod spoza katalogu pakietów jest pomijany — nikt by go potem nie odnalazł.
    assert "pakiet:nieznany" not in ustawienia.cennik
    # Cena pakietu nie jest ceną subskrypcji: jednorazowa wpłata nie może przestawić planu.
    assert ustawienia.plan_dla_ceny(CENA_PAKIETU_MALY) is None
    assert ustawienia.plan_dla_ceny(CENA_MIESIAC) == ("pro", "miesiac")


def test_pakiet_z_cena_jest_do_kupienia(client: TestClient, settings: Settings) -> None:
    """Pakiet z ceną w środowisku jest do kupienia, pakiet bez ceny pozostaje „Wkrótce”."""
    zaloguj(client, settings)
    dane = client.get("/api/platnosci/pakiety").json()
    pakiety = {pozycja["kod"]: pozycja for pozycja in dane["pakiety"]}
    assert dane["sprzedaz"] is True
    assert pakiety["maly"]["do_kupienia"] is True
    assert pakiety["maly"]["kredyty"] == 5_000
    assert pakiety["duzy"]["do_kupienia"] is False


def test_zakup_pakietu_tworzy_jednorazowa_platnosc(
    client: TestClient, settings: Settings, atrapa: AtrapaStripe
) -> None:
    """Dokupienie kredytów idzie jako jednorazowa płatność z kodem pakietu w metadanych.

    Kredyty dopisuje dopiero webhook, więc w metadanych sesji musi być komu i ile.
    """
    zaloguj(client, settings)
    odpowiedz = client.post(
        "/api/platnosci/pakiety/checkout", json={"pakiet": "maly"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 200, odpowiedz.text
    assert odpowiedz.json()["url"].startswith("https://checkout.stripe.test/")
    sesja = atrapa.sesje_checkout[-1]
    assert sesja["mode"] == "payment"
    assert sesja["line_items"] == [{"price": CENA_PAKIETU_MALY, "quantity": 1}]
    assert sesja["metadata"]["pakiet"] == "maly"
    assert sesja["metadata"]["kredyty"] == "5000"
    assert sesja["metadata"]["uzytkownik"] == KONTO_ADMINA


def test_zakup_pakietu_bez_ceny_konczy_sie_zrozumialym_bledem(
    client: TestClient, settings: Settings
) -> None:
    """Pakiet bez ceny w Stripe nie startuje, a komunikat mówi, czego brakuje."""
    zaloguj(client, settings)
    odpowiedz = client.post(
        "/api/platnosci/pakiety/checkout", json={"pakiet": "duzy"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 502
    assert "nie ma jeszcze ceny" in odpowiedz.json()["detail"]
    # Komunikat wskazuje klucz do uzupełnienia, więc brak ceny da się naprawić bez czytania kodu.
    assert "pakiet:duzy" in odpowiedz.json()["detail"]


def test_pusta_zmienna_pliku_wylacza_sprzedaz(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Środowisko próbne wyłącza sprzedaż, przykrywając wpisy z `.env` pustą wartością.

    Przedsionek próbował tego nazwami `NEXUS_STRIPE_SECRET_KEY`, których nikt nie czyta —
    i pracował na produkcyjnym kluczu Stripe z włączoną sprzedażą. Po poprawieniu nazw
    pusta wartość musi znaczyć „nie ma pliku”, a nie „plik o pustej nazwie”.
    """
    from nexus.platnosci.konfiguracja import UstawieniaPlatnosci

    klucz = tmp_path / "stripe-klucz"
    klucz.write_text("sk_test_abc", encoding="utf-8")

    monkeypatch.setenv("NEXUS_PLATNOSCI_STRIPE_KLUCZ_PLIK", str(klucz))
    assert UstawieniaPlatnosci().klucz == "sk_test_abc"

    monkeypatch.setenv("NEXUS_PLATNOSCI_STRIPE_KLUCZ_PLIK", "")
    monkeypatch.setenv("NEXUS_PLATNOSCI_STRIPE_KLUCZ", "")
    assert UstawieniaPlatnosci().klucz == ""


def test_strona_obiecuje_tyle_przestrzeni_ile_daje_katalog() -> None:
    """Zdania sprzedażowe o przestrzeni mają się zgadzać z katalogiem planów.

    Cennik na stronie idzie z serwera, ale zdanie „Własna przestrzeń w chmurze Nexusa:
    1 GB w planie Osobistym, 2 GB w Pro, 10 GB w Grupie” jest wpisane w tekst na stałe.
    Zmiana pojemności w katalogu nie ruszy tego zdania — a to obietnica sprzedażowa,
    nie ozdoba, i klient rozliczy nas z tego, co przeczytał przed zakupem.
    """
    tresc = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "landing" / "tresc.ts").read_text(
        encoding="utf-8"
    )
    for plan in KATALOG:
        gb = plan.przestrzen_gb
        napis = f"{gb:.0f} GB" if float(gb).is_integer() else f"{gb} GB"
        assert napis in tresc, (
            f"plan {plan.nazwa} daje {napis} przestrzeni, a tekst strony o tym nie mówi — "
            "sprawdź GWARANCJE w frontend/src/landing/tresc.ts"
        )
        assert plan.nazwa in tresc, f"plan {plan.nazwa} nie występuje w tekście strony"


# --- Kredyty okresu próbnego -----------------------------------------------------------
#
# Cennik obiecuje na 7 dni próbnych planu Osobisty węższy zakres (`probny_kredyty`), a serwer
# dawał już przy fakturze próbnej na 0 zł pełny przydział okresu (`kredyty_okresowo`).
# Pełny przydział ma przyjść dopiero z pierwszą opłaconą fakturą. Scenariusze biegną na
# koncie klienta: właściciel instalacji dostaje na start pełny plan, bez zakresu próbnego.

# Cena spoza cennika testowego: plan rozpoznaje się wtedy z metadanych subskrypcji.
CENA_OSOBISTY = "price_test_osobisty_miesiac"
OSOBISTY = next(plan for plan in KATALOG if plan.kod == "osobisty")
PROBNY = OSOBISTY.probny_kredyty
PELNY = OSOBISTY.kredyty_okresowo
PRO = next(plan for plan in KATALOG if plan.kod == "pro")
# Konto klienta portalu — tak kasa zapisuje je w metadanych Stripe.
KONTO_KLIENTA = "5b0c3a52-6f1e-4c8e-9d7a-2f4e8b1c9a10"


def subskrypcja_klienta(status: str, plan: str = "osobisty", cena: str = CENA_OSOBISTY) -> dict[str, Any]:
    """Subskrypcja klienta — ``trialing`` w okresie próbnym, ``active`` po nim."""
    return {
        **subskrypcja_biezaca(status, cena),
        "metadata": {"uzytkownik": KONTO_KLIENTA, "plan": plan, "okres": "miesiac"},
    }


def subskrypcja_osobista(status: str) -> dict[str, Any]:
    """Subskrypcja planu Osobisty — ``trialing`` w okresie próbnym, ``active`` po nim."""
    return subskrypcja_klienta(status)


def faktura_subskrypcji(identyfikator: str, kwota_gr: int, powod: str) -> dict[str, Any]:
    """Opłacona faktura subskrypcji klienta; ``billing_reason`` jak w Stripe."""
    return {
        **faktura_stripe("paid", identyfikator),
        "subscription": SUBSKRYPCJA_STRIPE,
        "billing_reason": powod,
        "amount_due": kwota_gr,
        "amount_paid": kwota_gr,
        "total": kwota_gr,
        "metadata": {"uzytkownik": KONTO_KLIENTA},
    }


def start_okresu_probnego() -> dict[str, Any]:
    """Zdarzenie: subskrypcja planu Osobisty weszła w okres próbny."""
    return zdarzenie("customer.subscription.created", subskrypcja_osobista("trialing"), "evt_probna_1")


def faktura_probna() -> dict[str, Any]:
    """Zdarzenie: opłacona faktura na 0 zł, którą Stripe otwiera okres próbny."""
    faktura = faktura_subskrypcji("in_probna_1", 0, "subscription_create")
    return zdarzenie("invoice.paid", faktura, "evt_probna_2")


def ksiega_klienta(settings: Settings) -> tuple[int, list[str]]:
    """Saldo konta klienta i powody wpisów księgi (od najstarszego)."""
    import uuid

    async def run() -> tuple[int, list[str]]:
        database = Database(settings.database_url)
        try:
            konto = uuid.UUID(KONTO_KLIENTA)
            saldo = (await kredyty.stan(database, konto)).saldo
            wpisy = await kredyty.historia(database, konto)
        finally:
            await database.close()
        return saldo, [wpis["powod"] for wpis in reversed(wpisy)]

    return asyncio.run(run())


def pierwsze_zlecenie_klienta(settings: Settings) -> None:
    """To samo sprawdzenie, które poprzedza każde zlecenie pracy agentowi."""
    import uuid

    async def run() -> None:
        database = Database(settings.database_url)
        try:
            await kredyty.sprawdz_przed_zleceniem(database, uuid.UUID(KONTO_KLIENTA))
        finally:
            await database.close()

    asyncio.run(run())


@pytest.mark.parametrize("subskrypcja_przed_faktura", [True, False])
def test_faktura_okresu_probnego_daje_zakres_probny(
    client: TestClient, settings: Settings, subskrypcja_przed_faktura: bool
) -> None:
    """Faktura na 0 zł otwierająca okres próbny daje tyle, ile obiecuje cennik.

    Stripe nie gwarantuje kolejności zdarzeń, więc faktura może przyjść, zanim baza
    dowie się o subskrypcji w okresie próbnym.
    """
    assert (PROBNY, PELNY) == (300, 2_000)
    kolejnosc = [start_okresu_probnego(), faktura_probna()]
    for tresc in kolejnosc if subskrypcja_przed_faktura else reversed(kolejnosc):
        assert wyslij_zdarzenie(client, tresc).status_code == 200

    assert ksiega_klienta(settings) == (PROBNY, ["okres-probny"])
    # Pierwsze zlecenie po fakturze nie dopisuje przydziału startowego drugi raz.
    pierwsze_zlecenie_klienta(settings)
    assert ksiega_klienta(settings) == (PROBNY, ["okres-probny"])


def test_zlecenie_przed_faktura_probna_nie_dubluje_przydzialu(client: TestClient, settings: Settings) -> None:
    """Konto, które zleciło pracę przed nadejściem faktury próbnej, nie dostaje zakresu dwa razy."""
    wyslij_zdarzenie(client, start_okresu_probnego())
    pierwsze_zlecenie_klienta(settings)
    assert ksiega_klienta(settings) == (PROBNY, ["start"])
    wyslij_zdarzenie(client, faktura_probna())
    assert ksiega_klienta(settings) == (PROBNY, ["start"])


def test_zakup_przed_okresem_probnym_nie_odbiera_zakresu_probnego(
    client: TestClient, settings: Settings
) -> None:
    """Klient najpierw dokupił pakiet, potem zaczął okres próbny — zakres próbny mu przysługuje."""
    zakup = {
        "id": "cs_test_pakiet_1",
        "object": "checkout.session",
        "mode": "payment",
        "payment_status": "paid",
        "customer": KLIENT_STRIPE,
        "metadata": {"uzytkownik": KONTO_KLIENTA, "pakiet": "maly", "kredyty": "5000"},
    }
    wyslij_zdarzenie(client, zdarzenie("checkout.session.completed", zakup, "evt_pakiet_1"))
    assert ksiega_klienta(settings) == (5_000, ["zakup"])

    wyslij_zdarzenie(client, start_okresu_probnego())
    wyslij_zdarzenie(client, faktura_probna())

    assert ksiega_klienta(settings) == (5_000 + PROBNY, ["zakup", "okres-probny"])


@pytest.mark.parametrize("kwota_gr", [1_900, 0], ids=["platna", "rabat-100-procent"])
@pytest.mark.parametrize("stan_przed_faktura", [True, False], ids=["stan-najpierw", "faktura-najpierw"])
def test_pierwsza_platna_faktura_daje_pelny_przydzial(
    client: TestClient, settings: Settings, kwota_gr: int, stan_przed_faktura: bool
) -> None:
    """Po okresie próbnym pierwsza faktura okresu dopisuje pełny przydział planu — raz.

    Faktura za pierwszy płatny okres (``subscription_cycle``) bywa doręczona przed zmianą
    stanu subskrypcji na ``active``; nie może być wtedy wzięta za próbną. Pełny rabat
    (faktura na 0 zł) nie zmienia tego, że zaczął się okres płatny.
    """
    wyslij_zdarzenie(client, start_okresu_probnego())
    wyslij_zdarzenie(client, faktura_probna())
    aktywna = zdarzenie("customer.subscription.updated", subskrypcja_osobista("active"), "evt_probna_3")
    faktura = faktura_subskrypcji("in_platna_1", kwota_gr, "subscription_cycle")
    platna = zdarzenie("invoice.paid", faktura, "evt_probna_4")
    for tresc in (aktywna, platna) if stan_przed_faktura else (platna, aktywna):
        assert wyslij_zdarzenie(client, tresc).status_code == 200

    assert ksiega_klienta(settings) == (PROBNY + PELNY, ["okres-probny", "odnowienie"])
    # Ponowne doręczenie tej samej faktury niczego nie dopisuje.
    assert wyslij_zdarzenie(client, platna).json()["duplikat"] is True
    assert ksiega_klienta(settings)[0] == PROBNY + PELNY


def test_plan_bez_okresu_probnego_dostaje_pelny_przydzial_od_pierwszej_faktury(
    client: TestClient, settings: Settings
) -> None:
    """Plan Pro nie ma okresu próbnego: pierwsza opłacona faktura daje jego pełny przydział."""
    subskrypcja = subskrypcja_klienta("active", "pro", CENA_MIESIAC)
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja, "evt_pro_1"))
    faktura = faktura_subskrypcji("in_pro_1", 4_900, "subscription_create")
    wyslij_zdarzenie(client, zdarzenie("invoice.paid", faktura, "evt_pro_2"))
    assert ksiega_klienta(settings) == (PRO.kredyty_okresowo, ["odnowienie"])


# Plan faktury: pozycja z ceną (starsze i nowsze API Stripe) albo metadane subskrypcji,
# które Stripe kopiuje do faktury. Baza wie o subskrypcji dopiero po jej zdarzeniu.
PLAN_NA_FAKTURZE = {
    "cena-pozycji": {"lines": {"object": "list", "data": [{"id": "il_1", "price": {"id": CENA_MIESIAC}}]}},
    "cena-pozycji-nowe-api": {
        "lines": {
            "object": "list",
            "data": [{"id": "il_1", "pricing": {"price_details": {"price": CENA_MIESIAC}}}],
        }
    },
    "metadane-subskrypcji": {"subscription_details": {"metadata": {"plan": "pro", "okres": "miesiac"}}},
    "metadane-subskrypcji-nowe-api": {"parent": {"subscription_details": {"metadata": {"plan": "pro"}}}},
}


@pytest.mark.parametrize("zrodlo", list(PLAN_NA_FAKTURZE))
@pytest.mark.parametrize("kwota_gr", [4_900, 0], ids=["platna", "rabat-100-procent"])
def test_plan_z_faktury_gdy_faktura_wyprzedza_subskrypcje(
    client: TestClient, settings: Settings, zrodlo: str, kwota_gr: int
) -> None:
    """Zakup planu Pro: faktura przychodzi przed ``customer.subscription.created``.

    Rekord w bazie ma wtedy jeszcze plan domyślny (Osobisty, z okresem próbnym). Płatna
    faktura dawała przydział Osobistego (2 000 zamiast 20 000), a faktura na 0 zł z pełnym
    rabatem była brana za okres próbny. O planie rozstrzyga sama faktura.
    """
    faktura = {**faktura_subskrypcji("in_pro_1", kwota_gr, "subscription_create"), **PLAN_NA_FAKTURZE[zrodlo]}
    assert wyslij_zdarzenie(client, zdarzenie("invoice.paid", faktura, "evt_pro_2")).status_code == 200
    assert ksiega_klienta(settings) == (PRO.kredyty_okresowo, ["odnowienie"])

    subskrypcja = subskrypcja_klienta("active", "pro", CENA_MIESIAC)
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja, "evt_pro_1"))
    assert ksiega_klienta(settings) == (PRO.kredyty_okresowo, ["odnowienie"])


def test_plan_z_faktury_pomija_zwrot_za_poprzedni_plan() -> None:
    """Faktura zmiany planu zaczyna się od zwrotu (kwota ujemna) za niewykorzystany czas
    poprzedniego planu — plan wyznacza pozycja nowego planu, nie ta pierwsza."""
    from nexus.platnosci.zdarzenia import _plan_z_faktury

    ustawienia = UstawieniaPlatnosci(ceny="pro:miesiac=price_pro;osobisty:miesiac=price_osobisty")
    faktura = {
        "lines": {
            "data": [
                {"amount": -1_900, "price": {"id": "price_osobisty"}},
                {"amount": 4_900, "price": {"id": "price_pro"}},
            ]
        }
    }
    assert _plan_z_faktury(ustawienia, faktura) == "pro"


# --- Wspólne konto Stripe: zdarzenia innych produktów ------------------------------------
#
# Na tym samym koncie Stripe sprzedają też danaco-lex.pl i e-kancelaria.app, a webhook
# dostaje wszystkie zdarzenia wybranych typów z całego konta. Zdarzenie bez konta Nexusa
# zostaje w dzienniku jako „pominiete” i niczego nie zmienia — dotąd trafiało do właściciela
# instalacji razem z fakturą, rekordem subskrypcji i kredytami.

OBCY_KLIENT = "cus_obcy_ekancelaria"
OBCA_CENA = "price_obca_ekancelaria"
OKRES_OD_DAHLIA = 1_771_200_000


def obca_subskrypcja(status: str = "active", cena: str = OBCA_CENA) -> dict[str, Any]:
    """Subskrypcja innego produktu: nieznany klient, bez metadanych Nexusa, obca cena."""
    return {
        "id": "sub_obca_1",
        "object": "subscription",
        "customer": OBCY_KLIENT,
        "status": status,
        "billing_mode": {"type": "flexible"},
        "cancel_at": None,
        "cancel_at_period_end": False,
        "metadata": {"planId": "basic"},
        "items": {
            "object": "list",
            "data": [
                {
                    "id": "si_obcy_1",
                    "quantity": 1,
                    "price": {"id": cena},
                    "current_period_start": OKRES_OD_DAHLIA,
                    "current_period_end": OKRES_DO_BIEZACY,
                }
            ],
        },
    }


def obca_faktura(status: str = "paid") -> dict[str, Any]:
    """Faktura subskrypcji innego produktu (kształt API 2026-06-24.dahlia)."""
    return {
        "id": "in_obca_1",
        "object": "invoice",
        "customer": OBCY_KLIENT,
        "status": status,
        "number": "EK-2026-0001",
        "currency": "pln",
        "billing_reason": "subscription_cycle",
        "amount_due": 9_900,
        "amount_paid": 9_900 if status == "paid" else 0,
        "total": 9_900,
        "created": 1_771_200_000,
        "invoice_pdf": "https://stripe.test/faktury/in_obca_1.pdf",
        "status_transitions": {"paid_at": 1_771_200_100 if status == "paid" else None},
        "metadata": {},
        "parent": {
            "type": "subscription_details",
            "subscription_details": {"subscription": "sub_obca_1", "metadata": {"planId": "basic"}},
        },
        "lines": {
            "object": "list",
            "data": [
                {
                    "id": "il_obca_1",
                    "amount": 9_900,
                    "pricing": {"type": "price_details", "price_details": {"price": OBCA_CENA}},
                }
            ],
        },
    }


def obca_sesja(**zmiany: Any) -> dict[str, Any]:
    """Sesja zakupu jak w e-kancelaria.app: bez klienta Stripe, z własnymi metadanymi."""
    return {
        "id": "cs_obca_1",
        "object": "checkout.session",
        "mode": "payment",
        "status": "complete",
        "payment_status": "paid",
        "customer": None,
        "customer_email": "klient@example.com",
        "amount_total": 9_900,
        "currency": "pln",
        "client_reference_id": None,
        "subscription": None,
        "metadata": {"caseId": "sprawa-1", "planId": "basic", "category": "cywilne"},
        **zmiany,
    }


OBCE_ZDARZENIA: dict[str, tuple[str, dict[str, Any]]] = {
    "sesja-bez-klienta": ("checkout.session.completed", obca_sesja()),
    # danaco-lex.pl zapisuje identyfikatory użytkowników jako uuid4().hex — bez łączników.
    "sesja-z-identyfikatorem-bez-lacznikow": (
        "checkout.session.completed",
        obca_sesja(
            mode="subscription",
            customer=OBCY_KLIENT,
            subscription="sub_obca_1",
            client_reference_id="3f2a9c1e5b7d4e8f9a0b1c2d3e4f5a6b",
        ),
    ),
    "sesja-z-obcym-loginem": (
        "checkout.session.completed",
        obca_sesja(client_reference_id="order-77", metadata={"uzytkownik": "jan.kowalski"}),
    ),
    "subskrypcja-utworzona": ("customer.subscription.created", obca_subskrypcja()),
    "subskrypcja-zmieniona": ("customer.subscription.updated", obca_subskrypcja("past_due")),
    "subskrypcja-usunieta": ("customer.subscription.deleted", obca_subskrypcja("canceled")),
    "faktura-oplacona": ("invoice.paid", obca_faktura()),
    "faktura-nieoplacona": ("invoice.payment_failed", obca_faktura("open")),
}


def migawka_bazy(settings: Settings) -> dict[str, Any]:
    """Stan tabel, które zdarzenie Stripe może zmienić: subskrypcje, faktury, kredyty."""

    async def run() -> dict[str, Any]:
        database = Database(settings.database_url)
        try:
            async with database.session() as session:
                subskrypcje = [
                    (
                        rekord.uzytkownik,
                        rekord.plan_kod,
                        rekord.status,
                        rekord.okres,
                        rekord.stripe_customer_id,
                        rekord.stripe_subscription_id,
                        rekord.okres_do,
                        rekord.anuluj_na_koniec,
                        rekord.miejsca,
                    )
                    for rekord in (await session.scalars(select(Subskrypcja))).all()
                ]
                faktury = sorted((await session.scalars(select(Faktura.stripe_invoice_id))).all())
                ruchy = await session.scalar(select(func.count()).select_from(kredyty.RuchKredytow))
                wynik = await session.scalars(select(kredyty.SaldoKredytow))
                salda = [(saldo.owner_id, saldo.saldo) for saldo in wynik]
        finally:
            await database.close()
        subskrypcje.sort(key=str)
        return {"subskrypcje": subskrypcje, "faktury": faktury, "ruchy": ruchy, "salda": salda}

    return asyncio.run(run())


def wpis_dziennika(settings: Settings, identyfikator: str) -> ZdarzenieStripe:
    """Wpis dziennika zdarzeń webhooka."""

    async def run() -> ZdarzenieStripe | None:
        database = Database(settings.database_url)
        try:
            async with database.session() as session:
                return await session.get(ZdarzenieStripe, identyfikator)
        finally:
            await database.close()

    wpis = asyncio.run(run())
    assert wpis is not None
    return wpis


def rekord_subskrypcji(settings: Settings, uzytkownik: str) -> Subskrypcja:
    """Rekord subskrypcji konta prosto z bazy."""

    async def run() -> Subskrypcja | None:
        database = Database(settings.database_url)
        try:
            async with database.session() as session:
                return await session.scalar(select(Subskrypcja).where(Subskrypcja.uzytkownik == uzytkownik))
        finally:
            await database.close()

    rekord = asyncio.run(run())
    assert rekord is not None
    return rekord


def faktura_z_bazy(settings: Settings, identyfikator: str) -> Faktura | None:
    """Faktura zapisana w bazie (albo ``None``)."""

    async def run() -> Faktura | None:
        database = Database(settings.database_url)
        try:
            async with database.session() as session:
                return await session.scalar(select(Faktura).where(Faktura.stripe_invoice_id == identyfikator))
        finally:
            await database.close()

    return asyncio.run(run())


@pytest.mark.parametrize("nazwa", list(OBCE_ZDARZENIA))
def test_obce_zdarzenie_jest_pomijane_i_niczego_nie_zmienia(
    client: TestClient, settings: Settings, nazwa: str
) -> None:
    """Każdy obsługiwany typ zdarzenia z innego produktu: wpis „pominiete”, stan bez zmian.

    Konto Nexusa ma już subskrypcję, fakturę i kredyty, żeby było widać, że obce zdarzenie
    nie dopisuje niczego ani nie nadpisuje stanu właściciela instalacji.
    """
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.created", subskrypcja_biezaca(), "evt_nexus_1"))
    wyslij_zdarzenie(client, zdarzenie("invoice.paid", faktura_stripe(), "evt_nexus_2"))
    wyslij_zdarzenie(
        client,
        zdarzenie("checkout.session.completed", {
            "id": "cs_nexus_1",
            "object": "checkout.session",
            "mode": "payment",
            "payment_status": "paid",
            "customer": KLIENT_STRIPE,
            "metadata": {"uzytkownik": KONTO_ADMINA, "pakiet": "maly", "kredyty": "5000"},
        }, "evt_nexus_3"),
    )
    przed = migawka_bazy(settings)
    assert przed["faktury"] == ["in_test_1"] and przed["ruchy"] == 1

    typ, obiekt = OBCE_ZDARZENIA[nazwa]
    odpowiedz = wyslij_zdarzenie(client, zdarzenie(typ, obiekt, "evt_obce_1"))

    assert odpowiedz.status_code == 200, odpowiedz.text
    assert odpowiedz.json() == {"otrzymano": True, "obsluzone": False, "typ": typ}
    wpis = wpis_dziennika(settings, "evt_obce_1")
    assert (wpis.status, wpis.blad) == ("pominiete", POMINIETE_OBCE)
    assert wpis.przetworzone_at is not None
    assert migawka_bazy(settings) == przed


def test_obca_sesja_z_identyfikatorem_uuid_jest_pomijana_bez_danych(
    client: TestClient, settings: Settings
) -> None:
    """Inny produkt na wspólnym koncie Stripe zapisuje w ``client_reference_id`` własny UUID.

    Sama postać identyfikatora nie czyni zdarzenia Nexusowym — konto musi istnieć. Ładunek
    obcego zdarzenia (adres i kwota cudzego klienta) nie zostaje w bazie Nexusa.
    """
    obcy = str(uuid.uuid4())
    sesja = {
        "id": "cs_obca_uuid",
        "object": "checkout.session",
        "mode": "payment",
        "payment_status": "paid",
        "customer": "cus_obcy_produkt",
        "customer_details": {"email": "klient@innego-produktu.pl"},
        "client_reference_id": obcy,
        "metadata": {"uzytkownik": obcy, "kredyty": "5000"},
    }
    przed = migawka_bazy(settings)

    odpowiedz = wyslij_zdarzenie(client, zdarzenie("checkout.session.completed", sesja, "evt_obce_uuid"))

    assert odpowiedz.json()["obsluzone"] is False
    wpis = wpis_dziennika(settings, "evt_obce_uuid")
    assert (wpis.status, wpis.blad, wpis.ladunek) == ("pominiete", POMINIETE_OBCE, {})
    assert migawka_bazy(settings) == przed


def test_obca_faktura_nie_trafia_na_liste_wlasciciela(client: TestClient, settings: Settings) -> None:
    """Faktura innego produktu nie pojawia się w rozliczeniach właściciela instalacji."""
    wyslij_zdarzenie(client, zdarzenie("invoice.paid", obca_faktura(), "evt_obce_2"))
    zaloguj(client, settings)
    assert client.get("/api/platnosci/faktury").json() == []
    assert faktura_z_bazy(settings, "in_obca_1") is None


def test_cena_nexusa_bez_konta_jest_pominieta_z_opisem(client: TestClient, settings: Settings) -> None:
    """Subskrypcja z ceną Nexusa, ale bez konta (np. założona ręcznie w panelu Stripe).

    Cena mówi, że to sprzedaż Nexusa, ale nie mówi, czyja — zdarzenie nie idzie do właściciela
    instalacji, tylko zostaje w dzienniku z opisem do wyjaśnienia.
    """
    przed = migawka_bazy(settings)
    tresc = zdarzenie("customer.subscription.created", obca_subskrypcja(cena=CENA_MIESIAC), "evt_obce_3")
    assert wyslij_zdarzenie(client, tresc).json()["obsluzone"] is False
    wpis = wpis_dziennika(settings, "evt_obce_3")
    assert (wpis.status, wpis.blad) == ("pominiete", POMINIETE_CENA_NEXUSA)
    assert migawka_bazy(settings) == przed


def test_login_administratora_instalacji_nadal_rozpoznawany(client: TestClient, settings: Settings) -> None:
    """Subskrypcje sprzed kluczowania kontem niosą login instalacji — to wciąż konto Nexusa."""
    zaloguj(client, settings)
    metadane = {"uzytkownik": "admin", "plan": "pro", "okres": "miesiac"}
    subskrypcja = {**subskrypcja_biezaca(), "metadata": metadane}
    tresc = zdarzenie("customer.subscription.created", subskrypcja, "evt_login_1")
    assert wyslij_zdarzenie(client, tresc).json()["obsluzone"] is True
    assert rekord_subskrypcji(settings, "admin").plan_kod == "pro"


# --- Ładunki w kształcie API 2026-06-24.dahlia -------------------------------------------
#
# Konto Stripe pracuje na wersji 2026-06-24.dahlia, a Nexus nie ustawia nagłówka
# Stripe-Version, więc webhook dostaje obiekty w tym kształcie: faktura bez `subscription`
# i bez metadanych konta (są w `parent.subscription_details`), cena pozycji faktury
# w `pricing.price_details.price`, okres subskrypcji wyłącznie na jej pozycjach, kupon kodu
# promocyjnego w `promotion.coupon`.


def subskrypcja_dahlia(
    status: str, plan: str = "osobisty", cena: str = CENA_OSOBISTY, **zmiany: Any
) -> dict[str, Any]:
    """Subskrypcja klienta bez okresu na poziomie subskrypcji (jest na pozycji)."""
    return {
        "id": SUBSKRYPCJA_STRIPE,
        "object": "subscription",
        "customer": KLIENT_STRIPE,
        "status": status,
        "billing_mode": {"type": "flexible"},
        "cancel_at": None,
        "cancel_at_period_end": False,
        "metadata": {"uzytkownik": KONTO_KLIENTA, "plan": plan, "okres": "miesiac"},
        "items": {
            "object": "list",
            "data": [
                {
                    "id": "si_test_1",
                    "object": "subscription_item",
                    "quantity": 1,
                    "price": {"id": cena, "object": "price"},
                    "current_period_start": OKRES_OD_DAHLIA,
                    "current_period_end": OKRES_DO_BIEZACY,
                }
            ],
        },
        **zmiany,
    }


def faktura_dahlia(
    identyfikator: str,
    kwota_gr: int,
    powod: str,
    plan: str = "osobisty",
    cena: str = CENA_OSOBISTY,
    konto: str = KONTO_KLIENTA,
) -> dict[str, Any]:
    """Opłacona faktura subskrypcji: konto i subskrypcja w ``parent.subscription_details``."""
    metadane = {"uzytkownik": konto, "plan": plan, "okres": "miesiac"} if konto else {}
    return {
        "id": identyfikator,
        "object": "invoice",
        "customer": KLIENT_STRIPE,
        "number": "NEXUS-2026-0042",
        "currency": "pln",
        "status": "paid",
        "billing_reason": powod,
        "amount_due": kwota_gr,
        "amount_paid": kwota_gr,
        "amount_remaining": 0,
        "total": kwota_gr,
        "created": 1_771_200_000,
        "invoice_pdf": f"https://stripe.test/faktury/{identyfikator}.pdf",
        "hosted_invoice_url": f"https://stripe.test/faktury/{identyfikator}",
        "status_transitions": {"finalized_at": 1_771_200_050, "paid_at": 1_771_200_100},
        "metadata": {},
        "parent": {
            "type": "subscription_details",
            "quote_details": None,
            "subscription_details": {"subscription": SUBSKRYPCJA_STRIPE, "metadata": metadane},
        },
        "lines": {
            "object": "list",
            "data": [
                {
                    "id": "il_test_1",
                    "object": "line_item",
                    "amount": kwota_gr,
                    "currency": "pln",
                    "pricing": {
                        "type": "price_details",
                        "price_details": {"price": cena, "product": "prod_test_1"},
                        "unit_amount_decimal": str(kwota_gr),
                    },
                    "parent": {
                        "type": "subscription_item_details",
                        "subscription_item_details": {
                            "subscription": SUBSKRYPCJA_STRIPE,
                            "subscription_item": "si_test_1",
                            "proration": False,
                        },
                    },
                }
            ],
        },
    }


def sesja_dahlia(**zmiany: Any) -> dict[str, Any]:
    """Sesja Checkout zamknięta po zakupie w kasie Nexusa."""
    return {
        "id": "cs_test_dahlia",
        "object": "checkout.session",
        "status": "complete",
        "currency": "pln",
        "customer": KLIENT_STRIPE,
        "client_reference_id": KONTO_KLIENTA,
        **zmiany,
    }


@pytest.mark.parametrize(
    "subskrypcja_przed_faktura", [True, False], ids=["stan-najpierw", "faktura-najpierw"]
)
def test_dahlia_faktury_subskrypcji_okres_probny_i_platny(
    client: TestClient, settings: Settings, subskrypcja_przed_faktura: bool
) -> None:
    """invoice.paid w nowym kształcie: faktura próbna daje zakres próbny, płatna — pełny.

    Przy „faktura-najpierw” baza nie zna jeszcze klienta Stripe, więc konto wskazują
    wyłącznie metadane subskrypcji skopiowane do ``parent.subscription_details``.
    """
    start = zdarzenie("customer.subscription.created", subskrypcja_dahlia("trialing"), "evt_dahlia_1")
    faktura = faktura_dahlia("in_dahlia_1", 0, "subscription_create")
    probna = zdarzenie("invoice.paid", faktura, "evt_dahlia_2")
    for tresc in (start, probna) if subskrypcja_przed_faktura else (probna, start):
        assert wyslij_zdarzenie(client, tresc).json()["obsluzone"] is True
    assert ksiega_klienta(settings) == (PROBNY, ["okres-probny"])

    aktywna = zdarzenie("customer.subscription.updated", subskrypcja_dahlia("active"), "evt_dahlia_3")
    platna = zdarzenie(
        "invoice.paid", faktura_dahlia("in_dahlia_2", 1_900, "subscription_cycle"), "evt_dahlia_4"
    )
    for tresc in (aktywna, platna):
        assert wyslij_zdarzenie(client, tresc).json()["obsluzone"] is True
    assert ksiega_klienta(settings) == (PROBNY + PELNY, ["okres-probny", "odnowienie"])


def test_dahlia_plan_z_ceny_pozycji_faktury(client: TestClient, settings: Settings) -> None:
    """Plan Pro rozpoznany po ``pricing.price_details.price``, zanim baza zna subskrypcję."""
    faktura = faktura_dahlia("in_dahlia_3", 4_900, "subscription_create", plan="", cena=CENA_MIESIAC)
    assert wyslij_zdarzenie(client, zdarzenie("invoice.paid", faktura, "evt_dahlia_5")).json()["obsluzone"]
    assert ksiega_klienta(settings) == (PRO.kredyty_okresowo, ["odnowienie"])


def test_dahlia_zakup_subskrypcji_wiaze_konto_z_klientem(client: TestClient, settings: Settings) -> None:
    """checkout.session.completed (subskrypcja), a potem faktura bez metadanych konta.

    Po zakupie konto zna klienta Stripe, więc fakturę bez oznaczenia konta rozpoznaje
    po kliencie — tak jak w produkcji, gdzie klienta zakłada kasa przed sesją zakupu.
    """
    sesja = sesja_dahlia(
        mode="subscription",
        payment_status="paid",
        subscription=SUBSKRYPCJA_STRIPE,
        amount_total=49_000,
        metadata={"uzytkownik": KONTO_KLIENTA, "plan": "pro", "okres": "rok"},
    )
    assert wyslij_zdarzenie(client, zdarzenie("checkout.session.completed", sesja, "evt_dahlia_6")).json()[
        "obsluzone"
    ]
    rekord = rekord_subskrypcji(settings, KONTO_KLIENTA)
    assert (rekord.stripe_customer_id, rekord.stripe_subscription_id) == (KLIENT_STRIPE, SUBSKRYPCJA_STRIPE)
    assert (rekord.plan_kod, rekord.okres) == ("pro", "rok")

    faktura = faktura_dahlia("in_dahlia_4", 49_000, "subscription_create", cena=CENA_ROK, konto="")
    assert wyslij_zdarzenie(client, zdarzenie("invoice.paid", faktura, "evt_dahlia_7")).json()["obsluzone"]
    zapisana = faktura_z_bazy(settings, "in_dahlia_4")
    assert zapisana is not None and zapisana.uzytkownik == KONTO_KLIENTA
    assert ksiega_klienta(settings) == (PRO.kredyty_okresowo, ["odnowienie"])


def test_dahlia_zakup_pakietu_i_jego_faktura(client: TestClient, settings: Settings) -> None:
    """checkout.session.completed (pakiet) i faktura pakietu bez ``parent`` ani metadanych.

    Klienta Stripe zakłada kasa Nexusa przed sesją zakupu, więc fakturę pakietu — bez żadnego
    oznaczenia konta — rozpoznaje klient. Faktura jednorazowa nie daje przydziału planu.
    """
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/pakiety/checkout", json={"pakiet": "maly"}, headers=HEADERS)
    assert odpowiedz.status_code == 200, odpowiedz.text
    przed = migawka_bazy(settings)

    sesja = sesja_dahlia(
        mode="payment",
        payment_status="paid",
        subscription=None,
        client_reference_id=KONTO_ADMINA,
        amount_total=4_900,
        invoice="in_pakiet_1",
        metadata={"uzytkownik": KONTO_ADMINA, "pakiet": "maly", "kredyty": "5000"},
    )
    assert wyslij_zdarzenie(client, zdarzenie("checkout.session.completed", sesja, "evt_dahlia_8")).json()[
        "obsluzone"
    ]
    faktura = {
        **faktura_dahlia("in_pakiet_1", 4_900, "manual", konto=""),
        "parent": None,
        "lines": {"object": "list", "data": [{"id": "il_pakiet_1", "amount": 4_900}]},
    }
    assert wyslij_zdarzenie(client, zdarzenie("invoice.paid", faktura, "evt_dahlia_9")).json()["obsluzone"]

    po = migawka_bazy(settings)
    assert po["ruchy"] == przed["ruchy"] + 1
    saldo = dict(po["salda"])[ADMIN_OWNER] - dict(przed["salda"]).get(ADMIN_OWNER, 0)
    assert saldo == 5_000
    zapisana = faktura_z_bazy(settings, "in_pakiet_1")
    assert zapisana is not None and zapisana.uzytkownik == KONTO_ADMINA


def test_dahlia_subskrypcja_bierze_okres_z_pozycji(client: TestClient, settings: Settings) -> None:
    """customer.subscription.updated bez ``current_period_*`` na subskrypcji."""
    subskrypcja = subskrypcja_dahlia("active", "pro", CENA_MIESIAC)
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.updated", subskrypcja, "evt_dahlia_10"))
    rekord = rekord_subskrypcji(settings, KONTO_KLIENTA)
    assert (rekord.plan_kod, rekord.okres, rekord.status) == ("pro", "miesiac", "aktywna")
    assert rekord.okres_od == datetime.fromtimestamp(OKRES_OD_DAHLIA, UTC)
    assert rekord.okres_do == datetime.fromtimestamp(OKRES_DO_BIEZACY, UTC)
    assert rekord.anuluj_na_koniec is False


def test_rezygnacja_przez_cancel_at_jest_rezygnacja(client: TestClient, settings: Settings) -> None:
    """W trybie „flexible” Stripe odradza ``cancel_at_period_end`` na rzecz ``cancel_at``."""
    subskrypcja = subskrypcja_dahlia("active", "pro", CENA_MIESIAC, cancel_at=OKRES_DO_BIEZACY)
    wyslij_zdarzenie(client, zdarzenie("customer.subscription.updated", subskrypcja, "evt_dahlia_11"))
    assert rekord_subskrypcji(settings, KONTO_KLIENTA).anuluj_na_koniec is True


def test_dahlia_zapis_faktury(client: TestClient, settings: Settings) -> None:
    """Kwota, numer, PDF, podgląd i data zapłaty z faktury w nowym kształcie."""
    faktura = faktura_dahlia("in_dahlia_5", 4_900, "subscription_create", "pro", CENA_MIESIAC, KONTO_ADMINA)
    wyslij_zdarzenie(client, zdarzenie("invoice.paid", faktura, "evt_dahlia_12"))
    zaloguj(client, settings)
    (pozycja,) = client.get("/api/platnosci/faktury").json()
    assert (pozycja["numer"], pozycja["kwota_gr"], pozycja["waluta"], pozycja["status"]) == (
        "NEXUS-2026-0042",
        4_900,
        "pln",
        "paid",
    )
    assert pozycja["pdf_url"] == "https://stripe.test/faktury/in_dahlia_5.pdf"
    assert pozycja["strona_url"] == "https://stripe.test/faktury/in_dahlia_5"
    assert pozycja["oplacona_at"] == datetime.fromtimestamp(1_771_200_100, UTC).isoformat()


def test_kupon_w_ksztalcie_dahlia(client: TestClient, settings: Settings, atrapa: AtrapaStripe) -> None:
    """Kod promocyjny od 2025-09-30.clover: kupon w ``promotion.coupon``, nie w ``coupon``."""
    atrapa.kupony["JESIEN2026"] = {
        "id": "promo_test_4",
        "object": "promotion_code",
        "code": "JESIEN2026",
        "active": True,
        "expires_at": None,
        "promotion": {
            "type": "coupon",
            "coupon": {"id": "cpn_test_4", "percent_off": 15, "valid": True, "name": "Jesień 2026"},
        },
    }
    atrapa.kupony["WYLACZONY"] = {
        "id": "promo_test_5",
        "active": True,
        "promotion": {"type": "coupon", "coupon": {"id": "cpn_test_5", "percent_off": 50, "valid": False}},
    }
    zaloguj(client, settings)
    odpowiedz = client.post("/api/platnosci/kupon", json={"kod": "JESIEN2026"}, headers=HEADERS)
    assert odpowiedz.status_code == 200, odpowiedz.text
    assert (odpowiedz.json()["rabat_procent"], odpowiedz.json()["opis"]) == (15, "Jesień 2026")
    assert client.post("/api/platnosci/kupon", json={"kod": "WYLACZONY"}, headers=HEADERS).status_code == 400


@pytest.mark.parametrize("ksztalt", ["dahlia", "sprzed-clover"])
def test_klient_http_podaje_kupon_kodu_promocyjnego(ksztalt: str) -> None:
    """Od clover ``promotion.coupon`` to sam identyfikator — klient dociąga kupon osobno.

    Atrapa transportu HTTP: żadne żądanie nie wychodzi do Stripe.
    """
    kupon = {"id": "cpn_1", "object": "coupon", "percent_off": 15, "valid": True}
    kod = {"id": "promo_1", "code": "JESIEN2026", "active": True}
    kod |= {"promotion": {"type": "coupon", "coupon": "cpn_1"}} if ksztalt == "dahlia" else {"coupon": kupon}
    sciezki: list[str] = []

    def obsluz(zadanie: httpx.Request) -> httpx.Response:
        sciezki.append(zadanie.url.path)
        if zadanie.url.path.endswith("/promotion_codes"):
            return httpx.Response(200, json={"object": "list", "data": [kod]})
        return httpx.Response(200, json=kupon)

    ustawienia = UstawieniaPlatnosci(stripe_klucz=KLUCZ_TESTOWY, api_url="https://stripe.test/v1")

    async def run() -> dict[str, Any] | None:
        klient = KlientHttpStripe(ustawienia, transport=httpx.MockTransport(obsluz))
        try:
            return await klient.znajdz_kod_promocyjny("JESIEN2026")
        finally:
            await klient.zamknij()

    znaleziony = asyncio.run(run())
    assert znaleziony is not None
    rabat = znaleziony.get("coupon") or znaleziony["promotion"]["coupon"]
    assert rabat["percent_off"] == 15
    dociagniety = ["/v1/coupons/cpn_1"] if ksztalt == "dahlia" else []
    assert sciezki == ["/v1/promotion_codes", *dociagniety]
