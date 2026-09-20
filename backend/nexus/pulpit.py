"""Przekaźnik narzędzi ``pc_*`` między agentem a komputerem z Nexus Desktop.

Komputer utrzymuje połączenie WebSocket z API (``/api/pulpit/ws``). Narzędzia agenta
działają w innym procesie (serwer MCP uruchamiany przez Claude Code CLI), więc żądania
przechodzą przez Redis (Valkey):

* narzędzie subskrybuje ``nexus:pc:resp:<id>`` i publikuje żądanie w ``nexus:pc:<urządzenie>:req``,
* API przekazuje żądanie przez WebSocket i publikuje odpowiedź komputera w kanale odpowiedzi,
* podłączone komputery są opisane w haszu ``nexus:pc:online`` (odświeżanym przy każdym pingu).

Bez Redisa (pusty ``redis_url``) używany jest pośrednik w pamięci – działa tylko wtedy,
gdy API i narzędzia pracują w jednym procesie (testy).
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import queue
import threading
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any

from nexus.config import Settings

ONLINE_KEY = "nexus:pc:online"
# Wpis starszy niż ten limit oznacza komputer, który zniknął bez rozłączenia.
ONLINE_STALE_SECONDS = 90.0
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
POLL_SECONDS = 1.0


class PcError(Exception):
    """Błąd przekaźnika opisany dla modelu."""


class PcCancelled(Exception):
    """Zadanie anulowane w trakcie oczekiwania na komputer."""


def request_channel(device_id: str) -> str:
    """Kanał żądań dla komputera."""
    return f"nexus:pc:{device_id}:req"


def response_channel(request_id: str) -> str:
    """Kanał odpowiedzi na jedno żądanie."""
    return f"nexus:pc:resp:{request_id}"


# --- pośrednik w pamięci (testy, tryb bez Redisa) ---


class MemoryBroker:
    """Publikacja/subskrypcja i rejestr komputerów w pamięci procesu (bezpieczne wątkowo)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Callable[[str], None]]] = {}
        self._online: dict[str, str] = {}

    def _add(self, channel: str, deliver: Callable[[str], None]) -> None:
        with self._lock:
            self._subscribers.setdefault(channel, []).append(deliver)

    def _remove(self, channel: str, deliver: Callable[[str], None]) -> None:
        with self._lock:
            items = self._subscribers.get(channel, [])
            if deliver in items:
                items.remove(deliver)
            if not items:
                self._subscribers.pop(channel, None)

    def publish_sync(self, channel: str, message: str) -> int:
        with self._lock:
            targets = list(self._subscribers.get(channel, []))
        for deliver in targets:
            deliver(message)
        return len(targets)

    async def publish(self, channel: str, message: str) -> int:
        return self.publish_sync(channel, message)

    @contextlib.contextmanager
    def subscribe_sync(self, channel: str) -> Iterator[Callable[[float], str | None]]:
        inbox: queue.Queue[str] = queue.Queue()
        self._add(channel, inbox.put)

        def get(timeout: float) -> str | None:
            try:
                return inbox.get(timeout=timeout)
            except queue.Empty:
                return None

        try:
            yield get
        finally:
            self._remove(channel, inbox.put)

    @contextlib.asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator[Callable[[float], Awaitable[str | None]]]:
        loop = asyncio.get_running_loop()
        inbox: asyncio.Queue[str] = asyncio.Queue()

        def deliver(message: str) -> None:
            loop.call_soon_threadsafe(inbox.put_nowait, message)

        async def get(timeout: float) -> str | None:
            try:
                return await asyncio.wait_for(inbox.get(), timeout)
            except TimeoutError:
                return None

        self._add(channel, deliver)
        try:
            yield get
        finally:
            self._remove(channel, deliver)

    async def set_online(self, device_id: str, info: dict[str, Any]) -> None:
        with self._lock:
            self._online[device_id] = json.dumps(info, ensure_ascii=False)

    async def set_offline(self, device_id: str) -> None:
        with self._lock:
            self._online.pop(device_id, None)

    def online_sync(self) -> dict[str, str]:
        with self._lock:
            return dict(self._online)

    async def close(self) -> None:
        return None


