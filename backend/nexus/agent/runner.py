"""Przebieg agenta przez Claude Code CLI.

Każde zadanie uruchamia ``claude -p`` w trybie ``stream-json``. Narzędzia
Nexusa dostarcza serwer MCP (``nexus.mcp_server``) uruchamiany przez CLI
na czas zadania. Kontekst rozmowy utrzymuje sesja CLI: pierwsze zadanie
rozmowy tworzy ją (``--session-id``), kolejne wznawiają (``--resume``).

Strumień zdarzeń CLI jest tłumaczony na zdarzenia interfejsu (``RunEvent``),
wpisy historii (``Message``) i rejestr wywołań narzędzi (``ToolCall``).
Anulowanie kończy całą grupę procesów CLI (razem z serwerem MCP).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import shutil
import signal
import sys
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

from nexus.agent.prompt import SYSTEM_PROMPT
from nexus.config import Settings
from nexus.db import Conversation, Database, Message, Run, RunEvent, ToolCall, utcnow

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "nexus"
MCP_PREFIX = f"mcp__{MCP_SERVER_NAME}__"
# Biała lista: narzędzia Nexusa i ToolSearch (definicje MCP mogą być odraczane).
ALLOWED_TOOLS = [f"mcp__{MCP_SERVER_NAME}", "ToolSearch"]
# Narzędzia wbudowane CLI jawnie zakazane – agent działa wyłącznie przez narzędzia Nexusa.
DISALLOWED_TOOLS = [
    "Bash",
    "PowerShell",
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "Glob",
    "Grep",
    "LS",
    "WebSearch",
    "WebFetch",
    "Task",
    "Agent",
    "Skill",
    "Workflow",
    "TodoWrite",
    "AskUserQuestion",
    "EnterPlanMode",
    "ExitPlanMode",
    "EnterWorktree",
    "ExitWorktree",
    "Monitor",
    "CronCreate",
    "CronDelete",
    "RemoteTrigger",
]
LIMIT_PATTERNS = ("session limit", "usage limit", "weekly limit", "rate limit", '"api_error_status":429')
AUTH_PATTERNS = (
    "could not be refreshed",
    "failed to authenticate",
    "invalid api key",
    "not logged in",
    "/login",
)
TEXT_FLUSH_SECONDS = 0.15
CANCEL_POLL_SECONDS = 1.0
TERMINATE_GRACE_SECONDS = 5.0
STREAM_LINE_LIMIT = 256 * 1024 * 1024
STDERR_TAIL_LINES = 40
HISTORY_DIGEST_MESSAGES = 16
HISTORY_DIGEST_CHARS = 1500


class RunCancelled(Exception):
    """Przebieg anulowany przez użytkownika."""


class RunTimedOut(Exception):
    """Przebieg przekroczył limit czasu."""


def tool_display_name(name: str) -> str:
    """Nazwa narzędzia bez prefiksu serwera MCP."""
    return name.removeprefix(MCP_PREFIX)


def find_session_file(profile: Path, session_id: str) -> Path | None:
    """Plik zapisanej sesji CLI (``<profil>/projects/*/<id>.jsonl``) lub ``None``."""
    projects = profile / "projects"
    if not projects.is_dir():
        return None
    return next(projects.glob(f"*/{session_id}.jsonl"), None)


def read_oauth_token(profile: Path) -> str:
    """Token OAuth konta Claude z pliku ``<profil>/oauth-token`` (pusty, gdy brak)."""
    try:
        return (profile / "oauth-token").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def cli_environment(settings: Settings, run_dir: Path) -> dict[str, str]:
    """Środowisko procesu CLI: profil projektu, token OAuth, limity MCP."""
    profile = settings.claude_profile_dir
    env = dict(os.environ)
    # Agent korzysta z subskrypcji Claude (token OAuth), nigdy z klucza API.
    for name in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
    ):
        env.pop(name, None)
    env["CLAUDE_CONFIG_DIR"] = str(profile)
    env["HOME"] = str(profile.parent)
    token = read_oauth_token(profile)
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    env["DISABLE_AUTOUPDATER"] = "1"
    env["MCP_TIMEOUT"] = str(settings.mcp_startup_timeout_s * 1000)
    env["MCP_TOOL_TIMEOUT"] = str(settings.tool_timeout_minutes * 60 * 1000)
    env["MAX_MCP_OUTPUT_TOKENS"] = str(settings.max_tool_output_tokens)
    if settings.max_output_tokens:
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(settings.max_output_tokens)
    env["TMPDIR"] = str(run_dir)
    return env


