"""Moduły API aplikacji (Cloud, Research, Kod, Poczta…).

Każdy plik ``nexus/api/modules/<moduł>.py`` z obiektem ``router``
(``fastapi.APIRouter`` z prefiksem ``/api/<moduł>`` i zależnością
``require_session``) jest podłączany automatycznie przez ``routers()``.
"""

from __future__ import annotations

import importlib
import pkgutil

from fastapi import APIRouter


def routers() -> list[APIRouter]:
    """Routery wszystkich modułów w kolejności nazw plików."""
    found = []
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda item: item.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        router = getattr(module, "router", None)
        if isinstance(router, APIRouter):
            found.append(router)
    return found
