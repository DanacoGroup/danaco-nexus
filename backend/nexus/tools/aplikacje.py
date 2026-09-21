"""Szablony aplikacji serwera: wykaz i założenie projektu z gotowego szablonu.

W ``/danaco/programy/web/kit/apps`` leżą kompletne aplikacje webowe z plikiem opisu
``danaco-szablon.json`` (marka, tokeny, kroje, polecenia dev/build). Do tej pory nie było
do nich żadnego narzędzia, więc dla agenta nie istniały: na „zrób mi panel” pisał aplikację
od zera, zamiast wziąć gotową i przebrać ją w markę użytkownika.

Dwa narzędzia domykają lukę:

* ``app_templates`` — co jest do wzięcia (z zawężaniem po nazwie i opisie),
* ``app_from_template`` — kopia szablonu jako nowy projekt w module Kod.

Bezpieczeństwo: identyfikator szablonu jest sprawdzany wzorcem i rozwiązywany wyłącznie
wewnątrz katalogu szablonów, a projekt powstaje w przestrzeni konta użytkownika
(``projekty_konta``), nigdy poza nią. Kopiowane są wyłącznie pliki szablonu — bez
``node_modules`` i bez historii gita autora.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from pydantic import Field

from nexus.agent.przestrzenie import (
    WorkspaceError,
    existing_project,
    project_dir,
    przypisz_projekt,
    valid_project_name,
)
from nexus.tools.base import ToolContext, ToolError, ToolInput, ToolResult, registry

#: Katalog szablonów aplikacji. Ze zmiennej otoczenia, żeby instalacja na innym serwerze
#: nie wymagała zmiany kodu.
SZABLONY = Path(os.environ.get("NEXUS_SZABLONY_APLIKACJI", "/danaco/programy/web/kit/apps"))
#: Kolekcja szablonów otwartych. Część z nich to nie witryny, tylko gotowe aplikacje
#: (panele, dashboardy) — leżały tam od początku, ale narzędzie ich nie widziało, więc
#: agent miał do dyspozycji dwa szablony zamiast kilkudziesięciu.
KOLEKCJA = Path(os.environ.get("NEXUS_KOLEKCJA_WWW", "/danaco/programy/web/kolekcja"))
#: Po tych określeniach w polu ``charakter`` poznajemy w kolekcji aplikację, a nie witrynę.
CHARAKTER_APLIKACJI = frozenset({"aplikacja", "panel"})
OPIS_SZABLONU = "danaco-szablon.json"
#: Czego nie kopiujemy do projektu użytkownika: paczki, wyniki budowy i historia gita autora.
POMIJANE_KATALOGI = frozenset(
    {"node_modules", ".git", ".next", "dist", "build", ".turbo", ".cache", ".vercel", "out"}
)
#: Ile plików wolno przenieść. Szablon z tysiącami plików to prawie na pewno szablon
#: z wynikiem budowy w środku — lepiej powiedzieć to wprost niż zapchać dysk konta.
MAKS_PLIKOW = 4000
NAZWA = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}")


def _czytaj_json(plik: Path) -> dict[str, Any]:
    try:
        dane = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dane if isinstance(dane, dict) else {}


def _wlasne() -> list[dict[str, Any]]:
    """Aplikacje zestawu Danaco — katalog z ``danaco-szablon.json`` w środku."""
    if not SZABLONY.is_dir():
        return []
    wynik: list[dict[str, Any]] = []
    for katalog in sorted(SZABLONY.iterdir()):
        if not katalog.is_dir() or katalog.name.startswith("."):
            continue
        opis = _czytaj_json(katalog / OPIS_SZABLONU)
        if not opis:
            continue
        wynik.append(
            {
                "id": str(opis.get("szablon") or katalog.name),
                "opis": str(opis.get("opis") or "")[:400],
                "marka": opis.get("marka") or "",
                "licencja": "własny zestaw Danaco",
                "stos": opis.get("stos") or [],
                "dev": opis.get("dev") or "",
                "build": opis.get("build") or "",
                "pliki_marki": opis.get("pliki_marki") or [],
                "tokeny": opis.get("tokeny") or "",
                "plikow": _ile_plikow(katalog),
                "zrodlo_szablonu": "danaco",
            }
        )
    return wynik


def _z_kolekcji() -> list[dict[str, Any]]:
    """Aplikacje i panele z kolekcji szablonów otwartych (katalog ``zrodlo/``)."""
    korzen = KOLEKCJA / "szablony"
    if not korzen.is_dir():
        return []
    wynik: list[dict[str, Any]] = []
    for meta in sorted(korzen.glob("*/meta.json")):
        opis = _czytaj_json(meta)
        if not CHARAKTER_APLIKACJI & set(opis.get("charakter") or []):
            continue
        zrodlo = meta.parent / "zrodlo"
        if not zrodlo.is_dir():
            continue
        wynik.append(
            {
                "id": str(opis.get("id") or meta.parent.name),
                "opis": str(opis.get("opis") or "")[:400],
                "marka": "",
                "licencja": opis.get("licencja") or "",
                "stos": opis.get("stos") or [],
                "dev": "",
                "build": "",
                "pliki_marki": [],
                "tokeny": "",
                "plikow": _ile_plikow(zrodlo),
                "zrodlo_szablonu": "kolekcja",
                "zrodlo_www": opis.get("zrodlo") or "",
            }
        )
    return wynik


def _szablony() -> list[dict[str, Any]]:
    """Wszystkie szablony aplikacji: zestaw Danaco i aplikacje z kolekcji otwartej."""
    return _wlasne() + _z_kolekcji()


def _ile_plikow(katalog: Path) -> int:
    ile = 0
    for sciezka in katalog.rglob("*"):
        if sciezka.is_file() and not _pomijany(sciezka.relative_to(katalog)):
            ile += 1
    return ile


def _pomijany(wzgledna: Path) -> bool:
    return any(czesc in POMIJANE_KATALOGI for czesc in wzgledna.parts)


class WykazAplikacjiInput(ToolInput):
    szukaj: str = Field(
        default="",
        max_length=60,
        description=(
            "Fragment nazwy, opisu albo stosu (np. „panel”, „sklep”, „react”, „vue”, „next”). "
            "Pusto = początek spisu."
        ),
    )
    limit: int = Field(
        default=12, ge=1, le=40, description="Ile pozycji wypisać. Pełny spis ma kilkadziesiąt."
    )


@registry.register(
    "app_templates",
    """Pokazuje 35 gotowych aplikacji webowych leżących na serwerze.
