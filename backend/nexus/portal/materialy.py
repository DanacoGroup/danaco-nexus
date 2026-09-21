"""Wczytywanie materiałów portalu z plików Markdown do bazy treści.

Blog, centrum wiedzy i dokumentacja trzymają treść w bazie (``portal_content``), a nie na dysku,
bo portal buduje z niej adresy, zajawki, indeks wyszukiwania i mapę witryny. Materiały powstają
jednak w repozytorium — jako pliki, które da się przejrzeć w historii zmian. Ten moduł przenosi
jedne w drugie: czyta katalog plików ``NN-adres.md`` i zapisuje je jako pozycje wybranego rodzaju.

Zapis jest powtarzalny: pozycja o tym samym rodzaju i adresie zostaje nadpisana, a nie powielona,
więc poprawiony plik wystarczy wczytać ponownie. Domyślnie materiał ląduje jako szkic — publikacja
jest osobną decyzją (``--opublikuj`` albo panel administratora).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from nexus.db import Database
from nexus.portal import repozytorium, tresc
from nexus.portal.repozytorium import BrakTresci, DaneTresci

# Nazwa pliku: dwucyfrowy numer porządkowy, myślnik, adres pozycji. Numer ustala kolejność
# w spisie dokumentacji; pozostałe rodzaje sortują się datą, więc tam jest tylko informacją.
NAZWA = re.compile(r"^(?P<numer>\d{2})-(?P<slug>[a-z0-9-]+)\.md$")
# Pliki katalogu, które nie są materiałem (opis katalogu dla człowieka).
POMIJANE = frozenset({"README.md"})


class BladMaterialu(ValueError):
    """Plik nie nadaje się na pozycję treści portalu."""


@dataclass(frozen=True)
class Material:
    """Pozycja treści odczytana z pliku, gotowa do zapisu."""

    rodzaj: str
    slug: str
    tytul: str
    tresc_md: str
    pozycja: int


def _rozbierz(plik: Path, rodzaj: str) -> Material:
    """Materiał z pojedynczego pliku; tytuł bierze z nagłówka ``# ``, resztę traktuje jako treść."""
    nazwa = NAZWA.match(plik.name)
    if nazwa is None:
        raise BladMaterialu(f"{plik.name}: nazwa musi mieć postać „NN-adres.md”.")
    wiersze = plik.read_text(encoding="utf-8").splitlines()
    naglowek = next((i for i, wiersz in enumerate(wiersze) if wiersz.startswith("# ")), None)
    if naglowek is None:
        raise BladMaterialu(f"{plik.name}: brak nagłówka „# Tytuł” w pierwszych wierszach.")
    tytul = wiersze[naglowek][2:].strip()
    if not tytul:
        raise BladMaterialu(f"{plik.name}: nagłówek „# ” jest pusty.")
    # Tytuł rysuje strona pozycji osobno (``frontend/src/portal/strony/Wpis.tsx``), więc treść
    # zaczyna się dopiero pod nagłówkiem — inaczej czytelnik zobaczyłby go dwa razy.
    body = "\n".join(wiersze[naglowek + 1 :]).strip()
    if not body:
        raise BladMaterialu(f"{plik.name}: pod nagłówkiem nie ma treści.")
    return Material(
        rodzaj=tresc.sprawdz_rodzaj(rodzaj),
        slug=tresc.sprawdz_slug(nazwa.group("slug")),
        tytul=tytul[:200],
        tresc_md=body,
        pozycja=int(nazwa.group("numer")),
    )


# Korzeń repozytorium: ``backend/nexus/portal/materialy.py`` → trzy poziomy w górę.
KORZEN = Path(__file__).resolve().parents[3]


def rozwin_katalog(podany: Path) -> Path:
    """Katalog względem bieżącego miejsca, a gdy tam go nie ma — względem korzenia repozytorium.

    Usługa pracuje w ``backend/``, a materiały leżą w ``docs/`` obok niego, więc ścieżka
    „taka, jak w dokumentacji” nie trafiałaby w cel przy uruchomieniu z katalogu usługi.
    """
    if podany.is_absolute() or podany.is_dir():
        return podany
    zapasowy = KORZEN / podany
    return zapasowy if zapasowy.is_dir() else podany


