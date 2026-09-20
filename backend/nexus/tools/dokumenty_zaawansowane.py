"""Skład do druku, konwersje tekstu, rozbiór dokumentu, napisy i czytanie na głos.

Serwer ma programy, których agent nie mógł dotąd użyć, a które domykają obietnicę
„PDF do druku” i pracę z tekstem mówionym:

* Typst — skład poligraficzny z gotowych szablonów (raport, oferta, CV, broszura,
  plakat); dotąd PDF powstawał z DOCX-a przepuszczonego przez LibreOffice,
* pandoc — konwersje, których LibreOffice nie robi: EPUB, LaTeX, Markdown, reStructuredText,
* Docling — rozbiór dokumentu na strukturę: nagłówki, kolejność czytania, tabele jako dane,
* WhisperX — transkrypcja z czasem każdego słowa i podziałem na mówców,
* srt — poprawianie czasów gotowych napisów,
* Piper — przeczytanie długiego dokumentu do pliku dźwiękowego.

Treść składu i konwersji pochodzi od modelu, a Typst i LaTeX potrafią czytać pliki oraz
pobierać pakiety z sieci. Dlatego źródło Typsta powstaje tutaj, a tekst modelu trafia do
niego wyłącznie jako literał łańcuchowy (``_ciag``); pandoc działa w trybie ``--sandbox``
z wyłączonymi wstawkami surowego kodu.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import wave
from pathlib import Path
from typing import Any, Literal

import pymupdf
from pydantic import Field

from nexus.storage import safe_filename
from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    image_preview,
    registry,
    truncate_text,
)
from nexus.tools.common import file_kind, render_pdf_page, with_suffix
from nexus.tools.files import _tika_text

#: Skład jest szybki, rozbiór dokumentu i transkrypcja liczą się na procesorze w minutach.
CZAS_SKLAD = 300
CZAS_KONWERSJA = 900
CZAS_STRUKTURA = 3 * 3600
CZAS_TRANSKRYPCJA = 6 * 3600
CZAS_NAPISY = 120
CZAS_DZWIEK = 900

PODGLAD = 1100
PODGLAD_STRON = 2

#: Kroje pisma serwera — przekazujemy je Typstowi wprost, bo usługa API nie musi mieć
#: skonfigurowanego fontconfiga.
KATALOG_KROJOW = Path("/danaco/programy/kroje")
#: Model podziału na mówców pobiera jednorazowo administrator; bez niego WhisperX odmawia.
ZNACZNIK_MOWCOW = Path("/danaco/programy/modele/audio/pyannote/GOTOWE")

BARWA = re.compile(r"^#[0-9A-Fa-f]{6}$")
WYROZNIENIE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
ZNACZNIK_CZASU = re.compile(r"^(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,6}(\.\d{1,3})?)$")
KONIEC_ZDANIA = re.compile(r"(?<=[.!?…:;])\s+")

#: Ile znaków treści przyjmuje jeden skład — powyżej dokument i tak przestaje być czytelny.
MAX_ZNAKOW_SKLADU = 400_000
#: Ile znaków czyta na głos jedno wywołanie (około trzech godzin nagrania).
MAX_ZNAKOW_CZYTANIA = 200_000
#: Długość porcji tekstu podawanej syntezatorowi naraz.
PORCJA_MOWY = 1200


def _program(nazwa: str, czego_dotyczy: str) -> str:
    """Ścieżka programu serwera albo błąd zrozumiały dla użytkownika."""
    sciezka = shutil.which(nazwa)
    if not sciezka:
        raise ToolError(f"{czego_dotyczy} jest niedostępne na tym serwerze.")
    return sciezka


def _kopia_robocza(ctx: ToolContext, file_id: str) -> tuple[str, Path]:
    """Kopia pliku rozmowy pod bezpieczną nazwą (programy nazywają wyniki po nazwie wejścia)."""
    plik = ctx.file(file_id)
    kopia = ctx.output_path(safe_filename(plik.name, "plik"))
    kopia.write_bytes(plik.path.read_bytes())
    return plik.name, kopia


# --- skład Typst ---------------------------------------------------------------------------


def _ciag(tekst: str, obetnij: bool = True) -> str:
    """Tekst modelu jako literał łańcuchowy Typsta — nigdy jako kod składu."""
    czysty = "".join(znak for znak in tekst if znak >= " " or znak in "\n\t")
    czysty = re.sub(r"\s+", " ", czysty)
    if obetnij:
        czysty = czysty.strip()
    return '"' + czysty.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _tresc(tekst: str) -> str:
    """Treść Typsta z tekstu modelu; ``**tak**`` daje pogrubienie, reszta zostaje tekstem.

    Odstępy wokół wyróżnienia zostają nietknięte, żeby pogrubione słowo nie skleiło się
    z sąsiednim.
    """
    tekst = tekst.strip()
    czesci: list[str] = []
    pozycja = 0
    for dopasowanie in WYROZNIENIE.finditer(tekst):
        if dopasowanie.start() > pozycja:
            czesci.append(f"#{_ciag(tekst[pozycja : dopasowanie.start()], obetnij=False)}")
        czesci.append(f"#strong[#{_ciag(dopasowanie.group(1))}]")
        pozycja = dopasowanie.end()
    if pozycja < len(tekst):
        czesci.append(f"#{_ciag(tekst[pozycja:], obetnij=False)}")
    return "".join(czesci) or '#""'


class Para(ToolInput):
    etykieta: str = Field(max_length=80, description="Nazwa pozycji, np. „Telefon”, „Termin”.")
    wartosc: str = Field(max_length=400, description="Wartość pozycji, np. „+48 22 000 00 00”.")


class Blok(ToolInput):
    rodzaj: Literal["akapit", "lista", "numeracja", "tabela", "dane", "cytat", "ramka", "nowa_strona"] = (
        Field(
            description="Rodzaj treści: akapit, lista punktowana, numeracja, tabela, pary "
            "etykieta–wartość, cytat, ramka z wyróżnieniem albo przejście na nową stronę."
        )
    )
    tekst: str = Field(
        default="",
        max_length=20_000,
        description="Treść akapitu, cytatu albo ramki. Pusty wiersz rozdziela akapity, "
        "**dwie gwiazdki** pogrubiają fragment.",
    )
    punkty: list[str] = Field(
        default_factory=list, max_length=100, description="Pozycje listy albo numeracji."
    )
    naglowki: list[str] = Field(
        default_factory=list, max_length=10, description="Nagłówki kolumn tabeli (od 1 do 10)."
    )
    wiersze: list[list[str]] = Field(
        default_factory=list,
        max_length=300,
        description="Wiersze tabeli; każdy ma tyle komórek, ile jest nagłówków.",
    )
    pary: list[Para] = Field(
        default_factory=list,
        max_length=40,
        description="Pary etykieta–wartość: dane kontaktowe, parametry, podsumowanie kwot.",
    )


class Sekcja(ToolInput):
    naglowek: str = Field(default="", max_length=200, description="Tytuł sekcji (pusty = bez nagłówka).")
    poziom: int = Field(default=1, ge=1, le=3, description="Stopień nagłówka: 1 — rozdział, 2 i 3 — niżej.")
    bloki: list[Blok] = Field(
        default_factory=list, max_length=80, description="Treść sekcji w kolejności składu."
    )


class SkladInput(ToolInput):
    szablon: Literal["raport", "oferta", "cv", "broszura", "plakat"] = Field(
        description="Układ strony: raport (A4, tekst ciągły), oferta (A4, tabele i kwoty), "
        "cv (A4, kolumna z danymi obok treści), broszura (A4, dwie szpalty), "
        "plakat (A3, duży tytuł i hasła)."
    )
    tytul: str = Field(min_length=1, max_length=200, description="Tytuł dokumentu; w CV imię i nazwisko.")
    podtytul: str = Field(
        default="", max_length=300, description="Wiersz pod tytułem; w CV stanowisko, na plakacie hasło."
    )
    autor: str = Field(default="", max_length=120, description="Nadawca: firma albo osoba.")
    adresat: str = Field(default="", max_length=300, description="Odbiorca (oferta, pismo).")
    data: str = Field(default="", max_length=60, description="Data w postaci gotowej do druku.")
    kontakt: list[Para] = Field(
        default_factory=list,
        max_length=12,
        description="Dane kontaktowe: w CV kolumna boczna, w ofercie blok pod nagłówkiem.",
    )
    sekcje: list[Sekcja] = Field(min_length=1, max_length=60, description="Treść dokumentu.")
    stopka: str = Field(default="", max_length=300, description="Wiersz stopki na każdej stronie.")
    kolor: str = Field(default="#1F3A5F", max_length=7, description="Barwa wiodąca w zapisie „#RRGGBB”.")
    nazwa: str = Field(default="dokument", max_length=80, description="Nazwa pliku bez rozszerzenia.")
    numeruj_strony: bool = Field(default=True, description="Numer strony w stopce.")


#: Parametry typograficzne szablonów: papier, marginesy, kroje, stopień pisma i skala
#: nagłówka rozdziału (na plakacie nagłówek ma być widoczny z drugiego końca sali).
SZABLONY: dict[str, dict[str, str]] = {
    "raport": {
        "papier": "a4",
        "margines": "(x: 24mm, y: 22mm)",
        "tekst": '("Literata", "DejaVu Serif")',
        "naglowki": '("IBM Plex Sans", "DejaVu Sans")',
        "stopien": "10.5pt",
        "naglowek": "1.35em",
    },
    "oferta": {
        "papier": "a4",
        "margines": "(x: 22mm, top: 20mm, bottom: 24mm)",
        "tekst": '("IBM Plex Sans", "DejaVu Sans")',
        "naglowki": '("IBM Plex Sans", "DejaVu Sans")',
        "stopien": "10.5pt",
        "naglowek": "1.35em",
    },
    "cv": {
        "papier": "a4",
        "margines": "(x: 18mm, y: 16mm)",
        "tekst": '("IBM Plex Sans", "DejaVu Sans")',
        "naglowki": '("IBM Plex Sans", "DejaVu Sans")',
        "stopien": "10pt",
        "naglowek": "1.3em",
    },
    "broszura": {
        "papier": "a4",
        "margines": "(x: 18mm, y: 18mm)",
        "tekst": '("Source Serif 4", "DejaVu Serif")',
        "naglowki": '("Archivo", "DejaVu Sans")',
        "stopien": "10pt",
        "naglowek": "1.3em",
    },
    "plakat": {
        "papier": "a3",
        "margines": "(x: 26mm, y: 30mm)",
        "tekst": '("Archivo", "DejaVu Sans")',
        "naglowki": '("Archivo", "DejaVu Sans")',
        "stopien": "20pt",
        "naglowek": "1.7em",
    },
}


def _akapity(tekst: str) -> list[str]:
    """Rozdziela treść bloku na akapity (pusty wiersz = nowy akapit)."""
    return [fragment for fragment in re.split(r"\n\s*\n", tekst) if fragment.strip()]


def _tabela(blok: Blok) -> str:
    """Tabela Typsta z nagłówkiem na barwie wiodącej i naprzemiennym tłem wierszy."""
    if not blok.naglowki:
        raise ToolError("Tabela potrzebuje nagłówków kolumn (pole naglowki).")
    for numer, wiersz in enumerate(blok.wiersze, 1):
        if len(wiersz) != len(blok.naglowki):
            raise ToolError(
                f"Wiersz {numer} tabeli ma {len(wiersz)} komórek, a nagłówków jest {len(blok.naglowki)}."
            )
    kolumny = ", ".join(["1fr"] + ["auto"] * (len(blok.naglowki) - 1))
    naglowek = ", ".join(f"[#strong[#{_ciag(tekst)}]]" for tekst in blok.naglowki)
    wiersze = "\n".join(
        "  " + ", ".join(f"[{_tresc(komorka)}]" for komorka in wiersz) + "," for wiersz in blok.wiersze
    )
    return (
        "#table(\n"
        f"  columns: ({kolumny}),\n"
        "  stroke: none,\n"
        "  inset: (x: 8pt, y: 6pt),\n"
        "  fill: (x, y) => if y == 0 { akcent.lighten(86%) } else if calc.odd(y) { luma(248) },\n"
        f"  table.header({naglowek}),\n"
        f"{wiersze}\n"
        ")\n"
    )


def _pary(pary: list[Para], stopien: str = "10pt") -> str:
    """Pary etykieta–wartość w dwóch kolumnach."""
    komorki = "\n".join(
        f"  [#text(fill: luma(105))[#{_ciag(para.etykieta)}]], [{_tresc(para.wartosc)}]," for para in pary
    )
    return (
        f"#block(width: 100%)[#set text(size: {stopien})\n"
        "#grid(columns: (auto, 1fr), column-gutter: 10pt, row-gutter: 5pt,\n"
        f"{komorki}\n)]\n"
    )


def _blok(blok: Blok) -> str:
    """Jeden blok treści zamieniony na źródło Typsta."""
    if blok.rodzaj == "nowa_strona":
        return "#pagebreak(weak: true)\n"
    if blok.rodzaj == "tabela":
        return _tabela(blok)
    if blok.rodzaj == "dane":
        if not blok.pary:
            raise ToolError("Blok „dane” potrzebuje par etykieta–wartość (pole pary).")
        return _pary(blok.pary)
    if blok.rodzaj in {"lista", "numeracja"}:
        if not blok.punkty:
            raise ToolError(f"Blok „{blok.rodzaj}” potrzebuje pozycji (pole punkty).")
        funkcja = "list" if blok.rodzaj == "lista" else "enum"
        pozycje = ", ".join(f"[{_tresc(punkt)}]" for punkt in blok.punkty)
        return f"#{funkcja}(spacing: 0.75em, {pozycje})\n"
    if not blok.tekst.strip():
        raise ToolError(f"Blok „{blok.rodzaj}” jest pusty (pole tekst).")
    wnetrze = "\n\n".join(_tresc(akapit) for akapit in _akapity(blok.tekst))
    if blok.rodzaj == "cytat":
        return (
            "#block(width: 100%, inset: (left: 12pt, y: 2pt), stroke: (left: 2pt + akcent))"
            f"[#emph[{wnetrze}]]\n"
        )
    if blok.rodzaj == "ramka":
        return f"#block(width: 100%, fill: akcent.lighten(92%), inset: 11pt, radius: 3pt)[{wnetrze}]\n"
    return wnetrze + "\n\n"


def _sekcje(sekcje: list[Sekcja]) -> str:
    """Treść dokumentu: nagłówki i bloki w kolejności podanej przez model."""
    czesci: list[str] = []
    for sekcja in sekcje:
        if sekcja.naglowek.strip():
            czesci.append(f"#heading(level: {sekcja.poziom})[#{_ciag(sekcja.naglowek)}]\n")
        czesci.extend(_blok(blok) for blok in sekcja.bloki)
    return "\n".join(czesci)


def _naglowek_dokumentu(args: SkladInput) -> str:
    """Blok tytułowy zależny od szablonu."""
    tytul = _ciag(args.tytul)
    podtytul = _ciag(args.podtytul)
    if args.szablon == "plakat":
        czesci = [
            "#align(center)[",
            "#set par(justify: false)",
            f"#text(size: 54pt, weight: 700, fill: akcent, hyphenate: false)[#{tytul}]",
            "#v(10pt)",
            f"#text(size: 22pt, fill: luma(70))[#{podtytul}]" if args.podtytul else "",
            "#v(12pt) #line(length: 40%, stroke: 3pt + akcent)",
            "]",
            "#v(22pt)",
        ]
        return "\n".join(part for part in czesci if part) + "\n"
    if args.szablon == "cv":
        czesci = [
            f"#text(font: naglowki, size: 26pt, weight: 600, fill: akcent, hyphenate: false)[#{tytul}]",
            f"#v(1pt)\n#text(font: naglowki, size: 12pt, fill: luma(90))[#{podtytul}]"
            if args.podtytul
            else "",
            "#v(6pt)\n#line(length: 100%, stroke: 1.2pt + akcent)",
            "#v(10pt)",
        ]
        return "\n".join(part for part in czesci if part) + "\n"
    # Raport, oferta i broszura: pasek z barwą wiodącą i wiersz metryki pod nim.
    metryka = []
    if args.autor:
        metryka.append(f"#{_ciag(args.autor)}")
    if args.adresat:
        metryka.append(f"#{_ciag('Dla: ' + args.adresat)}")
    if args.data:
        metryka.append(f"#{_ciag(args.data)}")
    wiersz = " #h(1fr) ".join(metryka)
    czesci = [
        "#block(width: 100%, fill: akcent, inset: (x: 14pt, y: 16pt), radius: 2pt)[",
        "  #set par(justify: false)",
        f"  #text(font: naglowki, fill: white, size: 23pt, weight: 600, hyphenate: false)[#{tytul}]",
        f"  #v(3pt)\n  #text(font: naglowki, fill: white.darken(12%), size: 11.5pt)[#{podtytul}]"
        if args.podtytul
        else "",
        "]",
        f"#v(7pt)\n#text(size: 9pt, fill: luma(95))[{wiersz}]" if wiersz else "",
        "#v(10pt)",
    ]
    return "\n".join(part for part in czesci if part) + "\n"


def _stopka_strony(args: SkladInput) -> str:
    """Ustawienie stopki: tekst stopki po lewej, numer strony po prawej."""
    if not args.stopka and not args.numeruj_strony:
        return ""
    lewa = f"#{_ciag(args.stopka)} #h(1fr) " if args.stopka else "#h(1fr) "
    prawa = "#context counter(page).display()" if args.numeruj_strony else ""
    return f"#set page(footer: context [\n  #set text(size: 8.5pt, fill: luma(115))\n  {lewa}{prawa}\n])\n"


def _zrodlo(args: SkladInput) -> str:
    """Kompletne źródło Typsta: ustawienia szablonu, blok tytułowy i treść."""
    szablon = SZABLONY[args.szablon]
    tresc = _sekcje(args.sekcje)
    if args.szablon == "broszura":
        tresc = f"#columns(2, gutter: 16pt)[\n{tresc}\n]\n"
    elif args.szablon == "cv" and args.kontakt:
        tresc = (
            "#grid(columns: (30%, 1fr), column-gutter: 16pt,\n"
            f"  [{_pary(args.kontakt, '9.5pt')}],\n"
            f"  [{tresc}]\n)\n"
        )
    elif args.kontakt:
        tresc = _pary(args.kontakt) + "\n" + tresc
    if args.szablon == "plakat":
        # Plakat czyta się z odległości: tekst wyśrodkowany w węższej kolumnie, listy bez
        # punktorów, które przy środkowaniu odrywają się od wiersza.
        tresc = (
            "#align(center)[#block(width: 78%)[\n"
            "#set par(justify: false)\n"
            "#set align(center)\n"
            "#set list(marker: [], indent: 0pt, body-indent: 0pt, spacing: 1.1em)\n"
            f"{tresc}\n]]\n"
        )
    czesci = [
        f"#let akcent = rgb({_ciag(args.kolor)})",
        f"#let naglowki = {szablon['naglowki']}",
        f"#set document(title: {_ciag(args.tytul)}, author: {_ciag(args.autor or 'Danaco Nexus')})",
        f"#set page(paper: {_ciag(szablon['papier'])}, margin: {szablon['margines']})",
        _stopka_strony(args),
        f'#set text(font: {szablon["tekst"]}, size: {szablon["stopien"]}, lang: "pl", hyphenate: true)',
        "#set par(justify: true, leading: 0.72em, spacing: 1.05em)",
        "#show heading: set text(font: naglowki, fill: akcent)",
        "#show heading.where(level: 1): it => block(above: 1.5em, below: 0.7em, width: 100%)[",
        f"  #text(size: {szablon['naglowek']}, weight: 600)[#it.body]",
        "  #v(-0.45em)",
        "  #line(length: 100%, stroke: 0.6pt + akcent.lighten(55%))",
        "]",
        "#show heading.where(level: 2): set text(size: 1.12em, weight: 600)",
        "#show heading.where(level: 3): set text(size: 1em, weight: 600)",
        "#show table.cell.where(y: 0): set text(fill: akcent.darken(20%))",
        "",
        _naglowek_dokumentu(args),
        tresc,
    ]
    return "\n".join(czesc for czesc in czesci if czesc)


@registry.register(
    "typeset_document",
    """Składa dokument do druku programem Typst: raport, oferta handlowa, CV, broszura
