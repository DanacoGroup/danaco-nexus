"""Poczta e-mail: IMAP (odczyt, wyszukiwanie, szkice) i SMTP (wysyłanie).

Poświadczenia leżą w pliku ``poczta_config_file`` (JSON zapisywany przez
``deploy/zapisz-poczte.sh``, prawa 600). Operacje są synchroniczne (imaplib,
smtplib) – API wywołuje je w wątku (``asyncio.to_thread``), narzędzia agenta
działają w wątku puli. Połączenia wyłącznie szyfrowane (TLS / STARTTLS),
z weryfikacją certyfikatu.

Sprawdzenie konfiguracji: ``python -m nexus.mail sprawdz``.
"""

from __future__ import annotations

import base64
import email
import imaplib
import json
import re
import smtplib
import ssl
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from email.headerregistry import Address
from email.message import EmailMessage, Message
from email.parser import BytesHeaderParser
from email.policy import default as default_policy
from email.utils import format_datetime, formataddr, getaddresses, make_msgid, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from nexus.config import Settings

MAX_LIST = 200
MAX_TEXT = 200_000
MAX_HTML = 1_500_000
HEADER_FIELDS = "FROM TO CC SUBJECT DATE MESSAGE-ID CONTENT-TYPE"
SPECIAL_USE = ("\\Drafts", "\\Sent", "\\Trash", "\\Junk", "\\Archive", "\\Flagged", "\\All")
FALLBACK_NAMES = {
    "\\Drafts": ("drafts", "szkice", "draft", "robocze", "kopie robocze"),
    "\\Sent": ("sent", "wysłane", "sent items", "sent messages", "elementy wysłane"),
    "\\Trash": ("trash", "kosz", "deleted items", "deleted messages"),
    "\\Junk": ("junk", "spam", "junk e-mail"),
}
FOLDER_NAMES_PL = {
    "INBOX": "Odebrane",
    "\\Drafts": "Szkice",
    "\\Sent": "Wysłane",
    "\\Trash": "Kosz",
    "\\Junk": "Spam",
    "\\Archive": "Archiwum",
}
LIST_LINE = re.compile(rb'^\((?P<flags>[^)]*)\)\s+(?P<delim>"(?:[^"\\]|\\.)*"|NIL)\s+(?P<name>.+)$')


class MailError(Exception):
    """Błąd poczty opisany dla użytkownika."""


class MailNotConfigured(MailError):
    """Brak pliku z poświadczeniami poczty."""


@dataclass(slots=True)
class MailConfig:
    """Konto pocztowe."""

    login: str
    password: str = field(repr=False)
    address: str
    name: str = ""
    imap_host: str = "mail.danaco-group.pl"
    imap_port: int = 993
    smtp_host: str = "mail.danaco-group.pl"
    smtp_port: int = 465
    smtp_security: str = "ssl"

    @property
    def sender(self) -> str:
        """Nadawca w nagłówku From."""
        return formataddr((self.name, self.address)) if self.name else self.address


def load_config(settings: Settings) -> MailConfig:
    """Wczytuje konto z pliku; brak lub błąd pliku zgłasza ``MailNotConfigured``."""
    path = Path(settings.poczta_config_file)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise MailNotConfigured(
            "Poczta nie jest skonfigurowana. Na serwerze uruchom: "
            "sudo -u danaco-serwis deploy/zapisz-poczte.sh"
        ) from error
    except (OSError, ValueError) as error:
        raise MailNotConfigured(f"Nie można odczytać konfiguracji poczty: {error}") from error
    if not isinstance(raw, dict) or not raw.get("login") or not raw.get("password"):
        raise MailNotConfigured("Plik konfiguracji poczty nie zawiera loginu i hasła.")
    security = str(raw.get("smtp_security") or "ssl").lower()
    if security not in ("ssl", "starttls"):
        raise MailNotConfigured("smtp_security musi mieć wartość 'ssl' albo 'starttls'.")
    login = str(raw["login"])
    return MailConfig(
        login=login,
        password=str(raw["password"]),
        address=str(raw.get("address") or login),
        name=str(raw.get("name") or ""),
        imap_host=str(raw.get("imap_host") or "mail.danaco-group.pl"),
        imap_port=int(raw.get("imap_port") or 993),
        smtp_host=str(raw.get("smtp_host") or raw.get("imap_host") or "mail.danaco-group.pl"),
        smtp_port=int(raw.get("smtp_port") or (465 if security == "ssl" else 587)),
        smtp_security=security,
    )


