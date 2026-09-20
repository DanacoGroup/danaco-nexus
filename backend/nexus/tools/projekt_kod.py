"""Narzędzia pracy nad kodem i stronami: kontrole jakości, audyt strony, zrzut, ikony.

Serwer ma komplet narzędzi programisty i webmastera, ale agent nie miał ich w rejestrze:
mógł napisać stronę, a nie mógł jej zobaczyć ani sprawdzić; mógł czytać kod projektu,
a nie mógł go skontrolować. Pięć narzędzi domyka tę lukę:

* ``code_check`` — semgrep, ruff, shellcheck i typos pod jednym wyborem,
* ``web_audit`` — Lighthouse (szybkość, SEO) i pa11y (dostępność WCAG),
* ``web_screenshot`` — Playwright: agent widzi stronę, którą właśnie napisał,
* ``icon_find`` — ikony Iconify (ponad 400 tys. znaków) jako gotowy SVG,
* ``site_optimize_assets`` — bezstratne odchudzenie PNG i SVG w szkicu strony.

Bezpieczeństwo: żadne z nich nie przyjmuje ścieżki z zewnątrz. Praca toczy się wyłącznie
w szkicu strony (``SiteStore``), w przestrzeni projektu modułu Kod (``safe_path``), na
plikach rozmowy albo pod publicznym adresem sprawdzonym ochroną SSRF z modułu badań.
Programy uruchamiamy listą argumentów, bez powłoki.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal

from PIL import Image
from pydantic import Field

from nexus.agent.przestrzenie import WorkspaceError, existing_project, safe_path
from nexus.research.web import FetchError, check_url
from nexus.storage import safe_filename
from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    image_preview,
    registry,
)
from nexus.tools.common import unique_name
from nexus.tworczy.strony import SiteError, check_path, site_store

#: Zbiór reguł semgrep i zbiór ikon Iconify leżą poza projektem — ścieżki z otoczenia,
#: żeby instalacja na innym serwerze nie wymagała zmiany kodu.
REGULY_SEMGREP = Path(os.environ.get("NEXUS_SEMGREP_REGULY", "/danaco/programy/semgrep-reguly"))
IKONY_DIR = Path(os.environ.get("NEXUS_IKONY_DIR", "/danaco/programy/web/ikony"))
IKONY_INDEKS = IKONY_DIR / "indeks-nazw.tsv"
IKONY_JSON = IKONY_DIR / "iconify" / "node_modules" / "@iconify" / "json" / "json"

CZAS_KONTROLI = 900
CZAS_AUDYTU = 420
CZAS_ZRZUTU = 180
CZAS_OPTYMALIZACJI = 120
PODGLAD = 1280

#: Katalogi, których żadna kontrola nie czyta: cudzy kod i wyniki budowania.
POMIJANE = frozenset(
    {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".next", "target"}
)
MAX_PLIKOW = 5000

WIDOKI = {"telefon": (390, 844), "tablet": (820, 1180), "komputer": (1440, 900)}
BARWA = re.compile(r"^(#[0-9A-Fa-f]{3,8}|currentColor|[A-Za-z]{3,20})$")
NAZWA_IKONY = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}:[a-z0-9][a-z0-9._-]{0,59}$")


def _program(nazwa: str, czego_dotyczy: str) -> str:
    """Ścieżka programu serwera albo błąd zrozumiały dla użytkownika."""
    sciezka = shutil.which(nazwa)
    if not sciezka:
        raise ToolError(f"{czego_dotyczy} jest niedostępne na tym serwerze.")
    return sciezka


def _uruchom_kontrole(ctx: ToolContext, polecenie: list[str], kody_ok: tuple[int, ...]) -> str:
    """Uruchamia kontrolę, dla której kod wyjścia inny niż zero oznacza *znalezione* usterki.

    ``ToolContext.run_command`` traktuje każdy taki kod jak awarię i gubi wynik, a
    shellcheck i typos nie umieją pisać raportu do pliku. Uruchomienie jest takie samo:
    lista argumentów, bez powłoki, z limitem czasu.
    """
    ctx.check_cancelled()
    try:
        wynik = subprocess.run(  # lista argumentów, bez powłoki
            polecenie,
            capture_output=True,
            text=True,
            timeout=CZAS_KONTROLI,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except subprocess.TimeoutExpired as blad:
        raise ToolError(f"Kontrola {Path(polecenie[0]).name} przekroczyła limit czasu.") from blad
    if wynik.returncode not in kody_ok:
        ogon = (wynik.stderr or wynik.stdout or "").strip()[-1000:]
        raise ToolError(f"Kontrola {Path(polecenie[0]).name} nie powiodła się: {ogon}")
    return wynik.stdout


# --- cele pracy: projekt kodu, szkic strony, adres publiczny --------------------------------------


def _pliki_projektu(katalog: Path) -> list[Path]:
    """Pliki projektu bez katalogów zależności i wyników budowania (te pomijamy w marszu)."""
    znalezione: list[Path] = []
    for korzen, katalogi, nazwy in os.walk(katalog, followlinks=False):
        katalogi[:] = sorted(nazwa for nazwa in katalogi if nazwa not in POMIJANE)
        for nazwa in sorted(nazwy):
            plik = Path(korzen) / nazwa
            if plik.is_file() and not plik.is_symlink():
                znalezione.append(plik)
                if len(znalezione) >= MAX_PLIKOW:
                    return znalezione
    return znalezione


def _cel_kodu(ctx: ToolContext, projekt: str, podkatalog: str, file_ids: list[str]) -> tuple[Path, str]:
    """Katalog do sprawdzenia: przestrzeń projektu modułu Kod albo pliki z rozmowy."""
    if bool(projekt) == bool(file_ids):
        raise ToolError("Podaj nazwę projektu z modułu Kod albo pliki z rozmowy — jedno z dwóch.")
    if projekt:
        katalog = existing_project(ctx.settings, projekt)
        if katalog is None:
            raise ToolError(f"Nie ma projektu {projekt!r} w module Kod (sprawdź listę projektów).")
        try:
            cel = safe_path(katalog, podkatalog) if podkatalog else katalog
        except WorkspaceError as blad:
            raise ToolError(str(blad)) from blad
        if not cel.exists():
            raise ToolError(f"W projekcie {projekt} nie ma ścieżki {podkatalog!r}.")
        return cel, f"projekt {projekt}" + (f"/{podkatalog}" if podkatalog else "")
    katalog = ctx.output_path("kontrola").parent
    uzyte: set[str] = set()
    for file_id in file_ids:
        plik = ctx.file(file_id)
        nazwa = unique_name(safe_filename(plik.name), uzyte)
        (katalog / nazwa).write_bytes(plik.path.read_bytes())
    return katalog, f"pliki z rozmowy ({len(file_ids)})"


def _szkic(ctx: ToolContext, site: str) -> Path:
    """Katalog szkicu strony; błąd, gdy strony nie ma."""
    store = site_store(ctx.settings)
    try:
        store.meta(site)
        katalog = store.draft_dir(site)
    except SiteError as blad:
        raise ToolError(str(blad)) from blad
    if not katalog.is_dir():
        raise ToolError(f"Strona {site!r} nie ma jeszcze plików.")
    return katalog


@contextmanager
def _serwer(katalog: Path) -> Iterator[str]:
    """Podaje szkic strony pod adresem 127.0.0.1 na czas badania (to nie jest publikacja)."""

    class Cichy(SimpleHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

    serwer = ThreadingHTTPServer(("127.0.0.1", 0), partial(Cichy, directory=str(katalog)))
    watek = threading.Thread(target=serwer.serve_forever, daemon=True)
    watek.start()
    try:
        yield f"http://127.0.0.1:{serwer.server_port}/"
    finally:
        serwer.shutdown()
        serwer.server_close()


@contextmanager
def _cel_www(ctx: ToolContext, site: str, podstrona: str, adres: str) -> Iterator[tuple[str, str]]:
    """Adres do zbadania: szkic strony podany lokalnie albo sprawdzony adres publiczny."""
    if bool(site) == bool(adres):
        raise ToolError("Podaj adres strony z modułu Strony (site) albo publiczny adres (adres).")
    if adres:
        try:
            sprawdzony = check_url(adres)
        except FetchError as blad:
            raise ToolError(str(blad)) from blad
        yield sprawdzony, sprawdzony
        return
    katalog = _szkic(ctx, site)
    try:
        sciezka = check_path(podstrona, allow_empty=True) if podstrona else ""
    except SiteError as blad:
        raise ToolError(str(blad)) from blad
    if sciezka and not (katalog / sciezka).is_file():
        raise ToolError(f"Strona {site} nie ma pliku {sciezka!r}.")
    if not sciezka and not (katalog / "index.html").is_file():
        raise ToolError(f"Strona {site} nie ma pliku index.html.")
    with _serwer(katalog) as baza:
        yield baza + sciezka, f"szkic strony {site}/{sciezka or 'index.html'}"


# --- kontrole jakości kodu ------------------------------------------------------------------------

JEZYKI_SEMGREP = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "go": "go",
    "java": "java",
    "php": "php",
    "ruby": "ruby",
    "rust": "rust",
    "csharp": "csharp",
    "powloka": "bash",
    "html": "html",
    "terraform": "terraform",
}
ROZSZERZENIA = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".php": "php",
    ".rb": "ruby",
    ".rs": "rust",
    ".cs": "csharp",
    ".sh": "powloka",
    ".bash": "powloka",
    ".html": "html",
    ".tf": "terraform",
}


def _wzgledna(plik: str, korzen: Path) -> str:
    """Ścieżka wyniku względem badanego katalogu (bez ujawniania układu dysku)."""
    try:
        return Path(plik).resolve().relative_to(korzen.resolve()).as_posix()
    except (ValueError, OSError):
        return Path(plik).name


def _jezyk_celu(cel: Path) -> str:
    """Język przeważający w badanym miejscu (po rozszerzeniach plików)."""
    pliki = _pliki_projektu(cel) if cel.is_dir() else [cel]
    liczby: dict[str, int] = {}
    for plik in pliki:
        jezyk = ROZSZERZENIA.get(plik.suffix.lower())
        if jezyk:
            liczby[jezyk] = liczby.get(jezyk, 0) + 1
    if not liczby:
        raise ToolError("Nie rozpoznaję języka w tym miejscu — podaj go polem „jezyk”.")
    kolejnosc = list(JEZYKI_SEMGREP)
    return min(liczby, key=lambda nazwa: (-liczby[nazwa], kolejnosc.index(nazwa)))


def _semgrep(ctx: ToolContext, cel: Path, jezyk: str, limit: int) -> dict[str, Any]:
    """Wzorce podatności i błędów (reguły semgrep z zasobu serwera)."""
    program = _program("semgrep", "Analiza bezpieczeństwa kodu (semgrep)")
    wybrany = jezyk if jezyk != "auto" else _jezyk_celu(cel)
    reguly = REGULY_SEMGREP / JEZYKI_SEMGREP[wybrany]
    if not reguly.is_dir():
        raise ToolError(f"Zbiór reguł semgrep dla języka {wybrany} nie jest dostępny na tym serwerze.")
    raport = ctx.output_path("semgrep.json")
    ctx.progress(f"Semgrep: reguły dla języka {wybrany}")
    ctx.run_command(
        [
            program,
            "scan",
            "--metrics=off",
            "--quiet",
            "--disable-version-check",
            "--timeout=10",
            f"--config={reguly}",
            f"--json-output={raport}",
            str(cel),
        ],
        timeout=CZAS_KONTROLI,
    )
    dane = json.loads(raport.read_text(encoding="utf-8")) if raport.is_file() else {"results": []}
    usterki = [
        {
            "plik": _wzgledna(str(wynik.get("path", "")), cel),
            "wiersz": wynik.get("start", {}).get("line"),
            "waga": str(wynik.get("extra", {}).get("severity", "")).lower(),
            "regula": str(wynik.get("check_id", "")).rsplit(".", 1)[-1],
            "opis": str(wynik.get("extra", {}).get("message", "")).strip()[:400],
        }
        for wynik in dane.get("results", [])
    ]
    return {"jezyk": wybrany, "znalezione": len(usterki), "lista": usterki[:limit]}


def _ruff(ctx: ToolContext, cel: Path, limit: int) -> dict[str, Any]:
    """Błędy i zapachy w kodzie Pythona (ruff)."""
    program = _program("ruff", "Kontrola kodu Pythona (ruff)")
    raport = ctx.output_path("ruff.json")
    ctx.progress("Ruff: kontrola kodu Pythona")
    ctx.run_command(
        [
            program,
            "check",
            "--exit-zero",
            "--no-cache",
            "--output-format",
            "json",
            "-o",
            str(raport),
            str(cel),
        ],
        timeout=CZAS_KONTROLI,
    )
    dane = json.loads(raport.read_text(encoding="utf-8")) if raport.is_file() else []
    usterki = [
        {
            "plik": _wzgledna(str(wynik.get("filename", "")), cel),
            "wiersz": (wynik.get("location") or {}).get("row"),
            "regula": wynik.get("code"),
            "opis": str(wynik.get("message", ""))[:300],
            "poprawka": bool(wynik.get("fix")),
        }
        for wynik in dane
    ]
    return {"znalezione": len(usterki), "lista": usterki[:limit]}


def _shellcheck(ctx: ToolContext, cel: Path, limit: int) -> dict[str, Any]:
    """Błędy w skryptach powłoki (shellcheck)."""
    program = _program("shellcheck", "Kontrola skryptów powłoki (shellcheck)")
    pliki = [
        plik
        for plik in (_pliki_projektu(cel) if cel.is_dir() else [cel])
        if plik.suffix.lower() in {".sh", ".bash"}
    ][:200]
    if not pliki:
        raise ToolError("Nie znalazłem w tym miejscu skryptów powłoki (.sh, .bash).")
    ctx.progress(f"Shellcheck: {len(pliki)} skryptów")
    wyjscie = _uruchom_kontrole(
        ctx, [program, "--format=json", "--severity=info", *[str(plik) for plik in pliki]], (0, 1)
    )
    dane = json.loads(wyjscie) if wyjscie.strip() else []
    usterki = [
        {
            "plik": _wzgledna(str(wynik.get("file", "")), cel),
            "wiersz": wynik.get("line"),
            "waga": wynik.get("level"),
            "regula": f"SC{wynik.get('code')}",
            "opis": str(wynik.get("message", ""))[:300],
        }
        for wynik in dane
    ]
    return {"sprawdzone_pliki": len(pliki), "znalezione": len(usterki), "lista": usterki[:limit]}


def _typos(ctx: ToolContext, cel: Path, limit: int) -> dict[str, Any]:
    """Literówki w kodzie i nazwach (słownik angielski)."""
    program = _program("typos", "Kontrola literówek (typos)")
    ctx.progress("Typos: literówki w kodzie")
    wyjscie = _uruchom_kontrole(ctx, [program, "--format", "json", "--sort", str(cel)], (0, 2))
    usterki = []
    for wiersz in wyjscie.splitlines():
        if not wiersz.strip():
            continue
        try:
            wynik = json.loads(wiersz)
        except json.JSONDecodeError:
            continue
        if wynik.get("type") != "typo":
            continue
        usterki.append(
            {
                "plik": _wzgledna(str(wynik.get("path", "")), cel),
                "wiersz": wynik.get("line_num"),
                "slowo": wynik.get("typo"),
                "propozycje": wynik.get("corrections", [])[:3],
            }
        )
    return {"znalezione": len(usterki), "lista": usterki[:limit]}


class KontrolaInput(ToolInput):
    projekt: str = Field(
        default="",
        max_length=64,
        description="Nazwa projektu z modułu Kod (np. „sklep”). Zamiast tego można podać file_ids.",
    )
    podkatalog: str = Field(
        default="",
        max_length=300,
        description="Ścieżka wewnątrz projektu, np. „backend/api” (pusto = cały projekt).",
    )
    file_ids: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Zamiast projektu: pliki z rozmowy (pojedynczy skrypt, paczka kodu).",
    )
    kontrole: list[Literal["bezpieczenstwo", "python", "powloka", "literowki"]] = Field(
        default=["bezpieczenstwo"],
        min_length=1,
        max_length=4,
        description=(
            "bezpieczenstwo = semgrep (podatności i pułapki w 12 językach), python = ruff, "
            "powloka = shellcheck (.sh), literowki = typos (słownik angielski)."
        ),
    )
    jezyk: Literal[
        "auto",
        "python",
        "javascript",
        "typescript",
        "go",
        "java",
        "php",
        "ruby",
        "rust",
        "csharp",
        "powloka",
        "html",
        "terraform",
    ] = Field(default="auto", description="Język reguł semgrep; auto = po rozszerzeniach plików.")
    limit: int = Field(default=40, ge=5, le=200, description="Najwięcej usterek jednej kontroli w wyniku.")


@registry.register(
    "code_check",
    """Kontroluje jakość kodu: podatności i pułapki (semgrep), błędy Pythona (ruff), błędy
