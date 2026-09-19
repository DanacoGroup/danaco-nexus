"""Testy przebiegu agenta przez Claude Code CLI (atrapa ``tests/fake_claude.py``).

Atrapa wypisuje zdarzenia w formacie ``stream-json`` i uruchamia prawdziwy
serwer MCP narzędzi, więc testy obejmują całą ścieżkę: kolejkę → CLI → MCP
→ narzędzie → zapis plików, historii i zdarzeń.
"""

from __future__ import annotations

import asyncio
import json
import re
import stat
import sys
import uuid
from pathlib import Path

import pytest
from conftest import render_text_image, write_image
from sqlalchemy import select, update

from nexus.agent.runner import (
    ALLOWED_TOOLS,
    AgentRunner,
    build_command,
    friendly_error,
    parse_tool_result,
    strip_images,
    tool_display_name,
)
from nexus.config import Settings
from nexus.db import Conversation, Database, Message, Run, RunEvent, StoredFile, ToolCall
from nexus.storage import FileStorage
from nexus.tools import registry

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="grupy procesów i skrypty wykonywalne POSIX")

FAKE_CLAUDE = Path(__file__).with_name("fake_claude.py")


def make_fake_cli(directory: Path) -> Path:
    """Plik wykonywalny ``claude`` uruchamiający atrapę interpreterem testów."""
    script = directory / "claude"
    script.write_text(f"#!/bin/sh\nexec '{sys.executable}' '{FAKE_CLAUDE}' \"$@\"\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


async def prepare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str = "tool", database_url: str | None = None
) -> tuple[Settings, Database, uuid.UUID, uuid.UUID, str, Path]:
    data_dir = tmp_path / "data"
    url = database_url or f"sqlite+aiosqlite:///{(tmp_path / 'agent.db').as_posix()}"
    profile = tmp_path / "profil" / "claude"
    profile.mkdir(parents=True)
    (profile / "oauth-token").write_text("token-testowy\n", encoding="utf-8")
    log = tmp_path / "claude-calls.jsonl"
    # Serwer MCP (proces potomny atrapy CLI) czyta konfigurację ze środowiska.
    monkeypatch.setenv("NEXUS_DATABASE_URL", url)
    monkeypatch.setenv("NEXUS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FAKE_CLAUDE_SCENARIO", scenario)
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "nie-powinien-trafic-do-cli")
    settings = Settings(
        data_dir=data_dir,
        database_url=url,
        claude_bin=str(make_fake_cli(tmp_path)),
        claude_profile_dir=profile,
        run_timeout_minutes=5,
    )
    database = Database(url)
    await database.create_schema()
    storage = FileStorage(settings.files_dir)
    image_path = write_image(tmp_path / "skan.jpg", render_text_image(dpi=60))
    with image_path.open("rb") as handle:
        file_id, relative, size, digest = storage.save_stream(handle, "skan.jpg", 10**8)
    conversation = Conversation(id=uuid.uuid4())
    async with database.session() as session:
        session.add(conversation)
        await session.flush()
        session.add(
            StoredFile(
                id=file_id,
                conversation_id=conversation.id,
                origin="upload",
                name="skan.jpg",
                mime="image/jpeg",
                size=size,
                sha256=digest,
                storage_path=relative,
            )
        )
    run_id = await add_run(database, conversation.id, f"Zamień na PNG\nfile_id: {file_id}")
    return settings, database, conversation.id, run_id, str(file_id), log


async def add_run(database: Database, conversation_id: uuid.UUID, text: str) -> uuid.UUID:
    run = Run(conversation_id=conversation_id)
    async with database.session() as session:
        session.add(run)
        await session.flush()
        session.add(
            Message(
                conversation_id=conversation_id,
                run_id=run.id,
                role="user",
                kind="user",
                content=[{"type": "text", "text": text}],
                meta={"text": text},
            )
        )
    return run.id


