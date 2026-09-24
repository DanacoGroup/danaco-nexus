"""Kredyty konta: przydział z planu, naliczanie za pracę agenta i historia zmian.

Kredyt jest jednostką pracy, nie pieniądzem. Konto dostaje przydział z planu (przy zakupie
i przy każdym odnowieniu), a każdy zakończony przebieg agenta pomniejsza saldo o koszt
policzony ze zużycia modelu. Saldo bliskie zeru zatrzymuje kolejne zlecenia, zanim zaczną
się liczyć — inaczej użytkownik dowiadywałby się o braku środków w połowie pracy.

Każda zmiana salda ma wpis w księdze (``RuchKredytow``): kiedy, ile, za co i z jakim saldem
po operacji. Bez księgi nie da się odpowiedzieć na pytanie „za co zeszły mi kredyty”, a to
pierwsze pytanie, jakie zadaje płacący użytkownik.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Integer, String, Uuid, func, select
from sqlalchemy.orm import Mapped, mapped_column

from nexus.db import ADMIN_OWNER, Base, Database, JsonType, UtcDateTime, utcnow

# --- cennik kredytów -------------------------------------------------------------------
#
# To jest **nasz** przelicznik, niezależny od tego, jak rozliczamy się z dostawcą modelu.
# Użytkownik płaci nam za kredyty i zużywa je według poniższych stawek; limity i koszty po
# stronie silnika są sprawą między nami a dostawcą i nigdzie nie wychodzą na wierzch.
#
# Stawki są w kredytach i całkowite, żeby saldo liczyło się dokładnie, bez ułamków groszy.
# Każdą z nich można zmienić zmienną środowiskową bez wydawania nowej wersji.

def stawka(nazwa: str, domyslna: int) -> int:
    """Stawka cennika ze zmiennej środowiskowej (albo wartość domyślna).

    Odczyt przy każdym użyciu, a nie raz przy imporcie: zmiana cennika ma działać po
    restarcie usługi, bez wydawania nowej wersji i bez przeładowywania modułu.
    """
    surowa = os.environ.get(f"NEXUS_KREDYT_{nazwa}", "")
    try:
        return max(int(surowa), 0) if surowa else domyslna
    except ValueError:
        return domyslna


# Za tysiąc żetonów wysłanych do modelu (treść rozmowy, fragmenty plików, kontekst).
DOMYSLNIE_1K_WEJSCIE = 1
# Za tysiąc żetonów wygenerowanych przez model. Droższe, bo droższe jest też u dostawcy.
DOMYSLNIE_1K_WYJSCIE = 5
# Najmniejsza opłata za przebieg: nawet krótka odpowiedź zajmuje maszynę.
DOMYSLNIE_MINIMUM = 1
# Poniżej tej wartości nie przyjmujemy nowego zlecenia.
PROG_ZLECENIA = 1

# Narzędzia, których koszt to czas maszyny, a nie żetony. Powiększanie zdjęcia siecią
# Real-ESRGAN na procesorze potrafi liczyć minuty, a w rozmowie zostawia dwa zdania —
# bez tej tabeli byłoby dla użytkownika praktycznie darmowe.
KOSZT_NARZEDZI: dict[str, int] = {
    "upscale_image": 20,
    "enhance_photo": 8,
    "retouch_portrait": 8,
    "remove_background": 6,
    "change_background": 6,
    "erase_objects": 10,
    "transcribe_audio": 15,
    "media_process": 10,
    "ocr_documents": 8,
    "enhance_document_scan": 6,
    "detect_document_boundaries": 6,
    "index_documents": 5,
    "translate_document": 5,
    "scholar_search": 4,
    "web_search": 2,
    "web_fetch_page": 2,
}


#: Powody wpisów, które są przydziałem z planu albo startu. Tylko one odbierają kontu
#: przydział startowy i zakres próbny — zakup (``zakup``) i praca (``przebieg``) nie.
POWODY_PRZYDZIALU = ("start", "okres-probny", "plan", "odnowienie", "konto-testowe")


class SaldoKredytow(Base):
    """Bieżące saldo kredytów konta."""

    __tablename__ = "platnosci_kredyty"

    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    saldo: Mapped[int] = mapped_column(BigInteger, default=0)
    przydzielone: Mapped[int] = mapped_column(BigInteger, default=0)
    zuzyte: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class RuchKredytow(Base):
    """Wpis księgi kredytów: przydział, zużycie albo korekta."""

    __tablename__ = "platnosci_kredyty_ruchy"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    # Dodatnia zmiana to przydział, ujemna to zużycie.
    zmiana: Mapped[int] = mapped_column(Integer)
    saldo_po: Mapped[int] = mapped_column(BigInteger)
    powod: Mapped[str] = mapped_column(String(40))
    opis: Mapped[str] = mapped_column(String(200), default="")
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    szczegoly: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, index=True)


class BrakKredytow(Exception):
    """Konto wyczerpało dostęp na kolejne zlecenie.

    Komunikat nie mówi o kredytach: jednostka rozliczeniowa jest nasza, nie użytkownika.
    Ma on wiedzieć, że praca stanęła i jak ją wznowić — liczba, której nigdzie nie widział,
    niczego by tu nie wyjaśniła.
    """

    def __init__(self, saldo: int) -> None:
        super().__init__(
            "Dostęp na tym koncie się wyczerpał. Przedłuż go albo odnów plan, "
            "a zadania ruszą od razu."
        )
        self.saldo = saldo
        # 402 Payment Required: dalsza praca wymaga doładowania.
        self.status = 402


@dataclass(frozen=True)
class StanKredytow:
    """Saldo konta w postaci przekazywanej do interfejsu."""

    saldo: int
    przydzielone: int
    zuzyte: int

    def mapa(self) -> dict[str, int]:
        return {"saldo": self.saldo, "przydzielone": self.przydzielone, "zuzyte": self.zuzyte}


def koszt_narzedzi(nazwy: Iterable[str]) -> int:
    """Dopłata za narzędzia liczone czasem maszyny, a nie żetonami."""
    return sum(KOSZT_NARZEDZI.get(nazwa, 0) for nazwa in nazwy)


def koszt_przebiegu(uzycie: dict[str, Any] | None, narzedzia: Iterable[str] = ()) -> int:
    """Koszt przebiegu w kredytach: żetony modelu plus dopłata za ciężkie narzędzia.

    Brak danych o zużyciu nie może oznaczać pracy za darmo — wtedy liczy się opłata
    minimalna, tak samo jak przy bardzo krótkiej odpowiedzi. Zaokrąglamy w górę do
    pełnego kredytu; ułamki działałyby na naszą niekorzyść przy tysiącach przebiegów.
    """
    dane = uzycie or {}
    wejscie = int(dane.get("input_tokens") or 0) + int(dane.get("cache_read_input_tokens") or 0)
    wyjscie = int(dane.get("output_tokens") or 0)
    za_wejscie = wejscie * stawka("1K_WEJSCIE", DOMYSLNIE_1K_WEJSCIE)
    za_wyjscie = wyjscie * stawka("1K_WYJSCIE", DOMYSLNIE_1K_WYJSCIE)
    za_zetony = (za_wejscie + za_wyjscie + 999) // 1000
    return max(za_zetony + koszt_narzedzi(narzedzia), stawka("MINIMUM", DOMYSLNIE_MINIMUM))


async def stan(database: Database, owner: uuid.UUID) -> StanKredytow:
    """Saldo konta; konto bez wpisu ma saldo zerowe."""
    async with database.session() as session:
        rekord = await session.get(SaldoKredytow, owner)
        if rekord is None:
            return StanKredytow(0, 0, 0)
        return StanKredytow(int(rekord.saldo), int(rekord.przydzielone), int(rekord.zuzyte))


async def _zapisz(
    database: Database,
    owner: uuid.UUID,
    zmiana: int,
    powod: str,
    opis: str = "",
    run_id: uuid.UUID | None = None,
    szczegoly: dict[str, Any] | None = None,
) -> int:
    """Zmienia saldo i dopisuje wpis do księgi; zwraca saldo po operacji."""
    async with database.session() as session:
        rekord = await session.get(SaldoKredytow, owner, with_for_update=True)
        if rekord is None:
            rekord = SaldoKredytow(owner_id=owner, saldo=0, przydzielone=0, zuzyte=0)
            session.add(rekord)
            await session.flush()
        # Saldo nie schodzi poniżej zera: przebieg, który przekroczył przydział, kosztuje
        # tyle, ile zostało. Dług na koncie byłby dla użytkownika niezrozumiały.
        faktyczna = zmiana if zmiana >= 0 else -min(-zmiana, int(rekord.saldo))
        rekord.saldo = int(rekord.saldo) + faktyczna
        if faktyczna >= 0:
            rekord.przydzielone = int(rekord.przydzielone) + faktyczna
        else:
            rekord.zuzyte = int(rekord.zuzyte) - faktyczna
        rekord.updated_at = utcnow()
        session.add(
            RuchKredytow(
                owner_id=owner,
                zmiana=faktyczna,
                saldo_po=int(rekord.saldo),
                powod=powod,
                opis=opis[:200],
                run_id=run_id,
                szczegoly=szczegoly or {},
            )
        )
        return int(rekord.saldo)


async def przydziel(
    database: Database, owner: uuid.UUID, ile: int, powod: str, opis: str = ""
) -> int:
    """Dopisuje kredyty do konta (zakup, odnowienie planu, konto testowe, korekta)."""
    if ile <= 0:
        return (await stan(database, owner)).saldo
    return await _zapisz(database, owner, ile, powod, opis)


async def obciaz(
    database: Database, owner: uuid.UUID, ile: int, run_id: uuid.UUID, uzycie: dict[str, Any] | None = None
) -> int:
    """Pomniejsza saldo o koszt zakończonego przebiegu."""
    if ile <= 0:
        return (await stan(database, owner)).saldo
    return await _zapisz(
        database, owner, -ile, "przebieg", "Praca agenta", run_id, {"uzycie": uzycie or {}}
    )


async def przydziel_z_planu(
    database: Database, owner: uuid.UUID, plan_kod: str, powod: str = "plan", probny: bool = False
) -> int:
    """Dopisuje kredyty wynikające z planu (uruchomienie subskrypcji, odnowienie okresu).

    ``probny`` daje zakres okresu próbnego (``probny_kredyty``), który obiecuje cennik.
    Plan bez okresu próbnego nie ma węższego zakresu i dostaje pełny przydział.
    """
    from nexus.platnosci.plany import PLAN_DOMYSLNY, pozycja_katalogu

    pozycja = pozycja_katalogu(plan_kod) or pozycja_katalogu(PLAN_DOMYSLNY)
    if pozycja is None:
        return (await stan(database, owner)).saldo
    if probny and pozycja.okres_probny_dni > 0 and pozycja.probny_kredyty > 0:
        opis = f"Plan {pozycja.nazwa}, okres próbny"
        return await przydziel(database, owner, pozycja.probny_kredyty, powod, opis)
    return await przydziel(database, owner, pozycja.kredyty_okresowo, powod, f"Plan {pozycja.nazwa}")


async def pierwszy_przydzial(
    database: Database, owner: uuid.UUID, plan_kod: str = "", powod: str = "start", probny: bool = True
) -> int:
    """Przydział startowy dla konta, które nigdy żadnego nie dostało.

    Bez tego świeżo założone konto — również konto administratora po instalacji — nie mogłoby
    zlecić ani jednego zadania. Przydział jest jednorazowy: liczy się wcześniejszy przydział
    (``POWODY_PRZYDZIALU``), a nie zerowe saldo po zużyciu. Zakup i wpis zerowy go nie blokują.

    Start to zakres okresu próbnego, nie pełny plan: pełny przydział przychodzi z pierwszą
    opłaconą fakturą. Tej samej funkcji używa faktura otwierająca okres próbny, więc konto,
    które zleciło pracę przed jej nadejściem, nie dostaje zakresu próbnego drugi raz.
    ``probny=False`` daje pełny plan (właściciel instalacji).
    """
    from nexus.platnosci.plany import PLAN_DOMYSLNY

    async with database.session() as session:
        byly_przydzialy = await session.scalar(
            select(func.count())
            .select_from(RuchKredytow)
            .where(
                RuchKredytow.owner_id == owner,
                RuchKredytow.powod.in_(POWODY_PRZYDZIALU),
                RuchKredytow.zmiana > 0,
            )
        )
    if byly_przydzialy:
        return (await stan(database, owner)).saldo
    return await przydziel_z_planu(database, owner, plan_kod or PLAN_DOMYSLNY, powod, probny=probny)


async def sprawdz_przed_zleceniem(database: Database, owner: uuid.UUID) -> None:
    """Zatrzymuje zlecenie, gdy konto nie ma już kredytów."""
    biezace = await stan(database, owner)
    if biezace.saldo >= PROG_ZLECENIA:
        return
    # Konto bez historii dostaje przydział startowy zamiast odmowy. Właściciel instalacji
    # dostaje pełny plan: nie ma okresu próbnego ani faktury, która by go potem uzupełniła.
    saldo = await pierwszy_przydzial(database, owner, probny=owner != ADMIN_OWNER)
    if saldo < PROG_ZLECENIA:
        raise BrakKredytow(saldo)


async def historia(database: Database, owner: uuid.UUID, limit: int = 50) -> list[dict[str, Any]]:
    """Ostatnie zmiany salda — odpowiedź na pytanie „za co zeszły mi kredyty”."""
    async with database.session() as session:
        wiersze = (
            await session.scalars(
                select(RuchKredytow)
                .where(RuchKredytow.owner_id == owner)
                .order_by(RuchKredytow.created_at.desc())
                .limit(min(limit, 200))
            )
        ).all()
    return [
        {
            "id": str(wiersz.id),
            "zmiana": int(wiersz.zmiana),
            "saldo_po": int(wiersz.saldo_po),
            "powod": wiersz.powod,
            "opis": wiersz.opis,
            "run_id": str(wiersz.run_id) if wiersz.run_id else None,
            "kiedy": wiersz.created_at.isoformat(),
        }
        for wiersz in wiersze
    ]


async def suma_zuzycia(database: Database, owner: uuid.UUID) -> int:
    """Łączne zużycie konta (kontrola spójności księgi z saldem)."""
    async with database.session() as session:
        return int(
            await session.scalar(
                select(func.coalesce(func.sum(RuchKredytow.zmiana), 0)).where(
                    RuchKredytow.owner_id == owner, RuchKredytow.zmiana < 0
                )
            )
            or 0
        )


# --- Doładowanie dostępu kwotą, a nie pakietem ---------------------------------------
#
# Użytkownik nie kupuje „kredytów” i nie widzi ich liczby: wpisuje kwotę, za jaką chce
# przedłużyć pracę z Nexusem. Kredyt zostaje jednostką wewnętrzną — tak samo jak koszt
# maszyny nie jest pozycją na paragonie w kawiarni. Przelicznik trzymamy po naszej
# stronie, żeby dało się go zmienić bez tłumaczenia się użytkownikowi z liczb, których
# nigdy nie widział.

#: Najniższa kwota doładowania w groszach. Poniżej opłata Stripe zjada znaczną część
#: wpłaty, a praca i tak nie starcza na nic sensownego.
MINIMUM_DOLADOWANIA_GR = 1_000

#: Największa kwota jednego doładowania — próg zdrowego rozsądku, nie ograniczenie
#: handlowe: chroni przed pomyłką o dwa zera przy ręcznym wpisywaniu.
MAKSIMUM_DOLADOWANIA_GR = 500_000

#: Kwoty szybkiego wyboru w groszach (użytkownik może też wpisać własną).
KWOTY_SZYBKIE_GR: tuple[int, ...] = (2_000, 5_000, 7_000, 15_000)

#: Progi przelicznika: (od ilu groszy, ile kredytów za złotówkę). Im większa wpłata,
#: tym korzystniejszy przelicznik — najwyższy próg zrównuje się ze stawką planu Pro,
#: więc nikt nie traci na tym, że dokupuje zamiast przechodzić wyżej.
PROGI_PRZELICZNIKA: tuple[tuple[int, int], ...] = (
    (50_000, 100),
    (20_000, 80),
    (0, 63),
)


def kredyty_za_kwote(kwota_gr: int) -> int:
    """Ile kredytów dopisujemy za wpłatę w groszach (przelicznik progowy)."""
    if kwota_gr < MINIMUM_DOLADOWANIA_GR:
        return 0
    for prog, za_zlotowke in PROGI_PRZELICZNIKA:
        if kwota_gr >= prog:
            return (kwota_gr * za_zlotowke) // 100
    return 0


def udzial_zuzycia(stan_konta: StanKredytow) -> float:
    """Jaka część przydziału została zużyta — liczba od 0 do 1, bez wartości bezwzględnych.

    Interfejs pokazuje z tego pasek. Gdy konto nie dostało jeszcze żadnego przydziału,
    nie ma czego dzielić i pasek stoi na zerze zamiast na „pełnym zużyciu”.
    """
    if stan_konta.przydzielone <= 0:
        return 0.0
    return min(1.0, stan_konta.zuzyte / stan_konta.przydzielone)