skryptów powłoki (shellcheck), literówki w kodzie (typos). Pracuje na projekcie z modułu Kod
albo na plikach wysłanych w rozmowie. Stosuj, gdy użytkownik pyta „czy ten kod jest bezpieczny”,
„znajdź błędy w projekcie”, „przejrzyj ten skrypt”, a także po większej zmianie w kodzie.
Zwraca listę usterek z plikiem, wierszem i wagą — nie poprawia ich sam. Do sprawdzenia
polszczyzny w tekście służy check_grammar, nie ta kontrola.""",
    KontrolaInput,
)
def code_check(ctx: ToolContext, args: KontrolaInput) -> ToolResult:
    cel, opis = _cel_kodu(ctx, args.projekt, args.podkatalog, args.file_ids)
    wyniki: dict[str, Any] = {}
    razem = 0
    for kontrola in dict.fromkeys(args.kontrole):
        ctx.check_cancelled()
        if kontrola == "bezpieczenstwo":
            wynik = _semgrep(ctx, cel, args.jezyk, args.limit)
        elif kontrola == "python":
            wynik = _ruff(ctx, cel, args.limit)
        elif kontrola == "powloka":
            wynik = _shellcheck(ctx, cel, args.limit)
        else:
            wynik = _typos(ctx, cel, args.limit)
        wyniki[kontrola] = wynik
        razem += int(wynik["znalezione"])
    podsumowanie = ", ".join(f"{nazwa}: {wynik['znalezione']}" for nazwa, wynik in wyniki.items())
    return ToolResult(
        {"sprawdzono": opis, "kontrole": wyniki},
        f"Kontrola kodu ({opis}) — {podsumowanie}" if razem else f"Kontrola kodu ({opis}) — bez usterek",
    )


# --- audyt strony ---------------------------------------------------------------------------------


def _lighthouse(ctx: ToolContext, adres: str, urzadzenie: str) -> dict[str, Any]:
    """Oceny Lighthouse: szybkość, dostępność, dobre praktyki, SEO."""
    program = _program("lighthouse", "Audyt wydajności stron (Lighthouse)")
    raport = ctx.output_path("lighthouse.json")
    polecenie = [
        program,
        adres,
        "--quiet",
        "--output=json",
        f"--output-path={raport}",
        "--only-categories=performance,accessibility,best-practices,seo",
        "--chrome-flags=--headless=new --no-sandbox --disable-dev-shm-usage",
        "--max-wait-for-load=45000",
    ]
    if urzadzenie == "komputer":
        polecenie.append("--preset=desktop")
    ctx.progress("Lighthouse: pomiar strony w przeglądarce")
    ctx.run_command(polecenie, timeout=CZAS_AUDYTU, cwd=ctx.work_dir)
    if not raport.is_file():
        raise ToolError("Lighthouse nie zapisał raportu.")
    dane = json.loads(raport.read_text(encoding="utf-8"))
    oceny = {
        nazwa: round((dzial.get("score") or 0) * 100)
        for nazwa, dzial in dane.get("categories", {}).items()
        if dzial.get("score") is not None
    }
    audyty = dane.get("audits", {})
    uwagi = []
    for nazwa, dzial in dane.get("categories", {}).items():
        for odnosnik in dzial.get("auditRefs", []):
            audyt = audyty.get(odnosnik.get("id"), {})
            ocena = audyt.get("score")
            if ocena is None or ocena >= 0.9 or not audyt.get("title"):
                continue
            uwagi.append(
                {
                    "dzial": nazwa,
                    "sprawa": str(audyt["title"])[:160],
                    "pomiar": str(audyt.get("displayValue") or "")[:80],
                }
            )
    return {"oceny_na_100": oceny, "do_poprawy": uwagi[:20]}


def _pa11y(ctx: ToolContext, adres: str, limit: int) -> dict[str, Any]:
    """Usterki dostępności WCAG 2.1 AA (pa11y: silniki HTML_CodeSniffer i axe)."""
    program = _program("pa11y", "Audyt dostępności stron (pa11y)")
    ctx.progress("pa11y: kontrola dostępności WCAG")
    wynik = ctx.run_command(
        [
            program,
            "--reporter",
            "json",
            "--standard",
            "WCAG2AA",
            "--runner",
            "htmlcs",
            "--runner",
            "axe",
            "--include-warnings",
            "--threshold",
            "100000",
            "--timeout",
            "60000",
            adres,
        ],
        timeout=CZAS_AUDYTU,
        cwd=ctx.work_dir,
    )
    try:
        zgloszenia = json.loads(wynik.stdout or "[]")
    except json.JSONDecodeError as blad:
        raise ToolError("pa11y nie zwrócił czytelnego raportu dostępności.") from blad
    kolejnosc = {"error": 0, "warning": 1, "notice": 2}
    zgloszenia.sort(key=lambda poz: kolejnosc.get(str(poz.get("type")), 3))
    lista = [
        {
            "waga": zgloszenie.get("type"),
            "zasada": zgloszenie.get("code"),
            "opis": str(zgloszenie.get("message", ""))[:300],
            "element": str(zgloszenie.get("selector", ""))[:160],
        }
        for zgloszenie in zgloszenia
    ]
    bledy = sum(1 for poz in lista if poz["waga"] == "error")
    return {"bledy": bledy, "ostrzezenia": len(lista) - bledy, "lista": lista[:limit]}


class AudytInput(ToolInput):
    site: str = Field(
        default="",
        max_length=64,
        description="Adres strony z modułu Strony (szkic), np. „kawiarnia-pod-lipami”.",
    )
    podstrona: str = Field(
        default="",
        max_length=200,
        description="Plik podstrony w szkicu, np. „cennik.html” (pusto = index.html).",
    )
    adres: str = Field(
        default="",
        max_length=500,
        description="Zamiast szkicu: publiczny adres https:// do zbadania (adresy lokalne są zablokowane).",
    )
    zakres: Literal["wszystko", "dostepnosc", "wydajnosc"] = Field(
        default="wszystko",
        description="dostepnosc = sama kontrola WCAG (szybka); wydajnosc = same pomiary Lighthouse.",
    )
    urzadzenie: Literal["telefon", "komputer"] = Field(
        default="telefon", description="Emulacja urządzenia w pomiarze wydajności."
    )
    limit: int = Field(default=25, ge=5, le=100, description="Najwięcej usterek dostępności w wyniku.")


@registry.register(
    "web_audit",
    """Bada gotową stronę WWW: dostępność według WCAG 2.1 AA (pa11y: brak opisów obrazów, za słaby
kontrast, pola bez etykiet) oraz szybkość, dobre praktyki i SEO (Lighthouse, oceny 0–100).
Działa na szkicu strony z modułu Strony — jeszcze przed publikacją — albo na publicznym adresie.
Stosuj, gdy użytkownik pyta „czy moja strona nie ma błędów dostępności”, „dlaczego strona wolno
się ładuje”, „sprawdź stronę przed publikacją”. Pokazuje usterki; poprawki wprowadzasz sam
narzędziami site_write_file. Żeby zobaczyć, jak strona wygląda, użyj web_screenshot.""",
    AudytInput,
)
def web_audit(ctx: ToolContext, args: AudytInput) -> ToolResult:
    dane: dict[str, Any] = {}
    with _cel_www(ctx, args.site, args.podstrona, args.adres) as (adres, opis):
        dane["zbadano"] = opis
        if args.zakres in {"wszystko", "dostepnosc"}:
            dane["dostepnosc"] = _pa11y(ctx, adres, args.limit)
        if args.zakres in {"wszystko", "wydajnosc"}:
            ctx.check_cancelled()
            dane["wydajnosc"] = _lighthouse(ctx, adres, args.urzadzenie)
    czesci = []
    if "dostepnosc" in dane:
        czesci.append(f"dostępność: {dane['dostepnosc']['bledy']} błędów")
    if "wydajnosc" in dane:
        oceny = dane["wydajnosc"]["oceny_na_100"]
        czesci.append("oceny: " + ", ".join(f"{nazwa} {ocena}" for nazwa, ocena in oceny.items()))
    return ToolResult(dane, f"Audyt ({opis}) — " + "; ".join(czesci))


class ZrzutInput(ToolInput):
    site: str = Field(default="", max_length=64, description="Adres strony z modułu Strony (szkic).")
    podstrona: str = Field(
        default="", max_length=200, description="Plik podstrony w szkicu (pusto = index.html)."
    )
    adres: str = Field(
        default="", max_length=500, description="Zamiast szkicu: publiczny adres https:// strony."
    )
    urzadzenie: Literal["telefon", "tablet", "komputer"] = Field(
        default="komputer", description="Szerokość okna: telefon 390 px, tablet 820 px, komputer 1440 px."
    )
    cala_strona: bool = Field(
        default=True, description="Prawda = cała strona z przewinięciem; fałsz = samo pierwsze okno."
    )
    motyw: Literal["jasny", "ciemny"] = Field(
        default="jasny", description="Tryb systemowy przeglądarki (prefers-color-scheme)."
    )


@registry.register(
    "web_screenshot",
    """Robi zrzut strony WWW w przeglądarce (Playwright) i pokazuje go w rozmowie — szkicu z modułu
