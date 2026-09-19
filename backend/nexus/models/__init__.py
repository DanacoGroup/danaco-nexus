"""Tabele modułów (Cloud, Research, Poczta, Kod…).

Każdy plik ``nexus/models/<moduł>.py`` definiuje modele na ``nexus.db.Base``;
import tego pakietu rejestruje je przed ``create_all``. Kolumny dodawane do
istniejących tabel moduł zgłasza w liście ``COLUMNS`` (jak ``nexus.db.COLUMNS``).
"""

from __future__ import annotations

import importlib
import pkgutil


def extra_columns() -> list[tuple[str, str, str, str]]:
    """Importuje wszystkie modele modułów i zwraca ich dodatkowe kolumny."""
    columns: list[tuple[str, str, str, str]] = []
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda item: item.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        columns.extend(getattr(module, "COLUMNS", []))
    return columns
