"""Moduł Agenci: wszystkie sesje (zadania) w toku i ostatnio zakończone, drzewo podagentów,
nowe zadania w tle i stan limitów konta Claude."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from nexus.agent.przestrzenie import existing_project
from nexus.agent.runner import RATE_LIMIT_KEY, conversation_mode, rate_limit_warning
from nexus.api.auth import require_session
from nexus.api.conversations import SendMessage, send_message
from nexus.config import Settings
from nexus.db import Conversation, Database, Run, RunEvent, Setting, utcnow

router = APIRouter(prefix="/api/agenci", tags=["agenci"], dependencies=[Depends(require_session)])

ACTIVE_STATUSES = ("queued", "running")
TRACKED_EVENTS = ("tool.started", "tool.finished", "tool.progress")
RECENT_HOURS = 24
TITLE_CHARS = 60


class NewTask(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    mode: Literal["chat", "research", "code", "strona"] = "chat"
    workspace: str = Field("", max_length=64, description="Projekt modułu Kod (tryb code).")
    title: str | None = Field(None, max_length=200)


def summarize_events(events: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Postęp przebiegu ze zdarzeń narzędzi: liczniki, ostatnia czynność i drzewo podagentów."""
    agents: dict[str, dict[str, Any]] = {}
    calls: dict[str, dict[str, Any]] = {}
    activity = ""
    for event_type, data in events:
        tool_use_id = str(data.get("tool_use_id") or "")
        parent = data.get("parent_tool_use_id")
        if event_type == "tool.started" and tool_use_id:
            call = {"name": str(data.get("name") or ""), "status": "running", "parent": parent}
            calls[tool_use_id] = call
            if isinstance(data.get("agent"), dict):
                agents[tool_use_id] = {
                    "tool_use_id": tool_use_id,
                    "parent_tool_use_id": parent,
                    "description": str(data["agent"].get("description") or ""),
                    "subagent_type": str(data["agent"].get("subagent_type") or ""),
                    "status": "running",
                    "summary": "",
                    "progress": "",
                    "tools_total": 0,
                    "tools_running": 0,
                    "duration_ms": 0,
                }
            activity = call["name"]
        elif event_type == "tool.finished" and tool_use_id in calls:
            calls[tool_use_id]["status"] = str(data.get("status") or "done")
            if tool_use_id in agents:
                agents[tool_use_id].update(
                    status=str(data.get("status") or "done"),
                    summary=str(data.get("summary") or ""),
                    duration_ms=int(data.get("duration_ms") or 0),
                    progress="",
                )
        elif event_type == "tool.progress":
            text = str(data.get("text") or "")
            if tool_use_id in agents:
                agents[tool_use_id]["progress"] = text
            if text:
                activity = text
    for call in calls.values():
        agent = agents.get(call["parent"] or "")
        if agent is not None:
            agent["tools_total"] += 1
            agent["tools_running"] += call["status"] == "running"
    plain = [call for tool_use_id, call in calls.items() if tool_use_id not in agents]
    return {
        "tools_total": len(plain),
        "tools_running": sum(call["status"] == "running" for call in plain),
        "agents": list(agents.values()),
        "activity": activity[:200],
    }


def _limits(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(info, dict):
        return None
    windows = info.get("unifiedWindows") if isinstance(info.get("unifiedWindows"), dict) else {}
    return {
        "status": info.get("status", ""),
        "updated_at": info.get("updated_at", ""),
        "windows": {
            key: {"utilization": value.get("utilization"), "resets_at": value.get("resetsAt")}
            for key, value in windows.items()
            if isinstance(value, dict)
        },
        "warning": rate_limit_warning(info),
    }


@router.get("/zadania")
async def list_tasks(
    request: Request, zakonczone: int = Query(20, ge=0, le=100, description="Liczba ostatnio zakończonych.")
) -> dict[str, Any]:
    """Zadania w toku (z postępem i podagentami) i ostatnio zakończone."""
    database: Database = request.app.state.database
    settings: Settings = request.app.state.settings
    since = utcnow() - timedelta(hours=RECENT_HOURS)
    async with database.session() as session:
        active = (
            await session.scalars(select(Run).where(Run.status.in_(ACTIVE_STATUSES)).order_by(Run.created_at))
        ).all()
        finished = (
            (
                await session.scalars(
                    select(Run)
                    .where(
                        Run.status.not_in(ACTIVE_STATUSES),
                        or_(Run.finished_at.is_(None), Run.finished_at >= since),
                    )
                    .order_by(Run.created_at.desc())
                    .limit(zakonczone)
                )
            ).all()
            if zakonczone
            else []
        )
        runs = [*active, *finished]
        conversations = (
            {
                row.id: row
                for row in (
                    await session.scalars(
                        select(Conversation).where(Conversation.id.in_({run.conversation_id for run in runs}))
                    )
                ).all()
            }
            if runs
            else {}
        )
        rows = (
            (
                await session.execute(
                    select(RunEvent.run_id, RunEvent.type, RunEvent.data)
                    .where(RunEvent.run_id.in_([run.id for run in runs]), RunEvent.type.in_(TRACKED_EVENTS))
                    .order_by(RunEvent.id)
                )
            ).all()
            if runs
            else []
        )
        limits = await session.scalar(select(Setting.value).where(Setting.key == RATE_LIMIT_KEY))
        queued = await session.scalar(select(func.count()).select_from(Run).where(Run.status == "queued"))
    events: dict[uuid.UUID, list[tuple[str, dict[str, Any]]]] = {}
    for run_id, event_type, data in rows:
        events.setdefault(run_id, []).append((event_type, data or {}))

    def payload(run: Run) -> dict[str, Any]:
        conversation = conversations.get(run.conversation_id)
        meta = (conversation.meta if conversation else None) or {}
        return {
            "id": str(run.id),
            "conversation_id": str(run.conversation_id),
            "title": conversation.title if conversation else "",
            "mode": conversation_mode(meta),
            "workspace": meta.get("workspace", ""),
            "status": run.status,
            "error": run.error,
            "created_at": run.created_at.isoformat(),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "usage": run.usage or {},
            **summarize_events(events.get(run.id, [])),
        }

    return {
        "active": [payload(run) for run in active],
        "finished": [payload(run) for run in finished],
        "config": {
            "concurrency": settings.worker_concurrency,
            "queued": int(queued or 0),
            "subagents": settings.claude_subagents,
            "max_subagents": settings.agenci_max_podagentow,
            "web_tools": settings.claude_web_tools,
        },
        "limits": _limits(limits),
    }


@router.post("/zadania", status_code=status.HTTP_202_ACCEPTED)
async def create_task(payload: NewTask, request: Request) -> dict[str, Any]:
    """Nowe zadanie w tle: osobna rozmowa w wybranym trybie i wiadomość w kolejce."""
    meta: dict[str, Any] = {"mode": payload.mode}
    if payload.mode == "code":
        if existing_project(request.app.state.settings, payload.workspace) is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Wybierz istniejący projekt modułu Kod."
            )
        meta["workspace"] = payload.workspace
    text = payload.text.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Opis zadania jest pusty.")
    source = " ".join(text.split())
    title = (payload.title or "").strip() or (
        source if len(source) <= TITLE_CHARS else source[: TITLE_CHARS - 3].rstrip() + "…"
    )
    conversation = Conversation(id=uuid.uuid4(), title=title, meta=meta)
    database: Database = request.app.state.database
    async with database.session() as session:
        session.add(conversation)
    queued = await send_message(conversation.id, SendMessage(text=text), request)
    return {"conversation_id": str(conversation.id), "run_id": queued["run_id"], "title": title}