albo plakat tekstowy. Treść podajesz w sekcjach i blokach (akapit, lista, tabela, pary
etykieta–wartość, cytat, ramka), a narzędzie dba o typografię: kroje, światło, tabele,
nagłówki, numerację stron i barwę wiodącą. Używaj go zawsze, gdy PDF ma wyglądać
zawodowo — write_document daje zwykły wydruk z edytora tekstu, a convert_documents
tylko przepuszcza gotowy plik przez LibreOffice.""",
    SkladInput,
)
def typeset_document(ctx: ToolContext, args: SkladInput) -> ToolResult:
    program = _program("typst", "Skład dokumentów (Typst)")
    if not BARWA.match(args.kolor):
        raise ToolError(f"Barwa wiodąca musi mieć postać „#RRGGBB”, a jest {args.kolor!r}.")
    znakow = len(args.tytul) + sum(
        len(blok.tekst) + sum(map(len, blok.punkty)) for sekcja in args.sekcje for blok in sekcja.bloki
    )
    if znakow > MAX_ZNAKOW_SKLADU:
        raise ToolError("Dokument jest za długi do jednego składu — podziel go na części.")

    rdzen = safe_filename(args.nazwa, "dokument").rsplit(".", 1)[0] or "dokument"
    zrodlo = ctx.output_path(f"{rdzen}.typ")
    zrodlo.write_text(_zrodlo(args), encoding="utf-8")
    cel = zrodlo.with_suffix(".pdf")
    polecenie = [program, "compile", "--root", str(zrodlo.parent)]
    if KATALOG_KROJOW.is_dir():
        polecenie += ["--font-path", str(KATALOG_KROJOW)]
    ctx.progress(f"Skład dokumentu: {args.szablon}")
    ctx.run_command([*polecenie, str(zrodlo), str(cel)], timeout=CZAS_SKLAD)
    if not cel.is_file():
        raise ToolError("Skład nie dał pliku PDF.")

    podglady: list[bytes] = []
    stron = 0
    with pymupdf.open(cel) as dokument:
        stron = dokument.page_count
        for numer in range(min(stron, PODGLAD_STRON)):
            podglady.append(image_preview(render_pdf_page(dokument, numer, PODGLAD)))
    return ToolResult(
        {"output": cel.name, "szablon": args.szablon, "stron": stron},
        f"Złożono „{args.tytul}” ({args.szablon}, {stron} s.)",
        images=podglady,
        files=[OutputFile(cel, cel.name, "Dokument złożony do druku (PDF)")],
    )


# --- konwersje pandoc ----------------------------------------------------------------------

#: Czytniki pandoca po rozszerzeniu pliku źródłowego.
CZYTNIKI = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "markdown",
    ".html": "html",
    ".htm": "html",
    ".docx": "docx",
    ".odt": "odt",
    ".epub": "epub",
    ".tex": "latex",
    ".rst": "rst",
    ".org": "org",
    ".ipynb": "ipynb",
    ".csv": "csv",
}
#: Formaty wynikowe: zapis pandoca i rozszerzenie pliku.
CELE = {
    "epub": ("epub3", ".epub"),
    "markdown": ("gfm", ".md"),
    "latex": ("latex", ".tex"),
    "html": ("html5", ".html"),
    "docx": ("docx", ".docx"),
    "odt": ("odt", ".odt"),
    "rst": ("rst", ".rst"),
    "org": ("org", ".org"),
    "typst": ("typst", ".typ"),
    "plain": ("plain", ".txt"),
    "pdf": ("pdf", ".pdf"),
}
#: Formaty, w których wstawka surowego kodu mogłaby się wykonać przy składzie.
CELE_WYKONYWALNE = frozenset({"pdf", "latex", "typst"})
SAMODZIELNE = frozenset({"epub", "html", "latex", "pdf", "docx", "odt"})


class KonwersjaInput(ToolInput):
    file_id: str | None = Field(
        default=None, description="Plik do przekształcenia (Markdown, HTML, DOCX, ODT, EPUB, LaTeX, RST)."
    )
    tekst: str | None = Field(
        default=None,
        max_length=800_000,
        description="Treść w Markdownie napisana przez Ciebie, gdy nie ma pliku źródłowego.",
    )
    format_docelowy: Literal[
        "epub", "markdown", "latex", "html", "docx", "odt", "rst", "org", "typst", "plain", "pdf"
    ] = Field(description="Format wynikowy.")
    tytul: str = Field(default="", max_length=200, description="Tytuł dokumentu (wymagany przez EPUB).")
    autor: str = Field(default="", max_length=120, description="Autor zapisywany w metadanych.")
    jezyk: str = Field(default="pl", max_length=5, description="Kod języka metadanych, np. „pl”, „en”.")
    spis_tresci: bool = Field(default=False, description="Dołącz spis treści (EPUB, HTML, PDF).")
    nazwa: str = Field(default="", max_length=80, description="Nazwa pliku wynikowego bez rozszerzenia.")


def _zrodlo_konwersji(ctx: ToolContext, args: KonwersjaInput) -> tuple[Path, str, str]:
    """Plik źródłowy, czytnik pandoca i nazwa dla wyniku."""
    if args.file_id:
        nazwa, kopia = _kopia_robocza(ctx, args.file_id)
        czytnik = CZYTNIKI.get(Path(nazwa).suffix.lower())
        if not czytnik:
            raise ToolError(
                f"{nazwa}: pandoc nie czyta tego rodzaju pliku. "
                "Dokumenty biurowe i PDF otwórz narzędziem extract_text albo convert_documents."
            )
        return kopia, czytnik, Path(nazwa).stem
    if not (args.tekst or "").strip():
        raise ToolError("Podaj file_id albo tekst do przekształcenia.")
    kopia = ctx.output_path("tresc.md")
    kopia.write_text(args.tekst or "", encoding="utf-8")
    return kopia, "markdown", "dokument"


@registry.register(
    "convert_text_format",
    """Przekształca tekst między formatami wydawniczymi programem pandoc: Markdown, HTML,
