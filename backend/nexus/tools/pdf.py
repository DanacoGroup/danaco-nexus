"""Narzędzia PDF: podział, łączenie, edycja stron, wykrywanie granic dokumentów."""

from __future__ import annotations

import re
import subprocess
from typing import Any

import cv2
import numpy as np
import pymupdf
from pydantic import BaseModel, ConfigDict, Field

from nexus.ocr.image_processor import binarize_for_analysis
from nexus.ocr.ocr_engine import NO_WINDOW, find_tesseract
from nexus.storage import safe_filename
from nexus.tools.base import OutputFile, ToolContext, ToolError, ToolInput, ToolResult, registry
from nexus.tools.common import as_pdf, file_kind, open_image, parse_pages, unique_name

TITLE_KEYWORDS = (
    "faktura",
    "rachunek",
    "umowa",
    "aneks",
    "protokół",
    "wezwanie",
    "postanowienie",
    "wyrok",
    "pełnomocnictwo",
    "zaświadczenie",
    "oświadczenie",
    "wniosek",
    "pozew",
    "decyzja",
    "zawiadomienie",
    "nakaz",
    "pismo",
    "potwierdzenie",
    "zamówienie",
    "oferta",
    "świadectwo",
    "invoice",
    "contract",
    "agreement",
    "certificate",
    "nota",
    "paragon",
    "polisa",
    "regulamin",
    "sprawozdanie",
    "raport",
)
PAGE_OF = re.compile(r"(?:strona|str\.?|page)\s*(\d{1,3})\s*(?:z|/|of)\s*(\d{1,3})", re.IGNORECASE)
PAGE_SLASH = re.compile(r"(?<![\d/.])(\d{1,3})\s*/\s*(\d{1,3})(?![\d/.])")
BLANK_INK_RATIO = 0.0005


class Segment(BaseModel):
    """Zakres stron nowego dokumentu."""

    model_config = ConfigDict(extra="forbid")

    pages: str = Field(description="Strony, np. '1-3' albo '4,6'.")
    name: str = Field(description="Nazwa pliku wynikowego (bez ścieżki), np. 'Faktura FV 12-2026.pdf'.")


class SplitInput(ToolInput):
    file_id: str = Field(description="PDF do podziału.")
    segments: list[Segment] = Field(min_length=1, max_length=500, description="Dokumenty do wydzielenia.")


class MergeInput(ToolInput):
    file_ids: list[str] = Field(
        min_length=1,
        max_length=300,
        description="Pliki w kolejności łączenia: PDF, obrazy, dokumenty biurowe.",
    )
    name: str = Field("Połączony dokument.pdf", description="Nazwa pliku wynikowego.")


class EditPagesInput(ToolInput):
    file_id: str = Field(description="PDF do edycji.")
    keep_pages: str | None = Field(
        None, description="Strony do zachowania w podanej kolejności, np. '3,1,2,5-'."
    )
    delete_pages: str | None = Field(None, description="Strony do usunięcia.")
    rotate: dict[str, int] = Field(
        default_factory=dict, description="Obrót stron: {'2': 90, '5-6': 180} (wielokrotności 90)."
    )
    name: str | None = Field(None, description="Nazwa wyniku.")


class BoundariesInput(ToolInput):
    file_id: str = Field(description="PDF zawierający wiele dokumentów.")
    ocr_language: str = Field("pol+eng", description="Język OCR nagłówków stron bez warstwy tekstowej.")


def _pdf_name(name: str) -> str:
    cleaned = safe_filename(name, "dokument.pdf")
    return cleaned if cleaned.lower().endswith(".pdf") else f"{cleaned}.pdf"


