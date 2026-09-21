"""Testy narzędzi agenta wykonywanych bezpośrednio (bez modelu)."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytest
from conftest import (
    SAMPLE_TEXT,
    ToolHarness,
    character_error_rate,
    render_text_image,
    requires_program,
    requires_tesseract,
    write_image,
    write_scanned_pdf,
    write_text_pdf,
)
from docx import Document as DocxDocument

from nexus.tools import registry
from nexus.tools.base import ToolError, ToolResult
from nexus.tools.imaging import analyze_image

NBSP = "\u00a0"


def read_image(path: Path, flags: int = cv2.IMREAD_COLOR) -> np.ndarray:
    return cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), flags)


def call(harness: ToolHarness, tool_name: str, /, **arguments: object) -> ToolResult:
    tool = registry.get(tool_name)
    return tool.handler(harness.context(), tool.parse(arguments))


def test_every_tool_has_valid_definition() -> None:
    definitions = registry.definitions()
    assert len(definitions) >= 20
    for definition in definitions:
        assert definition["description"]
        assert definition["input_schema"]["type"] == "object"
        assert set(definition) == {"name", "description", "input_schema"}
        json.dumps(definition)


def test_invalid_input_is_rejected() -> None:
    with pytest.raises(ToolError, match="Nieprawidłowe parametry"):
        registry.get("pdf_split").parse({"file_id": "x"})
    with pytest.raises(ToolError):
        registry.get("inspect_files").parse({"file_ids": ["a"], "nieznane": 1})


def test_inspect_files_reports_pdf_and_image_quality(harness: ToolHarness, tmp_path: Path) -> None:
    pdf = harness.add(write_scanned_pdf(tmp_path / "skan.pdf", [render_text_image(dpi=100)], dpi=100))
    dark = (render_text_image(dpi=100, skew=3) * 0.3).astype(np.uint8)
    image = harness.add(write_image(tmp_path / "ciemny.jpg", dark))
    result = call(harness, "inspect_files", file_ids=[pdf, image])
    first, second = result.data["files"]
    assert first["kind"] == "pdf" and first["looks_scanned"] is True
    assert second["kind"] == "image"
    assert "obraz niedoświetlony" in second["quality"]["assessment"]
    assert len(result.images) == 2


def test_view_pages_limits_page_count(harness: ToolHarness, tmp_path: Path) -> None:
    pdf = harness.add(write_text_pdf(tmp_path / "a.pdf", [f"Strona {i}" for i in range(1, 10)]))
    result = call(harness, "view_pages", file_id=pdf, pages="1-9", max_side=600)
    assert len(result.images) == 6
    assert result.data["shown_pages"] == [1, 2, 3, 4, 5, 6]


def test_extract_text_from_pdf(harness: ToolHarness, tmp_path: Path) -> None:
    pdf = harness.add(write_text_pdf(tmp_path / "a.pdf", ["Pierwsza strona", "Zażółć gęślą jaźń"]))
    result = call(harness, "extract_text", file_id=pdf, pages="2")
    assert "Zażółć gęślą jaźń" in result.data["text"]
    assert "Pierwsza" not in result.data["text"]


@requires_tesseract
def test_ocr_documents_from_photo_jpeg(harness: ToolHarness, tmp_path: Path) -> None:
    image = harness.add(write_image(tmp_path / "Faktura.jpg", render_text_image(noise=8)))
    result = call(harness, "ocr_documents", file_ids=[image], outputs=["pdf", "txt"], language="pol")
    names = sorted(output.name for output in result.files)
    assert names == ["Faktura_OCR.pdf", "Faktura_OCR.txt"]
    entry = result.data["results"][0]
    assert entry["status"] == "done"
    assert character_error_rate(SAMPLE_TEXT, entry["text"]) < 0.03


def test_enhance_document_scan_straightens_and_cleans(harness: ToolHarness, tmp_path: Path) -> None:
    source = render_text_image(dpi=150, skew=3.0, noise=12)
    shadow = np.tile(np.linspace(0.55, 1.0, source.shape[1]), (source.shape[0], 1))
    image = harness.add(write_image(tmp_path / "zdjecie.png", (source * shadow).astype(np.uint8)))
    result = call(harness, "enhance_document_scan", file_ids=[image], unpaper=False)
    entry = result.data["results"][0]
    assert entry["deskew_degrees"] == pytest.approx(3.0, abs=0.4)
    cleaned = read_image(result.files[0].path, cv2.IMREAD_GRAYSCALE)
    assert np.median(cleaned[:, : cleaned.shape[1] // 5]) > 230


def test_enhance_photo_corrects_color_cast(harness: ToolHarness, tmp_path: Path) -> None:
    generator = np.random.default_rng(3)
    base = generator.integers(60, 200, size=(400, 600, 3), dtype=np.uint8)
    base = cv2.GaussianBlur(base, (0, 0), 6)
    tinted = np.clip(base.astype(np.int16) + np.array([-25, 0, 30]), 0, 255).astype(np.uint8)
    image = harness.add(write_image(tmp_path / "pokoj.jpg", tinted))
    before = analyze_image(tinted)
    result = call(
        harness, "enhance_photo", file_ids=[image], white_balance=1.0, auto_levels=True, sharpen=0.5
    )
    after = analyze_image(read_image(result.files[0].path))
    assert abs(after["color_cast_b"]) < abs(before["color_cast_b"]) / 2
    assert result.files[0].name == "pokoj_poprawione.jpg"


def test_retouch_portrait_produces_image(harness: ToolHarness, tmp_path: Path) -> None:
    skin = np.full((300, 300, 3), (150, 170, 220), np.uint8)
    noisy = np.clip(skin + np.random.default_rng(1).normal(0, 12, skin.shape), 0, 255).astype(np.uint8)
    image = harness.add(write_image(tmp_path / "portret.jpg", noisy))
    result = call(harness, "retouch_portrait", file_ids=[image], skin_smoothing=0.6)
    output = read_image(result.files[0].path)
    assert output.std() < noisy.std()


def test_pdf_split_merge_and_edit(harness: ToolHarness, tmp_path: Path) -> None:
    pdf = harness.add(write_text_pdf(tmp_path / "zbior.pdf", [f"Dokument strona {i}" for i in range(1, 6)]))
    split = call(
        harness,
        "pdf_split",
        file_id=pdf,
        segments=[{"pages": "1-2", "name": "Faktura FV 1/2026"}, {"pages": "3-5", "name": "Umowa.pdf"}],
    )
    assert [output.name for output in split.files] == ["Faktura FV 1_2026.pdf", "Umowa.pdf"]
    ids = [harness.add(output.path) for output in split.files]
    merged = call(harness, "pdf_merge", file_ids=list(reversed(ids)), name="Razem")
    with pymupdf.open(merged.files[0].path) as document:
        assert document.page_count == 5
        assert "strona 3" in document[0].get_text().replace(NBSP, " ")
    edited = call(harness, "pdf_edit_pages", file_id=pdf, keep_pages="5,1", rotate={"1": 90})
    with pymupdf.open(edited.files[0].path) as document:
        texts = [page.get_text().replace(NBSP, " ").strip() for page in document]
        assert texts == ["Dokument strona 5", "Dokument strona 1"]
        assert document[1].rotation == 90


@requires_tesseract
def test_detect_document_boundaries(harness: ToolHarness, tmp_path: Path) -> None:
    pages = [
        "FAKTURA VAT nr 1/2026\nSprzedawca: Żuraw\nStrona 1 z 2",
        "Pozycje faktury ciąg dalszy\nStrona 2 z 2",
        "UMOWA NAJMU LOKALU\nzawarta w Gdańsku\nStrona 1 z 1",
        "WEZWANIE DO ZAPŁATY\nWzywamy do zapłaty kwoty\nStrona 1 z 1",
    ]
    pdf = harness.add(write_text_pdf(tmp_path / "wiele.pdf", pages))
    result = call(harness, "detect_document_boundaries", file_id=pdf)
    assert [segment["pages"] for segment in result.data["suggested_segments"]] == ["1-2", "3", "4"]


def test_archive_roundtrip_and_zip_slip_protection(harness: ToolHarness, tmp_path: Path) -> None:
    a = harness.add(write_text_pdf(tmp_path / "a.pdf", ["A"]))
    b = harness.add(write_text_pdf(tmp_path / "b.pdf", ["B"]))
    archive = call(harness, "create_archive", file_ids=[a, b], name="wyniki")
    with zipfile.ZipFile(archive.files[0].path) as handle:
        assert sorted(handle.namelist()) == ["a.pdf", "b.pdf"]
    evil = tmp_path / "zly.zip"
    with zipfile.ZipFile(evil, "w") as handle:
        handle.writestr("../../etc/passwd", "x")
        handle.writestr("katalog/dobry.txt", "ok")
    extracted = call(harness, "extract_archive", file_id=harness.add(evil))
    assert [output.name for output in extracted.files] == ["katalog - dobry.txt"]


def test_write_document_docx_and_markdown(harness: ToolHarness) -> None:
    content = "# Podsumowanie\n\n- **Strony:** 3\n- Kwota: 12 450 zł\n\nTreść akapitu."
    docx = call(harness, "write_document", name="Raport", format="docx", content=content)
    paragraphs = [p.text for p in DocxDocument(str(docx.files[0].path)).paragraphs]
    assert paragraphs[0] == "Podsumowanie"
    assert "Strony: 3" in paragraphs
    markdown = call(harness, "write_document", name="Notatka", format="md", content=content)
    assert markdown.files[0].path.read_text(encoding="utf-8") == content


def test_convert_images_to_single_pdf(harness: ToolHarness, tmp_path: Path) -> None:
    ids = [harness.add(write_image(tmp_path / f"s{i}.png", render_text_image(dpi=72))) for i in range(3)]
    result = call(harness, "convert_images", file_ids=ids, target_format="pdf", combine_into_one_pdf=True)
    with pymupdf.open(result.files[0].path) as document:
        assert document.page_count == 3


def test_imagemagick_rejects_unsafe_arguments(harness: ToolHarness, tmp_path: Path) -> None:
    image = harness.add(write_image(tmp_path / "a.png", render_text_image(dpi=50)))
    for arguments in (["-write", "/tmp/x.png"], ["@/etc/passwd"], ["msl:/tmp/x"], ["-script", "x"]):
        with pytest.raises(ToolError):
            call(harness, "imagemagick", file_id=image, arguments=arguments)


@requires_program("magick")
def test_imagemagick_runs_allowed_operations(harness: ToolHarness, tmp_path: Path) -> None:
    image = harness.add(write_image(tmp_path / "a.png", render_text_image(dpi=50)))
    result = call(
        harness,
        "imagemagick",
        file_id=image,
        arguments=["-auto-level", "-resize", "50%"],
        output_format="png",
    )
    assert result.files[0].path.stat().st_size > 0


@requires_program("soffice")
def test_convert_documents_docx_to_pdf(harness: ToolHarness) -> None:
    docx = call(harness, "write_document", name="Pismo", format="docx", content="Treść pisma ąęł")
    pdf = call(harness, "convert_documents", file_ids=[harness.add(docx.files[0].path)], target_format="pdf")
    with pymupdf.open(pdf.files[0].path) as document:
        assert "Treść pisma ąęł" in document[0].get_text()


@requires_program("ffmpeg")
def test_media_process_extracts_audio(harness: ToolHarness, tmp_path: Path) -> None:
    import subprocess

    video = tmp_path / "film.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=320x240:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-shortest",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    result = call(harness, "media_process", file_id=harness.add(video), operation="extract_audio")
    assert result.files[0].name == "film_audio.mp3"


@requires_program("unpaper")
def test_scan_cleanup_with_unpaper(harness: ToolHarness, tmp_path: Path) -> None:
    image = harness.add(write_image(tmp_path / "skan.png", render_text_image(dpi=100)))
    result = call(harness, "enhance_document_scan", file_ids=[image], unpaper=True)
    assert result.data["results"][0]["unpaper"] is True


def test_upscale_image_with_realesrgan(harness: ToolHarness, tmp_path: Path) -> None:
    executable = harness.settings.realesrgan_dir / "realesrgan-ncnn-vulkan"
    if not executable.is_file():
        pytest.skip("Brak Real-ESRGAN w środowisku testów")
    small = cv2.resize(render_text_image(dpi=40), (96, 128))
    image = harness.add(write_image(tmp_path / "maly.png", cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)))
    result = call(harness, "upscale_image", file_ids=[image], scale=2, model="anime")
    output = read_image(result.files[0].path)
    assert output.shape[:2] == (256, 192)
    assert result.files[0].name == "maly_x2.png"


def test_diagnostyka_zna_kazdy_program_wywolywany_przez_narzedzia() -> None:
    """Lista programów w `doctor` ma nadążać za narzędziami.

    Narzędzie trafia do rejestru niezależnie od tego, czy jego program jest na ścieżce —
    brak wychodzi dopiero przy wywołaniu, czyli już przy użytkowniku. Tak zniknął cały
    skład dokumentów: `typst` leżał poza `PATH` usług i `typeset_document` odmawiał pracy,
    choć widniał w spisie możliwości.
    """
    import re

    from nexus.doctor import PROGRAMY_NARZEDZI

    katalog = Path(__file__).resolve().parents[1] / "nexus" / "tools"
    wzorzec = re.compile(r'_program\(\s*"([a-z0-9._-]+)"')
    uzywane = {
        nazwa
        for plik in katalog.glob("*.py")
        for nazwa in wzorzec.findall(plik.read_text(encoding="utf-8"))
    }

    brakujace = sorted(uzywane - set(PROGRAMY_NARZEDZI))
    assert brakujace == [], f"dopisz do PROGRAMY_NARZEDZI w doctor.py: {brakujace}"
    zbedne = sorted(set(PROGRAMY_NARZEDZI) - uzywane)
    assert zbedne == [], f"te programy nie są już wywoływane przez narzędzia: {zbedne}"


def _pierwsze_zdanie():
    """Funkcja skracająca opisy z generatora katalogu — ładowana z pliku skryptu."""
    import importlib.util

    sciezka = Path(__file__).resolve().parents[2] / "frontend" / "scripts" / "narzedzia.py"
    spec = importlib.util.spec_from_file_location("narzedzia_skrypt", sciezka)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul.pierwsze_zdanie


def test_opis_narzedzia_nie_urywa_sie_w_pol_mysli() -> None:
    """Opis w katalogu ma być zdaniem, nie ogonem zdania.

    Skrót do pierwszego zdania ciął wcześniej także na dwukropku, a dwukropek zapowiada
    wyliczenie — w katalogu lądowało wtedy „…w zbiorze Iconify (ponad 400 tys. znaków:”
    z otwartym nawiasem i wiszącym dwukropkiem. Nikt tego nie zgłaszał, bo nic się nie psuło:
    po prostu klient czytał zdanie urwane w połowie.
    """
    pierwsze_zdanie = _pierwsze_zdanie()

    assert pierwsze_zdanie("Robi trzy rzeczy: Skanuje, Prostuje, Zapisuje. Drugie.") == (
        "Robi trzy rzeczy: Skanuje, Prostuje, Zapisuje."
    )
    # Koniec zdania nie wypada między otwarciem nawiasu a jego domknięciem.
    assert pierwsze_zdanie("Zdanie z (nawiasem. W środku) i koniec. Następne.") == (
        "Zdanie z (nawiasem. W środku) i koniec."
    )
    assert pierwsze_zdanie("Pierwsze zdanie. Drugie zdanie.") == "Pierwsze zdanie."
    # Skróty zostają skrótami: „(np. DOCX)” nie kończy zdania.
    assert pierwsze_zdanie("Konwertuje pliki (np. DOCX). Drugie.") == "Konwertuje pliki (np. DOCX)."


def test_opisy_w_katalogu_sa_calymi_zdaniami() -> None:
    """Żaden opis w katalogu strony nie kończy się dwukropkiem ani otwartym nawiasem."""
    katalog = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "dane" / "narzedzia.ts").read_text(
        encoding="utf-8"
    )
    opisy = re.findall(r'"opis": "((?:[^"\\]|\\.)*)"', katalog)
    assert len(opisy) > 50, "nie odczytano opisów — zmienił się kształt katalogu"
    urwane = [opis for opis in opisy if opis.rstrip().endswith((":", "(", ",")) or opis.count("(") != opis.count(")")]
    assert urwane == [], f"opisy urwane w pół myśli: {urwane[:5]}"


def test_katalog_narzedzi_strony_zgadza_sie_z_rejestrem() -> None:
    """Strona produktu obiecuje konkretną liczbę narzędzi — ma się zgadzać z rejestrem.

    `frontend/src/dane/narzedzia.ts` powstaje ze skryptu (`frontend/scripts/narzedzia.py`),
    ale nic nie pilnowało, żeby go po dołożeniu narzędzia uruchomić. Liczba `LICZBA_NARZEDZI`
    wchodzi wprost do zdań sprzedażowych („Nexus ma N narzędzi”, „Zobacz wszystkie N”), więc
    rozjazd to nie kosmetyka, tylko nieprawdziwa obietnica na stronie i nagłówek, który nie
    zgadza się z tym, co klient zobaczy po kliknięciu.
    """
    katalog = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "dane" / "narzedzia.ts").read_text(
        encoding="utf-8"
    )
    zadeklarowana = re.search(r"export const LICZBA_NARZEDZI = (\d+);", katalog)
    assert zadeklarowana, "nie znaleziono LICZBA_NARZEDZI — zmienił się kształt katalogu"

    # W pliku „id” mają i narzędzia, i dziedziny — te drugie po prostu nie występują
    # w rejestrze, a sprawdzamy wyłącznie różnicę w stronę rejestru, więc nie przeszkadzają.
    nazwy_strony = set(re.findall(r'"id": "([a-z0-9_]+)"', katalog))
    nazwy_rejestru = set(registry.names())

    brak_na_stronie = sorted(nazwy_rejestru - nazwy_strony)
    assert brak_na_stronie == [], (
        f"narzędzia z rejestru bez wpisu w katalogu strony: {brak_na_stronie} — "
        "uruchom `python frontend/scripts/narzedzia.py`"
    )
    assert int(zadeklarowana.group(1)) == len(nazwy_rejestru), (
        f"strona obiecuje {zadeklarowana.group(1)} narzędzi, rejestr ma {len(nazwy_rejestru)}"
    )
