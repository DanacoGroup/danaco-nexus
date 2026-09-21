"""Narzędzia Danaco Web Kit: gotowa witryna z presetu branżowego, a nie pusty plik HTML.

Na serwerze stoi zestaw do budowania stron — rdzeń Astro z 35 typami podstron, motywy,
presety branżowe, biblioteka sekcji, kroje nagłówkowe i kolekcja szablonów otwartych.
Do tej pory agent nie miał do niego dostępu: umiał zapisać plik w szkicu strony
(``site_write_file``) i na tym się kończyło, więc każda witryna powstawała od zera,
podstrona po podstronie.

Te narzędzia podpinają zestaw pod moduł Strony:

* ``site_kit_catalog`` — co jest do wzięcia (presety, motywy, kroje, sekcje, szablony);
* ``site_from_kit`` — generuje witrynę z presetu i motywu, buduje ją offline i wstawia
  gotowe pliki do szkicu strony użytkownika, skąd publikuje ją przyciskiem,
* ``site_from_template`` — wstawia do szkicu gotową, już zbudowaną witrynę z kolekcji
  szablonów otwartych (bez budowania, w sekundy).

Generator pracuje w katalogu roboczym zadania i instaluje zależności ze wspólnego
magazynu pnpm (``--offline``), więc budowa nie wychodzi do sieci.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from pydantic import Field

from nexus.tools.base import ToolContext, ToolError, ToolInput, ToolResult, registry
from nexus.tworczy.strony import MAX_FILES, SiteError, site_store

KIT = Path("/danaco/programy/web/kit")
KOLEKCJA = Path("/danaco/programy/web/kolekcja")
GENERATOR = "/danaco/programy/bin/danaco-nowa-strona"
GENERATOR_Z_MAPY = "/danaco/programy/bin/danaco-witryna-z-mapy"

# Budowa witryny z presetu to instalacja zależności offline i render kilkudziesięciu
# podstron — to minuty, nie sekundy.
CZAS_GENEROWANIA_S = 900
CZAS_BUDOWY_S = 900
# Zabezpieczenie przed wrzuceniem do szkicu całego `node_modules`, gdyby budowa padła.
# Duże szablony (panele administracyjne, sklepy) potrafią mieć kilka tysięcy plików wyniku,
# więc limit jest wyżej niż początkowe 1800 — chodzi o odcięcie awarii, nie dużych witryn.
MAX_PLIKOW = 9000
# Pliki, których w szkicu strony nie ma po co trzymać.
POMIJANE = {".DS_Store", "Thumbs.db"}


def _czytaj_json(sciezka: Path) -> Any:
    try:
        return json.loads(sciezka.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _lista_katalogow(katalog: Path) -> list[str]:
    if not katalog.is_dir():
        return []
    return sorted(p.name for p in katalog.iterdir() if p.is_dir() and not p.name.startswith("_"))


def _presety() -> list[dict[str, Any]]:
    """Presety branżowe z krótkim opisem z ``meta.json`` (gdy preset go ma)."""
    wynik: list[dict[str, Any]] = []
    for nazwa in _lista_katalogow(KIT / "presets"):
        meta = _czytaj_json(KIT / "presets" / nazwa / "meta.json") or {}
        wynik.append(
            {
                "preset": nazwa,
                "opis": str(meta.get("opis") or meta.get("description") or ""),
                "motywy_zalecane": meta.get("motywy") or meta.get("themes") or [],
            }
        )
    return wynik


def _liczba_sekcji() -> int:
    """Ile gotowych sekcji leży w bibliotece (pliki, nie rodziny)."""
    sekcje = KIT / "sections"
    return sum(1 for _ in sekcje.rglob("*.astro")) if sekcje.is_dir() else 0


def _sekcje(igla: str, limit: int) -> list[dict[str, Any]]:
    """Gotowe sekcje po nazwie i opisie — to, czym agent może obłożyć podstronę.

    Do tej pory spis podawał wyłącznie nazwy rodzin („hero”, „pricing”), więc sto
    kilkadziesiąt gotowych sekcji było dla agenta bezimienne i nie dało się żadnej wskazać.
    Katalog bez składnika (``Section.astro``) pomijamy — taka pozycja obiecuje sekcję,
    której nie ma.
    """
    korzen = KIT / "sections"
    if not korzen.is_dir():
        return []
    wynik: list[dict[str, Any]] = []
    for skladnik in sorted(korzen.glob("*/*/Section.astro")):
        katalog = skladnik.parent
        identyfikator = f"{katalog.parent.name}/{katalog.name}"
        meta = _czytaj_json(katalog / "meta.json") or {}
        opis = str(meta.get("description") or meta.get("opis") or "")
        tagi = meta.get("tags") or []
        opisane = f"{identyfikator} {meta.get('name') or ''} {opis} {' '.join(map(str, tagi))}"
        if igla and igla not in opisane.lower():
            continue
        wynik.append(
            {
                "id": identyfikator,
                "nazwa": meta.get("name") or katalog.name,
                "opis": opis[:200],
                "warianty": meta.get("variants") or [],
                "tagi": tagi,
            }
        )
        if len(wynik) >= limit:
            break
    return wynik


def _kroje() -> list[str]:
    kroje = KIT / "core" / "kroje"
    if kroje.is_dir():
        return _lista_katalogow(kroje)
    return _lista_katalogow(KIT / "themes" / "_tools" / "kroje")


def _kolekcja() -> dict[str, Any]:
    """Kolekcja szablonów i bibliotek bloków (projekty otwarte, każdy z licencją).

    Zbiorczy wykaz (``kolekcja.json``) bywa nieobecny — wtedy czytamy ``meta.json`` każdego
    szablonu. Bez tego narzędzie zgłaszało zero szablonów, choć na dysku leżało ich
    kilkadziesiąt, w tym kilkadziesiąt z gotową, zbudowaną witryną.
    """
    # Pierwszeństwo ma stan na dysku: zbiorczy wykaz bywa starszy od kolekcji (dochodzą
    # nowe szablony), a narzędzie ma mówić, co naprawdę da się dziś wziąć.
    pozycje: list[Any] = [
        meta
        for katalog in sorted((KOLEKCJA / "szablony").glob("*/meta.json"))
        if isinstance(meta := _czytaj_json(katalog), dict)
    ]
    if not pozycje:
        dane = _czytaj_json(KOLEKCJA / "kolekcja.json") or _czytaj_json(KIT / "catalog" / "kolekcja.json")
        pozycje = dane.get("templates") or [] if isinstance(dane, dict) else []
    szablony = [
        {
            "id": pozycja.get("id"),
            "nazwa": pozycja.get("nazwa"),
            "stos": pozycja.get("stos"),
            "charakter": pozycja.get("charakter"),
            "licencja": pozycja.get("licencja"),
            "liczba_stron": pozycja.get("liczba_stron"),
            # Gotowa witryna = da się ją wstawić do szkicu bez budowania (site_from_template).
            "gotowa_witryna": (KOLEKCJA / "szablony" / str(pozycja.get("id")) / "witryna").is_dir(),
            "opis": str(pozycja.get("opis") or "")[:200],
        }
        for pozycja in pozycje
        if isinstance(pozycja, dict)
    ]
    return {
        "szablony": szablony,
        "biblioteki_blokow": _lista_katalogow(KOLEKCJA / "bloki"),
    }


class KatalogInput(ToolInput):
    szczegoly: bool = Field(
        False,
        description="Dołącz pełną listę szablonów kolekcji zewnętrznej (kilkadziesiąt pozycji).",
    )
    szukaj_sekcji: str = Field(
        "",
        max_length=60,
        description=(
            "Fragment nazwy, opisu albo tagu sekcji (np. „cennik”, „opinie”, „hero”, „faq”). "
            "Pusto = początek spisu sekcji."
        ),
    )
    limit_sekcji: int = Field(
        25, ge=1, le=120, description="Ile gotowych sekcji wypisać (spis ma sto kilkadziesiąt pozycji)."
    )


@registry.register(
    "site_kit_catalog",
    """Pokazuje, z czego można zbudować witrynę, zanim powstanie pierwsza strona.
