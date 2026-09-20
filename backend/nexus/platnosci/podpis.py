"""Weryfikacja podpisu webhooka Stripe (nagłówek ``Stripe-Signature``).

Podpis liczony jest z surowej treści żądania: ``HMAC-SHA256`` z sekretu ``whsec_…``
nad zapisem ``<znacznik czasu>.<treść>``. Bez ważnego podpisu treść nie jest w ogóle
rozbierana – żądanie kończy się odpowiedzią 400.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

TOLERANCJA_S = 300


class BladPodpisu(Exception):
    """Nagłówek podpisu jest nieobecny, nieczytelny, przeterminowany albo niezgodny."""


def _rozbierz(naglowek: str) -> tuple[str, list[str]]:
    """Zwraca znacznik czasu i listę podpisów ``v1`` z nagłówka."""
    znacznik, podpisy = "", []
    for czesc in naglowek.split(","):
        klucz, _, wartosc = czesc.strip().partition("=")
        if klucz == "t":
            znacznik = wartosc
        elif klucz == "v1":
            podpisy.append(wartosc)
    return znacznik, podpisy


def zweryfikuj_podpis(
    ladunek: bytes,
    naglowek: str,
    sekret: str,
    tolerancja_s: int = TOLERANCJA_S,
    teraz: float | None = None,
) -> None:
    """Sprawdza podpis żądania webhooka; przy niezgodności zgłasza ``BladPodpisu``."""
    if not sekret:
        raise BladPodpisu("Webhook nie jest skonfigurowany: brak sekretu podpisu.")
    if not naglowek:
        raise BladPodpisu("Żądanie bez nagłówka Stripe-Signature.")
    znacznik, podpisy = _rozbierz(naglowek)
    if not znacznik.isdigit() or not podpisy:
        raise BladPodpisu("Nagłówek Stripe-Signature jest nieczytelny.")
    chwila = time.time() if teraz is None else teraz
    if tolerancja_s and abs(chwila - int(znacznik)) > tolerancja_s:
        raise BladPodpisu("Znacznik czasu podpisu jest poza dopuszczalnym oknem.")
    oczekiwany = hmac.new(
        sekret.encode("utf-8"), f"{znacznik}.".encode() + ladunek, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(oczekiwany, podpis) for podpis in podpisy):
        raise BladPodpisu("Podpis żądania nie zgadza się z sekretem webhooka.")


def odczytaj_zdarzenie(
    ladunek: bytes,
    naglowek: str,
    sekret: str,
    tolerancja_s: int = TOLERANCJA_S,
    teraz: float | None = None,
) -> dict[str, Any]:
    """Weryfikuje podpis i zwraca zdarzenie Stripe jako słownik."""
    zweryfikuj_podpis(ladunek, naglowek, sekret, tolerancja_s, teraz)
    try:
        zdarzenie = json.loads(ladunek.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as blad:
        raise BladPodpisu("Treść zdarzenia nie jest poprawnym JSON-em.") from blad
    if not isinstance(zdarzenie, dict) or not isinstance(zdarzenie.get("id"), str):
        raise BladPodpisu("Zdarzenie bez identyfikatora.")
    return zdarzenie


def podpisz_ladunek(ladunek: bytes, sekret: str, znacznik: int | None = None) -> str:
    """Buduje nagłówek ``Stripe-Signature`` – używane w testach i przy próbach lokalnych."""
    chwila = int(time.time()) if znacznik is None else znacznik
    podpis = hmac.new(sekret.encode("utf-8"), f"{chwila}.".encode() + ladunek, hashlib.sha256).hexdigest()
    return f"t={chwila},v1={podpis}"
