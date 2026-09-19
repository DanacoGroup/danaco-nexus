"""Wspólne atrapy testów modułu biuro: zalogowany klient API, serwer IMAP/SMTP, serwer CalDAV."""

from __future__ import annotations

import asyncio
import email
import imaplib
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from email.policy import default as default_policy
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from nexus.api.app import create_app
from nexus.api.auth import set_admin_credentials
from nexus.config import Settings
from nexus.db import Database

PASSWORD = "bardzo-tajne-haslo-2026"
HEADERS = {"X-Nexus-Request": "1"}


def make_settings(tmp_path: Path) -> Settings:
    """Ustawienia testowe z bazą SQLite w pliku (dostępną także z wątków narzędzi)."""
    token = tmp_path / "chmura-token"
    token.write_text("token-testowy\n", encoding="utf-8")
    return Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        cookie_secure=False,
        cookie_domain="",
        public_url="",
        chmura_url="http://chmura.test",
        chmura_public_url="https://cloud.example.pl",
        chmura_user="admin",
        chmura_token_file=token,
        poczta_config_file=tmp_path / "poczta.json",
        redis_url="",
        voice_warm_up=False,
        voice_stt_model_dir=tmp_path / "brak-modelu",
        voice_tts_dir=tmp_path / "brak-glosow",
        voice_google_key_file=tmp_path / "brak-klucza-google",
        qdrant_url="http://127.0.0.1:1",
    )


def create_schema(settings: Settings, password: bool = False) -> None:
    async def run() -> None:
        database = Database(settings.database_url)
        await database.create_schema()
        if password:
            await set_admin_credentials(database, "admin", PASSWORD)
        await database.close()

    asyncio.run(run())


@pytest.fixture
def biuro_settings(tmp_path: Path) -> Settings:
    settings = make_settings(tmp_path)
    create_schema(settings, password=True)
    return settings


@pytest.fixture
def api(biuro_settings: Settings) -> Iterator[TestClient]:
    """Klient API zalogowany jako administrator."""
    with TestClient(create_app(biuro_settings)) as client:
        response = client.post(
            "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
        )
        assert response.status_code == 200, response.text
        yield client


# --- atrapa serwera IMAP i SMTP ---


def raw_message(
    subject: str,
    sender: str = "Jan Kowalski <jan@example.pl>",
    body: str = "Treść",
    html: str | None = None,
    attachment: tuple[str, bytes] | None = None,
    message_id: str = "<m1@example.pl>",
) -> bytes:
    message = email.message.EmailMessage()
    message["From"] = sender
    message["To"] = "biuro@danaco-group.pl"
    message["Subject"] = subject
    message["Date"] = "Fri, 18 Sep 2026 10:15:00 +0200"
    message["Message-ID"] = message_id
    message.set_content(body)
    if html is not None:
        message.add_alternative(html, subtype="html")
    if attachment is not None:
        message.add_attachment(attachment[1], maintype="application", subtype="pdf", filename=attachment[0])
    return message.as_bytes(policy=default_policy.clone(linesep="\r\n"))


@dataclass
class StoredMail:
    uid: int
    raw: bytes
    flags: set[str] = field(default_factory=set)


class MailServer:
    """Stan atrapy serwera poczty (skrzynki, wysłane wiadomości)."""

    def __init__(self) -> None:
        self.password = "haslo-poczty"
        self.boxes: dict[str, list[StoredMail]] = {"INBOX": [], "Drafts": [], "Wysłane": []}
        self.sent: list[tuple[list[str], bytes]] = []
        self.smtp_fail = False
        self.logins: list[str] = []

    def add(self, box: str, raw: bytes, flags: set[str] | None = None) -> int:
        messages = self.boxes[box]
        uid = (messages[-1].uid if messages else 0) + 1
        messages.append(StoredMail(uid, raw, set(flags or ())))
        return uid


def _unquote(value: str) -> str:
    if value.startswith('"') and value.endswith('"'):
        return re.sub(r"\\(.)", r"\1", value[1:-1])
    return value


def _searchable(raw: bytes) -> str:
    message = email.message_from_bytes(raw, policy=default_policy)
    body = message.get_body(preferencelist=("plain",))
    content = body.get_content() if body is not None else ""  # type: ignore[union-attr]
    return f"{message['Subject']} {message['From']} {content}".lower()


