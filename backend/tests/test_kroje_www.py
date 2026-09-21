"""Kroje strony z serwera zamiast z Google (``site_fonts_local``).

Przygotowanie jednej rodziny (podzbiór znaków + kompresja woff2) trwa kilkanaście sekund,
więc program serwera jest w większości testów podstawiony. Jeden test idzie po prawdziwym
`danaco-kroj` — bez tego nie wiadomo, czy uzgodnienie z programem w ogóle trzyma.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import ToolHarness

from nexus.tools import kroje_www
from nexus.tools.base import ToolError, registry
from nexus.tworczy.strony import site_store

STRONA_Z_GOOGLE = (
    "<!doctype html><html><head>"
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700'
    '&family=Lora&display=swap">'
    '<link rel="stylesheet" href="styl.css">'
    "</head><body><h1>Cześć</h1></body></html>"
)


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object):  # type: ignore[no-untyped-def]
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


@pytest.fixture
def strona(harness: ToolHarness):  # type: ignore[no-untyped-def]
    store = site_store(harness.settings)
    store.create("firma", "Firma")
    store.write_text("firma", "index.html", STRONA_Z_GOOGLE)
    store.write_text("firma", "styl.css", "@import url('https://fonts.googleapis.com/css2?family=Inter');\nh1{font-family:Inter}")
    return store


def test_narzedzie_jest_w_rejestrze() -> None:
    assert registry.get("site_fonts_local").name == "site_fonts_local"


def test_rodziny_czytane_z_odsylaczy() -> None:
    assert kroje_www._rodziny(STRONA_Z_GOOGLE) == ["Inter", "Lora"]
    assert kroje_www._rodziny("<p>bez krojów</p>") == []
    # Nazwa z plusem i z kodowaniem procentowym to ta sama rodzina co ze spacją.
    assert kroje_www._rodziny(
        '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display">'
    ) == ["Playfair Display"]
    # Import w CSS domyka adres apostrofem i średnikiem — nazwa rodziny kończy się przed nimi.
    assert kroje_www._rodziny(
        "@import url('https://fonts.googleapis.com/css2?family=Inter');"
    ) == ["Inter"]


def test_strona_bez_krojow_google_mowi_co_zrobic(harness: ToolHarness) -> None:
    store = site_store(harness.settings)
    store.create("pusta", "Pusta")
    store.write_text("pusta", "index.html", "<p>nic</p>")

    with pytest.raises(ToolError, match="nie wczytuje krojów z Google"):
        wywolaj(harness, "site_fonts_local", site="pusta")


def test_brak_strony_mowi_wprost(harness: ToolHarness) -> None:
    with pytest.raises(ToolError, match="Nie ma strony"):
        wywolaj(harness, "site_fonts_local", site="nie-ma")


def test_zbyt_wiele_rodzin_odrzucone(harness: ToolHarness, strona) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ToolError, match="limit"):
        wywolaj(
            harness,
            "site_fonts_local",
            site="firma",
            rodziny=[f"Krój {numer}" for numer in range(kroje_www.MAKS_RODZIN + 1)],
        )


def test_rodzina_spoza_repozytorium_nie_przekresla_reszty(
    harness: ToolHarness, strona, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    """Krój firmowy albo płatny zostaje bez zmian, ale reszta i tak schodzi na serwer."""
    prawdziwe = kroje_www.PROGRAM

    def udawaj(self, polecenie, timeout=0, cwd=None, env=None):  # type: ignore[no-untyped-def]
        assert polecenie[0] == prawdziwe
        rodzina, cel = polecenie[2], Path(polecenie[3])
        if rodzina == "Lora":
            raise ToolError("nie znaleziono rodziny")
        (cel / f"{rodzina.lower()}.woff2").write_bytes(b"woff2")
        (cel / f"{rodzina.lower()}.css").write_text(
            f'@font-face{{font-family:"{rodzina}";src:url("kroje/{rodzina.lower()}.woff2")}}',
            encoding="utf-8",
        )
        (cel / f"{rodzina.lower()}-OFL.txt").write_text("licencja", encoding="utf-8")
        return None

    monkeypatch.setattr(kroje_www.ToolContext, "run_command", udawaj, raising=False)

    wynik = wywolaj(harness, "site_fonts_local", site="firma")

    assert wynik.data["rodziny"] == ["Inter"]
    assert wynik.data["poza_repozytorium"] == ["Lora"]
    html = strona.read_text("firma", "index.html")
    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html, "preconnect do Google też ma zniknąć"
    assert f'href="{kroje_www.ARKUSZ}"' in html
    assert 'href="styl.css"' in html, "własny arkusz strony zostaje nietknięty"
    # Import w CSS też znika, a plik kroju i licencja leżą w szkicu.
    assert "googleapis" not in strona.read_text("firma", "styl.css")
    assert strona.read_text("firma", kroje_www.ARKUSZ).count("@font-face") == 1
    sciezki = [pozycja["path"] for pozycja in strona.list_files("firma")]
    assert "kroje/inter.woff2" in sciezki
    assert "kroje/inter-OFL.txt" in sciezki, "licencja OFL musi jechać razem z krojem"


def test_prawdziwy_program_serwera_oddaje_krój_z_polskimi_znakami(
    harness: ToolHarness, strona
) -> None:  # type: ignore[no-untyped-def]
    """Uzgodnienie z `danaco-kroj`: nazwa polecenia, układ wyniku, prefiks adresu."""
    if not Path(kroje_www.PROGRAM).exists():
        pytest.skip("danaco-kroj nie jest zainstalowany")

    wynik = wywolaj(harness, "site_fonts_local", site="firma", rodziny=["Inter"])

    assert wynik.data["rodziny"] == ["Inter"]
    arkusz = strona.read_text("firma", kroje_www.ARKUSZ)
    assert "@font-face" in arkusz and 'font-family: "Inter"' in arkusz
    assert 'url("kroje/' in arkusz, "adresy w arkuszu mają wskazywać pliki w szkicu"
    pliki = [pozycja["path"] for pozycja in strona.list_files("firma")]
    assert any(p.endswith(".woff2") for p in pliki)


def test_odsylacz_do_arkusza_liczy_sie_od_podstrony(
    harness: ToolHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Arkusz leży w korzeniu strony — podstrona w katalogu musi wskazać go przez „../”."""
    store = site_store(harness.settings)
    store.create("wielostronicowa", "Wiele stron")
    store.write_text("wielostronicowa", "index.html", STRONA_Z_GOOGLE)
    store.write_text("wielostronicowa", "cennik/index.html", STRONA_Z_GOOGLE)

    def udawaj(self, polecenie, timeout=0, cwd=None, env=None):  # type: ignore[no-untyped-def]
        cel = Path(polecenie[3])
        (cel / "kroj.woff2").write_bytes(b"woff2")
        (cel / "kroj.css").write_text("@font-face{font-family:x}", encoding="utf-8")
        return None

    monkeypatch.setattr(kroje_www.ToolContext, "run_command", udawaj, raising=False)

    wywolaj(harness, "site_fonts_local", site="wielostronicowa")

    assert f'href="{kroje_www.ARKUSZ}"' in store.read_text("wielostronicowa", "index.html")
    assert f'href="../{kroje_www.ARKUSZ}"' in store.read_text("wielostronicowa", "cennik/index.html")
