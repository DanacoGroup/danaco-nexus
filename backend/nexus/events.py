"""Powiadomienia o nowych zdarzeniach zadań przez Redis (Valkey).

Źródłem prawdy pozostaje tabela ``run_events``; Redis tylko budzi strumienie
SSE, żeby nie odpytywały bazy w pętli. Bez Redisa (pusty ``redis_url`` albo
niedostępny serwer) strumień wraca do krótkiego odpytywania bazy.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "nexus:run:"
# Nowe zadanie w kolejce – proces roboczy podejmuje je od razu, bez czekania na odpytanie bazy.
QUEUE_CHANNEL = "nexus:queue"
FALLBACK_POLL_SECONDS = 0.25
RETRY_AFTER_ERROR_SECONDS = 30.0


def channel(run_id: uuid.UUID) -> str:
    """Kanał powiadomień zadania."""
    return f"{CHANNEL_PREFIX}{run_id}"


class EventBus:
    """Publikacja i oczekiwanie na powiadomienia o zdarzeniach zadań."""

    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._client: Any = None
        self._disabled_until = 0.0

    def _redis(self) -> Any:
        if not self._url or time.monotonic() < self._disabled_until:
            return None
        if self._client is None:
            import redis.asyncio as redis

            self._client = redis.from_url(self._url, socket_timeout=5, socket_connect_timeout=2)
        return self._client

    def _failed(self, error: Exception) -> None:
        logger.warning("Redis niedostępny (%s) – strumienie wracają do odpytywania bazy.", error)
        self._disabled_until = time.monotonic() + RETRY_AFTER_ERROR_SECONDS

    async def notify(self, run_id: uuid.UUID) -> None:
        """Budzi strumienie czekające na zdarzenia zadania (błędy są pomijane)."""
        client = self._redis()
        if client is None:
            return
        try:
            await client.publish(channel(run_id), "1")
        except Exception as error:  # noqa: BLE001 - powiadomienie jest tylko przyspieszeniem
            self._failed(error)

    async def notify_queue(self) -> None:
        """Budzi procesy robocze po dodaniu zadania do kolejki."""
        client = self._redis()
        if client is None:
            return
        try:
            await client.publish(QUEUE_CHANNEL, "1")
        except Exception as error:  # noqa: BLE001
            self._failed(error)

    @contextlib.asynccontextmanager
    async def listener(self, name: str) -> AsyncIterator[Any]:
        """Subskrypcja kanału (``channel(run_id)`` albo ``QUEUE_CHANNEL``); zwraca ``wait(timeout)``."""
        client = self._redis()
        pubsub = None
        if client is not None:
            try:
                pubsub = client.pubsub()
                await pubsub.subscribe(name)
            except Exception as error:  # noqa: BLE001 - tryb awaryjny: odpytywanie bazy
                self._failed(error)
                pubsub = None

        async def wait(timeout: float) -> None:
            nonlocal pubsub
            if pubsub is None:
                await asyncio.sleep(min(timeout, FALLBACK_POLL_SECONDS))
                return
            try:
                await pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
                # Kolejne powiadomienia z tej samej serii są zbędne – baza i tak zostanie odczytana.
                while await pubsub.get_message(ignore_subscribe_messages=True, timeout=0):
                    pass
            except Exception as error:  # noqa: BLE001
                self._failed(error)
                pubsub = None
                await asyncio.sleep(FALLBACK_POLL_SECONDS)

        try:
            yield wait
        finally:
            if pubsub is not None:
                with contextlib.suppress(Exception):
                    await pubsub.unsubscribe()
                    await pubsub.aclose()

    async def close(self) -> None:
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.aclose()
            self._client = None