def mcp_config(run_id: uuid.UUID, conversation_id: uuid.UUID) -> dict[str, Any]:
    """Konfiguracja serwera MCP narzędzi dla jednego zadania."""
    return {
        "mcpServers": {
            MCP_SERVER_NAME: {
                "type": "stdio",
                "command": sys.executable,
                "args": ["-m", "nexus.mcp_server"],
                "env": {"NEXUS_RUN_ID": str(run_id), "NEXUS_CONVERSATION_ID": str(conversation_id)},
            }
        }
    }


def build_command(settings: Settings, mcp_config_path: Path, session_id: str, resume: bool) -> list[str]:
    """Polecenie ``claude -p`` (treść zadania przekazywana na stdin)."""
    command = [
        settings.claude_bin,
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--model",
        settings.claude_model,
        "--system-prompt",
        SYSTEM_PROMPT,
        "--mcp-config",
        str(mcp_config_path),
        "--strict-mcp-config",
        "--allowed-tools",
        *ALLOWED_TOOLS,
        "--disallowed-tools",
        *DISALLOWED_TOOLS,
    ]
    if settings.claude_fallback_model and settings.claude_fallback_model != settings.claude_model:
        command += ["--fallback-model", settings.claude_fallback_model]
    if settings.claude_effort:
        command += ["--effort", settings.claude_effort]
    command += ["--resume", session_id] if resume else ["--session-id", session_id]
    return command


def strip_images(content: Any) -> Any:
    """Treść wyniku narzędzia bez danych obrazów (do zapisu w historii)."""
    if not isinstance(content, list):
        return content
    stripped = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "image":
            stripped.append({"type": "text", "text": "[podgląd obrazu]"})
        else:
            stripped.append(part)
    return stripped


