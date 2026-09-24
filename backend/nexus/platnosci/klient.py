"""Warstwa dostępu do Stripe: protokół operacji i implementacja HTTP na ``httpx``.

Biblioteki ``stripe`` nie ma w środowisku projektu i moduł jej nie wymaga – Nexus
rozmawia ze Stripe przez publiczne API REST, korzystając z ``httpx`` (zależność
projektu). Protokół ``KlientStripe`` pozwala podstawić w testach atrapę bez sieci;
aby wejść na oficjalną bibliotekę, wystarczy dostarczyć inną implementację protokołu.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from nexus.platnosci.konfiguracja import UstawieniaPlatnosci
from nexus.platnosci.stany import KOMUNIKAT_SPRZEDAZ_WYLACZONA

logger = logging.getLogger(__name__)


class BladStripe(Exception):
    """Błąd zgłoszony przez Stripe albo błąd połączenia z API."""

    def __init__(self, komunikat: str, status: int = 502) -> None:
        super().__init__(komunikat)
        self.status = status


def koduj_formularz(dane: Mapping[str, Any], przedrostek: str = "") -> list[tuple[str, str]]:
    """Spłaszcza zagnieżdżone dane do zapisu formularza Stripe (``a[b][0][c]=1``)."""
    pary: list[tuple[str, str]] = []
    for klucz, wartosc in dane.items():
        nazwa = f"{przedrostek}[{klucz}]" if przedrostek else str(klucz)
        if wartosc is None:
            continue
        if isinstance(wartosc, Mapping):
            pary.extend(koduj_formularz(wartosc, nazwa))
        elif isinstance(wartosc, Sequence) and not isinstance(wartosc, str | bytes):
            for indeks, element in enumerate(wartosc):
                if isinstance(element, Mapping):
                    pary.extend(koduj_formularz(element, f"{nazwa}[{indeks}]"))
                else:
                    pary.append((f"{nazwa}[{indeks}]", str(element)))
        elif isinstance(wartosc, bool):
            pary.append((nazwa, "true" if wartosc else "false"))
        else:
            pary.append((nazwa, str(wartosc)))
    return pary


class KlientStripe(Protocol):
    """Operacje Stripe używane przez moduł sprzedaży."""

    async def utworz_klienta(self, email: str, nazwa: str, metadane: Mapping[str, str]) -> dict[str, Any]:
        """Tworzy klienta (``customer``) i zwraca jego reprezentację."""
        ...

    async def utworz_sesje_checkout(self, dane: Mapping[str, Any]) -> dict[str, Any]:
        """Tworzy sesję Checkout na podstawie danych przygotowanych przez serwer."""
        ...

    async def pobierz_sesje_checkout(self, identyfikator: str) -> dict[str, Any]:
        """Pobiera sesję Checkout (powrót po zakupie)."""
        ...

    async def utworz_sesje_portalu(
        self, klient: str, adres_powrotu: str, przeplyw: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Tworzy sesję Billing Portal dla klienta (opcjonalnie od razu w danym przepływie)."""
        ...

    async def pobierz_subskrypcje(self, identyfikator: str) -> dict[str, Any]:
        """Pobiera subskrypcję po identyfikatorze."""
        ...

    async def lista_faktur(self, klient: str, limit: int = 24) -> list[dict[str, Any]]:
        """Zwraca faktury klienta, od najnowszej."""
        ...

    async def znajdz_kod_promocyjny(self, kod: str) -> dict[str, Any] | None:
        """Szuka aktywnego kodu promocyjnego o podanym zapisie (albo ``None``), z obiektem kuponu."""
        ...

    async def zamknij(self) -> None:
        """Zwalnia zasoby połączenia."""
        ...


