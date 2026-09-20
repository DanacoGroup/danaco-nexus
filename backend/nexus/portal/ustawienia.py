"""Konfiguracja portalu ze zmiennych środowiskowych ``NEXUS_PORTAL_*``.

Ustawienia aplikacji (``nexus.config.Settings``) są wspólne dla API i procesu roboczego; portal
czyta własne zmienne bezpośrednio ze środowiska, żeby nie zmieniać tamtej klasy. Wartości są
odczytywane przy każdym wywołaniu – restart procesu nie jest potrzebny po zmianie środowiska
tylko wtedy, gdy zmienną ustawia menedżer usług przed startem.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from nexus.config import Settings

PREFIX = "NEXUS_PORTAL_"
NADAWCA_DZIENNIK = "dziennik"
NADAWCA_SMTP = "smtp"


def _text(name: str, default: str = "") -> str:
    return os.environ.get(PREFIX + name, default).strip()


def _number(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = _text(name)
    if not raw.lstrip("-").isdigit():
        return default
    return max(minimum, min(maximum, int(raw)))


def _flag(name: str, default: bool) -> bool:
    raw = _text(name).lower()
    if raw in {"1", "tak", "true", "wlaczona", "włączona"}:
        return True
    if raw in {"0", "nie", "false", "wylaczona", "wyłączona"}:
        return False
    return default


@dataclass(frozen=True)
class PortalSettings:
    """Ustawienia portalu odczytane ze środowiska."""

    public_url: str
    mail_sender: str
    mail_from: str
    reset_ttl_minutes: int
    session_days: int
    registration_open: bool
    login_attempts: int
    reset_attempts: int
    contact_attempts: int

    @property
    def base_url(self) -> str:
        """Adres bazowy bez ukośnika na końcu (mapa witryny, kanał Atom, odsyłacze w poczcie)."""
        return self.public_url.rstrip("/")


def portal_settings(settings: Settings) -> PortalSettings:
    """Ustawienia portalu; adres publiczny dziedziczony z ``NEXUS_PUBLIC_URL``, gdy brak własnego."""
    sender = _text("MAIL_NADAWCA", NADAWCA_DZIENNIK).lower()
    return PortalSettings(
        public_url=_text("PUBLIC_URL") or settings.public_url or "https://danaco-nexus.pl",
        mail_sender=sender if sender in {NADAWCA_DZIENNIK, NADAWCA_SMTP} else NADAWCA_DZIENNIK,
        mail_from=_text("MAIL_FROM"),
        reset_ttl_minutes=_number("RESET_TTL_MINUTES", 30, 5, 240),
        session_days=_number("SESSION_DAYS", 14, 1, 90),
        registration_open=_flag("REJESTRACJA", True),
        login_attempts=_number("LOGIN_PROBY_15MIN", 8, 1, 100),
        reset_attempts=_number("RESET_PROBY_15MIN", 5, 1, 100),
        contact_attempts=_number("KONTAKT_PROBY_15MIN", 5, 1, 100),
    )
