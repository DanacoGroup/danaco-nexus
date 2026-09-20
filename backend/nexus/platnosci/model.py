"""Tabele modułu płatności: plany, subskrypcje, faktury, kupony i dziennik zdarzeń Stripe.

Tabele rejestrują się na ``nexus.db.Base`` przy imporcie routera modułu
(``nexus/api/modules/platnosci.py``), czyli przed wywołaniem ``create_schema``
w cyklu życia aplikacji – ``create_all`` zakłada je razem z pozostałymi.
Kwoty są zapisane w groszach (liczby całkowite), nigdy jako liczby zmiennoprzecinkowe.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from nexus.db import Base, JsonType, UtcDateTime, utcnow

# Stany subskrypcji w Nexusie (wartości kolumny ``status``).
STATUS_BRAK = "brak"
STATUS_PROBNA = "probna"
STATUS_AKTYWNA = "aktywna"
STATUS_ZALEGLA = "zalegla"
STATUS_ANULOWANA = "anulowana"
STATUS_NIEPELNA = "niepelna"
STATUSY_UPRAWNIAJACE = frozenset({STATUS_PROBNA, STATUS_AKTYWNA, STATUS_ZALEGLA})


class Plan(Base):
    """Plan sprzedażowy: nazwa, opis, ceny w groszach i limity egzekwowane przez serwer.

    Zawartość tabeli pochodzi z katalogu w kodzie (``nexus.platnosci.plany``) oraz
    z kwot podanych w zmiennych środowiskowych; klient nigdy nie ustala ceny.
    """

    __tablename__ = "platnosci_plany"

    kod: Mapped[str] = mapped_column(String(30), primary_key=True)
    nazwa: Mapped[str] = mapped_column(String(60))
    opis: Mapped[str] = mapped_column(Text, default="")
    cena_miesiac_gr: Mapped[int] = mapped_column(Integer, default=0)
    cena_rok_gr: Mapped[int] = mapped_column(Integer, default=0)
    # Limity planu, np. {"zadania_rownolegle": 4, "plik_mb": 2048, "automatyzacje": 20}.
    limity: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    kolejnosc: Mapped[int] = mapped_column(Integer, default=0)
    aktywny: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class Subskrypcja(Base):
    """Subskrypcja użytkownika: plan, okres rozliczeniowy, stan i powiązania ze Stripe."""

    __tablename__ = "platnosci_subskrypcje"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    uzytkownik: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    plan_kod: Mapped[str] = mapped_column(String(30), default="")
    status: Mapped[str] = mapped_column(String(20), default=STATUS_BRAK, index=True)
    # miesiac albo rok (pusty, dopóki nie ma płatnej subskrypcji).
    okres: Mapped[str] = mapped_column(String(10), default="")
    stripe_customer_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    stripe_subscription_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    okres_od: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    okres_do: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    anuluj_na_koniec: Mapped[bool] = mapped_column(Boolean, default=False)
    kupon: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class Faktura(Base):
    """Faktura Stripe: kwota, stan zapłaty i adresy do pobrania dokumentu."""

    __tablename__ = "platnosci_faktury"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    stripe_invoice_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    uzytkownik: Mapped[str] = mapped_column(String(100), default="", index=True)
    numer: Mapped[str] = mapped_column(String(60), default="")
    kwota_gr: Mapped[int] = mapped_column(Integer, default=0)
    waluta: Mapped[str] = mapped_column(String(3), default="pln")
    # open | paid | uncollectible | void | draft – stan nadany przez Stripe.
    status: Mapped[str] = mapped_column(String(20), default="")
    pdf_url: Mapped[str] = mapped_column(Text, default="")
    strona_url: Mapped[str] = mapped_column(Text, default="")
    wystawiona_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    oplacona_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class Kupon(Base):
    """Kod rabatowy Stripe (kod promocyjny) sprawdzony przed zakupem."""

    __tablename__ = "platnosci_kupony"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kod: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    stripe_promotion_id: Mapped[str] = mapped_column(String(64), default="")
    stripe_coupon_id: Mapped[str] = mapped_column(String(64), default="")
    rabat_procent: Mapped[int] = mapped_column(Integer, default=0)
    rabat_gr: Mapped[int] = mapped_column(Integer, default=0)
    waluta: Mapped[str] = mapped_column(String(3), default="pln")
    opis: Mapped[str] = mapped_column(String(200), default="")
    aktywny: Mapped[bool] = mapped_column(Boolean, default=True)
    wygasa_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    sprawdzony_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class ZdarzenieStripe(Base):
    """Dziennik zdarzeń webhooka. Klucz główny to identyfikator zdarzenia Stripe.

    Zapis powstaje przed jakąkolwiek zmianą stanu, więc powtórzone doręczenie tego
    samego zdarzenia jest rozpoznawane po kluczu głównym i pomijane (idempotencja).
    """

    __tablename__ = "platnosci_zdarzenia"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    typ: Mapped[str] = mapped_column(String(60), index=True)
    # przyjete | przetworzone | pominiete | blad
    status: Mapped[str] = mapped_column(String(20), default="przyjete", index=True)
    blad: Mapped[str] = mapped_column(Text, default="")
    ladunek: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    otrzymane_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    przetworzone_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
