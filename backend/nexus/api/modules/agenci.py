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

from nexus.agent.przestrzenie import projekt_konta
from nexus.agent.runner import conversation_mode, rate_limit_warning
from nexus.api.auth import require_session, wlasciciel
from nexus.api.conversations import SendMessage, send_message
from nexus.config import Settings
from nexus.db import Conversation, Database, Run, RunEvent, utcnow
from nexus.models.agenci import LIMIT_AGENTOW, AgentUzytkownika

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
    """Stan limitów kont silnika — wyłącznie do użytku operatora, nie do odpowiedzi API.

    Zostaje w kodzie, bo korzysta z niego diagnostyka; żaden punkt końcowy go nie zwraca.
    """
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
    request: Request,
    zakonczone: int = Query(20, ge=0, le=100, description="Liczba ostatnio zakończonych."),
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Zadania konta w toku (z postępem i podagentami) i ostatnio zakończone.

    Odpowiedź niesie tytuły rozmów, opisy podagentów i treść błędów, więc przebiegi
    wybieramy po właścicielu rozmowy — tak samo jak ``api/runs.py``.
    """
    database: Database = request.app.state.database
    settings: Settings = request.app.state.settings
    since = utcnow() - timedelta(hours=RECENT_HOURS)
    moje = (
        select(Run)
        .join(Conversation, Conversation.id == Run.conversation_id)
        .where(Conversation.owner_id == owner)
    )
    async with database.session() as session:
        active = (
            await session.scalars(moje.where(Run.status.in_(ACTIVE_STATUSES)).order_by(Run.created_at))
        ).all()
        finished = (
            (
                await session.scalars(
                    moje.where(
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
        queued = await session.scalar(
            select(func.count())
            .select_from(Run)
            .join(Conversation, Conversation.id == Run.conversation_id)
            .where(Run.status == "queued", Conversation.owner_id == owner)
        )
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
    }


@router.post("/zadania", status_code=status.HTTP_202_ACCEPTED)
async def create_task(payload: NewTask, request: Request) -> dict[str, Any]:
    """Nowe zadanie w tle: osobna rozmowa w wybranym trybie i wiadomość w kolejce."""
    # Zadanie w tle należy do konta, które je zleciło — jak każda inna rozmowa.
    wlasciciel_konta = (await require_session(request)).owner_id
    meta: dict[str, Any] = {"mode": payload.mode}
    if payload.mode == "code":
        # Tryb Kod uruchamia programy w katalogu projektu, więc projekt musi należeć
        # do tego konta — inaczej zadanie pracowałoby w cudzej przestrzeni.
        if projekt_konta(request.app.state.settings, payload.workspace, wlasciciel_konta) is None:
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
    conversation = Conversation(id=uuid.uuid4(), owner_id=wlasciciel_konta, title=title, meta=meta)
    database: Database = request.app.state.database
    async with database.session() as session:
        session.add(conversation)
    queued = await send_message(conversation.id, SendMessage(text=text), request, wlasciciel_konta)
    return {"conversation_id": str(conversation.id), "run_id": queued["run_id"], "title": title}


# --- Agenci zdefiniowani przez użytkownika -------------------------------------------


class NowyAgent(BaseModel):
    """Własny agent: nazwa, opis, instrukcja i tryb, w którym ma pracować."""

    nazwa: str = Field(min_length=1, max_length=80)
    opis: str = Field(default="", max_length=300)
    instrukcja: str = Field(min_length=1, max_length=8_000)
    tryb: Literal["chat", "research", "code", "strona"] = "chat"
    projekt: str = Field(default="", max_length=120)
    ikona: str = Field(default="iskra", max_length=40)


class ZlecenieAgenta(BaseModel):
    """Zadanie dla zapisanego agenta — to, co użytkownik chce dziś od niego."""

    tekst: str = Field(min_length=1, max_length=20_000)


def _agent_json(agent: AgentUzytkownika) -> dict[str, Any]:
    return {
        "id": str(agent.id),
        "nazwa": agent.nazwa,
        "opis": agent.opis,
        "instrukcja": agent.instrukcja,
        "tryb": agent.tryb,
        "projekt": agent.projekt,
        "ikona": agent.ikona,
        "uruchomienia": agent.uruchomienia,
    }


async def _mojego_agenta(request: Request, agent_id: uuid.UUID, owner: uuid.UUID) -> AgentUzytkownika:
    """Agent należący do tego konta albo 404 — cudzy nie różni się od nieistniejącego."""
    database: Database = request.app.state.database
    async with database.session() as session:
        agent = await session.get(AgentUzytkownika, agent_id)
        if agent is None or agent.owner_id != owner:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie ma takiego agenta.")
        session.expunge(agent)
    return agent


@router.get("/wlasni")
async def wlasni_agenci(request: Request, owner: uuid.UUID = Depends(wlasciciel)) -> list[dict[str, Any]]:
    """Agenci zapisani przez to konto; najczęściej używani na początku listy."""
    database: Database = request.app.state.database
    async with database.session() as session:
        agenci = (
            await session.scalars(
                select(AgentUzytkownika)
                .where(AgentUzytkownika.owner_id == owner)
                .order_by(AgentUzytkownika.uruchomienia.desc(), AgentUzytkownika.nazwa)
            )
        ).all()
    return [_agent_json(agent) for agent in agenci]


@router.post("/wlasni", status_code=status.HTTP_201_CREATED)
async def utworz_agenta(
    payload: NowyAgent, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, Any]:
    """Zapisuje nowego agenta konta."""
    if payload.tryb == "code" and projekt_konta(request.app.state.settings, payload.projekt, owner) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Wybierz istniejący projekt modułu Kod.")
    database: Database = request.app.state.database
    async with database.session() as session:
        ile = await session.scalar(
            select(func.count()).select_from(AgentUzytkownika).where(AgentUzytkownika.owner_id == owner)
        )
        if int(ile or 0) >= LIMIT_AGENTOW:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Masz już {LIMIT_AGENTOW} agentów — usuń któregoś, zanim dodasz nowego.",
            )
        agent = AgentUzytkownika(
            owner_id=owner,
            nazwa=payload.nazwa.strip(),
            opis=payload.opis.strip(),
            instrukcja=payload.instrukcja.strip(),
            tryb=payload.tryb,
            projekt=payload.projekt.strip() if payload.tryb == "code" else "",
            ikona=payload.ikona.strip() or "iskra",
        )
        session.add(agent)
        await session.flush()
        dane = _agent_json(agent)
    return dane


@router.patch("/wlasni/{agent_id}")
async def zmien_agenta(
    agent_id: uuid.UUID,
    payload: NowyAgent,
    request: Request,
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Zmienia zapisanego agenta."""
    await _mojego_agenta(request, agent_id, owner)
    if payload.tryb == "code" and projekt_konta(request.app.state.settings, payload.projekt, owner) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Wybierz istniejący projekt modułu Kod.")
    database: Database = request.app.state.database
    async with database.session() as session:
        agent = await session.get(AgentUzytkownika, agent_id)
        assert agent is not None  # sprawdzone wyżej
        agent.nazwa = payload.nazwa.strip()
        agent.opis = payload.opis.strip()
        agent.instrukcja = payload.instrukcja.strip()
        agent.tryb = payload.tryb
        agent.projekt = payload.projekt.strip() if payload.tryb == "code" else ""
        agent.ikona = payload.ikona.strip() or "iskra"
        agent.updated_at = utcnow()
        await session.flush()
        dane = _agent_json(agent)
    return dane