LaTeX, reStructuredText, Org, Typst, DOCX, ODT i — przede wszystkim — EPUB, czyli
książkę do czytnika. Stąd bierze się e-book z napisanego tekstu, plik LaTeX do czasopisma
i czysty Markdown z DOCX-a razem ze strukturą nagłówków. Do zwykłej zamiany dokumentu
biurowego na PDF czy DOCX służy convert_documents (LibreOffice), a do składu do druku —
typeset_document.""",
    KonwersjaInput,
)
def convert_text_format(ctx: ToolContext, args: KonwersjaInput) -> ToolResult:
    program = _program("pandoc", "Konwersje formatów tekstowych (pandoc)")
    zapis, rozszerzenie = CELE[args.format_docelowy]
    zrodlo, czytnik, rdzen = _zrodlo_konwersji(ctx, args)
    if args.format_docelowy == "pdf":
        _program("typst", "Skład PDF (Typst)")
    # Wstawki surowego kodu (```{=typst}, \input) omijają czytnik i trafiają prosto do składu,
    # dlatego przy formatach wykonywalnych są wyłączone; --sandbox odcina dostęp do plików.
    if czytnik == "markdown":
        czytnik += "-raw_attribute" + ("-raw_tex" if args.format_docelowy in CELE_WYKONYWALNE else "")
    elif czytnik in {"html", "latex"} and args.format_docelowy in CELE_WYKONYWALNE:
        czytnik += "-raw_html" if czytnik == "html" else "-raw_tex"

    nazwa = safe_filename(args.nazwa or rdzen, "dokument").rsplit(".", 1)[0] or "dokument"
    cel = ctx.output_path(f"{nazwa}{rozszerzenie}")
    polecenie = [
        program,
        "--sandbox",
        "--from",
        czytnik,
        "--to",
        zapis,
        "--output",
        str(cel),
        "--metadata",
        f"title={args.tytul or nazwa}",
        "--metadata",
        f"lang={args.jezyk}",
    ]
    if args.autor:
        polecenie += ["--metadata", f"author={args.autor}"]
    if args.format_docelowy in SAMODZIELNE:
        polecenie.append("--standalone")
    if args.spis_tresci:
        polecenie.append("--toc")
    if args.format_docelowy == "pdf":
        polecenie.append("--pdf-engine=typst")
    ctx.progress(f"Konwersja do {args.format_docelowy.upper()}")
    ctx.run_command([*polecenie, str(zrodlo)], timeout=CZAS_KONWERSJA)
    if not cel.is_file():
        raise ToolError(f"Pandoc nie utworzył pliku {args.format_docelowy.upper()}.")
    dane: dict[str, Any] = {"output": cel.name, "format": args.format_docelowy, "bajtow": cel.stat().st_size}
    if args.format_docelowy in {"markdown", "rst", "org", "plain", "typst", "latex"}:
        dane["text"], skrocono = truncate_text(cel.read_text(encoding="utf-8", errors="replace"))
        if skrocono:
            dane["note"] = "Treść skrócona — pełna jest w pliku wynikowym."
    return ToolResult(
        dane,
        f"Konwersja do {args.format_docelowy.upper()}: {cel.name}",
        files=[OutputFile(cel, cel.name, f"Plik {args.format_docelowy.upper()}")],
    )


# --- rozbiór struktury dokumentu -------------------------------------------------------------


class StrukturaInput(ToolInput):
    file_id: str = Field(description="PDF, skan, obraz strony, DOCX, PPTX, XLSX albo HTML.")
    ocr: Literal["auto", "wymus", "pomin"] = Field(
        default="auto",
        description="auto — OCR tylko tam, gdzie brak tekstu; wymus — cały dokument przez OCR "
        "(PDF ze złą warstwą tekstową); pomin — wyłącznie istniejąca warstwa tekstowa.",
    )
    jezyk: str = Field(default="pl", max_length=20, description="Języki OCR, np. „pl” albo „pl,en”.")
    tabele: Literal["dokladnie", "szybko", "pomin"] = Field(
        default="dokladnie", description="Jak rozpoznawać strukturę tabel."
    )


@registry.register(
    "analyze_document_structure",
    """Rozbiera dokument na strukturę programem Docling: nagłówki, akapity w kolejności
