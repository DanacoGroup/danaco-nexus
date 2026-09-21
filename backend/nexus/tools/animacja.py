"""Animacja wyjaśniająca: agent pisze scenę Manim, serwer ją renderuje w piaskownicy.

Na serwerze stoi Manim — silnik, którym powstają animowane wyjaśnienia: wykres, który się
rysuje, wzór, który się przekształca, schemat, w którym kolejne elementy wchodzą po kolei.
Do tej pory nie był podpięty do niczego, więc „wytłumacz mi to na animacji” kończyło się
obrazkiem albo tekstem.

Scena to kod Pythona pisany przez model, więc renderowanie idzie przez tę samą piaskownicę,
co sesja programistyczna: proces widzi katalog roboczy zadania i łańcuch narzędzi serwera,
a poza tym nic — i nie ma wyjścia do sieci. Bez piaskownicy narzędzie się nie uruchomi.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import Field

from nexus.agent import piaskownica
from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    registry,
)

MANIM = "/danaco/programy/bin/manim"
# Render jest liczony klatka po klatce; minuta animacji to minuty pracy procesora.
LIMIT_RENDEROWANIA_S = 1200
MAX_SCENA_ZNAKOW = 20_000
JAKOSCI = {"podglad": "-ql", "dobra": "-qh", "wysoka": "-qk"}
NAZWA_KLASY = re.compile(r"^\s*class\s+([A-Za-z_]\w*)\s*\(\s*(?:\w+\.)?Scene\s*\)", re.MULTILINE)
# Wprost zakazane: scena ma rysować, a nie sięgać do systemu. To druga linia po piaskownicy —
# gdyby ktoś ją wyłączył, te wzorce i tak odetną najprostsze próby.
ZAKAZANE = (
    "subprocess",
    "os.system",
    "os.popen",
    "socket",
    "urllib",
    "requests",
    "httpx",
    "__import__",
    "eval(",
    "exec(",
)


class AnimacjaInput(ToolInput):
    scena: str = Field(
        description="Kod sceny Manim w Pythonie: import z manim i jedna klasa dziedzicząca po Scene "
        "z metodą construct. Bez odczytu plików, sieci i uruchamiania programów.",
        max_length=MAX_SCENA_ZNAKOW,
    )
    nazwa: str = Field(
        "animacja", description="Nazwa pliku wynikowego (bez rozszerzenia).", max_length=60
    )
    jakosc: Literal["podglad", "dobra", "wysoka"] = Field(
        "dobra", description="podglad = szybko i mniej dokładnie, dobra = 1080p, wysoka = 4K."
    )


def _klasa_sceny(kod: str) -> str:
    dopasowanie = NAZWA_KLASY.search(kod)
    if dopasowanie is None:
        raise ToolError(
            "W kodzie nie ma klasy dziedziczącej po Scene. Napisz np. "
            "`class Wyjasnienie(Scene):` z metodą `construct(self)`."
        )
    return dopasowanie.group(1)


def _sprawdz_kod(kod: str) -> None:
    znalezione = [wzorzec for wzorzec in ZAKAZANE if wzorzec in kod]
    if znalezione:
        raise ToolError(
            "Scena ma rysować, a nie sięgać do systemu ani do sieci. Usuń: " + ", ".join(znalezione)
        )


@registry.register(
    "animate_explainer",
    """Renderuje animację wyjaśniającą z opisanej sceny (silnik Manim): rysujący się wykres,
przekształcający się wzór, schemat wchodzący element po elemencie, oś czasu, porównanie.
Scenę piszesz sam w Pythonie — jedna klasa dziedzicząca po Scene z metodą construct.
Stosuj, gdy rzecz łatwiej pokazać w ruchu niż opisać: zależność, proces, mechanizm, dowód.
Do ożywienia zdjęcia jest animate_photo, do złożenia gotowych elementów design_compose,
do animacji interfejsu render_lottie.""",
    AnimacjaInput,
)
def animate_explainer(ctx: ToolContext, args: AnimacjaInput) -> ToolResult:
    if not Path(MANIM).exists():
        raise ToolError("Silnik animacji nie jest zainstalowany na tym serwerze.")
    if not piaskownica.dostepna():
        raise ToolError(
            "Renderowanie sceny wymaga piaskownicy, a ta nie działa na tym serwerze. "
            "Zgłoś to — do czasu naprawy animacji nie zrobię."
        )
    _sprawdz_kod(args.scena)
    klasa = _klasa_sceny(args.scena)

    katalog = Path(ctx.output_path("scena.py")).parent
    plik = katalog / "scena.py"
    plik.write_text(args.scena, encoding="utf-8")

    polecenie = piaskownica.polecenie(
        piaskownica.znajdz_bwrap(),
        [
            MANIM,
            JAKOSCI[args.jakosc],
            "--format=mp4",
            "--media_dir",
            str(katalog / "wynik"),
            str(plik),
            klasa,
        ],
        cwd=katalog,
        zapis=(katalog,),
        siec=False,
    )
    ctx.progress(f"Renderowanie animacji „{klasa}” ({args.jakosc})…")
    ctx.run_command(polecenie, timeout=LIMIT_RENDEROWANIA_S, cwd=katalog)

    # Manim zostawia obok gotowego filmu katalog `partial_movie_files` z kawałkami
    # poszczególnych animacji; bez tego warunku wynikiem bywał pojedynczy kawałek.
    filmy = [
        plik
        for plik in sorted((katalog / "wynik").rglob("*.mp4"))
        if "partial_movie_files" not in plik.parts
    ]
    if not filmy:
        raise ToolError("Render nie zostawił pliku filmu — sprawdź, czy scena coś rysuje.")
    gotowy = katalog / f"{args.nazwa}.mp4"
    shutil.move(str(filmy[-1]), gotowy)
    shutil.rmtree(katalog / "wynik", ignore_errors=True)

    rozmiar_kb = round(gotowy.stat().st_size / 1024, 1)
    return ToolResult(
        {"scena": klasa, "jakosc": args.jakosc, "rozmiar_kb": rozmiar_kb},
        f"Animacja „{klasa}” gotowa ({args.jakosc}, {rozmiar_kb} KB).",
        files=[OutputFile(gotowy, gotowy.name, f"Animacja wyjaśniająca ({klasa})")],
    )


__all__ = ["animate_explainer"]
