"""Moduł Obrazy: usuwanie i zmiana tła, gumka obiektów, powiększanie AI – jako zadania w tle.

Operacje wywołują narzędzia agenta (``remove_background``, ``change_background``,
``erase_objects``, ``upscale_image``) bezpośrednio; wynik to nowy plik w magazynie.
"""

from __future__ import annotations

import base64
import binascii
import io
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from nexus.api.auth import require_session
from nexus.tools.base import FileRef
from nexus.tworczy.zadania import job_registry, start_tool_job

router = APIRouter(prefix="/api/obrazy", tags=["obrazy"], dependencies=[Depends(require_session)])

MAX_MASK_BYTES = 20 * 1024 * 1024


class ImageRequest(BaseModel):
    file_id: str
    fast: bool = False


class BackgroundRequest(BaseModel):
    file_id: str
    mode: Literal["color", "gradient", "image", "blur", "transparent"]
    color: str = "#ffffff"
    color2: str = "#e4e4e7"
    angle: float = Field(90, ge=0, le=360)
    background_file_id: str | None = None
    original_file_id: str | None = None
    blur_radius: float = Field(18, ge=1, le=120)
    fast: bool = False


class EraseRequest(BaseModel):
    file_id: str
    mask: str = Field(description="Maska PNG jako data URL (biel = usuń).", max_length=MAX_MASK_BYTES * 2)
    method: Literal["telea", "ns"] = "telea"
    radius: int = Field(9, ge=1, le=50)


class UpscaleRequest(BaseModel):
    file_id: str
    scale: Literal[2, 3, 4] = 2
    model: Literal["photo", "anime"] = "photo"


@router.get("/mozliwosci")
async def capabilities(request: Request) -> dict[str, bool]:
    """Dostępność programów zewnętrznych (rembg, Real-ESRGAN) na serwerze."""
    settings = request.app.state.settings
    return {
        "remove_background": Path(settings.tworczy_rembg_bin).is_file(),
        "upscale": (settings.realesrgan_dir / "realesrgan-ncnn-vulkan").is_file(),
    }


@router.post("/usun-tlo", status_code=status.HTTP_202_ACCEPTED)
async def remove_background(payload: ImageRequest, request: Request) -> dict[str, Any]:
    """Usuwa tło (PNG z przezroczystością)."""
    arguments = {"file_ids": [payload.file_id], "fast": payload.fast}
    job = await start_tool_job(request, "remove_background", arguments, [payload.file_id])
    return job.payload()


@router.post("/zmien-tlo", status_code=status.HTTP_202_ACCEPTED)
async def change_background(payload: BackgroundRequest, request: Request) -> dict[str, Any]:
    """Nowe tło: kolor, gradient, obraz, rozmycie albo przezroczystość."""
    arguments = payload.model_dump(exclude_none=True)
    file_ids = [
        value for value in (payload.file_id, payload.background_file_id, payload.original_file_id) if value
    ]
    job = await start_tool_job(request, "change_background", arguments, file_ids)
    return job.payload()


def _decode_mask(data_url: str, target: Path) -> None:
    _, _, encoded = data_url.partition("base64,")
    try:
        raw = base64.b64decode(encoded or data_url, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(422, "Nieprawidłowa maska.") from error
    if len(raw) > MAX_MASK_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Maska jest zbyt duża.")
    try:
        with Image.open(io.BytesIO(raw)) as mask:
            mask.load()
            if mask.width * mask.height > 60_000_000:
                raise HTTPException(422, "Maska ma zbyt duże wymiary.")
            target.parent.mkdir(parents=True, exist_ok=True)
            # Maska z płótna: przezroczystość = brak pociągnięcia pędzla.
            if mask.mode in ("RGBA", "LA") and mask.getchannel("A").getextrema() != (255, 255):
                grey = mask.getchannel("A")
            else:
                grey = mask.convert("L")
            grey.save(target, format="PNG")
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(422, "Maska nie jest obrazem PNG.") from error


@router.post("/gumka", status_code=status.HTTP_202_ACCEPTED)
async def erase(payload: EraseRequest, request: Request) -> dict[str, Any]:
    """Usuwa obiekty zamalowane na masce i odtwarza tło z otoczenia."""
    settings = request.app.state.settings
    mask_id = uuid.uuid4()
    mask_path = settings.work_dir / "tworczy-maski" / f"{mask_id.hex}.png"
    _decode_mask(payload.mask, mask_path)
    mask = FileRef(mask_id, "maska.png", "image/png", mask_path.stat().st_size, mask_path, {})
    arguments = {
        "file_id": payload.file_id,
        "mask_file_id": str(mask_id),
        "method": payload.method,
        "radius": payload.radius,
    }
    try:
        job = await start_tool_job(request, "erase_objects", arguments, [payload.file_id], extra_files=[mask])
    except BaseException:
        mask_path.unlink(missing_ok=True)
        raise
    return job.payload()


@router.post("/powieksz", status_code=status.HTTP_202_ACCEPTED)
async def upscale(payload: UpscaleRequest, request: Request) -> dict[str, Any]:
    """Powiększenie AI (Real-ESRGAN)."""
    arguments = {"file_ids": [payload.file_id], "scale": payload.scale, "model": payload.model}
    job = await start_tool_job(request, "upscale_image", arguments, [payload.file_id])
    return job.payload()


@router.get("/zadania/{job_id}")
async def job_status(job_id: str, request: Request) -> dict[str, Any]:
    """Stan zadania: running, done (z plikami wynikowymi), failed albo cancelled."""
    return job_registry(request.app).get(job_id).payload()


@router.delete("/zadania/{job_id}")
async def cancel_job(job_id: str, request: Request) -> dict[str, Any]:
    """Anuluje zadanie."""
    return job_registry(request.app).cancel(job_id).payload()
