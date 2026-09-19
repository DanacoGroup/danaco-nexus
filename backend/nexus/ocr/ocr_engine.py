"""Silnik OCR Tesseract uruchamiany jako proces zewnętrzny.

Każdy wątek roboczy korzysta z własnej instancji silnika
(:class:`OcrEngineFactory`); każde wywołanie to osobny proces systemowy.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
import shutil
import subprocess
import threading
from abc import ABC, abstractmethod
from pathlib import Path

import cv2
import numpy as np

from nexus.ocr.models import OcrLine, OcrWord, Quad, normalize_text
from nexus.ocr.options import OcrOptions

logger = logging.getLogger(__name__)

TESSERACT_DEFAULT_PATHS: tuple[Path, ...] = (
    Path("/usr/bin/tesseract"),
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
GARBAGE_CONFIDENCE = 0.8
OSD_MIN_CONFIDENCE = 2.0


class OcrEngineError(Exception):
    """Błąd silnika OCR z komunikatem dla użytkownika."""


class OcrEngine(ABC):
    """Wspólny interfejs silników OCR."""

    #: Czy silnik uzyskuje lepsze wyniki na obrazie po progowaniu.
    prefers_binary_input: bool = False

    @abstractmethod
    def recognize(self, image: np.ndarray, dpi: int) -> list[OcrLine]:
        """Rozpoznaje tekst; współrzędne w pikselach przekazanego obrazu."""

    @abstractmethod
    def detect_rotation(self, image: np.ndarray, dpi: int) -> int:
        """Zwraca obrót (0/90/180/270, zgodnie z ruchem wskazówek zegara) prostujący stronę."""


def _is_garbage(text: str, confidence: float) -> bool:
    """Czy słowo wygląda na artefakt (szum, linie tabeli, fragment grafiki)."""
    if not text:
        return True
    alnum = sum(1 for char in text if char.isalnum())
    if alnum == 0:
        return (confidence < GARBAGE_CONFIDENCE and len(text) > 1) or text in {"|", "||", "¦"}
    return len(text) > 2 and alnum / len(text) < 0.34 and confidence < GARBAGE_CONFIDENCE


def clean_lines(lines: list[OcrLine], min_confidence: float) -> list[OcrLine]:
    """Usuwa słowa o niskiej pewności i artefakty; normalizuje tekst."""
    cleaned: list[OcrLine] = []
    for line in lines:
        words = []
        for word in line.words:
            text = normalize_text(word.text)
            if word.confidence < min_confidence or _is_garbage(text, word.confidence):
                continue
            words.append(OcrWord(text, word.quad, word.confidence))
        if words:
            confidence = float(np.mean([word.confidence for word in words]))
            cleaned.append(OcrLine(words, confidence))
    return cleaned


def _box_quad(x0: float, y0: float, x1: float, y1: float) -> Quad:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def find_tesseract(configured: str = "") -> Path:
    """Lokalizuje plik wykonywalny Tesseract."""
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        raise OcrEngineError(f"Nie znaleziono programu Tesseract: {configured}")
    found = shutil.which("tesseract")
    if found:
        return Path(found)
    for candidate in TESSERACT_DEFAULT_PATHS:
        if candidate.is_file():
            return candidate
    raise OcrEngineError("Nie znaleziono programu Tesseract na serwerze.")


class TesseractOcrEngine(OcrEngine):
    """Silnik Tesseract (LSTM) z wykrywaniem orientacji modułem OSD."""

    prefers_binary_input = True

    def __init__(self, options: OcrOptions) -> None:
        self._executable = find_tesseract(options.tesseract_executable)
        self._language = options.language
        self._psm = options.page_segmentation_mode
        self._timeout = options.timeout_seconds
        self._environment = {**os.environ, "OMP_THREAD_LIMIT": "1"}

    def _run(self, image: np.ndarray, arguments: list[str]) -> subprocess.CompletedProcess[bytes]:
        ok, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        if not ok:
            raise OcrEngineError("Nie można zakodować obrazu strony dla Tesseract.")
        try:
            return subprocess.run(
                [str(self._executable), "stdin", "stdout", *arguments],
                input=encoded.tobytes(),
                capture_output=True,
                timeout=self._timeout,
                env=self._environment,
                creationflags=NO_WINDOW,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise OcrEngineError(f"Tesseract przekroczył limit czasu {self._timeout} s.") from error
        except OSError as error:
            raise OcrEngineError(f"Nie można uruchomić Tesseract: {error}") from error

    def recognize(self, image: np.ndarray, dpi: int) -> list[OcrLine]:
        """Rozpoznaje tekst i zwraca słowa z wyniku TSV."""
        completed = self._run(
            image, ["-l", self._language, "--oem", "1", "--psm", str(self._psm), "--dpi", str(dpi), "tsv"]
        )
        if completed.returncode != 0:
            message = completed.stderr.decode("utf-8", "replace").strip()
            raise OcrEngineError(f"Tesseract zakończył się błędem: {message}")
        return self.parse_tsv(completed.stdout.decode("utf-8", "replace"))

    @staticmethod
    def parse_tsv(content: str) -> list[OcrLine]:
        """Przetwarza wynik TSV Tesseract na wiersze i słowa."""
        reader = csv.DictReader(io.StringIO(content), delimiter="\t", quoting=csv.QUOTE_NONE)
        grouped: dict[tuple[str, str, str, str], list[OcrWord]] = {}
        for row in reader:
            if row.get("level") != "5":
                continue
            text = (row.get("text") or "").strip()
            confidence = float(row.get("conf") or -1)
            if not text or confidence < 0:
                continue
            left, top = float(row["left"]), float(row["top"])
            width, height = float(row["width"]), float(row["height"])
            key = (row["page_num"], row["block_num"], row["par_num"], row["line_num"])
            grouped.setdefault(key, []).append(
                OcrWord(text, _box_quad(left, top, left + width, top + height), confidence / 100)
            )
        return [OcrLine(words, float(np.mean([w.confidence for w in words]))) for words in grouped.values()]

    def detect_rotation(self, image: np.ndarray, dpi: int) -> int:
        """Wykrywa orientację modułem OSD Tesseract."""
        completed = self._run(image, ["--psm", "0", "--dpi", str(dpi)])
        output = completed.stdout.decode("utf-8", "replace")
        rotate = re.search(r"Rotate:\s*(\d+)", output)
        confidence = re.search(r"Orientation confidence:\s*([\d.]+)", output)
        if completed.returncode != 0 or not rotate or not confidence:
            return 0
        if float(confidence.group(1)) < OSD_MIN_CONFIDENCE:
            return 0
        return int(rotate.group(1)) % 360


def available_languages(executable: str = "") -> list[str]:
    """Języki zainstalowane w Tesseract (``--list-langs``)."""
    completed = subprocess.run(
        [str(find_tesseract(executable)), "--list-langs"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        creationflags=NO_WINDOW,
    )
    lines = completed.stdout.splitlines()[1:]
    return sorted(line.strip() for line in lines if line.strip() and line.strip() != "osd")


class OcrEngineFactory:
    """Dostarcza każdemu wątkowi roboczemu własną instancję silnika."""

    def __init__(self, options: OcrOptions) -> None:
        self._options = options
        self._local = threading.local()

    def engine(self) -> OcrEngine:
        """Zwraca silnik bieżącego wątku, tworząc go przy pierwszym użyciu."""
        engine = getattr(self._local, "engine", None)
        if engine is None:
            engine = TesseractOcrEngine(self._options)
            self._local.engine = engine
        return engine
