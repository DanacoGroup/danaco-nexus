"""Zadania w toku: wszystkie rozmowy z oczekującym albo trwającym zadaniem (wiele sesji naraz)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from nexus.api.auth import require_session, wlasciciel
from nexus.db import Conversation, Database, Run, RunEvent

router = APIRouter(prefix="/api/w-toku", tags=["w-toku"], dependencies=[Depends(require_session)])

ACTIVE_STATUSES = ("queued", "running")
TOOL_EVENTS = ("tool.started", "tool.pending")


@router.get("")
async def active_runs(request: Request, owner: uuid.UUID = Depends(wlasciciel)) -> list[dict[str, Any]]:
    """Trwające zadania konta, od najstarszego, z tytułem rozmowy i ostatnio użytym narzędziem.

    Tytuł rozmowy jest treścią użytkownika, więc lista niesie wyłącznie przebiegi z rozmów
    tego konta — sama ważna sesja pokazywała zadania całej instalacji.
    """
    database: Database = request.app.state.database
    async with database.session() as session:
        rows = (
            await session.execute(
                select(Run, Conversation)
                .join(Conversation, Conversation.id == Run.conversation_id)
                .where(Run.status.in_(ACTIVE_STATUSES), Conversation.owner_id == owner)
                .order_by(Run.created_at)
                .limit(100)
            )
        ).all()
        run_ids = [run.id for run, _ in rows]
        tools: dict[Any, str] = {}
        if run_ids:
            latest = (
                select(RunEvent.run_id, func.max(RunEvent.id).label("last_id"))
                .where(RunEvent.run_id.in_(run_ids), RunEvent.type.in_(TOOL_EVENTS))
                .group_by(RunEvent.run_id)
                .subquery()
            )
            for event in (
                await session.scalars(select(RunEvent).join(latest, RunEvent.id == latest.c.last_id))
            ).all():
                tools[event.run_id] = str((event.data or {}).get("name", ""))
    return [
        {
            "run_id": str(run.id),
            "conversation_id": str(conversation.id),
            "title": conversation.title,
            "mode": (conversation.meta or {}).get("mode", "chat"),
            "status": run.status,
            "created_at": run.created_at.isoformat(),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "tool": tools.get(run.id, ""),
        }
        for run, conversation in rows
    ]
