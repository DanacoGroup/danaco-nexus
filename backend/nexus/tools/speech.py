"""Transkrypcja nagrań audio i wideo (faster-whisper, model Whisper na CPU)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    registry,
    truncate_text,
)
from nexus.tools.common import file_kind, with_suffix

SCRIPT = Path(__file__).with_name("transkrypcja_proces.py")


def timestamp(seconds: float, separator: str = ",") -> str:
    """Znacznik czasu SRT/VTT, np. ``00:01:02,500``."""
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{milliseconds:03d}"


def to_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for index, segment in enumerate(segments, 1):
        blocks.append(
            f"{index}\n{timestamp(segment['start'])} --> {timestamp(segment['end'])}\n{segment['text']}\n"
        )
    return "\n".join(blocks)


def to_text(segments: list[dict[str, Any]], with_times: bool) -> str:
    if not with_times:
        return "\n".join(segment["text"] for segment in segments)
    return "\n".join(f"[{timestamp(segment['start'], '.')[:8]}] {segment['text']}" for segment in segments)


class TranscribeInput(ToolInput):
    file_id: str = Field(description="Nagranie audio lub wideo.")
    language: str = Field("pl", description="Kod języka mowy (np. 'pl', 'en') albo 'auto' – wykrycie.")
    formats: list[Literal["txt", "srt", "vtt"]] = Field(
        default_factory=lambda: ["txt"],
        description="Pliki wynikowe: txt (tekst ze znacznikami czasu), srt/vtt (napisy).",
    )


@registry.register(
    "transcribe_audio",
    """Zamienia mowę z nagrania audio lub wideo na tekst (Whisper): transkrypcja ze znacznikami
czasu, wykrycie języka, napisy SRT/VTT. Treść wraca do Ciebie, więc możesz ją streścić,
przetłumaczyć albo przygotować z niej notatkę czy protokół (write_document).""",
    TranscribeInput,
)
def transcribe_audio(ctx: ToolContext, args: TranscribeInput) -> ToolResult:
    settings = ctx.settings
    file = ctx.file(args.file_id)
    if file_kind(file) not in {"audio", "video"}:
        raise ToolError(f"{file.name} nie jest nagraniem audio ani wideo.")
    if (
        not Path(settings.whisper_python).is_file()
        or not (settings.whisper_model_dir / "model.bin").is_file()
    ):
        raise ToolError("Transkrypcja jest niedostępna (brak środowiska faster-whisper lub modelu).")
    language = args.language.strip().lower() or "auto"
    if language != "auto" and not language.isalpha():
        raise ToolError(f"Nieprawidłowy kod języka: {args.language}")
    ctx.progress("Transkrypcja nagrania…")
    completed = ctx.run_command(
        [
            settings.whisper_python,
            str(SCRIPT),
            str(settings.whisper_model_dir),
            str(file.path),
            language,
            str(max(1, settings.tool_threads)),
        ],
        timeout=4 * 3600,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ToolError("Transkrypcja zwróciła nieprawidłowy wynik.") from error
    segments = result.get("segments", [])
    outputs: list[OutputFile] = []
    for kind in dict.fromkeys(args.formats):
        if kind == "txt":
            content = to_text(segments, with_times=True)
        elif kind == "srt":
            content = to_srt(segments)
        else:
            content = "WEBVTT\n\n" + to_srt(segments).replace(",", ".")
        target = ctx.output_path(with_suffix(file.name, f".{kind}", "_transkrypcja"))
        target.write_text(content + "\n", encoding="utf-8")
        outputs.append(OutputFile(target, target.name, f"Transkrypcja ({kind.upper()})"))
    text, truncated = truncate_text(to_text(segments, with_times=True))
    data: dict[str, Any] = {
        "file": file.name,
        "language": result.get("language"),
        "language_probability": result.get("language_probability"),
        "duration_seconds": result.get("duration"),
        "segments": len(segments),
        "transcript": text,
    }
    if truncated:
        data["note"] = "Transkrypcja skrócona – pełna treść jest w pliku wynikowym."
    minutes = (result.get("duration") or 0) / 60
    return ToolResult(
        data,
        f"Transkrypcja {file.name}: {minutes:.1f} min, język {result.get('language')}, {len(segments)} fragmentów",
        files=outputs,
    )
