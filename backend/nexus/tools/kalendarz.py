"""Narzędzia kalendarza (CalDAV chmury): przegląd, dodawanie, zmiana, usuwanie po zatwierdzeniu.

Usuwania agent nie wykonuje sam: ``calendar_delete`` zapisuje prośbę, którą
użytkownik zatwierdza w module Kalendarz.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from pydantic import Field

from nexus import oczekujace
from nexus.calendar import CalendarClient, CalendarError, EventData, When
from nexus.tools.base import ToolContext, ToolError, ToolInput, ToolResult, registry

MAX_EVENTS = 300


def _client(ctx: ToolContext) -> CalendarClient:
    try:
        klient = CalendarClient(ctx.settings, owner=ctx.owner_id)
    except CalendarError as error:
        raise ToolError(str(error)) from error
    try:
        klient.zapewnij_kalendarz()
    except CalendarError as error:
        klient.close()
        raise ToolError(str(error)) from error
    return klient


def _short(event: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "summary", "start", "end", "all_day", "location", "calendar", "recurring", "recurrence_id")
    data = {key: event[key] for key in keys}
    if event["description"]:
        data["description"] = event["description"][:500]
    return data


class CalendarListInput(ToolInput):
    start: When | None = Field(None, description="Początek zakresu (domyślnie dziś).")
    end: When | None = Field(None, description="Koniec zakresu (domyślnie start + 7 dni).")
    calendars: list[str] = Field(
        default_factory=list, description="Identyfikatory kalendarzy (puste = wszystkie)."
    )
    query: str = Field("", max_length=200, description="Filtr tekstu (tytuł, miejsce, opis).")


class CalendarEventInput(ToolInput):
    summary: str = Field(max_length=300, description="Tytuł wydarzenia.")
    start: When = Field(
        description="Początek: 'RRRR-MM-DDTGG:MM' (czas lokalny, Europa/Warszawa) "
        "albo 'RRRR-MM-DD' (cały dzień)."
    )
    end: When | None = Field(None, description="Koniec (domyślnie 1 godzina / 1 dzień po początku).")
    all_day: bool | None = Field(None, description="Wydarzenie całodniowe (domyślnie: gdy podano same daty).")
    location: str = Field("", max_length=500)
    description: str = Field("", max_length=10_000)
    reminder_minutes: int | None = Field(None, ge=0, le=40_320, description="Przypomnienie N minut przed.")
    rrule: str = Field("", max_length=300, description="Powtarzanie RFC 5545, np. 'FREQ=WEEKLY;COUNT=10'.")
    calendar: str = Field("", description="Kalendarz (puste = domyślny).")


class CalendarUpdateInput(ToolInput):
    event_id: str = Field(description="Identyfikator wydarzenia z calendar_list (np. 'personal/abc.ics').")
    recurrence_id: str | None = Field(
        None, description="recurrence_id wystąpienia – przy zmianie czasu w serii przesuwa całą serię."
    )
    summary: str | None = None
    start: When | None = None
    end: When | None = None
    all_day: bool | None = None
    location: str | None = None
    description: str | None = None
    reminder_minutes: int | None = Field(None, ge=0, le=40_320, description="0 = bez przypomnienia.")
    rrule: str | None = Field(None, description="Nowa reguła powtarzania ('' = bez powtarzania).")


class CalendarDeleteInput(ToolInput):
    event_id: str = Field(description="Identyfikator wydarzenia z calendar_list.")
    reason: str = Field("", max_length=300, description="Krótkie uzasadnienie dla użytkownika.")


@registry.register(
    "calendar_list",
    """Wydarzenia z kalendarza użytkownika (Nextcloud) w zakresie dat, z listą kalendarzy.
Wydarzenia cykliczne są rozwinięte w wystąpienia. Czasy w strefie Europa/Warszawa.""",
    CalendarListInput,
)
def calendar_list(ctx: ToolContext, args: CalendarListInput) -> ToolResult:
    start = args.start or date.today()
    end = args.end or (start + timedelta(days=7))
    with _client(ctx) as client:
        try:
            calendars = client.calendars()
            events = client.events(start, end, args.calendars or None, args.query)
        except CalendarError as error:
            raise ToolError(str(error)) from error
    data = {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "calendars": [{k: cal[k] for k in ("id", "name", "writable", "default")} for cal in calendars],
        "events": [_short(event) for event in events[:MAX_EVENTS]],
        "total": len(events),
    }
    return ToolResult(data, f"Kalendarz: {len(events)} wydarzeń")


@registry.register(
    "calendar_create",
    """Dodaje wydarzenie do kalendarza użytkownika (spotkanie, termin, przypomnienie). Podaj czas
lokalny; wydarzenie od razu synchronizuje się z telefonem i komputerem.""",
    CalendarEventInput,
)
def calendar_create(ctx: ToolContext, args: CalendarEventInput) -> ToolResult:
    all_day = args.all_day if args.all_day is not None else not isinstance(args.start, datetime)
    data = EventData(
        summary=args.summary,
        start=args.start,
        end=args.end,
        all_day=all_day,
        location=args.location,
        description=args.description,
        reminder_minutes=args.reminder_minutes,
        rrule=args.rrule or None,
    )
    with _client(ctx) as client:
        try:
            event = client.create(args.calendar or None, data)
        except CalendarError as error:
            raise ToolError(str(error)) from error
    return ToolResult(_short(event), f"Dodano wydarzenie: {event['summary']} ({event['start']})")


@registry.register(
    "calendar_update",
    """Zmienia wydarzenie w kalendarzu (tytuł, czas, miejsce, opis, przypomnienie, powtarzanie).
Podaj tylko zmieniane pola.""",
    CalendarUpdateInput,
)
def calendar_update(ctx: ToolContext, args: CalendarUpdateInput) -> ToolResult:
    data = EventData(
        summary=args.summary,
        start=args.start,
        end=args.end,
        all_day=args.all_day,
        location=args.location,
        description=args.description,
        reminder_minutes=args.reminder_minutes,
        rrule=args.rrule,
    )
    with _client(ctx) as client:
        try:
            event = client.update(args.event_id, data, recurrence_id=args.recurrence_id)
        except CalendarError as error:
            raise ToolError(str(error)) from error
    return ToolResult(_short(event), f"Zmieniono wydarzenie: {event['summary']}")


@registry.register(
    "calendar_delete",
    """Prosi o usunięcie wydarzenia z kalendarza. Wydarzenie NIE jest usuwane od razu: użytkownik
zatwierdza usunięcie w module Kalendarz (dla serii – usuwana jest cała seria). Poinformuj o tym
użytkownika.""",
    CalendarDeleteInput,
)
def calendar_delete(ctx: ToolContext, args: CalendarDeleteInput) -> ToolResult:
    with _client(ctx) as client:
        try:
            event = client.get(args.event_id)
        except CalendarError as error:
            raise ToolError(str(error)) from error
    summary = f"Usuń: {event['summary'] or '(bez tytułu)'} ({event['start']})"
    pending_id = oczekujace.create_sync(
        ctx.settings,
        "kalendarz_usun",
        summary,
        {
            "event_id": args.event_id,
            "summary": event["summary"],
            "start": event["start"],
            "recurring": event["recurring"],
            "reason": args.reason,
        },
        ctx.run_id,
    )
    return ToolResult(
        {"pending_id": pending_id, "status": "czeka na zatwierdzenie użytkownika w module Kalendarz"},
        "Usunięcie czeka na zatwierdzenie w module Kalendarz",
    )
