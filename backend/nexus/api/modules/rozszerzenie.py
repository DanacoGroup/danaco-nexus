"""Rozszerzenie przeglądarki (Chrome, Edge, Danaco Lynx): konfiguracja dla klienta.

Rozszerzenie wywołuje ``GET /api/rozszerzenie/konfiguracja`` z kluczem urządzenia
(``Authorization: Bearer nxd_…``) – sprawdza w ten sposób klucz na ekranie opcji
i dowiaduje się, pod jakim adresem działa tryb osadzony (``?widok=panel``).
Strony rozszerzenia mają uprawnienie do hosta Nexusa, więc CORS nie jest potrzebny
i pozostaje zamknięty.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from nexus import __version__
from nexus.api.auth import require_session

router = APIRouter(prefix="/api/rozszerzenie", tags=["rozszerzenie"], dependencies=[Depends(require_session)])

PANEL_PATH = "/?widok=panel"


@router.get("/konfiguracja")
async def configuration(request: Request) -> dict[str, Any]:
    """Konfiguracja rozszerzenia i opis urządzenia, którego kluczem wysłano żądanie."""
    settings = request.app.state.settings
    device = getattr(request.state, "device", None)
    return {
        "wersja": __version__,
        "urzadzenie": device,
        "panel": PANEL_PATH,
        "rozszerzenie": {"wersja_minimalna": settings.rozszerzenie_wersja_minimalna},
    }
