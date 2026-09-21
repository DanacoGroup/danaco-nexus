"""Narzędzie OCR: przeszukiwalne PDF (warstwa tekstowa), TXT i DOCX."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pymupdf
from pydantic import Field

from nexus.ocr.document_processor import run_ocr
from nexus.ocr.models import DocumentStatus, ExportFormat
from nexus.ocr.options import OcrOptions, PreprocessingSettings
from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    registry,
    truncate_text,
)
from nexus.tools.common import file_kind, unique_name, with_suffix


class OcrInput(ToolInput):
    file_ids: list[str] = Field(
        min_length=1, max_length=200, description="Pliki PDF (skany) lub obrazy do rozpoznania."
    )
    language: str = Field("pol+eng", description="Języki Tesseract, np. 'pol', 'pol+eng', 'eng'.")
    outputs: list[Literal["pdf", "txt", "docx"]] = Field(
        default_factory=lambda: ["pdf"],
        description="Formaty wyników: pdf = przeszukiwalny PDF z niewidoczną warstwą tekstową.",
    )
    preprocessing: Literal["standard", "strong", "minimal"] = Field(
        "standard",
        description="standard: prostowanie, odszumianie, kontrast, obrót stron; strong: jak standard "
        "z progowaniem adaptacyjnym (słabe skany); minimal: bez obróbki (czyste PDF).",
    )
    force: bool = Field(False, description="OCR także stron, które mają już niewidoczną warstwę OCR.")
    render_dpi: int = Field(300, ge=150, le=600, description="Rozdzielczość renderowania stron PDF.")
    return_text: bool = Field(True, description="Zwróć rozpoznany tekst do dalszej analizy.")


def _preprocessing(mode: str) -> PreprocessingSettings:
    if mode == "minimal":
        return PreprocessingSettings(
            deskew=False,
            denoise=False,
            contrast_enhancement=False,
            adaptive_threshold="never",
            border_crop=False,
        )
    if mode == "strong":
        return PreprocessingSettings(adaptive_threshold="always")
    return PreprocessingSettings()


@registry.register(
    "ocr_documents",
    """Rozpoznaje tekst w skanach PDF i na zdjęciach dokumentów, także po polsku.
Tworzy przeszukiwalny PDF identyczny wizualnie z oryginałem (niewidoczna warstwa tekstowa,
strony wyprostowane do pionu), opcjonalnie TXT z zachowaniem układu i DOCX (OCR, Tesseract).
Obsługuje wiele plików naraz (OCR wsadowy). Strony z istniejącym tekstem są pomijane.""",
    OcrInput,
)
def ocr_documents(ctx: ToolContext, args: OcrInput) -> ToolResult:
    formats = [ExportFormat(value) for value in dict.fromkeys(args.outputs)]
    options = OcrOptions(
        language=args.language,
        render_dpi=args.render_dpi,
        formats=formats,
        force_ocr=args.force,
        threads=ctx.settings.tool_threads,
        preprocessing=_preprocessing(args.preprocessing),
    )
    used: set[str] = set()
    outputs: list[OutputFile] = []
    report = []
    for position, file_id in enumerate(args.file_ids, start=1):
        ctx.check_cancelled()
        file = ctx.file(file_id)
        kind = file_kind(file)
        if kind not in {"pdf", "image"}:
            report.append({"file": file.name, "status": "pominięto", "reason": "OCR obsługuje PDF i obrazy."})
            continue
        ctx.progress(f"OCR {position}/{len(args.file_ids)}: {file.name}")
        targets = {
            fmt: ctx.output_path(unique_name(with_suffix(file.name, f".{fmt.value}", "_OCR"), used))
            for fmt in formats
        }
        result = run_ocr(
            file.path,
            kind == "image",
            targets,
            options,
            cancel=ctx.cancel,
            on_progress=lambda event, name=file.name: ctx.progress(
                f"OCR {name}: strona {event.pages_done}/{event.pages_total}"
            ),
        )
        entry: dict[str, object] = {
            "file": file.name,
            "status": result.status.value,
            "pages": result.pages_total,
            "pages_ocr": result.pages_ocr,
            "seconds": round(result.seconds, 1),
        }
        if result.message:
            entry["message"] = result.message
        if result.status is DocumentStatus.CANCELLED:
            ctx.check_cancelled()
        if result.status is DocumentStatus.DONE:
            for path in result.outputs:
                outputs.append(OutputFile(path, path.name, f"Wynik OCR dla {file.name}"))
            txt = next((p for p in result.outputs if p.suffix == ".txt"), None)
            if args.return_text:
                text = txt.read_text(encoding="utf-8") if txt else _pdf_text(result.outputs)
                entry["text"], truncated = truncate_text(text, 30_000 // max(1, len(args.file_ids)))
                if truncated:
                    entry["text_truncated"] = True
        report.append(entry)
    done = sum(1 for item in report if item["status"] == "done")
    if not done and not any(item["status"] == "skipped" for item in report):
        raise ToolError(f"OCR nie powiódł się: {report}")
    return ToolResult(
        {"results": report}, f"OCR: przetworzono {done} z {len(args.file_ids)} plików", files=outputs
    )


def _pdf_text(paths: list[Path]) -> str:
    """Tekst warstwy PDF wyniku OCR."""

    pdf = next((p for p in paths if p.suffix == ".pdf"), None)
    if pdf is None:
        return ""
    with pymupdf.open(pdf) as document:
        return "\n\n".join(
            f"--- Strona {page.number + 1} ---\n{page.get_text('text').strip()}" for page in document
        )
