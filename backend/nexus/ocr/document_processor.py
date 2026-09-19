"""Przetwarzanie pojedynczego dokumentu: analiza, OCR stron, eksport.

Strony są renderowane w wątku koordynującym (PyMuPDF nie jest bezpieczny
wątkowo), a przygotowanie obrazu i OCR wykonują wątki puli. Liczba stron
przechowywanych jednocześnie w pamięci jest ograniczona oknem
``2 × liczba wątków``, a wyniki trafiają do eksporterów w kolejności stron,
co utrzymuje stałe zużycie pamięci niezależnie od liczby stron.
"""

from __future__ import annotations

import logging
import tempfile
import threading
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path

import numpy as np

from nexus.ocr.exporter import DocxExporter, PageSink, SearchablePdfExporter, TxtExporter
from nexus.ocr.image_processor import ImageProcessor, map_points
from nexus.ocr.models import (
    DocumentResult,
    DocumentStatus,
    ExportFormat,
    OcrLine,
    OcrPageResult,
    OcrWord,
    PageContent,
    ProgressEvent,
)
from nexus.ocr.ocr_engine import OcrEngineFactory, clean_lines
from nexus.ocr.options import OcrOptions
from nexus.ocr.pdf_processor import (
    PageAnalysis,
    analyze_document,
    build_image_container,
    find_text_layer_font,
    open_pdf,
    render_page_gray,
    strip_invisible_text,
)

logger = logging.getLogger(__name__)

MAX_IMAGE_RENDER_DPI = 400
MESSAGE_TEXT_LAYER_PRESENT = "PDF zawiera już warstwę tekstową. Pominięto OCR."


class ProcessingCancelled(Exception):
    """Przetwarzanie przerwane na żądanie."""


