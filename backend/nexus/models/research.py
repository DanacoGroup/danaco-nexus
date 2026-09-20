"""Tabele modułów Research i Baza wiedzy (kolekcje, źródła, notatki, raporty badań).

Treść źródeł i notatek jest indeksowana w Qdrant (``nexus.knowledge``); identyfikator
źródła lub notatki pełni w indeksie rolę ``file_id``, więc ``search_documents``
z listą identyfikatorów przeszukuje wybrane dokumenty bazy wiedzy.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from nexus.db import ADMIN_OWNER, Base, JsonType, UtcDateTime, utcnow


class KnowledgeCollection(Base):
    """Kolekcja bazy wiedzy (odpowiednik „Wisebase”): zbiór źródeł i notatek na jeden temat."""

    __tablename__ = "research_collections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Kolekcja należy do konta: baza wiedzy to prywatne dokumenty, a wyszukiwanie
    # semantyczne po cudzych materiałach byłoby wyciekiem tej samej klasy co cudza rozmowa.
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=lambda: ADMIN_OWNER, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class KnowledgeSource(Base):
    """Źródło w kolekcji: strona WWW, plik, praca naukowa albo wklejony tekst."""

    __tablename__ = "research_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_collections.id", ondelete="CASCADE"), index=True
    )
    # strona | plik | praca | tekst
    kind: Mapped[str] = mapped_column(String(20), default="strona")
    url: Mapped[str] = mapped_column(String(2000), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    # Metadane: opis, witryna, autorzy, DOI, rok, data publikacji, język, skrócenie treści.
    meta: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    index_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class KnowledgeNote(Base):
    """Notatka w kolekcji (własna albo agenta), opcjonalnie powiązana ze źródłem."""

    __tablename__ = "research_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_collections.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("research_sources.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class ResearchReport(Base):
    """Badanie (Deep Research / Scholar Research) prowadzone w osobnej rozmowie.

    Treścią raportu jest odpowiedź agenta w rozmowie ``conversation_id``.
    """

    __tablename__ = "research_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # deep | scholar
    kind: Mapped[str] = mapped_column(String(20), default="deep")
    question: Mapped[str] = mapped_column(Text)
    # quick | standard | deep
    depth: Mapped[str] = mapped_column(String(20), default="standard")
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("research_collections.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


# Kolumna dopisywana do istniejącej instalacji: kolekcje sprzed podziału na konta należą
# do administratora, tak samo jak jego rozmowy i pliki.
COLUMNS: list[tuple[str, str, str, str]] = [
    (
        "research_collections",
        "owner_id",
        "UUID NOT NULL DEFAULT '00000000-0000-0000-0000-0000000000a1'",
        "TEXT NOT NULL DEFAULT '00000000-0000-0000-0000-0000000000a1'",
    ),
]