def is_configured(settings: Settings) -> bool:
    """Czy plik konfiguracji poczty istnieje."""
    return Path(settings.poczta_config_file).is_file()


# --- zmodyfikowane UTF-7 (RFC 3501) dla nazw folderów, gdy serwer nie obsługuje UTF8=ACCEPT ---


def utf7_decode(name: str) -> str:
    """Dekoduje nazwę folderu IMAP w zmodyfikowanym UTF-7."""

    def replace(match: re.Match[str]) -> str:
        chunk = match.group(1)
        if not chunk:
            return "&"
        data = chunk.replace(",", "/")
        data += "=" * (-len(data) % 4)
        return base64.b64decode(data).decode("utf-16-be")

    return re.sub(r"&([A-Za-z0-9+,]*)-", replace, name)


def utf7_encode(name: str) -> str:
    """Koduje nazwę folderu IMAP w zmodyfikowanym UTF-7."""
    result: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            encoded = base64.b64encode("".join(buffer).encode("utf-16-be")).decode("ascii")
            result.append("&" + encoded.rstrip("=").replace("/", ",") + "-")
            buffer.clear()

    for char in name:
        if 0x20 <= ord(char) <= 0x7E:
            flush()
            result.append("&-" if char == "&" else char)
        else:
            buffer.append(char)
    flush()
    return "".join(result)


def quote_imap(value: str) -> str:
    """Łańcuch w cudzysłowie IMAP."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _unquote(value: bytes) -> str:
    text = value.decode("utf-8", "replace").strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = re.sub(r"\\(.)", r"\1", text[1:-1])
    return text


def _address_list(value: Any) -> list[dict[str, str]]:
    if not value:
        return []
    try:
        pairs = getaddresses([str(value)])
    except (TypeError, ValueError, IndexError):
        return [{"name": "", "email": str(value)}]
    return [{"name": name, "email": addr} for name, addr in pairs if addr or name]


def _date_iso(value: Any) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(str(value)).astimezone().isoformat(timespec="minutes")
    except (TypeError, ValueError, IndexError):
        return None


class _TextExtractor(HTMLParser):
    """Tekst z HTML (bez skryptów i stylów) – dla agenta i podglądu."""

    SKIP = frozenset({"script", "style", "head", "title"})
    BREAK = frozenset({"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "table", "blockquote"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skip += 1
        elif tag in self.BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag in self.BREAK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """Tekst czytelny dla człowieka z treści HTML."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - uszkodzony HTML: zwracamy to, co udało się odczytać
        pass
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def _leaf_parts(message: Message) -> list[Message]:
    return [part for part in message.walk() if not part.is_multipart()]


def _part_info(index: int, part: Message) -> dict[str, Any]:
    payload = part.get_payload(decode=True) or b""
    content_id = (part.get("Content-ID") or "").strip().strip("<>")
    return {
        "index": index,
        "name": part.get_filename() or (f"zalacznik-{index}" if not content_id else f"obraz-{index}"),
        "mime": part.get_content_type(),
        "size": len(payload),
        "content_id": content_id or None,
        "inline": (part.get_content_disposition() or "") != "attachment",
    }


