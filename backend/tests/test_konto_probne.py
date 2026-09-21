"""Wejście bez rejestracji: „Wypróbuj” otwiera aplikację, nie pokaz obok niej.

Konto próbne jest zwykłym kontem klienta — ma własną przestrzeń, własne kredyty i własny
termin ważności. Testy pilnują trzech rzeczy: że gość dostaje aplikację, że nie widzi
cudzych danych i że z jednego łącza nie da się zakładać kont bez końca.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from test_api import HEADERS, client, set_password, settings  # noqa: F401
from test_izolacja_kont import KLIENT_HASLO, zaloguj, zaloz_konto  # noqa: F401

from nexus.config import Settings


def test_gosc_dostaje_wlasne_konto_i_kredyty(client: TestClient, settings: Settings) -> None:  # noqa: F811
    set_password(settings)
    odpowiedz = client.post("/api/auth/gosc", headers=HEADERS)
    assert odpowiedz.status_code == 200, odpowiedz.text
    assert odpowiedz.json()["gosc"] == "1"

    ja = client.get("/api/auth/me")
    assert ja.status_code == 200, ja.text
    assert ja.json()["gosc"] == "1"
    assert ja.json()["username"] != "admin", "gość nie może widzieć nazwy administratora instalacji"

    saldo = client.get("/api/platnosci/kredyty")
    assert saldo.status_code == 200, saldo.text
    assert saldo.json()["saldo"] > 0, "bez kredytów konto próbne nie zleciłoby ani jednego zadania"

    # To ma być aplikacja, a nie makieta: rozmowy działają od razu.
    utworzona = client.post("/api/conversations", json={"title": "Pierwsza sprawa"}, headers=HEADERS)
    assert utworzona.status_code == 201, utworzona.text


def test_gosc_nie_widzi_cudzych_rozmow(client: TestClient, settings: Settings) -> None:  # noqa: F811
    set_password(settings)
    zaloz_konto(settings, "klient@example.com")
    zaloguj(client, "klient@example.com", KLIENT_HASLO)
    client.post("/api/conversations", json={"title": "Sprawy klienta"}, headers=HEADERS)
    client.post("/api/auth/logout", headers=HEADERS)

    client.post("/api/auth/gosc", headers=HEADERS)
    assert client.get("/api/conversations").json() == []


def test_kazde_wejscie_to_osobne_konto(client: TestClient, settings: Settings) -> None:  # noqa: F811
    set_password(settings)
    client.post("/api/auth/gosc", headers=HEADERS)
    client.post("/api/conversations", json={"title": "Pierwszy gość"}, headers=HEADERS)
    client.post("/api/auth/logout", headers=HEADERS)

    client.post("/api/auth/gosc", headers=HEADERS)
    assert client.get("/api/conversations").json() == [], "drugi gość zaczyna od pustej historii"


def test_limit_kont_z_jednego_adresu(client: TestClient, settings: Settings) -> None:  # noqa: F811
    set_password(settings)
    for _ in range(settings.goscie_na_adres):
        assert client.post("/api/auth/gosc", headers=HEADERS).status_code == 200
    odmowa = client.post("/api/auth/gosc", headers=HEADERS)
    assert odmowa.status_code == 429


def test_gosc_wymaga_naglowka_aplikacji(client: TestClient, settings: Settings) -> None:  # noqa: F811
    set_password(settings)
    assert client.post("/api/auth/gosc").status_code == 403


@pytest.mark.parametrize("sciezka", ["/api/conversations", "/api/platnosci/kredyty"])
def test_bez_wejscia_brak_dostepu(client: TestClient, settings: Settings, sciezka: str) -> None:  # noqa: F811
    set_password(settings)
    assert client.get(sciezka).status_code == 401
