"""Plik `.env.example` musi dać się wczytać i powłoką, i systemd.

`deploy/nexus-cli.sh` wczytuje konfigurację poleceniem `.` (source). Wartość z niecytowanym
średnikiem rozpada się wtedy na dwa polecenia — tak przestały działać **wszystkie** polecenia
administracyjne, bo cennik Stripe jest zapisany jako `kod:okres=price_…;kod:okres=price_…`.
systemd czyta ten sam plik jako zwykły EnvironmentFile i problemu nie widzi, więc usługi
działały dalej i nic nie zwracało uwagi.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

KORZEN = Path(__file__).resolve().parents[2]
WZOR = KORZEN / ".env.example"
#: Pliki etapów wdrożenia czyta systemd, ale sięga po nie także `deploy/wydania/*.sh`.
ETAPY = (KORZEN / "deploy/wydania/przedsionek.env", KORZEN / "deploy/wydania/produkcja.env")
#: Znaki, które powłoka czyta jako składnię albo rozdzielacz, a nie jako treść wartości.
#: Spacja jest tu równie groźna co średnik: `NAZWA=Danaco Nexus` to przypisanie i próba
#: uruchomienia polecenia „Nexus”.
SKLADNIA_POWLOKI = ";&|<>`$()" + " \t*?[]{}~!#"
WPIS = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)=(?!")(.*)$')


def test_wartosci_ze_skladnia_powloki_sa_w_cudzyslowach() -> None:
    niecytowane = []
    for numer, wiersz in enumerate(WZOR.read_text(encoding="utf-8").splitlines(), start=1):
        dopasowanie = WPIS.match(wiersz)
        if dopasowanie and any(znak in dopasowanie.group(2) for znak in SKLADNIA_POWLOKI):
            niecytowane.append(f"{numer}: {dopasowanie.group(1)}")

    assert niecytowane == [], f"ujmij wartość w cudzysłów, inaczej `source` ją rozetnie: {niecytowane}"


def test_wzor_konfiguracji_daje_sie_wczytac_powloka() -> None:
    """Sprawdzenie wprost: `bash -c 'set -a; . .env.example'` ma kończyć się zerem."""
    wynik = subprocess.run(
        ["bash", "-c", f'set -euo pipefail; set -a; . "{WZOR}"; set +a'],
        capture_output=True,
        text=True,
        check=False,
    )

    assert wynik.returncode == 0, wynik.stderr[-400:]
    assert not wynik.stderr.strip(), wynik.stderr[-400:]


def test_python_czyta_ten_sam_plik_tak_samo() -> None:
    """Cudzysłowy nie mogą wejść do wartości — pydantic-settings czyta je przez os.environ."""
    odczyt = "import os; print(os.environ['NEXUS_DATABASE_URL'])"
    polecenie = f'set -a; . "{WZOR}"; set +a; {sys.executable} -c "{odczyt}"'
    wynik = subprocess.run(["bash", "-c", polecenie], capture_output=True, text=True, check=False)

    assert wynik.returncode == 0, wynik.stderr[-300:]
    assert wynik.stdout.startswith("postgresql+asyncpg://"), wynik.stdout[:120]


def test_pliki_etapow_tez_daja_sie_wczytac() -> None:
    """Przedsionek i produkcja dokładają własne wpisy — one też muszą przejść przez `source`."""
    for plik in ETAPY:
        wynik = subprocess.run(
            ["bash", "-c", f'set -euo pipefail; set -a; . "{plik}"; set +a'],
            capture_output=True,
            text=True,
            check=False,
        )
        assert wynik.returncode == 0, f"{plik.name}: {wynik.stderr[-300:]}"


def test_diagnostyka_widzi_sprzecznosc_licencji_ze_sprzedaza(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprzedaż narzędzia o licencji niekomercyjnej ma być widoczna przy każdym wdrożeniu.

    Sprzeczność powstaje sama: narzędzie stoi w rejestrze od dawna, a warunek „dopóki
    produkt nie jest sprzedawany” przestaje obowiązywać w chwili, gdy ktoś wpisze klucz
    Stripe. Nic się wtedy nie psuje, więc nikt tego nie zauważa — poza diagnostyką.
    """
    from nexus.config import Settings
    from nexus.doctor import NARZEDZIA_NIEKOMERCYJNE, check_licencje_narzedzi
    from nexus.tools import registry

    assert set(NARZEDZIA_NIEKOMERCYJNE) <= set(registry.names()), (
        "wykaz narzędzi niekomercyjnych wskazuje nazwę spoza rejestru — zdezaktualizował się"
    )
    ustawienia = Settings()

    monkeypatch.delenv("NEXUS_PLATNOSCI_STRIPE_KLUCZ_PLIK", raising=False)
    monkeypatch.setenv("NEXUS_PLATNOSCI_STRIPE_KLUCZ", "")
    bez_sprzedazy = check_licencje_narzedzi(ustawienia)
    assert bez_sprzedazy.ok is True
    assert "sprzedaż wyłączona" in bez_sprzedazy.detail

    monkeypatch.setenv("NEXUS_PLATNOSCI_STRIPE_KLUCZ", "sk_test_licencja")
    ze_sprzedaza = check_licencje_narzedzi(ustawienia)
    assert ze_sprzedaza.ok is False
    assert "find_faces" in ze_sprzedaza.detail