def parse_message(raw: bytes) -> dict[str, Any]:
    """Nagłówki, treść (tekst i HTML) oraz lista załączników wiadomości."""
    message = email.message_from_bytes(raw, policy=default_policy)
    assert isinstance(message, EmailMessage)
    text_part = message.get_body(preferencelist=("plain",))
    html_part = message.get_body(preferencelist=("html",))
    text = _content(text_part) if text_part is not None else ""
    html = _content(html_part) if html_part is not None else ""
    if not text and html:
        text = html_to_text(html)
    body_parts = {id(text_part), id(html_part)}
    attachments = [
        _part_info(index, part)
        for index, part in enumerate(_leaf_parts(message))
        if id(part) not in body_parts
        and (part.get_filename() or part.get("Content-ID") or part.get_content_disposition() == "attachment")
    ]
    return {
        "subject": str(message.get("Subject") or ""),
        "from": _address_list(message.get("From")),
        "to": _address_list(message.get("To")),
        "cc": _address_list(message.get("Cc")),
        "reply_to": _address_list(message.get("Reply-To")),
        "date": _date_iso(message.get("Date")),
        "message_id": str(message.get("Message-ID") or "").strip(),
        "references": str(message.get("References") or "").strip(),
        "text": text[:MAX_TEXT],
        "html": html[:MAX_HTML],
        "attachments": attachments,
    }


def _content(part: Message) -> str:
    try:
        content = part.get_content()  # type: ignore[attr-defined]
    except (LookupError, UnicodeDecodeError, AttributeError):
        payload = part.get_payload(decode=True) or b""
        content = payload.decode("utf-8", "replace")
    return content if isinstance(content, str) else ""


def attachment_part(raw: bytes, index: int) -> tuple[str, str, bytes]:
    """Nazwa, typ MIME i zawartość części ``index`` (numeracja jak w ``parse_message``)."""
    message = email.message_from_bytes(raw, policy=default_policy)
    parts = _leaf_parts(message)
    if not 0 <= index < len(parts):
        raise MailError("Nie ma takiego załącznika.")
    info = _part_info(index, parts[index])
    return info["name"], info["mime"], parts[index].get_payload(decode=True) or b""


def _fetch_items(response: list[Any]) -> list[tuple[bytes, bytes]]:
    """Pary (opis odpowiedzi FETCH, dane literału) z wyniku imaplib."""
    items: list[tuple[bytes, bytes]] = []
    for index, entry in enumerate(response):
        if isinstance(entry, tuple):
            trailer = response[index + 1] if index + 1 < len(response) else b""
            description = entry[0] + (trailer if isinstance(trailer, bytes) else b"")
            items.append((description, entry[1]))
        elif isinstance(entry, bytes) and entry.strip() not in (b")", b""):
            items.append((entry, b""))
    return items


def _flags(description: bytes) -> list[str]:
    match = re.search(rb"FLAGS \(([^)]*)\)", description)
    return match.group(1).decode("utf-8", "replace").split() if match else []


def _number(name: bytes, description: bytes) -> int | None:
    match = re.search(name + rb" (\d+)", description)
    return int(match.group(1)) if match else None


def imap_date(value: date) -> str:
    """Data w formacie wyszukiwania IMAP (np. 19-Sep-2026)."""
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{value.day}-{months[value.month - 1]}-{value.year}"


