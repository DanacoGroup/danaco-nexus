"""Testy przebiegu agenta przez Claude Code CLI (atrapa ``tests/fake_claude.py``).

Atrapa wypisuje zdarzenia w formacie ``stream-json`` i uruchamia prawdziwy
serwer MCP narzędzi, więc testy obejmują całą ścieżkę: kolejkę → CLI → MCP
→ narzędzie → zapis plików, historii i zdarzeń.
"""

from __future__ import annotations

import asyncio
import json
import os
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
    RATE_LIMIT_KEY,
    AgentRunner,
    build_command,
    friendly_error,
    parse_tool_result,
    strip_images,
    tool_display_name,
)
from nexus.config import Settings
from nexus.db import Conversation, Database, Message, Run, RunEvent, Setting, StoredFile, ToolCall
from nexus.storage import FileStorage
from nexus.tools import registry
from nexus.worker import Worker

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
        # Tu sprawdzamy przebieg agenta, a nie piaskownicę: atrapa CLI jest skryptem
        # w katalogu tymczasowym i pisze obok siebie dziennik wywołań, więc w zamkniętej
        # przestrzeni montowań nie miałaby jak działać. Piaskownicę sprawdza
        # `test_piaskownica.py`, a jej wpięcie w polecenie — `test_polecenie_cli_*` niżej.
        agent_piaskownica=False,
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
    # Komunikat trafia do użytkownika, więc nie może wymieniać silnika ani stanu jego kont.
    [("auth", "Usługa jest chwilowo niedostępna"), ("crash", "Zadanie nie zostało ukończone")],
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
    przed = set(asyncio.all_tasks())
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
    # Bieg nie zostawia po sobie zadań w połowie sprzątania. Samo `cancel()` niczego nie
    # kończy, a obserwator anulowania jest wtedy w sesji bazy i ma jeszcze wycofać
    # transakcję. Niezebrane zadanie potrafiło zawiesić zamykanie pętli — a że pętlę
    # zamyka fikstura pytest-asyncio zaraz po teście, wieszało to cały przebieg testów
    # i bramkę wydania. Sprawdzamy więc nie tylko wynik biegu, ale i to, co po nim zostało.
    zostale = [zadanie for zadanie in asyncio.all_tasks() - przed if not zadanie.done()]
    assert zostale == [], f"bieg zostawił niedokończone zadania: {zostale}"


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
    przeciazenie = friendly_error("Claude AI usage limit reached|1760000000")
    assert "przeciążona" in przeciazenie and "claude" not in przeciazenie.lower()


@pytest.mark.parametrize("name", registry.names())
def test_tool_names_are_valid_for_mcp(name: str) -> None:
    assert re.fullmatch(r"[a-z][a-z0-9_]{1,63}", name)


# --- podagenci, tryby rozmów, wiele sesji ----------------------------------------------------


