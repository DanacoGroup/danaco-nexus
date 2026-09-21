"""Narzędzia korzystające z programów specjalistycznych zainstalowanych na serwerze.

Na serwerze leży kilkadziesiąt programów, z których agent nie mógł skorzystać, bo żaden
nie miał narzędzia w rejestrze. Cztery z nich dają funkcje, których nie zastąpi nic z
dotychczasowego zestawu:

* koloryzacja zdjęć czarno-białych (DDColor) — dopełnienie „odśwież stare zdjęcie”,
* odszumianie mowy (DeepFilterNet) — czysty dźwięk przed transkrypcją i do publikacji,
* ożywienie zdjęcia paralaksą 2.5D (mapa głębi + LaMa + FFmpeg) — film z jednego zdjęcia,
* rozdzielenie utworu na ścieżki (Demucs) — wokal, perkusja, bas i reszta osobno.
* rozpoznawanie twarzy (InsightFace) — porządkowanie archiwum zdjęć według osób.

Uwaga do ostatniego: modele InsightFace mają licencję niekomercyjną, a wizerunek
twarzy to dane biometryczne — szczególna kategoria wg RODO. Zastrzeżenie brzmiało
„przed wejściem produktu na rynek”, a **produkt wszedł na rynek 21 września 2026**
(sprzedaż włączona, Stripe skonfigurowany) — więc oba punkty czekają na rozstrzygnięcie
już teraz: licencja (wymiana modelu albo umowa z autorami) i podstawa przetwarzania
(zgoda, okres przechowywania wektorów). Czynność jest opisana
w `docs/zgodnosc/REJESTR-CZYNNOSCI.md` (CZ-14).

Każdy z tych programów ma na serwerze gotowe polecenie `danaco-*`, które ustawia modele
i tryb offline. Wywołujemy je zamiast powtarzać tu tamtą konfigurację.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Literal

from PIL import Image
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
from nexus.tools.common import file_kind, unique_name, with_suffix

PODGLAD = 1024

#: Modele liczą na procesorze — to minuty, nie sekundy. Limity są hojne, ale skończone.
CZAS_OBRAZ = 900
CZAS_DZWIEK = 1800
CZAS_FILM = 1800


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


def _nagranie(ctx: ToolContext, file_id: str) -> tuple[str, Path]:
    plik = ctx.file(file_id)
    if file_kind(plik) not in {"audio", "video"}:
        raise ToolError(f"{plik.name} nie jest nagraniem dźwiękowym ani filmem.")
    return plik.name, plik.path


class KoloryzacjaInput(ToolInput):
    file_ids: list[str] = Field(min_length=1, max_length=10, description="Zdjęcia do pokolorowania.")
    jakosc: Literal["najlepsza", "szybka"] = Field(
        default="najlepsza",
        description="najlepsza = model duży (dokładniejsze barwy, wolniej); szybka = model mały.",
    )
    nasycenie: float = Field(
        default=1.0, ge=0.2, le=2.0, description="Siła barw: 1,0 to wynik modelu, niżej — stonowany."
    )


@registry.register(
    "colorize_photo",
    """Koloryzuje zdjęcie czarno-białe albo sepiowe (model DDColor). Barwy są nadawane od nowa
na podstawie treści zdjęcia — do zdjęć rodzinnych, archiwalnych i skanów starych odbitek.
Zdjęcie kolorowe zostaje najpierw sprowadzone do jasności, więc narzędzie nadaje się też do
przebarwienia materiału o zepsutych kolorach. Do zwykłej korekty barw służy enhance_photo.""",
    KoloryzacjaInput,
)
def colorize_photo(ctx: ToolContext, args: KoloryzacjaInput) -> ToolResult:
    program = _program("danaco-koloryzacja", "Koloryzacja zdjęć")
    uzyte: set[str] = set()
    wyniki: list[OutputFile] = []
    podglady: list[bytes] = []
    for file_id in args.file_ids:
        ctx.check_cancelled()
        nazwa, sciezka = _obraz(ctx, file_id)
        cel = ctx.output_path(unique_name(with_suffix(nazwa, ".png", "_kolor"), uzyte))
        ctx.progress(f"Koloryzowanie: {nazwa}")
        ctx.run_command(
            [
                program,
                "--model",
                "duzy" if args.jakosc == "najlepsza" else "maly",
                "--nasycenie",
                f"{args.nasycenie:.2f}",
                str(sciezka),
                str(cel),
            ],
            timeout=CZAS_OBRAZ,
        )
        if not cel.is_file():
            raise ToolError(f"Koloryzacja {nazwa} nie dała pliku wynikowego.")
        wyniki.append(OutputFile(cel, cel.name, f"Pokolorowane: {nazwa}"))
        podglady.append(image_preview(Image.open(cel), PODGLAD))
    return ToolResult(
        {"pliki": [plik.name for plik in wyniki]},
        f"Koloryzacja: {len(wyniki)} zdj.",
        images=podglady,
        files=wyniki,
    )


class OdszumInput(ToolInput):
    file_id: str = Field(description="Nagranie dźwiękowe albo film z mową do oczyszczenia.")
    tlumienie_db: int = Field(
        default=0,
        ge=0,
        le=60,
        description="Ile decybeli odjąć szumowi (0 = pełne tłumienie modelu, niżej = delikatniej).",
    )
    format_wyniku: Literal["wav", "flac", "mp3"] = Field(
        default="wav", description="wav i flac są bezstratne; mp3 waży najmniej."
    )


@registry.register(
    "clean_audio",
    """Usuwa z nagrania mowy szum, wiatr, brum i pogłos (DeepFilterNet 3). Stosuj przed
