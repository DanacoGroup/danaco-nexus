"""Konfiguracja dziennika zdarzeń: konsola (journald) i plik z rotacją."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "PIL", "multipart", "qdrant_client")


def configure_logging(
    directory: Path, name: str, level: int = logging.INFO, console: bool = True, rotate: bool = True
) -> None:
    """Kieruje logi na standardowe wyjście błędów i do pliku ``<name>.log``.

    Plik jest rotowany (5 × 10 MB) tylko w procesach długotrwałych; procesy
    uruchamiane wielokrotnie równolegle (serwer MCP) dopisują bez rotacji.
    """
    directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT)
    root = logging.getLogger()
    root.handlers.clear()
    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        root.addHandler(stream)
    file_handler: logging.Handler = (
        RotatingFileHandler(
            directory / f"{name}.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        if rotate
        else logging.FileHandler(directory / f"{name}.log", encoding="utf-8")
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    root.setLevel(level)
    for noisy in NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)
