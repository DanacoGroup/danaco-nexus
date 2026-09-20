"""Testy piaskownicy „Wypróbuj teraz”: sesja gościa, limity, przebiegi i zabezpieczenia."""

from __future__ import annotations

import asyncio
import io
import json
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from nexus.api.app import create_app
from nexus.config import Settings
from nexus.demo import model as model_cli
from nexus.demo.gotowosc import NA_ZYWO, ODTWORZENIE
from nexus.demo.przebieg import Wykonanie, tryb_scenariusza, uruchom
from nexus.demo.scenariusze import SCENARIUSZE, Krok, Postep, Scenariusz, scenariusz
from nexus.demo.sesje import COOKIE_NAME, BladPiaskownicy, Limity, Piaskownica, sprawdz_plik

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
        claude_bin=str(tmp_path / "brak-claude"),
        claude_profile_dir=tmp_path / "brak-profilu",
        realesrgan_dir=tmp_path / "brak-realesrgan",
        whisper_python=str(tmp_path / "brak-whispera"),
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        # Odtworzenie w testach biegnie bez pauz udających czas pracy.
        test_client.app.state.demo_pauza = False
        yield test_client


def stan(client: TestClient) -> dict:
    response = client.get("/api/demo/stan")
    assert response.status_code == 200, response.text
    return response.json()


def czekaj(client: TestClient, przebieg_id: str, sekundy: float = 20.0) -> dict:
    """Odpytuje stan przebiegu aż do jego zakończenia."""
    koniec = time.monotonic() + sekundy
    while time.monotonic() < koniec:
        dane = client.get(f"/api/demo/przebiegi/{przebieg_id}", headers=HEADERS).json()
        if dane["stan"] != "trwa":
            return dane
        time.sleep(0.05)
    raise AssertionError("Przebieg nie zakończył się w czasie testu.")


def test_stan_zaklada_sesje_bez_logowania(client: TestClient) -> None:
    dane = stan(client)
    assert client.cookies.get(COOKIE_NAME)
    assert dane["sesja"]["wiadomosci_pozostalo"] == dane["limity"]["wiadomosci"]
    assert [pozycja["id"] for pozycja in dane["scenariusze"]] == [item.id for item in SCENARIUSZE]
    assert dane["gotowosc"]["model"] is False


def test_scenariusze_uzywaja_wylacznie_istniejacych_narzedzi() -> None:
    from nexus.tools import registry

    nazwy = set(registry.names())
    for pozycja in SCENARIUSZE:
        assert set(pozycja.narzedzia) <= nazwy, pozycja.id
        assert pozycja.nagranie.is_file(), pozycja.id
        for nazwa in pozycja.przyklady:
            assert (Path(pozycja.nagranie).parent.parent / nazwa).is_file(), nazwa


def test_zmiana_stanu_wymaga_naglowka_aplikacji(client: TestClient) -> None:
    stan(client)
    odpowiedz = client.post("/api/demo/scenariusze/faktura/uruchom", json={"pliki": []})
    assert odpowiedz.status_code == 403


def test_bez_sesji_nie_da_sie_uruchomic_scenariusza(client: TestClient) -> None:
    odpowiedz = client.post("/api/demo/scenariusze/faktura/uruchom", json={"pliki": []}, headers=HEADERS)
    assert odpowiedz.status_code == 401


def test_odtworzenie_nagrania_gdy_brakuje_modelu(client: TestClient) -> None:
    dane = stan(client)
    faktura = next(item for item in dane["scenariusze"] if item["id"] == "faktura")
    assert faktura["tryb"] == ODTWORZENIE
    assert "model" in faktura["braki"]
    start = client.post("/api/demo/scenariusze/faktura/uruchom", json={"pliki": []}, headers=HEADERS)
    assert start.status_code == 202, start.text
    przebieg = start.json()["przebieg"]
    assert przebieg["tryb"] == ODTWORZENIE
    koniec = czekaj(client, przebieg["id"])
    assert koniec["stan"] == "gotowe"
    assert "3 067,62" in koniec["odpowiedz"]
    assert [krok["stan"] for krok in koniec["kroki"]] == ["gotowe"] * 3
    assert all(krok["czas_ms"] > 0 for krok in koniec["kroki"])
    plik = koniec["pliki"][0]
    pobrane = client.get(plik["adres"], headers=HEADERS)
    assert pobrane.status_code == 200
    assert pobrane.content.startswith(b"%PDF-")


def test_limit_wiadomosci_konczy_pokaz(client: TestClient) -> None:
    dane = stan(client)
    limit = dane["limity"]["wiadomosci"]
    for numer in range(limit):
        odpowiedz = client.post(
            "/api/demo/scenariusze/wyszukiwanie/uruchom", json={"pliki": []}, headers=HEADERS
        )
        assert odpowiedz.status_code == 202, numer
        czekaj(client, odpowiedz.json()["przebieg"]["id"])
    wyczerpane = client.post(
        "/api/demo/scenariusze/wyszukiwanie/uruchom", json={"pliki": []}, headers=HEADERS
    )
    assert wyczerpane.status_code == 429
    assert "Limit wiadomości" in wyczerpane.json()["detail"]