class KlientHttpStripe:
    """Implementacja protokołu na publicznym API REST Stripe (``httpx``)."""

    def __init__(self, ustawienia: UstawieniaPlatnosci, transport: httpx.AsyncBaseTransport | None = None):
        if not ustawienia.klucz:
            raise BladStripe(KOMUNIKAT_SPRZEDAZ_WYLACZONA, 503)
        naglowki = {"Authorization": f"Bearer {ustawienia.klucz}"}
        if ustawienia.wersja_api:
            naglowki["Stripe-Version"] = ustawienia.wersja_api
        self._klient = httpx.AsyncClient(
            base_url=ustawienia.api_url.rstrip("/"),
            headers=naglowki,
            timeout=ustawienia.timeout_s,
            transport=transport,
        )

    async def _zadanie(
        self,
        metoda: str,
        sciezka: str,
        dane: Mapping[str, Any] | None = None,
        *,
        klucz_idempotencji: str = "",
    ) -> dict[str, Any]:
        naglowki = {"Idempotency-Key": klucz_idempotencji} if klucz_idempotencji else None
        tresc = koduj_formularz(dane) if dane else None
        try:
            if metoda == "GET":
                odpowiedz = await self._klient.get(sciezka, params=tresc, headers=naglowki)
            else:
                odpowiedz = await self._klient.request(metoda, sciezka, data=tresc, headers=naglowki)
        except httpx.HTTPError as blad:
            raise BladStripe(f"Brak połączenia ze Stripe: {blad}") from blad
        try:
            wynik = odpowiedz.json()
        except ValueError as blad:
            raise BladStripe("Stripe zwrócił odpowiedź nie w formacie JSON.") from blad
        if odpowiedz.status_code >= 400:
            opis = str(wynik.get("error", {}).get("message", "")) or f"Błąd Stripe ({odpowiedz.status_code})"
            # Komunikat Stripe trafia do dziennika; użytkownik widzi tekst bez danych konta.
            logger.warning("Stripe %s %s → %s: %s", metoda, sciezka, odpowiedz.status_code, opis)
            raise BladStripe(opis, 502 if odpowiedz.status_code >= 500 else 400)
        return dict(wynik)

    async def utworz_klienta(self, email: str, nazwa: str, metadane: Mapping[str, str]) -> dict[str, Any]:
        dane: dict[str, Any] = {"metadata": dict(metadane)}
        if email:
            dane["email"] = email
        if nazwa:
            dane["name"] = nazwa
        return await self._zadanie("POST", "/customers", dane)

    async def utworz_sesje_checkout(self, dane: Mapping[str, Any]) -> dict[str, Any]:
        return await self._zadanie("POST", "/checkout/sessions", dane)

    async def pobierz_sesje_checkout(self, identyfikator: str) -> dict[str, Any]:
        return await self._zadanie("GET", f"/checkout/sessions/{identyfikator}")

    async def utworz_sesje_portalu(
        self, klient: str, adres_powrotu: str, przeplyw: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        dane: dict[str, Any] = {"customer": klient, "return_url": adres_powrotu, "locale": "pl"}
        if przeplyw:
            dane["flow_data"] = dict(przeplyw)
        return await self._zadanie("POST", "/billing_portal/sessions", dane)

    async def pobierz_subskrypcje(self, identyfikator: str) -> dict[str, Any]:
        return await self._zadanie("GET", f"/subscriptions/{identyfikator}")

    async def lista_faktur(self, klient: str, limit: int = 24) -> list[dict[str, Any]]:
        wynik = await self._zadanie("GET", "/invoices", {"customer": klient, "limit": limit})
        return [dict(pozycja) for pozycja in wynik.get("data", [])]

    async def znajdz_kod_promocyjny(self, kod: str) -> dict[str, Any] | None:
        wynik = await self._zadanie("GET", "/promotion_codes", {"code": kod, "active": True, "limit": 1})
        pozycje = wynik.get("data", [])
        if not pozycje:
            return None
        znaleziony = dict(pozycje[0])
        # Od 2025-09-30.clover kupon stoi w promotion.coupon jako sam identyfikator. Kupon
        # dociągamy osobno, bo rozwinięcie (expand) tego pola starsza wersja API odrzuca.
        promocja = znaleziony.get("promotion")
        if isinstance(promocja, dict) and isinstance(promocja.get("coupon"), str) and promocja["coupon"]:
            rabat = await self._zadanie("GET", f"/coupons/{quote(promocja['coupon'], safe='')}")
            znaleziony["promotion"] = {**promocja, "coupon": rabat}
        return znaleziony

    async def zamknij(self) -> None:
        await self._klient.aclose()
