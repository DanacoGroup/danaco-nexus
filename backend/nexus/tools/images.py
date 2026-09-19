"""Narzędzia obróbki obrazów: poprawa skanów, zdjęć, retusz, powiększanie AI,
ImageMagick i konwersje formatów."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
import pymupdf
from PIL import Image
from pydantic import Field

from nexus.ocr.image_processor import (
    adaptive_threshold,
    binarize_for_analysis,
    estimate_skew_angle,
    normalize_background,
    remove_scanner_edges,
)
from nexus.tools import imaging
from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    image_preview,
    registry,
)
from nexus.tools.common import file_kind, open_image, unique_name, with_suffix

JPEG_QUALITY = 92
MAX_SCAN_PAGES = 500
SCAN_DPI = 300


def _save_bgr(image: np.ndarray, path: Path, dpi: float | None = None) -> None:
    """Zapisuje obraz BGR (JPEG/PNG/TIFF/WEBP wg rozszerzenia) z zachowaniem DPI."""
    pil = Image.fromarray(imaging.bgr_to_rgb(image) if image.ndim == 3 else image)
    params: dict[str, Any] = {}
    if dpi:
        params["dpi"] = (dpi, dpi)
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        params.update(quality=JPEG_QUALITY, optimize=True, subsampling=0)
    elif suffix in {".tif", ".tiff"}:
        params["compression"] = "tiff_lzw"
    pil.save(path, **params)


def _output_suffix(name: str, requested: str | None) -> str:
    if requested:
        return "." + requested.lower().lstrip(".")
    suffix = Path(name).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"} else ".png"


# --- Skany dokumentów ---------------------------------------------------------------------------


class ScanInput(ToolInput):
    file_ids: list[str] = Field(min_length=1, max_length=100, description="Skany: obrazy lub PDF.")
    crop_document: bool = Field(True, description="Wykryj kartkę na zdjęciu i wyprostuj perspektywę.")
    deskew: bool = Field(True, description="Wyprostuj przekrzywiony tekst.")
    denoise: bool = Field(True, description="Usuń szum.")
    normalize_background: bool = Field(True, description="Wyrównaj oświetlenie i cienie, wybiel tło.")
    remove_scanner_borders: bool = Field(True, description="Usuń czarne pasy przy krawędziach skanu.")
    unpaper: bool = Field(False, description="Dodatkowe czyszczenie artefaktów programem unpaper.")
    output_mode: Literal["color", "grayscale", "black_white"] = Field(
        "grayscale", description="Kolor, skala szarości albo czerń-biel (progowanie adaptacyjne)."
    )
    sharpen: float = Field(0.4, ge=0, le=2, description="Siła wyostrzenia tekstu.")
    output_format: Literal["same", "pdf", "png", "jpg", "tiff"] = Field(
        "same", description="Format wyniku; 'same' zachowuje format źródła."
    )


def _clean_scan(
    ctx: ToolContext, image: np.ndarray, args: ScanInput, dpi: int
) -> tuple[np.ndarray, dict[str, Any]]:
    applied: dict[str, Any] = {}
    if args.crop_document:
        quad = imaging.find_document_quad(image)
        if quad is not None:
            image = imaging.warp_document(image, quad)
            applied["perspective_corrected"] = True
    if args.denoise:
        image = imaging.denoise(image, 0.8)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if args.deskew:
        angle = estimate_skew_angle(binarize_for_analysis(gray))
        if abs(angle) >= 0.2:
            height, width = gray.shape
            matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
            image = cv2.warpAffine(
                image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255)
            )
            applied["deskew_degrees"] = round(-angle, 2)
    if args.output_mode == "color":
        result = image
        if args.normalize_background:
            planes = [normalize_background(image[:, :, channel]) for channel in range(3)]
            result = cv2.merge(planes)
    else:
        result = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if args.normalize_background:
            result = normalize_background(result)
        if args.remove_scanner_borders:
            result = remove_scanner_edges(result, binarize_for_analysis(result))
    if args.sharpen > 0:
        blurred = cv2.GaussianBlur(result, (0, 0), 1.0)
        result = cv2.addWeighted(result, 1 + args.sharpen, blurred, -args.sharpen, 0)
    if args.unpaper:
        result = _unpaper(ctx, result)
        applied["unpaper"] = True
    if args.output_mode == "black_white":
        gray_result = result if result.ndim == 2 else cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        result = adaptive_threshold(gray_result, dpi)
    return result, applied


def _unpaper(ctx: ToolContext, image: np.ndarray) -> np.ndarray:
    """Czyszczenie artefaktów skanu programem unpaper (PGM/PPM)."""
    source = ctx.output_path("unpaper_in.pgm" if image.ndim == 2 else "unpaper_in.ppm")
    target = source.with_name("unpaper_out" + source.suffix)
    ok, encoded = cv2.imencode(source.suffix, image)
    if not ok:
        raise ToolError("Nie można przygotować obrazu dla unpaper.")
    source.write_bytes(encoded.tobytes())
    ctx.run_command(["unpaper", "--overwrite", "--layout", "single", str(source), str(target)], timeout=300)
    result = cv2.imdecode(np.frombuffer(target.read_bytes(), np.uint8), cv2.IMREAD_UNCHANGED)
    if result is None:
        raise ToolError("unpaper nie zwrócił obrazu.")
    return result


@registry.register(
    "enhance_document_scan",
    """Poprawia jakość skanów i zdjęć dokumentów: wykrycie kartki i korekta perspektywy,