def parse_tool_result(block: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Podsumowanie i pliki wynikowe z bloku ``tool_result`` narzędzia Nexusa."""
    content = block.get("content")
    if isinstance(content, str):
        text = content
    else:
        text = next(
            (
                part.get("text", "")
                for part in content or []
                if isinstance(part, dict) and part.get("type") == "text"
            ),
            "",
        )
    if block.get("is_error"):
        return text.removeprefix("Błąd: ").strip()[:2000], []
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text[:2000], []
    if not isinstance(payload, dict):
        return text[:2000], []
    files = [
        {
            "id": item["file_id"],
            "name": item.get("name", ""),
            "mime": item.get("mime", ""),
            "size": item.get("size_bytes", 0),
        }
        for item in payload.get("output_files") or []
        if isinstance(item, dict) and item.get("file_id")
    ]
    return str(payload.get("summary") or "")[:2000], files


def friendly_error(text: str) -> str:
    """Czytelny komunikat błędu CLI dla użytkownika."""
    lowered = text.lower()
    if any(pattern in lowered for pattern in LIMIT_PATTERNS):
        return "Osiągnięto limit użycia konta Claude. Spróbuj ponownie później."
    if any(pattern in lowered for pattern in AUTH_PATTERNS):
        return (
            "Claude Code CLI nie jest zalogowany – brak lub nieważny token w pliku oauth-token "
            "profilu (polecenie: claude setup-token)."
        )
    tail = text.strip().splitlines()[-1] if text.strip() else ""
    return f"Błąd Claude Code CLI: {tail[:400]}" if tail else "Błąd Claude Code CLI."


def input_preview(raw: Any) -> dict[str, Any]:
    """Skrócony opis parametrów narzędzia do wyświetlenia w interfejsie."""
    if not isinstance(raw, dict):
        return {}
    preview: dict[str, Any] = {}
    for key, value in raw.items():
        text = json.dumps(value, ensure_ascii=False)
        preview[key] = value if len(text) <= 200 else text[:200] + "…"
    return preview


@dataclass
class _Buffer:
    """Łączy drobne fragmenty tekstu w większe zdarzenia (mniej zapisów w bazie)."""

    kind: str
    parts: list[str] = field(default_factory=list)
    last_flush: float = field(default_factory=time.monotonic)


@dataclass
class _RunState:
    """Stan tłumaczenia strumienia CLI na zdarzenia jednego przebiegu."""

    run_id: uuid.UUID
    conversation_id: uuid.UUID
    text: _Buffer = field(default_factory=lambda: _Buffer("text.delta"))
    thinking: _Buffer = field(default_factory=lambda: _Buffer("thinking.delta"))
    calls: dict[str, tuple[int, str, float]] = field(default_factory=dict)
    session_id: str = ""
    result: dict[str, Any] | None = None
    model: str = ""


class AgentRunner:
    """Wykonuje przebiegi agenta przez Claude Code CLI."""

    def __init__(self, settings: Settings, database: Database) -> None:
        self._settings = settings
        self._db = database

    # --- zdarzenia i zapis -----------------------------------------------------------------

    async def emit(self, run_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> None:
        """Zapisuje zdarzenie przebiegu (odczytywane strumieniowo przez API)."""
        async with self._db.session() as session:
            session.add(RunEvent(run_id=run_id, type=event_type, data=data))

    async def _flush(self, run_id: uuid.UUID, buffer: _Buffer, force: bool = False) -> None:
        if not buffer.parts:
            return
        if force or time.monotonic() - buffer.last_flush >= TEXT_FLUSH_SECONDS:
            text = "".join(buffer.parts)
            buffer.parts.clear()
            buffer.last_flush = time.monotonic()
            await self.emit(run_id, buffer.kind, {"text": text})

    async def _append(
        self, state: _RunState, role: str, kind: str, content: list[dict[str, Any]], meta: dict[str, Any]
    ) -> None:
        async with self._db.session() as session:
            session.add(
                Message(
                    conversation_id=state.conversation_id,
                    run_id=state.run_id,
                    role=role,
                    kind=kind,
                    content=content,
                    meta=meta,
                )
            )

    # --- przebieg --------------------------------------------------------------------------

    async def execute(self, run_id: uuid.UUID) -> None:
        """Wykonuje przebieg do końca; stan końcowy zapisuje w bazie."""
        async with self._db.session() as session:
            run = await session.get(Run, run_id)
            if run is None:
                return
            conversation = await session.get(Conversation, run.conversation_id)
            prompt_message = await session.scalar(
                select(Message).where(Message.run_id == run_id, Message.kind == "user").order_by(Message.id)
            )
        state = _RunState(run_id, run.conversation_id)
        usage: dict[str, Any] = {}
        status, error_text = "done", ""
        await self.emit(run_id, "run.started", {})
        try:
            prompt = _prompt_text(prompt_message)
            await self._run_cli(state, conversation, prompt)
            result = state.result or {}
            usage = _usage(result)
            if result.get("is_error") or result.get("subtype", "success") != "success":
                status = "failed"
                error_text = _result_error(result)
        except RunCancelled:
            status, error_text = "cancelled", "Zadanie anulowane."
        except RunTimedOut:
            status = "failed"
            error_text = f"Zadanie przekroczyło limit czasu ({self._settings.run_timeout_minutes} min)."
        except CliFailure as error:
            status, error_text = "failed", friendly_error(str(error))
            logger.error("Błąd CLI w przebiegu %s: %s", run_id, str(error)[-2000:])
        except Exception as error:  # noqa: BLE001 - błąd przebiegu raportowany w interfejsie
            status, error_text = "failed", f"Błąd wewnętrzny: {error}"
            logger.exception("Błąd przebiegu %s", run_id)
        await self._close_open_calls(state, status)
        async with self._db.session() as session:
            await session.execute(
                update(Run)
                .where(Run.id == run_id)
                .values(status=status, error=error_text, usage=usage, finished_at=utcnow())
            )
        final_type = {"done": "run.completed", "cancelled": "run.cancelled"}.get(status, "run.failed")
        await self.emit(run_id, final_type, {"error": error_text, "usage": usage})
        logger.info(
            "Przebieg %s: %s | model: %s | tury: %s | tokeny wej.: %s (cache: %s) | wyj.: %s",
            run_id,
            status,
            state.model or "-",
            usage.get("num_turns", "-"),
            usage.get("input_tokens", "-"),
            usage.get("cache_read_input_tokens", "-"),
            usage.get("output_tokens", "-"),
        )

    async def _session_for(
        self, state: _RunState, conversation: Conversation | None
    ) -> tuple[str, bool, str]:
        """Identyfikator sesji CLI, czy wznawiać, oraz ewentualne streszczenie historii."""
        existing = conversation.claude_session_id if conversation else None
        if existing and find_session_file(self._settings.claude_profile_dir, existing):
            return existing, True, ""
        session_id = str(uuid.uuid4())
        digest = await self._history_digest(state) if existing else ""
        async with self._db.session() as session:
            await session.execute(
                update(Conversation)
                .where(Conversation.id == state.conversation_id)
                .values(claude_session_id=session_id)
            )
        return session_id, False, digest

    async def _history_digest(self, state: _RunState) -> str:
        """Streszczenie wcześniejszych tur, gdy zapis sesji CLI nie jest już dostępny."""
        async with self._db.session() as session:
            rows = (
                await session.scalars(
                    select(Message)
                    .where(
                        Message.conversation_id == state.conversation_id,
                        Message.run_id != state.run_id,
                        Message.kind.in_(("user", "assistant")),
                    )
                    .order_by(Message.id.desc())
                    .limit(HISTORY_DIGEST_MESSAGES)
                )
            ).all()
        lines = []
        for row in reversed(rows):
            text = " ".join(
                block.get("text", "")
                for block in row.content
                if isinstance(block, dict) and block.get("type") == "text"
            ).strip()
            if text:
                who = "Użytkownik" if row.kind == "user" else "Asystent"
                lines.append(f"{who}: {text[:HISTORY_DIGEST_CHARS]}")
        if not lines:
            return ""
        return (
            "[Wcześniejsza część tej rozmowy – streszczenie]\n"
            + "\n\n".join(lines)
            + "\n[Koniec streszczenia]\n\n"
        )

    async def _run_cli(self, state: _RunState, conversation: Conversation | None, prompt: str) -> None:
        settings = self._settings
        session_id, resume, digest = await self._session_for(state, conversation)
        run_dir = settings.work_dir / f"cli-{state.run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        cwd = settings.data_dir / "agent"
        cwd.mkdir(parents=True, exist_ok=True)
        config_path = run_dir / "mcp.json"
        config_path.write_text(json.dumps(mcp_config(state.run_id, state.conversation_id)), encoding="utf-8")
        command = build_command(settings, config_path, session_id, resume)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=cli_environment(settings, run_dir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=STREAM_LINE_LIMIT,
            start_new_session=True,
        )
        stderr_tail: deque[str] = deque(maxlen=STDERR_TAIL_LINES)
        cancel = asyncio.Event()
        watcher = asyncio.create_task(self._watch_cancel(state.run_id, cancel))
        stderr_task = asyncio.create_task(_collect(process.stderr, stderr_tail))
        reader = asyncio.create_task(self._consume(process, state))
        cancel_wait = asyncio.create_task(cancel.wait())
        try:
            assert process.stdin is not None
            process.stdin.write((digest + prompt).encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()
            done, _ = await asyncio.wait(
                {reader, cancel_wait},
                timeout=settings.run_timeout_minutes * 60,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if reader not in done:
                await _terminate(process)
                reader.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await reader
                raise RunCancelled if cancel_wait in done else RunTimedOut
            reader.result()
            returncode = await process.wait()
            await stderr_task
            await self._flush(state.run_id, state.text, force=True)
            await self._flush(state.run_id, state.thinking, force=True)
            if state.result is None:
                raise CliFailure(f"kod wyjścia {returncode}\n" + "\n".join(stderr_tail))
            if state.result.get("is_error"):
                state.result.setdefault("stderr", "\n".join(stderr_tail))
        finally:
            watcher.cancel()
            cancel_wait.cancel()
            if process.returncode is None:
                await _terminate(process)
            if not stderr_task.done():
                stderr_task.cancel()
            _remove_tree(run_dir)

    async def _watch_cancel(self, run_id: uuid.UUID, cancel: asyncio.Event) -> None:
        while not cancel.is_set():
            await asyncio.sleep(CANCEL_POLL_SECONDS)
            async with self._db.session() as session:
                requested = await session.scalar(select(Run.cancel_requested).where(Run.id == run_id))
                await session.execute(update(Run).where(Run.id == run_id).values(heartbeat_at=utcnow()))
            if requested:
                cancel.set()

    # --- strumień CLI ----------------------------------------------------------------------

    async def _consume(self, process: asyncio.subprocess.Process, state: _RunState) -> None:
        assert process.stdout is not None
        while True:
            line = await process.stdout.readline()
            if not line:
                return
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Pominięto wiersz spoza JSON: %s", line[:200])
                continue
            if isinstance(event, dict):
                await self.handle_event(state, event)

    async def handle_event(self, state: _RunState, event: dict[str, Any]) -> None:
        """Tłumaczy jedno zdarzenie strumienia CLI."""
        kind = event.get("type")
        if event.get("parent_tool_use_id"):
            return
        if kind == "system" and event.get("subtype") == "init":
            state.session_id = event.get("session_id", "")
            state.model = event.get("model", "")
            failed = [
                server.get("name")
                for server in event.get("mcp_servers") or []
                if isinstance(server, dict) and server.get("status") not in ("connected", None)
            ]
            if failed:
                await self.emit(
                    state.run_id, "notice", {"text": "Narzędzia serwera są niedostępne (błąd serwera MCP)."}
                )
        elif kind == "stream_event":
            await self._stream_event(state, event.get("event") or {})
        elif kind == "assistant":
            await self._assistant(state, event.get("message") or {})
        elif kind == "user":
            await self._tool_results(state, event.get("message") or {})
        elif kind == "result":
            state.result = event

    async def _stream_event(self, state: _RunState, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta":
                state.text.parts.append(delta.get("text", ""))
                await self._flush(state.run_id, state.text)
            elif delta.get("type") == "thinking_delta":
                state.thinking.parts.append(delta.get("thinking", ""))
                await self._flush(state.run_id, state.thinking)
        elif kind == "content_block_start":
            await self._flush(state.run_id, state.text, force=True)
            await self._flush(state.run_id, state.thinking, force=True)
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use" and block.get("name", "").startswith(MCP_PREFIX):
                await self.emit(state.run_id, "tool.pending", {"name": tool_display_name(block["name"])})
            elif block.get("type") == "text":
                await self.emit(state.run_id, "text.block", {})
        elif kind == "message_stop":
            await self._flush(state.run_id, state.text, force=True)
            await self._flush(state.run_id, state.thinking, force=True)

    async def _assistant(self, state: _RunState, message: dict[str, Any]) -> None:
        await self._flush(state.run_id, state.text, force=True)
        await self._flush(state.run_id, state.thinking, force=True)
        content = []
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                name = block.get("name", "")
                if not name.startswith(MCP_PREFIX):
                    continue
                block = {**block, "name": tool_display_name(name)}
                await self._start_call(state, block)
            if block.get("type") in ("text", "thinking", "tool_use"):
                content.append(block)
        if message.get("model"):
            state.model = message["model"]
        if content:
            await self._append(state, "assistant", "assistant", content, {"model": message.get("model", "")})

    async def _start_call(self, state: _RunState, block: dict[str, Any]) -> None:
        tool_use_id = block.get("id", "")
        raw_input = block.get("input") if isinstance(block.get("input"), dict) else {}
        async with self._db.session() as session:
            call = ToolCall(run_id=state.run_id, tool_use_id=tool_use_id, name=block["name"], input=raw_input)
            session.add(call)
            await session.flush()
            state.calls[tool_use_id] = (call.id, block["name"], time.monotonic())
        await self.emit(
            state.run_id,
            "tool.started",
            {"tool_use_id": tool_use_id, "name": block["name"], "input": input_preview(raw_input)},
        )

    async def _tool_results(self, state: _RunState, message: dict[str, Any]) -> None:
        content = message.get("content")
        if not isinstance(content, list):
            return
        stored = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            tool_use_id = block.get("tool_use_id", "")
            if tool_use_id not in state.calls:
                continue
            summary, files = parse_tool_result(block)
            status = "error" if block.get("is_error") else "done"
            await self._finish_call(state, tool_use_id, status, summary, files)
            stored.append({**block, "content": strip_images(block.get("content"))})
        if stored:
            await self._append(state, "user", "tool_results", stored, {})

    async def _finish_call(
        self, state: _RunState, tool_use_id: str, status: str, summary: str, files: list[dict[str, Any]]
    ) -> None:
        call_id, name, started = state.calls.pop(tool_use_id)
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
            state.run_id,
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

    async def _close_open_calls(self, state: _RunState, status: str) -> None:
        """Wywołania bez wyniku (przerwany przebieg) oznacza jako anulowane lub błędne."""
        final = "cancelled" if status == "cancelled" else "error"
        summary = "Anulowano" if final == "cancelled" else "Przerwano"
        for tool_use_id in list(state.calls):
            await self._finish_call(state, tool_use_id, final, summary, [])


class CliFailure(Exception):
    """CLI zakończył działanie bez wyniku."""


def _prompt_text(message: Message | None) -> str:
    if message is None:
        raise CliFailure("brak wiadomości użytkownika dla zadania")
    return "\n".join(
        block.get("text", "")
        for block in message.content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def _usage(result: dict[str, Any]) -> dict[str, Any]:
    usage = result.get("usage") or {}
    summary: dict[str, Any] = {
        name: int(usage.get(name) or 0)
        for name in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        )
    }
    for name in ("num_turns", "duration_ms", "total_cost_usd"):
        if name in result:
            summary[name] = result[name]
    return summary


def _result_error(result: dict[str, Any]) -> str:
    subtype = result.get("subtype", "")
    if subtype == "error_max_turns":
        return "Osiągnięto limit kroków agenta dla jednego zadania."
    text = " ".join(
        str(part)
        for part in (result.get("result"), " ".join(result.get("errors") or []), result.get("stderr"))
        if part
    )
    return friendly_error(text or subtype)


async def _collect(stream: asyncio.StreamReader | None, tail: deque[str]) -> None:
    if stream is None:
        return
    while True:
        line = await stream.readline()
        if not line:
            return
        tail.append(line.decode("utf-8", "replace").rstrip())


async def _terminate(process: asyncio.subprocess.Process) -> None:
    """Kończy CLI wraz z procesami potomnymi (serwer MCP, programy narzędzi)."""
    if process.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), TERMINATE_GRACE_SECONDS)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()


def _remove_tree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
