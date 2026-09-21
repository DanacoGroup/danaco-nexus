"""Znaczniki strony wstawiane po stronie serwera.

Robot Facebooka, LinkedIna czy Slacka nie uruchamia JavaScriptu — widzi wyłącznie HTML,
który przyszedł z serwera. Te testy pilnują, że adres publiczny dostaje własny tytuł, opis
i Open Graph, a adres za logowaniem zostaje z „noindex”.
"""

from __future__ import annotations

import re
from pathlib import Path

from nexus.api import znaczniki

#: Korzeń repozytorium — test sięga po spis stron trzymany po stronie klienta.
KORZEN = Path(__file__).resolve().parents[2]

DOKUMENT = """<!doctype html><html lang="pl"><head>
<meta charset="utf-8">
<title>Danaco Nexus</title>
<meta name="description" content="Stary opis">
<meta property="og:title" content="Stary tytuł">
</head><body><div id="root"></div></body></html>"""


def test_podmienia_tytul_opis_i_open_graph() -> None:
    wynik = znaczniki.zastosuj(DOKUMENT, znaczniki.STALE["/portal/cennik"], "https://danaco-nexus.pl")

    assert "<title>Cennik Danaco Nexus — plany Osobisty, Pro i Grupa</title>" in wynik
    assert "Stary opis" not in wynik
    assert "Stary tytuł" not in wynik
    assert 'property="og:url" content="https://danaco-nexus.pl/portal/cennik"' in wynik
    assert 'rel="canonical" href="https://danaco-nexus.pl/portal/cennik"' in wynik
    assert 'property="og:image" content="https://danaco-nexus.pl/og.png"' in wynik
    assert "index, follow" in wynik


def test_dokłada_brakujące_znaczniki_przed_zamknieciem_head() -> None:
    wynik = znaczniki.zastosuj(DOKUMENT, znaczniki.STALE["/start"], "")

    # Dokument nie miał og:url ani kanonicznego — mają dojść, a nie zniknąć.
    assert 'property="og:url"' in wynik
    assert 'rel="canonical"' in wynik
    assert wynik.count("</head>") == 1


def test_pozycja_z_noindex_nie_jest_indeksowana() -> None:
    pozycja = znaczniki.Znaczniki("Szkic", "Opis", "/portal/blog/szkic", indeksuj=False)
    wynik = znaczniki.zastosuj(DOKUMENT, pozycja, "https://danaco-nexus.pl")
    assert "noindex, nofollow" in wynik
    assert "index, follow" not in wynik


def test_cudzyslowy_w_tytule_nie_rozbijaja_dokumentu() -> None:
    pozycja = znaczniki.Znaczniki('Tytuł z "cudzysłowem" i <tagiem>', "Opis & znak", "/portal")
    wynik = znaczniki.zastosuj(DOKUMENT, pozycja, "")
    assert "&quot;cudzysłowem&quot;" in wynik or "&#34;cudzysłowem&#34;" in wynik
    assert "<tagiem>" not in wynik


def test_rozpoznaje_adresy_tresci_portalu() -> None:
    assert znaczniki.sciezka_tresci("/portal/blog/jak-zaczac") == ("blog", "jak-zaczac")
    assert znaczniki.sciezka_tresci("/portal/wiedza/ocr-po-polsku") == ("wiedza", "ocr-po-polsku")
    assert znaczniki.sciezka_tresci("/portal/s/o-nas") == ("strona", "o-nas")
    # Listy, adresy aplikacji i próby wyjścia poza wzorzec nie są pozycjami treści.
    assert znaczniki.sciezka_tresci("/portal/blog") is None
    assert znaczniki.sciezka_tresci("/m/pliki") is None
    assert znaczniki.sciezka_tresci("/portal/blog/../../etc") is None
    assert znaczniki.sciezka_tresci("/portal/blog/WIELKIE") is None


def test_kazda_strona_portalu_z_klienta_jest_znana_serwerowi() -> None:
    """Serwer odsyła 404 na adres spoza swojej listy — lista musi obejmować wszystkie strony.

    Klient trzyma spis stron portalu w typie ``PortalStrona`` (``frontend/src/portal/trasy.ts``),
    serwer w ``kanaly.STRONY_STALE`` plus ``ZAMKNIETE_STRONY``. Gdy powstanie nowa strona
    i trafi tylko do klienta, ten test padnie — inaczej padłaby dopiero strona u gościa.
    """
    zrodlo = (KORZEN / "frontend" / "src" / "portal" / "trasy.ts").read_text(encoding="utf-8")
    blok = zrodlo.split("export type PortalStrona =", 1)[1].split(";", 1)[0]
    nazwy = set(re.findall(r'"([a-z]+)"', blok))
    # „glowna” to ``/portal``, „strona” to ``/portal/s/<adres>`` (pozycja treści),
    # „nieznana” nie jest adresem — reszta ma postać ``/portal/<nazwa>``.
    for nazwa in sorted(nazwy - {"glowna", "strona", "nieznana"}):
        assert znaczniki.strona_portalu(f"/portal/{nazwa}"), nazwa
    assert not znaczniki.strona_portalu("/portal/takiej-strony-nie-ma")


def test_wykaz_stalych_adresow_ma_komplet_pol() -> None:
    for adres, pozycja in znaczniki.STALE.items():
        assert adres.startswith("/"), adres
        assert pozycja.sciezka == adres, adres
        assert len(pozycja.tytul) > 10, adres
        assert len(pozycja.opis) > 40, adres