@registry.register(
    "pdf_split",
    """Dzieli PDF na osobne pliki według zakresów stron, bez utraty jakości.
Strony kopiowane są 1:1. Nadaj plikom opisowe nazwy (rodzaj dokumentu, numer, data).""",
    SplitInput,
)
def pdf_split(ctx: ToolContext, args: SplitInput) -> ToolResult:
    file = ctx.file(args.file_id)
    used: set[str] = set()
    outputs: list[OutputFile] = []
    report = []
    with pymupdf.open(as_pdf(ctx, file)) as source:
        for segment in args.segments:
            pages = parse_pages(segment.pages, source.page_count)
            target = ctx.output_path(unique_name(_pdf_name(segment.name), used))
            with pymupdf.open() as part:
                for index in pages:
                    part.insert_pdf(source, from_page=index, to_page=index)
                part.save(target, garbage=3, deflate=True)
            outputs.append(OutputFile(target, target.name, f"Strony {segment.pages} z {file.name}"))
            report.append({"name": target.name, "pages": [i + 1 for i in pages]})
    return ToolResult(
        {"documents": report}, f"Podzielono {file.name} na {len(outputs)} plików", files=outputs
    )


@registry.register(
    "pdf_merge",
    """Łączy pliki w jeden PDF w podanej kolejności. Przyjmuje PDF, obrazy (stają się
stronami) i dokumenty biurowe (konwersja LibreOffice).""",
    MergeInput,
)
def pdf_merge(ctx: ToolContext, args: MergeInput) -> ToolResult:
    target = ctx.output_path(_pdf_name(args.name))
    with pymupdf.open() as merged:
        for file_id in args.file_ids:
            ctx.check_cancelled()
            file = ctx.file(file_id)
            kind = file_kind(file)
            if kind == "image":
                image = open_image(file.path).convert("RGB")
                dpi = float((image.info.get("dpi") or (150,))[0] or 150)
                page = merged.new_page(width=image.width * 72 / dpi, height=image.height * 72 / dpi)
                staged = ctx.output_path("page.jpg")
                image.save(staged, quality=92)
                page.insert_image(page.rect, filename=str(staged))
            else:
                with pymupdf.open(as_pdf(ctx, file)) as source:
                    merged.insert_pdf(source)
        merged.save(target, garbage=3, deflate=True)
        pages = merged.page_count
    return ToolResult(
        {"output": target.name, "pages": pages},
        f"Połączono {len(args.file_ids)} plików ({pages} stron)",
        files=[OutputFile(target, target.name, "Połączony PDF")],
    )


@registry.register(
    "pdf_edit_pages",
    """Porządkuje strony w PDF: zmienia ich kolejność, usuwa zbędne i obraca te położone bokiem.""",
    EditPagesInput,
)
def pdf_edit_pages(ctx: ToolContext, args: EditPagesInput) -> ToolResult:
    file = ctx.file(args.file_id)
    with pymupdf.open(as_pdf(ctx, file)) as source:
        count = source.page_count
        order = parse_pages(args.keep_pages, count) if args.keep_pages else list(range(count))
        if args.delete_pages:
            removed = set(parse_pages(args.delete_pages, count))
            order = [index for index in order if index not in removed]
        if not order:
            raise ToolError("Po edycji nie pozostała żadna strona.")
        rotations: dict[int, int] = {}
        for spec, degrees in args.rotate.items():
            if degrees % 90:
                raise ToolError("Obrót musi być wielokrotnością 90°.")
            for index in parse_pages(spec, count):
                rotations[index] = degrees
        source.select(order)
        for position, original in enumerate(order):
            if original in rotations:
                page = source[position]
                page.set_rotation((page.rotation + rotations[original]) % 360)
        target = ctx.output_path(_pdf_name(args.name or f"{file.name.rsplit('.', 1)[0]}_edytowany.pdf"))
        source.save(target, garbage=3, deflate=True)
    return ToolResult(
        {"output": target.name, "pages": len(order)},
        f"Edycja stron {file.name}: {len(order)} stron",
        files=[OutputFile(target, target.name, f"Edycja stron {file.name}")],
    )


