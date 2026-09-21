"""Narzędzia obrazu, zdjęcia i wideo oparte na programach specjalistycznych serwera.

Rejestr miał dotąd obróbkę gotowych plików (ImageMagick, OpenCV, rembg, Real-ESRGAN)
i podstawy FFmpeg. Na serwerze leżały jednak programy, po które agent nie mógł sięgnąć,
choć odpowiadają na zdania padające w rozmowie wprost:

* „popraw twarze na tym starym zdjęciu” — rekonstrukcja twarzy (CodeFormer/GFPGAN),
* „usuń tę osobę z kadru”, „zeskanowana odbitka jest w rysach” — inpainting LaMa,
* „rozmyj tło jak w aparacie” — rozmycie sterowane mapą głębi (Depth Anything V2),
* „zrób z tego fragmentu GIF” — klatki z FFmpeg złożone przez gifski,
* „zrób film z tej animacji Lottie” — render animacji do MP4, WEBM, GIF albo PNG.

Modele liczą na procesorze, więc każdy program ma na serwerze gotowe polecenie
``danaco-*``, które ustawia wagi i tryb offline. Wywołujemy je zamiast powtarzać
tu tamtą konfigurację.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image, ImageFilter
from pydantic import Field

from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    image_preview,
    registry,
)
from nexus.tools.common import file_kind, open_image, unique_name, with_suffix
from nexus.tworczy.obrazy import regions_mask

PODGLAD = 1024

#: Limity czasu dobrane do pracy modeli na procesorze — to minuty, nie sekundy.
CZAS_GLEBIA = 900
CZAS_LAMA = 1200
CZAS_TWARZE = 1800
CZAS_GIF = 900
CZAS_LOTTIE = 600

#: Rozdzielczość sieci głębi: krótszy bok obrazu podawany modelowi (wielokrotność 14).
SZCZEGOLOWOSC_GLEBI = {"standard": 518, "wysoka": 770}

#: Ile warstw rozmycia składa głębię ostrości — więcej wygładza przejścia, ale kosztuje.
POZIOMY_ROZMYCIA = 4

#: Najwięcej klatek, z jakich ma sens składać GIF; powyżej plik przestaje nadawać się do wysłania.
MAKS_KLATEK_GIF = 450

ZAPIS_CZASU = re.compile(r"^\d{1,2}(:\d{2}){0,2}(\.\d+)?$")
BARWA = re.compile(r"^#[0-9A-Fa-f]{6}$")

LOTTIE_ROZSZERZENIA = frozenset({".json", ".lottie"})
#: Biblioteka gotowych animacji Lottie na serwerze (wykaz + pliki). Agent nie musi mieć
#: animacji od użytkownika — sięga po gotową i renderuje ją do filmu, GIF-a albo klatki.
LOTTIE_BIBLIOTEKA = Path(os.environ.get("NEXUS_LOTTIE_DIR", "/danaco/programy/web/lottie"))
LOTTIE_WYKAZ = LOTTIE_BIBLIOTEKA / "indeks.json"
#: Ile pozycji wykazu wraca bez zawężenia — pełne 450+ zajmowałoby pół okna rozmowy.
LOTTIE_LIMIT = 60


def _program(nazwa: str, czego_dotyczy: str) -> str:
    """Ścieżka polecenia serwera albo błąd zrozumiały dla użytkownika."""
    sciezka = shutil.which(nazwa)
    if not sciezka:
        raise ToolError(f"{czego_dotyczy} jest niedostępne na tym serwerze.")
    return sciezka


def _obraz(ctx: ToolContext, file_id: str) -> tuple[str, Path]:
    plik = ctx.file(file_id)
    if file_kind(plik) != "image":
        raise ToolError(f"{plik.name} nie jest obrazem.")
    return plik.name, plik.path


def _film(ctx: ToolContext, file_id: str) -> tuple[str, Path]:
    plik = ctx.file(file_id)
    if file_kind(plik) != "video":
        raise ToolError(f"{plik.name} nie jest filmem.")
    return plik.name, plik.path


def _zapisz_zdjecie(ctx: ToolContext, obraz: Image.Image, nazwa: str, znacznik: str) -> Path:
    """Zapisuje wynik: JPEG dla zdjęć z aparatu, PNG dla reszty (bez ponownej stratności)."""
    jpeg = Path(nazwa).suffix.lower() in {".jpg", ".jpeg"}
    cel = ctx.output_path(with_suffix(nazwa, ".jpg" if jpeg else ".png", znacznik))
    if jpeg:
        obraz.convert("RGB").save(cel, quality=92, optimize=True)
    else:
        obraz.save(cel, optimize=True)
    return cel


def _maska_z_obszarow(ctx: ToolContext, zrodlo: Path, obszary: list[list[float]]) -> Path:
    """Buduje białą maskę z prostokątów podanych ułamkami wymiarów obrazu."""
    prostokaty: list[tuple[float, float, float, float]] = []
    for obszar in obszary:
        if len(obszar) != 4 or not all(0 <= wartosc <= 1 for wartosc in obszar):
            raise ToolError("Każdy prostokąt to cztery ułamki 0–1: [x, y, szerokość, wysokość].")
        if obszar[2] <= 0 or obszar[3] <= 0:
            raise ToolError("Prostokąt musi mieć dodatnią szerokość i wysokość.")
        prostokaty.append((obszar[0], obszar[1], obszar[2], obszar[3]))
    with open_image(zrodlo) as otwarty:
        rozmiar = otwarty.size
    cel = ctx.output_path("maska.png")
    regions_mask(rozmiar, prostokaty).save(cel)
    return cel


def _mapa_glebi(ctx: ToolContext, zrodlo: Path, nazwa: str, szczegolowosc: str, podglad: Path | None) -> Path:
    """Uruchamia Depth Anything V2 i oddaje ścieżkę mapy głębi (PNG 16-bit)."""
    program = _program("danaco-glebia", "Liczenie mapy głębi ze zdjęcia")
    cel = ctx.output_path(with_suffix(nazwa, ".png", "_glebia"))
    polecenie = [program, "--rozdzielczosc", str(SZCZEGOLOWOSC_GLEBI[szczegolowosc])]
    if podglad is not None:
        polecenie += ["--podglad", str(podglad)]
    ctx.progress(f"Liczenie mapy głębi: {nazwa}")
    ctx.run_command([*polecenie, str(zrodlo), str(cel)], timeout=CZAS_GLEBIA)
    if not cel.is_file():
        raise ToolError(f"Mapa głębi dla {nazwa} nie powstała.")
    return cel


# --- Twarze --------------------------------------------------------------------------------------


class TwarzeInput(ToolInput):
    file_ids: list[str] = Field(
        min_length=1, max_length=10, description="Zdjęcia z twarzami do zrekonstruowania."
    )
    model: Literal["codeformer", "gfpgan"] = Field(
        default="codeformer",
        description="codeformer = mocniejsza rekonstrukcja mocno zniszczonych twarzy; gfpgan = łagodniejszy.",
    )
    wiernosc: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="0 = najmocniejsza poprawa (rysy mogą się zmienić), 1 = najwierniej oryginałowi.",
    )
    powiekszenie: Literal[1, 2, 4] = Field(
        default=1, description="Krotność powiększenia całego zdjęcia przy okazji rekonstrukcji."
    )
    tylko_glowna: bool = Field(
        default=False, description="Popraw wyłącznie twarz najbliżej środka kadru, resztę zostaw."
    )


@registry.register(
    "restore_faces",
    """Odtwarza twarze na zdjęciu zniszczonym, rozmytym, drobnym albo mocno skompresowanym.