@router.delete("/wlasni/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def usun_agenta(agent_id: uuid.UUID, request: Request, owner: uuid.UUID = Depends(wlasciciel)) -> None:
    """Usuwa agenta; zadania, które już zlecił, zostają nienaruszone."""
    await _mojego_agenta(request, agent_id, owner)
    database: Database = request.app.state.database
    async with database.session() as session:
        agent = await session.get(AgentUzytkownika, agent_id)
        if agent is not None:
            await session.delete(agent)


@router.post("/wlasni/{agent_id}/uruchom", status_code=status.HTTP_202_ACCEPTED)
async def uruchom_agenta(
    agent_id: uuid.UUID,
    payload: ZlecenieAgenta,
    request: Request,
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Uruchamia zapisanego agenta na podanym zadaniu.

    Instrukcja agenta idzie przed zadaniem i jest opisana jako sposób pracy, a treść
    użytkownika jako zadanie do wykonania. Dzięki temu agent zachowuje swoją rolę także
    wtedy, gdy samo zadanie brzmi zupełnie inaczej niż jego specjalizacja.
    """
    agent = await _mojego_agenta(request, agent_id, owner)
    zadanie = payload.tekst.strip()
    tresc = (
        f"Pracujesz jako „{agent.nazwa}”. Tak masz pracować:\n"
        f"{agent.instrukcja}\n\n"
        f"Zadanie na teraz:\n{zadanie}"
    )
    skrot = " ".join(zadanie.split())
    miejsce = TITLE_CHARS - len(agent.nazwa) - 2
    if len(skrot) > miejsce:
        skrot = skrot[: max(1, miejsce - 1)].rstrip() + "…"
    tytul = f"{agent.nazwa}: {skrot}"
    wynik = await create_task(
        NewTask(text=tresc, mode=agent.tryb, workspace=agent.projekt, title=tytul), request
    )
    database: Database = request.app.state.database
    async with database.session() as session:
        zapisany = await session.get(AgentUzytkownika, agent_id)
        if zapisany is not None:
            zapisany.uruchomienia += 1
    return wynik
