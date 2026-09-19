"""Nexus Desktop: WebSocket komputerów i przekaźnik narzędzi pc_* (fałszywy komputer).

Domyślnie przekaźnik działa w pamięci procesu. Z ``NEXUS_TEST_REDIS_URL`` (np. prywatny
Valkey) te same testy przechodzą przez prawdziwy Redis.
"""

from __future__ import annotations

import base64
import io
import os
import threading
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from conftest import ToolHarness
from fastapi.testclient import TestClient
from PIL import Image
from starlette.websockets import WebSocketDisconnect
from test_api import HEADERS, login, set_password

from nexus.api.app import create_app
from nexus.config import Settings
from nexus.pulpit import MEMORY_BROKER, PcError, choose_computer, online_computers
from nexus.tools.base import ToolCancelled, ToolError, registry

REDIS_URL = os.environ.get("NEXUS_TEST_REDIS_URL", "")
BROKERS = ["pamiec", pytest.param("redis", marks=pytest.mark.skipif(not REDIS_URL, reason="Brak Redisa"))]


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (40, 90, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(params=BROKERS)
def settings(request: pytest.FixtureRequest, tmp_path: Path) -> Settings:
    MEMORY_BROKER._online.clear()
    return Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        cookie_secure=False,
        cookie_domain="",
        public_url="",
        redis_url=REDIS_URL if request.param == "redis" else "",
        voice_warm_up=False,
        voice_stt_model_dir=tmp_path / "brak-modelu",
        voice_tts_dir=tmp_path / "brak-glosow",
        voice_google_key_file=tmp_path / "brak-klucza-google",
        qdrant_url="http://127.0.0.1:1",
        pulpit_timeout_s=5,
        pulpit_confirm_timeout_s=1,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Klient z zalogowaną przeglądarką (może wydawać klucze urządzeń)."""
    set_password(settings)
    with TestClient(create_app(settings)) as test_client:
        login(test_client)
        yield test_client


@pytest.fixture
def tools(settings: Settings, tmp_path: Path) -> ToolHarness:
    harness = ToolHarness(tmp_path / "narzedzia")
    harness.settings = settings
    return harness


def _device_key(client: TestClient, kind: str = "desktop", name: str = "Laptop") -> str:
    created = client.post("/api/urzadzenia", json={"name": name, "kind": kind}, headers=HEADERS)
    assert created.status_code == 201, created.text
    return created.json()["token"]


def _run_tool(tools: ToolHarness, name: str, args: dict[str, Any]) -> Future:
    tool = registry.get(name)
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(tool.handler, tools.context(), tool.parse(args))
    executor.shutdown(wait=False)
    return future


def _wait_online(client: TestClient, count: int = 1) -> list[dict[str, Any]]:
    for _ in range(50):
        found = client.get("/api/pulpit/komputery").json()
        if len(found) >= count:
            return found
        time.sleep(0.05)
    raise AssertionError("Komputer nie pojawił się w rejestrze.")


def test_tool_without_computer_explains_problem(tools: ToolHarness) -> None:
    with pytest.raises(ToolError, match="Żaden komputer"):
        registry.get("pc_info").handler(tools.context(), registry.get("pc_info").parse({}))


def test_relay_round_trip(client: TestClient, settings: Settings, tools: ToolHarness) -> None:
    token = _device_key(client)
    with client.websocket_connect("/api/pulpit/ws") as socket:
        socket.send_json({"type": "auth", "token": token, "host": "BIURO-PC", "version": "0.1.0"})
        ready = socket.receive_json()
        assert ready["type"] == "ready" and ready["device"]["name"] == "Laptop"
        listed = _wait_online(client)
        assert listed[0]["host"] == "BIURO-PC" and listed[0]["name"] == "Laptop"

        future = _run_tool(tools, "pc_info", {"top_processes": 5})
        request = socket.receive_json()
        assert request["type"] == "request" and request["tool"] == "pc_info"
        assert request["args"] == {"top_processes": 5}
        image = base64.b64encode(_png()).decode()
        socket.send_json(
            {
                "type": "response",
                "id": request["id"],
                "ok": True,
                "result": {"data": {"ram_gb": 16}, "text": "Windows 11", "images": [image]},
            }
        )
        result = future.result(timeout=10)
        assert result.data["data"] == {"ram_gb": 16} and result.data["host"] == "BIURO-PC"
        assert result.images == [_png()]

        # Błąd po stronie komputera trafia do modelu jako czytelny ToolError.
        future = _run_tool(
            tools, "pc_powershell", {"command": "Remove-Item C:\\x", "description": "Usuwa plik testowy"}
        )
        request = socket.receive_json()
        assert request["args"]["command"] == "Remove-Item C:\\x"
        socket.send_json(
            {"type": "response", "id": request["id"], "ok": False, "error": "Użytkownik odmówił."}
        )
        with pytest.raises(ToolError, match="Użytkownik odmówił"):
            future.result(timeout=10)

        # Ping odświeża rejestr i dostaje odpowiedź.
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}
    for _ in range(50):
        if not client.get("/api/pulpit/komputery").json():
            break
        time.sleep(0.05)
    assert client.get("/api/pulpit/komputery").json() == []


def test_upload_and_cancel(client: TestClient, settings: Settings, tools: ToolHarness) -> None:
    token = _device_key(client)
    with client.websocket_connect("/api/pulpit/ws", headers={"Authorization": f"Bearer {token}"}) as socket:
        assert socket.receive_json()["type"] == "ready"
        _wait_online(client)
        future = _run_tool(tools, "pc_read_file", {"path": "C:\\Users\\A\\umowa.txt", "upload": True})
        request = socket.receive_json()
        socket.send_json(
            {
                "type": "response",
                "id": request["id"],
                "ok": True,
                "result": {
                    "data": {"size": 5},
                    "file": {"name": "umowa.txt", "path": "C:\\Users\\A\\umowa.txt", "data": "VW1vd2E="},
                },
            }
        )
        result = future.result(timeout=10)
        assert len(result.files) == 1 and result.files[0].path.read_bytes() == b"Umowa"
        assert "file" not in result.data

        future = _run_tool(tools, "pc_screenshot", {})
        request = socket.receive_json()
        tools.cancel.set()
        cancel = socket.receive_json()
        assert cancel == {"type": "cancel", "id": request["id"]}
        with pytest.raises(ToolCancelled):
            future.result(timeout=10)


def test_timeout_when_computer_is_silent(client: TestClient, settings: Settings, tools: ToolHarness) -> None:
    settings.pulpit_timeout_s = 1
    token = _device_key(client)
    with client.websocket_connect("/api/pulpit/ws") as socket:
        socket.send_json({"type": "auth", "token": token})
        socket.receive_json()
        _wait_online(client)
        future = _run_tool(tools, "pc_info", {})
        socket.receive_json()
        with pytest.raises(ToolError, match="nie odpowiedział"):
            future.result(timeout=30)


def test_rejects_invalid_and_non_desktop_keys(client: TestClient, settings: Settings) -> None:
    phone = _device_key(client, kind="android", name="Telefon")
    for token in ("nxd_zly", phone, "brak-prefiksu"):
        with client.websocket_connect("/api/pulpit/ws") as socket:
            socket.send_json({"type": "auth", "token": token})
            message = socket.receive_json()
            assert message["type"] == "error"
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_json()
            assert closed.value.code == 4401
    client.cookies.clear()
    assert client.get("/api/pulpit/komputery").status_code == 401


def test_new_connection_replaces_previous(client: TestClient, settings: Settings) -> None:
    token = _device_key(client)
    with client.websocket_connect("/api/pulpit/ws") as first:
        first.send_json({"type": "auth", "token": token, "host": "A"})
        first.receive_json()
        with client.websocket_connect("/api/pulpit/ws") as second:
            second.send_json({"type": "auth", "token": token, "host": "B"})
            assert second.receive_json()["type"] == "ready"
            with pytest.raises(WebSocketDisconnect) as closed:
                first.receive_json()
            assert closed.value.code == 4409
            assert _wait_online(client)[0]["host"] == "B"


def test_choose_computer_and_stale_entries() -> None:
    computers = [
        {"id": "1", "name": "Laptop", "host": "LAP", "connected_at": 1},
        {"id": "2", "name": "Biuro", "host": "BIURO-PC", "connected_at": 2},
    ]
    assert choose_computer(computers, "")["id"] == "1"
    assert choose_computer(computers, "biuro-pc")["id"] == "2"
    with pytest.raises(PcError, match="Podłączone"):
        choose_computer(computers, "serwer")
    with pytest.raises(PcError, match="Żaden komputer"):
        choose_computer([], "")

    class Fixed:
        def online_sync(self) -> dict[str, str]:
            return {
                "a": '{"name": "stary", "seen": 0, "connected_at": 0}',
                "b": '{"name": "nowy", "seen": 1000, "connected_at": 5}',
                "c": "nie-json",
            }

    assert [c["name"] for c in online_computers(Fixed(), now=1010)] == ["nowy"]  # type: ignore[arg-type]


def test_tools_are_registered() -> None:
    names = set(registry.names())
    assert {"pc_info", "pc_find_files", "pc_read_file", "pc_powershell", "pc_screenshot"} <= names
    schema = registry.get("pc_powershell").definition()["input_schema"]
    assert set(schema["required"]) == {"command", "description"}


def test_threads_do_not_leak() -> None:
    # Pomocnicze wątki narzędzi kończą się razem z testami (brak wiszących subskrypcji).
    assert not MEMORY_BROKER._subscribers or all(
        not key.startswith("nexus:pc:resp:") for key in MEMORY_BROKER._subscribers
    )
    assert threading.active_count() < 50
