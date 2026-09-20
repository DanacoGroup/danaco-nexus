"""Kredyty konta: naliczanie za pracę, przydział z planu, zatrzymanie pustego konta.

Kredyt jest w tej fazie zaworem na wspólny limit silnika: jeden tester nie może wyczerpać
zasobu całej grupy. Dlatego liczy się i to, że przebieg zawsze coś kosztuje, i to, że saldo
nie schodzi poniżej zera, i to, że puste konto nie przyjmuje kolejnego zlecenia.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from nexus.db import Base, Database
from nexus.platnosci import kredyty


@pytest.fixture
def baza(tmp_path: Path) -> Database:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'kredyty.db').as_posix()}")

    async def utworz() -> None:
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(utworz())
    return database


def test_koszt_przebiegu_zawsze_niezerowy() -> None:
    assert kredyty.koszt_przebiegu(None) == kredyty.DOMYSLNIE_MINIMUM
    assert kredyty.koszt_przebiegu({}) == kredyty.DOMYSLNIE_MINIMUM
    assert kredyty.koszt_przebiegu({"input_tokens": 1, "output_tokens": 0}) == kredyty.DOMYSLNIE_MINIMUM


def test_koszt_rosnie_z_zuzyciem_i_wyzej_wycenia_wyjscie() -> None:
    tanie = kredyty.koszt_przebiegu({"input_tokens": 10_000, "output_tokens": 0})
    drogie = kredyty.koszt_przebiegu({"input_tokens": 0, "output_tokens": 10_000})
    assert tanie == 10
    assert drogie == 50
    assert drogie > tanie
    # Żetony odczytane z pamięci podręcznej też są pracą — liczą się jak wejściowe.
    assert kredyty.koszt_przebiegu({"cache_read_input_tokens": 10_000}) == 10


def test_przydzial_zuzycie_i_ksiega(baza: Database) -> None:
    konto = uuid.uuid4()

    async def przebieg() -> None:
        assert (await kredyty.stan(baza, konto)).saldo == 0
        await kredyty.przydziel(baza, konto, 100, "zakup", "Pakiet testowy")
        assert (await kredyty.stan(baza, konto)).saldo == 100

        await kredyty.obciaz(baza, konto, 30, uuid.uuid4(), {"output_tokens": 6000})
        biezacy = await kredyty.stan(baza, konto)
        assert (biezacy.saldo, biezacy.przydzielone, biezacy.zuzyte) == (70, 100, 30)

        wpisy = await kredyty.historia(baza, konto)
        assert [wpis["powod"] for wpis in wpisy] == ["przebieg", "zakup"]
        assert wpisy[0]["zmiana"] == -30 and wpisy[0]["saldo_po"] == 70
        assert wpisy[1]["zmiana"] == 100

    asyncio.run(przebieg())


def test_saldo_nie_schodzi_ponizej_zera(baza: Database) -> None:
    """Przebieg droższy niż saldo zabiera resztę, ale nie tworzy długu na koncie."""
    konto = uuid.uuid4()

    async def przebieg() -> None:
        await kredyty.przydziel(baza, konto, 10, "zakup")
        await kredyty.obciaz(baza, konto, 500, uuid.uuid4(), {"output_tokens": 100_000})
        assert (await kredyty.stan(baza, konto)).saldo == 0
        assert (await kredyty.historia(baza, konto))[0]["zmiana"] == -10

    asyncio.run(przebieg())


def test_nowe_konto_dostaje_przydzial_startowy(baza: Database) -> None:
    """Świeże konto ma móc od razu pracować — inaczej po rejestracji nic się nie dzieje."""
    konto = uuid.uuid4()

    async def przebieg() -> None:
        from nexus.platnosci.plany import PLAN_DOMYSLNY, pozycja_katalogu

        await kredyty.sprawdz_przed_zleceniem(baza, konto)
        assert (await kredyty.stan(baza, konto)).saldo == pozycja_katalogu(PLAN_DOMYSLNY).kredyty_okresowo
        assert (await kredyty.historia(baza, konto))[0]["powod"] == "start"

    asyncio.run(przebieg())


def test_zuzyte_konto_nie_przyjmuje_zlecenia(baza: Database) -> None:
    """Przydział startowy jest jednorazowy: po wyczerpaniu konto dostaje odmowę."""
    konto = uuid.uuid4()

    async def przebieg() -> None:
        await kredyty.przydziel(baza, konto, 5, "zakup")
        await kredyty.obciaz(baza, konto, 5, uuid.uuid4())
        assert (await kredyty.stan(baza, konto)).saldo == 0

        with pytest.raises(kredyty.BrakKredytow) as blad:
            await kredyty.sprawdz_przed_zleceniem(baza, konto)
        assert blad.value.status == 402
        assert "kredyt" in str(blad.value).lower()

    asyncio.run(przebieg())


def test_przydzial_z_planu_uzywa_katalogu(baza: Database) -> None:
    konto = uuid.uuid4()

    async def przebieg() -> None:
        from nexus.platnosci.plany import pozycja_katalogu

        saldo = await kredyty.przydziel_z_planu(baza, konto, "pro", "odnowienie")
        assert saldo == pozycja_katalogu("pro").kredyty_okresowo
        # Nieznany plan nie może zostawić konta bez kredytów — wpada plan domyślny.
        await kredyty.przydziel_z_planu(baza, konto, "nie-ma-takiego")
        assert (await kredyty.stan(baza, konto)).saldo > saldo

    asyncio.run(przebieg())


def test_konta_nie_dzielą_salda(baza: Database) -> None:
    pierwsze, drugie = uuid.uuid4(), uuid.uuid4()

    async def przebieg() -> None:
        await kredyty.przydziel(baza, pierwsze, 100, "zakup")
        assert (await kredyty.stan(baza, drugie)).saldo == 0
        await kredyty.obciaz(baza, pierwsze, 40, uuid.uuid4())
        assert (await kredyty.stan(baza, drugie)).saldo == 0
        assert (await kredyty.stan(baza, pierwsze)).saldo == 60

    asyncio.run(przebieg())


def test_komunikaty_bledow_nie_zdradzaja_kont_silnika() -> None:
    """Użytkownik nie może się z aplikacji dowiedzieć nic o kontach, na których działa silnik."""
    from nexus.agent.runner import friendly_error

    zakazane = ("claude", "oauth", "setup-token", "limit 5", "konta claude", "cli")
    for surowy in (
        "Error: session limit reached for this account",
        'stream error: {"api_error_status":429}',
        "Invalid API key · Please run /login",
        "weekly limit exceeded, resets at 18:00",
        "nieznany błąd procesu",
    ):
        komunikat = friendly_error(surowy).lower()
        for slowo in zakazane:
            assert slowo not in komunikat, f"komunikat zdradza silnik: {komunikat}"
        assert komunikat, "użytkownik musi dostać jakąkolwiek informację"


def test_modul_agentow_nie_wystawia_limitow_kont_silnika() -> None:
    """Punkt końcowy zadań nie może zwracać stanu limitów kont operatora."""
    from pathlib import Path

    # Ścieżka liczona od pliku modułu, nie od katalogu uruchomienia: pytest bywa
    # odpalany i z korzenia repozytorium, i z katalogu `backend`.
    import nexus.api.modules.agenci as modul

    zrodlo = Path(modul.__file__).read_text(encoding="utf-8")
    assert '"limits"' not in zrodlo


def test_ciezkie_narzedzia_maja_wlasna_stawke() -> None:
    """Powiększanie zdjęcia zajmuje minuty procesora, a w rozmowie zostawia dwa zdania."""
    bez = kredyty.koszt_przebiegu({"output_tokens": 200})
    z_powiekszeniem = kredyty.koszt_przebiegu({"output_tokens": 200}, ["upscale_image"])
    assert z_powiekszeniem == bez + kredyty.KOSZT_NARZEDZI["upscale_image"]
    # Narzędzie spoza tabeli nic nie dopłaca — liczą się wtedy same żetony.
    assert kredyty.koszt_przebiegu({"output_tokens": 200}, ["mail_list"]) == bez
    # Każde użycie liczy się osobno.
    assert kredyty.koszt_narzedzi(["web_search", "web_search"]) == 2 * kredyty.KOSZT_NARZEDZI["web_search"]


def test_cennik_kredytow_da_sie_zmienic_srodowiskiem(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stawki są cennikiem, nie stałą w kodzie — zmiana nie wymaga nowej wersji."""
    assert kredyty.koszt_przebiegu({"output_tokens": 1000}) == kredyty.DOMYSLNIE_1K_WYJSCIE
    monkeypatch.setenv("NEXUS_KREDYT_1K_WYJSCIE", "9")
    assert kredyty.koszt_przebiegu({"output_tokens": 1000}) == 9
    # Błędna wartość nie może wyłączyć naliczania — wraca stawka domyślna.
    monkeypatch.setenv("NEXUS_KREDYT_1K_WYJSCIE", "bez sensu")
    assert kredyty.koszt_przebiegu({"output_tokens": 1000}) == kredyty.DOMYSLNIE_1K_WYJSCIE