Strony albo publicznego adresu, w szerokości telefonu, tabletu lub komputera, w trybie jasnym
lub ciemnym. Stosuj, gdy właśnie napisałeś albo zmieniłeś stronę i chcesz ją zobaczyć zamiast
zgadywać, gdy użytkownik pyta „jak to wygląda na telefonie”, i przed pokazaniem strony do
akceptacji. Ocena liczbowa i lista usterek to web_audit; zrzut ekranu komputera użytkownika
to pc_screenshot.""",
    ZrzutInput,
)
def web_screenshot(ctx: ToolContext, args: ZrzutInput) -> ToolResult:
    program = _program("playwright", "Przeglądarka zrzutów (Playwright)")
    szerokosc, wysokosc = WIDOKI[args.urzadzenie]
    cel = ctx.output_path(f"strona-{args.urzadzenie}.png")
    with _cel_www(ctx, args.site, args.podstrona, args.adres) as (adres, opis):
        polecenie = [
            program,
            "screenshot",
            "--browser=chromium",
            f"--viewport-size={szerokosc},{wysokosc}",
            f"--color-scheme={'dark' if args.motyw == 'ciemny' else 'light'}",
            "--wait-for-timeout=1500",
        ]
        if args.cala_strona:
            polecenie.append("--full-page")
        ctx.progress(f"Zrzut strony ({args.urzadzenie})")
        ctx.run_command([*polecenie, adres, str(cel)], timeout=CZAS_ZRZUTU, cwd=ctx.work_dir)
    if not cel.is_file():
        raise ToolError("Przeglądarka nie zapisała zrzutu strony.")
    with Image.open(cel) as obraz:
        wymiary = obraz.size
        podglad = image_preview(obraz, PODGLAD)
    return ToolResult(
        {"zrzut": opis, "szerokosc": wymiary[0], "wysokosc": wymiary[1]},
        f"Zrzut: {opis} ({args.urzadzenie})",
        images=[podglad],
        files=[OutputFile(cel, cel.name, f"Zrzut strony ({args.urzadzenie})")],
    )


# --- ikony ------------------------------------------------------------------------------------------

#: Zbiory o spójnym rysunku stawiamy wyżej w wynikach — inaczej wygrywają zbiory przypadkowe.
ZESTAWY_PIERWSZEGO_WYBORU = (
    "lucide",
    "tabler",
    "mdi",
    "ph",
    "material-symbols",
    "heroicons",
    "carbon",
    "bi",
    "solar",
    "fa6-solid",
)


def _dopasowane_ikony(zapytanie: str, zestaw: str, limit: int) -> list[str]:
    """Nazwy ikon (``zestaw:nazwa``) pasujące do wszystkich słów zapytania."""
    if not IKONY_INDEKS.is_file():
        raise ToolError("Zbiór ikon Iconify nie jest dostępny na tym serwerze.")
    slowa = [slowo for slowo in re.split(r"[^a-z0-9]+", zapytanie.lower()) if slowo]
    if not slowa:
        raise ToolError("Podaj, czego szukasz — np. „envelope”, „shopping cart”, „arrow right”.")
    prefiks = zestaw.strip().lower()
    trafienia: list[tuple[tuple[int, int, int], str]] = []
    with IKONY_INDEKS.open(encoding="utf-8", errors="replace") as plik:
        for wiersz in plik:
            pelna = wiersz.rstrip("\n")
            if not pelna:
                continue
            nazwa = pelna.split("\t", 1)[0]
            zbior, _, sama = nazwa.partition(":")
            if prefiks and zbior != prefiks:
                continue
            niskie = pelna.lower()
            if not all(slowo in niskie for slowo in slowa):
                continue
            haslo = "-".join(slowa)
            dokladnosc = 0 if sama == haslo else 1 if sama.startswith(haslo) else 2
            preferencja = (
                ZESTAWY_PIERWSZEGO_WYBORU.index(zbior)
                if zbior in ZESTAWY_PIERWSZEGO_WYBORU
                else len(ZESTAWY_PIERWSZEGO_WYBORU)
            )
            trafienia.append(((dokladnosc, preferencja, len(sama)), nazwa))
    trafienia.sort()
    return [nazwa for _, nazwa in trafienia[: limit * 4]]


def _zbior_ikon(zbior: str) -> dict[str, Any]:
    """Plik zbioru Iconify; nazwa jest sprawdzana, więc nie wychodzi poza katalog zbiorów."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", zbior):
        raise ToolError(f"Niepoprawna nazwa zbioru ikon: {zbior!r}.")
    plik = IKONY_JSON / f"{zbior}.json"
    if not plik.is_file() or not plik.resolve().is_relative_to(IKONY_JSON.resolve()):
        raise ToolError(f"Zbiór ikon {zbior!r} nie jest dostępny na tym serwerze.")
    return json.loads(plik.read_text(encoding="utf-8"))


