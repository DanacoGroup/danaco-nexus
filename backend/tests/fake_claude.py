"""Atrapa Claude Code CLI dla testów (``claude -p --output-format stream-json``).

Wypisuje zdarzenia w formacie CLI i – w scenariuszu ``tool`` – naprawdę
uruchamia serwer MCP z ``--mcp-config`` oraz wywołuje przez niego narzędzie
``convert_images`` dla pierwszego ``file_id`` z treści zadania.

Scenariusz ``agents`` odtwarza strumień z podagentami (zdarzenia z
``parent_tool_use_id``, podagent w tle z ``task_notification``, dwie tury
i dwa wyniki), a podagent wywołuje narzędzie przez prawdziwy serwer MCP.

Sterowanie zmiennymi: ``FAKE_CLAUDE_SCENARIO`` (``tool``, ``agents``, ``text``,
``sleep``, ``auth``, ``hang``, ``crash``), ``FAKE_CLAUDE_SLEEP`` (sekundy dla
``sleep``) i ``FAKE_CLAUDE_LOG`` (plik JSONL z argumentami wywołań).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from typing import Any

MCP_PREFIX = "mcp__nexus__"


def out(event: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def option(args: list[str], name: str) -> str:
    return args[args.index(name) + 1] if name in args else ""


def stream(session: str, event: dict[str, Any]) -> None:
    out({"type": "stream_event", "event": event, "session_id": session, "parent_tool_use_id": None})


def text_block(session: str, index: int, text: str) -> None:
    stream(
        session,
        {"type": "content_block_start", "index": index, "content_block": {"type": "text", "text": ""}},
    )
    half = len(text) // 2
    for part in (text[:half], text[half:]):
        stream(
            session,
            {"type": "content_block_delta", "index": index, "delta": {"type": "text_delta", "text": part}},
        )
    stream(session, {"type": "content_block_stop", "index": index})


def assistant(session: str, content: list[dict[str, Any]], parent: str | None = None) -> None:
    out(
        {
            "type": "assistant",
            "message": {"id": "msg_1", "role": "assistant", "model": "claude-opus-5", "content": content},
            "session_id": session,
            "parent_tool_use_id": parent,
        }
    )


def tool_result(session: str, tool_use_id: str, result: dict[str, Any], parent: str | None = None) -> None:
    out(
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tool_use_id, **result}],
            },
            "session_id": session,
            "parent_tool_use_id": parent,
        }
    )


def system(session: str, subtype: str, **data: Any) -> None:
    out({"type": "system", "subtype": subtype, "session_id": session, **data})


def agents_scenario(session: str, config_path: str, file_id: str) -> None:
    """Dwa podagenty: pierwszy (na pierwszym planie) konwertuje plik, drugi pracuje w tle."""
    out(
        {
            "type": "rate_limit_event",
            "rate_limit_info": {
                "status": "allowed",
                "unifiedWindows": {"five_hour": {"utilization": 0.95, "resetsAt": 1789834200}},
            },
            "session_id": session,
        }
    )
    first = {"description": "Konwersja skanu", "subagent_type": "pomocnik", "prompt": f"Zamień {file_id}"}
    second = {
        "description": "Opis dokumentu",
        "subagent_type": "pomocnik",
        "prompt": "Opisz dokument",
        "run_in_background": True,
    }
    stream(
        session,
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "toolu_a1", "name": "Agent", "input": {}},
        },
    )
    assistant(
        session,
        [
            {"type": "tool_use", "id": "toolu_a1", "name": "Agent", "input": first},
            {"type": "tool_use", "id": "toolu_a2", "name": "Agent", "input": second},
        ],
    )
    system(session, "task_started", task_id="t1", tool_use_id="toolu_a1", description="Konwersja skanu")
    tool_result(
        session,
        "toolu_a2",
        {
            "content": [
                {"type": "text", "text": "Async agent launched successfully.\nagentId: a2 (internal ID)"}
            ]
        },
    )
    assistant(session, [{"type": "text", "text": "Zamieniam skan na PNG."}], parent="toolu_a1")
    tool_input = {"file_ids": [file_id], "target_format": "png"}
    assistant(
        session,
        [{"type": "tool_use", "id": "toolu_s1", "name": f"{MCP_PREFIX}convert_images", "input": tool_input}],
        parent="toolu_a1",
    )
    called = asyncio.run(call_tool(config_path, "convert_images", tool_input))
    tool_result(session, "toolu_s1", called, parent="toolu_a1")
    assistant(
        session,
        [{"type": "tool_use", "id": "toolu_s2", "name": "ToolSearch", "input": {}}],
        parent="toolu_a2",
    )
    tool_result(session, "toolu_s2", {"content": "brak"}, parent="toolu_a2")
    tool_result(
        session,
        "toolu_a1",
        {
            "content": [
                {"type": "text", "text": "Plik PNG gotowy.\nagentId: a1\n<usage>total_tokens: 10</usage>"}
            ]
        },
    )
    text_block(session, 1, "Pierwszy podagent skończył, czekam na drugi.")
    assistant(session, [{"type": "text", "text": "Pierwszy podagent skończył, czekam na drugi."}])
    result(session)
    system(session, "task_progress", tool_use_id="toolu_a2", description="Czytam dokument")
    assistant(session, [{"type": "text", "text": "Dokument to umowa."}], parent="toolu_a2")
    system(
        session,
        "task_notification",
        task_id="a2",
        tool_use_id="toolu_a2",
        status="completed",
        summary="Dokument to umowa o świadczenie usług.",
    )
    system(session, "init", model="claude-opus-5", mcp_servers=[{"name": "nexus", "status": "connected"}])


def result(session: str, is_error: bool = False, text: str = "Gotowe.", subtype: str = "success") -> None:
    out(
        {
            "type": "result",
            "subtype": subtype,
            "is_error": is_error,
            "result": text,
            "num_turns": 2,
            "duration_ms": 1234,
            "total_cost_usd": 0.01,
            "usage": {
                "input_tokens": 120,
                "output_tokens": 30,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 0,
            },
            "session_id": session,
        }
    )


async def call_tool(config_path: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    with open(config_path, encoding="utf-8") as handle:
        server = json.load(handle)["mcpServers"]["nexus"]
    parameters = StdioServerParameters(
        command=server["command"], args=server["args"], env={**os.environ, **server.get("env", {})}
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert any(tool.name == name for tool in tools.tools)
            called = await session.call_tool(name, arguments)
    content = []
    for part in called.content:
        if part.type == "text":
            content.append({"type": "text", "text": part.text})
        elif part.type == "image":
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": part.mime_type, "data": part.data},
                }
            )
    return {"content": content, "is_error": bool(called.is_error)}


def main() -> int:
    args = sys.argv[1:]
    prompt = sys.stdin.read()
    log = os.environ.get("FAKE_CLAUDE_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "args": args,
                        "prompt": prompt,
                        "token": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", ""),
                        "api_key_present": "ANTHROPIC_API_KEY" in os.environ,
                        "config_dir": os.environ.get("CLAUDE_CONFIG_DIR", ""),
                        "cwd": os.getcwd(),
                        "git_author": os.environ.get("GIT_AUTHOR_NAME", ""),
                    }
                )
                + "\n"
            )
    session = option(args, "--session-id") or option(args, "--resume")
    scenario = os.environ.get("FAKE_CLAUDE_SCENARIO", "tool")
    if scenario == "crash":
        sys.stderr.write("TypeError: nieoczekiwany błąd\n")
        return 1
    out(
        {
            "type": "system",
            "subtype": "init",
            "session_id": session,
            "model": option(args, "--model"),
            "tools": [f"{MCP_PREFIX}convert_images", "ToolSearch"],
            "mcp_servers": [{"name": "nexus", "status": "connected"}],
        }
    )
    if scenario == "auth":
        result(session, True, "Invalid API key · Please run /login")
        return 1
    if scenario == "sleep":
        time.sleep(float(os.environ.get("FAKE_CLAUDE_SLEEP", "1")))
    if scenario == "agents":
        match = re.search(r"file_id: ([0-9a-f-]{36})", prompt)
        assert match, prompt
        agents_scenario(session, option(args, "--mcp-config"), match.group(1))
    if scenario == "hang":
        text_block(session, 0, "Pracuję…")
        time.sleep(600)
        return 0
    if scenario == "tool":
        match = re.search(r"file_id: ([0-9a-f-]{36})", prompt)
        assert match, prompt
        stream(session, {"type": "message_start", "message": {"id": "msg_1", "model": "claude-opus-5"}})
        stream(
            session,
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "thinking", "thinking": ""},
            },
        )
        stream(
            session,
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": "Konwertuję obraz."},
            },
        )
        assistant(session, [{"type": "thinking", "thinking": "Konwertuję obraz.", "signature": "sig"}])
        text_block(session, 1, "Zamieniam skan na PNG.")
        assistant(session, [{"type": "text", "text": "Zamieniam skan na PNG."}])
        tool_input = {"file_ids": [match.group(1)], "target_format": "png"}
        stream(
            session,
            {
                "type": "content_block_start",
                "index": 2,
                "content_block": {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": f"{MCP_PREFIX}convert_images",
                    "input": {},
                },
            },
        )
        assistant(
            session,
            [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": f"{MCP_PREFIX}convert_images",
                    "input": tool_input,
                }
            ],
        )
        called = asyncio.run(call_tool(option(args, "--mcp-config"), "convert_images", tool_input))
        out(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_1", **called}],
                },
                "session_id": session,
                "parent_tool_use_id": None,
            }
        )
    text_block(session, 0, "Gotowe – plik PNG jest do pobrania.")
    assistant(session, [{"type": "text", "text": "Gotowe – plik PNG jest do pobrania."}])
    result(session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
