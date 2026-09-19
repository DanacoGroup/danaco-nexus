"""Baza wiedzy: indeksowanie treści dokumentów w Qdrant i wyszukiwanie semantyczne.

Osadzenia (embeddings) liczone są lokalnie modelem wielojęzycznym (fastembed,
ONNX Runtime), więc treść dokumentów nie opuszcza serwera.
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200
NAMESPACE = uuid.UUID("7d6a3f00-3c1d-4c6e-9e2a-5b0d8a1c4e21")


@dataclass(slots=True)
class TextChunk:
    """Fragment tekstu dokumentu z numerem strony (jeśli znany)."""

    text: str
    page: int | None


def chunk_pages(pages: list[tuple[int | None, str]]) -> list[TextChunk]:
    """Dzieli tekst stron na nakładające się fragmenty, zachowując granice akapitów."""
    chunks: list[TextChunk] = []
    for page, text in pages:
        text = re.sub(r"[ \t]+", " ", text).strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + CHUNK_CHARS)
            if end < len(text):
                cut = max(
                    text.rfind("\n", start + CHUNK_CHARS // 2, end),
                    text.rfind(". ", start + CHUNK_CHARS // 2, end),
                )
                if cut > start:
                    end = cut + 1
            chunks.append(TextChunk(text[start:end].strip(), page))
            if end >= len(text):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
    return [chunk for chunk in chunks if len(chunk.text) >= 20]


class KnowledgeBase:
    """Kolekcja Qdrant z fragmentami dokumentów."""

    _model_lock = threading.Lock()
    _models: dict[str, Any] = {}

    def __init__(self, url: str, collection: str, model_name: str, cache_dir: Path) -> None:
        self._client = QdrantClient(url=url, timeout=60, check_compatibility=False)
        self._collection = collection
        self._model_name = model_name
        self._cache_dir = cache_dir

    def _model(self) -> Any:
        with self._model_lock:
            model = self._models.get(self._model_name)
            if model is None:
                from fastembed import TextEmbedding

                self._cache_dir.mkdir(parents=True, exist_ok=True)
                model = TextEmbedding(self._model_name, cache_dir=str(self._cache_dir))
                self._models[self._model_name] = model
            return model

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model().embed(texts, batch_size=32)]

    def _ensure_collection(self, dimension: int) -> None:
        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                self._collection,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )
            self._client.create_payload_index(self._collection, "file_id", models.PayloadSchemaType.KEYWORD)

    def index(
        self,
        file_id: uuid.UUID,
        name: str,
        conversation_id: uuid.UUID | None,
        pages: list[tuple[int | None, str]],
    ) -> int:
        """Indeksuje dokument (poprzednia wersja indeksu pliku jest zastępowana)."""
        chunks = chunk_pages(pages)
        if not chunks:
            return 0
        vectors = self._embed([chunk.text for chunk in chunks])
        self._ensure_collection(len(vectors[0]))
        self.delete(file_id)
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(NAMESPACE, f"{file_id}:{position}")),
                vector=vector,
                payload={
                    "file_id": str(file_id),
                    "name": name,
                    "page": chunk.page,
                    "chunk": position,
                    "text": chunk.text,
                    "conversation_id": str(conversation_id) if conversation_id else None,
                },
            )
            for position, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        for start in range(0, len(points), 256):
            self._client.upsert(self._collection, points[start : start + 256], wait=True)
        return len(points)

    def delete(self, file_id: uuid.UUID) -> None:
        """Usuwa z indeksu fragmenty pliku."""
        if not self._client.collection_exists(self._collection):
            return
        self._client.delete(
            self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="file_id", match=models.MatchValue(value=str(file_id)))]
                )
            ),
        )

    def search(self, query: str, limit: int = 8, file_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """Wyszukiwanie semantyczne; opcjonalnie w obrębie wskazanych plików."""
        if not self._client.collection_exists(self._collection):
            return []
        query_filter = None
        if file_ids:
            query_filter = models.Filter(
                must=[models.FieldCondition(key="file_id", match=models.MatchAny(any=file_ids))]
            )
        response = self._client.query_points(
            self._collection,
            query=self._embed([query])[0],
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        return [{"score": round(point.score, 3), **(point.payload or {})} for point in response.points]
