"""Piaskownica procesu CLI: agent widzi wyłącznie przestrzeń użytkownika.

Instrukcja trybu mówiła agentowi, żeby nie wychodził poza katalog projektu, ale to było
ograniczenie „w dobrej wierze” — narzędzia ``Read`` i ``Bash`` przyjmują ścieżki
bezwzględne, więc sesja programistyczna mogła przeczytać kod samego Nexusa, cudze
projekty na serwerze i pliki producenta. Tutaj to samo ograniczenie egzekwuje jądro:
proces CLI startuje w osobnej przestrzeni montowań (``bwrap``), w której po prostu nie ma
czego czytać.

Co widać w środku:

* ``/usr`` i ``/etc`` tylko do odczytu — biblioteki systemowe, certyfikaty, DNS;
* ``/danaco/programy`` tylko do odczytu — łańcuch narzędzi (node, python, git, pnpm,
  linters), bez którego moduł Kod nie miałby czym budować ani testować;
* katalog projektu użytkownika, profil sesji CLI i katalog roboczy zadania — do zapisu.

Czego nie widać: katalogu z kodem Nexusa, pozostałych projektów na serwerze, katalogu
domowego producenta, kluczy, wydań, kopii i danych innych kont. Tych ścieżek nie da się
odczytać ani wymienić, bo w tej przestrzeni montowań nie istnieją.

Sieć zostaje włączona (``--share-net``): bez niej nie zadziałałby ani silnik modelu, ani
narzędzia sieciowe. Ograniczenie poleceń sieciowych w trybie Kod nadal robią reguły CLI.
"""

from __future__ import annotations

import functools
import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Katalogi systemowe montowane tylko do odczytu.
SYSTEM_RO = ("/usr", "/etc")
# ``/bin``, ``/lib`` itd. są na tym systemie dowiązaniami do ``/usr`` – odtwarzamy je.
SYSTEM_LINKS = (
    ("usr/bin", "/bin"),
    ("usr/sbin", "/sbin"),
    ("usr/lib", "/lib"),
    ("usr/lib64", "/lib64"),
)
# Łańcuch narzędzi serwera: programy, nie dane. Bez tego moduł Kod nie ma czym pracować.
TOOLCHAIN = Path("/danaco/programy")
# Katalog z konfiguracją DNS systemd-resolved (``/etc/resolv.conf`` prowadzi do niego).
DNS_RUNTIME = Path("/run/systemd/resolve")

#: Zmienne środowiska, które wolno wpuścić do piaskownicy.
#:
#: ``bwrap`` bez ``--clearenv`` dziedziczy całe środowisko procesu roboczego, a w nim stoją
#: adres bazy, ścieżki do plików z kluczami Stripe i hasłem chmury oraz adresy usług
#: wewnętrznych. Program uruchomiony w piaskownicy (``python``, ``node``, ``make``) czyta
#: je jednym wywołaniem — to wyciek, choć samych plików z sekretami i tak nie widać.
#: Dlatego środowisko jest budowane od zera: tylko to, bez czego programy nie ruszą.
ZMIENNE_DOZWOLONE = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TERM",
    "TMPDIR",
    "TZ",
    "USER",
    "LOGNAME",
)


def srodowisko(dodatkowe: dict[str, str] | None = None, *, dom: str = "") -> dict[str, str]:
    """Środowisko procesu w piaskownicy: wykaz dozwolonych zmiennych plus to, co podano.

    Buduje od zera, a nie odejmuje od ``os.environ`` — wykaz odejmowany trzeba by
    uzupełniać przy każdej nowej zmiennej, a zapomnienie kończy się wyciekiem.
    """
    czyste = {nazwa: os.environ[nazwa] for nazwa in ZMIENNE_DOZWOLONE if nazwa in os.environ}
    czyste.setdefault("PATH", "/danaco/programy/bin:/usr/local/bin:/usr/bin:/bin")
    if dom:
        czyste["HOME"] = dom
        czyste["TMPDIR"] = dom
    return {**czyste, **(dodatkowe or {})}


def znajdz_bwrap() -> str:
    """Ścieżka do ``bwrap`` albo pusty napis, gdy program nie jest zainstalowany."""
    return shutil.which("bwrap") or ""


