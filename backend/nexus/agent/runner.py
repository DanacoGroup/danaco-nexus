"""Pętla agenta: rozmowa z Claude, wykonywanie narzędzi, zapis historii i zdarzeń.

Pętla jest prowadzona ręcznie (a nie przez Tool Runner SDK), ponieważ
wymaga strumieniowania zdarzeń do interfejsu, zapisu każdego kroku w bazie,
anulowania w trakcie pracy i wykonywania narzędzi w puli wątków.
Historia rozmowy jest wyłącznie dopisywana (bloki thinking przekazywane
bez zmian), co zachowuje pamięć podręczną promptu.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import anthropic
from sqlalchemy import select, update

from nexus.agent.prompt import SYSTEM_PROMPT
from nexus.config import Settings
from nexus.db import Database, Message, Run, RunEvent, StoredFile, ToolCall, utcnow
from nexus.storage import FileStorage, guess_mime
from nexus.tools.base import (
    FileRef,
    ToolCancelled,
    ToolContext,
    ToolError,
    ToolRegistry,
    ToolResult,
    image_block,
)

logger = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
TEXT_FLUSH_SECONDS = 0.15
PROGRESS_MIN_INTERVAL = 0.7
CANCEL_POLL_SECONDS = 1.0
INTERNAL_BLOCKS_BEFORE_FALLBACK = {"thinking", "redacted_thinking", "tool_use"}


class RunCancelled(Exception):
    """Przebieg anulowany przez użytkownika."""


@dataclass(slots=True)
class Usage:
    """Sumaryczne zużycie tokenów przebiegu."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    requests: int = 0

    def add(self, usage: Any) -> None:
        self.requests += 1
        for name in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        ):
            setattr(self, name, getattr(self, name) + int(getattr(usage, name, 0) or 0))

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in self.__slots__}


