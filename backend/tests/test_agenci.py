"""Testy modułu agenci: flagi CLI trybów rozmów, podagenci, powiadomienia, kolejka na SQLite,
moduł Kod (projekty, bezpieczne ścieżki, git) i API modułu Agenci."""

from __future__ import annotations

import io
import json
import shutil
import sys
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import HEADERS, client, login, set_password, settings  # noqa: F401 - fikstury pytest

from nexus.agent import runner
from nexus.agent.przestrzenie import WorkspaceError, safe_path, valid_project_name
from nexus.agent.runner import (
    CODE_BASH_DENY,
    RunOptions,
    agent_output,
    build_command,
    builtin_summary,
    conversation_mode,
    rate_limit_warning,
    run_timeout_minutes,
    truncate_content,
)
from nexus.api.modules.agenci import summarize_events
from nexus.api.modules.kod import name_from_url, parse_status, validate_clone_url
from nexus.config import Settings
from nexus.db import Conversation, Database, Message, Run
from nexus.events import FINISHED_CHANNEL, EventBus
from nexus.worker import claim_next

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="Brak programu git")


def _option(command: list[str], name: str) -> str:
    return command[command.index(name) + 1]


def _values(command: list[str], name: str) -> list[str]:
    start = command.index(name) + 1
    end = next((i for i in range(start, len(command)) if command[i].startswith("--")), len(command))
    return command[start:end]


# --- polecenie CLI ------------------------------------------------------------------------------


def test_chat_command_enables_subagents_and_web(tmp_path: Path) -> None:
    command = build_command(Settings(), tmp_path / "mcp.json", "abc", resume=False)
    assert _option(command, "--tools") == "ToolSearch,Agent,WebSearch,WebFetch"
    allowed, disallowed = _values(command, "--allowed-tools"), _values(command, "--disallowed-tools")
    assert {"Agent", "WebSearch", "WebFetch"} <= set(allowed)
    assert not {"Agent", "Task", "WebSearch", "WebFetch"} & set(disallowed)
    assert {"Bash", "Read", "Write", "Skill"} <= set(disallowed)
    assert _option(command, "--permission-prompts") == "none"
    agents = json.loads(_option(command, "--agents"))
    assert set(agents) == {"pomocnik"} and "Agent" not in agents["pomocnik"]["tools"]
    assert "model" not in agents["pomocnik"]
    assert "--forward-subagent-text" in command
    assert "--permission-mode" not in command and "--append-system-prompt" not in command
    assert "Podagenci" in _option(command, "--system-prompt")


def test_disabled_capabilities_are_blocked(tmp_path: Path) -> None:
    config = Settings(claude_subagents=False, claude_web_tools=False)
    command = build_command(config, tmp_path / "mcp.json", "abc", resume=False)
    assert _option(command, "--tools") == "ToolSearch"
    assert {"Agent", "Task", "WebSearch", "WebFetch"} <= set(_values(command, "--disallowed-tools"))
    assert "--agents" not in command and "--forward-subagent-text" not in command
    assert "Podagenci" not in _option(command, "--system-prompt")


def test_subagent_model_setting(tmp_path: Path) -> None:
    command = build_command(
        Settings(claude_subagent_model="claude-sonnet-5"), tmp_path / "m.json", "a", False
    )
    assert json.loads(_option(command, "--agents"))["pomocnik"]["model"] == "claude-sonnet-5"


def test_code_mode_command(tmp_path: Path) -> None:
    project = tmp_path / "sklep"
    options = RunOptions(mode="code", workspace=project)
    command = build_command(Settings(), tmp_path / "mcp.json", "abc", resume=True, options=options)
    tools = _option(command, "--tools").split(",")
    assert {"Read", "Write", "Edit", "Glob", "Grep", "Bash"} <= set(tools)
    assert "Bash" in _values(command, "--allowed-tools")
    assert "Read" not in _values(command, "--allowed-tools")  # odczyt tylko w katalogach roboczych
    disallowed = _values(command, "--disallowed-tools")
    assert "Bash" not in disallowed and set(CODE_BASH_DENY) <= set(disallowed)
    assert "Bash(sudo *)" in disallowed and "Bash(git push *)" in disallowed
    assert _option(command, "--permission-mode") == "acceptEdits"
    assert _option(command, "--add-dir") == str(project)
    assert "sesja programistyczna" in _option(command, "--append-system-prompt")
    helper = json.loads(_option(command, "--agents"))["pomocnik"]
    assert "Bash" in helper["tools"] and "sesja programistyczna" in helper["prompt"]