def _rysunek_ikony(dane: dict[str, Any], nazwa: str) -> tuple[str, int, int] | None:
    """Treść ikony i jej pole rysunku (z rozwinięciem odsyłaczy do ikony źródłowej)."""
    ikony = dane.get("icons", {})
    aliasy = dane.get("aliases", {})
    biezaca = nazwa
    for _ in range(5):
        if biezaca in ikony:
            ikona = ikony[biezaca]
            return (
                str(ikona.get("body", "")),
                int(ikona.get("width") or dane.get("width") or 24),
                int(ikona.get("height") or dane.get("height") or 24),
            )
        alias = aliasy.get(biezaca)
        if not alias:
            return None
        biezaca = str(alias.get("parent", ""))
    return None


def _svg_ikony(tresc: str, szerokosc: int, wysokosc: int, kolor: str, rozmiar: int) -> str:
    """Gotowy dokument SVG jednej ikony."""
    wymiar = f' width="{rozmiar}" height="{rozmiar}"' if rozmiar else ""
    styl = f' style="color:{kolor}"' if kolor != "currentColor" else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}"'
        f"{wymiar}{styl}>{tresc}</svg>"
    )


def _podglad_ikon(ctx: ToolContext, ikony: list[dict[str, Any]]) -> list[bytes]:
    """Pasek z wybranymi ikonami — żeby model zobaczył, co proponuje (gdy jest Inkscape)."""
    if not shutil.which("inkscape"):
        return []
    krok, bok = 96, 64
    czesci = []
    for numer, ikona in enumerate(ikony):
        skala = bok / max(ikona["szerokosc"], ikona["wysokosc"])
        czesci.append(
            f'<g transform="translate({numer * krok + 16},16) scale({skala:.4f})">{ikona["tresc"]}</g>'
        )
    arkusz = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{len(ikony) * krok}" height="96" '
        f'viewBox="0 0 {len(ikony) * krok} 96"><rect width="100%" height="100%" fill="#ffffff"/>'
        f'<g color="#18181b">{"".join(czesci)}</g></svg>'
    )
    zrodlo = ctx.output_path("ikony-podglad.svg")
    zrodlo.write_text(arkusz, encoding="utf-8")
    cel = ctx.output_path("ikony-podglad.png")
    try:
        ctx.run_command(
            ["inkscape", str(zrodlo), "--export-type=png", f"--export-filename={cel}"], timeout=120
        )
    except ToolError:
        return []
    if not cel.is_file():
        return []
    with Image.open(cel) as obraz:
        return [image_preview(obraz, PODGLAD)]


