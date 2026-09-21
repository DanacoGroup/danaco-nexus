"""Kalendarz: CalDAV chmury osobistej (Nextcloud) – kalendarze, wydarzenia, zmiany.

Konto i hasło aplikacji są te same co dla plików chmury (``chmura_user``,
``chmura_token_file``). Wydarzenia cykliczne rozwija serwer (``<C:expand>``);
identyfikator wydarzenia to ``<kalendarz>/<plik>.ics``. Czasy bez strefy
są interpretowane w strefie ``kalendarz_timezone``.
"""

from __future__ import annotations

import logging
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any
from urllib.parse import quote, unquote, urlsplit
from zoneinfo import ZoneInfo

import httpx
from icalendar import Alarm, Calendar, Event, vRecur
from pydantic import BeforeValidator

from nexus.config import Settings

logger = logging.getLogger(__name__)

DAV = "{DAV:}"
CALDAV = "{urn:ietf:params:xml:ns:caldav}"
APPLE = "{http://apple.com/ns/ical/}"
TIMEOUT = httpx.Timeout(30.0)
MAX_RANGE_DAYS = 400
PROPFIND_CALENDARS = """<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" xmlns:a="http://apple.com/ns/ical/">
  <d:prop><d:resourcetype/><d:displayname/><a:calendar-color/><c:supported-calendar-component-set/>
  <d:current-user-privilege-set/></d:prop>
</d:propfind>"""
REPORT_EVENTS = """<?xml version="1.0"?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop><d:getetag/><c:calendar-data><c:expand start="{start}" end="{end}"/></c:calendar-data></d:prop>
  <c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT">
    <c:time-range start="{start}" end="{end}"/>
  </c:comp-filter></c:comp-filter></c:filter>
</c:calendar-query>"""


class CalendarError(Exception):
    """Błąd kalendarza opisany dla użytkownika."""


class CalendarNotConfigured(CalendarError):
    """Brak adresu chmury lub hasła aplikacji."""


def parse_when(value: Any) -> Any:
    """Tekst ISO na datę (sam dzień = cały dzień) albo czas; inne wartości bez zmian."""
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text) if ("T" in text or " " in text) else date.fromisoformat(text)
        except ValueError as error:
            raise ValueError(f"Nieprawidłowa data lub czas: {value}") from error
    return value


When = Annotated[datetime | date, BeforeValidator(parse_when)]


def _utc_stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def split_event_id(event_id: str) -> tuple[str, str]:
    """Kalendarz i nazwa pliku z identyfikatora ``<kalendarz>/<plik>.ics``."""
    parts = (event_id or "").strip("/").split("/")
    if len(parts) != 2 or not all(parts) or any(p in (".", "..") for p in parts):
        raise CalendarError(f"Nieprawidłowy identyfikator wydarzenia: {event_id}")
    if any(ord(char) < 32 for part in parts for char in part):
        raise CalendarError("Identyfikator wydarzenia zawiera niedozwolone znaki.")
    return parts[0], parts[1]


def _check_calendar_id(calendar_id: str) -> str:
    if not calendar_id or "/" in calendar_id or calendar_id in (".", "..") or not calendar_id.isprintable():
        raise CalendarError(f"Nieprawidłowy kalendarz: {calendar_id}")
    return calendar_id


@dataclass(slots=True)
class EventData:
    """Pola wydarzenia do utworzenia lub zmiany (``None`` = bez zmian)."""

    summary: str | None = None
    start: datetime | date | None = None
    end: datetime | date | None = None
    all_day: bool | None = None
    location: str | None = None
    description: str | None = None
    reminder_minutes: int | None = None
    rrule: str | None = None


def przedrostek_konta(owner: uuid.UUID | None) -> str:
    """Początek nazwy kalendarzy należących do konta (pusty przy braku rozdziału).

    Instalacja ma w Nextcloud jedno konto, więc wszystkie kalendarze leżą w jednym
    zbiorze. Rozdział robi nazwa kolekcji: konto widzi wyłącznie te, które zaczynają
    się jego przedrostkiem, i tylko do takich wolno mu adresować żądania.
    """
    return f"konto-{owner}-" if owner is not None else ""