Dorysowuje oczy, usta i kontury, których w pliku po prostu nie ma (CodeFormer lub GFPGAN).
Do zdjęć archiwalnych, skanów odbitek, kadrów z monitoringu i starych plików z telefonu.
Różnica wobec sąsiadów: retouch_portrait tylko wygładza istniejącą skórę, upscale_image
powiększa cały obraz bez wiedzy o twarzy, a to narzędzie dorysowuje brakujące rysy.""",
    TwarzeInput,
)
def restore_faces(ctx: ToolContext, args: TwarzeInput) -> ToolResult:
    program = _program("danaco-retusz-twarzy", "Rekonstrukcja twarzy")
    uzyte: set[str] = set()
    wyniki: list[OutputFile] = []
    podglady: list[bytes] = []
    policzone: dict[str, int | None] = {}
    for file_id in args.file_ids:
        ctx.check_cancelled()
        nazwa, sciezka = _obraz(ctx, file_id)
        cel = ctx.output_path(unique_name(with_suffix(nazwa, ".png", "_twarze"), uzyte))
        polecenie = [
            program,
            "--model",
            args.model,
            "--wiernosc",
            f"{args.wiernosc:.2f}",
            "--skala",
            str(args.powiekszenie),
        ]
        if args.tylko_glowna:
            polecenie.append("--tylko-srodkowa")
        ctx.progress(f"Rekonstrukcja twarzy: {nazwa}")
        przebieg = ctx.run_command([*polecenie, str(sciezka), str(cel)], timeout=CZAS_TWARZE)
        if not cel.is_file():
            raise ToolError(f"Rekonstrukcja twarzy dla {nazwa} nie dała pliku wynikowego.")
        # Program przy braku twarzy kończy się powodzeniem i przepisuje obraz bez zmian —
        # liczbę twarzy podaje na wyjściu i trzeba ją przekazać dalej, żeby nie obiecywać poprawy.
        zliczone = re.search(r"twarze\s+(\d+)", przebieg.stdout or "")
        policzone[nazwa] = int(zliczone.group(1)) if zliczone else None
        wyniki.append(OutputFile(cel, cel.name, f"Twarze odtworzone: {nazwa}"))
        if len(podglady) < 4:
            with Image.open(cel) as otwarty:
                podglady.append(image_preview(otwarty, PODGLAD))
    if policzone and all(liczba == 0 for liczba in policzone.values()):
        raise ToolError(
            "Na żadnym ze zdjęć nie rozpoznałem twarzy, więc nie ma czego odtwarzać. "
            "Do rozmytego zdjęcia bez twarzy użyj upscale_image."
        )
    return ToolResult(
        {"pliki": [plik.name for plik in wyniki], "model": args.model, "twarze": policzone},
        f"Rekonstrukcja twarzy: {len(wyniki)} zdj.",
        images=podglady,
        files=wyniki,
    )


# --- Usuwanie obiektów i rys ---------------------------------------------------------------------


class NaprawaInput(ToolInput):
    file_id: str = Field(description="Zdjęcie do naprawienia.")
    mask_file_id: str | None = Field(
        default=None, description="Maska obszaru: biel = usuń, czerń = zostaw bez zmian."
    )
    obszary: list[list[float]] = Field(
        default_factory=list,
        max_length=50,
        description="Albo prostokąty do usunięcia jako ułamki wymiarów [x, y, szerokość, wysokość] (0–1).",
    )
    rysy: bool = Field(
        default=False, description="Dodatkowo wykryj i usuń rysy, zagięcia i kurz ze skanu odbitki."
    )
    czulosc: float = Field(
        default=1.0,
        ge=0.2,
        le=3.0,
        description="Czułość wykrywania rys: więcej = więcej trafień (i pomyłek).",
    )
    rozszerz_px: int = Field(
        default=3, ge=0, le=40, description="O ile pikseli poszerzyć maskę, żeby objąć krawędzie obiektu."
    )


@registry.register(
    "inpaint_photo",
    """Usuwa ze zdjęcia duży element i dorysowuje to, co było za nim.
