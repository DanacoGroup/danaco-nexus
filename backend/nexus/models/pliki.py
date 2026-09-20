"""Przestrzeń plików konta: katalogi zakładane przez użytkownika.

Użytkownik ma jedną przestrzeń na pliki — te, które sam wgrał, i te, które wytworzył dla
niego agent. Nie ma tu dwóch osobnych światów „chmura” i „baza wiedzy”: to sąsiednie
grupy w jednym miejscu, a układ wyznacza sam użytkownik, zakładając katalogi i projekty
po swojemu.

Katalog jest wyłącznie etykietą porządkującą. Plik bez katalogu jest widoczny w widoku
„Wszystkie” — nic nie ginie przez to, że użytkownik niczego nie poukładał.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from nexus.db import ADMIN_OWNER, Base, UtcDateTime, utcnow

# Katalog o tym rodzaju grupuje pracę nad jednym tematem; „katalog” jest zwykłym folderem.
RODZAJE = ("katalog", "projekt")


class KatalogPlikow(Base):
    """Katalog albo projekt w przestrzeni plików konta."""

    __tablename__ = "pliki_katalogi"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=lambda: ADMIN_OWNER, index=True)
    # Katalog nadrzędny; brak oznacza katalog na najwyższym poziomie.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("pliki_katalogi.id", ondelete="CASCADE"), nullable=True, index=True
    )
    nazwa: Mapped[str] = mapped_column(String(160))
    opis: Mapped[str] = mapped_column(Text, default="")
    rodzaj: Mapped[str] = mapped_column(String(20), default="katalog")
    # Kolor kropki przy nazwie — drobiazg, ale to po nim ludzie rozpoznają swoje katalogi.
    kolor: Mapped[str] = mapped_column(String(20), default="")
    przypiety: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


# Przypisanie pliku do katalogu i własna nazwa nadana przez użytkownika. Nazwa pliku
# z dysku bywa nieczytelna („scan_0012.pdf”), a zmienianie jej na dysku psułoby odwołania
# w rozmowach — dlatego tytuł jest osobnym polem.
COLUMNS: list[tuple[str, str, str, str]] = [
    ("files", "katalog_id", "UUID", "TEXT"),
    ("files", "tytul", "VARCHAR(300) NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
]