# --- zakres planów ---------------------------------------------------------------------


def test_okres_probny_jest_wezszym_zakresem_planu_nie_osobnym_planem() -> None:
    """7 dni próbnych to ten sam plan z mniejszą przestrzenią i bez funkcji zaufanych."""
    from nexus.platnosci.plany import pozycja_katalogu
    from nexus.platnosci.uprawnienia import limity_planu

    probne = limity_planu("osobisty", "probna")
    oplacone = limity_planu("osobisty", "aktywna")
    pozycja = pozycja_katalogu("osobisty")
    assert pozycja is not None and pozycja.okres_probny_dni == 7

    # Ten sam plan, nie inny.
    assert probne.plan == oplacone.plan == "osobisty"
    assert probne.probny is True and oplacone.probny is False
    # Węższy zakres: mniej miejsca, bez poczty, bez automatyzacji.
    assert probne.przestrzen_mb < oplacone.przestrzen_mb
    assert probne.skrzynki == 0 and oplacone.skrzynki >= 1
    assert probne.automatyzacje == 0
    # Synchronizacja i wersje plików zaczynają się dopiero w planie Pro — to one są
    # powodem przejścia wyżej, więc Osobisty ich nie ma ani w okresie próbnym, ani po
    # opłaceniu.
    assert probne.synchronizacja is False and oplacone.synchronizacja is False
    assert limity_planu("pro", "aktywna").synchronizacja is True


