"""Testy kalendarza: klient CalDAV na atrapie serwera, narzędzia agenta, API modułu, prawdziwy Nextcloud."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from biuro_pomoc import HEADERS, FakeCalDAV, api, biuro_settings  # noqa: F401
from conftest import ToolHarness
from fastapi.testclient import TestClient
from icalendar import Calendar

from nexus.calendar import (
    CalendarClient,
    CalendarError,
    EventData,
    parse_when,
    przedrostek_konta,
    split_event_id,
)
from nexus.config import Settings
from nexus.db import ADMIN_OWNER
from nexus.tools import kalendarz as kalendarz_tools
from nexus.tools import registry
from nexus.tools.base import ToolError

TOKEN_FILE = os.environ.get("NEXUS_TEST_CHMURA_TOKEN_FILE", "")
CHMURA_URL = os.environ.get("NEXUS_TEST_CHMURA_URL", "http://127.0.0.1:8940")
WARSAW = ZoneInfo("Europe/Warsaw")


#: Przedrostek kalendarzy konta właściciela instalacji — tak nazywa je rozdział kont.
PRZEDROSTEK = przedrostek_konta(ADMIN_OWNER)
OSOBISTY = f"{PRZEDROSTEK}personal"
URODZINY = f"{PRZEDROSTEK}contact_birthdays"


@pytest.fixture
def caldav() -> FakeCalDAV:
    return FakeCalDAV(PRZEDROSTEK)


@pytest.fixture
def client(biuro_settings: Settings, caldav: FakeCalDAV) -> CalendarClient:  # noqa: F811
    return CalendarClient(biuro_settings, transport=caldav.transport(), owner=ADMIN_OWNER)


def call(harness: ToolHarness, name: str, /, **arguments: object):  # type: ignore[no-untyped-def]
    tool = registry.get(name)
    return tool.handler(harness.context(), tool.parse(arguments))


def test_parse_when_and_event_ids() -> None:
    assert parse_when("2026-09-20") == date(2026, 9, 20)
    assert parse_when("2026-09-20T10:30") == datetime(2026, 9, 20, 10, 30)
    assert parse_when("2026-09-20T08:30:00Z").utcoffset() == timedelta(0)
    with pytest.raises(ValueError):
        parse_when("jutro")
    assert split_event_id("personal/abc.ics") == ("personal", "abc.ics")
    for bad in ("abc.ics", "personal/../x.ics", "a/b/c.ics", "personal/\x00.ics"):
        with pytest.raises(CalendarError):
            split_event_id(bad)


def test_calendars(client: CalendarClient) -> None:
    calendars = client.calendars()
    assert [(c["id"], c["name"], c["color"], c["writable"], c["default"]) for c in calendars] == [
        (OSOBISTY, "Osobiste", "#00679e", True, True),
        (URODZINY, "Urodziny kontaktu", "#E9D859", False, False),
    ]


def test_create_list_update_delete(client: CalendarClient, caldav: FakeCalDAV) -> None:
    event = client.create(
        None,
        EventData(
            summary="Spotkanie z księgową",
            start=datetime(2026, 9, 21, 10, 0),
            location="Łódź",
            reminder_minutes=30,
        ),
    )
    assert event["id"].startswith(f"{OSOBISTY}/") and event["id"].endswith(".ics")
    assert event["start"] == "2026-09-21T10:00+02:00" and event["end"] == "2026-09-21T11:00+02:00"
    assert event["all_day"] is False and event["location"] == "Łódź"
    stored = Calendar.from_ical(next(iter(caldav.objects[OSOBISTY].values()))[0])
    assert stored.walk("VTIMEZONE"), "strefa czasowa dołączona do pliku"
    assert stored.walk("VALARM")[0].decoded("TRIGGER") == timedelta(minutes=-30)

    all_day = client.create(OSOBISTY, EventData(summary="Urlop", start=date(2026, 9, 24), all_day=True))
    assert all_day["all_day"] is True and (all_day["start"], all_day["end"]) == ("2026-09-24", "2026-09-25")

    events = client.events(date(2026, 9, 21), date(2026, 9, 28))
    assert [e["summary"] for e in events] == ["Spotkanie z księgową", "Urlop"]
    assert [e["summary"] for e in client.events(date(2026, 9, 21), date(2026, 9, 28), query="urlop")] == [
        "Urlop"
    ]

    updated = client.update(event["id"], EventData(start=datetime(2026, 9, 21, 12, 30), summary="Księgowa"))
    assert (updated["summary"], updated["start"], updated["end"]) == (
        "Księgowa",
        "2026-09-21T12:30+02:00",
        "2026-09-21T13:30+02:00",
    ), "zmiana początku zachowuje czas trwania"
    stale = event["etag"]
    with pytest.raises(CalendarError, match="zmieniło się"):
        client.update(event["id"], EventData(summary="X"), etag=stale)

    client.delete(event["id"])
    assert [e["summary"] for e in client.events(date(2026, 9, 21), date(2026, 9, 28))] == ["Urlop"]
    with pytest.raises(CalendarError, match="nie znaleziono"):
        client.delete(event["id"])
    with pytest.raises(CalendarError, match="brak uprawnień"):
        client.create(URODZINY, EventData(summary="X", start=date(2026, 9, 1)))
    # Kalendarz spoza przestrzeni konta jest dla klienta nieprawidłowy, a nie „tylko do odczytu”.
    with pytest.raises(CalendarError, match="Nieprawidłowy kalendarz"):
        client.create("contact_birthdays", EventData(summary="X", start=date(2026, 9, 1)))
    with pytest.raises(CalendarError, match="Zakres dat"):
        client.events(date(2026, 1, 1), date(2027, 6, 1))


def test_recurring_update_shifts_series(client: CalendarClient) -> None:
    event = client.create(
        None,
        EventData(summary="Joga", start=datetime(2026, 9, 7, 18, 0), rrule="FREQ=WEEKLY;COUNT=5"),
    )
    assert event["recurring"] is True
    client.update(
        event["id"],
        EventData(start=datetime(2026, 9, 14, 19, 0)),
        recurrence_id="2026-09-14T18:00+02:00",
    )
    master = client.get(event["id"])
    assert master["start"] == "2026-09-07T19:00+02:00", "seria przesunięta o godzinę, nie przeniesiona"
    with pytest.raises(CalendarError, match="reguła"):
        client.update(event["id"], EventData(rrule="FREQ=CO-TYDZIEN"))


def test_calendar_tools(
    harness: ToolHarness,
    biuro_settings: Settings,  # noqa: F811
    caldav: FakeCalDAV,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.settings = biuro_settings
    monkeypatch.setattr(
        kalendarz_tools,
        "CalendarClient",
        lambda settings, owner=None: CalendarClient(settings, transport=caldav.transport(), owner=owner),
    )
    created = call(
        harness, "calendar_create", summary="Przegląd auta", start="2026-10-02T08:00", location="ASO"
    )
    assert created.data["start"] == "2026-10-02T08:00+02:00"
    all_day = call(harness, "calendar_create", summary="Imieniny", start="2026-10-05")
    assert all_day.data["all_day"] is True
    listing = call(harness, "calendar_list", start="2026-10-01", end="2026-10-08")
    assert [e["summary"] for e in listing.data["events"]] == ["Przegląd auta", "Imieniny"]
    assert listing.data["calendars"][0]["id"] == OSOBISTY
    call(harness, "calendar_update", event_id=created.data["id"], location="Serwis Łódź")
    assert call(harness, "calendar_list", start="2026-10-02", end="2026-10-03").data["events"][0][
        "location"
    ] == ("Serwis Łódź")
    pending = call(harness, "calendar_delete", event_id=created.data["id"], reason="Przełożone")
    assert "Kalendarz" in pending.data["status"]
    assert len(caldav.objects[OSOBISTY]) == 2, "agent nie usuwa bez zatwierdzenia"
    with pytest.raises(ToolError, match="nie znaleziono"):
        call(harness, "calendar_delete", event_id=f"{OSOBISTY}/brak.ics")


def test_calendar_tools_without_token(harness: ToolHarness, tmp_path: Path) -> None:
    harness.settings.chmura_token_file = tmp_path / "brak"
    with pytest.raises(ToolError, match="nie jest skonfigurowany"):
        call(harness, "calendar_list")


def test_calendar_api(api: TestClient, caldav: FakeCalDAV, harness: ToolHarness, monkeypatch) -> None:  # noqa: F811
    api.app.state.calendar_transport = caldav.transport()
    assert [c["id"] for c in api.get("/api/kalendarz/kalendarze").json()] == [OSOBISTY, URODZINY]
    body = {
        "summary": "Dentysta",
        "start": "2026-09-22T15:00",
        "end": "2026-09-22T15:45",
        "reminder_minutes": 60,
    }
    assert api.post("/api/kalendarz/wydarzenia", json=body).status_code == 403, "CSRF"
    created = api.post("/api/kalendarz/wydarzenia", json=body, headers=HEADERS)
    assert created.status_code == 201, created.text
    event = created.json()
    listing = api.get("/api/kalendarz/wydarzenia", params={"od": "2026-09-21", "do": "2026-09-28"}).json()
    assert [(e["summary"], e["start"], e["end"]) for e in listing] == [
        ("Dentysta", "2026-09-22T15:00+02:00", "2026-09-22T15:45+02:00")
    ]
    calendar_id, name = event["id"].split("/")
    changed = api.patch(
        f"/api/kalendarz/wydarzenia/{calendar_id}/{name}",
        json={"summary": "Dentysta – kontrola"},
        headers=HEADERS,
    )
    assert changed.json()["summary"] == "Dentysta – kontrola"
    conflict = api.patch(
        f"/api/kalendarz/wydarzenia/{calendar_id}/{name}",
        json={"summary": "X", "etag": '"stary"'},
        headers=HEADERS,
    )
    assert conflict.status_code == 409

    # Prośba agenta o usunięcie – zatwierdzana w module.
    harness.settings = api.app.state.settings
    monkeypatch.setattr(
        kalendarz_tools,
        "CalendarClient",
        lambda settings, owner=None: CalendarClient(settings, transport=caldav.transport(), owner=owner),
    )
    pending_id = call(harness, "calendar_delete", event_id=event["id"]).data["pending_id"]
    queue = api.get("/api/kalendarz/oczekujace").json()
    assert [item["id"] for item in queue] == [pending_id]
    assert queue[0]["payload"]["summary"] == "Dentysta – kontrola"
    assert api.post(f"/api/kalendarz/oczekujace/{pending_id}/zatwierdz").status_code == 403
    approved = api.post(f"/api/kalendarz/oczekujace/{pending_id}/zatwierdz", headers=HEADERS)
    assert approved.json()["status"] == "done"
    assert caldav.objects[OSOBISTY] == {}
    assert api.post(f"/api/kalendarz/oczekujace/{pending_id}/odrzuc", headers=HEADERS).status_code == 409

    second = api.post("/api/kalendarz/wydarzenia", json=body, headers=HEADERS).json()
    rejected_id = call(harness, "calendar_delete", event_id=second["id"]).data["pending_id"]
    assert api.post(f"/api/kalendarz/oczekujace/{rejected_id}/odrzuc", headers=HEADERS).json()["status"] == (
        "cancelled"
    )
    assert len(caldav.objects[OSOBISTY]) == 1
    calendar_id, name = second["id"].split("/")
    assert api.delete(f"/api/kalendarz/wydarzenia/{calendar_id}/{name}", headers=HEADERS).json() == {
        "ok": True
    }
    assert api.get("/api/kalendarz/synchronizacja").json() == {
        "caldav_url": "https://cloud.example.pl/remote.php/dav",
        "user": "admin",
    }


def test_plan_with_nexus(api: TestClient) -> None:  # noqa: F811
    response = api.post(
        "/api/kalendarz/zaplanuj", json={"text": "trzy treningi w tym tygodniu"}, headers=HEADERS
    )
    assert response.status_code == 200, response.text
    conversation = api.get(f"/api/conversations/{response.json()['conversation_id']}").json()
    assert conversation["title"] == "Plan: trzy treningi w tym tygodniu"
    assert "calendar_create" in conversation["turns"][0]["text"]


@pytest.mark.skipif(
    not TOKEN_FILE or not Path(TOKEN_FILE).is_file(), reason="Brak NEXUS_TEST_CHMURA_TOKEN_FILE"
)
def test_real_nextcloud_calendar(tmp_path: Path) -> None:
    settings = Settings(
        chmura_url=CHMURA_URL,
        chmura_token_file=Path(TOKEN_FILE),
        database_url="sqlite+aiosqlite:///:memory:",
    )
    client = CalendarClient(settings)
    created: list[str] = []
    try:
        calendars = client.calendars()
        assert any(cal["id"] == "personal" and cal["writable"] for cal in calendars)
        day = date.today() + timedelta(days=400 - 30)
        event = client.create(
            "personal",
            EventData(
                summary="Nexus – test automatyczny",
                start=datetime.combine(day, datetime.min.time()).replace(hour=9),
                rrule="FREQ=DAILY;COUNT=3",
                reminder_minutes=15,
            ),
        )
        created.append(event["id"])
        instances = client.events(day, day + timedelta(days=5), ["personal"], "test automatyczny")
        assert [i["start"][:10] for i in instances] == [
            (day + timedelta(days=n)).isoformat() for n in range(3)
        ]
        assert all(i["recurring"] for i in instances)
        second = instances[1]
        client.update(
            event["id"],
            EventData(start=datetime.fromisoformat(second["start"]) + timedelta(hours=2)),
            recurrence_id=second["recurrence_id"],
        )
        moved = client.events(day, day + timedelta(days=5), ["personal"], "test automatyczny")
        assert [i["start"][11:16] for i in moved] == ["11:00", "11:00", "11:00"]
        client.delete(event["id"])
        created.clear()
        assert client.events(day, day + timedelta(days=5), ["personal"], "test automatyczny") == []
    finally:
        for event_id in created:
            try:
                client.delete(event_id)
            except CalendarError:
                pass
        client.close()


def test_rownolegle_zalozenie_kalendarza_nie_jest_awaria(biuro_settings: Settings) -> None:  # noqa: F811
    """Przegrana z wyścigu o ten sam kalendarz nie ma straszyć użytkownika czerwonym paskiem.

    Moduł i agent pytają o kalendarz równolegle przy pierwszym wejściu na konto. Obie próby
    zakładają tę samą kolekcję; przegrywająca dostaje z Nextcloud 500 z naruszenia warunku
    jednoznaczności, choć kalendarz w tej chwili już istnieje.
    """
    import uuid

    import httpx

    from nexus.calendar import CalendarClient

    konto = uuid.uuid4()
    domyslny = None

    def obsluga(request: httpx.Request) -> httpx.Response:
        nonlocal domyslny
        if request.method == "PROPFIND":
            if domyslny is None:
                return httpx.Response(207, content=b'<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"/>')
            sciezka = f"/remote.php/dav/calendars/admin/{domyslny}/"
            tresc = (
                '<?xml version="1.0"?>'
                '<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
                f"<d:response><d:href>{sciezka}</d:href><d:propstat><d:prop>"
                "<d:displayname>Kalendarz</d:displayname>"
                '<d:resourcetype><d:collection/><c:calendar/></d:resourcetype>'
                '<c:supported-calendar-component-set><c:comp name="VEVENT"/>'
                "</c:supported-calendar-component-set>"
                "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
                "</d:multistatus>"
            )
            return httpx.Response(207, content=tresc.encode("utf-8"))
        if request.method == "MKCALENDAR":
            # Ktoś inny zdążył pierwszy: kolekcja jest, a my dostajemy 500.
            domyslny = request.url.path.rstrip("/").rsplit("/", 1)[-1]
            return httpx.Response(500, content=b"<d:error/>")
        return httpx.Response(404)

    klient = CalendarClient(biuro_settings, transport=httpx.MockTransport(obsluga), owner=konto)
    klient.zapewnij_kalendarz()  # nie rzuca — kalendarz istnieje
    assert klient.calendars()[0]["id"] == klient.default_calendar
