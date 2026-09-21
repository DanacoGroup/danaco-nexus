"""Przeglądarka agenta i zestaw stron: narzędzia, granice adresów, sterownik.

Agent miał dotąd odczyt strony po HTTP i jednorazowy zrzut — wszystko za kliknięciem albo
formularzem było dla niego zamknięte. Testy pilnują, że narzędzia są zarejestrowane, że
adresy sieci wewnętrznej nie przechodzą i że sterownik naprawdę otwiera stronę oraz klika
(ten ostatni tylko tam, gdzie jest Chromium i wyjście do sieci).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from nexus.tools import registry
from nexus.tools.kit_www import KIT
from nexus.tworczy.przegladarka import NODE, STEROWNIK, przegladarka

NARZEDZIA_PRZEGLADARKI = ("browser_open", "browser_click", "browser_type", "browser_scroll", "browser_back")


def test_narzedzia_przegladarki_sa_w_rejestrze() -> None:
    nazwy = set(registry.names())
    assert set(NARZEDZIA_PRZEGLADARKI) <= nazwy


def test_narzedzia_zestawu_stron_sa_w_rejestrze() -> None:
    nazwy = set(registry.names())
    assert {"site_kit_catalog", "site_from_kit"} <= nazwy


def test_opis_przegladarki_mowi_kiedy_jej_uzyc() -> None:
    """Opis narzędzia jest jedyną instrukcją, jaką model widzi przy wyborze."""
    opis = registry.get("browser_open").description
    assert "browser_click" in opis
    assert "web_fetch_page" in opis, "model musi wiedzieć, kiedy wystarczy zwykły odczyt"


@pytest.mark.parametrize(
    "adres",
    ["http://127.0.0.1:8930/", "http://localhost/", "http://192.168.0.5/", "file:///etc/passwd"],
)
def test_adresy_sieci_wewnetrznej_nie_przechodza(adres: str) -> None:
    from nexus.research.web import check_url

    with pytest.raises(Exception):  # noqa: B017 - rodzaj wyjątku zależy od powodu odrzucenia
        check_url(adres)


def test_sterownik_jest_na_swoim_miejscu() -> None:
    assert STEROWNIK.is_file()


@pytest.mark.skipif(
    not Path(NODE).exists() or os.environ.get("NEXUS_BEZ_SIECI") == "1",
    reason="brak Node albo test bez sieci",
)
def test_sterownik_otwiera_strone_i_klika() -> None:
    okno = przegladarka()
    try:
        stan = okno.polecenie({"akcja": "otworz", "adres": "https://example.com"})
        assert stan["tytul"]
        assert stan["elementy"], "strona bez wykazu elementów jest dla modelu nieklikalna"
        nazwa = stan["elementy"][0]["nazwa"]
        po_kliknieciu = okno.polecenie({"akcja": "klik", "co": nazwa})
        assert po_kliknieciu["adres"] != stan["adres"]
        assert okno.polecenie({"akcja": "wstecz"})["adres"].startswith("https://example.com")
    finally:
        okno.zamknij()


@pytest.mark.skipif(not KIT.is_dir(), reason="Web Kit nie jest zainstalowany")
def test_katalog_zestawu_stron_ma_presety_i_motywy() -> None:
    from nexus.tools.kit_www import _lista_katalogow, _presety

    assert len(_presety()) >= 5
    assert len(_lista_katalogow(KIT / "themes")) >= 5


# --- animacja wyjaśniająca -------------------------------------------------------------------


def test_scena_bez_klasy_konczy_sie_zrozumialym_bledem() -> None:
    """Komunikat błędu jest jedyną wskazówką, jaką model dostaje — ma mówić, co poprawić."""
    from nexus.tools.animacja import _klasa_sceny
    from nexus.tools.base import ToolError

    with pytest.raises(ToolError, match="Scene"):
        _klasa_sceny("from manim import *\n\nprint('nic')\n")
    assert _klasa_sceny("from manim import *\n\nclass Wykres(Scene):\n    pass\n") == "Wykres"


@pytest.mark.parametrize(
    "kod",
    [
        "import subprocess\nclass A(Scene): pass",
        "class A(Scene):\n    def construct(self): __import__('os').system('ls')",
        "import socket\nclass A(Scene): pass",
    ],
)
def test_scena_siegajaca_do_systemu_nie_przechodzi(kod: str) -> None:
    """Scena i tak renderuje się w piaskownicy; to druga zapora, nie jedyna."""
    from nexus.tools.animacja import _sprawdz_kod
    from nexus.tools.base import ToolError

    with pytest.raises(ToolError):
        _sprawdz_kod(kod)


def test_narzedzie_animacji_jest_w_rejestrze() -> None:
    assert "animate_explainer" in registry.names()
    opis = registry.get("animate_explainer").description
    assert "Scene" in opis, "model musi wiedzieć, jak napisać scenę"
