"""Moduł Płatności: cennik, zakup planu przez Stripe Checkout, portal rozliczeniowy,
faktury, kupony rabatowe i webhook Stripe.

Punkty zmieniające stan działają pod ochroną sesji i nagłówka aplikacji (CSRF).
Wyjątkiem jest ``POST /api/platnosci/webhook`` – wywołuje go Stripe, więc nie ma
tam sesji; jego jedynym uwierzytelnieniem jest podpis treści żądania, bez którego
odpowiedź to 400. Publiczny jest wyłącznie ``GET /api/platnosci/cennik``: katalog
planów i kwoty, czyli treść przeznaczona do publikacji w portalu.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from nexus.api.auth import require_session
from nexus.chmura_konta import uzgodnij_limit_po_zmianie_planu
from nexus.db import Database, UserSession
from nexus.platnosci import kredyty
from nexus.platnosci.grupy import konto_rozliczeniowe
from nexus.platnosci.klient import BladStripe, KlientHttpStripe, KlientStripe
from nexus.platnosci.konfiguracja import (
    OKRESY,
    UstawieniaPlatnosci,
    adresy_powrotu,
    ustawienia_platnosci,
)
from nexus.platnosci.model import STATUS_PROBNA, Faktura, Plan, Subskrypcja
from nexus.platnosci.pakiety import KATALOG_PAKIETOW
from nexus.platnosci.plany import KATALOG_WG_KODU, PlanKatalogu, do_kupienia, synchronizuj_plany
from nexus.platnosci.podpis import BladPodpisu, odczytaj_zdarzenie
from nexus.platnosci.stany import KOMUNIKAT_SPRZEDAZ_WYLACZONA, stan_sprzedazy
from nexus.platnosci.uprawnienia import limity_planu, limity_subskrypcji
from nexus.platnosci.uslugi import (
    faktura_do_zaplaty,
    faktury_uzytkownika,
    ma_platna_subskrypcje,
    odswiez_faktury,
    otworz_portal,
    rozpocznij_doladowanie,
    rozpocznij_rezygnacje,
    rozpocznij_zakup,
    rozpocznij_zakup_pakietu,
    sprawdz_kupon,
    subskrypcja_uzytkownika,
    zsynchronizuj_po_powrocie,
)
from nexus.platnosci.zdarzenia import przyjmij_zdarzenie, wlasciciel_zdarzenia


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Przy starcie zapisuje katalog planów w bazie (nazwy, opisy, limity, kwoty)."""
    await synchronizuj_plany(app.state.database, ustawienia_platnosci())
    yield


router = APIRouter(prefix="/api/platnosci", tags=["platnosci"], lifespan=lifespan)

# Zdarzenie Stripe mieści się w dziesiątkach kilobajtów; megabajt to zapas, nie próg pracy.
MAX_WEBHOOK_BAJTOW = 1024 * 1024


class ZakupBody(BaseModel):
    """Żądanie zakupu: wyłącznie kod planu, okres rozliczeniowy i opcjonalny kupon."""

    plan: str = Field(min_length=1, max_length=30)
    okres: str = Field(max_length=10)
    kupon: str = Field("", max_length=64)


class KuponBody(BaseModel):
    kod: str = Field(min_length=1, max_length=64)


class PowrotBody(BaseModel):
    sesja: str = Field(min_length=1, max_length=200)


def _klient(request: Request) -> KlientStripe:
    """Klient Stripe: atrapa podstawiona w testach albo implementacja HTTP."""
    podstawiony = getattr(request.app.state, "platnosci_klient", None)
    if podstawiony is not None:
        return podstawiony
    try:
        return KlientHttpStripe(ustawienia_platnosci())
    except BladStripe as blad:
        raise HTTPException(blad.status, str(blad)) from blad


async def _wywolaj(request: Request, operacja: Any) -> Any:
    """Wykonuje operację na kliencie Stripe i zamienia błędy na odpowiedzi HTTP."""
    klient = _klient(request)
    wlasny = getattr(request.app.state, "platnosci_klient", None) is None
    try:
        return await operacja(klient)
    except BladStripe as blad:
        raise HTTPException(blad.status, str(blad)) from blad
    finally:
        if wlasny:
            await klient.zamknij()


def klucz_konta(sesja: UserSession) -> str:
    """Klucz subskrypcji: konto zalogowanego użytkownika, nie instalacja.

    Wcześniej subskrypcja była jedna na instalację (login właściciela), więc zakup
    jednego użytkownika obejmowałby wszystkich. Kluczem jest identyfikator konta —
    ten sam, po którym rozdzielone są rozmowy, pliki i kredyty.
    """
    return str(sesja.owner_id)