MEMORY_BROKER = MemoryBroker()


# --- Redis (Valkey) ---


class RedisAsyncBroker:
    """Strona API: publikacja odpowiedzi, subskrypcja żądań, rejestr komputerów."""

    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self._client = redis.from_url(url, socket_connect_timeout=3, health_check_interval=30)

    async def publish(self, channel: str, message: str) -> int:
        return int(await self._client.publish(channel, message))

    @contextlib.asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator[Callable[[float], Awaitable[str | None]]]:
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        # Potwierdzenie subskrypcji – dopiero potem publikacja w innych procesach trafi do nas.
        await pubsub.get_message(timeout=2)

        async def get(timeout: float) -> str | None:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
            if not message or message.get("type") != "message":
                return None
            data = message["data"]
            return data.decode("utf-8") if isinstance(data, bytes) else str(data)

        try:
            yield get
        finally:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()

    async def set_online(self, device_id: str, info: dict[str, Any]) -> None:
        await self._client.hset(ONLINE_KEY, device_id, json.dumps(info, ensure_ascii=False))

    async def set_offline(self, device_id: str) -> None:
        await self._client.hdel(ONLINE_KEY, device_id)

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self._client.aclose()


class RedisSyncBroker:
    """Strona narzędzi (wątek puli serwera MCP): żądanie i oczekiwanie na odpowiedź."""

    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(url, socket_connect_timeout=3, socket_timeout=10)

    def publish_sync(self, channel: str, message: str) -> int:
        return int(self._client.publish(channel, message))

    @contextlib.contextmanager
    def subscribe_sync(self, channel: str) -> Iterator[Callable[[float], str | None]]:
        pubsub = self._client.pubsub()
        pubsub.subscribe(channel)
        pubsub.get_message(timeout=2)

        def get(timeout: float) -> str | None:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
            if not message or message.get("type") != "message":
                return None
            data = message["data"]
            return data.decode("utf-8") if isinstance(data, bytes) else str(data)

        try:
            yield get
        finally:
            with contextlib.suppress(Exception):
                pubsub.unsubscribe(channel)
                pubsub.close()

    def online_sync(self) -> dict[str, str]:
        raw = self._client.hgetall(ONLINE_KEY)
        return {
            (key.decode() if isinstance(key, bytes) else key): (
                value.decode("utf-8") if isinstance(value, bytes) else value
            )
            for key, value in raw.items()
        }

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._client.close()


def async_broker(settings: Settings) -> MemoryBroker | RedisAsyncBroker:
    """Pośrednik dla API (Redis albo pamięć procesu)."""
    return RedisAsyncBroker(settings.redis_url) if settings.redis_url else MEMORY_BROKER


def sync_broker(settings: Settings) -> MemoryBroker | RedisSyncBroker:
    """Pośrednik dla narzędzi (Redis albo pamięć procesu)."""
    return RedisSyncBroker(settings.redis_url) if settings.redis_url else MEMORY_BROKER


# --- wybór komputera i wywołanie narzędzia ---


def online_computers(
    broker: MemoryBroker | RedisSyncBroker, now: float | None = None, *, owner: str
) -> list[dict[str, Any]]:
    """Podłączone komputery konta ``owner`` (najpierw najświeższe), bez nieaktualnych wpisów.

    Konto podaje się zawsze: rejestr jest wspólny dla całej instalacji, a komputer należy
    do konta, które wydało klucz urządzenia. Bez zawężenia konto próbne sięgało narzędziami
    ``pc_*`` do maszyny właściciela instalacji.
    """
    now = time.time() if now is None else now
    computers = []
    for device_id, raw in broker.online_sync().items():
        try:
            info = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if str(info.get("owner", "")) != owner:
            continue
        if now - float(info.get("seen", 0)) > ONLINE_STALE_SECONDS:
            continue
        computers.append({**info, "id": device_id})
    computers.sort(key=lambda item: float(item.get("connected_at", 0)), reverse=True)
    return computers