Zestaw Danaco Web Kit ma presety branżowe (gotowa struktura i treści), motywy, kroje nagłówkowe,
nazwane sekcje z opisami, szablony aplikacji oraz kolekcję szablonów otwartych. Bierz go przed
budową witryny, żeby nie pisać od zera tego, co jest już gotowe.""",
    KatalogInput,
)
def site_kit_catalog(ctx: ToolContext, args: KatalogInput) -> ToolResult:
    if not KIT.is_dir():
        raise ToolError("Zestaw Danaco Web Kit nie jest zainstalowany na tym serwerze.")
    kolekcja = _kolekcja()
    dane: dict[str, Any] = {
        "presety": _presety(),
        "motywy": _lista_katalogow(KIT / "themes"),
        "kroje_naglowkow": _kroje(),
        # Rodziny sekcji (katalogi) i liczba gotowych sekcji w środku: samo „22 rodzaje”
        # zaniżało obraz zestawu, w którym leży sto kilkadziesiąt gotowych sekcji.
        "rodzaje_sekcji": _lista_katalogow(KIT / "sections"),
        "liczba_sekcji": _liczba_sekcji(),
        "sekcje": _sekcje(args.szukaj_sekcji.strip().lower(), args.limit_sekcji),
        "szablony_aplikacji": _lista_katalogow(KIT / "apps"),
        "kolekcja_szablonow": len(kolekcja["szablony"]),
        "biblioteki_blokow": kolekcja["biblioteki_blokow"],
    }
    if args.szczegoly:
        dane["kolekcja"] = kolekcja["szablony"]
    podsumowanie = (
        f"Web Kit: {len(dane['presety'])} presetów branżowych, {len(dane['motywy'])} motywów, "
        f"{dane['liczba_sekcji']} sekcji w {len(dane['rodzaje_sekcji'])} rodzinach, "
        f"{dane['kolekcja_szablonow']} szablonów w kolekcji "
        f"({sum(1 for s in kolekcja['szablony'] if s['gotowa_witryna'])} z gotową witryną)."
    )
    return ToolResult(dane, podsumowanie)


class ZKituInput(ToolInput):
    site: str = Field(
        description="Adres strony użytkownika (np. 'kancelaria-nowak'). Powstanie, jeśli jeszcze jej nie ma.",
        max_length=80,
    )
    preset: str = Field(
        "",
        description="Preset branżowy z site_kit_catalog (np. 'law-firm', 'restaurant'). "
        "Pusto = witryna demonstracyjna rdzenia ze wszystkimi typami podstron.",
        max_length=60,
    )
    motyw: str = Field(
        "", description="Motyw wizualny; pusto = pierwszy zalecany przez preset.", max_length=60
    )
    nazwa: str = Field("", description="Nazwa marki w nagłówku i stopce witryny.", max_length=120)
    kolor: str = Field(
        "",
        description="Kolor główny marki jako '#RRGGBB'. Serwer przelicza z niego pełną skalę "
        "barw z kontrastem AA.",
        max_length=9,
    )
    kroj_naglowkow: str = Field("", description="Krój nagłówków z site_kit_catalog.", max_length=60)
    tytul: str = Field("", description="Tytuł strony w module Strony (gdy powstaje nowa).", max_length=120)


# Presety branżowe nazywają część podstron po swojemu („menu”, „product-index”,
# „courses-index”), a rdzeń zestawu zna 35 typów i garść nazw zastępczych. Brakujące
# nazwy wywalały budowę na pierwszej takiej podstronie: dziewięć presetów na dwanaście
# w ogóle nie dawało się zbudować. Rdzeń leży w katalogu programów serwera (tylko do
# odczytu), więc mapę uzupełniamy w wygenerowanym projekcie — tuż przed budową.
ALIASY_TYPOW: dict[str, dict[str, str]] = {
    # Karta dań i jej kategorie (restaurant).
    "menu": {"type": "product-catalog"},
    "menu-category": {"type": "category"},
    "menu-item": {"type": "product"},
    # Sklep i katalog (ecommerce-showcase).
    "product-index": {"type": "product-catalog"},
    "product-category": {"type": "category"},
    "product-collection": {"type": "category"},
    "collection-index": {"type": "category"},
    "listing-index": {"type": "product-catalog"},
    # Spisy i katalogi (education, legal-portal, institution, saas).
    "category-index": {"type": "category"},
    "courses-index": {"type": "category"},
    "features-index": {"type": "category"},
    "integrations-index": {"type": "category"},
    "solutions-index": {"type": "category"},
    "directory": {"type": "locations"},
    "events-index": {"type": "events-list"},
    "docs-index": {"type": "docs"},
    "glossary-index": {"type": "knowledge-base"},
    "resources": {"type": "knowledge-base"},
    "documents": {"type": "docs"},
    # Pojedyncze podstrony — elementy kolekcji nazywane przez presety po swojemu.
    "feature": {"type": "service-detail"},
    "solution": {"type": "service-detail"},
    "service-card": {"type": "service-detail"},
    "course": {"type": "service-detail"},
    "integration": {"type": "service-detail"},
    "guide": {"type": "docs-article"},
    "doc": {"type": "docs-article"},
    "resource": {"type": "docs-article"},
    "glossary-term": {"type": "docs-article"},
    "docs-page": {"type": "docs-article"},
    "changelog-entry": {"type": "blog-post"},
    "news-item": {"type": "blog-post"},
    "level": {"type": "service-detail"},
    "department": {"type": "service-detail"},
    "unit": {"type": "service-detail"},
    "procedure": {"type": "service-detail"},
    "document": {"type": "docs-article"},
    "tender": {"type": "docs-article"},
    "office": {"type": "location"},
    "article": {"type": "blog-post"},
    "news": {"type": "blog-post"},
    "changelog": {"type": "docs"},
    "project": {"type": "portfolio-item"},
    "listing": {"type": "portfolio-item"},
    "realization": {"type": "portfolio-item"},
    "case": {"type": "case-study"},
    "store": {"type": "location"},
    "branch": {"type": "location"},
    "person": {"type": "team-member"},
    "doctor": {"type": "team-member"},
    "lawyer": {"type": "team-member"},
    "specialist": {"type": "team-member"},
}


def _uzupelnij_aliasy(cel: Path) -> int:
    """Dopisuje brakujące nazwy zastępcze typów podstron do wygenerowanego projektu."""
    plik = cel / "src" / "lib" / "page-types.ts"
    if not plik.is_file():
        return 0
    tresc = plik.read_text(encoding="utf-8")
    brakujace = {
        nazwa: cel_aliasu
        for nazwa, cel_aliasu in ALIASY_TYPOW.items()
        if f'"{nazwa}":' not in tresc and f"\n  {nazwa}:" not in tresc
    }
    if not brakujace:
        return 0
    wpisy = "\n".join(
        f'  "{nazwa}": {{ type: "{cel_aliasu["type"]}" }},' for nazwa, cel_aliasu in brakujace.items()
    )
    plik.write_text(
        f"{tresc}\n// Nazwy zastępcze dołożone przez Danaco Nexus (site_from_kit).\n"
        f"Object.assign(TYPE_ALIASES, {{\n{wpisy}\n}});\n",
        encoding="utf-8",
    )
    return len(brakujace)


def _polecenie_generatora(args: ZKituInput, cel: Path) -> list[str]:
    polecenie = [GENERATOR, str(cel)]
    if args.preset:
        polecenie += ["--preset", args.preset]
    if args.motyw:
        polecenie += ["--motyw", args.motyw]
    if args.nazwa:
        polecenie += ["--nazwa", args.nazwa]
    if args.kolor:
        polecenie += ["--kolor", args.kolor]
    if args.kroj_naglowkow:
        polecenie += ["--kroj-naglowkow", args.kroj_naglowkow]
    polecenie.append("--bez-git")
    return polecenie


def _wynik_budowy(cel: Path) -> Path:
    """Katalog ze zbudowaną witryną (Astro: ``dist``; Next w trybie eksportu: ``out``)."""
    for nazwa in ("dist", "out", "build"):
        katalog = cel / nazwa
        if katalog.is_dir() and any(katalog.rglob("*.html")):
            return katalog
    raise ToolError(
        "Budowa nie zostawiła gotowych stron (brak katalogu dist/out z plikami HTML). "
        "Sprawdź preset i motyw albo zbuduj witrynę mniejszą."
    )


#: Odwołanie do zasobu spoza witryny (CDN) i odwołanie od korzenia domeny. Jedno i drugie
#: psuje stronę użytkownika: pierwsze wymaga sieci i wysyła gościa na cudzy serwer, drugie
#: nie działa, bo strony stoją pod ``/s/<adres>/``, a nie w korzeniu domeny.
#: Liczymy wyłącznie wczytywanie zasobów (skrypt, arkusz, obraz, film), nie zwykłe odsyłacze
#: — ``<a href="https://…">`` w treści strony jest w porządku i nie jest usterką.
ZASOB_Z_SIECI = re.compile(
    r"""<(?:script|img|source|iframe|video|audio)\b[^>]*\bsrc\s*=\s*["']https?://"""
    r"""|<link\b[^>]*\bhref\s*=\s*["']https?://""",
    re.I,
)
#: Ścieżka liczona od korzenia domeny — w atrybucie HTML i w ``url(…)`` arkusza stylów.
#: Adres z protokołem domyślnym (``//cdn…``) to nie jest ścieżka lokalna, więc go omijamy.
SCIEZKA_W_ATRYBUCIE = re.compile(
    r"""(\s(?:href|src|poster|data-src)\s*=\s*["'])/(?!/)([^"']*)""", re.I
)
SCIEZKA_W_SRCSET = re.compile(r"""(\ssrcset\s*=\s*["'])([^"']*)(["'])""", re.I)
SCIEZKA_W_STYLU = re.compile(r"""(url\(\s*['"]?)/(?!/)""", re.I)


