"""Przebieg agenta przez Claude Code CLI.

Każde zadanie uruchamia ``claude -p`` w trybie ``stream-json``. Narzędzia
Nexusa dostarcza serwer MCP (``nexus.mcp_server``) uruchamiany przez CLI
na czas zadania. Kontekst rozmowy utrzymuje sesja CLI: pierwsze zadanie
rozmowy tworzy ją (``--session-id``), kolejne wznawiają (``--resume``).

Tryb rozmowy (``Conversation.meta["mode"]``: ``chat``, ``research``, ``code``,
``strona``) dokleja instrukcję z ``nexus/agent/tryby/<tryb>.md``; tryb ``code``
dodaje narzędzia programistyczne CLI ograniczone do katalogu projektu.
Podagenci (narzędzie Agent) dziedziczą ograniczony zestaw narzędzi sesji;
ich zdarzenia (``parent_tool_use_id``) trafiają do interfejsu jako elementy
zagnieżdżone.

Strumień zdarzeń CLI jest tłumaczony na zdarzenia interfejsu (``RunEvent``),
wpisy historii (``Message``) i rejestr wywołań narzędzi (``ToolCall``).
Anulowanie kończy całą grupę procesów CLI (razem z serwerem MCP i podagentami).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import signal
import sys
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

from nexus.agent.prompt import SUBAGENT_PROMPT, system_prompt
from nexus.agent.przestrzenie import existing_project
from nexus.config import Settings
from nexus.db import (
    ADMIN_OWNER,
    Conversation,
    Database,
    Message,
    Run,
    RunEvent,
    Setting,
    ToolCall,
    utcnow,
)
from nexus.events import EventBus
from nexus.platnosci import kredyty

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "nexus"
MCP_PREFIX = f"mcp__{MCP_SERVER_NAME}__"
# Biała lista: narzędzia Nexusa i ToolSearch (definicje MCP mogą być odraczane).
ALLOWED_TOOLS = [f"mcp__{MCP_SERVER_NAME}", "ToolSearch"]
AGENT_TOOLS = frozenset({"Agent", "Task"})
AGENT_CALL_NAME = "podagent"
SUBAGENT_TYPE = "pomocnik"
WEB_TOOLS = ["WebSearch", "WebFetch"]
CODE_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
# Narzędzia pomocnicze CLI niewidoczne w interfejsie.
HIDDEN_TOOLS = frozenset({"ToolSearch", "TodoWrite"})
# Narzędzia wbudowane CLI jawnie zakazane (poza włączonymi dla trybu rozmowy).
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
# Tryb code: polecenia sieciowe i podnoszenie uprawnień zablokowane regułami CLI
# (dodatkowo do instrukcji trybu; to ograniczenie „w dobrej wierze”, nie piaskownica).
CODE_BASH_DENY = [
    f"Bash({command} *)"
    for command in (
        "sudo",
        "su",
        "doas",
        "pkexec",
        "curl",
        "wget",
        "ssh",
        "scp",
        "sftp",
        "rsync",
        "nc",
        "ncat",
        "socat",
        "telnet",
        "git push",
        "git fetch",
        "git pull",
        "git remote",
        "npm publish",
        "systemctl",
    )
]
MODES = ("chat", "research", "code", "strona")
MODES_DIR = Path(__file__).with_name("tryby")
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
BUILTIN_RESULT_CHARS = 4000
RATE_LIMIT_KEY = "claude.limity"
RATE_LIMIT_WARN = 0.9
BACKGROUND_AGENT_MARKER = "async agent launched"
VOICE_INSTRUCTION = (
    "[Rozmowa głosowa: użytkownik mówi, a Twoja odpowiedź zostanie przeczytana na głos. "
    "Odpowiadaj naturalnie i zwięźle, pełnymi zdaniami, bez Markdown, list, tabel i adresów. "
    "Zadania na plikach wykonuj jak zwykle; o wynikach powiedz krótko, pliki pojawią się na ekranie.]"
)
AGENT_STATUS = {
    "completed": "done",
    "success": "done",
    "done": "done",
    "failed": "error",
    "error": "error",
    "killed": "cancelled",
    "stopped": "cancelled",
    "cancelled": "cancelled",
}


class RunCancelled(Exception):
    """Przebieg anulowany przez użytkownika."""


class RunTimedOut(Exception):
    """Przebieg przekroczył limit czasu."""


class RunInterrupted(Exception):
    """Przebieg przerwany przez zatrzymanie procesu roboczego."""


class CliFailure(Exception):
    """CLI zakończył działanie bez wyniku albo nie mógł wystartować."""


class BladZlecenia(CliFailure):
    """Powód niepowodzenia, który dotyczy zlecenia użytkownika, a nie silnika.

    Taki komunikat trafia do użytkownika bez zmian: mówi, co poprawić (np. brakujący
    projekt w module Kod). Wszystko, co pochodzi z silnika, przechodzi przez
    ``friendly_error`` i jest zastępowane komunikatem ogólnym.
    """


@dataclass(frozen=True)
class RunOptions:
    """Ustawienia przebiegu wynikające z rozmowy i wiadomości."""

    mode: str = "chat"
    workspace: Path | None = None
    voice: bool = False


def tool_display_name(name: str) -> str:
    """Nazwa narzędzia w interfejsie: bez prefiksu MCP, podagent jako ``podagent``."""
    if name in AGENT_TOOLS:
        return AGENT_CALL_NAME
    return name.removeprefix(MCP_PREFIX)


def conversation_mode(meta: dict[str, Any] | None) -> str:
    """Tryb rozmowy z ``Conversation.meta`` (nieznany = ``chat``)."""
    mode = (meta or {}).get("mode")
    return mode if isinstance(mode, str) and mode in MODES else "chat"


def mode_instruction(mode: str) -> str:
    """Instrukcja trybu z ``tryby/<tryb>.md`` (pusta, gdy pliku nie ma)."""
    if mode not in MODES:
        return ""
    try:
        return (MODES_DIR / f"{mode}.md").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def run_timeout_minutes(settings: Settings, mode: str) -> int:
    """Limit czasu zadania: tryb badań ma dłuższy."""
    if mode == "research":
        return max(settings.run_timeout_minutes, settings.run_timeout_research_minutes)
    return settings.run_timeout_minutes


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


def cli_environment(settings: Settings, run_dir: Path, code: bool = False) -> dict[str, str]:
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
    if code:
        # Commity agenta w przestrzeni projektu; git nigdy nie pyta o hasło.
        env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = settings.kod_git_name
        env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = settings.kod_git_email
        env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def mcp_config(run_id: uuid.UUID, conversation_id: uuid.UUID, owner_id: uuid.UUID) -> dict[str, Any]:
    """Konfiguracja serwera MCP narzędzi dla jednego zadania.

    ``NEXUS_OWNER_ID`` wskazuje konto, w którego przestrzeni pracują narzędzia: skrzynka
    pocztowa, chmura i baza wiedzy należą do konta, a nie do serwera.
    """
    return {
        "mcpServers": {
            MCP_SERVER_NAME: {
                "type": "stdio",
                "command": sys.executable,
                "args": ["-m", "nexus.mcp_server"],
                "env": {
                    "NEXUS_RUN_ID": str(run_id),
                    "NEXUS_CONVERSATION_ID": str(conversation_id),
                    "NEXUS_OWNER_ID": str(owner_id),
                },
            }
        }
    }


def session_tools(settings: Settings, options: RunOptions) -> list[str]:
    """Wbudowane narzędzia CLI dostępne w sesji (``--tools``); podagenci dziedziczą ten zestaw."""
    tools = ["ToolSearch"]
    if settings.claude_subagents:
        tools.append("Agent")
    if settings.claude_web_tools:
        tools += WEB_TOOLS
    if options.mode == "code" and options.workspace is not None:
        tools += CODE_TOOLS
    return tools


def agent_definitions(settings: Settings, options: RunOptions) -> dict[str, Any]:
    """Definicja podagenta ``pomocnik`` (``--agents``): narzędzia sesji bez zlecania dalej."""
    from nexus.tools import registry

    tools = [f"{MCP_PREFIX}{name}" for name in registry.names()]
    tools += [tool for tool in session_tools(settings, options) if tool != "Agent"]
    definition: dict[str, Any] = {
        "description": (
            "Podagent Danaco Nexus do wydzielonej części zadania: praca na plikach narzędziami "
            "Nexusa, analiza, wyszukiwanie w sieci"
            + (", zmiany w kodzie projektu" if options.mode == "code" else "")
            + ". Uruchamiaj równolegle dla niezależnych części."
        ),
        "prompt": SUBAGENT_PROMPT
        + ("\n\n" + mode_instruction(options.mode) if options.mode == "code" else ""),
        "tools": tools,
    }
    if settings.claude_subagent_model:
        definition["model"] = settings.claude_subagent_model
    return {SUBAGENT_TYPE: definition}


def build_command(
    settings: Settings,
    mcp_config_path: Path,
    session_id: str,
    resume: bool,
    voice: bool = False,
    options: RunOptions | None = None,
) -> list[str]:
    """Polecenie ``claude -p`` (treść zadania przekazywana na stdin)."""
    options = options or RunOptions(voice=voice)
    tools = session_tools(settings, options)
    code = "Bash" in tools
    allowed = [*ALLOWED_TOOLS, *(tool for tool in tools if tool in ("Agent", *WEB_TOOLS))]
    if code:
        # Edycje plików w katalogu projektu akceptuje tryb acceptEdits; Bash wymaga reguły.
        allowed.append("Bash")
    enabled = set(tools) | (AGENT_TOOLS if "Agent" in tools else set())
    disallowed = [tool for tool in DISALLOWED_TOOLS if tool not in enabled]
    if code:
        disallowed += CODE_BASH_DENY
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
        system_prompt(settings.claude_subagents, settings.claude_web_tools, settings.agenci_max_podagentow),
        "--mcp-config",
        str(mcp_config_path),
        "--strict-mcp-config",
        "--tools",
        ",".join(tools),
        "--allowed-tools",
        *allowed,
        "--disallowed-tools",
        *disallowed,
        # Bez hosta uprawnień: wszystko, co wymagałoby zgody, jest odrzucane.
        "--permission-prompts",
        "none",
    ]
    instruction = mode_instruction(options.mode)
    if instruction:
        command += ["--append-system-prompt", instruction]
    if settings.claude_subagents:
        command += [
            "--agents",
            json.dumps(agent_definitions(settings, options), ensure_ascii=False),
            "--forward-subagent-text",
        ]
    if code and options.workspace is not None:
        command += ["--permission-mode", "acceptEdits", "--add-dir", str(options.workspace)]
    if settings.claude_fallback_model and settings.claude_fallback_model != settings.claude_model:
        command += ["--fallback-model", settings.claude_fallback_model]
    # Rozmowa głosowa: krótszy namysł – odpowiedź ma przyjść szybko.
    effort = (
        settings.claude_voice_effort
        if options.voice and settings.claude_voice_effort
        else settings.claude_effort
    )
    if effort:
        command += ["--effort", effort]
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


def truncate_content(content: Any, limit: int = BUILTIN_RESULT_CHARS) -> Any:
    """Skraca długie wyniki narzędzi wbudowanych (np. treść odczytanego pliku) przed zapisem."""
    if isinstance(content, str):
        return content if len(content) <= limit else content[:limit] + "…"
    if isinstance(content, list):
        return [
            {**part, "text": truncate_content(part["text"], limit)}
            if isinstance(part, dict) and isinstance(part.get("text"), str)
            else part
            for part in strip_images(content)
        ]
    return content


def result_text(block: dict[str, Any]) -> str:
    """Tekst bloku ``tool_result`` (pierwsza część tekstowa albo cały napis)."""
    content = block.get("content")
    if isinstance(content, str):
        return content
    return "\n".join(
        part.get("text", "")
        for part in content or []
        if isinstance(part, dict) and part.get("type") == "text"
    )


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


def builtin_summary(name: str, block: dict[str, Any]) -> str:
    """Krótki opis wyniku narzędzia wbudowanego CLI (bez przepisywania całej treści)."""
    text = result_text(block).strip()
    if block.get("is_error"):
        return re.sub(r"</?tool_use_error>", "", text)[:500] or "Błąd narzędzia"
    lines = [line for line in text.splitlines() if line.strip()]
    if name == "Read":
        return f"Odczytano {len(lines)} wierszy"
    if name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return "Zapisano zmiany"
    if name in ("Glob", "Grep"):
        if not lines or lines[0].lower().startswith("no "):
            return "Brak wyników"
        return f"Wyników: {len(lines)}"
    if name == "WebFetch":
        return "Odczytano stronę"
    if name == "WebSearch":
        return "Wyszukano w sieci"
    if name == "Bash":
        return "\n".join(lines[-6:])[-600:] or "Wykonano"
    return (lines[0] if lines else "")[:300]


def agent_output(text: str) -> str:
    """Wynik podagenta bez metadanych CLI (identyfikator agenta, zużycie)."""
    text = re.sub(r"<usage>.*?</usage>", "", text, flags=re.DOTALL)
    lines = [line for line in text.splitlines() if not line.strip().lower().startswith("agentid:")]
    return "\n".join(lines).strip()[:2000]


def friendly_error(text: str) -> str:
    """Komunikat błędu pokazywany użytkownikowi.

    Użytkownik ma widzieć wyłącznie to, co dotyczy jego konta. Stan kont silnika, ich limity
    i sposób logowania są sprawą operatora: trafiają do dziennika, nie na ekran. Inaczej
    tester zamiast „spróbuj za chwilę” dostaje informację, ile zostało cudzego limitu.
    """
    lowered = text.lower()
    if any(pattern in lowered for pattern in LIMIT_PATTERNS):
        return "Usługa jest chwilowo przeciążona. Zadanie można ponowić za kilka minut."
    if any(pattern in lowered for pattern in AUTH_PATTERNS):
        return "Usługa jest chwilowo niedostępna. Pracujemy nad przywróceniem jej działania."
    return "Zadanie nie zostało ukończone. Spróbuj ponownie; jeśli wróci, napisz do nas."


def input_preview(raw: Any) -> dict[str, Any]:
    """Skrócony opis parametrów narzędzia do wyświetlenia w interfejsie."""
    if not isinstance(raw, dict):
        return {}
    preview: dict[str, Any] = {}
    for key, value in raw.items():
        text = json.dumps(value, ensure_ascii=False)
        preview[key] = value if len(text) <= 200 else text[:200] + "…"
    return preview


def rate_limit_warning(info: dict[str, Any]) -> str:
    """Ostrzeżenie o wyczerpywaniu limitu konta (pusty napis, gdy daleko do limitu)."""
    windows = info.get("unifiedWindows") if isinstance(info.get("unifiedWindows"), dict) else {}
    labels = {"five_hour": "5-godzinnego", "seven_day": "tygodniowego"}
    worst: tuple[float, str, Any] | None = None
    for key, window in windows.items():
        if not isinstance(window, dict):
            continue
        try:
            utilization = float(window.get("utilization") or 0)
        except (TypeError, ValueError):
            continue
        if worst is None or utilization > worst[0]:
            worst = (utilization, labels.get(key, key), window.get("resetsAt"))
    status = str(info.get("status") or "allowed")
    if status != "allowed" and worst is None:
        return "Konto Claude osiągnęło limit użycia – zadania mogą czekać na odnowienie limitu."
    if worst is None or (worst[0] < RATE_LIMIT_WARN and status == "allowed"):
        return ""
    reset = ""
    if isinstance(worst[2], int | float):
        reset = f" (odnowienie: {_local_time(worst[2])})"
    return f"Wykorzystano {round(worst[0] * 100)}% limitu {worst[1]} konta Claude{reset}."


def _local_time(timestamp: float) -> str:
    moment = datetime.fromtimestamp(timestamp, UTC)
    with contextlib.suppress(Exception):
        from zoneinfo import ZoneInfo

        moment = moment.astimezone(ZoneInfo("Europe/Warsaw"))
    return moment.strftime("%d.%m %H:%M")


@dataclass
class _Buffer:
    """Łączy drobne fragmenty tekstu w większe zdarzenia (mniej zapisów w bazie)."""

    kind: str
    parts: list[str] = field(default_factory=list)
    last_flush: float = field(default_factory=time.monotonic)


@dataclass
class _Call:
    """Trwające wywołanie narzędzia (także podagenta) w przebiegu."""

    call_id: int
    name: str
    started: float
    parent: str | None = None
    mcp: bool = False
    agent: bool = False
    background: bool = False
    files: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _RunState:
    """Stan tłumaczenia strumienia CLI na zdarzenia jednego przebiegu."""

    run_id: uuid.UUID
    conversation_id: uuid.UUID
    owner_id: uuid.UUID = ADMIN_OWNER
    text: _Buffer = field(default_factory=lambda: _Buffer("text.delta"))
    thinking: _Buffer = field(default_factory=lambda: _Buffer("thinking.delta"))
    calls: dict[str, _Call] = field(default_factory=dict)
    session_id: str = ""
    result: dict[str, Any] | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    voice: bool = False
    init_seen: bool = False
    limit_warned: bool = False


class AgentRunner:
    """Wykonuje przebiegi agenta przez Claude Code CLI."""

    def __init__(self, settings: Settings, database: Database, events: EventBus | None = None) -> None:
        self._settings = settings
        self._db = database
        self._events = events or EventBus(settings.redis_url)
        self._shutdown = asyncio.Event()

    def interrupt_all(self) -> None:
        """Przerywa wszystkie trwające przebiegi (zatrzymanie procesu roboczego)."""
        self._shutdown.set()

    # --- zdarzenia i zapis -----------------------------------------------------------------

    async def emit(self, run_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> None:
        """Zapisuje zdarzenie przebiegu (odczytywane strumieniowo przez API)."""
        async with self._db.session() as session:
            session.add(RunEvent(run_id=run_id, type=event_type, data=data))
        await self._events.notify(run_id)

    async def _flush(self, run_id: uuid.UUID, buffer: _Buffer, force: bool = False) -> None:
        if not buffer.parts:
            return
        if force or time.monotonic() - buffer.last_flush >= TEXT_FLUSH_SECONDS:
            text = "".join(buffer.parts)
            buffer.parts.clear()
            buffer.last_flush = time.monotonic()
            await self.emit(run_id, buffer.kind, {"text": text})

    async def _flush_all(self, state: _RunState) -> None:
        await self._flush(state.run_id, state.text, force=True)
        await self._flush(state.run_id, state.thinking, force=True)

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
        state.owner_id = conversation.owner_id if conversation else ADMIN_OWNER
        state.voice = bool(prompt_message is not None and (prompt_message.meta or {}).get("voice"))
        meta = (conversation.meta if conversation else None) or {}
        mode = conversation_mode(meta)
        usage: dict[str, Any] = {}
        status, error_text = "done", ""
        timeout = run_timeout_minutes(self._settings, mode)
        await self.emit(run_id, "run.started", {"mode": mode} if mode != "chat" else {})
        try:
            options = self._options(mode, meta, state.voice)
            prompt = _prompt_text(prompt_message)
            await self._run_cli(state, conversation, prompt, options, timeout)
            result = state.result or {}
            usage = _usage_total(state.results or [result])
            if result.get("is_error") or result.get("subtype", "success") != "success":
                status = "failed"
                error_text = _result_error(result)
        except RunCancelled:
            status, error_text = "cancelled", "Zadanie anulowane."
        except RunTimedOut:
            status = "failed"
            error_text = f"Zadanie przekroczyło limit czasu ({timeout} min)."
        except RunInterrupted:
            status, error_text = "failed", "Zadanie przerwane (restart procesu roboczego)."
        except CliFailure as error:
            # Błąd zlecenia mówi użytkownikowi, co poprawić — zostaje bez zmian.
            status, error_text = "failed", (
                str(error) if isinstance(error, BladZlecenia) else friendly_error(str(error))
            )
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
        # Praca jest już wykonana, więc naliczamy ją także wtedy, gdy przebieg padł:
        # model i narzędzia zużyły czas maszyny niezależnie od wyniku. Anulowanie przez
        # użytkownika też kosztuje tyle, ile zdążyło policzyć.
        saldo_po = None
        try:
            async with self._db.session() as session:
                uzyte_narzedzia = list(
                    (await session.scalars(select(ToolCall.name).where(ToolCall.run_id == run_id))).all()
                )
            koszt = kredyty.koszt_przebiegu(usage, uzyte_narzedzia)
            saldo_po = await kredyty.obciaz(self._db, state.owner_id, koszt, run_id, usage)
        except Exception:  # noqa: BLE001 - brak naliczenia nie może przerwać zamknięcia przebiegu
            logger.exception("Nie udało się naliczyć kredytów za przebieg %s", run_id)
        final_type = {"done": "run.completed", "cancelled": "run.cancelled"}.get(status, "run.failed")
        await self.emit(
            run_id,
            final_type,
            {"error": error_text, "usage": usage, **({"saldo": saldo_po} if saldo_po is not None else {})},
        )
        async with self._db.session() as session:
            title = await session.scalar(
                select(Conversation.title).where(Conversation.id == run.conversation_id)
            )
        await self._events.notify_finished(run_id, run.conversation_id, status, title or "")
        logger.info(
            "Przebieg %s (%s): %s | model: %s | tury: %s | tokeny wej.: %s (cache: %s) | wyj.: %s",
            run_id,
            mode,
            status,
            state.model or "-",
            usage.get("num_turns", "-"),
            usage.get("input_tokens", "-"),
            usage.get("cache_read_input_tokens", "-"),
            usage.get("output_tokens", "-"),
        )

    def _options(self, mode: str, meta: dict[str, Any], voice: bool) -> RunOptions:
        workspace = None
        if mode == "code":
            name = str(meta.get("workspace") or "")
            workspace = existing_project(self._settings, name)
            if workspace is None:
                raise BladZlecenia(f"projekt „{name}” nie istnieje w module Kod")
        return RunOptions(mode=mode, workspace=workspace, voice=voice)

    async def _session_for(
        self, state: _RunState, conversation: Conversation | None
    ) -> tuple[str, bool, str]:
        """Identyfikator sesji CLI, czy wznawiać, oraz ewentualne streszczenie historii."""
        existing = conversation.claude_session_id if conversation else None
        if existing and find_session_file(self._settings.claude_profile_dir, existing):
            return existing, True, ""
        session_id = str(uuid.uuid4())
        digest = await self._history_digest(state) if existing else ""
        if existing:
            # Zapis sesji CLI zniknął: rozmowa dostaje streszczenie zamiast pełnego kontekstu.
            # Bez tego wpisu degradacja przechodzi bez śladu, bo nie jest błędem.
            logger.warning(
                "Przebieg %s: brak zapisu sesji CLI %s w %s — kontekst zastąpiony streszczeniem (%s znaków)",
                state.run_id,
                existing,
                self._settings.claude_profile_dir,
                len(digest),
            )
            await self.emit(
                state.run_id,
                "notice",
                {"text": "Zapis poprzedniej sesji wygasł — pracuję na streszczeniu wcześniejszej rozmowy."},
            )
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

    async def _run_cli(
        self,
        state: _RunState,
        conversation: Conversation | None,
        prompt: str,
        options: RunOptions,
        timeout_minutes: int,
    ) -> None:
        settings = self._settings
        session_id, resume, digest = await self._session_for(state, conversation)
        run_dir = settings.work_dir / f"cli-{state.run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        cwd = options.workspace or settings.data_dir / "agent"
        cwd.mkdir(parents=True, exist_ok=True)
        config_path = run_dir / "mcp.json"
        config_path.write_text(
            json.dumps(mcp_config(state.run_id, state.conversation_id, state.owner_id)), encoding="utf-8"
        )
        command = build_command(settings, config_path, session_id, resume, options=options)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=cli_environment(settings, run_dir, code=options.mode == "code"),
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
        shutdown_wait = asyncio.create_task(self._shutdown.wait())
        try:
            assert process.stdin is not None
            process.stdin.write((digest + prompt).encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()
            done, _ = await asyncio.wait(
                {reader, cancel_wait, shutdown_wait},
                timeout=timeout_minutes * 60,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if reader not in done:
                await _terminate(process)
                reader.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await reader
                if cancel_wait in done:
                    raise RunCancelled
                raise RunInterrupted if shutdown_wait in done else RunTimedOut
            reader.result()
            returncode = await process.wait()
            await stderr_task
            await self._flush_all(state)
            if state.result is None:
                raise CliFailure(f"kod wyjścia {returncode}\n" + "\n".join(stderr_tail))
            if state.result.get("is_error"):
                state.result.setdefault("stderr", "\n".join(stderr_tail))
        finally:
            watcher.cancel()
            cancel_wait.cancel()
            shutdown_wait.cancel()
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
        """Tłumaczy jedno zdarzenie strumienia CLI (także zdarzenia podagentów)."""
        kind = event.get("type")
        parent = event.get("parent_tool_use_id") or None
        if kind == "system":
            await self._system(state, event)
        elif kind == "stream_event":
            # Fragmenty odpowiedzi strumieniuje tylko agent główny; podagenci przysyłają całe bloki.
            if parent is None:
                await self._stream_event(state, event.get("event") or {})
        elif kind == "assistant":
            await self._assistant(state, event.get("message") or {}, parent)
        elif kind == "user":
            await self._tool_results(state, event.get("message") or {}, parent)
        elif kind == "result" and parent is None:
            state.results.append(event)
            state.result = event
        elif kind == "rate_limit_event":
            await self._rate_limit(state, event.get("rate_limit_info") or {})

    async def _system(self, state: _RunState, event: dict[str, Any]) -> None:
        subtype = event.get("subtype")
        if subtype == "init":
            # Po zakończeniu podagentów w tle CLI rozpoczyna kolejną turę z nowym „init”.
            state.session_id = event.get("session_id", "") or state.session_id
            state.model = event.get("model", "") or state.model
            if state.init_seen:
                return
            state.init_seen = True
            failed = [
                server.get("name")
                for server in event.get("mcp_servers") or []
                if isinstance(server, dict) and server.get("status") not in ("connected", None)
            ]
            if failed:
                await self.emit(
                    state.run_id, "notice", {"text": "Narzędzia serwera są niedostępne (błąd serwera MCP)."}
                )
        elif subtype == "task_notification":
            tool_use_id = str(event.get("tool_use_id") or "")
            call = state.calls.get(tool_use_id)
            if call is None or not call.agent:
                return
            status = AGENT_STATUS.get(str(event.get("status") or "").lower(), "done")
            summary = agent_output(str(event.get("summary") or ""))
            await self._finish_call(state, tool_use_id, status, summary or _status_text(status), [])
        elif subtype == "task_progress":
            tool_use_id = str(event.get("tool_use_id") or "")
            call = state.calls.get(tool_use_id)
            if call is None or not call.agent:
                return
            text = str(event.get("description") or event.get("last_tool_name") or "")
            if text:
                await self.emit(
                    state.run_id, "tool.progress", {"tool_use_id": tool_use_id, "text": text[:300]}
                )

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
            await self._flush_all(state)
            block = event.get("content_block") or {}
            name = block.get("name", "")
            if block.get("type") == "tool_use" and name not in HIDDEN_TOOLS:
                await self.emit(state.run_id, "tool.pending", {"name": tool_display_name(name)})
            elif block.get("type") == "text":
                await self.emit(state.run_id, "text.block", {})
        elif kind == "message_stop":
            await self._flush_all(state)

    async def _assistant(self, state: _RunState, message: dict[str, Any], parent: str | None) -> None:
        if parent is None:
            await self._flush_all(state)
        content = []
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "tool_use":
                name = block.get("name", "")
                if name in HIDDEN_TOOLS:
                    continue
                await self._start_call(state, block, parent)
                block = {**block, "name": tool_display_name(name)}
            elif kind == "text" and parent is not None:
                if block.get("text"):
                    data = {"parent_tool_use_id": parent}
                    await self.emit(state.run_id, "text.block", data)
                    await self.emit(state.run_id, "text.delta", {**data, "text": block["text"]})
                continue
            if kind in ("text", "thinking", "tool_use"):
                content.append(block)
        if parent is not None:
            return
        if message.get("model"):
            state.model = message["model"]
        if content:
            await self._append(state, "assistant", "assistant", content, {"model": message.get("model", "")})

    async def _start_call(self, state: _RunState, block: dict[str, Any], parent: str | None) -> None:
        tool_use_id = block.get("id", "")
        raw_name = block.get("name", "")
        name = tool_display_name(raw_name)
        raw_input = block.get("input") if isinstance(block.get("input"), dict) else {}
        agent = raw_name in AGENT_TOOLS
        async with self._db.session() as session:
            call = ToolCall(run_id=state.run_id, tool_use_id=tool_use_id, name=name, input=raw_input)
            session.add(call)
            await session.flush()
            state.calls[tool_use_id] = _Call(
                call.id,
                name,
                time.monotonic(),
                parent=parent,
                mcp=raw_name.startswith(MCP_PREFIX),
                agent=agent,
            )
        data: dict[str, Any] = {"tool_use_id": tool_use_id, "name": name, "input": input_preview(raw_input)}
        if parent is not None:
            data["parent_tool_use_id"] = parent
        if agent:
            data["agent"] = {
                "description": str(raw_input.get("description") or "")[:200],
                "subagent_type": str(raw_input.get("subagent_type") or ""),
                "background": bool(raw_input.get("run_in_background")),
            }
        await self.emit(state.run_id, "tool.started", data)

    async def _tool_results(self, state: _RunState, message: dict[str, Any], parent: str | None) -> None:
        content = message.get("content")
        if not isinstance(content, list):
            return
        stored = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            tool_use_id = block.get("tool_use_id", "")
            call = state.calls.get(tool_use_id)
            if call is None:
                continue
            status = "error" if block.get("is_error") else "done"
            files: list[dict[str, Any]] = []
            if call.agent:
                text = result_text(block)
                if not block.get("is_error") and BACKGROUND_AGENT_MARKER in text.lower():
                    # Podagent w tle: wynik przyjdzie w zdarzeniu task_notification.
                    call.background = True
                    await self.emit(
                        state.run_id, "tool.progress", {"tool_use_id": tool_use_id, "text": "Pracuje w tle…"}
                    )
                    stored.append({**block, "content": truncate_content(block.get("content"))})
                    continue
                summary = agent_output(text) or _status_text(status)
            elif call.mcp:
                summary, files = parse_tool_result(block)
            else:
                summary = builtin_summary(call.name, block)
            await self._finish_call(state, tool_use_id, status, summary, files)
            if call.mcp:
                stored.append({**block, "content": strip_images(block.get("content"))})
            else:
                stored.append({**block, "content": truncate_content(block.get("content"))})
        if stored and parent is None:
            await self._append(state, "user", "tool_results", stored, {})

    async def _finish_call(
        self, state: _RunState, tool_use_id: str, status: str, summary: str, files: list[dict[str, Any]]
    ) -> None:
        call = state.calls.pop(tool_use_id)
        duration = int((time.monotonic() - call.started) * 1000)
        if call.agent:
            # Podagent oddaje pliki wszystkich swoich wywołań (widoczne też w historii rozmowy).
            files = [*files, *call.files]
        async with self._db.session() as session:
            await session.execute(
                update(ToolCall)
                .where(ToolCall.id == call.call_id)
                .values(
                    status=status,
                    summary=summary[:2000],
                    duration_ms=duration,
                    output_file_ids=[f["id"] for f in files],
                )
            )
        if files:
            ancestor = state.calls.get(call.parent) if call.parent else None
            if ancestor is not None and ancestor.agent:
                ancestor.files.extend(files)
        data: dict[str, Any] = {
            "tool_use_id": tool_use_id,
            "name": call.name,
            "status": status,
            "summary": summary[:500],
            "files": files,
            "duration_ms": duration,
        }
        if call.parent is not None:
            data["parent_tool_use_id"] = call.parent
        await self.emit(state.run_id, "tool.finished", data)

    async def _close_open_calls(self, state: _RunState, status: str) -> None:
        """Wywołania bez wyniku (przerwany przebieg) oznacza jako anulowane lub błędne."""
        final = "cancelled" if status == "cancelled" else "error"
        summary = "Anulowano" if final == "cancelled" else "Przerwano"
        # Najpierw najgłębiej zagnieżdżone (odwrotna kolejność), żeby pliki trafiły do podagentów.
        for tool_use_id in reversed(list(state.calls)):
            if tool_use_id in state.calls:
                await self._finish_call(state, tool_use_id, final, summary, [])

    async def _rate_limit(self, state: _RunState, info: dict[str, Any]) -> None:
        """Zapamiętuje stan limitów konta (moduł Agenci) i ostrzega przy ich wyczerpywaniu."""
        if not isinstance(info, dict) or not info:
            return
        payload = json.dumps({**info, "updated_at": utcnow().isoformat()}, ensure_ascii=False)
        try:
            async with self._db.session() as session:
                await session.merge(Setting(key=RATE_LIMIT_KEY, value=payload, updated_at=utcnow()))
        except Exception:  # noqa: BLE001 - informacja pomocnicza, równoległe zapisy mogą się zderzyć
            logger.debug("Nie zapisano stanu limitów konta", exc_info=True)
        # Stan limitów kont silnika zostaje po stronie operatora: w ustawieniach i w dzienniku.
        # Użytkownik nie może się z aplikacji dowiedzieć, z jakiego konta korzysta ani ile
        # zostało jego limitu — widzi wyłącznie własne saldo kredytów.
        warning = rate_limit_warning(info)
        if warning and not state.limit_warned:
            state.limit_warned = True
            logger.warning("Limity konta silnika (przebieg %s): %s", state.run_id, warning)


def _status_text(status: str) -> str:
    return {"done": "Zakończono", "cancelled": "Anulowano"}.get(status, "Nie powiodło się")


def _prompt_text(message: Message | None) -> str:
    if message is None:
        raise CliFailure("brak wiadomości użytkownika dla zadania")
    text = "\n".join(
        block.get("text", "")
        for block in message.content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()
    if (message.meta or {}).get("voice"):
        text = f"{VOICE_INSTRUCTION}\n\n{text}"
    return text


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


def _usage_total(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Zużycie wszystkich tur przebiegu (podagenci w tle wydłużają przebieg o kolejne tury)."""
    total: dict[str, Any] = {}
    for result in results:
        for name, value in _usage(result).items():
            if name == "total_cost_usd":
                # CLI podaje koszt narastająco w obrębie procesu.
                total[name] = value
            elif isinstance(value, int | float):
                total[name] = total.get(name, 0) + value
    return total


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
    """Kończy CLI wraz z procesami potomnymi (serwer MCP, podagenci, programy narzędzi)."""
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
