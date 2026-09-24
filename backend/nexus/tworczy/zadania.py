"""Zadania w tle modułów twórczych (obróbka obrazów, tłumaczenie dokumentów) uruchamiane z API.

Moduły wywołują te same narzędzia co agent, ale bezpośrednio – bez rozmowy i modelu.
Zadanie działa w procesie API (wątek puli), jego stan jest w pamięci; wynikowe pliki trafiają
do magazynu jak wyniki narzędzi agenta. Interfejs odpytuje stan zadania.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status

from nexus.api.auth import require_session
from nexus.file_service import FileService
from nexus.tools.base import FileRef, ToolCancelled, ToolContext, ToolError

logger = logging.getLogger(__name__)

MAX_JOBS = 200
FINISHED_TTL_SECONDS = 6 * 3600


@dataclass
class Job:
    """Zadanie modułu: stan, postęp, wynik albo błąd."""

    kind: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "running"
    progress: str = ""
    result: dict[str, Any] | None = None
    error: str = ""
    created: float = field(default_factory=time.time)
    finished: float | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    task: asyncio.Task[None] | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
        }


class JobRegistry:
    """Zadania w tle jednego procesu API."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def _prune(self) -> None:
        now = time.time()
        for job_id, job in list(self._jobs.items()):
            if job.finished and now - job.finished > FINISHED_TTL_SECONDS:
                del self._jobs[job_id]
        while len(self._jobs) >= MAX_JOBS:
            oldest = min(self._jobs.values(), key=lambda item: item.created)
            if oldest.status == "running":
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Zbyt wiele trwających zadań.")
            del self._jobs[oldest.id]

    def start(self, kind: str, work: Callable[[Job], Awaitable[dict[str, Any]]]) -> Job:
        """Uruchamia zadanie; ``work`` zwraca wynik (słownik) albo zgłasza błąd."""
        self._prune()
        job = Job(kind)
        self._jobs[job.id] = job

        async def runner() -> None:
            try:
                job.result = await work(job)
                job.status = "cancelled" if job.cancel.is_set() else "done"
            except ToolCancelled:
                job.status, job.error = "cancelled", "Zadanie anulowane."
            except (ToolError, ValueError) as error:
                job.status, job.error = "failed", str(error)
            except Exception:  # noqa: BLE001 - błąd zadania pokazywany w interfejsie
                # Treść wyjątku zostaje w dzienniku: bywa w niej ścieżka na serwerze albo
                # nazwa pliku producenta, a użytkownikowi i tak nic nie mówi.
                logger.exception("Błąd zadania %s (%s)", job.id, kind)
                job.status = "failed"
                job.error = (
                    "Coś poszło nie tak po naszej stronie — zadanie nie zostało wykonane. "
                    f"Spróbuj jeszcze raz; przy zgłoszeniu podaj numer {str(job.id)[:8]}."
                )
            finally:
                job.finished = time.time()

        job.task = asyncio.get_running_loop().create_task(runner())
        return job

    def get(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono zadania (mogło wygasnąć).")
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        job.cancel.set()
        return job

    async def close(self) -> None:
        for job in self._jobs.values():
            job.cancel.set()
            if job.task is not None and not job.task.done():
                job.task.cancel()
                with contextlib.suppress(BaseException):
                    await job.task


def job_registry(app: FastAPI) -> JobRegistry:
    """Rejestr zadań aplikacji (tworzony przy pierwszym użyciu)."""
    registry = getattr(app.state, "tworczy_jobs", None)
    if registry is None:
        registry = JobRegistry()
        app.state.tworczy_jobs = registry
    return registry


async def start_tool_job(
    request: Request,
    tool_name: str,
    arguments: dict[str, Any],
    file_ids: list[str],
    extra_files: list[FileRef] | None = None,
) -> Job:
    """Uruchamia narzędzie agenta jako zadanie modułu; pliki wynikowe trafiają do magazynu.

    ``extra_files`` to pliki pomocnicze spoza magazynu (np. maska gumki) – usuwane po zadaniu.
    """
    from nexus.tools import registry

    try:
        tool = registry.get(tool_name)
        parsed = tool.parse(arguments)
    except ToolError as error:
        raise HTTPException(422, str(error)) from error
    app = request.app
    wlasciciel = (await require_session(request)).owner_id
    files = FileService(app.state.database, app.state.storage, wlasciciel)
    resolved: dict[uuid.UUID, FileRef] = {}
    for file_id in file_ids:
        try:
            parsed_id = uuid.UUID(str(file_id))
            resolved[parsed_id] = await files.resolve(parsed_id)
        except (ValueError, ToolError) as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Nie znaleziono pliku: {file_id}") from error
    for extra in extra_files or []:
        resolved[extra.id] = extra

    def resolve(file_id: uuid.UUID) -> FileRef:
        if file_id not in resolved:
            raise ToolError(f"Plik {file_id} nie jest dostępny w tym zadaniu.")
        return resolved[file_id]

    async def work(job: Job) -> dict[str, Any]:
        context = ToolContext(
            app.state.settings,
            uuid.uuid4(),
            resolve_file=resolve,
            cancel=job.cancel,
            progress=lambda text: setattr(job, "progress", text),
            owner_id=wlasciciel,
        )
        try:
            result = await asyncio.to_thread(tool.handler, context, parsed)
            stored = await files.store_outputs(None, None, result.files)  # type: ignore[arg-type]
        finally:
            await asyncio.to_thread(context.cleanup)
            for extra in extra_files or []:
                extra.path.unlink(missing_ok=True)
        return {"summary": result.summary, "files": stored, "data": result.data}

    return job_registry(app).start(tool_name, work)
