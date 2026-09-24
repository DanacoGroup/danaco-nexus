"""Usunięcie danych konta: tylko dane tego konta, razem z plikami na dysku; konto właściciela nietykalne."""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from nexus.api.auth import GOSC_DOMENA, GOSC_PLAN, token_hash
from nexus.config import Settings
from nexus.db import ADMIN_OWNER, Conversation, Database, Message, Run, StoredFile, UserSession, utcnow
from nexus.models.portal import PortalUser
from nexus.models.research import KnowledgeCollection, KnowledgeNote
from nexus.storage import FileStorage
from nexus.usuwanie_konta import UsuniecieNiedozwolone, usun_dane_konta, usun_wygasle_konta_probne


@pytest.fixture
def ustawienia(tmp_path: Path) -> Settings:
    # Chmura i indeks wektorowy są niedostępne: te kroki mają się zalogować i nie zatrzymać reszty.
    return Settings(
        data_dir=tmp_path / "dane",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        chmura_url="",
        qdrant_url="http://127.0.0.1:1",
    )


async def _konto_z_danymi(database: Database, magazyn: FileStorage, owner: uuid.UUID) -> Path:
    """Rozmowa z przebiegiem, plik na dysku, kolekcja z notatką i sesja okna aplikacji."""
    file_id, relative, size, digest = magazyn.save_stream(io.BytesIO(b"tresc prywatna"), "notatka.txt", 10**6)
    rozmowa = Conversation(id=uuid.uuid4(), owner_id=owner, title="Rozmowa")
    kolekcja = KnowledgeCollection(owner_id=owner, name="Ogólne")
    async with database.session() as session:
        session.add_all([rozmowa, kolekcja])
        await session.flush()
        przebieg = Run(conversation_id=rozmowa.id)
        session.add(przebieg)
        await session.flush()
        session.add_all(
            [
                Message(conversation_id=rozmowa.id, run_id=przebieg.id, role="user", kind="user", content=[]),
                StoredFile(
                    id=file_id,
                    conversation_id=rozmowa.id,
                    owner_id=owner,
                    origin="upload",
                    name="notatka.txt",
                    mime="text/plain",
                    size=size,
                    sha256=digest,
                    storage_path=relative,
                ),
                KnowledgeNote(collection_id=kolekcja.id, title="Notatka", content="Wnioski"),
                UserSession(
                    token_hash=token_hash(uuid.uuid4().hex),
                    owner_id=owner,
                    expires_at=utcnow() + timedelta(days=1),
                ),
            ]
        )
    return magazyn.root / relative


async def _liczba(database: Database, model: type, **warunki: object) -> int:
    async with database.session() as session:
        zapytanie = select(func.count()).select_from(model)
        for pole, wartosc in warunki.items():
            zapytanie = zapytanie.where(getattr(model, pole) == wartosc)
        return int(await session.scalar(zapytanie) or 0)


def test_usuwa_dane_konta_i_zostawia_cudze(ustawienia: Settings) -> None:
    async def run() -> None:
        database = Database(ustawienia.database_url)
        await database.create_schema()
        magazyn = FileStorage(ustawienia.files_dir)
        klient, inny = uuid.uuid4(), uuid.uuid4()
        plik_klienta = await _konto_z_danymi(database, magazyn, klient)
        plik_innego = await _konto_z_danymi(database, magazyn, inny)
        assert plik_klienta.is_file() and plik_innego.is_file()

        wynik = await usun_dane_konta(ustawienia, database, klient)

        assert wynik == {"rozmowy": 1, "pliki": 1, "kolekcje": 1}
        assert not plik_klienta.exists(), "plik konta ma zniknąć z dysku"
        assert plik_innego.is_file(), "pliki innego konta zostają"
        for model in (Conversation, StoredFile, KnowledgeCollection, UserSession):
            assert await _liczba(database, model, owner_id=klient) == 0, model.__name__
            assert await _liczba(database, model, owner_id=inny) == 1, model.__name__
        assert await _liczba(database, Run) == 1 and await _liczba(database, Message) == 1
        assert await _liczba(database, KnowledgeNote) == 1
        await database.close()

    asyncio.run(run())


def test_danych_wlasciciela_instalacji_nie_da_sie_usunac(ustawienia: Settings) -> None:
    async def run() -> None:
        database = Database(ustawienia.database_url)
        await database.create_schema()
        with pytest.raises(UsuniecieNiedozwolone):
            await usun_dane_konta(ustawienia, database, ADMIN_OWNER)
        await database.close()

    asyncio.run(run())


def test_sprzatanie_usuwa_tylko_wygasle_konta_probne(ustawienia: Settings) -> None:
    async def run() -> None:
        database = Database(ustawienia.database_url)
        await database.create_schema()
        dawno = utcnow() - timedelta(days=5)

        def gosc(znacznik: str, utworzone: object) -> PortalUser:
            return PortalUser(
                email=f"probny-{znacznik}@{GOSC_DOMENA}",
                password_hash="x",
                name="Konto próbne",
                plan=GOSC_PLAN,
                active=True,
                created_at=utworzone,
            )

        wygasly, z_sesja, swiezy = gosc("a", dawno), gosc("b", dawno), gosc("c", utcnow())
        klient = PortalUser(
            email="klient@example.com",
            password_hash="x",
            name="Klient",
            plan="start",
            active=True,
            created_at=dawno,
        )
        async with database.session() as session:
            session.add_all([wygasly, z_sesja, swiezy, klient])
            await session.flush()
            session.add_all(
                [
                    Conversation(id=uuid.uuid4(), owner_id=wygasly.id, title="Próba"),
                    UserSession(
                        token_hash=token_hash("aktywna"),
                        owner_id=z_sesja.id,
                        expires_at=utcnow() + timedelta(hours=3),
                    ),
                ]
            )

        assert await usun_wygasle_konta_probne(ustawienia, database) == 1
        async with database.session() as session:
            zostaly = set((await session.scalars(select(PortalUser.email))).all())
        assert zostaly == {z_sesja.email, swiezy.email, klient.email}
        assert await _liczba(database, Conversation, owner_id=wygasly.id) == 0
        await database.close()

    asyncio.run(run())
