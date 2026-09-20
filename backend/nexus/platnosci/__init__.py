"""Sprzedaż subskrypcji: plany, zakup przez Stripe, faktury, kupony i limity planów.

Moduł nie wymaga biblioteki ``stripe`` – dostęp do API opisuje protokół
``nexus.platnosci.klient.KlientStripe`` z implementacją HTTP na ``httpx``.
"""

from __future__ import annotations

from nexus.platnosci.konfiguracja import UstawieniaPlatnosci, adresy_powrotu, ustawienia_platnosci
from nexus.platnosci.uprawnienia import LimitPrzekroczony, Limity, limity_uzytkownika, sprawdz_limit

__all__ = [
    "LimitPrzekroczony",
    "Limity",
    "UstawieniaPlatnosci",
    "adresy_powrotu",
    "limity_uzytkownika",
    "sprawdz_limit",
    "ustawienia_platnosci",
]