czytania i tabele odtworzone jako dane. Oddaje Markdown i pełny opis w JSON, więc nadaje
się do umowy, faktury, sprawozdania i skanu, z którego trzeba wyjąć tabelę, a nie samo
zdanie. Do szybkiego odczytu treści wystarczy extract_text, a do wgrania warstwy tekstowej
w skan — ocr_documents; to narzędzie bierz wtedy, gdy liczy się układ i tabele.""",
    StrukturaInput,
)
def analyze_document_structure(ctx: ToolContext, args: StrukturaInput) -> ToolResult:
    program = _program("danaco-dokument-na-tekst", "Rozbiór struktury dokumentu (Docling)")
    plik = ctx.file(args.file_id)
    if file_kind(plik) not in {"pdf", "image", "office", "text"}:
        raise ToolError(f"{plik.name} nie jest dokumentem ani obrazem strony.")
    if not re.fullmatch(r"[a-z]{2}(,[a-z]{2}){0,3}", args.jezyk):
        raise ToolError(
            f"Nieprawidłowy zapis języków OCR: {args.jezyk!r} — oczekiwano np. „pl” albo „pl,en”."
        )
    nazwa, kopia = _kopia_robocza(ctx, args.file_id)
    katalog = kopia.parent
    polecenie = [program, "-o", str(katalog), "--jezyk", args.jezyk]
    polecenie += {"auto": [], "wymus": ["--ocr"], "pomin": ["--bez-ocr"]}[args.ocr]
    polecenie += {"dokladnie": ["--tabele"], "szybko": ["--tabele-szybko"], "pomin": ["--bez-tabel"]}[
        args.tabele
    ]
    ctx.progress(f"Rozbiór dokumentu: {nazwa}")
    ctx.run_command([*polecenie, str(kopia)], timeout=CZAS_STRUKTURA)

    markdown = katalog / f"{kopia.stem}.md"
    opis = katalog / f"{kopia.stem}.json"
    if not markdown.is_file():
        raise ToolError(f"Rozbiór {nazwa} nie dał wyniku tekstowego.")
    tresc = markdown.read_text(encoding="utf-8", errors="replace")
    dane: dict[str, Any] = {"file": nazwa}
    if opis.is_file():
        try:
            struktura = json.loads(opis.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            struktura = {}
        dane["tabel"] = len(struktura.get("tables") or [])
        dane["stron"] = len(struktura.get("pages") or {}) or None
    dane["naglowki"] = [wiersz.strip() for wiersz in tresc.splitlines() if wiersz.startswith("#")][:60]
    dane["markdown"], skrocono = truncate_text(tresc)
    if skrocono:
        dane["note"] = "Markdown skrócony — pełna treść jest w pliku wynikowym."
    wyniki = [OutputFile(markdown, with_suffix(nazwa, ".md", "_struktura"), "Dokument jako Markdown")]
    if opis.is_file():
        wyniki.append(OutputFile(opis, with_suffix(nazwa, ".json", "_struktura"), "Struktura dokumentu"))
    podsumowanie = f"Rozbiór {nazwa}: {dane.get('tabel', 0)} tab., {len(tresc)} znaków"
    return ToolResult(dane, podsumowanie, files=wyniki)


# --- transkrypcja ze słowami i mówcami --------------------------------------------------------


class MowcyInput(ToolInput):
    file_id: str = Field(description="Nagranie audio albo wideo z rozmową.")
    jezyk: str = Field(default="pl", max_length=10, description="Kod języka mowy albo „auto”.")
    model: Literal["turbo", "medium", "small"] = Field(
        default="turbo", description="turbo — najdokładniejszy; small — najszybszy."
    )
    mowcy: bool = Field(default=True, description="Rozdziel wypowiedzi na mówców (kto co powiedział).")
    liczba_mowcow: int | None = Field(
        default=None, ge=1, le=12, description="Dokładna liczba rozmówców, jeżeli jest znana."
    )
    formaty: list[Literal["txt", "srt", "json"]] = Field(
        default_factory=lambda: ["txt", "srt"],
        max_length=3,
        description="txt — zapis rozmowy, srt — napisy, json — czasy każdego słowa.",
    )


@registry.register(
    "transcribe_speakers",
    """Spisuje rozmowę z podziałem na mówców i z czasem każdego wypowiedzianego słowa