Znika przechodzień, samochód, kosz na śmieci albo słup, a w trybie „rysy” także rysy, zagięcia
i kurz ze skanu starej odbitki (model LaMa). Obszar wskazuje maska albo prostokąty; tryb rys
działa bez wskazywania czegokolwiek. Do drobnego napisu, znaku wodnego czy pyłku szybciej użyć
erase_objects (bez modelu) — tutaj model dopowiada całą treść, więc znika też duży obiekt
na niejednolitym tle.""",
    NaprawaInput,
)
def inpaint_photo(ctx: ToolContext, args: NaprawaInput) -> ToolResult:
    program = _program("danaco-usun-obiekt", "Usuwanie obiektów ze zdjęcia")
    nazwa, sciezka = _obraz(ctx, args.file_id)
    polecenie = [program, "--rozszerz", str(args.rozszerz_px)]
    if args.mask_file_id:
        polecenie += ["--maska", str(_obraz(ctx, args.mask_file_id)[1])]
    elif args.obszary:
        polecenie += ["--maska", str(_maska_z_obszarow(ctx, sciezka, args.obszary))]
    elif not args.rysy:
        raise ToolError(
            "Nie wiem, co usunąć: podaj maskę (mask_file_id), prostokąty (obszary) "
            "albo włącz tryb rys (rysy)."
        )
    if args.rysy:
        polecenie += ["--rysy", "--czulosc", f"{args.czulosc:.2f}"]
    cel = ctx.output_path(with_suffix(nazwa, ".png", "_naprawione"))
    ctx.progress(f"Usuwanie i dorysowywanie tła: {nazwa}")
    ctx.run_command([*polecenie, str(sciezka), str(cel)], timeout=CZAS_LAMA)
    if not cel.is_file():
        raise ToolError(f"Naprawa {nazwa} nie dała pliku wynikowego.")
    with Image.open(cel) as otwarty:
        podglad = image_preview(otwarty, PODGLAD)
    return ToolResult(
        {"output": cel.name, "rysy": args.rysy},
        f"Zdjęcie naprawione: {nazwa}",
        images=[podglad],
        files=[OutputFile(cel, cel.name, f"{nazwa} po usunięciu wskazanych miejsc")],
    )


# --- Głębia --------------------------------------------------------------------------------------


class GlebiaInput(ToolInput):
    file_id: str = Field(description="Zdjęcie, dla którego ma powstać mapa głębi.")
    szczegolowosc: Literal["standard", "wysoka"] = Field(
        default="standard", description="wysoka = drobniejsze szczegóły planów, liczy się dłużej."
    )


@registry.register(
    "depth_map",
    """Liczy, jak daleko od aparatu leży każdy punkt zdjęcia.