def test_mode_instruction_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "research.md").write_text("Instrukcja badań.\n", encoding="utf-8")
    monkeypatch.setattr(runner, "MODES_DIR", tmp_path)
    command = build_command(
        Settings(), tmp_path / "mcp.json", "abc", resume=False, options=RunOptions(mode="research")
    )
    assert _option(command, "--append-system-prompt") == "Instrukcja badań."
    # Tryb bez pliku instrukcji (np. strona przed scaleniem modułu) działa jak czat.
    plain = build_command(Settings(), tmp_path / "mcp.json", "abc", False, options=RunOptions(mode="strona"))
    assert "--append-system-prompt" not in plain


def test_modes_and_timeouts() -> None:
    config = Settings(run_timeout_minutes=120, run_timeout_research_minutes=360)
    assert conversation_mode({"mode": "research"}) == "research"
    assert conversation_mode({"mode": "nieznany"}) == conversation_mode(None) == "chat"
    assert run_timeout_minutes(config, "research") == 360
    assert run_timeout_minutes(config, "chat") == run_timeout_minutes(config, "code") == 120


def test_result_helpers() -> None:
    assert agent_output("Wynik.\nagentId: abc\n<usage>total_tokens: 5\ntool_uses: 1</usage>") == "Wynik."
    assert builtin_summary("Read", {"content": "1\ta\n2\tb"}) == "Odczytano 2 wierszy"
    assert builtin_summary("Glob", {"content": "No files found"}) == "Brak wyników"
    assert builtin_summary("Bash", {"content": "\n".join(str(i) for i in range(20))}).splitlines()[-1] == "19"
    assert (
        builtin_summary("Bash", {"is_error": True, "content": "<tool_use_error>zakaz</tool_use_error>"})
        == "zakaz"
    )
    long = [{"type": "text", "text": "x" * 10_000}, {"type": "image", "source": {}}]
    shortened = truncate_content(long, 100)
    assert len(shortened[0]["text"]) == 101 and shortened[1]["type"] == "text"
    assert (
        rate_limit_warning({"status": "allowed", "unifiedWindows": {"seven_day": {"utilization": 0.5}}}) == ""
    )
    warning = rate_limit_warning(
        {"status": "allowed", "unifiedWindows": {"seven_day": {"utilization": 0.93}}}
    )
    assert "93% limitu tygodniowego" in warning
    assert "limit" in rate_limit_warning({"status": "rejected"})


# --- powiadomienia i kolejka ------------------------------------------------------------------


class _FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))


async def test_notify_finished_publishes_json() -> None:
    bus = EventBus("redis://nie-uzywany")
    fake = _FakeRedis()
    bus._client = fake  # noqa: SLF001 - podmiana klienta Redis w teście
    run_id, conversation_id = uuid.uuid4(), uuid.uuid4()
    await bus.notify_finished(run_id, conversation_id, "done", "Raport")
    ((channel, message),) = fake.published
    assert channel == FINISHED_CHANNEL == "nexus:run-finished"
    assert json.loads(message) == {
        "run_id": str(run_id),
        "conversation_id": str(conversation_id),
        "status": "done",
        "title": "Raport",
    }
    # Bez Redisa powiadomienie jest pomijane bez błędu.
    await EventBus("").notify_finished(run_id, conversation_id, "done", "")


async def test_sqlite_queue_keeps_conversation_order(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'q.db').as_posix()}")
    await database.create_schema()
    ids: list[list[uuid.UUID]] = []
    for runs in (2, 1):
        conversation = Conversation(id=uuid.uuid4())
        created = []
        async with database.session() as session:
            session.add(conversation)
            await session.flush()
            for _ in range(runs):
                run = Run(id=uuid.uuid4(), conversation_id=conversation.id)
                session.add(run)
                await session.flush()
                session.add(
                    Message(
                        conversation_id=conversation.id, run_id=run.id, role="user", kind="user", content=[]
                    )
                )
                created.append(run.id)
        ids.append(created)
    claimed = [await claim_next(database, "w1") for _ in range(3)]
    assert claimed == [ids[0][0], ids[1][0], None]
    await database.close()


# --- moduł Kod: ścieżki i adresy ---------------------------------------------------------------


