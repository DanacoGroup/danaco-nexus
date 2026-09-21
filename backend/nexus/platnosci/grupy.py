"""Grupa: wspólna pula dostępu, miejsca i przekazanie roli założyciela.

Plan „Grupa” kosztuje za każdego użytkownika, a dostęp kupuje jeden — założyciel. Tutaj
leży mechanika, która to realizuje. Najważniejsza jest jedna funkcja:
``konto_rozliczeniowe`` — konto, z którego schodzi praca. Dla osoby prywatnej to ona sama,
dla członka grupy to założyciel. Wszystko inne (zaproszenia, miejsca, przekazanie roli)
obsługuje ten sam plik, żeby reguły grupy nie rozłaziły się po module płatności.

Zasady, których pilnują funkcje niżej:

* konto należy najwyżej do jednej grupy (warunek jednoznaczności w tabeli);
* liczba miejsc bierze się z planu założyciela, nie z ustawienia w grupie;
* założyciel jest dokładnie jeden — przekazanie roli zamienia ją z członkiem, a nie dodaje
  drugiego założyciela;
* zaproszenie jest jednorazowe, wygasa i w bazie leży wyłącznie jako skrót tokenu.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select

from nexus.db import Database, utcnow
from nexus.models.grupy import (
    MIEJSC_DOMYSLNIE,
    ROLA_CZLONEK,
    ROLA_ZALOZYCIEL,
    WAZNOSC_ZAPROSZENIA_DNI,
    CzlonekGrupy,
    Grupa,
    ZaproszenieGrupy,
)
from nexus.models.portal import PortalUser
from nexus.platnosci.plany import pozycja_katalogu

#: Plan, który w ogóle pozwala założyć grupę.
PLAN_GRUPY = "zespol"


class BladGrupy(Exception):
    """Powód odmowy opisany dla użytkownika (trafia do interfejsu bez zmian)."""


@dataclass(frozen=True)
class CzlonekOpis:
    """Członek grupy w postaci pokazywanej w interfejsie."""

    uzytkownik_id: uuid.UUID
    email: str
    nazwa: str
    rola: str


def _skrot(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def miejsca_planu(plan_kod: str) -> int:
    """Ile kont mieści się w grupie przy tym planie (gdy nie ma opłaconej subskrypcji)."""
    pozycja = pozycja_katalogu(plan_kod)
    if pozycja is None:
        return MIEJSC_DOMYSLNIE
    return int(pozycja.limity.get("konta") or MIEJSC_DOMYSLNIE)


async def miejsca_grupy(database: Database, zalozyciel: uuid.UUID) -> int:
    """Liczba miejsc, za które naprawdę zapłacono.

    Plan „Grupa” kosztuje za każdego użytkownika i liczbę miejsc ustala kupujący w kasie
    Stripe. Bierzemy ją z subskrypcji, a nie z limitu planu — limit jest tylko wartością
    zastępczą, dopóki subskrypcji nie ma (konto testowe, okres przed pierwszą płatnością).
    """
    from nexus.platnosci.model import Subskrypcja

    async with database.session() as session:
        rekord = await session.scalar(
            select(Subskrypcja).where(Subskrypcja.uzytkownik == str(zalozyciel))
        )
    if rekord is not None and rekord.plan_kod == PLAN_GRUPY and rekord.miejsca > 1:
        return rekord.miejsca
    return miejsca_planu(PLAN_GRUPY)


async def czlonkostwo(database: Database, uzytkownik: uuid.UUID) -> CzlonekGrupy | None:
    """Wpis przynależności konta do grupy albo ``None``."""
    async with database.session() as session:
        return await session.scalar(
            select(CzlonekGrupy).where(CzlonekGrupy.uzytkownik_id == uzytkownik)
        )


async def konto_rozliczeniowe(database: Database, uzytkownik: uuid.UUID) -> uuid.UUID:
    """Konto, z którego schodzi praca tego użytkownika.

    Dla osoby poza grupą — ona sama. Dla członka grupy — założyciel, bo to jego pulę
    dostępu kupiono dla całej grupy. Założyciel rozlicza się sam ze sobą.
    """
    wpis = await czlonkostwo(database, uzytkownik)
    if wpis is None:
        return uzytkownik
    async with database.session() as session:
        grupa = await session.get(Grupa, wpis.grupa_id)
    return grupa.zalozyciel_id if grupa is not None else uzytkownik


async def grupa_uzytkownika(database: Database, uzytkownik: uuid.UUID) -> Grupa | None:
    """Grupa, do której należy konto (jako założyciel albo członek)."""
    wpis = await czlonkostwo(database, uzytkownik)
    if wpis is None:
        return None
    async with database.session() as session:
        return await session.get(Grupa, wpis.grupa_id)


async def czlonkowie(database: Database, grupa_id: uuid.UUID) -> list[CzlonekOpis]:
    """Skład grupy z adresami i nazwami kont; założyciel zawsze pierwszy."""
    async with database.session() as session:
        wpisy = (
            await session.scalars(select(CzlonekGrupy).where(CzlonekGrupy.grupa_id == grupa_id))
        ).all()
        konta = {
            konto.id: konto
            for konto in (
                await session.scalars(
                    select(PortalUser).where(PortalUser.id.in_([w.uzytkownik_id for w in wpisy]))
                )
            ).all()
        }
    opisy = [
        CzlonekOpis(
            uzytkownik_id=wpis.uzytkownik_id,
            email=konta[wpis.uzytkownik_id].email if wpis.uzytkownik_id in konta else "",
            nazwa=konta[wpis.uzytkownik_id].name if wpis.uzytkownik_id in konta else "",
            rola=wpis.rola,
        )
        for wpis in wpisy
    ]
    return sorted(opisy, key=lambda o: (o.rola != ROLA_ZALOZYCIEL, o.email))


async def zaloz(database: Database, zalozyciel: uuid.UUID, nazwa: str = "") -> Grupa:
    """Zakłada grupę. Wymaga planu grupowego i wolnego konta (nikt nie jest w dwóch grupach)."""
    async with database.session() as session:
        konto = await session.get(PortalUser, zalozyciel)
    if konto is None:
        # Konto administratora instalacji nie jest kontem klienta: nie ma planu, nie ma
        # subskrypcji i nie ma czego rozliczać. Grupę zakłada się z konta założonego
        # w portalu — to ono kupuje plan i to z jego puli schodzi praca grupy.
        raise BladGrupy(
            "Grupę zakłada się z konta klienta założonego w portalu, na planie Grupa. "
            "To konto nie jest kontem klienta."
        )
    if (konto.plan or "").strip().lower() != PLAN_GRUPY:
        raise BladGrupy("Grupę zakłada się na planie Grupa — najpierw zmień plan.")
    if await czlonkostwo(database, zalozyciel) is not None:
        raise BladGrupy("To konto już należy do grupy.")
    grupa = Grupa(zalozyciel_id=zalozyciel, nazwa=(nazwa or "").strip()[:120])
    async with database.session() as session:
        session.add(grupa)
        await session.flush()
        session.add(
            CzlonekGrupy(grupa_id=grupa.id, uzytkownik_id=zalozyciel, rola=ROLA_ZALOZYCIEL)
        )
    return grupa


async def _sprawdz_zalozyciela(database: Database, grupa: Grupa, kto: uuid.UUID) -> None:
    if grupa.zalozyciel_id != kto:
        raise BladGrupy("To może zrobić wyłącznie założyciel grupy.")


async def zapros(database: Database, grupa: Grupa, zapraszajacy: uuid.UUID, email: str) -> str:
    """Tworzy jednorazowe zaproszenie i zwraca token do wysłania na podany adres."""
    await _sprawdz_zalozyciela(database, grupa, zapraszajacy)
    adres = (email or "").strip().lower()
    if "@" not in adres or len(adres) > 320:
        raise BladGrupy("Podaj poprawny adres e-mail.")

    miejsca = await miejsca_grupy(database, grupa.zalozyciel_id)
    obecni = await czlonkowie(database, grupa.id)
    oczekujace = await zaproszenia_oczekujace(database, grupa.id)
    if len(obecni) + len(oczekujace) >= miejsca:
        raise BladGrupy(
            f"Grupa ma {miejsca} miejsc i wszystkie są zajęte albo zaproszone. "
            "Usuń kogoś albo odwołaj zaproszenie."
        )
    if any(pozycja.email == adres for pozycja in obecni):
        raise BladGrupy("Ta osoba już jest w grupie.")

    token = secrets.token_urlsafe(32)
    async with database.session() as session:
        session.add(
            ZaproszenieGrupy(
                token_hash=_skrot(token),
                grupa_id=grupa.id,
                email=adres,
                zaprosil_id=zapraszajacy,
                wygasa_at=utcnow() + timedelta(days=WAZNOSC_ZAPROSZENIA_DNI),
            )
        )
    return token


async def zaproszenia_oczekujace(database: Database, grupa_id: uuid.UUID) -> list[ZaproszenieGrupy]:
    """Zaproszenia jeszcze nieprzyjęte i jeszcze ważne."""
    teraz = utcnow()
    async with database.session() as session:
        wszystkie = (
            await session.scalars(
                select(ZaproszenieGrupy).where(ZaproszenieGrupy.grupa_id == grupa_id)
            )
        ).all()
    return [z for z in wszystkie if z.przyjete_at is None and z.wygasa_at > teraz]


async def przyjmij(database: Database, token: str, uzytkownik: uuid.UUID) -> Grupa:
    """Przyjmuje zaproszenie: konto wchodzi do grupy i od tej chwili pracuje na jej puli."""
    async with database.session() as session:
        zaproszenie = await session.get(ZaproszenieGrupy, _skrot(token))
    if zaproszenie is None:
        raise BladGrupy("Zaproszenie jest nieznane albo zostało już wykorzystane.")
    if zaproszenie.przyjete_at is not None:
        raise BladGrupy("To zaproszenie zostało już wykorzystane.")
    if zaproszenie.wygasa_at <= utcnow():
        raise BladGrupy("Zaproszenie straciło ważność — poproś o nowe.")
    if await czlonkostwo(database, uzytkownik) is not None:
        raise BladGrupy("To konto już należy do grupy — najpierw z niej wyjdź.")

    async with database.session() as session:
        konto = await session.get(PortalUser, uzytkownik)
        if konto is None:
            raise BladGrupy("Nie znaleziono konta.")
        # Zaproszenie idzie na konkretny adres; przyjęcie z innego konta byłoby
        # wejściem do cudzej grupy na cudzy rachunek.
        if konto.email.strip().lower() != zaproszenie.email:
            raise BladGrupy("Zaproszenie wystawiono na inny adres e-mail.")
        grupa = await session.get(Grupa, zaproszenie.grupa_id)
        if grupa is None:
            raise BladGrupy("Grupa już nie istnieje.")
        session.add(CzlonekGrupy(grupa_id=grupa.id, uzytkownik_id=uzytkownik, rola=ROLA_CZLONEK))
        wpis = await session.get(ZaproszenieGrupy, _skrot(token))
        if wpis is not None:
            wpis.przyjete_at = utcnow()
    return grupa


async def usun_czlonka(database: Database, grupa: Grupa, kto: uuid.UUID, kogo: uuid.UUID) -> None:
    """Usuwa członka z grupy. Założyciela nie da się usunąć — najpierw przekazuje rolę."""
    if kto != kogo:
        await _sprawdz_zalozyciela(database, grupa, kto)
    if kogo == grupa.zalozyciel_id:
        raise BladGrupy(
            "Założyciel nie może wyjść z grupy, dopóki nie przekaże roli komuś innemu."
        )
    async with database.session() as session:
        await session.execute(
            delete(CzlonekGrupy).where(
                CzlonekGrupy.grupa_id == grupa.id, CzlonekGrupy.uzytkownik_id == kogo
            )
        )


async def przekaz_zalozyciela(database: Database, grupa: Grupa, kto: uuid.UUID, komu: uuid.UUID) -> None:
    """Przekazuje rolę założyciela innemu członkowi grupy (role się zamieniają).

    Od tej chwili to nowy założyciel płaci i jego pula obsługuje grupę — dlatego rola
    wędruje w całości, a nie w postaci drugiego założyciela obok pierwszego.
    """
    await _sprawdz_zalozyciela(database, grupa, kto)
    if komu == kto:
        raise BladGrupy("Ta osoba już jest założycielem.")
    async with database.session() as session:
        nowy = await session.scalar(
            select(CzlonekGrupy).where(
                CzlonekGrupy.grupa_id == grupa.id, CzlonekGrupy.uzytkownik_id == komu
            )
        )
        if nowy is None:
            raise BladGrupy("Ta osoba nie należy do grupy.")
        stary = await session.scalar(
            select(CzlonekGrupy).where(
                CzlonekGrupy.grupa_id == grupa.id, CzlonekGrupy.uzytkownik_id == kto
            )
        )
        nowy.rola = ROLA_ZALOZYCIEL
        if stary is not None:
            stary.rola = ROLA_CZLONEK
        rekord = await session.get(Grupa, grupa.id)
        if rekord is not None:
            rekord.zalozyciel_id = komu
            rekord.updated_at = utcnow()


async def rozwiaz(database: Database, grupa: Grupa, kto: uuid.UUID) -> None:
    """Rozwiązuje grupę — członkowie wracają do rozliczania się na własnych kontach."""
    await _sprawdz_zalozyciela(database, grupa, kto)
    async with database.session() as session:
        await session.execute(delete(CzlonekGrupy).where(CzlonekGrupy.grupa_id == grupa.id))
        await session.execute(delete(ZaproszenieGrupy).where(ZaproszenieGrupy.grupa_id == grupa.id))
        rekord = await session.get(Grupa, grupa.id)
        if rekord is not None:
            await session.delete(rekord)