def wczytaj_katalog(katalog: Path, rodzaj: str) -> list[Material]:
    """Materiały z katalogu, w kolejności numerów w nazwach plików."""
    katalog = rozwin_katalog(katalog)
    if not katalog.is_dir():
        raise BladMaterialu(f"{katalog}: nie ma takiego katalogu.")
    pliki = sorted(p for p in katalog.glob("*.md") if p.name not in POMIJANE)
    if not pliki:
        raise BladMaterialu(f"{katalog}: brak plików „NN-adres.md”.")
    materialy = [_rozbierz(plik, rodzaj) for plik in pliki]
    # Dwa pliki o tym samym adresie (np. „01-start.md” i „02-start.md”) nie są błędem dla
    # repozytorium, ale byłyby nim w portalu: drugi dostałby od niego adres „start-2”,
    # inny niż nazwa pliku. Lepiej powiedzieć to teraz niż zostawić rozjazd w bazie.
    adresy = [material.slug for material in materialy]
    powtorzone = sorted({adres for adres in adresy if adresy.count(adres) > 1})
    if powtorzone:
        raise BladMaterialu(f"{katalog}: ten sam adres w kilku plikach: {', '.join(powtorzone)}.")
    return materialy


async def zapisz(
    database: Database,
    materialy: list[Material],
    *,
    opublikuj: bool = False,
    autor: str = "",
    synchronizuj: bool = False,
) -> list[tuple[str, str]]:
    """Zapisuje materiały; zwraca pary ``(adres, „nowa”, „zmieniona” albo „usunięta”)``.

    Przy ``synchronizuj`` katalog jest jedynym źródłem prawdy dla swojego rodzaju: pozycje
    tego rodzaju, których nie ma wśród plików, zostają usunięte z bazy. Bez tej opcji
    wczytanie tylko dokłada i nadpisuje, a materiał wycofany z repozytorium zostaje
    w portalu — co przy poprawianiu treści łatwo przeoczyć.
    """
    status = "opublikowany" if opublikuj else "szkic"
    wynik: list[tuple[str, str]] = []
    async with database.session() as session:
        for material in materialy:
            dane = DaneTresci(
                kind=material.rodzaj,
                slug=material.slug,
                title=material.tytul,
                excerpt="",
                body=material.tresc_md,
                author=autor,
                tags=[],
                status=status,
                seo={},
                position=material.pozycja,
            )
            try:
                istniejaca = await repozytorium.pobierz(
                    session, material.rodzaj, material.slug, tylko_opublikowane=False
                )
            except BrakTresci:
                await repozytorium.utworz(session, dane)
                wynik.append((f"{material.rodzaj}/{material.slug}", "nowa"))
            else:
                await repozytorium.zmien(session, istniejaca, dane)
                wynik.append((f"{material.rodzaj}/{material.slug}", "zmieniona"))
        if synchronizuj:
            wynik.extend(await _usun_spoza_katalogu(session, materialy))
    return wynik


async def _usun_spoza_katalogu(
    session: AsyncSession, materialy: list[Material]
) -> list[tuple[str, str]]:
    """Usuwa pozycje rodzaju, których nie ma wśród wczytanych plików."""
    rodzaje = {material.rodzaj for material in materialy}
    zachowane = {(material.rodzaj, material.slug) for material in materialy}
    usuniete: list[tuple[str, str]] = []
    for rodzaj in sorted(rodzaje):
        # Spis jest stronicowany, a rodzaj może mieć więcej pozycji niż jedna strona.
        # Zbieramy wszystkie przed usuwaniem: kasowanie w trakcie przewijania przesuwałoby
        # kolejne strony i część pozycji przepadłaby z pola widzenia.
        obce: list[tuple[str, str]] = []
        strona_nr = 1
        while True:
            strona = await repozytorium.lista(
                session,
                kind=rodzaj,
                tylko_opublikowane=False,
                strona=strona_nr,
                na_stronie=repozytorium.MAX_NA_STRONIE,
            )
            obce.extend(
                (str(pozycja["id"]), str(pozycja["slug"]))
                for pozycja in strona["items"]
                if (rodzaj, pozycja["slug"]) not in zachowane
            )
            if strona_nr >= int(strona["pages"]):
                break
            strona_nr += 1
        for identyfikator, slug in obce:
            await repozytorium.usun(session, uuid.UUID(identyfikator))
            usuniete.append((f"{rodzaj}/{slug}", "usunięta"))
    return usuniete
