"""Szkielet narzędzi agenta: kontekst wykonania, wynik, rejestr.

Każde narzędzie deklaruje model wejścia (pydantic), z którego powstaje
schemat JSON przekazywany do Claude, oraz funkcję wykonującą pracę
synchronicznie (w wątku puli). Pliki są wskazywane identyfikatorami;
narzędzie nigdy nie przyjmuje ścieżek z zewnątrz.
"""

from __future__ import annotations

import io
import logging
import shutil
import subprocess
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import BaseModel, ConfigDict, ValidationError

from nexus.config import Settings
from nexus.db import ADMIN_OWNER

logger = logging.getLogger(__name__)

PREVIEW_MAX_SIDE = 1280
PREVIEW_MAX_IMAGES = 6
MAX_TEXT_RESULT = 60_000


class ToolError(Exception):
    """Błąd narzędzia opisany dla modelu (zwracany jako ``is_error``)."""


class ToolCancelled(Exception):
    """Zadanie anulowane przez użytkownika."""


class ToolInput(BaseModel):
    """Bazowy model wejścia narzędzia (bez pól nadmiarowych)."""

    model_config = ConfigDict(extra="forbid")


@dataclass(slots=True)
class FileRef:
    """Plik dostępny dla narzędzia."""

    id: uuid.UUID
    name: str
    mime: str
    size: int
    path: Path
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def suffix(self) -> str:
        """Rozszerzenie nazwy pliku (małe litery)."""
        return Path(self.name).suffix.lower()


@dataclass(slots=True)
class OutputFile:
    """Plik wynikowy przygotowany przez narzędzie (jeszcze poza magazynem)."""

    path: Path
    name: str
    description: str = ""


@dataclass(slots=True)
class ToolResult:
    """Wynik narzędzia: dane dla modelu, podglądy obrazów i pliki wynikowe."""

    data: dict[str, Any] | str
    summary: str
    images: list[bytes] = field(default_factory=list)
    files: list[OutputFile] = field(default_factory=list)


class ToolContext:
    """Środowisko wykonania narzędzia w ramach jednego przebiegu agenta."""

    def __init__(
        self,
        settings: Settings,
        run_id: uuid.UUID,
        resolve_file: Callable[[uuid.UUID], FileRef],
        cancel: threading.Event,
        progress: Callable[[str], None],
        mark_indexed: Callable[[uuid.UUID], None] | None = None,
        owner_id: uuid.UUID | None = None,
    ) -> None:
        self.settings = settings
        self.run_id = run_id
        # Konto, w którego przestrzeni pracuje narzędzie: skrzynka pocztowa, chmura
        # i baza wiedzy należą do konta użytkownika, nie do serwera.
        self.owner_id = owner_id or ADMIN_OWNER
        self._resolve_file = resolve_file
        self.cancel = cancel
        self._progress = progress
        self._mark_indexed = mark_indexed
        settings.work_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir = Path(tempfile.mkdtemp(prefix=f"run_{run_id.hex[:8]}_", dir=settings.work_dir))

    def file(self, file_id: str) -> FileRef:
        """Plik rozmowy o podanym identyfikatorze."""
        try:
            parsed = uuid.UUID(str(file_id))
        except ValueError as error:
            raise ToolError(f"Nieprawidłowy identyfikator pliku: {file_id}") from error
        return self._resolve_file(parsed)

    def output_path(self, name: str) -> Path:
        """Ścieżka nowego pliku wynikowego w katalogu roboczym przebiegu."""
        directory = Path(tempfile.mkdtemp(dir=self.work_dir))
        return directory / name

    def progress(self, message: str) -> None:
        """Przekazuje do interfejsu krótki komunikat o postępie."""
        self._progress(message)

    def mark_indexed(self, file_id: uuid.UUID) -> None:
        """Odnotowuje zaindeksowanie pliku w bazie wiedzy."""
        if self._mark_indexed is not None:
            self._mark_indexed(file_id)

    def check_cancelled(self) -> None:
        """Przerywa pracę, gdy użytkownik anulował zadanie."""
        if self.cancel.is_set():
            raise ToolCancelled

    def run_command(
        self,
        arguments: list[str],
        timeout: int = 600,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Uruchamia program zewnętrzny (bez powłoki) z limitem czasu.

        Proces jest przerywany także po anulowaniu zadania.
        """
        self.check_cancelled()
        executable = shutil.which(arguments[0]) or arguments[0]
        process = subprocess.Popen(
            [executable, *arguments[1:]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        waited = 0.0
        while True:
            try:
                stdout, stderr = process.communicate(timeout=1.0)
                break
            except subprocess.TimeoutExpired:
                waited += 1.0
                if self.cancel.is_set() or waited >= timeout:
                    process.kill()
                    process.communicate()
                    if self.cancel.is_set():
                        raise ToolCancelled from None
                    raise ToolError(f"Program {arguments[0]} przekroczył limit czasu {timeout} s.") from None
        result = subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)
        if result.returncode != 0:
            tail = (stderr or stdout or "").strip()[-1500:]
            raise ToolError(f"Program {arguments[0]} zakończył się błędem ({result.returncode}): {tail}")
        return result

    def cleanup(self) -> None:
        """Usuwa katalog roboczy przebiegu."""
        shutil.rmtree(self.work_dir, ignore_errors=True)


ToolHandler = Callable[[ToolContext, Any], ToolResult]


@dataclass(slots=True)
class Tool:
    """Definicja narzędzia."""

    name: str
    description: str
    input_model: type[ToolInput]
    handler: ToolHandler

    def definition(self) -> dict[str, Any]:
        """Definicja narzędzia (nazwa, opis, schemat JSON parametrów)."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": clean_schema(self.input_model.model_json_schema()),
        }

    def parse(self, raw: Any) -> ToolInput:
        """Waliduje wejście (przy strumieniowaniu wejścia API go nie sprawdza)."""
        if not isinstance(raw, dict):
            raise ToolError("Wejście narzędzia musi być obiektem JSON.")
        try:
            return self.input_model.model_validate(raw)
        except ValidationError as error:
            details = "; ".join(
                f"{'.'.join(str(p) for p in item['loc'])}: {item['msg']}" for item in error.errors()[:8]
            )
            raise ToolError(f"Nieprawidłowe parametry narzędzia: {details}") from error


def clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Usuwa ze schematu pydantic pola nieistotne dla modelu (tytuły)."""
    if isinstance(schema, dict):
        return {key: clean_schema(value) for key, value in schema.items() if key != "title"}
    if isinstance(schema, list):
        return [clean_schema(item) for item in schema]  # type: ignore[return-value]
    return schema


class ToolRegistry:
    """Zbiór narzędzi w stałej kolejności (stabilny prefiks pamięci podręcznej)."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self, name: str, description: str, input_model: type[ToolInput]
    ) -> Callable[[ToolHandler], ToolHandler]:
        """Dekorator rejestrujący funkcję jako narzędzie."""

        def decorator(handler: ToolHandler) -> ToolHandler:
            if name in self._tools:
                raise ValueError(f"Narzędzie {name} jest już zarejestrowane.")
            self._tools[name] = Tool(name, description.strip(), input_model, handler)
            return handler

        return decorator

    def get(self, name: str) -> Tool:
        """Narzędzie o podanej nazwie."""
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"Nieznane narzędzie: {name}")
        return tool

    def names(self) -> list[str]:
        """Nazwy narzędzi."""
        return sorted(self._tools)

    def definitions(self) -> list[dict[str, Any]]:
        """Definicje wszystkich narzędzi posortowane po nazwie."""
        return [self._tools[name].definition() for name in sorted(self._tools)]


registry = ToolRegistry()


def image_preview(image: Image.Image, max_side: int = PREVIEW_MAX_SIDE) -> bytes:
    """Podgląd obrazu w formacie JPEG dla modelu."""
    preview = image.copy()
    if preview.mode not in ("RGB", "L"):
        preview = preview.convert("RGB")
    preview.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    preview.save(buffer, format="JPEG", quality=82, optimize=True)
    return buffer.getvalue()


def truncate_text(text: str, limit: int = MAX_TEXT_RESULT) -> tuple[str, bool]:
    """Skraca długi tekst wyniku; zwraca tekst i informację o skróceniu."""
    if len(text) <= limit:
        return text, False
    return text[:limit], True
