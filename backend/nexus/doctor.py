"""Diagnostyka środowiska: baza, usługi pomocnicze, programy narzędziowe, klucz API.

Każda kontrola zwraca wynik z opisem; żadna nie generuje tokenów modelu
(klucz API sprawdzany jest odczytem metadanych modelu).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
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


def check_anthropic(settings: Settings, online: bool) -> Check:
    """Obecność klucza API; z ``online`` – odczyt metadanych modelu (bez generowania)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return Check("klucz API Claude", False, "brak ANTHROPIC_API_KEY")
    if not online:
        return Check("klucz API Claude", True, "ustawiony (bez sprawdzenia online)")
    import anthropic

    try:
        model = anthropic.Anthropic(max_retries=1).models.retrieve(settings.anthropic_model)
        return Check("klucz API Claude", True, f"model {model.id} dostępny")
    except anthropic.APIError as error:
        return Check("klucz API Claude", False, str(error)[:300])


def run_checks(settings: Settings, online: bool = False) -> list[Check]:
    """Wykonuje wszystkie kontrole."""
    steps: list[Callable[[], Check | list[Check]]] = [
        lambda: asyncio.run(check_database(settings)),
        lambda: check_data_dir(settings),
        check_font,
        check_programs,
        lambda: check_realesrgan(settings),
        lambda: check_http("qdrant", f"{settings.qdrant_url}/readyz"),
        lambda: check_http("tika", f"{settings.tika_url}/version"),
        lambda: check_http("languagetool", f"{settings.languagetool_url}/v2/languages"),
        lambda: check_anthropic(settings, online),
    ]
    results: list[Check] = []
    for step in steps:
        outcome = step()
        results.extend(outcome if isinstance(outcome, list) else [outcome])
    return results