class IkonyInput(ToolInput):
    zapytanie: str = Field(
        min_length=2,
        max_length=60,
        description="Czego szukasz — po angielsku, np. „envelope”, „shopping cart”, „arrow right”.",
    )
    zestaw: str = Field(
        default="",
        max_length=40,
        description="Ograniczenie do jednego zbioru, np. „lucide”, „mdi”, „tabler”, „material-symbols”.",
    )
    limit: int = Field(default=6, ge=1, le=20, description="Ile propozycji zwrócić.")
    kolor: str = Field(
        default="currentColor",
        max_length=40,
        description="Barwa ikony: „currentColor” (dziedziczy kolor tekstu), „#RRGGBB” albo nazwa barwy.",
    )
    rozmiar_px: int = Field(
        default=0, ge=0, le=512, description="Rozmiar w pikselach; 0 = bez wymiarów (ikona skaluje się)."
    )
    do_strony: str = Field(
        default="",
        max_length=64,
        description="Adres strony z modułu Strony: zapisz znalezione ikony jako pliki SVG w jej szkicu.",
    )
    katalog: str = Field(
        default="img/ikony", max_length=200, description="Katalog w szkicu strony dla zapisanych ikon."
    )


@registry.register(
    "icon_find",
    """Znajduje gotową ikonę w zbiorze Iconify (ponad 400 tys. znaków: Lucide, Material, Tabler,
Phosphor, logotypy marek) i oddaje ją jako kod SVG — a na życzenie zapisuje jako plik w szkicu
strony. Stosuj, gdy w projekcie graficznym albo na stronie potrzebny jest symbol: koperta,
telefon, koszyk, strzałka, znak serwisu. Kod SVG możesz wkleić wprost do treści strony albo do
rysunku w design_vector, zamiast rysować symbol ręcznie. Zapytanie podawaj po angielsku.""",
    IkonyInput,
)
def icon_find(ctx: ToolContext, args: IkonyInput) -> ToolResult:
    if not BARWA.match(args.kolor):
        raise ToolError(f"Niedozwolona barwa ikony: {args.kolor!r}")
    nazwy = _dopasowane_ikony(args.zapytanie, args.zestaw, args.limit)
    if not nazwy:
        raise ToolError(f"Nie znalazłem ikony dla {args.zapytanie!r} — spróbuj innego słowa po angielsku.")
    zbiory: dict[str, dict[str, Any]] = {}
    znalezione: list[dict[str, Any]] = []
    for pelna in nazwy:
        ctx.check_cancelled()
        if len(znalezione) >= args.limit:
            break
        if not NAZWA_IKONY.fullmatch(pelna):
            continue
        zbior, _, nazwa = pelna.partition(":")
        if zbior not in zbiory:
            zbiory[zbior] = _zbior_ikon(zbior)
        rysunek = _rysunek_ikony(zbiory[zbior], nazwa)
        if rysunek is None:
            continue
        tresc, szerokosc, wysokosc = rysunek
        znalezione.append(
            {
                "nazwa": pelna,
                "tresc": tresc,
                "szerokosc": szerokosc,
                "wysokosc": wysokosc,
                "svg": _svg_ikony(tresc, szerokosc, wysokosc, args.kolor, args.rozmiar_px),
            }
        )
    if not znalezione:
        raise ToolError(f"Nie udało się odczytać ikon dla {args.zapytanie!r}.")

    zapisane: list[str] = []
    if args.do_strony:
        store = site_store(ctx.settings)
        try:
            katalog = check_path(args.katalog, allow_empty=True)
            for ikona in znalezione:
                sciezka = f"{katalog}/{ikona['nazwa'].replace(':', '-')}.svg" if katalog else ""
                zapis = store.write_bytes(
                    args.do_strony,
                    sciezka or f"{ikona['nazwa'].replace(':', '-')}.svg",
                    ikona["svg"].encode("utf-8"),
                )
                zapisane.append(zapis["path"])
        except SiteError as blad:
            raise ToolError(str(blad)) from blad

    dane = {
        "ikony": [{"nazwa": poz["nazwa"], "svg": poz["svg"]} for poz in znalezione],
        "zapisane_pliki": zapisane,
    }
    podsumowanie = f"Ikony „{args.zapytanie}”: {len(znalezione)}"
    return ToolResult(
        dane,
        podsumowanie + (f", zapisane w stronie {args.do_strony}" if zapisane else ""),
        images=_podglad_ikon(ctx, znalezione),
    )


