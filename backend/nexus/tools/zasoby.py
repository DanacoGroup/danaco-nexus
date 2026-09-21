"""Biblioteki materiałów serwera: grafika, ruch, media.

Na serwerze leżą gotowe materiały, po które agent ma sięgać zamiast rysować wszystko kodem:
ilustracje SVG, wzory i tekstury teł, gradienty, makiety urządzeń, animowane tła WebGL,
biblioteki animacji CSS, shadery, dźwięki, podkłady muzyczne, LUT-y i przejścia wideo.
Do tej pory nie było ich w rejestrze, więc dla agenta nie istniały.

Dwa narzędzia domykają lukę:

* ``asset_library`` — co jest w bibliotece (z zawężaniem po nazwie i dziale),
* ``asset_to_site`` — wstawienie wybranego pliku do szkicu strony użytkownika.

Bezpieczeństwo: ścieżka materiału jest rozwiązywana wyłącznie wewnątrz katalogu działu
(symlinki i „..” odpadają), a zapis idzie przez ``SiteStore``, który pilnuje typów plików.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from nexus.tools.base import ToolContext, ToolError, ToolInput, ToolResult, registry
from nexus.tworczy.strony import SiteError, site_store

#: Działy bibliotek i ich katalogi na serwerze. Ścieżki z otoczenia, żeby instalacja na innym
#: serwerze nie wymagała zmiany kodu.
DZIALY: dict[str, Path] = {
    "grafika": Path(os.environ.get("NEXUS_ZASOBY_GRAFIKA", "/danaco/programy/grafika")),
    "ruch": Path(os.environ.get("NEXUS_ZASOBY_RUCH", "/danaco/programy/motion-zasoby")),
    "media": Path(os.environ.get("NEXUS_ZASOBY_MEDIA", "/danaco/programy/media-zasoby")),
}
OPISY_DZIALOW = {
    "grafika": "ilustracje SVG, wzory i tekstury teł, gradienty, makiety urządzeń",
    "ruch": "animowane tła WebGL, biblioteki animacji CSS/JS, shadery, animacje Lottie",
    "media": "dźwięki interfejsu, podkłady muzyczne, LUT-y kolorystyczne, przejścia wideo",
}
#: Ile pozycji wraca bez zawężenia — pełne wykazy mają tysiące plików.
LIMIT = 40
#: Pliki służbowe zestawów — nie są materiałem do wstawienia na stronę. Poza wykazami
#: zestawu są tu pliki budowy paczki npm: zestaw przychodzi czasem z całym repozytorium
#: autora, a ``rollup.config.js`` w spisie ilustracji to dla agenta fałszywy trop.
POMIJANE = frozenset(
    {"manifest.json", "odrzucone.json", "package.json", "package-lock.json", "pnpm-lock.yaml",
     "tsconfig.json", "indeks.json", "rollup.config.js", "vite.config.js", "webpack.config.js",
     "gulpfile.js", "babel.config.js", "jest.config.js", "eslint.config.js",
     "postcss.config.js", "tailwind.config.js", "generator.js", "karma.conf.js"}
)
#: Katalogi, których zawartość nie jest materiałem: część zestawów niesie ze sobą aplikację
#: przykładową, testy i pliki serwisu kodu. Osobno — katalog z materiałem, którego tutejsze
#: programy nie otworzą (zostaje na dysku, bywa poprawny dla innych narzędzi).
#: „examples” świadomie nie jest pomijane: three.js trzyma tam dodatki (kontrolki, efekty),
#: z których agent naprawdę korzysta.
POMIJANE_KATALOGI = frozenset(
    {"nieobslugiwane-ffmpeg", "_zrodlo", "node_modules", "zrodlo",
     "example", "demo", "demos", "test", "tests", "__tests__", ".github", "coverage"}
)
#: Rozszerzenia pokazywane jako materiał (reszta to pliki pomocnicze projektu).
MATERIALY = frozenset(
    {".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".json", ".css", ".js", ".mjs",
     ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".mp4", ".webm", ".cube", ".glsl", ".frag", ".vert",
     # Materiały do renderu 3D (Blender): sceny, mapy oświetlenia, tekstury PBR.
     ".blend", ".hdr", ".exr"}
)


def _katalog(dzial: str) -> Path:
    katalog = DZIALY.get(dzial)
    if katalog is None:
        raise ToolError(f"Nie znam działu {dzial!r}. Dostępne: {', '.join(sorted(DZIALY))}.")
    if not katalog.is_dir():
        raise ToolError(f"Dział „{dzial}” nie jest zainstalowany na tym serwerze.")
    return katalog


def _manifest(katalog: Path) -> list[dict[str, Any]]:
    """Wykaz zestawów z ``manifest.json``; przy jego braku — same katalogi zestawów."""
    plik = katalog / "manifest.json"
    if plik.is_file():
        try:
            dane = json.loads(plik.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            dane = None
        if isinstance(dane, list):
            return [p for p in dane if isinstance(p, dict)]
        if isinstance(dane, dict):
            for klucz in ("pozycje", "zestawy", "items"):
                if isinstance(dane.get(klucz), list):
                    return [p for p in dane[klucz] if isinstance(p, dict)]
    return [
        {"id": p.name, "nazwa": p.name.replace("-", " "), "katalog": p.name}
        for p in sorted(katalog.iterdir())
        if p.is_dir() and not p.name.startswith(".")
    ]


def _zestaw_skrocony(pozycja: dict[str, Any]) -> dict[str, Any]:
    """Zestaw w postaci, która mówi agentowi, po co ma po niego sięgnąć."""
    return {
        "id": pozycja.get("id") or pozycja.get("nazwa"),
        "nazwa": pozycja.get("nazwa"),
        "katalog": pozycja.get("katalog"),
        "plikow": pozycja.get("liczba_plikow") or pozycja.get("plikow"),
        "licencja": pozycja.get("licencja"),
        # „zastosowanie” pisze wykonawca instalacji po polsku: kiedy ten zestaw jest właściwy.
        "zastosowanie": str(pozycja.get("zastosowanie") or pozycja.get("opis") or "")[:240],
    }


def _pliki(katalog: Path, igla: str, limit: int) -> list[dict[str, Any]]:
    """Materiały pasujące do zapytania — ścieżki względem katalogu działu."""
    wynik: list[dict[str, Any]] = []
    for plik in sorted(katalog.rglob("*")):
        if len(wynik) >= limit:
            break
        if not plik.is_file() or plik.suffix.lower() not in MATERIALY or plik.name in POMIJANE:
            continue
        wzgledna = plik.relative_to(katalog).as_posix()
        if any(czesc in POMIJANE_KATALOGI for czesc in plik.relative_to(katalog).parts[:-1]):
            continue
        if igla and igla not in wzgledna.lower():
            continue
        wynik.append({"sciezka": wzgledna, "rozmiar_kb": round(plik.stat().st_size / 1024, 1)})
    return wynik


class WykazInput(ToolInput):
    dzial: Literal["", "grafika", "ruch", "media"] = Field(
        default="", description="Dział biblioteki; pusto = przegląd wszystkich działów."
    )
    szukaj: str = Field(
        default="",
        max_length=60,
        description="Fragment ścieżki albo nazwy (np. „peeps”, „gradient”, „whoosh”, „lut”).",
    )
    limit: int = Field(default=25, ge=1, le=LIMIT, description="Ile materiałów wypisać.")


@registry.register(
    "asset_library",
    """Pokazuje, jakie gotowe materiały leżą na serwerze, zanim zaczniesz szukać ich w sieci.
