"""Ustawienia konta: preferencje użytkownika trzymane po stronie serwera.

Do tej pory jedyne, co dało się ustawić, mieszkało w ``localStorage`` przeglądarki —
motyw i głos. Po przesiadce na telefon albo po wyczyszczeniu danych witryny wszystko
wracało do stanu fabrycznego, a ustawienia, które dotyczą pracy agenta (tryb startowy,
czytanie odpowiedzi na głos, powiadomienia), nie miały gdzie zamieszkać.

Tabela jest jednym wierszem na konto z dokumentem JSON: zbiór preferencji zmienia się
razem z interfejsem, a osobna kolumna na każdą z nich oznaczałaby migrację przy każdym
nowym przełączniku. Klucze spoza wykazu w ``nexus.api.modules.konto`` są odrzucane, więc
dokument nie staje się workiem na cokolwiek.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from nexus.db import Base, JsonType, UtcDateTime, utcnow


class UstawieniaKonta(Base):
    """Preferencje jednego konta (``owner_id`` z sesji)."""

    __tablename__ = "ustawienia_konta"

    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    dane: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