prostowanie, odszumianie, wyrównanie oświetlenia/cieni i wybielenie tła, usunięcie
czarnych krawędzi, opcjonalnie unpaper, wyostrzenie tekstu i czerń-biel. Obsługuje obrazy
i wielostronicowe PDF (wynik PDF). Dobierz opcje po inspect_files; potem możesz wykonać OCR.""",
    ScanInput,
)
def enhance_document_scan(ctx: ToolContext, args: ScanInput) -> ToolResult:
    used: set[str] = set()
    outputs: list[OutputFile] = []
    report: list[dict[str, Any]] = []
    previews: list[bytes] = []
    for file_id in args.file_ids:
        ctx.check_cancelled()
        file = ctx.file(file_id)
        kind = file_kind(file)
        if kind == "image":
            source = open_image(file.path)
            dpi = int(source.info.get("dpi", (SCAN_DPI,))[0] or SCAN_DPI)
            cleaned, applied = _clean_scan(ctx, imaging.pil_to_bgr(source), args, dpi)
            suffix = (
                ".pdf"
                if args.output_format == "pdf"
                else _output_suffix(file.name, None if args.output_format == "same" else args.output_format)
            )
            target = ctx.output_path(unique_name(with_suffix(file.name, suffix, "_poprawiony"), used))
            if suffix == ".pdf":
                _images_to_pdf([cleaned], target, dpi)
            else:
                _save_bgr(cleaned, target, dpi)
            pages = 1
        elif kind == "pdf":
            target = ctx.output_path(unique_name(with_suffix(file.name, ".pdf", "_poprawiony"), used))
            with pymupdf.open(file.path) as document:
                if document.page_count > MAX_SCAN_PAGES:
                    raise ToolError(f"{file.name}: maks. {MAX_SCAN_PAGES} stron w jednym wywołaniu.")
                pages_out = []
                applied = {}
                for index in range(document.page_count):
                    ctx.check_cancelled()
                    ctx.progress(f"{file.name}: strona {index + 1}/{document.page_count}")
                    page = document[index]
                    pixmap = page.get_pixmap(dpi=SCAN_DPI, alpha=False)
                    rgb = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width, 3)
                    cleaned, applied = _clean_scan(ctx, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), args, SCAN_DPI)
                    pages_out.append(cleaned)
                _images_to_pdf(pages_out, target, SCAN_DPI)
                pages = document.page_count
                cleaned = pages_out[0]
        else:
            raise ToolError(f"{file.name}: obsługiwane są obrazy i PDF.")
        if len(previews) < 4:
            previews.append(
                image_preview(
                    Image.fromarray(imaging.bgr_to_rgb(cleaned) if cleaned.ndim == 3 else cleaned), 1024
                )
            )
        outputs.append(OutputFile(target, target.name, f"Poprawiony skan {file.name}"))
        report.append({"file": file.name, "pages": pages, "output": target.name, **applied})
    return ToolResult(
        {"results": report}, f"Poprawiono skany: {len(outputs)}", images=previews, files=outputs
    )


def _images_to_pdf(images: list[np.ndarray], target: Path, dpi: int) -> None:
    """Składa strony w PDF (czerń-biel jako PNG 1-bit, pozostałe jako JPEG)."""
    with pymupdf.open() as document:
        for image in images:
            height, width = image.shape[:2]
            page = document.new_page(width=width * 72 / dpi, height=height * 72 / dpi)
            unique = np.unique(image) if image.ndim == 2 and image.size < 60_000_000 else None
            if unique is not None and len(unique) <= 2:
                ok, data = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_BILEVEL, 1])
            else:
                ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
            if not ok:
                raise ToolError("Nie można zakodować strony wynikowej.")
            page.insert_image(page.rect, stream=data.tobytes())
        document.save(target, garbage=3, deflate=True)


# --- Zdjęcia --------------------------------------------------------------------------------------


class PhotoInput(ToolInput):
    file_ids: list[str] = Field(min_length=1, max_length=100, description="Zdjęcia do poprawy.")
    white_balance: float = Field(0.0, ge=0, le=1, description="Korekta balansu bieli (0 = brak, 1 = pełna).")
    auto_levels: bool = Field(False, description="Rozciągnięcie zakresu tonalnego.")
    auto_exposure: bool = Field(False, description="Automatyczna korekta ekspozycji.")
    exposure_ev: float = Field(0.0, ge=-2, le=2, description="Ręczna korekta ekspozycji w EV.")
    shadows: float = Field(0.0, ge=0, le=1, description="Rozjaśnienie cieni.")
    highlights: float = Field(0.0, ge=0, le=1, description="Odzyskanie świateł.")
    local_contrast: float = Field(0.0, ge=0, le=1, description="Kontrast lokalny (CLAHE).")
    saturation: float = Field(1.0, ge=0, le=2, description="Nasycenie (1 = bez zmian).")
    warmth: float = Field(0.0, ge=-1, le=1, description="Ocieplenie (+) / ochłodzenie (−) tonacji.")
    denoise: float = Field(0.0, ge=0, le=1.5, description="Siła odszumiania.")
    sharpen: float = Field(0.0, ge=0, le=2, description="Siła wyostrzenia.")
    straighten_verticals: bool = Field(False, description="Wyprostuj pionowe linie (wnętrza, budynki).")
    max_side: int | None = Field(
        None, ge=512, le=12000, description="Opcjonalne zmniejszenie dłuższego boku."
    )
    output_format: Literal["same", "jpg", "png", "webp", "tiff"] = Field("same", description="Format wyniku.")


@registry.register(
    "enhance_photo",
    """Profesjonalna korekta zdjęć (np. ogłoszenia nieruchomości, produkty): balans bieli,
