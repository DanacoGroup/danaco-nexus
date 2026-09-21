"""Montaż filmu z ujęć: zdjęcia i klipy + napisy + podkład z biblioteki serwera.

Nexus umiał dotąd wyłącznie przerabiać gotowe nagranie (``media_process``, Studio). Nie
umiał **złożyć** materiału — a o to prosi użytkownik, gdy mówi „zrób filmik promocyjny
z tych zdjęć”. To narzędzie domyka lukę: bierze listę ujęć, każde ożywia ruchem kamery
(najazd, odjazd, panorama), nakłada napis, spina ujęcia przenikaniem i podkłada muzykę
z biblioteki ``/danaco/programy/media-zasoby``.

Napisy rysuje Pillow do przezroczystej nakładki, a nie ``drawtext`` FFmpeg: polskie znaki
i cudzysłowy w tekście użytkownika łamały cytowanie filtru, a nakładka jest odporna
na dowolną treść.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, Field

from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    image_preview,
    registry,
)
from nexus.tools.common import file_kind

#: Katalog muzyki i dźwięków serwera (ten sam, po którym chodzi ``asset_library``).
MEDIA = Path(os.environ.get("NEXUS_ZASOBY_MEDIA", "/danaco/programy/media-zasoby"))
KROJE = Path(os.environ.get("NEXUS_KROJE", "/danaco/programy/kroje"))
#: Krój napisów: zmienny Inter w odmianie grubej. Ma polskie znaki i czyta się w ruchu.
KROJ_NAPISU = KROJE / "Inter[opsz,wght].ttf"
DZWIEK = frozenset({".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus"})

KADRY: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}
FPS = 30
#: Czas przenikania między ujęciami. Krótsze gubi się w odbiorze, dłuższe zjada ujęcie.
PRZENIKANIE = 0.6
#: Najkrótsze sensowne ujęcie — poniżej widz nie zdąży przeczytać napisu.
MIN_UJECIE = 1.2
MAKS_UJECIE = 30.0
MAKS_UJEC = 40
CZAS_MONTAZU = 900

RUCHY = ("brak", "najazd", "odjazd", "w-lewo", "w-prawo")
#: Przejścia wbudowane w filtr ``xfade`` FFmpeg.
PRZEJSCIA_WBUDOWANE = (
    "fade", "fadeblack", "fadewhite", "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown", "circleopen", "circleclose",
    "circlecrop", "rectcrop", "dissolve", "distance", "smoothleft", "smoothright",
    "smoothup", "smoothdown", "radial", "pixelize", "hlslice", "vuslice", "zoomin",
)
#: Własne przejścia serwera: wyrażenia dla ``xfade=transition=custom``. Leżą w bibliotece
#: materiałów, a nie w kodzie — plik jest wspólny dla wszystkich projektów serwera.
PRZEJSCIA_WLASNE = MEDIA / "przejscia" / "xfade-danaco" / "przejscia.tsv"


def _przejscia_wlasne() -> dict[str, str]:
    """Nazwa przejścia → wyrażenie ``xfade``; pusty słownik, gdy biblioteki nie ma."""
    if not PRZEJSCIA_WLASNE.is_file():
        return {}
    wynik: dict[str, str] = {}
    for wiersz in PRZEJSCIA_WLASNE.read_text(encoding="utf-8").splitlines()[1:]:
        czesci = wiersz.split("\t")
        if len(czesci) >= 2 and czesci[0].strip() and czesci[1].strip():
            wynik[czesci[0].strip()] = czesci[1].strip()
    return wynik


class Ujecie(BaseModel):
    """Jedno ujęcie filmu."""

    file_id: str = Field(description="Zdjęcie albo klip wideo z rozmowy.")
    sekundy: float = Field(
        default=4.0, ge=MIN_UJECIE, le=MAKS_UJECIE, description="Jak długo ujęcie stoi na ekranie."
    )
    napis: str = Field(default="", max_length=180, description="Tekst na dole kadru (pusto = bez napisu).")
    ruch: Literal[RUCHY] = Field(  # type: ignore[valid-type]
        default="najazd", description="Ruch kamery: najazd, odjazd, w-lewo, w-prawo albo brak."
    )
    lektor: str = Field(
        default="",
        max_length=400,
        description=(
            "Zdanie czytane na głos w czasie tego ujęcia (pusto = bez lektora). Pisz krótko: "
            "na cztery sekundy wchodzi jedno zdanie."
        ),
    )


class MontazInput(ToolInput):
    ujecia: list[Ujecie] = Field(
        description="Ujęcia po kolei — zdjęcia i klipy z rozmowy.", min_length=1, max_length=MAKS_UJEC
    )
    kadr: Literal["16:9", "9:16", "1:1", "4:5"] = Field(
        default="16:9", description="Proporcje kadru: 16:9 na YouTube, 9:16 na rolki, 1:1 i 4:5 na posty."
    )
    przejscie: str = Field(
        default="fade",
        max_length=40,
        description=(
            "Jak ujęcia przechodzą jedno w drugie. Wbudowane w FFmpeg: fade, fadeblack, "
            "fadewhite, wipeleft/right/up/down, slideleft/right/up/down, circleopen, "
            "circleclose, circlecrop, rectcrop, dissolve, distance, smoothleft/right/up/down, "
            "radial, pixelize, hlslice, vuslice, zoomin. Własne przejścia serwera: "
            "przekatna-tl-br, przekatna-tr-bl, romb, kolo-srodek, kolo-rog, zegar, "
            "zaluzje-pionowe, zaluzje-poziome, paski-naprzemienne, schody, rozpad-ziarnisty, "
            "siatka-kwadratow, zamiatanie-miekkie, zamiatanie-miekkie-gora, "
            "przenikanie-progowe, rozblysk-biel, rozblysk-czern, spirala, fala-pionowa, "
            "klin-srodek, klin-brzegi."
        ),
    )
    muzyka: str = Field(
        default="",
        max_length=300,
        description=(
            "Podkład: ścieżka z biblioteki serwera dokładnie jak w asset_library dla działu "
            "„media” (np. „muzyka/incompetech-kevin-macleod/korporacyjny/Cloud Dancer.mp3”) "
            "albo identyfikator pliku z rozmowy. Pusto = film bez dźwięku."
        ),
    )
    glosnosc: float = Field(default=0.6, ge=0.0, le=1.0, description="Głośność podkładu (1.0 = bez zmian).")
    glos: str = Field(
        default="",
        max_length=80,
        description="Głos lektora (identyfikator z ustawień konta). Pusto = głos domyślny serwera.",
    )
    tytul: str = Field(default="", max_length=120, description="Napis otwierający na pierwszym ujęciu.")
    nazwa_pliku: str = Field(default="film", max_length=60, description="Nazwa pliku wynikowego (bez .mp4).")


def _kroj(rozmiar: int, grubosc: str = "Bold") -> ImageFont.FreeTypeFont:
    if not KROJ_NAPISU.is_file():
        raise ToolError("Na serwerze nie ma kroju pisma do napisów.")
    font = ImageFont.truetype(str(KROJ_NAPISU), rozmiar)
    try:
        font.set_variation_by_name(grubosc)
    except OSError:  # krój niezmienny — zostaje odmiana podstawowa
        pass
    return font


def _zawin(tekst: str, font: ImageFont.FreeTypeFont, szerokosc: int) -> list[str]:
    """Łamie napis na wiersze mieszczące się w kadrze."""
    wiersze: list[str] = []
    biezacy = ""
    for slowo in tekst.split():
        proba = f"{biezacy} {slowo}".strip()
        if font.getbbox(proba)[2] <= szerokosc or not biezacy:
            biezacy = proba
        else:
            wiersze.append(biezacy)
            biezacy = slowo
    if biezacy:
        wiersze.append(biezacy)
    return wiersze[:4]


def _jasnosc_pasa(zrodlo: Path | None, szerokosc: int, wysokosc: int, gora: int, dol: int) -> int | None:
    """Średnia jasność tego pasa kadru, na którym stanie napis (0–255).

    Zwraca ``None``, gdy nie ma czego zmierzyć (ujęcie z klipu wideo).
    """
    if zrodlo is None:
        return None
    try:
        with Image.open(zrodlo) as obraz:
            szary = obraz.convert("L").resize((szerokosc // 8, wysokosc // 8))
    except (OSError, ValueError):
        return None
    pas = szary.crop((0, gora // 8, szary.width, max(gora // 8 + 1, dol // 8)))
    dane = list(pas.get_flattened_data())
    return round(sum(dane) / len(dane)) if dane else None


def _nakladka(
    tekst: str,
    szerokosc: int,
    wysokosc: int,
    cel: Path,
    duzy: bool,
    zrodlo: Path | None = None,
) -> None:
    """Rysuje napis na przezroczystej nakładce wielkości kadru.

    Pod tekstem kładzie przyciemnienie dobrane do zdjęcia: na jasnym biały napis bez niego
    ginie, a na ciemnym pełne przyciemnienie tylko zabija rysunek. Jasność pasa mierzymy
    ze zdjęcia ujęcia, więc kadr zostaje tak czytelny, jak był.
    """
    obraz = Image.new("RGBA", (szerokosc, wysokosc), (0, 0, 0, 0))
    rysunek = ImageDraw.Draw(obraz)
    margines = round(szerokosc * 0.07)
    font = _kroj(round(szerokosc * (0.062 if duzy else 0.042)))
    wiersze = _zawin(tekst, font, szerokosc - 2 * margines)
    odstep = round(font.size * 1.28)
    wysokosc_tekstu = odstep * len(wiersze)
    gora = wysokosc - margines - wysokosc_tekstu if not duzy else round((wysokosc - wysokosc_tekstu) / 2)
    # Przyciemnienie: pas gęstniejący ku dołowi kadru (albo ku środkowi przy tytule).
    # Przy tytule pas jest szeroki, żeby czytał się jak winieta, a nie jak pasek na środku.
    rozlew = round(font.size * (2.6 if duzy else 1.2))
    pas_gora = max(0, gora - rozlew)
    pas_dol = min(wysokosc, gora + wysokosc_tekstu + round(font.size * (2.2 if duzy else 0.9)))
    jasnosc = _jasnosc_pasa(zrodlo, szerokosc, wysokosc, pas_gora, pas_dol)
    if jasnosc is None:
        szczyt = 150 if not duzy else 130
    elif jasnosc < 70:  # kadr i tak ciemny — wystarczy muśnięcie, żeby nie zabić rysunku
        szczyt = 45
    elif jasnosc < 140:
        szczyt = 105
    else:
        szczyt = 175
    for y in range(pas_gora, pas_dol):
        postep = (y - pas_gora) / max(1, pas_dol - pas_gora)
        krycie = round(szczyt * (postep if not duzy else 1 - abs(2 * postep - 1)))
        rysunek.line([(0, y), (szerokosc, y)], fill=(0, 0, 0, krycie))
    # Pod literami idzie rozmyty cień. Samo przyciemnienie pasa nie wystarcza: na ciemnym
    # ujęciu pas jest celowo lekki, a biały napis potrafi trafić wprost na jasny rysunek.
    cien = Image.new("RGBA", (szerokosc, wysokosc), (0, 0, 0, 0))
    pisak_cienia = ImageDraw.Draw(cien)
    ulozenie = []
    for numer, wiersz in enumerate(wiersze):
        szer = font.getbbox(wiersz)[2]
        ulozenie.append((round((szerokosc - szer) / 2), gora + numer * odstep, wiersz))
    for x, y, wiersz in ulozenie:
        pisak_cienia.text((x, y), wiersz, font=font, fill=(0, 0, 0, 235))
    cien = cien.filter(ImageFilter.GaussianBlur(max(2, round(font.size * 0.16))))
    obraz.alpha_composite(cien)
    obraz.alpha_composite(cien)
    for x, y, wiersz in ulozenie:
        rysunek.text((x, y), wiersz, font=font, fill=(255, 255, 255, 255))
    obraz.save(cel)


def _podklad(ctx: ToolContext, wybor: str) -> Path:
    """Ścieżka podkładu: pozycja z biblioteki serwera albo plik z rozmowy."""
    wybor = wybor.strip()
    kandydat = (MEDIA / wybor).resolve()
    if MEDIA.is_dir() and MEDIA.resolve() in kandydat.parents and kandydat.is_file():
        if kandydat.suffix.lower() not in DZWIEK:
            raise ToolError(f"{kandydat.name} nie jest plikiem dźwiękowym.")
        return kandydat
    # Zapis ze ścieżką to próba sięgnięcia do biblioteki, nie identyfikator pliku z rozmowy.
    # Bez tego rozróżnienia użytkownik dostawał „nieprawidłowy identyfikator pliku” w miejscu,
    # w którym pomylił się o jeden katalog.
    if "/" in wybor or Path(wybor).suffix.lower() in DZWIEK:
        raise ToolError(
            f"Biblioteka materiałów nie ma podkładu {wybor!r}. Ścieżkę weź z asset_library "
            "(dział „media”, katalog „muzyka”) albo podaj identyfikator pliku z rozmowy."
        )
    plik = ctx.file(wybor)
    if file_kind(plik) != "audio":
        raise ToolError(f"{plik.name} nie jest plikiem dźwiękowym.")
    return plik.path


def _dlugosc_dzwieku(ctx: ToolContext, plik: Path) -> float:
    """Długość nagrania w sekundach — z ffprobe, bo kwestie lektora trzeba ułożyć w czasie."""
    wynik = ctx.run_command(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(plik)],
        timeout=60,
    )
    try:
        return float(wynik.stdout.strip())
    except (TypeError, ValueError) as blad:
        raise ToolError(f"Nie udało się zmierzyć długości nagrania {plik.name}.") from blad


def _glosnosc_podkladu(glosnosc: float, z_lektorem: bool) -> float:
    """Głośność muzyki: pod lektorem schodzi, bo inaczej nie rozumie się ani jednego, ani drugiego.

    Współczynnik dobrany na słuch i sprawdzony rozpoznaniem mowy z gotowego filmu: przy
    0,35 zdania wracają z transkrypcji w całości, przy pełnej głośności podkład je zagłusza.
    """
    return round(glosnosc * (0.35 if z_lektorem else 1.0), 3)


def _lektor(ctx: ToolContext, tekst: str, glos: str, katalog: Path, numer: int) -> Path:
    """Zdanie lektora jako plik WAV. Czyta ten sam silnik co rozmowa głosowa (Piper)."""
    from nexus.voice import VoiceEngine, VoiceUnavailable

    try:
        dane, _typ = VoiceEngine(ctx.settings).speak(tekst.strip(), glos.strip())
    except (VoiceUnavailable, ValueError) as blad:
        raise ToolError(f"Nie udało się przeczytać zdania lektora: {blad}") from blad
    plik = katalog / f"lektor-{numer}.wav"
    plik.write_bytes(dane)
    return plik


def _filtr_ujecia(numer: int, obraz: bool, klatki: int, ruch: str, szer: int, wys: int) -> str:
    """Filtr normalizujący jedno ujęcie do kadru filmu, z ruchem kamery przy zdjęciach."""
    if not obraz:
        # ``tpad`` przytrzymuje ostatnią klatkę: klip krótszy od zamówionego ujęcia urwałby
        # się w pół, a przenikanie liczone z zadeklarowanych czasów trafiłoby w pustkę.
        czas = klatki / FPS
        return (
            f"[{numer}:v]scale={szer}:{wys}:force_original_aspect_ratio=increase,"
            f"crop={szer}:{wys},"
            # Bez ``setpts`` przed ``tpad``: wyzerowanie znaczników czasu sprawia, że tpad
            # nie dokłada ani jednej klatki i krótki klip zostaje krótki.
            f"tpad=stop_mode=clone:stop_duration={czas:.3f},trim=duration={czas:.3f},"
            # ``fps`` na końcu, bo ``tpad`` oddaje strumień o zmiennej klatce, a xfade
            # przyjmuje wyłącznie stałą.
            f"fps={FPS},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[s{numer}]"
        )
    # Zdjęcie skalujemy z zapasem, żeby zoompan miał z czego brać przy najeździe.
    zapas_szer, zapas_wys = szer * 2, wys * 2
    if ruch == "najazd":
        z, x, y = "min(1.0+0.0013*on,1.14)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif ruch == "odjazd":
        z, x, y = "max(1.14-0.0013*on,1.0)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif ruch == "w-lewo":
        z, x, y = "1.12", f"(iw-iw/zoom)*(1-on/{max(1, klatki - 1)})", "ih/2-(ih/zoom/2)"
    elif ruch == "w-prawo":
        z, x, y = "1.12", f"(iw-iw/zoom)*(on/{max(1, klatki - 1)})", "ih/2-(ih/zoom/2)"
    else:
        z, x, y = "1.0", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    return (
        f"[{numer}:v]scale={zapas_szer}:{zapas_wys}:force_original_aspect_ratio=increase,"
        f"crop={zapas_szer}:{zapas_wys},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={klatki}:s={szer}x{wys}:fps={FPS},"
        f"setsar=1,format=yuv420p[s{numer}]"
    )


def _rodzaj_przejscia(nazwa: str) -> str:
    """Fragment filtru ``xfade`` opisujący wybrane przejście.

    Własne przejścia serwera idą jako ``transition=custom`` z wyrażeniem w apostrofach —
    wyrażenie ma w środku przecinki, które bez apostrofów FFmpeg wziąłby za koniec filtru.
    """
    nazwa = nazwa.strip()
    if nazwa in PRZEJSCIA_WBUDOWANE:
        return f"transition={nazwa}"
    wlasne = _przejscia_wlasne()
    if nazwa in wlasne:
        wyrazenie = wlasne[nazwa]
        # Wyrażenie wchodzi w apostrofach do filtru; apostrof w środku rozerwałby filtr.
        if "'" in wyrazenie or "\\" in wyrazenie:
            raise ToolError(f"Wyrażenie przejścia {nazwa!r} ma znak, którego filtr nie przyjmie.")
        return f"transition=custom:expr='{wyrazenie}'"
    raise ToolError(
        f"Nie znam przejścia {nazwa!r}. Wbudowane: {', '.join(PRZEJSCIA_WBUDOWANE[:8])}… "
        f"Własne przejścia serwera: {', '.join(sorted(wlasne)[:8]) or '(biblioteka nie jest zainstalowana)'}…"
    )


def _przenikanie(czasy: list[float]) -> float:
    """Ile trwa przejście między ujęciami.

    Przenikanie zabiera kawałek obu sąsiednich ujęć, więc nie może być dłuższe niż
    najkrótsze z nich — przy zbyt długim FFmpeg przerywa montaż z błędem offsetu.
    """
    if len(czasy) < 2:
        return PRZENIKANIE
    return max(0.1, min(PRZENIKANIE, min(czasy) - 0.2))


@registry.register(
    "video_compose",
    """Składa gotowy film ze zdjęć i klipów: filmik promocyjny, zapowiedź, portfolio, rolkę
