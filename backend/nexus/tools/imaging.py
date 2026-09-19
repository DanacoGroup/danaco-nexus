"""Analiza i korekcja obrazów (OpenCV): metryki jakości, kolory, ekspozycja,
ostrość, perspektywa, wygładzanie skóry.

Funkcje operują na obrazach BGR ``uint8`` i nie mają efektów ubocznych.
"""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

from nexus.ocr.image_processor import (
    binarize_for_analysis,
    estimate_noise_sigma,
    estimate_skew_angle,
)

ANALYSIS_SIDE = 1600


def pil_to_bgr(image: Any) -> np.ndarray:
    """Konwersja obrazu Pillow do BGR ``uint8``."""
    rgb = image.convert("RGB")
    return cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)


def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    """Konwersja BGR → RGB."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _downscale(image: np.ndarray, side: int = ANALYSIS_SIDE) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(1.0, side / max(height, width))
    if scale >= 1.0:
        return image
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def analyze_image(image: np.ndarray) -> dict[str, Any]:
    """Metryki jakości obrazu przydatne do doboru korekt.

    Zwraca m.in. jasność, kontrast, przepalenia i niedoświetlenia, ostrość
    (wariancja Laplasjanu), poziom szumu, zafarb kolorystyczny (Lab)
    oraz dla dokumentów udział tła i pochylenie tekstu.
    """
    small = _downscale(image)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    luminance = gray.astype(np.float32)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    bright_background = float(np.mean(gray > 200))
    ink = binarize_for_analysis(gray)
    ink_ratio = float(np.count_nonzero(ink) / ink.size)
    document_like = bright_background > 0.55 and 0.01 < ink_ratio < 0.35
    saturation = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)[:, :, 1]
    metrics: dict[str, Any] = {
        "brightness_mean": round(float(luminance.mean()), 1),
        "brightness_median": round(float(np.median(luminance)), 1),
        "contrast_std": round(float(luminance.std()), 1),
        "shadows_clipped_pct": round(100 * float(np.mean(gray <= 3)), 2),
        "highlights_clipped_pct": round(100 * float(np.mean(gray >= 252)), 2),
        "sharpness_laplacian_var": round(sharpness, 1),
        "noise_sigma": round(estimate_noise_sigma(gray), 2),
        "color_cast_a": round(float(lab[:, :, 1].mean() - 128), 2),
        "color_cast_b": round(float(lab[:, :, 2].mean() - 128), 2),
        "saturation_mean": round(float(saturation.mean()), 1),
        "document_like": bool(document_like),
    }
    if document_like:
        metrics["text_skew_degrees"] = round(-estimate_skew_angle(ink), 2)
    metrics["assessment"] = _assessment(metrics)
    return metrics


def _assessment(metrics: dict[str, Any]) -> list[str]:
    """Słowne wnioski z metryk (pomocnicze dla modelu)."""
    notes = []
    if metrics["brightness_median"] < 85:
        notes.append("obraz niedoświetlony")
    elif metrics["brightness_median"] > 200 and not metrics["document_like"]:
        notes.append("obraz prześwietlony")
    if metrics["contrast_std"] < 35:
        notes.append("niski kontrast")
    if metrics["highlights_clipped_pct"] > 3:
        notes.append("przepalone światła")
    if metrics["sharpness_laplacian_var"] < 60:
        notes.append("obraz nieostry lub rozmyty")
    if metrics["noise_sigma"] > 6:
        notes.append("wyraźny szum")
    if abs(metrics["color_cast_a"]) > 6 or abs(metrics["color_cast_b"]) > 8:
        notes.append("zafarb kolorystyczny (balans bieli)")
    if metrics.get("text_skew_degrees") and abs(metrics["text_skew_degrees"]) > 0.4:
        notes.append("przekrzywiony tekst")
    return notes or ["brak wyraźnych problemów"]


def white_balance(image: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """Balans bieli: wyrównanie średnich a/b w Lab do neutralnej szarości."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    luminance = lab[:, :, 0] / 255.0
    for channel in (1, 2):
        shift = lab[:, :, channel].mean() - 128.0
        lab[:, :, channel] -= strength * shift * (0.5 + 0.5 * luminance)
    return cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def auto_levels(image: np.ndarray, clip_percent: float = 0.5) -> np.ndarray:
    """Rozciągnięcie zakresu jasności z odcięciem skrajnych percentyli."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    luminance = lab[:, :, 0].astype(np.float32)
    low, high = np.percentile(luminance, (clip_percent, 100 - clip_percent))
    if high - low < 10:
        return image
    lab[:, :, 0] = np.clip((luminance - low) * 255.0 / (high - low), 0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def adjust_exposure(image: np.ndarray, stops: float) -> np.ndarray:
    """Zmiana ekspozycji o ``stops`` EV krzywą gamma chroniącą światła."""
    if abs(stops) < 1e-3:
        return image
    gamma = 2.0 ** (-stops * 0.6)
    table = np.array([((value / 255.0) ** gamma) * 255 for value in range(256)], dtype=np.uint8)
    return cv2.LUT(image, table)


def auto_exposure(image: np.ndarray, target_median: float = 118.0) -> np.ndarray:
    """Automatyczna korekta ekspozycji do docelowej mediany jasności."""
    gray = cv2.cvtColor(_downscale(image), cv2.COLOR_BGR2GRAY)
    median = max(float(np.median(gray)), 1.0)
    gamma = math.log(target_median / 255.0) / math.log(median / 255.0) if 0 < median < 255 else 1.0
    gamma = float(np.clip(gamma, 0.55, 1.8))
    table = np.array([((value / 255.0) ** gamma) * 255 for value in range(256)], dtype=np.uint8)
    return cv2.LUT(image, table)


def shadows_highlights(image: np.ndarray, shadows: float, highlights: float) -> np.ndarray:
    """Rozjaśnienie cieni i przyciemnienie świateł (wartości 0–1)."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    luminance = lab[:, :, 0] / 255.0
    blurred = cv2.GaussianBlur(luminance, (0, 0), sigmaX=max(image.shape[:2]) / 60)
    lift = shadows * 0.35 * (1.0 - blurred) ** 2
    cut = highlights * 0.30 * blurred**2
    lab[:, :, 0] = np.clip((luminance + lift - cut) * 255.0, 0, 255)
    return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)