Wynikiem jest PNG 16-bit, w którym jaśniejszy piksel znaczy „bliżej aparatu”, plus barwny
podgląd do obejrzenia (Depth Anything V2). Przydaje się, gdy planami zdjęcia ma zająć się coś
dalszego: maska pierwszego planu, relief albo model 3D, efekt paralaksy w innym programie,
warstwy do montażu. Do samego rozmycia tła służy blur_background_by_depth, a do gotowego filmu
z paralaksą — animate_photo.""",
    GlebiaInput,
)
def depth_map(ctx: ToolContext, args: GlebiaInput) -> ToolResult:
    nazwa, sciezka = _obraz(ctx, args.file_id)
    podglad = ctx.output_path(with_suffix(nazwa, ".png", "_glebia_podglad"))
    mapa = _mapa_glebi(ctx, sciezka, nazwa, args.szczegolowosc, podglad)
    wyniki = [OutputFile(mapa, mapa.name, "Mapa głębi (PNG 16-bit, jaśniej = bliżej)")]
    podglady: list[bytes] = []
    if podglad.is_file():
        wyniki.append(OutputFile(podglad, podglad.name, "Barwny podgląd mapy głębi"))
        with Image.open(podglad) as otwarty:
            podglady.append(image_preview(otwarty, PODGLAD))
    return ToolResult(
        {"pliki": [plik.name for plik in wyniki]},
        f"Mapa głębi: {nazwa}",
        images=podglady,
        files=wyniki,
    )


class RozmycieInput(ToolInput):
    file_id: str = Field(description="Zdjęcie, na którym ma zostać rozmyte tło.")
    punkt_ostrosci: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Który plan zostaje ostry: 1 = najbliższy, 0,5 = środkowy, 0 = najdalszy.",
    )
    sila: int = Field(
        default=16,
        ge=2,
        le=60,
        description="Największe rozmycie w pikselach na planie najdalszym od ostrego.",
    )
    strefa_ostrosci: float = Field(
        default=0.25,
        ge=0.0,
        le=0.9,
        description="Jak szeroki plan zostaje zupełnie ostry: 0 = sama wybrana odległość, 0,5 = pół sceny.",
    )
    szczegolowosc: Literal["standard", "wysoka"] = Field(
        default="standard", description="Dokładność mapy głębi; wysoka lepiej trzyma cienkie krawędzie."
    )


@registry.register(
    "blur_background_by_depth",
    """Rozmywa tło zdjęcia tak, jak robi to jasny obiektyw.
