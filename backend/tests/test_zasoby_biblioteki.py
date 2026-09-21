"""Biblioteki materiałów serwera: wykaz i wstawianie do szkicu strony.

Materiały leżą poza projektem (``/danaco/programy``), więc testy pracują na podstawionych
katalogach — sprawdzamy to, co decyduje o poprawności i bezpieczeństwie: zawężanie wykazu,
rozwiązywanie ścieżki wyłącznie wewnątrz działu i zapis przez ``SiteStore``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import ToolHarness

from nexus.tools import zasoby
from nexus.tools.base import ToolError, ToolResult, registry
from nexus.tworczy.strony import site_store


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object) -> ToolResult:
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


@pytest.fixture
def biblioteki(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    grafika = tmp_path / "grafika"
    (grafika / "ilustracje" / "open-peeps").mkdir(parents=True)
    (grafika / "ilustracje" / "open-peeps" / "osoba-1.svg").write_text("<svg/>", encoding="utf-8")
    (grafika / "ilustracje" / "open-peeps" / "osoba-2.svg").write_text("<svg/>", encoding="utf-8")
    (grafika / "wzory").mkdir()
    (grafika / "wzory" / "kropki.svg").write_text("<svg/>", encoding="utf-8")
    (grafika / "notatka.txt").write_text("nie materiał", encoding="utf-8")
    (grafika / "manifest.json").write_text(
        json.dumps([{"id": "open-peeps", "nazwa": "Open Peeps", "licencja": "CC0-1.0"}]),
        encoding="utf-8",
    )
    ruch = tmp_path / "ruch"
    (ruch / "tla-webgl").mkdir(parents=True)
    (ruch / "tla-webgl" / "vanta.min.js").write_text("// tło", encoding="utf-8")
    media = tmp_path / "media"
    (media / "dzwieki").mkdir(parents=True)
    (media / "dzwieki" / "klik.mp3").write_bytes(b"ID3")
    monkeypatch.setitem(zasoby.DZIALY, "grafika", grafika)
    monkeypatch.setitem(zasoby.DZIALY, "ruch", ruch)
    monkeypatch.setitem(zasoby.DZIALY, "media", media)
    return {"grafika": grafika, "ruch": ruch, "media": media}


def test_wykaz_liczy_materialy_i_pomija_pliki_pomocnicze(
    harness: ToolHarness, biblioteki: dict[str, Path]
) -> None:
    wynik = wywolaj(harness, "asset_library")
    grafika = wynik.data["dzialy"]["grafika"]
    # notatka.txt nie jest materiałem do wstawienia na stronę.
    assert grafika["materialow"] == 3
    assert [z["id"] for z in grafika["zestawy"]] == ["open-peeps"], "zestawy mają iść z manifestu"
    assert grafika["zestawy"][0]["licencja"] == "CC0-1.0"
    assert wynik.data["dzialy"]["media"]["materialow"] == 1


def test_wykaz_zaweza_po_fragmencie_sciezki(harness: ToolHarness, biblioteki: dict[str, Path]) -> None:
    wynik = wywolaj(harness, "asset_library", dzial="grafika", szukaj="peeps")
    pasujace = [p["sciezka"] for p in wynik.data["dzialy"]["grafika"]["pasujace"]]
    assert pasujace == ["ilustracje/open-peeps/osoba-1.svg", "ilustracje/open-peeps/osoba-2.svg"]


def test_wykaz_bez_manifestu_bierze_nazwy_katalogow(
    harness: ToolHarness, biblioteki: dict[str, Path]
) -> None:
    wynik = wywolaj(harness, "asset_library", dzial="ruch")
    assert [z["id"] for z in wynik.data["dzialy"]["ruch"]["zestawy"]] == ["tla-webgl"]


def test_material_trafia_do_szkicu_strony(harness: ToolHarness, biblioteki: dict[str, Path]) -> None:
    store = site_store(harness.settings)
    store.create("wizytowka", "Wizytówka")
    wynik = wywolaj(
        harness,
        "asset_to_site",
        site="wizytowka",
        dzial="grafika",
        sciezka="wzory/kropki.svg",
        cel="img/tlo.svg",
    )
    assert wynik.data["plik"] == "img/tlo.svg"
    assert "<svg" in store.read_text("wizytowka", "img/tlo.svg")


def test_material_bez_wskazanego_celu_ladu_je_w_zasobach(
    harness: ToolHarness, biblioteki: dict[str, Path]
) -> None:
    store = site_store(harness.settings)
    store.create("blog", "Blog")
    wynik = wywolaj(harness, "asset_to_site", site="blog", dzial="media", sciezka="dzwieki/klik.mp3")
    assert wynik.data["plik"] == "zasoby/klik.mp3"


def test_sciezka_nie_wyprowadza_poza_dzial(harness: ToolHarness, biblioteki: dict[str, Path]) -> None:
    """Ścieżka materiału idzie z rozmowy — „..” nie może wyprowadzić poza katalog działu."""
    store = site_store(harness.settings)
    store.create("proba", "Próba")
    with pytest.raises(ToolError, match="nie ma materiału"):
        wywolaj(harness, "asset_to_site", site="proba", dzial="grafika", sciezka="../../etc/passwd")


def test_wstawienie_do_nieistniejacej_strony_mowi_co_zrobic(
    harness: ToolHarness, biblioteki: dict[str, Path]
) -> None:
    with pytest.raises(ToolError, match="Najpierw załóż ją"):
        wywolaj(harness, "asset_to_site", site="brak", dzial="grafika", sciezka="wzory/kropki.svg")


def test_brak_dzialu_na_serwerze_mowi_wprost(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(zasoby.DZIALY, "grafika", tmp_path / "nie-ma")
    with pytest.raises(ToolError, match="nie jest zainstalowany"):
        wywolaj(harness, "asset_library", dzial="grafika")


def test_material_z_katalogu_nieobslugiwanego_nie_jest_proponowany(
    harness: ToolHarness, biblioteki: dict[str, Path]
) -> None:
    """Materiał, którego tutejsze programy nie otworzą, zostaje na dysku, ale nie w spisie.

    Dziewięć LUT-ów ACES ma niestandardowy zakres wejścia i ffmpeg ich nie wczytuje; dla
    programów do montażu są poprawne, więc ich nie kasujemy — ale agent nie ma ich podawać.
    """
    media = biblioteki["media"]
    (media / "luty" / "nieobslugiwane-ffmpeg").mkdir(parents=True)
    (media / "luty" / "nieobslugiwane-ffmpeg" / "aces.cube").write_text("LUT_3D_SIZE 2", encoding="utf-8")
    (media / "luty" / "dziala.cube").write_text("LUT_3D_SIZE 2", encoding="utf-8")

    wynik = wywolaj(harness, "asset_library", dzial="media", szukaj="cube")
    sciezki = [p["sciezka"] for p in wynik.data["dzialy"]["media"]["pasujace"]]

    assert sciezki == ["luty/dziala.cube"]

    store = site_store(harness.settings)
    store.create("proba", "Próba")
    with pytest.raises(ToolError, match="nie otworzą"):
        wywolaj(
            harness,
            "asset_to_site",
            site="proba",
            dzial="media",
            sciezka="luty/nieobslugiwane-ffmpeg/aces.cube",
        )


def test_pliki_budowy_paczki_nie_uchodza_za_material(
    harness: ToolHarness, biblioteki: dict[str, Path]
) -> None:
    """Zestaw bywa całym repozytorium autora — konfiguracja budowy nie jest ilustracją.

    Open Doodles przyszedł z ``rollup.config.js``, aplikacją przykładową i testami. Bez
    odsiania agent dostawał je na początku spisu ilustracji i miał z czego wybrać źle.
    """
    grafika = biblioteki["grafika"]
    zestaw = grafika / "ilustracje" / "doodles"
    (zestaw / "example" / "src").mkdir(parents=True)
    (zestaw / "svg").mkdir()
    (zestaw / "rollup.config.js").write_text("export default {}", encoding="utf-8")
    (zestaw / "example" / "src" / "App.js").write_text("// przykład", encoding="utf-8")
    (zestaw / "svg" / "kawa.svg").write_text("<svg/>", encoding="utf-8")

    wynik = wywolaj(harness, "asset_library", dzial="grafika", szukaj="doodles")
    sciezki = [p["sciezka"] for p in wynik.data["dzialy"]["grafika"]["pasujace"]]

    assert sciezki == ["ilustracje/doodles/svg/kawa.svg"]
