"""Generator plików przykładowych i nagrań pokazu.

Uruchamiany ręcznie (``python -m nexus.demo.przyklady.generuj``) po zmianie scenariuszy.
Tworzy małe pliki wejściowe (skan faktury, stare zdjęcie, dwie strony umowy, nagranie
narady, dokumenty tekstowe) oraz nagrane przebiegi z plikami wynikowymi.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image

KATALOG = Path(__file__).parent
NAGRANIA = KATALOG / "nagrania"
PLIKI_NAGRAN = NAGRANIA / "pliki"

FAKTURA = """FAKTURA VAT nr FV/2026/08/117
Sprzedawca: Przedsiębiorstwo Handlowe Żuraw Sp. z o.o., ul. Morska 14, 80-299 Gdańsk
NIP 584-10-22-118
Nabywca: Ćma Grzegorz Łęcki, ul. Piotrkowska 61, 90-413 Łódź
Data wystawienia: 29 sierpnia 2026 r.
Termin płatności: 12 września 2026 r.
Sposób zapłaty: przelew, 14 dni
Lp. Nazwa usługi                     Ilość   Cena netto   Wartość netto
1.  Przegląd techniczny instalacji     1        1 980,00        1 980,00
2.  Wymiana filtrów i uszczelek        3          126,00          378,00
3.  Dojazd serwisu                     2           68,00          136,00
Razem netto: 2 494,00 zł
VAT 23%: 573,62 zł
Do zapłaty: 3 067,62 zł
Rachunek: PL 21 1020 1026 0000 1102 0306 4189
"""

UMOWA_1 = """UMOWA SERWISOWA nr 17/2026
zawarta 12 września 2026 r. w Łodzi pomiędzy:
Przedsiębiorstwem Handlowym Żuraw Sp. z o.o. z siedzibą w Gdańsku,
a firmą Ćma Grzegorz Łęcki, zwaną dalej Zamawiającym.
§ 1. Przedmiot umowy
Wykonawca zobowiązuje się do przeprowadzania przeglądów technicznych instalacji
wentylacyjnej w siedzibie Zamawiającego, dwa razy w roku kalendarzowym.
§ 2. Terminy
Pierwszy przegląd odbędzie się do 30 listopada 2026 r., kolejny do 31 maja 2027 r.
Za terminowość przeglądów odpowiada kierownik serwisu Halina Ostrowska.
"""

UMOWA_2 = """§ 3. Wynagrodzenie
Łączne wynagrodzenie roczne wynosi 12 450,00 zł brutto, płatne w dwóch ratach
po każdym przeglądzie, w terminie 14 dni od doręczenia faktury.
§ 4. Odpowiedzialność
Wykonawca odpowiada za usunięcie usterek wykrytych podczas przeglądu w ciągu 7 dni.
§ 5. Postanowienia końcowe
Umowa wchodzi w życie z dniem podpisania i obowiązuje przez 24 miesiące.
Zażółć gęślą jaźń, pchnąć w tę łódź jeża lub ośm skrzyń fig.
"""

DOKUMENTY = {
    "notatki-projekt.txt": (
        "Notatki z rozruchu instalacji, sierpień 2026\n\n"
        "Rozruch przebiegł bez zakłóceń, wentylacja pracuje na drugim biegu.\n"
        "Kierownik serwisu Halina Ostrowska prowadzi harmonogram przeglądów.\n"
        "Pierwszy przegląd techniczny zaplanowano do 30 listopada 2026 r.\n"
        "Zamawiający prosi o protokół w formie elektronicznej.\n"
    ),
    "umowa-serwisowa.txt": UMOWA_1 + "\n" + UMOWA_2,
    "protokol-odbioru.txt": (
        "Protokół odbioru robót, 29 sierpnia 2026 r.\n\n"
        "Komisja stwierdziła wykonanie prac zgodnie z projektem.\n"
        "Za przegląd techniczny instalacji odpowiada kierownik serwisu Halina Ostrowska.\n"
        "Termin pierwszego przeglądu: do 30 listopada 2026 r.\n"
        "Usterki drobne: nieszczelność przy kratce w sali 2 – do usunięcia w 7 dni.\n"
    ),
}

NARADA = [
    ("gosia", "Zaczynamy naradę serwisową. Temat: przegląd instalacji w Łodzi."),
    ("darkman", "Przegląd musi się odbyć do trzydziestego listopada, inaczej tracimy gwarancję."),
    ("gosia", "Halina Ostrowska bierze harmonogram i umawia termin z zamawiającym."),
    ("darkman", "Ja przygotuję listę części, głównie filtry i uszczelki, do piątku."),
    ("gosia", "Protokół z przeglądu wysyłamy w formie elektronicznej, tak jak prosił zamawiający."),
    ("darkman", "Nieszczelność przy kratce w sali drugiej usuwamy w ciągu siedmiu dni."),
]


def _font() -> str:
    from nexus.ocr.pdf_processor import find_text_layer_font

    return str(find_text_layer_font())


def _strona(tekst: str, dpi: int = 150, rozmiar: float = 11.0) -> np.ndarray:
    """Strona A4 z tekstem jako obraz w skali szarości."""
    with pymupdf.open() as dokument:
        strona = dokument.new_page(width=595, height=842)
        strona.insert_font(fontname="doc", fontfile=_font())
        strona.insert_textbox(
            pymupdf.Rect(50, 60, 545, 800), tekst, fontname="doc", fontsize=rozmiar, lineheight=1.5
        )
        pixmap = strona.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        return np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width).copy()


def _zdjecie_skanu(obraz: np.ndarray, skos: float, cien: float) -> np.ndarray:
    """Symuluje zdjęcie kartki telefonem: przekrzywienie, cień i szum."""
    wysokosc, szerokosc = obraz.shape
    macierz = cv2.getRotationMatrix2D((szerokosc / 2, wysokosc / 2), skos, 1.0)
    obraz = cv2.warpAffine(obraz, macierz, (szerokosc, wysokosc), borderValue=255)
    poziom = np.linspace(1.0, 1.0 - cien, szerokosc, dtype=np.float32)
    obraz = np.clip(obraz.astype(np.float32) * poziom[None, :], 0, 255)
    generator = np.random.default_rng(11)
    obraz = np.clip(obraz + generator.normal(0, 6, obraz.shape), 0, 255)
    return obraz.astype(np.uint8)


def _zapisz(sciezka: Path, obraz: np.ndarray, jakosc: int = 70) -> Path:
    parametry = [cv2.IMWRITE_JPEG_QUALITY, jakosc] if sciezka.suffix == ".jpg" else []
    ok, dane = cv2.imencode(sciezka.suffix, obraz, parametry)
    if not ok:
        raise RuntimeError(f"Nie można zapisać {sciezka.name}")
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    sciezka.write_bytes(dane.tobytes())
    return sciezka


def _stare_zdjecie() -> np.ndarray:
    """Syntetyczne zdjęcie z lat 70.: wyblakłe barwy, niski kontrast, ziarno."""
    wysokosc, szerokosc = 420, 560
    obraz = np.zeros((wysokosc, szerokosc, 3), np.uint8)
    for wiersz in range(wysokosc):
        udzial = wiersz / wysokosc
        obraz[wiersz, :] = (200 - 60 * udzial, 170 - 40 * udzial, 140 - 20 * udzial)
    cv2.rectangle(obraz, (60, 250), (500, 420), (120, 140, 150), -1)
    cv2.rectangle(obraz, (150, 150), (330, 300), (90, 110, 160), -1)
    cv2.rectangle(obraz, (190, 210), (230, 260), (60, 70, 110), -1)
    cv2.circle(obraz, (430, 90), 40, (150, 190, 220), -1)
    obraz = cv2.GaussianBlur(obraz, (0, 0), 1.1)
    wyblakle = np.clip(obraz.astype(np.float32) * 0.62 + 78, 0, 255)
    wyblakle[:, :, 0] *= 0.9
    wyblakle[:, :, 2] *= 1.06
    generator = np.random.default_rng(5)
    wyblakle = np.clip(wyblakle + generator.normal(0, 7, wyblakle.shape), 0, 255)
    return wyblakle.astype(np.uint8)


def _nagranie(cel: Path) -> bool:
    """Nagranie narady dwoma głosami Piper; ``False``, gdy głosów nie ma na dysku."""
    from nexus.config import get_settings

    katalog = get_settings().voice_tts_dir
    glosy = {nazwa: katalog / f"pl_PL-{nazwa}-medium.onnx" for nazwa in {osoba for osoba, _ in NARADA}}
    if not all(sciezka.is_file() for sciezka in glosy.values()):
        return False
    from piper import PiperVoice

    zaladowane = {nazwa: PiperVoice.load(str(sciezka)) for nazwa, sciezka in glosy.items()}
    czestotliwosc = next(iter(zaladowane.values())).config.sample_rate
    probki: list[np.ndarray] = []
    cisza = np.zeros(int(czestotliwosc * 0.4), np.int16)
    for osoba, zdanie in NARADA:
        kawalki = [
            np.frombuffer(kawalek.audio_int16_bytes, np.int16)
            for kawalek in zaladowane[osoba].synthesize(zdanie)
        ]
        probki.extend(kawalki)
        probki.append(cisza)
    # Whisper i tak pracuje na 16 kHz – plik przykładowy jest w tej częstotliwości mniejszy.
    dane = np.concatenate(probki).astype(np.float32)
    docelowa = 16_000
    osie = np.linspace(0, len(dane) - 1, int(len(dane) * docelowa / czestotliwosc), dtype=np.float32)
    przeliczone = np.interp(osie, np.arange(len(dane), dtype=np.float32), dane).astype(np.int16)
    cel.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(cel), "wb") as plik:
        plik.setnchannels(1)
        plik.setsampwidth(2)
        plik.setframerate(docelowa)
        plik.writeframes(przeliczone.tobytes())
    return True


def _pdf_z_warstwa(cel: Path, obrazy: list[np.ndarray], teksty: list[str]) -> Path:
    """PDF ze stronami obrazowymi i niewidoczną warstwą tekstową (wynik nagrany)."""
    with pymupdf.open() as dokument:
        for obraz, tekst in zip(obrazy, teksty, strict=True):
            wysokosc, szerokosc = obraz.shape[:2]
            strona = dokument.new_page(width=szerokosc * 72 / 150, height=wysokosc * 72 / 150)
            ok, zakodowany = cv2.imencode(".jpg", obraz, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                raise RuntimeError("Nie można zakodować strony.")
            strona.insert_image(strona.rect, stream=zakodowany.tobytes())
            strona.insert_font(fontname="doc", fontfile=_font())
            strona.insert_textbox(
                pymupdf.Rect(18, 22, strona.rect.width - 18, strona.rect.height - 22),
                tekst,
                fontname="doc",
                fontsize=8,
                lineheight=1.5,
                render_mode=3,
            )
        cel.parent.mkdir(parents=True, exist_ok=True)
        dokument.save(cel, garbage=3, deflate=True)
    return cel


NOTATKA = """# Notatka z narady serwisowej