Mapa głębi rozdziela plany, więc rozmycie narasta wraz z odległością od wybranego planu,
zamiast kończyć się na ostrej obwódce wokół wyciętego obiektu. Do zdjęć krajobrazu, wnętrza,
stołu, produktu i grupy osób — wszędzie tam, gdzie „tło” nie jest jednym przedmiotem.
Dla pojedynczej osoby albo produktu na wycince wystarczy change_background w trybie „blur”.""",
    RozmycieInput,
)
def blur_background_by_depth(ctx: ToolContext, args: RozmycieInput) -> ToolResult:
    nazwa, sciezka = _obraz(ctx, args.file_id)
    mapa = _mapa_glebi(ctx, sciezka, nazwa, args.szczegolowosc, None)
    with open_image(sciezka) as otwarty:
        zdjecie = otwarty.convert("RGB")
    with Image.open(mapa) as glebia:
        # Mapa jest 16-bitowa (tryb „I;16”), więc idzie do numpy bez konwersji trybu.
        if glebia.size != zdjecie.size:
            glebia = glebia.resize(zdjecie.size, Image.Resampling.BILINEAR)
        wartosci = np.asarray(glebia, dtype=np.float32)
    najmniej, najwiecej = float(wartosci.min()), float(wartosci.max())
    if najwiecej - najmniej < 1.0:
        raise ToolError(
            f"Na zdjęciu {nazwa} nie da się rozdzielić planów — wszystko jest w tej samej odległości."
        )
    blisko = (wartosci - najmniej) / (najwiecej - najmniej)
    # Plan w strefie ostrości zostaje nietknięty, dalej rozmycie narasta aż do pełnej siły.
    odleglosc = np.abs(blisko - args.punkt_ostrosci) - args.strefa_ostrosci
    odleglosc = np.clip(odleglosc / max(1e-3, 1.0 - args.strefa_ostrosci), 0.0, 1.0)

    ctx.progress(f"Rozmywanie planów dalszych: {nazwa}")
    wynik = zdjecie
    for poziom in range(1, POZIOMY_ROZMYCIA + 1):
        ctx.check_cancelled()
        rozmyte = zdjecie.filter(ImageFilter.GaussianBlur(args.sila * poziom / POZIOMY_ROZMYCIA))
        prog = (poziom - 1) / POZIOMY_ROZMYCIA
        udzial = np.clip((odleglosc - prog) * POZIOMY_ROZMYCIA, 0.0, 1.0)
        maska = Image.fromarray((udzial * 255).astype(np.uint8), "L")
        wynik = Image.composite(rozmyte, wynik, maska)

    cel = _zapisz_zdjecie(ctx, wynik, nazwa, "_rozmyte_tlo")
    return ToolResult(
        {"output": cel.name, "punkt_ostrosci": args.punkt_ostrosci, "sila": args.sila},
        f"Tło rozmyte według głębi: {nazwa}",
        images=[image_preview(wynik, PODGLAD)],
        files=[OutputFile(cel, cel.name, f"{nazwa} z rozmytym tłem")],
    )


# --- GIF z filmu ---------------------------------------------------------------------------------


class GifInput(ToolInput):
    file_id: str = Field(description="Film, z którego ma powstać GIF.")
    start: str | None = Field(
        default=None, max_length=12, description="Początek fragmentu, np. „00:01:30” (puste = od początku)."
    )
    czas_s: float = Field(default=5.0, ge=0.5, le=30.0, description="Długość fragmentu w sekundach.")
    fps: int = Field(
        default=15, ge=5, le=30, description="Klatki na sekundę: 10–15 wystarcza, 25 daje płynny ruch."
    )
    szerokosc: int = Field(default=640, ge=120, le=1200, description="Szerokość GIF-a w pikselach.")
    jakosc: int = Field(
        default=90, ge=40, le=100, description="Jakość barw: niżej = mniejszy plik, widoczne pasy."
    )


@registry.register(
    "video_to_gif",
    """Składa GIF z fragmentu filmu w jakości, jakiej nie daje zwykła konwersja.
