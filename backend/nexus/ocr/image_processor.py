"""Wstępne przetwarzanie obrazu strony przed OCR.

Obróbka dotyczy wyłącznie obrazu przekazywanego do OCR; wygląd strony
w pliku wynikowym pozostaje oryginalny. Każda operacja geometryczna
(obrót, prostowanie, kadrowanie) jest zapisywana w macierzy przekształcenia,
dzięki której współrzędne tekstu wracają do układu strony.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np

from nexus.ocr.options import PreprocessingSettings

logger = logging.getLogger(__name__)

ANALYSIS_WIDTH = 1200
MAX_SKEW_DEGREES = 10.0
MIN_SKEW_DEGREES = 0.2
NOISE_SIGMA_THRESHOLD = 4.0


class OrientationDetector(Protocol):
    """Wykrywanie orientacji strony (0, 90, 180, 270 stopni)."""

    def detect_rotation(self, image: np.ndarray, dpi: int) -> int:
        """Zwraca kąt obrotu zgodnie z ruchem wskazówek zegara prostujący stronę."""
        ...


@dataclass(frozen=True, slots=True)
class PreparedImage:
    """Obraz gotowy do OCR wraz z danymi do odwzorowania współrzędnych.

    ``to_upright`` to macierz 3x3 przekształcająca piksele obrazu OCR
    na piksele strony wyprostowanej (po obrocie o ``rotation``).
    """

    image: np.ndarray
    to_upright: np.ndarray
    rotation: int
    skew_angle: float
    upright_size: tuple[int, int]


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Konwertuje obraz RGB, RGBA lub szary do skali szarości."""
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)


def rotate_right_angle(image: np.ndarray, degrees_clockwise: int) -> np.ndarray:
    """Obraca obraz o wielokrotność 90 stopni zgodnie z ruchem wskazówek zegara."""
    codes = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }
    code = codes.get(degrees_clockwise % 360)
    return image if code is None else cv2.rotate(image, code)


def binarize_for_analysis(gray: np.ndarray) -> np.ndarray:
    """Zwraca maskę atramentu (tekst = 255) metodą Otsu."""
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return mask


def estimate_noise_sigma(gray: np.ndarray) -> float:
    """Szacuje odchylenie standardowe szumu metodą Immerkæra."""
    height, width = gray.shape
    if height < 3 or width < 3:
        return 0.0
    crop = gray[: min(height, 1024), : min(width, 1024)].astype(np.float32)
    kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float32)
    response = np.abs(cv2.filter2D(crop, -1, kernel))[1:-1, 1:-1]
    rows, cols = response.shape
    return float(response.sum() * math.sqrt(math.pi / 2) / (6 * rows * cols))


def estimate_skew_angle(ink_mask: np.ndarray) -> float:
    """Wyznacza kąt pochylenia tekstu metodą profilu projekcji.

    Zwraca kąt w stopniach (przeciwnie do ruchu wskazówek zegara),
    o który należy obrócić obraz, aby wiersze tekstu były poziome.
    """
    height, width = ink_mask.shape
    scale = min(1.0, ANALYSIS_WIDTH / max(width, 1))
    small = cv2.resize(ink_mask, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if np.count_nonzero(small) < 0.002 * small.size:
        return 0.0
    center = (small.shape[1] / 2, small.shape[0] / 2)

    def score(angle: float) -> float:
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            small, matrix, (small.shape[1], small.shape[0]), flags=cv2.INTER_NEAREST, borderValue=0
        )
        profile = rotated.sum(axis=1, dtype=np.float64)
        return float(np.sum(np.diff(profile) ** 2))

    coarse = np.arange(-MAX_SKEW_DEGREES, MAX_SKEW_DEGREES + 0.01, 0.5)
    best = max(coarse, key=score)
    fine = np.arange(best - 0.5, best + 0.501, 0.05)
    best = max(fine, key=score)
    return float(round(best, 2))


def find_content_box(ink_mask: np.ndarray, margin: int) -> tuple[int, int, int, int] | None:
    """Wyznacza prostokąt treści, pomijając ciemne krawędzie skanu i drobny szum.

    Zwraca ``(x0, y0, x1, y1)`` albo ``None``, gdy strona jest pusta.
    """
    height, width = ink_mask.shape
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink_mask, connectivity=8)
    min_area = max(4, int(height * width * 2e-6))
    keep = np.zeros(count, dtype=bool)
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        touches_edge = x == 0 or y == 0 or x + w >= width or y + h >= height
        is_scanner_edge = touches_edge and (w > 0.3 * width or h > 0.3 * height)
        keep[label] = area >= min_area and not is_scanner_edge
    if not keep.any():
        return None
    boxes = stats[keep]
    x0 = int(boxes[:, cv2.CC_STAT_LEFT].min())
    y0 = int(boxes[:, cv2.CC_STAT_TOP].min())
    x1 = int((boxes[:, cv2.CC_STAT_LEFT] + boxes[:, cv2.CC_STAT_WIDTH]).max())
    y1 = int((boxes[:, cv2.CC_STAT_TOP] + boxes[:, cv2.CC_STAT_HEIGHT]).max())
    return (max(0, x0 - margin), max(0, y0 - margin), min(width, x1 + margin), min(height, y1 + margin))