def _wymagaj_sprzedazy(ustawienia: UstawieniaPlatnosci) -> None:
    """Zatrzymuje operacje sprzedaży, dopóki nie ma klucza Stripe, z komunikatem dla użytkownika."""
    if not ustawienia.skonfigurowane:
        raise HTTPException(status.HTTP_409_CONFLICT, KOMUNIKAT_SPRZEDAZ_WYLACZONA)


def _adresy(request: Request) -> Any:
    return adresy_powrotu(ustawienia_platnosci(), request.app.state.settings.public_url)


async def _subskrypcja_json(
    database: Database, subskrypcja: Subskrypcja, ustawienia: UstawieniaPlatnosci
) -> dict[str, Any]:
    """Subskrypcja, limity planu i stan sprzedaży wraz z komunikatem dla użytkownika."""
    limity = limity_subskrypcji(subskrypcja)
    pozycja = KATALOG_WG_KODU.get(subskrypcja.plan_kod)
    zalegla = await faktura_do_zaplaty(database, subskrypcja.uzytkownik)
    stan = stan_sprzedazy(subskrypcja, ustawienia.skonfigurowane, zalegla)
    return {
        "stan": stan.mapa(),
        "faktura_do_zaplaty": _faktura_json(zalegla) if zalegla is not None else None,
        "plan": subskrypcja.plan_kod,
        "nazwa_planu": pozycja.nazwa if pozycja else subskrypcja.plan_kod,
        "status": subskrypcja.status,
        "okres": subskrypcja.okres,
        "okres_od": subskrypcja.okres_od.isoformat() if subskrypcja.okres_od else None,
        "okres_do": subskrypcja.okres_do.isoformat() if subskrypcja.okres_do else None,
        "anuluj_na_koniec": subskrypcja.anuluj_na_koniec,
        "ma_konto_stripe": bool(subskrypcja.stripe_customer_id),
        "ma_platny_plan": ma_platna_subskrypcje(subskrypcja),
        "limity": limity.mapa(),
    }


def _faktura_json(faktura: Faktura) -> dict[str, Any]:
    return {
        "id": str(faktura.id),
        "numer": faktura.numer,
        "kwota_gr": faktura.kwota_gr,
        "waluta": faktura.waluta,
        "status": faktura.status,
        "pdf_url": faktura.pdf_url,
        "strona_url": faktura.strona_url,
        "wystawiona_at": faktura.wystawiona_at.isoformat() if faktura.wystawiona_at else None,
        "oplacona_at": faktura.oplacona_at.isoformat() if faktura.oplacona_at else None,
    }


def _probny_json(pozycja: PlanKatalogu) -> dict[str, int]:
    """Zakres okresu próbnego wzięty stamtąd, skąd bierze go egzekwowanie.

    Cennik obiecuje pełny zakres planu, a przez pierwsze dni serwer stosuje węższy
    (`limity_planu` ze statusem próbnym). Gdyby cennik przepisywał te liczby z katalogu
    po swojemu, rozjechałby się z tym, co naprawdę dopuszcza `api/files.py` — a użytkownik
    poznałby różnicę dopiero odpowiedzią 413.
    """
    if pozycja.okres_probny_dni <= 0:
        return dict.fromkeys(
            ("dni", "przestrzen_mb", "kredyty", "skrzynki", "wersjonowanie", "synchronizacja"), 0
        )
    limity = limity_planu(pozycja.kod, STATUS_PROBNA)
    return {
        "dni": pozycja.okres_probny_dni,
        "przestrzen_mb": limity.przestrzen_mb,
        "kredyty": pozycja.probny_kredyty,
        "skrzynki": limity.skrzynki,
        "wersjonowanie": int(limity.wersjonowanie),
        "synchronizacja": int(limity.synchronizacja),
    }


