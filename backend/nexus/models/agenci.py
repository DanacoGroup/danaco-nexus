"""Agenci zdefiniowani przez użytkownika: własne specjalizacje zamiast jednego asystenta.

Moduł Agenci pokazywał do tej pory wyłącznie zadania w tle — nie dało się w nim utworzyć
żadnego agenta, mimo nazwy. A to właśnie jest sedno: użytkownik opisuje raz, jak ma
pracować „redaktor”, „księgowy” albo „programista”, i potem uruchamia go jednym
kliknięciem, zamiast za każdym razem powtarzać te same instrukcje.

Agent jest zapisanym poleceniem, nie osobnym silnikiem. Uruchomienie dokleja instrukcję
agenta do treści zadania i zleca je tak samo jak każde inne — dzięki temu wszystko, co
działa w rozmowie (narzędzia, pliki, podagenci), działa też tutaj.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from nexus.db import ADMIN_OWNER, Base, UtcDateTime, utcnow

#: Tryby pracy, w których agent może zostać uruchomiony — te same, co w zadaniach w tle.
TRYBY = ("chat", "research", "code", "strona")

#: Ile agentów wolno mieć na koncie. Próg zdrowego rozsądku: powyżej tego lista przestaje
#: być narzędziem wyboru, a zaczyna być kolejnym katalogiem do przeszukania.
LIMIT_AGENTOW = 40


class AgentUzytkownika(Base):
    """Własny agent konta: nazwa, opis i instrukcja doklejana do zlecenia."""

    __tablename__ = "agenci_uzytkownika"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=lambda: ADMIN_OWNER, index=True)
    nazwa: Mapped[str] = mapped_column(String(80))
    # Zdanie dla człowieka: po czym poznać, kiedy sięgnąć po tego agenta.
    opis: Mapped[str] = mapped_column(String(300), default="")
    # Instrukcja dla modelu — to ona robi z agenta specjalistę.
    instrukcja: Mapped[str] = mapped_column(Text, default="")
    tryb: Mapped[str] = mapped_column(String(20), default="chat")
    # Projekt modułu Kod, gdy agent pracuje w trybie `code`; pusty dla pozostałych.
    projekt: Mapped[str] = mapped_column(String(120), default="")
    # Ikona z zestawu interfejsu — wybór użytkownika, po nim rozpoznaje agenta na liście.
    ikona: Mapped[str] = mapped_column(String(40), default="iskra")
    # Ile razy agent był uruchomiony — najczęściej używane idą na górę listy.
    uruchomienia: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