def choose_computer(computers: list[dict[str, Any]], wanted: str) -> dict[str, Any]:
    """Komputer wskazany nazwą/identyfikatorem (pusty = ostatnio podłączony)."""
    if not computers:
        raise PcError(
            "Żaden komputer z Nexus Desktop nie jest teraz podłączony. Poproś użytkownika o uruchomienie "
            "aplikacji Nexus Desktop i połączenie jej z Nexusem (Ustawienia → Połącz komputer)."
        )
    wanted = wanted.strip().lower()
    if not wanted:
        return computers[0]
    for computer in computers:
        names = {str(computer.get("id", "")).lower(), str(computer.get("name", "")).lower()}
        names.add(str(computer.get("host", "")).lower())
        if wanted in names:
            return computer
    available = ", ".join(f"{c.get('name')} ({c.get('host', '?')})" for c in computers)
    raise PcError(f"Nie znaleziono komputera „{wanted}”. Podłączone: {available}.")


def decode_images(raw: Any) -> list[bytes]:
    """Obrazy z odpowiedzi komputera (base64 JPEG/PNG) z kontrolą rozmiaru."""
    images: list[bytes] = []
    for item in raw or []:
        if not isinstance(item, str):
            continue
        try:
            data = base64.b64decode(item, validate=True)
        except (binascii.Error, ValueError) as error:
            raise PcError("Komputer zwrócił uszkodzony obraz.") from error
        if len(data) > MAX_IMAGE_BYTES:
            raise PcError("Obraz z komputera jest zbyt duży.")
        if not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8")):
            raise PcError("Komputer zwrócił obraz w nieobsługiwanym formacie.")
        images.append(data)
    return images


def call_computer(
    broker: MemoryBroker | RedisSyncBroker,
    tool: str,
    args: dict[str, Any],
    *,
    owner: str,
    computer: str = "",
    timeout: float = 60.0,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[str], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Wysyła żądanie narzędzia do komputera i czeka na odpowiedź.

    Zwraca ``(wynik, opis_komputera)``. Błąd po stronie komputera, brak komputera
    albo przekroczenie czasu kończą się ``PcError``; anulowanie zadania – ``PcCancelled``.
    Wybór ogranicza się do komputerów konta ``owner``.
    """
    target = choose_computer(online_computers(broker, owner=owner), computer)
    request_id = uuid.uuid4().hex
    request = json.dumps({"id": request_id, "tool": tool, "args": args}, ensure_ascii=False)
    with broker.subscribe_sync(response_channel(request_id)) as get:
        if broker.publish_sync(request_channel(target["id"]), request) == 0:
            raise PcError(
                f"Komputer „{target.get('name')}” nie odpowiada (połączenie zostało przerwane). "
                "Poproś użytkownika o sprawdzenie Nexus Desktop."
            )
        if progress is not None:
            progress(f"Komputer „{target.get('name')}”: {tool}")
        deadline = time.monotonic() + timeout
        while True:
            if cancelled():
                cancel = json.dumps({"id": request_id, "cancel": True})
                with contextlib.suppress(Exception):
                    broker.publish_sync(request_channel(target["id"]), cancel)
                raise PcCancelled
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PcError(
                    f"Komputer „{target.get('name')}” nie odpowiedział w ciągu {int(timeout)} s "
                    "(przy poleceniach wymagających zgody – użytkownik nie potwierdził na czas)."
                )
            raw = get(min(POLL_SECONDS, remaining))
            if raw is None:
                continue
            try:
                response = json.loads(raw)
            except ValueError as error:
                raise PcError("Komputer zwrócił nieczytelną odpowiedź.") from error
            if not isinstance(response, dict):
                raise PcError("Komputer zwrócił nieczytelną odpowiedź.")
            if not response.get("ok"):
                message = str(response.get("error") or "nieznany błąd")[:2000]
                raise PcError(f"Komputer „{target.get('name')}”: {message}")
            result = response.get("result")
            return (result if isinstance(result, dict) else {"text": str(result)}), target
