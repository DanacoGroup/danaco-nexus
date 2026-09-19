"""Narzędzia agenta. Import modułów rejestruje narzędzia w rejestrze."""

from nexus.tools import (  # noqa: F401
    archive,
    cloud,
    files,
    images,
    knowledge,
    media,
    ocr,
    office,
    pdf,
    speech,
)
from nexus.tools.base import registry

__all__ = ["registry"]