def _band_text(page: pymupdf.Page, language: str, tesseract: str) -> tuple[str, str, float]:
    """Tekst nagłówka i stopki strony oraz udział „atramentu” (pusta strona)."""
    pixmap = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY, alpha=False)
    gray = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width)
    ink_ratio = float(np.count_nonzero(binarize_for_analysis(gray)) / gray.size)
    text = page.get_text("text").strip()
    if len(text) > 40:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return " ".join(lines[:4]), " ".join(lines[-3:]), ink_ratio
    if ink_ratio < BLANK_INK_RATIO:
        return "", "", ink_ratio
    height = gray.shape[0]
    bands = []
    for band in (gray[: int(height * 0.28)], gray[int(height * 0.86) :]):
        ok, encoded = cv2.imencode(".png", band)
        completed = subprocess.run(
            [tesseract, "stdin", "stdout", "-l", language, "--psm", "6", "--dpi", "150"],
            input=encoded.tobytes(),
            capture_output=True,
            timeout=120,
            check=False,
            creationflags=NO_WINDOW,
        )
        bands.append(" ".join(completed.stdout.decode("utf-8", "replace").split()) if ok else "")
    return bands[0], bands[1], ink_ratio


def _words(text: str) -> set[str]:
    return {word for word in re.findall(r"\w{3,}", text.lower()) if not word.isdigit()}


@registry.register(
    "detect_document_boundaries",
    """Znajduje w jednym PDF granice między dokumentami, gdy w stosie skanów leży kilka pism naraz.
Strona po stronie sprawdza nagłówki i stopki (w razie potrzeby z OCR), numerację „strona X z Y”,
puste strony rozdzielające, tytuły dokumentów i podobieństwo nagłówków. Zwraca propozycję
podziału z uzasadnieniem — sam podział wykonuje pdf_split.""",
    BoundariesInput,
)
def detect_document_boundaries(ctx: ToolContext, args: BoundariesInput) -> ToolResult:
    file = ctx.file(args.file_id)
    tesseract = str(find_tesseract())
    pages: list[dict[str, Any]] = []
    starts: list[int] = []
    previous_words: set[str] = set()
    expected_end = -1
    with pymupdf.open(as_pdf(ctx, file)) as document:
        for index, page in enumerate(document):
            ctx.check_cancelled()
            ctx.progress(f"Analiza stron: {index + 1}/{document.page_count}")
            header, footer, ink = _band_text(page, args.ocr_language, tesseract)
            blank = ink < BLANK_INK_RATIO and not header
            combined = f"{header} {footer}"
            marker = PAGE_OF.search(combined) or PAGE_SLASH.search(footer)
            page_number = (int(marker.group(1)), int(marker.group(2))) if marker else None
            title = next((word for word in TITLE_KEYWORDS if word in header.lower()), None)
            words = _words(header)
            similarity = (
                len(words & previous_words) / max(1, len(words | previous_words))
                if words and previous_words
                else 0.0
            )
            reasons = []
            if index == 0:
                reasons.append("pierwsza strona")
            elif not blank:
                if page_number and page_number[0] == 1:
                    reasons.append("numeracja zaczyna się od 1")
                if title and similarity < 0.5:
                    reasons.append(f"tytuł: {title}")
                if pages and pages[-1]["blank"]:
                    reasons.append("po pustej stronie")
                if expected_end >= 0 and index > expected_end:
                    reasons.append("poprzedni dokument zakończony wg numeracji")
                if (
                    not reasons
                    and similarity < 0.1
                    and len(words) >= 4
                    and not (page_number and page_number[0] > 1)
                ):
                    reasons.append("zmiana nagłówka")
            if page_number:
                expected_end = index + (page_number[1] - page_number[0])
            likely_start = bool(reasons) and not blank
            if likely_start:
                starts.append(index)
            pages.append(
                {
                    "page": index + 1,
                    "blank": blank,
                    "header": header[:160],
                    "footer": footer[:100],
                    "page_marker": list(page_number) if page_number else None,
                    "header_similarity_to_previous": round(similarity, 2),
                    "likely_new_document": likely_start,
                    "reasons": reasons,
                }
            )
            if not blank:
                previous_words = words
        total = document.page_count
    segments = []
    for position, start in enumerate(starts):
        end = (starts[position + 1] if position + 1 < len(starts) else total) - 1
        while end > start and pages[end]["blank"]:
            end -= 1
        segments.append(
            {
                "pages": f"{start + 1}-{end + 1}" if end > start else str(start + 1),
                "first_header": pages[start]["header"][:100],
            }
        )
    return ToolResult(
        {"page_count": total, "suggested_segments": segments, "pages": pages},
        f"Wykryto {len(segments)} prawdopodobnych dokumentów w {file.name}",
    )