async def _cennik_json(request: Request) -> dict[str, Any]:
    """Cennik rozstrzygnięty przez serwer: plany, kwoty w groszach i możliwość zakupu.

    Jedna definicja obsługuje moduł Płatności i publiczny cennik portalu, więc obie
    powierzchnie pokazują te same nazwy, zakresy i kwoty.
    """
    ustawienia = ustawienia_platnosci()
    database: Database = request.app.state.database
    async with database.session() as session:
        rekordy = (await session.scalars(select(Plan).where(Plan.aktywny.is_(True)))).all()
    lista = []
    for rekord in sorted(rekordy, key=lambda pozycja: pozycja.kolejnosc):
        pozycja = KATALOG_WG_KODU.get(rekord.kod)
        if pozycja is None:
            continue
        lista.append(
            {
                "kod": rekord.kod,
                "nazwa": rekord.nazwa,
                "opis": rekord.opis,
                "bezplatny": pozycja.bezplatny,
                "znacznik": pozycja.znacznik,
                "zawartosc": list(pozycja.zawartosc),
                # Kredyty i dni próbne rozstrzygają decyzję o zakupie: kredyty mówią, ile
                # pracy obejmuje plan, a okres próbny — od kiedy naliczamy opłatę.
                "kredyty_okresowo": pozycja.kredyty_okresowo,
                "okres_probny_dni": pozycja.okres_probny_dni,
                # Zakres planu rozstrzyga serwer: witryna i aplikacja mają pokazywać te
                # liczby, a nie wpisywać własnych. Okres próbny to ten sam plan w węższym
                # zakresie, więc jedzie w osobnym polu obok docelowego.
                "przestrzen_mb": pozycja.przestrzen_mb,
                "skrzynki_poczty": pozycja.skrzynki_poczty,
                "wersjonowanie": pozycja.wersjonowanie,
                "synchronizacja": pozycja.synchronizacja,
                "probny": _probny_json(pozycja),
                "limity": rekord.limity,
                "cena_miesiac_gr": rekord.cena_miesiac_gr,
                "cena_rok_gr": rekord.cena_rok_gr,
                "do_kupienia": {
                    okres: do_kupienia(
                        pozycja,
                        okres,
                        ustawienia,
                        rekord.cena_miesiac_gr if okres == "miesiac" else rekord.cena_rok_gr,
                    )
                    for okres in OKRESY
                },
            }
        )
    return {"waluta": ustawienia.waluta, "sprzedaz_aktywna": ustawienia.skonfigurowane, "plany": lista}


#: Próg, od którego mówimy użytkownikowi, że dostęp się kończy (udział zużycia).
PROG_OSTRZEZENIA = 0.85


@router.get("/kredyty")
async def kredyty_konta(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, Any]:
    """Stan wykorzystania dostępu — paskiem, bez liczb.

    Kredyt jest jednostką rozliczeniową między nami a dostawcą modelu, nie towarem dla
    użytkownika. Pokazywanie salda w sztukach zmuszałoby go do liczenia, ile „kosztuje”
    zdanie, i robiłoby z rozmowy licznik taksówki. Dlatego na zewnątrz idzie wyłącznie
    udział zużycia (0–1), z którego interfejs rysuje pasek, oraz stan słowny.

    Historia zmian zostaje, ale bez wartości: mówi, co się działo, a nie ile czego ubyło.
    """
    database: Database = request.app.state.database
    # W grupie pasek pokazuje wspólną pulę: to z niej schodzi praca każdego członka,
    # więc pokazywanie mu własnego, nietykanego konta byłoby wprowadzaniem w błąd.
    konto = await konto_rozliczeniowe(database, sesja.owner_id)
    biezace = await kredyty.stan(database, konto)
    udzial = kredyty.udzial_zuzycia(biezace)
    wyczerpane = biezace.saldo < kredyty.PROG_ZLECENIA
    stan = "wyczerpany" if wyczerpane else "konczy_sie" if udzial >= PROG_OSTRZEZENIA else "w_porzadku"
    historia = [
        {"powod": wpis["powod"], "opis": wpis["opis"], "kiedy": wpis["kiedy"]}
        for wpis in await kredyty.historia(database, konto, 30)
    ]
    return {
        "zuzycie": round(udzial, 4),
        "stan": stan,
        "wyczerpane": wyczerpane,
        "historia": historia,
        # Pola zgodności dla okien, które nie zdążyły się jeszcze zaktualizować.
        # Aplikacja jest instalowana jako PWA i potrafi chodzić na wersji sprzed
        # wydania; bez tych pól stary kod sięga po `saldo`, nie znajduje go i gasi
        # cały ekran. Do usunięcia, gdy wszystkie okna będą po aktualizacji.
        "saldo": biezace.saldo,
        "przydzielone": biezace.przydzielone,
        "zuzyte": biezace.zuzyte,
        "doladowanie": {
            "minimum_gr": kredyty.MINIMUM_DOLADOWANIA_GR,
            "maksimum_gr": kredyty.MAKSIMUM_DOLADOWANIA_GR,
            "kwoty_szybkie_gr": list(kredyty.KWOTY_SZYBKIE_GR),
            "sprzedaz": ustawienia_platnosci().skonfigurowane,
        },
    }


class DoladowanieBody(BaseModel):
    """Kwota doładowania wpisana przez użytkownika (w groszach)."""

    kwota_gr: int = Field(ge=0, le=10_000_000)


