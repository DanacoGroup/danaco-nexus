"""Moduł Kalendarz: wydarzenia z CalDAV chmury, dodawanie, zmiany i zatwierdzanie usunięć agenta."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from nexus import oczekujace
from nexus.api import conversations
from nexus.api.auth import require_session
from nexus.calendar import CalendarClient, CalendarError, CalendarNotConfigured, EventData, When, caldav_url
from nexus.config import Settings

router = APIRouter(prefix="/api/kalendarz", tags=["kalendarz"], dependencies=[Depends(require_session)])


def _settings(request: Request) -> Settings:
    return request.app.state.settings


async def _calendar[T](request: Request, work: Callable[[CalendarClient], T]) -> T:
    """Operacja CalDAV w wątku; błędy kalendarza jako odpowiedzi HTTP."""
    settings = _settings(request)
    transport = getattr(request.app.state, "calendar_transport", None)

    def run() -> T:
        with CalendarClient(settings, transport=transport) as client:
            return work(client)

    try:
        return await asyncio.to_thread(run)
    except CalendarNotConfigured as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except CalendarError as error:
        message = str(error)
        code = status.HTTP_409_CONFLICT if "zmieniło się" in message else status.HTTP_400_BAD_REQUEST
        if "nie znaleziono" in message.lower():
            code = status.HTTP_404_NOT_FOUND
        raise HTTPException(code, message) from error


class EventCreate(BaseModel):
    calendar: str = Field("", max_length=200)
    summary: str = Field(min_length=1, max_length=300)
    start: When
    end: When | None = None
    all_day: bool | None = None
    location: str = Field("", max_length=500)
    description: str = Field("", max_length=10_000)
    reminder_minutes: int | None = Field(None, ge=0, le=40_320)
    rrule: str = Field("", max_length=300)


class EventUpdate(BaseModel):
    summary: str | None = Field(None, max_length=300)
    start: When | None = None
    end: When | None = None
    all_day: bool | None = None
    location: str | None = Field(None, max_length=500)
    description: str | None = Field(None, max_length=10_000)
    reminder_minutes: int | None = Field(None, ge=0, le=40_320)
    rrule: str | None = Field(None, max_length=300)
    etag: str | None = Field(None, max_length=200)
    recurrence_id: str | None = Field(None, max_length=40)


class PlanRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    day: date | None = None


def _event_data(payload: BaseModel) -> EventData:
    fields = payload.model_dump(exclude={"calendar", "etag", "recurrence_id"})
    if isinstance(payload, EventCreate) and fields.get("all_day") is None:
        fields["all_day"] = not isinstance(payload.start, datetime)
    if isinstance(payload, EventCreate):
        fields["rrule"] = fields.get("rrule") or None
    return EventData(**fields)


@router.get("/kalendarze")
async def calendars(request: Request) -> list[dict[str, Any]]:
    """Kalendarze konta."""
    return await _calendar(request, lambda client: client.calendars())


@router.get("/wydarzenia")
async def events(
    request: Request,
    start: date = Query(alias="od"),
    end: date = Query(alias="do"),
    calendars: str = Query("", alias="kalendarze", description="Identyfikatory rozdzielone przecinkami."),
    q: str = Query("", max_length=200),
) -> list[dict[str, Any]]:
    """Wydarzenia w przedziale dat [od, do) z rozwiniętymi seriami."""
    wanted = [item for item in calendars.split(",") if item] or None
    return await _calendar(request, lambda client: client.events(start, end, wanted, q))


@router.post("/wydarzenia", status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventCreate, request: Request) -> dict[str, Any]:
    """Dodaje wydarzenie."""
    data = _event_data(payload)
    return await _calendar(request, lambda client: client.create(payload.calendar or None, data))


@router.patch("/wydarzenia/{calendar_id}/{name}")
async def update_event(calendar_id: str, name: str, payload: EventUpdate, request: Request) -> dict[str, Any]:
    """Zmienia wydarzenie (w serii zmiana czasu przesuwa całą serię)."""
    data = _event_data(payload)
    return await _calendar(
        request,
        lambda client: client.update(f"{calendar_id}/{name}", data, payload.etag, payload.recurrence_id),
    )


@router.delete("/wydarzenia/{calendar_id}/{name}")
async def delete_event(
    calendar_id: str, name: str, request: Request, etag: str | None = None
) -> dict[str, bool]:
    """Usuwa wydarzenie (całą serię) – wywoływane po potwierdzeniu w interfejsie."""
    await _calendar(request, lambda client: client.delete(f"{calendar_id}/{name}", etag))
    return {"ok": True}


@router.get("/oczekujace")
async def pending(request: Request) -> list[dict[str, Any]]:
    """Usunięcia zaproponowane przez asystenta, czekające na decyzję."""
    records = await oczekujace.list_pending(request.app.state.database, "kalendarz_usun")
    return [oczekujace.payload(record) for record in records]


@router.post("/oczekujace/{action_id}/zatwierdz")
async def approve(action_id: uuid.UUID, request: Request) -> dict[str, Any]:
    """Zatwierdza usunięcie wydarzenia zaproponowane przez asystenta."""
    database = request.app.state.database
    record = await oczekujace.claim(database, action_id, "kalendarz_usun")
    if record is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ta prośba nie czeka już na decyzję.")
    event_id = str((record.payload or {}).get("event_id", ""))
    try:
        await _calendar(request, lambda client: client.delete(event_id))
    except HTTPException as error:
        if error.status_code != status.HTTP_404_NOT_FOUND:
            await oczekujace.update(database, action_id, status="pending", error=str(error.detail))
            raise
    updated = await oczekujace.update(database, action_id, status="done", error="")
    return oczekujace.payload(updated)


@router.post("/oczekujace/{action_id}/odrzuc")
async def reject(action_id: uuid.UUID, request: Request) -> dict[str, Any]:
    """Odrzuca prośbę o usunięcie (wydarzenie zostaje)."""
    database = request.app.state.database
    record = await oczekujace.get(database, action_id, "kalendarz_usun")
    if record is None or record.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Ta prośba nie czeka już na decyzję.")
    updated = await oczekujace.update(database, action_id, status="cancelled")
    return oczekujace.payload(updated)


@router.post("/zaplanuj")
async def plan_with_nexus(payload: PlanRequest, request: Request) -> dict[str, Any]:
    """„Zaplanuj z Nexusem”: rozmowa, w której asystent układa plan i dodaje wydarzenia."""
    day = payload.day or date.today()
    week_end = day + timedelta(days=7)
    text = (
        f"Pomóż mi zaplanować w kalendarzu: {payload.text.strip()}\n\n"
        f"Punkt odniesienia: {day.isoformat()} (strefa {_settings(request).kalendarz_timezone}). "
        f"Najpierw sprawdź narzędziem calendar_list moje terminy od {day.isoformat()} "
        f"do {week_end.isoformat()} "
        "(albo w zakresie, którego dotyczy prośba), unikaj kolizji, a potem dodaj wydarzenia narzędziem "
        "calendar_create. Na końcu krótko podsumuj, co i kiedy zaplanowałeś."
    )
    created = await conversations.create_conversation(
        conversations.CreateConversation(title=f"Plan: {payload.text.strip()}"[:200]), request
    )
    conversation_id = uuid.UUID(created["id"])
    result = await conversations.send_message(conversation_id, conversations.SendMessage(text=text), request)
    return {"conversation_id": str(conversation_id), "run_id": result["run_id"]}


@router.get("/synchronizacja")
async def sync_info(request: Request) -> dict[str, str]:
    """Adres CalDAV do synchronizacji telefonu (DAVx5) i programów kalendarza."""
    settings = _settings(request)
    return {"caldav_url": caldav_url(settings), "user": settings.chmura_user}