def test_diagnostyka_liczy_wydania_i_wolne_miejsce(tmp_path: Path) -> None:
    """Stare wydania zjadają dysk po cichu — kontrola ma je policzyć i podpowiedzieć sprzątanie.

    Każde wydanie to ok. 0,65 GB, a powstaje ich po kilkanaście dziennie; nic ich nie kasuje
    samoczynnie. Brak miejsca odbija się naraz na bazie, kopii zapasowej i pracy agenta,
    a widać go dopiero po awarii.
    """
    from nexus.config import Settings
    from nexus.doctor import WYDAN_PROG, check_miejsce

    dane = tmp_path / "dane" / "app"
    dane.mkdir(parents=True)
    wynik = check_miejsce(Settings(data_dir=dane))

    # Na dysku, na którym to leci, miejsce jest; kontrola ma o nim powiedzieć wprost.
    assert wynik.ok is True
    assert "wolne" in wynik.detail and "GB" in wynik.detail

    # Katalog wydań liczony jest od korzenia repozytorium, nie od `data_dir`: przedsionek
    # trzyma swoje dane **wewnątrz** `wydania/`, więc wyprowadzanie ścieżki z `data_dir`
    # dawało dla niego `wydania/wydania/wersje` i zawsze zero.
    wersje = KORZEN / "wydania" / "wersje"
    if wersje.is_dir():
        ile = len(list(wersje.iterdir()))
        assert f"wydań na dysku: {ile}" in wynik.detail or f"{ile} wydań" in wynik.detail
        if ile > WYDAN_PROG:
            assert "sprzataj.sh" in wynik.detail


