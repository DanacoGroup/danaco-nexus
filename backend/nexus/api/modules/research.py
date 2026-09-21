"""API modułów Research (Deep Research, Scholar Research) i Baza wiedzy (Wisebase).

Kolekcje, źródła (strony, pliki, prace, teksty) i notatki; zapis strony po adresie;
wyszukiwanie semantyczne w kolekcji; badania prowadzone w rozmowach w trybie ``research``
i rozmowy z wybranymi dokumentami bazy wiedzy.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from nexus.api.auth import require_session, wlasciciel
from nexus.api.conversations import ACTIVE_STATUSES, SendMessage, send_message
from nexus.db import Conversation, Database, Message, Run, StoredFile, utcnow
from nexus.models.research import KnowledgeCollection, KnowledgeNote, KnowledgeSource, ResearchReport
from nexus.research import store
from nexus.research.web import FetchError, fetch_page
from nexus.storage import FileStorage

_dziennik = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"], dependencies=[Depends(require_session)])

DEPTHS: dict[str, str] = {
    "quick": "szybka – 4–6 źródeł, jedna runda wyszukiwania, zwięzły raport",
    "standard": "standardowa – 10–15 źródeł, 2–3 rundy wyszukiwania, pełny raport",
    "deep": "dogłębna – 25+ źródeł, wiele rund i podagenci równolegle, obszerny raport z analizą",
}
KIND_NAMES = {"deep": "Deep Research", "scholar": "Scholar Research"}
DEFAULT_CHAT_QUESTION = (
    "Przejrzyj wybrane dokumenty i przygotuj krótkie streszczenie najważniejszych informacji z każdego."
)


# --- Modele wejścia -----------------------------------------------------------------------------


class CollectionInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=2000)


class CollectionPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)


class SourceInput(BaseModel):
    url: str = Field("", max_length=2000)
    file_id: uuid.UUID | None = None
    title: str = Field("", max_length=500)
    content: str = Field("", max_length=2_000_000)


class SourcePatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    collection_id: uuid.UUID | None = None


class NoteInput(BaseModel):
    title: str = Field("", max_length=300)
    content: str = Field(min_length=1, max_length=500_000)
    source_id: uuid.UUID | None = None


class NotePatch(BaseModel):
    title: str | None = Field(None, max_length=300)
    content: str | None = Field(None, min_length=1, max_length=500_000)


class PreviewInput(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class ResearchInput(BaseModel):
    question: str = Field(min_length=3, max_length=5000)
    kind: Literal["deep", "scholar"] = "deep"
    depth: Literal["quick", "standard", "deep"] = "standard"
    collection_id: uuid.UUID | None = None
    save_sources: bool = True


class ChatInput(BaseModel):
    source_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    note_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    collection_id: uuid.UUID | None = None
    question: str = Field("", max_length=20_000)


# --- Pomocnicze ---------------------------------------------------------------------------------


def _database(request: Request) -> Database:
    return request.app.state.database


async def _get(database: Database, model: type, entry_id: uuid.UUID, missing: str) -> Any:
    async with database.session() as session:
        record = await session.get(model, entry_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, missing)
    return record


async def _collection(
    database: Database, collection_id: uuid.UUID, owner: uuid.UUID | None = None
) -> KnowledgeCollection:
    """Kolekcja bazy wiedzy należąca do konta; cudza daje 404 jak nieistniejąca."""
    record = await _get(database, KnowledgeCollection, collection_id, "Nie znaleziono kolekcji.")
    if owner is not None and record.owner_id != owner:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono kolekcji.")
    return record


def _schedule_index(request: Request, tasks: BackgroundTasks, model: type, entry_id: uuid.UUID) -> None:
    tasks.add_task(store.index_entry, _database(request), request.app.state.knowledge, model, entry_id)


async def _fetch(request: Request, url: str) -> Any:
    settings = request.app.state.settings
    try:
        return await asyncio.to_thread(
            fetch_page,
            url,
            max_bytes=settings.research_page_max_mb * 1024 * 1024,
            max_chars=settings.research_page_max_chars,
            timeout=settings.research_fetch_timeout_s,
        )
    except FetchError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error


# --- Kolekcje -----------------------------------------------------------------------------------


@router.get("/kolekcje")
async def list_collections(
    request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> list[dict[str, Any]]:
    """Kolekcje konta od ostatnio zmienionej, z liczbą źródeł i notatek."""
    database = _database(request)
    counts = await store.collection_counts(database)
    async with database.session() as session:
        rows = (
            await session.scalars(
                select(KnowledgeCollection)
                .where(KnowledgeCollection.owner_id == owner)
                .order_by(KnowledgeCollection.updated_at.desc())
            )
        ).all()
    return [store.collection_payload(row, *counts.get(row.id, (0, 0))) for row in rows]


@router.post("/kolekcje", status_code=status.HTTP_201_CREATED)
async def create_collection(
    payload: CollectionInput, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, Any]:
    """Tworzy kolekcję na koncie zalogowanego użytkownika."""
    record = KnowledgeCollection(
        owner_id=owner,
        name=" ".join(payload.name.split()),
        description=payload.description.strip(),
    )
    async with _database(request).session() as session:
        session.add(record)
    return store.collection_payload(record)


@router.patch("/kolekcje/{collection_id}")
async def update_collection(
    collection_id: uuid.UUID,
    payload: CollectionPatch,
    request: Request,
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Zmienia nazwę lub opis kolekcji."""
    database = _database(request)
    async with database.session() as session:
        record = await session.get(KnowledgeCollection, collection_id)
        if record is None or record.owner_id != owner:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono kolekcji.")
        if payload.name is not None:
            record.name = " ".join(payload.name.split())
        if payload.description is not None:
            record.description = payload.description.strip()
        record.updated_at = utcnow()
    counts = (await store.collection_counts(database)).get(collection_id, (0, 0))
    return store.collection_payload(record, *counts)


