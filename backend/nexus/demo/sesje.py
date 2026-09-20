"""Sesje gościa: token w ciasteczku, limity, katalog roboczy i kasowanie danych.

Sesja istnieje wyłącznie w pamięci procesu API. Jej pliki leżą w osobnym katalogu
``<work_dir>/demo/<sesja>`` – magazyn plików użytkownika, baza rozmów i baza wiedzy
użytkownika nie są tu używane. Wygaśnięcie sesji kasuje katalog wraz z zawartością.
"""

from __future__ import annotations

import logging
import secrets
import shutil
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.config import Settings

logger = logging.getLogger(__name__)

COOKIE_NAME = "nexus_demo"
COOKIE_PATH = "/api/demo"


@dataclass(frozen=True, slots=True)
class Limity:
    """Twarde ograniczenia piaskownicy (wspólne dla wszystkich gości)."""

    wiadomosci: int = 6
    plik_mb: int = 8
    plikow: int = 4
    zycie_minut: int = 30
    sesje_z_adresu: int = 3
    zapytan_na_minute: int = 30
    znakow_wiadomosci: int = 500
    przebiegow_rownolegle: int = 1

    def payload(self) -> dict[str, int]:
        """Limity w postaci czytanej przez interfejs."""
        return {
            "wiadomosci": self.wiadomosci,
            "plik_mb": self.plik_mb,
            "plikow": self.plikow,
            "zycie_minut": self.zycie_minut,
            "znakow_wiadomosci": self.znakow_wiadomosci,
        }


LIMITY = Limity()

