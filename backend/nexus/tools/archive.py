"""Narzędzia archiwów ZIP: tworzenie i bezpieczne rozpakowanie."""

from __future__ import annotations

import zipfile
from pathlib import PurePosixPath

from pydantic import Field

from nexus.storage import safe_filename
from nexus.tools.base import OutputFile, ToolContext, ToolError, ToolInput, ToolResult, registry
from nexus.tools.common import unique_name

MAX_EXTRACT_FILES = 2000
MAX_EXTRACT_BYTES = 8 * 1024**3
MAX_COMPRESSION_RATIO = 200


class CreateArchiveInput(ToolInput):
    file_ids: list[str] = Field(min_length=1, max_length=1000, description="Pliki do spakowania.")
    name: str = Field("archiwum.zip", description="Nazwa archiwum.")


class ExtractArchiveInput(ToolInput):
    file_id: str = Field(description="Archiwum ZIP.")


@registry.register(
    "create_archive",
    """Pakuje wskazane pliki do archiwum ZIP (np. wszystkie wyniki zadania do pobrania naraz).""",
    CreateArchiveInput,
)
def create_archive(ctx: ToolContext, args: CreateArchiveInput) -> ToolResult:
    name = safe_filename(args.name, "archiwum.zip")
    if not name.lower().endswith(".zip"):
        name += ".zip"
    target = ctx.output_path(name)
    used: set[str] = set()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file_id in args.file_ids:
            ctx.check_cancelled()
            file = ctx.file(file_id)
            archive.write(file.path, arcname=unique_name(safe_filename(file.name), used))
    return ToolResult(
        {"output": target.name, "files": len(args.file_ids)},
        f"Utworzono archiwum {target.name} ({len(args.file_ids)} plików)",
        files=[OutputFile(target, target.name, "Archiwum ZIP")],
    )


@registry.register(
    "extract_archive",
    """Rozpakowuje archiwum ZIP i wkłada każdy plik osobno do rozmowy.
Rozpakowane pliki możesz od razu przetwarzać dalej (np. OCR wsadowy dokumentów z archiwum).""",
    ExtractArchiveInput,
)
def extract_archive(ctx: ToolContext, args: ExtractArchiveInput) -> ToolResult:
    file = ctx.file(args.file_id)
    outputs: list[OutputFile] = []
    used: set[str] = set()
    try:
        archive = zipfile.ZipFile(file.path)
    except zipfile.BadZipFile as error:
        raise ToolError(f"{file.name} nie jest poprawnym archiwum ZIP: {error}") from error
    with archive:
        entries = [info for info in archive.infolist() if not info.is_dir()]
        if len(entries) > MAX_EXTRACT_FILES:
            raise ToolError(f"Archiwum zawiera {len(entries)} plików (limit {MAX_EXTRACT_FILES}).")
        total = sum(info.file_size for info in entries)
        if total > MAX_EXTRACT_BYTES:
            raise ToolError("Rozpakowana zawartość przekracza limit 8 GB.")
        for info in entries:
            ctx.check_cancelled()
            if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                raise ToolError(f"Podejrzany współczynnik kompresji pliku {info.filename} (bomba ZIP).")
            parts = PurePosixPath(info.filename.replace("\\", "/")).parts
            if any(part == ".." for part in parts):
                continue
            display = " - ".join(parts) if len(parts) > 1 else parts[-1]
            target = ctx.output_path(unique_name(safe_filename(display), used))
            with archive.open(info) as source, target.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            outputs.append(OutputFile(target, target.name, f"Z archiwum {file.name}"))
    return ToolResult(
        {"extracted": [f.name for f in outputs]},
        f"Rozpakowano {len(outputs)} plików z {file.name}",
        files=outputs,
    )
