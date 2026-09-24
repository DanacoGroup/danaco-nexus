"""Usunięcie danych konta klienta: rozmowy, pliki, baza wiedzy, strony, projekty, chmura.

Konto portalu jest kontem aplikacji. Samo skasowanie konta (logowanie, sesje portalu) zostawiało
na serwerze rozmowy, pliki i przestrzeń w chmurze, do których nikt już nie miał dostępu, a sesja
aplikacji działała dalej do wygaśnięcia. Regulamin i polityka prywatności mówią o przechowywaniu
„do czasu usunięcia konta”, a konto próbne ma znikać po dwóch dniach razem z rozmowami i plikami.

Zostają dane rozliczeniowe (subskrypcje, faktury) — obowiązek przechowywania dokumentów
księgowych jest niezależny od konta. Konto właściciela instalacji nie da się tędy usunąć.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import delete, select

from nexus.config import Settings
from nexus.db import (
    ADMIN_OWNER,
    Conversation,
    Database,
    DeviceToken,
    Message,
    Run,
    RunEvent,
    StoredFile,
    ToolCall,
    UserSession,
    utcnow,
)
from nexus.models.agenci import AgentUzytkownika
from nexus.models.biuro import PendingAction
from nexus.models.grupy import CzlonekGrupy, Grupa, ZaproszenieGrupy
from nexus.models.pliki import KatalogPlikow
from nexus.models.push import PushSubscription
from nexus.models.research import KnowledgeCollection, KnowledgeNote, KnowledgeSource, ResearchReport
from nexus.models.ustawienia import UstawieniaKonta
from nexus.storage import FileStorage

logger = logging.getLogger(__name__)


class UsuniecieNiedozwolone(ValueError):
    """Konto, którego dane nie mogą zostać usunięte tą drogą."""


async def usun_dane_konta(
    settings: Settings,
    database: Database,
    owner: uuid.UUID,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, int]:
    """Usuwa wszystkie dane konta poza rozliczeniowymi; zwraca liczby usuniętych pozycji.

    Baza jest czyszczona w jednej transakcji. Pliki na dysku, indeks wektorowy, strony,
    projekty, poczta i chmura — po niej; błąd któregoś z tych kroków trafia do dziennika
    i nie cofa pozostałych, bo konto i tak przestało istnieć.
    """
    if owner == ADMIN_OWNER:
        raise UsuniecieNiedozwolone("Danych właściciela instalacji nie usuwa się z poziomu konta.")
    wynik: dict[str, int] = {}
    pliki_na_dysku: list[StoredFile] = []
    async with database.session() as session:
        rozmowy = list(
            (await session.scalars(select(Conversation.id).where(Conversation.owner_id == owner))).all()
        )
        przebiegi = (
            list((await session.scalars(select(Run.id).where(Run.conversation_id.in_(rozmowy)))).all())
            if rozmowy
            else []
        )
        if przebiegi:
            await session.execute(delete(ToolCall).where(ToolCall.run_id.in_(przebiegi)))
            await session.execute(delete(RunEvent).where(RunEvent.run_id.in_(przebiegi)))
            await session.execute(delete(Run).where(Run.id.in_(przebiegi)))
        pliki_na_dysku = list(
            (await session.scalars(select(StoredFile).where(StoredFile.owner_id == owner))).all()
        )
        await session.execute(delete(StoredFile).where(StoredFile.owner_id == owner))
        if rozmowy:
            await session.execute(delete(Message).where(Message.conversation_id.in_(rozmowy)))
            await session.execute(delete(ResearchReport).where(ResearchReport.conversation_id.in_(rozmowy)))
            await session.execute(delete(Conversation).where(Conversation.id.in_(rozmowy)))
        await session.execute(delete(KatalogPlikow).where(KatalogPlikow.owner_id == owner))

        kolekcje = list(
            (
                await session.scalars(
                    select(KnowledgeCollection.id).where(KnowledgeCollection.owner_id == owner)
                )
            ).all()
        )
        if kolekcje:
            await session.execute(delete(KnowledgeNote).where(KnowledgeNote.collection_id.in_(kolekcje)))
            await session.execute(delete(KnowledgeSource).where(KnowledgeSource.collection_id.in_(kolekcje)))
            await session.execute(delete(KnowledgeCollection).where(KnowledgeCollection.id.in_(kolekcje)))

        grupy = list((await session.scalars(select(Grupa.id).where(Grupa.zalozyciel_id == owner))).all())
        if grupy:
            await session.execute(delete(ZaproszenieGrupy).where(ZaproszenieGrupy.grupa_id.in_(grupy)))
            await session.execute(delete(CzlonekGrupy).where(CzlonekGrupy.grupa_id.in_(grupy)))
            await session.execute(delete(Grupa).where(Grupa.id.in_(grupy)))
        await session.execute(delete(CzlonekGrupy).where(CzlonekGrupy.uzytkownik_id == owner))

        await session.execute(delete(AgentUzytkownika).where(AgentUzytkownika.owner_id == owner))
        await session.execute(delete(UstawieniaKonta).where(UstawieniaKonta.owner_id == owner))
        await session.execute(delete(UserSession).where(UserSession.owner_id == owner))
        await session.execute(delete(DeviceToken).where(DeviceToken.owner_id == owner))
        await session.execute(delete(PushSubscription).where(PushSubscription.owner_id == owner))
        await session.execute(delete(PendingAction).where(PendingAction.owner_id == owner))
        wynik.update(rozmowy=len(rozmowy), pliki=len(pliki_na_dysku), kolekcje=len(kolekcje))

    magazyn = FileStorage(settings.files_dir)
    for rekord in pliki_na_dysku:
        try:
            magazyn.delete(rekord)
        except OSError as blad:
            logger.warning("Plik %s konta %s został na dysku: %s", rekord.id, owner, blad)

    await _krok("indeks wektorowy", _usun_z_indeksu(settings, owner))
    await _krok("strony", asyncio.to_thread(_usun_strony, settings, owner))
    await _krok("projekty", asyncio.to_thread(_usun_projekty, settings, owner))
    await _krok("poczta", asyncio.to_thread(_usun_poczte, settings, owner))
    await _krok("kalendarz", asyncio.to_thread(_usun_kalendarze, settings, owner))
    await _krok("chmura", _usun_chmure(settings, owner, transport))
    logger.info("Usunięto dane konta %s: %s", owner, wynik)
    return wynik


async def _krok(nazwa: str, zadanie: Any) -> None:
    try:
        await zadanie
    except Exception as blad:  # noqa: BLE001 - jeden nieudany krok nie może zostawić reszty danych
        logger.warning("Usuwanie danych konta — krok „%s” nie powiódł się: %s", nazwa, blad)


async def _usun_z_indeksu(settings: Settings, owner: uuid.UUID) -> None:
    from nexus.knowledge import KnowledgeBase

    baza = KnowledgeBase(
        settings.qdrant_url,
        settings.qdrant_collection,
        settings.embedding_model,
        settings.cache_dir / "fastembed",
    )
    await asyncio.to_thread(baza.usun_konto, owner)


def _usun_strony(settings: Settings, owner: uuid.UUID) -> None:
    from nexus.tworczy.strony import site_store

    magazyn = site_store(settings, owner)
    for strona in magazyn.list_sites():
        magazyn.delete_site(strona["address"])


def _usun_projekty(settings: Settings, owner: uuid.UUID) -> None:
    from nexus.agent.przestrzenie import projekty_konta, zapomnij_projekt

    for katalog in projekty_konta(settings, owner):
        shutil.rmtree(katalog, ignore_errors=True)
        zapomnij_projekt(settings, katalog.name)


def _usun_poczte(settings: Settings, owner: uuid.UUID) -> None:
    from nexus.mail import config_path

    config_path(settings, owner).unlink(missing_ok=True)


def _usun_kalendarze(settings: Settings, owner: uuid.UUID) -> None:
    from nexus.calendar import CalendarClient, CalendarNotConfigured

    try:
        klient = CalendarClient(settings, owner=owner)
    except CalendarNotConfigured:
        return
    with klient:
        klient.usun_kalendarze_konta()


async def _usun_chmure(
    settings: Settings, owner: uuid.UUID, transport: httpx.AsyncBaseTransport | None
) -> None:
    """Konto Nextcloud klienta (plan z synchronizacją) albo jego folder w koncie technicznym."""
    from urllib.parse import quote

    from nexus.chmura_konta import konto_chmury, occ_uslugi, usun_haslo
    from nexus.tools.cloud import katalog_konta

    konto = konto_chmury(settings, owner)
    if konto is not None:
        kod, wyjscie = await occ_uslugi(settings)(["user:delete", konto.uid], {})
        if kod != 0 and "does not exist" not in wyjscie:
            raise RuntimeError(f"occ user:delete {konto.uid}: {wyjscie.strip()[-200:]}")
        usun_haslo(settings, konto.uid)
    try:
        token = settings.chmura_token_file.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if not settings.chmura_url or not token:
        return
    adres = (
        f"{settings.chmura_url.rstrip('/')}/remote.php/dav/files/"
        f"{quote(settings.chmura_user)}{quote(katalog_konta(owner))}"
    )
    async with httpx.AsyncClient(auth=(settings.chmura_user, token), timeout=60, transport=transport) as http:
        odpowiedz = await http.request("DELETE", adres)
    if odpowiedz.status_code not in (204, 404):
        raise RuntimeError(f"folder chmury konta został ({odpowiedz.status_code})")


#: Jak długo zostaje historia zatwierdzonych i odrzuconych działań (szkiców maili, usunięć).
HISTORIA_DZIALAN_DNI = 30


async def sprzataj_przeterminowane(database: Database) -> dict[str, int]:
    """Kasuje wygasłe sesje aplikacji i starą historię działań oczekujących.

    Polityka prywatności podaje dla sesji „do wygaśnięcia”, a dla działań do zatwierdzenia
    — czas do decyzji i 30 dni historii. Bez tego wpisy (w tym treść szkiców maili) zostawały
    w bazie na zawsze.
    """
    teraz = utcnow()
    async with database.session() as session:
        sesje = await session.execute(delete(UserSession).where(UserSession.expires_at < teraz))
        dzialania = await session.execute(
            delete(PendingAction).where(
                PendingAction.status.in_(("done", "cancelled")),
                PendingAction.updated_at < teraz - timedelta(days=HISTORIA_DZIALAN_DNI),
            )
        )
    return {"sesje": sesje.rowcount or 0, "dzialania": dzialania.rowcount or 0}


async def usun_wygasle_konta_probne(settings: Settings, database: Database) -> int:
    """Usuwa konta próbne starsze niż ich czas życia — razem z rozmowami i plikami.

    Konto próbne ma sesję na ``GOSC_DNI`` dni i nie da się do niego wrócić po jej wygaśnięciu
    (hasło jest losowe i nigdzie nie ujawnione), a portal obiecuje, że rozmowy i pliki znikają
    razem z nim. Usuwane jest wyłącznie konto z planem próbnym i adresem technicznym gościa.
    """
    from nexus.api.auth import GOSC_DNI, GOSC_DOMENA, GOSC_PLAN
    from nexus.models.portal import PortalUser
    from nexus.portal.konta import usun_konto

    granica = utcnow() - timedelta(days=GOSC_DNI)
    async with database.session() as session:
        konta = list(
            (
                await session.scalars(
                    select(PortalUser).where(
                        PortalUser.plan == GOSC_PLAN,
                        PortalUser.email.endswith(f"@{GOSC_DOMENA}"),
                        PortalUser.created_at < granica,
                    )
                )
            ).all()
        )
    usuniete = 0
    for konto in konta:
        async with database.session() as session:
            aktywna = await session.scalar(
                select(UserSession.token_hash)
                .where(UserSession.owner_id == konto.id, UserSession.expires_at > utcnow())
                .limit(1)
            )
        if aktywna is not None:
            continue
        await usun_dane_konta(settings, database, konto.id)
        async with database.session() as session:
            rekord = await session.get(PortalUser, konto.id)
            if rekord is not None:
                await usun_konto(session, rekord)
        usuniete += 1
    if usuniete:
        logger.info("Usunięto %d wygasłych kont próbnych.", usuniete)
    return usuniete