W dziale „grafika” są ilustracje SVG, wzory i tekstury teł, gradienty i makiety urządzeń,
w dziale „ruch” — animowane tła WebGL, biblioteki animacji i shadery, w dziale „media” —
dźwięki, podkłady muzyczne, LUT-y i przejścia wideo. Wszystko jest na miejscu i działa bez
sieci. Wybraną pozycję wstawia do strony asset_to_site.""",
    WykazInput,
)
def asset_library(ctx: ToolContext, args: WykazInput) -> ToolResult:
    dzialy = [args.dzial] if args.dzial else [d for d in DZIALY if DZIALY[d].is_dir()]
    if not dzialy:
        raise ToolError("Biblioteki materiałów nie są zainstalowane na tym serwerze.")
    igla = args.szukaj.strip().lower()
    dane: dict[str, Any] = {"dzialy": {}}
    razem = 0
    for nazwa in dzialy:
        katalog = _katalog(nazwa)
        pliki = _pliki(katalog, igla, args.limit)
        wszystkich = sum(
            1
            for p in katalog.rglob("*")
            if p.is_file()
            and p.suffix.lower() in MATERIALY
            and p.name not in POMIJANE
            and not any(czesc in POMIJANE_KATALOGI for czesc in p.relative_to(katalog).parts[:-1])
        )
        razem += wszystkich
        zestawy = [_zestaw_skrocony(p) for p in _manifest(katalog)]
        if igla:
            pasujace_zestawy = [
                z for z in zestawy if igla in f"{z['id']} {z['nazwa']} {z['zastosowanie']}".lower()
            ]
            zestawy = pasujace_zestawy or zestawy[:6]
        dane["dzialy"][nazwa] = {
            "opis": OPISY_DZIALOW[nazwa],
            "zestawy": zestawy[:20],
            "zestawow": len(_manifest(katalog)),
            "materialow": wszystkich,
            "pasujace": pliki,
        }
    podsumowanie = ", ".join(f"{n}: {dane['dzialy'][n]['materialow']}" for n in dzialy)
    if igla:
        znalezione = sum(len(dane["dzialy"][n]["pasujace"]) for n in dzialy)
        return ToolResult(
            dane, f"Materiały pasujące do „{args.szukaj}”: {znalezione} (w bibliotece {razem})."
        )
    return ToolResult(dane, f"Biblioteki materiałów — {podsumowanie} (razem {razem} plików).")


class DoStronyInput(ToolInput):
    site: str = Field(description="Adres strony użytkownika, do której wstawiamy materiał.", max_length=80)
    dzial: Literal["grafika", "ruch", "media"] = Field(description="Dział biblioteki.")
    sciezka: str = Field(
        description="Ścieżka materiału w dziale, dokładnie jak w asset_library.", max_length=300
    )
    cel: str = Field(
        default="",
        max_length=300,
        description="Ścieżka w szkicu strony (np. „img/tlo.svg”). Pusto = ta sama nazwa w „zasoby/”.",
    )


@registry.register(
    "asset_to_site",
    """Wstawia materiał z biblioteki serwera do szkicu strony użytkownika: ilustrację, wzór tła,