poziomy, ekspozycja, cienie/światła, kontrast lokalny, nasycenie, temperatura barwowa,
odszumianie, wyostrzenie, prostowanie pionów i perspektywy. Parametry dobierz na
podstawie metryk z inspect_files i podglądu. Zwraca podgląd wyniku do oceny.""",
    PhotoInput,
)
def enhance_photo(ctx: ToolContext, args: PhotoInput) -> ToolResult:
    used: set[str] = set()
    outputs: list[OutputFile] = []
    report: list[dict[str, Any]] = []
    previews: list[bytes] = []
    for file_id in args.file_ids:
        ctx.check_cancelled()
        file = ctx.file(file_id)
        if file_kind(file) != "image":
            raise ToolError(f"{file.name} nie jest obrazem.")
        source = open_image(file.path)
        image = imaging.pil_to_bgr(source)
        applied: dict[str, Any] = {}
        if args.straighten_verticals:
            image, geometry = imaging.straighten_verticals(image)
            applied["verticals"] = geometry
        if args.denoise > 0:
            image = imaging.denoise(image, args.denoise)
        if args.white_balance > 0:
            image = imaging.white_balance(image, args.white_balance)
        if args.auto_levels:
            image = imaging.auto_levels(image)
        if args.auto_exposure:
            image = imaging.auto_exposure(image)
        if args.exposure_ev:
            image = imaging.adjust_exposure(image, args.exposure_ev)
        if args.shadows or args.highlights:
            image = imaging.shadows_highlights(image, args.shadows, args.highlights)
        if args.local_contrast > 0:
            image = imaging.local_contrast(image, args.local_contrast)
        if args.saturation != 1.0:
            image = imaging.adjust_saturation(image, args.saturation)
        if args.warmth:
            image = imaging.warm_tone(image, args.warmth)
        if args.sharpen > 0:
            image = imaging.sharpen(image, args.sharpen)
        if args.max_side and max(image.shape[:2]) > args.max_side:
            scale = args.max_side / max(image.shape[:2])
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        suffix = _output_suffix(file.name, None if args.output_format == "same" else args.output_format)
        target = ctx.output_path(unique_name(with_suffix(file.name, suffix, "_poprawione"), used))
        _save_bgr(image, target, (source.info.get("dpi") or (None,))[0])
        outputs.append(OutputFile(target, target.name, f"Poprawione zdjęcie {file.name}"))
        report.append(
            {
                "file": file.name,
                "output": target.name,
                "applied": applied,
                "quality_after": imaging.analyze_image(image)["assessment"],
            }
        )
        if len(previews) < 4:
            previews.append(image_preview(Image.fromarray(imaging.bgr_to_rgb(image)), 1024))
    return ToolResult(
        {"results": report}, f"Poprawiono zdjęcia: {len(outputs)}", images=previews, files=outputs
    )


class RetouchInput(ToolInput):
    file_ids: list[str] = Field(min_length=1, max_length=50, description="Zdjęcia portretowe.")
    skin_smoothing: float = Field(
        0.4, ge=0, le=1, description="Siła wygładzenia skóry (naturalnie: 0.2–0.5)."
    )
    warmth: float = Field(0.1, ge=-1, le=1, description="Delikatne ocieplenie tonacji.")
    brighten: float = Field(0.15, ge=0, le=1, description="Rozjaśnienie cieni twarzy.")
    sharpen: float = Field(0.3, ge=0, le=1.5, description="Wyostrzenie oczu i detali.")
    output_format: Literal["same", "jpg", "png", "webp"] = Field("same", description="Format wyniku.")


@registry.register(
    "retouch_portrait",
    """Naturalny retusz portretu: wygładzenie skóry z zachowaniem tekstury, delikatne