class MailClient:
    """Połączenie IMAP z kontem (menedżer kontekstu)."""

    def __init__(self, config: MailConfig, timeout: float = 30) -> None:
        self.config = config
        self.timeout = timeout
        self.imap: imaplib.IMAP4 | None = None
        self.utf8 = False
        self._folders: list[dict[str, Any]] | None = None

    def __enter__(self) -> MailClient:
        context = ssl.create_default_context()
        try:
            imap = imaplib.IMAP4_SSL(
                self.config.imap_host, self.config.imap_port, ssl_context=context, timeout=self.timeout
            )
        except (OSError, imaplib.IMAP4.error) as error:
            raise MailError(
                f"Nie można połączyć się z serwerem poczty {self.config.imap_host}: {error}"
            ) from error
        try:
            if self.config.password.isascii() and self.config.login.isascii():
                imap.login(self.config.login, self.config.password)
            else:
                secret = f"\0{self.config.login}\0{self.config.password}".encode()
                imap.authenticate("PLAIN", lambda _challenge: secret)
        except imaplib.IMAP4.error as error:
            imap.shutdown()
            raise MailError("Serwer poczty odrzucił login lub hasło.") from error
        self.imap = imap
        if "UTF8=ACCEPT" in getattr(imap, "capabilities", ()):
            try:
                imap.enable("UTF8=ACCEPT")
                self.utf8 = True
            except imaplib.IMAP4.error:
                self.utf8 = False
        return self

    def __exit__(self, *_exc: object) -> None:
        if self.imap is not None:
            try:
                self.imap.logout()
            except (OSError, imaplib.IMAP4.error):
                pass
            self.imap = None

    # --- pomocnicze ---

    @property
    def _conn(self) -> imaplib.IMAP4:
        if self.imap is None:
            raise MailError("Brak połączenia z serwerem poczty.")
        return self.imap

    def _mailbox(self, name: str) -> str:
        return quote_imap(name if self.utf8 else utf7_encode(name))

    def _ok(self, result: tuple[str, list[Any]], action: str) -> list[Any]:
        status, data = result
        if status != "OK":
            detail = b" ".join(item for item in data if isinstance(item, bytes)).decode("utf-8", "replace")
            raise MailError(f"Poczta: {action} nie powiodło się ({detail or status}).")
        return data

    def _select(self, folder: str, readonly: bool = True) -> int:
        try:
            result, data = self._conn.select(self._mailbox(folder), readonly=readonly)
        except imaplib.IMAP4.error as error:
            raise MailError(f"Nie ma folderu {folder}.") from error
        if result != "OK":
            raise MailError(f"Nie ma folderu {folder}.")
        try:
            return int(data[0])
        except (TypeError, ValueError, IndexError):
            return 0

    # --- foldery ---

    def folders(self, with_counts: bool = False) -> list[dict[str, Any]]:
        """Foldery konta z rolą (Szkice, Wysłane…) i opcjonalnie liczbą wiadomości."""
        if self._folders is None:
            found: list[dict[str, Any]] = []
            for line in self._ok(self._conn.list(), "lista folderów"):
                raw = line[0] + line[1] if isinstance(line, tuple) else line
                if not isinstance(raw, bytes):
                    continue
                match = LIST_LINE.match(raw.strip())
                if not match:
                    continue
                flags = match.group("flags").decode("utf-8", "replace").split()
                if any(flag.lower() == "\\noselect" or flag.lower() == "\\nonexistent" for flag in flags):
                    continue
                name = _unquote(match.group("name"))
                if not self.utf8:
                    name = utf7_decode(name)
                role = next((flag for flag in flags if flag in SPECIAL_USE), None)
                if name.upper() == "INBOX":
                    name, role = "INBOX", "INBOX"
                found.append({"name": name, "role": role})
            for role, names in FALLBACK_NAMES.items():
                if not any(entry["role"] == role for entry in found):
                    candidate = next(
                        (e for e in found if e["role"] is None and e["name"].lower() in names), None
                    )
                    if candidate:
                        candidate["role"] = role
            order = ["INBOX", "\\Drafts", "\\Sent", "\\Archive", "\\Junk", "\\Trash"]
            found.sort(
                key=lambda e: (order.index(e["role"]) if e["role"] in order else 99, e["name"].lower())
            )
            for entry in found:
                entry["label"] = FOLDER_NAMES_PL.get(entry["role"] or "", entry["name"])
            self._folders = found
        if with_counts:
            for entry in self._folders:
                entry.update(self.folder_status(entry["name"]))
        return [dict(entry) for entry in self._folders]

    def folder_status(self, folder: str) -> dict[str, int]:
        """Liczba wiadomości i nieprzeczytanych w folderze."""
        try:
            data = self._ok(self._conn.status(self._mailbox(folder), "(MESSAGES UNSEEN)"), "stan folderu")
        except (MailError, imaplib.IMAP4.error):
            return {"messages": 0, "unseen": 0}
        text = b" ".join(item for item in data if isinstance(item, bytes))
        return {
            "messages": _number(rb"MESSAGES", text) or 0,
            "unseen": _number(rb"UNSEEN", text) or 0,
        }

    def folder_by_role(self, role: str) -> str | None:
        """Nazwa folderu o danej roli (np. ``\\Drafts``)."""
        return next((entry["name"] for entry in self.folders() if entry["role"] == role), None)

    # --- wiadomości ---

    def _search(self, criteria: list[str], literal: str | None = None) -> list[int]:
        conn = self._conn
        if literal is not None:
            if self.utf8 or literal.isascii():
                criteria = [*criteria, quote_imap(literal)]
            else:
                conn.literal = literal.encode("utf-8")  # type: ignore[attr-defined]
                criteria = ["CHARSET", "UTF-8", *criteria]
        data = self._ok(conn.uid("SEARCH", *(criteria or ["ALL"])), "wyszukiwanie")
        numbers = b" ".join(item for item in data if isinstance(item, bytes)).split()
        return sorted({int(number) for number in numbers if number.isdigit()})

    def _headers(self, uids: list[int]) -> list[dict[str, Any]]:
        if not uids:
            return []
        data = self._ok(
            self._conn.uid(
                "FETCH",
                ",".join(str(uid) for uid in uids),
                f"(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.FIELDS ({HEADER_FIELDS})])",
            ),
            "pobranie nagłówków",
        )
        parser = BytesHeaderParser(policy=default_policy)
        result = []
        for description, header_bytes in _fetch_items(data):
            uid = _number(rb"UID", description)
            if uid is None:
                continue
            headers = parser.parsebytes(header_bytes)
            flags = _flags(description)
            content_type = str(headers.get("Content-Type") or "").lower()
            result.append(
                {
                    "uid": uid,
                    "subject": str(headers.get("Subject") or ""),
                    "from": _address_list(headers.get("From")),
                    "to": _address_list(headers.get("To")),
                    "date": _date_iso(headers.get("Date")),
                    "seen": "\\Seen" in flags,
                    "flagged": "\\Flagged" in flags,
                    "answered": "\\Answered" in flags,
                    "has_attachments": content_type.startswith("multipart/mixed"),
                    "size": _number(rb"RFC822.SIZE", description) or 0,
                }
            )
        result.sort(key=lambda item: item["uid"], reverse=True)
        return result

    def list_messages(
        self, folder: str = "INBOX", limit: int = 30, before_uid: int | None = None, unread_only: bool = False
    ) -> dict[str, Any]:
        """Najnowsze wiadomości folderu (stronicowanie: ``before_uid``)."""
        self._select(folder)
        uids = self._search(["UNSEEN"] if unread_only else ["ALL"])
        if before_uid is not None:
            uids = [uid for uid in uids if uid < before_uid]
        limit = max(1, min(limit, MAX_LIST))
        page = uids[-limit:]
        return {
            "folder": folder,
            "total": len(uids),
            "messages": self._headers(page),
            "more": len(uids) > len(page),
        }

    def search(
        self,
        folder: str = "INBOX",
        text: str = "",
        sender: str = "",
        since: date | None = None,
        before: date | None = None,
        unread_only: bool = False,
        limit: int = 30,
    ) -> dict[str, Any]:
        """Wyszukiwanie wiadomości (treść, nadawca, zakres dat, nieprzeczytane)."""
        self._select(folder)
        criteria: list[str] = []
        if unread_only:
            criteria.append("UNSEEN")
        if since:
            criteria += ["SINCE", imap_date(since)]
        if before:
            criteria += ["BEFORE", imap_date(before)]
        if sender:
            if sender.isascii() or self.utf8:
                criteria += ["FROM", quote_imap(sender)]
            else:
                text = f"{sender} {text}".strip()
        literal = None
        if text:
            criteria.append("TEXT")
            literal = text
        uids = self._search(criteria or ["ALL"], literal)
        limit = max(1, min(limit, MAX_LIST))
        return {
            "folder": folder,
            "total": len(uids),
            "messages": self._headers(uids[-limit:]),
            "more": len(uids) > limit,
        }

    def fetch_raw(self, folder: str, uid: int) -> bytes:
        """Cała wiadomość (bez oznaczania jako przeczytanej)."""
        self._select(folder)
        data = self._ok(self._conn.uid("FETCH", str(uid), "(UID BODY.PEEK[])"), "pobranie wiadomości")
        for _description, content in _fetch_items(data):
            if content:
                return content
        raise MailError(f"Nie ma wiadomości {uid} w folderze {folder}.")

    def read(self, folder: str, uid: int, mark_seen: bool = False) -> dict[str, Any]:
        """Wiadomość z treścią i listą załączników."""
        raw = self.fetch_raw(folder, uid)
        message = parse_message(raw)
        message.update({"uid": uid, "folder": folder, "size": len(raw)})
        if mark_seen:
            self.set_flag(folder, uid, "\\Seen", True)
        return message

    def set_flag(self, folder: str, uid: int, flag: str, value: bool) -> None:
        """Ustawia lub zdejmuje flagę (``\\Seen``, ``\\Flagged``)."""
        if flag not in ("\\Seen", "\\Flagged", "\\Answered"):
            raise MailError("Nieobsługiwana flaga.")
        self._select(folder, readonly=False)
        self._ok(
            self._conn.uid("STORE", str(uid), "+FLAGS" if value else "-FLAGS", f"({flag})"),
            "zmiana flagi",
        )

    def append(self, role: str, message: EmailMessage, flags: str) -> str:
        """Dopisuje wiadomość do folderu o danej roli (Szkice, Wysłane); zwraca nazwę folderu."""
        folder = self.folder_by_role(role)
        if folder is None:
            folder = "Drafts" if role == "\\Drafts" else "Sent"
            try:
                self._conn.create(self._mailbox(folder))
            except imaplib.IMAP4.error:
                pass
            self._folders = None
        self._ok(
            self._conn.append(
                self._mailbox(folder),
                flags,
                imaplib.Time2Internaldate(time.time()),
                message.as_bytes(policy=default_policy.clone(linesep="\r\n")),
            ),
            f"zapis w folderze {folder}",
        )
        return folder


