"""API rozmowy głosowej: konfiguracja, rozpoznawanie mowy, synteza mowy."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from nexus.api.auth import require_session
from nexus.voice import VoiceEngine, VoiceUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"], dependencies=[Depends(require_session)])

MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_SPEAK_CHARS = 1200
CHUNK = 1024 * 1024


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SPEAK_CHARS)
    voice: str = Field("", max_length=80)
    speed: float = Field(1.0, ge=0.5, le=2.0)


def _engine(request: Request) -> VoiceEngine:
    return request.app.state.voice


@router.get("/config")
async def voice_config(request: Request) -> dict[str, Any]:
    """Dostępność rozmowy głosowej i lista głosów."""
    engine = _engine(request)
    voices = engine.voices()
    return {
        "available": engine.stt_available() and bool(voices),
        "voices": voices,
        "default_voice": engine.default_voice(),
    }


@router.post("/transcribe")
async def transcribe(
    request: Request, audio: UploadFile = File(...), language: str = Form("pl")
) -> dict[str, Any]:
    """Rozpoznaje nagraną wypowiedź."""
    if not language.isalpha() and language != "auto":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nieprawidłowy kod języka.")
    suffix = Path(audio.filename or "nagranie.webm").suffix[:8] or ".webm"
    settings = request.app.state.settings
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=suffix, dir=settings.work_dir) as handle:
        size = 0
        while chunk := await audio.read(CHUNK):
            size += len(chunk)
            if size > MAX_AUDIO_BYTES:
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Nagranie jest za długie.")
            handle.write(chunk)
        handle.flush()
        try:
            result = await asyncio.to_thread(_engine(request).transcribe, Path(handle.name), language)
        except VoiceUnavailable as error:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
        except Exception:  # noqa: BLE001 - zbyt krótkie albo uszkodzone nagranie to „brak mowy”
            logger.warning("Nie udało się odczytać nagrania (%d B)", size, exc_info=True)
            return {"text": "", "language": language, "duration": 0.0}
    return {"text": result.text, "language": result.language, "duration": result.duration}


@router.post("/speak")
async def speak(payload: SpeakRequest, request: Request) -> Response:
    """Czyta tekst wybranym głosem (WAV)."""
    try:
        audio = await asyncio.to_thread(_engine(request).speak, payload.text, payload.voice, payload.speed)
    except VoiceUnavailable as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
