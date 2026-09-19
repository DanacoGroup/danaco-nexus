"""Testy API: logowanie, ochrona CSRF, pliki, rozmowy, kolejka zadań i strumień zdarzeń."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexus.api.app import create_app
from nexus.api.auth import set_admin_credentials
from nexus.config import Settings
from nexus.db import Base, Database

PASSWORD = "bardzo-tajne-haslo-2026"
HEADERS = {"X-Nexus-Request": "1"}


def _reset_postgres(url: str) -> None:
    async def run() -> None:
        database = Database(url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await database.close()

    asyncio.run(run())


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Ustawienia testowe: SQLite albo PostgreSQL (gdy ustawiono NEXUS_TEST_POSTGRES_URL)."""
    postgres = os.environ.get("NEXUS_TEST_POSTGRES_URL", "")
    if postgres:
        _reset_postgres(postgres)
    return Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=postgres or f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        cookie_secure=False,
        login_attempts_per_15_min=3,
        qdrant_url="http://127.0.0.1:1",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def set_password(settings: Settings) -> None:
    async def run() -> None:
        database = Database(settings.database_url)
        await database.create_schema()
        await set_admin_credentials(database, "admin", PASSWORD)
        await database.close()

    asyncio.run(run())


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200, response.text


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_requires_configured_password(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "x"}, headers=HEADERS)
    assert response.status_code == 503
    assert "set-password" in response.json()["detail"]


def test_login_flow_and_throttling(client: TestClient, settings: Settings) -> None:
    set_password(settings)
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD}).status_code == 403
    for _ in range(3):
        bad = client.post("/api/auth/login", json={"username": "admin", "password": "zle"}, headers=HEADERS)
        assert bad.status_code == 401
    blocked = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    )
    assert blocked.status_code == 429


def test_session_cookie_and_csrf(client: TestClient, settings: Settings) -> None:
    set_password(settings)
    login(client)
    cookie = client.cookies.get("nexus_session")
    assert cookie and len(cookie) > 30
    assert client.get("/api/auth/me").json() == {"username": "admin", "cloud_url": ""}
    assert client.post("/api/conversations", json={}).status_code == 403
    assert client.post("/api/conversations", json={}, headers=HEADERS).status_code == 201
    client.post("/api/auth/logout", headers=HEADERS)
    assert client.get("/api/auth/me").status_code == 401


def test_conversation_message_run_and_events(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    set_password(settings)
    login(client)
    conversation = client.post("/api/conversations", json={}, headers=HEADERS).json()
    upload = client.post(
        "/api/files",
        files={"file": ("Umowa najmu – skan.pdf", b"%PDF-1.4\n%test\n", "application/pdf")},
        headers=HEADERS,
    )
    assert upload.status_code == 201, upload.text
    file_info = upload.json()
    assert file_info["name"] == "Umowa najmu – skan.pdf"

    sent = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"text": "Wykonaj OCR tego skanu", "file_ids": [file_info["id"]]},
        headers=HEADERS,
    )
    assert sent.status_code == 202, sent.text
    run_id = sent.json()["run_id"]

    busy = client.post(
        f"/api/conversations/{conversation['id']}/messages", json={"text": "Drugie"}, headers=HEADERS
    )
    assert busy.status_code == 409

    detail = client.get(f"/api/conversations/{conversation['id']}").json()
    assert detail["title"] == "Wykonaj OCR tego skanu"
    assert detail["active_run"] == {"id": run_id, "status": "queued"}
    assert detail["turns"][0]["files"][0]["id"] == file_info["id"]
    listed = client.get("/api/conversations").json()
    assert listed[0]["active"] is True

    assert client.post(f"/api/runs/{run_id}/cancel", headers=HEADERS).json() == {"status": "cancelled"}
    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        body = "".join(stream.iter_text())
    assert "event: run.cancelled" in body

    download = client.get(f"/api/files/{file_info['id']}/download")
    assert download.status_code == 200
    assert "filename*=UTF-8''Umowa%20najmu%20%E2%80%93%20skan.pdf" in download.headers["content-disposition"]
    assert download.headers["content-type"] == "application/octet-stream"

    stored = list((settings.files_dir).rglob("*.pdf"))
    assert len(stored) == 1
    assert client.delete(f"/api/conversations/{conversation['id']}", headers=HEADERS).json() == {"ok": True}
    assert not stored[0].exists()
    assert client.get(f"/api/conversations/{conversation['id']}").status_code == 404


def test_upload_limit(client: TestClient, settings: Settings) -> None:
    set_password(settings)
    login(client)
    client.app.state.settings.upload_limit_mb = 1  # type: ignore[attr-defined]
    response = client.post(
        "/api/files", files={"file": ("duzy.bin", b"0" * (1024 * 1024 + 10))}, headers=HEADERS
    )
    assert response.status_code == 413
    assert not any(settings.files_dir.rglob("*.bin"))


def test_security_headers(client: TestClient) -> None:
    headers = client.get("/api/health").headers
    assert headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in headers["content-security-policy"]