def test_safe_paths(tmp_path: Path) -> None:
    root = tmp_path / "projekt"
    (root / "src").mkdir(parents=True)
    assert safe_path(root, "src") == (root / "src").resolve()
    assert safe_path(root, "") == root.resolve()
    for bad in ("../x", "src/../../x", "/etc/passwd", "C:/Windows", "a\x00b"):
        with pytest.raises(WorkspaceError):
            safe_path(root, bad)
    assert valid_project_name("sklep-2.0") and not valid_project_name("..") and not valid_project_name(".git")
    assert not valid_project_name("a/b") and not valid_project_name("")


@pytest.mark.skipif(sys.platform == "win32", reason="dowiązania symboliczne POSIX")
def test_symlink_outside_project_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "projekt"
    root.mkdir()
    (root / "wyjscie").symlink_to(tmp_path)
    with pytest.raises(WorkspaceError):
        safe_path(root, "wyjscie/sekret")


def test_clone_url_validation() -> None:
    assert validate_clone_url("https://github.com/org/repo.git") == "https://github.com/org/repo.git"
    for bad in (
        "http://github.com/org/repo",
        "git@github.com:org/repo.git",
        "https://token@github.com/org/repo",
        "https://user:haslo@github.com/org/repo",
        "https://github.com/org/repo?token=1",
        "https://127.0.0.1/repo",
        "https://localhost/repo",
        "file:///etc",
    ):
        with pytest.raises(WorkspaceError):
            validate_clone_url(bad)
    assert name_from_url("https://github.com/org/moj-projekt.git") == "moj-projekt"


def test_parse_git_status() -> None:
    output = b"## main...origin/main\x00 M src/a.py\x00?? nowy plik.txt\x00R  b.py\x00a.py\x00"
    branch, changes = parse_status(output)
    assert branch == "main"
    assert changes == [
        {"path": "src/a.py", "index": " ", "worktree": "M"},
        {"path": "nowy plik.txt", "index": "?", "worktree": "?"},
        {"path": "b.py", "index": "R", "worktree": " ", "from": "a.py"},
    ]


def test_summarize_events_builds_agent_tree() -> None:
    events = [
        ("tool.started", {"tool_use_id": "a1", "name": "podagent", "agent": {"description": "Część 1"}}),
        ("tool.started", {"tool_use_id": "a2", "name": "podagent", "agent": {"description": "Część 2"}}),
        ("tool.started", {"tool_use_id": "t1", "name": "ocr_documents", "parent_tool_use_id": "a1"}),
        ("tool.progress", {"tool_use_id": "a2", "text": "Pracuje w tle…"}),
        ("tool.finished", {"tool_use_id": "t1", "status": "done"}),
        ("tool.finished", {"tool_use_id": "a1", "status": "done", "summary": "OK", "duration_ms": 1500}),
        ("tool.started", {"tool_use_id": "t2", "name": "inspect_files"}),
    ]
    summary = summarize_events(events)
    first, second = summary["agents"]
    assert first["status"] == "done" and first["summary"] == "OK" and first["tools_total"] == 1
    assert second["status"] == "running" and second["progress"] == "Pracuje w tle…"
    assert summary["tools_total"] == 2 and summary["tools_running"] == 1
    assert summary["activity"] == "inspect_files"


# --- API modułów Kod i Agenci -----------------------------------------------------------------


@pytest.fixture
def logged(client: TestClient, settings: Settings) -> TestClient:  # noqa: F811
    set_password(settings)
    login(client)
    return client