def test_przestrzen_rosnie_wraz_z_planem() -> None:
    """Przestrzeń jest wspólna dla plików i poczty i rośnie z każdym poziomem."""
    from nexus.platnosci.uprawnienia import limity_planu, opis_przestrzeni

    osobisty = limity_planu("osobisty", "aktywna")
    pro = limity_planu("pro", "aktywna")
    zespol = limity_planu("zespol", "aktywna")
    assert osobisty.przestrzen_mb < pro.przestrzen_mb < zespol.przestrzen_mb
    assert (osobisty.skrzynki, pro.skrzynki) == (1, 10)
    assert osobisty.wersjonowanie is False and pro.wersjonowanie is True
    assert opis_przestrzeni(100) == "100 MB"
    assert opis_przestrzeni(1024) == "1 GB"
    assert opis_przestrzeni(10240) == "10 GB"


def test_poczta_dopiero_od_planu_platnego() -> None:
    """Skrzynka wymaga opłaconego planu — darmowa skrzynka samoobsługowa ściąga spamerów."""
    from nexus.platnosci.uprawnienia import limity_planu

    assert limity_planu("osobisty", "probna").skrzynki == 0
    assert limity_planu("osobisty", "brak").skrzynki == 0
    for kod in ("osobisty", "pro", "zespol"):
        assert limity_planu(kod, "aktywna").skrzynki >= 1
