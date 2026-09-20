#!/usr/bin/env python3
"""Przenosi gotowe pakiety marki do katalogu publicznego aplikacji.

Źródłem prawdy są katalogi pakietów (design-tokens, logo, landing, motion, promocja).
Pliki w `frontend/public` i `frontend/src/tokens.css` są wynikiem tego skryptu i nie
podlegają ręcznej edycji. Uruchamiane automatycznie przed `dev`, `build` i `test`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PUBLIC = REPO / "frontend" / "public"

# (źródło względem katalogu repozytorium, cel względem frontend/public)
PLIKI: list[tuple[str, str]] = [
    ("landing/strona/kroje/figtree.woff2", "kroje/figtree.woff2"),
    ("landing/strona/kroje/inter.woff2", "kroje/inter.woff2"),
    ("landing/strona/kroje/cascadia.woff2", "kroje/cascadia.woff2"),
    ("logo/pwa/favicon.svg", "favicon.svg"),
    ("logo/pwa/favicon.ico", "favicon.ico"),
    ("logo/pwa/apple-touch-icon.png", "apple-touch-icon.png"),
    ("logo/pwa/safari-pinned-tab.svg", "icons/safari-pinned-tab.svg"),
    ("logo/pwa/favicon-16.png", "icons/favicon-16.png"),
    ("logo/pwa/favicon-32.png", "icons/favicon-32.png"),
    ("logo/pwa/favicon-48.png", "icons/favicon-48.png"),
    ("logo/pwa/icon-192.png", "icons/icon-192.png"),
    ("logo/pwa/icon-256.png", "icons/icon-256.png"),
    ("logo/pwa/icon-384.png", "icons/icon-384.png"),
    ("logo/pwa/icon-512.png", "icons/icon-512.png"),
    ("logo/pwa/icon-1024.png", "icons/icon-1024.png"),
    ("logo/pwa/icon-maskable-192.png", "icons/maskable-192.png"),
    ("logo/pwa/icon-maskable-512.png", "icons/maskable-512.png"),
    ("logo/pwa/icon-maskable-1024.png", "icons/maskable-1024.png"),
    ("logo/pwa/android/monochrome-432.png", "icons/monochrome-432.png"),
    # Do katalogu publicznego trafia tylko to, co aplikacja naprawdę wczytuje:
    # sygnet i logotyp poziomy w dwóch wariantach. Sam znak rysuje komponent Mark.
    ("logo/svg/symbol.svg", "znak/symbol.svg"),
    ("logo/svg/logo-horizontal-on-dark.svg", "znak/logo-poziome-ciemny.svg"),
    ("logo/svg/logo-horizontal-on-light.svg", "znak/logo-poziome-jasny.svg"),
    ("landing/ladowanie/ladowanie.css", "ladowanie/ladowanie.css"),
    ("landing/ladowanie/ladowanie.js", "ladowanie/ladowanie.js"),
    ("branding/ilustracje/zastosowania/og-1200x630.png", "og.png"),
    ("promocja/film/okladki/okladka-1280x720.png", "film/okladka.png"),
    ("promocja/film/wideo/nexus-60s-16x9.mp4", "film/nexus-60s.mp4"),
    ("promocja/film/wideo/nexus-60s-16x9.webm", "film/nexus-60s.webm"),
    ("promocja/film-praca/okladki/okladka-praca-1280x720.png", "film/okladka-praca.png"),
    ("promocja/film-praca/wideo/nexus-praca-60s-16x9.mp4", "film/nexus-praca-60s.mp4"),
    ("promocja/film-praca/wideo/nexus-praca-60s-16x9.webm", "film/nexus-praca-60s.webm"),
]

# Tła sekcji: AVIF dla przeglądarek z obsługą, WebP jako zapas.
TLA = ("aurora-mgla", "luk-brama", "noc-horyzont", "szklo-kafle", "cieply-swit", "ziarno")
for nazwa in TLA:
    for rozszerzenie in ("avif", "webp"):
        PLIKI.append((f"landing/tla/grafiki/{nazwa}@2x.{rozszerzenie}", f"tla/{nazwa}.{rozszerzenie}"))

# Tła na żywo (landing/tla): moduł JS, arkusz i zrzuty zastępcze muszą leżeć w jednym
# katalogu — ścieżki obrazów w arkuszu pakietu są względne. Do katalogu publicznego trafiają
# wyłącznie tła, które strona naprawdę montuje: aurora (hero) i łuk (wezwanie końcowe) na
# WebGL oraz świt i ziarno rysowane samym CSS. Granicą jest budżet wydajności strony produktu
# (LANDING_PAGE_SPEC rozdz. 11: LCP < 2,0 s, TBT < 200 ms): każde kolejne tło WebGL to
# 8–10 KB skryptu po kompresji i osobne płótno liczone w każdej klatce.
TLA_WEBGL = ("aurora", "luk")
TLA_CSS = ("swit", "ziarno")
ZRZUTY_TLA = ("1920x1080", "1170x2532", "3840x2160")

for nazwa in TLA_WEBGL + TLA_CSS:
    for rozszerzenie in ("js", "css"):
        PLIKI.append((f"landing/tla/{nazwa}/{nazwa}.{rozszerzenie}", f"tla/{nazwa}/{nazwa}.{rozszerzenie}"))
for nazwa in TLA_WEBGL:
    for rozmiar in ZRZUTY_TLA:
        for rozszerzenie in ("avif", "webp"):
            plik = f"{nazwa}-{rozmiar}.{rozszerzenie}"
            PLIKI.append((f"landing/tla/{nazwa}/{plik}", f"tla/{nazwa}/{plik}"))

# Materiały ruchome pokazujące działanie produktu (wytyczne ruchu, motion/).
RUCH = ("agent-status", "czat-strumien", "upuszczanie-pliku", "pasek-paleta", "wskaznik-pracy", "znak-intro")
for nazwa in RUCH:
    PLIKI.append((f"motion/przyklady/{nazwa}.mp4", f"ruch/{nazwa}.mp4"))

NAPISY = [
    ("promocja/film/wideo/nexus-60s-16x9.pl.srt", "film/nexus-60s.pl.vtt"),
    ("promocja/film/wideo/nexus-60s-16x9.en.srt", "film/nexus-60s.en.vtt"),
    ("promocja/film-praca/wideo/nexus-praca-60s-16x9.pl.srt", "film/nexus-praca-60s.pl.vtt"),
    ("promocja/film-praca/wideo/nexus-praca-60s-16x9.en.srt", "film/nexus-praca-60s.en.vtt"),
]


# ---------------------------------------------------------------------------
# Pełny katalog materiałów ruchomych
#
# W repozytorium leży kilkaset gotowych nagrań: filmy promocyjne (promocja/film),
# animacje kampanijne w trzech kadrach (promocja/kampania), animacje stanów aplikacji
# i ekranu startowego (motion/stany, motion/start). Do `frontend/public` trafiają
# wszystkie z nich — ale wyłącznie w formatach, które przeglądarka odtwarza (mp4, webm)
# oraz plakaty i napisy. Pliki GIF i źródła projektowe pomijamy: to te same ujęcia
# w formacie, którego strona nie używa. Kopiowanie idzie przez dowiązania twarde,
# więc katalog publiczny nie zajmuje drugi raz miejsca na dysku.
# ---------------------------------------------------------------------------

WIDEO = (".mp4", ".webm")
PLAKATY = (".png", ".jpg", ".webp", ".avif")
NAPISY_ROZSZ = (".vtt",)

# (źródło, cel w public, dopuszczone rozszerzenia)
KATALOGI: list[tuple[str, str, tuple[str, ...]]] = [
    ("promocja/film/wideo", "film/katalog", WIDEO),
    ("promocja/film-praca/wideo", "film/katalog", WIDEO),
    ("promocja/kampania/wideo", "kampania", WIDEO),
    ("promocja/kampania/napisy", "kampania/napisy", NAPISY_ROZSZ),
    ("motion/stany/wideo", "ruch/stany", WIDEO),
    # Nagrania momentów startu. Decyzja pary P5: znak w stanach aplikacji rysuje CSS
    # (`src/ruch/znak.css`, komponent `ZnakRuchu`) — ten sam gest waży tysiące razy mniej
    # od nagrania i stoi sam przy ograniczonym ruchu. Nagrania wczytuje `ruch/NagranieStartu.tsx`
    # tam, gdzie moment ma wypełnić całe okno: ekran startowy, brak połączenia, powiadomienia.
    ("motion/start/wideo", "ruch/start", WIDEO),
]

# Plakaty nagrań: źródła to PNG po 0,4–1 MB, do public idą w WebP (kilkanaście razy mniej).
# Bez przelicznika zostaje PNG, a spis podaje ścieżkę do niego. (źródło, cel w public)
PLAKATY_KATALOGU: list[tuple[str, str]] = [
    ("promocja/film/okladki", "film/okladki"),
    ("promocja/film-praca/okladki", "film/okladki"),
    ("promocja/kampania/okladki", "kampania/okladki"),
    ("motion/stany/plansze", "ruch/stany/plansze"),
]
JAKOSC_WEBP = 82

# Zajawki pod przyciskami odtwarzania w sekcji „Filmy”: po sześć sekund na film. Źródła mają
# 1920 px i dźwięk, do dekoracji idzie 1280 px bez dźwięku; pełna jakość zostaje w katalogu.
# (źródło bez rozszerzenia, nazwa pliku w frontend/public/film)
ZAJAWKI = [
    ("promocja/film/wideo/nexus-6s-16x9", "zajawka"),
    ("promocja/film-praca/wideo/nexus-praca-6s-16x9", "zajawka-praca"),
]
ZAJAWKA_SZEROKOSC = 1280

# `motion/start/lottie/intro-znaku.json` nie trafia do katalogu publicznego. Decyzja pary P5:
# odtwarzacz Lottie to osobna biblioteka w paczce strony produktu dla jednego ujęcia, które
# `ZnakRuchu` rysuje momentem „uruchomienie”. Wraca, gdy Lottie będzie potrzebny gdzie indziej.

# Napisy filmów leżą jako SRT — przeglądarka potrzebuje WebVTT.
NAPISY_FILMU_Z_SRT = ("promocja/film/wideo", "promocja/film-praca/wideo")

# Opisy do katalogu w aplikacji. Klucz to nazwa pliku bez kadru i rozszerzenia.
OPISY_KAMPANII = {
    "nexus-analityka": ("Analityka biznesowa", "Liczby z faktur i arkuszy zamienione w wykres i wniosek."),
    "nexus-automatyzacja": ("Automatyzacja", "Powtarzalna robota ustawiona raz i wykonywana sama."),
    "nexus-firmy": ("Dla firm", "Jedna przestrzeń dla zespołu: dokumenty, poczta, kalendarz."),
    "nexus-funkcje": ("Funkcje", "Przegląd tego, co Nexus robi na co dzień."),
    "nexus-marka": ("Marka", "Znak, łuk i Aurora — język wizualny Nexusa."),
    "nexus-produktywnosc": ("Produktywność", "Dzień pracy skrócony o rzeczy, których nie trzeba robić ręcznie."),
    "nexus-wiedza": ("Baza wiedzy", "Własne dokumenty jako pamięć agenta — z przypisami do źródła."),
    "nexus-wyszukiwanie": ("Wyszukiwanie", "Pytanie opisowe zamiast przypominania sobie nazwy pliku."),
}

OPISY_FILMOW = {
    "nexus-6s": ("Zajawka", "Sześć sekund: znak, obietnica, adres."),
    "nexus-15s": ("Spot 15 s", "Krótka forma do mediów społecznościowych."),
    "nexus-30s": ("Spot 30 s", "Pełna obietnica produktu w pół minuty."),
    "nexus-60s": ("Film główny", "Minuta o tym, czym jest Danaco Nexus."),
    "nexus-praca-6s": ("Nexus w pracy — zajawka", "Sześć sekund z drugiego filmu."),
    "nexus-praca-60s": ("Nexus w pracy", "Minuta o dniu pracy: poczta, terminy, badania, projekty, strona i kod."),
}


def opis_filmu(baza: str) -> tuple[str, str, str]:
    """Tytuł, opis i wariant dla rdzenia nazwy pliku (bez kadru).

    Klucze mają różną liczbę członów, więc bierzemy najdłuższy pasujący przedrostek.
    """
    czesci = baza.split("-")
    for dlugosc in range(len(czesci), 0, -1):
        klucz = "-".join(czesci[:dlugosc])
        if klucz in OPISY_FILMOW:
            return (*OPISY_FILMOW[klucz], "-".join(czesci[dlugosc:]))
    return baza, "", ""

# Animacje stanów — rodziny według motion/stany/README.md.
RODZINY_STANOW = {
    "praca agenta": ("ocr", "odnawianie", "powiekszanie", "tlo", "transkrypcja", "czytanie",
                     "ilustracja", "wiedza", "wycieczka", "automatyzacja"),
    "stany": ("sukces", "blad", "ostrzezenie", "polaczenie", "synchronizacja", "przesylanie",
              "upuszczanie", "pusta-rozmowa", "brak-wynikow", "pierwsze-uruchomienie",
              "powiadomienie", "skopiowano", "przypiecie"),
    "przejścia widoków": ("widoki", "podglad-pliku", "szuflada"),
    "zestawienie": ("showreel",),
}

KADRY = {"16x9": "16:9", "1x1": "1:1", "9x16": "9:16"}

CZAS = re.compile(r"(\d\d:\d\d:\d\d),(\d\d\d)")

# Zrzuty w oknie instalacji aplikacji — skalowane z makiet zespołu „Produkt i UX”.
ZRZUTY = [
    ("prezentacja/makiety/d02-rozmowa-w-toku.png", "screenshots/wide.png", (1280, 800)),
    ("prezentacja/makiety/m02-rozmowa-agent-status.png", "screenshots/narrow.png", (780, 1688)),
]


def na_vtt(srt: str) -> str:
    """Zamienia napisy SRT na WEBVTT (przecinek dziesiętny na kropkę)."""
    return "WEBVTT\n\n" + CZAS.sub(r"\1.\2", srt.replace("\r\n", "\n")).lstrip("\ufeff")



def zwiaz(zrodlo: Path, cel: Path) -> bool:
    """Wstawia plik dowiązaniem twardym; kopiuje, gdy się nie da.

    Pakiety marki nie leżą w repozytorium (w git jest gotowy `public`), więc brak źródła
    jest usterką tylko wtedy, gdy nie ma też pliku docelowego.
    """
    if not zrodlo.is_file():
        if cel.is_file():
            return True
        print(f"brak źródła: {zrodlo.relative_to(REPO)}", file=sys.stderr)
        return False
    cel.parent.mkdir(parents=True, exist_ok=True)
    if cel.exists():
        if cel.stat().st_size == zrodlo.stat().st_size and cel.stat().st_mtime >= zrodlo.stat().st_mtime:
            return True
        cel.unlink()
    try:
        os.link(zrodlo, cel)
    except OSError:
        # Inny system plików albo limit dowiązań — kopia jest równie dobra, tylko cięższa.
        shutil.copy2(zrodlo, cel)
    return True


def rozbierz(nazwa: str) -> tuple[str, str]:
    """Dzieli `nexus-analityka-16x9` na (`nexus-analityka`, `16:9`)."""
    for przyrostek, kadr in KADRY.items():
        if nazwa.endswith("-" + przyrostek):
            return nazwa[: -len(przyrostek) - 1], kadr
    return nazwa, ""


def kopiuj(zrodlo: Path, cel: Path) -> bool:
    if not zrodlo.is_file():
        print(f"brak źródła: {zrodlo.relative_to(REPO)}", file=sys.stderr)
        return False
    cel.parent.mkdir(parents=True, exist_ok=True)
    if cel.is_file() and cel.stat().st_mtime >= zrodlo.stat().st_mtime and cel.stat().st_size == zrodlo.stat().st_size:
        return True
    shutil.copy2(zrodlo, cel)
    return True



# Plakaty nagrań: pierwsza klatka bywa czarna, więc element wideo bez plakatu pokazuje
# ciemny prostokąt do czasu wczytania. Klatkę bierzemy z miejsca, w którym scena jest
# już zbudowana.
PLAKATY_NAGRAN: list[tuple[str, str, str]] = [
    ("ruch/start/uruchomienie-komputer-ciemny.mp4", "ruch/start/uruchomienie-komputer-ciemny.png", "2.5"),
    ("ruch/start/uruchomienie-komputer-jasny.mp4", "ruch/start/uruchomienie-komputer-jasny.png", "2.5"),
    ("ruch/start/uruchomienie-telefon-ciemny.mp4", "ruch/start/uruchomienie-telefon-ciemny.png", "2.5"),
]


def sciezka_ffmpeg() -> Path | None:
    """Ścieżka do ffmpeg albo None, gdy programu nie ma na maszynie."""
    znalezione = Path(shutil.which("ffmpeg") or "/danaco/programy/ffmpeg/ffmpeg")
    return znalezione if znalezione.exists() else None


def na_webp(zrodlo: Path, cel: Path) -> bool:
    """Zapisuje obraz w WebP: Pillow, a gdy go nie ma w tym Pythonie — ffmpeg.

    False oznacza brak przelicznika; zostaje wtedy format źródłowy.
    """
    if not zrodlo.is_file():
        return cel.is_file()
    if cel.is_file() and cel.stat().st_mtime >= zrodlo.stat().st_mtime:
        return True
    cel.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        ffmpeg = sciezka_ffmpeg()
        if ffmpeg is None:
            return False
        wynik = subprocess.run(
            [str(ffmpeg), "-v", "error", "-y", "-i", str(zrodlo),
             "-c:v", "libwebp", "-quality", str(JAKOSC_WEBP), "-compression_level", "6", str(cel)],
            capture_output=True,
            check=False,
        )
        return wynik.returncode == 0
    with Image.open(zrodlo) as obraz:
        # Przezroczystość zostaje, tak samo jak w gałęzi ffmpeg: inaczej wynik przelicznika
        # zależałby od tego, którym Pythonem uruchomiono skrypt.
        tryb = "RGBA" if obraz.mode in ("RGBA", "LA", "PA") or "transparency" in obraz.info else "RGB"
        obraz.convert(tryb).save(cel, "WEBP", quality=JAKOSC_WEBP, method=6)
    return True


def plakaty_katalogu() -> int:
    """Przenosi plakaty nagrań do katalogu publicznego w WebP. Zwraca liczbę braków."""
    braki = 0
    for zrodlo_kat, cel_kat in PLAKATY_KATALOGU:
        katalog = REPO / zrodlo_kat
        if not katalog.is_dir():
            # Bez pakietu źródłowego liczy się to, co leży w `public`.
            if (PUBLIC / cel_kat).is_dir():
                continue
            print(f"brak katalogu: {zrodlo_kat}", file=sys.stderr)
            braki += 1
            continue
        for plik in sorted(katalog.iterdir()):
            if not plik.is_file() or plik.suffix.lower() not in PLAKATY:
                continue
            if na_webp(plik, PUBLIC / cel_kat / f"{plik.stem}.webp"):
                continue
            if not zwiaz(plik, PUBLIC / cel_kat / plik.name):
                braki += 1
    return braki


def zajawka_lekka() -> int:
    """Buduje lekkie warianty zajawek (ffmpeg). Bez ffmpeg zostaje kopia pełnego nagrania."""
    ffmpeg = sciezka_ffmpeg()
    braki = 0
    for zrodlo_filmu, nazwa in ZAJAWKI:
        for rozszerzenie in ("webm", "mp4"):
            zrodlo = REPO / f"{zrodlo_filmu}.{rozszerzenie}"
            cel = PUBLIC / f"film/{nazwa}.{rozszerzenie}"
            if not zrodlo.is_file():
                if not cel.is_file():
                    print(f"brak źródła: {zrodlo_filmu}.{rozszerzenie}", file=sys.stderr)
                    braki += 1
                continue
            if cel.is_file() and cel.stat().st_mtime >= zrodlo.stat().st_mtime:
                continue
            if ffmpeg is None:
                if not kopiuj(zrodlo, cel):
                    braki += 1
                continue
            cel.parent.mkdir(parents=True, exist_ok=True)
            kodek = (
                ["-c:v", "libvpx-vp9", "-crf", "38", "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "3"]
                if rozszerzenie == "webm"
                else ["-c:v", "libx264", "-crf", "30", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
            )
            wynik = subprocess.run(
                [str(ffmpeg), "-v", "error", "-y", "-i", str(zrodlo),
                 "-an", "-vf", f"scale={ZAJAWKA_SZEROKOSC}:-2", *kodek, str(cel)],
                capture_output=True,
                check=False,
            )
            if wynik.returncode != 0 and not kopiuj(zrodlo, cel):
                braki += 1
    return braki


def plakaty_nagran() -> int:
    """Wycina plakaty z nagrań (ffmpeg). Brak ffmpeg nie jest usterką — plakat jest ozdobą."""
    ffmpeg = sciezka_ffmpeg()
    if ffmpeg is None:
        return 0
    zrobione = 0
    for zrodlo, cel, sekunda in PLAKATY_NAGRAN:
        plik = PUBLIC / zrodlo
        docelowy = PUBLIC / cel
        if not plik.is_file() or docelowy.is_file():
            continue
        docelowy.parent.mkdir(parents=True, exist_ok=True)
        wynik = subprocess.run(
            [str(ffmpeg), "-v", "error", "-y", "-ss", sekunda, "-i", str(plik), "-vframes", "1", str(docelowy)],
            capture_output=True,
            check=False,
        )
        if wynik.returncode == 0:
            zrobione += 1
    return zrobione


def katalog_ruchu() -> int:
    """Przenosi katalog nagrań i wypisuje spis do `frontend/src/media`. Zwraca liczbę braków."""
    braki = 0
    for zrodlo_kat, cel_kat, rozszerzenia in KATALOGI:
        katalog = REPO / zrodlo_kat
        if not katalog.is_dir():
            # Jak wyżej: bez pakietu źródłowego liczy się to, co już leży w `public`.
            if (PUBLIC / cel_kat).is_dir():
                continue
            print(f"brak katalogu: {zrodlo_kat}", file=sys.stderr)
            braki += 1
            continue
        for plik in sorted(katalog.iterdir()):
            if plik.suffix.lower() in rozszerzenia and plik.is_file():
                if not zwiaz(plik, PUBLIC / cel_kat / plik.name):
                    braki += 1

    # Napisy filmów są w SRT; przeglądarka czyta WebVTT.
    for katalog_napisow in NAPISY_FILMU_Z_SRT:
        zrodlo_napisow = REPO / katalog_napisow
        if not zrodlo_napisow.is_dir():
            continue
        for plik in sorted(zrodlo_napisow.glob("*.srt")):
            cel = PUBLIC / "film" / "katalog" / (plik.stem + ".vtt")
            cel.parent.mkdir(parents=True, exist_ok=True)
            cel.write_text(na_vtt(plik.read_text(encoding="utf-8")), encoding="utf-8")

    spis = {"filmy": [], "kampania": [], "stany": [], "start": []}

    def warianty(katalog: Path, rdzen: str) -> dict[str, str]:
        """Zwraca ścieżki publiczne mp4/webm dla danego rdzenia nazwy."""
        znalezione = {}
        for rozszerzenie in ("mp4", "webm"):
            if (katalog / f"{rdzen}.{rozszerzenie}").is_file():
                znalezione[rozszerzenie] = f"/{katalog.relative_to(PUBLIC)}/{rdzen}.{rozszerzenie}"
        return znalezione

    def plakat(katalog: Path, rdzen: str) -> str:
        """Ścieżka plakatu: WebP, a gdy go nie ma (brak Pillow) — plik źródłowy PNG."""
        for rozszerzenie in ("webp", "png"):
            if (katalog / f"{rdzen}.{rozszerzenie}").is_file():
                return f"/{katalog.relative_to(PUBLIC)}/{rdzen}.{rozszerzenie}"
        return ""

    kat_filmy = PUBLIC / "film" / "katalog"
    if kat_filmy.is_dir():
        for plik in sorted(kat_filmy.glob("*.mp4")):
            rdzen = plik.stem
            baza, kadr = rozbierz(rdzen)
            tytul, opis, wariant = opis_filmu(baza)
            spis["filmy"].append({
                "id": rdzen,
                "tytul": tytul + (f" ({wariant})" if wariant else ""),
                "opis": opis,
                "kadr": kadr,
                "zrodla": warianty(kat_filmy, rdzen),
                "plakat": plakat(
                    kat_filmy.parent / "okladki",
                    "okladka-praca-1920x1080" if rdzen.startswith("nexus-praca") else "okladka-1920x1080",
                ),
                "napisy": {
                    jezyk: f"/film/katalog/{rdzen}.{jezyk}.vtt"
                    for jezyk in ("pl", "en")
                    if (kat_filmy / f"{rdzen}.{jezyk}.vtt").is_file()
                },
            })

    kat_kampania = PUBLIC / "kampania"
    if kat_kampania.is_dir():
        for plik in sorted(kat_kampania.glob("*.mp4")):
            rdzen = plik.stem
            baza, kadr = rozbierz(rdzen)
            tytul, opis = OPISY_KAMPANII.get(baza, (baza, ""))
            spis["kampania"].append({
                "id": rdzen,
                "temat": baza,
                "tytul": tytul,
                "opis": opis,
                "kadr": kadr,
                "zrodla": warianty(kat_kampania, rdzen),
                "plakat": plakat(kat_kampania / "okladki", rdzen),
                "napisy": {
                    jezyk: f"/kampania/napisy/{rdzen}.{jezyk}.vtt"
                    for jezyk in ("pl", "en")
                    if (kat_kampania / "napisy" / f"{rdzen}.{jezyk}.vtt").is_file()
                },
            })

    rodzina_po_id = {nazwa: rodzina for rodzina, nazwy in RODZINY_STANOW.items() for nazwa in nazwy}
    kat_stany = PUBLIC / "ruch" / "stany"
    if kat_stany.is_dir():
        for plik in sorted(kat_stany.glob("*.mp4")):
            spis["stany"].append({
                "id": plik.stem,
                "rodzina": rodzina_po_id.get(plik.stem, "stany"),
                "zrodla": warianty(kat_stany, plik.stem),
            })

    kat_start = PUBLIC / "ruch" / "start"
    if kat_start.is_dir():
        for plik in sorted(kat_start.glob("*.mp4")):
            spis["start"].append({"id": plik.stem, "zrodla": warianty(kat_start, plik.stem)})

    naglowek = (
        "// Spis materiałów ruchomych. Wynik frontend/scripts/zasoby.py — nie edytować ręcznie.\n"
        "// Źródła: promocja/film, promocja/kampania, motion/stany, motion/start.\n\n"
    )
    media = REPO / "frontend" / "src" / "media"
    media.mkdir(parents=True, exist_ok=True)
    (media / "katalog-typy.ts").write_text(
        naglowek
        + "export type Zrodla = { mp4?: string; webm?: string };\n"
        "export type Film = { id: string; tytul: string; opis: string; kadr: string;"
        " zrodla: Zrodla; plakat: string; napisy: Record<string, string> };\n"
        "export type Kampania = Film & { temat: string };\n"
        "export type Nagranie = { id: string; zrodla: Zrodla };\n"
        "export type Stan = Nagranie & { rodzina: string };\n",
        encoding="utf-8",
    )
    for nazwa in ("filmy", "kampania", "stany", "start"):
        (media / f"katalog-{nazwa}.ts").write_text(
            naglowek + f"export const {nazwa.upper()} = "
            f"{json.dumps(spis[nazwa], ensure_ascii=False, indent=2)} as const;\n",
            encoding="utf-8",
        )
    # Działy w osobnych plikach: paczka wejściowa bierze sam spis ujęć startowych, a spis
    # kampanii jedzie z podstroną „Zastosowania”. Ten plik je zbiera pod jednym importem.
    (media / "katalog.ts").write_text(
        naglowek
        + 'export type { Film, Kampania, Nagranie, Stan, Zrodla } from "./katalog-typy";\n'
        'export { FILMY } from "./katalog-filmy";\n'
        'export { KAMPANIA } from "./katalog-kampania";\n'
        'export { STANY } from "./katalog-stany";\n'
        'export { START } from "./katalog-start";\n',
        encoding="utf-8",
    )
    print(
        "katalog ruchu: "
        f"{len(spis['filmy'])} filmów, {len(spis['kampania'])} animacji kampanijnych, "
        f"{len(spis['stany'])} animacji stanów, {len(spis['start'])} animacji startu"
    )
    return braki


def main() -> int:
    braki = 0
    for zrodlo, cel in PLIKI:
        if not kopiuj(REPO / zrodlo, PUBLIC / cel):
            braki += 1

    for zrodlo, cel in NAPISY:
        plik = REPO / zrodlo
        if not plik.is_file():
            print(f"brak źródła: {zrodlo}", file=sys.stderr)
            braki += 1
            continue
        docelowy = PUBLIC / cel
        docelowy.parent.mkdir(parents=True, exist_ok=True)
        docelowy.write_text(na_vtt(plik.read_text(encoding="utf-8")), encoding="utf-8")

    # Skalowanie wymaga Pillow; bez niego zostają zrzuty zapisane w repozytorium.
    try:
        from PIL import Image
    except ImportError:
        # Zrzuty są zapisane w repozytorium, więc brak Pillow nie jest usterką —
        # zgłaszamy go tylko wtedy, gdy plik faktycznie nie istnieje.
        brakujace = [cel for _, cel, _ in ZRZUTY if not (PUBLIC / cel).is_file()]
        if brakujace:
            print(f"brak Pillow — nie da się odtworzyć zrzutów: {', '.join(brakujace)}", file=sys.stderr)
            braki += len(brakujace)
    else:
        for zrodlo, cel, rozmiar in ZRZUTY:
            plik = REPO / zrodlo
            if not plik.is_file():
                print(f"brak źródła: {zrodlo}", file=sys.stderr)
                braki += 1
                continue
            docelowy = PUBLIC / cel
            docelowy.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(plik) as obraz:
                obraz.convert("RGB").resize(rozmiar, Image.LANCZOS).save(docelowy, "PNG", optimize=True)

    # Plakat filmu także w WebP.
    na_webp(REPO / "promocja/film/okladki/okladka-1280x720.png", PUBLIC / "film/okladka.webp")

    braki += zajawka_lekka()
    braki += plakaty_katalogu()
    braki += katalog_ruchu()
    plakaty_nagran()

    tokeny = REPO / "design-tokens" / "dist" / "tokens.css"
    if tokeny.is_file():
        naglowek = "/* Kopia design-tokens/dist/tokens.css. Wynik frontend/scripts/zasoby.py — nie edytować. */\n"
        (REPO / "frontend" / "src" / "tokens.css").write_text(naglowek + tokeny.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        print("brak design-tokens/dist/tokens.css", file=sys.stderr)
        braki += 1

    print(f"zasoby: {len(PLIKI) + len(NAPISY) + 1 - braki} gotowych, {braki} braków")
    return 1 if braki else 0


if __name__ == "__main__":
    raise SystemExit(main())