@requires_git
def test_kod_project_lifecycle(logged: TestClient, settings: Settings) -> None:  # noqa: F811
    created = logged.post("/api/kod/projekty", json={"name": "sklep"}, headers=HEADERS)
    assert created.status_code == 201, created.text
    assert created.json()["git"] is True and created.json()["branch"] == "main"
    assert logged.post("/api/kod/projekty", json={"name": "sklep"}, headers=HEADERS).status_code == 409
    assert [item["name"] for item in logged.get("/api/kod/projekty").json()] == ["sklep"]

    root = settings.kod_dir / "sklep"
    (root / "src").mkdir()
    (root / "src" / "app.py").write_bytes("print('Zażółć')\n".encode())
    (root / "README.md").write_bytes(b"# sklep\nOpis\n")
    tree = logged.get("/api/kod/projekty/sklep/drzewo").json()
    assert [(e["name"], e["type"]) for e in tree["entries"]] == [("src", "dir"), ("README.md", "file")]
    assert (
        logged.get("/api/kod/projekty/sklep/drzewo", params={"sciezka": "src"}).json()["entries"][0]["path"]
        == "src/app.py"
    )
    preview = logged.get("/api/kod/projekty/sklep/plik", params={"sciezka": "src/app.py"}).json()
    assert preview["text"] == "print('Zażółć')\n" and not preview["binary"]
    assert logged.get("/api/kod/projekty/sklep/plik", params={"sciezka": "../x"}).status_code == 400
    assert logged.get("/api/kod/projekty/sklep/plik", params={"sciezka": "/etc/hosts"}).status_code == 400

    status_payload = logged.get("/api/kod/projekty/sklep/git/status").json()
    changes = {item["path"]: item["worktree"] for item in status_payload["changes"]}
    assert status_payload["branch"] == "main" and changes == {"README.md": "M", "src/app.py": "?"}
    diff = logged.get("/api/kod/projekty/sklep/git/diff").json()["diff"]
    assert "+Opis" in diff
    new_file = logged.get("/api/kod/projekty/sklep/git/diff", params={"sciezka": "src/app.py"}).json()["diff"]
    assert "+print('Zażółć')" in new_file
    (log_entry,) = logged.get("/api/kod/projekty/sklep/git/log").json()
    assert log_entry["subject"] == "Początek projektu" and log_entry["author"] == settings.kod_git_name
    shown = logged.get(f"/api/kod/projekty/sklep/git/commit/{log_entry['hash']}").json()["diff"]
    assert "+# sklep" in shown
    assert logged.get("/api/kod/projekty/sklep/git/commit/HEAD;ls").status_code in (400, 404)

    archive = logged.get("/api/kod/projekty/sklep/zip")
    assert archive.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(archive.content)).namelist()
    assert "sklep/src/app.py" in names and not any("/.git/" in name for name in names)

    conversation = logged.post("/api/kod/projekty/sklep/rozmowy", json={}, headers=HEADERS)
    assert conversation.status_code == 201 and conversation.json()["title"] == "Kod: sklep"
    listed = logged.get("/api/kod/projekty/sklep/rozmowy").json()
    assert [item["id"] for item in listed] == [conversation.json()["id"]]

    sent = logged.post(
        f"/api/conversations/{conversation.json()['id']}/messages",
        json={"text": "Dodaj test"},
        headers=HEADERS,
    )
    assert sent.status_code == 202
    # Trwające zadanie w projekcie blokuje usunięcie.
    assert logged.delete("/api/kod/projekty/sklep", headers=HEADERS).status_code == 409
    logged.post(f"/api/runs/{sent.json()['run_id']}/cancel", headers=HEADERS)
    assert logged.delete("/api/kod/projekty/sklep", headers=HEADERS).status_code == 200
    assert not root.exists()


def test_kod_rejects_bad_input(logged: TestClient) -> None:
    for payload in ({"name": "../x"}, {"name": ""}, {"repo_url": "http://example.com/r.git"}):
        assert logged.post("/api/kod/projekty", json=payload, headers=HEADERS).status_code == 422
    assert logged.get("/api/kod/projekty/brak/drzewo").status_code == 404
    assert logged.get("/api/kod/projekty/..%2F..%2Fetc/drzewo").status_code == 404


def test_kod_requires_login(client: TestClient) -> None:  # noqa: F811
    assert client.get("/api/kod/projekty").status_code == 401
    assert client.get("/api/agenci/zadania").status_code == 401


def test_agenci_background_task(logged: TestClient) -> None:
    empty = logged.get("/api/agenci/zadania").json()
    assert empty["active"] == [] and empty["config"]["concurrency"] >= 1
    # Stan limitów kont silnika nie należy do odpowiedzi dla użytkownika.
    assert "limits" not in empty
    created = logged.post(
        "/api/agenci/zadania",
        json={"text": "Zbadaj rynek hoteli w Gdańsku", "mode": "research"},
        headers=HEADERS,
    )
    assert created.status_code == 202, created.text
    tasks = logged.get("/api/agenci/zadania").json()
    (task,) = tasks["active"]
    assert task["id"] == created.json()["run_id"] and task["mode"] == "research"
    assert task["status"] == "queued" and task["title"] == "Zbadaj rynek hoteli w Gdańsku"
    assert tasks["config"]["queued"] == 1
    conversation = logged.get(f"/api/conversations/{created.json()['conversation_id']}").json()
    assert conversation["active_run"]["id"] == task["id"]
    code = logged.post("/api/agenci/zadania", json={"text": "x", "mode": "code"}, headers=HEADERS)
    assert code.status_code == 422
