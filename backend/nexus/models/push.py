"""Subskrypcje powiadomień Web Push (przeglądarki i aplikacje zainstalowane jako PWA)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from nexus.db import Base, UtcDateTime, utcnow


class PushSubscription(Base):
    """Punkt odbioru powiadomień jednej przeglądarki (``PushSubscription.toJSON()``)."""

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    endpoint_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    endpoint: Mapped[str] = mapped_column(Text)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    last_sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