@router.post("/doladowanie/checkout")
async def checkout_doladowania(
    payload: DoladowanieBody, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, str]:
    """Rozpoczyna jednorazowe doładowanie dostępu kwotą podaną przez użytkownika."""
    _wymagaj_sprzedazy(ustawienia_platnosci())
    database: Database = request.app.state.database
    uzytkownik = klucz_konta(sesja)
    wynik = await _wywolaj(
        request,
        lambda klient: rozpocznij_doladowanie(
            database,
            klient,
            ustawienia_platnosci(),
            _adresy(request),
            uzytkownik,
            payload.kwota_gr,
        ),
    )
    return {"url": wynik.adres, "tryb": wynik.tryb}


@router.get("/cennik")
async def cennik(request: Request) -> dict[str, Any]:
    """Publiczny cennik dla portalu i strony produktu (bez danych konta)."""
    return await _cennik_json(request)


@router.get("/plany")
async def plany(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, Any]:
    """Cennik wraz z bieżącą subskrypcją konta i stanem sprzedaży."""
    database: Database = request.app.state.database
    dane = await _cennik_json(request)
    uzytkownik = klucz_konta(sesja)
    subskrypcja = await subskrypcja_uzytkownika(database, uzytkownik)
    dane["subskrypcja"] = await _subskrypcja_json(database, subskrypcja, ustawienia_platnosci())
    return dane


@router.get("/subskrypcja")
async def subskrypcja(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, Any]:
    """Aktywna subskrypcja użytkownika wraz z limitami planu i stanem sprzedaży."""
    database: Database = request.app.state.database
    uzytkownik = klucz_konta(sesja)
    rekord = await subskrypcja_uzytkownika(database, uzytkownik)
    return await _subskrypcja_json(database, rekord, ustawienia_platnosci())


class PakietBody(BaseModel):
    """Żądanie zakupu pakietu kredytów."""

    pakiet: str = Field(min_length=1, max_length=30)


@router.get("/pakiety")
async def pakiety(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, Any]:
    """Pakiety kredytów do dokupienia poza subskrypcją."""
    ustawienia = ustawienia_platnosci()
    return {
        "sprzedaz": ustawienia.skonfigurowane,
        "pakiety": [
            {
                "kod": pozycja.kod,
                "nazwa": pozycja.nazwa,
                "opis": pozycja.opis,
                "kredyty": pozycja.kredyty,
                "do_kupienia": bool(ustawienia.cennik.get(pozycja.klucz_ceny)),
            }
            for pozycja in KATALOG_PAKIETOW
        ],
    }


@router.post("/pakiety/checkout")
async def checkout_pakietu(
    payload: PakietBody, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, str]:
    """Rozpoczyna jednorazowy zakup pakietu kredytów."""
    _wymagaj_sprzedazy(ustawienia_platnosci())
    database: Database = request.app.state.database
    uzytkownik = klucz_konta(sesja)
    wynik = await _wywolaj(
        request,
        lambda klient: rozpocznij_zakup_pakietu(
            database,
            klient,
            ustawienia_platnosci(),
            _adresy(request),
            uzytkownik,
            payload.pakiet.strip().lower(),
        ),
    )
    return {"url": wynik.adres, "tryb": wynik.tryb, "pakiet": wynik.plan}


@router.post("/checkout")
async def checkout(
    payload: ZakupBody, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, str]:
    """Rozpoczyna zakup planu albo — gdy plan już jest opłacony — jego zmianę w portalu."""
    _wymagaj_sprzedazy(ustawienia_platnosci())
    database: Database = request.app.state.database
    uzytkownik = klucz_konta(sesja)
    wynik = await _wywolaj(
        request,
        lambda klient: rozpocznij_zakup(
            database,
            klient,
            ustawienia_platnosci(),
            _adresy(request),
            uzytkownik,
            payload.plan.strip().lower(),
            payload.okres.strip().lower(),
            payload.kupon,
        ),
    )
    return {"url": wynik.adres, "tryb": wynik.tryb, "plan": wynik.plan, "okres": wynik.okres}


@router.post("/portal")
async def portal(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, str]:
    """Adres portalu rozliczeniowego Stripe (metoda płatności, rezygnacja, faktury)."""
    _wymagaj_sprzedazy(ustawienia_platnosci())
    database: Database = request.app.state.database
    uzytkownik = klucz_konta(sesja)
    adres = await _wywolaj(
        request, lambda klient: otworz_portal(database, klient, _adresy(request), uzytkownik)
    )
    return {"url": adres}


