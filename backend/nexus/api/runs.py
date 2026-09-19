"""API zadań agenta: stan, anulowanie, strumień zdarzeń (Server-Sent Events)."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update

from nexus.api.auth import require_session
from nexus.db import Database, Run, RunEvent
from nexus.events import EventBus, channel

router = APIRouter(prefix="/api/runs", tags=["runs"], dependencies=[Depends(require_session)])

FINAL_EVENTS = frozenset({"run.completed", "run.failed", "run.cancelled"})
# Z Redisem strumień czeka na powiadomienie; baza jest i tak odczytywana co kilka sekund.
WAIT_SECONDS = 5.0
KEEPALIVE_SECONDS = 15.0


async def _run(request: Request, run_id: uuid.UUID) -> Run:
    database: Database = request.app.state.database
    async with database.session() as session:
        run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono zadania.")
    return run


@router.get("/{run_id}")
async def get_run(run_id: uuid.UUID, request: Request) -> dict[str, Any]:
    """Stan zadania."""
    run = await _run(request, run_id)
    return {
        "id": str(run.id),
        "status": run.status,
        "error": run.error,
        "usage": run.usage,
        "conversation_id": str(run.conversation_id),
    }


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: uuid.UUID, request: Request) -> dict[str, str]:
    """Zgłasza anulowanie zadania (oczekujące jest anulowane od razu)."""
    await _run(request, run_id)
    database: Database = request.app.state.database
    async with database.session() as session:
        await session.execute(
            update(Run)
            .where(Run.id == run_id, Run.status == "queued")
            .values(status="cancelled", error="Zadanie anulowane.")
        )
        await session.execute(update(Run).where(Run.id == run_id).values(cancel_requested=True))
        current = await session.scalar(select(Run.status).where(Run.id == run_id))
        if current == "cancelled":
            session.add(RunEvent(run_id=run_id, type="run.cancelled", data={"error": "Zadanie anulowane."}))
    if current == "cancelled":
        await request.app.state.events.notify(run_id)
    return {"status": current or "unknown"}


def _sse(event_id: int, event_type: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"


@router.get("/{run_id}/events")
async def run_events(
    run_id: uuid.UUID, request: Request, after: int = 0, last_event_id: str | None = Header(None)
) -> StreamingResponse:
    """Strumień zdarzeń zadania; wznowienie od ``Last-Event-ID`` lub parametru ``after``."""
    await _run(request, run_id)
    database: Database = request.app.state.database
    bus: EventBus = request.app.state.events
    start = max(after, int(last_event_id) if last_event_id and last_event_id.isdigit() else 0)

    async def stream() -> AsyncIterator[str]:
        cursor = start
        last_sent = time.monotonic()
        yield "retry: 2000\n\n"
        # Subskrypcja przed pierwszym odczytem bazy – żadne powiadomienie nie ginie.
        async with bus.listener(channel(run_id)) as wait:
            while True:
                if await request.is_disconnected():
                    return
                async with database.session() as session:
                    events = (
                        await session.scalars(
                            select(RunEvent)
                            .where(RunEvent.run_id == run_id, RunEvent.id > cursor)
                            .order_by(RunEvent.id)
                            .limit(500)
                        )
                    ).all()
                for event in events:
                    cursor = event.id
                    yield _sse(event.id, event.type, event.data or {})
                    if event.type in FINAL_EVENTS:
                        return
                if events:
                    last_sent = time.monotonic()
                    continue
                if time.monotonic() - last_sent > KEEPALIVE_SECONDS:
                    last_sent = time.monotonic()
                    yield ": keepalive\n\n"
                await wait(WAIT_SECONDS)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