plik animowanego tła, dźwięk. Podajesz dział i ścieżkę z asset_library. Plik trafia do szkicu,
więc odwołujesz się do niego zwykłą ścieżką w HTML i CSS. Publikuje wyłącznie użytkownik.""",
    DoStronyInput,
)
def asset_to_site(ctx: ToolContext, args: DoStronyInput) -> ToolResult:
    katalog = _katalog(args.dzial)
    zrodlo = (katalog / args.sciezka).resolve()
    if not zrodlo.is_file() or katalog.resolve() not in zrodlo.parents:
        raise ToolError(f"Dział „{args.dzial}” nie ma materiału {args.sciezka!r}. Spis daje asset_library.")
    if zrodlo.suffix.lower() not in MATERIALY or zrodlo.name in POMIJANE:
        raise ToolError(f"{zrodlo.name} nie jest materiałem do wstawienia na stronę.")
    if any(czesc in POMIJANE_KATALOGI for czesc in zrodlo.relative_to(katalog).parts[:-1]):
        raise ToolError(
            f"{zrodlo.name} leży w katalogu materiałów, których tutejsze programy nie otworzą."
        )
    cel = args.cel.strip() or f"zasoby/{zrodlo.name}"
    store = site_store(ctx.settings, ctx.owner_id)
    if not store.exists(args.site):
        raise ToolError(f"Nie ma strony „{args.site}”. Najpierw załóż ją w module Strony.")
    try:
        store.write_bytes(args.site, cel, zrodlo.read_bytes())
    except SiteError as blad:
        raise ToolError(f"Nie udało się wstawić {zrodlo.name}: {blad}") from blad
    return ToolResult(
        {"site": args.site, "plik": cel, "zrodlo": f"{args.dzial}/{args.sciezka}"},
        f"Materiał w szkicu strony „{args.site}”: {cel}.",
    )


__all__ = ["asset_library", "asset_to_site"]
