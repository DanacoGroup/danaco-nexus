"""Testy modułu płatności: cennik, zakup, portal, kupony, faktury, webhook i limity planów.

Testy nie łączą się z siecią – Stripe zastępuje atrapa protokołu ``KlientStripe``,
a zdarzenia webhooka to utrwalone ładunki podpisane sekretem testowym.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from nexus.api.app import create_app
from nexus.api.auth import set_admin_credentials
from nexus.config import Settings, get_settings
from nexus.db import ADMIN_OWNER, Database
from nexus.platnosci.klient import koduj_formularz
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
        yield test_client


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


def test_zaden_plan_nie_jest_bezplatny_a_konto_bez_planu_pracuje_na_kredytach() -> None:
    """Wszystkie trzy plany są płatne, więc żaden komunikat nie obiecuje planu bez opłat."""
    assert not any(pozycja.bezplatny for pozycja in KATALOG)
    bez_planu = stan_sprzedazy(
        Subskrypcja(uzytkownik=KONTO_ADMINA, plan_kod="osobisty", status="brak"), True
    )
    assert "kredytach" in bez_planu.komunikat
    assert "bez opłat" not in f"{bez_planu.tytul} {bez_planu.komunikat}"
    assert "bez opłat" not in KOMUNIKAT_SPRZEDAZ_WYLACZONA


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