@router.delete("/kolekcje/{collection_id}")
async def delete_collection(
    collection_id: uuid.UUID, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, bool]:
    """Usuwa kolekcję z jej źródłami i notatkami (także z indeksu)."""
    database = _database(request)
    await _collection(database, collection_id, owner)
    async with database.session() as session:
        source_ids = list(
            await session.scalars(
                select(KnowledgeSource.id).where(KnowledgeSource.collection_id == collection_id)
            )
        )
        note_ids = list(
            await session.scalars(
                select(KnowledgeNote.id).where(KnowledgeNote.collection_id == collection_id)
            )
        )
        await session.execute(delete(KnowledgeNote).where(KnowledgeNote.collection_id == collection_id))
        await session.execute(delete(KnowledgeSource).where(KnowledgeSource.collection_id == collection_id))
        await session.execute(delete(KnowledgeCollection).where(KnowledgeCollection.id == collection_id))
    await store.forget_entries(request.app.state.knowledge, source_ids + note_ids)
    return {"ok": True}


# --- Źródła -------------------------------------------------------------------------------------


@router.get("/kolekcje/{collection_id}/zrodla")
async def list_sources(
    collection_id: uuid.UUID, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> list[dict[str, Any]]:
    """Źródła kolekcji (bez pełnej treści)."""
    database = _database(request)
    await _collection(database, collection_id, owner)
    async with database.session() as session:
        rows = (
            await session.scalars(
                select(KnowledgeSource)
                .where(KnowledgeSource.collection_id == collection_id)
                .order_by(KnowledgeSource.created_at.desc())
            )
        ).all()
    return [store.source_payload(row) for row in rows]


@router.post("/kolekcje/{collection_id}/zrodla", status_code=status.HTTP_201_CREATED)
async def add_source(
    collection_id: uuid.UUID,
    payload: SourceInput,
    request: Request,
    tasks: BackgroundTasks,
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Dodaje źródło: stronę po adresie, przesłany plik albo wklejony tekst; indeksuje w tle."""
    database = _database(request)
    collection = await _collection(database, collection_id, owner)
    meta: dict[str, Any] = {"saved_by": "user"}
    if payload.file_id is not None:
        record = await _get(database, StoredFile, payload.file_id, "Nie znaleziono pliku.")
        storage: FileStorage = request.app.state.storage
        path = storage.path_of(record)
        if not path.is_file():
            raise HTTPException(status.HTTP_410_GONE, "Plik nie jest już dostępny.")
        try:
            content = await asyncio.to_thread(
                store.extract_file_text, request.app.state.settings, path, record.name, record.mime
            )
        except Exception as error:  # noqa: BLE001 - komunikat dla użytkownika
            # Wyjątek biblioteki potrafi nieść ścieżkę pliku na dysku serwera; do rozmowy
            # wraca sama informacja, że z tego pliku nie da się wyciągnąć tekstu.
            _dziennik.warning("nie udało się odczytać tekstu pliku %s: %s", record.name, error)
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Nie udało się odczytać tekstu z tego pliku. Sprawdź, czy nie jest uszkodzony "
                "albo zabezpieczony hasłem.",
            ) from error
        if not content.strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Plik nie zawiera tekstu (skan? – najpierw wykonaj OCR).",
            )
        meta.update({"file_name": record.name, "mime": record.mime, "size": record.size})
        source, _created = await store.save_source(
            database,
            collection,
            kind="plik",
            title=payload.title or record.name,
            content=content,
            meta=meta,
            file_id=record.id,
        )
    elif payload.url.strip():
        page = await _fetch(request, payload.url.strip())
        meta.update(
            {
                key: value
                for key, value in {
                    "description": page.description,
                    "site_name": page.site_name,
                    "author": page.author,
                    "published": page.published,
                    "language": page.language,
                    "final_url": page.final_url if page.final_url != payload.url.strip() else "",
                    "truncated": page.truncated,
                }.items()
                if value
            }
        )
        source, _created = await store.save_source(
            database,
            collection,
            kind="strona",
            title=payload.title or page.title,
            content=page.text,
            url=payload.url.strip(),
            meta=meta,
        )
    elif payload.content.strip():
        source, _created = await store.save_source(
            database, collection, kind="tekst", title=payload.title or "", content=payload.content, meta=meta
        )
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Podaj adres strony, plik albo treść.")
    _schedule_index(request, tasks, KnowledgeSource, source.id)
    return store.source_payload(source)


@router.get("/zrodla/{source_id}")
async def get_source(source_id: uuid.UUID, request: Request) -> dict[str, Any]:
    """Źródło z pełną treścią."""
    record = await _get(_database(request), KnowledgeSource, source_id, "Nie znaleziono źródła.")
    return store.source_payload(record, full=True)


@router.patch("/zrodla/{source_id}")
async def update_source(
    source_id: uuid.UUID,
    payload: SourcePatch,
    request: Request,
    tasks: BackgroundTasks,
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Zmienia tytuł źródła lub przenosi je do innej kolekcji."""
    database = _database(request)
    if payload.collection_id is not None:
        await _collection(database, payload.collection_id, owner)
    async with database.session() as session:
        record = await session.get(KnowledgeSource, source_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono źródła.")
        if payload.title is not None:
            record.title = " ".join(payload.title.split())
        if payload.collection_id is not None:
            record.collection_id = payload.collection_id
        record.updated_at = utcnow()
    if payload.title is not None:
        _schedule_index(request, tasks, KnowledgeSource, source_id)
    return store.source_payload(record)


@router.post("/zrodla/{source_id}/indeksuj", status_code=status.HTTP_202_ACCEPTED)
async def reindex_source(source_id: uuid.UUID, request: Request, tasks: BackgroundTasks) -> dict[str, bool]:
    """Ponawia indeksowanie źródła (np. po niedostępności bazy wektorowej)."""
    await _get(_database(request), KnowledgeSource, source_id, "Nie znaleziono źródła.")
    _schedule_index(request, tasks, KnowledgeSource, source_id)
    return {"ok": True}


@router.delete("/zrodla/{source_id}")
async def delete_source(source_id: uuid.UUID, request: Request) -> dict[str, bool]:
    """Usuwa źródło (i jego indeks); plik źródła usuwa, gdy nie należy do żadnej rozmowy."""
    database = _database(request)
    record = await _get(database, KnowledgeSource, source_id, "Nie znaleziono źródła.")
    storage: FileStorage = request.app.state.storage
    async with database.session() as session:
        await session.execute(delete(KnowledgeSource).where(KnowledgeSource.id == source_id))
        if record.file_id is not None:
            stored = await session.get(StoredFile, record.file_id)
            in_use = await session.scalar(
                select(func.count())
                .select_from(KnowledgeSource)
                .where(KnowledgeSource.file_id == record.file_id)
            )
            if stored is not None and stored.conversation_id is None and not in_use:
                storage.delete(stored)
                await session.delete(stored)
    await store.forget_entries(request.app.state.knowledge, [source_id])
    return {"ok": True}


# --- Notatki ------------------------------------------------------------------------------------


@router.get("/kolekcje/{collection_id}/notatki")
async def list_notes(
    collection_id: uuid.UUID, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> list[dict[str, Any]]:
    """Notatki kolekcji od ostatnio zmienionej."""
    database = _database(request)
    await _collection(database, collection_id, owner)
    async with database.session() as session:
        rows = (
            await session.scalars(
                select(KnowledgeNote)
                .where(KnowledgeNote.collection_id == collection_id)
                .order_by(KnowledgeNote.updated_at.desc())
            )
        ).all()
    return [store.note_payload(row) for row in rows]


@router.post("/kolekcje/{collection_id}/notatki", status_code=status.HTTP_201_CREATED)
async def add_note(
    collection_id: uuid.UUID,
    payload: NoteInput,
    request: Request,
    tasks: BackgroundTasks,
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Dodaje notatkę do kolekcji."""
    database = _database(request)
    collection = await _collection(database, collection_id, owner)
    if payload.source_id is not None:
        await _get(database, KnowledgeSource, payload.source_id, "Nie znaleziono źródła.")
    note = await store.save_note(
        database, collection, title=payload.title, content=payload.content, source_id=payload.source_id
    )
    _schedule_index(request, tasks, KnowledgeNote, note.id)
    return store.note_payload(note)


@router.patch("/notatki/{note_id}")
async def update_note(
    note_id: uuid.UUID, payload: NotePatch, request: Request, tasks: BackgroundTasks
) -> dict[str, Any]:
    """Zmienia tytuł lub treść notatki."""
    async with _database(request).session() as session:
        record = await session.get(KnowledgeNote, note_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono notatki.")
        if payload.title is not None:
            record.title = " ".join(payload.title.split()) or record.title
        if payload.content is not None:
            record.content = payload.content
        record.indexed = False
        record.updated_at = utcnow()
    _schedule_index(request, tasks, KnowledgeNote, note_id)
    return store.note_payload(record)


@router.delete("/notatki/{note_id}")
async def delete_note(note_id: uuid.UUID, request: Request) -> dict[str, bool]:
    """Usuwa notatkę."""
    database = _database(request)
    await _get(database, KnowledgeNote, note_id, "Nie znaleziono notatki.")
    async with database.session() as session:
        await session.execute(delete(KnowledgeNote).where(KnowledgeNote.id == note_id))
    await store.forget_entries(request.app.state.knowledge, [note_id])
    return {"ok": True}


# --- Wyszukiwanie i podgląd ---------------------------------------------------------------------


@router.get("/szukaj")
async def search(
    request: Request,
    q: str,
    collection_id: uuid.UUID | None = None,
    limit: int = 12,
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Wyszukiwanie semantyczne w bazie wiedzy konta (całej albo jednej kolekcji).

    Zakres wyznaczają dwie niezależne granice: lista wpisów z bazy relacyjnej zawężona
    do kolekcji właściciela i warunek na koncie w samym indeksie wektorowym. Jedna
    z nich by wystarczyła, ale indeks jest wspólny dla instalacji i nie chcę, żeby
    rozdzielenie kont zależało od poprawności jednego zapytania.
    """
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Zapytanie jest zbyt krótkie.")
    database = _database(request)
    if collection_id is not None:
        await _collection(database, collection_id, owner)
    async with database.session() as session:
        source_query = (
            select(KnowledgeSource.id, KnowledgeSource.title, KnowledgeSource.collection_id)
            .join(KnowledgeCollection, KnowledgeCollection.id == KnowledgeSource.collection_id)
            .where(KnowledgeCollection.owner_id == owner)
        )
        note_query = (
            select(KnowledgeNote.id, KnowledgeNote.title, KnowledgeNote.collection_id)
            .join(KnowledgeCollection, KnowledgeCollection.id == KnowledgeNote.collection_id)
            .where(KnowledgeCollection.owner_id == owner)
        )
        if collection_id is not None:
            source_query = source_query.where(KnowledgeSource.collection_id == collection_id)
            note_query = note_query.where(KnowledgeNote.collection_id == collection_id)
        entries = {
            str(row[0]): ("source", row[1], row[2]) for row in (await session.execute(source_query)).all()
        }
        entries.update(
            {str(row[0]): ("note", row[1], row[2]) for row in (await session.execute(note_query)).all()}
        )
    if not entries:
        return {"query": query, "results": []}
    try:
        hits = await asyncio.to_thread(
            request.app.state.knowledge.search, query, max(1, min(limit, 30)), list(entries), owner
        )
    except Exception as error:  # noqa: BLE001 - usługa wektorowa niedostępna
        # Treść wyjątku zostaje w dzienniku serwera. Wcześniej szła wprost do odpowiedzi,
        # więc użytkownik dostawał komunikat biblioteki razem z adresem i portem usługi
        # wektorowej — a i tak nie było to nic, co mógłby z tym zrobić.
        _dziennik.warning("wyszukiwanie w bazie wektorowej nie powiodło się: %s", error)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Wyszukiwanie po znaczeniu jest chwilowo niedostępne. Spróbuj ponownie za chwilę.",
        ) from error
    results = []
    for hit in hits:
        entry = entries.get(str(hit.get("file_id")))
        if entry is None:
            continue
        kind, title, owner = entry
        results.append(
            {
                "id": str(hit.get("file_id")),
                "type": kind,
                "title": title,
                "collection_id": str(owner),
                "score": hit.get("score"),
                "text": hit.get("text", ""),
            }
        )
    return {"query": query, "results": results}


@router.post("/podglad")
async def preview(payload: PreviewInput, request: Request) -> dict[str, Any]:
    """Pobiera stronę do podglądu (bez zapisu) – widok źródła obok raportu."""
    page = await _fetch(request, payload.url)
    data = page.as_dict()
    data["text"] = data["text"][:60_000]
    return data


# --- Badania (Deep Research / Scholar Research) -------------------------------------------------


def research_prompt(payload: ResearchInput, collection: KnowledgeCollection | None) -> str:
    """Wiadomość rozpoczynająca badanie: parametry i pytanie użytkownika."""
    lines = [
        f"[Research: {KIND_NAMES[payload.kind]} | głębokość: {DEPTHS[payload.depth]}]",
    ]
    if payload.kind == "scholar":
        lines.append(
            "[Tylko prace naukowe: scholar_search / scholar_paper; cytowania APA; "
            "lista „Bibliografia” na końcu.]"
        )
    else:
        lines.append(
            "[Raport w Markdown z przypisami [1], [2]… w tekście i numerowaną listą „Źródła” na końcu "
            "(- [n] Tytuł – adres).]"
        )
    if collection is not None and payload.save_sources:
        lines.append(
            f"[Zapisuj wykorzystane źródła w bazie wiedzy (knowledge_save) w kolekcji "
            f"„{collection.name}” (collection: {collection.id}).]"
        )
    lines.append("")
    lines.append(payload.question.strip())
    return "\n".join(lines)


def _report_title(kind: str, question: str) -> str:
    # Tytuł widzi użytkownik, a produkt jest po polsku. Dotyczy nowych raportów;
    # wcześniejsze zachowują swój tytuł, bo to dane, nie etykieta interfejsu.
    prefix = "Badanie sieci" if kind == "deep" else "Prace naukowe"
    flat = " ".join(question.split())
    title = f"{prefix}: {flat}"
    return title if len(title) <= 120 else title[:117].rstrip() + "…"


async def _latest_runs(database: Database, conversation_ids: list[uuid.UUID]) -> dict[uuid.UUID, Run]:
    if not conversation_ids:
        return {}
    async with database.session() as session:
        runs = (
            await session.scalars(
                select(Run).where(Run.conversation_id.in_(conversation_ids)).order_by(Run.created_at)
            )
        ).all()
    latest: dict[uuid.UUID, Run] = {}
    for run in runs:
        latest[run.conversation_id] = run
    return latest


def report_payload(report: ResearchReport, run: Run | None, title: str = "") -> dict[str, Any]:
    """Opis badania z bieżącym stanem zadania."""
    return {
        "id": str(report.id),
        "conversation_id": str(report.conversation_id),
        "kind": report.kind,
        "question": report.question,
        "depth": report.depth,
        "collection_id": str(report.collection_id) if report.collection_id else None,
        "title": title,
        "status": run.status if run else "done",
        "run_id": str(run.id) if run else None,
        "error": run.error if run else "",
        "created_at": report.created_at.isoformat(),
    }


@router.post("/badania", status_code=status.HTTP_201_CREATED)
async def start_research(
    payload: ResearchInput, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, Any]:
    """Rozpoczyna badanie: rozmowa w trybie ``research`` i pytanie wysłane do agenta."""
    database = _database(request)
    collection = None
    if payload.collection_id is not None:
        collection = await _collection(database, payload.collection_id, owner)
    elif payload.save_sources:
        collection = await store.resolve_collection(database, "Research", owner=owner)
    meta: dict[str, Any] = {"mode": "research", "depth": payload.depth, "research_kind": payload.kind}
    if collection is not None and payload.save_sources:
        meta["collection_id"] = str(collection.id)
    conversation = Conversation(
        id=uuid.uuid4(),
        owner_id=owner,
        title=_report_title(payload.kind, payload.question),
        meta=meta,
    )
    report = ResearchReport(
        conversation_id=conversation.id,
        kind=payload.kind,
        question=payload.question.strip(),
        depth=payload.depth,
        collection_id=collection.id if collection is not None else None,
    )
    async with database.session() as session:
        session.add(conversation)
        await session.flush()
        session.add(report)
    sent = await send_message(
        conversation.id, SendMessage(text=research_prompt(payload, collection)), request, owner
    )
    return {
        **report_payload(report, None, conversation.title),
        "status": "queued",
        "run_id": sent["run_id"],
    }


@router.get("/badania")
async def list_research(request: Request) -> list[dict[str, Any]]:
    """Badania od najnowszego ze stanem ostatniego zadania."""
    database = _database(request)
    async with database.session() as session:
        rows = (
            await session.execute(
                select(ResearchReport, Conversation.title)
                .join(Conversation, Conversation.id == ResearchReport.conversation_id)
                .order_by(ResearchReport.created_at.desc())
                .limit(300)
            )
        ).all()
    runs = await _latest_runs(database, [row[0].conversation_id for row in rows])
    return [report_payload(report, runs.get(report.conversation_id), title) for report, title in rows]


def report_text(messages: list[Message], run_id: uuid.UUID | None) -> str:
    """Tekst odpowiedzi agenta w danym zadaniu (bloki tekstu w kolejności)."""
    parts: list[str] = []
    for message in messages:
        if message.kind != "assistant" or message.run_id != run_id:
            continue
        for block in message.content:
            if block.get("type") == "text" and block.get("text"):
                parts.append(block["text"])
    return "\n\n".join(parts)


@router.get("/badania/{report_id}")
async def get_research(report_id: uuid.UUID, request: Request) -> dict[str, Any]:
    """Badanie z treścią raportu (ostatnia odpowiedź agenta zawierająca tekst)."""
    database = _database(request)
    report = await _get(database, ResearchReport, report_id, "Nie znaleziono badania.")
    async with database.session() as session:
        conversation = await session.get(Conversation, report.conversation_id)
        messages = (
            await session.scalars(
                select(Message).where(Message.conversation_id == report.conversation_id).order_by(Message.id)
            )
        ).all()
        runs = (
            await session.scalars(
                select(Run).where(Run.conversation_id == report.conversation_id).order_by(Run.created_at)
            )
        ).all()
    latest = runs[-1] if runs else None
    text = ""
    for run in reversed(runs):
        text = report_text(list(messages), run.id)
        if text:
            break
    data = report_payload(report, latest, conversation.title if conversation else "")
    data["report"] = text
    data["active"] = bool(latest and latest.status in ACTIVE_STATUSES)
    return data


@router.delete("/badania/{report_id}")
async def delete_research(report_id: uuid.UUID, request: Request) -> dict[str, bool]:
    """Usuwa badanie z listy (rozmowa z raportem pozostaje w historii czatu)."""
    database = _database(request)
    await _get(database, ResearchReport, report_id, "Nie znaleziono badania.")
    async with database.session() as session:
        await session.execute(delete(ResearchReport).where(ResearchReport.id == report_id))
    return {"ok": True}


# --- Rozmowa z wybranymi dokumentami ------------------------------------------------------------


def chat_prompt(question: str, sources: list[KnowledgeSource], notes: list[KnowledgeNote]) -> str:
    """Pierwsza wiadomość rozmowy z dokumentami: spis dokumentów i sposób korzystania z nich."""
    lines = ["[Rozmowa z dokumentami z bazy wiedzy]"]
    for source in sources:
        where = f" | {source.url}" if source.url else ""
        size = f"{len(source.content)} znaków"
        lines.append(f"- source_id: {source.id} | {source.kind} | „{source.title}”{where} | {size}")
    for note in notes:
        lines.append(f"- note_id: {note.id} | notatka | „{note.title}”")
    ids = [str(source.id) for source in sources] + [str(note.id) for note in notes]
    lines.append(
        "[Odpowiadaj na podstawie tych dokumentów: treść czytaj knowledge_read (source_id / note_id), "
        "a fragmenty wyszukuj search_documents z file_ids = "
        + ", ".join(ids)
        + ". Wskazuj, z którego dokumentu pochodzi informacja; "
        "jeśli dokumenty czegoś nie mówią – powiedz to.]"
    )
    lines.append("")
    lines.append(question.strip() or DEFAULT_CHAT_QUESTION)
    return "\n".join(lines)


@router.post("/rozmowa", status_code=status.HTTP_201_CREATED)
async def chat_with_documents(payload: ChatInput, request: Request) -> dict[str, Any]:
    """Tworzy rozmowę z kontekstem wybranych źródeł i notatek (albo całej kolekcji)."""
    database = _database(request)
    async with database.session() as session:
        if payload.source_ids or payload.note_ids:
            sources = (
                (
                    await session.scalars(
                        select(KnowledgeSource).where(KnowledgeSource.id.in_(payload.source_ids))
                    )
                ).all()
                if payload.source_ids
                else []
            )
            notes = (
                (
                    await session.scalars(select(KnowledgeNote).where(KnowledgeNote.id.in_(payload.note_ids)))
                ).all()
                if payload.note_ids
                else []
            )
        elif payload.collection_id is not None:
            sources = (
                await session.scalars(
                    select(KnowledgeSource)
                    .where(KnowledgeSource.collection_id == payload.collection_id)
                    .order_by(KnowledgeSource.created_at)
                    .limit(200)
                )
            ).all()
            notes = (
                await session.scalars(
                    select(KnowledgeNote)
                    .where(KnowledgeNote.collection_id == payload.collection_id)
                    .order_by(KnowledgeNote.created_at)
                    .limit(200)
                )
            ).all()
        else:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wybierz dokumenty albo kolekcję.")
        collection = (
            await session.get(KnowledgeCollection, payload.collection_id) if payload.collection_id else None
        )
    explicit = bool(payload.source_ids or payload.note_ids)
    if explicit and (
        len(sources) != len(set(payload.source_ids)) or len(notes) != len(set(payload.note_ids))
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono części wybranych dokumentów.")
    if not sources and not notes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Kolekcja nie zawiera dokumentów.")
    first = sources[0].title if sources else notes[0].title
    count = len(sources) + len(notes)
    name = (
        collection.name if collection is not None else (first if count == 1 else f"{first} i inne ({count})")
    )
    title = f"Dokumenty: {name}"
    wlasciciel_konta = (await require_session(request)).owner_id
    conversation = Conversation(
        owner_id=wlasciciel_konta,
        title=title if len(title) <= 120 else title[:117].rstrip() + "…",
        meta={
            "mode": "chat",
            "knowledge": {
                "collection_id": str(payload.collection_id) if payload.collection_id else None,
                "source_ids": [str(source.id) for source in sources],
                "note_ids": [str(note.id) for note in notes],
            },
        },
    )
    async with database.session() as session:
        session.add(conversation)
    sent = await send_message(
        conversation.id,
        SendMessage(text=chat_prompt(payload.question, list(sources), list(notes))),
        request,
        wlasciciel_konta,
    )
    return {"conversation_id": str(conversation.id), "run_id": sent["run_id"], "title": conversation.title}