# --- tworzenie i wysyłanie wiadomości ---


def valid_addresses(values: list[str]) -> list[str]:
    result = []
    for value in values:
        for name, address in getaddresses([value]):
            if not re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", address or ""):
                raise MailError(f"Nieprawidłowy adres e-mail: {value}")
            result.append(formataddr((name, address)) if name else address)
    return result


@dataclass(slots=True)
class Attachment:
    """Załącznik wiadomości wychodzącej."""

    name: str
    mime: str
    data: bytes


def build_message(
    config: MailConfig,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    in_reply_to: str = "",
    references: str = "",
    attachments: list[Attachment] | None = None,
) -> EmailMessage:
    """Wiadomość gotowa do wysłania lub zapisania jako szkic."""
    message = EmailMessage()
    message["From"] = config.sender
    if to:
        message["To"] = ", ".join(valid_addresses(to))
    if cc:
        message["Cc"] = ", ".join(valid_addresses(cc))
    message["Subject"] = subject
    message["Date"] = format_datetime(datetime.now().astimezone())
    domain = config.address.rsplit("@", 1)[-1] if "@" in config.address else None
    message["Message-ID"] = make_msgid(domain=domain)
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = f"{references} {in_reply_to}".strip()
    message.set_content(body)
    for attachment in attachments or []:
        maintype, _, subtype = (attachment.mime or "application/octet-stream").partition("/")
        message.add_attachment(
            attachment.data, maintype=maintype, subtype=subtype or "octet-stream", filename=attachment.name
        )
    return message


