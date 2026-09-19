"""Testy modułu API rozszerzenia przeglądarki."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexus import __version__
from nexus.api.app import create_app
from nexus.api.auth import set_admin_credentials
from nexus.config import Settings
from nexus.db import Database

PASSWORD = "bardzo-tajne-haslo-2026"
HEADERS = {"X-Nexus-Request": "1"}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        cookie_secure=False,
        cookie_domain="",
        public_url="",
        chmura_public_url="",
        redis_url="",
        voice_warm_up=False,
        voice_stt_model_dir=tmp_path / "brak-modelu",
        voice_tts_dir=tmp_path / "brak-glosow",
        voice_google_key_file=tmp_path / "brak-klucza-google",
        qdrant_url="http://127.0.0.1:1",
        rozszerzenie_wersja_minimalna="0.1.0",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _device_token(client: TestClient, settings: Settings) -> str:
    async def run() -> None:
        database = Database(settings.database_url)
        await set_admin_credentials(database, "admin", PASSWORD)
        await database.close()

    asyncio.run(run())
    login = client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS)
    assert login.status_code == 200
    created = client.post(
        "/api/urzadzenia", json={"name": "Chrome – biuro", "kind": "rozszerzenie"}, headers=HEADERS
    )
    assert created.status_code == 201
    client.cookies.clear()
    return created.json()["token"]


def test_configuration_requires_key(client: TestClient) -> None:
    assert client.get("/api/rozszerzenie/konfiguracja").status_code == 401
    bad = client.get("/api/rozszerzenie/konfiguracja", headers={"Authorization": "Bearer nxd_zly"})
    assert bad.status_code == 401


def test_configuration_with_device_key(client: TestClient, settings: Settings) -> None:
    token = _device_token(client, settings)
    response = client.get("/api/rozszerzenie/konfiguracja", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["wersja"] == __version__
    assert data["panel"] == "/?widok=panel"
    assert data["urzadzenie"]["name"] == "Chrome – biuro"
    assert data["urzadzenie"]["kind"] == "rozszerzenie"
    assert data["rozszerzenie"] == {"wersja_minimalna": "0.1.0"}
    # CORS pozostaje zamknięty – rozszerzenie korzysta z uprawnień hosta, nie z nagłówków CORS.
    preflight = client.get(
        "/api/rozszerzenie/konfiguracja",
        headers={"Authorization": f"Bearer {token}", "Origin": "chrome-extension://abcdefghijklmnop"},
    )
    assert "access-control-allow-origin" not in preflight.headers
