"""Tabele modułu biuro (Poczta, Kalendarz): działania czekające na zatwierdzenie użytkownika."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from nexus.db import Base, JsonType, UtcDateTime, utcnow


class PendingAction(Base):
    """Działanie przygotowane przez agenta, wykonywane dopiero po zatwierdzeniu w interfejsie.

    ``kind``: ``mail`` (wiadomość do wysłania) albo ``kalendarz_usun`` (usunięcie wydarzenia).
    ``status``: ``pending``, ``done``, ``cancelled`` albo ``failed``.
    """

    __tablename__ = "biuro_oczekujace"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    summary: Mapped[str] = mapped_column(String(300), default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
