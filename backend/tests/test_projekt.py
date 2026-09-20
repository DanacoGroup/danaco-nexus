"""Narzędzia projektowania grafiki: rysunek wektorowy i skład kadru.

Do tej pory agent umiał wyłącznie poprawiać cudze pliki — nie miał czym zaprojektować
grafiki od zera. Testy pilnują, że projekt naprawdę powstaje jako plik oraz że rysunek
nie może pobierać zasobów z sieci ani przemycić kodu.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import ToolHarness, requires_program
from PIL import Image

from nexus.tools.base import ToolError, registry

PROSTY_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100" width="200" height="100">'
    '<rect width="200" height="100" fill="#0D0F17"/>'
    '<circle cx="60" cy="50" r="28" fill="#7B5CFF"/>'
    '<text x="110" y="56" fill="#FFFFFF" font-size="18">Nexus</text>'
    "</svg>"
)


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object):  # type: ignore[no-untyped-def]
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


def test_narzedzia_projektowe_sa_zarejestrowane() -> None:
    assert {"design_vector", "design_compose"} <= set(registry.names())


@pytest.mark.parametrize(
    "svg",
    [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>alert(1)</script></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<image xlink:href="https://obcy.example/x.png"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<foreignObject><div>x</div></foreignObject></svg>',
        '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text>&x;</text></svg>',
    ],
)
def test_rysunek_odrzuca_zasoby_z_sieci_i_kod(harness: ToolHarness, svg: str) -> None:
    with pytest.raises(ToolError, match="sieci|skrypt"):
        wywolaj(harness, "design_vector", svg=svg, formaty=["svg"])


def test_rysunek_wymaga_rozmiaru(harness: ToolHarness) -> None:
    bez_rozmiaru = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    with pytest.raises(ToolError, match="viewBox"):
        wywolaj(harness, "design_vector", svg=bez_rozmiaru + " " * 40, formaty=["svg"])


def test_rysunek_oddaje_svg_bez_rasteryzacji(harness: ToolHarness) -> None:
    """Sam SVG nie wymaga Inkscape'a — plik jest wynikiem pracy modelu."""
    wynik = wywolaj(harness, "design_vector", svg=PROSTY_SVG, nazwa="znak", formaty=["svg"])
    assert [plik.name for plik in wynik.files] == ["znak.svg"]
    assert "circle" in Path(wynik.files[0].path).read_text(encoding="utf-8")


@requires_program("inkscape")
def test_rysunek_renderuje_png_i_pdf(harness: ToolHarness) -> None:
    wynik = wywolaj(
        harness, "design_vector", svg=PROSTY_SVG, nazwa="plakat", formaty=["png", "pdf"], szerokosc_px=400
    )
    nazwy = {plik.name for plik in wynik.files}
    assert nazwy == {"plakat.png", "plakat.pdf"}
    png = next(plik.path for plik in wynik.files if plik.name.endswith(".png"))
    with Image.open(png) as obraz:
        assert obraz.width == 400
    assert wynik.images, "model dostaje podgląd projektu"


def test_sklad_nakłada_warstwy(harness: ToolHarness, tmp_path: Path) -> None:
    kwadrat = tmp_path / "kwadrat.png"
    Image.new("RGBA", (40, 40), (255, 0, 0, 255)).save(kwadrat)
    wynik = wywolaj(
        harness,
        "design_compose",
        szerokosc=120,
        wysokosc=80,
        tlo="#FFFFFF",
        nazwa="baner",
        warstwy=[{"file_id": harness.add(kwadrat), "x": 10, "y": 20}],
    )
    assert wynik.data["szerokosc"] == 120
    with Image.open(wynik.files[0].path) as obraz:
        assert obraz.size == (120, 80)
        assert obraz.convert("RGB").getpixel((30, 40)) == (255, 0, 0)
        assert obraz.convert("RGB").getpixel((5, 5)) == (255, 255, 255)


def test_sklad_wymaga_zawartosci(harness: ToolHarness) -> None:
    with pytest.raises(ToolError, match="choć jednej warstwy"):
        wywolaj(harness, "design_compose", szerokosc=100, wysokosc=100)


def test_sklad_odrzuca_niedozwolona_barwe(harness: ToolHarness, tmp_path: Path) -> None:
    plik = tmp_path / "x.png"
    Image.new("RGBA", (4, 4), (0, 0, 0, 255)).save(plik)
    with pytest.raises(ToolError, match="barwa"):
        wywolaj(
            harness,
            "design_compose",
            szerokosc=50,
            wysokosc=50,
            tlo="url(http://zly)",
            warstwy=[{"file_id": harness.add(plik)}],
        )
