"""Agenci zdefiniowani przez użytkownika: tworzenie, uruchamianie, rozdział kont.

Moduł Agenci pokazywał wyłącznie zadania w tle — nie dało się w nim utworzyć żadnego
agenta, mimo nazwy. Testy pilnują, że własny agent naprawdę powstaje, że jego instrukcja
trafia do zlecenia i że konto nie widzi cudzych agentów.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from test_api import HEADERS, PASSWORD, client, set_password, settings  # noqa: F401
from test_izolacja_kont import KLIENT_HASLO, zaloguj, zaloz_konto  # noqa: F401

from nexus.config import Settings

AGENT = {
    "nazwa": "Redaktor",
    "opis": "Poprawia teksty przed wysłaniem.",
    "instrukcja": "Poprawiasz styl i interpunkcję. Nie zmieniasz sensu. Oddajesz sam tekst.",
    "tryb": "chat",
}


def zaloguj_admina(klient: TestClient) -> None:
    assert klient.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    ).status_code == 200


def test_agent_powstaje_i_jest_na_liscie(client: TestClient, settings: Settings) -> None:  # noqa: F811
    set_password(settings)
    zaloguj_admina(client)

    utworzony = client.post("/api/agenci/wlasni", json=AGENT, headers=HEADERS)
    assert utworzony.status_code == 201, utworzony.text
    assert utworzony.json()["nazwa"] == "Redaktor"

    lista = client.get("/api/agenci/wlasni").json()
    assert [pozycja["nazwa"] for pozycja in lista] == ["Redaktor"]
    assert lista[0]["instrukcja"].startswith("Poprawiasz styl")


def test_uruchomienie_dokleja_instrukcje_agenta(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Zlecenie ma nieść rolę agenta, inaczej zapisanie go niczego by nie dawało."""
    set_password(settings)
    zaloguj_admina(client)
    agent_id = client.post("/api/agenci/wlasni", json=AGENT, headers=HEADERS).json()["id"]

    wynik = client.post(
        f"/api/agenci/wlasni/{agent_id}/uruchom",
        json={"tekst": "Popraw ten akapit o jesieni."},
        headers=HEADERS,
    )
    assert wynik.status_code == 202, wynik.text
    rozmowa = client.get(f"/api/conversations/{wynik.json()['conversation_id']}").json()
    assert rozmowa["title"].startswith("Redaktor: ")

    tresc = " ".join(
        blok.get("text", "")
        for tura in rozmowa["turns"]
        if tura["type"] == "user"
        for blok in ([{"text": tura.get("text", "")}])
    )
    assert "Pracujesz jako „Redaktor”" in tresc
    assert "Poprawiasz styl" in tresc
    assert "Popraw ten akapit o jesieni." in tresc

    # Licznik uruchomień porządkuje listę — najczęściej używani na górze.
    assert client.get("/api/agenci/wlasni").json()[0]["uruchomienia"] == 1


def test_agenci_nie_przeciekaja_miedzy_kontami(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    set_password(settings)
    zaloz_konto(settings, "obcy@example.com")
    zaloguj_admina(client)
    agent_id = client.post("/api/agenci/wlasni", json=AGENT, headers=HEADERS).json()["id"]

    client.post("/api/auth/logout", headers=HEADERS)
    zaloguj(client, "obcy@example.com", KLIENT_HASLO)
    assert client.get("/api/agenci/wlasni").json() == []
    # Cudzy agent nie różni się od nieistniejącego.
    assert client.delete(f"/api/agenci/wlasni/{agent_id}", headers=HEADERS).status_code == 404
    assert client.post(
        f"/api/agenci/wlasni/{agent_id}/uruchom", json={"tekst": "cokolwiek"}, headers=HEADERS
    ).status_code == 404


def test_tryb_kodu_wymaga_istniejacego_projektu(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    set_password(settings)
    zaloguj_admina(client)
    odmowa = client.post(
        "/api/agenci/wlasni",
        json={**AGENT, "tryb": "code", "projekt": "nie-ma-takiego"},
        headers=HEADERS,
    )
    assert odmowa.status_code == 422
    assert "projekt" in odmowa.json()["detail"].lower()
