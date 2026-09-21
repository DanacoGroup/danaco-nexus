"""Narzędzia pracy nad kodem i stronami: kontrole jakości, audyt, zrzut, ikony, odchudzanie.

Sprawdzamy to, co decyduje o poprawności i bezpieczeństwie: obecność w rejestrze, odrzucanie
ścieżek i adresów spoza przestrzeni użytkownika, komunikat przy braku programu oraz złożenie
polecenia. Kontrole szybkie (typos, svgo, pa11y, ikony) uruchamiamy naprawdę — reszta idzie
przez podstawiony ``ToolContext.run_command``, bo Lighthouse i semgrep liczą kilkanaście sekund.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import ToolHarness, requires_program

from nexus.tools import projekt_kod
from nexus.tools.base import ToolError, ToolResult, registry
from nexus.tworczy.strony import site_store

NARZEDZIA = ("code_check", "web_audit", "web_screenshot", "icon_find", "site_optimize_assets")

STRONA = """<!doctype html><html><head><meta charset="utf-8"><title>Próba</title></head>
<body><h1>Kawiarnia</h1><img src="img/logo.svg"><p>Zapraszamy</p></body></html>"""
LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
    '  <!-- znak firmowy -->\n  <circle cx="50.00000" cy="50.0000" r="40.000" fill="#ff0000"/>\n</svg>'
)


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object) -> ToolResult:
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


def zaloz_strone(harness: ToolHarness, adres: str = "proba") -> None:
    """Szkic strony w magazynie stron (tak jak zrobiłby to moduł Strony)."""
    store = site_store(harness.settings)
    store.create(adres, "Próba")
    store.write_text(adres, "index.html", STRONA)
    store.write_text(adres, "img/logo.svg", LOGO)


def zaloz_projekt(harness: ToolHarness, nazwa: str = "sklep") -> Path:
    """Przestrzeń projektu modułu Kod z kilkoma plikami do sprawdzenia."""
    katalog = harness.settings.kod_dir / nazwa
    (katalog / "backend").mkdir(parents=True)
    (katalog / "backend" / "app.py").write_text(
        "import subprocess\n\n\ndef uruchom(polecenie):\n    return subprocess.call(polecenie, shell=True)\n",
        encoding="utf-8",
    )
    (katalog / "skrypt.sh").write_text(
        "#!/bin/bash\nfor f in $(ls *.txt); do rm $f; done\n", encoding="utf-8"
    )
    return katalog


def test_narzedzia_sa_w_rejestrze() -> None:
    assert set(NARZEDZIA) <= set(registry.names())


# --- kontrola kodu --------------------------------------------------------------------------------


def test_kontrola_wymaga_jednego_celu(harness: ToolHarness) -> None:
    """Bez celu albo z dwoma celami naraz narzędzie nie zgaduje, tylko pyta."""
    with pytest.raises(ToolError, match="jedno z dwóch"):
        wywolaj(harness, "code_check")


def test_kontrola_odrzuca_sciezke_poza_projektem(harness: ToolHarness) -> None:
    """Podkatalog z ``..`` nie może wyprowadzić kontroli poza przestrzeń projektu."""
    zaloz_projekt(harness)
    with pytest.raises(ToolError, match="wewnątrz projektu"):
        wywolaj(harness, "code_check", projekt="sklep", podkatalog="../../../etc")


def test_kontrola_odrzuca_nieznany_projekt(harness: ToolHarness) -> None:
    with pytest.raises(ToolError, match="Nie ma projektu"):
        wywolaj(harness, "code_check", projekt="czegos-takiego-nie-ma")


def test_brak_programu_mowi_po_ludzku(harness: ToolHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    zaloz_projekt(harness)
    monkeypatch.setattr(projekt_kod.shutil, "which", lambda _nazwa: None)
    with pytest.raises(ToolError, match="niedostępne na tym serwerze"):
        wywolaj(harness, "code_check", projekt="sklep", kontrole=["bezpieczenstwo"])


def test_semgrep_sklada_polecenie_z_regulami_wykrytego_jezyka(
    harness: ToolHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Język wykryty po plikach ma wskazać katalog reguł, a wynik iść do pliku w przebiegu."""
    zaloz_projekt(harness)
    reguly = harness.settings.data_dir / "reguly"
    (reguly / "python").mkdir(parents=True)
    monkeypatch.setattr(projekt_kod, "REGULY_SEMGREP", reguly)
    monkeypatch.setattr(projekt_kod.shutil, "which", lambda nazwa: f"/udawane/{nazwa}")
    zapis: list[list[str]] = []

    def udawany_bieg(self, arguments, timeout=600, cwd=None, env=None):  # type: ignore[no-untyped-def]
        zapis.append(list(arguments))
        raport = next(arg for arg in arguments if arg.startswith("--json-output=")).split("=", 1)[1]
        Path(raport).write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "path": str(harness.settings.kod_dir / "sklep" / "backend" / "app.py"),
                            "start": {"line": 5},
                            "check_id": "python.lang.security.audit.subprocess-shell-true",
                            "extra": {"severity": "ERROR", "message": "shell=True"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return None

    monkeypatch.setattr("nexus.tools.base.ToolContext.run_command", udawany_bieg)
    wynik = wywolaj(harness, "code_check", projekt="sklep", kontrole=["bezpieczenstwo"])

    polecenie = zapis[0]
    assert polecenie[0].endswith("semgrep")
    assert "--metrics=off" in polecenie
    assert f"--config={reguly / 'python'}" in polecenie
    assert polecenie[-1] == str(harness.settings.kod_dir / "sklep")
    kontrola = wynik.data["kontrole"]["bezpieczenstwo"]
    assert kontrola["jezyk"] == "python"
    assert kontrola["lista"] == [
        {
            "plik": "backend/app.py",
            "wiersz": 5,
            "waga": "error",
            "regula": "subprocess-shell-true",
            "opis": "shell=True",
        }
    ]


def test_kontrola_zglasza_brak_skryptow_powloki(harness: ToolHarness) -> None:
    katalog = harness.settings.kod_dir / "tylko-python"
    katalog.mkdir(parents=True)
    (katalog / "main.py").write_text("print('cześć')\n", encoding="utf-8")
    with pytest.raises(ToolError, match="skryptów powłoki"):
        wywolaj(harness, "code_check", projekt="tylko-python", kontrole=["powloka"])


@requires_program("typos")
def test_literowki_znajduja_blad_w_pliku_z_rozmowy(harness: ToolHarness, tmp_path: Path) -> None:
    """Kontrola uruchomiona naprawdę na pliku wysłanym w rozmowie."""
    plik = tmp_path / "notatka.md"
    plik.write_text("Ther is a typo adn another one.\n", encoding="utf-8")
    wynik = wywolaj(harness, "code_check", file_ids=[harness.add(plik)], kontrole=["literowki"])
    literowki = wynik.data["kontrole"]["literowki"]
    assert literowki["znalezione"] >= 2
    assert {poz["slowo"] for poz in literowki["lista"]} >= {"Ther", "adn"}
    assert all(poz["plik"] == "notatka.md" for poz in literowki["lista"])


# --- audyt i zrzut strony -------------------------------------------------------------------------


def test_audyt_wymaga_jednego_celu(harness: ToolHarness) -> None:
    zaloz_strone(harness)
    with pytest.raises(ToolError, match="albo publiczny adres"):
        wywolaj(harness, "web_audit", site="proba", adres="https://example.com/")


def test_audyt_odrzuca_adres_w_sieci_lokalnej(harness: ToolHarness) -> None:
    """Model nie może skierować przeglądarki na usługi wewnętrzne serwera."""
    with pytest.raises(ToolError, match="niedozwolony|prywatn"):
        wywolaj(harness, "web_audit", adres="http://127.0.0.1:8000/admin")


def test_audyt_odrzuca_nieistniejaca_podstrone(harness: ToolHarness) -> None:
    zaloz_strone(harness)
    with pytest.raises(ToolError, match="nie ma pliku"):
        wywolaj(harness, "web_audit", site="proba", podstrona="cennik.html")


@requires_program("pa11y")
def test_audyt_dostepnosci_wytyka_brak_opisu_obrazu(harness: ToolHarness) -> None:
    """Szkic strony jest podawany lokalnie i badany naprawdę — bez publikacji."""
    zaloz_strone(harness)
    wynik = wywolaj(harness, "web_audit", site="proba", zakres="dostepnosc", limit=20)
    dostepnosc = wynik.data["dostepnosc"]
    assert dostepnosc["bledy"] >= 1
    opisy = " ".join(poz["opis"] for poz in dostepnosc["lista"])
    assert "alt" in opisy


def test_zrzut_sklada_polecenie_przegladarki(harness: ToolHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    """Wybór urządzenia i motywu ma trafić do polecenia, a adres wskazywać lokalny podgląd."""
    zaloz_strone(harness)
    monkeypatch.setattr(projekt_kod.shutil, "which", lambda nazwa: f"/udawane/{nazwa}")
    zapis: list[list[str]] = []

    def udawany_bieg(self, arguments, timeout=600, cwd=None, env=None):  # type: ignore[no-untyped-def]
        zapis.append(list(arguments))
        from PIL import Image

        Image.new("RGB", (390, 844), (240, 240, 240)).save(arguments[-1])
        return None

    monkeypatch.setattr("nexus.tools.base.ToolContext.run_command", udawany_bieg)
    wynik = wywolaj(harness, "web_screenshot", site="proba", urzadzenie="telefon", motyw="ciemny")

    polecenie = zapis[0]
    assert polecenie[0].endswith("playwright")
    assert polecenie[1] == "screenshot"
    assert "--viewport-size=390,844" in polecenie
    assert "--color-scheme=dark" in polecenie
    assert "--full-page" in polecenie
    assert polecenie[-2].startswith("http://127.0.0.1:")
    assert wynik.images and wynik.files


# --- ikony ----------------------------------------------------------------------------------------

brak_ikon = pytest.mark.skipif(not projekt_kod.IKONY_INDEKS.is_file(), reason="Brak zbioru ikon Iconify")


def test_ikony_odrzucaja_niedozwolona_barwe(harness: ToolHarness) -> None:
    with pytest.raises(ToolError, match="Niedozwolona barwa"):
        wywolaj(harness, "icon_find", zapytanie="envelope", kolor='#fff" onload="x')


def test_zbior_ikon_nie_wychodzi_poza_katalog_zbiorow() -> None:
    """Nazwa zbioru jest sprawdzana, więc nie da się nią wskazać pliku spoza zbioru ikon."""
    with pytest.raises(ToolError, match="Niepoprawna nazwa zbioru"):
        projekt_kod._zbior_ikon("../../../etc/passwd")


@brak_ikon
def test_ikony_znajduja_koperte(harness: ToolHarness) -> None:
    wynik = wywolaj(harness, "icon_find", zapytanie="envelope", limit=3)
    ikony = wynik.data["ikony"]
    assert 1 <= len(ikony) <= 3
    assert all(poz["svg"].startswith("<svg") and poz["svg"].endswith("</svg>") for poz in ikony)
    assert all("envelope" in poz["nazwa"] for poz in ikony)


@brak_ikon
def test_ikony_trafiaja_do_szkicu_strony(harness: ToolHarness) -> None:
    zaloz_strone(harness)
    wynik = wywolaj(harness, "icon_find", zapytanie="envelope", limit=2, do_strony="proba", zestaw="mdi")
    zapisane = wynik.data["zapisane_pliki"]
    assert zapisane and all(sciezka.startswith("img/ikony/") for sciezka in zapisane)
    szkic = site_store(harness.settings).draft_dir("proba")
    assert (szkic / zapisane[0]).is_file()


@brak_ikon
def test_ikony_zglaszaja_brak_trafien(harness: ToolHarness) -> None:
    with pytest.raises(ToolError, match="Nie znalazłem ikony"):
        wywolaj(harness, "icon_find", zapytanie="zzzqqq-nie-ma-takiej")


# --- odchudzanie plików strony ----------------------------------------------------------------------


def test_odchudzanie_zglasza_brak_plikow(harness: ToolHarness) -> None:
    zaloz_strone(harness)
    with pytest.raises(ToolError, match="nie ma plików"):
        wywolaj(harness, "site_optimize_assets", site="proba", rodzaj="png")


@requires_program("svgo")
def test_odchudzanie_zmniejsza_svg_w_szkicu(harness: ToolHarness) -> None:
    """Plik w szkicu zostaje podmieniony na mniejszy — naprawdę, przez svgo."""
    zaloz_strone(harness)
    szkic = site_store(harness.settings).draft_dir("proba")
    przed = (szkic / "img" / "logo.svg").stat().st_size
    wynik = wywolaj(harness, "site_optimize_assets", site="proba", rodzaj="svg")
    assert wynik.data["odchudzone"][0]["plik"] == "img/logo.svg"
    assert (szkic / "img" / "logo.svg").stat().st_size < przed


def test_sekrety_nie_wypuszczaja_wartosci_klucza(
    harness: ToolHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gitleaks ma iść z `--redact`: do rozmowy wraca opis znaleziska, nie sam sekret."""
    zaloz_projekt(harness)
    monkeypatch.setattr(projekt_kod.shutil, "which", lambda nazwa: f"/udawane/{nazwa}")
    zapis: list[list[str]] = []

    def udawana_kontrola(ctx, polecenie, kody_ok):  # type: ignore[no-untyped-def]
        zapis.append(list(polecenie))
        raport = polecenie[polecenie.index("--report-path") + 1]
        Path(raport).write_text(
            json.dumps(
                [
                    {
                        "File": str(harness.settings.kod_dir / "sklep" / "backend" / "app.py"),
                        "StartLine": 12,
                        "RuleID": "stripe-access-token",
                        "Description": "Stripe Access Token",
                    }
                ]
            ),
            encoding="utf-8",
        )
        return ""

    monkeypatch.setattr(projekt_kod, "_uruchom_kontrole", udawana_kontrola)
    wynik = wywolaj(harness, "code_check", projekt="sklep", kontrole=["sekrety"])

    assert "--redact" in zapis[0]
    kontrola = wynik.data["kontrole"]["sekrety"]
    assert kontrola["lista"] == [
        {
            "plik": "backend/app.py",
            "wiersz": 12,
            "waga": "error",
            "regula": "stripe-access-token",
            "opis": "Stripe Access Token",
        }
    ]


def test_zaleznosci_wypisuja_podatnosci_bibliotek(
    harness: ToolHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    zaloz_projekt(harness)
    monkeypatch.setattr(projekt_kod.shutil, "which", lambda nazwa: f"/udawane/{nazwa}")
    raport = json.dumps(
        {
            "results": [
                {
                    "source": {"path": str(harness.settings.kod_dir / "sklep" / "requirements.txt")},
                    "packages": [
                        {
                            "package": {"name": "requests", "version": "2.19.0"},
                            "vulnerabilities": [
                                {"id": "GHSA-x84v", "summary": "Wyciek nagłówka Authorization"}
                            ],
                        }
                    ],
                }
            ]
        }
    )
    monkeypatch.setattr(projekt_kod, "_uruchom_kontrole", lambda *_args, **_kwargs: raport)
    wynik = wywolaj(harness, "code_check", projekt="sklep", kontrole=["zaleznosci"])

    kontrola = wynik.data["kontrole"]["zaleznosci"]
    assert kontrola["znalezione"] == 1
    assert kontrola["lista"][0]["regula"] == "GHSA-x84v"
    assert "requests 2.19.0" in kontrola["lista"][0]["opis"]


def test_nowe_kontrole_sa_w_wykazie_narzedzia() -> None:
    """Wykaz kontroli jest jednocześnie dokumentacją dla agenta — ma wymieniać komplet."""
    narzedzie = registry.get("code_check")
    opis = narzedzie.input_model.model_fields["kontrole"].description or ""
    for nazwa in ("sekrety", "zaleznosci", "powtorzenia"):
        assert nazwa in opis


def test_uzupelnienie_aliasow_typow_podstron(tmp_path: Path) -> None:
    """Presety nazywają część podstron po swojemu; rdzeń zestawu zna tylko swoje nazwy.

    Bez dopisania nazw zastępczych budowa witryny wywalała się na pierwszej takiej
    podstronie — dziewięć presetów na dwanaście w ogóle nie dawało się zbudować.
    """
    from nexus.tools.kit_www import _uzupelnij_aliasy

    plik = tmp_path / "src" / "lib" / "page-types.ts"
    plik.parent.mkdir(parents=True)
    plik.write_text(
        'export const TYPE_ALIASES: Record<string, { type: string }> = {\n'
        '  page: { type: "about" },\n'
        '  "menu": { type: "product-catalog" },\n'
        "};\n",
        encoding="utf-8",
    )

    dolozone = _uzupelnij_aliasy(tmp_path)
    tresc = plik.read_text(encoding="utf-8")

    assert dolozone > 0
    assert "Object.assign(TYPE_ALIASES" in tresc
    # Nazwa już obecna nie jest dopisywana drugi raz.
    assert tresc.count('"menu":') == 1
    assert '"courses-index": { type: "category" }' in tresc

    # Powtórne wywołanie na uzupełnionym pliku nie dokłada już niczego.
    assert _uzupelnij_aliasy(tmp_path) == 0


def test_uzupelnienie_aliasow_bez_pliku_nic_nie_robi(tmp_path: Path) -> None:
    from nexus.tools.kit_www import _uzupelnij_aliasy

    assert _uzupelnij_aliasy(tmp_path) == 0


@pytest.mark.skipif(
    not Path("/danaco/programy/web/kit/presets").is_dir(),
    reason="Danaco Web Kit nie jest zainstalowany na tym serwerze.",
)
def test_kazdy_preset_ma_pokryte_typy_podstron() -> None:
    """Każdy typ podstrony z presetu ma odpowiednik w rdzeniu albo nazwę zastępczą.

    Bez tego budowa witryny wywala się na pierwszej nieznanej podstronie — a sprawdzenie
    tego przez zbudowanie dwunastu witryn trwa minuty. Tu wystarczy odczyt map stron.
    """
    import re as _re

    from nexus.tools.kit_www import ALIASY_TYPOW

    rdzen = Path("/danaco/programy/web/kit/core/src/lib/page-types.ts")
    typy_rdzenia = set(_re.findall(r'^\s*"?([\w-]+)"?:\s*\{\s*label:', rdzen.read_text("utf-8"), _re.M))
    aliasy_rdzenia = set(
        _re.findall(r'^\s*"?([\w-]+)"?:\s*\{\s*type:', rdzen.read_text("utf-8"), _re.M)
    )
    znane = typy_rdzenia | aliasy_rdzenia | set(ALIASY_TYPOW)
    assert typy_rdzenia, "nie udało się odczytać typów rdzenia zestawu"

    braki: dict[str, set[str]] = {}
    for mapa in sorted(Path("/danaco/programy/web/kit/presets").glob("*/site.yaml")):
        tresc = mapa.read_text("utf-8")
        uzyte = set(_re.findall(r"^\s+(?:item)?[Tt]ype:\s*([\w-]+)\s*$", tresc, _re.M))
        nieznane = uzyte - znane
        if nieznane:
            braki[mapa.parent.name] = nieznane
    assert not braki, f"presety używają typów bez odpowiednika: {braki}"


def test_kolekcja_szablonow_czyta_meta_gdy_brak_zbiorczego_wykazu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zbiorczy `kolekcja.json` bywa nieobecny — wtedy liczy się `meta.json` szablonów.

    Bez tego `site_kit_catalog` zgłaszał zero szablonów, choć na dysku leżało ich
    kilkadziesiąt, w tym kilkadziesiąt z gotową, zbudowaną witryną.
    """
    from nexus.tools import kit_www

    szablony = tmp_path / "szablony"
    (szablony / "astro-blog" / "witryna").mkdir(parents=True)
    (szablony / "astro-blog" / "meta.json").write_text(
        json.dumps({"id": "astro-blog", "nazwa": "Astro Blog", "licencja": "MIT", "liczba_stron": 8}),
        encoding="utf-8",
    )
    (szablony / "bez-budowy").mkdir(parents=True)
    (szablony / "bez-budowy" / "meta.json").write_text(
        json.dumps({"id": "bez-budowy", "nazwa": "Bez budowy"}), encoding="utf-8"
    )
    monkeypatch.setattr(kit_www, "KOLEKCJA", tmp_path)
    # Zbiorczy wykaz leży też przy rdzeniu zestawu — odcinamy oba, żeby sprawdzić awaryjne
    # czytanie `meta.json`.
    monkeypatch.setattr(kit_www, "KIT", tmp_path / "kit")

    wynik = kit_www._kolekcja()
    wedlug_id = {pozycja["id"]: pozycja for pozycja in wynik["szablony"]}

    assert set(wedlug_id) == {"astro-blog", "bez-budowy"}
    assert wedlug_id["astro-blog"]["gotowa_witryna"] is True
    assert wedlug_id["bez-budowy"]["gotowa_witryna"] is False


def test_szablon_bez_gotowej_witryny_mowi_co_zrobic(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nexus.tools import kit_www

    (tmp_path / "szablony" / "pusty").mkdir(parents=True)
    monkeypatch.setattr(kit_www, "KOLEKCJA", tmp_path)
    with pytest.raises(ToolError, match="nie ma gotowej witryny"):
        wywolaj(harness, "site_from_template", site="proba", szablon="pusty")


def test_szablon_odrzuca_identyfikator_ze_sciezka(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Identyfikator idzie do ścieżki na dysku — wyjście z katalogu kolekcji jest odrzucane."""
    from nexus.tools import kit_www

    (tmp_path / "szablony").mkdir(parents=True)
    monkeypatch.setattr(kit_www, "KOLEKCJA", tmp_path)
    with pytest.raises(ToolError, match="Nieprawidłowy identyfikator"):
        wywolaj(harness, "site_from_template", site="proba", szablon="../../etc")


def test_szablon_z_gotowa_witryna_trafia_do_szkicu(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gotowa witryna idzie prosto do szkicu — bez budowania, z licencją w podsumowaniu."""
    from nexus.tools import kit_www

    witryna = tmp_path / "szablony" / "astro-blog" / "witryna"
    (witryna / "wpis").mkdir(parents=True)
    (witryna / "index.html").write_text("<!doctype html><title>Blog</title>", encoding="utf-8")
    (witryna / "wpis" / "index.html").write_text("<!doctype html><title>Wpis</title>", encoding="utf-8")
    (tmp_path / "szablony" / "astro-blog" / "meta.json").write_text(
        json.dumps({"id": "astro-blog", "nazwa": "Astro Blog", "licencja": "MIT"}), encoding="utf-8"
    )
    monkeypatch.setattr(kit_www, "KOLEKCJA", tmp_path)

    wynik = wywolaj(harness, "site_from_template", site="blog-ani", szablon="astro-blog")

    assert wynik.data["podstrony"] == 2
    assert wynik.data["licencja"] == "MIT"
    assert "MIT" in wynik.summary
    store = site_store(harness.settings)
    assert store.exists("blog-ani")
    assert "Blog" in store.read_text("blog-ani", "index.html")
    assert "Wpis" in store.read_text("blog-ani", "wpis/index.html")


def test_szablon_pomija_pliki_ktorych_szkic_nie_przyjmuje(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jeden plik spoza wykazu typów nie może wywalić całej witryny.

    Gotowe szablony miewają animacje Rive albo mapy źródeł; szkic strony ich nie przyjmuje.
    Wcześniej cała operacja kończyła się błędem i użytkownik nie dostawał nic.
    """
    from nexus.tools import kit_www

    witryna = tmp_path / "szablony" / "z-animacja" / "witryna"
    witryna.mkdir(parents=True)
    (witryna / "index.html").write_text("<!doctype html><title>Portfolio</title>", encoding="utf-8")
    (witryna / "ruch.riv").write_bytes(b"RIVE")
    monkeypatch.setattr(kit_www, "KOLEKCJA", tmp_path)

    wynik = wywolaj(harness, "site_from_template", site="portfolio", szablon="z-animacja")

    assert wynik.data["pliki"] == 1
    assert wynik.data["pominiete"] == 1
    assert wynik.data["pominiete_pliki"] == ["ruch.riv"]
    assert site_store(harness.settings).exists("portfolio")


def test_szablon_z_samymi_nieobslugiwanymi_plikami_mowi_wprost(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nexus.tools import kit_www

    witryna = tmp_path / "szablony" / "same-animacje" / "witryna"
    witryna.mkdir(parents=True)
    (witryna / "ruch.riv").write_bytes(b"RIVE")
    monkeypatch.setattr(kit_www, "KOLEKCJA", tmp_path)

    with pytest.raises(ToolError, match="Żaden plik witryny"):
        wywolaj(harness, "site_from_template", site="pusta", szablon="same-animacje")


def test_szablon_wiekszy_niz_strona_mowi_o_tym_przed_kopiowaniem(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Limit plików strony sprawdzamy przed wstawianiem, nie w połowie kopiowania."""
    from nexus.tools import kit_www

    witryna = tmp_path / "szablony" / "ogromny" / "witryna"
    witryna.mkdir(parents=True)
    (witryna / "index.html").write_text("<!doctype html>", encoding="utf-8")
    monkeypatch.setattr(kit_www, "KOLEKCJA", tmp_path)
    monkeypatch.setattr(kit_www, "MAX_FILES", 0)

    with pytest.raises(ToolError, match="a strona mieści"):
        wywolaj(harness, "site_from_template", site="proba", szablon="ogromny")


def test_uwagi_witryny_liczy_zasoby_a_nie_odsylacze(tmp_path: Path) -> None:
    """Uwaga ma dotyczyć wczytywanych zasobów; zwykły odsyłacz w treści nie jest usterką."""
    from nexus.tools.kit_www import _uwagi_witryny

    (tmp_path / "index.html").write_text(
        '<!doctype html><html><head>'
        '<link rel="stylesheet" href="https://cdn.example/styl.css">'
        '<link rel="stylesheet" href="/assets/styl.css">'
        "</head><body>"
        '<a href="https://astro.build">Astro</a>'
        '<a href="/o-nas">O nas</a>'
        '<img src="https://cdn.example/logo.png">'
        '<script src="/js/app.js"></script>'
        "</body></html>",
        encoding="utf-8",
    )

    uwagi = _uwagi_witryny(tmp_path)

    # Dwa zasoby z sieci (arkusz i obraz), nie trzy — odsyłacz w treści się nie liczy.
    # Ścieżek od korzenia domeny nie ma na liście uwag: te są naprawiane przy wstawianiu.
    assert len(uwagi) == 1
    assert "2 odwołań do zasobów z sieci" in uwagi[0]
    # Sama liczba nie mówi, co pobrać — nazwa serwera mówi.
    assert "cdn.example (2)" in uwagi[0]


def test_witryna_bez_zewnetrznych_zasobow_nie_ma_uwag(tmp_path: Path) -> None:
    from nexus.tools.kit_www import _uwagi_witryny

    (tmp_path / "index.html").write_text(
        '<!doctype html><link rel="stylesheet" href="styl.css"><img src="img/logo.png">',
        encoding="utf-8",
    )
    assert _uwagi_witryny(tmp_path) == []


def test_sciezki_od_korzenia_staja_sie_wzgledne(tmp_path: Path) -> None:
    """Strona stoi pod „/s/<adres>/”, więc „/assets/…” musi zamienić się na ścieżkę względną."""
    from nexus.tools.kit_www import _na_wzgledne

    strona = (
        '<link rel="stylesheet" href="/assets/styl.css">'
        '<script src="/js/app.js"></script>'
        '<img srcset="/img/a.png 1x, /img/a@2x.png 2x" src="/img/a.png">'
        '<a href="/o-nas/">O nas</a>'
        '<a href="https://astro.build">Astro</a>'
        '<img src="//cdn.example/logo.png">'
    )

    plytko, ile_plytko = _na_wzgledne(strona, 0, styl=False)
    gleboko, ile_gleboko = _na_wzgledne(strona, 2, styl=False)

    assert ile_plytko == ile_gleboko == 6
    assert 'href="./assets/styl.css"' in plytko
    assert 'srcset="./img/a.png 1x, ./img/a@2x.png 2x"' in plytko
    assert 'href="../../o-nas/"' in gleboko
    assert 'src="../../js/app.js"' in gleboko
    # Cudzy adres i adres z protokołem domyślnym zostają nietknięte.
    assert 'href="https://astro.build"' in gleboko
    assert 'src="//cdn.example/logo.png"' in gleboko


def test_arkusz_stylow_poprawia_tylko_url(tmp_path: Path) -> None:
    """W arkuszu stylów nie ma atrybutów HTML — poprawiamy wyłącznie ``url(…)``."""
    from nexus.tools.kit_www import _na_wzgledne

    arkusz = "a{background:url(/img/tlo.png)}b{background:url('/img/b.png')}c{src:url(../x.woff2)}"

    wynik, ile = _na_wzgledne(arkusz, 1, styl=True)

    assert ile == 2
    assert "url(../img/tlo.png)" in wynik
    assert "url('../img/b.png')" in wynik
    assert "url(../x.woff2)" in wynik


def test_szablon_z_ryzykownymi_sciezkami_wstawia_sie_naprawiony(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Szablon spod korzenia domeny ma po wstawieniu działające style i menu."""
    from nexus.tools import kit_www

    witryna = tmp_path / "szablony" / "landing" / "witryna"
    (witryna / "kontakt").mkdir(parents=True)
    (witryna / "assets").mkdir()
    (witryna / "index.html").write_text(
        '<link rel="stylesheet" href="/assets/styl.css"><a href="/kontakt/">Kontakt</a>',
        encoding="utf-8",
    )
    (witryna / "kontakt" / "index.html").write_text(
        '<link rel="stylesheet" href="/assets/styl.css">', encoding="utf-8"
    )
    (witryna / "assets" / "styl.css").write_text("body{background:url(/assets/tlo.png)}", encoding="utf-8")
    (tmp_path / "szablony" / "landing" / "meta.json").write_text(
        json.dumps({"id": "landing", "nazwa": "Landing", "licencja": "MIT"}), encoding="utf-8"
    )
    monkeypatch.setattr(kit_www, "KOLEKCJA", tmp_path)

    wynik = wywolaj(harness, "site_from_template", site="firma", szablon="landing")

    assert wynik.data["poprawione_sciezki"] == 4
    store = site_store(harness.settings)
    assert 'href="./assets/styl.css"' in store.read_text("firma", "index.html")
    assert 'href="./kontakt/"' in store.read_text("firma", "index.html")
    assert 'href="../assets/styl.css"' in store.read_text("firma", "kontakt/index.html")
    assert "url(../assets/tlo.png)" in store.read_text("firma", "assets/styl.css")


def test_spis_sekcji_podaje_nazwy_a_nie_same_rodziny(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sto kilkadziesiąt gotowych sekcji było bezimienne — agent nie mógł wskazać żadnej."""
    from nexus.tools import kit_www

    kit = tmp_path / "kit"
    for rodzina, nazwa, opis in (
        ("pricing", "calculator", "Kalkulator ceny z suwakami."),
        ("hero", "split", "Nagłówek z obrazem obok."),
    ):
        katalog = kit / "sections" / rodzina / nazwa
        katalog.mkdir(parents=True)
        (katalog / "Section.astro").write_text("---\n---\n<section />", encoding="utf-8")
        (katalog / "meta.json").write_text(
            json.dumps({"name": nazwa.title(), "description": opis, "tags": ["cennik"]}),
            encoding="utf-8",
        )
    # Katalog bez składnika obiecuje sekcję, której nie ma — nie wolno go podawać.
    (kit / "sections" / "forms" / "booking").mkdir(parents=True)
    monkeypatch.setattr(kit_www, "KIT", kit)
    monkeypatch.setattr(kit_www, "KOLEKCJA", tmp_path / "kolekcja")

    wszystkie = wywolaj(harness, "site_kit_catalog")
    zawezone = wywolaj(harness, "site_kit_catalog", szukaj_sekcji="obrazem")

    assert [s["id"] for s in wszystkie.data["sekcje"]] == ["hero/split", "pricing/calculator"]
    assert [s["id"] for s in zawezone.data["sekcje"]] == ["hero/split"]
    assert "forms" in wszystkie.data["rodzaje_sekcji"], "rodzina zostaje w spisie rodzin"


def test_spis_sekcji_szanuje_limit(
    harness: ToolHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nexus.tools import kit_www

    kit = tmp_path / "kit"
    for numer in range(5):
        katalog = kit / "sections" / "hero" / f"wariant-{numer}"
        katalog.mkdir(parents=True)
        (katalog / "Section.astro").write_text("<section />", encoding="utf-8")
    monkeypatch.setattr(kit_www, "KIT", kit)
    monkeypatch.setattr(kit_www, "KOLEKCJA", tmp_path / "kolekcja")

    wynik = wywolaj(harness, "site_kit_catalog", limit_sekcji=2)

    assert len(wynik.data["sekcje"]) == 2
    assert wynik.data["liczba_sekcji"] == 5, "licznik ma mówić, ile jest naprawdę"


def test_odsylacz_do_podstrony_dostaje_kreske(tmp_path: Path) -> None:
    """Bez kreski przeglądarka liczy ścieżki względne od katalogu wyżej i gubi style."""
    from nexus.tools.kit_www import _na_wzgledne

    strona = (
        '<a href="/cennik">Cennik</a>'
        '<a href="/blog/wpis?utm=x">Wpis</a>'
        '<a href="/kontakt#formularz">Kontakt</a>'
        '<a href="/o-nas/">O nas</a>'
        '<link rel="stylesheet" href="/assets/styl.css">'
        '<img src="/img/logo.svg">'
    )

    wynik, ile = _na_wzgledne(strona, 0, styl=False)

    assert ile == 6
    assert 'href="./cennik/"' in wynik
    assert 'href="./blog/wpis/?utm=x"' in wynik
    assert 'href="./kontakt/#formularz"' in wynik
    assert 'href="./o-nas/"' in wynik, "kreska już była — nie dokładamy drugiej"
    # Pliki poznajemy po rozszerzeniu: im kreska by zaszkodziła.
    assert 'href="./assets/styl.css"' in wynik
    assert 'src="./img/logo.svg"' in wynik


def test_kroje_z_google_dostaja_osobna_uwage(tmp_path: Path) -> None:
    """Hotlink do Google Fonts to nie tylko wygląd — to wysyłka adresu IP odwiedzającego."""
    from nexus.tools.kit_www import _uwagi_witryny

    (tmp_path / "index.html").write_text(
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">'
        '<link rel="preconnect" href="https://fonts.gstatic.com">',
        encoding="utf-8",
    )

    uwagi = _uwagi_witryny(tmp_path)

    assert len(uwagi) == 2
    assert "adres IP odwiedzającego" in uwagi[1]
    assert "site_fonts_local" in uwagi[1]


def test_witryna_z_cdn_bez_krojow_ma_jedna_uwage(tmp_path: Path) -> None:
    """Uwaga o krojach należy się tylko wtedy, gdy kroje faktycznie idą z Google."""
    from nexus.tools.kit_www import _uwagi_witryny

    (tmp_path / "index.html").write_text(
        '<script src="https://cdn.jsdelivr.net/npm/alpine.js"></script>', encoding="utf-8"
    )

    assert len(_uwagi_witryny(tmp_path)) == 1


def test_adresy_w_skryptach_sa_zgloszone_a_nie_przepisane(tmp_path: Path) -> None:
    """W JavaScripcie „/login” bywa adresem, kluczem albo tekstem — automat by je pomylił."""
    from nexus.tools.kit_www import _uwagi_witryny

    (tmp_path / "index.html").write_text("<p>bez zasobów z sieci</p>", encoding="utf-8")
    (tmp_path / "panel.js").write_text(
        'if (!zalogowany) location.href = "/login";\nconst api = "/api/dane";\nconst x = "/ab";',
        encoding="utf-8",
    )

    uwagi = _uwagi_witryny(tmp_path)

    assert len(uwagi) == 1
    # „/ab” jest za krótkie, żeby uznać je za ścieżkę — liczymy dwa adresy, nie trzy.
    assert "2 adresów liczonych od korzenia" in uwagi[0]
    assert "site_write_file" in uwagi[0]


def test_cudzy_adres_kanoniczny_jest_zglaszany(tmp_path: Path) -> None:
    """Zostawiony `canonical` autora mówi wyszukiwarce, że strona użytkownika jest kopią."""
    from nexus.tools.kit_www import _uwagi_witryny

    (tmp_path / "index.html").write_text(
        '<link rel="canonical" href="https://dashboard.autor.dev/">'
        '<meta property="og:url" content="https://dashboard.autor.dev/">',
        encoding="utf-8",
    )
    (tmp_path / "cennik.html").write_text(
        '<link rel="canonical" href="https://dashboard.autor.dev/cennik">', encoding="utf-8"
    )

    uwagi = _uwagi_witryny(tmp_path)

    assert len(uwagi) == 1
    assert "dashboard.autor.dev (3)" in uwagi[0]
    assert "canonical" in uwagi[0]


def test_canonical_nie_liczy_sie_jako_zasob_z_sieci(tmp_path: Path) -> None:
    """`rel="canonical"` niczego nie pobiera — liczony jako zasób mieszał dwie różne sprawy."""
    from nexus.tools.kit_www import _uwagi_witryny

    (tmp_path / "index.html").write_text(
        '<link rel="canonical" href="https://autor.dev/">'
        '<link rel="alternate" hreflang="en" href="https://autor.dev/en/">'
        '<link rel="stylesheet" href="https://cdn.example/styl.css">'
        '<link rel="preconnect" href="https://cdn.example">',
        encoding="utf-8",
    )

    uwagi = _uwagi_witryny(tmp_path)

    # Dwie uwagi: zasoby z sieci (arkusz + preconnect) oraz cudzy adres kanoniczny.
    assert len(uwagi) == 2
    assert "2 odwołań do zasobów z sieci" in uwagi[0]
    assert "cdn.example (2)" in uwagi[0]
    assert "autor.dev" in uwagi[1]
