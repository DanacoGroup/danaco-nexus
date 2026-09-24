"""Działania oczekujące (szkice maili, usunięcia wydarzeń) widzi i wykonuje tylko konto, które je zleciło."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from nexus import oczekujace
from nexus.db import Database


def test_oczekujace_nie_przeciekaja_miedzy_kontami(tmp_path: Path) -> None:
    async def run() -> None:
        database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}")
        await database.create_schema()
        autor, obcy = uuid.uuid4(), uuid.uuid4()
        szkic = await oczekujace.create(
            database, "mail", "Do: zarzad@example.com — wyniki", {"to": ["zarzad@example.com"]}, owner=autor
        )

        assert [r.id for r in await oczekujace.list_pending(database, "mail", autor)] == [szkic.id]
        assert await oczekujace.list_pending(database, "mail", obcy) == []
        assert await oczekujace.get(database, szkic.id, "mail", obcy) is None
        assert await oczekujace.claim(database, szkic.id, "mail", obcy) is None
        assert (await oczekujace.claim(database, szkic.id, "mail", autor)) is not None
        await database.close()

    asyncio.run(run())


def test_zadanie_modulu_widzi_tylko_konto_ktore_je_zlecilo() -> None:
    import pytest
    from fastapi import HTTPException

    from nexus.tworczy.zadania import JobRegistry

    async def run() -> None:
        rejestr = JobRegistry()
        autor, obcy = uuid.uuid4(), uuid.uuid4()

        async def praca(_zadanie: object) -> dict[str, object]:
            return {"files": []}

        zadanie = rejestr.start("remove_background", praca, autor)
        await asyncio.sleep(0)
        assert rejestr.get(zadanie.id, autor) is zadanie
        with pytest.raises(HTTPException):
            rejestr.get(zadanie.id, obcy)
        with pytest.raises(HTTPException):
            rejestr.cancel(zadanie.id, obcy)
        await rejestr.close()

    asyncio.run(run())
