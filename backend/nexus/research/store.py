"""Operacje na bazie wiedzy wspólne dla API i narzędzi agenta.

Kolekcje, źródła i notatki są zapisywane w bazie danych, a ich treść indeksowana
w Qdrant (``KnowledgeBase``) pod identyfikatorem źródła lub notatki.
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import func, select

from nexus.config import Settings
from nexus.db import ADMIN_OWNER, Database, utcnow
from nexus.models.research import KnowledgeCollection, KnowledgeNote, KnowledgeSource
from nexus.research.web import extract_html, normalize_text

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "Ogólne"
MAX_CONTENT_CHARS = 2_000_000
EXCERPT_CHARS = 280
SOURCE_KINDS = ("strona", "plik", "praca", "tekst")


class Indexer(Protocol):
    """Część interfejsu ``KnowledgeBase`` używana przez bazę wiedzy."""

    def index(
        self,
        file_id: uuid.UUID,
        name: str,
        conversation_id: uuid.UUID | None,
        pages: list[tuple[int | None, str]],
    ) -> int: ...

    def delete(self, file_id: uuid.UUID) -> None: ...

    def search(
        self, query: str, limit: int = 8, file_ids: list[str] | None = None
    ) -> list[dict[str, Any]]: ...


MARKDOWN_MARKS = re.compile(r"(?m)^\s*(#{1,6}|[-*+>]|\d+[.)])\s+|\*\*|__|`")


def excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    """Początek treści w jednym wierszu (bez znaczników Markdown: nagłówków, punktorów, pogrubień)."""
    flat = " ".join(MARKDOWN_MARKS.sub(" ", text[: limit * 4]).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def collection_payload(record: KnowledgeCollection, sources: int = 0, notes: int = 0) -> dict[str, Any]:
    """Opis kolekcji dla interfejsu i narzędzi."""
    return {
        "id": str(record.id),
        "name": record.name,
        "description": record.description,
        "sources": sources,
        "notes": notes,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def source_payload(record: KnowledgeSource, full: bool = False) -> dict[str, Any]:
    """Opis źródła; ``full`` dołącza całą treść."""
    data: dict[str, Any] = {
        "id": str(record.id),
        "collection_id": str(record.collection_id),
        "kind": record.kind,
        "url": record.url,
        "title": record.title,
        "excerpt": excerpt((record.meta or {}).get("description") or record.content or ""),
        "chars": len(record.content or ""),
        "meta": record.meta or {},
        "file_id": str(record.file_id) if record.file_id else None,
        "indexed": record.indexed,
        "index_error": record.index_error,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
    if full:
        data["content"] = record.content
    return data


def note_payload(record: KnowledgeNote) -> dict[str, Any]:
    """Opis notatki (z treścią – notatki są krótkie)."""
    return {
        "id": str(record.id),
        "collection_id": str(record.collection_id),
        "source_id": str(record.source_id) if record.source_id else None,
        "title": record.title,
        "content": record.content,
        "indexed": record.indexed,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None or isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value).strip())
    except ValueError:
        return None


async def resolve_collection(
    database: Database,
    reference: str | uuid.UUID | None,
    create: bool = True,
    owner: uuid.UUID | None = None,
) -> KnowledgeCollection | None:
    """Kolekcja konta wskazana identyfikatorem albo nazwą (brak nazwy = kolekcja „Ogólne”).

    Wyszukiwanie po nazwie obejmuje wyłącznie kolekcje właściciela: dwa konta mogą mieć
    „Ogólne” i nie mogą na siebie trafić.
    """
    wlasciciel = owner or ADMIN_OWNER
    identifier = _uuid(reference)
    async with database.session() as session:
        if identifier is not None:
            found = await session.get(KnowledgeCollection, identifier)
            if found is not None and found.owner_id != wlasciciel:
                found = None
            if found is not None or not create:
                return found
        name = " ".join(str(reference or "").split())[:120] if identifier is None else ""
        name = name or DEFAULT_COLLECTION
        found = await session.scalar(
            select(KnowledgeCollection)
            .where(
                func.lower(KnowledgeCollection.name) == name.lower(),
                KnowledgeCollection.owner_id == wlasciciel,
            )
            .order_by(KnowledgeCollection.created_at)
            .limit(1)
        )
        if found is not None or not create:
            return found
        record = KnowledgeCollection(owner_id=wlasciciel, name=name)
        session.add(record)
    return record


async def collection_counts(database: Database) -> dict[uuid.UUID, tuple[int, int]]:
    """Liczba źródeł i notatek w każdej kolekcji."""
    async with database.session() as session:
        sources = dict(
            (
                await session.execute(
                    select(KnowledgeSource.collection_id, func.count()).group_by(
                        KnowledgeSource.collection_id
                    )
                )
            ).all()
        )
        notes = dict(
            (
                await session.execute(
                    select(KnowledgeNote.collection_id, func.count()).group_by(KnowledgeNote.collection_id)
                )
            ).all()
        )
    keys = set(sources) | set(notes)
    return {key: (sources.get(key, 0), notes.get(key, 0)) for key in keys}


async def save_source(
    database: Database,
    collection: KnowledgeCollection,
    *,
    kind: str,
    title: str,
    content: str,
    url: str = "",
    meta: dict[str, Any] | None = None,
    file_id: uuid.UUID | None = None,
) -> tuple[KnowledgeSource, bool]:
    """Zapisuje źródło; to samo źródło (adres lub plik) w kolekcji jest aktualizowane.

    Zwraca rekord i informację, czy powstał nowy.
    """
    content = (content or "")[:MAX_CONTENT_CHARS]
    title = " ".join((title or url or "Bez tytułu").split())[:500]
    async with database.session() as session:
        existing = None
        if url or file_id:
            condition = KnowledgeSource.url == url if url else KnowledgeSource.file_id == file_id
            existing = await session.scalar(
                select(KnowledgeSource)
                .where(KnowledgeSource.collection_id == collection.id, condition)
                .limit(1)
            )
        if existing is not None:
            existing.title = title
            existing.content = content
            existing.meta = {**(existing.meta or {}), **(meta or {})}
            existing.kind = kind
            existing.indexed = False
            existing.index_error = ""
            existing.updated_at = utcnow()
            session.add(existing)
            record, created = existing, False
        else:
            record = KnowledgeSource(
                collection_id=collection.id,
                kind=kind if kind in SOURCE_KINDS else "tekst",
                url=url[:2000],
                title=title,
                content=content,
                meta=meta or {},
                file_id=file_id,
            )
            session.add(record)
            created = True
        await session.flush()
        collection_record = await session.get(KnowledgeCollection, collection.id)
        if collection_record is not None:
            collection_record.updated_at = utcnow()
    return record, created


async def save_note(
    database: Database,
    collection: KnowledgeCollection,
    *,
    title: str,
    content: str,
    source_id: uuid.UUID | None = None,
) -> KnowledgeNote:
    """Zapisuje nową notatkę w kolekcji."""
    record = KnowledgeNote(
        collection_id=collection.id,
        source_id=source_id,
        title=" ".join((title or excerpt(content, 80) or "Notatka").split())[:300],
        content=content[:MAX_CONTENT_CHARS],
    )
    async with database.session() as session:
        session.add(record)
        collection_record = await session.get(KnowledgeCollection, collection.id)
        if collection_record is not None:
            collection_record.updated_at = utcnow()
    return record


def index_text(title: str, content: str, meta: dict[str, Any] | None = None) -> str:
    """Tekst indeksowany: tytuł, opis/autorzy i treść."""
    meta = meta or {}
    header = [title]
    if meta.get("authors"):
        header.append(", ".join(meta["authors"][:10]))
    if meta.get("description"):
        header.append(meta["description"])
    return "\n".join(part for part in header if part) + "\n\n" + (content or "")


async def index_entry(database: Database, knowledge: Indexer, model: type, entry_id: uuid.UUID) -> str:
    """Indeksuje źródło lub notatkę w Qdrant; zwraca opis błędu (pusty = sukces)."""
    async with database.session() as session:
        record = await session.get(model, entry_id)
    if record is None:
        return "Nie znaleziono wpisu."
    meta = getattr(record, "meta", None) or {}
    text = index_text(record.title, record.content, meta)
    error = ""
    try:
        chunks = await asyncio.to_thread(knowledge.index, record.id, record.title, None, [(None, text)])
        if chunks == 0:
            error = "Brak tekstu do zaindeksowania."
    except Exception as failure:  # noqa: BLE001 - niedostępna baza wektorowa nie blokuje zapisu
        logger.warning("Indeksowanie %s nie powiodło się: %s", entry_id, failure)
        error = f"Indeksowanie nie powiodło się: {failure}"[:500]
    async with database.session() as session:
        fresh = await session.get(model, entry_id)
        if fresh is not None:
            fresh.indexed = not error
            if isinstance(fresh, KnowledgeSource):
                fresh.index_error = error
            session.add(fresh)
    return error


async def forget_entries(knowledge: Indexer, entry_ids: list[uuid.UUID]) -> None:
    """Usuwa wpisy z indeksu Qdrant (błędy usługi są tylko logowane)."""
    if not entry_ids:
        return

    def run() -> None:
        for entry_id in entry_ids:
            try:
                knowledge.delete(entry_id)
            except Exception as failure:  # noqa: BLE001 - brak usługi nie blokuje usuwania
                logger.warning("Usuwanie z indeksu %s nie powiodło się: %s", entry_id, failure)

    await asyncio.to_thread(run)


def extract_file_text(settings: Settings, path: Path, name: str, mime: str) -> str:
    """Tekst pliku dodanego do bazy wiedzy (PDF, tekst, HTML; pozostałe przez Apache Tika)."""
    suffix = Path(name).suffix.lower()
    if mime == "application/pdf" or suffix == ".pdf":
        import pymupdf

        with pymupdf.open(path) as document:
            return normalize_text("\n\n".join(page.get_text("text") for page in document))
    if suffix in {".html", ".htm"} or mime in {"text/html", "application/xhtml+xml"}:
        return extract_html(path.read_text(encoding="utf-8", errors="replace"), "")["text"]
    if mime.startswith("text/") or suffix in {".txt", ".md", ".csv", ".json", ".xml", ".log"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if mime.startswith(("image/", "audio/", "video/")):
        raise ValueError(
            "Pliki obrazów, dźwięku i wideo nie zawierają tekstu – najpierw OCR lub transkrypcja."
        )
    from nexus.tools.base import FileRef, ToolContext
    from nexus.tools.files import _tika_text

    context = ToolContext(
        settings,
        uuid.uuid4(),
        resolve_file=lambda _id: None,
        cancel=threading.Event(),
        progress=lambda _t: None,
    )
    try:
        reference = FileRef(uuid.uuid4(), name, mime, path.stat().st_size, path, {})
        return normalize_text(_tika_text(context, reference))
    finally:
        context.cleanup()
