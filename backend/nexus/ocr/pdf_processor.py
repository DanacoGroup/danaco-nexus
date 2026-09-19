"""Operacje na dokumentach PDF.

Podział odpowiedzialności bibliotek:

* PyMuPDF – analiza istniejącej warstwy tekstowej, renderowanie stron
  i budowa PDF z plików graficznych (bez ponownej kompresji JPEG),
* reportlab – budowa niewidocznej warstwy tekstowej,
* pikepdf – nałożenie warstwy tekstowej na nienaruszone strony oryginału.
"""

from __future__ import annotations

import functools
import io
import logging
import numbers
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pikepdf
import pymupdf
from PIL import Image, ImageOps, ImageSequence
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from nexus.ocr.models import OcrPageResult

logger = logging.getLogger(__name__)

TEXT_LAYER_FONT_NAME = "OcrTextLayer"
MIN_DIGITAL_TEXT_CHARS = 50
LARGE_IMAGE_COVERAGE = 0.6
INVISIBLE_TEXT_TYPE = 3
FONT_CANDIDATES: tuple[Path, ...] = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",
)
FONT_DIRECTORIES: tuple[Path, ...] = (
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path("/danaco/programy/kroje"),
)
FONT_FILE_NAMES: tuple[str, ...] = (
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "Arimo-Regular.ttf",
    "NotoSans-Regular.ttf",
)
EXIF_ROTATION: dict[int, int] = {3: 180, 6: 90, 8: 270}


class PdfProcessingError(Exception):
    """Błąd przetwarzania dokumentu PDF z komunikatem dla użytkownika."""


@dataclass(frozen=True, slots=True)
class PageAnalysis:
    """Wynik analizy strony pod kątem istniejącej warstwy tekstowej."""

    index: int
    needs_ocr: bool
    has_text: bool
    invisible_text_only: bool
    existing_text: str


def open_pdf(path: Path) -> pymupdf.Document:
    """Otwiera PDF w PyMuPDF, zgłaszając czytelne błędy."""
    try:
        document = pymupdf.open(path)
    except (pymupdf.FileDataError, RuntimeError) as error:
        raise PdfProcessingError(f"Plik PDF jest uszkodzony lub nieobsługiwany: {error}") from error
    if document.needs_pass:
        document.close()
        raise PdfProcessingError("PDF jest zabezpieczony hasłem – przetwarzanie niemożliwe.")
    if document.page_count == 0:
        document.close()
        raise PdfProcessingError("PDF nie zawiera żadnej strony.")
    return document


def _image_coverage(page: pymupdf.Page) -> float:
    """Udział powierzchni strony zajętej przez największy obraz."""
    page_area = abs(page.rect)
    if page_area <= 0:
        return 0.0
    best = 0.0
    for info in page.get_image_info():
        bbox = pymupdf.Rect(info["bbox"]) & page.rect
        best = max(best, abs(bbox) / page_area)
    return best


def analyze_page(page: pymupdf.Page, force_ocr: bool) -> PageAnalysis:
    """Ustala, czy strona wymaga OCR.

    Strona z tekstem wyłącznie niewidocznym ma już warstwę OCR – jest
    pomijana, chyba że wymuszono OCR. Strona z widocznym tekstem cyfrowym
    jest pomijana zawsze, z wyjątkiem skanu z niewielką wstawką tekstową
    (np. stopką drukarki), który wymaga OCR.
    """
    text = page.get_text("text")
    char_count = sum(1 for char in text if not char.isspace())
    if char_count == 0:
        return PageAnalysis(page.number, True, False, False, "")
    visible_chars = 0
    for span in page.get_texttrace():
        if span.get("type") != INVISIBLE_TEXT_TYPE and span.get("opacity", 1) > 0:
            visible_chars += len(span.get("chars", ()))
    invisible_only = visible_chars == 0
    if invisible_only:
        return PageAnalysis(page.number, force_ocr, True, True, text)
    is_scan_with_stamp = (
        visible_chars < MIN_DIGITAL_TEXT_CHARS and _image_coverage(page) >= LARGE_IMAGE_COVERAGE
    )
    return PageAnalysis(page.number, is_scan_with_stamp, True, False, text)


