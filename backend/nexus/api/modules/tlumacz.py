"""Moduł Tłumacz: tłumaczenie tekstu (od razu) i dokumentów z zachowaniem układu (zadanie w tle)."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from nexus.api.auth import require_session
from nexus.tworczy import tlumaczenie
from nexus.tworczy.tlumaczenie import LANGUAGES, STYLES, ClaudeTranslator, TranslationError
from nexus.tworczy.zadania import job_registry, start_tool_job

router = APIRouter(prefix="/api/tlumacz", tags=["tlumacz"], dependencies=[Depends(require_session)])

MAX_TEXT_CHARS = 30_000
SINGLE_SEGMENT_CHARS = 5000


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    target: str = Field(min_length=2, max_length=8)
    source: str = Field("auto", max_length=8)
    style: str = Field("neutralny", max_length=20)
    glossary: str = Field("", max_length=4000)


class DocumentRequest(BaseModel):
    file_id: str
    target: str = Field(min_length=2, max_length=8)
    source: str = Field("auto", max_length=8)
    style: str = Field("neutralny", max_length=20)
    glossary: str = Field("", max_length=4000)


def split_text(text: str) -> list[str]:
    """Krótki tekst to jeden segment; długi – akapity z zachowanymi separatorami."""
    if len(text) <= SINGLE_SEGMENT_CHARS:
        return [text]
    return re.split(r"(\n\s*\n)", text)


def translator_for(request: Request, payload: TextRequest) -> ClaudeTranslator:
    """Tłumacz tekstu (w testach zastępowany atrapą)."""
    return ClaudeTranslator(
        request.app.state.settings, payload.target, payload.source, payload.style, payload.glossary
    )


@router.get("/jezyki")
async def languages() -> dict[str, Any]:
    """Obsługiwane języki i style tłumaczenia."""
    return {
        "languages": [{"code": code, "name": name} for code, name in LANGUAGES.items()],
        "styles": [{"id": key, "description": value} for key, value in STYLES.items()],
    }


@router.post("/tekst")
async def translate_text(payload: TextRequest, request: Request) -> dict[str, str]:
    """Tłumaczy tekst; zwraca tłumaczenie i wykryty język źródłowy."""
    try:
        translator = translator_for(request, payload)
        pieces = split_text(payload.text)
        translated = await asyncio.to_thread(translator, pieces)
    except TranslationError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    return {
        "translation": "".join(tlumaczenie.ANY_TAG.sub("", piece) for piece in translated),
        "source_language": translator.detected or (payload.source if payload.source != "auto" else ""),
    }


@router.post("/dokument", status_code=status.HTTP_202_ACCEPTED)
async def translate_document(payload: DocumentRequest, request: Request) -> dict[str, Any]:
    """Tłumaczy dokument (DOCX, PPTX, PDF, TXT, MD) z zachowaniem układu – zadanie w tle."""
    arguments = {
        "file_id": payload.file_id,
        "target_language": payload.target,
        "source_language": payload.source,
        "style": payload.style,
        "glossary": payload.glossary,
    }
    job = await start_tool_job(request, "translate_document", arguments, [payload.file_id])
    return job.payload()


@router.get("/zadania/{job_id}")
async def job_status(job_id: str, request: Request) -> dict[str, Any]:
    """Stan zadania tłumaczenia dokumentu."""
    return job_registry(request.app).get(job_id, (await require_session(request)).owner_id).payload()


@router.delete("/zadania/{job_id}")
async def cancel_job(job_id: str, request: Request) -> dict[str, Any]:
    """Anuluje tłumaczenie dokumentu."""
    return job_registry(request.app).cancel(job_id, (await require_session(request)).owner_id).payload()