def _z_kreska_na_koncu(wartosc: str) -> str:
    """Dokłada kreskę odsyłaczowi do podstrony, żeby ścieżki względne liczyły się od niej.

    Zestaw buduje witryny w układzie katalogowym, ale odsyłacze pisze bez kreski
    („/cennik”). Po przeliczeniu na „./cennik” przeglądarka staje pod adresem bez kreski
    i traktuje ostatni człon jak plik — wtedy „../_astro/…” z tamtej podstrony wychodzi
    o poziom za wysoko i podstrona otwiera się bez stylów.
    """
    czesc = re.split(r"[?#]", wartosc, maxsplit=1)[0]
    if not czesc or czesc.endswith("/") or "." in czesc.rsplit("/", 1)[-1]:
        return wartosc
    reszta = wartosc[len(czesc) :]
    return f"{czesc}/{reszta}"


def _na_wzgledne(tresc: str, glebokosc: int, styl: bool) -> tuple[str, int]:
    """Zamienia ścieżki „/assets/…” na względne i mówi, ile ich było.

    Strony użytkowników stoją pod adresem ``/s/<adres>/``, a nie w korzeniu domeny, więc
    ścieżka od korzenia trafia w pustkę — strona pokazuje się bez stylów i z martwym
    menu. Przedrostek liczymy z zagnieżdżenia pliku: arkusz w ``assets/`` odwołuje się
    przez ``../``, strona w ``uslugi/naprawa/`` przez ``../../``.
    """
    przedrostek = "../" * glebokosc if glebokosc else "./"
    licznik = 0

    def podmien(dopasowanie: re.Match[str]) -> str:
        nonlocal licznik
        licznik += 1
        return dopasowanie.group(1) + przedrostek

    def podmien_atrybut(dopasowanie: re.Match[str]) -> str:
        nonlocal licznik
        licznik += 1
        return dopasowanie.group(1) + przedrostek + _z_kreska_na_koncu(dopasowanie.group(2))

    tresc = SCIEZKA_W_STYLU.sub(podmien, tresc)
    if not styl:
        tresc = SCIEZKA_W_ATRYBUCIE.sub(podmien_atrybut, tresc)

        def zestaw_obrazow(dopasowanie: re.Match[str]) -> str:
            nonlocal licznik
            czesci = []
            for pozycja in dopasowanie.group(2).split(","):
                pozycja = pozycja.strip()
                if pozycja.startswith("/") and not pozycja.startswith("//"):
                    licznik += 1
                    pozycja = przedrostek + pozycja[1:]
                czesci.append(pozycja)
            return dopasowanie.group(1) + ", ".join(czesci) + dopasowanie.group(3)

        tresc = SCIEZKA_W_SRCSET.sub(zestaw_obrazow, tresc)
    return tresc, licznik