Barwy dobierane są osobno dla każdej klatki (FFmpeg i gifski), więc obraz nie rozsypuje się
na plamy. Do wstawki na stronę, do wiadomości, do dokumentacji i do pokazania ruchu tam, gdzie
film się nie odtworzy. Narzędzie media_process też zapisze GIF, ale ubogą paletą i w 10 klatkach
na sekundę — tego używaj, gdy wynik ma dobrze wyglądać.""",
    GifInput,
)
def video_to_gif(ctx: ToolContext, args: GifInput) -> ToolResult:
    ffmpeg = _program("ffmpeg", "FFmpeg")
    gifski = _program("gifski", "Składanie GIF-ów (gifski)")
    if args.start and not ZAPIS_CZASU.match(args.start):
        raise ToolError(f"Nieprawidłowy czas początku: {args.start}")
    klatek = round(args.fps * args.czas_s)
    if klatek > MAKS_KLATEK_GIF:
        raise ToolError(
            f"{klatek} klatek to za dużo jak na GIF — skróć fragment albo zmniejsz liczbę klatek na sekundę."
        )
    nazwa, sciezka = _film(ctx, args.file_id)

    katalog = ctx.output_path("klatki")
    katalog.mkdir(parents=True, exist_ok=True)
    ctx.progress(f"Pobieranie klatek: {nazwa}")
    ctx.run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-y",
            *(["-ss", args.start] if args.start else []),
            "-t",
            f"{args.czas_s:.2f}",
            "-i",
            str(sciezka),
            "-vf",
            f"fps={args.fps},scale={args.szerokosc}:-2:flags=lanczos",
            str(katalog / "klatka_%05d.png"),
        ],
        timeout=CZAS_GIF,
    )
    klatki = sorted(katalog.glob("klatka_*.png"))
    if not klatki:
        raise ToolError(f"Z filmu {nazwa} nie udało się pobrać klatek — sprawdź, czy fragment w nim leży.")

    cel = ctx.output_path(with_suffix(nazwa, ".gif"))
    ctx.progress(f"Składanie GIF-a z {len(klatki)} klatek")
    ctx.run_command(
        [
            gifski,
            "--output",
            str(cel),
            "--fps",
            str(args.fps),
            "--quality",
            str(args.jakosc),
            "--width",
            str(args.szerokosc),
            *(str(klatka) for klatka in klatki),
        ],
        timeout=CZAS_GIF,
    )
    if not cel.is_file():
        raise ToolError(f"GIF z {nazwa} nie powstał.")
    with Image.open(klatki[0]) as otwarty:
        podglad = image_preview(otwarty, PODGLAD)
    waga_mb = round(cel.stat().st_size / 1_000_000, 2)
    return ToolResult(
        {"output": cel.name, "klatki": len(klatki), "waga_mb": waga_mb},
        f"GIF gotowy: {len(klatki)} klatek, {waga_mb} MB",
        images=[podglad],
        files=[OutputFile(cel, cel.name, f"GIF z fragmentu: {nazwa}")],
    )


# --- Lottie --------------------------------------------------------------------------------------


def _animacja_biblioteki(nazwa: str) -> Path:
    """Ścieżka animacji z biblioteki serwera; odrzuca wszystko, co wychodzi poza nią."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,60}/[A-Za-z0-9][A-Za-z0-9._-]{0,80}", nazwa):
        raise ToolError(
            f"Nieprawidłowa nazwa animacji {nazwa!r}. Podaj postać „zbior/nazwa” ze spisu lottie_library."
        )
    plik = (LOTTIE_BIBLIOTEKA / "animacje" / f"{nazwa}.json").resolve()
    korzen = (LOTTIE_BIBLIOTEKA / "animacje").resolve()
    if not plik.is_file() or korzen not in plik.parents:
        raise ToolError(f"Biblioteka nie ma animacji {nazwa!r}. Spis pokazuje lottie_library.")
    return plik


