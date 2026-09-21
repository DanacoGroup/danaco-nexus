"""Przeglądarka agenta: jedno okno Chromium na czas zadania, sterowane z Pythona.

Sterownikiem jest ``przegladarka.mjs`` — proces Node z otwartą kartą, który przyjmuje
polecenia wierszami JSON. Trzymamy go po stronie serwera MCP (jeden proces na zadanie),
więc kolejne wywołania narzędzi trafiają na tę samą kartę: agent może otworzyć stronę,
kliknąć, wypełnić formularz i przejść dalej, zamiast za każdym razem zaczynać od adresu.

Adresy przechodzą przez ``research.web.check_url`` — tę samą ochronę przed SSRF, co odczyt
strony po HTTP. Sieć wewnętrzna serwera nie jest dla agenta dostępna ani tą drogą.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STEROWNIK = Path(__file__).with_name("przegladarka.mjs")
NODE = "/danaco/programy/node/bin/node"
MODULY_NODE = "/danaco/programy/node/lib/node_modules"
PRZEGLADARKI = "/danaco/programy/playwright"
# Akcja w przeglądarce (wczytanie strony, kliknięcie z przeładowaniem) potrafi potrwać;
# powyżej tego czasu uznajemy kartę za zawieszoną i zamykamy sterownik.
LIMIT_ODPOWIEDZI_S = 90


class BladPrzegladarki(Exception):
    """Sterownik nie wystartował albo nie wykonał polecenia."""


class Przegladarka:
    """Uchwyt do procesu sterownika; jeden na proces serwera MCP (czyli na zadanie)."""

    def __init__(self) -> None:
        self._proces: subprocess.Popen[str] | None = None
        self._zamek = threading.Lock()

    def _srodowisko(self) -> dict[str, str]:
        return {
            **os.environ,
            "NODE_PATH": MODULY_NODE,
            "NEXUS_PLAYWRIGHT": f"{MODULY_NODE}/playwright",
            "PLAYWRIGHT_BROWSERS_PATH": PRZEGLADARKI,
        }

    def _uruchom(self) -> subprocess.Popen[str]:
        if not STEROWNIK.is_file():
            raise BladPrzegladarki("Brak sterownika przeglądarki na serwerze.")
        if not Path(NODE).exists():
            raise BladPrzegladarki("Brak środowiska Node do uruchomienia przeglądarki.")
        return subprocess.Popen(  # noqa: S603 - stała ścieżka, bez powłoki
            [NODE, str(STEROWNIK)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self._srodowisko(),
            cwd=MODULY_NODE,
        )

    def polecenie(self, dane: dict[str, Any]) -> dict[str, Any]:
        """Wysyła polecenie do sterownika i zwraca odpowiedź (stan karty albo błąd)."""
        with self._zamek:
            if self._proces is None or self._proces.poll() is not None:
                self._proces = self._uruchom()
            proces = self._proces
            assert proces.stdin is not None and proces.stdout is not None
            try:
                proces.stdin.write(json.dumps(dane, ensure_ascii=False) + "\n")
                proces.stdin.flush()
            except (BrokenPipeError, ValueError) as blad:
                self._zakoncz()
                raise BladPrzegladarki("Przeglądarka przestała odpowiadać.") from blad

            wiersz = self._czytaj(proces)
            try:
                odpowiedz = json.loads(wiersz)
            except ValueError as blad:
                self._zakoncz()
                raise BladPrzegladarki("Przeglądarka zwróciła nieczytelną odpowiedź.") from blad
            if not odpowiedz.get("ok"):
                raise BladPrzegladarki(str(odpowiedz.get("blad") or "Nie udało się wykonać działania."))
            return odpowiedz

    def _czytaj(self, proces: subprocess.Popen[str]) -> str:
        """Jeden wiersz odpowiedzi z limitem czasu (wątek, bo strumień nie ma timeoutu)."""
        wynik: list[str] = []

        def pobierz() -> None:
            assert proces.stdout is not None
            wynik.append(proces.stdout.readline())

        watek = threading.Thread(target=pobierz, daemon=True)
        watek.start()
        watek.join(LIMIT_ODPOWIEDZI_S)
        if watek.is_alive() or not wynik or not wynik[0]:
            self._zakoncz()
            raise BladPrzegladarki("Strona nie odpowiedziała w wyznaczonym czasie.")
        return wynik[0]

    def _zakoncz(self) -> None:
        proces, self._proces = self._proces, None
        if proces is None:
            return
        proces.kill()
        try:
            proces.communicate(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - proces już nie żyje
            pass

    def zamknij(self) -> None:
        """Zamyka okno i kończy sterownik (wywoływane przy sprzątaniu po zadaniu)."""
        with self._zamek:
            self._zakoncz()


_przegladarka = Przegladarka()


def przegladarka() -> Przegladarka:
    """Przeglądarka tego procesu (jedna na zadanie)."""
    return _przegladarka
