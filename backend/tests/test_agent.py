"""Testy pętli agenta z atrapą klienta Claude (bez połączenia z API)."""

from __future__ import annotations

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import render_text_image, write_image
from sqlalchemy import select

from nexus.agent.runner import AgentRunner, sanitize_assistant_content
from nexus.config import Settings
from nexus.db import Conversation, Database, Message, Run, RunEvent, StoredFile, ToolCall
from nexus.storage import FileStorage
from nexus.tools import registry


class Block:
    def __init__(self, **data: Any) -> None:
        self._data = data
        for key, value in data.items():
            setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


def reply(blocks: list[dict[str, Any]], stop_reason: str) -> SimpleNamespace:
    usage = SimpleNamespace(
        input_tokens=100, output_tokens=20, cache_read_input_tokens=50, cache_creation_input_tokens=0
    )
    return SimpleNamespace(
        content=[Block(**block) for block in blocks],
        stop_reason=stop_reason,
        usage=usage,
        model="claude-opus-5",
    )


class FakeStream:
    def __init__(self, message: SimpleNamespace) -> None:
        self._message = message

    async def __aenter__(self) -> FakeStream:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def __aiter__(self) -> Any:
        return self._events()

    async def _events(self) -> Any:
        for block in self._message.content:
            yield SimpleNamespace(type="content_block_start", content_block=block)
            if block.type == "text":
                for part in (block.text[: len(block.text) // 2], block.text[len(block.text) // 2 :]):
                    yield SimpleNamespace(type="text", text=part)
            elif block.type == "thinking":
                yield SimpleNamespace(type="thinking", thinking=block.thinking)
            await asyncio.sleep(0)

    async def get_final_message(self) -> SimpleNamespace:
        return self._message


class FakeClient:
    """Atrapa ``AsyncAnthropic``: odtwarza kolejne zaplanowane odpowiedzi."""

    def __init__(self, replies: list[SimpleNamespace]) -> None:
        self._replies = list(replies)
        self.requests: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **params: Any) -> FakeStream:
        self.requests.append(json.loads(json.dumps(params, default=str)))
        return FakeStream(self._replies.pop(0))


async def prepare(
    tmp_path: Path, text: str
) -> tuple[Settings, Database, FileStorage, uuid.UUID, uuid.UUID, str]:
    settings = Settings(
        data_dir=tmp_path / "data", database_url=f"sqlite+aiosqlite:///{(tmp_path / 'agent.db').as_posix()}"
    )
    database = Database(settings.database_url)
    await database.create_schema()
    storage = FileStorage(settings.files_dir)
    image_path = write_image(tmp_path / "skan.jpg", render_text_image(dpi=60))
    with image_path.open("rb") as handle:
        file_id, relative, size, digest = storage.save_stream(handle, "skan.jpg", 10**8)
    conversation = Conversation(id=uuid.uuid4())
    run = Run(conversation_id=conversation.id)
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
        session.add(run)
        await session.flush()
        session.add(
            Message(
                conversation_id=conversation.id,
                run_id=run.id,
                role="user",
                kind="user",
                content=[{"type": "text", "text": f"{text}\nfile_id: {file_id}"}],
                meta={"text": text, "file_ids": [str(file_id)]},
            )
        )
    return settings, database, storage, conversation.id, run.id, str(file_id)


async def execute(
    settings: Settings, database: Database, storage: FileStorage, client: FakeClient, run_id: uuid.UUID
) -> None:
    with ThreadPoolExecutor(max_workers=2) as executor:
        runner = AgentRunner(settings, database, storage, client, registry, executor)  # type: ignore[arg-type]
        await runner.execute(run_id)


async def test_agent_runs_tool_and_answers(tmp_path: Path) -> None:
    settings, database, storage, conversation_id, run_id, file_id = await prepare(tmp_path, "Sprawdź skan")
    client = FakeClient(
        [
            reply(
                [
                    {"type": "thinking", "thinking": "Sprawdzę jakość.", "signature": "sig-1"},
                    {"type": "text", "text": "Sprawdzam plik."},
                    {
                        "type": "tool_use",
                        "id": "tu_1",
                        "name": "inspect_files",
                        "input": {"file_ids": [file_id]},
                    },
                ],
                "tool_use",
            ),
            reply([{"type": "text", "text": "Skan jest czytelny."}], "end_turn"),
        ]
    )
    await execute(settings, database, storage, client, run_id)

    async with database.session() as session:
        run = await session.get(Run, run_id)
        messages = (
            await session.scalars(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
            )
        ).all()
        calls = (await session.scalars(select(ToolCall))).all()
        events = [
            event.type
            for event in (
                await session.scalars(select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.id))
            ).all()
        ]
    await database.close()

    assert run is not None and run.status == "done", run.error if run else None
    assert run.usage["requests"] == 2
    assert [message.kind for message in messages] == ["user", "assistant", "tool_results", "assistant"]
    assert messages[1].content[0] == {
        "type": "thinking",
        "thinking": "Sprawdzę jakość.",
        "signature": "sig-1",
    }
    result_block = messages[2].content[0]
    assert result_block["type"] == "tool_result" and result_block["tool_use_id"] == "tu_1"
    assert "is_error" not in result_block
    assert any(part["type"] == "image" for part in result_block["content"])
    assert calls[0].name == "inspect_files" and calls[0].status == "done"
    assert events[0] == "run.started" and events[-1] == "run.completed"
    assert {"tool.pending", "tool.started", "tool.finished", "text.delta", "thinking.delta"} <= set(events)

    first, second = client.requests
    assert first["model"] == "claude-opus-5"
    assert first["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert first["fallbacks"] == "default" and first["betas"] == ["server-side-fallback-2026-07-01"]
    assert first["cache_control"] == {"type": "ephemeral"}
    assert [tool["name"] for tool in first["tools"]] == sorted(tool["name"] for tool in first["tools"])
    assert second["messages"][-1]["content"][0]["tool_use_id"] == "tu_1"


async def test_invalid_tool_input_returns_error_result(tmp_path: Path) -> None:
    settings, database, storage, conversation_id, run_id, _ = await prepare(tmp_path, "Podziel PDF")
    client = FakeClient(
        [
            reply(
                [{"type": "tool_use", "id": "tu_x", "name": "pdf_split", "input": {"file_id": "abc"}}],
                "tool_use",
            ),
            reply([{"type": "tool_use", "id": "tu_y", "name": "nieistniejace", "input": {}}], "tool_use"),
            reply([{"type": "text", "text": "Nie mogę podzielić pliku."}], "end_turn"),
        ]
    )
    await execute(settings, database, storage, client, run_id)
    async with database.session() as session:
        results = (
            await session.scalars(select(Message).where(Message.kind == "tool_results").order_by(Message.id))
        ).all()
        run = await session.get(Run, run_id)
    await database.close()
    assert run is not None and run.status == "done"
    assert all(message.content[0]["is_error"] for message in results)
    assert "Nieprawidłowe parametry" in results[0].content[0]["content"][0]["text"]
    assert "Nieznane narzędzie" in results[1].content[0]["content"][0]["text"]


async def test_truncated_tool_use_keeps_history_valid(tmp_path: Path) -> None:
    settings, database, storage, conversation_id, run_id, file_id = await prepare(tmp_path, "OCR")
    client = FakeClient(
        [
            reply(
                [
                    {"type": "text", "text": "Uruchamiam"},
                    {"type": "tool_use", "id": "tu_cut", "name": "ocr_documents", "input": {}},
                ],
                "max_tokens",
            ),
        ]
    )
    await execute(settings, database, storage, client, run_id)
    async with database.session() as session:
        messages = (
            await session.scalars(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
            )
        ).all()
        events = [event.type for event in (await session.scalars(select(RunEvent))).all()]
    await database.close()
    assert [message.kind for message in messages] == ["user", "assistant", "tool_results"]
    assert messages[2].content[0]["tool_use_id"] == "tu_cut"
    assert "notice" in events


async def test_api_error_marks_run_failed(tmp_path: Path) -> None:
    import anthropic
    import httpx

    settings, database, storage, _, run_id, _ = await prepare(tmp_path, "Cokolwiek")

    class FailingClient(FakeClient):
        def _stream(self, **params: Any) -> FakeStream:
            response = httpx.Response(
                401, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
            )
            raise anthropic.AuthenticationError("invalid x-api-key", response=response, body=None)

    await execute(settings, database, storage, FailingClient([]), run_id)
    async with database.session() as session:
        run = await session.get(Run, run_id)
    await database.close()
    assert run is not None and run.status == "failed"
    assert "ANTHROPIC_API_KEY" in run.error


def test_fallback_blocks_are_sanitized() -> None:
    content = [
        {"type": "thinking", "thinking": "a", "signature": "s"},
        {"type": "text", "text": "Częściowa odpowiedź"},
        {"type": "tool_use", "id": "t", "name": "x", "input": {}},
        {"type": "fallback", "from": {"model": "claude-opus-5"}, "to": {"model": "claude-opus-4-8"}},
        {"type": "thinking", "thinking": "b", "signature": "s2"},
        {"type": "text", "text": "Dalej"},
    ]
    assert [block["type"] for block in sanitize_assistant_content(content)] == [
        "text",
        "fallback",
        "thinking",
        "text",
    ]
    plain = [{"type": "text", "text": "x"}]
    assert sanitize_assistant_content(plain) is plain


@pytest.mark.parametrize("name", registry.names())
def test_tool_names_are_valid_for_api(name: str) -> None:
    import re

    assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name)
