"""Proces roboczy: pobiera zadania z kolejki PostgreSQL i wykonuje przebiegi agenta.

Kolejka korzysta z ``SELECT … FOR UPDATE SKIP LOCKED``, więc może działać
kilka procesów roboczych jednocześnie; przebiegi jednej rozmowy są
wykonywane kolejno.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import anthropic
from sqlalchemy import text, update

from nexus.agent.runner import AgentRunner
from nexus.config import Settings, get_settings
from nexus.db import Database, Run, utcnow
from nexus.logging_setup import configure_logging
from nexus.storage import FileStorage
from nexus.tools import registry

logger = logging.getLogger("nexus.worker")

POLL_SECONDS = 1.0
STALE_AFTER = timedelta(minutes=3)

CLAIM_SQL = text("""
UPDATE runs SET status = 'running', worker_id = :worker, started_at = now(), heartbeat_at = now()
WHERE id = (
    SELECT r.id FROM runs r
    WHERE r.status = 'queued'
      AND NOT EXISTS (SELECT 1 FROM runs o WHERE o.conversation_id = r.conversation_id
                      AND o.status = 'running')
    ORDER BY r.created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id
""")


async def claim_next(database: Database, worker_id: str) -> uuid.UUID | None:
    """Pobiera najstarsze oczekujące zadanie (lub ``None``)."""
    async with database.session() as session:
        return await session.scalar(CLAIM_SQL, {"worker": worker_id})


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

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._database = Database(settings.database_url)
        self._executor = ThreadPoolExecutor(
            max_workers=max(4, settings.tool_threads), thread_name_prefix="tool"
        )
        self._runner = AgentRunner(
            settings,
            self._database,
            FileStorage(settings.files_dir),
            anthropic.AsyncAnthropic(max_retries=4),
            registry,
            self._executor,
        )
        self._worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self._slots = asyncio.Semaphore(max(1, settings.worker_concurrency))
        self._stopping = asyncio.Event()
        self._tasks: set[asyncio.Task[None]] = set()

    def stop(self) -> None:
        """Kończy pobieranie nowych zadań (bieżące są dokańczane)."""
        self._stopping.set()

    async def run(self) -> None:
        """Główna pętla procesu roboczego."""
        await self._database.create_schema()
        recovered = await recover_stale_runs(self._database)
        if recovered:
            logger.warning("Oznaczono %d przerwanych zadań.", recovered)
        logger.info(
            "Proces roboczy %s gotowy (równoległe przebiegi: %d, narzędzia: %d: %s)",
            self._worker_id,
            self._settings.worker_concurrency,
            len(registry.names()),
            ", ".join(registry.names()),
        )
        while not self._stopping.is_set():
            await self._slots.acquire()
            run_id = None
            try:
                run_id = await claim_next(self._database, self._worker_id)
            except Exception:  # noqa: BLE001 - chwilowa niedostępność bazy nie zatrzymuje procesu
                logger.exception("Błąd pobierania zadania z kolejki")
            if run_id is None:
                self._slots.release()
                try:
                    await asyncio.wait_for(self._stopping.wait(), POLL_SECONDS)
                except TimeoutError:
                    pass
                continue
            task = asyncio.create_task(self._execute(run_id))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        if self._tasks:
            logger.info("Oczekiwanie na zakończenie %d zadań…", len(self._tasks))
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._executor.shutdown(wait=True, cancel_futures=True)
        await self._database.close()

    async def _execute(self, run_id: uuid.UUID) -> None:
        try:
            logger.info("Start przebiegu %s", run_id)
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