@functools.cache
def dostepna() -> bool:
    """Czy piaskownica działa na tym systemie (``bwrap`` uruchamia proces testowy)."""
    program = znajdz_bwrap()
    if not program:
        return False
    try:
        sprawdzenie = [program, "--unshare-all", "--share-net", "--ro-bind", "/usr", "/usr"]
        for cel, dowiazanie in SYSTEM_LINKS:
            if Path(dowiazanie).is_symlink():
                sprawdzenie += ["--symlink", cel, dowiazanie]
        wynik = subprocess.run(  # noqa: S603 - stała lista argumentów
            [*sprawdzenie, "--", "/usr/bin/true"],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if wynik.returncode != 0:
        logger.warning("bwrap nie działa na tym systemie: %s", wynik.stderr.decode("utf-8", "replace")[:200])
    return wynik.returncode == 0


def _katalogi_zapisu(zapis: tuple[Path, ...]) -> list[Path]:
    """Katalogi do zapisu bez powtórzeń i bez ścieżek zawartych w innych."""
    unikalne: list[Path] = []
    for katalog in sorted({sciezka.resolve() for sciezka in zapis if sciezka}, key=lambda p: len(p.parts)):
        if any(katalog.is_relative_to(wyzej) for wyzej in unikalne):
            continue
        unikalne.append(katalog)
    return unikalne


def polecenie(
    program: str,
    polecenie_cli: list[str],
    *,
    cwd: Path,
    zapis: tuple[Path, ...],
    odczyt: tuple[Path, ...] = (),
    siec: bool = True,
    srodowisko_procesu: dict[str, str] | None = None,
) -> list[str]:
    """Owija polecenie CLI w ``bwrap``.

    ``zapis`` to katalogi, w których agent ma pracować (projekt, profil sesji, katalog
    roboczy zadania); ``odczyt`` to dodatkowe katalogi tylko do odczytu; ``siec`` wpuszcza
    proces do sieci (potrzebne procesowi CLI, niepotrzebne programom liczącym na plikach);
    ``srodowisko_procesu`` to komplet zmiennych widocznych w środku — bez niego wchodzi
    sam wykaz z ``srodowisko()``. Katalogi pojawiają
    się w piaskownicy pod tymi samymi ścieżkami, więc ani polecenie CLI, ani konfiguracja
    MCP nie wymagają tłumaczenia ścieżek.
    """
    args = [
        program,
        "--unshare-all",
        # Środowisko procesu roboczego zostaje za progiem: ``--clearenv`` odcina wszystko,
        # a do środka wchodzi wyłącznie to, co poda ``srodowisko_procesu``.
        "--clearenv",
        # Proces ginie razem z serwerem – po awarii nie zostaje osierocona sesja CLI.
        "--die-with-parent",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/run",
    ]
    # Sieć zostaje tam, gdzie jest potrzebna (proces CLI rozmawia z silnikiem modelu).
    # Program, który tylko przelicza pliki, dostaje przestrzeń sieciową bez żadnego łącza.
    if siec:
        args.insert(2, "--share-net")
    # ``/etc/resolv.conf`` jest tu dowiązaniem do ``/run/systemd/resolve``; bez tego katalogu
    # w piaskownicy nie działa rozwiązywanie nazw, czyli nie działa ani silnik, ani sieć narzędzi.
    if DNS_RUNTIME.is_dir():
        args += ["--ro-bind", str(DNS_RUNTIME), str(DNS_RUNTIME)]
    for katalog in SYSTEM_RO:
        if Path(katalog).is_dir():
            args += ["--ro-bind", katalog, katalog]
    for cel, dowiazanie in SYSTEM_LINKS:
        if Path(dowiazanie).is_symlink():
            args += ["--symlink", cel, dowiazanie]
    if TOOLCHAIN.is_dir():
        args += ["--ro-bind", str(TOOLCHAIN), str(TOOLCHAIN)]
    for katalog in odczyt:
        if katalog and katalog.is_dir():
            pelna = katalog.resolve()
            args += ["--ro-bind", str(pelna), str(pelna)]
    for katalog in _katalogi_zapisu(zapis):
        args += ["--bind", str(katalog), str(katalog)]
    # Ścieżki muszą być bezwzględne: w piaskownicy nie ma katalogu bieżącego procesu
    # roboczego, więc ścieżka względna wskazywałaby tam, gdzie nic nie zamontowano.
    for nazwa, wartosc in (srodowisko_procesu or srodowisko()).items():
        args += ["--setenv", nazwa, wartosc]
    args += ["--chdir", str(cwd.resolve()), "--"]
    return [*args, *polecenie_cli]