(WhisperX). Bierz to narzędzie do spotkania, wywiadu, rozprawy i podcastu, czyli wszędzie
tam, gdzie trzeba wiedzieć, kto powiedział które zdanie, albo dociąć napisy co do słowa.
Do zwykłego spisania nagrania jednej osoby szybsze jest transcribe_audio.""",
    MowcyInput,
)
def transcribe_speakers(ctx: ToolContext, args: MowcyInput) -> ToolResult:
    program = _program("danaco-transkrypcja", "Transkrypcja z podziałem na mówców")
    plik = ctx.file(args.file_id)
    if file_kind(plik) not in {"audio", "video"}:
        raise ToolError(f"{plik.name} nie jest nagraniem audio ani wideo.")
    jezyk = args.jezyk.strip().lower() or "pl"
    if not jezyk.isalpha():
        raise ToolError(f"Nieprawidłowy kod języka: {args.jezyk!r}")
    if args.mowcy and not ZNACZNIK_MOWCOW.is_file():
        raise ToolError(
            "Podział na mówców nie jest jeszcze przygotowany na tym serwerze — model pobiera "
            "jednorazowo administrator. Bez niego spiszę nagranie bez rozdzielania głosów "
            "(ustaw mowcy = fałsz) albo użyj transcribe_audio."
        )
    nazwa, kopia = _kopia_robocza(ctx, args.file_id)
    katalog = kopia.parent
    polecenie = [
        program,
        str(kopia),
        "-o",
        str(katalog),
        "--jezyk",
        jezyk,
        "--model",
        args.model,
        "--watki",
        str(max(1, ctx.settings.tool_threads)),
    ]
    if args.mowcy:
        polecenie.append("--mowcy")
    if args.liczba_mowcow:
        polecenie += ["--liczba-mowcow", str(args.liczba_mowcow)]
    ctx.progress(f"Spisywanie rozmowy: {nazwa}")
    ctx.run_command(polecenie, timeout=CZAS_TRANSKRYPCJA)

    opis = katalog / f"{kopia.stem}.json"
    if not opis.is_file():
        raise ToolError(f"Transkrypcja {nazwa} nie dała wyniku.")
    wynik = json.loads(opis.read_text(encoding="utf-8", errors="replace"))
    segmenty = wynik.get("segmenty") or []
    glosy = sorted({segment["speaker"] for segment in segmenty if segment.get("speaker")})
    wyniki: list[OutputFile] = []
    for format_pliku in dict.fromkeys(args.formaty):
        plik_wyniku = katalog / f"{kopia.stem}.{format_pliku}"
        if plik_wyniku.is_file():
            wyniki.append(
                OutputFile(
                    plik_wyniku,
                    with_suffix(nazwa, f".{format_pliku}", "_rozmowa"),
                    f"Transkrypcja ({format_pliku.upper()})",
                )
            )
    zapis = (katalog / f"{kopia.stem}.txt").read_text(encoding="utf-8", errors="replace")
    tekst, skrocono = truncate_text(zapis)
    dane: dict[str, Any] = {
        "file": nazwa,
        "jezyk": wynik.get("jezyk"),
        "czas_nagrania_s": wynik.get("czas_nagrania_s"),
        "czasy_slow": wynik.get("wyrownanie_slow"),
        "mowcy": glosy,
        "segmentow": len(segmenty),
        "transcript": tekst,
    }
    if skrocono:
        dane["note"] = "Zapis skrócony — pełny jest w pliku wynikowym."
    minuty = (wynik.get("czas_nagrania_s") or 0) / 60
    return ToolResult(
        dane,
        f"Rozmowa {nazwa}: {minuty:.1f} min, {len(glosy) or 1} mówc. , {len(segmenty)} wypowiedzi",
        files=wyniki,
    )


# --- napisy ------------------------------------------------------------------------------------


class NapisyInput(ToolInput):
    file_id: str = Field(description="Plik napisów SRT.")
    operacja: Literal["przesun", "dopasuj", "scal", "usun_duplikaty", "uporzadkuj"] = Field(
        description="przesun — o stałą liczbę sekund; dopasuj — rozciągnij czasy między dwoma "
        "punktami; scal — połącz z drugim plikiem napisów; usun_duplikaty; uporzadkuj — napraw "
        "uszkodzony plik."
    )
    sekundy: float = Field(
        default=0.0, ge=-7200, le=7200, description="Przesunięcie w sekundach (ujemne = wcześniej)."
    )
    od_pierwszy: str = Field(default="", max_length=20, description="Zły czas pierwszej kwestii.")
    na_pierwszy: str = Field(default="", max_length=20, description="Właściwy czas pierwszej kwestii.")
    od_ostatni: str = Field(default="", max_length=20, description="Zły czas ostatniej kwestii.")
    na_ostatni: str = Field(default="", max_length=20, description="Właściwy czas ostatniej kwestii.")
    file_id_drugi: str | None = Field(default=None, description="Drugi plik napisów przy operacji „scal”.")


def _plik_napisow(ctx: ToolContext, file_id: str) -> tuple[str, Path]:
    plik = ctx.file(file_id)
    if plik.suffix != ".srt":
        raise ToolError(
            f"{plik.name} nie jest plikiem napisów SRT. Napisy VTT zamień najpierw na SRT "
            "(transcribe_audio oddaje oba formaty)."
        )
    return plik.name, plik.path


def _czas(wartosc: str, pole: str) -> str:
    """Znacznik czasu napisów: „00:01:02,500” albo liczba sekund."""
    oczyszczony = wartosc.strip()
    if not ZNACZNIK_CZASU.match(oczyszczony):
        raise ToolError(f"Pole {pole} ma być czasem „00:01:02,500” albo liczbą sekund, a jest {wartosc!r}.")
    return oczyszczony


@registry.register(
    "edit_subtitles",
    """Poprawia gotowy plik napisów SRT: przesuwa czasy o stałą wartość, rozciąga je liniowo,