class WykazLottieInput(ToolInput):
    szukaj: str = Field(
        default="",
        max_length=60,
        description="Fragment nazwy (np. „loading”, „check”, „rocket”). Pusto = początek spisu.",
    )
    limit: int = Field(default=30, ge=1, le=LOTTIE_LIMIT, description="Ile pozycji zwrócić.")


@registry.register(
    "lottie_library",
    """Spis gotowych animacji Lottie leżących na serwerze — animacje interfejsu, ikony w ruchu,
wskaźniki ładowania, ilustracje. Użyj, zanim sięgniesz po render_lottie: wybierasz pozycję ze
spisu i podajesz jej identyfikator („zbior/nazwa”) do render_lottie, bez proszenia użytkownika
o plik. Do ożywienia strony, materiału promocyjnego albo wstawki do posta.""",
    WykazLottieInput,
)
def lottie_library(ctx: ToolContext, args: WykazLottieInput) -> ToolResult:
    if not LOTTIE_WYKAZ.is_file():
        raise ToolError("Biblioteka animacji Lottie nie jest zainstalowana na tym serwerze.")
    try:
        wykaz = json.loads(LOTTIE_WYKAZ.read_text(encoding="utf-8"))
    except (OSError, ValueError) as blad:
        raise ToolError("Wykaz biblioteki animacji jest nieczytelny.") from blad
    animacje = wykaz.get("animacje") or []
    igla = args.szukaj.strip().lower()
    if igla:
        animacje = [a for a in animacje if igla in str(a.get("id", "")).lower()]
    wybrane = animacje[: args.limit]
    dane = {
        "wszystkich": wykaz.get("pozycji", len(wykaz.get("animacje") or [])),
        "pasujacych": len(animacje),
        "animacje": wybrane,
    }
    if igla and not animacje:
        return ToolResult(dane, f"Biblioteka nie ma animacji pasującej do „{args.szukaj}”.")
    return ToolResult(
        dane,
        f"Animacje Lottie: {len(wybrane)} z {dane['pasujacych']} pasujących "
        f"(w bibliotece {dane['wszystkich']}). Identyfikator podaj do render_lottie.",
    )


