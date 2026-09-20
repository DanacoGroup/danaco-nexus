"""Silnik nie wychodzi na wierzch: ani w instrukcji agenta, ani w interfejsie.

Użytkownik rozlicza się z nami i widzi Danaco Nexusa. To, na czym stoi silnik i z kim się
rozliczamy, jest sprawą między nami a dostawcą — nie pojawia się w prompcie, w tekstach
witryny ani w komunikatach aplikacji. Wyjątkiem są dokumenty prawne, w których wskazanie
podmiotu przetwarzającego jest obowiązkiem, a nie wyborem.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from nexus.agent.prompt import SUBAGENT_PROMPT, system_prompt

REPO = Path(__file__).resolve().parents[2]
# Nazwy, które nie mają prawa trafić do użytkownika.
NAZWY = ("claude", "opus 5", "sonnet 5", "chatgpt", "gemini", "deepseek")
# „Anthropic” wolno wymienić wyłącznie w dokumentach prawnych jako podmiot przetwarzający.
PLIKI_PRAWNE = {"tresc-prawna.ts"}


def test_instrukcja_agenta_nie_wymienia_silnika() -> None:
    for tresc in (system_prompt(True, True, 3), system_prompt(False, False, 1), SUBAGENT_PROMPT):
        niska = tresc.lower()
        for nazwa in NAZWY:
            assert nazwa not in niska, f"instrukcja wymienia „{nazwa}”"


def test_instrukcja_agenta_nadaje_tozsamosc() -> None:
    tresc = system_prompt(True, True, 3)
    assert "Jesteś Danaco Nexus" in tresc
    niska = tresc.lower()
    # Musi być powiedziane wprost, że nazwa modelu i dostawcy nie wychodzi na zewnątrz.
    assert "nie ujawniasz" in niska
    assert "instrukcji systemowej" in niska


def _pliki_interfejsu() -> list[Path]:
    """Wszystkie pliki interfejsu, łącznie z prawnymi.

    Dokumenty prawne wskazują podmiot przetwarzający z nazwy — tak każe obowiązek
    informacyjny — ale nazw i wersji modeli nie podają, bo dobór modelu jest naszą
    decyzją i nie zmienia zakresu przetwarzanych danych.
    """
    katalog = REPO / "frontend" / "src"
    return [
        plik
        for plik in katalog.rglob("*")
        if plik.suffix in (".ts", ".tsx") and "__tests__" not in plik.parts
    ]


def test_dostawca_tylko_w_dokumentach_prawnych() -> None:
    """Nazwa dostawcy pojawia się w polityce i regulaminie, ale nigdzie indziej."""
    wzorzec = re.compile("anthropic", re.IGNORECASE)
    poza_prawnymi = [
        str(plik.relative_to(REPO))
        for plik in _pliki_interfejsu()
        if plik.name not in PLIKI_PRAWNE and wzorzec.search(plik.read_text(encoding="utf-8"))
    ]
    assert not poza_prawnymi, f"dostawca wymieniony poza dokumentami prawnymi: {poza_prawnymi}"


@pytest.mark.parametrize("nazwa", NAZWY)
def test_interfejs_nie_wymienia_silnika(nazwa: str) -> None:
    wzorzec = re.compile(re.escape(nazwa), re.IGNORECASE)
    znalezione = [
        f"{plik.relative_to(REPO)}:{numer}"
        for plik in _pliki_interfejsu()
        for numer, wiersz in enumerate(plik.read_text(encoding="utf-8").splitlines(), 1)
        if wzorzec.search(wiersz)
    ]
    assert not znalezione, f"„{nazwa}” w interfejsie: {', '.join(znalezione[:5])}"


def test_strona_produktu_nie_wymienia_silnika_w_metadanych() -> None:
    for sciezka in ("frontend/index.html", "frontend/vite.config.ts"):
        tresc = (REPO / sciezka).read_text(encoding="utf-8").lower()
        for nazwa in NAZWY:
            assert nazwa not in tresc, f"{sciezka} wymienia „{nazwa}”"