def local_contrast(image: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """Kontrast lokalny (CLAHE na kanale jasności)."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=1.0 + 1.5 * strength, tileGridSize=(8, 8))
    enhanced = clahe.apply(lab[:, :, 0])
    lab[:, :, 0] = cv2.addWeighted(enhanced, min(strength, 1.0), lab[:, :, 0], 1 - min(strength, 1.0), 0)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def adjust_saturation(image: np.ndarray, factor: float) -> np.ndarray:
    """Nasycenie z ochroną kolorów już nasyconych (vibrance)."""
    if abs(factor - 1.0) < 1e-3:
        return image
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
    saturation = hsv[:, :, 1] / 255.0
    weight = 1.0 - saturation if factor > 1 else 1.0
    hsv[:, :, 1] = np.clip(255.0 * saturation * (1 + (factor - 1) * weight), 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def sharpen(image: np.ndarray, amount: float = 0.8, radius: float = 1.2) -> np.ndarray:
    """Maska wyostrzająca na kanale jasności (bez przebarwień)."""
    if amount <= 0:
        return image
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    luminance = lab[:, :, 0]
    blurred = cv2.GaussianBlur(luminance, (0, 0), radius)
    lab[:, :, 0] = cv2.addWeighted(luminance, 1 + amount, blurred, -amount, 0)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def denoise(image: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """Odszumianie nielokalnymi średnimi, siła dopasowana do zmierzonego szumu."""
    gray = cv2.cvtColor(_downscale(image, 1024), cv2.COLOR_BGR2GRAY)
    sigma = max(estimate_noise_sigma(gray), 2.0)
    h = float(np.clip(sigma * 0.9 * strength, 2, 15))
    return cv2.fastNlMeansDenoisingColored(image, None, h, h * 0.8, 7, 21)


def straighten_verticals(image: np.ndarray, keystone: bool = True) -> tuple[np.ndarray, dict[str, float]]:
    """Prostuje pionowe linie (architektura, wnętrza): obrót i korekta zbieżności.

    Kąty wyznaczane są z odcinków Hougha bliskich pionowi. Zwraca obraz
    i zastosowane parametry.
    """
    small = _downscale(image, 1200)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    min_length = small.shape[0] // 8
    segments = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=60, minLineLength=min_length, maxLineGap=10)
    if segments is None:
        return image, {"rotation": 0.0, "keystone": 0.0}
    tilts: list[tuple[float, float, float]] = []
    for x1, y1, x2, y2 in segments[:, 0]:
        dx, dy = float(x2 - x1), float(y2 - y1)
        if abs(dy) < 1:
            continue
        angle = math.degrees(math.atan2(dx, dy))
        angle = angle - 180 if angle > 90 else angle + 180 if angle < -90 else angle
        if abs(angle) < 12:
            length = math.hypot(dx, dy)
            tilts.append((angle, (x1 + x2) / 2 / small.shape[1], length))
    if len(tilts) < 3:
        return image, {"rotation": 0.0, "keystone": 0.0}
    angles = np.array([t[0] for t in tilts])
    weights = np.array([t[2] for t in tilts])
    rotation = float(np.average(angles, weights=weights))
    height, width = image.shape[:2]
    result = image
    if abs(rotation) > 0.15:
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), -rotation, 1.0)
        result = cv2.warpAffine(
            image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT
        )
    keystone_degrees = 0.0
    if keystone:
        positions = np.array([t[1] for t in tilts])
        left = angles[positions < 0.4] - rotation
        right = angles[positions > 0.6] - rotation
        if len(left) >= 2 and len(right) >= 2:
            keystone_degrees = float((np.median(left) - np.median(right)) / 2)
            if 0.3 < abs(keystone_degrees) < 8:
                offset = math.tan(math.radians(abs(keystone_degrees))) * height
                offset = min(offset, width * 0.12)
                if keystone_degrees > 0:
                    source = np.float32([[offset, 0], [width - offset, 0], [width, height], [0, height]])
                else:
                    source = np.float32([[0, 0], [width, 0], [width - offset, height], [offset, height]])
                target = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
                transform = cv2.getPerspectiveTransform(source, target)
                result = cv2.warpPerspective(
                    result, transform, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT
                )
            else:
                keystone_degrees = 0.0
    return result, {"rotation": round(rotation, 2), "keystone": round(keystone_degrees, 2)}


def find_document_quad(image: np.ndarray) -> np.ndarray | None:
    """Czworokąt dokumentu sfotografowanego na tle (lub ``None``)."""
    small = _downscale(image, 1000)
    scale = image.shape[1] / small.shape[1]
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 40, 120), np.ones((3, 3), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_total = small.shape[0] * small.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        area = cv2.contourArea(contour)
        if area < 0.2 * area_total or area > 0.98 * area_total:
            continue
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return approx.reshape(4, 2).astype(np.float32) * scale
    return None


def warp_document(image: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """Prostuje perspektywę dokumentu do prostokąta."""
    total = quad.sum(axis=1)
    diff = np.diff(quad, axis=1).ravel()
    ordered = np.float32(
        [quad[np.argmin(total)], quad[np.argmin(diff)], quad[np.argmax(total)], quad[np.argmax(diff)]]
    )
    width = int(max(np.linalg.norm(ordered[0] - ordered[1]), np.linalg.norm(ordered[3] - ordered[2])))
    height = int(max(np.linalg.norm(ordered[0] - ordered[3]), np.linalg.norm(ordered[1] - ordered[2])))
    target = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    transform = cv2.getPerspectiveTransform(ordered, target)
    return cv2.warpPerspective(image, transform, (width, height), flags=cv2.INTER_CUBIC)


def skin_mask(image: np.ndarray) -> np.ndarray:
    """Miękka maska odcieni skóry (YCrCb), wartości 0–1."""
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    mask = cv2.inRange(ycrcb, (0, 135, 85), (255, 180, 135)).astype(np.float32) / 255.0
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    return cv2.GaussianBlur(mask, (0, 0), sigmaX=max(image.shape[:2]) / 300 + 2)


def smooth_skin(image: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """Naturalne wygładzenie skóry z zachowaniem krawędzi i tekstury."""
    strength = float(np.clip(strength, 0.0, 1.0))
    if strength == 0:
        return image
    diameter = max(5, int(max(image.shape[:2]) / 250) | 1)
    smoothed = cv2.bilateralFilter(image, diameter, 30 + 40 * strength, diameter * 2)
    detail = cv2.subtract(image, cv2.GaussianBlur(image, (0, 0), 1.2))
    smoothed = cv2.add(smoothed, (detail * 0.35).astype(np.uint8))
    mask = skin_mask(image)[:, :, None] * (0.35 + 0.5 * strength)
    blended = image.astype(np.float32) * (1 - mask) + smoothed.astype(np.float32) * mask
    return np.clip(blended, 0, 255).astype(np.uint8)


def warm_tone(image: np.ndarray, amount: float) -> np.ndarray:
    """Delikatne ocieplenie (dodatnie) lub ochłodzenie (ujemne) tonacji."""
    if abs(amount) < 1e-3:
        return image
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[:, :, 2] += 6.0 * amount
    lab[:, :, 1] += 1.5 * amount
    return cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
