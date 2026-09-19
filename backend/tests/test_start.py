"""Testy modułu „start”: pobieranie instalatorów, Web Push, zadania w toku, tryb osadzony."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from nexus.api.app import create_app
from nexus.api.auth import set_admin_credentials
from nexus.api.modules.osadzanie import panel_csp
from nexus.config import Settings
from nexus.db import Database
from nexus.push_service import ensure_vapid_key, run_finished_message, send_to_all

PASSWORD = "bardzo-tajne-haslo-2026"
HEADERS = {"X-Nexus-Request": "1"}


class FakeSender:
    """Zastępuje pywebpush: zapamiętuje wysyłki, zwraca zadany kod HTTP dla adresu."""

    def __init__(self, statuses: dict[str, int] | None = None) -> None:
        self.statuses = statuses or {}
        self.sent: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, subscription: dict[str, Any], payload: str) -> int:
        self.sent.append((subscription["endpoint"], json.loads(payload)))
        return self.statuses.get(subscription["endpoint"], 201)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        cookie_secure=False,
        redis_url="",
        voice_warm_up=False,
        voice_stt_model_dir=tmp_path / "brak-modelu",
        voice_tts_dir=tmp_path / "brak-glosow",
        voice_google_key_file=tmp_path / "brak-klucza-google",
        qdrant_url="http://127.0.0.1:1",
    )


def _prepare(settings: Settings) -> None:
    async def run() -> None:
        database = Database(settings.database_url)
        await database.create_schema()
        await set_admin_credentials(database, "admin", PASSWORD)
        await database.close()

    asyncio.run(run())


@pytest.fixture
def sender() -> FakeSender:
    return FakeSender({"https://push.example.com/wygasla": 410})


@pytest.fixture
def client(settings: Settings, sender: FakeSender) -> Iterator[TestClient]:
    _prepare(settings)
    app = create_app(settings)
    app.state.push_sender = sender
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200, response.text


# --- pobieranie ---


def test_downloads_are_public_and_whitelisted(client: TestClient, settings: Settings) -> None:
    listing = client.get("/pobierz").json()
    assert {item["name"] for item in listing} == {
        "nexus-android.apk",
        "nexus-desktop-setup.exe",
        "nexus-rozszerzenie.zip",
    }
    assert not any(item["available"] for item in listing)
    assert client.get("/pobierz/nexus-android.apk").status_code == 404

    settings.downloads_dir.mkdir(parents=True)
    (settings.downloads_dir / "nexus-android.apk").write_bytes(b"PK\x03\x04apk")
    (settings.downloads_dir / "tajne.txt").write_text("nie do pobrania", encoding="utf-8")

    response = client.get("/pobierz/nexus-android.apk")
    assert response.status_code == 200
    assert response.content == b"PK\x03\x04apk"
    assert response.headers["content-type"] == "application/vnd.android.package-archive"
    assert response.headers["content-disposition"].startswith('attachment; filename="nexus-android.apk"')
    assert client.head("/pobierz/nexus-android.apk").status_code == 200

    apk = next(item for item in client.get("/pobierz").json() if item["name"] == "nexus-android.apk")
    assert apk["available"] is True and apk["size"] == 7 and len(apk["sha256"]) == 64

    assert client.get("/pobierz/tajne.txt").status_code == 404
    assert client.get("/pobierz/..%2Fnexus.db").status_code == 404
    assert client.get("/pobierz/%2E%2E/nexus.db").status_code in (404, 405)


# --- Web Push ---


def test_vapid_key_created_once_with_private_mode(tmp_path: Path) -> None:
    path = tmp_path / "app" / "vapid"
    public = ensure_vapid_key(path)
    raw = base64.urlsafe_b64decode(public + "=" * (-len(public) % 4))
    assert len(raw) == 65 and raw[0] == 4
    assert ensure_vapid_key(path) == public
    assert b"PRIVATE KEY" in path.read_bytes()
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_run_finished_message() -> None:
    done = run_finished_message(
        {"run_id": "r1", "conversation_id": "c1", "status": "done", "title": "Raport z faktur"}
    )
    assert done == {
        "title": "Zadanie zakończone",
        "body": "Raport z faktur",
        "url": "/c/c1",
        "tag": "run-c1",
        "run_id": "r1",
        "status": "done",
    }
    failed = run_finished_message({"run_id": "r2", "conversation_id": "c1", "status": "failed", "title": ""})
    assert (
        failed is not None and failed["title"] == "Zadanie nie powiodło się" and failed["body"] == "Rozmowa"
    )
    assert run_finished_message({"run_id": "r3", "conversation_id": "c1", "status": "cancelled"}) is None
    assert run_finished_message({"status": "done"}) is None


def test_push_subscriptions_and_delivery(client: TestClient, settings: Settings, sender: FakeSender) -> None:
    assert client.get("/api/push/klucz").status_code == 401
    _login(client)
    key = client.get("/api/push/klucz").json()
    assert key["available"] is True and key["subscriptions"] == 0
    assert key["public_key"] == ensure_vapid_key(settings.vapid_file)

    keys = {"p256dh": "B" + "a" * 86, "auth": "c" * 22}
    for endpoint in ("https://push.example.com/telefon", "https://push.example.com/wygasla"):
        created = client.post(
            "/api/push/subskrypcje",
            json={"endpoint": endpoint, "keys": keys, "name": "Telefon"},
            headers=HEADERS,
        )
        assert created.status_code == 201, created.text
    # Ponowna subskrypcja tego samego adresu nie tworzy duplikatu.
    client.post(
        "/api/push/subskrypcje",
        json={"endpoint": "https://push.example.com/telefon", "keys": keys},
        headers=HEADERS,
    )
    assert client.get("/api/push/klucz").json()["subscriptions"] == 2
    assert (
        client.post(
            "/api/push/subskrypcje",
            json={"endpoint": "http://niebezpieczny.pl/x", "keys": keys},
            headers=HEADERS,
        ).status_code
        == 422
    )

    report = client.post("/api/push/test", headers=HEADERS).json()
    assert report == {"sent": 1, "removed": 1, "failed": 0}
    assert {endpoint for endpoint, _ in sender.sent} == {
        "https://push.example.com/telefon",
        "https://push.example.com/wygasla",
    }
    assert sender.sent[0][1]["title"] == "Danaco Nexus"
    assert client.get("/api/push/klucz").json()["subscriptions"] == 1

    client.post("/api/push/wypisz", json={"endpoint": "https://push.example.com/telefon"}, headers=HEADERS)
    assert client.get("/api/push/klucz").json()["subscriptions"] == 0


def test_send_to_all_drops_subscription_after_repeated_failures(settings: Settings) -> None:
    from nexus.models.push import PushSubscription

    async def run() -> list[int]:
        database = Database(settings.database_url)
        await database.create_schema()
        async with database.session() as session:
            session.add(
                PushSubscription(
                    endpoint_hash="x" * 64, endpoint="https://push.example.com/blad", p256dh="p", auth="a"
                )
            )
        failing = FakeSender({"https://push.example.com/blad": 500})
        results = []
        for _ in range(5):
            report = await send_to_all(database, failing, {"title": "t"})
            results.append(report.removed)
        await database.close()
        return results

    assert asyncio.run(run()) == [0, 0, 0, 0, 1]


# --- zadania w toku ---


def test_active_runs_listing(client: TestClient) -> None:
    _login(client)
    assert client.get("/api/w-toku").json() == []
    conversation = client.post("/api/conversations", json={"title": "Porządki w PDF"}, headers=HEADERS).json()
    run_id = client.post(
        f"/api/conversations/{conversation['id']}/messages", json={"text": "Podziel ten PDF"}, headers=HEADERS
    ).json()["run_id"]
    listed = client.get("/api/w-toku").json()
    assert len(listed) == 1
    assert listed[0]["run_id"] == run_id
    assert listed[0]["conversation_id"] == conversation["id"]
    assert listed[0]["status"] == "queued" and listed[0]["mode"] == "chat" and listed[0]["tool"] == ""
    client.post(f"/api/runs/{run_id}/cancel", headers=HEADERS)
    assert client.get("/api/w-toku").json() == []


# --- tryb osadzony ---


def test_panel_view_may_be_framed(settings: Settings) -> None:
    settings.static_dir.mkdir(parents=True)
    (settings.static_dir / "index.html").write_text("<!doctype html><title>Nexus</title>", encoding="utf-8")
    with TestClient(create_app(settings)) as client:
        normal = client.get("/")
        assert normal.status_code == 200 and "Nexus" in normal.text
        assert "frame-ancestors 'none'" in normal.headers["content-security-policy"]
        assert normal.headers["x-frame-options"] == "DENY"
        panel = client.get("/?widok=panel")
        assert panel.status_code == 200 and "Nexus" in panel.text
        csp = panel.headers["content-security-policy"]
        assert "frame-ancestors * chrome-extension: moz-extension:" in csp and "'none'" not in csp
        assert panel.headers["x-frame-options"] == ""
        assert panel.headers["cache-control"] == "no-cache"


def test_panel_csp_helper() -> None:
    assert panel_csp("default-src 'self'; frame-ancestors 'none'; base-uri 'self'", "chrome-extension:") == (
        "default-src 'self'; frame-ancestors chrome-extension:; base-uri 'self'"
    )
    assert panel_csp("default-src 'self';", "*") == "default-src 'self'; frame-ancestors *"
