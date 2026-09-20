"""Narzędzia składu, konwersji, rozbioru dokumentu, napisów i czytania na głos.

Skład Typstem jest na tyle szybki, że dwa przypadki uruchamiają prawdziwy program:
powstanie PDF-u i to, że treść od modelu nigdy nie staje się kodem składu. Docling,
WhisperX i synteza mowy liczą na procesorze minutami, więc tam sprawdzamy to, co i tak
decyduje o poprawności: obecność w rejestrze, odrzucenie pliku niewłaściwego rodzaju,
komunikat przy braku programu i złożenie polecenia z wyborów użytkownika.
"""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest
from conftest import ToolHarness, requires_program

from nexus.tools.base import ToolError, registry

NARZEDZIA = (
    "typeset_document",
    "convert_text_format",
    "analyze_document_structure",
    "transcribe_speakers",
    "edit_subtitles",
    "read_document_aloud",
)

RAPORT = {
    "szablon": "raport",
    "tytul": "Raport z przeglądu technicznego",
    "podtytul": "Hala produkcyjna nr 3",
    "autor": "Danaco Group sp. z o.o.",
    "data": "20 września 2026",
    "stopka": "Dokument poufny",
    "sekcje": [
        {
            "naglowek": "Podsumowanie",
            "bloki": [
                {"rodzaj": "akapit", "tekst": "Przegląd wykazał **dwie usterki** wymagające naprawy."},
                {"rodzaj": "lista", "punkty": ["Nieszczelny zawór.", "Zużyte filtry."]},
                {
                    "rodzaj": "tabela",
                    "naglowki": ["Pozycja", "Kwota"],
                    "wiersze": [["Przegląd instalacji", "2 400,00 zł"]],
                },
                {"rodzaj": "dane", "pary": [{"etykieta": "Obiekt", "wartosc": "Hala nr 3"}]},
            ],
        }
    ],
}


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object):  # type: ignore[no-untyped-def]
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


def tekst_pdf(sciezka: Path) -> str:
    with pymupdf.open(sciezka) as dokument:
        return "\n".join(strona.get_text("text") for strona in dokument)


def test_narzedzia_sa_w_rejestrze() -> None:
    assert set(NARZEDZIA) <= set(registry.names())


# --- skład Typst ---------------------------------------------------------------------------


@requires_program("typst")
def test_sklad_daje_pdf_z_trescia_i_podgladem(harness: ToolHarness) -> None:
    wynik = wywolaj(harness, "typeset_document", **RAPORT, nazwa="raport")
    assert wynik.data["stron"] == 1
    assert wynik.images
    plik = wynik.files[0]
    assert plik.path.is_file() and plik.name.endswith(".pdf")
    tresc = tekst_pdf(plik.path)
    assert "Raport z przeglądu technicznego" in tresc
    # Wyróżnienie nie może sklejać słów: „wykazał **dwie usterki** wymagające”.
    assert "wykazał dwie usterki wymagające" in tresc
    assert "2 400,00 zł" in tresc
    assert "Dokument poufny" in tresc


@requires_program("typst")
@pytest.mark.parametrize("szablon", ["raport", "oferta", "cv", "broszura", "plakat"])
def test_kazdy_szablon_sie_sklada(harness: ToolHarness, szablon: str) -> None:
    dane = {
        **RAPORT,
        "szablon": szablon,
        "kontakt": [{"etykieta": "Telefon", "wartosc": "+48 22 000 00 00"}],
        "nazwa": szablon,
    }
    wynik = wywolaj(harness, "typeset_document", **dane)
    assert wynik.data["szablon"] == szablon
    assert wynik.data["stron"] >= 1