class DocumentProcessor:
    """Wykonuje pełny proces OCR jednego dokumentu."""

    def __init__(
        self,
        options: OcrOptions,
        engine_factory: OcrEngineFactory,
        executor: ThreadPoolExecutor,
        worker_count: int,
    ) -> None:
        self._options = options
        self._engines = engine_factory
        self._executor = executor
        self._window = max(2, worker_count * 2)

    def process(
        self,
        source: Path,
        is_image: bool,
        targets: dict[ExportFormat, Path],
        cancel: threading.Event,
        on_progress: Callable[[ProgressEvent], None],
    ) -> DocumentResult:
        """Przetwarza dokument i zwraca podsumowanie (nie zgłasza wyjątków)."""
        started = time.perf_counter()
        result = DocumentResult(source, DocumentStatus.PROCESSING)
        try:
            with tempfile.TemporaryDirectory(prefix="nexus_ocr_") as temporary:
                self._run(source, is_image, targets, Path(temporary), cancel, on_progress, result)
        except ProcessingCancelled:
            result.status = DocumentStatus.CANCELLED
            result.message = "Przetwarzanie anulowane."
            result.outputs.clear()
        except Exception as error:  # noqa: BLE001 - błąd dokumentu nie przerywa partii
            logger.exception("Błąd OCR pliku %s", source)
            result.status = DocumentStatus.FAILED
            result.message = str(error) or error.__class__.__name__
            result.outputs.clear()
        result.seconds = time.perf_counter() - started
        logger.info(
            "OCR: %s | status: %s | stron: %d | OCR: %d | czas: %.2f s | %s",
            source.name,
            result.status.value,
            result.pages_total,
            result.pages_ocr,
            result.seconds,
            result.message,
        )
        return result

    def _run(
        self,
        source: Path,
        is_image: bool,
        targets: dict[ExportFormat, Path],
        temporary: Path,
        cancel: threading.Event,
        on_progress: Callable[[ProgressEvent], None],
        result: DocumentResult,
    ) -> None:
        options = self._options
        if not source.is_file():
            raise FileNotFoundError(f"Plik nie istnieje: {source}")
        base = source
        image_dpis: list[float] | None = None
        if is_image:
            base = temporary / "image_container.pdf"
            image_dpis = build_image_container(source, base, options.image_default_dpi)

        pdf = open_pdf(base)
        try:
            if image_dpis is not None:
                analyses = [PageAnalysis(i, True, False, False, "") for i in range(pdf.page_count)]
            else:
                analyses = analyze_document(pdf, options.force_ocr)
            result.pages_total = len(analyses)
            ocr_pages = [item.index for item in analyses if item.needs_ocr]
            if not ocr_pages:
                result.status = DocumentStatus.SKIPPED
                result.message = MESSAGE_TEXT_LAYER_PRESENT
                return
            stale_layers = [item.index for item in analyses if item.needs_ocr and item.invisible_text_only]
            if stale_layers:
                stripped = temporary / "without_old_text_layer.pdf"
                strip_invisible_text(base, stale_layers, stripped)
                base = stripped

            sinks = self._create_sinks(targets, base)
            try:
                self._process_pages(
                    pdf,
                    analyses,
                    image_dpis,
                    sinks,
                    cancel,
                    lambda done: on_progress(ProgressEvent(source, done, len(ocr_pages))),
                )
                outputs = [sink.finish() for sink in sinks]
            except BaseException:
                for sink in sinks:
                    sink.abort()
                raise
        finally:
            pdf.close()

        result.outputs = outputs
        result.pages_ocr = len(ocr_pages)
        result.status = DocumentStatus.DONE
        skipped = result.pages_total - result.pages_ocr
        result.message = f"Pominięto {skipped} stron z istniejącą warstwą tekstową." if skipped else ""

    def _create_sinks(self, targets: dict[ExportFormat, Path], base: Path) -> list[PageSink]:
        """Tworzy eksportery dla wskazanych formatów."""
        sinks: list[PageSink] = []
        for export_format, target in targets.items():
            if export_format is ExportFormat.PDF:
                sinks.append(
                    SearchablePdfExporter(base, target, find_text_layer_font(), self._options.rotate_pages)
                )
            elif export_format is ExportFormat.TXT:
                sinks.append(TxtExporter(target))
            else:
                sinks.append(DocxExporter(target))
        return sinks

    def _process_pages(
        self,
        pdf: object,
        analyses: list[PageAnalysis],
        image_dpis: list[float] | None,
        sinks: list[PageSink],
        cancel: threading.Event,
        on_done: Callable[[int], None],
    ) -> None:
        """Renderuje strony, zleca OCR i przekazuje wyniki eksporterom w kolejności."""
        pending: dict[Future[OcrPageResult], int] = {}
        ready: dict[int, PageContent] = {}
        next_page = 0
        done = 0

        def collect(block: bool) -> None:
            nonlocal done
            if not pending:
                return
            finished, _ = wait(list(pending), timeout=None if block else 0, return_when=FIRST_COMPLETED)
            for future in finished:
                index = pending.pop(future)
                try:
                    page_result = future.result()
                except ProcessingCancelled:
                    raise
                except Exception as error:
                    raise RuntimeError(f"Strona {index + 1}: {error}") from error
                ready[index] = PageContent(index, ocr=page_result)
                done += 1
                on_done(done)

        def flush() -> None:
            nonlocal next_page
            while next_page in ready:
                content = ready.pop(next_page)
                for sink in sinks:
                    sink.add_page(content)
                next_page += 1

        try:
            for analysis in analyses:
                if cancel.is_set():
                    raise ProcessingCancelled
                if not analysis.needs_ocr:
                    ready[analysis.index] = PageContent(analysis.index, existing_text=analysis.existing_text)
                    flush()
                    continue
                while len(pending) >= self._window:
                    collect(block=True)
                    flush()
                    if cancel.is_set():
                        raise ProcessingCancelled
                dpi = self._render_dpi(analysis.index, image_dpis)
                image = render_page_gray(pdf, analysis.index, dpi)  # type: ignore[arg-type]
                future = self._executor.submit(self._ocr_page, analysis.index, image, dpi, cancel)
                pending[future] = analysis.index
                collect(block=False)
                flush()
            while pending:
                collect(block=True)
                flush()
                if cancel.is_set():
                    raise ProcessingCancelled
        except BaseException:
            for future in pending:
                future.cancel()
            raise

    def _render_dpi(self, index: int, image_dpis: list[float] | None) -> int:
        """Rozdzielczość renderowania strony.

        Dla plików graficznych: rozdzielczość natywna, podniesiona do
        ustawionej minimalnej i ograniczona do ``MAX_IMAGE_RENDER_DPI``.
        """
        configured = self._options.render_dpi
        if image_dpis is None:
            return configured
        native = int(round(image_dpis[index]))
        return min(max(native, configured), max(configured, MAX_IMAGE_RENDER_DPI))

    def _ocr_page(self, index: int, image: np.ndarray, dpi: int, cancel: threading.Event) -> OcrPageResult:
        """Przygotowuje obraz i rozpoznaje tekst jednej strony (wątek puli)."""
        if cancel.is_set():
            raise ProcessingCancelled
        started = time.perf_counter()
        engine = self._engines.engine()
        options = self._options
        processor = ImageProcessor(options.preprocessing, engine, engine.prefers_binary_input)
        prepared = processor.prepare(image, dpi)
        del image
        lines = clean_lines(engine.recognize(prepared.image, dpi), options.min_confidence)
        to_points = np.diag([72.0 / dpi, 72.0 / dpi, 1.0]) @ prepared.to_upright
        mapped = [
            OcrLine([self._map_word(word, to_points) for word in line.words], line.confidence)
            for line in lines
        ]
        width_px, height_px = prepared.upright_size
        return OcrPageResult(
            page_index=index,
            width=width_px * 72.0 / dpi,
            height=height_px * 72.0 / dpi,
            rotation=prepared.rotation,
            skew_angle=prepared.skew_angle,
            lines=mapped,
            ocr_seconds=time.perf_counter() - started,
        )

    @staticmethod
    def _map_word(word: OcrWord, matrix: np.ndarray) -> OcrWord:
        points = map_points(matrix, np.asarray(word.quad, dtype=np.float64))
        quad = tuple((float(x), float(y)) for x, y in points)
        return OcrWord(word.text, quad, word.confidence)  # type: ignore[arg-type]


def run_ocr(
    source: Path,
    is_image: bool,
    targets: dict[ExportFormat, Path],
    options: OcrOptions,
    cancel: threading.Event | None = None,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> DocumentResult:
    """Wykonuje OCR jednego dokumentu z własną pulą wątków."""
    workers = options.thread_count()
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ocr") as executor:
        processor = DocumentProcessor(options, OcrEngineFactory(options), executor, workers)
        return processor.process(
            source, is_image, targets, cancel or threading.Event(), on_progress or (lambda _event: None)
        )