rozjaśnienie cieni, ocieplenie i wyostrzenie detali. Bez zmiany rysów twarzy.""",
    RetouchInput,
)
def retouch_portrait(ctx: ToolContext, args: RetouchInput) -> ToolResult:
    used: set[str] = set()
    outputs: list[OutputFile] = []
    previews: list[bytes] = []
    for file_id in args.file_ids:
        ctx.check_cancelled()
        file = ctx.file(file_id)
        if file_kind(file) != "image":
            raise ToolError(f"{file.name} nie jest obrazem.")
        source = open_image(file.path)
        image = imaging.pil_to_bgr(source)
        image = imaging.smooth_skin(image, args.skin_smoothing)
        if args.brighten:
            image = imaging.shadows_highlights(image, args.brighten, 0.0)
        image = imaging.warm_tone(image, args.warmth)
        image = imaging.sharpen(image, args.sharpen, radius=1.0)
        suffix = _output_suffix(file.name, None if args.output_format == "same" else args.output_format)
        target = ctx.output_path(unique_name(with_suffix(file.name, suffix, "_retusz"), used))
        _save_bgr(image, target, (source.info.get("dpi") or (None,))[0])
        outputs.append(OutputFile(target, target.name, f"Retusz {file.name}"))
        if len(previews) < 4:
            previews.append(image_preview(Image.fromarray(imaging.bgr_to_rgb(image)), 1024))
    return ToolResult(
        {"outputs": [f.name for f in outputs]},
        f"Retusz zdjęć: {len(outputs)}",
        images=previews,
        files=outputs,
    )


# --- Powiększanie AI ------------------------------------------------------------------------------


class UpscaleInput(ToolInput):
    file_ids: list[str] = Field(min_length=1, max_length=30, description="Obrazy do powiększenia.")
    scale: Literal[2, 3, 4] = Field(4, description="Krotność powiększenia.")
    model: Literal["photo", "anime"] = Field("photo", description="photo: zdjęcia; anime: grafika/rysunki.")


@registry.register(
    "upscale_image",
    """Powiększa i rekonstruuje szczegóły obrazu siecią Real-ESRGAN (AI, na CPU – może
trwać kilka minut dla dużych zdjęć). Używaj dla małych, rozmytych lub skompresowanych
zdjęć, gdy potrzebna jest wyższa rozdzielczość.""",
    UpscaleInput,
)
def upscale_image(ctx: ToolContext, args: UpscaleInput) -> ToolResult:
    root = ctx.settings.realesrgan_dir
    executable = root / "realesrgan-ncnn-vulkan"
    if not executable.is_file():
        raise ToolError("Real-ESRGAN nie jest dostępny w środowisku narzędzi.")
    if args.model == "photo":
        model = "realesrgan-x4plus"
        native_scale = 4
    else:
        model = f"realesr-animevideov3-x{args.scale}"
        native_scale = args.scale
    used: set[str] = set()
    outputs: list[OutputFile] = []
    previews: list[bytes] = []
    for file_id in args.file_ids:
        ctx.check_cancelled()
        file = ctx.file(file_id)
        if file_kind(file) != "image":
            raise ToolError(f"{file.name} nie jest obrazem.")
        source = open_image(file.path).convert("RGB")
        if source.width * source.height > 12_000_000:
            raise ToolError(
                f"{file.name}: obraz jest już duży ({source.width}×{source.height}); "
                "powiększanie AI ma sens dla obrazów do ok. 12 Mpx."
            )
        staged = ctx.output_path("input.png")
        source.save(staged)
        produced = staged.with_name("output.png")
        ctx.progress(f"Real-ESRGAN: {file.name}")
        ctx.run_command(
            [
                str(executable),
                "-i",
                str(staged),
                "-o",
                str(produced),
                "-n",
                model,
                "-s",
                str(native_scale),
                "-m",
                str(root / "models"),
                "-f",
                "png",
            ],
            timeout=3600,
            env={**os.environ, "VK_ICD_FILENAMES": _lavapipe_icd()},
        )
        result = Image.open(produced)
        if native_scale != args.scale:
            target_size = (source.width * args.scale, source.height * args.scale)
            result = result.resize(target_size, Image.Resampling.LANCZOS)
        target = ctx.output_path(unique_name(with_suffix(file.name, ".png", f"_x{args.scale}"), used))
        result.save(target, optimize=True)
        outputs.append(OutputFile(target, target.name, f"Powiększenie ×{args.scale} {file.name}"))
        if len(previews) < 3:
            previews.append(image_preview(result, 1280))
    return ToolResult(
        {"outputs": [f.name for f in outputs], "model": model},
        f"Powiększono obrazy: {len(outputs)}",
        images=previews,
        files=outputs,
    )


def _lavapipe_icd() -> str:
    """Sterownik Vulkan na CPU (lavapipe) – serwer nie ma karty graficznej."""
    for candidate in ("/usr/share/vulkan/icd.d/lvp_icd.json", "/usr/share/vulkan/icd.d/lvp_icd.x86_64.json"):
        if Path(candidate).is_file():
            return candidate
    return os.environ.get("VK_ICD_FILENAMES", "")


# --- ImageMagick i konwersje ----------------------------------------------------------------------

MAGICK_ALLOWED = re.compile(
    r"^-(auto-level|auto-gamma|auto-orient|normalize|equalize|enhance|despeckle|strip|trim|"
    r"flip|flop|negate|grayscale|colorspace|brightness-contrast|level|modulate|gamma|sharpen|"
    r"unsharp|blur|gaussian-blur|resize|crop|rotate|deskew|contrast-stretch|sigmoidal-contrast|"
    r"white-balance|quality|density|units|background|flatten|extent|gravity|border|bordercolor|"
    r"threshold|monochrome|posterize|sepia-tone|vignette|shave|fuzz|median|noise|type|depth|"
    r"clahe|colors|dither|filter|interpolate|trim|repage|chop|fill|tint|colorize|channel|separate)$"
)
MAGICK_VALUE = re.compile(r"^[A-Za-z0-9.,:%x+\-#!<>@^ ]{1,40}$")


class MagickInput(ToolInput):
    file_id: str = Field(description="Obraz źródłowy.")
    arguments: list[str] = Field(
        min_length=1,
        max_length=40,
        description="Operacje ImageMagick, np. ['-auto-level', '-unsharp', '0x1'].",
    )
    output_format: Literal["jpg", "png", "webp", "tiff", "gif", "pdf"] = Field(
        "png", description="Format wyniku."
    )


@registry.register(
    "imagemagick",
    """Uruchamia ImageMagick (magick) z listą operacji na jednym obrazie, gdy potrzebna jest