def calls(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


async def events(database: Database, run_id: uuid.UUID) -> list[RunEvent]:
    async with database.session() as session:
        return list(
            (
                await session.scalars(select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.id))
            ).all()
        )


async def test_cli_run_with_mcp_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings, database, conversation_id, run_id, file_id, log = await prepare(tmp_path, monkeypatch)
    await AgentRunner(settings, database).execute(run_id)
    async with database.session() as session:
        run = await session.get(Run, run_id)
        messages = (
            await session.scalars(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
            )
        ).all()
        call = await session.scalar(select(ToolCall).where(ToolCall.run_id == run_id))
        results = (await session.scalars(select(StoredFile).where(StoredFile.origin == "result"))).all()
        conversation = await session.get(Conversation, conversation_id)
    assert run is not None and run.status == "done", run.error if run else ""
    assert run.usage["input_tokens"] == 120 and run.usage["num_turns"] == 2
    assert [m.kind for m in messages] == [
        "user",
        "assistant",
        "assistant",
        "assistant",
        "tool_results",
        "assistant",
    ]
    assert messages[3].content[0]["name"] == "convert_images"
    stored_result = messages[4].content[0]
    assert all(part.get("type") != "image" for part in stored_result["content"])
    assert call is not None and call.name == "convert_images" and call.status == "done"
    assert len(results) == 1 and results[0].name.endswith(".png")
    assert results[0].conversation_id == conversation_id and results[0].run_id == run_id
    assert call.output_file_ids == [str(results[0].id)]
    assert conversation is not None and conversation.claude_session_id

    types = [event.type for event in await events(database, run_id)]
    assert types[0] == "run.started" and types[-1] == "run.completed"
    for expected in (
        "thinking.delta",
        "text.block",
        "text.delta",
        "tool.pending",
        "tool.started",
        "tool.finished",
    ):
        assert expected in types, expected
    finished = next(e for e in await events(database, run_id) if e.type == "tool.finished")
    assert finished.data["name"] == "convert_images" and finished.data["files"][0]["id"] == str(results[0].id)

    (invocation,) = calls(log)
    args = invocation["args"]
    assert invocation["token"] == "token-testowy" and not invocation["api_key_present"]
    assert invocation["config_dir"] == str(settings.claude_profile_dir)
    assert args[args.index("--session-id") + 1] == conversation.claude_session_id
    assert "--resume" not in args and "--strict-mcp-config" in args
    assert f"file_id: {file_id}" in invocation["prompt"]


async def test_second_run_resumes_cli_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings, database, conversation_id, run_id, _file_id, log = await prepare(tmp_path, monkeypatch, "text")
    runner = AgentRunner(settings, database)
    await runner.execute(run_id)
    async with database.session() as session:
        session_id = (await session.get(Conversation, conversation_id)).claude_session_id
    # Zapis sesji tworzy CLI; atrapa go nie tworzy, więc symulujemy go w profilu.
    session_file = settings.claude_profile_dir / "projects" / "-dane-agent" / f"{session_id}.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text("{}\n", encoding="utf-8")
    second = await add_run(database, conversation_id, "Dziękuję, a teraz streść dokument.")
    await runner.execute(second)
    first_call, second_call = calls(log)
    assert second_call["args"][second_call["args"].index("--resume") + 1] == session_id
    assert "--session-id" not in second_call["args"]
    assert "[Wcześniejsza część" not in second_call["prompt"]
    assert first_call["prompt"].startswith("Zamień na PNG")


async def test_lost_cli_session_starts_new_one_with_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, database, conversation_id, run_id, _file_id, log = await prepare(tmp_path, monkeypatch, "text")
    runner = AgentRunner(settings, database)
    await runner.execute(run_id)
    second = await add_run(database, conversation_id, "Co było w poprzedniej odpowiedzi?")
    await runner.execute(second)
    first_call, second_call = calls(log)
    first_id = first_call["args"][first_call["args"].index("--session-id") + 1]
    second_id = second_call["args"][second_call["args"].index("--session-id") + 1]
    assert first_id != second_id
    assert second_call["prompt"].startswith("[Wcześniejsza część tej rozmowy")
    assert "Gotowe – plik PNG" in second_call["prompt"]
    assert second_call["prompt"].rstrip().endswith("Co było w poprzedniej odpowiedzi?")