def sanitize_assistant_content(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Przygotowuje treść odpowiedzi do zapisu w historii.

    Po przełączeniu na model zapasowy (blok ``fallback``) bloki wewnętrzne
    sprzed ostatniego przełączenia nie mogą być odsyłane – zgodnie z zasadami
    server-side fallbacks są pomijane; pozostałe bloki zostają bez zmian.
    """
    last_fallback = max((i for i, block in enumerate(content) if block.get("type") == "fallback"), default=-1)
    if last_fallback < 0:
        return content
    kept = []
    for index, block in enumerate(content):
        if index < last_fallback and block.get("type") in INTERNAL_BLOCKS_BEFORE_FALLBACK:
            continue
        kept.append(block)
    return kept


@dataclass
class _EventBuffer:
    """Łączy drobne fragmenty tekstu w większe zdarzenia (mniej zapisów w bazie)."""

    kind: str
    text: list[str] = field(default_factory=list)
    last_flush: float = field(default_factory=time.monotonic)


class AgentRunner:
    """Wykonuje przebiegi agenta."""

    def __init__(
        self,
        settings: Settings,
        database: Database,
        storage: FileStorage,
        client: anthropic.AsyncAnthropic,
        registry: ToolRegistry,
        executor: ThreadPoolExecutor,
    ) -> None:
        self._settings = settings
        self._db = database
        self._storage = storage
        self._client = client
        self._registry = registry
        self._executor = executor

    # --- zdarzenia -------------------------------------------------------------------------

    async def emit(self, run_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> None:
        """Zapisuje zdarzenie przebiegu (odczytywane strumieniowo przez API)."""
        async with self._db.session() as session:
            session.add(RunEvent(run_id=run_id, type=event_type, data=data))

    async def _flush(self, run_id: uuid.UUID, buffer: _EventBuffer, force: bool = False) -> None:
        if not buffer.text:
            return
        if force or time.monotonic() - buffer.last_flush >= TEXT_FLUSH_SECONDS:
            text = "".join(buffer.text)
            buffer.text.clear()
            buffer.last_flush = time.monotonic()
            await self.emit(run_id, buffer.kind, {"text": text})

    # --- przebieg --------------------------------------------------------------------------

    async def execute(self, run_id: uuid.UUID) -> None:
        """Wykonuje przebieg do końca; stan końcowy zapisuje w bazie."""
        cancel = threading.Event()
        watcher = asyncio.create_task(self._watch_cancel(run_id, cancel))
        usage = Usage()
        status, error_text = "done", ""
        try:
            async with self._db.session() as session:
                run = await session.get(Run, run_id)
                if run is None:
                    return
                conversation_id = run.conversation_id
            await self.emit(run_id, "run.started", {})
            await self._loop(run_id, conversation_id, cancel, usage)
        except RunCancelled:
            status, error_text = "cancelled", "Zadanie anulowane."
        except anthropic.APIStatusError as error:
            status, error_text = "failed", _api_error_message(error)
            logger.error("Błąd API Claude w przebiegu %s: %s", run_id, error)
        except anthropic.APIConnectionError as error:
            status, error_text = "failed", "Brak połączenia z API Claude. Spróbuj ponownie."
            logger.error("Błąd połączenia z API w przebiegu %s: %s", run_id, error)
        except Exception as error:  # noqa: BLE001 - błąd przebiegu raportowany w interfejsie
            status, error_text = "failed", f"Błąd wewnętrzny: {error}"
            logger.exception("Błąd przebiegu %s", run_id)
        finally:
            watcher.cancel()
        async with self._db.session() as session:
            await session.execute(
                update(Run)
                .where(Run.id == run_id)
                .values(status=status, error=error_text, usage=usage.as_dict(), finished_at=utcnow())
            )
        final_type = {"done": "run.completed", "cancelled": "run.cancelled"}.get(status, "run.failed")
        await self.emit(run_id, final_type, {"error": error_text, "usage": usage.as_dict()})
        logger.info(
            "Przebieg %s: %s | zapytania: %d | tokeny wej.: %d (cache: %d) | wyj.: %d",
            run_id,
            status,
            usage.requests,
            usage.input_tokens,
            usage.cache_read_input_tokens,
            usage.output_tokens,
        )

    async def _watch_cancel(self, run_id: uuid.UUID, cancel: threading.Event) -> None:
        while not cancel.is_set():
            await asyncio.sleep(CANCEL_POLL_SECONDS)
            async with self._db.session() as session:
                requested = await session.scalar(select(Run.cancel_requested).where(Run.id == run_id))
                await session.execute(update(Run).where(Run.id == run_id).values(heartbeat_at=utcnow()))
            if requested:
                cancel.set()

    async def _history(self, conversation_id: uuid.UUID) -> list[dict[str, Any]]:
        async with self._db.session() as session:
            rows = (
                await session.scalars(
                    select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
                )
            ).all()
        return [{"role": row.role, "content": row.content} for row in rows]

    async def _append(
        self,
        conversation_id: uuid.UUID,
        run_id: uuid.UUID,
        role: str,
        kind: str,
        content: list[dict[str, Any]],
        meta: dict[str, Any] | None = None,
    ) -> None:
        async with self._db.session() as session:
            session.add(
                Message(
                    conversation_id=conversation_id,
                    run_id=run_id,
                    role=role,
                    kind=kind,
                    content=content,
                    meta=meta or {},
                )
            )

    def _request(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        settings = self._settings
        params: dict[str, Any] = {
            "model": settings.anthropic_model,
            "max_tokens": settings.max_output_tokens,
            "system": [{"type": "text", "text": SYSTEM_PROMPT}],
            "tools": self._registry.definitions(),
            "messages": history,
            "thinking": {"type": "adaptive", "display": "summarized"},
            "cache_control": {"type": "ephemeral"},
        }
        if settings.anthropic_effort:
            params["output_config"] = {"effort": settings.anthropic_effort}
        if settings.server_side_fallbacks:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    async def _loop(
        self, run_id: uuid.UUID, conversation_id: uuid.UUID, cancel: threading.Event, usage: Usage
    ) -> None:
        for _step in range(self._settings.max_agent_steps):
            if cancel.is_set():
                raise RunCancelled
            history = await self._history(conversation_id)
            message = await self._call_model(run_id, history, cancel)
            usage.add(message.usage)
            content = sanitize_assistant_content([block.to_dict() for block in message.content])
            if content:
                await self._append(
                    conversation_id,
                    run_id,
                    "assistant",
                    "assistant",
                    content,
                    {"model": message.model, "stop_reason": message.stop_reason},
                )
            stop = message.stop_reason
            tool_blocks = [block for block in content if block.get("type") == "tool_use"]
            if stop == "tool_use" and tool_blocks:
                results = await asyncio.gather(
                    *(self._run_tool(run_id, conversation_id, block, cancel) for block in tool_blocks)
                )
                # Wyniki są zapisywane zawsze, także po anulowaniu: każde wywołanie
                # narzędzia w historii musi mieć odpowiadający mu wynik.
                await self._append(conversation_id, run_id, "user", "tool_results", list(results))
                if cancel.is_set():
                    raise RunCancelled
                continue
            if tool_blocks:
                await self._append(
                    conversation_id,
                    run_id,
                    "user",
                    "tool_results",
                    [
                        {
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "is_error": True,
                            "content": "Wywołanie nie zostało wykonane (odpowiedź przerwana).",
                        }
                        for block in tool_blocks
                    ],
                )
            if stop == "refusal":
                await self.emit(run_id, "notice", {"text": "Model odmówił wykonania tej prośby."})
                return
            if stop == "pause_turn":
                continue
            if stop == "max_tokens":
                await self.emit(
                    run_id, "notice", {"text": "Odpowiedź przekroczyła limit długości i została ucięta."}
                )
            return
        await self.emit(run_id, "notice", {"text": "Osiągnięto limit kroków agenta dla jednego zadania."})

    async def _call_model(
        self, run_id: uuid.UUID, history: list[dict[str, Any]], cancel: threading.Event
    ) -> Any:
        text = _EventBuffer("text.delta")
        thinking = _EventBuffer("thinking.delta")
        async with self._client.beta.messages.stream(**self._request(history)) as stream:
            async for event in stream:
                if cancel.is_set():
                    raise RunCancelled
                if event.type == "text":
                    text.text.append(event.text)
                    await self._flush(run_id, text)
                elif event.type == "thinking":
                    thinking.text.append(event.thinking)
                    await self._flush(run_id, thinking)
                elif event.type == "content_block_start":
                    block_type = getattr(event.content_block, "type", "")
                    await self._flush(run_id, text, force=True)
                    await self._flush(run_id, thinking, force=True)
                    if block_type == "tool_use":
                        await self.emit(run_id, "tool.pending", {"name": event.content_block.name})
                    elif block_type == "text":
                        await self.emit(run_id, "text.block", {})
            await self._flush(run_id, text, force=True)
            await self._flush(run_id, thinking, force=True)
            return await stream.get_final_message()

    # --- narzędzia -------------------------------------------------------------------------

    async def _run_tool(
        self, run_id: uuid.UUID, conversation_id: uuid.UUID, block: dict[str, Any], cancel: threading.Event
    ) -> dict[str, Any]:
        tool_use_id, name = block["id"], block["name"]
        raw_input = block.get("input") or {}
        started = time.monotonic()
        async with self._db.session() as session:
            call = ToolCall(
                run_id=run_id,
                tool_use_id=tool_use_id,
                name=name,
                input=raw_input if isinstance(raw_input, dict) else {},
            )
            session.add(call)
            await session.flush()
            call_id = call.id
        await self.emit(
            run_id,
            "tool.started",
            {"tool_use_id": tool_use_id, "name": name, "input": _input_preview(raw_input)},
        )
        loop = asyncio.get_running_loop()
        context = ToolContext(
            self._settings,
            run_id,
            resolve_file=lambda file_id: asyncio.run_coroutine_threadsafe(
                self._resolve_file(file_id), loop
            ).result(),
            cancel=cancel,
            progress=_throttled(
                lambda text: asyncio.run_coroutine_threadsafe(
                    self.emit(run_id, "tool.progress", {"tool_use_id": tool_use_id, "text": text}), loop
                ).result()
            ),
            mark_indexed=lambda file_id: asyncio.run_coroutine_threadsafe(
                self._mark_indexed(file_id), loop
            ).result(),
        )
        status, summary, files, is_error = "done", "", [], False
        try:
            tool = self._registry.get(name)
            arguments = tool.parse(raw_input)
            result: ToolResult = await loop.run_in_executor(self._executor, tool.handler, context, arguments)
            files = await self._store_outputs(run_id, conversation_id, result)
            summary = result.summary
            payload: dict[str, Any] = {"result": result.data}
            if files:
                payload["output_files"] = [
                    {"file_id": f["id"], "name": f["name"], "mime": f["mime"], "size_bytes": f["size"]}
                    for f in files
                ]
            content: list[dict[str, Any]] = [
                {"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}
            ]
            content.extend(image_block(image) for image in result.images)
        except ToolCancelled:
            status, is_error, summary = "cancelled", True, "Anulowano"
            content = [{"type": "text", "text": "Zadanie anulowane przez użytkownika."}]
        except ToolError as error:
            status, is_error, summary = "error", True, str(error)
            content = [{"type": "text", "text": f"Błąd: {error}"}]
        except Exception as error:  # noqa: BLE001 - błąd narzędzia przekazywany modelowi
            logger.exception("Błąd narzędzia %s w przebiegu %s", name, run_id)
            status, is_error, summary = "error", True, f"Błąd wewnętrzny narzędzia: {error}"
            content = [{"type": "text", "text": summary}]
        finally:
            await loop.run_in_executor(self._executor, context.cleanup)
        duration = int((time.monotonic() - started) * 1000)
        async with self._db.session() as session:
            await session.execute(
                update(ToolCall)
                .where(ToolCall.id == call_id)
                .values(
                    status=status,
                    summary=summary[:2000],
                    duration_ms=duration,
                    output_file_ids=[f["id"] for f in files],
                )
            )
        await self.emit(
            run_id,
            "tool.finished",
            {
                "tool_use_id": tool_use_id,
                "name": name,
                "status": status,
                "summary": summary[:500],
                "files": files,
                "duration_ms": duration,
            },
        )
        result_block: dict[str, Any] = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
        if is_error:
            result_block["is_error"] = True
        return result_block

    async def _resolve_file(self, file_id: uuid.UUID) -> FileRef:
        async with self._db.session() as session:
            record = await session.get(StoredFile, file_id)
        if record is None:
            raise ToolError(f"Plik {file_id} nie istnieje.")
        path = self._storage.path_of(record)
        if not path.is_file():
            raise ToolError(f"Plik {record.name} nie jest już dostępny na dysku.")
        meta = dict(record.meta or {})
        meta["conversation_id"] = record.conversation_id
        return FileRef(record.id, record.name, record.mime, record.size, path, meta)

    async def _mark_indexed(self, file_id: uuid.UUID) -> None:
        async with self._db.session() as session:
            await session.execute(update(StoredFile).where(StoredFile.id == file_id).values(indexed=True))

    async def _store_outputs(
        self, run_id: uuid.UUID, conversation_id: uuid.UUID, result: ToolResult
    ) -> list[dict[str, Any]]:
        stored: list[dict[str, Any]] = []
        for output in result.files:
            if not output.path.is_file():
                continue
            file_id, relative, size, digest = await asyncio.to_thread(
                self._storage.import_file, output.path, output.name
            )
            record = StoredFile(
                id=file_id,
                conversation_id=conversation_id,
                run_id=run_id,
                origin="result",
                name=output.name,
                mime=guess_mime(output.name),
                size=size,
                sha256=digest,
                storage_path=relative,
                meta={"description": output.description},
            )
            async with self._db.session() as session:
                session.add(record)
            stored.append({"id": str(file_id), "name": output.name, "mime": record.mime, "size": size})
        return stored


def _throttled(send: Any) -> Any:
    """Ogranicza częstotliwość komunikatów postępu narzędzi."""
    last = [0.0]

    def wrapper(text: str) -> None:
        now = time.monotonic()
        if now - last[0] >= PROGRESS_MIN_INTERVAL:
            last[0] = now
            send(text)

    return wrapper


def _input_preview(raw: Any) -> dict[str, Any]:
    """Skrócony opis parametrów narzędzia do wyświetlenia w interfejsie."""
    if not isinstance(raw, dict):
        return {}
    preview: dict[str, Any] = {}
    for key, value in raw.items():
        text = json.dumps(value, ensure_ascii=False)
        preview[key] = value if len(text) <= 200 else text[:200] + "…"
    return preview


def _api_error_message(error: anthropic.APIStatusError) -> str:
    """Czytelny komunikat błędu API Claude."""
    if isinstance(error, anthropic.AuthenticationError):
        return "Nieprawidłowy klucz API Anthropic (ANTHROPIC_API_KEY)."
    if isinstance(error, anthropic.RateLimitError):
        return "Przekroczono limit zapytań API Claude. Spróbuj za chwilę."
    if error.status_code >= 500:
        return "Usługa Claude jest chwilowo niedostępna. Spróbuj ponownie."
    return f"Błąd API Claude ({error.status_code}): {error.message}"