def analyze_document(document: pymupdf.Document, force_ocr: bool) -> list[PageAnalysis]:
    """Analizuje wszystkie strony dokumentu."""
    return [analyze_page(page, force_ocr) for page in document]


def render_page_gray(document: pymupdf.Document, index: int, dpi: int) -> np.ndarray:
    """Renderuje stronę (w orientacji wyświetlania) do obrazu w skali szarości."""
    page = document[index]
    pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    array = np.frombuffer(pixmap.samples, dtype=np.uint8)
    return array.reshape(pixmap.height, pixmap.width, pixmap.n)[:, :, 0].copy()


def strip_invisible_text(source: Path, pages: list[int], target: Path) -> None:
    """Usuwa dotychczasową niewidoczną warstwę tekstową ze wskazanych stron."""
    with pymupdf.open(source) as document:
        for index in pages:
            page = document[index]
            page.add_redact_annot(page.rect)
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_NONE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                text=pymupdf.PDF_REDACT_TEXT_REMOVE,
            )
        document.save(target, garbage=1, deflate=True)


def _frame_dpi(frame: Image.Image, default_dpi: int) -> float:
    """Rozdzielczość klatki z metadanych albo wartość domyślna."""
    dpi = frame.info.get("dpi")
    # Pillow podaje rozdzielczość TIFF jako IFDRational (numbers.Real, nie float).
    if isinstance(dpi, tuple) and dpi and isinstance(dpi[0], numbers.Real):
        value = float(dpi[0])
        if 72 <= value <= 2400:
            return value
    return float(default_dpi)


def _encode_frame(frame: Image.Image) -> bytes:
    """Koduje klatkę bezstratnie w formacie obsługiwanym przez PDF."""
    buffer = io.BytesIO()
    if frame.mode == "1":
        frame.save(buffer, format="TIFF", compression="group4")
        return buffer.getvalue()
    if frame.mode not in ("L", "RGB"):
        frame = frame.convert("RGB")
    frame.save(buffer, format="PNG", compress_level=6)
    return buffer.getvalue()


def build_image_container(image_path: Path, target: Path, default_dpi: int) -> list[float]:
    """Tworzy PDF ze stronami zawierającymi obraz(y) pliku graficznego.

    Pliki JPEG są osadzane bez ponownej kompresji, a orientacja EXIF jest
    odwzorowana obrotem strony. Pliki TIFF wielostronicowe dają wiele
    stron. Zwraca rozdzielczość każdej strony (do renderowania 1:1).
    """
    dpis: list[float] = []
    try:
        source_image = Image.open(image_path)
    except (OSError, Image.DecompressionBombError) as error:
        raise PdfProcessingError(f"Nie można odczytać obrazu: {error}") from error
    with source_image, pymupdf.open() as document:
        is_jpeg = source_image.format == "JPEG"
        orientation = source_image.getexif().get(0x0112, 1) if is_jpeg else 1
        for frame in ImageSequence.Iterator(source_image):
            dpi = _frame_dpi(frame, default_dpi)
            page_rotation = 0
            if is_jpeg and orientation in (1, *EXIF_ROTATION):
                data = image_path.read_bytes()
                width, height = frame.size
                page_rotation = EXIF_ROTATION.get(orientation, 0)
            else:
                upright = ImageOps.exif_transpose(frame) if is_jpeg else frame
                data = _encode_frame(upright)
                width, height = upright.size
            page = document.new_page(width=width * 72 / dpi, height=height * 72 / dpi)
            page.insert_image(page.rect, stream=data)
            if page_rotation:
                page.set_rotation(page_rotation)
            dpis.append(dpi)
        if not dpis:
            raise PdfProcessingError("Plik graficzny nie zawiera obrazu.")
        document.save(target, garbage=1, deflate=True)
    return dpis