## Ustalenia
- Przegląd instalacji w Łodzi musi się odbyć do 30 listopada 2026 r., inaczej wygasa gwarancja.
- Protokół z przeglądu trafia do zamawiającego w formie elektronicznej.
- Nieszczelność przy kratce w sali 2 zostaje usunięta w ciągu 7 dni.

## Zadania
- Halina Ostrowska — harmonogram przeglądu i ustalenie terminu z zamawiającym.
- Serwis — lista części (filtry, uszczelki) do piątku.
"""

ODPOWIEDZ_FAKTURA = (
    "Do zapłaty jest 3 067,62 zł brutto (netto 2 494,00 zł, VAT 573,62 zł).\n"
    "Termin płatności upływa 12 września 2026 r., przelewem na rachunek ze skanu."
)
ODPOWIEDZ_SKANY = (
    "Dwie strony umowy zostały złożone w jeden PDF i opatrzone niewidoczną warstwą tekstową — "
    "w pliku da się szukać tekstu i kopiować go, a wygląd stron pozostał bez zmian."
)
ODPOWIEDZ_ZDJECIE = (
    "Zdjęcie ma wyrównany balans bieli, odzyskane cienie i mniej ziarna, a po powiększeniu 2× "
    "nadaje się do wydruku w formacie 15 × 21 cm."
)
ODPOWIEDZ_WYSZUKIWANIE = (
    "Za przegląd techniczny odpowiada kierownik serwisu Halina Ostrowska, "
    "a termin pierwszego przeglądu to 30 listopada 2026 r. "
    "Wskazują na to protokół odbioru i notatki z rozruchu."
)


def _nagranie_json(nazwa: str, kroki: list[dict], odpowiedz: str, pliki: list[dict]) -> None:
    NAGRANIA.mkdir(parents=True, exist_ok=True)
    tresc = {"scenariusz": nazwa, "kroki": kroki, "odpowiedz": odpowiedz, "pliki": pliki}
    (NAGRANIA / f"{nazwa}.json").write_text(
        json.dumps(tresc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def generuj() -> None:
    """Tworzy wszystkie pliki przykładowe i nagrania."""
    KATALOG.mkdir(parents=True, exist_ok=True)
    for nazwa, tresc in DOKUMENTY.items():
        (KATALOG / nazwa).write_text(tresc, encoding="utf-8")

    faktura = _zdjecie_skanu(_strona(FAKTURA, rozmiar=11.5), skos=1.6, cien=0.18)
    _zapisz(KATALOG / "faktura-skan.jpg", faktura)
    strony = [_strona(UMOWA_1), _strona(UMOWA_2)]
    for numer, strona in enumerate(strony, start=1):
        _zapisz(KATALOG / f"umowa-strona-{numer}.jpg", _zdjecie_skanu(strona, skos=0.8, cien=0.1))
    _zapisz(KATALOG / "zdjecie-1974.jpg", _stare_zdjecie(), jakosc=62)
    if not _nagranie(KATALOG / "narada.wav"):
        print("Pominięto narada.wav – brak głosów Piper.")

    czysta_faktura = _strona(FAKTURA, rozmiar=11.5)
    _pdf_z_warstwa(PLIKI_NAGRAN / "faktura" / "FV_2026_08_117_OCR.pdf", [czysta_faktura], [FAKTURA])
    _pdf_z_warstwa(PLIKI_NAGRAN / "skany" / "umowa_polaczone_OCR.pdf", strony, [UMOWA_1, UMOWA_2])
    poprawione = np.clip(_stare_zdjecie().astype(np.float32) * 1.45 - 60, 0, 255).astype(np.uint8)
    poprawione = cv2.detailEnhance(poprawione, sigma_s=8, sigma_r=0.2)
    _zapisz(PLIKI_NAGRAN / "zdjecie" / "zdjecie-1974_poprawione.jpg", poprawione, jakosc=90)
    with Image.fromarray(cv2.cvtColor(poprawione, cv2.COLOR_BGR2RGB)) as obraz:
        powiekszone = obraz.resize((obraz.width * 2, obraz.height * 2), Image.Resampling.LANCZOS)
        cel = PLIKI_NAGRAN / "zdjecie" / "zdjecie-1974_powiekszone.png"
        cel.parent.mkdir(parents=True, exist_ok=True)
        powiekszone.save(cel)
    (PLIKI_NAGRAN / "notatka").mkdir(parents=True, exist_ok=True)
    (PLIKI_NAGRAN / "notatka" / "Notatka z narady.md").write_text(NOTATKA, encoding="utf-8")

    _nagranie_json(
        "faktura",
        [
            {"etykieta": "Poprawa skanu", "czas_ms": 3120, "opis": "Poprawiono skany: 1"},
            {
                "etykieta": "Rozpoznanie tekstu i przeszukiwalny PDF",
                "czas_ms": 6840,
                "opis": "OCR: 1 plik, 1 strona, język pol",
            },
            {"etykieta": "Odczyt kwoty i terminu", "czas_ms": 2380, "opis": "Odpowiedź modelu"},
        ],
        ODPOWIEDZ_FAKTURA,
        [{"nazwa": "FV_2026_08_117_OCR.pdf", "plik": "faktura/FV_2026_08_117_OCR.pdf"}],
    )
    _nagranie_json(
        "zdjecie",
        [
            {"etykieta": "Korekta zdjęcia", "czas_ms": 2450, "opis": "Poprawiono zdjęcia: 1"},
            {"etykieta": "Powiększenie AI", "czas_ms": 48200, "opis": "Powiększono 2×: 1 obraz"},
        ],
        ODPOWIEDZ_ZDJECIE,
        [
            {"nazwa": "zdjecie-1974_poprawione.jpg", "plik": "zdjecie/zdjecie-1974_poprawione.jpg"},
            {"nazwa": "zdjecie-1974_powiekszone.png", "plik": "zdjecie/zdjecie-1974_powiekszone.png"},
        ],
    )
    _nagranie_json(
        "skany",
        [
            {"etykieta": "Złożenie stron w jeden PDF", "czas_ms": 940, "opis": "Skonwertowano: 1"},
            {
                "etykieta": "Rozpoznanie tekstu (warstwa tekstowa)",
                "czas_ms": 11260,
                "opis": "OCR: 1 plik, 2 strony, język pol",
            },
        ],
        ODPOWIEDZ_SKANY,
        [{"nazwa": "umowa_polaczone_OCR.pdf", "plik": "skany/umowa_polaczone_OCR.pdf"}],
    )
    _nagranie_json(
        "notatka",
        [
            {
                "etykieta": "Transkrypcja nagrania",
                "czas_ms": 14700,
                "opis": "Transkrypcja narada.wav: 0,6 min, język pl",
            },
            {"etykieta": "Ustalenia i zadania", "czas_ms": 3900, "opis": "Odpowiedź modelu"},
            {"etykieta": "Zapis notatki", "czas_ms": 210, "opis": "Utworzono Notatka z narady.md"},
        ],
        NOTATKA,
        [{"nazwa": "Notatka z narady.md", "plik": "notatka/Notatka z narady.md"}],
    )
    _nagranie_json(
        "wyszukiwanie",
        [
            {"etykieta": "Indeksowanie dokumentów", "czas_ms": 1980, "opis": "Zaindeksowano dokumenty: 3"},
            {"etykieta": "Wyszukiwanie po znaczeniu", "czas_ms": 640, "opis": "Wyszukiwanie: 3 fragmentów"},
        ],
        ODPOWIEDZ_WYSZUKIWANIE,
        [],
    )
    print(f"Gotowe: {KATALOG}")


if __name__ == "__main__":
    generuj()
