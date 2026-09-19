"""API rozmów: lista, tworzenie, historia w postaci tur, wysyłanie wiadomości."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update

from nexus.api.auth import require_session
from nexus.db import Conversation, Database, Message, Run, StoredFile, ToolCall, utcnow
from nexus.storage import FileStorage
from nexus.tools.base import image_block, image_preview
from nexus.tools.common import open_image

router = APIRouter(
    prefix="/api/conversations", tags=["conversations"], dependencies=[Depends(require_session)]
)

DEFAULT_TITLE = "Nowa rozmowa"
ACTIVE_STATUSES = ("queued", "running")
MAX_ATTACHED_IMAGE_PREVIEWS = 4
IMAGE_MIME_PREFIX = "image/"


class CreateConversation(BaseModel):
    title: str | None = Field(None, max_length=200)


class RenameConversation(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SendMessage(BaseModel):
    text: str = Field("", max_length=100_000)
    file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)


def file_payload(record: StoredFile) -> dict[str, Any]:
    """Opis pliku dla interfejsu."""
    return {
        "id": str(record.id),
        "name": record.name,
        "mime": record.mime,
        "size": record.size,
        "origin": record.origin,
        "created_at": record.created_at.isoformat(),
        "indexed": record.indexed,
        "description": (record.meta or {}).get("description", ""),
    }


def _database(request: Request) -> Database:
    return request.app.state.database


async def _conversation(database: Database, conversation_id: uuid.UUID) -> Conversation:
    async with database.session() as session:
        conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono rozmowy.")
    return conversation


@router.get("")
async def list_conversations(request: Request) -> list[dict[str, Any]]:
    """Rozmowy od najnowszej, z informacją o trwającym zadaniu."""
    async with _database(request).session() as session:
        rows = (
            await session.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(500))
        ).all()
        active = set(
            (await session.scalars(select(Run.conversation_id).where(Run.status.in_(ACTIVE_STATUSES)))).all()
        )
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "updated_at": row.updated_at.isoformat(),
            "active": row.id in active,
        }
        for row in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: CreateConversation, request: Request) -> dict[str, Any]:
    """Tworzy rozmowę."""
    conversation = Conversation(title=(payload.title or DEFAULT_TITLE).strip() or DEFAULT_TITLE)
    async with _database(request).session() as session:
        session.add(conversation)
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "updated_at": conversation.updated_at.isoformat(),
        "active": False,
    }


@router.patch("/{conversation_id}")
async def rename_conversation(
    conversation_id: uuid.UUID, payload: RenameConversation, request: Request
) -> dict[str, str]:
    """Zmienia tytuł rozmowy."""
    await _conversation(_database(request), conversation_id)
    async with _database(request).session() as session:
        await session.execute(
            update(Conversation).where(Conversation.id == conversation_id).values(title=payload.title.strip())
        )
    return {"id": str(conversation_id), "title": payload.title.strip()}


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: uuid.UUID, request: Request) -> dict[str, bool]:
    """Usuwa rozmowę wraz z jej plikami i wpisami w bazie wiedzy."""
    database = _database(request)
    storage: FileStorage = request.app.state.storage
    await _conversation(database, conversation_id)
    async with database.session() as session:
        busy = await session.scalar(
            select(func.count())
            .select_from(Run)
            .where(Run.conversation_id == conversation_id, Run.status.in_(ACTIVE_STATUSES))
        )
        if busy:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Rozmowa ma trwające zadanie – najpierw je zatrzymaj."
            )
        files = (
            await session.scalars(select(StoredFile).where(StoredFile.conversation_id == conversation_id))
        ).all()
        indexed = [record.id for record in files if record.indexed]
        for record in files:
            storage.delete(record)
        await session.execute(delete(StoredFile).where(StoredFile.conversation_id == conversation_id))
        await session.execute(delete(Conversation).where(Conversation.id == conversation_id))
    if indexed:
        knowledge = request.app.state.knowledge
        await asyncio.to_thread(lambda: [knowledge.delete(file_id) for file_id in indexed])
    return {"ok": True}


def build_turns(
    messages: list[Message],
    files: dict[str, dict[str, Any]],
    calls: dict[str, ToolCall],
    runs: dict[uuid.UUID, Run],
) -> list[dict[str, Any]]:
    """Składa historię Messages API w tury do wyświetlenia w czacie."""
    turns: list[dict[str, Any]] = []
    for message in messages:
        if message.kind == "user":
            meta = message.meta or {}
            turns.append(
                {
                    "type": "user",
                    "id": message.id,
                    "text": meta.get("text", ""),
                    "run_id": str(message.run_id) if message.run_id else None,
                    "files": [files[fid] for fid in meta.get("file_ids", []) if fid in files],
                    "created_at": message.created_at.isoformat(),
                }
            )
            continue
        if message.kind == "tool_results":
            continue
        previous = turns[-1] if turns else None
        if previous is None or previous["type"] != "assistant" or previous["run_id"] != str(message.run_id):
            run = runs.get(message.run_id) if message.run_id else None
            previous = {
                "type": "assistant",
                "run_id": str(message.run_id) if message.run_id else None,
                "items": [],
                "status": run.status if run else "done",
                "error": run.error if run else "",
                "created_at": message.created_at.isoformat(),
            }
            turns.append(previous)
        for block in message.content:
            kind = block.get("type")
            if kind == "text" and block.get("text"):
                previous["items"].append({"kind": "text", "text": block["text"]})
            elif kind == "thinking" and block.get("thinking"):
                previous["items"].append({"kind": "thinking", "text": block["thinking"]})
            elif kind == "tool_use":
                call = calls.get(block.get("id", ""))
                previous["items"].append(
                    {
                        "kind": "tool",
                        "tool_use_id": block.get("id"),
                        "name": block.get("name"),
                        "status": call.status if call else "done",
                        "summary": call.summary if call else "",
                        "duration_ms": call.duration_ms if call else 0,
                        "files": [
                            files[fid] for fid in (call.output_file_ids if call else []) if fid in files
                        ],
                    }
                )
    present = {turn["run_id"] for turn in turns if turn["type"] == "assistant"}
    for run_id, run in runs.items():
        if str(run_id) in present or run.status == "done":
            continue
        position = next(
            (
                index + 1
                for index, turn in enumerate(turns)
                if turn["type"] == "user" and turn.get("run_id") == str(run_id)
            ),
            len(turns),
        )
        turns.insert(
            position,
            {
                "type": "assistant",
                "run_id": str(run_id),
                "items": [],
                "status": run.status,
                "error": run.error,
                "created_at": run.created_at.isoformat(),
            },
        )
    return turns


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: uuid.UUID, request: Request) -> dict[str, Any]:
    """Rozmowa z historią tur, plikami i stanem bieżącego zadania."""
    database = _database(request)
    conversation = await _conversation(database, conversation_id)
    async with database.session() as session:
        messages = (
            await session.scalars(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
            )
        ).all()
        records = (
            await session.scalars(
                select(StoredFile)
                .where(StoredFile.conversation_id == conversation_id)
                .order_by(StoredFile.created_at)
            )
        ).all()
        runs = {
            run.id: run
            for run in (
                await session.scalars(
                    select(Run).where(Run.conversation_id == conversation_id).order_by(Run.created_at)
                )
            ).all()
        }
        calls = (
            {
                call.tool_use_id: call
                for call in (
                    await session.scalars(select(ToolCall).where(ToolCall.run_id.in_(list(runs))))
                ).all()
            }
            if runs
            else {}
        )
    files = {str(record.id): file_payload(record) for record in records}
    active = next((run for run in runs.values() if run.status in ACTIVE_STATUSES), None)
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "turns": build_turns(list(messages), files, calls, runs),
        "files": list(files.values()),
        "active_run": {"id": str(active.id), "status": active.status} if active else None,
    }


def _attachment_manifest(records: list[StoredFile]) -> str:
    lines = ["", "[Załączone pliki]"]
    for record in records:
        lines.append(
            f"- file_id: {record.id} | nazwa: {record.name} | typ: {record.mime} | rozmiar: {record.size} B"
        )
    return "\n".join(lines)


def _image_previews(storage: FileStorage, records: list[StoredFile]) -> list[dict[str, Any]]:
    blocks = []
    for record in records:
        if len(blocks) >= MAX_ATTACHED_IMAGE_PREVIEWS or not record.mime.startswith(IMAGE_MIME_PREFIX):
            continue
        try:
            blocks.append(image_block(image_preview(open_image(storage.path_of(record)), 1024)))
        except Exception:  # noqa: BLE001 - brak podglądu nie blokuje wiadomości
            continue
    return blocks


@router.post("/{conversation_id}/messages", status_code=status.HTTP_202_ACCEPTED)
async def send_message(conversation_id: uuid.UUID, payload: SendMessage, request: Request) -> dict[str, Any]:
    """Zapisuje wiadomość użytkownika i zleca jej obsługę agentowi (kolejka)."""
    database = _database(request)
    storage: FileStorage = request.app.state.storage
    conversation = await _conversation(database, conversation_id)
    text = payload.text.strip()
    if not text and not payload.file_ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Wiadomość jest pusta.")
    async with database.session() as session:
        busy = await session.scalar(
            select(func.count())
            .select_from(Run)
            .where(Run.conversation_id == conversation_id, Run.status.in_(ACTIVE_STATUSES))
        )
        if busy:
            raise HTTPException(status.HTTP_409_CONFLICT, "Poprzednie zadanie jeszcze trwa.")
        records = (
            (await session.scalars(select(StoredFile).where(StoredFile.id.in_(payload.file_ids)))).all()
            if payload.file_ids
            else []
        )
    if len(records) != len(set(payload.file_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono części załączonych plików.")
    order = {file_id: position for position, file_id in enumerate(payload.file_ids)}
    records = sorted(records, key=lambda record: order[record.id])
    previews = await asyncio.to_thread(_image_previews, storage, records)
    body = (text or "Przeanalizuj załączone pliki.") + (_attachment_manifest(records) if records else "")
    content = [*previews, {"type": "text", "text": body}]
    run = Run(conversation_id=conversation_id)
    async with database.session() as session:
        for record in records:
            if record.conversation_id is None:
                record.conversation_id = conversation_id
                session.add(record)
        session.add(run)
        await session.flush()
        session.add(
            Message(
                conversation_id=conversation_id,
                run_id=run.id,
                role="user",
                kind="user",
                content=content,
                meta={"text": text, "file_ids": [str(r.id) for r in records]},
            )
        )
        values: dict[str, Any] = {"updated_at": utcnow()}
        if conversation.title == DEFAULT_TITLE:
            values["title"] = _title_from(text, records)
        await session.execute(update(Conversation).where(Conversation.id == conversation_id).values(**values))
    return {"run_id": str(run.id)}


def _title_from(text: str, records: list[StoredFile]) -> str:
    """Tytuł rozmowy z pierwszej wiadomości."""
    source = " ".join(text.split()) or (records[0].name if records else DEFAULT_TITLE)
    return source if len(source) <= 60 else source[:57].rstrip() + "…"
