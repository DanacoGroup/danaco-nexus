"""Grupa: kilka kont pracujących na wspólnej puli dostępu kupionej przez założyciela.

Plan „Grupa” był do tej pory samym opisem w cenniku — dało się go kupić, ale nie dało
się nikogo do grupy dodać. Tutaj jest jego mechanika:

* jedna grupa ma jednego **założyciela** i do kilku **członków** (limit z planu);
* płaci założyciel — za każde miejsce — i to on dokupuje dostęp;
* praca każdego członka schodzi ze wspólnej puli, czyli z konta założyciela;
* rolę założyciela można przekazać innemu członkowi (`przekaz_zalozyciela`), bo grupy
  przeżywają zmiany: ktoś odchodzi z firmy, ktoś inny przejmuje rozliczenia.

Zaproszenie jest jednorazowym odsyłaczem na adres e-mail; w bazie leży wyłącznie skrót
tokenu, tak samo jak przy sesjach i odzyskiwaniu hasła.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from nexus.db import Base, UtcDateTime, utcnow

#: Role w grupie. Założyciel jest dokładnie jeden i tylko on płaci oraz zaprasza.
ROLA_ZALOZYCIEL = "zalozyciel"
ROLA_CZLONEK = "czlonek"
ROLE = (ROLA_ZALOZYCIEL, ROLA_CZLONEK)

#: Zaproszenie traci ważność po tylu dniach — odsyłacz krążący w skrzynce bez końca
#: to otwarte drzwi do cudzej puli dostępu.
WAZNOSC_ZAPROSZENIA_DNI = 14

#: Ile miejsc ma grupa, gdy plan nie mówi inaczej (plan „Grupa”: `limity["konta"]`).
MIEJSC_DOMYSLNIE = 5


class Grupa(Base):
    """Grupa kont rozliczana wspólnie."""

    __tablename__ = "grupy"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Konto, które płaci i którego pula dostępu obsługuje całą grupę.
    zalozyciel_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    nazwa: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class CzlonekGrupy(Base):
    """Przynależność konta do grupy. Konto należy najwyżej do jednej grupy."""

    __tablename__ = "grupy_czlonkowie"
    __table_args__ = (
        UniqueConstraint("uzytkownik_id", name="uq_grupy_czlonek_uzytkownik"),
        Index("ix_grupy_czlonkowie_grupa", "grupa_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    grupa_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("grupy.id", ondelete="CASCADE"), index=True
    )
    uzytkownik_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    rola: Mapped[str] = mapped_column(String(20), default=ROLA_CZLONEK)
    dolaczyl_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class ZaproszenieGrupy(Base):
    """Zaproszenie do grupy — w bazie skrót tokenu, nigdy sam token."""

    __tablename__ = "grupy_zaproszenia"
    __table_args__ = (Index("ix_grupy_zaproszenia_grupa", "grupa_id"),)

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    grupa_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("grupy.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), index=True)
    zaprosil_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    wygasa_at: Mapped[datetime] = mapped_column(UtcDateTime())
    przyjete_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
