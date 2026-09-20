"""Tabele portalu produktowego: treści (blog, baza wiedzy, dokumentacja, strony),
konta klientów, sesje portalu, tokeny odzyskiwania hasła i potwierdzenia adresu
oraz wiadomości z formularza kontaktu.

Treść jest przechowywana w jednej tabeli z rozróżnieniem ``kind`` – wszystkie rodzaje mają ten sam
zestaw pól (slug, tytuł, zajawka, Markdown, autor, znaczniki, status, metadane SEO), więc osobne
tabele wymuszałyby powielanie zapytań listujących i wyszukiwania.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from nexus.db import Base, JsonType, UtcDateTime, utcnow

# Rodzaje treści portalu i dozwolone statusy publikacji.
RODZAJE = ("blog", "wiedza", "dokumentacja", "strona")
STATUSY = ("szkic", "opublikowany")

# Kolumna dochodzi do tabeli, która na wdrożonych instalacjach już istnieje – ``create_all``
# nie zmienia istniejących tabel, więc dopisuje ją ``Database.create_schema``.
COLUMNS: list[tuple[str, str, str, str]] = [
    ("portal_users", "email_confirmed_at", "TIMESTAMPTZ", "TIMESTAMP"),
]


class PortalContent(Base):
    """Pozycja treści portalu: wpis bloga, artykuł bazy wiedzy, strona dokumentacji lub statyczna."""

    __tablename__ = "portal_content"
    __table_args__ = (
        UniqueConstraint("kind", "slug", name="uq_portal_content_kind_slug"),
        Index("ix_portal_content_kind_status", "kind", "status"),
        Index("ix_portal_content_published", "status", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # blog | wiedza | dokumentacja | strona
    kind: Mapped[str] = mapped_column(String(20), index=True)
    slug: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(200))
    excerpt: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(120), default="")
    tags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    # szkic | opublikowany
    status: Mapped[str] = mapped_column(String(20), default="szkic", index=True)
    # Metadane SEO: {"meta_title", "meta_description", "og_image", "canonical", "noindex"}.
    seo: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    # Kolejność w spisie dokumentacji (mniejsza liczba = wyżej); pozostałe rodzaje sortują się datą.
    position: Mapped[int] = mapped_column(Integer, default=0)
    # Tytuł, zajawka, treść i znaczniki bez znaków diakrytycznych – podstawa wyszukiwania.
    search_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class PortalUser(Base):
    """Konto klienta portalu (rejestracja własna, hasło haszowane Argon2)."""

    __tablename__ = "portal_users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(120), default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    # Plan subskrypcji prezentowany w panelu klienta.
    plan: Mapped[str] = mapped_column(String(20), default="start")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Pusta wartość znaczy „adres niepotwierdzony”. Potwierdzenie niczego nie blokuje – konto
    # działa od razu, bo wysyłka poczty bywa nieskonfigurowana i klient nie dostałby odsyłacza.
    email_confirmed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class PortalSession(Base):
    """Sesja klienta portalu – w bazie wyłącznie skrót tokenu z ciasteczka ``HttpOnly``."""

    __tablename__ = "portal_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("portal_users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")


class PortalPasswordReset(Base):
    """Token odzyskiwania hasła o krótkim czasie życia (przechowywany jako skrót SHA-256)."""

    __tablename__ = "portal_password_resets"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("portal_users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class PortalEmailConfirmation(Base):
    """Token potwierdzenia adresu poczty (w bazie wyłącznie skrót SHA-256)."""

    __tablename__ = "portal_email_confirmations"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("portal_users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class PortalMessage(Base):
    """Wiadomość z formularza kontaktowego (odczytywana w panelu administratora)."""

    __tablename__ = "portal_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text)
    handled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, index=True)
