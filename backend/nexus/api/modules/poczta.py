"""Moduł Poczta: skrzynki IMAP, czytanie, szkice i wysyłanie wiadomości po zatwierdzeniu.

Każda wysyłka przechodzi przez „oczekującą wiadomość”: przygotowuje ją agent
(narzędzie ``mail_send``) albo formularz w interfejsie, a wysyła wyłącznie
użytkownik przyciskiem (``POST /api/poczta/wyslij/<id>`` z nagłówkiem CSRF).
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import uuid
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from nexus import oczekujace
from nexus.api import conversations
from nexus.api.auth import require_session
from nexus.api.files import _content_disposition
from nexus.config import Settings
from nexus.db import Database, StoredFile
from nexus.mail import (
    Attachment,
    MailClient,
    MailError,
    MailNotConfigured,
    UnknownAccount,
    attachment_part,
    build_message,
    is_configured,
    load_accounts,
    load_config,
    send_message,
    valid_addresses,
)
from nexus.storage import FileStorage

router = APIRouter(prefix="/api/poczta", tags=["poczta"], dependencies=[Depends(require_session)])

IMAGE_LIMIT = 5 * 1024 * 1024
IMAGE_REDIRECTS = 3
SAFE_INLINE = ("image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf", "text/plain")


def _settings(request: Request) -> Settings:
    return request.app.state.settings


async def _mail[T](request: Request, work: Callable[[MailClient], T], account: str = "") -> T:
    """Wykonuje operację IMAP na koncie ``account`` w wątku; błędy poczty zamienia na odpowiedzi HTTP."""
    settings = _settings(request)

    def run() -> T:
        config = load_config(settings, account)
        with MailClient(config, settings.poczta_timeout_s) as client:
            return work(client)

    try:
        return await asyncio.to_thread(run)
    except MailNotConfigured as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except UnknownAccount as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except MailError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error


ACCOUNT = Query("", max_length=200, description="Konto (adres); puste – domyślne.")


class FlagBody(BaseModel):
    konto: str = Field("", max_length=200)
    folder: str = Field(max_length=500)
    uid: int = Field(ge=1)
    flag: str = Field(pattern="^(seen|flagged)$")
    value: bool


class ReplyRef(BaseModel):
    folder: str = Field(max_length=500)
    uid: int = Field(ge=1)


class Draft(BaseModel):
    account: str = Field("", max_length=200)
    signature: bool = True
    to: list[str] = Field(default_factory=list, max_length=50)
    cc: list[str] = Field(default_factory=list, max_length=50)
    bcc: list[str] = Field(default_factory=list, max_length=50)
    subject: str = Field("", max_length=300)
    body: str = Field("", max_length=100_000)
    reply: ReplyRef | None = None
    in_reply_to: str = Field("", max_length=1000)
    references: str = Field("", max_length=5000)
    file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class DraftUpdate(BaseModel):
    account: str | None = Field(None, max_length=200)
    signature: bool | None = None
    to: list[str] | None = Field(None, max_length=50)
    cc: list[str] | None = Field(None, max_length=50)
    bcc: list[str] | None = Field(None, max_length=50)
    subject: str | None = Field(None, max_length=300)
    body: str | None = Field(None, max_length=100_000)
    file_ids: list[uuid.UUID] | None = Field(None, max_length=20)


class NexusReply(BaseModel):
    konto: str = Field("", max_length=200)
    folder: str = Field("INBOX", max_length=500)
    uid: int = Field(ge=1)
    instruction: str = Field("", max_length=5000)


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    try:
        for key in ("to", "cc", "bcc"):
            data[key] = valid_addresses(data.get(key) or [])
    except MailError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    data["file_ids"] = [str(file_id) for file_id in data.get("file_ids") or []]
    return data


def _summary(data: dict[str, Any]) -> str:
    sender = f"Od: {data['account']} · " if data.get("account") else ""
    recipients_text = ", ".join(data.get("to") or ["(brak adresata)"])
    return f"{sender}Do: {recipients_text} – {data.get('subject') or '(bez tematu)'}"


# --- skrzynka ---


@router.get("/stan")
async def mail_state(request: Request) -> dict[str, Any]:
    """Czy poczta jest skonfigurowana (bez łączenia z serwerem) i lista kont (pierwsze – domyślne)."""
    settings = _settings(request)
    if not is_configured(settings):
        return {
            "configured": False,
            "address": "",
            "accounts": [],
            "setup": "sudo -u danaco-serwis deploy/zapisz-poczte.sh",
        }
    try:
        accounts = await asyncio.to_thread(load_accounts, settings)
    except MailError as error:
        return {"configured": False, "address": "", "accounts": [], "error": str(error)}
    return {
        "configured": True,
        "address": accounts[0].address,
        "name": accounts[0].name,
        "accounts": [
            {
                "id": config.id,
                "address": config.address,
                "name": config.name,
                "label": config.label,
                "signature": bool(config.signature_html),
            }
            for config in accounts
        ],
    }


@router.get("/podpis")
async def signature(request: Request, konto: str = ACCOUNT) -> Response:
    """Podgląd podpisu konta (HTML oczyszcza interfejs)."""
    settings = _settings(request)
    try:
        config = await asyncio.to_thread(load_config, settings, konto)
    except UnknownAccount as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except MailError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    return Response(config.signature_html, media_type="text/plain; charset=utf-8")


@router.get("/foldery")
async def folders(request: Request, konto: str = ACCOUNT) -> list[dict[str, Any]]:
    """Foldery z liczbą wiadomości i nieprzeczytanych."""
    return await _mail(request, lambda client: client.folders(with_counts=True), konto)


@router.get("/wiadomosci")
async def messages(
    request: Request,
    folder: str = "INBOX",
    before_uid: int | None = Query(None, ge=1),
    limit: int = Query(40, ge=1, le=200),
    unread: bool = False,
    konto: str = ACCOUNT,
) -> dict[str, Any]:
    """Najnowsze wiadomości folderu (kolejna strona: ``before_uid``)."""
    return await _mail(request, lambda client: client.list_messages(folder, limit, before_uid, unread), konto)


@router.get("/szukaj")
async def search(
    request: Request,
    folder: str = "INBOX",
    q: str = Query("", max_length=200),
    sender: str = Query("", max_length=200),
    since: date | None = None,
    before: date | None = None,
    unread: bool = False,
    konto: str = ACCOUNT,
) -> dict[str, Any]:
    """Wyszukiwanie wiadomości."""
    return await _mail(
        request, lambda client: client.search(folder, q, sender, since, before, unread, 100), konto
    )


@router.get("/wiadomosc")
async def read_message(
    request: Request, folder: str, uid: int = Query(ge=1), mark_seen: bool = True, konto: str = ACCOUNT
) -> dict[str, Any]:
    """Wiadomość z treścią tekstową i HTML (HTML oczyszcza interfejs) oraz listą załączników."""
    return await _mail(request, lambda client: client.read(folder, uid, mark_seen), konto)


@router.get("/zalacznik")
async def attachment(
    request: Request,
    folder: str,
    uid: int = Query(ge=1),
    index: int = Query(ge=0),
    inline: bool = False,
    konto: str = ACCOUNT,
) -> Response:
    """Załącznik (``inline=1`` – obraz osadzony w treści, PDF, tekst)."""
    name, mime, data = await _mail(
        request, lambda client: attachment_part(client.fetch_raw(folder, uid), index), konto
    )
    show_inline = inline and mime in SAFE_INLINE
    return Response(
        data,
        media_type=mime if show_inline else "application/octet-stream",
        headers={
            "Content-Disposition": _content_disposition(name, show_inline),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=600",
        },
    )


@router.post("/flaga")
async def set_flag(payload: FlagBody, request: Request) -> dict[str, bool]:
    """Oznacza wiadomość jako przeczytaną/nieprzeczytaną albo ważną."""
    flag = "\\Seen" if payload.flag == "seen" else "\\Flagged"
    await _mail(
        request,
        lambda client: client.set_flag(payload.folder, payload.uid, flag, payload.value),
        payload.konto,
    )
    return {"ok": True}


# --- zdalne obrazy (na życzenie użytkownika, przez Nexusa – bez ujawniania adresu IP) ---


def _public_host(host: str, port: int) -> bool:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        return False
    addresses = {info[4][0] for info in infos}
    return bool(addresses) and all(
        ipaddress.ip_address(address.split("%")[0]).is_global for address in addresses
    )


def _allowed_url(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        return False
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return False
    return port in (80, 443) and _public_host(parts.hostname, port)


@router.get("/obraz")
async def remote_image(request: Request, url: str = Query(max_length=4000)) -> Response:
    """Pobiera zdalny obraz z treści e-maila (tylko publiczne adresy, porty 80/443, do 5 MB)."""
    transport = getattr(request.app.state, "mail_image_transport", None)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        follow_redirects=False,
        transport=transport,
        headers={"User-Agent": "DanacoNexus/1.0 (podglad obrazow)"},
    ) as client:
        current = url
        for _ in range(IMAGE_REDIRECTS + 1):
            if not await asyncio.to_thread(_allowed_url, current):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Niedozwolony adres obrazu.")
            try:
                async with client.stream("GET", current) as response:
                    if response.is_redirect and "location" in response.headers:
                        current = urljoin(current, response.headers["location"])
                        continue
                    mime = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if response.status_code != 200 or mime not in SAFE_INLINE[:4]:
                        raise HTTPException(status.HTTP_404_NOT_FOUND, "To nie jest obraz.")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > IMAGE_LIMIT:
                            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Obraz jest za duży.")
                    return Response(
                        bytes(data),
                        media_type=mime,
                        headers={
                            "Cache-Control": "private, max-age=86400",
                            "X-Content-Type-Options": "nosniff",
                        },
                    )
            except httpx.HTTPError as error:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Nie udało się pobrać obrazu.") from error
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Za dużo przekierowań.")


# --- oczekujące wiadomości ---


def _database(request: Request) -> Database:
    return request.app.state.database


async def _pending(request: Request, action_id: uuid.UUID) -> Any:
    record = await oczekujace.get(_database(request), action_id, "mail")
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono wiadomości.")
    return record


@router.get("/oczekujace")
async def pending_list(request: Request, all: bool = False) -> list[dict[str, Any]]:  # noqa: A002
    """Wiadomości czekające na wysłanie (``all=1`` – także wysłane i odrzucone)."""
    records = await oczekujace.list_pending(_database(request), "mail", include_finished=all)
    return [oczekujace.payload(record) for record in records]


@router.post("/oczekujace", status_code=status.HTTP_201_CREATED)
async def pending_create(payload: Draft, request: Request) -> dict[str, Any]:
    """Nowa wiadomość z formularza (wysyłana osobnym kliknięciem „Wyślij”)."""
    data = _validate(payload.model_dump(mode="json"))
    record = await oczekujace.create(_database(request), "mail", _summary(data), data)
    return oczekujace.payload(record)


@router.patch("/oczekujace/{action_id}")
async def pending_update(action_id: uuid.UUID, payload: DraftUpdate, request: Request) -> dict[str, Any]:
    """Poprawia oczekującą wiadomość przed wysłaniem."""
    record = await _pending(request, action_id)
    if record.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Tej wiadomości nie można już zmienić.")
    data = dict(record.payload or {})
    data.update(payload.model_dump(mode="json", exclude_none=True))
    data = _validate(data)
    updated = await oczekujace.update(_database(request), action_id, payload=data, summary=_summary(data))
    return oczekujace.payload(updated)


@router.delete("/oczekujace/{action_id}")
async def pending_cancel(action_id: uuid.UUID, request: Request) -> dict[str, Any]:
    """Odrzuca oczekującą wiadomość (nie zostanie wysłana)."""
    record = await _pending(request, action_id)
    if record.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Ta wiadomość nie czeka już na wysłanie.")
    updated = await oczekujace.update(_database(request), action_id, status="cancelled")
    return oczekujace.payload(updated)


async def _attachments(request: Request, file_ids: list[str]) -> list[Attachment]:
    if not file_ids:
        return []
    storage: FileStorage = request.app.state.storage
    limit = _settings(request).poczta_attachments_limit_mb * 1024 * 1024
    ids = [uuid.UUID(file_id) for file_id in file_ids]
    async with _database(request).session() as session:
        records = {
            r.id: r for r in (await session.scalars(select(StoredFile).where(StoredFile.id.in_(ids)))).all()
        }
    if len(records) != len(set(ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono części załączników.")
    if sum(record.size for record in records.values()) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Załączniki są za duże.")
    result = []
    for file_id in ids:
        record = records[file_id]
        data = await asyncio.to_thread(storage.path_of(record).read_bytes)
        result.append(Attachment(record.name, record.mime, data))
    return result


def _message(settings: Settings, data: dict[str, Any], attachments: list[Attachment]) -> Any:
    config = load_config(settings, data.get("account") or "")
    return config, build_message(
        config,
        data.get("to") or [],
        data.get("subject") or "",
        data.get("body") or "",
        data.get("cc") or [],
        data.get("in_reply_to") or "",
        data.get("references") or "",
        attachments,
        signature=data.get("signature", True) is not False,
    )


@router.post("/oczekujace/{action_id}/szkic")
async def pending_to_drafts(action_id: uuid.UUID, request: Request) -> dict[str, Any]:
    """Zapisuje oczekującą wiadomość jako szkic w skrzynce (folder Szkice)."""
    record = await _pending(request, action_id)
    data = dict(record.payload or {})
    attachments = await _attachments(request, data.get("file_ids") or [])
    settings = _settings(request)

    def work(client: MailClient) -> str:
        _config, message = _message(settings, data, attachments)
        return client.append("\\Drafts", message, "(\\Draft \\Seen)")

    folder = await _mail(request, work, data.get("account") or "")
    return {"ok": True, "folder": folder}


@router.post("/wyslij/{action_id}")
async def send(action_id: uuid.UUID, request: Request) -> dict[str, Any]:
    """Wysyła oczekującą wiadomość – wyłącznie na polecenie użytkownika."""
    database = _database(request)
    await _pending(request, action_id)
    record = await oczekujace.claim(database, action_id, "mail")
    if record is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ta wiadomość została już wysłana lub odrzucona.")
    data = dict(record.payload or {})
    settings = _settings(request)
    try:
        if not data.get("to"):
            raise MailError("Wiadomość nie ma adresata.")
        attachments = await _attachments(request, data.get("file_ids") or [])
        config, message = await asyncio.to_thread(_message, settings, data, attachments)
        await asyncio.to_thread(
            send_message, config, message, data.get("bcc") or [], settings.poczta_timeout_s
        )
    except (MailError, HTTPException) as error:
        detail = error.detail if isinstance(error, HTTPException) else str(error)
        await oczekujace.update(database, action_id, status="pending", error=str(detail))
        code = error.status_code if isinstance(error, HTTPException) else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(code, str(detail)) from error
    except BaseException:
        await oczekujace.update(database, action_id, status="pending", error="Wysłanie przerwane.")
        raise
    updated = await oczekujace.update(database, action_id, status="done", error="")
    reply = data.get("reply") or None

    def archive(client: MailClient) -> None:
        # Kopia w „Wysłanych” i oznaczenie oryginału jako „odpowiedziano” – bez wpływu na wynik wysyłki.
        try:
            client.append("\\Sent", message, "(\\Seen)")
        except MailError:
            pass
        if reply:
            try:
                client.set_flag(reply["folder"], int(reply["uid"]), "\\Answered", True)
            except MailError:
                pass

    try:
        await _mail(request, archive, data.get("account") or "")
    except HTTPException:
        pass
    return oczekujace.payload(updated)


# --- odpowiedź przygotowana przez Nexusa ---


@router.post("/odpowiedz-z-nexusem")
async def reply_with_nexus(payload: NexusReply, request: Request) -> dict[str, Any]:
    """Zleca asystentowi szkic odpowiedzi (trafia do „Oczekujących” do sprawdzenia i wysłania)."""
    header = await _mail(request, lambda client: client.read(payload.folder, payload.uid), payload.konto)
    account = f"konto {payload.konto}, " if payload.konto else ""
    sender = (header.get("from") or [{}])[0]
    who = sender.get("name") or sender.get("email") or "nadawcy"
    text = (
        f"Przygotuj odpowiedź na e-mail od {who} „{header.get('subject') or '(bez tematu)'}” "
        f"({account}folder {payload.folder}, UID {payload.uid}). Przeczytaj go narzędziem mail_read, "
        "a gotową odpowiedź przekaż narzędziem mail_send z reply_to_uid i tym samym account – trafi "
        "do „Oczekujących” w module Poczta, gdzie ją sprawdzę i sam wyślę. Pisz po polsku, rzeczowo, "
        "w tonie dopasowanym do wiadomości. Nie wpisuj podpisu – podpis konta dołącza się sam."
    )
    if payload.instruction.strip():
        text += f"\n\nMoje wskazówki do odpowiedzi: {payload.instruction.strip()}"
    created = await conversations.create_conversation(
        conversations.CreateConversation(title=f"Odpowiedź: {header.get('subject') or 'e-mail'}"[:200]),
        request,
    )
    conversation_id = uuid.UUID(created["id"])
    result = await conversations.send_message(conversation_id, conversations.SendMessage(text=text), request)
    return {"conversation_id": str(conversation_id), "run_id": result["run_id"]}
