"""Obsługa zdarzeń webhooka Stripe: zapis w dzienniku, idempotencja, zmiana stanu.

Kolejność jest stała: najpierw zdarzenie trafia do tabeli ``platnosci_zdarzenia``
(klucz główny to identyfikator zdarzenia Stripe), dopiero potem zmieniany jest stan
subskrypcji albo faktur. Powtórne doręczenie tego samego zdarzenia – a Stripe
ponawia doręczenia – kończy się rozpoznaniem duplikatu i odpowiedzią bez zmian.
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
from nexus.platnosci.model import STATUS_ANULOWANA, Subskrypcja, ZdarzenieStripe
from nexus.platnosci.pakiety import pakiet
from nexus.platnosci.plany import PLAN_DOMYSLNY
from nexus.platnosci.uslugi import (
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


async def _uzytkownik(database: Database, obiekt: dict[str, Any]) -> str:
    """Właściciel zdarzenia: z metadanych, z powiązanego klienta Stripe albo właściciel instalacji."""
    metadane = obiekt.get("metadata") or {}
    nazwa = str(metadane.get("uzytkownik") or obiekt.get("client_reference_id") or "")
    if nazwa:
        return nazwa
    klient = obiekt.get("customer")
    klient_id = klient if isinstance(klient, str) else str((klient or {}).get("id", ""))
    if klient_id:
        async with database.session() as session:
            rekord = await session.scalar(
                select(Subskrypcja).where(Subskrypcja.stripe_customer_id == klient_id)
            )
        if rekord is not None:
            return rekord.uzytkownik
    return await nazwa_uzytkownika(database)


async def _wlasciciel_konta(database: Database, uzytkownik: str) -> uuid.UUID | None:
    """Konto, do którego należą kredyty: konto portalu albo administrator instalacji."""
    from nexus.models.portal import PortalUser

    nazwa = (uzytkownik or "").strip().lower()
    if not nazwa:
        return None
    try:
        return uuid.UUID(nazwa)
    except ValueError:
        pass
    if "@" in nazwa:
        async with database.session() as session:
            user = await session.scalar(select(PortalUser).where(PortalUser.email == nazwa))
        return user.id if user is not None else None
    # Login bez „@” to administrator instalacji.
    return ADMIN_OWNER


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


async def _przydziel_kredyty_planu(database: Database, uzytkownik: str, plan_kod: str, powod: str) -> None:
    """Przydział kredytów po uruchomieniu albo odnowieniu subskrypcji."""
    konto = await _wlasciciel_konta(database, uzytkownik)
    if konto is None:
        logger.warning("Nie rozpoznano konta %r — kredyty planu nie przydzielone.", uzytkownik)
        return
    saldo = await kredyty.przydziel_z_planu(database, konto, plan_kod, powod)
    logger.info("Przydział kredytów planu %s dla konta %s; saldo: %s", plan_kod, konto, saldo)


async def _checkout_zakonczony(
    database: Database, ustawienia: UstawieniaPlatnosci, obiekt: dict[str, Any]
) -> None:
    """Powiązanie konta z klientem Stripe po opłaceniu sesji Checkout.

    Pełny stan subskrypcji przynosi zdarzenie ``customer.subscription.created``;
    tutaj zapisywane są wyłącznie powiązania i wybrany plan.
    """
    uzytkownik = await _uzytkownik(database, obiekt)
    metadane = obiekt.get("metadata") or {}
    # Jednorazowy zakup — pakiet albo doładowanie kwotą — nie zakłada ani nie zmienia
    # subskrypcji: dopisuje kredyty i na tym kończy.
    if metadane.get("pakiet") or metadane.get("doladowanie"):
        await _dopisz_pakiet(database, uzytkownik, obiekt, metadane)
        return
    klient = obiekt.get("customer")
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    async with database.session() as session:
        rekord.stripe_customer_id = (
            klient if isinstance(klient, str) else str((klient or {}).get("id", ""))
        ) or rekord.stripe_customer_id
        subskrypcja = obiekt.get("subscription")
        rekord.stripe_subscription_id = (
            subskrypcja if isinstance(subskrypcja, str) else str((subskrypcja or {}).get("id", ""))
        ) or rekord.stripe_subscription_id
        rekord.plan_kod = str(metadane.get("plan") or rekord.plan_kod or PLAN_DOMYSLNY)
        rekord.okres = str(metadane.get("okres") or rekord.okres)
        rekord.updated_at = utcnow()
        await session.merge(rekord)


async def _subskrypcja_zmieniona(
    database: Database, ustawienia: UstawieniaPlatnosci, obiekt: dict[str, Any]
) -> None:
    """Zapis nowego stanu subskrypcji (utworzenie, zmiana planu, rezygnacja)."""
    uzytkownik = await _uzytkownik(database, obiekt)
    await zapisz_subskrypcje(database, ustawienia, uzytkownik, obiekt)


async def _subskrypcja_usunieta(
    database: Database, ustawienia: UstawieniaPlatnosci, obiekt: dict[str, Any]
) -> None:
    """Zakończenie subskrypcji – konto wraca do planu bezpłatnego."""
    await _subskrypcja_zmieniona(database, ustawienia, {**obiekt, "status": "canceled"})
    uzytkownik = await _uzytkownik(database, obiekt)
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    if rekord.status != STATUS_ANULOWANA:
        async with database.session() as session:
            rekord.status = STATUS_ANULOWANA
            rekord.plan_kod = PLAN_DOMYSLNY
            rekord.okres = ""
            rekord.updated_at = utcnow()
            await session.merge(rekord)


async def _faktura(database: Database, ustawienia: UstawieniaPlatnosci, obiekt: dict[str, Any]) -> None:
    """Zapis faktury i — przy opłaconej fakturze subskrypcji — przydział kredytów okresu.

    Przydział wiążemy z opłaconą fakturą, a nie ze zmianą subskrypcji: faktura przychodzi
    raz na okres rozliczeniowy i tylko wtedy, gdy pieniądze naprawdę wpłynęły. Faktura
    z okresu próbnego opiewa na zero i również daje przydział — po to jest okres próbny.
    """
    uzytkownik = await _uzytkownik(database, obiekt)
    await zapisz_fakture(database, uzytkownik, obiekt)
    if str(obiekt.get("status") or "") != "paid" or not obiekt.get("subscription"):
        return
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    await _przydziel_kredyty_planu(database, uzytkownik, rekord.plan_kod or PLAN_DOMYSLNY, "odnowienie")


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


async def _oznacz(database: Database, identyfikator: str, status: str, blad: str = "") -> None:
    """Zamyka wpis w dzienniku zdarzeń (stan przetwarzania)."""
    async with database.session() as session:
        rekord = await session.get(ZdarzenieStripe, identyfikator)
        if rekord is not None:
            rekord.status = status
            rekord.blad = blad[:2000]
            rekord.przetworzone_at = utcnow()


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
        await _oznacz(database, identyfikator, "pominiete")
        return {"otrzymano": True, "obsluzone": False, "typ": typ}
    obiekt = (zdarzenie.get("data") or {}).get("object") or {}
    try:
        await obsluga(database, ustawienia, dict(obiekt))
    except Exception as blad:
        logger.exception("Nie udało się przetworzyć zdarzenia Stripe %s (%s)", identyfikator, typ)
        await _oznacz(database, identyfikator, "blad", str(blad))
        raise
    await _oznacz(database, identyfikator, "przetworzone")
    return {"otrzymano": True, "obsluzone": True, "typ": typ}
