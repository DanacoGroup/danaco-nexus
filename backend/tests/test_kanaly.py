"""Kanały dla wyszukiwarek: mapa witryny, robots.txt i zgodność obu z trasowaniem portalu.

Testy działają na samym module ``nexus.portal.kanaly`` — bez bazy i bez klienta HTTP — bo
sprawdzają reguły doboru adresów, a nie sposób ich podania. Ścieżki publiczne czytane są
z ``frontend/src/portal/trasy.ts``, żeby mapa i trasowanie nie rozjechały się po cichu.
"""

from __future__ import annotations

import re
from pathlib import Path

from nexus.portal import kanaly

BAZA = "https://danaco-nexus.pl"
TRASY = Path(__file__).resolve().parents[2] / "frontend" / "src" / "portal" / "trasy.ts"
# Strony zgodności są publiczne i podlinkowane ze stopki, więc muszą być w mapie witryny.
ZGODNOSC = ("/portal/prywatnosc", "/portal/regulamin", "/portal/cookies")
# Klucz wpisu w stałej trasowania: gołe słowo albo słowo w cudzysłowie (także puste — strona główna
# portalu). Cyfry i łączniki są dopuszczone, żeby nowa trasa nie wypadła z kontroli po cichu.
KLUCZ = re.compile(r'^\s*"?([a-z0-9_-]*)"?\s*:\s*"')


def _mapa() -> str:
    return kanaly.sitemap(BAZA, [])


def _sciezki_stalej(zrodlo: str, nazwa: str) -> set[str]:
    """Ścieżki portalu z jednej stałej trasowania; każdy wiersz bloku musi dać się odczytać."""
    blok = re.search(rf"{nazwa}[^=]*=\s*\{{(.*?)\}}", zrodlo, re.S)
    assert blok, f"w trasy.ts nie ma stałej {nazwa}"
    sciezki = set()
    for wiersz in blok.group(1).splitlines():
        tekst = wiersz.strip()
        if not tekst or tekst.startswith("//"):
            continue
        dopasowanie = KLUCZ.match(wiersz)
        assert dopasowanie, f"{nazwa}: nierozpoznany wpis {tekst}"
        klucz = dopasowanie.group(1)
        sciezki.add(f"/portal/{klucz}" if klucz else "/portal")
    return sciezki


def test_mapa_zawiera_strony_zgodnosci_i_zastosowania() -> None:
    mapa = _mapa()
    for sciezka in (*ZGODNOSC, "/portal/zastosowania"):
        assert f"<loc>{BAZA}{sciezka}</loc>" in mapa


def test_mapa_pomija_adresy_zamkniete() -> None:
    mapa = _mapa()
    for sciezka in kanaly.ZAMKNIETE:
        assert f"<loc>{BAZA}{sciezka.rstrip('/')}</loc>" not in mapa


def test_czy_zamkniety_odsiewa_panele_i_przepuszcza_strony_publiczne() -> None:
    zamkniete = ("/portal/szukaj", "/portal/szukaj?q=faktura", "/portal/konto", "/api/portal/tresci")
    for sciezka in (*zamkniete, "/s/wizytowka"):
        assert kanaly.czy_zamkniety(sciezka) is True
    for sciezka in (*ZGODNOSC, "/", "/wyprobuj", "/portal/cennik", "/portal/blog/pierwsze-kroki"):
        assert kanaly.czy_zamkniety(sciezka) is False


def test_robots_zamyka_wyszukiwarke_portalu() -> None:
    tresc = kanaly.robots(BAZA)
    assert "Disallow: /portal/szukaj" in tresc
    assert f"Sitemap: {BAZA}/sitemap.xml" in tresc


def test_mapa_zgadza_sie_z_trasowaniem_portalu() -> None:
    """Każda trasa portalu — prosta i sekcja z pozycjami — jest albo w mapie, albo zamknięta."""
    zrodlo = TRASY.read_text(encoding="utf-8")
    trasy = _sciezki_stalej(zrodlo, "PROSTE") | _sciezki_stalej(zrodlo, "Z_POZYCJA")
    for sciezka in (*ZGODNOSC, "/portal", "/portal/blog", "/portal/s"):
        assert sciezka in trasy, sciezka
    mapa = _mapa()
    for sciezka in trasy:
        w_mapie = f"<loc>{BAZA}{sciezka}</loc>" in mapa
        assert w_mapie != kanaly.czy_zamkniety(sciezka), sciezka


def test_przedrostek_stron_tworcy_zamkniety_bez_samych_stron() -> None:
    """``/portal/s`` nie jest stroną, ale opublikowane ``/portal/s/<adres>`` zostają otwarte."""
    assert kanaly.czy_zamkniety("/portal/s") is True
    assert kanaly.czy_zamkniety("/portal/s/wizytowka") is False
    assert kanaly.czy_zamkniety("/portal/szukaj") is True
    assert "Disallow: /portal/s$" in kanaly.robots(BAZA)
