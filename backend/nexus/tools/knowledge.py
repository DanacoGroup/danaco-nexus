"""Narzędzia bazy wiedzy (Qdrant): indeksowanie i wyszukiwanie dokumentów po treści."""

from __future__ import annotations

import pymupdf
from pydantic import Field

from nexus.knowledge import KnowledgeBase
from nexus.tools.base import ToolContext, ToolError, ToolInput, ToolResult, registry
from nexus.tools.common import file_kind
from nexus.tools.files import _tika_text


class IndexInput(ToolInput):
    file_ids: list[str] = Field(min_length=1, max_length=500, description="Dokumenty do zaindeksowania.")


class SearchInput(ToolInput):
    query: str = Field(min_length=2, description="Pytanie lub opis szukanej treści (język naturalny).")
    limit: int = Field(8, ge=1, le=30, description="Liczba wyników.")
    file_ids: list[str] | None = Field(None, description="Ogranicz wyszukiwanie do tych plików.")


def knowledge_base(ctx: ToolContext) -> KnowledgeBase:
    """Klient bazy wiedzy dla bieżącej konfiguracji."""
    settings = ctx.settings
    return KnowledgeBase(
        settings.qdrant_url,
        settings.qdrant_collection,
        settings.embedding_model,
        settings.cache_dir / "fastembed",
    )


@registry.register(
    "index_documents",
    """Dodaje dokumenty do prywatnej bazy wiedzy (Qdrant), aby można je było później
wyszukiwać po treści i znaczeniu. Wymaga tekstu: dla skanów najpierw wykonaj OCR
i indeksuj przeszukiwalny PDF. Ponowne indeksowanie zastępuje poprzedni indeks pliku.""",
    IndexInput,
)
def index_documents(ctx: ToolContext, args: IndexInput) -> ToolResult:
    base = knowledge_base(ctx)
    report = []
    for file_id in args.file_ids:
        ctx.check_cancelled()
        file = ctx.file(file_id)
        kind = file_kind(file)
        if kind == "pdf":
            with pymupdf.open(file.path) as document:
                pages = [(page.number + 1, page.get_text("text")) for page in document]
        elif kind == "text":
            pages = [(None, file.path.read_text(encoding="utf-8", errors="replace"))]
        elif kind in {"office", "other"}:
            pages = [(None, _tika_text(ctx, file))]
        else:
            report.append({"file": file.name, "status": "pominięto", "reason": "brak tekstu"})
            continue
        ctx.progress(f"Indeksowanie: {file.name}")
        chunks = base.index(
            file.id, file.name, file.meta.get("conversation_id"), pages, owner_id=ctx.owner_id
        )
        if chunks == 0:
            report.append(
                {"file": file.name, "status": "pominięto", "reason": "brak tekstu – najpierw wykonaj OCR"}
            )
            continue
        ctx.mark_indexed(file.id)
        report.append({"file": file.name, "status": "zaindeksowano", "chunks": chunks})
    indexed = sum(1 for item in report if item["status"] == "zaindeksowano")
    return ToolResult({"results": report}, f"Zaindeksowano dokumenty: {indexed}")


@registry.register(
    "search_documents",
    """Wyszukuje semantycznie w prywatnej bazie wiedzy (wszystkie zaindeksowane dokumenty,
także z innych rozmów). Zwraca fragmenty z nazwą pliku, stroną i identyfikatorem pliku.""",
    SearchInput,
)
def search_documents(ctx: ToolContext, args: SearchInput) -> ToolResult:
    try:
        # Wyszukiwanie obejmuje wyłącznie dokumenty konta, w którego przestrzeni
        # pracuje przebieg — kolekcja Qdranta jest wspólna dla instalacji.
        hits = knowledge_base(ctx).search(args.query, args.limit, args.file_ids, ctx.owner_id)
    except Exception as error:  # noqa: BLE001 - błąd usługi zgłaszany modelowi
        raise ToolError(f"Baza wiedzy jest niedostępna: {error}") from error
    results = [
        {
            "file_id": hit.get("file_id"),
            "name": hit.get("name"),
            "page": hit.get("page"),
            "score": hit.get("score"),
            "text": hit.get("text"),
        }
        for hit in hits
    ]
    return ToolResult({"query": args.query, "results": results}, f"Wyszukiwanie: {len(results)} fragmentów")