def remove_scanner_edges(gray: np.ndarray, ink_mask: np.ndarray) -> np.ndarray:
    """Wybiela ciemne pasy przy krawędziach skanu, źródło błędnych znaków OCR."""
    height, width = ink_mask.shape
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink_mask, connectivity=8)
    result = gray
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        touches_edge = x == 0 or y == 0 or x + w >= width or y + h >= height
        long_band = w > 0.3 * width or h > 0.3 * height
        dense = area > 0.5 * w * h or min(w, h) < 0.02 * max(width, height)
        if touches_edge and long_band and dense:
            if result is gray:
                result = gray.copy()
            result[labels == label] = 255
    return result


def normalize_background(gray: np.ndarray) -> np.ndarray:
    """Wyrównuje oświetlenie i podnosi kontrast tekstu względem tła."""
    height, width = gray.shape
    small = cv2.resize(gray, (max(1, width // 4), max(1, height // 4)), interpolation=cv2.INTER_AREA)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    background = cv2.dilate(small, kernel)
    background = cv2.medianBlur(background, 21 if min(background.shape) > 21 else 3)
    background = cv2.resize(background, (width, height), interpolation=cv2.INTER_LINEAR)
    normalized = cv2.divide(gray, np.maximum(background, 1), scale=255)
    low = float(np.percentile(normalized, 0.5))
    if low >= 250:
        return normalized
    stretched = (normalized.astype(np.float32) - low) * (255.0 / (255.0 - low))
    return np.clip(stretched, 0, 255).astype(np.uint8)


def adaptive_threshold(gray: np.ndarray, dpi: int) -> np.ndarray:
    """Progowanie adaptacyjne z oknem dopasowanym do rozdzielczości."""
    block = max(15, int(dpi / 10)) | 1
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 12)


def _translation(dx: float, dy: float) -> np.ndarray:
    return np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1]], dtype=np.float64)


class ImageProcessor:
    """Przygotowuje obraz strony do OCR zgodnie z ustawieniami."""

    def __init__(
        self,
        settings: PreprocessingSettings,
        orientation_detector: OrientationDetector | None = None,
        binarize: bool = False,
    ) -> None:
        """Tworzy procesor.

        ``binarize`` włącza progowanie adaptacyjne obrazu dla OCR
        (w trybie ``auto`` decyduje o tym wybrany silnik).
        """
        self._settings = settings
        self._orientation = orientation_detector
        mode = settings.adaptive_threshold
        self._binarize = mode == "always" or (mode == "auto" and binarize)

    def prepare(self, image: np.ndarray, dpi: int) -> PreparedImage:
        """Wykonuje pełne przygotowanie obrazu strony."""
        rotation = 0
        if self._settings.rotation_detection and self._orientation is not None:
            rotation = self._orientation.detect_rotation(image, dpi) % 360
        gray = rotate_right_angle(to_grayscale(image), rotation)
        upright_height, upright_width = gray.shape
        forward = np.eye(3)

        if self._settings.denoise:
            sigma = estimate_noise_sigma(gray)
            if sigma > NOISE_SIGMA_THRESHOLD:
                strength = float(min(sigma * 1.2, 25.0))
                gray = cv2.fastNlMeansDenoising(
                    gray, None, h=strength, templateWindowSize=7, searchWindowSize=21
                )

        if self._settings.contrast_enhancement:
            gray = normalize_background(gray)

        skew = 0.0
        if self._settings.deskew:
            skew = estimate_skew_angle(binarize_for_analysis(gray))
            if abs(skew) >= MIN_SKEW_DEGREES:
                gray, matrix = self._rotate_expanded(gray, skew)
                forward = matrix @ forward
            else:
                skew = 0.0

        if self._settings.border_crop:
            ink = binarize_for_analysis(gray)
            gray = remove_scanner_edges(gray, ink)
            margin = max(10, dpi // 10)
            box = find_content_box(ink, margin)
            if box is not None:
                x0, y0, x1, y1 = box
                gray = gray[y0:y1, x0:x1]
                forward = _translation(-x0, -y0) @ forward

        if self._binarize:
            gray = adaptive_threshold(gray, dpi)

        return PreparedImage(
            image=np.ascontiguousarray(gray),
            to_upright=np.linalg.inv(forward),
            rotation=rotation,
            skew_angle=skew,
            upright_size=(upright_width, upright_height),
        )

    @staticmethod
    def _rotate_expanded(gray: np.ndarray, angle: float) -> tuple[np.ndarray, np.ndarray]:
        """Obraca obraz o dowolny kąt, powiększając płótno, aby nie uciąć treści."""
        height, width = gray.shape
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
        new_width = int(math.ceil(height * sin + width * cos))
        new_height = int(math.ceil(height * cos + width * sin))
        matrix[0, 2] += new_width / 2 - width / 2
        matrix[1, 2] += new_height / 2 - height / 2
        rotated = cv2.warpAffine(
            gray, matrix, (new_width, new_height), flags=cv2.INTER_CUBIC, borderValue=255
        )
        return rotated, np.vstack([matrix, [0, 0, 1]])


def map_points(matrix: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Przekształca tablicę punktów ``(n, 2)`` macierzą jednorodną 3x3."""
    homogeneous = np.hstack([points, np.ones((points.shape[0], 1))])
    mapped = homogeneous @ matrix.T
    return mapped[:, :2]
