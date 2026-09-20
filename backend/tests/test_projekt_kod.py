"""Narzędzia pracy nad kodem i stronami: kontrole jakości, audyt, zrzut, ikony, odchudzanie.

Sprawdzamy to, co decyduje o poprawności i bezpieczeństwie: obecność w rejestrze, odrzucanie
ścieżek i adresów spoza przestrzeni użytkownika, komunikat przy braku programu oraz złożenie
polecenia. Kontrole szybkie (typos, svgo, pa11y, ikony) uruchamiamy naprawdę — reszta idzie
przez podstawiony ``ToolContext.run_command``, bo Lighthouse i semgrep liczą kilkanaście sekund.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import ToolHarness, requires_program

from nexus.tools import projekt_kod
from nexus.tools.base import ToolError, ToolResult, registry
from nexus.tworczy.strony import site_store

NARZEDZIA = ("code_check", "web_audit", "web_screenshot", "icon_find", "site_optimize_assets")

STRONA = """<!doctype html><html><head><meta charset="utf-8"><title>Próba</title></head>
<body><h1>Kawiarnia</h1><img src="img/logo.svg"><p>Zapraszamy</p></body></html>"""
LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
    '  <!-- znak firmowy -->\n  <circle cx="50.00000" cy="50.0000" r="40.000" fill="#ff0000"/>\n</svg>'
)


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object) -> ToolResult:
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


def zaloz_strone(harness: ToolHarness, adres: str = "proba") -> None:
    """Szkic strony w magazynie stron (tak jak zrobiłby to moduł Strony)."""
    store = site_store(harness.settings)
    store.create(adres, "Próba")
    store.write_text(adres, "index.html", STRONA)
    store.write_text(adres, "img/logo.svg", LOGO)


def zaloz_projekt(harness: ToolHarness, nazwa: str = "sklep") -> Path:
    """Przestrzeń projektu modułu Kod z kilkoma plikami do sprawdzenia."""
    katalog = harness.settings.kod_dir / nazwa
    (katalog / "backend").mkdir(parents=True)
    (katalog / "backend" / "app.py").write_text(
        "import subprocess\n\n\ndef uruchom(polecenie):\n    return subprocess.call(polecenie, shell=True)\n",
        encoding="utf-8",
    )
    (katalog / "skrypt.sh").write_text(
        "#!/bin/bash\nfor f in $(ls *.txt); do rm $f; done\n", encoding="utf-8"
    )
    return katalog


def test_narzedzia_sa_w_rejestrze() -> None:
    assert set(NARZEDZIA) <= set(registry.names())


# --- kontrola kodu --------------------------------------------------------------------------------


def test_kontrola_wymaga_jednego_celu(harness: ToolHarness) -> None:
    """Bez celu albo z dwoma celami naraz narzędzie nie zgaduje, tylko pyta."""
    with pytest.raises(ToolError, match="jedno z dwóch"):
        wywolaj(harness, "code_check")


def test_kontrola_odrzuca_sciezke_poza_projektem(harness: ToolHarness) -> None:
    """Podkatalog z ``..`` nie może wyprowadzić kontroli poza przestrzeń projektu."""
    zaloz_projekt(harness)
    with pytest.raises(ToolError, match="wewnątrz projektu"):
        wywolaj(harness, "code_check", projekt="sklep", podkatalog="../../../etc")


def test_kontrola_odrzuca_nieznany_projekt(harness: ToolHarness) -> None:
    with pytest.raises(ToolError, match="Nie ma projektu"):
        wywolaj(harness, "code_check", projekt="czegos-takiego-nie-ma")


def test_brak_programu_mowi_po_ludzku(harness: ToolHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    zaloz_projekt(harness)
    monkeypatch.setattr(projekt_kod.shutil, "which", lambda _nazwa: None)
    with pytest.raises(ToolError, match="niedostępne na tym serwerze"):
        wywolaj(harness, "code_check", projekt="sklep", kontrole=["bezpieczenstwo"])


def test_semgrep_sklada_polecenie_z_regulami_wykrytego_jezyka(
    harness: ToolHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Język wykryty po plikach ma wskazać katalog reguł, a wynik iść do pliku w przebiegu."""
    zaloz_projekt(harness)
    reguly = harness.settings.data_dir / "reguly"
    (reguly / "python").mkdir(parents=True)
    monkeypatch.setattr(projekt_kod, "REGULY_SEMGREP", reguly)
    monkeypatch.setattr(projekt_kod.shutil, "which", lambda nazwa: f"/udawane/{nazwa}")
    zapis: list[list[str]] = []

    def udawany_bieg(self, arguments, timeout=600, cwd=None, env=None):  # type: ignore[no-untyped-def]
        zapis.append(list(arguments))
        raport = next(arg for arg in arguments if arg.startswith("--json-output=")).split("=", 1)[1]
        Path(raport).write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "path": str(harness.settings.kod_dir / "sklep" / "backend" / "app.py"),
                            "start": {"line": 5},
                            "check_id": "python.lang.security.audit.subprocess-shell-true",
                            "extra": {"severity": "ERROR", "message": "shell=True"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return None

    monkeypatch.setattr("nexus.tools.base.ToolContext.run_command", udawany_bieg)
    wynik = wywolaj(harness, "code_check", projekt="sklep", kontrole=["bezpieczenstwo"])

    polecenie = zapis[0]
    assert polecenie[0].endswith("semgrep")
    assert "--metrics=off" in polecenie
    assert f"--config={reguly / 'python'}" in polecenie
    assert polecenie[-1] == str(harness.settings.kod_dir / "sklep")
    kontrola = wynik.data["kontrole"]["bezpieczenstwo"]
    assert kontrola["jezyk"] == "python"
    assert kontrola["lista"] == [
        {
            "plik": "backend/app.py",
            "wiersz": 5,
            "waga": "error",
            "regula": "subprocess-shell-true",
            "opis": "shell=True",
        }
    ]


def test_kontrola_zglasza_brak_skryptow_powloki(harness: ToolHarness) -> None:
    katalog = harness.settings.kod_dir / "tylko-python"
    katalog.mkdir(parents=True)
    (katalog / "main.py").write_text("print('cześć')\n", encoding="utf-8")
    with pytest.raises(ToolError, match="skryptów powłoki"):
        wywolaj(harness, "code_check", projekt="tylko-python", kontrole=["powloka"])


@requires_program("typos")
def test_literowki_znajduja_blad_w_pliku_z_rozmowy(harness: ToolHarness, tmp_path: Path) -> None:
    """Kontrola uruchomiona naprawdę na pliku wysłanym w rozmowie."""
    plik = tmp_path / "notatka.md"
    plik.write_text("Ther is a typo adn another one.\n", encoding="utf-8")
    wynik = wywolaj(harness, "code_check", file_ids=[harness.add(plik)], kontrole=["literowki"])
    literowki = wynik.data["kontrole"]["literowki"]
    assert literowki["znalezione"] >= 2
    assert {poz["slowo"] for poz in literowki["lista"]} >= {"Ther", "adn"}
    assert all(poz["plik"] == "notatka.md" for poz in literowki["lista"])


# --- audyt i zrzut strony -------------------------------------------------------------------------


def test_audyt_wymaga_jednego_celu(harness: ToolHarness) -> None:
    zaloz_strone(harness)
    with pytest.raises(ToolError, match="albo publiczny adres"):
        wywolaj(harness, "web_audit", site="proba", adres="https://example.com/")


def test_audyt_odrzuca_adres_w_sieci_lokalnej(harness: ToolHarness) -> None:
    """Model nie może skierować przeglądarki na usługi wewnętrzne serwera."""
    with pytest.raises(ToolError, match="niedozwolony|prywatn"):
        wywolaj(harness, "web_audit", adres="http://127.0.0.1:8000/admin")


def test_audyt_odrzuca_nieistniejaca_podstrone(harness: ToolHarness) -> None:
    zaloz_strone(harness)
    with pytest.raises(ToolError, match="nie ma pliku"):
        wywolaj(harness, "web_audit", site="proba", podstrona="cennik.html")


@requires_program("pa11y")
def test_audyt_dostepnosci_wytyka_brak_opisu_obrazu(harness: ToolHarness) -> None:
    """Szkic strony jest podawany lokalnie i badany naprawdę — bez publikacji."""
    zaloz_strone(harness)
    wynik = wywolaj(harness, "web_audit", site="proba", zakres="dostepnosc", limit=20)
    dostepnosc = wynik.data["dostepnosc"]
    assert dostepnosc["bledy"] >= 1
    opisy = " ".join(poz["opis"] for poz in dostepnosc["lista"])
    assert "alt" in opisy


def test_zrzut_sklada_polecenie_przegladarki(harness: ToolHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    """Wybór urządzenia i motywu ma trafić do polecenia, a adres wskazywać lokalny podgląd."""
    zaloz_strone(harness)
    monkeypatch.setattr(projekt_kod.shutil, "which", lambda nazwa: f"/udawane/{nazwa}")
    zapis: list[list[str]] = []

    def udawany_bieg(self, arguments, timeout=600, cwd=None, env=None):  # type: ignore[no-untyped-def]
        zapis.append(list(arguments))
        from PIL import Image

        Image.new("RGB", (390, 844), (240, 240, 240)).save(arguments[-1])
        return None

    monkeypatch.setattr("nexus.tools.base.ToolContext.run_command", udawany_bieg)
    wynik = wywolaj(harness, "web_screenshot", site="proba", urzadzenie="telefon", motyw="ciemny")

    polecenie = zapis[0]
    assert polecenie[0].endswith("playwright")
    assert polecenie[1] == "screenshot"
    assert "--viewport-size=390,844" in polecenie
    assert "--color-scheme=dark" in polecenie
    assert "--full-page" in polecenie
    assert polecenie[-2].startswith("http://127.0.0.1:")
    assert wynik.images and wynik.files


# --- ikony ----------------------------------------------------------------------------------------

brak_ikon = pytest.mark.skipif(not projekt_kod.IKONY_INDEKS.is_file(), reason="Brak zbioru ikon Iconify")


def test_ikony_odrzucaja_niedozwolona_barwe(harness: ToolHarness) -> None:
    with pytest.raises(ToolError, match="Niedozwolona barwa"):
        wywolaj(harness, "icon_find", zapytanie="envelope", kolor='#fff" onload="x')


def test_zbior_ikon_nie_wychodzi_poza_katalog_zbiorow() -> None:
    """Nazwa zbioru jest sprawdzana, więc nie da się nią wskazać pliku spoza zbioru ikon."""
    with pytest.raises(ToolError, match="Niepoprawna nazwa zbioru"):
        projekt_kod._zbior_ikon("../../../etc/passwd")


@brak_ikon
def test_ikony_znajduja_koperte(harness: ToolHarness) -> None:
    wynik = wywolaj(harness, "icon_find", zapytanie="envelope", limit=3)
    ikony = wynik.data["ikony"]
    assert 1 <= len(ikony) <= 3
    assert all(poz["svg"].startswith("<svg") and poz["svg"].endswith("</svg>") for poz in ikony)
    assert all("envelope" in poz["nazwa"] for poz in ikony)


@brak_ikon
def test_ikony_trafiaja_do_szkicu_strony(harness: ToolHarness) -> None:
    zaloz_strone(harness)
    wynik = wywolaj(harness, "icon_find", zapytanie="envelope", limit=2, do_strony="proba", zestaw="mdi")
    zapisane = wynik.data["zapisane_pliki"]
    assert zapisane and all(sciezka.startswith("img/ikony/") for sciezka in zapisane)
    szkic = site_store(harness.settings).draft_dir("proba")
    assert (szkic / zapisane[0]).is_file()


@brak_ikon
def test_ikony_zglaszaja_brak_trafien(harness: ToolHarness) -> None:
    with pytest.raises(ToolError, match="Nie znalazłem ikony"):
        wywolaj(harness, "icon_find", zapytanie="zzzqqq-nie-ma-takiej")


# --- odchudzanie plików strony ----------------------------------------------------------------------


def test_odchudzanie_zglasza_brak_plikow(harness: ToolHarness) -> None:
    zaloz_strone(harness)
    with pytest.raises(ToolError, match="nie ma plików"):
        wywolaj(harness, "site_optimize_assets", site="proba", rodzaj="png")


@requires_program("svgo")
def test_odchudzanie_zmniejsza_svg_w_szkicu(harness: ToolHarness) -> None:
    """Plik w szkicu zostaje podmieniony na mniejszy — naprawdę, przez svgo."""
    zaloz_strone(harness)
    szkic = site_store(harness.settings).draft_dir("proba")
    przed = (szkic / "img" / "logo.svg").stat().st_size
    wynik = wywolaj(harness, "site_optimize_assets", site="proba", rodzaj="svg")
    assert wynik.data["odchudzone"][0]["plik"] == "img/logo.svg"
    assert (szkic / "img" / "logo.svg").stat().st_size < przed