na media społecznościowe. Każde zdjęcie dostaje ruch kamery (najazd, odjazd, panorama),
napis z przyciemnieniem pod spodem, a ujęcia spina przenikanie. Podkład muzyczny bierzesz
z biblioteki serwera (asset_library, dział „media”, katalog „muzyka”) — nie pytaj
użytkownika o plik, jeśli pasuje coś gotowego. Kadr dobierz do miejsca publikacji:
16:9 na YouTube, 9:16 na rolki, 1:1 i 4:5 na post. Różnica wobec media_process: tam
przerabiasz jedno gotowe nagranie, tu powstaje nowy materiał z wielu ujęć.""",
    MontazInput,
)
def video_compose(ctx: ToolContext, args: MontazInput) -> ToolResult:
    szer, wys = KADRY[args.kadr]
    katalog = ctx.output_path("montaz").parent
    cel = katalog / f"{args.nazwa_pliku.strip() or 'film'}.mp4"

    wejscia: list[str] = []
    filtry: list[str] = []
    strumienie: list[str] = []
    czasy: list[float] = []
    numer = 0
    for i, ujecie in enumerate(args.ujecia):
        ctx.check_cancelled()
        plik = ctx.file(ujecie.file_id)
        rodzaj = file_kind(plik)
        if rodzaj not in {"image", "video"}:
            raise ToolError(f"{plik.name} nie jest zdjęciem ani filmem — ujęcia składamy z obrazu.")
        obraz = rodzaj == "image"
        klatki = max(1, round(ujecie.sekundy * FPS))
        if obraz:
            # Bez „-loop”: zoompan sam rozciąga jedną klatkę na całe ujęcie.
            wejscia += ["-i", str(plik.path)]
        else:
            wejscia += ["-t", f"{ujecie.sekundy:.3f}", "-i", str(plik.path)]
        filtry.append(_filtr_ujecia(numer, obraz, klatki, ujecie.ruch, szer, wys))
        zrodlo = f"[s{numer}]"
        numer += 1
        napis = args.tytul if (i == 0 and args.tytul) else ujecie.napis
        if napis.strip():
            nakladka = katalog / f"napis-{i}.png"
            _nakladka(
                napis.strip(),
                szer,
                wys,
                nakladka,
                duzy=bool(i == 0 and args.tytul),
                zrodlo=plik.path if obraz else None,
            )
            wejscia += ["-i", str(nakladka)]
            # ``fps`` na wyjściu każdej gałęzi: xfade przyjmuje wyłącznie stałą klatkę,
            # a nakładka z napisem to pojedynczy obraz bez własnego tempa.
            filtry.append(
                f"{zrodlo}[{numer}:v]overlay=0:0:format=auto,fps={FPS},format=yuv420p[v{i}]"
            )
            numer += 1
        else:
            filtry.append(f"{zrodlo}fps={FPS},format=yuv420p[v{i}]")
        strumienie.append(f"[v{i}]")
        czasy.append(ujecie.sekundy)

    przenikanie = _przenikanie(czasy)
    rodzaj = _rodzaj_przejscia(args.przejscie)
    if len(strumienie) == 1:
        filtry.append(f"{strumienie[0]}null[wynik]")
        calosc = czasy[0]
    else:
        biezacy = strumienie[0]
        przesuniecie = 0.0
        for i in range(1, len(strumienie)):
            przesuniecie += czasy[i - 1] - przenikanie
            nastepny = "[wynik]" if i == len(strumienie) - 1 else f"[x{i}]"
            filtry.append(
                f"{biezacy}{strumienie[i]}xfade={rodzaj}:"
                f"duration={przenikanie:.3f}:offset={przesuniecie:.3f}{nastepny}"
            )
            biezacy = nastepny
        calosc = sum(czasy) - przenikanie * (len(czasy) - 1)

    # Lektor: każde ujęcie może mieć swoje zdanie, czytane od początku tego ujęcia.
    lektor_wejscia: list[tuple[Path, float]] = []
    if any(ujecie.lektor.strip() for ujecie in args.ujecia):
        poczatek = 0.0
        for i, ujecie in enumerate(args.ujecia):
            if ujecie.lektor.strip():
                ctx.progress(f"Czytam zdanie lektora do ujęcia {i + 1}…")
                lektor_wejscia.append((_lektor(ctx, ujecie.lektor, args.glos, katalog, i), poczatek))
            poczatek += czasy[i] - (przenikanie if i < len(czasy) - 1 else 0.0)

    polecenie = ["ffmpeg", "-hide_banner", "-y"]
    mapowania = ["-map", "[wynik]"]
    sciezki_dzwieku: list[str] = []
    glosnosc_muzyki = _glosnosc_podkladu(args.glosnosc, bool(lektor_wejscia))
    if args.muzyka.strip():
        sciezka = _podklad(ctx, args.muzyka)
        # „-stream_loop -1” zapętla krótki jingiel na całą długość filmu.
        wejscia += ["-stream_loop", "-1", "-i", str(sciezka)]
        wyciszenie = max(0.0, calosc - 2.0)
        filtry.append(
            f"[{numer}:a]atrim=0:{calosc:.3f},asetpts=N/SR/TB,volume={glosnosc_muzyki:.2f},"
            f"afade=t=in:st=0:d=1,afade=t=out:st={wyciszenie:.3f}:d=2[podklad]"
        )
        sciezki_dzwieku.append("[podklad]")
        numer += 1
    for kolejny, (plik_lektora, start) in enumerate(lektor_wejscia):
        wejscia += ["-i", str(plik_lektora)]
        filtry.append(
            f"[{numer}:a]adelay={round(start * 1000)}:all=1,volume=1.0[lektor{kolejny}]"
        )
        sciezki_dzwieku.append(f"[lektor{kolejny}]")
        numer += 1
    if sciezki_dzwieku:
        if len(sciezki_dzwieku) == 1:
            filtry.append(f"{sciezki_dzwieku[0]}anull[dzwiek]")
        else:
            filtry.append(
                "".join(sciezki_dzwieku)
                + f"amix=inputs={len(sciezki_dzwieku)}:duration=longest:normalize=0[dzwiek]"
            )
        mapowania += ["-map", "[dzwiek]", "-c:a", "aac", "-b:a", "192k"]
    polecenie += wejscia
    polecenie += ["-filter_complex", ";".join(filtry), *mapowania]
    polecenie += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-pix_fmt", "yuv420p", "-r", str(FPS), "-t", f"{calosc:.3f}",
        "-movflags", "+faststart", str(cel),
    ]

    ctx.progress(f"Montaż filmu: {len(args.ujecia)} ujęć, {calosc:.1f} s, kadr {args.kadr}…")
    ctx.run_command(polecenie, timeout=CZAS_MONTAZU)
    if not cel.is_file() or cel.stat().st_size == 0:
        raise ToolError("Montaż nie dał pliku wynikowego.")

    podglady: list[bytes] = []
    klatka = katalog / "klatka.jpg"
    try:
        ctx.run_command(
            ["ffmpeg", "-hide_banner", "-y", "-ss", f"{min(1.0, calosc / 2):.2f}", "-i", str(cel),
             "-frames:v", "1", "-q:v", "3", str(klatka)],
            timeout=120,
        )
        if klatka.is_file():
            with Image.open(klatka) as otwarty:
                podglady.append(image_preview(otwarty.convert("RGB")))
    except ToolError:  # podgląd jest dodatkiem — brak klatki nie przekreśla filmu
        pass

    dane: dict[str, Any] = {
        "output": cel.name,
        "ujec": len(args.ujecia),
        "dlugosc_s": round(calosc, 1),
        "kadr": args.kadr,
        "rozdzielczosc": f"{szer}x{wys}",
        "przejscie": args.przejscie,
        "muzyka": args.muzyka.strip() or "(bez podkładu)",
        "rozmiar_mb": round(cel.stat().st_size / 1024 / 1024, 1),
    }
    return ToolResult(
        dane,
        f"Film zmontowany: {len(args.ujecia)} ujęć, {calosc:.1f} s, {szer}×{wys} ({args.kadr}).",
        images=podglady,
        files=[OutputFile(cel, cel.name, f"Film {args.kadr}, {calosc:.1f} s")],
    )


class KwestiaInput(BaseModel):
    """Jedna wypowiedź lektora w materiale dźwiękowym."""

    tekst: str = Field(description="Zdanie do przeczytania.", max_length=600)
    przerwa_po_s: float = Field(
        default=0.6, ge=0.0, le=10.0, description="Cisza po tej kwestii (sekundy)."
    )


class SpotInput(ToolInput):
    kwestie: list[KwestiaInput] = Field(
        default_factory=list,
        max_length=20,
        description="Wypowiedzi lektora po kolei. Pusto = sam podkład (np. sama pętla muzyczna).",
    )
    muzyka: str = Field(
        default="",
        max_length=300,
        description=(
            "Podkład: ścieżka z biblioteki serwera jak w asset_library (dział „media”, katalog "
            "„muzyka”) albo identyfikator pliku z rozmowy. Pusto = sam głos."
        ),
    )
    glosnosc: float = Field(default=0.6, ge=0.0, le=1.0, description="Głośność podkładu.")
    glos: str = Field(default="", max_length=80, description="Głos lektora; pusto = domyślny serwera.")
    wstep_s: float = Field(
        default=1.5, ge=0.0, le=10.0, description="Ile sekund muzyki przed pierwszym zdaniem."
    )
    wybrzmienie_s: float = Field(
        default=2.0, ge=0.0, le=10.0, description="Ile sekund muzyki po ostatnim zdaniu."
    )
    dlugosc_s: float = Field(
        default=30.0,
        ge=3.0,
        le=600.0,
        description="Długość, gdy nie ma kwestii lektora (sam podkład). Z kwestiami liczy się sama.",
    )
    nazwa_pliku: str = Field(default="spot", max_length=60, description="Nazwa pliku (bez .mp3).")


@registry.register(
    "audio_compose",
    """Składa gotowy materiał dźwiękowy: spot radiowy, intro do podcastu, zapowiedź, wiadomość
