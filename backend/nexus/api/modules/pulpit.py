"""Nexus Desktop: połączenie WebSocket komputerów i przekaźnik narzędzi ``pc_*``.

Protokół (JSON, jeden obiekt na komunikat):

* komputer → serwer: ``{"type": "auth", "token": "nxd_…", "host", "version", "platform"}``
  (pierwszy komunikat; zamiast niego można wysłać nagłówek ``Authorization: Bearer nxd_…``),
  ``{"type": "ping"}``, ``{"type": "response", "id", "ok", "result" | "error"}``;
* serwer → komputer: ``{"type": "ready", "device"}``, ``{"type": "pong"}``,
  ``{"type": "request", "id", "tool", "args"}``, ``{"type": "cancel", "id"}``,
  ``{"type": "error", "message"}``.

Trasy HTTP wymagają sesji (``require_session``) każda z osobna – WebSocket uwierzytelnia
się kluczem urządzenia rodzaju ``desktop`` i nie przechodzi przez zależność sesji.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
import uuid
from functools import partial
from typing import Any

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from nexus.api.auth import DEVICE_TOKEN_PREFIX, require_session, token_hash
from nexus.db import Database, DeviceToken, UserSession, utcnow
from nexus.pulpit import (
    MemoryBroker,
    RedisAsyncBroker,
    async_broker,
    online_computers,
    request_channel,
    response_channel,
    sync_broker,
)

logger = logging.getLogger(__name__)

#: Ile czekamy na dokończenie zadania przekazującego po rozłączeniu komputera.
#:
#: Sprzątanie nie może stać dłużej niż chwilę: za nim jest skreślenie komputera z listy
#: podłączonych, a wpis wygasa dopiero po ``ONLINE_STALE_SECONDS`` (90 s).
SPRZATANIE_SEKUND = 2.0

router = APIRouter(prefix="/api/pulpit", tags=["pulpit"])

AUTH_TIMEOUT_SECONDS = 10.0
REVALIDATE_SECONDS = 60.0
MAX_MESSAGE_BYTES = 16 * 1024 * 1024
REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
CLOSE_UNAUTHORIZED = 4401
CLOSE_REPLACED = 4409

# Połączenia w tym procesie API: nowe połączenie tego samego komputera zamyka poprzednie,
# inaczej jedno żądanie wykonałoby się dwa razy.
_connections: dict[str, WebSocket] = {}


def _broker(websocket_or_request: WebSocket | Request) -> MemoryBroker | RedisAsyncBroker:
    state = websocket_or_request.app.state
    broker = getattr(state, "pulpit_broker", None)
    if broker is None:
        broker = async_broker(state.settings)
        state.pulpit_broker = broker
    return broker


async def _device_for_token(database: Database, token: str) -> dict[str, str] | None:
    """Opis komputera dla ważnego klucza urządzenia rodzaju ``desktop``."""
    if not token.startswith(DEVICE_TOKEN_PREFIX):
        return None
    async with database.session() as session:
        record = await session.scalar(select(DeviceToken).where(DeviceToken.token_hash == token_hash(token)))
        if record is None or record.revoked or record.kind != "desktop":
            return None
        record.last_used_at = utcnow()
        return {
            "id": str(record.id),
            "name": record.name,
            "kind": record.kind,
            "owner": str(record.owner_id),
        }


async def _still_valid(database: Database, device_id: str) -> bool:
    async with database.session() as session:
        record = await session.get(DeviceToken, uuid.UUID(device_id))
    return record is not None and not record.revoked


def _clean(value: Any, limit: int = 100) -> str:
    return str(value or "")[:limit]


async def _authenticate(websocket: WebSocket) -> tuple[dict[str, str] | None, dict[str, Any]]:
    database: Database = websocket.app.state.database
    header = websocket.headers.get("authorization", "")
    hello: dict[str, Any] = {}
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not token:
        try:
            hello = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_SECONDS)
        except (TimeoutError, ValueError, WebSocketDisconnect):
            return None, {}
        if not isinstance(hello, dict) or hello.get("type") != "auth":
            return None, {}
        token = str(hello.get("token") or "")
    return await _device_for_token(database, token), hello


@router.websocket("/ws")
async def computer_socket(websocket: WebSocket) -> None:
    """Połączenie komputera z Nexus Desktop."""
    await websocket.accept()
    device, hello = await _authenticate(websocket)
    if device is None:
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {"type": "error", "message": "Nieprawidłowy, cofnięty lub nie-komputerowy klucz urządzenia."}
            )
            await websocket.close(code=CLOSE_UNAUTHORIZED)
        return
    device_id = device["id"]
    previous = _connections.get(device_id)
    if previous is not None:
        with contextlib.suppress(Exception):
            await previous.close(code=CLOSE_REPLACED)
    _connections[device_id] = websocket
    broker = _broker(websocket)
    database: Database = websocket.app.state.database
    now = time.time()
    # Właściciel klucza urządzenia trafia do rejestru: przekaźnik wydaje komputer tylko
    # temu kontu, a wykaz w API i narzędzia ``pc_*`` zawężają po tym polu.
    info = {
        "owner": device["owner"],
        "name": device["name"],
        "host": _clean(hello.get("host")),
        "version": _clean(hello.get("version"), 40),
        "platform": _clean(hello.get("platform"), 40),
        "connected_at": now,
        "seen": now,
    }
    logger.info("Komputer %s (%s) podłączony.", device["name"], device_id)
    try:
        async with broker.subscribe(request_channel(device_id)) as get_request:
            await broker.set_online(device_id, info)
            opis = {key: device[key] for key in ("id", "name", "kind")}
            await websocket.send_json({"type": "ready", "device": opis})
            forward = asyncio.create_task(_forward_requests(websocket, get_request))
            try:
                await _receive_loop(websocket, broker, database, device_id, info)
            finally:
                forward.cancel()
                # Z limitem, nie „na zawsze”. Zadanie przekazujące wisi na odczycie
                # z kanału Redisa; anulowanie dochodzi do niego dopiero, gdy odczyt wróci.
                # Bez limitu całe sprzątanie rozłączenia stało tutaj, a komputer zostawał
                # na liście podłączonych do wygaśnięcia wpisu (90 s) — w oknie Urządzeń
                # widniał jako obecny, a narzędzia `pc_*` wybierały go i kończyły się
                # przeterminowaniem.
                with contextlib.suppress(asyncio.CancelledError, TimeoutError, Exception):
                    await asyncio.wait_for(forward, SPRZATANIE_SEKUND)
    except WebSocketDisconnect:
        pass
    finally:
        if _connections.get(device_id) is websocket:
            _connections.pop(device_id, None)
            try:
                # `shield`, bo to sprzątanie biegnie zwykle w **anulowanym** zadaniu:
                # serwer kończy obsługę gniazda przez `cancel()`, a wtedy pierwsze `await`
                # w tym bloku natychmiast podnosi `CancelledError`. Wcześniej stało tu
                # `suppress(Exception)`, które `CancelledError` nie łapie (to `BaseException`),
                # więc skreślenie obecności **nigdy nie dochodziło do skutku**: komputer
                # zostawał na liście podłączonych aż do wygaśnięcia wpisu (90 s). W oknie
                # Urządzeń widniał jako obecny, a narzędzia `pc_*` wybierały go i kończyły
                # się przeterminowaniem. `shield` pozwala samemu skreśleniu dobiec do końca.
                await asyncio.shield(broker.set_offline(device_id))
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001 - rozłączenie nie może się wywrócić na sprzątaniu
                logger.warning(
                    "Nie udało się skreślić komputera %s z listy podłączonych.",
                    device_id,
                    exc_info=True,
                )
        logger.info("Komputer %s (%s) rozłączony.", device["name"], device_id)


async def _forward_requests(websocket: WebSocket, get_request: Any) -> None:
    """Żądania narzędzi z Redisa → WebSocket komputera."""
    while True:
        raw = await get_request(5.0)
        if raw is None:
            continue
        try:
            request = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(request, dict) or not REQUEST_ID.match(str(request.get("id", ""))):
            continue
        if request.get("cancel"):
            await websocket.send_json({"type": "cancel", "id": request["id"]})
            continue
        await websocket.send_json(
            {"type": "request", "id": request["id"], "tool": request.get("tool"), "args": request.get("args")}
        )


async def _receive_loop(
    websocket: WebSocket,
    broker: MemoryBroker | RedisAsyncBroker,
    database: Database,
    device_id: str,
    info: dict[str, Any],
) -> None:
    """Komunikaty komputera: odpowiedzi narzędzi i pingi (odświeżenie rejestru, kontrola klucza)."""
    checked = time.monotonic()
    while True:
        received = await websocket.receive()
        if received["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(received.get("code", 1000))
        text = received.get("text")
        if not text or len(text) > MAX_MESSAGE_BYTES:
            continue
        try:
            message = json.loads(text)
        except ValueError:
            continue
        if not isinstance(message, dict):
            continue
        kind = message.get("type")
        if kind == "ping":
            if time.monotonic() - checked > REVALIDATE_SECONDS:
                checked = time.monotonic()
                if not await _still_valid(database, device_id):
                    revoked = {"type": "error", "message": "Klucz urządzenia został cofnięty."}
                    await websocket.send_json(revoked)
                    await websocket.close(code=CLOSE_UNAUTHORIZED)
                    return
            info["seen"] = time.time()
            await broker.set_online(device_id, info)
            await websocket.send_json({"type": "pong"})
        elif kind == "response":
            request_id = str(message.get("id", ""))
            if not REQUEST_ID.match(request_id):
                continue
            payload = {
                "ok": bool(message.get("ok")),
                "result": message.get("result"),
                "error": message.get("error"),
            }
            await broker.publish(response_channel(request_id), json.dumps(payload, ensure_ascii=False))


@router.get("/komputery")
async def computers(request: Request, sesja: UserSession = Depends(require_session)) -> list[dict[str, Any]]:
    """Komputery konta podłączone w tej chwili do Nexus Desktop.

    Wykaz zawęża się do kluczy urządzeń tego konta: rejestr jest wspólny dla instalacji,
    więc bez zawężenia konto próbne widziało maszynę właściciela instalacji.
    """
    settings = request.app.state.settings
    broker = sync_broker(settings)
    owner = str(sesja.owner_id)
    try:
        found = await asyncio.get_running_loop().run_in_executor(
            None, partial(online_computers, broker, owner=owner)
        )
    finally:
        if not isinstance(broker, MemoryBroker):
            broker.close()
    return [
        {key: item.get(key) for key in ("id", "name", "host", "version", "platform", "connected_at")}
        for item in found
    ]
