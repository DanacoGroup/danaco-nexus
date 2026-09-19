"""Model danych i dostęp do bazy PostgreSQL (SQLAlchemy, asyncio).

Przechowywane są rozmowy, wiadomości w formacie Messages API, pliki,
zadania agenta (przebiegi), zdarzenia strumieniowane do interfejsu
oraz wywołania narzędzi.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonType = JSON().with_variant(JSONB(), "postgresql")
IdType = BigInteger().with_variant(Integer(), "sqlite")
SCHEMA_LOCK_ID = 7_314_225


def utcnow() -> datetime:
    """Bieżący czas UTC ze strefą."""
    return datetime.now(UTC)


class UtcDateTime(TypeDecorator[datetime]):
    """Znacznik czasu zawsze ze strefą UTC (SQLite zwraca wartości bez strefy)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    """Klasa bazowa modeli."""


class Setting(Base):
    """Ustawienie klucz–wartość (np. skrót hasła administratora)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class UserSession(Base):
    """Sesja zalogowanego administratora (przechowywany skrót tokenu)."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")


class Conversation(Base):
    """Rozmowa z asystentem."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), default="Nowa rozmowa")
    claude_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class Message(Base):
    """Wiadomość w formacie Messages API (lista bloków treści).

    ``kind`` rozróżnia wiadomość użytkownika (``user``), odpowiedź asystenta
    (``assistant``) i wyniki narzędzi (``tool_results``, rola ``user``).
    Historia jest wyłącznie dopisywana – wcześniejsze tury nie są zmieniane.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(IdType, primary_key=True, autoincrement=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    role: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))
    content: Mapped[list[dict[str, Any]]] = mapped_column(JsonType)
    meta: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class StoredFile(Base):
    """Plik przesłany przez użytkownika albo wytworzony przez narzędzie."""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    origin: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(300))
    mime: Mapped[str] = mapped_column(String(150))
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(300))
    meta: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class Run(Base):
    """Przebieg agenta obsługujący jedną wiadomość użytkownika (zadanie w kolejce)."""

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    worker_id: Mapped[str] = mapped_column(String(100), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    usage: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class RunEvent(Base):
    """Zdarzenie przebiegu przekazywane do interfejsu (strumień SSE)."""

    __tablename__ = "run_events"
    __table_args__ = (Index("ix_run_events_run_seq", "run_id", "id"),)

    id: Mapped[int] = mapped_column(IdType, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("runs.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(40))
    data: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class ToolCall(Base):
    """Wywołanie narzędzia przez agenta (historia zadań)."""

    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(IdType, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    tool_use_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(100))
    input: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="running")
    summary: Mapped[str] = mapped_column(Text, default="")
    output_file_ids: Mapped[list[str]] = mapped_column(JsonType, default=list)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)


class Database:
    """Silnik i fabryka sesji bazy danych."""

    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        """Tworzy brakujące tabele; w PostgreSQL pod blokadą doradczą (API i worker)."""
        async with self.engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                await connection.execute(text(f"SELECT pg_advisory_xact_lock({SCHEMA_LOCK_ID})"))
            await connection.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Sesja z automatycznym zatwierdzeniem albo wycofaniem."""
        async with self.sessions() as session:
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    async def close(self) -> None:
        """Zamyka pulę połączeń."""
        await self.engine.dispose()