obróbka, której nie obejmują inne narzędzia (np. przycięcie, obramowanie, sepia, zmiana
rozmiaru, kolorystyka). Dozwolone są tylko bezpieczne operatory; ścieżki są dodawane automatycznie.""",
    MagickInput,
)
def run_imagemagick(ctx: ToolContext, args: MagickInput) -> ToolResult:
    file = ctx.file(args.file_id)
    if file_kind(file) != "image":
        raise ToolError(f"{file.name} nie jest obrazem.")
    for argument in args.arguments:
        if argument[:1] in "-+" and not re.match(r"^[-+]?\d", argument):
            if not MAGICK_ALLOWED.match("-" + argument[1:]):
                raise ToolError(f"Operacja ImageMagick niedozwolona: {argument}")
        elif (
            not MAGICK_VALUE.match(argument)
            or argument.startswith("@")
            or re.match(r"^[A-Za-z]{2,}:", argument)
        ):
            raise ToolError(f"Niedozwolona wartość argumentu ImageMagick: {argument!r}")
    target = ctx.output_path(with_suffix(file.name, f".{args.output_format}", "_edytowany"))
    ctx.run_command(["magick", str(file.path), *args.arguments, str(target)], timeout=600)
    previews = [] if args.output_format == "pdf" else [image_preview(Image.open(target), 1024)]
    return ToolResult(
        {"output": target.name},
        f"ImageMagick: {file.name}",
        images=previews,
        files=[OutputFile(target, target.name, f"Obróbka ImageMagick {file.name}")],
    )


class ConvertImageInput(ToolInput):
    file_ids: list[str] = Field(min_length=1, max_length=200, description="Obrazy do konwersji.")
    target_format: Literal["jpg", "png", "webp", "tiff", "pdf", "bmp"] = Field(description="Format docelowy.")
    combine_into_one_pdf: bool = Field(False, description="Przy PDF: połącz wszystkie obrazy w jeden plik.")
    max_side: int | None = Field(None, ge=64, le=20000, description="Opcjonalne zmniejszenie dłuższego boku.")
    quality: int = Field(90, ge=40, le=100, description="Jakość JPEG/WEBP.")


@registry.register(
    "convert_images",
    """Konwertuje obrazy między formatami (JPG, PNG, WEBP, TIFF, BMP, PDF), opcjonalnie
