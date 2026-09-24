"""Konfiguracja aplikacji odczytywana ze zmiennych środowiskowych ``NEXUS_*``.

Agent działa przez Claude Code CLI z własnym profilem projektu
(``NEXUS_CLAUDE_PROFILE_DIR``); token OAuth konta leży w pliku
``<profil>/oauth-token``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ustawienia wspólne dla API i procesu roboczego."""

    model_config = SettingsConfigDict(env_prefix="NEXUS_", extra="ignore")

    database_url: str = "postgresql+asyncpg://nexus@127.0.0.1:5433/nexus"
    data_dir: Path = Path("dane/app")
    static_dir: Path = Path("frontend/dist")

    claude_bin: str = "claude"
    claude_profile_dir: Path = Path("dane/claude-profil")
    claude_model: str = "claude-opus-5"
    claude_fallback_model: str = "claude-sonnet-5"
    claude_effort: str = ""
    claude_voice_effort: str = "low"
    max_output_tokens: int = 0
    max_tool_output_tokens: int = 60000
    run_timeout_minutes: int = 120
    tool_timeout_minutes: int = 90
    mcp_startup_timeout_s: int = 60

    worker_concurrency: int = 4
    tool_threads: int = 8
    upload_limit_mb: int = 2048

    redis_url: str = ""
    qdrant_url: str = "http://127.0.0.1:6335"
    qdrant_collection: str = "nexus_documents"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    tika_url: str = ""
    tika_app_jar: Path = Path("/danaco/programy/tika/tika-app-4.0.0.jar")
    java_bin: str = "/danaco/programy/java/bin/java"
    languagetool_url: str = "http://127.0.0.1:8010"
    chmura_url: str = "http://127.0.0.1:8940"
    chmura_public_url: str = ""
    chmura_user: str = "admin"
    chmura_token_file: Path = Path("dane/app/chmura-token")
    chmura_occ: Path = Path("/danaco/projekty/danaco-nexus/deploy/chmura/occ.sh")
    realesrgan_dir: Path = Path("/danaco/programy/realesrgan")
    voice_stt_model_dir: Path = Path("/danaco/programy/modele/whisper-large-v3-turbo")
    voice_tts_dir: Path = Path("/danaco/programy/modele/piper")
    voice_default: str = ""
    voice_google_key_file: Path = Path("/danaco/projekty/danaco-nexus/dane/app/google-api-key")
    voice_threads: int = 16
    voice_warm_up: bool = True
    whisper_python: str = "/danaco/programy/srodowiska/mowa/bin/python"
    whisper_model_dir: Path = Path("/danaco/programy/modele/mowa")

    session_days: int = 30
    cookie_secure: bool = True
    cookie_domain: str = ""
    public_url: str = ""
    login_attempts_per_15_min: int = 8
    #: Ile kont próbnych wolno założyć z jednego adresu IP na dobę. Piątka blokowała całe
    #: biuro i użytkowników jednego operatora komórkowego (wspólny adres za NAT-em), a
    #: „Wejdź bez rejestracji” jest główną drogą wejścia ze strony produktu.
    goscie_na_adres: int = 20

    # --- moduł research ---
    # Pobieranie stron (web_fetch_page, zapis strony w bazie wiedzy): limity i czas oczekiwania.
    research_page_max_mb: int = 8
    research_page_max_chars: int = 200_000
    research_fetch_timeout_s: int = 30
    # Adres kontaktowy dla OpenAlex/Crossref („polite pool”, szybsza obsługa); pusty = brak.
    research_contact_email: str = ""
    # Własna instancja SearXNG (np. http://127.0.0.1:8888) dla web_search; pusty = DuckDuckGo.
    research_searxng_url: str = ""
    # Opcjonalny klucz API Semantic Scholar (wyższy limit zapytań); zapisuje go
    # deploy/zapisz-klucz-semantic-scholar.sh. Brak pliku = zapytania bez klucza.
    research_semantic_scholar_key_file: Path = Path(
        "/danaco/projekty/danaco-nexus/dane/app/semantic-scholar-key"
    )
    # --- moduł biuro ---
    # Poczta: plik z loginem, hasłem i serwerami (deploy/zapisz-poczte.sh; ścieżka względna = w data_dir).
    poczta_config_file: Path = Path("poczta.json")
    # Zapasowa przestrzeń konta, gdy plan nie podaje własnej (katalog planów w
    # nexus/platnosci/plany.py rozstrzyga pierwszy: 100 MB w okresie próbnym, 1 GB
    # w planie Osobistym, 2 GB w Pro, 10 GB w Grupie).
    konto_limit_mb: int = 1024
    poczta_timeout_s: int = 30
    poczta_attachments_limit_mb: int = 25
    # Kalendarz (CalDAV Nextcloud, konto chmura_user): kalendarz domyślny i strefa czasowa.
    kalendarz_default: str = "personal"
    kalendarz_timezone: str = "Europe/Warsaw"
    # --- moduł pulpit ---
    # Limit czasu narzędzi pc_* (odpowiedź komputera) i dodatkowy czas na zgodę użytkownika
    # przy poleceniach PowerShell zmieniających system.
    pulpit_timeout_s: int = 90
    pulpit_confirm_timeout_s: int = 300

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

    # --- moduł agenci ---
    claude_subagents: bool = True
    # Piaskownica procesu CLI (bwrap): agent widzi wyłącznie przestrzeń użytkownika,
    # nie kod Nexusa ani cudze projekty na serwerze. Wyłączać tylko do diagnostyki.
    agent_piaskownica: bool = True
    claude_web_tools: bool = True
    claude_subagent_model: str = ""
    agenci_max_podagentow: int = 15
    run_timeout_research_minutes: int = 360
    worker_stop_grace_s: int = 90
    kod_git_name: str = "Danaco Nexus"
    kod_git_email: str = "nexus@danaco-nexus.pl"
    kod_clone_timeout_s: int = 600
    kod_file_preview_kb: int = 1024

    @property
    def kod_dir(self) -> Path:
        """Katalog przestrzeni projektów modułu Kod."""
        return self.data_dir / "kod"

    # --- moduł start ---
    # Powiadomienia Web Push: klucz VAPID (PEM, plik 600) tworzony przy pierwszym starcie API.
    push_enabled: bool = True
    push_vapid_file: Path | None = None
    push_contact: str = ""
    # Kto może osadzać kompaktowy panel (/?widok=panel) w ramce: strony (panel wstrzykiwany przez
    # rozszerzenie), strony rozszerzeń i Nexus Desktop. „*” nie obejmuje schematów innych niż http(s).
    panel_frame_ancestors: str = "* chrome-extension: moz-extension: safari-web-extension: file:"

    @property
    def vapid_file(self) -> Path:
        """Plik klucza prywatnego VAPID (domyślnie ``<data_dir>/vapid``)."""
        return self.push_vapid_file or self.data_dir / "vapid"

    @property
    def downloads_dir(self) -> Path:
        """Katalog instalatorów udostępnianych pod ``/pobierz/<plik>``."""
        return self.data_dir / "pobieranie"

    # --- moduł tworczy ---
    # Strony WWW (Twórca stron): limit rozmiaru jednej strony.
    tworczy_site_max_mb: int = 200
    # Usuwanie tła obrazów: uruchamiacz rembg i model (pusty = domyślny model rembg).
    tworczy_rembg_bin: str = "/danaco/programy/bin/rembg"
    tworczy_rembg_model: str = ""
    tworczy_rembg_fast_model: str = "isnet-general-use"
    # Tłumacz: model Claude (przez Claude Code CLI), limit czasu partii, rozmiar partii w znakach.
    tworczy_translate_model: str = "claude-sonnet-5"
    tworczy_translate_timeout_s: int = 300
    tworczy_translate_batch_chars: int = 6000
    # --- moduł rozszerzenie ---
    # Najstarsza wersja rozszerzenia przeglądarki zgodna z serwerem (zwracana klientowi).
    rozszerzenie_wersja_minimalna: str = "0.1.0"
    # --- licencje narzędzi ---
    # Narzędzia niekomercyjne, co do których właściciel podjął decyzję i przyjął ryzyko
    # (nazwy po przecinku). Diagnostyka przestaje wtedy zapalać czerwone światło przy
    # każdym wdrożeniu, ale nadal wypisuje, czego decyzja dotyczy — wpis ma być
    # świadomym przyjęciem sprawy, a nie jej zamiataniem. Wykaz sprzeczności zostaje
    # w dokumentach zgodności niezależnie od tego ustawienia.
    licencje_przyjete: str = ""


@lru_cache
def get_settings() -> Settings:
    """Zwraca konfigurację (jednokrotnie odczytaną)."""
    return Settings()
