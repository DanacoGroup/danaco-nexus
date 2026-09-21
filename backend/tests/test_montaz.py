"""Montaż filmu z ujęć (``video_compose``).

FFmpeg jest uruchamiany naprawdę tylko w jednym teście — składanie kilku ujęć w 1080p trwa
kilkanaście sekund, więc reszta sprawdza to, co decyduje o poprawności: złożenie filtru,
długość filmu po przenikaniu, odrzucenie pliku niewłaściwego rodzaju i wybór podkładu
z biblioteki serwera.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import ToolHarness
from PIL import Image

from nexus.tools import montaz
from nexus.tools.base import ToolError, registry


def wywolaj(harness: ToolHarness, nazwa: str, /, **argumenty: object):  # type: ignore[no-untyped-def]
    narzedzie = registry.get(nazwa)
    return narzedzie.handler(harness.context(), narzedzie.parse(argumenty))


def zdjecie(katalog: Path, nazwa: str, barwa: tuple[int, int, int] = (40, 60, 120)) -> Path:
    plik = katalog / nazwa
    Image.new("RGB", (1200, 900), barwa).save(plik, quality=85)
    return plik


def test_narzedzie_jest_w_rejestrze() -> None:
    assert registry.get("video_compose").name == "video_compose"


def test_film_powstaje_z_trzech_zdjec_z_napisami(harness: ToolHarness, tmp_path: Path) -> None:
    """Pełny przebieg: trzy ujęcia, napisy z polskimi znakami, przenikanie, podkład z biblioteki."""
    if not montaz.MEDIA.is_dir():
        pytest.skip("biblioteka materiałów nie jest zainstalowana")
    podklad = next(
        (p for p in (montaz.MEDIA / "muzyka").rglob("*.mp3") if p.is_file()),
        None,
    )
    if podklad is None:
        pytest.skip("biblioteka nie ma podkładu muzycznego")

    ujecia = [
        {
            "file_id": harness.add(zdjecie(tmp_path, f"{i}.jpg", (30 + i * 60, 40, 90))),
            "sekundy": 1.5,
            "napis": 'Zażółć gęślą jaźń "i" apostrof \'w\' napisie',
            "ruch": ruch,
        }
        for i, ruch in enumerate(("najazd", "w-lewo", "odjazd"))
    ]

    wynik = wywolaj(
        harness,
        "video_compose",
        ujecia=ujecia,
        kadr="9:16",
        tytul="Danaco Nexus",
        muzyka=str(podklad.relative_to(montaz.MEDIA)),
        nazwa_pliku="promo",
    )

    plik = wynik.files[0].path
    assert plik.is_file() and plik.stat().st_size > 0
    assert wynik.data["rozdzielczosc"] == "1080x1920"
    # Trzy ujęcia po 1,5 s minus dwa przenikania po 0,6 s.
    assert wynik.data["dlugosc_s"] == pytest.approx(3.3, abs=0.2)
    assert wynik.images, "film powinien wrócić z klatką podglądu"
    opis = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv", str(plik)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "video" in opis and "audio" in opis


def test_ujecie_z_pliku_ktory_nie_jest_obrazem_odpada(harness: ToolHarness, tmp_path: Path) -> None:
    dokument = tmp_path / "umowa.pdf"
    dokument.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(ToolError, match="nie jest zdjęciem ani filmem"):
        wywolaj(
            harness,
            "video_compose",
            ujecia=[{"file_id": harness.add(dokument), "sekundy": 2.0}],
        )


def test_podklad_spoza_biblioteki_nie_wychodzi_poza_katalog(harness: ToolHarness, tmp_path: Path) -> None:
    """„..” w ścieżce podkładu nie może wyprowadzić poza bibliotekę serwera."""
    with pytest.raises(ToolError):
        montaz._podklad(harness.context(), "../../../etc/passwd")


def test_podklad_z_rozmowy_musi_byc_dzwiekiem(harness: ToolHarness, tmp_path: Path) -> None:
    obraz = zdjecie(tmp_path, "tlo.jpg")

    with pytest.raises(ToolError, match="nie jest plikiem dźwiękowym"):
        montaz._podklad(harness.context(), harness.add(obraz))


def test_napis_z_dlugim_tekstem_lamie_sie_na_wiersze(tmp_path: Path) -> None:
    """Długi napis ma się zmieścić w kadrze, a nie uciec poza jego krawędź."""
    cel = tmp_path / "napis.png"
    montaz._nakladka(
        "Bardzo długi napis reklamowy, który sam z siebie nie zmieści się w jednym wierszu kadru",
        1920,
        1080,
        cel,
        duzy=False,
    )

    with Image.open(cel) as obraz:
        assert obraz.size == (1920, 1080)
        assert obraz.mode == "RGBA"
        # Tekst stoi w dolnej części kadru; górne pasmo zostaje przezroczyste.
        assert obraz.crop((0, 0, 1920, 300)).getbbox() is None


def test_filtr_zdjecia_ma_ruch_kamery_a_filmu_nie() -> None:
    """Zdjęcie ożywia zoompan; klip wideo idzie prosto do kadru, bez sztucznego ruchu."""
    zdj = montaz._filtr_ujecia(0, obraz=True, klatki=90, ruch="najazd", szer=1920, wys=1080)
    klip = montaz._filtr_ujecia(1, obraz=False, klatki=90, ruch="najazd", szer=1920, wys=1080)

    assert "zoompan" in zdj and "d=90" in zdj and "s=1920x1080" in zdj
    assert "zoompan" not in klip and "fps=30" in klip


def test_przenikanie_nie_zjada_calego_ujecia() -> None:
    """Przy krótkich ujęciach przenikanie skraca się samo — inaczej FFmpeg przerywa montaż."""
    assert montaz._przenikanie([4.0, 5.0, 3.0]) == montaz.PRZENIKANIE
    assert montaz._przenikanie([0.5, 4.0]) == pytest.approx(0.3)
    assert montaz._przenikanie([0.15, 4.0]) == pytest.approx(0.1)
    # Jedno ujęcie: nie ma czego przenikać, wartość nie ma znaczenia dla wyniku.
    assert montaz._przenikanie([2.0]) == montaz.PRZENIKANIE


def test_wlasne_przejscie_serwera_idzie_jako_wyrazenie(harness: ToolHarness, tmp_path: Path) -> None:
    """21 własnych przejść z biblioteki ma być dostępne tak samo jak wbudowane w FFmpeg."""
    if not montaz.PRZEJSCIA_WLASNE.is_file():
        pytest.skip("biblioteka przejść nie jest zainstalowana")
    wlasne = montaz._przejscia_wlasne()
    assert "zegar" in wlasne and len(wlasne) >= 20

    rodzaj = montaz._rodzaj_przejscia("zegar")

    # Apostrofy są obowiązkowe: wyrażenie ma w środku przecinki, które FFmpeg wziąłby
    # za koniec filtru.
    assert rodzaj.startswith("transition=custom:expr='") and rodzaj.endswith("'")
    assert montaz._rodzaj_przejscia("dissolve") == "transition=dissolve"


def test_nieznane_przejscie_mowi_czym_zastapic() -> None:
    with pytest.raises(ToolError, match="Nie znam przejścia"):
        montaz._rodzaj_przejscia("tęcza")


def test_film_z_wlasnym_przejsciem_faktycznie_powstaje(harness: ToolHarness, tmp_path: Path) -> None:
    """Sprawdzenie na prawdziwym FFmpeg — samo złożenie napisu niczego by nie dowiodło."""
    if not montaz.PRZEJSCIA_WLASNE.is_file():
        pytest.skip("biblioteka przejść nie jest zainstalowana")

    wynik = wywolaj(
        harness,
        "video_compose",
        ujecia=[
            {"file_id": harness.add(zdjecie(tmp_path, "a.jpg", (30, 40, 90))), "sekundy": 1.3},
            {"file_id": harness.add(zdjecie(tmp_path, "b.jpg", (190, 80, 40))), "sekundy": 1.3},
        ],
        kadr="1:1",
        przejscie="zegar",
        nazwa_pliku="zegarek",
    )

    assert wynik.files[0].path.is_file()
    assert wynik.data["przejscie"] == "zegar"


def test_przyciemnienie_pod_napisem_zalezy_od_zdjecia(tmp_path: Path) -> None:
    """Na ciemnym kadrze pas ma tylko musnąć, na jasnym – wyraźnie przyciemnić."""
    ciemne = tmp_path / "ciemne.jpg"
    Image.new("RGB", (1200, 900), (12, 14, 24)).save(ciemne)
    jasne = tmp_path / "jasne.jpg"
    Image.new("RGB", (1200, 900), (240, 242, 245)).save(jasne)

    def krycie(zrodlo: Path) -> int:
        cel = tmp_path / f"{zrodlo.stem}.png"
        montaz._nakladka("Napis na kadrze", 1920, 1080, cel, duzy=False, zrodlo=zrodlo)
        with Image.open(cel) as nakladka:
            # Przy lewej krawędzi kadru nie ma liter (margines 7%), więc mierzymy samo
            # przyciemnienie; najgęstsze jest tuż nad dolną krawędzią pasa.
            return max(px[3] for px in nakladka.crop((0, 990, 60, 1018)).get_flattened_data())

    assert krycie(ciemne) < krycie(jasne)
    assert krycie(ciemne) <= 45
    assert krycie(jasne) >= 150


def test_bez_zdjecia_przyciemnienie_wraca_do_wartosci_bezpiecznej(tmp_path: Path) -> None:
    """Ujęcie z klipu wideo nie da się zmierzyć – wtedy pas ma być na tyle mocny, by napis czytać."""
    assert montaz._jasnosc_pasa(None, 1920, 1080, 800, 1000) is None


def test_klip_krotszy_niz_ujecie_nie_urywa_filmu(harness: ToolHarness, tmp_path: Path) -> None:
    """Użytkownik wrzuca sekundowy klip i prosi o trzy sekundy — ostatnia klatka ma poczekać."""
    klip = tmp_path / "krotki.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=size=320x240:rate=25:duration=1", "-pix_fmt", "yuv420p", str(klip)],
        check=True,
        timeout=60,
    )

    wynik = wywolaj(
        harness,
        "video_compose",
        ujecia=[
            {"file_id": harness.add(klip), "sekundy": 3.0, "napis": "Klip"},
            {"file_id": harness.add(zdjecie(tmp_path, "b.jpg")), "sekundy": 2.0},
        ],
        kadr="1:1",
        nazwa_pliku="krotki-klip",
    )

    dlugosc = float(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(wynik.files[0].path)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )

    # 3 s + 2 s minus jedno przenikanie 0,6 s.
    assert dlugosc == pytest.approx(4.4, abs=0.25)


def test_zla_sciezka_podkladu_mowi_gdzie_szukac(harness: ToolHarness) -> None:
    """Pomyłka o jeden katalog nie może wracać jako „nieprawidłowy identyfikator pliku”."""
    with pytest.raises(ToolError, match="asset_library"):
        montaz._podklad(harness.context(), "muzyka/nie-ma-takiego/utwor.mp3")


def test_lektor_czyta_zdania_ujec_i_slychac_go_nad_muzyka(harness: ToolHarness, tmp_path: Path) -> None:
    """Dowód przez rozpoznanie mowy: to, co lektor przeczytał, wraca z gotowego filmu."""
    from nexus.config import Settings
    from nexus.voice import VoiceEngine

    if not VoiceEngine(Settings()).local_voices():
        pytest.skip("głosy Piper nie są zainstalowane")
    podklad = next((p for p in (montaz.MEDIA / "muzyka").rglob("*.mp3") if p.is_file()), None)
    if podklad is None:
        pytest.skip("biblioteka nie ma podkładu muzycznego")

    wynik = wywolaj(
        harness,
        "video_compose",
        ujecia=[
            {
                "file_id": harness.add(zdjecie(tmp_path, "a.jpg")),
                "sekundy": 4.0,
                "lektor": "Robimy meble na wymiar.",
            },
            {
                "file_id": harness.add(zdjecie(tmp_path, "b.jpg", (150, 60, 40))),
                "sekundy": 4.0,
                "lektor": "Zadzwoń i umów się na pomiar.",
            },
        ],
        kadr="16:9",
        muzyka=str(podklad.relative_to(montaz.MEDIA)),
        nazwa_pliku="z-lektorem",
    )

    audio = tmp_path / "dzwiek.wav"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wynik.files[0].path),
         "-ac", "1", "-ar", "16000", str(audio)],
        check=True,
        timeout=120,
    )
    rozpoznane = VoiceEngine(Settings()).transcribe(audio, "pl").text.lower()

    # Rozpoznanie mowy myli się w końcówkach („wymiar” wraca jako „wymian”, „meble” jako
    # „mebe”), więc nie stawiamy testu na jednym słowie. Liczy się to, czy z filmu wraca
    # dość materiału z obu zdań i czy drugie jest po pierwszym.
    z_pierwszego = [rdzen for rdzen in ("robimy", "meb", "wymia") if rdzen in rozpoznane]
    z_drugiego = [rdzen for rdzen in ("zadzwo", "umów", "pomia") if rdzen in rozpoznane]
    assert len(z_pierwszego) >= 2, rozpoznane
    assert len(z_drugiego) >= 2, rozpoznane
    assert rozpoznane.index(z_pierwszego[0]) < rozpoznane.index(z_drugiego[0]), rozpoznane


def test_podklad_schodzi_tylko_pod_lektorem() -> None:
    """Ściszamy muzykę wtedy i tylko wtedy, gdy ma pod czym zejść."""
    assert montaz._glosnosc_podkladu(0.6, z_lektorem=False) == 0.6
    assert montaz._glosnosc_podkladu(0.6, z_lektorem=True) == pytest.approx(0.21)
    assert montaz._glosnosc_podkladu(0.0, z_lektorem=True) == 0.0


def test_spot_radiowy_ma_kwestie_w_kolejnosci_i_podklad(harness: ToolHarness, tmp_path: Path) -> None:
    """Materiał dźwiękowy: kwestie po kolei, muzyka pod nimi, wybrzmienie na końcu."""
    from nexus.config import Settings
    from nexus.voice import VoiceEngine

    if not VoiceEngine(Settings()).local_voices():
        pytest.skip("głosy Piper nie są zainstalowane")
    podklad = next((p for p in (montaz.MEDIA / "muzyka").rglob("*.mp3") if p.is_file()), None)
    if podklad is None:
        pytest.skip("biblioteka nie ma podkładu muzycznego")

    wynik = wywolaj(
        harness,
        "audio_compose",
        kwestie=[
            {"tekst": "Pracownia stolarska Kowalscy.", "przerwa_po_s": 0.4},
            {"tekst": "Zadzwoń i umów bezpłatny pomiar.", "przerwa_po_s": 0.2},
        ],
        muzyka=str(podklad.relative_to(montaz.MEDIA)),
        nazwa_pliku="spot",
    )

    plik = wynik.files[0].path
    assert plik.is_file() and plik.suffix == ".mp3"
    assert wynik.data["kwestii"] == 2
    rozpoznane = VoiceEngine(Settings()).transcribe(plik, "pl").text.lower()
    # Jak wyżej: rdzenie zamiast pełnych form, bo rozpoznanie mowy myli końcówki.
    z_pierwszej = [rdzen for rdzen in ("pracownia", "stolar", "kowalsc") if rdzen in rozpoznane]
    z_drugiej = [rdzen for rdzen in ("zadzwo", "umów", "pomia") if rdzen in rozpoznane]
    assert len(z_pierwszej) >= 2, rozpoznane
    assert len(z_drugiej) >= 2, rozpoznane
    assert rozpoznane.index(z_pierwszej[0]) < rozpoznane.index(z_drugiej[0]), rozpoznane


def test_spot_bez_kwestii_i_bez_muzyki_mowi_wprost(harness: ToolHarness) -> None:
    with pytest.raises(ToolError, match="z niczego nie zrobię"):
        wywolaj(harness, "audio_compose")


def test_sam_podklad_ma_zadana_dlugosc(harness: ToolHarness) -> None:
    """Bez kwestii długość nie może być zgadywana — bierze się z pola, nie z liczby w kodzie."""
    podklad = next((p for p in (montaz.MEDIA / "muzyka").rglob("*.mp3") if p.is_file()), None)
    if podklad is None:
        pytest.skip("biblioteka nie ma podkładu muzycznego")

    wynik = wywolaj(
        harness,
        "audio_compose",
        muzyka=str(podklad.relative_to(montaz.MEDIA)),
        dlugosc_s=8.0,
        nazwa_pliku="podklad",
    )

    assert wynik.data["kwestii"] == 0
    assert wynik.data["dlugosc_s"] == pytest.approx(8.0, abs=0.2)
    dlugosc = float(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(wynik.files[0].path)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    assert dlugosc == pytest.approx(8.0, abs=0.4)
