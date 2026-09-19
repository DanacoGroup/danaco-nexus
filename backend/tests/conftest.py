"""Wspólne dane testów: syntetyczne skany, kontekst narzędzi, ustawienia."""

from __future__ import annotations

import os
import re
import shutil
import sys
import threading
import uuid
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytest

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from nexus.config import Settings  # noqa: E402
from nexus.ocr.pdf_processor import find_text_layer_font  # noqa: E402
from nexus.storage import guess_mime  # noqa: E402
from nexus.tools.base import FileRef, ToolContext, ToolError  # noqa: E402

SAMPLE_TEXT = (
    "Umowa o świadczenie usług nr 17/2026\n"
    "zawarta w dniu 12 września 2026 r. w Łodzi pomiędzy:\n"
    "Przedsiębiorstwem Handlowym Żuraw Sp. z o.o. z siedzibą w Gdańsku,\n"
    "a firmą Ćma Grzegorz Łęcki, zwaną dalej Wykonawcą.\n"
    "§ 1. Przedmiot umowy\n"
    "Wykonawca zobowiązuje się do przeprowadzenia przeglądu technicznego.\n"
    "Łączne wynagrodzenie wynosi 12 450,00 zł brutto.\n"
    "Zażółć gęślą jaźń, pchnąć w tę łódź jeża lub ośm skrzyń fig.\n"
)
FONT_FILE = str(find_text_layer_font())
HAS_TESSERACT = (
    shutil.which("tesseract") is not None or Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe").is_file()
)

requires_tesseract = pytest.mark.skipif(not HAS_TESSERACT, reason="Brak programu Tesseract")


def requires_program(name: str) -> pytest.MarkDecorator:
    """Pomija test, gdy program narzędziowy nie jest zainstalowany."""
    return pytest.mark.skipif(shutil.which(name) is None, reason=f"Brak programu {name}")


def character_error_rate(expected: str, actual: str) -> float:
    """Współczynnik błędów znakowych (odległość Levenshteina / długość wzorca)."""
    a = re.sub(r"\s+", " ", expected).strip()
    b = re.sub(r"\s+", " ", actual).strip()
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1] / max(len(a), 1)


def render_text_image(
    text: str = SAMPLE_TEXT,
    dpi: int = 300,
    skew: float = 0.0,
    rotate_clockwise: int = 0,
    noise: float = 0.0,
    font_size: float = 12,
) -> np.ndarray:
    """Strona A4 z tekstem jako obraz w skali szarości (symulacja skanu)."""
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        page.insert_font(fontname="doc", fontfile=FONT_FILE)
        page.insert_textbox(
            pymupdf.Rect(60, 70, 540, 800), text, fontname="doc", fontsize=font_size, lineheight=1.6
        )
        pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        image = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width).copy()
    if skew:
        height, width = image.shape
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), skew, 1.0)
        image = cv2.warpAffine(image, matrix, (width, height), borderValue=255)
    if noise:
        generator = np.random.default_rng(7)
        image = np.clip(image + generator.normal(0, noise, image.shape), 0, 255).astype(np.uint8)
    if rotate_clockwise:
        image = np.ascontiguousarray(np.rot90(image, k=-(rotate_clockwise // 90)))
    return image


def write_image(path: Path, image: np.ndarray, quality: int = 92) -> Path:
    """Zapisuje obraz (obsługuje ścieżki ze znakami spoza ASCII)."""
    ok, data = cv2.imencode(path.suffix, image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    assert ok
    path.write_bytes(data.tobytes())
    return path


def write_scanned_pdf(path: Path, images: list[np.ndarray], dpi: int = 300) -> Path:
    """PDF, którego strony zawierają wyłącznie obrazy."""
    with pymupdf.open() as document:
        for image in images:
            ok, encoded = cv2.imencode(".png", image)
            assert ok
            height, width = image.shape[:2]
            page = document.new_page(width=width * 72 / dpi, height=height * 72 / dpi)
            page.insert_image(page.rect, stream=encoded.tobytes())
        document.save(path)
    return path


def write_text_pdf(path: Path, pages: list[str]) -> Path:
    """PDF z widocznym tekstem cyfrowym (jedna pozycja listy = jedna strona)."""
    with pymupdf.open() as document:
        for text in pages:
            page = document.new_page(width=595, height=842)
            page.insert_font(fontname="doc", fontfile=FONT_FILE)
            page.insert_textbox(pymupdf.Rect(60, 60, 540, 800), text, fontname="doc", fontsize=12)
        document.save(path)
    return path


class ToolHarness:
    """Kontekst narzędzi z plikami rejestrowanymi w pamięci (bez bazy danych)."""

    def __init__(self, root: Path) -> None:
        self.settings = Settings(data_dir=root / "data", database_url="sqlite+aiosqlite:///:memory:")
        self.files: dict[uuid.UUID, FileRef] = {}
        self.progress: list[str] = []
        self.indexed: list[uuid.UUID] = []
        self.cancel = threading.Event()

    def add(self, path: Path, name: str | None = None) -> str:
        file_id = uuid.uuid4()
        name = name or path.name
        self.files[file_id] = FileRef(file_id, name, guess_mime(name), path.stat().st_size, path, {})
        return str(file_id)

    def _resolve(self, file_id: uuid.UUID) -> FileRef:
        if file_id not in self.files:
            raise ToolError(f"Plik {file_id} nie istnieje.")
        return self.files[file_id]

    def context(self) -> ToolContext:
        return ToolContext(
            self.settings,
            uuid.uuid4(),
            resolve_file=self._resolve,
            cancel=self.cancel,
            progress=self.progress.append,
            mark_indexed=self.indexed.append,
        )


@pytest.fixture
def harness(tmp_path: Path) -> ToolHarness:
    """Środowisko wykonywania narzędzi."""
    return ToolHarness(tmp_path)


def pytest_configure(config: pytest.Config) -> None:
    os.environ.setdefault("NEXUS_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