class FakeIMAP:
    """Podzbiór imaplib.IMAP4_SSL wystarczający dla nexus.mail."""

    server: MailServer

    def __init__(self, host: str, port: int, ssl_context: Any = None, timeout: float | None = None) -> None:
        self.capabilities = ("IMAP4REV1", "UTF8=ACCEPT")
        self.selected: str | None = None
        self.literal: bytes | None = None

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        if password != self.server.password:
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        self.server.logins.append(f"imap:{user}")
        return "OK", [b"zalogowano"]

    def enable(self, capability: str) -> tuple[str, list[bytes]]:
        return "OK", [b""]

    def list(self) -> tuple[str, list[bytes]]:
        return "OK", [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Drafts) "/" "Drafts"',
            b'(\\HasNoChildren \\Sent) "/" "Wys\xc5\x82ane"',
            b'(\\Noselect \\HasChildren) "/" "Stare"',
        ]

    def status(self, mailbox: str, items: str) -> tuple[str, list[bytes]]:
        box = self.server.boxes[_unquote(mailbox)]
        unseen = sum("\\Seen" not in mail.flags for mail in box)
        return "OK", [f"{mailbox} (MESSAGES {len(box)} UNSEEN {unseen})".encode()]

    def select(self, mailbox: str, readonly: bool = False) -> tuple[str, list[bytes]]:
        name = _unquote(mailbox)
        if name not in self.server.boxes:
            return "NO", [b"Mailbox does not exist"]
        self.selected = name
        return "OK", [str(len(self.server.boxes[name])).encode()]

    def _box(self) -> list[StoredMail]:
        assert self.selected is not None
        return self.server.boxes[self.selected]

    def uid(self, command: str, *args: str) -> tuple[str, list[Any]]:
        if command == "SEARCH":
            return "OK", [" ".join(str(mail.uid) for mail in self._search(list(args))).encode()]
        if command == "FETCH":
            wanted = {int(uid) for uid in args[0].split(",")}
            result: list[Any] = []
            for index, mail in enumerate(self._box(), 1):
                if mail.uid not in wanted:
                    continue
                flags = " ".join(sorted(mail.flags))
                if "HEADER.FIELDS" in args[1]:
                    data = mail.raw.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
                    label = "BODY[HEADER.FIELDS (FROM TO)]"
                else:
                    data, label = mail.raw, "BODY[]"
                size = len(mail.raw)
                prefix = f"{index} (UID {mail.uid} FLAGS ({flags}) RFC822.SIZE {size} {label} {{{len(data)}}}"
                result.extend([(prefix.encode(), data), b")"])
            return "OK", result
        if command == "STORE":
            uid, mode, flags = int(args[0]), args[1], args[2].strip("()").split()
            for mail in self._box():
                if mail.uid == uid:
                    mail.flags = mail.flags | set(flags) if mode == "+FLAGS" else mail.flags - set(flags)
            return "OK", [b""]
        raise AssertionError(f"Nieobsługiwane polecenie {command}")

    def _search(self, criteria: list[str]) -> list[StoredMail]:
        found = list(self._box())
        tokens = list(criteria)
        if self.literal is not None:
            tokens.append('"' + self.literal.decode("utf-8") + '"')
            self.literal = None
        while tokens:
            token = tokens.pop(0)
            if token in ("ALL", "CHARSET", "UTF-8"):
                continue
            if token == "UNSEEN":
                found = [mail for mail in found if "\\Seen" not in mail.flags]
            elif token in ("TEXT", "FROM"):
                needle = _unquote(tokens.pop(0)).lower()
                found = [mail for mail in found if needle in _searchable(mail.raw)]
            elif token in ("SINCE", "BEFORE"):
                tokens.pop(0)
        return found

    def append(self, mailbox: str, flags: str, date_time: str, message: bytes) -> tuple[str, list[bytes]]:
        name = _unquote(mailbox)
        self.server.add(name, message, set(flags.strip("()").split()))
        return "OK", [b"APPEND completed"]

    def create(self, mailbox: str) -> tuple[str, list[bytes]]:
        self.server.boxes.setdefault(_unquote(mailbox), [])
        return "OK", [b""]

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b""]

    def shutdown(self) -> None:
        return None


class FakeSMTP:
    """Atrapa smtplib.SMTP_SSL zapisująca wysłane wiadomości."""

    server: MailServer

    def __init__(self, host: str, port: int, context: Any = None, timeout: float | None = None) -> None:
        self.logged_in = False

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def login(self, user: str, password: str) -> None:
        import smtplib

        if password != self.server.password:
            raise smtplib.SMTPAuthenticationError(535, b"Bad credentials")
        self.server.logins.append(f"smtp:{user}")
        self.logged_in = True

    def send_message(
        self, message: Any, from_addr: str | None = None, to_addrs: list[str] | None = None
    ) -> None:
        import smtplib

        assert self.logged_in
        if self.server.smtp_fail:
            raise smtplib.SMTPServerDisconnected("Połączenie zerwane")
        self.server.sent.append((list(to_addrs or []), message.as_bytes()))


