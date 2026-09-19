"""Narzędzia agenta. Import modułów rejestruje narzędzia w rejestrze."""

from nexus.tools import archive, cloud, files, images, knowledge, media, ocr, office, pdf, speech  # noqa: F401
from nexus.tools.base import registry

__all__ = ["registry"]
