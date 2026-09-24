"""Grupa: wspólna pula dostępu, miejsca, zaproszenia i przekazanie roli założyciela.

Plan „Grupa” dawało się kupić, ale nie dawało się nikogo do grupy dodać — cennik obiecywał
mechanikę, której nie było. Te testy pilnują tego, co w grupie kosztuje pieniądze i czyjeś
dane: kto płaci, kto może kogo dodać i usunąć, i co się dzieje, gdy rola założyciela
przechodzi na kogoś innego.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio

from nexus.db import Database
from nexus.models.portal import PortalUser
from nexus.platnosci import grupy
from nexus.portal.konta import utworz_konto

HASLO = "Haslo-Testera-2026!"


@pytest_asyncio.fixture
async def baza(tmp_path: Path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'grupy.db'}")
    await database.create_schema()
    yield database
    await database.close()


async def konto(database: Database, email: str, plan: str = "zespol") -> uuid.UUID:
    async with database.session() as session:
        user = await utworz_konto(session, email=email, haslo=HASLO, name=email.split("@")[0])
        await session.flush()
        identyfikator = user.id
    async with database.session() as session:
        rekord = await session.get(PortalUser, identyfikator)
        rekord.plan = plan
    return identyfikator


@pytest.mark.asyncio
async def test_grupe_zaklada_tylko_konto_na_planie_grupowym(baza: Database) -> None:
    osobiste = await konto(baza, "sam@example.com", plan="osobisty")
    with pytest.raises(grupy.BladGrupy, match="planie Grupa"):
        await grupy.zaloz(baza, osobiste)


@pytest.mark.asyncio
async def test_zalozyciel_rozlicza_sie_sam_ze_soba(baza: Database) -> None:
    szef = await konto(baza, "szef@example.com")
    await grupy.zaloz(baza, szef, "Kancelaria")
    assert await grupy.konto_rozliczeniowe(baza, szef) == szef


@pytest.mark.asyncio
async def test_praca_czlonka_schodzi_z_puli_zalozyciela(baza: Database) -> None:
    """To jest sedno planu: płaci jeden, pracuje kilku."""
    szef = await konto(baza, "szef@example.com")
    pracownik = await konto(baza, "pracownik@example.com", plan="osobisty")
    grupa = await grupy.zaloz(baza, szef, "Kancelaria")

    # Poza grupą każdy rozlicza się sam.
    assert await grupy.konto_rozliczeniowe(baza, pracownik) == pracownik

    token = await grupy.zapros(baza, grupa, szef, "pracownik@example.com")
    await grupy.przyjmij(baza, token, pracownik)

    assert await grupy.konto_rozliczeniowe(baza, pracownik) == szef


@pytest.mark.asyncio
async def test_zaproszenie_dziala_raz(baza: Database) -> None:
    szef = await konto(baza, "szef@example.com")
    pracownik = await konto(baza, "pracownik@example.com", plan="osobisty")
    inny = await konto(baza, "inny@example.com", plan="osobisty")
    grupa = await grupy.zaloz(baza, szef)
    token = await grupy.zapros(baza, grupa, szef, "pracownik@example.com")
    await grupy.przyjmij(baza, token, pracownik)
    with pytest.raises(grupy.BladGrupy, match="wykorzystane"):
        await grupy.przyjmij(baza, token, inny)


@pytest.mark.asyncio
async def test_zaproszenia_nie_da_sie_przejac_z_innego_konta(baza: Database) -> None:
    """Odsyłacz z cudzej skrzynki nie wpuszcza na cudzy rachunek."""
    szef = await konto(baza, "szef@example.com")
    obcy = await konto(baza, "obcy@example.com", plan="osobisty")
    await konto(baza, "pracownik@example.com", plan="osobisty")
    grupa = await grupy.zaloz(baza, szef)
    token = await grupy.zapros(baza, grupa, szef, "pracownik@example.com")
    with pytest.raises(grupy.BladGrupy, match="inny adres"):
        await grupy.przyjmij(baza, token, obcy)


@pytest.mark.asyncio
async def test_zaprasza_wylacznie_zalozyciel(baza: Database) -> None:
    szef = await konto(baza, "szef@example.com")
    pracownik = await konto(baza, "pracownik@example.com", plan="osobisty")
    grupa = await grupy.zaloz(baza, szef)
    token = await grupy.zapros(baza, grupa, szef, "pracownik@example.com")
    await grupy.przyjmij(baza, token, pracownik)
    with pytest.raises(grupy.BladGrupy, match="założyciel"):
        await grupy.zapros(baza, grupa, pracownik, "ktos@example.com")


@pytest.mark.asyncio
async def test_grupa_nie_przyjmuje_wiecej_niz_ma_miejsc(baza: Database) -> None:
    szef = await konto(baza, "szef@example.com")
    grupa = await grupy.zaloz(baza, szef)
    miejsca = grupy.miejsca_planu("zespol")
    for numer in range(miejsca - 1):
        await grupy.zapros(baza, grupa, szef, f"k{numer}@example.com")
    with pytest.raises(grupy.BladGrupy, match="miejsc"):
        await grupy.zapros(baza, grupa, szef, "ostatni@example.com")


@pytest.mark.asyncio
async def test_zalozyciel_nie_wychodzi_bez_przekazania_roli(baza: Database) -> None:
    """Inaczej zostałaby grupa bez nikogo, kto za nią płaci."""
    szef = await konto(baza, "szef@example.com")
    grupa = await grupy.zaloz(baza, szef)
    with pytest.raises(grupy.BladGrupy, match="przekaże roli"):
        await grupy.usun_czlonka(baza, grupa, szef, szef)


@pytest.mark.asyncio
async def test_przekazanie_roli_przenosi_rachunek(baza: Database) -> None:
    szef = await konto(baza, "szef@example.com")
    nastepca = await konto(baza, "nastepca@example.com", plan="osobisty")
    grupa = await grupy.zaloz(baza, szef)
    token = await grupy.zapros(baza, grupa, szef, "nastepca@example.com")
    await grupy.przyjmij(baza, token, nastepca)
    await subskrypcja(baza, nastepca, grupy.PLAN_GRUPY, "aktywna")

    await grupy.przekaz_zalozyciela(baza, grupa, szef, nastepca)

    # Od tej chwili płaci następca — także za poprzedniego założyciela.
    assert await grupy.konto_rozliczeniowe(baza, nastepca) == nastepca
    assert await grupy.konto_rozliczeniowe(baza, szef) == nastepca
    role = {pozycja.email: pozycja.rola for pozycja in await grupy.czlonkowie(baza, grupa.id)}
    assert role["nastepca@example.com"] == grupy.ROLA_ZALOZYCIEL
    assert role["szef@example.com"] == grupy.ROLA_CZLONEK


@pytest.mark.asyncio
@pytest.mark.parametrize("stan", [None, "anulowana"], ids=["bez-subskrypcji", "subskrypcja-anulowana"])
async def test_rola_zalozyciela_tylko_dla_konta_z_oplaconym_planem_grupa(
    baza: Database, stan: str | None
) -> None:
    """Subskrypcja, która płaci za grupę, zostaje na koncie płacącego.

    Przekazanie roli komuś bez własnego planu Grupa odebrałoby wszystkim członkom limity
    planu i pulę pracy, a Stripe dalej obciążałby poprzedniego założyciela.
    """
    szef = await konto(baza, "szef@example.com")
    nastepca = await konto(baza, "nastepca@example.com", plan="osobisty")
    grupa = await grupy.zaloz(baza, szef)
    await grupy.przyjmij(baza, await grupy.zapros(baza, grupa, szef, "nastepca@example.com"), nastepca)
    if stan is not None:
        await subskrypcja(baza, nastepca, grupy.PLAN_GRUPY, stan)

    with pytest.raises(grupy.BladGrupy, match="plan Grupa"):
        await grupy.przekaz_zalozyciela(baza, grupa, szef, nastepca)

    assert await grupy.konto_rozliczeniowe(baza, nastepca) == szef
    role = {pozycja.email: pozycja.rola for pozycja in await grupy.czlonkowie(baza, grupa.id)}
    assert role["szef@example.com"] == grupy.ROLA_ZALOZYCIEL


@pytest.mark.asyncio
async def test_czlonek_moze_wyjsc_sam(baza: Database) -> None:
    szef = await konto(baza, "szef@example.com")
    pracownik = await konto(baza, "pracownik@example.com", plan="osobisty")
    grupa = await grupy.zaloz(baza, szef)
    token = await grupy.zapros(baza, grupa, szef, "pracownik@example.com")
    await grupy.przyjmij(baza, token, pracownik)

    await grupy.usun_czlonka(baza, grupa, pracownik, pracownik)
    assert await grupy.konto_rozliczeniowe(baza, pracownik) == pracownik


@pytest.mark.asyncio
async def test_czlonek_nie_usuwa_innego_czlonka(baza: Database) -> None:
    szef = await konto(baza, "szef@example.com")
    jeden = await konto(baza, "jeden@example.com", plan="osobisty")
    dwa = await konto(baza, "dwa@example.com", plan="osobisty")
    grupa = await grupy.zaloz(baza, szef)
    for adres, identyfikator in (("jeden@example.com", jeden), ("dwa@example.com", dwa)):
        await grupy.przyjmij(baza, await grupy.zapros(baza, grupa, szef, adres), identyfikator)
    with pytest.raises(grupy.BladGrupy, match="założyciel"):
        await grupy.usun_czlonka(baza, grupa, jeden, dwa)


@pytest.mark.asyncio
async def test_rozwiazanie_grupy_przywraca_wlasne_rachunki(baza: Database) -> None:
    szef = await konto(baza, "szef@example.com")
    pracownik = await konto(baza, "pracownik@example.com", plan="osobisty")
    grupa = await grupy.zaloz(baza, szef)
    token = await grupy.zapros(baza, grupa, szef, "pracownik@example.com")
    await grupy.przyjmij(baza, token, pracownik)

    await grupy.rozwiaz(baza, grupa, szef)

    assert await grupy.grupa_uzytkownika(baza, szef) is None
    assert await grupy.konto_rozliczeniowe(baza, pracownik) == pracownik


@pytest.mark.asyncio
async def test_konto_nalezy_najwyzej_do_jednej_grupy(baza: Database) -> None:
    pierwszy = await konto(baza, "pierwszy@example.com")
    drugi = await konto(baza, "drugi@example.com")
    pracownik = await konto(baza, "pracownik@example.com", plan="osobisty")
    grupa_a = await grupy.zaloz(baza, pierwszy)
    grupa_b = await grupy.zaloz(baza, drugi)
    token_a = await grupy.zapros(baza, grupa_a, pierwszy, "pracownik@example.com")
    await grupy.przyjmij(baza, token_a, pracownik)
    token_b = await grupy.zapros(baza, grupa_b, drugi, "pracownik@example.com")
    with pytest.raises(grupy.BladGrupy, match="już należy"):
        await grupy.przyjmij(baza, token_b, pracownik)


# --- punkty API -------------------------------------------------------------------------------
#
# Reguły grupy pilnuje warstwa usług (testy wyżej). Tu sprawdzamy, że API ich nie omija
# i że odmowa dochodzi do użytkownika jako czytelny powód, a nie jako pięćsetka.

from fastapi.testclient import TestClient  # noqa: E402
from test_api import HEADERS, PASSWORD, client, set_password, settings  # noqa: E402, F401

from nexus.config import Settings  # noqa: E402


def zaloguj(klient: TestClient, ustawienia: Settings) -> None:  # noqa: F811
    set_password(ustawienia)
    assert (
        klient.post(
            "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
        ).status_code
        == 200
    )


def test_bez_grupy_api_mowi_ile_jest_miejsc(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    zaloguj(client, settings)
    odpowiedz = client.get("/api/grupa", headers=HEADERS)
    assert odpowiedz.status_code == 200, odpowiedz.text
    dane = odpowiedz.json()
    assert dane["grupa"] is None
    assert dane["miejsca"] >= 2


def test_zalozenie_bez_planu_grupowego_konczy_sie_czytelna_odmowa(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Konto administratora instalacji nie jest kontem klienta — ma to usłyszeć wprost.

    Komunikat „Nie znaleziono konta” wyglądałby na awarię bazy, a to jest zwykła odmowa
    z powodu, który da się naprawić: grupę zakłada się z konta z portalu.
    """
    zaloguj(client, settings)
    odpowiedz = client.post("/api/grupa", json={"nazwa": "Zespół"}, headers=HEADERS)
    assert odpowiedz.status_code == 400, odpowiedz.text
    detal = odpowiedz.json()["detail"]
    assert "kontem klienta" in detal
    assert "Nie znaleziono" not in detal


