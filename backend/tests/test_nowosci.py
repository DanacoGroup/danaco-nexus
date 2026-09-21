"""„Co nowego”: wykaz zmian wydania czytany z dziennika zmian.

Produkt zmienia się po kilkanaście razy dziennie, a użytkownik nie miał gdzie tego
zobaczyć. Testy pilnują, żeby okno dostawało zdania, a nie składnię Markdowna, i żeby
brał się z najnowszej sekcji — nie z całej historii.
"""

from __future__ import annotations

from nexus.api.modules.nowosci import czytaj_nowosci

DZIENNIK = """# Dziennik zmian

## [Nieopublikowane]

### Dodano

- **Montaż filmu ze zdjęć (`video_compose`).** Nexus umiał dotąd wyłącznie przerabiać
  gotowe nagranie — nie umiał go *złożyć*.
- **Spot dźwiękowy.** Kwestie lektora i podkład z biblioteki.

### Zmieniono

- **Ustawienia przestały być trzema kafelkami.** Teraz jest [profil](README.md) i reszta.

## [0.9.0] - 2026-09-01

### Dodano

- **Stara pozycja.** Nie powinna się pokazać.
"""


def test_bierze_tylko_najnowsza_sekcje() -> None:
    dane = czytaj_nowosci(DZIENNIK)

    assert dane["wersja"] == "Nieopublikowane"
    assert dane["wszystkich"] == 3
    assert all("Stara pozycja" not in p["tytul"] for p in dane["pozycje"])


def test_pozycje_maja_tytul_tresc_i_rodzaj() -> None:
    pozycje = czytaj_nowosci(DZIENNIK)["pozycje"]

    assert pozycje[0]["tytul"] == "Montaż filmu ze zdjęć (video_compose)"
    assert pozycje[0]["rodzaj"] == "Dodano"
    assert pozycje[2]["rodzaj"] == "Zmieniono"
    # Ciąg dalszy z wciętego wiersza dokleja się do treści.
    assert "nie umiał go" in pozycje[0]["tresc"]


def test_skladnia_markdowna_nie_wychodzi_do_okna() -> None:
    pozycje = czytaj_nowosci(DZIENNIK)["pozycje"]

    caly = " ".join(f"{p['tytul']} {p['tresc']}" for p in pozycje)
    assert "`" not in caly
    assert "**" not in caly
    assert "](" not in caly, "odsyłacz ma zostawić sam tekst"
    assert "profil" in pozycje[2]["tresc"]


def test_limit_obcina_wykaz() -> None:
    dane = czytaj_nowosci(DZIENNIK, limit=1)

    assert len(dane["pozycje"]) == 1
    assert dane["wszystkich"] == 3, "liczba wszystkich zostaje, żeby dało się powiedzieć „i więcej”"


def test_pusty_dziennik_nie_wywraca_odczytu() -> None:
    assert czytaj_nowosci("")["pozycje"] == []
    assert czytaj_nowosci("# Dziennik zmian\n\nbez sekcji\n")["pozycje"] == []


def test_tytul_bez_dwukropka_a_tresc_skrocona() -> None:
    """Wpisy w dzienniku pisze się dla kogoś, kto wchodzi w kod — w oknie ma zostać zdanie."""
    dziennik = (
        "# Dziennik zmian\n\n## [Nieopublikowane]\n\n### Dodano\n\n"
        "- **Zestaw po rozbudowie:** motywy 10 → 50, każdy z opisem i sprawdzonym kontrastem.\n"
        "  Weryfikator liczył wszystko od nowa i budował witryny: dwadzieścia budów na nowych\n"
        "  motywach, dwie regresyjne na starych, a do tego dwanaście presetów branżowych, które\n"
        "  wszystkie budują się bez błędu, więc urośnięcie biblioteki niczego nie zepsuło.\n"
    )

    pozycja = czytaj_nowosci(dziennik)["pozycje"][0]

    assert pozycja["tytul"] == "Zestaw po rozbudowie"
    assert len(pozycja["tresc"]) <= 224
    assert pozycja["tresc"].endswith((".", "…"))


def test_wyroznienie_przez_zlamanie_wiersza_nie_zostawia_gwiazdek() -> None:
    """Para gwiazdek potrafi rozjechać się na dwa wiersze dziennika."""
    dziennik = (
        "# Dziennik zmian\n\n## [Nieopublikowane]\n\n### Zmieniono\n\n"
        "- **Coś.** Przejścia to 26 wbudowanych **oraz 21\n  własnych** z biblioteki serwera.\n"
    )

    tresc = czytaj_nowosci(dziennik)["pozycje"][0]["tresc"]

    assert "*" not in tresc
    assert "oraz 21 własnych" in tresc


def test_pochylenie_tez_znika() -> None:
    dziennik = (
        "# Dziennik zmian\n\n## [Nieopublikowane]\n\n### Dodano\n\n"
        "- **Montaż.** Nexus umiał przerabiać nagranie — nie umiał go *złożyć*.\n"
    )

    tresc = czytaj_nowosci(dziennik)["pozycje"][0]["tresc"]

    assert "*" not in tresc
    assert "złożyć" in tresc
