"""Gotowość serwera do przebiegu na żywo: model, programy narzędzi, baza wiedzy.

Wynik rozstrzyga tryb pracy scenariusza. Brak choćby jednego wymagania oznacza
odtworzenie nagranego przebiegu – interfejs oznacza to wtedy jako pokaz.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import httpx

from nexus.config import Settings

NA_ZYWO = "na-zywo"
ODTWORZENIE = "odtworzenie"
# Sprawdzenie Qdranta to zapytanie sieciowe do usługi lokalnej – wynik żyje przez minutę.
QDRANT_TTL_S = 60.0
_qdrant_cache: tuple[float, bool] = (0.0, False)


def model_dostepny(settings: Settings) -> bool:
    """Czy agent ma czym pracować: program CLI i token konta Claude."""
    from nexus.agent.runner import read_oauth_token

    if not (shutil.which(settings.claude_bin) or Path(settings.claude_bin).is_file()):
        return False
    return bool(read_oauth_token(settings.claude_profile_dir))


def programy(settings: Settings) -> dict[str, bool]:
    """Dostępność programów zewnętrznych używanych przez scenariusze pokazu."""
    return {
        "tesseract": shutil.which("tesseract") is not None,
        "realesrgan": (settings.realesrgan_dir / "realesrgan-ncnn-vulkan").is_file(),
        "whisper": Path(settings.whisper_python).is_file()
        and (settings.whisper_model_dir / "model.bin").is_file(),
        "libreoffice": shutil.which("soffice") is not None,
    }


def qdrant_dostepny(settings: Settings) -> bool:
    """Czy baza wiedzy odpowiada (wynik zapamiętany na minutę)."""
    global _qdrant_cache
    teraz = time.monotonic()
    if teraz - _qdrant_cache[0] < QDRANT_TTL_S:
        return _qdrant_cache[1]
    try:
        odpowiedz = httpx.get(f"{settings.qdrant_url.rstrip('/')}/collections", timeout=2.0)
        dostepny = odpowiedz.status_code == 200
    except httpx.HTTPError:
        dostepny = False
    _qdrant_cache = (teraz, dostepny)
    return dostepny


class Gotowosc:
    """Zbiorczy stan serwera odczytany raz na żądanie interfejsu."""

    def __init__(self, settings: Settings) -> None:
        self.model = model_dostepny(settings)
        self.programy = programy(settings)
        self.qdrant = qdrant_dostepny(settings)

    def brakuje(self, wymagane: tuple[str, ...], model: bool, qdrant: bool) -> list[str]:
        """Czego brakuje do przebiegu na żywo dla scenariusza."""
        braki = [nazwa for nazwa in wymagane if not self.programy.get(nazwa, False)]
        if model and not self.model:
            braki.append("model")
        if qdrant and not self.qdrant:
            braki.append("baza wiedzy")
        return braki

    def payload(self) -> dict[str, object]:
        return {"model": self.model, "programy": self.programy, "baza_wiedzy": self.qdrant}
