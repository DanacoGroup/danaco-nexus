"""Narzędzia agenta. Import modułów rejestruje narzędzia w rejestrze.

Każdy moduł ``nexus/tools/*.py`` (poza pomocniczymi ``base``, ``common``
i plikami zaczynającymi się od ``_``) jest importowany automatycznie –
nowe narzędzie wystarczy dodać w osobnym pliku z ``@registry.register``.
"""

import importlib
import pkgutil

from nexus.tools.base import registry

HELPERS = frozenset({"base", "common", "transkrypcja_proces"})

for _info in sorted(pkgutil.iter_modules(__path__), key=lambda item: item.name):
    if _info.name not in HELPERS and not _info.name.startswith("_"):
        importlib.import_module(f"{__name__}.{_info.name}")

__all__ = ["registry"]
