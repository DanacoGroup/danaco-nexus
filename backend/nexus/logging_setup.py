"""Konfiguracja dziennika zdarzeń: konsola (docker logs) i plik z rotacją."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
NOISY_LOGGERS = ("httpx", "httpcore", "anthropic", "urllib3", "PIL", "multipart", "qdrant_client")


def configure_logging(directory: Path, name: str, level: int = logging.INFO) -> None:
    """Kieruje logi na standardowe wyjście i do pliku ``<name>.log`` (5 × 10 MB)."""
    directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT)
    root = logging.getLogger()
    root.handlers.clear()
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        directory / f"{name}.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(console)
    root.addHandler(file_handler)
    root.setLevel(level)
    for noisy in NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)
