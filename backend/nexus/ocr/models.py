"""Modele danych współdzielone przez warstwy aplikacji."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

Point = tuple[float, float]
Quad = tuple[Point, Point, Point, Point]


class ExportFormat(str, Enum):
    """Formaty plików wynikowych."""

    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"


class DocumentStatus(str, Enum):
    """Stan przetwarzania pojedynczego dokumentu."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class OcrWord:
    """Rozpoznane słowo wraz z czworokątem położenia.

    Wierzchołki ``quad`` są uporządkowane: lewy górny, prawy górny,
    prawy dolny, lewy dolny; układ współrzędnych ma początek w lewym
    górnym rogu, oś Y skierowaną w dół.
    """

    text: str
    quad: Quad
    confidence: float


@dataclass(slots=True)
class OcrLine:
    """Wiersz tekstu złożony ze słów w kolejności czytania."""

    words: list[OcrWord]
    confidence: float

    @property
    def text(self) -> str:
        """Treść wiersza ze słowami rozdzielonymi spacją."""
        return " ".join(word.text for word in self.words)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Prostokąt otaczający wiersz: ``(x0, y0, x1, y1)``."""
        xs = [x for word in self.words for x, _ in word.quad]
        ys = [y for word in self.words for _, y in word.quad]
        return min(xs), min(ys), max(xs), max(ys)


@dataclass(slots=True)
class OcrPageResult:
    """Wynik OCR jednej strony w punktach PDF strony wyprostowanej.

    Współrzędne słów odnoszą się do strony w orientacji docelowej
    (po obrocie o ``rotation``), z początkiem w lewym górnym rogu.
    """

    page_index: int
    width: float
    height: float
    rotation: int
    skew_angle: float
    lines: list[OcrLine]
    ocr_seconds: float = 0.0

    @property
    def text(self) -> str:
        """Treść strony wiersz po wierszu."""
        return "\n".join(line.text for line in self.lines)

    @property
    def word_count(self) -> int:
        """Liczba rozpoznanych słów."""
        return sum(len(line.words) for line in self.lines)


@dataclass(slots=True)
class PageContent:
    """Treść strony przekazywana do eksportu.

    Strona poddana OCR ma wypełnione ``ocr``; strona pominięta
    (z istniejącą warstwą tekstową) ma wypełnione ``existing_text``.
    """

    page_index: int
    ocr: OcrPageResult | None = None
    existing_text: str = ""


@dataclass(slots=True)
class DocumentResult:
    """Podsumowanie przetworzenia dokumentu."""

    source: Path
    status: DocumentStatus
    message: str = ""
    outputs: list[Path] = field(default_factory=list)
    pages_total: int = 0
    pages_ocr: int = 0
    seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Postęp przetwarzania bieżącego dokumentu."""

    source: Path
    pages_done: int
    pages_total: int


def normalize_text(text: str) -> str:
    """Normalizuje tekst OCR do postaci NFC bez znaków sterujących."""
    normalized = unicodedata.normalize("NFC", text)
    return "".join(
        char for char in normalized if unicodedata.category(char)[0] != "C" or char == "\t"
    ).strip()