def recipients(message: EmailMessage, bcc: list[str] | None = None) -> list[str]:
    """Adresy wszystkich odbiorców (To, Cc, Bcc)."""
    values = [str(message.get(name) or "") for name in ("To", "Cc")] + list(bcc or [])
    return [address for _name, address in getaddresses(values) if address]


def send_message(
    config: MailConfig, message: EmailMessage, bcc: list[str] | None = None, timeout: float = 30
) -> None:
    """Wysyła wiadomość przez SMTP (TLS albo STARTTLS) z logowaniem."""
    to_addrs = recipients(message, valid_addresses(bcc or []))
    if not to_addrs:
        raise MailError("Wiadomość nie ma odbiorców.")
    context = ssl.create_default_context()
    try:
        if config.smtp_security == "ssl":
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(
                config.smtp_host, config.smtp_port, context=context, timeout=timeout
            )
        else:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=timeout)
            smtp.starttls(context=context)
        with smtp:
            smtp.login(config.login, config.password)
            smtp.send_message(message, from_addr=config.address, to_addrs=to_addrs)
    except smtplib.SMTPAuthenticationError as error:
        raise MailError("Serwer SMTP odrzucił login lub hasło.") from error
    except smtplib.SMTPRecipientsRefused as error:
        raise MailError(f"Serwer odrzucił odbiorców: {', '.join(error.recipients)}") from error
    except (smtplib.SMTPException, OSError) as error:
        raise MailError(f"Wysłanie nie powiodło się: {error}") from error