gdy napisy rozjeżdżają się do końca filmu, łączy dwie wersje językowe w jeden plik, usuwa
powtórzone kwestie i naprawia uszkodzony zapis. Do wytworzenia napisów z nagrania służą
transcribe_audio i transcribe_speakers — to narzędzie pracuje na istniejącym pliku.""",
    NapisyInput,
)
def edit_subtitles(ctx: ToolContext, args: NapisyInput) -> ToolResult:
    program = _program("srt", "Obróbka napisów")
    nazwa, sciezka = _plik_napisow(ctx, args.file_id)
    cel = ctx.output_path(with_suffix(nazwa, ".srt", "_poprawione"))
    wejscia = ["-i", str(sciezka)]
    if args.operacja == "przesun":
        if not args.sekundy:
            raise ToolError("Podaj, o ile sekund przesunąć napisy (pole sekundy).")
        polecenie = [program, "fixed-timeshift", "--seconds", f"{args.sekundy:g}"]
    elif args.operacja == "dopasuj":
        polecenie = [
            program,
            "linear-timeshift",
            "--from-start",
            _czas(args.od_pierwszy, "od_pierwszy"),
            "--to-start",
            _czas(args.na_pierwszy, "na_pierwszy"),
            "--from-end",
            _czas(args.od_ostatni, "od_ostatni"),
            "--to-end",
            _czas(args.na_ostatni, "na_ostatni"),
        ]
    elif args.operacja == "scal":
        if not args.file_id_drugi:
            raise ToolError("Scalanie potrzebuje drugiego pliku napisów (pole file_id_drugi).")
        _, druga = _plik_napisow(ctx, args.file_id_drugi)
        polecenie = [program, "mux"]
        wejscia = ["-i", str(sciezka), str(druga)]
    elif args.operacja == "usun_duplikaty":
        polecenie = [program, "deduplicate"]
    else:
        polecenie = [program, "normalise"]
    ctx.progress(f"Napisy: {args.operacja}")
    ctx.run_command([*polecenie, *wejscia, "-o", str(cel), "--ignore-parsing-errors"], timeout=CZAS_NAPISY)
    if not cel.is_file():
        raise ToolError("Obróbka napisów nie dała pliku wynikowego.")
    tresc = cel.read_text(encoding="utf-8", errors="replace")
    kwestii = len(re.findall(r"-->", tresc))
    return ToolResult(
        {"output": cel.name, "operacja": args.operacja, "kwestii": kwestii},
        f"Napisy {nazwa}: {args.operacja}, {kwestii} kwestii",
        files=[OutputFile(cel, cel.name, "Poprawione napisy")],
    )


# --- czytanie dokumentu na głos ------------------------------------------------------------------


class CzytanieInput(ToolInput):
    file_id: str | None = Field(
        default=None, description="Dokument do przeczytania (PDF z tekstem, DOCX, ODT, TXT, MD, HTML)."
    )
    tekst: str | None = Field(
        default=None, max_length=MAX_ZNAKOW_CZYTANIA, description="Tekst do przeczytania, gdy nie ma pliku."
    )
    glos: str = Field(default="", max_length=60, description="Identyfikator głosu; pusty = głos domyślny.")
    tempo: float = Field(default=1.0, ge=0.6, le=1.6, description="Tempo mowy (1,0 = naturalne).")
    format_wyniku: Literal["mp3", "wav"] = Field(
        default="mp3", description="mp3 waży kilkanaście razy mniej; wav jest bezstratny."
    )
    nazwa: str = Field(default="", max_length=80, description="Nazwa pliku wynikowego bez rozszerzenia.")


def _tekst_do_czytania(ctx: ToolContext, args: CzytanieInput) -> tuple[str, str]:
    """Treść i nazwa dla pliku dźwiękowego."""
    if args.file_id:
        plik = ctx.file(args.file_id)
        rodzaj = file_kind(plik)
        if rodzaj == "pdf":
            with pymupdf.open(plik.path) as dokument:
                tresc = "\n".join(strona.get_text("text") for strona in dokument)
            if len(tresc.strip()) < 30:
                raise ToolError(f"{plik.name} nie ma warstwy tekstowej — najpierw użyj ocr_documents.")
        elif rodzaj == "text":
            tresc = plik.path.read_text(encoding="utf-8", errors="replace")
        elif rodzaj == "office":
            tresc = _tika_text(ctx, plik)
        else:
            raise ToolError(f"{plik.name} nie jest dokumentem tekstowym do przeczytania.")
        return tresc, Path(plik.name).stem
    if not (args.tekst or "").strip():
        raise ToolError("Podaj file_id albo tekst do przeczytania.")
    return args.tekst or "", "nagranie"


def _porcje(tekst: str) -> list[str]:
    """Dzieli tekst na porcje kończące się na granicy zdania."""
    porcje: list[str] = []
    biezaca = ""
    for zdanie in KONIEC_ZDANIA.split(re.sub(r"\s+", " ", tekst).strip()):
        if not zdanie:
            continue
        if len(biezaca) + len(zdanie) + 1 > PORCJA_MOWY and biezaca:
            porcje.append(biezaca)
            biezaca = ""
        biezaca = f"{biezaca} {zdanie}".strip() if biezaca else zdanie[:PORCJA_MOWY]
    if biezaca:
        porcje.append(biezaca)
    return porcje


@registry.register(
    "read_document_aloud",
    """Czyta cały dokument na głos i zapisuje to jako plik dźwiękowy (głosy Piper, po polsku).