#: Zasób wczytywany z sieci: media i skrypty po ``src``, a z ``<link>`` tylko te, które
#: naprawdę coś pobierają. ``rel="canonical"`` i ``rel="alternate"`` nic nie wczytują —
#: liczone jako zasób zawyżały obraz i mieszały dwie różne sprawy.
MEDIA_Z_SIECI = re.compile(
    r"""<(?:script|img|source|iframe|video|audio)\b[^>]*\bsrc\s*=\s*["'](https?://[^"']+)""", re.I
)
LINK_Z_SIECI = re.compile(r"""<link\b([^>]*)>""", re.I)
LINK_HREF = re.compile(r"""\bhref\s*=\s*["'](https?://[^"']+)""", re.I)
LINK_REL = re.compile(r"""\brel\s*=\s*["']([^"']+)["']""", re.I)
#: Rodzaje odsyłaczy, które nie pobierają pliku ani nie łączą się z serwerem.
REL_BEZ_POBRANIA = frozenset({"canonical", "alternate", "me", "author", "license", "prev", "next"})


def _adresy_zasobow(tresc: str) -> list[str]:
    """Adresy, pod które przeglądarka naprawdę pójdzie, otwierając tę stronę."""
    wynik = list(MEDIA_Z_SIECI.findall(tresc))
    for atrybuty in LINK_Z_SIECI.findall(tresc):
        adres = LINK_HREF.search(atrybuty)
        if not adres:
            continue
        rel = LINK_REL.search(atrybuty)
        rodzaje = {r.lower() for r in rel.group(1).split()} if rel else set()
        if rodzaje & REL_BEZ_POBRANIA:
            continue
        wynik.append(adres.group(1))
    return wynik


