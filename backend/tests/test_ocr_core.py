"""Testy rdzenia OCR: przygotowanie obrazu, warstwa tekstowa PDF, silnik Tesseract."""

from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytest
from conftest import SAMPLE_TEXT, character_error_rate, render_text_image, requires_tesseract
from PIL import Image

from nexus.ocr.document_processor import run_ocr
from nexus.ocr.image_processor import (
    ImageProcessor,
    binarize_for_analysis,
    estimate_skew_angle,
    find_content_box,
    map_points,
    rotate_right_angle,
)
from nexus.ocr.models import DocumentStatus, ExportFormat, OcrLine, OcrPageResult, OcrWord
from nexus.ocr.ocr_engine import TesseractOcrEngine, clean_lines
from nexus.ocr.options import OcrOptions, PreprocessingSettings
from nexus.ocr.pdf_processor import (
    OverlayInstruction,
    TextLayerWriter,
    apply_text_layer,
    build_image_container,
    find_text_layer_font,
    placement_matrix,
)


class FixedRotation:
    def __init__(self, degrees: int) -> None:
        self.degrees = degrees

    def detect_rotation(self, image: np.ndarray, dpi: int) -> int:
        return self.degrees


@pytest.mark.parametrize("skew", [-4.0, 2.0, 6.0])
def test_skew_angle_is_estimated(skew: float) -> None:
    image = render_text_image(skew=skew, dpi=150)
    assert estimate_skew_angle(binarize_for_analysis(image)) == pytest.approx(-skew, abs=0.3)


def test_prepare_maps_coordinates_back_to_upright_page() -> None:
    upright = render_text_image(dpi=150)
    cv2.rectangle(upright, (600, 900), (640, 940), 0, -1)
    height, width = upright.shape
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), 3.0, 1.0)
    skewed = cv2.warpAffine(upright, matrix, (width, height), borderValue=255)
    marker = map_points(np.vstack([matrix, [0, 0, 1]]), np.array([[620.0, 920.0]]))
    prepared = ImageProcessor(PreprocessingSettings(), FixedRotation(270), binarize=False).prepare(
        rotate_right_angle(skewed, 90), 150
    )
    count, _, stats, centroids = cv2.connectedComponentsWithStats(binarize_for_analysis(prepared.image))
    square = max(range(1, count), key=lambda label: stats[label][cv2.CC_STAT_AREA])
    assert np.allclose(map_points(prepared.to_upright, centroids[square].reshape(1, 2)), marker, atol=3)


def test_scanner_edges_do_not_extend_content_box() -> None:
    page = np.full((1000, 800), 255, np.uint8)
    page[:, :25] = 0
    page[300:340, 200:600] = 0
    assert find_content_box(binarize_for_analysis(page), margin=10) == (190, 290, 610, 350)


def test_clean_lines_drops_garbage() -> None:
    def word(text: str, confidence: float) -> OcrWord:
        return OcrWord(text, ((0, 0), (10, 0), (10, 10), (0, 10)), confidence)

    lines = [OcrLine([word("Umowa", 0.98), word("|", 0.99), word("~~", 0.4)], 0.8)]
    assert [line.text for line in clean_lines(lines, 0.5)] == ["Umowa"]


def test_tiff_resolution_is_read(tmp_path: Path) -> None:
    frames = [Image.fromarray(render_text_image(dpi=72)).convert("1") for _ in range(2)]
    source = tmp_path / "skan.tif"
    frames[0].save(source, save_all=True, append_images=frames[1:], compression="group4", dpi=(72, 72))
    assert build_image_container(source, tmp_path / "out.pdf", 300) == [72.0, 72.0]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_placement_matrix_maps_corners(rotation: int) -> None:
    crop = (10.0, 20.0, 610.0, 820.0)
    displayed = (600.0, 800.0) if rotation in (0, 180) else (800.0, 600.0)
    a, b, c, d, e, f = placement_matrix(crop, rotation, displayed)
    corners = [(0, 0), (displayed[0], 0), (0, displayed[1]), displayed]
    mapped = {(round(a * x + c * y + e), round(b * x + d * y + f)) for x, y in corners}
    assert mapped == {(10, 20), (610, 20), (10, 820), (610, 820)}


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_text_layer_is_searchable_on_rotated_pages(tmp_path: Path, rotation: int) -> None:
    base = tmp_path / "base.pdf"
    with pymupdf.open() as document:
        page = document.new_page(width=400, height=500)
        buffer = io.BytesIO()
        Image.fromarray(np.full((500, 400), 230, np.uint8)).save(buffer, format="PNG")
        page.insert_image(page.rect, stream=buffer.getvalue())
        page.set_rotation(rotation)
        width, height = page.rect.width, page.rect.height
        document.save(base)
    words = [
        OcrWord("Zażółć", ((72, 100), (150, 100), (150, 114), (72, 114)), 0.99),
        OcrWord("gęślą", ((156, 100), (210, 100), (210, 114), (156, 114)), 0.99),
    ]
    layer = tmp_path / "layer.pdf"
    writer = TextLayerWriter(layer, find_text_layer_font())
    writer.add_page(OcrPageResult(0, width, height, 0, 0.0, [OcrLine(words, 0.99)]))
    writer.close()
    output = tmp_path / "wynik.pdf"
    apply_text_layer(base, layer, [OverlayInstruction(0, 0, 0)], output)
    with pymupdf.open(output) as document:
        page = document[0]
        assert page.get_text().split() == ["Zażółć", "gęślą"]
        found = page.search_for("gęślą")[0] * page.rotation_matrix
        assert found.x0 == pytest.approx(156, abs=2)
        assert found.x1 == pytest.approx(210, abs=2)


@requires_tesseract
@pytest.mark.parametrize("rotation, expected", [(0, 0), (90, 270), (180, 180)])
def test_tesseract_orientation(rotation: int, expected: int) -> None:
    engine = TesseractOcrEngine(OcrOptions(language="pol"))
    assert engine.detect_rotation(render_text_image(rotate_clockwise=rotation), 300) == expected


@requires_tesseract
def test_ocr_pipeline_creates_searchable_pdf_txt_docx(tmp_path: Path) -> None:
    source = tmp_path / "skan.pdf"
    with pymupdf.open() as document:
        for image in (render_text_image(skew=2.5, noise=10), render_text_image(rotate_clockwise=90)):
            ok, data = cv2.imencode(".png", image)
            height, width = image.shape
            page = document.new_page(width=width * 72 / 300, height=height * 72 / 300)
            page.insert_image(page.rect, stream=data.tobytes())
        document.save(source)
    targets = {fmt: tmp_path / f"wynik.{fmt.value}" for fmt in ExportFormat}
    result = run_ocr(source, False, targets, OcrOptions(language="pol", threads=4))
    assert result.status is DocumentStatus.DONE, result.message
    with pymupdf.open(targets[ExportFormat.PDF]) as document:
        assert document[1].rotation == 270
        for page in document:
            assert len(page.get_images()) == 1
            assert character_error_rate(SAMPLE_TEXT, page.get_text()) < 0.03
    assert "Strona 2" in targets[ExportFormat.TXT].read_text(encoding="utf-8")
    assert targets[ExportFormat.DOCX].stat().st_size > 5000
