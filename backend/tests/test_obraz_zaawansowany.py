"""Narzędzia obrazu, zdjęcia i wideo oparte na programach serwera.

Modele głębi, rekonstrukcji twarzy i inpaintingu liczą na procesorze minutami, więc
testy nie uruchamiają ich na prawdziwych plikach. Sprawdzają to, co decyduje o
poprawności: obecność w rejestrze, odrzucenie pliku niewłaściwego rodzaju, komunikat
przy braku programu oraz złożenie polecenia z wyborów użytkownika. Tam, gdzie wynik
powstaje po stronie narzędzia (maska z prostokątów, rozmycie według mapy głębi),
liczony jest naprawdę — na podstawionej odpowiedzi programu.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from conftest import ToolHarness
from PIL import Image, ImageDraw

from nexus.tools import obraz_zaawansowany
from nexus.tools.base import ToolError, registry

NARZEDZIA = (
    "restore_faces",
    "inpaint_photo",
    "depth_map",
    "blur_background_by_depth",
    "video_to_gif",
    "render_lottie",
    "lottie_library",
)


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object):  # type: ignore[no-untyped-def]
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


def podstaw_programy(monkeypatch, brakujace: set[str] | None = None) -> None:  # type: ignore[no-untyped-def]
    """Udaje, że polecenia serwera są zainstalowane (poza wymienionymi)."""
    brak = brakujace or set()
    monkeypatch.setattr(
        "nexus.tools.obraz_zaawansowany.shutil.which",
        lambda nazwa: None if nazwa in brak else f"/udawane/{nazwa}",
    )


def podstaw_przebieg(
    monkeypatch,  # type: ignore[no-untyped-def]
    zapis: list[list[str]],
    efekt: Callable[[list[str]], str] | None = None,
) -> None:
    """Zastępuje uruchamianie programów: zapisuje polecenie i oddaje jego wyjście."""

    def udawany_bieg(self, arguments, timeout=600, cwd=None, env=None):  # type: ignore[no-untyped-def]
        polecenie = list(arguments)
        zapis.append(polecenie)
        wyjscie = efekt(polecenie) if efekt else ""
        return subprocess.CompletedProcess(polecenie, 0, wyjscie, "")

    monkeypatch.setattr("nexus.tools.base.ToolContext.run_command", udawany_bieg)


def zdjecie(katalog: Path, nazwa: str = "zdjecie.png") -> Path:
    """Obraz z ostrą krawędzią w każdej połowie kadru — po rozmyciu widać różnicę."""
    obraz = Image.new("RGB", (64, 64), (240, 240, 240))
    rysunek = ImageDraw.Draw(obraz)
    rysunek.rectangle([8, 4, 56, 20], fill=(10, 10, 10))
    rysunek.rectangle([8, 44, 56, 60], fill=(10, 10, 10))
    plik = katalog / nazwa
    obraz.save(plik)
    return plik


def test_narzedzia_sa_w_rejestrze() -> None:
    assert set(NARZEDZIA) <= set(registry.names())


def test_rekonstrukcja_odrzuca_plik_ktory_nie_jest_obrazem(harness: ToolHarness, tmp_path: Path) -> None:
    notatka = tmp_path / "notatka.txt"
    notatka.write_text("to nie jest zdjęcie", encoding="utf-8")
    with pytest.raises(ToolError, match="nie jest obrazem"):
        wywolaj(harness, "restore_faces", file_ids=[harness.add(notatka)])


def test_gif_odrzuca_plik_ktory_nie_jest_filmem(harness: ToolHarness, tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="nie jest filmem"):
        wywolaj(harness, "video_to_gif", file_id=harness.add(zdjecie(tmp_path)))


def test_brak_programu_mowi_po_ludzku(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Gdy programu nie ma, użytkownik dostaje zdanie, a nie ślad wykonania."""
    podstaw_programy(monkeypatch, brakujace={"danaco-retusz-twarzy"})
    with pytest.raises(ToolError, match="niedostępne na tym serwerze"):
        wywolaj(harness, "restore_faces", file_ids=[harness.add(zdjecie(tmp_path))])


