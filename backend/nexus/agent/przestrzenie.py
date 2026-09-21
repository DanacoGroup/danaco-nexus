"""Przestrzenie projektów modułu Kod (``<data_dir>/kod/<nazwa>``) i bezpieczne ścieżki w nich."""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from nexus.config import Settings
from nexus.db import ADMIN_OWNER

PROJECT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
DRIVE = re.compile(r"[A-Za-z]:")
#: Wykaz właścicieli projektów. Katalog projektu nie ma pola konta, a projekt to miejsce,
#: w którym uruchamiają się programy — bez tego wykazu każda sesja sięgałaby do cudzego.
WLASCICIELE = ".wlasciciele.json"


class WorkspaceError(ValueError):
    """Niepoprawna nazwa projektu lub ścieżka spoza projektu."""


def valid_project_name(name: str) -> bool:
    """Nazwa katalogu projektu: litery, cyfry, ``._-``, bez ``..`` i ukrytych katalogów."""
    return bool(PROJECT_NAME.fullmatch(name)) and ".." not in name


def project_dir(settings: Settings, name: str) -> Path:
    """Katalog projektu (bez sprawdzania istnienia); błąd dla niepoprawnej nazwy."""
    if not valid_project_name(name):
        raise WorkspaceError("Niepoprawna nazwa projektu (litery, cyfry, kropka, podkreślnik, myślnik).")
    return settings.kod_dir / name


def existing_project(settings: Settings, name: str) -> Path | None:
    """Katalog istniejącego projektu albo ``None``."""
    try:
        path = project_dir(settings, name)
    except WorkspaceError:
        return None
    return path if path.is_dir() and not path.is_symlink() else None


class WykazNieczytelny(WorkspaceError):
    """Wykaz właścicieli istnieje, ale nie da się go odczytać.

    To nie jest to samo, co brak wykazu. Pusty wykaz znaczy „wszystko należy do właściciela
    instalacji” — gdyby uszkodzony plik dawał ten sam wynik, jedna nieudana zapisana bajtem
    operacja przepisałaby projekty wszystkich kont na administratora. Lepiej odmówić obsługi
    niż po cichu zmienić właściciela.
    """


def _wykaz(settings: Settings) -> dict[str, str]:
    """Zawartość wykazu właścicieli. Brak pliku = pusty wykaz; plik nieczytelny = wyjątek."""
    plik = settings.kod_dir / WLASCICIELE
    try:
        tresc = plik.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as blad:
        raise WykazNieczytelny("Nie udało się odczytać wykazu właścicieli projektów.") from blad
    try:
        dane = json.loads(tresc)
    except json.JSONDecodeError as blad:
        raise WykazNieczytelny("Wykaz właścicieli projektów jest uszkodzony.") from blad
    if not isinstance(dane, dict):
        raise WykazNieczytelny("Wykaz właścicieli projektów ma nieoczekiwaną postać.")
    return {str(klucz): str(wartosc) for klucz, wartosc in dane.items()}


@contextmanager
def _pod_blokada(settings: Settings) -> Iterator[None]:
    """Wyłączny dostęp do wykazu na czas odczytu-zmiany-zapisu.

    Bez tego dwa konta zakładające projekt w tej samej chwili czytają ten sam wykaz
    i drugi zapis kasuje pierwszy — projekt zostaje bez właściciela, czyli trafia do
    właściciela instalacji.
    """
    settings.kod_dir.mkdir(parents=True, exist_ok=True)
    zamek = settings.kod_dir / ".wlasciciele.lock"
    with zamek.open("a+") as uchwyt:
        fcntl.flock(uchwyt, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(uchwyt, fcntl.LOCK_UN)


def _zapisz_wykaz(settings: Settings, wykaz: dict[str, str]) -> None:
    """Zapisuje wykaz w całości (podmiana pliku, więc odczyt nigdy nie widzi połowy)."""
    settings.kod_dir.mkdir(parents=True, exist_ok=True)
    uchwyt, tymczasowy = tempfile.mkstemp(dir=settings.kod_dir, prefix=".wlasciciele-")
    try:
        with os.fdopen(uchwyt, "w", encoding="utf-8") as plik:
            json.dump(wykaz, plik, ensure_ascii=False, indent=1)
        os.replace(tymczasowy, settings.kod_dir / WLASCICIELE)
    except BaseException:
        Path(tymczasowy).unlink(missing_ok=True)
        raise


def wlasciciel_projektu(settings: Settings, name: str) -> uuid.UUID:
    """Konto, do którego należy projekt; projekty sprzed wykazu należą do właściciela instalacji."""
    zapis = _wykaz(settings).get(name, "")
    try:
        return uuid.UUID(zapis)
    except ValueError:
        return ADMIN_OWNER


def przypisz_projekt(settings: Settings, name: str, owner: uuid.UUID) -> None:
    """Zapisuje konto zakładające projekt (pod blokadą, bo to odczyt-zmiana-zapis)."""
    with _pod_blokada(settings):
        wykaz = _wykaz(settings)
        wykaz[name] = str(owner)
        _zapisz_wykaz(settings, wykaz)


def zapomnij_projekt(settings: Settings, name: str) -> None:
    """Usuwa wpis skasowanego projektu, aby nazwa dała się założyć na nowo."""
    with _pod_blokada(settings):
        wykaz = _wykaz(settings)
        if wykaz.pop(name, None) is not None:
            _zapisz_wykaz(settings, wykaz)


def projekt_konta(settings: Settings, name: str, owner: uuid.UUID) -> Path | None:
    """Katalog projektu należącego do ``owner``; cudzy projekt jest jak nieistniejący."""
    path = existing_project(settings, name)
    if path is None or wlasciciel_projektu(settings, name) != owner:
        return None
    return path


def projekty_konta(settings: Settings, owner: uuid.UUID) -> list[Path]:
    """Katalogi projektów należących do konta (bez katalogów ukrytych i dowiązań)."""
    root = settings.kod_dir
    if not root.is_dir():
        return []
    return [
        path
        for path in root.iterdir()
        if path.is_dir()
        and not path.is_symlink()
        and not path.name.startswith(".")
        and wlasciciel_projektu(settings, path.name) == owner
    ]


def safe_path(root: Path, relative: str) -> Path:
    """Ścieżka wewnątrz projektu; odrzuca ścieżki bezwzględne, ``..`` i dowiązania na zewnątrz."""
    relative = (relative or "").replace("\\", "/").rstrip("/")
    if "\x00" in relative:
        raise WorkspaceError("Niepoprawna ścieżka.")
    candidate = Path(relative)
    if (
        relative.startswith("/")
        or DRIVE.match(relative)
        or candidate.is_absolute()
        or any(part == ".." for part in candidate.parts)
    ):
        raise WorkspaceError("Ścieżka musi leżeć wewnątrz projektu.")
    base = root.resolve()
    resolved = (base / candidate).resolve()
    if resolved != base and not resolved.is_relative_to(base):
        raise WorkspaceError("Ścieżka musi leżeć wewnątrz projektu.")
    return resolved
