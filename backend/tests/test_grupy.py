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

    await grupy.przekaz_zalozyciela(baza, grupa, szef, nastepca)

    # Od tej chwili płaci następca — także za poprzedniego założyciela.
    assert await grupy.konto_rozliczeniowe(baza, nastepca) == nastepca
    assert await grupy.konto_rozliczeniowe(baza, szef) == nastepca
    role = {pozycja.email: pozycja.rola for pozycja in await grupy.czlonkowie(baza, grupa.id)}
    assert role["nastepca@example.com"] == grupy.ROLA_ZALOZYCIEL
    assert role["szef@example.com"] == grupy.ROLA_CZLONEK


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
