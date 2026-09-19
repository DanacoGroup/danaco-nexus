"""Funkcje pomocnicze wspólne dla narzędzi: rodzaje plików, strony, konwersje."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps

from nexus.tools.base import FileRef, ToolContext, ToolError

Image.MAX_IMAGE_PIXELS = 400_000_000

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".gif"})
OFFICE_SUFFIXES = frozenset(
    {".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods", ".csv", ".ppt", ".pptx", ".odp"}
)
TEXT_SUFFIXES = frozenset({".txt", ".md", ".json", ".xml", ".html", ".htm"})
AUDIO_SUFFIXES = frozenset({".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"})
VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".mkv", ".avi", ".webm"})
ARCHIVE_SUFFIXES = frozenset({".zip"})


def file_kind(file: FileRef) -> str:
    """Rodzaj pliku: pdf, image, office, text, audio, video, archive, svg albo other."""
    suffix = file.suffix
    if suffix == ".pdf" or file.mime == "application/pdf":
        return "pdf"
    if suffix == ".svg":
        return "svg"
    if suffix in IMAGE_SUFFIXES or file.mime.startswith("image/"):
        return "image"
    if suffix in OFFICE_SUFFIXES:
        return "office"
    if suffix in TEXT_SUFFIXES or file.mime.startswith("text/"):
        return "text"
    if suffix in AUDIO_SUFFIXES or file.mime.startswith("audio/"):
        return "audio"
    if suffix in VIDEO_SUFFIXES or file.mime.startswith("video/"):
        return "video"
    if suffix in ARCHIVE_SUFFIXES:
        return "archive"
    return "other"


def parse_pages(spec: str | None, page_count: int) -> list[int]:
    """Zamienia opis stron (np. ``"1-3,5,8-"``) na indeksy od zera.

    Pusty opis oznacza wszystkie strony.
    """
    if not spec or spec.strip().lower() in {"all", "wszystkie", "*"}:
        return list(range(page_count))
    pages: list[int] = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        match = re.fullmatch(r"(\d*)-(\d*)|(\d+)", part)
        if not match:
            raise ToolError(f"Nieprawidłowy zakres stron: {part!r}")
        if match.group(3):
            start = end = int(match.group(3))
        else:
            start = int(match.group(1) or 1)
            end = int(match.group(2) or page_count)
        if start < 1 or end > page_count or start > end:
            raise ToolError(f"Zakres {part!r} wykracza poza dokument ({page_count} stron).")
        pages.extend(range(start - 1, end))
    return list(dict.fromkeys(pages))


def open_image(path: Path) -> Image.Image:
    """Otwiera obraz z uwzględnieniem orientacji EXIF."""
    try:
        image = Image.open(path)
        image.load()
    except (OSError, Image.DecompressionBombError) as error:
        raise ToolError(f"Nie można odczytać obrazu: {error}") from error
    return ImageOps.exif_transpose(image)


def render_pdf_page(document: pymupdf.Document, index: int, max_side: int) -> Image.Image:
    """Renderuje stronę PDF tak, by dłuższy bok miał co najwyżej ``max_side`` pikseli."""
    page = document[index]
    scale = max_side / max(page.rect.width, page.rect.height)
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def libreoffice_convert(ctx: ToolContext, source: Path, target_format: str) -> Path:
    """Konwertuje dokument pakietem LibreOffice (tryb bezobsługowy).

    Każde wywołanie ma własny profil użytkownika, więc konwersje mogą
    przebiegać równolegle.
    """
    out_dir = ctx.output_path("lo").parent
    profile = ctx.work_dir / f"lo_profile_{uuid.uuid4().hex}"
    ctx.run_command(
        [
            "soffice",
            "--headless",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to",
            target_format,
            "--outdir",
            str(out_dir),
            str(source),
        ],
        timeout=600,
    )
    extension = target_format.split(":")[0]
    produced = out_dir / f"{source.stem}.{extension}"
    if not produced.is_file():
        raise ToolError(f"LibreOffice nie utworzył pliku {extension.upper()} z {source.name}.")
    return produced


def as_pdf(ctx: ToolContext, file: FileRef) -> Path:
    """Ścieżka PDF dla pliku (PDF bez zmian, dokument biurowy po konwersji)."""
    kind = file_kind(file)
    if kind == "pdf":
        return file.path
    if kind in {"office", "text"}:
        staged = ctx.output_path(file.name)
        staged.write_bytes(file.path.read_bytes())
        return libreoffice_convert(ctx, staged, "pdf")
    raise ToolError(f"Plik {file.name} nie jest dokumentem, który można potraktować jak PDF.")


def unique_name(name: str, used: set[str]) -> str:
    """Nazwa pliku niekolidująca z już użytymi (``nazwa (2).pdf``)."""
    candidate = name
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 2
    while candidate.lower() in used:
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def with_suffix(name: str, suffix: str, tag: str = "") -> str:
    """Nazwa wyniku na podstawie nazwy źródła, np. ``skan.jpg`` → ``skan_OCR.pdf``."""
    stem = Path(name).stem
    return f"{stem}{tag}{suffix}"
