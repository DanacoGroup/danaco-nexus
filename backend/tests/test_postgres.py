"""Testy na PostgreSQL: kolejka zadań, odzyskiwanie przerwanych zadań, pełny przebieg
procesu roboczego. Wymagają zmiennej NEXUS_TEST_POSTGRES_URL (pusta baza testowa)."""

from __future__ import annotations

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, text, update
from test_agent import FakeClient, reply

from nexus.agent.runner import AgentRunner
from nexus.config import Settings
from nexus.db import Base, Conversation, Database, Message, Run, RunEvent, utcnow
from nexus.storage import FileStorage
from nexus.tools import registry
from nexus.worker import claim_next, recover_stale_runs

POSTGRES_URL = os.environ.get("NEXUS_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="Brak NEXUS_TEST_POSTGRES_URL")


@pytest.fixture
async def database() -> Database:
    database = Database(POSTGRES_URL)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await database.create_schema()
    yield database
    await database.close()


async def add_conversation(database: Database, runs: int) -> tuple[uuid.UUID, list[uuid.UUID]]:
    conversation = Conversation(id=uuid.uuid4())
    run_ids = []
    async with database.session() as session:
        session.add(conversation)
        await session.flush()
        for _ in range(runs):
            run = Run(id=uuid.uuid4(), conversation_id=conversation.id)
            session.add(run)
            await session.flush()
            run_ids.append(run.id)
            session.add(
                Message(
                    conversation_id=conversation.id,
                    run_id=run.id,
                    role="user",
                    kind="user",
                    content=[{"type": "text", "text": "Cześć"}],
                    meta={"text": "Cześć"},
                )
            )
    return conversation.id, run_ids


async def test_queue_respects_order_and_conversation_exclusivity(database: Database) -> None:
    _, first_runs = await add_conversation(database, 2)
    _, second_runs = await add_conversation(database, 1)
    claimed = [await claim_next(database, "w1") for _ in range(4)]
    # Druga wiadomość pierwszej rozmowy czeka, aż pierwsza się zakończy.
    assert claimed == [first_runs[0], second_runs[0], None, None]
    async with database.session() as session:
        await session.execute(update(Run).where(Run.id == first_runs[0]).values(status="done"))
    assert await claim_next(database, "w1") == first_runs[1]


async def test_concurrent_workers_never_claim_the_same_run(database: Database) -> None:
    for _ in range(10):
        await add_conversation(database, 1)
    results = await asyncio.gather(*(claim_next(database, f"w{i}") for i in range(10)))
    claimed = [run_id for run_id in results if run_id is not None]
    assert len(claimed) == len(set(claimed)) == 10


async def test_stale_running_runs_are_recovered(database: Database) -> None:
    _, (run_id,) = await add_conversation(database, 1)
    async with database.session() as session:
        await session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(status="running", heartbeat_at=utcnow() - timedelta(minutes=10))
        )
    assert await recover_stale_runs(database) == 1
    async with database.session() as session:
        run = await session.get(Run, run_id)
    assert run is not None and run.status == "failed"


async def test_full_worker_run_on_postgres(database: Database, tmp_path: Path) -> None:
    conversation_id, (run_id,) = await add_conversation(database, 1)
    settings = Settings(data_dir=tmp_path / "data", database_url=POSTGRES_URL)
    client = FakeClient(
        [
            reply(
                [
                    {"type": "thinking", "thinking": "Plan: odpowiedz.", "signature": "s"},
                    {
                        "type": "tool_use",
                        "id": "tu_1",
                        "name": "search_documents",
                        "input": {"query": "umowa najmu"},
                    },
                ],
                "tool_use",
            ),
            reply([{"type": "text", "text": "Nie znalazłem dokumentów w bazie wiedzy."}], "end_turn"),
        ]
    )
    assert await claim_next(database, "test") == run_id
    with ThreadPoolExecutor(max_workers=2) as executor:
        runner = AgentRunner(
            settings,
            database,
            FileStorage(settings.files_dir),
            client,  # type: ignore[arg-type]
            registry,
            executor,
        )
        await runner.execute(run_id)
    async with database.session() as session:
        run = await session.get(Run, run_id)
        kinds = (
            await session.scalars(
                select(Message.kind).where(Message.conversation_id == conversation_id).order_by(Message.id)
            )
        ).all()
        final = await session.scalar(
            select(RunEvent.type).where(RunEvent.run_id == run_id).order_by(RunEvent.id.desc()).limit(1)
        )
        jsonb = await session.scalar(text("SELECT jsonb_typeof(content) FROM messages LIMIT 1"))
    assert run is not None and run.status == "done", run.error if run else ""
    assert list(kinds) == ["user", "assistant", "tool_results", "assistant"]
    assert final == "run.completed"
    assert jsonb == "array"
