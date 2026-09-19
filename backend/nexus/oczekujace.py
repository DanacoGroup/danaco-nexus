"""Działania czekające na zatwierdzenie użytkownika (wysłanie e-maila, usunięcie wydarzenia).

Narzędzia agenta tylko zapisują propozycję; wykonuje ją API po kliknięciu
użytkownika w module Poczta albo Kalendarz.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import select

from nexus.config import Settings
from nexus.db import Database, utcnow
from nexus.models.biuro import PendingAction

KINDS = frozenset({"mail", "kalendarz_usun"})


def payload(record: PendingAction) -> dict[str, Any]:
    """Opis działania dla interfejsu."""
    return {
        "id": str(record.id),
        "kind": record.kind,
        "status": record.status,
        "summary": record.summary,
        "payload": record.payload or {},
        "run_id": str(record.run_id) if record.run_id else None,
        "error": record.error,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


async def create(
    database: Database, kind: str, summary: str, data: dict[str, Any], run_id: uuid.UUID | None = None
) -> PendingAction:
    """Zapisuje nowe działanie oczekujące."""
    if kind not in KINDS:
        raise ValueError(f"Nieznany rodzaj działania: {kind}")
    record = PendingAction(kind=kind, summary=summary[:300], payload=data, run_id=run_id)
    async with database.session() as session:
        session.add(record)
    return record


async def list_pending(database: Database, kind: str, include_finished: bool = False) -> list[PendingAction]:
    """Działania danego rodzaju od najnowszego."""
    query = select(PendingAction).where(PendingAction.kind == kind)
    if not include_finished:
        query = query.where(PendingAction.status == "pending")
    async with database.session() as session:
        return list((await session.scalars(query.order_by(PendingAction.created_at.desc()).limit(200))).all())


async def get(database: Database, action_id: uuid.UUID, kind: str) -> PendingAction | None:
    """Działanie o podanym identyfikatorze (tylko wskazanego rodzaju)."""
    async with database.session() as session:
        record = await session.get(PendingAction, action_id)
    return record if record is not None and record.kind == kind else None


async def update(database: Database, action_id: uuid.UUID, **values: Any) -> PendingAction | None:
    """Zmienia pola działania; zwraca rekord po zmianie."""
    async with database.session() as session:
        record = await session.get(PendingAction, action_id)
        if record is None:
            return None
        for key, value in values.items():
            setattr(record, key, value)
        record.updated_at = utcnow()
    return record


async def claim(database: Database, action_id: uuid.UUID, kind: str) -> PendingAction | None:
    """Oznacza oczekujące działanie jako wykonywane (chroni przed podwójnym wysłaniem)."""
    async with database.session() as session:
        record = await session.get(PendingAction, action_id, with_for_update=True)
        if record is None or record.kind != kind or record.status != "pending":
            return None
        record.status = "running"
        record.updated_at = utcnow()
    return record


def create_sync(settings: Settings, kind: str, summary: str, data: dict[str, Any], run_id: uuid.UUID) -> str:
    """Wersja dla narzędzi agenta (wątek puli, bez pętli zdarzeń); zwraca identyfikator."""

    async def run() -> str:
        database = Database(settings.database_url)
        try:
            record = await create(database, kind, summary, data, run_id)
            return str(record.id)
        finally:
            await database.close()

    return asyncio.run(run())