#: Adres własny szablonu wpisany w metadane strony: ``<link rel="canonical">`` oraz
#: ``og:url``. To nie jest zasób do pobrania, tylko wskazanie „prawdziwy adres tej strony
#: jest gdzie indziej” — zostawione, mówi wyszukiwarce, że strona użytkownika jest kopią.
ADRES_KANONICZNY = re.compile(
    r"""<link\b[^>]*\brel\s*=\s*["']canonical["'][^>]*\bhref\s*=\s*["'](https?://[^"']+)"""
    r"""|<meta\b[^>]*\b(?:property|name)\s*=\s*["']og:url["'][^>]*\bcontent\s*=\s*["'](https?://[^"']+)""",
    re.I,
)

#: Adres od korzenia domeny w łańcuchu znaków skryptu — „/login”, „/panel/ustawienia”.
#: Wyłącznie do policzenia: przepisywać ścieżek w kodzie nie wolno, bo taki sam zapis bywa
#: kluczem albo zwykłym tekstem.
SCIEZKA_W_SKRYPCIE = re.compile(r"""["'`]/[a-z][a-z0-9/_-]{2,60}["'`]""")


def _uwagi_witryny(zrodlo: Path) -> list[str]:
    """Co w gotowej witrynie zaskoczy użytkownika po wstawieniu jej do szkicu."""
    z_sieci = 0
    serwery: dict[str, int] = {}
    for plik in zrodlo.rglob("*.html"):
        try:
            tresc = plik.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for adres in _adresy_zasobow(tresc):
            z_sieci += 1
            serwer = adres.split("/", 3)[2] if adres.count("/") >= 2 else adres
            serwery[serwer] = serwery.get(serwer, 0) + 1
    uwagi: list[str] = []
    if z_sieci:
        # Sama liczba nie mówi, co pobrać. Nazwy serwerów mówią: z „fonts.googleapis.com”
        # bierze się kroje, z „cdn.jsdelivr.net” biblioteki — i wiadomo, czego szukać.
        najczestsze = sorted(serwery.items(), key=lambda pozycja: -pozycja[1])[:5]
        wykaz = ", ".join(f"{serwer} ({ile})" for serwer, ile in najczestsze)
        uwagi.append(
            f"Witryna ma {z_sieci} odwołań do zasobów z sieci (CDN): {wykaz}. Bez internetu "
            "część wyglądu nie wstanie, a odwiedzający łączy się z cudzym serwerem — pobierz "
            "te pliki do strony (site_import_file) i podmień odwołania na własne."
        )
        if any(serwer.endswith(("googleapis.com", "gstatic.com")) for serwer in serwery):
            # Kroje z Google to nie tylko wygląd: każde wejście na stronę wysyła adres IP
            # odwiedzającego do Google, a serwer ma te same rodziny u siebie.
            uwagi.append(
                "Kroje wczytują się z serwerów Google — każde wejście na stronę wysyła tam "
                "adres IP odwiedzającego, co przy stronie firmowej trzeba wpisać do "
                "informacji o przetwarzaniu. Przenieś je na serwer narzędziem "
                "site_fonts_local: jedno wywołanie, kroje z repozytorium serwera "
                "(2050 rodzin) z polskimi znakami i podmienione odsyłacze."
            )
    kanoniczne: dict[str, int] = {}
    for plik in zrodlo.rglob("*.html"):
        try:
            tresc = plik.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for dopasowanie in ADRES_KANONICZNY.finditer(tresc):
            adres = dopasowanie.group(1) or dopasowanie.group(2)
            host = adres.split("/", 3)[2] if adres.count("/") >= 2 else adres
            kanoniczne[host] = kanoniczne.get(host, 0) + 1
    if kanoniczne:
        wykaz = ", ".join(f"{host} ({ile})" for host, ile in sorted(kanoniczne.items()))
        uwagi.append(
            f"Podstrony wskazują cudzy adres jako własny (canonical / og:url): {wykaz}. "
            "Zostawione mówi wyszukiwarce, że strona użytkownika jest kopią tamtej — trzeba "
            "podmienić te adresy na adres strony użytkownika albo je usunąć (site_write_file)."
        )
    w_skrypcie = 0
    for plik in zrodlo.rglob("*.js"):
        try:
            tresc = plik.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        w_skrypcie += len(SCIEZKA_W_SKRYPCIE.findall(tresc))
    if w_skrypcie:
        # Ścieżek w kodzie nie przepisujemy: w JavaScripcie „/panel” bywa adresem strony,
        # bywa kluczem, bywa fragmentem tekstu — automat pomyliłby je ze sobą.
        uwagi.append(
            f"W skryptach witryny jest {w_skrypcie} adresów liczonych od korzenia domeny "
            "(np. przekierowanie na „/login”). Ścieżek w kodzie nie przepisujemy — strona "
            "stoi pod „/s/<adres>/”, więc takie przejście trafi w pustkę. Sprawdź je "
            "web_screenshot i popraw ręcznie site_write_file."
        )
    return uwagi