@functools.lru_cache(maxsize=4)
def find_text_layer_font(preferred: str = "") -> Path:
    """Wyszukuje czcionkę TrueType z polskimi znakami dla warstwy tekstowej.

    Kolejność: wskazany plik, zmienna ``NEXUS_TEXT_LAYER_FONT``, znane ścieżki,
    a następnie przeszukanie katalogów czcionek pod kątem znanych nazw plików.
    """
    for configured in (preferred, os.environ.get("NEXUS_TEXT_LAYER_FONT", "")):
        if configured and Path(configured).is_file():
            return Path(configured)
    for candidate in FONT_CANDIDATES:
        if candidate.is_file():
            return candidate
    for directory in FONT_DIRECTORIES:
        if not directory.is_dir():
            continue
        for root, _, names in os.walk(directory):
            for name in FONT_FILE_NAMES:
                if name in names:
                    return Path(root) / name
    raise PdfProcessingError("Nie znaleziono czcionki TrueType do warstwy tekstowej PDF.")


def _register_font(font_path: Path) -> None:
    """Rejestruje czcionkę warstwy tekstowej w reportlab (jednokrotnie)."""
    if TEXT_LAYER_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(TEXT_LAYER_FONT_NAME, str(font_path)))


class TextLayerWriter:
    """Buduje PDF zawierający wyłącznie niewidoczny tekst, strona po stronie."""

    def __init__(self, target: Path, font_path: Path) -> None:
        _register_font(font_path)
        self._canvas = canvas.Canvas(str(target), pageCompression=1)
        self._canvas.setTitle("OCR text layer")
        ascent, descent = pdfmetrics.getAscentDescent(TEXT_LAYER_FONT_NAME, 1000)
        self._ascent = ascent / 1000
        self._descent = -descent / 1000
        self._pages = 0

    @property
    def page_count(self) -> int:
        """Liczba zapisanych stron warstwy."""
        return self._pages

    def add_page(self, result: OcrPageResult) -> int:
        """Dodaje stronę warstwy; zwraca jej numer (od zera)."""
        pdf = self._canvas
        pdf.setPageSize((result.width, result.height))
        text = pdf.beginText()
        text.setTextRenderMode(3)
        for line in result.lines:
            last = len(line.words) - 1
            for position, word in enumerate(line.words):
                self._place_word(text, word.text, word.quad, result.height, trailing_space=position < last)
        pdf.drawText(text)
        pdf.showPage()
        self._pages += 1
        return self._pages - 1

    def _place_word(
        self, text: object, content: str, quad: tuple, page_height: float, trailing_space: bool
    ) -> None:
        """Umieszcza słowo tak, aby jego zaznaczenie pokrywało obraz słowa."""
        (tlx, tly), (trx, try_), (brx, bry), (blx, bly) = quad
        tl = np.array([tlx, page_height - tly])
        bl = np.array([blx, page_height - bly])
        br = np.array([brx, page_height - bry])
        baseline = br - bl
        width = float(np.hypot(*baseline))
        height = float(np.hypot(*(tl - bl)))
        if width < 0.5 or height < 0.5 or not content:
            return
        font_size = height / (self._ascent + self._descent)
        cos, sin = baseline / width
        up = np.array([-sin, cos])
        origin = bl + up * (self._descent * font_size)
        natural = pdfmetrics.stringWidth(content, TEXT_LAYER_FONT_NAME, font_size)
        if natural <= 0:
            return
        text.setFont(TEXT_LAYER_FONT_NAME, font_size)  # type: ignore[attr-defined]
        text.setHorizScale(100.0 * width / natural)  # type: ignore[attr-defined]
        text.setTextTransform(cos, sin, -sin, cos, origin[0], origin[1])  # type: ignore[attr-defined]
        text.textOut(content + (" " if trailing_space else ""))  # type: ignore[attr-defined]

    def close(self) -> None:
        """Zapisuje plik warstwy."""
        if self._pages == 0:
            self._canvas.setPageSize((72, 72))
            self._canvas.showPage()
        self._canvas.save()


