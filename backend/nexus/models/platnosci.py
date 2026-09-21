"""Rejestracja tabel sprzedaży i kredytów przed ``create_all``.

Tabele planów, subskrypcji i faktur powstają przy imporcie modułu API sprzedaży, a ten
ładuje się dopiero przy budowie aplikacji. Kredyty muszą istnieć wcześniej: nalicza je
także proces roboczy, który routerów API nie importuje. Ten plik wciąga oba zestawy,
więc schemat powstaje niezależnie od kolejności ładowania modułów.
"""

from __future__ import annotations

from nexus.platnosci.kredyty import RuchKredytow, SaldoKredytow  # noqa: F401
from nexus.platnosci.model import (  # noqa: F401
    Faktura,
    Kupon,
    Plan,
    Subskrypcja,
    ZdarzenieStripe,
)

# Kolumna dochodzi do tabeli, która na wdrożonych instalacjach już istnieje — ``create_all``
# nie zmienia istniejących tabel, więc dopisuje ją ``Database.create_schema``.
# Domyślne 1 jest poprawne wstecz: przed planem „Grupa” każda subskrypcja była jednoosobowa.
COLUMNS: list[tuple[str, str, str, str]] = [
    ("platnosci_subskrypcje", "miejsca", "INTEGER NOT NULL DEFAULT 1", "INTEGER NOT NULL DEFAULT 1"),
]
