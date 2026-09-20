"""Narzędzia korzystające z programów specjalistycznych serwera.

Modele liczą na procesorze minutami, więc testy nie uruchamiają ich na prawdziwych
plikach. Sprawdzają to, co i tak decyduje o poprawności: że narzędzia są w rejestrze,
że odrzucają plik niewłaściwego rodzaju, że brak programu daje komunikat dla człowieka
i że polecenie składa się z właściwych argumentów.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import ToolHarness
from PIL import Image

from nexus.tools.base import ToolError, registry


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object):  # type: ignore[no-untyped-def]
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


NARZEDZIA = ("colorize_photo", "clean_audio", "animate_photo", "split_audio_tracks")


def test_narzedzia_sa_w_rejestrze() -> None:
    assert set(NARZEDZIA) <= set(registry.names())


def test_koloryzacja_odrzuca_plik_ktory_nie_jest_obrazem(harness: ToolHarness, tmp_path: Path) -> None:
    notatka = tmp_path / "notatka.txt"
    notatka.write_text("to nie jest zdjęcie", encoding="utf-8")
    with pytest.raises(ToolError, match="nie jest obrazem"):
        wywolaj(harness, "colorize_photo", file_ids=[harness.add(notatka)])


def test_odszumianie_odrzuca_plik_ktory_nie_jest_nagraniem(harness: ToolHarness, tmp_path: Path) -> None:
    zdjecie = tmp_path / "zdjecie.png"
    Image.new("RGB", (8, 8), (10, 10, 10)).save(zdjecie)
    with pytest.raises(ToolError, match="nie jest nagraniem"):
        wywolaj(harness, "clean_audio", file_id=harness.add(zdjecie))


def test_brak_programu_mowi_po_ludzku(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Gdy programu nie ma, użytkownik dostaje zdanie, a nie ślad wykonania."""
    monkeypatch.setattr("nexus.tools.studio.shutil.which", lambda _nazwa: None)
    zdjecie = tmp_path / "zdjecie.png"
    Image.new("RGB", (8, 8), (10, 10, 10)).save(zdjecie)
    with pytest.raises(ToolError, match="niedostępne na tym serwerze"):
        wywolaj(harness, "colorize_photo", file_ids=[harness.add(zdjecie)])


def test_ozywienie_sklada_polecenie_z_wyborami_uzytkownika(
    harness: ToolHarness, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    """Wybory z rozmowy mają trafić do polecenia, a nie zostać po drodze."""
    zdjecie = tmp_path / "widok.png"
    Image.new("RGB", (16, 16), (60, 60, 60)).save(zdjecie)
    zapis: list[list[str]] = []

    def udawany_bieg(self, arguments, timeout=600, cwd=None, env=None):  # type: ignore[no-untyped-def]
        zapis.append(list(arguments))
        Path(arguments[-1]).write_bytes(b"film")
        return None

    monkeypatch.setattr("nexus.tools.studio.shutil.which", lambda nazwa: f"/udawane/{nazwa}")
    monkeypatch.setattr("nexus.tools.base.ToolContext.run_command", udawany_bieg)
    wynik = wywolaj(
        harness,
        "animate_photo",
        file_id=harness.add(zdjecie),
        czas_s=8,
        ruch="okrag",
        kadr="9:16",
    )
    assert wynik.data["czas_s"] == 8
    polecenie = zapis[0]
    assert polecenie[0].endswith("danaco-ozyw-zdjecie")
    assert polecenie[polecenie.index("--czas") + 1] == "8"
    assert polecenie[polecenie.index("--ruch") + 1] == "okrag"
    assert polecenie[polecenie.index("--format") + 1] == "9:16"


def test_rozdzielenie_zglasza_brak_sciezek(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    nagranie = tmp_path / "utwor.mp3"
    nagranie.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")

    monkeypatch.setattr("nexus.tools.studio.shutil.which", lambda nazwa: f"/udawane/{nazwa}")
    monkeypatch.setattr(
        "nexus.tools.base.ToolContext.run_command",
        lambda self, arguments, timeout=600, cwd=None, env=None: None,
    )
    with pytest.raises(ToolError, match="nie dało żadnej ścieżki"):
        wywolaj(harness, "split_audio_tracks", file_id=harness.add(nagranie))
