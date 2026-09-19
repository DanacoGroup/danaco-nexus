"""Diagnostyka środowiska: baza, usługi pomocnicze, programy narzędziowe, Claude Code CLI.

Każda kontrola zwraca wynik z opisem. Bez ``--online`` żadna nie korzysta
z modelu; z ``--online`` CLI wykonuje jedno krótkie zapytanie testowe.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from nexus.config import Settings
from nexus.db import Database
from nexus.ocr.pdf_processor import PdfProcessingError, find_text_layer_font

REQUIRED_TESSERACT_LANGUAGES = ("pol", "eng", "osd")
PROGRAMS = ("soffice", "ffmpeg", "ffprobe", "magick", "unpaper", "inkscape")


@dataclass(slots=True)
class Check:
    """Wynik jednej kontroli."""

    name: str
    ok: bool
    detail: str


def _run(
    arguments: list[str], timeout: int = 60, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, check=False, env=env)


def check_programs() -> list[Check]:
    """Obecność programów narzędziowych i języków Tesseract."""
    checks = []
    tesseract = shutil.which("tesseract")
    if tesseract:
        languages = {line.strip() for line in _run([tesseract, "--list-langs"]).stdout.splitlines()[1:]}
        missing = [lang for lang in REQUIRED_TESSERACT_LANGUAGES if lang not in languages]
        checks.append(
            Check(
                "tesseract",
                not missing,
                f"języki: {', '.join(sorted(languages))}" + (f"; brak: {missing}" if missing else ""),
            )
        )
    else:
        checks.append(Check("tesseract", False, "brak programu"))
    for program in PROGRAMS:
        path = shutil.which(program)
        checks.append(Check(program, path is not None, path or "brak programu"))
    return checks


def check_realesrgan(settings: Settings) -> Check:
    """Real-ESRGAN: plik wykonywalny, modele i test na obrazie 16×16 (Vulkan na CPU)."""
    root = settings.realesrgan_dir
    executable = root / "realesrgan-ncnn-vulkan"
    if not executable.is_file():
        return Check("real-esrgan", False, f"brak {executable}")
    from PIL import Image

    from nexus.tools.images import _lavapipe_icd

    with tempfile.TemporaryDirectory() as directory:
        source, target = Path(directory) / "a.png", Path(directory) / "b.png"
        Image.new("RGB", (16, 16), "white").save(source)
        completed = _run(
            [
                str(executable),
                "-i",
                str(source),
                "-o",
                str(target),
                "-n",
                "realesr-animevideov3-x2",
                "-s",
                "2",
                "-m",
                str(root / "models"),
            ],
            timeout=120,
            env={**os.environ, "VK_ICD_FILENAMES": _lavapipe_icd()},
        )
        ok = target.is_file()
    return Check(
        "real-esrgan",
        ok,
        "działa (Vulkan: " + (_lavapipe_icd() or "domyślny") + ")" if ok else completed.stderr.strip()[-300:],
    )


def check_font() -> Check:
    """Czcionka warstwy tekstowej PDF."""
    try:
        return Check("czcionka PDF", True, str(find_text_layer_font()))
    except PdfProcessingError as error:
        return Check("czcionka PDF", False, str(error))


def check_data_dir(settings: Settings) -> Check:
    """Katalog danych z prawem zapisu."""
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.data_dir):
            pass
        return Check("katalog danych", True, str(settings.data_dir))
    except OSError as error:
        return Check("katalog danych", False, f"{settings.data_dir}: {error}")


def check_tika_app(settings: Settings) -> Check:
    """Apache Tika w trybie wsadowym (tika-app)."""
    if not settings.tika_app_jar.is_file():
        return Check("tika", False, f"brak {settings.tika_app_jar}")
    completed = _run([settings.java_bin, "-jar", str(settings.tika_app_jar), "--version"], timeout=120)
    version = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    return Check("tika", completed.returncode == 0, version or completed.stderr.strip()[-300:])


def check_chmura(settings: Settings) -> Check:
    """Chmura osobista: Nextcloud zainstalowany i dostęp WebDAV hasłem aplikacji Nexusa."""
    from nexus.tools.base import ToolError
    from nexus.tools.cloud import CloudClient

    try:
        status = httpx.get(f"{settings.chmura_url}/status.php", timeout=10).json()
    except (httpx.HTTPError, ValueError) as error:
        return Check("chmura", False, f"{settings.chmura_url}: {error.__class__.__name__}")
    if not status.get("installed"):
        return Check("chmura", False, "Nextcloud nie jest zainstalowany")
    try:
        client = CloudClient(settings)
        try:
            entries = client.list("/")
        finally:
            client.close()
    except ToolError as error:
        return Check("chmura", False, f"Nextcloud {status.get('versionstring')}: {error}")
    return Check(
        "chmura", True, f"Nextcloud {status.get('versionstring')}, WebDAV OK ({len(entries)} pozycji)"
    )


def check_http(name: str, url: str) -> Check:
    """Dostępność usługi HTTP."""
    try:
        response = httpx.get(url, timeout=10)
        return Check(name, response.status_code < 500, f"{url} → HTTP {response.status_code}")
    except httpx.HTTPError as error:
        return Check(name, False, f"{url}: {error.__class__.__name__}")


async def check_database(settings: Settings) -> Check:
    """Połączenie z bazą i schemat."""
    database = Database(settings.database_url)
    try:
        await database.create_schema()
        return Check("baza danych", True, settings.database_url.split("@")[-1])
    except Exception as error:  # noqa: BLE001 - wynik diagnostyki
        return Check("baza danych", False, f"{error.__class__.__name__}: {error}"[:300])
    finally:
        await database.close()


def check_claude_cli(settings: Settings) -> list[Check]:
    """Claude Code CLI: program, profil projektu i plik tokenu OAuth."""
    from nexus.agent.runner import read_oauth_token

    executable = shutil.which(settings.claude_bin)
    if not executable:
        return [Check("claude cli", False, f"brak programu {settings.claude_bin}")]
    version = _run([executable, "--version"], timeout=30).stdout.strip()
    profile = settings.claude_profile_dir
    token = read_oauth_token(profile)
    return [
        Check("claude cli", bool(version), f"{executable} ({version or 'brak wersji'})"),
        Check(
            "token claude",
            bool(token),
            f"{profile / 'oauth-token'}" + ("" if token else " – brak (claude setup-token)"),
        ),
    ]


async def _list_mcp_tools() -> list[str]:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "nexus.mcp_server"],
        env={**os.environ, "NEXUS_RUN_ID": str(uuid.uuid4()), "NEXUS_CONVERSATION_ID": ""},
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
    return [tool.name for tool in result.tools]


def check_mcp_server() -> Check:
    """Serwer MCP narzędzi: uruchomienie i lista narzędzi."""
    from nexus.tools import registry

    try:
        names = asyncio.run(asyncio.wait_for(_list_mcp_tools(), 120))
    except Exception as error:  # noqa: BLE001 - wynik diagnostyki
        return Check("serwer MCP", False, f"{error.__class__.__name__}: {error}"[:300])
    expected = set(registry.names())
    missing = sorted(expected - set(names))
    return Check(
        "serwer MCP",
        not missing,
        f"{len(names)} narzędzi" + (f"; brak: {missing}" if missing else ""),
    )


def check_claude_online(settings: Settings) -> Check:
    """Krótkie zapytanie testowe przez CLI (weryfikuje token i dostęp do modelu)."""
    from nexus.agent.runner import cli_environment, friendly_error

    with tempfile.TemporaryDirectory() as directory:
        completed = _run(
            [
                settings.claude_bin,
                "-p",
                "Odpowiedz jednym słowem: OK",
                "--model",
                settings.claude_model,
                "--output-format",
                "json",
                "--no-session-persistence",
                "--strict-mcp-config",
                "--allowed-tools",
                "ToolSearch",
            ],
            timeout=180,
            env=cli_environment(settings, Path(directory)),
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    if completed.returncode == 0 and not payload.get("is_error"):
        return Check("claude online", True, f"model {settings.claude_model} odpowiada")
    return Check("claude online", False, friendly_error(completed.stdout + completed.stderr))


def run_checks(settings: Settings, online: bool = False) -> list[Check]:
    """Wykonuje wszystkie kontrole."""
    steps: list[Callable[[], Check | list[Check]]] = [
        lambda: asyncio.run(check_database(settings)),
        lambda: check_data_dir(settings),
        check_font,
        check_programs,
        lambda: check_realesrgan(settings),
        lambda: check_http("qdrant", f"{settings.qdrant_url}/readyz"),
        lambda: (
            check_http("tika", f"{settings.tika_url}/version")
            if settings.tika_url
            else check_tika_app(settings)
        ),
        lambda: check_http("languagetool", f"{settings.languagetool_url}/v2/languages"),
        lambda: check_chmura(settings),
        lambda: check_claude_cli(settings),
        check_mcp_server,
    ]
    if online:
        steps.append(lambda: check_claude_online(settings))
    results: list[Check] = []
    for step in steps:
        outcome = step()
        results.extend(outcome if isinstance(outcome, list) else [outcome])
    return results