def _wstaw_do_szkicu(ctx: ToolContext, site: str, zrodlo: Path, tytul: str) -> dict[str, Any]:
    store = site_store(ctx.settings, ctx.owner_id)
    if not store.exists(site):
        store.create(site, tytul or site, "")
    # Pliki i katalogi ukryte (``.htaccess``, ``.prerender/``) nie są treścią witryny:
    # szkic strony ich nie przyjmuje, a część gotowych szablonów je ze sobą niesie.
    pliki = [
        p
        for p in sorted(zrodlo.rglob("*"))
        if p.is_file()
        and p.name not in POMIJANE
        and not any(czesc.startswith(".") for czesc in p.relative_to(zrodlo).parts)
    ]
    if len(pliki) > MAX_PLIKOW:
        raise ToolError(
            f"Zbudowana witryna ma {len(pliki)} plików (limit {MAX_PLIKOW}). "
            "Wygeneruj mniejszą witrynę albo ogranicz preset."
        )
    zapisane = 0
    bajty = 0
    # Szkic strony przyjmuje tylko typy plików, które przeglądarka umie bezpiecznie podać
    # (``ALLOWED_SUFFIXES``). Gotowe witryny miewają pojedyncze pliki spoza tej listy —
    # animacje Rive, mapy źródeł, czcionki w nietypowym formacie. Pojedynczy taki plik nie
    # może wywalić całej witryny: pomijamy go i mówimy, ile pominięto.
    pominiete: list[str] = []
    naprawione = 0
    for i, plik in enumerate(pliki):
        ctx.check_cancelled()
        if i % 50 == 0:
            ctx.progress(f"Wstawianie plików witryny: {i}/{len(pliki)}")
        dane = plik.read_bytes()
        wzgledna = plik.relative_to(zrodlo).as_posix()
        if plik.suffix.lower() in (".html", ".htm", ".css"):
            try:
                tekst = dane.decode("utf-8")
            except UnicodeDecodeError:
                tekst = None
            if tekst is not None:
                tekst, ile = _na_wzgledne(
                    tekst, wzgledna.count("/"), plik.suffix.lower() == ".css"
                )
                if ile:
                    naprawione += ile
                    dane = tekst.encode("utf-8")
        try:
            store.write_bytes(site, wzgledna, dane)
        except SiteError as blad:
            # Pliki, których szkic nie przyjmie z powodu typu, nazwy albo zagnieżdżenia
            # ścieżki, pomijamy z adnotacją — jeden taki plik nie może przekreślić witryny.
            if any(
                fragment in str(blad)
                for fragment in ("Niedozwolony typ pliku", "Nieprawidłowa ścieżka", "zbyt głęboka")
            ):
                pominiete.append(wzgledna)
                continue
            raise ToolError(f"Nie udało się zapisać {plik.name}: {blad}") from blad
        zapisane += 1
        bajty += len(dane)
    if not zapisane:
        raise ToolError(
            "Żaden plik witryny nie nadaje się do szkicu strony (same nieobsługiwane typy). "
            "Wybierz inny szablon albo zbuduj witrynę z presetu."
        )
    wynik: dict[str, Any] = {"pliki": zapisane, "rozmiar_kb": round(bajty / 1024, 1)}
    if naprawione:
        wynik["poprawione_sciezki"] = naprawione
    if pominiete:
        wynik["pominiete"] = len(pominiete)
        wynik["pominiete_pliki"] = pominiete[:10]
    return wynik


