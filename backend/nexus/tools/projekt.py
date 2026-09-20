"""Narzędzia projektowania grafiki: rysunek wektorowy i skład wielu warstw.

Serwer ma Inkscape i ImageMagick, ale agent nie miał czym *zaprojektować* grafiki —
mógł tylko poprawiać cudze pliki. Stąd wrażenie, że produkt służy do retuszu zdjęć.
Te dwa narzędzia domykają lukę: pierwsze zamienia opis agenta w plik wektorowy
(logo, plakat, okładka, ikona, wykres, wizytówka), drugie składa gotowe elementy
w jeden kadr (baner, post, miniatura) z tekstem i przezroczystością.

Rysunek powstaje jako SVG pisany przez model — to format tekstowy, więc agent panuje
nad każdym elementem, a Inkscape odpowiada wyłącznie za rasteryzację i PDF do druku.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Literal

from PIL import Image
from pydantic import Field

from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    image_preview,
    registry,
)
from nexus.tools.common import file_kind, unique_name

#: Największy wymiar strony/kadru w pikselach — powyżej rasteryzacja zjada pamięć.
MAX_BOK = 10_000
PODGLAD = 1024

#: Konstrukcje SVG, które pobierają zasoby albo wykonują kod. Grafika ma być plikiem,
#: nie żądaniem sieciowym: bez tego rysunek agenta mógłby wyciągnąć dane z serwera.
ZAKAZANE = re.compile(
    r"<\s*(script|foreignObject|iframe|use\b[^>]*\bhref\s*=\s*[\"']\s*https?:)"
    r"|<!DOCTYPE|<!ENTITY|xlink:href\s*=\s*[\"']\s*(?!data:image/)"
    r"|\bhref\s*=\s*[\"']\s*(?!#)",
    re.IGNORECASE,
)

FORMATY = {"png", "svg", "pdf"}


class RysunekInput(ToolInput):
    svg: str = Field(
        min_length=40,
        max_length=400_000,
        description="Kompletny dokument SVG: <svg …>…</svg> z atrybutami width, height albo viewBox.",
    )
    nazwa: str = Field(
        default="projekt",
        max_length=80,
        description="Nazwa pliku bez rozszerzenia (np. „plakat-koncert”).",
    )
    formaty: list[Literal["png", "svg", "pdf"]] = Field(
        default=["png", "svg"],
        max_length=3,
        description="Które pliki oddać: png do podglądu i sieci, svg do dalszej edycji, pdf do druku.",
    )
    szerokosc_px: int = Field(
        default=0,
        ge=0,
        le=MAX_BOK,
        description="Szerokość rasteryzacji PNG w pikselach (0 = wymiar z dokumentu SVG).",
    )


def _sprawdz_svg(svg: str) -> str:
    """Sprawdza, że to jeden dokument SVG bez zasobów z sieci i bez kodu."""
    tekst = svg.strip()
    if ZAKAZANE.search(tekst):
        raise ToolError(
            "Rysunek nie może pobierać zasobów z sieci ani zawierać skryptów. "
            "Wszystko — kształty, tekst, obrazy w data: — musi być w samym pliku."
        )
    try:
        korzen = ET.fromstring(tekst)
    except ET.ParseError as error:
        raise ToolError(f"SVG jest niepoprawny składniowo: {error}") from error
    if not korzen.tag.endswith("svg"):
        raise ToolError("Dokument musi zaczynać się elementem <svg>.")
    if not (korzen.get("viewBox") or (korzen.get("width") and korzen.get("height"))):
        raise ToolError("Podaj viewBox albo width i height — inaczej nie wiadomo, jak duży jest projekt.")
    return tekst


@registry.register(
    "design_vector",
    """Projektuje grafikę wektorową od zera: logo, znak, plakat, okładka, ulotka, wizytówka,
