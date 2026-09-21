"""Konfiguracja sprzedaży: klucze Stripe, identyfikatory cen i kwoty planów.

Wszystkie sekrety pochodzą ze zmiennych środowiskowych ``NEXUS_PLATNOSCI_*`` albo
z plików wskazanych tymi zmiennymi. W repozytorium nie ma żadnego klucza, sekretu
webhooka ani identyfikatora ceny – cennik wiąże kod planu z ceną Stripe dopiero
w środowisku uruchomieniowym.

Zapis zmiennych zbiorczych: ``CENY`` to „pro:miesiac=price_…;pro:rok=price_…”, a ``KWOTY``
to kwoty brutto w groszach, np. „pro:miesiac=4900;pro:rok=49000”. Ceny pakietów kredytów
idą tą samą zmienną ``CENY`` pod kluczem „pakiet:<kod>”, np. „pakiet:maly=price_…”.
Klucz tajny konta
(``sk_…``) i sekret podpisu webhooka (``whsec_…``) podaje się wprost albo w pliku
o uprawnieniach 600, wskazanym zmienną ``*_PLIK``; plik ma pierwszeństwo. Pusta
``WERSJA_API`` oznacza wersję API przypisaną do konta Stripe, a ``ADRES_POWROTU``
zastępuje ``NEXUS_PUBLIC_URL`` w adresach, na które Stripe odsyła po zakupie.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from nexus.platnosci.pakiety import PAKIETY_WG_KODU, PRZEDROSTEK_PAKIETU

logger = logging.getLogger(__name__)

OKRESY = ("miesiac", "rok")
API_URL = "https://api.stripe.com/v1"


def _wczytaj_sekret(wartosc: str, plik: Path | None) -> str:
    """Sekret z zmiennej środowiskowej albo z pliku (plik ma pierwszeństwo)."""
    if plik is not None:
        try:
            return plik.read_text(encoding="utf-8").strip()
        except OSError as blad:
            logger.warning("Nie można odczytać sekretu płatności z pliku %s: %s", plik, blad)
            return ""
    return wartosc.strip()


def _mapa(zapis: str) -> dict[str, str]:
    """Rozbiera zapis ``plan:okres=wartosc;pakiet:kod=wartosc`` na słownik.

    Cennik prowadzi dwa rodzaje pozycji: subskrypcję planu (``plan:okres``) i pakiet
    kredytów kupowany jednorazowo (``pakiet:kod``). Rozróżnia je pierwszy człon klucza,
    bo pakiet nie ma okresu rozliczeniowego.
    """
    wynik: dict[str, str] = {}
    for pozycja in zapis.replace("\n", ";").split(";"):
        pozycja = pozycja.strip()
        if not pozycja or "=" not in pozycja:
            continue
        klucz, wartosc = pozycja.split("=", 1)
        klucz, wartosc = klucz.strip().lower(), wartosc.strip()
        if ":" not in klucz or not wartosc:
            continue
        rodzaj, druga_czesc = klucz.split(":", 1)
        if rodzaj == PRZEDROSTEK_PAKIETU:
            if druga_czesc not in PAKIETY_WG_KODU:
                logger.warning("Pominięto pozycję cennika %r: nieznany kod pakietu kredytów.", klucz)
                continue
        elif druga_czesc not in OKRESY:
            logger.warning("Pominięto pozycję cennika %r: nieznany okres rozliczeniowy.", klucz)
            continue
        wynik[f"{rodzaj}:{druga_czesc}"] = wartosc
    return wynik


class UstawieniaPlatnosci(BaseSettings):
    """Ustawienia modułu płatności (zmienne ``NEXUS_PLATNOSCI_*``)."""

    model_config = SettingsConfigDict(env_prefix="NEXUS_PLATNOSCI_", extra="ignore")

    stripe_klucz: str = ""
    stripe_klucz_plik: Path | None = None
    webhook_sekret: str = ""
    webhook_sekret_plik: Path | None = None
    ceny: str = ""
    kwoty: str = ""
    waluta: str = "pln"
    api_url: str = API_URL
    wersja_api: str = ""
    timeout_s: int = 20
    adres_powrotu: str = ""

    @field_validator("stripe_klucz_plik", "webhook_sekret_plik", mode="before")
    @classmethod
    def _pusta_sciezka_to_brak(cls, wartosc: object) -> object:
        """Pusta zmienna znaczy „nie ma pliku”, a nie „plik o pustej nazwie”.

        Tak wyłącza się sprzedaż w środowisku próbnym: `NEXUS_PLATNOSCI_STRIPE_KLUCZ_PLIK=`
        w pliku etapu ma przykryć wartość z `.env`. Bez tego powstawała ścieżka `Path("")`,
        odczyt kończył się błędem i ostrzeżeniem w dzienniku przy każdym pytaniu o cennik.
        """
        return None if wartosc in ("", None) else wartosc

    @property
    def klucz(self) -> str:
        """Klucz tajny Stripe (pusty = sprzedaż nieskonfigurowana)."""
        return _wczytaj_sekret(self.stripe_klucz, self.stripe_klucz_plik)

    @property
    def sekret_webhooka(self) -> str:
        """Sekret podpisu webhooka (pusty = webhook odrzuca wszystkie żądania)."""
        return _wczytaj_sekret(self.webhook_sekret, self.webhook_sekret_plik)

    @property
    def cennik(self) -> dict[str, str]:
        """Mapa ``plan:okres`` i ``pakiet:kod`` → identyfikator ceny Stripe."""
        return _mapa(self.ceny)

    @property
    def kwoty_groszy(self) -> dict[str, int]:
        """Mapa ``plan:okres`` → kwota w groszach (wartości niepoprawne pomijane)."""
        wynik: dict[str, int] = {}
        for klucz, wartosc in _mapa(self.kwoty).items():
            if wartosc.isdigit():
                wynik[klucz] = int(wartosc)
            else:
                logger.warning("Pominięto kwotę %r dla %r: oczekiwano liczby groszy.", wartosc, klucz)
        return wynik

    def cena_stripe(self, plan: str, okres: str) -> str:
        """Identyfikator ceny Stripe dla planu i okresu (pusty, gdy nie skonfigurowano)."""
        return self.cennik.get(f"{plan}:{okres}", "")

    def plan_dla_ceny(self, cena: str) -> tuple[str, str] | None:
        """Odwrotność cennika: plan i okres dla identyfikatora ceny Stripe.

        Pozycje pakietów są pomijane: pakiet nie jest subskrypcją, więc jego cena nigdy
        nie oznacza planu — inaczej jednorazowa wpłata przestawiłaby konto na plan
        o nazwie „pakiet”.
        """
        for klucz, wartosc in self.cennik.items():
            if wartosc != cena:
                continue
            plan, okres = klucz.split(":", 1)
            if plan == PRZEDROSTEK_PAKIETU:
                continue
            return plan, okres
        return None

    @property
    def skonfigurowane(self) -> bool:
        """Czy można w ogóle rozmawiać ze Stripe (jest klucz tajny)."""
        return bool(self.klucz)

    @property
    def tryb_probny(self) -> bool:
        """Czy sprzedaż chodzi na kluczu **testowym** Stripe.

        Klucz testowy (``sk_test_…``) nie przyjmuje prawdziwych pieniędzy: obsługuje karty
        próbne i służy do sprawdzenia przebiegu zakupu. Rozróżnienie ma znaczenie poza samą
        bramką płatności — np. diagnostyka pyta o licencje narzędzi wyłącznie wtedy, gdy
        produkt jest naprawdę sprzedawany, a nie gdy testerzy klikają zakupy próbne.
        """
        return self.klucz.startswith(("sk_test_", "rk_test_"))


@dataclass(frozen=True)
class AdresyPowrotu:
    """Adresy, na które Stripe odsyła użytkownika po zakupie i z portalu."""

    sukces: str
    anulowanie: str
    portal: str


def adresy_powrotu(ustawienia: UstawieniaPlatnosci, adres_publiczny: str) -> AdresyPowrotu:
    """Buduje adresy powrotu z adresu publicznego Nexusa (albo z ustawień modułu)."""
    baza = (ustawienia.adres_powrotu or adres_publiczny or "").rstrip("/")
    ekran = f"{baza}/m/platnosci"
    return AdresyPowrotu(
        sukces=f"{ekran}?zakup=udany&sesja={{CHECKOUT_SESSION_ID}}",
        anulowanie=f"{ekran}?zakup=anulowany",
        portal=f"{ekran}?powrot=rozliczenia",
    )


@lru_cache
def ustawienia_platnosci() -> UstawieniaPlatnosci:
    """Ustawienia modułu odczytane ze środowiska (jednokrotnie)."""
    return UstawieniaPlatnosci()
