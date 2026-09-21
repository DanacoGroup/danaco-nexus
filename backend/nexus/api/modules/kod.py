"""Moduł Kod: przestrzenie projektów (git), podgląd plików, zmiany i historia, rozmowy w trybie ``code``.

Projekty leżą w ``<data_dir>/kod/<nazwa>``. Rozmowa programistyczna to zwykła rozmowa
z ``meta = {"mode": "code", "workspace": <nazwa>}`` – agent (Claude Code) pracuje wtedy
w katalogu projektu z narzędziami Read/Write/Edit/Glob/Grep/Bash.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import shlex
import shutil
import stat
import tempfile
import time
import uuid
import zipfile
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette.background import BackgroundTask

from nexus.agent.piaskownica import polecenie as polecenie_piaskownicy
from nexus.agent.piaskownica import srodowisko as srodowisko_piaskownicy
from nexus.agent.piaskownica import znajdz_bwrap
from nexus.agent.przestrzenie import (
    WorkspaceError,
    project_dir,
    projekt_konta,
    projekty_konta,
    przypisz_projekt,
    safe_path,
    zapomnij_projekt,
)
from nexus.agent.runner import piaskownica_wlaczona
from nexus.api.auth import require_session, wlasciciel
from nexus.config import Settings
from nexus.db import ADMIN_OWNER, Conversation, Database, Run

router = APIRouter(prefix="/api/kod", tags=["kod"], dependencies=[Depends(require_session)])

GIT_TIMEOUT_S = 30
MAX_TREE_ENTRIES = 2000
MAX_DIFF_BYTES = 2 * 1024 * 1024
LOG_LIMIT = 200
COMMIT_PATTERN = re.compile(r"[0-9a-fA-F]{4,64}")
ACTIVE_STATUSES = ("queued", "running")
SKIPPED_DIRS = frozenset({".git"})


class NewProject(BaseModel):
    name: str = Field("", max_length=64)
    repo_url: str = Field("", max_length=500, description="Adres https repozytorium do sklonowania.")


class NewConversation(BaseModel):
    title: str | None = Field(None, max_length=200)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _database(request: Request) -> Database:
    return request.app.state.database


async def _project(request: Request, name: str) -> Path:
    """Projekt konta, które wykonuje żądanie; cudzy jest jak nieistniejący.

    Projekt to miejsce, w którym agent i terminal uruchamiają programy na serwerze, więc
    sama ważna sesja nie wystarcza — konto klienta i konto próbne dostają taką samą sesję
    jak właściciel instalacji.
    """
    owner = (await require_session(request)).owner_id
    try:
        path = projekt_konta(_settings(request), name, owner)
    except WorkspaceError as blad:
        # Uszkodzony wykaz właścicieli: lepiej odmówić obsługi, niż zgadywać, czyj to
        # projekt. Odmowa jest chwilowa i mówi, co się stało — 500 z tropieniem stosu nie.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(blad)) from blad
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono projektu.")
    return path


def _inside(root: Path, relative: str) -> Path:
    try:
        return safe_path(root, relative)
    except WorkspaceError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root.resolve()).as_posix()


def validate_clone_url(url: str) -> str:
    """Adres repozytorium: tylko https, bez danych logowania, bez adresów lokalnych."""
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise WorkspaceError("Adres repozytorium musi zaczynać się od https://.")
    if "@" in parts.netloc or parts.username or parts.password:
        raise WorkspaceError("Adres nie może zawierać danych logowania (tylko repozytoria publiczne).")
    if parts.query or parts.fragment:
        raise WorkspaceError("Adres repozytorium nie może zawierać parametrów.")
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise WorkspaceError("Adres lokalny jest niedozwolony.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise WorkspaceError("Adres lokalny jest niedozwolony.")
    return url


def remove_tree(path: Path, missing_ok: bool = False) -> None:
    """Usuwa katalog projektu, także pliki tylko do odczytu (obiekty git)."""

    def writable(function: Any, target: str, _error: BaseException) -> None:
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        function(target)

    if missing_ok and not path.exists():
        return
    shutil.rmtree(path, onexc=writable)


def name_from_url(url: str) -> str:
    """Nazwa projektu z adresu repozytorium (ostatni człon bez ``.git``)."""
    tail = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    tail = tail.removesuffix(".git")
    return re.sub(r"[^A-Za-z0-9._-]", "-", tail).strip(".-")[:64]


def _git_env(settings: Settings) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "GIT_AUTHOR_NAME": settings.kod_git_name,
            "GIT_AUTHOR_EMAIL": settings.kod_git_email,
            "GIT_COMMITTER_NAME": settings.kod_git_name,
            "GIT_COMMITTER_EMAIL": settings.kod_git_email,
            "LC_ALL": "C.UTF-8",
        }
    )
    return env


async def run_git(
    settings: Settings, cwd: Path, *args: str, timeout: float = GIT_TIMEOUT_S, check: bool = True
) -> tuple[int, bytes, str]:
    """Uruchamia git (bez powłoki); zwraca kod wyjścia, stdout i stderr."""
    process = await asyncio.create_subprocess_exec(
        "git",
        "-c",
        "core.quotepath=off",
        *args,
        cwd=cwd,
        env=_git_env(settings),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT, "Polecenie git przekroczyło limit czasu."
        ) from None
    message = stderr.decode("utf-8", "replace").strip()
    if check and process.returncode != 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"git: {message[-400:] or 'błąd'}")
    return process.returncode or 0, stdout, message


async def _has_head(settings: Settings, root: Path) -> bool:
    code, _, _ = await run_git(settings, root, "rev-parse", "--verify", "-q", "HEAD", check=False)
    return code == 0


def _branch(root: Path) -> str:
    try:
        head = (root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return head.removeprefix("ref: refs/heads/") if head.startswith("ref: ") else head[:12]


def _project_payload(path: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "git": (path / ".git").is_dir(),
        "branch": _branch(path),
        "modified": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
    }


async def _workspace_conversations(
    database: Database, name: str, owner: uuid.UUID | None = None
) -> list[Conversation]:
    async with database.session() as session:
        zapytanie = select(Conversation).order_by(Conversation.updated_at.desc()).limit(2000)
        if owner is not None:
            zapytanie = zapytanie.where(Conversation.owner_id == owner)
        rows = (await session.scalars(zapytanie)).all()
    return [row for row in rows if (row.meta or {}).get("workspace") == name]


# --- projekty ---------------------------------------------------------------------------------


@router.get("/projekty")
async def list_projects(request: Request, owner: uuid.UUID = Depends(wlasciciel)) -> list[dict[str, Any]]:
    """Projekty konta w przestrzeni modułu Kod (od ostatnio zmienianego)."""
    projects = [_project_payload(path) for path in projekty_konta(_settings(request), owner)]
    return sorted(projects, key=lambda item: item["modified"], reverse=True)


@router.post("/projekty", status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: NewProject, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, Any]:
    """Tworzy projekt (``git init``) albo klonuje repozytorium publiczne (https)."""
    settings = _settings(request)
    try:
        url = validate_clone_url(payload.repo_url) if payload.repo_url.strip() else ""
        name = payload.name.strip() or (name_from_url(url) if url else "")
        path = project_dir(settings, name)
    except WorkspaceError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    if path.exists():
        # Katalogi projektów leżą we wspólnej przestrzeni nazw, więc zajętość nazwy da się
        # sprawdzić także wtedy, gdy projekt należy do kogoś innego. Komunikat nie mówi
        # jednak czyj on jest ani że w ogóle istnieje cudzy — tylko że ta nazwa odpada.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ta nazwa jest zajęta. Wybierz inną nazwę projektu."
        )
    settings.kod_dir.mkdir(parents=True, exist_ok=True)
    try:
        if url:
            await run_git(
                settings,
                settings.kod_dir,
                "-c",
                "protocol.allow=never",
                "-c",
                "protocol.https.allow=always",
                "-c",
                "credential.helper=",
                "clone",
                "--no-recurse-submodules",
                "--",
                url,
                name,
                timeout=settings.kod_clone_timeout_s,
            )
        else:
            path.mkdir()
            await run_git(settings, path, "init", "-q", "-b", "main")
            (path / "README.md").write_text(f"# {name}\n", encoding="utf-8")
            await run_git(settings, path, "add", "README.md")
            await run_git(settings, path, "commit", "-q", "-m", "Początek projektu")
    except BaseException:
        remove_tree(path, missing_ok=True)
        raise
    # Projekt należy do konta, które go założyło — wykaz rozstrzyga późniejszy dostęp.
    przypisz_projekt(settings, name, owner)
    return _project_payload(path)


@router.delete("/projekty/{name}")
async def delete_project(
    name: str, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, bool]:
    """Usuwa katalog projektu (rozmowy zostają w historii)."""
    path = await _project(request, name)
    database = _database(request)
    conversations = {row.id for row in await _workspace_conversations(database, name, owner)}
    if conversations:
        async with database.session() as session:
            busy = (
                await session.scalars(
                    select(Run.id).where(
                        Run.conversation_id.in_(conversations), Run.status.in_(ACTIVE_STATUSES)
                    )
                )
            ).first()
        if busy:
            raise HTTPException(status.HTTP_409_CONFLICT, "W projekcie trwa zadanie – najpierw je zatrzymaj.")
    await asyncio.to_thread(remove_tree, path)
    zapomnij_projekt(_settings(request), name)
    return {"ok": True}


# --- pliki ------------------------------------------------------------------------------------


@router.get("/projekty/{name}/drzewo")
async def list_directory(name: str, request: Request, sciezka: str = "") -> dict[str, Any]:
    """Zawartość katalogu projektu (katalogi najpierw); ``.git`` jest pomijany."""
    root = await _project(request, name)
    directory = _inside(root, sciezka)
    if not directory.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono katalogu.")
    entries = []
    for entry in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if entry.name in SKIPPED_DIRS:
            continue
        if len(entries) >= MAX_TREE_ENTRIES:
            break
        try:
            resolved = entry.resolve()
        except OSError:
            continue
        if not resolved.is_relative_to(root.resolve()):
            continue
        is_dir = entry.is_dir()
        entries.append(
            {
                "name": entry.name,
                "path": _relative(root, entry.parent.resolve() / entry.name),
                "type": "dir" if is_dir else "file",
                "size": 0 if is_dir else entry.stat().st_size,
            }
        )
    return {"path": _relative(root, directory) if directory != root.resolve() else "", "entries": entries}


@router.get("/projekty/{name}/plik")
async def read_file(name: str, request: Request, sciezka: str = Query(..., min_length=1)) -> dict[str, Any]:
    """Treść pliku tekstowego do podglądu (duże pliki są skracane, binarne – tylko opis)."""
    root = await _project(request, name)
    path = _inside(root, sciezka)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono pliku.")
    limit = _settings(request).kod_file_preview_kb * 1024
    size = path.stat().st_size
    with path.open("rb") as handle:
        data = handle.read(limit)
    binary = b"\x00" in data[:8192]
    return {
        "path": _relative(root, path),
        "size": size,
        "binary": binary,
        "truncated": size > limit,
        "text": "" if binary else data.decode("utf-8", "replace"),
    }


@router.get("/projekty/{name}/pobierz")
async def download_file(name: str, request: Request, sciezka: str = Query(..., min_length=1)) -> FileResponse:
    """Pobranie pojedynczego pliku projektu."""
    root = await _project(request, name)
    path = _inside(root, sciezka)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono pliku.")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


def _write_zip(root: Path, target: Path, include_git: bool) -> None:
    base = root.resolve()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for current, directories, files in os.walk(base):
            if not include_git:
                directories[:] = [item for item in directories if item not in SKIPPED_DIRS]
            for file_name in files:
                path = Path(current) / file_name
                if path.is_symlink():
                    continue
                archive.write(path, Path(base.name) / path.relative_to(base))


@router.get("/projekty/{name}/zip")
async def download_zip(name: str, request: Request, git: bool = False) -> FileResponse:
    """Cały projekt jako archiwum ZIP (``git=1`` – razem z historią ``.git``)."""
    root = await _project(request, name)
    work = _settings(request).work_dir
    work.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix="kod-", suffix=".zip", dir=work)
    os.close(handle)
    target = Path(temporary)
    try:
        await asyncio.to_thread(_write_zip, root, target, git)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return FileResponse(
        target,
        filename=f"{root.name}.zip",
        media_type="application/zip",
        background=BackgroundTask(target.unlink, missing_ok=True),
    )


# --- git --------------------------------------------------------------------------------------


def parse_status(output: bytes) -> tuple[str, list[dict[str, str]]]:
    """Wynik ``git status --porcelain=v1 -b -z``: gałąź i lista zmian."""
    parts = output.decode("utf-8", "replace").split("\x00")
    branch = ""
    changes: list[dict[str, str]] = []
    index = 0
    while index < len(parts):
        entry = parts[index]
        index += 1
        if not entry:
            continue
        if entry.startswith("## "):
            branch = entry[3:].split("...", 1)[0].removeprefix("No commits yet on ")
            continue
        code, path = entry[:2], entry[3:]
        item = {"path": path, "index": code[0], "worktree": code[1]}
        if "R" in code or "C" in code:
            item["from"] = parts[index] if index < len(parts) else ""
            index += 1
        changes.append(item)
    return branch, changes


@router.get("/projekty/{name}/git/status")
async def git_status(name: str, request: Request) -> dict[str, Any]:
    """Gałąź i zmienione pliki (indeks i katalog roboczy)."""
    root = await _project(request, name)
    if not (root / ".git").is_dir():
        return {"git": False, "branch": "", "changes": []}
    _, output, _ = await run_git(
        _settings(request), root, "status", "--porcelain=v1", "-b", "-z", "--untracked-files=all"
    )
    branch, changes = parse_status(output)
    return {"git": True, "branch": branch, "changes": changes}


def _limited(output: bytes) -> dict[str, Any]:
    truncated = len(output) > MAX_DIFF_BYTES
    return {"diff": output[:MAX_DIFF_BYTES].decode("utf-8", "replace"), "truncated": truncated}


@router.get("/projekty/{name}/git/diff")
async def git_diff(name: str, request: Request, sciezka: str = "") -> dict[str, Any]:
    """Różnice katalogu roboczego względem ostatniego commitu (całość albo jeden plik)."""
    root = await _project(request, name)
    settings = _settings(request)
    target: list[str] = []
    if sciezka:
        path = _inside(root, sciezka)
        relative = _relative(root, path)
        target = ["--", relative]
        _, tracked, _ = await run_git(settings, root, "ls-files", "--", relative)
        if path.is_file() and not tracked.strip():
            # Nowy, nieśledzony plik: różnica względem pustego pliku.
            _, output, _ = await run_git(
                settings, root, "diff", "--no-index", "--", "/dev/null", relative, check=False
            )
            return _limited(output)
    base = ["HEAD"] if await _has_head(settings, root) else ["--cached"]
    _, output, _ = await run_git(settings, root, "diff", *base, *target)
    return _limited(output)


@router.get("/projekty/{name}/git/log")
async def git_log(
    name: str, request: Request, limit: int = Query(100, ge=1, le=LOG_LIMIT)
) -> list[dict[str, str]]:
    """Historia commitów (od najnowszego)."""
    root = await _project(request, name)
    settings = _settings(request)
    if not (root / ".git").is_dir() or not await _has_head(settings, root):
        return []
    _, output, _ = await run_git(
        settings, root, "log", f"-n{limit}", "--pretty=format:%H%x1f%an%x1f%aI%x1f%s%x1e"
    )
    commits = []
    for record in output.decode("utf-8", "replace").split("\x1e"):
        fields = record.strip("\n").split("\x1f")
        if len(fields) == 4:
            commits.append({"hash": fields[0], "author": fields[1], "date": fields[2], "subject": fields[3]})
    return commits


@router.get("/projekty/{name}/git/commit/{commit}")
async def git_show(name: str, commit: str, request: Request) -> dict[str, Any]:
    """Zmiany wprowadzone przez jeden commit."""
    root = await _project(request, name)
    if not COMMIT_PATTERN.fullmatch(commit):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Niepoprawny identyfikator commitu.")
    _, output, _ = await run_git(
        _settings(request), root, "show", "--stat", "--patch", "--format=fuller", commit
    )
    return _limited(output)


# --- rozmowy ----------------------------------------------------------------------------------


@router.get("/projekty/{name}/rozmowy")
async def list_conversations(
    name: str, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> list[dict[str, Any]]:
    """Rozmowy programistyczne projektu (wyłącznie rozmowy tego konta)."""
    await _project(request, name)
    rows = await _workspace_conversations(_database(request), name, owner)
    return [{"id": str(row.id), "title": row.title, "updated_at": row.updated_at.isoformat()} for row in rows]


@router.post("/projekty/{name}/rozmowy", status_code=status.HTTP_201_CREATED)
async def create_conversation(name: str, payload: NewConversation, request: Request) -> dict[str, Any]:
    """Nowa rozmowa z Claude Code w trybie ``code`` dla projektu."""
    await _project(request, name)
    conversation = Conversation(
        id=uuid.uuid4(),
        owner_id=(await require_session(request)).owner_id,
        title=(payload.title or "").strip() or f"Kod: {name}",
        meta={"mode": "code", "workspace": name},
    )
    async with _database(request).session() as session:
        session.add(conversation)
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "updated_at": conversation.updated_at.isoformat(),
    }


# --- Terminal pomocniczy projektu ----------------------------------------------------
#
# Moduł Kod pokazywał pliki, zmiany i historię, ale nie dawał uruchomić niczego ręcznie:
# żeby zobaczyć wynik testów, trzeba było prosić o to agenta i czytać jego relację.
# Ten punkt końcowy wykonuje polecenie w katalogu projektu i oddaje surowe wyjście.
#
# Nie jest to powłoka i celowo nią nie jest. Polecenie wykonujemy listą argumentów, bez
# interpretacji przez `sh`, a pierwszy człon musi należeć do wykazu poniżej. Dzięki temu
# nie ma tu ani `rm -rf /`, ani `curl … | sh`, ani podstawień `$(…)` — a to, po co ludzie
# naprawdę sięgają w projekcie (testy, budowa, git, zależności), działa.

#: Programy, które wolno uruchomić w projekcie. Wykaz jest zamknięty i sprawdzany na
#: pierwszym członie polecenia; wszystko spoza niego jest odrzucane z nazwą programu.
DOZWOLONE_PROGRAMY = frozenset(
    {
        "cargo",
        "cat",
        "echo",
        "eslint",
        "find",
        "gh",
        "git",
        "go",
        "grep",
        "head",
        "ls",
        "make",
        "mypy",
        "node",
        "npm",
        "npx",
        "pnpm",
        "pytest",
        "python",
        "python3",
        "ruff",
        "rustc",
        "sed",
        "sort",
        "tail",
        "tsc",
        "uniq",
        "uv",
        "wc",
    }
)

#: Znaki, które w powłoce zmieniają znaczenie polecenia. Nie uruchamiamy powłoki, więc
#: trafiłyby do programu dosłownie — ale ich obecność znaczy, że ktoś spodziewa się
#: powłoki, a nie jej dostanie. Lepiej powiedzieć to wprost niż wykonać co innego.
ZNAKI_POWLOKI = re.compile(r"[;&|`$><(){}\n]")

#: Ile wyjścia oddajemy. Dłuższe i tak nie zmieści się w oknie, a wciągnięte do rozmowy
#: zjadłoby kontekst agenta.
LIMIT_WYJSCIA = 40_000

#: Limit czasu jednego polecenia. Budowa i testy bywają długie, ale nie bez końca.
LIMIT_CZASU_S = 600
#: Ile poleceń wolno wykonać na jednym koncie w oknie czasu.
#:
#: Każde polecenie to proces w piaskownicy, a te potrafią zająć rdzeń na kilka minut
#: (`pytest`, `npm install`, `cargo build`). Bez ograniczenia jedno konto próbne trzymało
#: serwer w pętli tak długo, jak chciało. Limit jest hojny — ma zatrzymać zalew, a nie
#: przeszkadzać w pracy.
POLECEN_NA_OKNO = 60
OKNO_POLECEN_S = 300


class Polecenie(BaseModel):
    """Polecenie do wykonania w katalogu projektu."""

    polecenie: str = Field(min_length=1, max_length=2_000)


def _poza_projektem(katalog: Path, argument: str) -> bool:
    """Czy argument wskazuje plik spoza projektu (ścieżka bezwzględna, ``..``, katalog domowy).

    Wykaz programów pilnował, *co* wolno uruchomić, ale nie *na czym*: ``cat /etc/hostname``
    czytał dowolny plik prawami procesu API. Ścieżki sprawdzamy tą samą funkcją, co podgląd
    plików projektu.
    """
    wartosc = argument.split("=", 1)[1] if argument.startswith("-") and "=" in argument else argument
    if not wartosc or wartosc.startswith("-"):
        return False
    if wartosc.startswith("~"):
        return True
    if "/" not in wartosc and wartosc != "..":
        return False
    try:
        safe_path(katalog, wartosc)
    except WorkspaceError:
        return True
    return False


def _rozbierz(tresc: str, katalog: Path) -> list[str]:
    """Dzieli polecenie na argumenty i sprawdza, czy wolno je wykonać."""
    if ZNAKI_POWLOKI.search(tresc):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "To nie jest powłoka: potoki, przekierowania i łączenie poleceń nie zadziałają. "
            "Uruchom jedno polecenie naraz.",
        )
    try:
        czesci = shlex.split(tresc)
    except ValueError as blad:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Niedomknięty cudzysłów.") from blad
    if not czesci:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Polecenie jest puste.")
    # Wykaz sprawdzamy po samej nazwie, ale wtedy `./git` albo `/tmp/git` z katalogu projektu
    # przechodziłby jako „git” i uruchamiał cudzy plik. Program podaje się nazwą — ścieżkę
    # rozwiązuje PATH piaskownicy, czyli łańcuch narzędzi serwera.
    nazwa = czesci[0]
    if "/" in nazwa:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Program podaje się samą nazwą (np. „git”), bez ścieżki.",
        )
    if nazwa not in DOZWOLONE_PROGRAMY:
        dozwolone = ", ".join(sorted(DOZWOLONE_PROGRAMY))
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Program „{nazwa}” nie jest tu dostępny. Wolno uruchomić: {dozwolone}.",
        )
    for argument in czesci[1:]:
        if _poza_projektem(katalog, argument):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Argument „{argument}” wskazuje poza projekt. Terminal pracuje wyłącznie "
                "na plikach projektu.",
            )
    return czesci


def _w_piaskownicy(settings: Settings, katalog: Path, czesci: list[str]) -> tuple[list[str], dict[str, str]]:
    """Polecenie i środowisko procesu: ta sama piaskownica, w której pracuje agent.

    Program z wykazu nadal wykonuje dowolny kod (``python``, ``make``, ``npm``), więc
    o granicy nie rozstrzyga wykaz, tylko przestrzeń montowań: widać projekt, łańcuch
    narzędzi i katalog domowy zadania, nie widać kodu Nexusa ani cudzych projektów.
    """
    dom = settings.work_dir / f"terminal-{katalog.name}"
    dom.mkdir(parents=True, exist_ok=True)
    czyste = srodowisko_piaskownicy(dom=str(dom))
    argumenty = polecenie_piaskownicy(
        znajdz_bwrap(), czesci, cwd=katalog, zapis=(katalog, dom), srodowisko_procesu=czyste
    )
    # Środowisko budowane od zera. Poprzednio szło tu całe `os.environ` procesu roboczego:
    # adres bazy, ścieżki do plików z kluczem Stripe i hasłem chmury, adresy usług
    # wewnętrznych. `node -p process.env` z konta próbnego wypisywał to jednym poleceniem.
    return argumenty, czyste


#: Ostatnie uruchomienia poleceń na konto (czas jednostajny, nie zegar ścienny).
_uruchomienia: dict[str, deque[float]] = defaultdict(deque)


def _przepustnica(owner: uuid.UUID) -> None:
    """Odmawia, gdy konto wykonało już za dużo poleceń w oknie czasu."""
    wpisy = _uruchomienia[str(owner)]
    prog = time.monotonic() - OKNO_POLECEN_S
    while wpisy and wpisy[0] < prog:
        wpisy.popleft()
    if len(wpisy) >= POLECEN_NA_OKNO:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Za dużo poleceń naraz. Odczekaj chwilę i spróbuj ponownie.",
        )
    wpisy.append(time.monotonic())


@router.post("/projekty/{name}/polecenie")
async def uruchom_polecenie(
    name: str, payload: Polecenie, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, Any]:
    """Wykonuje polecenie w katalogu projektu (w piaskownicy) i oddaje jego wyjście."""
    _przepustnica(owner)
    katalog = await _project(request, name)
    settings = _settings(request)
    czesci = _rozbierz(payload.polecenie.strip(), katalog)
    if piaskownica_wlaczona(settings):
        argumenty, srodowisko = _w_piaskownicy(settings, katalog, czesci)
    elif owner == ADMIN_OWNER:
        argumenty, srodowisko = czesci, dict(os.environ)
    else:
        # Bez piaskownicy polecenie widziałoby cały dysk serwera. Właściciel instalacji
        # ma do niego dostęp tak czy inaczej; konto klienta – nie i nie dostanie go tędy.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Terminal projektu jest chwilowo niedostępny (brak piaskownicy na serwerze).",
        )

    async def bieg() -> tuple[int, str]:
        proces = await asyncio.create_subprocess_exec(
            *argumenty,
            cwd=katalog,
            env=srodowisko,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            surowe, _ = await asyncio.wait_for(proces.communicate(), timeout=LIMIT_CZASU_S)
        except TimeoutError:
            proces.kill()
            await proces.wait()
            raise
        return proces.returncode or 0, surowe.decode("utf-8", "replace")

    try:
        kod, wyjscie = await bieg()
    except TimeoutError:
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT,
            f"Polecenie przekroczyło {LIMIT_CZASU_S // 60} minut i zostało przerwane.",
        ) from None
    except FileNotFoundError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Nie ma programu „{czesci[0]}” na tym serwerze.",
        ) from None

    obciete = len(wyjscie) > LIMIT_WYJSCIA
    return {
        "kod": kod,
        "wyjscie": wyjscie[-LIMIT_WYJSCIA:] if obciete else wyjscie,
        "obciete": obciete,
        "polecenie": " ".join(czesci),
    }