async def test_subagents_become_nested_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings, database, conversation_id, run_id, _file_id, log = await prepare(
        tmp_path, monkeypatch, "agents"
    )
    await AgentRunner(settings, database).execute(run_id)
    async with database.session() as session:
        run = await session.get(Run, run_id)
        tool_calls = {
            call.tool_use_id: call
            for call in (await session.scalars(select(ToolCall).where(ToolCall.run_id == run_id))).all()
        }
        results = (await session.scalars(select(StoredFile).where(StoredFile.origin == "result"))).all()
        messages = (
            await session.scalars(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
            )
        ).all()
        limits = await session.get(Setting, RATE_LIMIT_KEY)
    assert run is not None and run.status == "done", run.error if run else ""
    # Dwie tury CLI (podagent w tle) – zużycie jest sumą obu wyników.
    assert run.usage["input_tokens"] == 240 and run.usage["num_turns"] == 4
    assert set(tool_calls) == {"toolu_a1", "toolu_a2", "toolu_s1"}
    first, second, nested = tool_calls["toolu_a1"], tool_calls["toolu_a2"], tool_calls["toolu_s1"]
    assert first.name == second.name == "podagent" and nested.name == "convert_images"
    assert first.status == "done" and first.summary == "Plik PNG gotowy."
    assert second.status == "done" and second.summary == "Dokument to umowa o świadczenie usług."
    # Plik z narzędzia podagenta trafia też do wywołania podagenta (historia rozmowy).
    assert len(results) == 1 and first.output_file_ids == [str(results[0].id)] == nested.output_file_ids
    assert limits is not None and json.loads(limits.value)["status"] == "allowed"

    stored = [block for message in messages if message.kind == "assistant" for block in message.content]
    assert [block["name"] for block in stored if block["type"] == "tool_use"] == ["podagent", "podagent"]
    # Tekst podagentów nie trafia do historii rozmowy głównej.
    texts = " ".join(block.get("text", "") for block in stored)
    assert "Zamieniam skan" not in texts and "Gotowe – plik PNG" in texts

    evts = await events(database, run_id)
    started = [e.data for e in evts if e.type == "tool.started"]
    assert started[0]["agent"] == {
        "description": "Konwersja skanu",
        "subagent_type": "pomocnik",
        "background": False,
    }
    assert started[1]["agent"]["background"] is True
    assert next(d for d in started if d["tool_use_id"] == "toolu_s1")["parent_tool_use_id"] == "toolu_a1"
    nested_text = [e.data for e in evts if e.type == "text.delta" and e.data.get("parent_tool_use_id")]
    assert {d["parent_tool_use_id"] for d in nested_text} == {"toolu_a1", "toolu_a2"}
    progress = [e.data for e in evts if e.type == "tool.progress" and e.data.get("tool_use_id") == "toolu_a2"]
    assert [d["text"] for d in progress] == ["Pracuje w tle…", "Czytam dokument"]
    finished = {e.data["tool_use_id"]: e.data for e in evts if e.type == "tool.finished"}
    assert finished["toolu_s1"]["parent_tool_use_id"] == "toolu_a1"
    assert finished["toolu_a1"]["files"][0]["id"] == str(results[0].id)
    # Stan limitów kont silnika nie może dotrzeć do użytkownika żadnym zdarzeniem.
    notices = [e.data["text"] for e in evts if e.type == "notice"]
    assert not any("limitu" in tekst or "Claude" in tekst for tekst in notices)
    assert "ToolSearch" not in {d["name"] for d in started}

    (invocation,) = calls(log)
    args = invocation["args"]
    agents = json.loads(args[args.index("--agents") + 1])
    assert "Agent" not in agents["pomocnik"]["tools"]
    assert "mcp__nexus__convert_images" in agents["pomocnik"]["tools"]
    assert "--forward-subagent-text" in args
    assert args[args.index("--tools") + 1] == "ToolSearch,Agent,WebSearch,WebFetch"


async def test_code_mode_runs_in_project_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings, database, conversation_id, run_id, _file_id, log = await prepare(tmp_path, monkeypatch, "text")
    project = settings.kod_dir / "sklep"
    project.mkdir(parents=True)
    async with database.session() as session:
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(meta={"mode": "code", "workspace": "sklep"})
        )
    await AgentRunner(settings, database).execute(run_id)
    async with database.session() as session:
        run = await session.get(Run, run_id)
    assert run is not None and run.status == "done", run.error
    (invocation,) = calls(log)
    args = invocation["args"]
    assert Path(invocation["cwd"]).resolve() == project.resolve()
    assert invocation["git_author"] == settings.kod_git_name
    assert args[args.index("--permission-mode") + 1] == "acceptEdits"
    assert args[args.index("--add-dir") + 1] == str(project)
    assert "sesja programistyczna" in args[args.index("--append-system-prompt") + 1]
    assert "Bash" in args[args.index("--tools") + 1].split(",")

    # Usunięty projekt: zadanie kończy się czytelnym błędem.
    project.rmdir()
    second = await add_run(database, conversation_id, "Dalej")
    await AgentRunner(settings, database).execute(second)
    async with database.session() as session:
        failed = await session.get(Run, second)
    assert failed is not None and failed.status == "failed" and "sklep" in failed.error