transkrypcją słabego nagrania oraz wtedy, gdy nagranie ma pójść do publikacji — rozmowa
ze spotkania, wywiad, dyktafon, ścieżka dźwiękowa filmu. Przyjmuje też pliki wideo:
wynikiem jest wtedy sam oczyszczony dźwięk.""",
    OdszumInput,
)
def clean_audio(ctx: ToolContext, args: OdszumInput) -> ToolResult:
    program = _program("danaco-odszum", "Odszumianie nagrań")
    nazwa, sciezka = _nagranie(ctx, args.file_id)
    cel = ctx.output_path(with_suffix(nazwa, f".{args.format_wyniku}", "_czyste"))
    polecenie = [program, "--metoda", "deepfilternet"]
    if args.tlumienie_db:
        polecenie += ["--tlumienie", str(args.tlumienie_db)]
    ctx.progress(f"Oczyszczanie dźwięku: {nazwa}")
    ctx.run_command([*polecenie, str(sciezka), str(cel)], timeout=CZAS_DZWIEK)
    if not cel.is_file():
        raise ToolError(f"Oczyszczanie {nazwa} nie dało pliku wynikowego.")
    return ToolResult(
        {"output": cel.name},
        f"Dźwięk oczyszczony: {nazwa}",
        files=[OutputFile(cel, cel.name, "Nagranie bez szumu i pogłosu")],
    )


class OzywienieInput(ToolInput):
    file_id: str = Field(description="Zdjęcie, z którego ma powstać film.")
    czas_s: int = Field(default=5, ge=2, le=20, description="Długość filmu w sekundach.")
    ruch: Literal["przybliz", "poziomo", "pionowo", "okrag"] = Field(
        default="przybliz", description="Ruch kamery nad zdjęciem."
    )
    sila: float = Field(default=1.0, ge=0.2, le=2.0, description="Siła efektu głębi.")
    kadr: Literal["auto", "16:9", "9:16", "1:1", "4:3", "3:4"] = Field(
        default="auto", description="Proporcje kadru; 9:16 do mediów społecznościowych."
    )


@registry.register(
    "animate_photo",
    """Zamienia zdjęcie w krótki film z efektem paralaksy 2.5D: mapa głębi rozdziela plany,
kamera przesuwa się nad kadrem, a odsłonięte miejsca są dopełniane. Do ożywienia zdjęcia
archiwalnego, wstawki do filmu, posta w mediach społecznościowych albo prezentacji.
Wynik to plik MP4 bez dźwięku.""",
    OzywienieInput,
)
def animate_photo(ctx: ToolContext, args: OzywienieInput) -> ToolResult:
    program = _program("danaco-ozyw-zdjecie", "Ożywianie zdjęć")
    nazwa, sciezka = _obraz(ctx, args.file_id)
    cel = ctx.output_path(with_suffix(nazwa, ".mp4", "_film"))
    polecenie = [
        program,
        "--czas",
        str(args.czas_s),
        "--ruch",
        args.ruch,
        "--sila",
        f"{args.sila:.2f}",
        "--format",
        args.kadr,
    ]
    ctx.progress(f"Ożywianie zdjęcia: {nazwa}")
    ctx.run_command([*polecenie, str(sciezka), str(cel)], timeout=CZAS_FILM)
    if not cel.is_file():
        raise ToolError(f"Ożywienie {nazwa} nie dało pliku wynikowego.")
    return ToolResult(
        {"output": cel.name, "czas_s": args.czas_s},
        f"Film ze zdjęcia: {nazwa}",
        files=[OutputFile(cel, cel.name, f"Film {args.czas_s} s z paralaksą")],
    )


class RozdzielenieInput(ToolInput):
    file_id: str = Field(description="Utwór albo nagranie do rozdzielenia na ścieżki.")
    tylko_wokal: bool = Field(
        default=False, description="Prawda = dwie ścieżki (wokal i podkład) zamiast czterech."
    )
    format_wyniku: Literal["wav", "flac", "mp3"] = Field(default="wav", description="Format ścieżek.")


@registry.register(
    "split_audio_tracks",
    """Rozdziela nagranie muzyczne na osobne ścieżki (Demucs): wokal, perkusja, bas i reszta —