def reply_headers(original: dict[str, Any]) -> dict[str, str]:
    """Temat, adresat i nagłówki wątku odpowiedzi na wiadomość ``original`` (z ``parse_message``)."""
    subject = original.get("subject", "")
    if not re.match(r"^\s*(re|odp)\s*:", subject, re.IGNORECASE):
        subject = f"Re: {subject}"
    sender = (original.get("reply_to") or original.get("from") or [{}])[0]
    to = str(Address(sender.get("name", ""), addr_spec=sender["email"])) if sender.get("email") else ""
    return {
        "subject": subject,
        "to": to,
        "in_reply_to": original.get("message_id", ""),
        "references": original.get("references", ""),
    }


def quote_body(original: dict[str, Any]) -> str:
    """Cytat oryginału dopisywany pod odpowiedzią."""
    sender = (original.get("from") or [{}])[0]
    who = sender.get("name") or sender.get("email") or "nadawca"
    when = original.get("date") or ""
    quoted = "\n".join(f"> {line}" for line in (original.get("text") or "").splitlines()[:200])
    return f"\n\n{when} {who} napisał(a):\n{quoted}"


def check(settings: Settings) -> int:
    """Sprawdza logowanie IMAP i SMTP (bez wysyłania); zwraca kod wyjścia."""
    try:
        config = load_config(settings)
    except MailNotConfigured as error:
        print(error, file=sys.stderr)
        return 1
    try:
        with MailClient(config, settings.poczta_timeout_s) as client:
            folders = client.folders()
        print(f"IMAP {config.imap_host}:{config.imap_port}: zalogowano, folderów: {len(folders)}")
    except MailError as error:
        print(f"IMAP: {error}", file=sys.stderr)
        return 1
    try:
        context = ssl.create_default_context()
        if config.smtp_security == "ssl":
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(
                config.smtp_host, config.smtp_port, context=context, timeout=30
            )
        else:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
            smtp.starttls(context=context)
        with smtp:
            smtp.login(config.login, config.password)
        print(f"SMTP {config.smtp_host}:{config.smtp_port} ({config.smtp_security}): zalogowano")
    except (smtplib.SMTPException, OSError) as error:
        print(f"SMTP: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    from nexus.config import get_settings

    if sys.argv[1:] != ["sprawdz"]:
        print("Użycie: python -m nexus.mail sprawdz", file=sys.stderr)
        sys.exit(2)
    sys.exit(check(get_settings()))