def test_dzialania_w_nieistniejacej_grupie_daja_404(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    zaloguj(client, settings)
    for metoda, adres, tresc in (
        ("post", "/api/grupa/zaproszenia", {"email": "ktos@example.com"}),
        ("delete", "/api/grupa", None),
    ):
        odpowiedz = getattr(client, metoda)(
            adres, headers=HEADERS, **({"json": tresc} if tresc else {})
        )
        assert odpowiedz.status_code == 404, f"{adres}: {odpowiedz.text}"


def test_punkty_grupy_wymagaja_sesji(client: TestClient) -> None:  # noqa: F811
    assert client.get("/api/grupa", headers=HEADERS).status_code == 401
    assert client.post("/api/grupa", json={"nazwa": "x"}, headers=HEADERS).status_code == 401


@pytest.mark.asyncio
async def test_miejsca_bierze_sie_z_oplaconej_subskrypcji(baza: Database) -> None:
    """Plan „Grupa” kosztuje za użytkownika — miejsc jest tyle, ile opłacono, nie tyle, ile w limicie."""
    from nexus.platnosci.model import Subskrypcja

    szef = await konto(baza, "szef@example.com")
    async with baza.session() as session:
        session.add(
            Subskrypcja(uzytkownik=str(szef), plan_kod=grupy.PLAN_GRUPY, okres="miesiac", miejsca=9)
        )
    assert await grupy.miejsca_grupy(baza, szef) == 9


@pytest.mark.asyncio
async def test_bez_subskrypcji_miejsca_biora_sie_z_limitu_planu(baza: Database) -> None:
    """Konto testowe albo chwila przed pierwszą płatnością — limit planu jako wartość zastępcza."""
    szef = await konto(baza, "szef@example.com")
    assert await grupy.miejsca_grupy(baza, szef) == grupy.miejsca_planu(grupy.PLAN_GRUPY)


# --- limity planu u członka grupy ------------------------------------------------------------
#
# Członek grupy dostawał z grupy wyłącznie pulę dostępu założyciela, a przestrzeń, zadania
# naraz i synchronizację brał z własnej subskrypcji — bez niej z zakresu próbnego (100 MB,
# jedno zadanie, bez synchronizacji). Cennik obiecuje w Grupie co innego.


async def subskrypcja(database: Database, konto_id: uuid.UUID, plan: str, status: str) -> None:
    from nexus.platnosci.model import Subskrypcja

    async with database.session() as session:
        session.add(Subskrypcja(uzytkownik=str(konto_id), plan_kod=plan, status=status, okres="miesiac"))


async def zmien_status(database: Database, konto_id: uuid.UUID, status: str) -> None:
    from sqlalchemy import update

    from nexus.platnosci.model import Subskrypcja

    async with database.session() as session:
        await session.execute(
            update(Subskrypcja).where(Subskrypcja.uzytkownik == str(konto_id)).values(status=status)
        )


async def grupa_z_czlonkiem(database: Database) -> tuple[grupy.Grupa, uuid.UUID, uuid.UUID]:
    szef = await konto(database, "szef@example.com")
    pracownik = await konto(database, "pracownik@example.com", plan="osobisty")
    await subskrypcja(database, szef, grupy.PLAN_GRUPY, "aktywna")
    grupa = await grupy.zaloz(database, szef, "Kancelaria")
    token = await grupy.zapros(database, grupa, szef, "pracownik@example.com")
    await grupy.przyjmij(database, token, pracownik)
    return grupa, szef, pracownik


def zakres(limity) -> tuple[int, int, bool]:
    return limity.zadania_rownolegle, limity.przestrzen_mb, limity.synchronizacja


@pytest.mark.asyncio
async def test_czlonek_oplaconej_grupy_ma_limity_planu_grupa(baza: Database) -> None:
    """Członek pracuje na tym samym planie co założyciel: 8 zadań naraz, 10 GB, synchronizacja."""
    from nexus.platnosci.uprawnienia import limity_uzytkownika

    _, szef, pracownik = await grupa_z_czlonkiem(baza)

    zalozyciel = await limity_uzytkownika(baza, str(szef))
    czlonek = await limity_uzytkownika(baza, str(pracownik))
    assert zakres(zalozyciel) == (8, 10_240, True)
    assert zakres(czlonek) == zakres(zalozyciel)
    assert czlonek.nazwa_planu == "Grupa"
    assert czlonek.probny is False


@pytest.mark.asyncio
async def test_po_wyjsciu_z_grupy_czlonek_wraca_do_wlasnych_limitow(baza: Database) -> None:
    from nexus.platnosci.uprawnienia import limity_uzytkownika

    grupa, _, pracownik = await grupa_z_czlonkiem(baza)
    await grupy.usun_czlonka(baza, grupa, pracownik, pracownik)

    assert zakres(await limity_uzytkownika(baza, str(pracownik))) == (1, 100, False)


@pytest.mark.asyncio
async def test_po_wygasnieciu_subskrypcji_grupy_czlonek_wraca_do_wlasnego_planu(baza: Database) -> None:
    """Grupa bez opłaty nie daje nic ponad własny plan członka — także gdy ten ma własny Pro."""
    from nexus.platnosci.uprawnienia import limity_uzytkownika

    _, szef, pracownik = await grupa_z_czlonkiem(baza)
    await subskrypcja(baza, pracownik, "pro", "aktywna")
    assert zakres(await limity_uzytkownika(baza, str(pracownik))) == (8, 10_240, True)

    await zmien_status(baza, szef, "anulowana")

    assert zakres(await limity_uzytkownika(baza, str(pracownik))) == (4, 2_048, True)
    # Pula dostępu dalej należy do założyciela — to osobna zasada, limity jej nie zmieniają.
    assert await grupy.konto_rozliczeniowe(baza, pracownik) == szef


@pytest.mark.asyncio
async def test_grupa_bez_oplaconego_planu_nie_rozszerza_limitow_czlonka(baza: Database) -> None:
    from nexus.platnosci.uprawnienia import limity_uzytkownika

    szef = await konto(baza, "szef@example.com")
    pracownik = await konto(baza, "pracownik@example.com", plan="osobisty")
    grupa = await grupy.zaloz(baza, szef)
    await grupy.przyjmij(baza, await grupy.zapros(baza, grupa, szef, "pracownik@example.com"), pracownik)

    assert zakres(await limity_uzytkownika(baza, str(pracownik))) == (1, 100, False)


@pytest.mark.asyncio
async def test_zmiana_subskrypcji_zalozyciela_uzgadnia_chmure_czlonkow(
    baza: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Członek z własnym Nextcloudem dostaje limit grupy od razu, a nie przy wejściu do Nexusa."""
    import nexus.chmura_konta as chmura

    _, szef, pracownik = await grupa_z_czlonkiem(baza)
    uzgodnione: list[uuid.UUID] = []

    async def zapisz(_ustawienia: object, _baza: object, owner: uuid.UUID, *_: object, **__: object) -> None:
        uzgodnione.append(owner)

    monkeypatch.setattr(chmura, "konto_chmury", lambda _ustawienia, _owner: object())
    monkeypatch.setattr(chmura, "konto_wedlug_planu", zapisz)

    await chmura.uzgodnij_limit_po_zmianie_planu(None, baza, szef)  # type: ignore[arg-type]
    assert uzgodnione == [szef, pracownik]

    uzgodnione.clear()
    await chmura.uzgodnij_limit_po_zmianie_planu(None, baza, pracownik)  # type: ignore[arg-type]
    assert uzgodnione == [pracownik], "członek nie pociąga za sobą reszty grupy"


@pytest.mark.asyncio
async def test_blad_chmury_jednego_konta_nie_zatrzymuje_uzgadniania_reszty(
    baza: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wyjątek przy założycielu (np. błąd bazy przy limitach) nie może zostawić członków ze starym limitem."""
    import nexus.chmura_konta as chmura

    _, szef, pracownik = await grupa_z_czlonkiem(baza)
    uzgodnione: list[uuid.UUID] = []

    async def zapisz(_ustawienia: object, _baza: object, owner: uuid.UUID, *_: object, **__: object) -> None:
        if owner == szef:
            raise RuntimeError("baza chwilowo niedostępna")
        uzgodnione.append(owner)

    monkeypatch.setattr(chmura, "konto_chmury", lambda _ustawienia, _owner: object())
    monkeypatch.setattr(chmura, "konto_wedlug_planu", zapisz)

    await chmura.uzgodnij_limit_po_zmianie_planu(None, baza, szef)  # type: ignore[arg-type]
    assert uzgodnione == [pracownik]


def test_kasa_planu_grupowego_pozwala_wybrac_liczbe_miejsc() -> None:
    """Bez tego 49 zł byłoby ceną całej grupy, a nie ceną za osobę — czyli czymś innym niż cennik."""
    from nexus.platnosci.plany import pozycja_katalogu
    from nexus.platnosci.uslugi import MIEJSC_MAX, MIEJSC_MIN, _pozycja_zakupu

    grupowy = pozycja_katalogu("zespol")
    assert grupowy is not None
    pozycja = _pozycja_zakupu(grupowy, "price_x")
    assert pozycja["quantity"] == MIEJSC_MIN
    assert pozycja["adjustable_quantity"] == {
        "enabled": True,
        "minimum": MIEJSC_MIN,
        "maximum": MIEJSC_MAX,
    }

    osobisty = pozycja_katalogu("osobisty")
    assert osobisty is not None
    jednoosobowa = _pozycja_zakupu(osobisty, "price_y")
    assert jednoosobowa == {"price": "price_y", "quantity": 1}


@pytest.mark.asyncio
async def test_ekran_platnosci_czlonka_pokazuje_limity_grupy(baza: Database) -> None:
    """Moduł Twój plan ma pokazywać limity, które serwer stosuje, a nie zakres próbny członka."""
    from nexus.api.modules.platnosci import _subskrypcja_json
    from nexus.platnosci.konfiguracja import ustawienia_platnosci
    from nexus.platnosci.uslugi import subskrypcja_uzytkownika

    _, _, pracownik = await grupa_z_czlonkiem(baza)
    rekord = await subskrypcja_uzytkownika(baza, str(pracownik))

    dane = await _subskrypcja_json(baza, rekord, ustawienia_platnosci())

    assert dane["limity"]["zadania_rownolegle"] == 8
    assert dane["limity"]["synchronizacja"]


# --- grupa w aplikacji: zadania naraz, przekazanie roli, przyjęcie zaproszenia -------------------

import asyncio  # noqa: E402

import nexus.api.modules.grupy as api_grupy  # noqa: E402
from nexus.db import Conversation, Run  # noqa: E402


def w_bazie(ustawienia: Settings, praca):  # type: ignore[no-untyped-def]  # noqa: F811
    """Wykonuje ``praca(baza)`` na bazie aplikacji testowej."""

    async def run():  # type: ignore[no-untyped-def]
        database = Database(ustawienia.database_url)
        try:
            await database.create_schema()
            return await praca(database)
        finally:
            await database.close()

    return asyncio.run(run())


def grupa_w_aplikacji(ustawienia: Settings) -> tuple[uuid.UUID, uuid.UUID]:  # noqa: F811
    """Opłacona grupa z założycielem i członkiem — konta portalu logujące się do aplikacji."""
    set_password(ustawienia)

    async def praca(baza: Database) -> tuple[uuid.UUID, uuid.UUID]:
        _, szef, pracownik = await grupa_z_czlonkiem(baza)
        return szef, pracownik

    return w_bazie(ustawienia, praca)


def zaloguj_konto(klient: TestClient, email: str) -> None:
    klient.cookies.clear()
    odpowiedz = klient.post("/api/auth/login", json={"username": email, "password": HASLO}, headers=HEADERS)
    assert odpowiedz.status_code == 200, odpowiedz.text


def sledz_chmure(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    """Zapisuje konta, dla których API zleca uzgodnienie limitu chmury."""
    uzgodnione: list[uuid.UUID] = []

    async def zapisz(_ustawienia: object, _baza: object, owner: uuid.UUID) -> None:
        uzgodnione.append(owner)

    monkeypatch.setattr(api_grupy, "uzgodnij_limit_po_zmianie_planu", zapisz)
    return uzgodnione


def test_zadania_naraz_licza_sie_dla_calej_grupy(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    """Cennik: „Osiem zadań naraz, więc kilka osób pracuje jednocześnie” — osiem na grupę.

    Liczone osobno dla każdego członka dawało grupie z 20 miejscami 160 zadań naraz.
    """
    szef, pracownik = grupa_w_aplikacji(settings)

    async def zajmij(baza: Database) -> list[uuid.UUID]:
        przebiegi = []
        async with baza.session() as session:
            for numer in range(8):
                rozmowa = Conversation(owner_id=szef if numer < 5 else pracownik, title=f"Zadanie {numer}")
                session.add(rozmowa)
                await session.flush()
                przebieg = Run(conversation_id=rozmowa.id, status="running")
                session.add(przebieg)
                await session.flush()
                przebiegi.append(przebieg.id)
        return przebiegi

    przebiegi = w_bazie(settings, zajmij)

    for email in ("pracownik@example.com", "szef@example.com"):
        zaloguj_konto(client, email)
        rozmowa = client.post("/api/conversations", json={}, headers=HEADERS).json()["id"]
        odmowa = client.post(
            f"/api/conversations/{rozmowa}/messages", json={"text": "Zadanie"}, headers=HEADERS
        )
        assert odmowa.status_code == 409, f"{email}: {odmowa.text}"
        assert "8 zadania naraz" in odmowa.json()["detail"]

    async def zakoncz(baza: Database) -> None:
        async with baza.session() as session:
            przebieg = await session.get(Run, przebiegi[0])
            przebieg.status = "done"

    w_bazie(settings, zakoncz)
    zaloguj_konto(client, "pracownik@example.com")
    rozmowa = client.post("/api/conversations", json={}, headers=HEADERS).json()["id"]
    wolne = client.post(f"/api/conversations/{rozmowa}/messages", json={"text": "Zadanie"}, headers=HEADERS)
    assert wolne.status_code == 202, wolne.text


def test_przekazanie_roli_wymaga_planu_grupa_i_uzgadnia_chmure_grupy(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    szef, pracownik = grupa_w_aplikacji(settings)
    uzgodnione = sledz_chmure(monkeypatch)
    zaloguj_konto(client, "szef@example.com")

    odmowa = client.post("/api/grupa/zalozyciel", json={"uzytkownik_id": str(pracownik)}, headers=HEADERS)
    assert odmowa.status_code == 400, odmowa.text
    assert "plan Grupa" in odmowa.json()["detail"]
    assert client.get("/api/grupa", headers=HEADERS).json()["grupa"]["jestem_zalozycielem"] is True
    assert uzgodnione == []

    w_bazie(settings, lambda baza: subskrypcja(baza, pracownik, grupy.PLAN_GRUPY, "aktywna"))
    przekazanie = client.post(
        "/api/grupa/zalozyciel", json={"uzytkownik_id": str(pracownik)}, headers=HEADERS
    )
    assert przekazanie.status_code == 200, przekazanie.text
    assert przekazanie.json()["grupa"]["jestem_zalozycielem"] is False
    # Limity wszystkich członków idą teraz za subskrypcją nowego założyciela.
    assert sorted(uzgodnione) == sorted([szef, pracownik])


def test_przyjecie_zaproszenia_uzgadnia_chmure_przyjmujacego(
    client: TestClient,  # noqa: F811
    settings: Settings,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Członek z własnym Nextcloudem dostaje limit grupy od razu, a nie przy wejściu do chmury."""
    set_password(settings)

    async def przygotuj(baza: Database) -> tuple[uuid.UUID, str]:
        szef = await konto(baza, "szef@example.com")
        pracownik = await konto(baza, "pracownik@example.com", plan="osobisty")
        await subskrypcja(baza, szef, grupy.PLAN_GRUPY, "aktywna")
        grupa = await grupy.zaloz(baza, szef)
        return pracownik, await grupy.zapros(baza, grupa, szef, "pracownik@example.com")

    pracownik, token = w_bazie(settings, przygotuj)
    uzgodnione = sledz_chmure(monkeypatch)
    zaloguj_konto(client, "pracownik@example.com")

    przyjecie = client.post("/api/grupa/przyjmij", json={"token": token}, headers=HEADERS)

    assert przyjecie.status_code == 200, przyjecie.text
    assert uzgodnione == [pracownik]
