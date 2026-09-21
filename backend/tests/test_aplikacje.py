"""Szablony aplikacji: wykaz i założenie projektu w module Kod.

Testy nie kopiują prawdziwych szablonów z ``/danaco/programy`` (Next.js ma tysiące plików) —
katalog szablonów jest podstawiany w ``tmp_path``. Sprawdzane jest to, co decyduje
o poprawności: czytanie opisu, odsianie paczek i wyników budowy, granica przestrzeni
projektów i przypisanie projektu do konta.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import ToolHarness

from nexus.agent.przestrzenie import wlasciciel_projektu
from nexus.tools import aplikacje
from nexus.tools.base import ToolError, registry


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object):  # type: ignore[no-untyped-def]
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


@pytest.fixture
def szablony(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    korzen = tmp_path / "apps"
    panel = korzen / "next-dashboard"
    (panel / "app").mkdir(parents=True)
    (panel / "node_modules" / "react").mkdir(parents=True)
    (panel / ".next" / "server").mkdir(parents=True)
    (panel / "danaco-szablon.json").write_text(
        json.dumps(
            {
                "szablon": "next-dashboard",
                "opis": "Panel operacyjny z kaflami KPI i tabelą zleceń.",
                "marka": "Lumen",
                "tokeny": "app/tokens.css",
                "pliki_marki": ["lib/site.ts"],
                "dev": "pnpm dev",
                "build": "pnpm build",
            }
        ),
        encoding="utf-8",
    )
    (panel / "app" / "page.tsx").write_text("export default () => null;", encoding="utf-8")
    (panel / "app" / "tokens.css").write_text(":root{--akcent:#6C5CE7}", encoding="utf-8")
    (panel / "node_modules" / "react" / "index.js").write_text("// paczka", encoding="utf-8")
    (panel / ".next" / "server" / "page.js").write_text("// wynik budowy", encoding="utf-8")

    (korzen / "bez-opisu").mkdir()
    (korzen / "bez-opisu" / "index.html").write_text("<!doctype html>", encoding="utf-8")

    # Kolekcja szablonów otwartych ma swoją część wykazu — w testach też jest podstawiana,
    # inaczej wchodzą do niego prawdziwe pozycje z /danaco/programy.
    kolekcja = tmp_path / "kolekcja"
    panel_kolekcji = kolekcja / "szablony" / "tailadmin-react"
    (panel_kolekcji / "zrodlo" / "src").mkdir(parents=True)
    (panel_kolekcji / "witryna").mkdir()
    (panel_kolekcji / "zrodlo" / "src" / "App.tsx").write_text("export default () => null;", encoding="utf-8")
    (panel_kolekcji / "zrodlo" / "package.json").write_text('{"name":"tailadmin"}', encoding="utf-8")
    (panel_kolekcji / "meta.json").write_text(
        json.dumps(
            {
                "id": "tailadmin-react",
                "opis": "Panel administracyjny React + Tailwind.",
                "licencja": "MIT",
                "stos": ["react", "vite", "tailwind"],
                "charakter": ["panel", "aplikacja"],
                "zrodlo": "https://github.com/TailAdmin/free-react-tailwind-admin-dashboard",
            }
        ),
        encoding="utf-8",
    )
    witryna = kolekcja / "szablony" / "astro-blog"
    (witryna / "zrodlo").mkdir(parents=True)
    (witryna / "meta.json").write_text(
        json.dumps({"id": "astro-blog", "charakter": ["blog"], "licencja": "MIT"}), encoding="utf-8"
    )

    monkeypatch.setattr(aplikacje, "SZABLONY", korzen)
    monkeypatch.setattr(aplikacje, "KOLEKCJA", kolekcja)
    return korzen


def test_wykaz_laczy_zestaw_danaco_z_aplikacjami_kolekcji(
    harness: ToolHarness, szablony: Path
) -> None:
    """Kolekcja szablonów otwartych ma kilkadziesiąt paneli — były niewidoczne dla agenta."""
    wynik = wywolaj(harness, "app_templates")

    assert [s["id"] for s in wynik.data["szablony"]] == ["next-dashboard", "tailadmin-react"]
    assert wynik.data["szablony"][0]["marka"] == "Lumen"
    assert wynik.data["szablony"][0]["dev"] == "pnpm dev"
    # Paczki i wynik budowy nie liczą się do wielkości szablonu.
    assert wynik.data["szablony"][0]["plikow"] == 3
    z_kolekcji = wynik.data["szablony"][1]
    assert z_kolekcji["licencja"] == "MIT"
    assert z_kolekcji["stos"] == ["react", "vite", "tailwind"]
    assert z_kolekcji["zrodlo_szablonu"] == "kolekcja"


def test_wykaz_pomija_witryny_z_kolekcji(harness: ToolHarness, szablony: Path) -> None:
    """Blog z kolekcji to witryna — wstawia go site_from_template, nie app_from_template."""
    wynik = wywolaj(harness, "app_templates")

    assert "astro-blog" not in [s["id"] for s in wynik.data["szablony"]]


def test_wykaz_zaweza_po_opisie(harness: ToolHarness, szablony: Path) -> None:
    wynik = wywolaj(harness, "app_templates", szukaj="kpi")

    assert len(wynik.data["szablony"]) == 1


def test_brak_szablonow_mowi_wprost(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(aplikacje, "SZABLONY", tmp_path / "nie-ma")
    monkeypatch.setattr(aplikacje, "KOLEKCJA", tmp_path / "tez-nie-ma")

    with pytest.raises(ToolError, match="nie są zainstalowane"):
        wywolaj(harness, "app_templates")


def test_projekt_powstaje_bez_paczek_i_wynikow_budowy(harness: ToolHarness, szablony: Path) -> None:
    wynik = wywolaj(harness, "app_from_template", szablon="next-dashboard", projekt="panel-ani")

    katalog = harness.settings.kod_dir / "panel-ani"
    assert (katalog / "app" / "page.tsx").is_file()
    assert (katalog / "danaco-szablon.json").is_file()
    assert not (katalog / "node_modules").exists()
    assert not (katalog / ".next").exists()
    assert wynik.data["pliki"] == 3
    assert wynik.data["pliki_marki"] == ["lib/site.ts"]
    # Projekt należy do konta, które go założyło — inaczej byłby niewidoczny w module Kod.
    assert wlasciciel_projektu(harness.settings, "panel-ani") == harness.context().owner_id


def test_nie_nadpisuje_istniejacego_projektu(harness: ToolHarness, szablony: Path) -> None:
    wywolaj(harness, "app_from_template", szablon="next-dashboard", projekt="panel")

    with pytest.raises(ToolError, match="już istnieje"):
        wywolaj(harness, "app_from_template", szablon="next-dashboard", projekt="panel")


def test_szablon_ze_sciezka_odpada(harness: ToolHarness, szablony: Path) -> None:
    with pytest.raises(ToolError, match="Nieprawidłowy identyfikator"):
        wywolaj(harness, "app_from_template", szablon="../../etc", projekt="proba")


def test_katalog_bez_opisu_nie_jest_szablonem(harness: ToolHarness, szablony: Path) -> None:
    with pytest.raises(ToolError, match="nie jest szablonem aplikacji"):
        wywolaj(harness, "app_from_template", szablon="bez-opisu", projekt="proba")


def test_nazwa_projektu_ze_sciezka_odpada(harness: ToolHarness, szablony: Path) -> None:
    with pytest.raises(ToolError, match="Niepoprawna nazwa projektu"):
        wywolaj(harness, "app_from_template", szablon="next-dashboard", projekt="../ucieczka")


def test_szablon_z_tysiacami_plikow_mowi_o_tym_przed_kopiowaniem(
    harness: ToolHarness, szablony: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(aplikacje, "MAKS_PLIKOW", 1)

    with pytest.raises(ToolError, match="wynikiem budowy"):
        wywolaj(harness, "app_from_template", szablon="next-dashboard", projekt="duzy")


def test_przerwane_kopiowanie_nie_zostawia_polowicznego_projektu(
    harness: ToolHarness, szablony: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Projekt bez właściciela nie pokazuje się w module Kod — nawet po to, żeby go skasować."""
    import shutil as _shutil

    from nexus.tools import aplikacje as modul

    wywolania = {"ile": 0}

    def padnij(zrodlo: object, cel: object) -> None:
        wywolania["ile"] += 1
        if wywolania["ile"] > 1:
            raise OSError("brak miejsca na dysku")
        _shutil.copy2(zrodlo, cel)  # type: ignore[arg-type]

    monkeypatch.setattr(modul.shutil, "copy2", padnij)

    with pytest.raises(OSError, match="brak miejsca"):
        wywolaj(harness, "app_from_template", szablon="next-dashboard", projekt="niedokonczony")

    assert not (harness.settings.kod_dir / "niedokonczony").exists()