async def test_worker_runs_sessions_in_parallel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings, database, _conversation_id, first_run, _file_id, _log = await prepare(
        tmp_path, monkeypatch, "sleep"
    )
    monkeypatch.setenv("FAKE_CLAUDE_SLEEP", "2")
    run_ids = [first_run]
    for index in range(3):
        conversation = Conversation(id=uuid.uuid4(), title=f"Sesja {index}")
        async with database.session() as session:
            session.add(conversation)
        run_ids.append(await add_run(database, conversation.id, "Zadanie w tle"))
    worker = Worker(settings.model_copy(update={"worker_concurrency": 4}), database)
    loop = asyncio.create_task(worker.run())
    try:
        for _ in range(300):
            async with database.session() as session:
                statuses = (await session.scalars(select(Run.status).where(Run.id.in_(run_ids)))).all()
            if all(value == "done" for value in statuses):
                break
            await asyncio.sleep(0.1)
    finally:
        worker.stop()
        await asyncio.wait_for(loop, 30)
    check = Database(settings.database_url)
    async with check.session() as session:
        runs = (await session.scalars(select(Run).where(Run.id.in_(run_ids)))).all()
    await check.close()
    assert [run.status for run in runs] == ["done"] * 4
    # Wszystkie cztery sesje trwały jednocześnie (każda ~2 s).
    assert max(run.started_at for run in runs) < min(run.finished_at for run in runs)


async def test_worker_stop_interrupts_runs_after_grace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, database, _conversation_id, run_id, _file_id, _log = await prepare(
        tmp_path, monkeypatch, "hang"
    )
    worker = Worker(settings.model_copy(update={"worker_stop_grace_s": 0}), database)
    loop = asyncio.create_task(worker.run())
    for _ in range(100):
        if any(event.type == "text.delta" for event in await events(database, run_id)):
            break
        await asyncio.sleep(0.1)
    worker.stop()
    await asyncio.wait_for(loop, 30)
    check = Database(settings.database_url)
    async with check.session() as session:
        run = await session.get(Run, run_id)
        final = await session.scalar(
            select(RunEvent.type).where(RunEvent.run_id == run_id).order_by(RunEvent.id.desc()).limit(1)
        )
    await check.close()
    assert run is not None and run.status == "failed" and "przerwane" in run.error
    assert final == "run.failed"


# --- piaskownica w poleceniu CLI ----------------------------------------------------------


def test_polecenie_cli_jest_owiniete_w_piaskownice(tmp_path: Path) -> None:
    """Domyślnie proces CLI startuje w zamkniętej przestrzeni montowań, nie wprost."""
    from nexus.agent import piaskownica

    if not piaskownica.dostepna():
        pytest.skip("bwrap niedostępny")
    projekt = tmp_path / "projekt"
    projekt.mkdir()
    owiniete = piaskownica.polecenie(
        piaskownica.znajdz_bwrap(), ["claude", "-p"], cwd=projekt, zapis=(projekt,)
    )
    assert owiniete[0].endswith("bwrap")
    assert owiniete[-2:] == ["claude", "-p"]
    assert "--unshare-all" in owiniete
    assert str(projekt) in owiniete


def test_ustawienie_wylacza_piaskownice_w_przebiegu() -> None:
    """Wyłącznik jest świadomą decyzją operatora, nie stanem domyślnym."""
    from nexus.agent.runner import piaskownica_wlaczona

    assert piaskownica_wlaczona(Settings(agent_piaskownica=False)) is False