Są wśród nich panele administracyjne, pulpity z danymi, landingi i strony produktowe na React,
Vue, Next, Nuxt, Astro, Bootstrap i Tailwindzie. Sprawdź ten spis, zanim zaczniesz pisać
aplikację od zera: przebranie gotowego szablonu w markę użytkownika jest szybsze i daje lepszy
wynik niż kod pisany od podstaw. Pole `stos` mówi, na czym stoi szablon, `licencja` — na jakich
warunkach wolno go użyć. Wybraną pozycję zakłada app_from_template.""",
    WykazAplikacjiInput,
)
def app_templates(ctx: ToolContext, args: WykazAplikacjiInput) -> ToolResult:
    wszystkie = _szablony()
    if not wszystkie:
        raise ToolError("Szablony aplikacji nie są zainstalowane na tym serwerze.")
    igla = args.szukaj.strip().lower()
    pasujace = [
        s
        for s in wszystkie
        if not igla
        or igla in f"{s['id']} {s['opis']} {s['marka']} {' '.join(map(str, s['stos']))}".lower()
    ]
    # Pełny spis z opisami to kilkanaście tysięcy znaków w jednej odpowiedzi — tyle kontekstu
    # nie jest potrzebne, żeby wybrać szablon. Liczba wszystkich zostaje w wyniku.
    wycinek = (pasujace or wszystkie)[: args.limit]
    ogolem = len(pasujace or wszystkie)
    podsumowanie = f"Szablony aplikacji: {len(wycinek)} z {ogolem}"
    if ogolem > len(wycinek):
        podsumowanie += " (zaweź spis polem `szukaj` albo podnieś `limit`)"
    return ToolResult(
        {"szablony": wycinek, "pasujacych": ogolem, "wszystkich": len(wszystkie)},
        podsumowanie + ".",
    )


def _katalog_szablonu(nazwa: str) -> tuple[Path, dict[str, Any]]:
    """Katalog z plikami szablonu i jego opis — z zestawu Danaco albo z kolekcji otwartej.

    Ścieżka jest rozwiązywana wyłącznie wewnątrz katalogu, w którym szablon ma prawo leżeć;
    „..” i dowiązania odpadają razem z resztą.
    """
    wlasny = (SZABLONY / nazwa).resolve()
    if SZABLONY.is_dir() and SZABLONY.resolve() in wlasny.parents and wlasny.is_dir():
        opis = _czytaj_json(wlasny / OPIS_SZABLONU)
        if not opis:
            raise ToolError(f"Katalog {nazwa!r} nie jest szablonem aplikacji (brak {OPIS_SZABLONU}).")
        return wlasny, opis

    korzen = KOLEKCJA / "szablony"
    pozycja = (korzen / nazwa).resolve()
    if korzen.is_dir() and korzen.resolve() in pozycja.parents and (pozycja / "zrodlo").is_dir():
        opis = _czytaj_json(pozycja / "meta.json")
        if not CHARAKTER_APLIKACJI & set(opis.get("charakter") or []):
            raise ToolError(
                f"Szablon {nazwa!r} z kolekcji to witryna, nie aplikacja — wstawia go "
                "site_from_template do szkicu strony."
            )
        return pozycja / "zrodlo", opis

    raise ToolError(f"Nie ma szablonu aplikacji {nazwa!r}. Spis daje app_templates.")


class ZSzablonuAplikacjiInput(ToolInput):
    szablon: str = Field(description="Identyfikator szablonu z app_templates (pole `id`).", max_length=80)
    projekt: str = Field(
        description="Nazwa nowego projektu w module Kod (litery, cyfry, kropka, podkreślnik, myślnik).",
        max_length=80,
    )


@registry.register(
    "app_from_template",
    """Zakłada nowy projekt z gotowego szablonu aplikacji i otwiera go w module Kod.