@registry.register(
    "site_from_kit",
    """Buduje kompletną witrynę z zestawu Danaco Web Kit i wstawia ją do szkicu strony
użytkownika. Preset daje strukturę i treści branżowe (podstrony, sekcje, teksty zastępcze),
motyw wygląd, a kolor i krój dopasowują ją do marki. Witryna jest budowana na serwerze
offline i trafia do szkicu jako gotowe pliki — dalej poprawiasz ją site_write_file,
oglądasz web_screenshot, publikuje ją użytkownik przyciskiem w module Strony.
Presety i motywy sprawdź wcześniej narzędziem site_kit_catalog.""",
    ZKituInput,
)
def site_from_kit(ctx: ToolContext, args: ZKituInput) -> ToolResult:
    if not Path(GENERATOR).exists():
        raise ToolError("Generator witryn Danaco Web Kit nie jest zainstalowany na tym serwerze.")
    cel = ctx.work_dir / f"kit-{args.site}"
    shutil.rmtree(cel, ignore_errors=True)

    ctx.progress("Generowanie witryny z presetu…")
    ctx.run_command(_polecenie_generatora(args, cel), timeout=CZAS_GENEROWANIA_S, cwd=ctx.work_dir)

    dolozone = _uzupelnij_aliasy(cel)
    if dolozone:
        ctx.progress(f"Uzupełniam mapę typów podstron ({dolozone} nazw zastępczych)…")

    ctx.progress("Budowa witryny (offline)…")
    ctx.run_command(["/danaco/programy/bin/pnpm", "build"], timeout=CZAS_BUDOWY_S, cwd=cel)

    zrodlo = _wynik_budowy(cel)
    podstrony = sum(1 for _ in zrodlo.rglob("*.html"))
    ctx.progress(f"Witryna zbudowana: {podstrony} podstron. Wstawiam do szkicu…")
    wynik = _wstaw_do_szkicu(ctx, args.site, zrodlo, args.tytul)
    shutil.rmtree(cel, ignore_errors=True)

    dane = {
        "site": args.site,
        "preset": args.preset or "(witryna demonstracyjna rdzenia)",
        "motyw": args.motyw or "(zalecany przez preset)",
        "podstrony": podstrony,
        **wynik,
        "podglad": f"/s/{args.site}/",
    }
    return ToolResult(
        dane,
        f"Witryna „{args.site}”: {podstrony} podstron, {wynik['pliki']} plików w szkicu. "
        "Publikację zatwierdza użytkownik w module Strony.",
    )