@requires_program("typst")
def test_tresc_od_modelu_nie_wykonuje_sie_jako_kod(harness: ToolHarness) -> None:
    """Wstawka Typsta podana w treści ma zostać wydrukowana, a nie uruchomiona."""
    zlosliwa = '#read("/etc/passwd") oraz #eval("1+1") i cudzysłów " w treści'
    dane = {
        "szablon": "raport",
        "tytul": 'Próba #read("/etc/passwd")',
        "sekcje": [{"naglowek": "Treść", "bloki": [{"rodzaj": "akapit", "tekst": zlosliwa}]}],
        "nazwa": "proba",
    }
    wynik = wywolaj(harness, "typeset_document", **dane)
    tresc = tekst_pdf(wynik.files[0].path)
    assert '#read("/etc/passwd")' in tresc
    assert "root:" not in tresc


def test_sklad_odrzuca_bledna_barwe(harness: ToolHarness) -> None:
    with pytest.raises(ToolError, match="#RRGGBB"):
        wywolaj(harness, "typeset_document", **RAPORT, kolor="#ZZ1122")


def test_sklad_odrzuca_tabele_o_nierownych_wierszach(harness: ToolHarness) -> None:
    dane = {
        "szablon": "raport",
        "tytul": "Tabela",
        "sekcje": [
            {
                "naglowek": "Zestawienie",
                "bloki": [
                    {
                        "rodzaj": "tabela",
                        "naglowki": ["Pozycja", "Kwota"],
                        "wiersze": [["Przegląd", "100 zł"], ["Braki"]],
                    }
                ],
            }
        ],
    }
    with pytest.raises(ToolError, match="komórek"):
        wywolaj(harness, "typeset_document", **dane)


