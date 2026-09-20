"""Operacje sprzedaży: zakup planu, portal rozliczeniowy, subskrypcja, faktury i kupony.

Cała arytmetyka cen dzieje się tutaj – klient przekazuje wyłącznie kod planu i okres
rozliczeniowy, a identyfikator ceny Stripe bierze się z konfiguracji środowiska.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from nexus.api.auth import DEFAULT_USERNAME, USERNAME_KEY
from nexus.db import Database, Setting, utcnow
from nexus.platnosci.klient import BladStripe, KlientStripe
from nexus.platnosci.konfiguracja import OKRESY, AdresyPowrotu, UstawieniaPlatnosci
from nexus.platnosci.model import (
    STATUS_AKTYWNA,
    STATUS_ANULOWANA,
    STATUS_BRAK,
    STATUS_NIEPELNA,
    STATUS_PROBNA,
    STATUS_ZALEGLA,
    STATUSY_UPRAWNIAJACE,
    Faktura,
    Kupon,
    Subskrypcja,
)
from nexus.platnosci.pakiety import pakiet
from nexus.platnosci.plany import PLAN_DOMYSLNY, do_kupienia, pozycja_katalogu
from nexus.platnosci.stany import (
    KOMUNIKATY_KUPONU,
    STATUSY_FAKTURY_DO_ZAPLATY,
    zapis_daty,
)

# Tryby rozpoczęcia zakupu: nowa sesja Checkout albo zmiana planu w portalu.
TRYB_CHECKOUT = "checkout"
TRYB_PORTAL = "portal"

# Stany subskrypcji Stripe przełożone na stany Nexusa.
STATUSY_STRIPE = {
    "trialing": STATUS_PROBNA,
    "active": STATUS_AKTYWNA,
    "past_due": STATUS_ZALEGLA,
    "unpaid": STATUS_ZALEGLA,
    "canceled": STATUS_ANULOWANA,
    "incomplete": STATUS_NIEPELNA,
    "incomplete_expired": STATUS_ANULOWANA,
    "paused": STATUS_ANULOWANA,
}


def czas(wartosc: Any) -> datetime | None:
    """Znacznik czasu Stripe (sekundy uniksowe) jako data ze strefą UTC."""
    if isinstance(wartosc, int | float) and wartosc > 0:
        return datetime.fromtimestamp(int(wartosc), UTC)
    return None


def _identyfikator(wartosc: Any) -> str:
    """Identyfikator obiektu Stripe podanego wprost albo rozwiniętego do słownika."""
    if isinstance(wartosc, str):
        return wartosc
    if isinstance(wartosc, dict):
        return str(wartosc.get("id", ""))
    return ""


def _pozycja_subskrypcji(dane: dict[str, Any]) -> str:
    """Identyfikator pierwszej pozycji subskrypcji (Stripe wymaga go przy zmianie planu)."""
    pozycje = (dane.get("items") or {}).get("data") or []
    return _identyfikator(pozycje[0]) if pozycje else ""


async def nazwa_uzytkownika(database: Database) -> str:
    """Login właściciela instalacji – klucz subskrypcji w bazie."""
    async with database.session() as session:
        rekord = await session.get(Setting, USERNAME_KEY)
    return rekord.value if rekord else DEFAULT_USERNAME


async def subskrypcja_uzytkownika(database: Database, uzytkownik: str) -> Subskrypcja:
    """Zwraca subskrypcję użytkownika; przy pierwszym wywołaniu zakłada plan bezpłatny."""
    async with database.session() as session:
        rekord = await session.scalar(select(Subskrypcja).where(Subskrypcja.uzytkownik == uzytkownik))
        if rekord is None:
            rekord = Subskrypcja(uzytkownik=uzytkownik, plan_kod=PLAN_DOMYSLNY, status=STATUS_BRAK)
            session.add(rekord)
    return rekord


async def _zapisz(database: Database, rekord: Subskrypcja) -> Subskrypcja:
    """Zapisuje zmieniony rekord subskrypcji (obiekt odłączony od sesji)."""
    async with database.session() as session:
        rekord.updated_at = utcnow()
        await session.merge(rekord)
    return rekord


async def zapewnij_klienta(
    database: Database, klient: KlientStripe, uzytkownik: str, email: str = ""
) -> Subskrypcja:
    """Zapewnia istnienie klienta Stripe powiązanego z użytkownikiem."""
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    if rekord.stripe_customer_id:
        return rekord
    utworzony = await klient.utworz_klienta(email, uzytkownik, {"uzytkownik": uzytkownik})
    rekord.stripe_customer_id = _identyfikator(utworzony)
    if not rekord.stripe_customer_id:
        raise BladStripe("Stripe nie zwrócił identyfikatora klienta.")
    return await _zapisz(database, rekord)


def powod_odrzucenia_kuponu(kod_promocyjny: dict[str, Any], teraz: datetime | None = None) -> str:
    """Powód, dla którego kodu rabatowego nie można użyć (pusty = kod jest ważny)."""
    rabat = kod_promocyjny.get("coupon") or {}
    if not kod_promocyjny.get("active", True) or not rabat.get("valid", True):
        return "nieaktywny"
    wygasa = czas(kod_promocyjny.get("expires_at"))
    if wygasa is not None and wygasa < (teraz or utcnow()):
        return "wygasl"
    limit = kod_promocyjny.get("max_redemptions")
    if isinstance(limit, int) and limit > 0 and int(kod_promocyjny.get("times_redeemed") or 0) >= limit:
        return "wyczerpany"
    return ""


async def sprawdz_kupon(database: Database, klient: KlientStripe, kod: str) -> Kupon:
    """Sprawdza kod rabatowy w Stripe i zapisuje jego opis w bazie."""
    kod = kod.strip()
    if not kod:
        raise BladStripe("Podaj kod rabatowy albo kup plan bez kodu.", 400)
    znaleziony = await klient.znajdz_kod_promocyjny(kod)
    if not znaleziony:
        raise BladStripe(KOMUNIKATY_KUPONU["nieznany"], 400)
    powod = powod_odrzucenia_kuponu(znaleziony)
    if powod:
        wygasa = zapis_daty(czas(znaleziony.get("expires_at")))
        koniec = f" Kod był ważny do {wygasa}." if powod == "wygasl" and wygasa else ""
        raise BladStripe(f"{KOMUNIKATY_KUPONU[powod]}{koniec}", 400)
    rabat = znaleziony.get("coupon") or {}
    procent = rabat.get("percent_off") or 0
    kwota = rabat.get("amount_off") or 0
    async with database.session() as session:
        rekord = await session.scalar(select(Kupon).where(Kupon.kod == kod))
        if rekord is None:
            rekord = Kupon(kod=kod)
            session.add(rekord)
        rekord.stripe_promotion_id = _identyfikator(znaleziony)
        rekord.stripe_coupon_id = _identyfikator(rabat)
        rekord.rabat_procent = int(procent)
        rekord.rabat_gr = int(kwota)
        rekord.waluta = str(rabat.get("currency") or "pln")[:3]
        rekord.opis = str(rabat.get("name") or "")[:200]
        rekord.aktywny = bool(znaleziony.get("active", True))
        rekord.wygasa_at = czas(znaleziony.get("expires_at"))
        rekord.sprawdzony_at = utcnow()
    return rekord


@dataclass(frozen=True)
class Zakup:
    """Wynik rozpoczęcia zakupu: adres do przejścia i tryb, w jakim się to dzieje."""

    adres: str
    tryb: str
    plan: str
    okres: str


def przeplyw_zmiany_planu(
    subskrypcja: str, pozycja: str, cena: str, adresy: AdresyPowrotu, promocja: str = ""
) -> dict[str, Any]:
    """Przepływ portalu z wybranym planem: Stripe pokazuje od razu potwierdzenie zmiany.

    Bez pozycji i ceny portal otwierałby ogólną listę planów z panelu Stripe, więc wybór
    z cennika Nexusa trzeba by powtórzyć. Kod rabatowy idzie tą samą drogą co w Checkoucie.
    """
    zmiana: dict[str, Any] = {
        "subscription": subskrypcja,
        "items": [{"id": pozycja, "price": cena, "quantity": 1}],
    }
    if promocja:
        zmiana["discounts"] = [{"promotion_code": promocja}]
    return {
        "type": "subscription_update_confirm",
        "subscription_update_confirm": zmiana,
        "after_completion": {"type": "redirect", "redirect": {"return_url": adresy.portal}},
    }


def przeplyw_rezygnacji(subskrypcja: str, adresy: AdresyPowrotu) -> dict[str, Any]:
    """Przepływ portalu rozliczeniowego otwarty od razu na rezygnacji z planu."""
    return {
        "type": "subscription_cancel",
        "subscription_cancel": {"subscription": subskrypcja},
        "after_completion": {"type": "redirect", "redirect": {"return_url": adresy.portal}},
    }


def ma_platna_subskrypcje(rekord: Subskrypcja) -> bool:
    """Czy konto ma opłaconą subskrypcję Stripe, którą można zmienić albo zakończyć."""
    return bool(rekord.stripe_subscription_id) and rekord.status in STATUSY_UPRAWNIAJACE


async def rozpocznij_zakup(
    database: Database,
    klient: KlientStripe,
    ustawienia: UstawieniaPlatnosci,
    adresy: AdresyPowrotu,
    uzytkownik: str,
    plan: str,
    okres: str,
    kupon: str = "",
) -> Zakup:
    """Prowadzi do zakupu planu: nowa sesja Checkout albo zmiana planu w portalu."""
    if okres not in OKRESY:
        raise BladStripe("Nieznany okres rozliczeniowy. Wybierz rozliczenie miesięczne albo roczne.", 400)
    pozycja = pozycja_katalogu(plan)
    if pozycja is None:
        raise BladStripe("Nie znamy takiego planu. Wybierz plan z cennika.", 400)
    kwota = ustawienia.kwoty_groszy.get(f"{pozycja.kod}:{okres}", 0)
    if not do_kupienia(pozycja, okres, ustawienia, kwota):
        raise BladStripe(
            f"Plan {pozycja.nazwa} nie jest jeszcze w sprzedaży. Zostań przy planie Osobistym — "
            "damy znać, gdy ruszy sprzedaż.",
            409,
        )
    biezaca = await subskrypcja_uzytkownika(database, uzytkownik)
    zmiana_planu = ma_platna_subskrypcje(biezaca)
    if zmiana_planu and biezaca.plan_kod == pozycja.kod and biezaca.okres == okres:
        raise BladStripe(f"Plan {pozycja.nazwa} jest już aktywny na tym koncie.", 409)
    cena = ustawienia.cena_stripe(pozycja.kod, okres)
    promocja = ""
    if kupon.strip():
        promocja = (await sprawdz_kupon(database, klient, kupon)).stripe_promotion_id
    if zmiana_planu:
        # Druga sesja Checkout założyłaby drugą subskrypcję – zmiana planu idzie portalem.
        dane_subskrypcji = await klient.pobierz_subskrypcje(biezaca.stripe_subscription_id)
        element = _pozycja_subskrypcji(dane_subskrypcji)
        if not element:
            raise BladStripe(
                "Stripe nie podał pozycji bieżącej subskrypcji, więc nie można od razu "
                "potwierdzić zmiany planu. Spróbuj ponownie za chwilę.",
            )
        adres = await otworz_portal(
            database,
            klient,
            adresy,
            uzytkownik,
            przeplyw_zmiany_planu(biezaca.stripe_subscription_id, element, cena, adresy, promocja),
        )
        return Zakup(adres, TRYB_PORTAL, pozycja.kod, okres)
    rekord = await zapewnij_klienta(database, klient, uzytkownik)
    dane: dict[str, Any] = {
        "mode": "subscription",
        "customer": rekord.stripe_customer_id,
        "client_reference_id": uzytkownik,
        "locale": "pl",
        "line_items": [{"price": cena, "quantity": 1}],
        "success_url": adresy.sukces,
        "cancel_url": adresy.anulowanie,
        "metadata": {"uzytkownik": uzytkownik, "plan": pozycja.kod, "okres": okres},
        "subscription_data": {"metadata": {"uzytkownik": uzytkownik, "plan": pozycja.kod, "okres": okres}},
    }
    if pozycja.okres_probny_dni > 0:
        # Karta jest podawana od razu, a po okresie próbnym subskrypcja przechodzi w płatną
        # bez dodatkowego kroku. Bez pobrania karty Stripe pozwoliłby skończyć okres próbny
        # bez płatności, a wtedy nie da się sprawdzić, czy rozliczenie działa.
        dane["subscription_data"]["trial_period_days"] = pozycja.okres_probny_dni
        dane["subscription_data"]["trial_settings"] = {
            "end_behavior": {"missing_payment_method": "cancel"}
        }
        dane["payment_method_collection"] = "always"
    if promocja:
        dane["discounts"] = [{"promotion_code": promocja}]
    else:
        dane["allow_promotion_codes"] = True
    sesja = await klient.utworz_sesje_checkout(dane)
    adres = str(sesja.get("url") or "")
    if not adres:
        raise BladStripe("Stripe nie zwrócił adresu płatności. Spróbuj ponownie za chwilę.")
    return Zakup(adres, TRYB_CHECKOUT, pozycja.kod, okres)


async def rozpocznij_zakup_pakietu(
    database: Database,
    klient: KlientStripe,
    ustawienia: UstawieniaPlatnosci,
    adresy: AdresyPowrotu,
    uzytkownik: str,
    kod_pakietu: str,
) -> Zakup:
    """Jednorazowy zakup pakietu kredytów (Stripe ``mode: "payment"``).

    Kredyty dopisuje webhook po potwierdzeniu wpłaty, nie powrót z przeglądarki — adres
    powrotu da się otworzyć ponownie i podrobić, a kredyty są towarem.
    """
    pozycja = pakiet(kod_pakietu)
    if pozycja is None:
        raise BladStripe(f"Nie ma pakietu {kod_pakietu}.")
    cena = ustawienia.cennik.get(pozycja.klucz_ceny, "")
    if not cena:
        raise BladStripe(
            f"Pakiet „{pozycja.nazwa}” nie ma jeszcze ceny w Stripe. "
            "Dodaj ją do NEXUS_PLATNOSCI_CENY pod kluczem "
            f"{pozycja.klucz_ceny}."
        )
    rekord = await zapewnij_klienta(database, klient, uzytkownik)
    dane: dict[str, Any] = {
        "mode": "payment",
        "customer": rekord.stripe_customer_id,
        "client_reference_id": uzytkownik,
        "locale": "pl",
        "line_items": [{"price": cena, "quantity": 1}],
        "success_url": adresy.sukces,
        "cancel_url": adresy.anulowanie,
        "invoice_creation": {"enabled": True},
        "metadata": {
            "uzytkownik": uzytkownik,
            "pakiet": pozycja.kod,
            "kredyty": str(pozycja.kredyty),
        },
    }
    sesja = await klient.utworz_sesje_checkout(dane)
    adres = str(sesja.get("url") or "")
    if not adres:
        raise BladStripe("Stripe nie zwrócił adresu płatności. Spróbuj ponownie za chwilę.")
    return Zakup(adres, TRYB_CHECKOUT, pozycja.kod, "jednorazowo")


async def otworz_portal(
    database: Database,
    klient: KlientStripe,
    adresy: AdresyPowrotu,
    uzytkownik: str,
    przeplyw: dict[str, Any] | None = None,
) -> str:
    """Tworzy sesję Billing Portal (zmiana metody płatności, rezygnacja, faktury)."""
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    if not rekord.stripe_customer_id:
        raise BladStripe(
            "Nie masz jeszcze żadnego zakupu, więc rozliczenia są puste. Wybierz plan, "
            "a portal otworzy się po pierwszej płatności.",
            409,
        )
    sesja = await klient.utworz_sesje_portalu(rekord.stripe_customer_id, adresy.portal, przeplyw)
    adres = str(sesja.get("url") or "")
    if not adres:
        raise BladStripe("Stripe nie zwrócił adresu portalu rozliczeniowego. Spróbuj ponownie za chwilę.")
    return adres


async def rozpocznij_rezygnacje(
    database: Database, klient: KlientStripe, adresy: AdresyPowrotu, uzytkownik: str
) -> str:
    """Otwiera portal rozliczeniowy na rezygnacji z bieżącego planu."""
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    if not ma_platna_subskrypcje(rekord):
        raise BladStripe(
            "Nie masz wykupionego planu, z którego można zrezygnować.",
            409,
        )
    if rekord.anuluj_na_koniec:
        koniec = zapis_daty(rekord.okres_do)
        kiedy = f" {koniec}" if koniec else " wraz z opłaconym okresem"
        raise BladStripe(f"Rezygnacja jest już złożona — plan kończy się{kiedy}.", 409)
    return await otworz_portal(
        database, klient, adresy, uzytkownik, przeplyw_rezygnacji(rekord.stripe_subscription_id, adresy)
    )


def _okres_subskrypcji(dane: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    """Początek i koniec bieżącego okresu – z subskrypcji albo z jej pierwszej pozycji."""
    od, do = czas(dane.get("current_period_start")), czas(dane.get("current_period_end"))
    if od and do:
        return od, do
    pozycje = (dane.get("items") or {}).get("data") or []
    if pozycje:
        pierwsza = pozycje[0]
        return czas(pierwsza.get("current_period_start")) or od, czas(
            pierwsza.get("current_period_end")
        ) or do
    return od, do


def _cena_subskrypcji(dane: dict[str, Any]) -> str:
    """Identyfikator ceny z pierwszej pozycji subskrypcji."""
    pozycje = (dane.get("items") or {}).get("data") or []
    if not pozycje:
        return ""
    return _identyfikator((pozycje[0] or {}).get("price"))


async def zapisz_subskrypcje(
    database: Database, ustawienia: UstawieniaPlatnosci, uzytkownik: str, dane: dict[str, Any]
) -> Subskrypcja:
    """Przepisuje stan subskrypcji Stripe do bazy (plan rozpoznany po cenie)."""
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    rekord.stripe_subscription_id = _identyfikator(dane)
    klient_id = _identyfikator(dane.get("customer"))
    if klient_id:
        rekord.stripe_customer_id = klient_id
    rekord.status = STATUSY_STRIPE.get(str(dane.get("status") or ""), STATUS_NIEPELNA)
    rozpoznany = ustawienia.plan_dla_ceny(_cena_subskrypcji(dane))
    metadane = dane.get("metadata") or {}
    if rozpoznany:
        rekord.plan_kod, rekord.okres = rozpoznany
    else:
        rekord.plan_kod = str(metadane.get("plan") or rekord.plan_kod or PLAN_DOMYSLNY)
        rekord.okres = str(metadane.get("okres") or rekord.okres)
    rekord.okres_od, rekord.okres_do = _okres_subskrypcji(dane)
    rekord.anuluj_na_koniec = bool(dane.get("cancel_at_period_end"))
    if rekord.status == STATUS_ANULOWANA:
        rekord.plan_kod = PLAN_DOMYSLNY
        rekord.okres = ""
    return await _zapisz(database, rekord)


async def zapisz_fakture(database: Database, uzytkownik: str, dane: dict[str, Any]) -> Faktura:
    """Zapisuje (albo odświeża) fakturę Stripe w bazie."""
    identyfikator = _identyfikator(dane)
    async with database.session() as session:
        rekord = await session.scalar(select(Faktura).where(Faktura.stripe_invoice_id == identyfikator))
        if rekord is None:
            rekord = Faktura(stripe_invoice_id=identyfikator)
            session.add(rekord)
        rekord.uzytkownik = uzytkownik
        rekord.numer = str(dane.get("number") or "")[:60]
        rekord.kwota_gr = int(dane.get("amount_due") or dane.get("total") or 0)
        rekord.waluta = str(dane.get("currency") or "pln")[:3]
        rekord.status = str(dane.get("status") or "")[:20]
        rekord.pdf_url = str(dane.get("invoice_pdf") or "")
        rekord.strona_url = str(dane.get("hosted_invoice_url") or "")
        rekord.wystawiona_at = czas(dane.get("created"))
        oplacona = (dane.get("status_transitions") or {}).get("paid_at")
        rekord.oplacona_at = czas(oplacona)
        if rekord.oplacona_at is None and dane.get("status") == "paid":
            rekord.oplacona_at = czas(dane.get("created"))
    return rekord


async def odswiez_faktury(database: Database, klient: KlientStripe, uzytkownik: str) -> list[Faktura]:
    """Pobiera faktury klienta ze Stripe i zapisuje je w bazie."""
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    if not rekord.stripe_customer_id:
        return []
    for pozycja in await klient.lista_faktur(rekord.stripe_customer_id):
        await zapisz_fakture(database, uzytkownik, pozycja)
    return await faktury_uzytkownika(database, uzytkownik)


async def faktury_uzytkownika(database: Database, uzytkownik: str, limit: int = 50) -> list[Faktura]:
    """Faktury użytkownika zapisane w bazie, od najnowszej."""
    async with database.session() as session:
        wynik = await session.scalars(
            select(Faktura)
            .where(Faktura.uzytkownik == uzytkownik)
            .order_by(Faktura.wystawiona_at.desc().nullslast(), Faktura.created_at.desc())
            .limit(limit)
        )
        return list(wynik.all())


async def faktura_do_zaplaty(database: Database, uzytkownik: str) -> Faktura | None:
    """Najnowsza faktura użytkownika czekająca na zapłatę (albo ``None``)."""
    async with database.session() as session:
        return await session.scalar(
            select(Faktura)
            .where(Faktura.uzytkownik == uzytkownik)
            .where(Faktura.status.in_(tuple(STATUSY_FAKTURY_DO_ZAPLATY)))
            .order_by(Faktura.wystawiona_at.desc().nullslast(), Faktura.created_at.desc())
            .limit(1)
        )


async def zsynchronizuj_po_powrocie(
    database: Database,
    klient: KlientStripe,
    ustawienia: UstawieniaPlatnosci,
    uzytkownik: str,
    identyfikator_sesji: str,
) -> Subskrypcja:
    """Uzgadnia stan po powrocie z Checkoutu, nie czekając na webhook."""
    sesja = await klient.pobierz_sesje_checkout(identyfikator_sesji)
    # Sesja bez oznaczenia konta też jest odrzucana: każdą zakłada tutejszy zakup, więc brak
    # oznaczenia znaczy, że sesja powstała poza tą drogą i nie może przypisać planu do konta.
    if str(sesja.get("client_reference_id") or "") != uzytkownik:
        raise BladStripe("Sesja zakupu należy do innego konta.", 403)
    subskrypcja = _identyfikator(sesja.get("subscription"))
    if not subskrypcja:
        return await subskrypcja_uzytkownika(database, uzytkownik)
    dane = await klient.pobierz_subskrypcje(subskrypcja)
    return await zapisz_subskrypcje(database, ustawienia, uzytkownik, dane)