def test_projekt_z_aplikacji_kolekcji_bierze_zrodlo_a_nie_witryne(
    harness: ToolHarness, szablony: Path
) -> None:
    """Do modułu Kod idzie projekt do edycji, nie zbudowana witryna."""
    wynik = wywolaj(harness, "app_from_template", szablon="tailadmin-react", projekt="panel-firmy")

    katalog = harness.settings.kod_dir / "panel-firmy"
    assert (katalog / "src" / "App.tsx").is_file()
    assert (katalog / "package.json").is_file()
    assert not (katalog / "witryna").exists()
    assert wynik.data["licencja"] == "MIT"
    assert "MIT" in wynik.summary


def test_witryna_z_kolekcji_odsyla_do_wlasciwego_narzedzia(harness: ToolHarness, szablony: Path) -> None:
    with pytest.raises(ToolError, match="site_from_template"):
        wywolaj(harness, "app_from_template", szablon="astro-blog", projekt="blog")


def test_wykaz_nie_wysypuje_calej_biblioteki_do_odpowiedzi(
    harness: ToolHarness, szablony: Path
) -> None:
    """Pełny spis z opisami to kilkanaście tysięcy znaków — tyle kontekstu nie jest potrzebne."""
    wynik = wywolaj(harness, "app_templates", limit=1)

    assert len(wynik.data["szablony"]) == 1
    assert wynik.data["pasujacych"] == 2, "liczba wszystkich pasujących zostaje w wyniku"
    assert "zaweź spis" in wynik.summary


def test_wykaz_zaweza_takze_po_stosie(harness: ToolHarness, szablony: Path) -> None:
    """„Panel na Vue” ma dać panele na Vue, a nie wszystko, co ma w opisie słowo panel."""
    wynik = wywolaj(harness, "app_templates", szukaj="react")

    assert [s["id"] for s in wynik.data["szablony"]] == ["tailadmin-react"]


def test_szablon_bez_mapy_marki_mowi_gdzie_jej_szukac(harness: ToolHarness, szablony: Path) -> None:
    """Kolekcja otwarta nie ma pola `pliki_marki` — agent nie może zgadywać, gdzie jest marka."""
    z_mapa = wywolaj(harness, "app_from_template", szablon="next-dashboard", projekt="z-mapa")
    bez_mapy = wywolaj(harness, "app_from_template", szablon="tailadmin-react", projekt="bez-mapy")

    assert "pliki_marki" in z_mapa.summary or "lib/site.ts" in str(z_mapa.data["pliki_marki"])
    assert "package.json" in bez_mapy.summary
    assert bez_mapy.data["marka_do_znalezienia"] is True
    assert "marka_do_znalezienia" not in z_mapa.data
