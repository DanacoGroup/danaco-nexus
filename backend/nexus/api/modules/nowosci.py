"""Co nowego w Nexusie — wykaz zmian wydania, czytany z dziennika zmian.

Produkt zmienia się po kilkanaście razy dziennie, a użytkownik nie miał gdzie tego
zobaczyć: jedyną informacją o nowym wydaniu było to, że coś wygląda inaczej. Ten moduł
czyta `CHANGELOG.md` wydania (kopiowany do artefaktu razem z kodem) i oddaje pozycje
najnowszej sekcji w postaci, którą da się pokazać w oknie.

Nie ma tu żadnych danych użytkownika, ale wykaz i tak jest za sesją: to, co dokładnie
zmieniło się w środku produktu, nie musi być publiczne.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from nexus.api.auth import require_session

router = APIRouter(prefix="/api/nowosci", tags=["nowosci"], dependencies=[Depends(require_session)])

#: Ile pozycji oddajemy. Dziennik bywa długi, a okno ma pokazać, co się zmieniło teraz.
LIMIT = 12
#: Ile znaków treści pokazujemy. Wpisy w dzienniku są pisane dla kogoś, kto wchodzi w kod;
#: w oknie ma zostać zdanie, po którym wiadomo, czego dotyczy zmiana.
DLUGOSC_TRESCI = 220
#: Nagłówek sekcji dziennika: „## [Nieopublikowane]” albo „## [1.2.0] - 2026-09-21”.
SEKCJA = re.compile(r"^##\s+\[([^\]]+)\](?:\s*[-–]\s*(\S+))?\s*$")
#: Pozycja: „- **Tytuł.** treść…”, ciąg dalszy we wciętych wierszach.
POZYCJA = re.compile(r"^-\s+\*\*(.+?)\*\*\s*(.*)$")
#: Nagłówek rodzaju zmian w sekcji („### Dodano”, „### Zmieniono”).
RODZAJ = re.compile(r"^###\s+(.+?)\s*$")


def _dziennik(request: Request) -> Path:
    """Ścieżka dziennika zmian wydania: obok katalogu z gotowym interfejsem."""
    statyczne = Path(request.app.state.settings.static_dir).resolve()
    # <wydanie>/frontend/dist -> <wydanie>/CHANGELOG.md
    return statyczne.parent.parent / "CHANGELOG.md"


def _oczysc(tekst: str) -> str:
    """Zapis Markdown na zwykły tekst — okno pokazuje zdania, nie składnię.

    Czyścimy dopiero złożony akapit, nie pojedyncze wiersze: wyróżnienia w dzienniku
    potrafią przechodzić przez złamanie wiersza i para gwiazdek rozjeżdża się na dwa
    wiersze, więc czyszczone osobno zostawiałyby gwiazdki w oknie.
    """
    tekst = re.sub(r"`([^`]+)`", r"\1", tekst)
    tekst = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", tekst)
    tekst = tekst.replace("**", "")
    # Pochylenie (`*słowo*`) też jest składnią, nie treścią. Zdejmujemy je po wyróżnieniu,
    # żeby nie rozbić pary gwiazdek na dwie osobne.
    tekst = re.sub(r"\*([^*\n]+)\*", r"\1", tekst)
    return re.sub(r"\s+", " ", tekst).strip()


def _skroc(tekst: str, limit: int = DLUGOSC_TRESCI) -> str:
    """Pierwsze zdania mieszczące się w limicie; reszta zostaje w dzienniku."""
    tekst = tekst.strip()
    if len(tekst) <= limit:
        return tekst
    uciete = tekst[:limit]
    kropka = max(uciete.rfind(". "), uciete.rfind("; "))
    if kropka > limit // 2:
        return uciete[: kropka + 1]
    spacja = uciete.rfind(" ")
    return (uciete[:spacja] if spacja > 0 else uciete).rstrip(" ,;–—") + "…"


def czytaj_nowosci(tresc: str, limit: int = LIMIT) -> dict[str, Any]:
    """Pozycje najnowszej sekcji dziennika zmian."""
    wiersze = tresc.splitlines()
    wersja = ""
    data = ""
    rodzaj = ""
    pozycje: list[dict[str, str]] = []
    biezaca: dict[str, str] | None = None
    w_sekcji = False
    for wiersz in wiersze:
        naglowek = SEKCJA.match(wiersz)
        if naglowek:
            if w_sekcji:
                break  # druga sekcja — mamy już najnowszą
            wersja, data = naglowek.group(1), naglowek.group(2) or ""
            w_sekcji = True
            continue
        if not w_sekcji:
            continue
        podtytul = RODZAJ.match(wiersz)
        if podtytul:
            rodzaj = podtytul.group(1)
            continue
        pozycja = POZYCJA.match(wiersz)
        if pozycja:
            if biezaca:
                pozycje.append(biezaca)
            biezaca = {"tytul": pozycja.group(1), "tresc": pozycja.group(2), "rodzaj": rodzaj}
            continue
        if biezaca is not None and wiersz.startswith("  ") and wiersz.strip():
            biezaca["tresc"] = f"{biezaca['tresc']} {wiersz.strip()}"
    if biezaca:
        pozycje.append(biezaca)
    pozycje = [
        {
            "tytul": _oczysc(p["tytul"]).rstrip(".:•— "),
            "tresc": _skroc(_oczysc(p["tresc"])),
            "rodzaj": p["rodzaj"],
        }
        for p in pozycje
    ]
    return {"wersja": wersja, "data": data, "pozycje": pozycje[:limit], "wszystkich": len(pozycje)}


@router.get("")
async def nowosci(request: Request) -> dict[str, Any]:
    """Co przyniosło bieżące wydanie."""
    plik = _dziennik(request)
    try:
        tresc = plik.read_text(encoding="utf-8")
    except OSError:
        return {"wersja": "", "data": "", "pozycje": [], "wszystkich": 0, "wydanie": ""}
    dane = czytaj_nowosci(tresc)
    znacznik = plik.parent / "WYDANIE-DATA"
    try:
        surowa = znacznik.read_text(encoding="utf-8").strip()
        dane["wydanie"] = datetime.fromisoformat(surowa).date().isoformat()
    except (OSError, ValueError):
        dane["wydanie"] = ""
    return dane