@pytest.mark.parametrize(
    ("scenario", "message"),
    [("auth", "nie jest zalogowany"), ("crash", "Błąd Claude Code CLI")],
)
async def test_cli_failures_mark_run_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str, message: str
) -> None:
    settings, database, _conversation_id, run_id, _file_id, _log = await prepare(
        tmp_path, monkeypatch, scenario
    )
    await AgentRunner(settings, database).execute(run_id)
    async with database.session() as session:
        run = await session.get(Run, run_id)
    assert run is not None and run.status == "failed"
    assert message in run.error
    assert (await events(database, run_id))[-1].type == "run.failed"


async def test_cancel_kills_cli_process_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings, database, _conversation_id, run_id, _file_id, _log = await prepare(
        tmp_path, monkeypatch, "hang"
    )
    task = asyncio.create_task(AgentRunner(settings, database).execute(run_id))
    for _ in range(100):
        if any(event.type == "text.delta" for event in await events(database, run_id)):
            break
        await asyncio.sleep(0.1)
    async with database.session() as session:
        await session.execute(update(Run).where(Run.id == run_id).values(cancel_requested=True))
    await asyncio.wait_for(task, 30)
    async with database.session() as session:
        run = await session.get(Run, run_id)
    assert run is not None and run.status == "cancelled"
    assert (await events(database, run_id))[-1].type == "run.cancelled"


def test_command_uses_whitelist_and_resume(tmp_path: Path) -> None:
    settings = Settings(
        claude_model="claude-opus-5", claude_fallback_model="claude-sonnet-5", claude_effort="high"
    )
    command = build_command(settings, tmp_path / "mcp.json", "abc", resume=True)
    assert (
        command[command.index("--allowed-tools") + 1 : command.index("--allowed-tools") + 3] == ALLOWED_TOOLS
    )
    assert "Bash" in command[command.index("--disallowed-tools") :]
    assert command[command.index("--resume") + 1] == "abc"
    assert command[command.index("--fallback-model") + 1] == "claude-sonnet-5"
    assert command[command.index("--effort") + 1] == "high"
    voice = build_command(settings, tmp_path / "mcp.json", "abc", resume=True, voice=True)
    assert voice[voice.index("--effort") + 1] == "low"
    assert "-p" in command and "stream-json" in command


def test_tool_result_helpers() -> None:
    payload = {
        "summary": "Skonwertowano 1 plik",
        "result": {},
        "output_files": [{"file_id": "f1", "name": "a.png", "mime": "image/png", "size_bytes": 10}],
    }
    block = {
        "type": "tool_result",
        "content": [{"type": "text", "text": json.dumps(payload)}, {"type": "image"}],
    }
    summary, files = parse_tool_result(block)
    assert summary == "Skonwertowano 1 plik"
    assert files == [{"id": "f1", "name": "a.png", "mime": "image/png", "size": 10}]
    assert parse_tool_result({"is_error": True, "content": "Błąd: brak pliku"}) == ("brak pliku", [])
    assert strip_images(block["content"])[1] == {"type": "text", "text": "[podgląd obrazu]"}
    assert tool_display_name("mcp__nexus__ocr_documents") == "ocr_documents"
    assert "limit użycia" in friendly_error("Claude AI usage limit reached|1760000000")


@pytest.mark.parametrize("name", registry.names())
def test_tool_names_are_valid_for_mcp(name: str) -> None:
    assert re.fullmatch(r"[a-z][a-z0-9_]{1,63}", name)
