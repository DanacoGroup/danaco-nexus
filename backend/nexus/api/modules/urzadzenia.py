"""Klucze urządzeń: aplikacja Android, Nexus Desktop, rozszerzenie przeglądarki.

Klucz tworzy zalogowany użytkownik (sesja przeglądarki); jest pokazywany tylko raz.
Urządzenie wysyła go w nagłówku ``Authorization: Bearer nxd_…``.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from nexus.api.auth import COOKIE_NAME, DEVICE_TOKEN_PREFIX, require_session, token_hash
from nexus.db import Database, DeviceToken

router = APIRouter(prefix="/api/urzadzenia", tags=["urzadzenia"], dependencies=[Depends(require_session)])


class NewDevice(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["android", "desktop", "rozszerzenie", "inne"] = "inne"


def _require_browser_login(request: Request) -> None:
    # Nowe klucze wydaje wyłącznie zalogowana przeglądarka – nie inne urządzenie.
    if not request.cookies.get(COOKIE_NAME) or getattr(request.state, "device", None):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Klucze urządzeń zarządza się z zalogowanej przeglądarki."
        )


def _payload(record: DeviceToken) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "name": record.name,
        "kind": record.kind,
        "created_at": record.created_at.isoformat(),
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
        "revoked": record.revoked,
    }


@router.get("")
async def list_devices(request: Request) -> list[dict[str, Any]]:
    """Klucze urządzeń (bez samych kluczy)."""
    database: Database = request.app.state.database
    async with database.session() as session:
        rows = (await session.scalars(select(DeviceToken).order_by(DeviceToken.created_at.desc()))).all()
    return [_payload(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_device(payload: NewDevice, request: Request) -> dict[str, Any]:
    """Tworzy klucz urządzenia; zwraca go jednorazowo w polu ``token``."""
    _require_browser_login(request)
    token = DEVICE_TOKEN_PREFIX + secrets.token_urlsafe(32)
    record = DeviceToken(token_hash=token_hash(token), name=payload.name.strip(), kind=payload.kind)
    database: Database = request.app.state.database
    async with database.session() as session:
        session.add(record)
    return {**_payload(record), "token": token}


@router.delete("/{device_id}")
async def revoke_device(device_id: uuid.UUID, request: Request) -> dict[str, bool]:
    """Cofa klucz urządzenia."""
    _require_browser_login(request)
    database: Database = request.app.state.database
    async with database.session() as session:
        result = await session.execute(
            update(DeviceToken).where(DeviceToken.id == device_id).values(revoked=True)
        )
    if not result.rowcount:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono urządzenia.")
    return {"ok": True}
