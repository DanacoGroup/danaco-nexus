"""Narzędzie audio i wideo (FFmpeg)."""

from __future__ import annotations

import re
from typing import Literal

from PIL import Image
from pydantic import Field

from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    image_preview,
    registry,
)
from nexus.tools.common import file_kind, with_suffix

TIME = re.compile(r"^\d{1,2}(:\d{2}){0,2}(\.\d+)?$")


class MediaInput(ToolInput):
    file_id: str = Field(description="Plik audio lub wideo.")
    operation: Literal[
        "convert", "extract_audio", "trim", "compress_video", "thumbnail", "normalize_audio", "resize_video"
    ] = Field(description="Operacja.")
    target_format: Literal["mp4", "webm", "mp3", "wav", "m4a", "ogg", "flac", "gif", "jpg"] | None = Field(
        None, description="Format wyniku (dla convert/extract_audio)."
    )
    start: str | None = Field(None, description="Początek fragmentu (trim/thumbnail), np. '00:01:30'.")
    end: str | None = Field(None, description="Koniec fragmentu (trim), np. '00:02:10'.")
    height: int | None = Field(None, ge=144, le=4320, description="Wysokość wideo (resize_video).")
    quality: Literal["high", "medium", "small"] = Field("medium", description="Kompromis jakość/rozmiar.")


@registry.register(
    "media_process",
    """Tnie, konwertuje i odchudza nagrania dźwiękowe oraz filmy.
Zmienia format, wyciąga ścieżkę dźwiękową, wycina fragment, kompresuje i skaluje wideo,
wyrównuje głośność (EBU R128) i zapisuje klatkę podglądu (FFmpeg).""",
    MediaInput,
)
def media_process(ctx: ToolContext, args: MediaInput) -> ToolResult:
    file = ctx.file(args.file_id)
    if file_kind(file) not in {"audio", "video"}:
        raise ToolError(f"{file.name} nie jest plikiem audio/wideo.")
    for value in (args.start, args.end):
        if value and not TIME.match(value):
            raise ToolError(f"Nieprawidłowy czas: {value}")
    crf = {"high": "20", "medium": "26", "small": "32"}[args.quality]
    source = str(file.path)
    command = ["ffmpeg", "-hide_banner", "-y"]
    if args.operation == "thumbnail":
        target = ctx.output_path(with_suffix(file.name, ".jpg", "_klatka"))
        command += ["-ss", args.start or "00:00:01", "-i", source, "-frames:v", "1", "-q:v", "2", str(target)]
    elif args.operation == "extract_audio":
        extension = args.target_format or "mp3"
        target = ctx.output_path(with_suffix(file.name, f".{extension}", "_audio"))
        command += ["-i", source, "-vn"] + (["-q:a", "2"] if extension == "mp3" else []) + [str(target)]
    elif args.operation == "trim":
        if not args.start and not args.end:
            raise ToolError("Podaj start i/lub end fragmentu.")
        extension = args.target_format or file.suffix.lstrip(".")
        target = ctx.output_path(with_suffix(file.name, f".{extension}", "_fragment"))
        window = (["-ss", args.start] if args.start else []) + (["-to", args.end] if args.end else [])
        codecs = ["-c:v", "libx264", "-crf", crf, "-c:a", "aac"] if file_kind(file) == "video" else []
        command += ["-i", source, *window, *codecs, str(target)]
    elif args.operation in {"compress_video", "resize_video"}:
        target = ctx.output_path(with_suffix(file.name, ".mp4", "_skompresowane"))
        scale = ["-vf", f"scale=-2:{args.height}"] if args.height else []
        command += [
            "-i",
            source,
            *scale,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            crf,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(target),
        ]
    elif args.operation == "normalize_audio":
        target = ctx.output_path(with_suffix(file.name, file.suffix or ".mp3", "_znormalizowane"))
        command += ["-i", source, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "copy", str(target)]
    else:
        extension = args.target_format or ("mp4" if file_kind(file) == "video" else "mp3")
        target = ctx.output_path(with_suffix(file.name, f".{extension}"))
        extra = ["-vf", "fps=10,scale=640:-2"] if extension == "gif" else []
        command += ["-i", source, *extra, str(target)]
    ctx.progress(f"FFmpeg: {args.operation} {file.name}")
    ctx.run_command(command, timeout=3600)
    images = []
    if target.suffix == ".jpg":
        images.append(image_preview(Image.open(target), 1024))
    return ToolResult(
        {"output": target.name, "operation": args.operation},
        f"FFmpeg ({args.operation}): {file.name}",
        images=images,
        files=[OutputFile(target, target.name, f"{args.operation} {file.name}")],
    )
