"""Zasoby z cudzych serwerów ściągnięte do strony (``site_vendor_assets``).

Testy nie wychodzą do sieci: pobieranie jest podstawiane. Sprawdzane jest to, co decyduje
o poprawności — rozpoznanie adresów, pominięcie krojów Google (mają własną drogę), nazwa
pliku w szkicu, podmiana odwołań z uwzględnieniem zagnieżdżenia i zachowanie przy błędzie.
"""

from __future__ import annotations

import pytest
from conftest import ToolHarness

from nexus.tools import zewnetrzne
from nexus.tools.base import ToolError, registry
from nexus.tworczy.strony import site_store

STRONA = (
    "<!doctype html><html><head>"
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5/dist/bootstrap.min.css">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">'
    "</head><body>"
    '<img src="https://images.unsplash.com/photo-123?w=800&amp;q=80">'
    '<a href="https://przyklad.pl/o-nas">Odsyłacz w treści</a>'
    '<script src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>'
    "</body></html>"
)


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object):  # type: ignore[no-untyped-def]
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


@pytest.fixture
def strona(harness: ToolHarness):  # type: ignore[no-untyped-def]
    store = site_store(harness.settings)
    store.create("firma", "Firma")
    store.write_text("firma", "index.html", STRONA)
    store.write_text("firma", "cennik/index.html", STRONA)
    store.write_text("firma", "styl.css", "body{background:url('https://cdn.example/tlo.png')}")
    return store


def test_narzedzie_jest_w_rejestrze() -> None:
    assert registry.get("site_vendor_assets").name == "site_vendor_assets"


def test_adresy_pomijaja_kroje_google_i_zwykle_odsylacze() -> None:
    adresy = zewnetrzne._adresy(STRONA)

    assert "https://cdn.jsdelivr.net/npm/bootstrap@5/dist/bootstrap.min.css" in adresy
    assert "https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js" in adresy
    assert any("images.unsplash.com" in a for a in adresy)
    # Kroje Google mają własną drogę (site_fonts_local), odsyłacz w treści to nie zasób.
    assert not any("fonts.googleapis.com" in a for a in adresy)
    assert not any("przyklad.pl/o-nas" in a for a in adresy)


def test_nazwa_lokalna_przechodzi_przez_sito_znakow() -> None:
    assert zewnetrzne._nazwa_lokalna("https://cdn.jsdelivr.net/npm/b@5/dist/bootstrap.min.css") == (
        "zewnetrzne/cdn.jsdelivr.net/bootstrap.min.css"
    )
    # Zapytanie w adresie nie może wejść do nazwy pliku, a nazwa bez rozszerzenia je dostaje.
    assert zewnetrzne._nazwa_lokalna("https://images.unsplash.com/photo-123?w=800") == (
        "zewnetrzne/images.unsplash.com/photo-123.txt"
    )
    assert zewnetrzne._nazwa_lokalna("https://przyklad.pl/") == "zewnetrzne/przyklad.pl/plik.txt"


def test_pliki_ladują_w_szkicu_a_odwolania_liczą_sie_od_podstrony(
    harness: ToolHarness, strona, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(zewnetrzne, "_pobierz", lambda adres: b"tresc pliku")

    wynik = wywolaj(harness, "site_vendor_assets", site="firma")

    assert wynik.data["pobranych"] >= 3
    sciezki = [p["path"] for p in strona.list_files("firma")]
    assert "zewnetrzne/cdn.jsdelivr.net/bootstrap.min.css" in sciezki
    strona_glowna = strona.read_text("firma", "index.html")
    podstrona = strona.read_text("firma", "cennik/index.html")
    assert 'href="zewnetrzne/cdn.jsdelivr.net/bootstrap.min.css"' in strona_glowna
    assert 'href="../zewnetrzne/cdn.jsdelivr.net/bootstrap.min.css"' in podstrona
    assert "cdn.jsdelivr.net/npm" not in strona_glowna
    # Kroje Google zostają — zdejmuje je site_fonts_local.
    assert "fonts.googleapis.com" in strona_glowna


def test_bledne_pobranie_nie_przekresla_reszty(
    harness: ToolHarness, strona, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    def pobierz(adres: str) -> bytes:
        if "unsplash" in adres:
            raise ToolError("Serwer odpowiedział 403.")
        return b"tresc"

    monkeypatch.setattr(zewnetrzne, "_pobierz", pobierz)

    wynik = wywolaj(harness, "site_vendor_assets", site="firma")

    assert wynik.data["pobranych"] >= 2
    assert any("unsplash" in p["adres"] for p in wynik.data["pominiete"])
    assert "Nie udało się przy" in wynik.summary


def test_strona_bez_zasobow_z_sieci_mowi_wprost(harness: ToolHarness) -> None:
    store = site_store(harness.settings)
    store.create("czysta", "Czysta")
    store.write_text("czysta", "index.html", '<img src="img/logo.png">')

    with pytest.raises(ToolError, match="nie wczytuje niczego z cudzych serwerów"):
        wywolaj(harness, "site_vendor_assets", site="czysta")


def test_limit_zostawia_resztę_na_kolejne_wywolanie(
    harness: ToolHarness, strona, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(zewnetrzne, "_pobierz", lambda adres: b"tresc")

    wynik = wywolaj(harness, "site_vendor_assets", site="firma", limit=1)

    assert wynik.data["pobranych"] == 1
    assert wynik.data["zostalo_w_sieci"] >= 1
    assert "wywołaj jeszcze raz" in wynik.summary


def test_adres_z_sieci_lokalnej_jest_odrzucony() -> None:
    with pytest.raises(ToolError):
        zewnetrzne._pobierz("http://127.0.0.1:8940/status.php")
