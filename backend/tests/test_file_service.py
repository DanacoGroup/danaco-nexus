"""Pliki widziane przez narzędzia: tylko pliki konta, dla którego pracuje narzędzie."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from nexus.db import ADMIN_OWNER, Database, StoredFile
from nexus.file_service import FileService
from nexus.storage import FileStorage
from nexus.tools.base import OutputFile, ToolError


def test_wyniki_naleza_do_konta_i_obce_konto_ich_nie_otworzy(tmp_path: Path) -> None:
    async def run() -> None:
        database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'pliki.db').as_posix()}")
        await database.create_schema()
        magazyn = FileStorage(tmp_path / "magazyn")
        klient = uuid.uuid4()
        wynik = tmp_path / "wynik.txt"
        wynik.write_text("wynik zlecenia klienta", encoding="utf-8")

        zapisane = await FileService(database, magazyn, klient).store_outputs(
            uuid.uuid4(), None, [OutputFile(wynik, "wynik.txt", "Wynik")]
        )
        identyfikator = uuid.UUID(zapisane[0]["id"])
        async with database.session() as session:
            rekord = await session.get(StoredFile, identyfikator)
        # Plik ma należeć do klienta — inaczej API plików odmawia mu pobrania własnego wyniku.
        assert rekord is not None and rekord.owner_id == klient

        assert (await FileService(database, magazyn, klient).resolve(identyfikator)).name == "wynik.txt"
        with pytest.raises(ToolError, match="nie istnieje"):
            await FileService(database, magazyn, ADMIN_OWNER).resolve(identyfikator)
        with pytest.raises(ToolError, match="nie istnieje"):
            await FileService(database, magazyn, uuid.uuid4()).resolve(identyfikator)
        await database.close()

    asyncio.run(run())