def test_diagnostyka_pilnuje_swiezosci_kopii_zapasowej(tmp_path: Path) -> None:
    """Kopia robi się z timera i milczy — zepsuta wychodzi dopiero w dniu odtwarzania.

    Dlatego pyta o nią diagnostyka: czy katalog jest, czy cokolwiek w nim leży i czy
    najnowsza kopia nie jest sprzed dwóch dób.
    """
    import os
    import time

    from nexus.config import Settings
    from nexus.doctor import KOPIA_ALARM_H, check_kopia_zapasowa

    dane = tmp_path / "dane" / "app"
    dane.mkdir(parents=True)
    ustawienia = Settings(data_dir=dane)

    brak = check_kopia_zapasowa(ustawienia)
    assert brak.ok is False and "nie ma katalogu" in brak.detail

    kopie = tmp_path / "dane" / "kopie"
    kopie.mkdir()
    pusty = check_kopia_zapasowa(ustawienia)
    assert pusty.ok is False and "nigdy nie powstała" in pusty.detail

    swieza = kopie / "20260921T033558Z"
    swieza.mkdir()
    # Sam katalog to za mało: skrypt kopii kończy każdy krok `|| true`, więc brakujący
    # składnik nie zgłasza się sam. Najdotkliwszy byłby brak kodu — drzewo robocze bywa
    # jedynym miejscem, gdzie kod istnieje.
    bez_skladnikow = check_kopia_zapasowa(ustawienia)
    assert bez_skladnikow.ok is False and "zrodla.tar.zst" in bez_skladnikow.detail

    from nexus.doctor import KOPIA_MIN_BAJTOW, SKLADNIKI_KOPII

    for nazwa in SKLADNIKI_KOPII:
        (swieza / nazwa).write_bytes(b"x" * (KOPIA_MIN_BAJTOW + 1))
    dobra = check_kopia_zapasowa(ustawienia)
    assert dobra.ok is True and swieza.name in dobra.detail

    # Urwany plik (zabrakło miejsca w połowie zapisu) też ma być widoczny.
    (swieza / "zrodla.tar.zst").write_bytes(b"x")
    urwana = check_kopia_zapasowa(ustawienia)
    assert urwana.ok is False and "urwany" in urwana.detail
    (swieza / "zrodla.tar.zst").write_bytes(b"x" * (KOPIA_MIN_BAJTOW + 1))

    # Kopia sprzed trzech dób to nie „opóźnienie”, tylko zepsuty timer.
    stara = time.time() - (KOPIA_ALARM_H + 24) * 3600
    os.utime(swieza, (stara, stara))
    przeterminowana = check_kopia_zapasowa(ustawienia)
    assert przeterminowana.ok is False and "kopia.timer" in przeterminowana.detail


def test_ograniczony_ruch_zeruje_takze_opoznienia() -> None:
    """Wyciszenie ruchu obejmuje cały przebieg — opóźnienie też.

    Pomiar w przeglądarce na wydaniu z 21 września 2026 pokazał, że przy
    ``prefers-reduced-motion: reduce`` czas trwania spada do 0,00001 s, ale opóźnienie
    kaskady zostaje (0,08–0,32 s). Przy ``animation-fill-mode: both`` treść stoi wtedy
    na kryciu 0 i wyskakuje schodkami — czyli robi dokładnie to, przed czym ograniczenie
    ruchu ma chronić. Sprawdzenie stoi po stronie Pythona, bo jsdom nie liczy kaskady CSS,
    a projekt interfejsu nie ma typów ``node`` do czytania plików.
    """
    from pathlib import Path

    arkusz = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "styles.css").read_text(
        encoding="utf-8"
    )

    galezie = {
        "systemowa": "@media (prefers-reduced-motion: reduce) {",
        "z ustawień konta": ':root[data-ruch="ograniczony"] *,',
    }
    for nazwa, poczatek in galezie.items():
        assert poczatek in arkusz, f"brak gałęzi {nazwa}"
        blok = arkusz[arkusz.index(poczatek) :]
        blok = blok[: blok.index("scroll-behavior: auto !important;")]
        assert "animation-delay: 0ms !important;" in blok, nazwa
        assert "transition-delay: 0ms !important;" in blok, nazwa


def test_kaskada_milczy_w_czasie_przejscia_widoku() -> None:
    """Dwa ruchy na jednej zmianie czytają się jak usterka (motion, rozdz. 13).

    Treść modułu bywa na miejscu od razu — szybka odpowiedź serwera albo lista z pamięci —
    i wtedy kaskada wejścia startuje równocześnie z przejściem widoku. Zmierzone na
    zbudowanym interfejsie 21 września 2026: przez pierwsze 480 ms osiem pozycji animowało
    się przy ``data-przejscie="true"``. Reguła zdejmuje animację na czas przejścia; po
    zdjęciu znacznika wraca i rusza od początku, więc kaskada gra po przejściu, nie razem
    z nim.
    """
    from pathlib import Path

    arkusz = (
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "ruch" / "wejscia.css"
    ).read_text(encoding="utf-8")

    for selektor in (
        '.ruch-widok[data-przejscie="true"] > .ui-widok',
        '.ruch-widok[data-przejscie="true"] .ui-wejscie',
    ):
        assert selektor in arkusz, selektor
        blok = arkusz[arkusz.index(selektor) :]
        assert "animation: none;" in blok[: blok.index("}")], selektor