def test_brak_programu_mowi_po_ludzku(harness: ToolHarness, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Gdy programu nie ma, użytkownik dostaje zdanie, a nie ślad wykonania."""
    monkeypatch.setattr("nexus.tools.dokumenty_zaawansowane.shutil.which", lambda _nazwa: None)
    with pytest.raises(ToolError, match="niedostępne na tym serwerze"):
        wywolaj(harness, "typeset_document", **RAPORT)


# --- konwersje pandoc ----------------------------------------------------------------------


def _bez_programow(monkeypatch, zapis: list[list[str]], wynik: bytes = b"wynik") -> None:  # type: ignore[no-untyped-def]
    """Podmienia wyszukiwanie programów i ich uruchomienie; zapisuje złożone polecenia."""

    def udawany_bieg(self, arguments, timeout=600, cwd=None, env=None):  # type: ignore[no-untyped-def]
        zapis.append(list(arguments))
        if "--output" in arguments:
            Path(arguments[arguments.index("--output") + 1]).write_bytes(wynik)
        return None

    monkeypatch.setattr("nexus.tools.dokumenty_zaawansowane.shutil.which", lambda nazwa: f"/udawane/{nazwa}")
    monkeypatch.setattr("nexus.tools.base.ToolContext.run_command", udawany_bieg)


def test_konwersja_sklada_polecenie_pandoca(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    zrodlo = tmp_path / "ksiazka.md"
    zrodlo.write_text("# Rozdział\n\nTreść.\n", encoding="utf-8")
    zapis: list[list[str]] = []
    _bez_programow(monkeypatch, zapis)
    wywolaj(
        harness,
        "convert_text_format",
        file_id=harness.add(zrodlo),
        format_docelowy="epub",
        tytul="Książka",
        autor="Danaco",
        spis_tresci=True,
    )
    polecenie = zapis[0]
    assert polecenie[0].endswith("pandoc")
    assert "--sandbox" in polecenie
    assert polecenie[polecenie.index("--from") + 1] == "markdown-raw_attribute"
    assert polecenie[polecenie.index("--to") + 1] == "epub3"
    assert "--toc" in polecenie and "--standalone" in polecenie
    assert "title=Książka" in polecenie and "author=Danaco" in polecenie


def test_konwersja_do_pdf_wylacza_wstawki_surowego_kodu(
    harness: ToolHarness, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    """Przy formatach, które się składają, surowy kod z Markdownu nie może przejść dalej."""
    zrodlo = tmp_path / "tekst.md"
    zrodlo.write_text("Treść.\n", encoding="utf-8")
    zapis: list[list[str]] = []
    _bez_programow(monkeypatch, zapis)
    wywolaj(harness, "convert_text_format", file_id=harness.add(zrodlo), format_docelowy="pdf")
    polecenie = zapis[0]
    assert polecenie[polecenie.index("--from") + 1] == "markdown-raw_attribute-raw_tex"
    assert "--pdf-engine=typst" in polecenie


def test_konwersja_odmawia_nieczytelnego_zrodla(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    nagranie = tmp_path / "rozmowa.mp3"
    nagranie.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")
    _bez_programow(monkeypatch, [])
    with pytest.raises(ToolError, match="nie czyta tego rodzaju pliku"):
        wywolaj(harness, "convert_text_format", file_id=harness.add(nagranie), format_docelowy="markdown")


def test_konwersja_wymaga_zrodla(harness: ToolHarness, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _bez_programow(monkeypatch, [])
    with pytest.raises(ToolError, match="file_id albo tekst"):
        wywolaj(harness, "convert_text_format", format_docelowy="epub")


# --- rozbiór struktury dokumentu ---------------------------------------------------------------


def test_rozbior_odrzuca_nagranie(harness: ToolHarness, tmp_path: Path) -> None:
    nagranie = tmp_path / "rozmowa.mp3"
    nagranie.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")
    with pytest.raises(ToolError, match="nie jest dokumentem"):
        wywolaj(harness, "analyze_document_structure", file_id=harness.add(nagranie))


def test_rozbior_sklada_polecenie_z_wyborami_uzytkownika(
    harness: ToolHarness, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    dokument = tmp_path / "umowa.pdf"
    dokument.write_bytes(b"%PDF-1.4\n")
    zapis: list[list[str]] = []

    def udawany_bieg(self, arguments, timeout=600, cwd=None, env=None):  # type: ignore[no-untyped-def]
        zapis.append(list(arguments))
        zrodlo = Path(arguments[-1])
        zrodlo.with_suffix(".md").write_text("# Umowa\n\nTreść umowy.\n", encoding="utf-8")
        zrodlo.with_suffix(".json").write_text(
            json.dumps({"tables": [{}, {}], "pages": {"1": {}}}), encoding="utf-8"
        )
        return None

    monkeypatch.setattr("nexus.tools.dokumenty_zaawansowane.shutil.which", lambda nazwa: f"/udawane/{nazwa}")
    monkeypatch.setattr("nexus.tools.base.ToolContext.run_command", udawany_bieg)
    wynik = wywolaj(
        harness,
        "analyze_document_structure",
        file_id=harness.add(dokument),
        ocr="wymus",
        tabele="szybko",
        jezyk="pl,en",
    )
    polecenie = zapis[0]
    assert polecenie[0].endswith("danaco-dokument-na-tekst")
    assert "--ocr" in polecenie and "--tabele-szybko" in polecenie
    assert polecenie[polecenie.index("--jezyk") + 1] == "pl,en"
    assert wynik.data["tabel"] == 2
    assert wynik.data["naglowki"] == ["# Umowa"]
    assert len(wynik.files) == 2


def test_rozbior_odrzuca_dziwny_zapis_jezyka(harness: ToolHarness, tmp_path: Path) -> None:
    dokument = tmp_path / "umowa.pdf"
    dokument.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(ToolError, match="zapis języków OCR"):
        wywolaj(harness, "analyze_document_structure", file_id=harness.add(dokument), jezyk="polski")


# --- transkrypcja z mówcami --------------------------------------------------------------------


def test_podzial_na_mowcow_bez_modelu_mowi_co_zrobic(
    harness: ToolHarness, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    nagranie = tmp_path / "spotkanie.mp3"
    nagranie.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")
    monkeypatch.setattr("nexus.tools.dokumenty_zaawansowane.shutil.which", lambda nazwa: f"/udawane/{nazwa}")
    monkeypatch.setattr("nexus.tools.dokumenty_zaawansowane.ZNACZNIK_MOWCOW", tmp_path / "brak")
    with pytest.raises(ToolError, match="nie jest jeszcze przygotowany"):
        wywolaj(harness, "transcribe_speakers", file_id=harness.add(nagranie), mowcy=True)


def test_transkrypcja_odrzuca_dokument(harness: ToolHarness, tmp_path: Path) -> None:
    notatka = tmp_path / "notatka.txt"
    notatka.write_text("to nie jest nagranie", encoding="utf-8")
    with pytest.raises(ToolError, match="nie jest nagraniem"):
        wywolaj(harness, "transcribe_speakers", file_id=harness.add(notatka), mowcy=False)


def test_transkrypcja_sklada_polecenie_i_czyta_mowcow(
    harness: ToolHarness, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    nagranie = tmp_path / "spotkanie.mp3"
    nagranie.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")
    znacznik = tmp_path / "GOTOWE"
    znacznik.write_text("model", encoding="utf-8")
    zapis: list[list[str]] = []

    def udawany_bieg(self, arguments, timeout=600, cwd=None, env=None):  # type: ignore[no-untyped-def]
        zapis.append(list(arguments))
        zrodlo = Path(arguments[1])
        zrodlo.with_suffix(".json").write_text(
            json.dumps(
                {
                    "jezyk": "pl",
                    "czas_nagrania_s": 120.0,
                    "wyrownanie_slow": True,
                    "segmenty": [
                        {"start": 0.0, "end": 2.0, "text": "Dzień dobry.", "speaker": "SPEAKER_00"},
                        {"start": 2.0, "end": 4.0, "text": "Witam.", "speaker": "SPEAKER_01"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        zrodlo.with_suffix(".txt").write_text("SPEAKER_00: Dzień dobry.\n", encoding="utf-8")
        zrodlo.with_suffix(".srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nDzień dobry.\n", "utf-8")
        return None

    monkeypatch.setattr("nexus.tools.dokumenty_zaawansowane.shutil.which", lambda nazwa: f"/udawane/{nazwa}")
    monkeypatch.setattr("nexus.tools.dokumenty_zaawansowane.ZNACZNIK_MOWCOW", znacznik)
    monkeypatch.setattr("nexus.tools.base.ToolContext.run_command", udawany_bieg)
    wynik = wywolaj(
        harness,
        "transcribe_speakers",
        file_id=harness.add(nagranie),
        mowcy=True,
        liczba_mowcow=2,
        model="medium",
        formaty=["txt", "srt"],
    )
    polecenie = zapis[0]
    assert polecenie[0].endswith("danaco-transkrypcja")
    assert "--mowcy" in polecenie
    assert polecenie[polecenie.index("--model") + 1] == "medium"
    assert polecenie[polecenie.index("--liczba-mowcow") + 1] == "2"
    assert wynik.data["mowcy"] == ["SPEAKER_00", "SPEAKER_01"]
    assert wynik.data["segmentow"] == 2
    assert [plik.name for plik in wynik.files] == ["spotkanie_rozmowa.txt", "spotkanie_rozmowa.srt"]


# --- napisy ------------------------------------------------------------------------------------

NAPISY = "1\n00:00:01,000 --> 00:00:03,000\nDzień dobry.\n\n2\n00:00:04,000 --> 00:00:06,000\nWitam.\n"


@requires_program("srt")
def test_przesuniecie_napisow_zmienia_czasy(harness: ToolHarness, tmp_path: Path) -> None:
    napisy = tmp_path / "film.srt"
    napisy.write_text(NAPISY, encoding="utf-8")
    wynik = wywolaj(harness, "edit_subtitles", file_id=harness.add(napisy), operacja="przesun", sekundy=-0.5)
    assert wynik.data["kwestii"] == 2
    assert "00:00:00,500 --> 00:00:02,500" in wynik.files[0].path.read_text(encoding="utf-8")


def test_napisy_odrzucaja_inny_plik(harness: ToolHarness, tmp_path: Path) -> None:
    notatka = tmp_path / "notatka.txt"
    notatka.write_text("nie napisy", encoding="utf-8")
    with pytest.raises(ToolError, match="nie jest plikiem napisów"):
        wywolaj(harness, "edit_subtitles", file_id=harness.add(notatka), operacja="uporzadkuj")


def test_napisy_pilnuja_kompletu_danych(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    napisy = tmp_path / "film.srt"
    napisy.write_text(NAPISY, encoding="utf-8")
    _bez_programow(monkeypatch, [])
    file_id = harness.add(napisy)
    with pytest.raises(ToolError, match="o ile sekund"):
        wywolaj(harness, "edit_subtitles", file_id=file_id, operacja="przesun")
    with pytest.raises(ToolError, match="drugiego pliku napisów"):
        wywolaj(harness, "edit_subtitles", file_id=file_id, operacja="scal")
    with pytest.raises(ToolError, match="czasem"):
        wywolaj(
            harness,
            "edit_subtitles",
            file_id=file_id,
            operacja="dopasuj",
            od_pierwszy="na początku",
            na_pierwszy="00:00:02,000",
            od_ostatni="00:00:06,000",
            na_ostatni="00:00:08,000",
        )


# --- czytanie na głos ----------------------------------------------------------------------------


def test_czytanie_bez_glosu_mowi_po_ludzku(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    notatka = tmp_path / "notatka.txt"
    notatka.write_text("Dzień dobry. To jest próba czytania.", encoding="utf-8")
    monkeypatch.setattr("nexus.voice.VoiceEngine.local_voices", lambda self: [])
    with pytest.raises(ToolError, match="nie ma zainstalowanego głosu"):
        wywolaj(harness, "read_document_aloud", file_id=harness.add(notatka))


def test_czytanie_laczy_porcje_w_jedno_nagranie(harness: ToolHarness, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Długi tekst jest czytany po kawałku, a wynikiem ma być jeden plik dźwiękowy."""
    import io
    import wave

    def udawana_synteza(self, text, voice_id="", speed=1.0):  # type: ignore[no-untyped-def]
        bufor = io.BytesIO()
        with wave.open(bufor, "wb") as zapis:
            zapis.setnchannels(1)
            zapis.setsampwidth(2)
            zapis.setframerate(22050)
            zapis.writeframes(b"\x00\x00" * 22050)
        return bufor.getvalue(), "audio/wav"

    monkeypatch.setattr(
        "nexus.voice.VoiceEngine.local_voices", lambda self: [{"id": "pl_PL-test", "name": "Próbny"}]
    )
    monkeypatch.setattr("nexus.voice.VoiceEngine.speak", udawana_synteza)
    notatka = tmp_path / "raport.txt"
    notatka.write_text("Zdanie próbne. " * 300, encoding="utf-8")
    wynik = wywolaj(harness, "read_document_aloud", file_id=harness.add(notatka), format_wyniku="wav")
    assert wynik.data["glos"] == "pl_PL-test"
    assert wynik.data["czas_s"] > 1
    assert wynik.files[0].path.suffix == ".wav"


def test_czytanie_odrzuca_obraz(harness: ToolHarness, tmp_path: Path) -> None:
    from PIL import Image

    zdjecie = tmp_path / "skan.png"
    Image.new("RGB", (8, 8), (20, 20, 20)).save(zdjecie)
    with pytest.raises(ToolError, match="nie jest dokumentem tekstowym"):
        wywolaj(harness, "read_document_aloud", file_id=harness.add(zdjecie))