def _inherited(page: pikepdf.Dictionary, key: str) -> object | None:
    """Odczytuje atrybut strony z uwzględnieniem dziedziczenia po węzłach /Pages."""
    node: pikepdf.Dictionary | None = page
    while node is not None:
        if key in node:
            return node[key]
        node = node.get("/Parent")
    return None


def _box(value: object) -> tuple[float, float, float, float]:
    """Normalizuje prostokąt PDF do ``(x0, y0, x1, y1)``."""
    x0, y0, x1, y1 = (float(v) for v in value)  # type: ignore[union-attr]
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def placement_matrix(
    crop: tuple[float, float, float, float], rotation: int, layer_size: tuple[float, float]
) -> tuple[float, ...]:
    """Macierz ``cm`` umieszczająca warstwę (w układzie strony wyświetlanej)
    w nieobróconej przestrzeni strony PDF z atrybutem /Rotate."""
    x0, y0, x1, y1 = crop
    crop_width, crop_height = x1 - x0, y1 - y0
    displayed = (crop_width, crop_height) if rotation in (0, 180) else (crop_height, crop_width)
    sx = displayed[0] / layer_size[0]
    sy = displayed[1] / layer_size[1]
    base = {
        0: (1, 0, 0, 1, x0, y0),
        90: (0, 1, -1, 0, x0 + crop_width, y0),
        180: (-1, 0, 0, -1, x0 + crop_width, y0 + crop_height),
        270: (0, -1, 1, 0, x0, y0 + crop_height),
    }[rotation]
    a, b, c, d, e, f = base
    return (a * sx, b * sx, c * sy, d * sy, e, f)


def _format_number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


@dataclass(frozen=True, slots=True)
class OverlayInstruction:
    """Powiązanie strony dokumentu ze stroną warstwy tekstowej."""

    page_index: int
    layer_page: int
    rotation_delta: int


def apply_text_layer(base: Path, layer: Path, instructions: list[OverlayInstruction], target: Path) -> None:
    """Nakłada strony warstwy tekstowej na strony dokumentu bazowego.

    Treść oryginalnych stron nie jest modyfikowana; warstwa trafia na
    stronę jako Form XObject. Obrót ``rotation_delta`` jest dodawany do
    atrybutu /Rotate, co prostuje stronę bez zmiany jej obrazu.
    """
    with pikepdf.open(base) as document, pikepdf.open(layer) as layer_document:
        for item in instructions:
            page = document.pages[item.page_index]
            page_object = page.obj
            rotation = int(_inherited(page_object, "/Rotate") or 0) % 360
            if item.rotation_delta:
                rotation = (rotation + item.rotation_delta) % 360
                page_object.Rotate = rotation
            crop_value = _inherited(page_object, "/CropBox") or _inherited(page_object, "/MediaBox")
            if crop_value is None:
                raise PdfProcessingError(f"Strona {item.page_index + 1} nie ma atrybutu /MediaBox.")
            layer_page = layer_document.pages[item.layer_page]
            layer_box = _box(layer_page.mediabox)
            layer_size = (layer_box[2] - layer_box[0], layer_box[3] - layer_box[1])
            matrix = placement_matrix(_box(crop_value), rotation, layer_size)
            form = document.copy_foreign(layer_page.as_form_xobject())
            name = page.add_resource(form, pikepdf.Name.XObject, prefix="OcrText")
            operands = " ".join(_format_number(value) for value in matrix)
            page.contents_add(document.make_stream(b"q\n"), prepend=True)
            page.contents_add(document.make_stream(f"\nQ\nq {operands} cm {name} Do Q\n".encode("ascii")))
        document.save(target, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)


def page_size_points(width_px: int, height_px: int, dpi: float) -> tuple[float, float]:
    """Wymiary w punktach PDF dla obrazu o podanej rozdzielczości."""
    return width_px * 72.0 / dpi, height_px * 72.0 / dpi
