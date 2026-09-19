"""Konfiguracja aplikacji odczytywana ze zmiennych środowiskowych ``NEXUS_*``.

Klucz API Anthropic SDK odczytuje samodzielnie ze zmiennej
``ANTHROPIC_API_KEY``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ustawienia wspólne dla API i procesu roboczego."""

    model_config = SettingsConfigDict(env_prefix="NEXUS_", extra="ignore")

    database_url: str = "postgresql+asyncpg://nexus:nexus@postgres:5432/nexus"
    data_dir: Path = Path("/data")
    static_dir: Path = Path("/app/static")

    anthropic_model: str = "claude-opus-5"
    anthropic_effort: str = ""
    max_output_tokens: int = 64000
    max_agent_steps: int = 60
    server_side_fallbacks: bool = True

    worker_concurrency: int = 2
    tool_threads: int = 8
    upload_limit_mb: int = 2048

    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "nexus_documents"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    tika_url: str = "http://tika:9998"
    languagetool_url: str = "http://languagetool:8010"
    realesrgan_dir: Path = Path("/opt/realesrgan")

    session_days: int = 30
    cookie_secure: bool = True
    login_attempts_per_15_min: int = 8

    @property
    def files_dir(self) -> Path:
        """Katalog przechowywanych plików."""
        return self.data_dir / "files"

    @property
    def cache_dir(self) -> Path:
        """Katalog pamięci podręcznej modeli (osadzenia, konwersje)."""
        return self.data_dir / "cache"

    @property
    def work_dir(self) -> Path:
        """Katalog roboczy narzędzi (pliki tymczasowe zadań)."""
        return self.data_dir / "work"


@lru_cache
def get_settings() -> Settings:
    """Zwraca konfigurację (jednokrotnie odczytaną)."""
    return Settings()
