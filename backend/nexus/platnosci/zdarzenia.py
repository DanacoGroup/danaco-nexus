"""Obsługa zdarzeń webhooka Stripe: zapis w dzienniku, idempotencja, zmiana stanu.

Kolejność jest stała: najpierw zdarzenie trafia do tabeli ``platnosci_zdarzenia``
(klucz główny to identyfikator zdarzenia Stripe), dopiero potem zmieniany jest stan
subskrypcji albo faktur. Powtórne doręczenie tego samego zdarzenia – a Stripe
ponawia doręczenia – kończy się rozpoznaniem duplikatu i odpowiedzią bez zmian.

Konto Stripe jest wspólne dla kilku produktów Danaco, więc webhook dostaje także faktury,
subskrypcje i sesje zakupu innych produktów. Zdarzenie, którego nie da się przypisać do
konta Nexusa, zostaje w dzienniku ze stanem ``pominiete`` i niczego nie zmienia.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from nexus.db import ADMIN_OWNER, Database, utcnow
from nexus.platnosci import kredyty
from nexus.platnosci.konfiguracja import UstawieniaPlatnosci
from nexus.platnosci.model import STATUS_ANULOWANA, STATUS_PROBNA, Subskrypcja, ZdarzenieStripe
from nexus.platnosci.pakiety import pakiet
from nexus.platnosci.plany import PLAN_DOMYSLNY, pozycja_katalogu
from nexus.platnosci.uslugi import (
    _identyfikator,
    nazwa_uzytkownika,
    subskrypcja_uzytkownika,
    zapisz_fakture,
    zapisz_subskrypcje,
)

logger = logging.getLogger(__name__)

OBSLUGIWANE = (
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
)


def _wskazania_konta(obiekt: dict[str, Any]) -> list[str]:
    """Oznaczenia konta, które kasa Nexusa zapisuje w obiektach Stripe, w kolejności ważności.

    Sesja zakupu i subskrypcja niosą ``metadata.uzytkownik``, sesja także
    ``client_reference_id``. Faktury subskrypcji nie mają metadanych konta: Stripe kopiuje
    metadane subskrypcji do ``subscription_details`` (API do 2025-02-24) albo
    ``parent.subscription_details`` (od 2025-03-31).
    """
    szczegoly = (obiekt.get("subscription_details"), (obiekt.get("parent") or {}).get("subscription_details"))
    kandydaci = [
        (obiekt.get("metadata") or {}).get("uzytkownik"),
        obiekt.get("client_reference_id"),
        *(((wpis or {}).get("metadata") or {}).get("uzytkownik") for wpis in szczegoly),
    ]
    return [str(kandydat).strip() for kandydat in kandydaci if kandydat and str(kandydat).strip()]


async def _uzytkownik(database: Database, obiekt: dict[str, Any]) -> str:
    """Konto Nexusa, którego dotyczy obiekt Stripe; pusty napis, gdy obiekt nie jest Nexusa.

    Rozstrzyga oznaczenie konta z metadanych albo klient Stripe zapisany w
    ``platnosci_subskrypcje`` (kasa zakłada go przed każdą sesją zakupu). Oznaczenie, które
    nie wskazuje konta Nexusa, jest pomijane: pole ``client_reference_id`` ustawiają też inne
    produkty na wspólnym koncie Stripe. Zdarzenia bez takiego powiązania nie przypisujemy
    właścicielowi instalacji — dostałby faktury i kredyty cudzych klientów.
    """
    for nazwa in _wskazania_konta(obiekt):
        if await _wlasciciel_konta(database, nazwa) is not None:
            return nazwa
    klient_id = _identyfikator(obiekt.get("customer"))
    if not klient_id:
        return ""
    async with database.session() as session:
        rekord = await session.scalar(select(Subskrypcja).where(Subskrypcja.stripe_customer_id == klient_id))
    if rekord is None or await _wlasciciel_konta(database, rekord.uzytkownik) is None:
        return ""
    return rekord.uzytkownik


def _uuid_konta(nazwa: str) -> uuid.UUID | None:
    """Identyfikator konta w zapisie kasy Nexusa (``str(uuid)``, z łącznikami).

    ``uuid.UUID`` przyjmuje też 32 znaki szesnastkowe bez łączników, a w tej postaci inne
    produkty na wspólnym koncie Stripe zapisują własne identyfikatory użytkowników.
    """
    try:
        wartosc = uuid.UUID(nazwa)
    except ValueError:
        return None
    return wartosc if str(wartosc) == nazwa else None


async def _wlasciciel_konta(database: Database, uzytkownik: str) -> uuid.UUID | None:
    """Konto Nexusa, do którego należą kredyty; ``None``, gdy oznaczenie go nie wskazuje.

    Uznawane oznaczenia: identyfikator konta, adres konta portalu i login administratora
    tej instalacji (subskrypcje sprzed kluczowania kontem).
    """
    from nexus.models.portal import PortalUser

    nazwa = (uzytkownik or "").strip().lower()
    if not nazwa:
        return None
    konto = _uuid_konta(nazwa)
    if konto is not None:
        # Sama postać identyfikatora nie wystarcza: inne produkty na wspólnym koncie Stripe
        # też zapisują w ``client_reference_id`` identyfikatory UUID. Konto musi istnieć.
        if konto == ADMIN_OWNER:
            return konto
        async with database.session() as session:
            istnieje = await session.get(PortalUser, konto)
        return konto if istnieje is not None else None
    if "@" in nazwa:
        async with database.session() as session:
            user = await session.scalar(select(PortalUser).where(PortalUser.email == nazwa))
        return user.id if user is not None else None
    if nazwa == (await nazwa_uzytkownika(database)).strip().lower():
        return ADMIN_OWNER
    return None


def _ceny_obiektu(obiekt: dict[str, Any]) -> set[str]:
    """Identyfikatory cen z pozycji subskrypcji albo faktury (starszy i nowszy kształt API)."""
    ceny: set[str] = set()
    for pole in ("items", "lines"):
        for wpis in ((obiekt.get(pole) or {}).get("data")) or []:
            linia = wpis or {}
            ceny.add(_identyfikator(linia.get("price")))
            ceny.add(_identyfikator(((linia.get("pricing") or {}).get("price_details") or {}).get("price")))
    ceny.discard("")
    return ceny


POMINIETE_OBCE = "Obce zdarzenie: brak konta Nexusa w metadanych i nieznany klient Stripe."
POMINIETE_CENA_NEXUSA = "Cena z cennika Nexusa, ale bez konta Nexusa w metadanych ani znanego klienta Stripe."


def _powod_pominiecia(ustawienia: UstawieniaPlatnosci, obiekt: dict[str, Any]) -> str:
    """Opis pominiętego zdarzenia bez konta Nexusa do dziennika zdarzeń.

    Cena z cennika Nexusa świadczy, że to sprzedaż Nexusa, ale nie mówi, czyja — takie
    zdarzenie (np. subskrypcja założona ręcznie w panelu Stripe) wymaga wyjaśnienia.
    """
    if _ceny_obiektu(obiekt) & set(ustawienia.cennik.values()):
        return POMINIETE_CENA_NEXUSA
    return POMINIETE_OBCE


async def _dopisz_pakiet(
    database: Database, uzytkownik: str, obiekt: dict[str, Any], metadane: dict[str, Any]
) -> None:
    """Dopisuje kredyty z opłaconego pakietu.

    Warunkiem jest potwierdzona wpłata: sesja Checkout w trybie ``payment`` bywa zamknięta
    także wtedy, gdy płatność jeszcze się nie rozliczyła.
    """
    if str(obiekt.get("payment_status") or "") not in ("paid", "no_payment_required"):
        logger.info("Pakiet kredytów bez potwierdzonej wpłaty – kredytów nie dopisuję.")
        return
    konto = await _wlasciciel_konta(database, uzytkownik)
    if konto is None:
        logger.warning("Nie rozpoznano konta %r przy zakupie pakietu — kredyty nie dopisane.", uzytkownik)
        return
    # Doładowanie kwotą: liczbę kredytów wylicza serwer z wpłaconej sumy, a nie z katalogu
    # pakietów. Metadane niosą już wynik przeliczenia, ale liczymy go tu ponownie z kwoty —
    # metadane sesji Checkout pochodzą z naszego żądania, jednak to wpłata jest faktem.
    if str(metadane.get("doladowanie") or "") == "1":
        kwota_gr = int(str(obiekt.get("amount_total") or metadane.get("kwota_gr") or "0") or 0)
        ile = kredyty.kredyty_za_kwote(kwota_gr)
        nazwa = "Przedłużenie dostępu"
        if ile <= 0:
            logger.warning("Doładowanie na %s gr nie daje kredytów — nic nie dopisuję.", kwota_gr)
            return
        saldo = await kredyty.przydziel(database, konto, ile, "zakup", nazwa)
        logger.info("Doładowanie %s gr → %s kredytów na koncie %s; saldo: %s", kwota_gr, ile, konto, saldo)
        return

    pozycja = pakiet(str(metadane.get("pakiet") or ""))
    ile = pozycja.kredyty if pozycja else int(str(metadane.get("kredyty") or "0") or 0)
    if ile <= 0:
        logger.warning("Pakiet %r nie ma liczby kredytów — nic nie dopisuję.", metadane.get("pakiet"))
        return
    nazwa = pozycja.nazwa if pozycja else "Pakiet kredytów"
    saldo = await kredyty.przydziel(database, konto, ile, "zakup", nazwa)
    logger.info("Dopisano %s kredytów (%s) koncie %s; saldo: %s", ile, nazwa, konto, saldo)


async def _przydziel_kredyty_planu(
    database: Database, uzytkownik: str, plan_kod: str, powod: str, probny: bool = False
) -> None:
    """Przydział kredytów po uruchomieniu albo odnowieniu subskrypcji.

    Okres próbny dostaje zakres próbny i tylko wtedy, gdy konto nie miało jeszcze żadnego
    przydziału (także startowego przy pierwszym zleceniu) — inaczej zakres by się dublował.
    """
    konto = await _wlasciciel_konta(database, uzytkownik)
    if konto is None:
        logger.warning("Nie rozpoznano konta %r — kredyty planu nie przydzielone.", uzytkownik)
        return
    if probny:
        saldo = await kredyty.pierwszy_przydzial(database, konto, plan_kod, powod)
    else:
        saldo = await kredyty.przydziel_z_planu(database, konto, plan_kod, powod)
    logger.info("Przydział kredytów planu %s dla konta %s; saldo: %s", plan_kod, konto, saldo)


def _kwota_faktury(obiekt: dict[str, Any]) -> int:
    """Kwota faktury w groszach — największa z zapłaconej, łącznej i należnej."""
    pola = (obiekt.get(pole) for pole in ("amount_paid", "total", "amount_due"))
    return max((int(wartosc) for wartosc in pola if isinstance(wartosc, int | float)), default=0)


def _plan_z_faktury(ustawienia: UstawieniaPlatnosci, obiekt: dict[str, Any]) -> str:
    """Plan opłacony fakturą: z ceny pozycji, a bez niej z metadanych subskrypcji na fakturze.

    Pusty napis, gdy faktura planu nie wskazuje. Cena pozycji leży w ``price`` albo
    (nowsze API Stripe) w ``pricing.price_details.price``; metadane subskrypcji Stripe
    kopiuje do ``subscription_details`` albo ``parent.subscription_details``.
    """
    for wpis in ((obiekt.get("lines") or {}).get("data")) or []:
        linia = wpis or {}
        kwota = linia.get("amount")
        if isinstance(kwota, int | float) and kwota < 0:
            # Zwrot za niewykorzystany czas poprzedniego planu przy zmianie planu.
            continue
        cena = _identyfikator(linia.get("price")) or _identyfikator(
            ((linia.get("pricing") or {}).get("price_details") or {}).get("price")
        )
        rozpoznany = ustawienia.plan_dla_ceny(cena) if cena else None
        if rozpoznany:
            return rozpoznany[0]
    rodzic = obiekt.get("parent") or {}
    for szczegoly in (obiekt.get("subscription_details"), rodzic.get("subscription_details")):
        plan = str(((szczegoly or {}).get("metadata") or {}).get("plan") or "")
        if pozycja_katalogu(plan) is not None:
            return plan
    return ""


def _subskrypcja_faktury(obiekt: dict[str, Any]) -> str:
    """Identyfikator subskrypcji, z której wystawiono fakturę.

    Do wersji API 2025-02-24 Stripe podawał go w ``invoice.subscription``; od wersji
    2025-03-31 („basil”) pole zniknęło, a identyfikator stoi w
    ``invoice.parent.subscription_details.subscription``. Konto Stripe Nexusa pracuje na
    wersji nowszej (webhook dostaje zdarzenia w wersji konta), więc bez drugiej ścieżki
    żadna opłacona faktura subskrypcji nie dawała przydziału.
    """
    bezposrednio = obiekt.get("subscription")
    if bezposrednio:
        return bezposrednio if isinstance(bezposrednio, str) else str((bezposrednio or {}).get("id", ""))
    szczegoly = (obiekt.get("parent") or {}).get("subscription_details") or {}
    wartosc = szczegoly.get("subscription")
    if isinstance(wartosc, dict):
        return str(wartosc.get("id", ""))
    return str(wartosc or "")


def _otwiera_okres_probny(obiekt: dict[str, Any], rekord: Subskrypcja, plan_kod: str) -> bool:
    """Czy opłacona faktura na 0 zł otwiera okres próbny planu ``plan_kod``.

    Stripe wystawia ją z ``billing_reason`` = ``subscription_create``, a kolejność zdarzeń
    nie jest gwarantowana — o okresie próbnym rozstrzyga więc sama faktura, a stan
    subskrypcji w bazie tylko wtedy, gdy faktura nie podaje powodu. Faktura
    ``subscription_cycle`` zaczyna okres płatny także przy pełnym rabacie.
    """
    pozycja = pozycja_katalogu(plan_kod)
    if pozycja is None or pozycja.okres_probny_dni <= 0 or _kwota_faktury(obiekt) > 0:
        return False
    powod = str(obiekt.get("billing_reason") or "")
    if powod == "subscription_cycle":
        return False
    return powod == "subscription_create" or rekord.status == STATUS_PROBNA


async def _checkout_zakonczony(
    database: Database, ustawienia: UstawieniaPlatnosci, uzytkownik: str, obiekt: dict[str, Any]
) -> None:
    """Powiązanie konta z klientem Stripe po opłaceniu sesji Checkout.

    Pełny stan subskrypcji przynosi zdarzenie ``customer.subscription.created``;
    tutaj zapisywane są wyłącznie powiązania i wybrany plan.
    """
    metadane = obiekt.get("metadata") or {}
    # Jednorazowy zakup — pakiet albo doładowanie kwotą — nie zakłada ani nie zmienia
    # subskrypcji: dopisuje kredyty i na tym kończy.
    if metadane.get("pakiet") or metadane.get("doladowanie"):
        await _dopisz_pakiet(database, uzytkownik, obiekt, metadane)
        return
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    async with database.session() as session:
        rekord.stripe_customer_id = _identyfikator(obiekt.get("customer")) or rekord.stripe_customer_id
        rekord.stripe_subscription_id = (
            _identyfikator(obiekt.get("subscription")) or rekord.stripe_subscription_id
        )
        rekord.plan_kod = str(metadane.get("plan") or rekord.plan_kod or PLAN_DOMYSLNY)
        rekord.okres = str(metadane.get("okres") or rekord.okres)
        rekord.updated_at = utcnow()
        await session.merge(rekord)


async def _subskrypcja_zmieniona(
    database: Database, ustawienia: UstawieniaPlatnosci, uzytkownik: str, obiekt: dict[str, Any]
) -> None:
    """Zapis nowego stanu subskrypcji (utworzenie, zmiana planu, rezygnacja)."""
    await zapisz_subskrypcje(database, ustawienia, uzytkownik, obiekt)


async def _subskrypcja_usunieta(
    database: Database, ustawienia: UstawieniaPlatnosci, uzytkownik: str, obiekt: dict[str, Any]
) -> None:
    """Zakończenie subskrypcji – konto wraca do planu bezpłatnego."""
    await _subskrypcja_zmieniona(database, ustawienia, uzytkownik, {**obiekt, "status": "canceled"})
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    if rekord.status != STATUS_ANULOWANA:
        async with database.session() as session:
            rekord.status = STATUS_ANULOWANA
            rekord.plan_kod = PLAN_DOMYSLNY
            rekord.okres = ""
            rekord.updated_at = utcnow()
            await session.merge(rekord)


async def _faktura(
    database: Database, ustawienia: UstawieniaPlatnosci, uzytkownik: str, obiekt: dict[str, Any]
) -> None:
    """Zapis faktury i — przy opłaconej fakturze subskrypcji — przydział kredytów okresu.

    Przydział wiążemy z opłaconą fakturą, a nie ze zmianą subskrypcji: faktura przychodzi
    raz na okres rozliczeniowy i tylko wtedy, gdy pieniądze naprawdę wpłynęły. Faktura
    otwierająca okres próbny opiewa na zero i daje zakres próbny z katalogu
    (``probny_kredyty``); pełny przydział planu wchodzi z pierwszą fakturą okresu płatnego.
    """
    await zapisz_fakture(database, uzytkownik, obiekt)
    if str(obiekt.get("status") or "") != "paid" or not _subskrypcja_faktury(obiekt):
        return
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    # Rekord w bazie jest tylko rezerwą: faktura bywa doręczona przed zdarzeniem subskrypcji,
    # a do tego czasu rekord ma plan domyślny, więc zakup Pro dałby przydział Osobistego.
    plan_kod = _plan_z_faktury(ustawienia, obiekt) or rekord.plan_kod or PLAN_DOMYSLNY
    if _otwiera_okres_probny(obiekt, rekord, plan_kod):
        await _przydziel_kredyty_planu(database, uzytkownik, plan_kod, "okres-probny", probny=True)
        return
    await _przydziel_kredyty_planu(database, uzytkownik, plan_kod, "odnowienie")


OBSLUGA = {
    "checkout.session.completed": _checkout_zakonczony,
    "customer.subscription.created": _subskrypcja_zmieniona,
    "customer.subscription.updated": _subskrypcja_zmieniona,
    "customer.subscription.deleted": _subskrypcja_usunieta,
    "invoice.paid": _faktura,
    "invoice.payment_failed": _faktura,
}


async def _zapisz_zdarzenie(database: Database, zdarzenie: dict[str, Any]) -> bool:
    """Zapisuje zdarzenie w dzienniku. ``False`` = zdarzenie już było (duplikat)."""
    try:
        async with database.session() as session:
            session.add(
                ZdarzenieStripe(
                    id=str(zdarzenie.get("id", ""))[:64],
                    typ=str(zdarzenie.get("type", ""))[:60],
                    ladunek=zdarzenie,
                )
            )
    except IntegrityError:
        return False
    return True


async def _oznacz(
    database: Database, identyfikator: str, status: str, blad: str = "", bez_ladunku: bool = False
) -> None:
    """Zamyka wpis w dzienniku zdarzeń (stan przetwarzania).

    ``bez_ladunku`` czyści zapisany ładunek: zdarzenie innego produktu na wspólnym koncie
    Stripe niesie dane jego klientów (adresy, kwoty), których Nexus nie potrzebuje i nie
    powinien przechowywać. Do rozpoznania duplikatu wystarczą identyfikator i typ.
    """
    async with database.session() as session:
        rekord = await session.get(ZdarzenieStripe, identyfikator)
        if rekord is not None:
            rekord.status = status
            rekord.blad = blad[:2000]
            rekord.przetworzone_at = utcnow()
            if bez_ladunku:
                rekord.ladunek = {}


async def wlasciciel_zdarzenia(database: Database, zdarzenie: dict[str, Any]) -> uuid.UUID | None:
    """Konto, którego dotyczy zdarzenie Stripe (do działań po zmianie planu)."""
    obiekt = (zdarzenie.get("data") or {}).get("object") or {}
    return await _wlasciciel_konta(database, await _uzytkownik(database, dict(obiekt)))


async def przyjmij_zdarzenie(
    database: Database, ustawienia: UstawieniaPlatnosci, zdarzenie: dict[str, Any]
) -> dict[str, Any]:
    """Przetwarza zdarzenie webhooka idempotentnie i zwraca odpowiedź dla Stripe."""
    identyfikator = str(zdarzenie.get("id", ""))[:64]
    typ = str(zdarzenie.get("type", ""))
    if not await _zapisz_zdarzenie(database, zdarzenie):
        return {"otrzymano": True, "duplikat": True, "typ": typ}
    obsluga = OBSLUGA.get(typ)
    if obsluga is None:
        await _oznacz(database, identyfikator, "pominiete", bez_ladunku=True)
        return {"otrzymano": True, "obsluzone": False, "typ": typ}
    obiekt = dict((zdarzenie.get("data") or {}).get("object") or {})
    try:
        uzytkownik = await _uzytkownik(database, obiekt)
        if not uzytkownik:
            powod = _powod_pominiecia(ustawienia, obiekt)
            # Obcych zdarzeń na wspólnym koncie jest wiele; ostrzeżenie tylko przy cenie Nexusa.
            poziom = logging.INFO if powod == POMINIETE_OBCE else logging.WARNING
            logger.log(poziom, "Zdarzenie Stripe %s (%s) pominięte: %s", identyfikator, typ, powod)
            await _oznacz(database, identyfikator, "pominiete", powod, bez_ladunku=powod == POMINIETE_OBCE)
            return {"otrzymano": True, "obsluzone": False, "typ": typ}
        await obsluga(database, ustawienia, uzytkownik, obiekt)
    except Exception as blad:
        logger.exception("Nie udało się przetworzyć zdarzenia Stripe %s (%s)", identyfikator, typ)
        await _oznacz(database, identyfikator, "blad", str(blad))
        raise
    await _oznacz(database, identyfikator, "przetworzone")
    return {"otrzymano": True, "obsluzone": True, "typ": typ}
