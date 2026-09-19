"""Powiadomienia Web Push: klucz publiczny VAPID, subskrypcje przeglądarek, powiadomienie próbne.

Przy starcie API (lifespan routera) powstaje klucz VAPID i rusza nasłuch kanału Redis
``nexus:run-finished`` – po zakończeniu zadania każda subskrypcja dostaje powiadomienie.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from nexus.api.auth import require_session
from nexus.db import Database
from nexus.models.push import PushSubscription
from nexus.push_service import (
    endpoint_hash,
    ensure_vapid_key,
    listen_run_finished,
    pywebpush_sender,
    send_to_all,
)

logger = logging.getLogger(__name__)
PUSH_DISABLED = "Powiadomienia push są wyłączone na serwerze."


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    app.state.push_public_key = ""
    listener: asyncio.Task[None] | None = None
    if settings.push_enabled:
        try:
            app.state.push_public_key = ensure_vapid_key(settings.vapid_file)
        except (OSError, ValueError) as error:
            logger.warning("Powiadomienia push niedostępne – klucz VAPID: %s", error)
        if app.state.push_public_key and getattr(app.state, "push_sender", None) is None:
            try:
                app.state.push_sender = pywebpush_sender(settings)
            except ImportError:
                logger.warning("Brak biblioteki pywebpush – powiadomienia push są wyłączone.")
        if app.state.push_public_key and getattr(app.state, "push_sender", None) is not None:
            listener = asyncio.create_task(
                listen_run_finished(settings, app.state.database, app.state.push_sender),
                name="push-run-finished",
            )
    yield
    if listener is not None:
        listener.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener


router = APIRouter(
    prefix="/api/push", tags=["push"], dependencies=[Depends(require_session)], lifespan=lifespan
)


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class NewSubscription(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000, pattern=r"^https://")
    keys: SubscriptionKeys
    name: str = Field("", max_length=100)


class RemoveSubscription(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)


def _available(request: Request) -> bool:
    return bool(getattr(request.app.state, "push_public_key", "")) and (
        getattr(request.app.state, "push_sender", None) is not None
    )


@router.get("/klucz")
async def public_key(request: Request) -> dict[str, Any]:
    """Klucz publiczny VAPID (``applicationServerKey``) i liczba zapisanych subskrypcji."""
    database: Database = request.app.state.database
    async with database.session() as session:
        count = await session.scalar(select(func.count()).select_from(PushSubscription))
    return {
        "available": _available(request),
        "public_key": getattr(request.app.state, "push_public_key", ""),
        "subscriptions": count or 0,
    }


@router.post("/subskrypcje", status_code=status.HTTP_201_CREATED)
async def subscribe(payload: NewSubscription, request: Request) -> dict[str, Any]:
    """Zapisuje (albo odświeża) subskrypcję przeglądarki."""
    if not _available(request):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, PUSH_DISABLED)
    database: Database = request.app.state.database
    key = endpoint_hash(payload.endpoint)
    async with database.session() as session:
        record = await session.scalar(select(PushSubscription).where(PushSubscription.endpoint_hash == key))
        if record is None:
            record = PushSubscription(endpoint_hash=key, endpoint=payload.endpoint)
            session.add(record)
        record.p256dh = payload.keys.p256dh
        record.auth = payload.keys.auth
        record.name = payload.name.strip()
        record.user_agent = request.headers.get("user-agent", "")[:300]
        record.failures = 0
    return {"ok": True}


@router.post("/wypisz")
async def unsubscribe(payload: RemoveSubscription, request: Request) -> dict[str, bool]:
    """Usuwa subskrypcję (wyłączenie powiadomień na tym urządzeniu)."""
    database: Database = request.app.state.database
    async with database.session() as session:
        await session.execute(
            delete(PushSubscription).where(PushSubscription.endpoint_hash == endpoint_hash(payload.endpoint))
        )
    return {"ok": True}


@router.post("/test")
async def test_notification(request: Request) -> dict[str, int]:
    """Wysyła powiadomienie próbne do wszystkich subskrypcji."""
    if not _available(request):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, PUSH_DISABLED)
    report = await send_to_all(
        request.app.state.database,
        request.app.state.push_sender,
        {"title": "Danaco Nexus", "body": "Powiadomienia działają.", "url": "/", "tag": "nexus-test"},
    )
    return {"sent": report.sent, "removed": report.removed, "failed": report.failed}
