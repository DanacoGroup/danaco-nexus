"""Dostęp narzędzi do plików: odczyt po identyfikatorze i rejestracja wyników."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import update

from nexus.db import ADMIN_OWNER, Database, StoredFile
from nexus.storage import FileStorage, guess_mime
from nexus.tools.base import FileRef, OutputFile, ToolError


class FileService:
    """Pliki rozmów widziane przez narzędzia agenta — wyłącznie pliki jednego konta.

    Wyniki zapisują się na konto, dla którego pracuje narzędzie. Wcześniej trafiały na
    konto właściciela instalacji (wartość domyślna kolumny), więc klient nie mógł pobrać
    wyników własnego zlecenia, a narzędzie przyjmowało plik dowolnego konta po numerze.
    """

    def __init__(self, database: Database, storage: FileStorage, owner_id: uuid.UUID = ADMIN_OWNER) -> None:
        self._db = database
        self._storage = storage
        self._owner_id = owner_id

    async def resolve(self, file_id: uuid.UUID) -> FileRef:
        """Plik o podanym identyfikatorze (z weryfikacją obecności na dysku)."""
        async with self._db.session() as session:
            record = await session.get(StoredFile, file_id)
        if record is None or record.owner_id != self._owner_id:
            raise ToolError(f"Plik {file_id} nie istnieje.")
        path = self._storage.path_of(record)
        if not path.is_file():
            raise ToolError(f"Plik {record.name} nie jest już dostępny na dysku.")
        meta = dict(record.meta or {})
        meta["conversation_id"] = record.conversation_id
        return FileRef(record.id, record.name, record.mime, record.size, path, meta)

    async def mark_indexed(self, file_id: uuid.UUID) -> None:
        """Odnotowuje zaindeksowanie pliku w bazie wiedzy."""
        async with self._db.session() as session:
            await session.execute(update(StoredFile).where(StoredFile.id == file_id).values(indexed=True))

    async def store_outputs(
        self, run_id: uuid.UUID, conversation_id: uuid.UUID | None, outputs: list[OutputFile]
    ) -> list[dict[str, Any]]:
        """Przenosi pliki wynikowe narzędzia do magazynu i rejestruje je w bazie."""
        stored: list[dict[str, Any]] = []
        for output in outputs:
            if not output.path.is_file():
                continue
            file_id, relative, size, digest = await asyncio.to_thread(
                self._storage.import_file, output.path, output.name
            )
            record = StoredFile(
                id=file_id,
                conversation_id=conversation_id,
                run_id=run_id,
                owner_id=self._owner_id,
                origin="result",
                name=output.name,
                mime=guess_mime(output.name),
                size=size,
                sha256=digest,
                storage_path=relative,
                meta={"description": output.description},
            )
            async with self._db.session() as session:
                session.add(record)
            stored.append({"id": str(file_id), "name": output.name, "mime": record.mime, "size": size})
        return stored