def test_pytanie_bez_modelu_jest_odrzucane(client: TestClient) -> None:
    stan(client)
    odpowiedz = client.post("/api/demo/pytanie", json={"tekst": "Zrób mi notatkę"}, headers=HEADERS)
    assert odpowiedz.status_code == 503
    assert stan(client)["sesja"]["wiadomosci_pozostalo"] == Limity().wiadomosci


def _jpg(rozmiar: tuple[int, int] = (40, 30)) -> bytes:
    bufor = io.BytesIO()
    Image.new("RGB", rozmiar, (200, 120, 60)).save(bufor, format="JPEG")
    return bufor.getvalue()


def test_wgranie_pliku_sprawdza_typ_i_tresc(client: TestClient) -> None:
    stan(client)
    dobry = client.post(
        "/api/demo/pliki", files={"plik": ("skan.jpg", _jpg(), "image/jpeg")}, headers=HEADERS
    )
    assert dobry.status_code == 201, dobry.text
    assert dobry.json()["mime"] == "image/jpeg"
    obcy = client.post(
        "/api/demo/pliki", files={"plik": ("skrypt.sh", b"#!/bin/sh\nrm -rf /", "text/x-sh")}, headers=HEADERS
    )
    assert obcy.status_code == 415
    podszywka = client.post(
        "/api/demo/pliki", files={"plik": ("obraz.png", b"MZ\x90\x00 program", "image/png")}, headers=HEADERS
    )
    assert podszywka.status_code == 415


def test_walidacja_plikow_poza_api() -> None:
    limity = Limity()
    with pytest.raises(BladPiaskownicy) as za_duzy:
        sprawdz_plik("skan.jpg", b"\xff\xd8\xff" + b"0" * (limity.plik_mb * 1024 * 1024), limity)
    assert za_duzy.value.kod == 413
    with pytest.raises(BladPiaskownicy):
        sprawdz_plik("notatka.txt", b"\xff\xfe\x00tekst", limity)
    sprawdz_plik("notatka.txt", "zażółć gęślą jaźń".encode(), limity)


def test_nazwa_pliku_nie_wychodzi_poza_katalog_sesji(settings: Settings) -> None:
    box = Piaskownica(settings)
    sesja = box.utworz("10.0.0.1")
    plik = box.dodaj_plik(sesja, "../../etc/passwd.jpg", _jpg())
    assert plik.sciezka.parent == sesja.katalog / "pliki"
    assert plik.sciezka.resolve().is_relative_to(sesja.katalog.resolve())
    assert ".." not in plik.nazwa


def test_pliki_innej_sesji_sa_niewidoczne(settings: Settings) -> None:
    box = Piaskownica(settings)
    pierwsza = box.utworz("10.0.0.1")
    druga = box.utworz("10.0.0.2")
    plik = box.dodaj_plik(pierwsza, "skan.jpg", _jpg())
    with pytest.raises(BladPiaskownicy) as blad:
        druga.plik(plik.id)
    assert blad.value.kod == 404


def test_wygasla_sesja_traci_dane(settings: Settings) -> None:
    box = Piaskownica(settings, Limity(zycie_minut=0))
    sesja = box.utworz("10.0.0.3")
    box.dodaj_plik(sesja, "skan.jpg", _jpg())
    katalog = sesja.katalog
    assert katalog.is_dir()
    assert box.pobierz(sesja.token) is None
    assert not katalog.exists()


def test_limit_sesji_z_jednego_adresu(settings: Settings) -> None:
    box = Piaskownica(settings, Limity(sesje_z_adresu=2))
    box.utworz("10.0.0.4")
    box.utworz("10.0.0.4")
    with pytest.raises(BladPiaskownicy) as blad:
        box.utworz("10.0.0.4")
    assert blad.value.kod == 429


def test_tempo_zapytan(settings: Settings) -> None:
    box = Piaskownica(settings, Limity(zapytan_na_minute=2))
    box.tempo.sprawdz("10.0.0.5")
    box.tempo.sprawdz("10.0.0.5")
    with pytest.raises(BladPiaskownicy) as blad:
        box.tempo.sprawdz("10.0.0.5")
    assert blad.value.kod == 429


def test_zakonczenie_sesji_kasuje_katalog(client: TestClient, settings: Settings) -> None:
    stan(client)
    client.post("/api/demo/pliki", files={"plik": ("skan.jpg", _jpg(), "image/jpeg")}, headers=HEADERS)
    korzen = settings.work_dir / "demo"
    assert any(korzen.iterdir())
    odpowiedz = client.request("DELETE", "/api/demo/sesja", headers=HEADERS)
    assert odpowiedz.json() == {"ok": True}
    assert not any(korzen.iterdir())