# --- odchudzanie plików strony ----------------------------------------------------------------------


class OptymalizacjaInput(ToolInput):
    site: str = Field(max_length=64, description="Adres strony z modułu Strony (szkic).")
    rodzaj: Literal["wszystko", "png", "svg"] = Field(
        default="wszystko", description="Które pliki odchudzić."
    )
    limit_plikow: int = Field(default=100, ge=1, le=400, description="Najwięcej plików w jednym przebiegu.")


@registry.register(
    "site_optimize_assets",
    """Odchudza pliki graficzne w szkicu strony bez zmiany wyglądu: PNG (oxipng) i SVG (svgo).
Stosuj, gdy web_audit wytknie zbyt ciężkie obrazy, gdy strona wolno się ładuje albo przed
publikacją. Zmiana jest bezstratna — obraz wygląda tak samo, waży mniej; pliki cięższe po
optymalizacji zostają bez zmian. Do zmiany rozmiaru, kadru czy formatu zdjęć służą narzędzia
obrazów (convert_images), a nie to narzędzie.""",
    OptymalizacjaInput,
)
def site_optimize_assets(ctx: ToolContext, args: OptymalizacjaInput) -> ToolResult:
    katalog = _szkic(ctx, args.site)
    rozszerzenia = {"png": {".png"}, "svg": {".svg"}}.get(args.rodzaj, {".png", ".svg"})
    pliki = [
        plik
        for plik in sorted(katalog.rglob("*"))
        if plik.is_file() and not plik.is_symlink() and plik.suffix.lower() in rozszerzenia
    ][: args.limit_plikow]
    if not pliki:
        raise ToolError(f"Strona {args.site} nie ma plików {' ani '.join(sorted(rozszerzenia))}.")
    store = site_store(ctx.settings)
    zmienione: list[dict[str, Any]] = []
    pominiete: list[str] = []
    przed_razem = po_razem = 0
    for numer, plik in enumerate(pliki, 1):
        ctx.check_cancelled()
        if numer % 10 == 1:
            ctx.progress(f"Odchudzanie plików strony: {numer}/{len(pliki)}")
        wzgledna = plik.relative_to(katalog).as_posix()
        przed = plik.stat().st_size
        cel = ctx.output_path(plik.name)
        try:
            if plik.suffix.lower() == ".svg":
                program = _program("svgo", "Optymalizacja plików SVG (svgo)")
                ctx.run_command(
                    [program, "--multipass", "--quiet", "-i", str(plik), "-o", str(cel)],
                    timeout=CZAS_OPTYMALIZACJI,
                )
            else:
                program = _program("oxipng", "Optymalizacja plików PNG (oxipng)")
                ctx.run_command(
                    [program, "-o", "4", "-s", "--quiet", "--out", str(cel), str(plik)],
                    timeout=CZAS_OPTYMALIZACJI,
                )
        except ToolError:
            pominiete.append(wzgledna)
            continue
        if not cel.is_file():
            pominiete.append(wzgledna)
            continue
        po = cel.stat().st_size
        przed_razem += przed
        po_razem += min(po, przed)
        if po >= przed:
            continue
        try:
            store.write_bytes(args.site, wzgledna, cel.read_bytes())
        except SiteError as blad:
            raise ToolError(str(blad)) from blad
        zmienione.append(
            {"plik": wzgledna, "przed_b": przed, "po_b": po, "zysk_proc": round(100 - po * 100 / przed)}
        )
    zysk = przed_razem - po_razem
    return ToolResult(
        {
            "strona": args.site,
            "sprawdzone": len(pliki),
            "odchudzone": zmienione,
            "pominiete": pominiete,
            "zysk_kb": round(zysk / 1024, 1),
        },
        f"Odchudzono {len(zmienione)} z {len(pliki)} plików strony {args.site} (–{round(zysk / 1024, 1)} KB)",
    )


__all__ = ["code_check", "icon_find", "site_optimize_assets", "web_audit", "web_screenshot"]