głosową z podkładem. Podajesz kwestie lektora po kolei (czyta je głos serwera, po polsku)
i podkład z biblioteki serwera — muzyka wchodzi przed pierwszym zdaniem, schodzi pod głos
i wybrzmiewa po ostatnim. Różnica wobec read_document_aloud: tam powstaje samo czytanie
dokumentu, tu materiał z muzyką, przerwami i wyciszeniem. Bez kwestii dostajesz sam podkład
przycięty do długości z wyciszeniem — na podkład pod czyjeś nagranie.""",
    SpotInput,
)
def audio_compose(ctx: ToolContext, args: SpotInput) -> ToolResult:
    if not args.kwestie and not args.muzyka.strip():
        raise ToolError("Podaj kwestie lektora albo podkład — z niczego nie zrobię nagrania.")
    katalog = ctx.output_path("spot").parent
    cel = katalog / f"{args.nazwa_pliku.strip() or 'spot'}.mp3"

    wejscia: list[str] = []
    filtry: list[str] = []
    sciezki: list[str] = []
    numer = 0
    moment = args.wstep_s if args.kwestie else 0.0
    for i, kwestia in enumerate(args.kwestie):
        ctx.check_cancelled()
        ctx.progress(f"Czytam kwestię {i + 1} z {len(args.kwestie)}…")
        plik = _lektor(ctx, kwestia.tekst, args.glos, katalog, i)
        wejscia += ["-i", str(plik)]
        filtry.append(f"[{numer}:a]adelay={round(moment * 1000)}:all=1[glos{i}]")
        sciezki.append(f"[glos{i}]")
        moment += _dlugosc_dzwieku(ctx, plik) + kwestia.przerwa_po_s
        numer += 1
    calosc = round(moment + args.wybrzmienie_s, 3) if args.kwestie else args.dlugosc_s

    if args.muzyka.strip():
        podklad = _podklad(ctx, args.muzyka)
        wejscia += ["-stream_loop", "-1", "-i", str(podklad)]
        wyciszenie = max(0.0, calosc - args.wybrzmienie_s)
        filtry.append(
            f"[{numer}:a]atrim=0:{calosc:.3f},asetpts=N/SR/TB,"
            f"volume={_glosnosc_podkladu(args.glosnosc, bool(args.kwestie)):.2f},"
            f"afade=t=in:st=0:d=1,afade=t=out:st={wyciszenie:.3f}:d={max(0.5, args.wybrzmienie_s):.2f}"
            f"[podklad]"
        )
        sciezki.append("[podklad]")
        numer += 1

    if len(sciezki) == 1:
        filtry.append(f"{sciezki[0]}anull[wynik]")
    else:
        filtry.append(
            "".join(sciezki) + f"amix=inputs={len(sciezki)}:duration=longest:normalize=0[wynik]"
        )
    polecenie = ["ffmpeg", "-hide_banner", "-y", *wejscia]
    polecenie += ["-filter_complex", ";".join(filtry), "-map", "[wynik]"]
    polecenie += ["-t", f"{calosc:.3f}", "-c:a", "libmp3lame", "-b:a", "192k", str(cel)]

    ctx.progress(f"Składam nagranie: {len(args.kwestie)} kwestii, {calosc:.1f} s…")
    ctx.run_command(polecenie, timeout=CZAS_MONTAZU)
    if not cel.is_file() or cel.stat().st_size == 0:
        raise ToolError("Składanie nagrania nie dało pliku wynikowego.")

    dane: dict[str, Any] = {
        "output": cel.name,
        "kwestii": len(args.kwestie),
        "dlugosc_s": round(calosc, 1),
        "muzyka": args.muzyka.strip() or "(bez podkładu)",
        "rozmiar_kb": round(cel.stat().st_size / 1024, 1),
    }
    return ToolResult(
        dane,
        f"Nagranie złożone: {len(args.kwestie)} kwestii lektora, {calosc:.1f} s.",
        files=[OutputFile(cel, cel.name, f"Nagranie {calosc:.1f} s")],
    )


__all__ = ["audio_compose", "video_compose"]
