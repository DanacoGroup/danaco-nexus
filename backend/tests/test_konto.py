"""Ustawienia konta: profil, hasło, preferencje, sesje i eksport danych.

Moduł Ustawienia w aplikacji pokazywał wcześniej wyłącznie motyw i listę głosów, bo nic
innego nie miało po stronie serwera swojego punktu. Te testy pilnują, że ma: preferencje
przeżywają wylogowanie, obce klucze są odrzucane, a hasło konta próbnego pozostaje poza
zasięgiem (konto próbne go nie ma).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexus.api.app import create_app
from nexus.api.auth import set_admin_credentials
from nexus.config import Settings
from nexus.db import Database

HASLO = "haslo-administratora-2026"
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
        agent_piaskownica=False,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    async def przygotuj() -> None:
        database = Database(settings.database_url)
        await database.create_schema()
        await set_admin_credentials(database, "admin", HASLO)
        await database.close()

    asyncio.run(przygotuj())
    with TestClient(create_app(settings)) as test_client:
        response = test_client.post(
            "/api/auth/login", json={"username": "admin", "password": HASLO}, headers=HEADERS
        )
        assert response.status_code == 200, response.text
        yield test_client


def test_profil_administratora_nie_jest_kontem_klienta(client: TestClient) -> None:
    dane = client.get("/api/konto").json()
    assert dane["nazwa"] == "admin"
    assert dane["wlasne_konto"] is False
    # Profil i hasło właściciela instalacji zmienia się w panelu administratora, nie tutaj.
    assert client.patch("/api/konto", json={"name": "Inny"}, headers=HEADERS).status_code == 400
    odpowiedz = client.post(
        "/api/konto/haslo", json={"current_password": HASLO, "new_password": "x"}, headers=HEADERS
    )
    assert odpowiedz.status_code == 400


def test_preferencje_maja_wartosci_domyslne_i_zapisuja_sie(client: TestClient) -> None:
    domyslne = client.get("/api/konto/preferencje").json()
    assert domyslne["motyw"] == "dark"
    assert domyslne["wysylka"] == "enter"
    assert domyslne["ograniczony_ruch"] is False

    zapisane = client.put(
        "/api/konto/preferencje",
        json={"wysylka": "ctrl-enter", "ograniczony_ruch": True},
        headers=HEADERS,
    )
    assert zapisane.status_code == 200, zapisane.text
    assert zapisane.json()["wysylka"] == "ctrl-enter"

    # Zapis jest scaleniem, nie podmianą całości: motyw zostaje na swojej wartości.
    po_drugim = client.put("/api/konto/preferencje", json={"motyw": "light"}, headers=HEADERS).json()
    assert po_drugim == {**domyslne, "wysylka": "ctrl-enter", "ograniczony_ruch": True, "motyw": "light"}
    assert client.get("/api/konto/preferencje").json()["motyw"] == "light"


def test_preferencje_odrzucaja_obce_klucze_i_zle_typy(client: TestClient) -> None:
    obcy = client.put("/api/konto/preferencje", json={"cokolwiek": "1"}, headers=HEADERS)
    assert obcy.status_code == 422
    assert "Nieznane ustawienie" in obcy.text

    zly_typ = client.put("/api/konto/preferencje", json={"ograniczony_ruch": "tak"}, headers=HEADERS)
    assert zly_typ.status_code == 422

    poza_wykazem = client.put("/api/konto/preferencje", json={"motyw": "neonowy"}, headers=HEADERS)
    assert poza_wykazem.status_code == 422


def test_sesje_pokazuja_biezaca_przegladarke(client: TestClient) -> None:
    sesje = client.get("/api/konto/sesje").json()
    assert len(sesje) == 1
    assert sesje[0]["biezaca"] is True

    wynik = client.post("/api/konto/sesje/zakoncz-pozostale", headers=HEADERS).json()
    assert wynik["zakonczone"] == 0
    # Bieżąca sesja ma przeżyć wylogowanie pozostałych.
    assert client.get("/api/konto").status_code == 200


def test_eksport_zawiera_profil_preferencje_i_spis_rozmow(client: TestClient) -> None:
    dane = client.get("/api/konto/eksport").json()
    assert set(dane) == {"wygenerowano", "profil", "preferencje", "rozmowy"}
    assert dane["profil"]["nazwa"] == "admin"
    assert dane["preferencje"]["motyw"] == "dark"
    assert isinstance(dane["rozmowy"], list)


def test_ustawienia_wymagaja_zalogowania(settings: Settings) -> None:
    with TestClient(create_app(settings)) as anonim:
        assert anonim.get("/api/konto").status_code == 401
        assert anonim.get("/api/konto/preferencje").status_code == 401



def test_katalog_kitu_podaje_presety_z_polskimi_nazwami(client: TestClient) -> None:
    """Moduł Strony pokazuje gotowe układy — nazwy mają być czytelne, nie techniczne."""
    dane = client.get("/api/strony/kit").json()
    assert set(dane) == {"dostepny", "presety", "motywy", "szablony"}
    if not dane["dostepny"]:
        pytest.skip("Danaco Web Kit nie jest zainstalowany na tym serwerze.")
    assert dane["presety"], "zestaw jest zainstalowany, a lista presetów pusta"
    for pozycja in dane["presety"]:
        assert pozycja["nazwa"], pozycja
        # Nazwa techniczna zostaje w osobnym polu, żeby dało się ją podać agentowi.
        assert pozycja["preset"]
    # Kolekcja szablonów otwartych: tylko pozycje z gotową witryną — inne nie dają się
    # wstawić do szkicu bez budowania.
    for pozycja in dane["szablony"]:
        assert pozycja["id"] and pozycja["nazwa"]


def test_katalog_kitu_wymaga_zalogowania(settings: Settings) -> None:
    with TestClient(create_app(settings)) as anonim:
        assert anonim.get("/api/strony/kit").status_code == 401
