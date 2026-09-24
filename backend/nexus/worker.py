"""Proces roboczy: pobiera zadania z kolejki PostgreSQL i wykonuje przebiegi agenta.

Kolejka korzysta z ``SELECT … FOR UPDATE SKIP LOCKED``, więc może działać
kilka procesów roboczych jednocześnie. Jeden proces wykonuje do
``worker_concurrency`` przebiegów naraz (wiele sesji równolegle); przebiegi
jednej rozmowy są wykonywane kolejno.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import time
import uuid
from datetime import timedelta

from sqlalchemy import text, update

from nexus.agent.runner import AgentRunner
from nexus.config import Settings, get_settings
from nexus.db import Database, Run, utcnow
from nexus.events import QUEUE_CHANNEL, EventBus
from nexus.logging_setup import configure_logging
from nexus.tools import registry
from nexus.usuwanie_konta import usun_wygasle_konta_probne

logger = logging.getLogger("nexus.worker")

POLL_SECONDS = 1.0
STALE_AFTER = timedelta(minutes=3)
RECOVER_EVERY_SECONDS = 60.0
# Konta próbne żyją dwa dni; sprzątanie co godzinę wystarcza, żeby „znikają razem
# z kontem” było prawdą, a nie obciąża bazy.
SPRZATANIE_GOSCI_CO_SEKUND = 3600.0

_CLAIM_TEMPLATE = """
UPDATE runs SET status = 'running', worker_id = :worker, started_at = {now}, heartbeat_at = {now}
WHERE id = (
    SELECT r.id FROM runs r
    WHERE r.status = 'queued'
      AND NOT EXISTS (SELECT 1 FROM runs o WHERE o.conversation_id = r.conversation_id
                      AND o.status = 'running')
    ORDER BY r.created_at
    {lock}
    LIMIT 1
)
RETURNING id
"""
CLAIM_SQL = text(_CLAIM_TEMPLATE.format(now="now()", lock="FOR UPDATE SKIP LOCKED"))
# SQLite (testy, rozwój) nie zna blokad wierszy – zapisy i tak są szeregowane przez bazę.
CLAIM_SQL_SQLITE = text(_CLAIM_TEMPLATE.format(now="CURRENT_TIMESTAMP", lock=""))


async def claim_next(database: Database, worker_id: str) -> uuid.UUID | None:
    """Pobiera najstarsze oczekujące zadanie (lub ``None``)."""
    sqlite = database.engine.dialect.name == "sqlite"
    async with database.session() as session:
        value = await session.scalar(CLAIM_SQL_SQLITE if sqlite else CLAIM_SQL, {"worker": worker_id})
    if value is None or isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


async def recover_stale_runs(database: Database) -> int:
    """Oznacza jako przerwane zadania, których proces roboczy przestał działać."""
    async with database.session() as session:
        result = await session.execute(
            update(Run)
            .where(Run.status == "running", Run.heartbeat_at < utcnow() - STALE_AFTER)
            .values(
                status="failed", error="Zadanie przerwane (restart procesu roboczego).", finished_at=utcnow()
            )
        )
        return result.rowcount or 0


class Worker:
    """Pętla pobierania zadań z ograniczeniem liczby równoległych przebiegów."""

    def __init__(self, settings: Settings, database: Database | None = None) -> None:
        self._settings = settings
        self._database = database or Database(settings.database_url)
        self._events = EventBus(settings.redis_url)
        self._runner = AgentRunner(settings, self._database, self._events)
        self._worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self._concurrency = max(1, settings.worker_concurrency)
        self._slots = asyncio.Semaphore(self._concurrency)
        self._stopping = asyncio.Event()
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def active(self) -> int:
        """Liczba trwających przebiegów."""
        return len(self._tasks)

    def stop(self) -> None:
        """Kończy pobieranie nowych zadań (bieżące są dokańczane w czasie ``worker_stop_grace_s``)."""
        self._stopping.set()

    async def run(self) -> None:
        """Główna pętla procesu roboczego."""
        await self._database.create_schema()
        recovered = await recover_stale_runs(self._database)
        if recovered:
            logger.warning("Oznaczono %d przerwanych zadań.", recovered)
        logger.info(
            "Proces roboczy %s gotowy (CLI: %s, model: %s, równoległe przebiegi: %d, narzędzia: %d: %s)",
            self._worker_id,
            self._settings.claude_bin,
            self._settings.claude_model,
            self._concurrency,
            len(registry.names()),
            ", ".join(registry.names()),
        )
        last_recover = time.monotonic()
        ostatnie_sprzatanie = 0.0
        # Powiadomienie o nowym zadaniu (Redis) budzi pętlę od razu; baza jest i tak
        # odpytywana co POLL_SECONDS (zadania z innych źródeł, brak Redisa).
        async with self._events.listener(QUEUE_CHANNEL) as wait:
            while not self._stopping.is_set():
                if time.monotonic() - last_recover >= RECOVER_EVERY_SECONDS:
                    # Zadania innych (zatrzymanych awaryjnie) procesów roboczych blokowałyby rozmowy.
                    last_recover = time.monotonic()
                    try:
                        recovered = await recover_stale_runs(self._database)
                        if recovered:
                            logger.warning("Oznaczono %d przerwanych zadań.", recovered)
                    except Exception:  # noqa: BLE001
                        logger.exception("Błąd odzyskiwania przerwanych zadań")
                if time.monotonic() - ostatnie_sprzatanie >= SPRZATANIE_GOSCI_CO_SEKUND:
                    ostatnie_sprzatanie = time.monotonic()
                    try:
                        await usun_wygasle_konta_probne(self._settings, self._database)
                    except Exception:  # noqa: BLE001 - sprzątanie nie może zatrzymać kolejki
                        logger.exception("Błąd sprzątania wygasłych kont próbnych")
                if not await self._acquire_slot():
                    continue
                run_id = None
                try:
                    run_id = await claim_next(self._database, self._worker_id)
                except Exception:  # noqa: BLE001 - chwilowa niedostępność bazy nie zatrzymuje procesu
                    logger.exception("Błąd pobierania zadania z kolejki")
                if run_id is None:
                    self._slots.release()
                    await wait(POLL_SECONDS)
                    continue
                task = asyncio.create_task(self._execute(run_id))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        await self._drain()
        await self._events.close()
        await self._database.close()

    async def _acquire_slot(self) -> bool:
        """Czeka na wolne miejsce; ``False``, gdy w międzyczasie zażądano zatrzymania."""
        acquire = asyncio.create_task(self._slots.acquire())
        stopping = asyncio.create_task(self._stopping.wait())
        done, _ = await asyncio.wait({acquire, stopping}, return_when=asyncio.FIRST_COMPLETED)
        stopping.cancel()
        if acquire in done:
            if self._stopping.is_set():
                self._slots.release()
                return False
            return True
        acquire.cancel()
        return False

    async def _drain(self) -> None:
        """Dokańcza bieżące przebiegi; po czasie ``worker_stop_grace_s`` przerywa pozostałe."""
        if not self._tasks:
            return
        logger.info("Oczekiwanie na zakończenie %d zadań…", len(self._tasks))
        _, pending = await asyncio.wait(set(self._tasks), timeout=max(0, self._settings.worker_stop_grace_s))
        if pending:
            logger.warning("Przerywanie %d niezakończonych zadań.", len(pending))
            self._runner.interrupt_all()
            await asyncio.gather(*pending, return_exceptions=True)

    async def _execute(self, run_id: uuid.UUID) -> None:
        try:
            logger.info("Start przebiegu %s (trwające: %d/%d)", run_id, len(self._tasks), self._concurrency)
            await self._runner.execute(run_id)
        finally:
            self._slots.release()


async def main() -> None:
    """Uruchamia proces roboczy z obsługą sygnałów zakończenia."""
    settings = get_settings()
    configure_logging(settings.data_dir / "logs", "worker")
    worker = Worker(settings)
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(signum, worker.stop)
        except NotImplementedError:
            pass
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
