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
from fastapi.testclient import TestClient
from test_api import HEADERS, PASSWORD, client, set_password, settings  # noqa: F401

from nexus.config import Settings
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
    """Świeże konto ma móc od razu pracować — inaczej po rejestracji nic się nie dzieje.

    Start to zakres okresu próbnego, a nie pełny przydział planu: pełny przychodzi dopiero
    z opłaconą fakturą, a cennik obiecuje na początek właśnie zakres próbny.
    """
    konto = uuid.uuid4()

    async def przebieg() -> None:
        from nexus.platnosci.plany import PLAN_DOMYSLNY, pozycja_katalogu

        await kredyty.sprawdz_przed_zleceniem(baza, konto)
        pozycja = pozycja_katalogu(PLAN_DOMYSLNY)
        assert pozycja is not None and 0 < pozycja.probny_kredyty < pozycja.kredyty_okresowo
        assert (await kredyty.stan(baza, konto)).saldo == pozycja.probny_kredyty
        assert (await kredyty.historia(baza, konto))[0]["powod"] == "start"
        # Przydział startowy jest jednorazowy.
        await kredyty.pierwszy_przydzial(baza, konto)
        assert (await kredyty.stan(baza, konto)).saldo == pozycja.probny_kredyty

    asyncio.run(przebieg())


def test_zakres_probny_tylko_dla_planu_z_okresem_probnym(baza: Database) -> None:
    """Plan bez okresu próbnego nie ma węższego zakresu — dostaje pełny przydział."""
    osobiste, pro = uuid.uuid4(), uuid.uuid4()

    async def przebieg() -> None:
        from nexus.platnosci.plany import pozycja_katalogu

        assert await kredyty.przydziel_z_planu(baza, osobiste, "osobisty", "okres-probny", probny=True) == (
            pozycja_katalogu("osobisty").probny_kredyty
        )
        assert await kredyty.przydziel_z_planu(baza, pro, "pro", "okres-probny", probny=True) == (
            pozycja_katalogu("pro").kredyty_okresowo
        )

    asyncio.run(przebieg())


def test_zakup_ani_wpis_zerowy_nie_odbieraja_zakresu_probnego(baza: Database) -> None:
    """Zakres próbny blokuje wyłącznie wcześniejszy przydział, a nie zakup czy wpis zerowy.

    Konto, które najpierw dokupiło dostęp kwotą, a potem zaczęło okres próbny, nie dostało
    nigdy przydziału startowego — faktura otwierająca okres próbny ma mu go dać.
    """
    po_zakupie, po_pustym_przebiegu = uuid.uuid4(), uuid.uuid4()

    async def przebieg() -> None:
        from nexus.platnosci.plany import pozycja_katalogu

        probny = pozycja_katalogu("osobisty").probny_kredyty
        await kredyty.przydziel(baza, po_zakupie, 630, "zakup", "Przedłużenie dostępu")
        saldo = await kredyty.pierwszy_przydzial(baza, po_zakupie, "osobisty", "okres-probny")
        assert saldo == 630 + probny
        powody = [wpis["powod"] for wpis in await kredyty.historia(baza, po_zakupie)]
        assert powody == ["okres-probny", "zakup"]

        # Obciążenie przy saldzie zero zapisuje wpis ze zmianą 0 — to nie był przydział.
        await kredyty.obciaz(baza, po_pustym_przebiegu, 5, uuid.uuid4())
        saldo = await kredyty.pierwszy_przydzial(baza, po_pustym_przebiegu, "osobisty", "okres-probny")
        assert saldo == probny

    asyncio.run(przebieg())


def test_wlasciciel_instalacji_dostaje_na_start_pelny_plan(baza: Database) -> None:
    """Właściciel instalacji nie ma okresu próbnego ani faktury, która dałaby mu pełny przydział.

    Z zakresem próbnym świeża instalacja stawała po kilkudziesięciu zleceniach, a konta
    administratora nie da się doładować poleceniem CLI.
    """
    from nexus.db import ADMIN_OWNER
    from nexus.platnosci.plany import PLAN_DOMYSLNY, pozycja_katalogu

    async def przebieg() -> None:
        await kredyty.sprawdz_przed_zleceniem(baza, ADMIN_OWNER)
        pelny = pozycja_katalogu(PLAN_DOMYSLNY).kredyty_okresowo
        assert (await kredyty.stan(baza, ADMIN_OWNER)).saldo == pelny
        assert [wpis["powod"] for wpis in await kredyty.historia(baza, ADMIN_OWNER)] == ["start"]

    asyncio.run(przebieg())