zmniejsza je i łączy wiele obrazów w jeden PDF.""",
    ConvertImageInput,
)
def convert_images(ctx: ToolContext, args: ConvertImageInput) -> ToolResult:
    used: set[str] = set()
    images: list[tuple[str, Image.Image]] = []
    for file_id in args.file_ids:
        file = ctx.file(file_id)
        if file_kind(file) != "image":
            raise ToolError(f"{file.name} nie jest obrazem.")
        image = open_image(file.path)
        if args.max_side:
            image.thumbnail((args.max_side, args.max_side), Image.Resampling.LANCZOS)
        images.append((file.name, image))
    outputs: list[OutputFile] = []
    if args.target_format == "pdf" and args.combine_into_one_pdf:
        target = ctx.output_path(with_suffix(images[0][0], ".pdf", "_polaczone"))
        rgb = [image.convert("RGB") for _, image in images]
        rgb[0].save(target, save_all=True, append_images=rgb[1:], resolution=150.0)
        outputs.append(OutputFile(target, target.name, "Obrazy połączone w PDF"))
    else:
        for name, image in images:
            target = ctx.output_path(unique_name(with_suffix(name, f".{args.target_format}"), used))
            params: dict[str, Any] = {}
            if args.target_format in {"jpg", "webp"}:
                image = image.convert("RGB")
                params["quality"] = args.quality
            elif args.target_format == "pdf":
                image = image.convert("RGB")
                params["resolution"] = 150.0
            image.save(target, **params)
            outputs.append(OutputFile(target, target.name, f"Konwersja {name}"))
    return ToolResult({"outputs": [f.name for f in outputs]}, f"Skonwertowano: {len(outputs)}", files=outputs)