def test_podglad_przykladu_tylko_z_listy_scenariusza(client: TestClient) -> None:
    stan(client)
    dobry = client.get("/api/demo/przyklady/faktura/faktura-skan.jpg")
    assert dobry.status_code == 200
    assert dobry.content.startswith(b"\xff\xd8\xff")
    obcy = client.get("/api/demo/przyklady/faktura/generuj.py")
    assert obcy.status_code == 404
    poza = client.get("/api/demo/przyklady/faktura/..%2F..%2Fconfig.py")
    assert poza.status_code == 404


def test_tryb_zalezy_od_brakow() -> None:
    faktura = scenariusz("faktura")
    assert faktura is not None
    assert tryb_scenariusza(faktura, []) == NA_ZYWO
    assert tryb_scenariusza(faktura, ["tesseract"]) == ODTWORZENIE


def test_postep_podaje_pliki_ostatniego_kroku() -> None:
    postep = Postep(wejscie=["a"])
    assert postep.ostatnie_pliki() == ["a"]
    postep.pliki.append(["b"])
    postep.pliki.append([])
    assert postep.ostatnie_pliki() == ["b"]
    postep.teksty.extend(["pierwszy", "drugi"])
    assert postep.tekst(1) == "drugi"
    assert postep.tekst(9) == ""


def test_odpowiedz_modelu_jest_czytana_z_koperty() -> None:
    assert model_cli.odczytaj_odpowiedz(json.dumps({"result": " Gotowe "})) == "Gotowe"
    with pytest.raises(model_cli.BladModelu):
        model_cli.odczytaj_odpowiedz(json.dumps({"is_error": True, "result": "limit"}))
    with pytest.raises(model_cli.BladModelu):
        model_cli.odczytaj_odpowiedz("nie-json")


def test_polecenie_modelu_nie_wlacza_narzedzi(settings: Settings) -> None:
    polecenie = model_cli.polecenie_cli(settings, "pytanie")
    assert "--tools" in polecenie and polecenie[polecenie.index("--tools") + 1] == ""
    assert "--no-session-persistence" in polecenie
    assert "--strict-mcp-config" in polecenie


async def test_przebieg_na_zywo_wykonuje_narzedzie_i_model(settings: Settings) -> None:
    """Scenariusz próbny: krok narzędzia (bez programów zewnętrznych) i krok modelu."""
    box = Piaskownica(settings)
    sesja = box.utworz("10.0.0.6")
    wejscie = box.dodaj_plik(sesja, "strona.jpg", _jpg((80, 60)), "przyklad").id
    probny = Scenariusz(
        id="probny",
        tytul="Próbny",
        opis="Test",
        wiadomosc="Zrób PDF",
        przyklady=("strona.jpg",),
        kroki=(
            Krok(
                "Złożenie w PDF",
                "convert_images",
                lambda postep: {
                    "file_ids": postep.wejscie,
                    "target_format": "pdf",
                    "combine_into_one_pdf": True,
                },
            ),
            Krok("Podsumowanie", polecenie=lambda postep: f"Podsumuj: {postep.tekst(0)}"),
        ),
        wymaga_modelu=True,
    )

    def uruchamiacz(polecenie: list[str], srodowisko: dict[str, str], katalog: Path) -> str:
        assert "--tools" in polecenie
        assert "ANTHROPIC_API_KEY" not in srodowisko
        return json.dumps({"result": "Zrobione: jeden plik PDF."})

    wykonanie = Wykonanie(settings=settings, piaskownica=box, uruchamiacz_modelu=uruchamiacz)
    przebieg = uruchom(wykonanie, sesja, probny, NA_ZYWO, [wejscie])
    assert przebieg.zadanie is not None
    await asyncio.wait_for(przebieg.zadanie, 60)
    assert przebieg.stan == "gotowe", przebieg.blad
    assert przebieg.odpowiedz == "Zrobione: jeden plik PDF."
    assert przebieg.kroki[0].czas_ms >= 0
    assert przebieg.pliki and przebieg.pliki[0]["nazwa"].endswith(".pdf")
    zapisany = sesja.plik(przebieg.pliki[0]["id"])
    assert zapisany.sciezka.resolve().is_relative_to(sesja.katalog.resolve())


async def test_przebieg_zglasza_blad_narzedzia(settings: Settings) -> None:
    box = Piaskownica(settings)
    sesja = box.utworz("10.0.0.7")
    zly = Scenariusz(
        id="zly",
        tytul="Zły",
        opis="Test",
        wiadomosc="",
        przyklady=(),
        kroki=(
            Krok(
                "Konwersja",
                "convert_images",
                lambda _: {"file_ids": ["nie-uuid"], "target_format": "pdf"},
            ),
        ),
    )
    przebieg = uruchom(Wykonanie(settings=settings, piaskownica=box), sesja, zly, NA_ZYWO, [])
    assert przebieg.zadanie is not None
    await asyncio.wait_for(przebieg.zadanie, 30)
    assert przebieg.stan == "blad"
    assert przebieg.blad