albo sam wokal i podkład. Do karaoke, podkładu pod film, wyciągnięcia głosu z nagrania
z muzyką w tle i do pracy nad materiałem dźwiękowym.""",
    RozdzielenieInput,
)
def split_audio_tracks(ctx: ToolContext, args: RozdzielenieInput) -> ToolResult:
    program = _program("danaco-rozdziel-audio", "Rozdzielanie ścieżek")
    nazwa, sciezka = _nagranie(ctx, args.file_id)
    katalog = ctx.output_path("sciezki").parent
    polecenie = [program, "--format", args.format_wyniku, "--wyjscie", str(katalog)]
    if args.tylko_wokal:
        polecenie.append("--wokal")
    ctx.progress(f"Rozdzielanie ścieżek: {nazwa}")
    ctx.run_command([*polecenie, str(sciezka)], timeout=CZAS_DZWIEK)
    sciezki = sorted(plik for plik in katalog.rglob(f"*.{args.format_wyniku}") if plik.is_file())
    if not sciezki:
        raise ToolError(f"Rozdzielenie {nazwa} nie dało żadnej ścieżki.")
    wyniki = [OutputFile(plik, plik.name, f"Ścieżka: {plik.stem}") for plik in sciezki]
    return ToolResult(
        {"sciezki": [plik.name for plik in wyniki]},
        f"Ścieżki rozdzielone: {len(wyniki)}",
        files=wyniki,
    )


__all__ = ["animate_photo", "clean_audio", "colorize_photo", "find_faces", "split_audio_tracks"]


class TwarzeInput(ToolInput):
    file_ids: list[str] = Field(
        min_length=1, max_length=60, description="Zdjęcia do przejrzenia pod kątem twarzy."
    )
    grupuj: bool = Field(
        default=False,
        description="Prawda = pogrupuj twarze tej samej osoby na wszystkich zdjęciach naraz.",
    )
    prog: float = Field(
        default=0.40,
        ge=0.2,
        le=0.9,
        description="Próg podobieństwa przy grupowaniu: wyżej = ostrzej, mniej pomyłek, więcej grup.",
    )


@registry.register(
    "find_faces",
    """Znajduje twarze na zdjęciach i — na życzenie — grupuje zdjęcia tej samej osoby
(InsightFace). Do porządkowania archiwum rodzinnego i zbioru zdjęć z wydarzenia:
„na których zdjęciach jest babcia”, „rozdziel te dwieście zdjęć według osób”.
Zwraca liczbę i położenie twarzy, a przy grupowaniu — przypisanie zdjęć do osób.
Nie rozpoznaje tożsamości: mówi wyłącznie, które twarze są do siebie podobne.""",
    TwarzeInput,
)
def find_faces(ctx: ToolContext, args: TwarzeInput) -> ToolResult:
    program = _program("danaco-twarze-indeks", "Rozpoznawanie twarzy")
    katalog = ctx.output_path("twarze").parent
    nazwy: dict[str, str] = {}
    for file_id in args.file_ids:
        ctx.check_cancelled()
        nazwa, sciezka = _obraz(ctx, file_id)
        kopia = katalog / sciezka.name
        kopia.write_bytes(sciezka.read_bytes())
        nazwy[kopia.name] = nazwa

    wynik = ctx.output_path("twarze.json")
    if args.grupuj:
        ctx.progress(f"Grupowanie twarzy na {len(nazwy)} zdj.")
        polecenie = [program, "grupuj", "--prog", f"{args.prog:.2f}", "--wyjscie", str(wynik), str(katalog)]
    else:
        if len(args.file_ids) > 1:
            raise ToolError("Bez grupowania narzędzie czyta jedno zdjęcie naraz — włącz grupowanie.")
        ctx.progress("Szukanie twarzy")
        jedyne = next(iter(nazwy))
        polecenie = [program, "wykryj", "--wyjscie", str(wynik), str(katalog / jedyne)]

    ctx.run_command(polecenie, timeout=CZAS_DZWIEK)
    if not wynik.is_file():
        raise ToolError("Rozpoznawanie twarzy nie zwróciło wyniku.")
    dane = json.loads(wynik.read_text(encoding="utf-8"))
    podsumowanie = (
        f"Twarze: {len(dane.get('grupy', []))} osób na {len(nazwy)} zdj."
        if args.grupuj
        else f"Twarze na zdjęciu: {len(dane.get('twarze', []))}"
    )
    return ToolResult(
        {"wynik": dane, "nazwy_plikow": nazwy},
        podsumowanie,
        files=[OutputFile(wynik, wynik.name, "Wynik rozpoznawania twarzy (JSON)")],
    )