ikona, diagram, infografika, etykieta, post do mediów społecznościowych. Podajesz gotowy
dokument SVG (kształty, krzywe, gradienty, tekst), a narzędzie sprawdza go i oddaje pliki:
PNG do sieci, SVG do dalszej edycji i PDF do druku. Używaj go zawsze, gdy grafika ma
dopiero powstać — narzędzia obrazów służą wyłącznie do pracy na gotowych plikach.""",
    RysunekInput,
)
def design_vector(ctx: ToolContext, args: RysunekInput) -> ToolResult:
    tekst = _sprawdz_svg(args.svg)
    rdzen = re.sub(r"[^\w\- ]+", "", args.nazwa).strip() or "projekt"
    zrodlo = ctx.output_path(f"{rdzen}.svg")
    zrodlo.write_text(tekst, encoding="utf-8")

    uzyte: set[str] = set()
    wyniki: list[OutputFile] = []
    podglady: list[bytes] = []
    formaty = list(dict.fromkeys(args.formaty)) or ["png"]

    for format_pliku in formaty:
        ctx.check_cancelled()
        if format_pliku == "svg":
            wyniki.append(OutputFile(zrodlo, zrodlo.name, "Projekt wektorowy (do edycji)"))
            continue
        cel = ctx.output_path(unique_name(f"{rdzen}.{format_pliku}", uzyte))
        polecenie = [
            "inkscape",
            str(zrodlo),
            f"--export-type={format_pliku}",
            f"--export-filename={cel}",
        ]
        if format_pliku == "png" and args.szerokosc_px:
            polecenie.append(f"--export-width={args.szerokosc_px}")
        ctx.progress(f"Renderowanie projektu do {format_pliku.upper()}")
        ctx.run_command(polecenie, timeout=600)
        if not cel.is_file():
            raise ToolError(f"Nie udało się zapisać pliku {format_pliku.upper()}.")
        opis = "Projekt do druku (PDF)" if format_pliku == "pdf" else "Projekt do sieci (PNG)"
        wyniki.append(OutputFile(cel, cel.name, opis))
        if format_pliku == "png":
            podglady.append(image_preview(Image.open(cel), PODGLAD))

    return ToolResult(
        {"pliki": [plik.name for plik in wyniki]},
        f"Projekt „{rdzen}”: {', '.join(format_pliku.upper() for format_pliku in formaty)}",
        images=podglady,
        files=wyniki,
    )


class WarstwaInput(ToolInput):
    file_id: str = Field(description="Obraz do nałożenia (PNG z przezroczystością, JPG, WEBP).")
    x: int = Field(default=0, description="Przesunięcie w poziomie od lewej krawędzi kadru.")
    y: int = Field(default=0, description="Przesunięcie w pionie od górnej krawędzi kadru.")
    szerokosc: int = Field(
        default=0, ge=0, le=MAX_BOK, description="Docelowa szerokość warstwy (0 = bez skalowania)."
    )
    krycie: float = Field(default=1.0, ge=0.0, le=1.0, description="Krycie warstwy (1 = nieprzezroczysta).")


class SkladInput(ToolInput):
    szerokosc: int = Field(ge=16, le=MAX_BOK, description="Szerokość kadru w pikselach.")
    wysokosc: int = Field(ge=16, le=MAX_BOK, description="Wysokość kadru w pikselach.")
    tlo: str = Field(
        default="#FFFFFF",
        max_length=40,
        description="Barwa tła: „#RRGGBB”, „none” dla przezroczystego albo nazwa barwy.",
    )
    warstwy: list[WarstwaInput] = Field(
        default_factory=list, max_length=20, description="Obrazy nakładane w podanej kolejności."
    )
    nakladka_svg: str = Field(
        default="",
        max_length=400_000,
        description="Warstwa wektorowa na wierzchu (napisy, ramki, znak) w rozmiarze kadru.",
    )
    nazwa: str = Field(default="sklad", max_length=80, description="Nazwa pliku bez rozszerzenia.")


BARWA = re.compile(r"^(#[0-9A-Fa-f]{3,8}|none|transparent|[A-Za-z]{3,20})$")


@registry.register(
    "design_compose",
    """Składa gotowe elementy w jeden kadr: baner, miniatura, post, okładka, plansza porównawcza,
kolaż. Ustawiasz rozmiar i barwę tła, nakładasz obrazy z podaniem pozycji, rozmiaru i krycia,
a na wierzch możesz dołożyć warstwę wektorową (napisy, ramki, znak) w rozmiarze kadru.
Do zaprojektowania samej grafiki od zera użyj design_vector.""",
    SkladInput,
)
def design_compose(ctx: ToolContext, args: SkladInput) -> ToolResult:
    if not BARWA.match(args.tlo):
        raise ToolError(f"Niedozwolona barwa tła: {args.tlo!r}")
    if not args.warstwy and not args.nakladka_svg:
        raise ToolError("Skład potrzebuje choć jednej warstwy albo nakładki wektorowej.")

    przezroczyste = args.tlo in {"none", "transparent"}
    kadr = Image.new(
        "RGBA",
        (args.szerokosc, args.wysokosc),
        (0, 0, 0, 0) if przezroczyste else args.tlo,
    )

    for warstwa in args.warstwy:
        ctx.check_cancelled()
        plik = ctx.file(warstwa.file_id)
        if file_kind(plik) != "image":
            raise ToolError(f"{plik.name} nie jest obrazem.")
        with Image.open(plik.path) as otwarty:
            obraz = otwarty.convert("RGBA")
        if warstwa.szerokosc and warstwa.szerokosc != obraz.width:
            wysokosc = max(1, round(obraz.height * warstwa.szerokosc / obraz.width))
            obraz = obraz.resize((warstwa.szerokosc, wysokosc), Image.LANCZOS)
        if warstwa.krycie < 1.0:
            krycie = warstwa.krycie
            kanal = obraz.getchannel("A").point(lambda wartosc, k=krycie: round(wartosc * k))
            obraz.putalpha(kanal)
        kadr.alpha_composite(obraz, (warstwa.x, warstwa.y))

    if args.nakladka_svg:
        tekst = _sprawdz_svg(args.nakladka_svg)
        zrodlo = ctx.output_path("nakladka.svg")
        zrodlo.write_text(tekst, encoding="utf-8")
        warstwa_png = ctx.output_path("nakladka.png")
        ctx.progress("Renderowanie warstwy wektorowej")
        ctx.run_command(
            [
                "inkscape",
                str(zrodlo),
                "--export-type=png",
                f"--export-filename={warstwa_png}",
                f"--export-width={args.szerokosc}",
                f"--export-height={args.wysokosc}",
            ],
            timeout=600,
        )
        with Image.open(warstwa_png) as otwarty:
            kadr.alpha_composite(otwarty.convert("RGBA"), (0, 0))

    rdzen = re.sub(r"[^\w\- ]+", "", args.nazwa).strip() or "sklad"
    cel = ctx.output_path(f"{rdzen}.png")
    (kadr if przezroczyste else kadr.convert("RGB")).save(cel, optimize=True)
    return ToolResult(
        {"output": cel.name, "szerokosc": args.szerokosc, "wysokosc": args.wysokosc},
        f"Skład „{rdzen}” ({args.szerokosc}×{args.wysokosc})",
        images=[image_preview(Image.open(cel), PODGLAD)],
        files=[OutputFile(cel, cel.name, "Gotowy kadr")],
    )


__all__ = ["design_compose", "design_vector"]
