"""Piaskownica agenta: co proces CLI widzi, a czego nie.

Instrukcja trybu Kod mówiła agentowi „nie wychodź poza katalog projektu”, ale ani Read, ani
Bash tego nie egzekwowały — wystarczyła ścieżka bezwzględna, żeby przeczytać kod Nexusa albo
cudzy projekt na serwerze. Te testy sprawdzają, że ograniczenie robi teraz jądro: w przestrzeni
montowań procesu CLI tamtych katalogów po prostu nie ma.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from nexus.agent import piaskownica
from nexus.agent.runner import piaskownica_wlaczona
from nexus.config import Settings

pytestmark = pytest.mark.skipif(not piaskownica.dostepna(), reason="bwrap niedostępny")

KOD_NEXUSA = Path(__file__).resolve().parents[1] / "nexus" / "agent" / "runner.py"


def w_piaskownicy(polecenie: str, projekt: Path) -> str:
    """Uruchamia polecenie powłoki w piaskownicy z jednym katalogiem do zapisu."""
    args = piaskownica.polecenie(
        piaskownica.znajdz_bwrap(),
        ["/usr/bin/sh", "-c", polecenie],
        cwd=projekt,
        zapis=(projekt,),
    )
    wynik = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)
    return wynik.stdout + wynik.stderr


def test_projekt_uzytkownika_jest_widoczny(tmp_path: Path) -> None:
    (tmp_path / "notatka.txt").write_text("treść użytkownika\n", encoding="utf-8")
    assert "treść użytkownika" in w_piaskownicy("cat notatka.txt", tmp_path)


def test_kod_nexusa_jest_niewidoczny(tmp_path: Path) -> None:
    assert KOD_NEXUSA.is_file(), "test nie ma sensu bez pliku odniesienia"
    wyjscie = w_piaskownicy(f"cat {KOD_NEXUSA} 2>&1", tmp_path)
    assert "No such file" in wyjscie or "Nie ma" in wyjscie
    assert "Przebieg agenta" not in wyjscie


def test_pozostale_projekty_serwera_sa_niewidoczne(tmp_path: Path) -> None:
    """Na dysku stoi kilkadziesiąt projektów; agent jednego konta nie ma wstępu do żadnego.

    Sama ścieżka do katalogu roboczego musi istnieć, więc jej kolejne człony są w piaskownicy
    widoczne jako puste katalogi. Liczy się to, że nic poza wskazanym katalogiem nie ma
    zawartości — i to sprawdza ten test.
    """
    projekty = Path("/danaco/projekty")
    if not projekty.is_dir():
        pytest.skip("brak katalogu projektów serwera")
    wyjscie = w_piaskownicy("ls /danaco/projekty 2>&1", tmp_path)
    widoczne = {nazwa for nazwa in wyjscie.split() if nazwa}
    na_dysku = {p.name for p in projekty.iterdir() if p.is_dir()}
    assert len(na_dysku) > 1, "test nie ma sensu przy jednym projekcie na dysku"
    assert not (widoczne & na_dysku), f"agent widzi cudze projekty: {widoczne & na_dysku}"


def test_lancuch_narzedzi_zostaje_dostepny(tmp_path: Path) -> None:
    """Bez programów serwera moduł Kod nie miałby czym budować ani testować."""
    assert "bin" in w_piaskownicy("ls /danaco/programy", tmp_path)


def test_zapis_poza_wskazanym_katalogiem_jest_niemozliwy(tmp_path: Path) -> None:
    wyjscie = w_piaskownicy("touch /usr/proba 2>&1; echo koniec", tmp_path)
    assert "koniec" in wyjscie
    assert not Path("/usr/proba").exists()


def test_ustawienie_wylacza_piaskownice() -> None:
    assert piaskownica_wlaczona(Settings(agent_piaskownica=False)) is False


# --- środowisko procesu ------------------------------------------------------------------


def test_srodowisko_serwera_nie_wchodzi_do_piaskownicy(tmp_path: Path, monkeypatch) -> None:
    """W środowisku procesu roboczego stoi adres bazy i ścieżki do plików z kluczami.

    `bwrap` bez `--clearenv` dziedziczy je w całości, a program uruchomiony w piaskownicy
    (`node -p process.env`, `python -c "import os;print(os.environ)"`) wypisuje je jednym
    poleceniem. Sekretów i tak nie widać — ale adresy, ścieżki i nazwy usług wewnętrznych
    to wyciek, którego nie musi być.
    """
    monkeypatch.setenv("NEXUS_TAJNE", "sekret-do-wykrycia")
    monkeypatch.setenv("NEXUS_DATABASE_URL", "postgresql://ktos:haslo@host/baza")
    wyjscie = w_piaskownicy("env", tmp_path)
    assert "sekret-do-wykrycia" not in wyjscie
    assert "postgresql://" not in wyjscie
    widoczne = {wiersz.split("=", 1)[0] for wiersz in wyjscie.splitlines() if "=" in wiersz}
    assert not {nazwa for nazwa in widoczne if nazwa.startswith("NEXUS_")}
    # To, bez czego programy nie ruszą, zostaje.
    assert {"PATH", "HOME"} <= widoczne


def test_wykaz_zmiennych_buduje_srodowisko_od_zera(monkeypatch) -> None:
    """Wykaz jest dodający, nie odejmujący — nowa zmienna nie przecieka sama z siebie."""
    monkeypatch.setenv("NEXUS_NOWA_ZMIENNA", "cokolwiek")
    czyste = piaskownica.srodowisko(dom="/tmp/dom")
    assert "NEXUS_NOWA_ZMIENNA" not in czyste
    assert czyste["HOME"] == "/tmp/dom" and czyste["TMPDIR"] == "/tmp/dom"
    assert czyste["PATH"]


def test_srodowisko_cli_przepuszcza_tylko_ustawienia_cli() -> None:
    """Proces CLI dostaje swoje zmienne; konfiguracja Nexusa zostaje po stronie serwera."""
    from nexus.agent.runner import srodowisko_cli

    czyste = srodowisko_cli(
        {
            "CLAUDE_CONFIG_DIR": "/profil",
            "CLAUDE_CODE_OAUTH_TOKEN": "token",
            "MCP_TIMEOUT": "1000",
            "NEXUS_DATABASE_URL": "postgresql://ktos:haslo@host/baza",
            "NEXUS_PLATNOSCI_STRIPE_KLUCZ_PLIK": "/dane/stripe",
            "HOME": "/dom",
        }
    )
    assert czyste["CLAUDE_CONFIG_DIR"] == "/profil"
    assert czyste["CLAUDE_CODE_OAUTH_TOKEN"] == "token"
    assert czyste["MCP_TIMEOUT"] == "1000"
    assert czyste["HOME"] == "/dom"
    assert not [nazwa for nazwa in czyste if nazwa.startswith("NEXUS_")]