@pytest.fixture
def mail_server(monkeypatch: pytest.MonkeyPatch, biuro_settings: Settings) -> MailServer:
    """Atrapa serwera poczty i plik konfiguracji konta."""
    import json

    server = MailServer()
    imap_class = type("FakeIMAPBound", (FakeIMAP,), {"server": server})
    smtp_class = type("FakeSMTPBound", (FakeSMTP,), {"server": server})
    monkeypatch.setattr(imaplib, "IMAP4_SSL", imap_class)
    import smtplib

    monkeypatch.setattr(smtplib, "SMTP_SSL", smtp_class)
    Path(biuro_settings.poczta_config_file).write_text(
        json.dumps(
            {
                "login": "biuro@danaco-group.pl",
                "password": server.password,
                "name": "Biuro Danaco",
                "imap_host": "mail.test",
                "smtp_host": "mail.test",
            }
        ),
        encoding="utf-8",
    )
    return server


# --- atrapa serwera CalDAV (Nextcloud) ---


class FakeCalDAV:
    """Kalendarze w pamięci obsługiwane przez httpx.MockTransport."""

    ROOT = "/remote.php/dav/calendars/admin/"

    def __init__(self) -> None:
        self.objects: dict[str, dict[str, tuple[str, str]]] = {"personal": {}, "contact_birthdays": {}}
        self.counter = 0
        self.requests: list[tuple[str, str]] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def _etag(self) -> str:
        self.counter += 1
        return f'"etag-{self.counter}"'

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = httpx.URL(str(request.url)).path
        self.requests.append((request.method, path))
        if request.headers.get("authorization", "") == "":
            return httpx.Response(401)
        if request.method == "PROPFIND" and path == self.ROOT:
            return httpx.Response(207, content=self._calendars())
        relative = path.removeprefix(self.ROOT).strip("/")
        calendar, _, name = relative.partition("/")
        if calendar not in self.objects:
            return httpx.Response(404)
        store = self.objects[calendar]
        if request.method == "REPORT":
            return httpx.Response(207, content=self._report(calendar))
        if request.method == "GET":
            if name not in store:
                return httpx.Response(404)
            data, etag = store[name]
            return httpx.Response(200, text=data, headers={"etag": etag})
        if request.method == "PUT":
            if calendar == "contact_birthdays":
                return httpx.Response(403)
            if request.headers.get("if-none-match") == "*" and name in store:
                return httpx.Response(412)
            match = request.headers.get("if-match")
            if match and (name not in store or store[name][1] != match):
                return httpx.Response(412)
            etag = self._etag()
            store[name] = (request.content.decode("utf-8"), etag)
            return httpx.Response(201 if not match else 204, headers={"etag": etag})
        if request.method == "DELETE":
            if name not in store:
                return httpx.Response(404)
            match = request.headers.get("if-match")
            if match and store[name][1] != match:
                return httpx.Response(412)
            del store[name]
            return httpx.Response(204)
        return httpx.Response(405)

    def _calendars(self) -> bytes:
        def entry(name: str, display: str, color: str, writable: bool) -> str:
            privileges = "<d:privilege><d:read/></d:privilege>" + (
                "<d:privilege><d:write/></d:privilege>" if writable else ""
            )
            return (
                f"<d:response><d:href>{self.ROOT}{name}/</d:href><d:propstat><d:prop>"
                "<d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>"
                f"<d:displayname>{display}</d:displayname><x1:calendar-color>{color}FF</x1:calendar-color>"
                '<cal:supported-calendar-component-set><cal:comp name="VEVENT"/>'
                "</cal:supported-calendar-component-set>"
                f"<d:current-user-privilege-set>{privileges}</d:current-user-privilege-set>"
                "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
            )

        body = (
            '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav" '
            'xmlns:x1="http://apple.com/ns/ical/">'
            f"<d:response><d:href>{self.ROOT}</d:href><d:propstat><d:prop><d:resourcetype><d:collection/>"
            "</d:resourcetype></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
            + entry("personal", "Osobiste", "#00679e", True)
            + entry("contact_birthdays", "Urodziny kontaktu", "#E9D859", False)
            + f"<d:response><d:href>{self.ROOT}inbox/</d:href><d:propstat><d:prop><d:resourcetype>"
            "<d:collection/><cal:schedule-inbox/></d:resourcetype></d:prop>"
            "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
            "</d:multistatus>"
        )
        return body.encode("utf-8")

    def _report(self, calendar: str) -> bytes:
        from xml.sax.saxutils import escape

        parts = []
        for name, (data, etag) in self.objects[calendar].items():
            parts.append(
                f"<d:response><d:href>{self.ROOT}{calendar}/{name}</d:href><d:propstat><d:prop>"
                f"<d:getetag>{escape(etag)}</d:getetag><cal:calendar-data>{escape(data)}</cal:calendar-data>"
                "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
            )
        return (
            '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">'
            + "".join(parts)
            + "</d:multistatus>"
        ).encode("utf-8")