class CalendarClient:
    """Klient CalDAV konta Nextcloud (synchroniczny; API wywołuje go w wątku)."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        owner: uuid.UUID | None = None,
    ) -> None:
        try:
            token = settings.chmura_token_file.read_text(encoding="utf-8").strip()
        except OSError:
            token = ""
        if not settings.chmura_url or not token:
            raise CalendarNotConfigured(
                "Kalendarz nie jest skonfigurowany (brak adresu chmury lub hasła aplikacji)."
            )
        self.user = settings.chmura_user
        self.owner = owner
        self.tz = ZoneInfo(settings.kalendarz_timezone)
        self.przedrostek = przedrostek_konta(owner)
        self.default_calendar = f"{self.przedrostek}{settings.kalendarz_default}"
        self.root = f"{settings.chmura_url.rstrip('/')}/remote.php/dav/calendars/{quote(self.user)}/"
        self._root_path = urlsplit(self.root).path
        self.http = httpx.Client(
            auth=(self.user, token), timeout=TIMEOUT, follow_redirects=False, transport=transport
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> CalendarClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # --- pomocnicze ---

    def _moj_kalendarz(self, calendar_id: str) -> str:
        """Sprawdza identyfikator i to, że kalendarz należy do konta tego klienta."""
        sprawdzony = _check_calendar_id(calendar_id)
        if self.przedrostek and not sprawdzony.startswith(self.przedrostek):
            raise CalendarError(f"Nieprawidłowy kalendarz: {calendar_id}")
        return sprawdzony

    def _url(self, calendar_id: str, name: str | None = None) -> str:
        url = self.root + quote(self._moj_kalendarz(calendar_id)) + "/"
        return url + quote(name) if name else url

    def zapewnij_kalendarz(self) -> None:
        """Zakłada domyślny kalendarz konta, gdy jeszcze go nie ma."""
        if not self.przedrostek:
            return
        if any(kalendarz["id"] == self.default_calendar for kalendarz in self.calendars()):
            return
        response = self.http.request(
            "MKCALENDAR",
            self._url(self.default_calendar),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            content=(
                b'<?xml version="1.0" encoding="utf-8"?>'
                b'<c:mkcalendar xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
                b"<d:set><d:prop><d:displayname>Kalendarz</d:displayname>"
                b"<c:supported-calendar-component-set>"
                b'<c:comp name="VEVENT"/>'
                b"</c:supported-calendar-component-set>"
                b"</d:prop></d:set></c:mkcalendar>"
            ),
        )
        # 405 znaczy, że kalendarz już istnieje — to nie błąd.
        if response.status_code < 400 or response.status_code == 405:
            return
        # Moduł i agent pytają o kalendarz równolegle przy pierwszym wejściu na konto.
        # Wtedy obie próby zakładają tę samą kolekcję i przegrywająca dostaje z Nextcloud
        # nie 405, tylko 500 z naruszenia warunku jednoznaczności w bazie. Kalendarz w tym
        # momencie już jest, więc zanim ogłosimy awarię, sprawdzamy stan faktyczny —
        # użytkownik nie ma oglądać czerwonego paska nad działającym kalendarzem.
        if any(kalendarz["id"] == self.default_calendar for kalendarz in self.calendars()):
            logger.info("Kalendarz konta powstał równolegle (HTTP %s) — nic nie robię.", response.status_code)
            return
        self._check(response, "utworzenie kalendarza konta")

    def _check(self, response: httpx.Response, action: str) -> None:
        if response.status_code == 401:
            raise CalendarError("Chmura odrzuciła hasło aplikacji Nexusa (401).")
        if response.status_code == 404:
            raise CalendarError(f"Kalendarz: nie znaleziono ({action}).")
        if response.status_code == 412:
            raise CalendarError("Wydarzenie zmieniło się w międzyczasie – odśwież i spróbuj ponownie.")
        if response.status_code == 403:
            raise CalendarError(f"Kalendarz: brak uprawnień ({action}).")
        if response.status_code >= 400:
            raise CalendarError(f"Kalendarz: {action} nie powiodło się (HTTP {response.status_code}).")

    def local(self, value: datetime | date) -> datetime | date:
        """Czas w strefie kalendarza (czas bez strefy traktowany jako lokalny)."""
        if isinstance(value, datetime):
            return value.replace(tzinfo=self.tz) if value.tzinfo is None else value.astimezone(self.tz)
        return value

    def _serialize(self, value: datetime | date) -> str:
        if isinstance(value, datetime):
            return self.local(value).isoformat(timespec="minutes")  # type: ignore[union-attr]
        return value.isoformat()

    # --- kalendarze ---

    def calendars(self) -> list[dict[str, Any]]:
        """Kalendarze z wydarzeniami (VEVENT): identyfikator, nazwa, kolor, prawo zapisu."""
        response = self.http.request(
            "PROPFIND",
            self.root,
            headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
            content=PROPFIND_CALENDARS,
        )
        self._check(response, "lista kalendarzy")
        result = []
        for item in ET.fromstring(response.content).findall(f"{DAV}response"):
            props = item.find(f"{DAV}propstat/{DAV}prop")
            if props is None or props.find(f"{DAV}resourcetype/{CALDAV}calendar") is None:
                continue
            components = [
                comp.get("name")
                for comp in props.findall(f"{CALDAV}supported-calendar-component-set/{CALDAV}comp")
            ]
            if components and "VEVENT" not in components:
                continue
            href = unquote(item.findtext(f"{DAV}href", "")).removeprefix(self._root_path).strip("/")
            if self.przedrostek and not href.startswith(self.przedrostek):
                continue
            privileges = {
                child.tag
                for privilege in props.findall(f"{DAV}current-user-privilege-set/{DAV}privilege")
                for child in privilege
            }
            writable = (
                bool(privileges & {f"{DAV}write", f"{DAV}all", f"{DAV}write-content"}) or not privileges
            )
            color = (props.findtext(f"{APPLE}calendar-color") or "").strip()
            result.append(
                {
                    "id": href,
                    "name": props.findtext(f"{DAV}displayname") or href.removeprefix(self.przedrostek),
                    "color": color[:7] if color.startswith("#") else "#7B5CFF",
                    "writable": writable and href != "contact_birthdays",
                    "default": href == self.default_calendar,
                }
            )
        result.sort(key=lambda cal: (not cal["default"], not cal["writable"], cal["name"].lower()))
        return result

    # --- wydarzenia ---

    def events(
        self,
        start: datetime | date,
        end: datetime | date,
        calendar_ids: list[str] | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Wydarzenia w przedziale (wystąpienia cykliczne rozwinięte), posortowane po czasie."""
        start_dt = self._range_bound(start)
        end_dt = self._range_bound(end)
        if end_dt <= start_dt:
            raise CalendarError("Koniec zakresu musi być po jego początku.")
        if end_dt - start_dt > timedelta(days=MAX_RANGE_DAYS):
            raise CalendarError(f"Zakres dat może obejmować najwyżej {MAX_RANGE_DAYS} dni.")
        calendars = self.calendars()
        wanted = [cal for cal in calendars if not calendar_ids or cal["id"] in calendar_ids]
        body = REPORT_EVENTS.format(start=_utc_stamp(start_dt), end=_utc_stamp(end_dt))
        needle = query.strip().lower()
        result: list[dict[str, Any]] = []
        for cal in wanted:
            response = self.http.request(
                "REPORT",
                self._url(cal["id"]),
                headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
                content=body,
            )
            self._check(response, f"odczyt kalendarza {cal['name']}")
            for item in ET.fromstring(response.content).findall(f"{DAV}response"):
                data = item.findtext(f"{DAV}propstat/{DAV}prop/{CALDAV}calendar-data")
                if not data:
                    continue
                name = unquote(item.findtext(f"{DAV}href", "")).rstrip("/").rsplit("/", 1)[-1]
                etag = item.findtext(f"{DAV}propstat/{DAV}prop/{DAV}getetag") or ""
                for event in self._parse(data, f"{cal['id']}/{name}", etag, cal):
                    text = " ".join((event["summary"], event["location"], event["description"])).lower()
                    if not needle or needle in text:
                        result.append(event)
        result.sort(key=lambda event: (event["start"], event["summary"]))
        return result

    def _range_bound(self, value: datetime | date) -> datetime:
        if isinstance(value, datetime):
            return self.local(value)  # type: ignore[return-value]
        return datetime.combine(value, time.min, tzinfo=self.tz)

    def _parse(self, data: str, event_id: str, etag: str, cal: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            parsed = Calendar.from_ical(data)
        except ValueError:
            return []
        events = []
        for component in parsed.walk("VEVENT"):
            start = component.decoded("DTSTART", None)
            if start is None:
                continue
            end = component.decoded("DTEND", None)
            if end is None:
                duration = component.decoded("DURATION", None)
                if duration is not None:
                    end = start + duration
                else:
                    end = start + timedelta(days=1) if not isinstance(start, datetime) else start
            all_day = not isinstance(start, datetime)
            recurrence = component.decoded("RECURRENCE-ID", None)
            events.append(
                {
                    "id": event_id,
                    "uid": str(component.get("UID", "")),
                    "etag": etag,
                    "calendar": cal["id"],
                    "calendar_name": cal["name"],
                    "color": cal["color"],
                    "writable": cal["writable"],
                    "summary": str(component.get("SUMMARY", "")),
                    "location": str(component.get("LOCATION", "")),
                    "description": str(component.get("DESCRIPTION", "")),
                    "start": self._serialize(start),
                    "end": self._serialize(end),
                    "all_day": all_day,
                    "recurring": recurrence is not None or component.get("RRULE") is not None,
                    "recurrence_id": self._serialize(recurrence) if recurrence is not None else None,
                }
            )
        return events

    def _get(self, event_id: str) -> tuple[Calendar, str]:
        calendar_id, name = split_event_id(event_id)
        # Bez kompresji: serwer dopisuje wtedy do ETag przyrostek „-gzip”, którego If-Match nie uzna.
        response = self.http.get(self._url(calendar_id, name), headers={"Accept-Encoding": "identity"})
        self._check(response, "odczyt wydarzenia")
        etag = response.headers.get("etag", "").replace("-gzip", "")
        try:
            return Calendar.from_ical(response.text), etag
        except ValueError as error:
            raise CalendarError("Nie można odczytać wydarzenia (uszkodzony iCalendar).") from error

    def get(self, event_id: str) -> dict[str, Any]:
        """Wydarzenie (wzorzec serii dla wydarzeń cyklicznych)."""
        calendar_id, _name = split_event_id(event_id)
        parsed, etag = self._get(event_id)
        cal = {"id": calendar_id, "name": calendar_id, "color": "#7B5CFF", "writable": True}
        events = self._parse(parsed.to_ical().decode("utf-8"), event_id, etag, cal)
        master = next((event for event in events if event["recurrence_id"] is None), None)
        if master is None and not events:
            raise CalendarError("Wydarzenie jest puste.")
        return master or events[0]

    def _apply(self, event: Event, data: EventData, shift: timedelta | None = None) -> None:
        if data.summary is not None:
            event.pop("SUMMARY", None)
            event.add("summary", data.summary.strip() or "(bez tytułu)")
        for key, value in (("location", data.location), ("description", data.description)):
            if value is not None:
                event.pop(key.upper(), None)
                if value.strip():
                    event.add(key, value.strip())
        start = event.decoded("DTSTART", None)
        end = event.decoded("DTEND", None)
        if end is None and start is not None:
            duration = event.decoded("DURATION", None)
            end = start + duration if duration is not None else start
        if shift is not None and start is not None:
            new_start: datetime | date | None = start + shift
            new_end: datetime | date | None = end + shift if end is not None else None
            if data.start is not None and data.end is not None and type(data.start) is type(data.end):
                new_end = new_start + (self.local(data.end) - self.local(data.start))  # type: ignore[operator]
        else:
            new_start, new_end = data.start, data.end
        if data.all_day is not None or new_start is not None or new_end is not None:
            all_day = (
                data.all_day if data.all_day is not None else not isinstance(new_start or start, datetime)
            )
            start_value = self._normalize(new_start if new_start is not None else start, all_day)
            if new_end is None and start is not None and end is not None and new_start is not None:
                new_end = new_start + (end - start) if type(start) is type(new_start) else None
            end_value = self._normalize(new_end, all_day) if new_end is not None else None
            if end_value is None or end_value <= start_value:  # type: ignore[operator]
                end_value = start_value + (timedelta(days=1) if all_day else timedelta(hours=1))
            for key in ("DTSTART", "DTEND", "DURATION"):
                event.pop(key, None)
            event.add("dtstart", start_value)
            event.add("dtend", end_value)
        if data.reminder_minutes is not None:
            event.subcomponents = [sub for sub in event.subcomponents if sub.name != "VALARM"]
            if data.reminder_minutes > 0:
                alarm = Alarm()
                alarm.add("action", "DISPLAY")
                alarm.add("description", "Przypomnienie")
                alarm.add("trigger", timedelta(minutes=-data.reminder_minutes))
                event.add_component(alarm)
        if data.rrule is not None:
            event.pop("RRULE", None)
            if data.rrule.strip():
                try:
                    event.add("rrule", vRecur.from_ical(data.rrule.strip().removeprefix("RRULE:")))
                except ValueError as error:
                    raise CalendarError(f"Nieprawidłowa reguła powtarzania: {data.rrule}") from error

    def _normalize(self, value: datetime | date | None, all_day: bool) -> datetime | date:
        if value is None:
            raise CalendarError("Brak czasu rozpoczęcia wydarzenia.")
        if all_day:
            if isinstance(value, datetime):
                return (value.astimezone(self.tz) if value.tzinfo else value).date()
            return value
        if not isinstance(value, datetime):
            return datetime.combine(value, time(9, 0), tzinfo=self.tz)
        return self.local(value)  # type: ignore[return-value]

    def _put(self, calendar_id: str, name: str, calendar: Calendar, etag: str | None) -> str:
        try:
            calendar.add_missing_timezones()
        except Exception:  # noqa: BLE001 - brak definicji strefy nie blokuje zapisu (czas UTC nadal poprawny)
            pass
        headers = {"Content-Type": "text/calendar; charset=utf-8"}
        headers.update({"If-Match": etag} if etag else {"If-None-Match": "*"})
        response = self.http.put(self._url(calendar_id, name), content=calendar.to_ical(), headers=headers)
        self._check(response, "zapis wydarzenia")
        return response.headers.get("etag", "")

    def create(self, calendar_id: str | None, data: EventData) -> dict[str, Any]:
        """Tworzy wydarzenie; zwraca je w postaci z ``events``."""
        calendar_id = self._moj_kalendarz(calendar_id or self.default_calendar)
        if data.start is None:
            raise CalendarError("Podaj początek wydarzenia.")
        uid = f"{uuid.uuid4()}@danaco-nexus"
        calendar = Calendar()
        calendar.add("prodid", "-//Danaco Nexus//Kalendarz//PL")
        calendar.add("version", "2.0")
        event = Event()
        event.add("uid", uid)
        event.add("dtstamp", datetime.now(UTC))
        event.add("created", datetime.now(UTC))
        self._apply(event, replace(data, summary=data.summary or "(bez tytułu)"))
        calendar.add_component(event)
        name = f"{uid.split('@')[0]}.ics"
        self._put(calendar_id, name, calendar, None)
        return self.get(f"{calendar_id}/{name}")

    def update(
        self, event_id: str, data: EventData, etag: str | None = None, recurrence_id: str | None = None
    ) -> dict[str, Any]:
        """Zmienia wydarzenie. W serii zmiana czasu wystąpienia przesuwa całą serię o tę samą różnicę."""
        calendar_id, name = split_event_id(event_id)
        parsed, current_etag = self._get(event_id)
        masters = [c for c in parsed.walk("VEVENT") if c.get("RECURRENCE-ID") is None]
        if not masters:
            raise CalendarError("Nie znaleziono wydarzenia w pliku kalendarza.")
        master = masters[0]
        shift = None
        if master.get("RRULE") is not None and data.start is not None and recurrence_id:
            instance = (
                datetime.fromisoformat(recurrence_id)
                if "T" in recurrence_id
                else date.fromisoformat(recurrence_id)
            )
            new_start = self.local(data.start)
            if isinstance(instance, datetime) and isinstance(new_start, datetime):
                shift = new_start - self.local(instance)  # type: ignore[operator]
            elif not isinstance(instance, datetime) and not isinstance(new_start, datetime):
                shift = new_start - instance
            else:
                raise CalendarError("W serii nie można zmienić wydarzenia całodniowego na godzinowe.")
        self._apply(master, data, shift)
        master.pop("DTSTAMP", None)
        master.add("dtstamp", datetime.now(UTC))
        master.pop("LAST-MODIFIED", None)
        master.add("last-modified", datetime.now(UTC))
        sequence = int(master.get("SEQUENCE", 0) or 0) + 1
        master.pop("SEQUENCE", None)
        master.add("sequence", sequence)
        self._put(calendar_id, name, parsed, etag or current_etag or None)
        return self.get(event_id)

    def delete(self, event_id: str, etag: str | None = None) -> None:
        """Usuwa wydarzenie (całą serię); Nextcloud przenosi je do kosza kalendarza."""
        calendar_id, name = split_event_id(event_id)
        headers = {"If-Match": etag} if etag else {}
        response = self.http.delete(self._url(calendar_id, name), headers=headers)
        self._check(response, "usunięcie wydarzenia")


def caldav_url(settings: Settings) -> str:
    """Adres CalDAV do konfiguracji telefonu (DAVx5) i programów pocztowych."""
    base = settings.chmura_public_url or settings.chmura_url
    return f"{base.rstrip('/')}/remote.php/dav"