class ZSzablonuInput(ToolInput):
    site: str = Field(
        description="Adres strony użytkownika (np. 'blog-ani'). Powstanie, jeśli jeszcze jej nie ma.",
        max_length=80,
    )
    szablon: str = Field(
        description="Identyfikator szablonu z site_kit_catalog (pole `id`, np. 'astro-blog').",
        max_length=80,
    )
    tytul: str = Field("", description="Tytuł strony w module Strony (gdy powstaje nowa).", max_length=120)


@registry.register(
    "site_from_template",
    """Wstawia do Twojego szkicu gotową, już zbudowaną witrynę z kolekcji szablonów otwartych.
Do wyboru jest 81 pozycji: blogi, portfolio, dokumentacja, panele, landingi, sklepy i strony
wydarzeń. Nic się nie buduje — pliki idą prosto do szkicu, więc trwa to sekundy, a ścieżki
„/assets/…” są przy okazji przestawiane na względne. Różnica wobec site_from_kit: tam powstaje
witryna z presetu branżowego z treściami po polsku i motywem marki, tu dostajesz cudzy, gotowy
projekt (własna licencja, treści po angielsku) do przerobienia. Listę szablonów daje
site_kit_catalog ze `szczegoly: true`.""",
    ZSzablonuInput,
)
def site_from_template(ctx: ToolContext, args: ZSzablonuInput) -> ToolResult:
    if not KOLEKCJA.is_dir():
        raise ToolError("Kolekcja szablonów nie jest zainstalowana na tym serwerze.")
    nazwa = args.szablon.strip()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}", nazwa):
        raise ToolError("Nieprawidłowy identyfikator szablonu.")
    katalog = KOLEKCJA / "szablony" / nazwa
    witryna = katalog / "witryna"
    if not witryna.is_dir():
        raise ToolError(
            f"Szablon „{nazwa}” nie ma gotowej witryny. Wybierz pozycję z `gotowa_witryna: true` "
            "w site_kit_catalog albo zbuduj witrynę z presetu narzędziem site_from_kit."
        )
    meta = _czytaj_json(katalog / "meta.json") or {}
    # Szkic strony ma własny limit plików. Lepiej powiedzieć to przed kopiowaniem niż
    # zostawić użytkownikowi witrynę wgraną w połowie.
    ile = sum(1 for p in witryna.rglob("*") if p.is_file())
    if ile > MAX_FILES:
        raise ToolError(
            f"Szablon „{nazwa}” ma {ile} plików, a strona mieści {MAX_FILES}. "
            "Wybierz lżejszy szablon albo zbuduj witrynę z presetu (site_from_kit)."
        )
    ctx.progress(f"Wstawiam szablon „{meta.get('nazwa') or nazwa}” do szkicu…")
    wynik = _wstaw_do_szkicu(ctx, args.site, witryna, args.tytul or str(meta.get("nazwa") or nazwa))
    podstrony = sum(1 for _ in witryna.rglob("*.html"))
    uwagi = _uwagi_witryny(witryna)
    dane = {
        "site": args.site,
        "szablon": nazwa,
        "nazwa": meta.get("nazwa") or nazwa,
        "licencja": meta.get("licencja") or "",
        "zrodlo": meta.get("zrodlo") or "",
        "podstrony": podstrony,
        **wynik,
        "podglad": f"/s/{args.site}/",
        "uwagi": uwagi,
    }
    licencja = f" Licencja szablonu: {dane['licencja']}." if dane["licencja"] else ""
    return ToolResult(
        dane,
        f"Szablon „{dane['nazwa']}” w szkicu strony „{args.site}”: {podstrony} podstron, "
        f"{wynik['pliki']} plików.{licencja}"
        + (f" Do poprawienia: {len(uwagi)} (patrz „uwagi”)." if uwagi else "")
        + " Publikację zatwierdza użytkownik w module Strony.",
    )


__all__ = ["site_from_kit", "site_from_template", "site_kit_catalog"]