def test_serwer_mcp_dostaje_kod_z_tego_samego_miejsca_co_proces_roboczy() -> None:
    """Narzędzia i agent mają pochodzić z jednego kodu — także po wymianie wydania.

    Serwer MCP startuje w przestrzeni użytkownika, więc `python -m nexus.mcp_server`
    nie znajdzie tam pakietu przy bieżącym katalogu i sięgnąłby po instalację edytowalną
    z venv, czyli po stan roboczy repozytorium. `PYTHONPATH` przecina tę drogę.
    """
    from pathlib import Path

    import nexus as nexus_pakiet
    from nexus.agent.runner import mcp_config

    konfiguracja = mcp_config(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    serwer = next(iter(konfiguracja["mcpServers"].values()))
    oczekiwany = str(Path(nexus_pakiet.__file__).resolve().parents[1])

    assert serwer["env"]["PYTHONPATH"].split(os.pathsep)[0] == oczekiwany


def test_diagnostyka_widzi_zadania_stojace_w_kolejce(tmp_path: Path) -> None:
    """Instalacja bez procesu roboczego przyjmuje zadania i nigdy ich nie wykonuje.

    Jedynym śladem jest zaległość w kolejce — dlatego `doctor` pyta o nią wprost.
    """
    from datetime import timedelta

    from nexus.db import Conversation, Run, utcnow
    from nexus.doctor import KOLEJKA_ALARM_MIN, check_kolejka

    ustawienia = Settings(
        data_dir=tmp_path / "dane",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'kolejka.db').as_posix()}",
    )

    async def przygotuj(wiek_minut: int) -> None:
        baza = Database(ustawienia.database_url)
        await baza.create_schema()
        async with baza.session() as sesja:
            rozmowa = Conversation(title="Próba")
            sesja.add(rozmowa)
            await sesja.flush()
            sesja.add(
                Run(
                    conversation_id=rozmowa.id,
                    status="queued",
                    created_at=utcnow() - timedelta(minutes=wiek_minut),
                )
            )
        await baza.close()

    async def sprawdz() -> tuple[bool, str]:
        wynik = await check_kolejka(ustawienia)
        return wynik.ok, wynik.detail

    # Zadanie świeżo w kolejce to normalna praca, nie usterka.
    asyncio.run(przygotuj(0))
    assert asyncio.run(sprawdz())[0] is True

    asyncio.run(przygotuj(KOLEJKA_ALARM_MIN + 10))
    ok, szczegoly = asyncio.run(sprawdz())
    assert ok is False
    assert "proces roboczy" in szczegoly


def test_diagnostyka_nie_przewraca_sie_na_jednej_kontroli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Po to uruchamia się diagnostykę, żeby zobaczyć wszystko, co nie działa.

    Kontrola mowy wywoływała `ffmpeg`; brak programu wychodził jako `FileNotFoundError`
    i przerywał `doctor` w połowie — reszty kontroli nikt już nie zobaczył.
    """
    from nexus import doctor

    def wybuch() -> doctor.Check:
        raise FileNotFoundError(2, "No such file or directory", "ffmpeg")

    monkeypatch.setattr(doctor, "check_font", wybuch)

    wyniki = doctor.run_checks(Settings(database_url="sqlite+aiosqlite:///:memory:"))

    przerwane = [wynik for wynik in wyniki if wynik.name == "kontrola przerwana"]
    assert len(przerwane) == 1
    assert "ffmpeg" in przerwane[0].detail
    # Pozostałe kontrole i tak się wykonały.
    assert len(wyniki) > 5


def test_nieoczekiwany_blad_nie_pokazuje_wnetrza_serwera() -> None:
    """Na ekran idzie zdanie do przeczytania, treść wyjątku zostaje w dzienniku.

    Wyjątek bywa niesie ścieżkę na serwerze albo fragment zapytania do bazy — rzeczy,
    których użytkownik nie powinien widzieć, a które i tak nic mu nie mówią.
    """
    import inspect

    from nexus.agent import runner as modul_runnera
    from nexus.tworczy import zadania

    for zrodlo in (inspect.getsource(modul_runnera), inspect.getsource(zadania)):
        assert 'f"Błąd wewnętrzny: {error}"' not in zrodlo
        assert "Coś poszło nie tak po naszej stronie" in zrodlo


def test_polecenie_systemowe_zakazuje_rozmowy_o_rozliczeniach() -> None:
    """Liczba kredytów nie ma prawa wyjść do użytkownika — także ustami asystenta.

    Interfejs zasady pilnuje (moduł Płatności pokazuje pasek wykorzystania, nie liczby),
    ale polecenie systemowe uczyło dotąd modelu, że „podagenci kosztują użytkownika
    dodatkowe kredyty”. Żadne narzędzie nie podaje stanu konta, więc konkretnej liczby
    asystent nie wymyśli — ale samo pojęcie mogło trafić do odpowiedzi jako wymówka
    („zrobię prościej, żeby nie zużyć kredytów”). Zasada stoi teraz wprost.
    """
    from nexus.agent.prompt import AGENTS_SECTION, SYSTEM_PROMPT

    assert "Rozliczenia nie są tematem rozmowy." in SYSTEM_PROMPT
    assert "Nie podawaj stanu konta" in SYSTEM_PROMPT
    # Uzasadnienie doboru podagentów zostaje, ale bez odsyłania użytkownika do rachunku.
    assert "kredyty" not in AGENTS_SECTION
