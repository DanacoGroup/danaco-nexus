"""Przestrzeń plików konta: katalogi użytkownika, filtrowanie, wyszukiwanie, porządkowanie.

Jedna przestrzeń zamiast osobnych światów „chmura” i „baza wiedzy”: pliki wgrane przez
użytkownika i wytworzone przez agenta leżą obok siebie, a układ wyznacza sam użytkownik.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from test_api import HEADERS, client, set_password, settings  # noqa: F401
from test_izolacja_kont import KLIENT_HASLO, zaloguj, zaloz_konto  # noqa: F401

from nexus.config import Settings


def przygotuj(klient: TestClient, ustawienia: Settings, email: str = "pliki@example.com") -> None:
    set_password(ustawienia)
    zaloz_konto(ustawienia, email)
    zaloguj(klient, email, KLIENT_HASLO)


def wyslij(klient: TestClient, nazwa: str, tresc: bytes, mime: str) -> str:
    odpowiedz = klient.post(
        "/api/files", files={"file": (nazwa, io.BytesIO(tresc), mime)}, headers=HEADERS
    )
    assert odpowiedz.status_code == 201, odpowiedz.text
    return odpowiedz.json()["id"]


def test_katalogi_uzytkownika(client: TestClient, settings: Settings) -> None:  # noqa: F811
    """Użytkownik zakłada własne katalogi i projekty, nazywa je i przypina."""
    przygotuj(client, settings)
    assert client.get("/api/pliki/katalogi").json() == []

    utworzony = client.post(
        "/api/pliki/katalogi",
        json={"nazwa": "  Faktury   2026 ", "rodzaj": "projekt", "kolor": "iris"},
        headers=HEADERS,
    )
    assert utworzony.status_code == 201, utworzony.text
    katalog = utworzony.json()
    assert katalog["nazwa"] == "Faktury 2026", "nadmiarowe spacje mają zniknąć"
    assert katalog["rodzaj"] == "projekt" and katalog["plikow"] == 0

    zmiana = client.patch(
        f"/api/pliki/katalogi/{katalog['id']}",
        json={"nazwa": "Faktury", "przypiety": True},
        headers=HEADERS,
    )
    assert zmiana.status_code == 200, zmiana.text
    assert zmiana.json()["nazwa"] == "Faktury" and zmiana.json()["przypiety"] is True

    odrzucony = client.post(
        "/api/pliki/katalogi", json={"nazwa": "Coś", "rodzaj": "bzdura"}, headers=HEADERS
    )
    assert odrzucony.status_code == 422


def test_filtrowanie_i_wyszukiwanie(client: TestClient, settings: Settings) -> None:  # noqa: F811
    przygotuj(client, settings, "filtr@example.com")
    wyslij(client, "umowa-najmu.pdf", b"%PDF-1.4", "application/pdf")
    wyslij(client, "wakacje.jpg", b"\xff\xd8\xff", "image/jpeg")
    wyslij(client, "spotkanie.mp3", b"ID3", "audio/mpeg")

    wszystkie = client.get("/api/pliki").json()
    assert len(wszystkie["pliki"]) == 3
    assert wszystkie["przestrzen"]["limit"] > 0 and wszystkie["przestrzen"]["opis_limitu"]

    zdjecia = client.get("/api/pliki", params={"rodzaj": "zdjecia"}).json()["pliki"]
    assert [plik["name"] for plik in zdjecia] == ["wakacje.jpg"]

    nagrania = client.get("/api/pliki", params={"rodzaj": "nagrania"}).json()["pliki"]
    assert [plik["name"] for plik in nagrania] == ["spotkanie.mp3"]

    znalezione = client.get("/api/pliki", params={"q": "najmu"}).json()["pliki"]
    assert [plik["name"] for plik in znalezione] == ["umowa-najmu.pdf"]


def test_porzadkowanie_plikow(client: TestClient, settings: Settings) -> None:  # noqa: F811
    """Plik trafia do katalogu, wraca z niego, a własny tytuł nie rusza nazwy z dysku."""
    przygotuj(client, settings, "porzadek@example.com")
    plik = wyslij(client, "scan_0012.pdf", b"%PDF", "application/pdf")
    katalog = client.post("/api/pliki/katalogi", json={"nazwa": "Umowy"}, headers=HEADERS).json()

    przypisanie = client.post(
        "/api/pliki/przypisz", json={"pliki": [plik], "katalog_id": katalog["id"]}, headers=HEADERS
    )
    assert przypisanie.status_code == 200 and przypisanie.json()["przeniesione"] == 1
    w_katalogu = client.get("/api/pliki", params={"katalog_id": katalog["id"]}).json()["pliki"]
    assert [pozycja["id"] for pozycja in w_katalogu] == [plik]
    assert client.get("/api/pliki", params={"bez_katalogu": True}).json()["pliki"] == []

    nazwany = client.patch(f"/api/pliki/{plik}", json={"tytul": "Umowa najmu 2026"}, headers=HEADERS)
    assert nazwany.status_code == 200
    assert nazwany.json()["tytul"] == "Umowa najmu 2026"
    assert nazwany.json()["name"] == "scan_0012.pdf", "nazwa na dysku zostaje bez zmian"
    # Szukanie działa po własnym tytule, nie tylko po nazwie pliku.
    assert len(client.get("/api/pliki", params={"q": "Umowa najmu"}).json()["pliki"]) == 1


def test_usuniecie_katalogu_nie_kasuje_plikow(client: TestClient, settings: Settings) -> None:  # noqa: F811
    """Katalog jest etykietą — jego usunięcie nie może zabrać treści bez wyraźnej zgody."""
    przygotuj(client, settings, "katalog@example.com")
    plik = wyslij(client, "notatka.txt", b"tresc", "text/plain")
    katalog = client.post("/api/pliki/katalogi", json={"nazwa": "Tymczasowy"}, headers=HEADERS).json()
    client.post("/api/pliki/przypisz", json={"pliki": [plik], "katalog_id": katalog["id"]}, headers=HEADERS)

    usuniecie = client.delete(f"/api/pliki/katalogi/{katalog['id']}", headers=HEADERS)
    assert usuniecie.status_code == 200 and usuniecie.json()["usuniete_pliki"] == 0
    zostale = client.get("/api/pliki").json()["pliki"]
    assert [pozycja["id"] for pozycja in zostale] == [plik]
    assert zostale[0]["katalog_id"] is None


def test_usuniecie_katalogu_z_plikami_na_zadanie(client: TestClient, settings: Settings) -> None:  # noqa: F811
    przygotuj(client, settings, "zplikami@example.com")
    plik = wyslij(client, "stare.txt", b"tresc", "text/plain")
    katalog = client.post("/api/pliki/katalogi", json={"nazwa": "Do kosza"}, headers=HEADERS).json()
    client.post("/api/pliki/przypisz", json={"pliki": [plik], "katalog_id": katalog["id"]}, headers=HEADERS)

    usuniecie = client.delete(
        f"/api/pliki/katalogi/{katalog['id']}", params={"z_plikami": True}, headers=HEADERS
    )
    assert usuniecie.status_code == 200 and usuniecie.json()["usuniete_pliki"] == 1
    assert client.get("/api/pliki").json()["pliki"] == []


def test_przestrzen_plikow_nie_przecieka_miedzy_kontami(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    przygotuj(client, settings, "pierwszy-plik@example.com")
    plik = wyslij(client, "prywatne.txt", b"tresc", "text/plain")
    katalog = client.post("/api/pliki/katalogi", json={"nazwa": "Moje"}, headers=HEADERS).json()

    zaloz_konto(settings, "drugi-plik@example.com")
    client.post("/api/auth/logout", headers=HEADERS)
    zaloguj(client, "drugi-plik@example.com", KLIENT_HASLO)

    assert client.get("/api/pliki").json()["pliki"] == []
    assert client.get("/api/pliki/katalogi").json() == []
    assert client.get("/api/pliki", params={"katalog_id": katalog["id"]}).status_code == 404
    assert client.patch(f"/api/pliki/{plik}", json={"tytul": "Przejęte"}, headers=HEADERS).status_code == 404
    assert client.delete(f"/api/pliki/{plik}", headers=HEADERS).status_code == 404
