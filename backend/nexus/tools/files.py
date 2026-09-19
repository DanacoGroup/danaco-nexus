"""Narzędzia rozpoznania plików: metadane i jakość, podgląd stron, odczyt tekstu."""

from __future__ import annotations

import json
import zipfile
from typing import Any

import httpx
import pymupdf
from pydantic import Field

from nexus.tools.base import (
    PREVIEW_MAX_IMAGES,
    FileRef,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    image_preview,
    registry,
    truncate_text,
)
from nexus.tools.common import as_pdf, file_kind, open_image, parse_pages, render_pdf_page
from nexus.tools.imaging import analyze_image, pil_to_bgr

MAX_INSPECTED_PDF_PAGES = 40


class InspectInput(ToolInput):
    file_ids: list[str] = Field(
        min_length=1, max_length=30, description="Identyfikatory plików do sprawdzenia."
    )
    include_previews: bool = Field(True, description="Dołącz podgląd (pierwsza strona / obraz).")


class ViewInput(ToolInput):
    file_id: str = Field(description="Identyfikator pliku (PDF, obraz, dokument biurowy).")
    pages: str = Field("1", description="Strony PDF, np. '1', '2-4', '1,5,9'. Maks. 6 stron.")
    max_side: int = Field(
        1280, ge=400, le=2000, description="Dłuższy bok podglądu w pikselach (więcej = więcej szczegółów)."
    )


class ExtractTextInput(ToolInput):
    file_id: str = Field(description="Identyfikator pliku.")
    pages: str | None = Field(None, description="Zakres stron PDF (domyślnie wszystkie).")


def _pdf_info(file: FileRef, include_preview: bool) -> tuple[dict[str, Any], list[bytes]]:
    try:
        document = pymupdf.open(file.path)
    except (pymupdf.FileDataError, RuntimeError) as error:
        raise ToolError(f"PDF {file.name} jest uszkodzony: {error}") from error
    with document:
        if document.needs_pass:
            return {"encrypted": True, "note": "PDF zabezpieczony hasłem"}, []
        pages: list[dict[str, Any]] = []
        text_pages = 0
        for page in list(document)[:MAX_INSPECTED_PDF_PAGES]:
            chars = len(page.get_text("text").strip())
            images = page.get_image_info()
            coverage = max(
                (abs(pymupdf.Rect(i["bbox"]) & page.rect) / max(abs(page.rect), 1) for i in images),
                default=0.0,
            )
            text_pages += chars > 50
            pages.append(
                {
                    "page": page.number + 1,
                    "text_chars": chars,
                    "image_coverage": round(coverage, 2),
                    "rotation": page.rotation,
                    "size_pt": [round(page.rect.width), round(page.rect.height)],
                }
            )
        info = {
            "page_count": document.page_count,
            "pages_with_text_layer": text_pages,
            "looks_scanned": text_pages < max(1, len(pages) // 2),
            "metadata": {k: v for k, v in (document.metadata or {}).items() if v},
            "pages": pages,
        }
        if document.page_count > MAX_INSPECTED_PDF_PAGES:
            info["note"] = f"Szczegóły dla pierwszych {MAX_INSPECTED_PDF_PAGES} stron."
        previews = [image_preview(render_pdf_page(document, 0, 1024))] if include_preview else []
    return info, previews


def _image_info(file: FileRef, include_preview: bool) -> tuple[dict[str, Any], list[bytes]]:
    image = open_image(file.path)
    info: dict[str, Any] = {"width": image.width, "height": image.height, "mode": image.mode}
    dpi = image.info.get("dpi")
    if dpi:
        info["dpi"] = [round(float(value)) for value in dpi]
    exif = image.getexif()
    camera = " ".join(str(exif.get(tag, "")) for tag in (0x010F, 0x0110)).strip()
    if camera:
        info["camera"] = camera
    info["quality"] = analyze_image(pil_to_bgr(image))
    frames = getattr(image, "n_frames", 1)
    if frames > 1:
        info["frames"] = frames
    return info, [image_preview(image, 1024)] if include_preview else []


def _media_info(ctx: ToolContext, file: FileRef) -> dict[str, Any]:
    result = ctx.run_command(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(file.path)],
        timeout=60,
    )
    data = json.loads(result.stdout or "{}")
    fmt = data.get("format", {})
    streams = [
        {
            key: stream.get(key)
            for key in ("codec_type", "codec_name", "width", "height", "sample_rate", "channels", "bit_rate")
            if stream.get(key) is not None
        }
        for stream in data.get("streams", [])
    ]
    return {
        "duration_s": round(float(fmt.get("duration", 0) or 0), 2),
        "format": fmt.get("format_long_name"),
        "bit_rate": fmt.get("bit_rate"),
        "streams": streams,
    }


def _archive_info(file: FileRef) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(file.path) as archive:
            entries = [info for info in archive.infolist() if not info.is_dir()]
            return {
                "entries": len(entries),
                "uncompressed_bytes": sum(info.file_size for info in entries),
                "names": [info.filename for info in entries[:40]],
            }
    except zipfile.BadZipFile as error:
        raise ToolError(f"Archiwum {file.name} jest uszkodzone: {error}") from error


