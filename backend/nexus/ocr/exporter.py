"""Eksport wyników OCR: przeszukiwalny PDF, TXT i DOCX.

Eksportery przyjmują strony strumieniowo, w kolejności dokumentu, dzięki
czemu pamięć nie rośnie z liczbą stron. Pliki powstają pod nazwą
tymczasową i są podmieniane dopiero po poprawnym zakończeniu.
"""

from __future__ import annotations

import logging
import os
import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from docx import Document as DocxDocument
from docx.enum.text import WD_BREAK
from docx.shared import Pt

from nexus.ocr.models import OcrLine, OcrPageResult, PageContent
from nexus.ocr.pdf_processor import OverlayInstruction, TextLayerWriter, apply_text_layer

logger = logging.getLogger(__name__)

COLUMN_GAP_CHARS = 4
PARAGRAPH_GAP_RATIO = 1.1
PAGE_SEPARATOR = "\n\n----- Strona {number} -----\n\n"


class PageSink(Protocol):
    """Odbiorca stron dokumentu w kolejności ich występowania."""

    def add_page(self, content: PageContent) -> None:
        """Przyjmuje kolejną stronę."""
        ...

    def finish(self) -> Path:
        """Zapisuje plik wynikowy i zwraca jego ścieżkę."""
        ...

    def abort(self) -> None:
        """Porzuca zapis i usuwa pliki tymczasowe."""
        ...