def test_zuzyte_konto_nie_przyjmuje_zlecenia(baza: Database) -> None:
    """Przydział startowy jest jednorazowy: po wyczerpaniu konto dostaje odmowę."""
    konto = uuid.uuid4()

    async def przebieg() -> None:
        await kredyty.przydziel(baza, konto, 5, "start")
        await kredyty.obciaz(baza, konto, 5, uuid.uuid4())
        assert (await kredyty.stan(baza, konto)).saldo == 0

        with pytest.raises(kredyty.BrakKredytow) as blad:
            await kredyty.sprawdz_przed_zleceniem(baza, konto)
        assert blad.value.status == 402
        # Komunikat mówi o dostępie, nie o kredytach: jednostka rozliczeniowa jest nasza,
        # a użytkownik nigdy nie widzi jej liczby, więc nie ma jej po czym rozpoznać.
        tresc = str(blad.value).lower()
        assert "kredyt" not in tresc
        assert "dostęp" in tresc and "przedłuż" in tresc

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


# --- Dostęp bez liczb i doładowanie kwotą ------------------------------------------


def test_przelicznik_nagradza_wieksza_wplate() -> None:
    """Im większa wpłata, tym korzystniejszy przelicznik — inaczej nikt by nie dopłacał."""
    from nexus.platnosci import kredyty as ksiega

    za_dyche = ksiega.kredyty_za_kwote(1_000)
    za_dwie_stowy = ksiega.kredyty_za_kwote(20_000)
    za_piec_stowek = ksiega.kredyty_za_kwote(50_000)
    assert za_dyche > 0
    # Stawka za złotówkę rośnie wraz z progiem.
    assert za_dwie_stowy / 200 > za_dyche / 10
    assert za_piec_stowek / 500 > za_dwie_stowy / 200


def test_ponizej_minimum_nie_daje_dostepu() -> None:
    from nexus.platnosci import kredyty as ksiega

    assert ksiega.kredyty_za_kwote(ksiega.MINIMUM_DOLADOWANIA_GR - 1) == 0
    assert ksiega.kredyty_za_kwote(0) == 0


def test_udzial_zuzycia_bez_przydzialu_to_zero() -> None:
    """Konto bez przydziału nie może pokazywać pełnego zużycia — nie ma czego dzielić."""
    from nexus.platnosci.kredyty import StanKredytow, udzial_zuzycia

    assert udzial_zuzycia(StanKredytow(saldo=0, przydzielone=0, zuzyte=0)) == 0.0
    assert udzial_zuzycia(StanKredytow(saldo=500, przydzielone=2_000, zuzyte=1_500)) == 0.75
    # Zużycie ponad przydział (korekty, doliczenia) nie wychodzi poza pełny pasek.
    assert udzial_zuzycia(StanKredytow(saldo=0, przydzielone=100, zuzyte=250)) == 1.0


def test_api_kredytow_nie_wystawia_zadnych_liczb(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Saldo, przydział i koszt pojedynczej pracy zostają po stronie serwera."""
    set_password(settings)
    assert client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
    ).status_code == 200

    dane = client.get("/api/platnosci/kredyty").json()
    # Pola zgodności (`saldo`, `przydzielone`, `zuzyte`) zostają dla okien sprzed
    # aktualizacji; interfejs ich nie czyta i nie pokazuje.
    assert {"zuzycie", "stan", "wyczerpane", "historia", "doladowanie"} <= set(dane)
    assert 0.0 <= dane["zuzycie"] <= 1.0
    assert dane["stan"] in {"w_porzadku", "konczy_sie", "wyczerpany"}
    assert dane["doladowanie"]["minimum_gr"] == 1_000
    for wpis in dane["historia"]:
        assert set(wpis) == {"powod", "opis", "kiedy"}, "historia nie może nieść wartości"
