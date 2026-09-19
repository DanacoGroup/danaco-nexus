"""Parametry procesu OCR dobierane przez agenta dla konkretnego zadania."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from nexus.ocr.models import ExportFormat

THRESHOLD_MODES: tuple[str, ...] = ("auto", "always", "never")


@dataclass(slots=True)
class PreprocessingSettings:
    """Wstępne przetwarzanie obrazu przed OCR.

    ``adaptive_threshold``: ``auto`` (progowanie dla Tesseract), ``always``
    albo ``never``.
    """

    rotation_detection: bool = True
    deskew: bool = True
    denoise: bool = True
    contrast_enhancement: bool = True
    adaptive_threshold: str = "auto"
    border_crop: bool = True


@dataclass(slots=True)
class OcrOptions:
    """Ustawienia jednego zlecenia OCR."""

    language: str = "pol+eng"
    render_dpi: int = 300
    min_confidence: float = 0.5
    formats: list[ExportFormat] = field(default_factory=lambda: [ExportFormat.PDF])
    force_ocr: bool = False
    rotate_pages: bool = True
    image_default_dpi: int = 300
    threads: int = 0
    tesseract_executable: str = ""
    page_segmentation_mode: int = 3
    timeout_seconds: int = 300
    preprocessing: PreprocessingSettings = field(default_factory=PreprocessingSettings)

    def thread_count(self) -> int:
        """Liczba równoległych procesów Tesseract."""
        if self.threads > 0:
            return self.threads
        return max(1, min(8, (os.cpu_count() or 2) // 2))