def _temporary_path(target: Path) -> Path:
    """Ścieżka pliku tymczasowego w katalogu docelowym (podmiana atomowa)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{target.stem}.", suffix=".part", dir=target.parent)
    os.close(handle)
    return Path(name)


def _remove_quietly(path: Path) -> None:
    """Usuwa plik tymczasowy; brak pliku nie jest błędem."""
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        logger.warning("Nie można usunąć pliku tymczasowego %s: %s", path, error)


@dataclass(slots=True)
class LayoutRow:
    """Wiersz wizualny strony: fragmenty tekstu leżące na tej samej wysokości."""

    top: float
    bottom: float
    segments: list[tuple[float, float, str]]

    @property
    def height(self) -> float:
        """Wysokość wiersza w punktach."""
        return self.bottom - self.top


def build_rows(lines: list[OcrLine]) -> list[LayoutRow]:
    """Grupuje wiersze OCR w wiersze wizualne w kolejności czytania."""
    items = []
    for line in lines:
        if not line.words:
            continue
        x0, y0, x1, y1 = line.bounds
        items.append((y0, y1, x0, x1, line.text))
    items.sort(key=lambda item: ((item[0] + item[1]) / 2, item[2]))
    rows: list[LayoutRow] = []
    for y0, y1, x0, x1, text in items:
        center = (y0 + y1) / 2
        row = rows[-1] if rows else None
        if row is not None and row.top <= center <= row.bottom:
            row.segments.append((x0, x1, text))
            row.top, row.bottom = min(row.top, y0), max(row.bottom, y1)
        else:
            rows.append(LayoutRow(y0, y1, [(x0, x1, text)]))
    for row in rows:
        row.segments.sort()
    return rows


def _char_width(rows: list[LayoutRow]) -> float:
    """Mediana szerokości znaku na stronie (do odtwarzania odstępów)."""
    widths = [(x1 - x0) / len(text) for row in rows for x0, x1, text in row.segments if text]
    return statistics.median(widths) if widths else 5.0


def page_text_with_layout(result: OcrPageResult) -> str:
    """Tekst strony z odstępami odwzorowującymi położenie bloków."""
    rows = build_rows(result.lines)
    if not rows:
        return ""
    char_width = _char_width(rows)
    left = min(row.segments[0][0] for row in rows)
    output: list[str] = []
    previous: LayoutRow | None = None
    for row in rows:
        if previous is not None and row.top - previous.bottom > PARAGRAPH_GAP_RATIO * previous.height:
            output.append("")
        parts: list[str] = []
        cursor = 0
        for x0, _, text in row.segments:
            column = int(round((x0 - left) / char_width))
            gap = column - cursor if parts else column
            parts.append(" " * max(1 if parts else 0, gap) + text)
            cursor = column + len(text)
        output.append("".join(parts).rstrip())
        previous = row
    return "\n".join(output)


def page_paragraphs(result: OcrPageResult) -> list[tuple[float, list[str]]]:
    """Dzieli stronę na akapity: ``(wcięcie w punktach, wiersze)``.

    Fragmenty wiersza rozdzielone szeroką przerwą (kolumny, tabele) są
    łączone tabulatorem.
    """
    rows = build_rows(result.lines)
    if not rows:
        return []
    char_width = _char_width(rows)
    left = min(row.segments[0][0] for row in rows)
    paragraphs: list[tuple[float, list[str]]] = []
    previous: LayoutRow | None = None
    for row in rows:
        pieces = [row.segments[0][2]]
        for (_, prev_x1, _), (x0, _, text) in zip(row.segments, row.segments[1:], strict=False):
            separator = "\t" if x0 - prev_x1 > COLUMN_GAP_CHARS * char_width else " "
            pieces.append(separator + text)
        line = "".join(pieces)
        new_paragraph = previous is None or row.top - previous.bottom > PARAGRAPH_GAP_RATIO * previous.height
        if new_paragraph:
            paragraphs.append((max(0.0, row.segments[0][0] - left), [line]))
        else:
            paragraphs[-1][1].append(line)
        previous = row
    return paragraphs


class TxtExporter:
    """Eksport do pliku tekstowego UTF-8 z zachowaniem układu stron."""

    def __init__(self, target: Path) -> None:
        self._target = target
        self._temporary = _temporary_path(target)
        self._file = self._temporary.open("w", encoding="utf-8", newline="\r\n")
        self._pages = 0

    def add_page(self, content: PageContent) -> None:
        """Dopisuje tekst strony."""
        if self._pages:
            self._file.write(PAGE_SEPARATOR.format(number=content.page_index + 1))
        text = page_text_with_layout(content.ocr) if content.ocr else content.existing_text
        self._file.write(text.rstrip())
        self._pages += 1

    def finish(self) -> Path:
        """Zamyka plik i publikuje go pod nazwą docelową."""
        self._file.write("\n")
        self._file.close()
        os.replace(self._temporary, self._target)
        return self._target

    def abort(self) -> None:
        """Porzuca eksport."""
        self._file.close()
        _remove_quietly(self._temporary)


class DocxExporter:
    """Eksport do dokumentu Word z akapitami i podziałem na strony."""

    def __init__(self, target: Path) -> None:
        self._target = target
        self._document = DocxDocument()
        style = self._document.styles["Normal"]
        style.font.name = "Calibri"
        style.font.size = Pt(11)
        self._pages = 0

    def add_page(self, content: PageContent) -> None:
        """Dodaje stronę jako ciąg akapitów."""
        document = self._document
        if self._pages:
            document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        if content.ocr is not None:
            paragraphs = page_paragraphs(content.ocr)
        else:
            blocks = [block for block in content.existing_text.split("\n\n") if block.strip()]
            paragraphs = [(0.0, block.strip().splitlines()) for block in blocks]
        for indent, lines in paragraphs:
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(4)
            if indent > 0:
                paragraph.paragraph_format.left_indent = Pt(min(indent, 300.0))
            for number, line in enumerate(lines):
                run = paragraph.add_run(line)
                if number < len(lines) - 1:
                    run.add_break()
        self._pages += 1

    def finish(self) -> Path:
        """Zapisuje dokument."""
        temporary = _temporary_path(self._target)
        try:
            self._document.save(str(temporary))
            os.replace(temporary, self._target)
        except OSError:
            _remove_quietly(temporary)
            raise
        return self._target

    def abort(self) -> None:
        """Porzuca eksport (dokument istnieje tylko w pamięci)."""
        self._document = DocxDocument()


class SearchablePdfExporter:
    """Eksport do PDF: oryginalne strony z nałożoną niewidoczną warstwą tekstu."""

    def __init__(self, base_pdf: Path, target: Path, font_path: Path, rotate_pages: bool) -> None:
        self._base = base_pdf
        self._target = target
        self._rotate_pages = rotate_pages
        self._layer_path = _temporary_path(target)
        self._layer = TextLayerWriter(self._layer_path, font_path)
        self._instructions: list[OverlayInstruction] = []

    def add_page(self, content: PageContent) -> None:
        """Dodaje warstwę tekstu strony poddanej OCR."""
        if content.ocr is None:
            return
        layer_page = self._layer.add_page(content.ocr)
        rotation = content.ocr.rotation if self._rotate_pages else 0
        self._instructions.append(OverlayInstruction(content.page_index, layer_page, rotation))

    def finish(self) -> Path:
        """Łączy warstwę z dokumentem bazowym i zapisuje wynik."""
        self._layer.close()
        temporary = _temporary_path(self._target)
        try:
            apply_text_layer(self._base, self._layer_path, self._instructions, temporary)
            os.replace(temporary, self._target)
        except Exception:
            _remove_quietly(temporary)
            raise
        finally:
            _remove_quietly(self._layer_path)
        return self._target

    def abort(self) -> None:
        """Porzuca eksport."""
        try:
            self._layer.close()
        except OSError as error:
            logger.warning("Nie można zamknąć warstwy tekstowej: %s", error)
        _remove_quietly(self._layer_path)