# Rodzaje plików przyjmowane od gościa: skany i zdjęcia, PDF, nagranie, zwykły tekst.
# Każdy wpis to rozszerzenie, typ MIME i początek pliku, który musi się zgadzać.
DOZWOLONE: dict[str, tuple[str, tuple[bytes, ...]]] = {
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".webp": ("image/webp", (b"RIFF",)),
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".wav": ("audio/wav", (b"RIFF",)),
    ".mp3": ("audio/mpeg", (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")),
    ".m4a": ("audio/mp4", (b"\x00\x00\x00",)),
    ".txt": ("text/plain", ()),
    ".md": ("text/markdown", ()),
}


class BladPiaskownicy(Exception):
    """Naruszenie zasad piaskownicy opisane dla gościa."""

    def __init__(self, komunikat: str, kod: int = 400) -> None:
        super().__init__(komunikat)
        self.kod = kod


@dataclass(slots=True)
class DemoPlik:
    """Plik widoczny w jednej sesji gościa (przykładowy albo wgrany)."""

    id: str
    nazwa: str
    mime: str
    rozmiar: int
    sciezka: Path
    zrodlo: str = "przyklad"

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nazwa": self.nazwa,
            "mime": self.mime,
            "rozmiar": self.rozmiar,
            "zrodlo": self.zrodlo,
        }


@dataclass(slots=True)
class DemoSesja:
    """Stan jednej sesji gościa."""

    token: str
    adres: str
    katalog: Path
    utworzona: float
    wygasa: float
    wiadomosci_uzyte: int = 0
    pliki: dict[str, DemoPlik] = field(default_factory=dict)
    przebiegi: dict[str, Any] = field(default_factory=dict)
    zaindeksowane: list[uuid.UUID] = field(default_factory=list)

    @property
    def pozostalo(self) -> int:
        """Ile wiadomości gościowi jeszcze zostało."""
        return max(0, LIMITY.wiadomosci - self.wiadomosci_uzyte)

    @property
    def wygasla(self) -> bool:
        return time.time() >= self.wygasa

    def katalog_plikow(self) -> Path:
        """Katalog z plikami sesji (tworzony przy pierwszym użyciu)."""
        target = self.katalog / "pliki"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def plik(self, file_id: str) -> DemoPlik:
        """Plik sesji o podanym identyfikatorze."""
        found = self.pliki.get(file_id)
        if found is None or not found.sciezka.is_file():
            raise BladPiaskownicy("Plik nie należy do tej sesji pokazu.", 404)
        return found

    def payload(self) -> dict[str, Any]:
        return {
            "wygasa_za_s": max(0, int(self.wygasa - time.time())),
            "wiadomosci_pozostalo": self.pozostalo,
            "wiadomosci_limit": LIMITY.wiadomosci,
            "pliki": [plik.payload() for plik in self.pliki.values() if plik.zrodlo == "gosc"],
        }


class Tempo:
    """Ograniczenie tempa zapytań z jednego adresu (okno przesuwne)."""

    def __init__(self, na_minute: int) -> None:
        self._limit = na_minute
        self._wpisy: dict[str, deque[float]] = defaultdict(deque)

    def sprawdz(self, adres: str) -> None:
        """Zgłasza błąd 429, gdy adres przekroczył limit zapytań na minutę."""
        wpisy = self._wpisy[adres]
        granica = time.monotonic() - 60.0
        while wpisy and wpisy[0] < granica:
            wpisy.popleft()
        if len(wpisy) >= self._limit:
            raise BladPiaskownicy("Zbyt wiele zapytań z tego adresu. Odczekaj chwilę.", 429)
        wpisy.append(time.monotonic())

    def zapomnij(self, adres: str) -> None:
        self._wpisy.pop(adres, None)


class Piaskownica:
    """Rejestr sesji gościa wraz z ich katalogami roboczymi."""

    def __init__(self, settings: Settings, limity: Limity = LIMITY) -> None:
        self.settings = settings
        self.limity = limity
        self.korzen = settings.work_dir / "demo"
        self.tempo = Tempo(limity.zapytan_na_minute)
        self._sesje: dict[str, DemoSesja] = {}

    def sprzataj(self) -> None:
        """Kasuje sesje, którym upłynął czas życia, razem z ich katalogami."""
        for token, sesja in list(self._sesje.items()):
            if sesja.wygasla:
                self._usun(token, sesja)

    def _usun(self, token: str, sesja: DemoSesja) -> None:
        self._sesje.pop(token, None)
        shutil.rmtree(sesja.katalog, ignore_errors=True)
        logger.info("Zakończono sesję pokazu (%s pliki usunięte).", sesja.katalog.name)

    def utworz(self, adres: str) -> DemoSesja:
        """Nowa sesja gościa; nadmiar sesji z jednego adresu jest odrzucany."""
        self.sprzataj()
        self.tempo.sprawdz(adres)
        z_adresu = sum(1 for sesja in self._sesje.values() if sesja.adres == adres)
        if z_adresu >= self.limity.sesje_z_adresu:
            raise BladPiaskownicy("Z tego adresu działa już maksymalna liczba pokazów.", 429)
        token = secrets.token_urlsafe(24)
        teraz = time.time()
        katalog = self.korzen / uuid.uuid4().hex
        katalog.mkdir(parents=True, exist_ok=True)
        sesja = DemoSesja(
            token=token,
            adres=adres,
            katalog=katalog,
            utworzona=teraz,
            wygasa=teraz + self.limity.zycie_minut * 60,
        )
        self._sesje[token] = sesja
        return sesja

    def pobierz(self, token: str | None) -> DemoSesja | None:
        """Sesja o podanym tokenie albo ``None`` (także gdy wygasła)."""
        if not token:
            return None
        sesja = self._sesje.get(token)
        if sesja is None:
            return None
        if sesja.wygasla:
            self._usun(token, sesja)
            return None
        return sesja

    def wymagaj(self, token: str | None, adres: str) -> DemoSesja:
        """Ważna sesja albo błąd; przy okazji kontroluje tempo zapytań."""
        self.tempo.sprawdz(adres)
        sesja = self.pobierz(token)
        if sesja is None:
            raise BladPiaskownicy("Pokaz wygasł. Odśwież stronę, aby zacząć od nowa.", 401)
        return sesja

    def zuzyj_wiadomosc(self, sesja: DemoSesja) -> None:
        """Odejmuje jedną wiadomość z limitu sesji."""
        if sesja.pozostalo <= 0:
            raise BladPiaskownicy("Limit wiadomości w pokazie został wyczerpany.", 429)
        sesja.wiadomosci_uzyte += 1

    def zakoncz(self, token: str | None) -> bool:
        """Kończy sesję i kasuje jej dane; zwraca informację, czy sesja istniała."""
        sesja = self._sesje.get(token or "")
        if sesja is None:
            return False
        self._usun(token or "", sesja)
        return True

    def dodaj_plik(self, sesja: DemoSesja, nazwa: str, dane: bytes, zrodlo: str = "gosc") -> DemoPlik:
        """Zapisuje plik w katalogu sesji po sprawdzeniu rozszerzenia, rozmiaru i nagłówka."""
        wlasne = sum(1 for plik in sesja.pliki.values() if plik.zrodlo == "gosc")
        if zrodlo == "gosc" and wlasne >= self.limity.plikow:
            raise BladPiaskownicy(f"W pokazie można wgrać najwyżej {self.limity.plikow} pliki.", 429)
        sprawdz_plik(nazwa, dane, self.limity)
        suffix = Path(nazwa).suffix.lower()
        file_id = str(uuid.uuid4())
        # Nazwa na dysku pochodzi wyłącznie z identyfikatora – nazwa od gościa nigdy
        # nie trafia do ścieżki, więc nie może wskazać katalogu ani nadpisać pliku.
        sciezka = sesja.katalog_plikow() / f"{file_id}{suffix}"
        sciezka.write_bytes(dane)
        plik = DemoPlik(
            id=file_id,
            nazwa=bezpieczna_nazwa(nazwa),
            mime=DOZWOLONE[suffix][0],
            rozmiar=len(dane),
            sciezka=sciezka,
            zrodlo=zrodlo,
        )
        sesja.pliki[file_id] = plik
        return plik

    async def zamknij(self) -> None:
        """Kasuje wszystkie sesje (zamknięcie aplikacji)."""
        for token, sesja in list(self._sesje.items()):
            self._usun(token, sesja)


def bezpieczna_nazwa(nazwa: str) -> str:
    """Nazwa pliku do pokazania: bez ścieżek i znaków sterujących."""
    from nexus.storage import safe_filename

    return safe_filename(Path(nazwa).name, "plik")[:120]


def sprawdz_plik(nazwa: str, dane: bytes, limity: Limity = LIMITY) -> None:
    """Sprawdza rozszerzenie, rozmiar i sygnaturę pliku wgrywanego przez gościa."""
    suffix = Path(nazwa).suffix.lower()
    if suffix not in DOZWOLONE:
        dozwolone = ", ".join(sorted(DOZWOLONE))
        raise BladPiaskownicy(f"W pokazie przyjmujemy pliki: {dozwolone}.", 415)
    if not dane:
        raise BladPiaskownicy("Plik jest pusty.", 400)
    if len(dane) > limity.plik_mb * 1024 * 1024:
        raise BladPiaskownicy(f"Plik przekracza limit {limity.plik_mb} MB.", 413)
    _, sygnatury = DOZWOLONE[suffix]
    if sygnatury and not any(dane.startswith(sygnatura) for sygnatura in sygnatury):
        raise BladPiaskownicy("Treść pliku nie odpowiada jego rozszerzeniu.", 415)
    if not sygnatury:
        try:
            dane.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BladPiaskownicy("Plik tekstowy musi być zapisany w UTF-8.", 415) from error