def test_rekonstrukcja_sklada_polecenie_z_wyborami_uzytkownika(
    harness: ToolHarness, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    zapis: list[list[str]] = []
    podstaw_programy(monkeypatch)
    podstaw_przebieg(monkeypatch, zapis, lambda polecenie: _zapisz_obraz(polecenie[-1], "twarze 2"))
    wynik = wywolaj(
        harness,
        "restore_faces",
        file_ids=[harness.add(zdjecie(tmp_path))],
        model="gfpgan",
        wiernosc=0.35,
        powiekszenie=2,
        tylko_glowna=True,
    )
    polecenie = zapis[0]
    assert polecenie[0].endswith("danaco-retusz-twarzy")
    assert polecenie[polecenie.index("--model") + 1] == "gfpgan"
    assert polecenie[polecenie.index("--wiernosc") + 1] == "0.35"
    assert polecenie[polecenie.index("--skala") + 1] == "2"
    assert "--tylko-srodkowa" in polecenie
    assert wynik.data["twarze"] == {"zdjecie.png": 2}


def test_rekonstrukcja_nie_udaje_poprawy_bez_twarzy(
    harness: ToolHarness, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    """Program przy braku twarzy przepisuje obraz bez zmian — narzędzie ma to powiedzieć."""
    podstaw_programy(monkeypatch)
    podstaw_przebieg(monkeypatch, [], lambda polecenie: _zapisz_obraz(polecenie[-1], "twarze 0"))
    with pytest.raises(ToolError, match="nie rozpoznałem twarzy"):
        wywolaj(harness, "restore_faces", file_ids=[harness.add(zdjecie(tmp_path))])


def _zapisz_obraz(sciezka: str, komunikat: str = "") -> str:
    """Udaje wynik programu: zapisuje mały obraz pod wskazaną ścieżką."""
    Image.new("RGB", (32, 32), (128, 128, 128)).save(sciezka)
    return komunikat


def test_naprawa_wymaga_wskazania_co_usunac(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    podstaw_programy(monkeypatch)
    with pytest.raises(ToolError, match="Nie wiem, co usunąć"):
        wywolaj(harness, "inpaint_photo", file_id=harness.add(zdjecie(tmp_path)))


def test_naprawa_odrzuca_bledny_prostokat(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    podstaw_programy(monkeypatch)
    with pytest.raises(ToolError, match="cztery ułamki"):
        wywolaj(
            harness,
            "inpaint_photo",
            file_id=harness.add(zdjecie(tmp_path)),
            obszary=[[0.1, 0.1, 2.0, 0.3]],
        )


def test_naprawa_buduje_maske_z_prostokatow(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Prostokąty z rozmowy mają się zamienić w białą maskę we właściwym miejscu."""
    zapis: list[list[str]] = []
    podstaw_programy(monkeypatch)
    podstaw_przebieg(monkeypatch, zapis, lambda polecenie: _zapisz_obraz(polecenie[-1]))
    wywolaj(
        harness,
        "inpaint_photo",
        file_id=harness.add(zdjecie(tmp_path)),
        obszary=[[0.5, 0.5, 0.25, 0.25]],
        rozszerz_px=7,
    )
    polecenie = zapis[0]
    assert polecenie[0].endswith("danaco-usun-obiekt")
    assert polecenie[polecenie.index("--rozszerz") + 1] == "7"
    assert "--rysy" not in polecenie
    maska = np.asarray(Image.open(polecenie[polecenie.index("--maska") + 1]).convert("L"))
    assert maska.shape == (64, 64)
    assert maska[40, 40] == 255
    assert maska[8, 8] == 0


def test_naprawa_w_trybie_rys_nie_potrzebuje_maski(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    zapis: list[list[str]] = []
    podstaw_programy(monkeypatch)
    podstaw_przebieg(monkeypatch, zapis, lambda polecenie: _zapisz_obraz(polecenie[-1]))
    wywolaj(harness, "inpaint_photo", file_id=harness.add(zdjecie(tmp_path)), rysy=True, czulosc=1.8)
    polecenie = zapis[0]
    assert "--maska" not in polecenie
    assert "--rysy" in polecenie
    assert polecenie[polecenie.index("--czulosc") + 1] == "1.80"


def _zapisz_glebie(sciezka: str, gorna_polowa_dalej: bool = True) -> str:
    """Udaje mapę głębi: PNG 16-bit, w którym jaśniej znaczy bliżej."""
    mapa = np.zeros((64, 64), dtype=np.uint16)
    mapa[32:, :] = 65535 if gorna_polowa_dalej else 0
    mapa[:32, :] = 0 if gorna_polowa_dalej else 65535
    Image.fromarray(mapa).save(sciezka)
    return ""


def test_mapa_glebi_przekazuje_rozdzielczosc_i_podglad(
    harness: ToolHarness, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    zapis: list[list[str]] = []
    podstaw_programy(monkeypatch)

    def efekt(polecenie: list[str]) -> str:
        _zapisz_glebie(polecenie[-1])
        _zapisz_obraz(polecenie[polecenie.index("--podglad") + 1])
        return ""

    podstaw_przebieg(monkeypatch, zapis, efekt)
    wynik = wywolaj(harness, "depth_map", file_id=harness.add(zdjecie(tmp_path)), szczegolowosc="wysoka")
    polecenie = zapis[0]
    assert polecenie[0].endswith("danaco-glebia")
    assert polecenie[polecenie.index("--rozdzielczosc") + 1] == "770"
    assert polecenie[polecenie.index("--podglad") + 1].endswith("_glebia_podglad.png")
    assert len(wynik.files) == 2


def test_rozmycie_zostawia_ostry_plan_bliski(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Przy ostrości na pierwszym planie dalszy plan ma się rozmyć, a bliższy zostać."""
    podstaw_programy(monkeypatch)
    podstaw_przebieg(monkeypatch, [], lambda polecenie: _zapisz_glebie(polecenie[-1]))
    zrodlo = zdjecie(tmp_path)
    wynik = wywolaj(
        harness,
        "blur_background_by_depth",
        file_id=harness.add(zrodlo),
        punkt_ostrosci=1.0,
        strefa_ostrosci=0.0,
        sila=12,
    )
    przed = np.asarray(Image.open(zrodlo).convert("RGB"), dtype=np.int16)
    po = np.asarray(Image.open(wynik.files[0].path).convert("RGB"), dtype=np.int16)
    assert np.array_equal(przed[40:, :], po[40:, :])
    assert np.abs(przed[:24, :] - po[:24, :]).max() > 10


def test_rozmycie_zglasza_plaska_glebie(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    podstaw_programy(monkeypatch)

    def efekt(polecenie: list[str]) -> str:
        Image.fromarray(np.full((64, 64), 700, dtype=np.uint16)).save(polecenie[-1])
        return ""

    podstaw_przebieg(monkeypatch, [], efekt)
    with pytest.raises(ToolError, match="nie da się rozdzielić planów"):
        wywolaj(harness, "blur_background_by_depth", file_id=harness.add(zdjecie(tmp_path)))


def film(katalog: Path) -> Path:
    plik = katalog / "nagranie.mp4"
    plik.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return plik


def test_gif_odrzuca_zbyt_dlugi_fragment(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    podstaw_programy(monkeypatch)
    with pytest.raises(ToolError, match="za dużo jak na GIF"):
        wywolaj(harness, "video_to_gif", file_id=harness.add(film(tmp_path)), czas_s=20, fps=30)


def test_gif_odrzuca_bledny_czas_poczatku(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    podstaw_programy(monkeypatch)
    with pytest.raises(ToolError, match="Nieprawidłowy czas"):
        wywolaj(harness, "video_to_gif", file_id=harness.add(film(tmp_path)), start="za chwilę")


def test_gif_idzie_przez_ffmpeg_i_gifski(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Klatki pobiera FFmpeg, barwy dobiera gifski — oba polecenia muszą dostać swoje wybory."""
    zapis: list[list[str]] = []
    podstaw_programy(monkeypatch)

    def efekt(polecenie: list[str]) -> str:
        if polecenie[0].endswith("ffmpeg"):
            katalog = Path(polecenie[-1]).parent
            for numer in (1, 2):
                Image.new("RGB", (24, 16), (numer * 40, 60, 90)).save(katalog / f"klatka_{numer:05d}.png")
        else:
            Path(polecenie[polecenie.index("--output") + 1]).write_bytes(b"GIF89a")
        return ""

    podstaw_przebieg(monkeypatch, zapis, efekt)
    wynik = wywolaj(
        harness,
        "video_to_gif",
        file_id=harness.add(film(tmp_path)),
        start="00:00:05",
        czas_s=2,
        fps=12,
        szerokosc=320,
        jakosc=80,
    )
    ffmpeg, gifski = zapis
    assert ffmpeg[ffmpeg.index("-ss") + 1] == "00:00:05"
    assert ffmpeg[ffmpeg.index("-t") + 1] == "2.00"
    assert "fps=12" in ffmpeg[ffmpeg.index("-vf") + 1]
    assert gifski[0].endswith("gifski")
    assert gifski[gifski.index("--fps") + 1] == "12"
    assert gifski[gifski.index("--quality") + 1] == "80"
    assert gifski[gifski.index("--width") + 1] == "320"
    assert gifski[-2:] == [
        str(Path(ffmpeg[-1]).parent / "klatka_00001.png"),
        str(Path(ffmpeg[-1]).parent / "klatka_00002.png"),
    ]
    assert wynik.data["klatki"] == 2


def test_lottie_odrzuca_plik_ktory_nie_jest_animacja(
    harness: ToolHarness, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    podstaw_programy(monkeypatch)
    with pytest.raises(ToolError, match="nie jest animacją Lottie"):
        wywolaj(harness, "render_lottie", file_id=harness.add(zdjecie(tmp_path)))


def test_lottie_sklada_polecenie_renderu(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    zapis: list[list[str]] = []
    podstaw_programy(monkeypatch)

    def efekt(polecenie: list[str]) -> str:
        Image.new("RGB", (16, 16), (200, 30, 30)).save(polecenie[3], format="GIF")
        return ""

    podstaw_przebieg(monkeypatch, zapis, efekt)
    animacja = tmp_path / "znak.json"
    animacja.write_text('{"v":"5.7.4","fr":25,"w":100,"h":100,"layers":[]}', encoding="utf-8")
    wynik = wywolaj(
        harness,
        "render_lottie",
        file_id=harness.add(animacja),
        format_wyniku="gif",
        szerokosc=480,
        fps=30,
        tlo="#FFFFFF",
    )
    polecenie = zapis[0]
    assert polecenie[0].endswith("danaco-lottie")
    assert polecenie[1] == "render"
    assert polecenie[3].endswith("znak.gif")
    assert polecenie[polecenie.index("--szerokosc") + 1] == "480"
    assert polecenie[polecenie.index("--fps") + 1] == "30"
    assert polecenie[polecenie.index("--tlo") + 1] == "#FFFFFF"
    assert wynik.data["format"] == "gif"
    assert len(wynik.images) == 1


# --- biblioteka animacji Lottie -------------------------------------------------------------


def biblioteka_lottie(tmp_path: Path, monkeypatch) -> Path:  # type: ignore[no-untyped-def]
    """Podstawiona biblioteka serwera: dwie animacje i wykaz."""
    korzen = tmp_path / "lottie"
    (korzen / "animacje" / "airbnb").mkdir(parents=True)
    for nazwa in ("check-pop", "rakieta"):
        (korzen / "animacje" / "airbnb" / f"{nazwa}.json").write_text(
            '{"v":"5.7.4","fr":25,"w":100,"h":100,"op":50,"ip":0,"layers":[]}', encoding="utf-8"
        )
    (korzen / "indeks.json").write_text(
        json.dumps(
            {
                "pozycji": 2,
                "animacje": [
                    {
                        "id": "airbnb/check-pop",
                        "nazwa": "check pop",
                        "zbior": "airbnb",
                        "licencja": "Apache-2.0",
                    },
                    {"id": "airbnb/rakieta", "nazwa": "rakieta", "zbior": "airbnb", "licencja": "Apache-2.0"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(obraz_zaawansowany, "LOTTIE_BIBLIOTEKA", korzen)
    monkeypatch.setattr(obraz_zaawansowany, "LOTTIE_WYKAZ", korzen / "indeks.json")
    return korzen


def test_wykaz_animacji_zaweza_po_nazwie(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    biblioteka_lottie(tmp_path, monkeypatch)
    wynik = wywolaj(harness, "lottie_library", szukaj="rakieta")
    assert wynik.data["pasujacych"] == 1
    assert wynik.data["animacje"][0]["id"] == "airbnb/rakieta"

    puste = wywolaj(harness, "lottie_library", szukaj="czegotaniema")
    assert puste.data["pasujacych"] == 0
    assert "nie ma animacji" in puste.summary


def test_render_bierze_animacje_z_biblioteki(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Agent nie potrzebuje pliku od użytkownika — sięga po pozycję z biblioteki serwera."""
    korzen = biblioteka_lottie(tmp_path, monkeypatch)
    podstaw_programy(monkeypatch)
    zapis: list[list[str]] = []

    def efekt(polecenie: list[str]) -> str:
        Image.new("RGB", (16, 16), (10, 20, 30)).save(polecenie[3], format="GIF")
        return ""

    podstaw_przebieg(monkeypatch, zapis, efekt)
    wynik = wywolaj(harness, "render_lottie", animacja="airbnb/check-pop", format_wyniku="gif")

    assert zapis[0][2] == str(korzen / "animacje" / "airbnb" / "check-pop.json")
    assert "check-pop" in wynik.summary


def test_render_odrzuca_wyjscie_poza_biblioteke(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Nazwa animacji idzie do ścieżki na dysku — „..” nie może z niej wyprowadzić."""
    biblioteka_lottie(tmp_path, monkeypatch)
    podstaw_programy(monkeypatch)
    with pytest.raises(ToolError, match="Nieprawidłowa nazwa animacji"):
        wywolaj(harness, "render_lottie", animacja="../../etc/passwd")
    with pytest.raises(ToolError, match="Biblioteka nie ma animacji"):
        wywolaj(harness, "render_lottie", animacja="airbnb/czegotaniema")


def test_render_wymaga_pliku_albo_animacji(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    biblioteka_lottie(tmp_path, monkeypatch)
    podstaw_programy(monkeypatch)
    with pytest.raises(ToolError, match="Podaj plik animacji"):
        wywolaj(harness, "render_lottie")
