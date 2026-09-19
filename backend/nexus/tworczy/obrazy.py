"""Obróbka obrazów modułu Obrazy: wycinanie tła (rembg), nowe tło, gumka (inpainting).

Funkcje działają na obrazach Pillow; kompozycja tła korzysta z kanału alfa wycinka
(maski obiektu), a gumka – z maski narysowanej przez użytkownika (biel = usuń).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image, ImageFilter

BackgroundMode = Literal["transparent", "color", "gradient", "image", "blur"]
HEX_COLOR = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
INPAINT_WORK_SIDE = 640


class ImageOpError(ValueError):
    """Nieprawidłowe parametry obróbki obrazu."""


def parse_color(value: str) -> tuple[int, int, int, int]:
    """Kolor ``#rgb``, ``#rrggbb`` lub ``#rrggbbaa`` jako RGBA."""
    match = HEX_COLOR.fullmatch((value or "").strip())
    if not match:
        raise ImageOpError(f"Nieprawidłowy kolor: {value!r} (oczekiwano np. #ffffff).")
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(char * 2 for char in digits)
    if len(digits) == 6:
        digits += "ff"
    return tuple(int(digits[index : index + 2], 16) for index in range(0, 8, 2))  # type: ignore[return-value]


def cover_fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Skaluje obraz tak, by wypełnił ``size`` (bez zniekształceń), i przycina środek."""
    width, height = size
    scale = max(width / image.width, height / image.height)
    resized = image.resize(
        (max(width, round(image.width * scale)), max(height, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def linear_gradient(
    size: tuple[int, int], start: tuple[int, int, int, int], end: tuple[int, int, int, int], angle: float
) -> Image.Image:
    """Gradient liniowy RGBA; kąt w stopniach (0 = z lewej do prawej, 90 = z góry na dół)."""
    width, height = size
    radians = np.deg2rad(angle)
    direction = np.array([np.cos(radians), np.sin(radians)])
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    projection = (xs - width / 2) * direction[0] + (ys - height / 2) * direction[1]
    extent = abs(width / 2 * direction[0]) + abs(height / 2 * direction[1]) or 1.0
    t = np.clip((projection / extent + 1) / 2, 0, 1)[..., None]
    pixels = np.array(start, np.float32) * (1 - t) + np.array(end, np.float32) * t
    return Image.fromarray(np.round(pixels).astype(np.uint8), "RGBA")


def _subject_free_background(original: Image.Image, alpha: np.ndarray) -> Image.Image:
    """Tło bez obiektu: obszar obiektu wypełniony inpaintingiem (mniej poświaty po rozmyciu)."""
    rgb = np.asarray(original.convert("RGB"))
    height, width = alpha.shape
    scale = min(1.0, INPAINT_WORK_SIDE / max(width, height))
    small_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    small = cv2.resize(rgb, small_size, interpolation=cv2.INTER_AREA)
    mask = cv2.resize((alpha > 32).astype(np.uint8) * 255, small_size, interpolation=cv2.INTER_NEAREST)
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=2)
    filled = cv2.inpaint(small, mask, 7, cv2.INPAINT_TELEA)
    return Image.fromarray(cv2.resize(filled, (width, height), interpolation=cv2.INTER_CUBIC), "RGB")


def compose_background(
    cutout: Image.Image,
    mode: BackgroundMode,
    *,
    color: str = "#ffffff",
    color2: str = "#e4e4e7",
    angle: float = 90.0,
    background: Image.Image | None = None,
    original: Image.Image | None = None,
    blur_radius: float = 18.0,
) -> Image.Image:
    """Nakłada wycinek (RGBA z maską obiektu w kanale alfa) na nowe tło."""
    cutout = cutout.convert("RGBA")
    size = cutout.size
    if mode == "transparent":
        return cutout
    if mode == "color":
        base = Image.new("RGBA", size, parse_color(color))
    elif mode == "gradient":
        base = linear_gradient(size, parse_color(color), parse_color(color2), angle)
    elif mode == "image":
        if background is None:
            raise ImageOpError("Wskaż obraz tła.")
        base = cover_fit(background.convert("RGBA"), size)
    elif mode == "blur":
        if original is None:
            raise ImageOpError("Rozmycie tła wymaga oryginalnego zdjęcia.")
        source = original.convert("RGB")
        if source.size != size:
            source = source.resize(size, Image.Resampling.LANCZOS)
        alpha = np.asarray(cutout.getchannel("A"))
        filled = _subject_free_background(source, alpha)
        radius = max(0.0, min(float(blur_radius), 200.0))
        base = filled.filter(ImageFilter.GaussianBlur(radius)).convert("RGBA")
    else:
        raise ImageOpError(f"Nieznany rodzaj tła: {mode}")
    return Image.alpha_composite(base, cutout)


def erase_with_mask(
    image: Image.Image, mask: Image.Image, method: Literal["telea", "ns"] = "telea", radius: int = 9
) -> Image.Image:
    """Usuwa obszar maski (biel = usuń) i odtwarza go z otoczenia (cv2.inpaint)."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    mask_array = np.asarray(mask.convert("L").resize(rgba.size, Image.Resampling.NEAREST))
    binary = (mask_array > 127).astype(np.uint8) * 255
    if not binary.any():
        raise ImageOpError("Maska jest pusta – zaznacz obszar do usunięcia.")
    binary = cv2.dilate(binary, np.ones((3, 3), np.uint8), iterations=2)
    bgr = cv2.cvtColor(np.asarray(rgba.convert("RGB")), cv2.COLOR_RGB2BGR)
    flag = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
    repaired = cv2.inpaint(bgr, binary, max(1, min(int(radius), 50)), flag)
    result = Image.fromarray(cv2.cvtColor(repaired, cv2.COLOR_BGR2RGB), "RGB")
    if image.mode in ("RGBA", "LA", "P") and alpha.getextrema() != (255, 255):
        result = result.convert("RGBA")
        result.putalpha(alpha)
    return result


def regions_mask(size: tuple[int, int], regions: list[tuple[float, float, float, float]]) -> Image.Image:
    """Maska z prostokątów podanych ułamkami wymiarów obrazu (x, y, szerokość, wysokość)."""
    width, height = size
    mask = np.zeros((height, width), np.uint8)
    for x, y, w, h in regions:
        left, top = round(x * width), round(y * height)
        right, bottom = round((x + w) * width), round((y + h) * height)
        mask[max(0, top) : min(height, bottom), max(0, left) : min(width, right)] = 255
    return Image.fromarray(mask, "L")


def remove_background(
    run: Callable[[list[str]], object], rembg_bin: str, model: str, source: Path, target: Path
) -> Image.Image:
    """Wycina obiekt z tła programem rembg; zwraca obraz RGBA (tło przezroczyste)."""
    command = [rembg_bin, "i"]
    if model:
        command += ["-m", model]
    run([*command, str(source), str(target)])
    if not target.is_file():
        raise ImageOpError("rembg nie utworzył pliku wynikowego.")
    with Image.open(target) as produced:
        return produced.convert("RGBA")


def has_transparency(image: Image.Image) -> bool:
    """Czy obraz ma kanał alfa z przezroczystymi pikselami."""
    if image.mode not in ("RGBA", "LA", "PA") and not (image.mode == "P" and "transparency" in image.info):
        return False
    return image.convert("RGBA").getchannel("A").getextrema()[0] < 250