class LottieInput(ToolInput):
    file_id: str = Field(
        default="",
        description="Plik animacji Lottie z rozmowy (.json albo .lottie). Zamiast tego można podać "
        "`animacja` — pozycję z biblioteki serwera.",
    )
    animacja: str = Field(
        default="",
        max_length=120,
        description="Animacja z biblioteki serwera w postaci „zbior/nazwa” (spis: lottie_library).",
    )
    format_wyniku: Literal["mp4", "webm", "gif", "png"] = Field(
        default="mp4",
        description="mp4 do filmu i prezentacji, webm z przezroczystością, gif do wiadomości, "
        "png = jedna klatka.",
    )
    szerokosc: int = Field(
        default=800, ge=64, le=1920, description="Szerokość wyniku w pikselach (wysokość w proporcji)."
    )
    fps: int = Field(default=0, ge=0, le=60, description="Klatki na sekundę; 0 zostawia tempo animacji.")
    tlo: str = Field(
        default="",
        max_length=7,
        description="Barwa tła „#RRGGBB”; puste = przezroczyste (PNG, GIF, WEBM) albo białe (MP4).",
    )


@registry.register(
    "render_lottie",
    """Zamienia gotową animację z sieci albo z pakietu graficznego w zwykły film lub obrazek.
Z pliku .json albo .lottie powstaje MP4, WEBM z przezroczystością, GIF albo pojedyncza klatka
PNG. Używaj, gdy użytkownik przyniósł taką animację i chce z niej film, obrazek albo wstawkę
do posta; nic innego w zestawie nie otwiera tego formatu.""",
    LottieInput,
)
def render_lottie(ctx: ToolContext, args: LottieInput) -> ToolResult:
    program = _program("danaco-lottie", "Render animacji Lottie")
    if args.animacja and args.file_id:
        raise ToolError("Podaj albo plik z rozmowy (file_id), albo animację z biblioteki — nie oba naraz.")
    if args.animacja:
        sciezka = _animacja_biblioteki(args.animacja)
        nazwa_zrodla = sciezka.name
    elif args.file_id:
        plik = ctx.file(args.file_id)
        if plik.suffix not in LOTTIE_ROZSZERZENIA:
            raise ToolError(f"{plik.name} nie jest animacją Lottie — potrzebny plik .json albo .lottie.")
        sciezka = plik.path
        nazwa_zrodla = plik.name
    else:
        raise ToolError("Podaj plik animacji (file_id) albo pozycję z biblioteki (animacja).")
    if args.tlo and not BARWA.match(args.tlo):
        raise ToolError(f"Barwa tła musi mieć postać „#RRGGBB”, a nie {args.tlo!r}.")
    cel = ctx.output_path(with_suffix(nazwa_zrodla, f".{args.format_wyniku}"))
    polecenie = [program, "render", str(sciezka), str(cel), "--szerokosc", str(args.szerokosc)]
    if args.fps:
        polecenie += ["--fps", str(args.fps)]
    if args.tlo:
        polecenie += ["--tlo", args.tlo]
    ctx.progress(f"Renderowanie animacji: {nazwa_zrodla}")
    ctx.run_command(polecenie, timeout=CZAS_LOTTIE)
    if not cel.is_file():
        raise ToolError(f"Render animacji {nazwa_zrodla} nie dał pliku wynikowego.")
    podglady: list[bytes] = []
    if args.format_wyniku in {"png", "gif"}:
        with Image.open(cel) as otwarty:
            podglady.append(image_preview(otwarty.convert("RGB"), PODGLAD))
    return ToolResult(
        {"output": cel.name, "format": args.format_wyniku},
        f"Animacja wyrenderowana: {nazwa_zrodla} → {args.format_wyniku.upper()}",
        images=podglady,
        files=[OutputFile(cel, cel.name, f"{nazwa_zrodla} jako {args.format_wyniku.upper()}")],
    )


__all__ = [
    "blur_background_by_depth",
    "lottie_library",
    "depth_map",
    "inpaint_photo",
    "render_lottie",
    "restore_faces",
    "video_to_gif",
]