Z raportu, umowy, artykułu albo własnego tekstu robi nagranie do odsłuchania w drodze —
audiobook, wersję dla osoby słabowidzącej, ścieżkę lektorską pod film. Rozmowa głosowa
w oknie programu czyta wyłącznie bieżącą odpowiedź; tu powstaje plik z całości.""",
    CzytanieInput,
)
def read_document_aloud(ctx: ToolContext, args: CzytanieInput) -> ToolResult:
    from nexus.voice import VoiceEngine, VoiceUnavailable, spoken_text

    tresc, rdzen = _tekst_do_czytania(ctx, args)
    tresc = spoken_text(tresc)
    if not tresc.strip():
        raise ToolError("W tym materiale nie ma tekstu do przeczytania.")
    if len(tresc) > MAX_ZNAKOW_CZYTANIA:
        raise ToolError(
            f"Tekst ma {len(tresc)} znaków — przeczytam naraz najwyżej {MAX_ZNAKOW_CZYTANIA}. "
            "Podziel dokument na części."
        )
    silnik = VoiceEngine(ctx.settings)
    glosy = [glos["id"] for glos in silnik.local_voices()]
    if not glosy:
        raise ToolError("Na tym serwerze nie ma zainstalowanego głosu do czytania dokumentów.")
    glos = args.glos or ctx.settings.voice_default
    if glos not in glosy:
        glos = glosy[0]

    nazwa = safe_filename(args.nazwa or rdzen, "nagranie").rsplit(".", 1)[0] or "nagranie"
    wav = ctx.output_path(f"{nazwa}.wav")
    porcje = _porcje(tresc)
    parametry_ustawione = False
    with wave.open(str(wav), "wb") as zapis:
        for numer, porcja in enumerate(porcje, 1):
            ctx.check_cancelled()
            if numer == 1 or numer % 10 == 0:
                ctx.progress(f"Czytanie: fragment {numer} z {len(porcje)}")
            try:
                dzwiek, _ = silnik.speak(porcja, glos, args.tempo)
            except (VoiceUnavailable, ValueError) as blad:
                raise ToolError(f"Synteza mowy nie powiodła się: {blad}") from blad
            with wave.open(io.BytesIO(dzwiek), "rb") as odczyt:
                if not parametry_ustawione:
                    zapis.setparams(odczyt.getparams())
                    parametry_ustawione = True
                zapis.writeframes(odczyt.readframes(odczyt.getnframes()))
    if not parametry_ustawione:
        raise ToolError("Synteza mowy nie dała dźwięku.")

    cel = wav
    if args.format_wyniku == "mp3":
        cel = wav.with_suffix(".mp3")
        ctx.progress("Zapis nagrania do MP3")
        ctx.run_command(
            ["ffmpeg", "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "96k", str(cel)],
            timeout=CZAS_DZWIEK,
        )
    with wave.open(str(wav), "rb") as odczyt:
        sekundy = round(odczyt.getnframes() / max(1, odczyt.getframerate()), 1)
    return ToolResult(
        {"output": cel.name, "znakow": len(tresc), "czas_s": sekundy, "glos": glos},
        f"Nagranie {cel.name}: {sekundy / 60:.1f} min",
        files=[OutputFile(cel, cel.name, "Dokument przeczytany na głos")],
    )


__all__ = [
    "analyze_document_structure",
    "convert_text_format",
    "edit_subtitles",
    "read_document_aloud",
    "transcribe_speakers",
    "typeset_document",
]