Spis szablonów daje app_templates.""",
    ZSzablonuAplikacjiInput,
)
def app_from_template(ctx: ToolContext, args: ZSzablonuAplikacjiInput) -> ToolResult:
    nazwa = args.szablon.strip()
    if not NAZWA.fullmatch(nazwa):
        raise ToolError("Nieprawidłowy identyfikator szablonu.")
    zrodlo, opis = _katalog_szablonu(nazwa)

    if not valid_project_name(args.projekt):
        raise ToolError("Niepoprawna nazwa projektu (litery, cyfry, kropka, podkreślnik, myślnik).")
    if existing_project(ctx.settings, args.projekt) is not None:
        raise ToolError(f"Projekt „{args.projekt}” już istnieje — wybierz inną nazwę.")
    try:
        cel = project_dir(ctx.settings, args.projekt)
    except WorkspaceError as blad:
        raise ToolError(str(blad)) from blad

    pliki = [
        p
        for p in sorted(zrodlo.rglob("*"))
        if p.is_file() and not _pomijany(p.relative_to(zrodlo))
    ]
    if len(pliki) > MAKS_PLIKOW:
        raise ToolError(
            f"Szablon {nazwa!r} ma {len(pliki)} plików (limit {MAKS_PLIKOW}). "
            "Wygląda na szablon z wynikiem budowy w środku — zgłoś to administratorowi."
        )

    ctx.progress(f"Zakładam projekt „{args.projekt}” z szablonu {nazwa}…")
    cel.mkdir(parents=True, exist_ok=True)
    bajty = 0
    try:
        for plik in pliki:
            ctx.check_cancelled()
            docelowy = cel / plik.relative_to(zrodlo)
            docelowy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(plik, docelowy)
            bajty += plik.stat().st_size
    except BaseException:
        # Projekt w połowie skopiowany jest gorszy niż jego brak: nie ma właściciela,
        # więc w module Kod nie widać go nawet po to, żeby go usunąć.
        shutil.rmtree(cel, ignore_errors=True)
        raise
    przypisz_projekt(ctx.settings, args.projekt, ctx.owner_id)

    dane = {
        "projekt": args.projekt,
        "szablon": nazwa,
        "pliki": len(pliki),
        "rozmiar_kb": round(bajty / 1024, 1),
        "marka_szablonu": opis.get("marka") or "",
        "pliki_marki": opis.get("pliki_marki") or [],
        "tokeny": opis.get("tokeny") or "",
        "dev": opis.get("dev") or "",
        "build": opis.get("build") or "",
        "licencja": opis.get("licencja") or "",
        "zrodlo_www": opis.get("zrodlo") or "",
        "stos": opis.get("stos") or [],
    }
    licencja = f" Licencja szablonu: {dane['licencja']}." if dane["licencja"] else ""
    if dane["pliki_marki"]:
        wskazowka = "Markę podmień w plikach z pola `pliki_marki` i w tokenach z pola `tokeny`."
    else:
        # Szablony z kolekcji otwartej nie mają mapy marki — trzeba ją znaleźć w projekcie.
        dane["marka_do_znalezienia"] = True
        wskazowka = (
            "Ten szablon nie ma mapy marki: znajdź w projekcie nazwę i barwy autora "
            "(zacznij od `package.json`, `README`, plików `*.config.*` i arkuszy stylów) "
            "i podmień je na dane użytkownika, zanim mu cokolwiek pokażesz."
        )
    return ToolResult(
        dane,
        f"Projekt „{args.projekt}” założony z szablonu {nazwa}: {len(pliki)} plików.{licencja} "
        f"Otwórz go w module Kod. {wskazowka}",
    )


__all__ = ["app_from_template", "app_templates"]
