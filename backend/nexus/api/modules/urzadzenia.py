"""Klucze urządzeń: aplikacja Android, Nexus Desktop, rozszerzenie przeglądarki.

Klucz tworzy zalogowany użytkownik (sesja przeglądarki); jest pokazywany tylko raz.
Urządzenie wysyła go w nagłówku ``Authorization: Bearer nxd_…``.

Okno aplikacji Android i Nexus Desktop zakłada klucz dla siebie z własnej sesji (ciasteczko
jak w przeglądarce). Klucz zapamiętuje tę sesję, a cofnięcie klucza ją kończy: zgubiony
telefon traci wtedy i klucz, i zalogowane okno, więc nie założy sobie nowego klucza.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from nexus.api.auth import COOKIE_NAME, DEVICE_TOKEN_PREFIX, require_session, token_hash, wlasciciel
from nexus.db import Database, DeviceToken, UserSession, utcnow

router = APIRouter(prefix="/api/urzadzenia", tags=["urzadzenia"], dependencies=[Depends(require_session)])


class NewDevice(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["android", "desktop", "rozszerzenie", "inne"] = "inne"
    # Formularz w module Sprzęt wydaje klucz dla innego urządzenia (rozszerzenie, klucz
    # wklejany w Nexus Desktop) — sesji przeglądarki, która go wydała, nie wiążemy, bo jego
    # cofnięcie wylogowałoby tę przeglądarkę. Okno aplikacji pola nie wysyła.
    dla_innego_urzadzenia: bool = False


def _require_browser_login(request: Request) -> None:
    # Nowe klucze wydaje wyłącznie zalogowana przeglądarka – nie inne urządzenie.
    if not request.cookies.get(COOKIE_NAME) or getattr(request.state, "device", None):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Klucze urządzeń zarządza się z zalogowanej przeglądarki."
        )


def _payload(record: DeviceToken, zywe_sesje: set[str] | None = None) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "name": record.name,
        "kind": record.kind,
        "created_at": record.created_at.isoformat(),
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
        "revoked": record.revoked,
        # Czy cofnięcie klucza wyloguje też okno aplikacji, które go założyło. Tylko wtedy,
        # gdy ta sesja jeszcze trwa: okno zalogowane ponownie po wygaśnięciu sesji (30 dni)
        # zatrzymuje stary klucz, a jego nowej sesji klucz nie zna — obietnica byłaby pusta.
        "wylogowuje_okno": record.sesja_hash is not None
        and (zywe_sesje is None or record.sesja_hash in zywe_sesje),
    }


@router.get("")
async def list_devices(
    request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> list[dict[str, Any]]:
    """Klucze urządzeń konta (bez samych kluczy)."""
    database: Database = request.app.state.database
    async with database.session() as session:
        rows = (
            await session.scalars(
                select(DeviceToken)
                .where(DeviceToken.owner_id == owner)
                .order_by(DeviceToken.created_at.desc())
            )
        ).all()
        zywe = set(
            (
                await session.scalars(
                    select(UserSession.token_hash).where(
                        UserSession.owner_id == owner, UserSession.expires_at > utcnow()
                    )
                )
            ).all()
        )
    return [_payload(row, zywe) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: NewDevice, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, Any]:
    """Tworzy klucz urządzenia konta; zwraca go jednorazowo w polu ``token``.

    Klucz urządzenia daje dostęp do rozmów i plików konta, więc musi mieć właściciela.
    Bez niego wpadałby domyślny administrator i telefon jednego użytkownika otwierałby
    cudzą przestrzeń.
    """
    _require_browser_login(request)
    token = DEVICE_TOKEN_PREFIX + secrets.token_urlsafe(32)
    sesja = None if payload.dla_innego_urzadzenia else token_hash(request.cookies[COOKIE_NAME])
    record = DeviceToken(
        token_hash=token_hash(token),
        owner_id=owner,
        name=payload.name.strip(),
        kind=payload.kind,
        sesja_hash=sesja,
    )
    database: Database = request.app.state.database
    async with database.session() as session:
        session.add(record)
    return {**_payload(record), "token": token}


@router.delete("/{device_id}")
async def revoke_device(
    device_id: uuid.UUID, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, bool]:
    """Cofa klucz urządzenia należący do konta i kończy sesję, z której go założono.

    Klucz bez zapamiętanej sesji (założony przed tą zmianą albo dla innego urządzenia)
    jest wyłącznie unieważniany, jak dotąd.
    """
    _require_browser_login(request)
    database: Database = request.app.state.database
    async with database.session() as session:
        record = await session.scalar(
            select(DeviceToken).where(DeviceToken.id == device_id, DeviceToken.owner_id == owner)
        )
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono urządzenia.")
        record.revoked = True
        if record.sesja_hash:
            await session.execute(
                delete(UserSession).where(
                    UserSession.token_hash == record.sesja_hash, UserSession.owner_id == owner
                )
            )
    return {"ok": True}