@router.post("/rezygnacja")
async def rezygnacja(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, str]:
    """Adres portalu rozliczeniowego otwartego od razu na rezygnacji z planu."""
    _wymagaj_sprzedazy(ustawienia_platnosci())
    database: Database = request.app.state.database
    uzytkownik = klucz_konta(sesja)
    adres = await _wywolaj(
        request, lambda klient: rozpocznij_rezygnacje(database, klient, _adresy(request), uzytkownik)
    )
    return {"url": adres}


@router.post("/kupon")
async def kupon(
    payload: KuponBody, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, Any]:
    """Sprawdza kod rabatowy w Stripe przed zakupem."""
    _wymagaj_sprzedazy(ustawienia_platnosci())
    database: Database = request.app.state.database
    rekord = await _wywolaj(request, lambda klient: sprawdz_kupon(database, klient, payload.kod))
    return {
        "kod": rekord.kod,
        "rabat_procent": rekord.rabat_procent,
        "rabat_gr": rekord.rabat_gr,
        "waluta": rekord.waluta,
        "opis": rekord.opis,
        "wygasa_at": rekord.wygasa_at.isoformat() if rekord.wygasa_at else None,
    }


@router.post("/powrot")
async def powrot(
    payload: PowrotBody, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, Any]:
    """Uzgadnia stan po powrocie z Checkoutu, nie czekając na webhook."""
    database: Database = request.app.state.database
    uzytkownik = klucz_konta(sesja)
    rekord = await _wywolaj(
        request,
        lambda klient: zsynchronizuj_po_powrocie(
            database, klient, ustawienia_platnosci(), uzytkownik, payload.sesja
        ),
    )
    return await _subskrypcja_json(database, rekord, ustawienia_platnosci())


@router.get("/faktury")
async def faktury(
    request: Request, odswiez: bool = False, sesja: UserSession = Depends(require_session)
) -> list[dict[str, Any]]:
    """Faktury użytkownika; ``odswiez=1`` pobiera je najpierw ze Stripe."""
    database: Database = request.app.state.database
    uzytkownik = klucz_konta(sesja)
    if odswiez:
        rekordy = await _wywolaj(request, lambda klient: odswiez_faktury(database, klient, uzytkownik))
    else:
        rekordy = await faktury_uzytkownika(database, uzytkownik)
    return [_faktura_json(rekord) for rekord in rekordy]


async def _tresc_webhooka(request: Request) -> bytes:
    """Treść żądania webhooka czytana strumieniem, z twardym ograniczeniem rozmiaru.

    Punkt jest publiczny, a podpis da się sprawdzić dopiero na całej treści. Bez tego limitu
    każdy mógłby wprowadzić do pamięci procesu API żądanie tej wielkości, jaką dopuszcza
    odwrotne proxy, i to bez żadnego uwierzytelnienia.
    """
    bufor = bytearray()
    async for kawalek in request.stream():
        bufor.extend(kawalek)
        if len(bufor) > MAX_WEBHOOK_BAJTOW:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE, "Treść zdarzenia webhooka przekracza limit."
            )
    return bytes(bufor)


async def _uzgodnij_limit_chmury(request: Request, zdarzenie: dict[str, Any]) -> None:
    """Limit chmury idzie za planem; błąd chmury nie może cofać przyjęcia zdarzenia przez Stripe."""
    if not str(zdarzenie.get("type", "")).startswith(("customer.subscription.", "checkout.")):
        return
    try:
        owner = await wlasciciel_zdarzenia(request.app.state.database, zdarzenie)
        if owner is not None:
            await uzgodnij_limit_po_zmianie_planu(
                request.app.state.settings, request.app.state.database, owner
            )
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "Nie udało się uzgodnić limitu chmury po zdarzeniu %s", zdarzenie.get("id"), exc_info=True
        )


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request, stripe_signature: str = Header("")) -> dict[str, Any]:
    """Webhook Stripe: weryfikacja podpisu, zapis zdarzenia, idempotentna zmiana stanu."""
    ustawienia = ustawienia_platnosci()
    ladunek = await _tresc_webhooka(request)
    try:
        zdarzenie = odczytaj_zdarzenie(ladunek, stripe_signature, ustawienia.sekret_webhooka)
    except BladPodpisu as blad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(blad)) from blad
    try:
        wynik = await przyjmij_zdarzenie(request.app.state.database, ustawienia, zdarzenie)
    except Exception as blad:
        # Stripe ponawia doręczenie po odpowiedzi 500; zdarzenie jest już w dzienniku.
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Nie udało się przetworzyć zdarzenia."
        ) from blad
    if wynik.get("obsluzone"):
        await _uzgodnij_limit_chmury(request, zdarzenie)
    return wynik