@registry.register(
    "inspect_files",
    """Sprawdza pliki: typ, rozmiar, liczbę stron, obecność warstwy tekstowej PDF,
wymiary i metryki jakości obrazów (jasność, kontrast, ostrość, szum, zafarb, pochylenie
tekstu), parametry audio/wideo i zawartość archiwów ZIP. Użyj przed doborem obróbki,
gdy jakość lub rodzaj pliku ma znaczenie. Zwraca też podgląd pierwszej strony/obrazu.""",
    InspectInput,
)
def inspect_files(ctx: ToolContext, args: InspectInput) -> ToolResult:
    report: list[dict[str, Any]] = []
    previews: list[bytes] = []
    for file_id in args.file_ids:
        ctx.check_cancelled()
        file = ctx.file(file_id)
        kind = file_kind(file)
        entry: dict[str, Any] = {
            "file_id": str(file.id),
            "name": file.name,
            "kind": kind,
            "mime": file.mime,
            "size_bytes": file.size,
        }
        want_preview = args.include_previews and len(previews) < PREVIEW_MAX_IMAGES
        try:
            if kind == "pdf":
                details, images = _pdf_info(file, want_preview)
            elif kind == "image":
                details, images = _image_info(file, want_preview)
            elif kind in {"audio", "video"}:
                details, images = _media_info(ctx, file), []
            elif kind == "archive":
                details, images = _archive_info(file), []
            elif kind == "text":
                content = file.path.read_text(encoding="utf-8", errors="replace")
                details, images = {"chars": len(content), "beginning": content[:400]}, []
            else:
                details, images = {}, []
        except ToolError as error:
            details, images = {"error": str(error)}, []
        entry.update(details)
        previews.extend(images)
        report.append(entry)
    return ToolResult({"files": report}, f"Sprawdzono pliki: {len(report)}", images=previews)


@registry.register(
    "view_pages",
    """Pokazuje wybrane strony dokumentu (PDF, DOCX/XLSX/PPTX po konwersji) lub obraz
jako podgląd, abyś mógł ocenić treść, układ, jakość albo granice dokumentów.
Maksymalnie 6 stron w jednym wywołaniu.""",
    ViewInput,
)
def view_pages(ctx: ToolContext, args: ViewInput) -> ToolResult:
    file = ctx.file(args.file_id)
    kind = file_kind(file)
    if kind == "image":
        return ToolResult(
            {"file": file.name},
            f"Podgląd {file.name}",
            images=[image_preview(open_image(file.path), args.max_side)],
        )
    with pymupdf.open(as_pdf(ctx, file)) as document:
        pages = parse_pages(args.pages, document.page_count)[:PREVIEW_MAX_IMAGES]
        images = [
            image_preview(render_pdf_page(document, index, args.max_side), args.max_side) for index in pages
        ]
        total = document.page_count
    return ToolResult(
        {"file": file.name, "page_count": total, "shown_pages": [index + 1 for index in pages]},
        f"Podgląd {file.name}: strony {', '.join(str(i + 1) for i in pages)}",
        images=images,
    )


def _tika_text(ctx: ToolContext, file: FileRef) -> str:
    """Tekst dokumentu przez Apache Tika: serwer (``tika_url``) albo tika-app w trybie wsadowym."""
    settings = ctx.settings
    if not settings.tika_url:
        if not settings.tika_app_jar.is_file():
            raise ToolError(f"Brak Apache Tika ({settings.tika_app_jar}).")
        completed = ctx.run_command(
            [
                settings.java_bin,
                "-Xmx2g",
                "-jar",
                str(settings.tika_app_jar),
                "--text",
                "--encoding=UTF-8",
                str(file.path),
            ],
            timeout=600,
        )
        return completed.stdout
    with file.path.open("rb") as handle:
        try:
            response = httpx.put(
                f"{settings.tika_url}/tika",
                content=handle.read(),
                headers={"Accept": "text/plain; charset=UTF-8"},
                timeout=300,
            )
        except httpx.HTTPError as error:
            raise ToolError(f"Usługa Apache Tika jest niedostępna: {error}") from error
    if response.status_code != 200:
        raise ToolError(f"Apache Tika zwróciła błąd HTTP {response.status_code}.")
    return response.content.decode("utf-8", errors="replace")


@registry.register(
    "extract_text",
    """Odczytuje tekst z pliku: warstwę tekstową PDF (strona po stronie), dokumenty
DOCX/XLSX/PPTX/ODT/RTF/HTML/TXT (Apache Tika). Dla skanów bez warstwy tekstowej
i zdjęć użyj najpierw ocr_documents. Długi tekst jest skracany – wtedy czytaj
kolejne zakresy stron.""",
    ExtractTextInput,
)
def extract_text(ctx: ToolContext, args: ExtractTextInput) -> ToolResult:
    file = ctx.file(args.file_id)
    kind = file_kind(file)
    if kind == "pdf":
        with pymupdf.open(file.path) as document:
            pages = parse_pages(args.pages, document.page_count)
            parts = [
                f"--- Strona {index + 1} ---\n{document[index].get_text('text').strip()}" for index in pages
            ]
        text = "\n\n".join(parts)
    elif kind == "text":
        text = file.path.read_text(encoding="utf-8", errors="replace")
    elif kind in {"image"}:
        raise ToolError("Obraz nie ma warstwy tekstowej – użyj ocr_documents.")
    else:
        text = _tika_text(ctx, file)
    text, truncated = truncate_text(text.replace(" ", " "))
    data: dict[str, Any] = {"file": file.name, "chars": len(text), "text": text}
    if truncated:
        data["truncated"] = (
            "Tekst skrócony do limitu – odczytaj kolejne strony parametrem pages, aby poznać resztę."
        )
    if kind == "pdf" and len(text.strip()) < 30:
        data["hint"] = "PDF prawie nie ma tekstu – to prawdopodobnie skan; użyj ocr_documents."
    return ToolResult(data, f"Odczytano tekst: {file.name} ({len(text)} znaków)")
