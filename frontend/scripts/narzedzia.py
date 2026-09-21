#!/usr/bin/env python3
"""Wypisuje katalog narzędzi agenta do `frontend/src/dane/narzedzia.ts`.

Źródłem prawdy jest rejestr `backend/nexus/tools` — ten sam, z którego korzysta serwer MCP.
Dzięki temu witryna i aplikacja nie mogą obiecać narzędzia, którego nie ma, ani przemilczeć
tego, które istnieje. Opis narzędzia bierzemy wprost z rejestru; przypisanie do dziedziny
i przykład użycia są tu, bo rejestr ich nie zna.

Uruchamiane razem z `zasoby.py` przed `dev`, `build` i `test`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

# Dziedziny opisują, co człowiek chce zrobić, a nie jak to jest zbudowane.
# Kolejność jest kolejnością prezentacji.
DZIEDZINY: list[tuple[str, str, str, tuple[str, ...]]] = [
    (
        "projekt",
        "Projektowanie grafiki",
        "Logo, plakat, ulotka, ikona, baner i post powstają od zera, w rozmowie. "
        "Dostajesz plik wektorowy do dalszej edycji i PDF gotowy do druku.",
        ("design_vector", "design_compose", "icon_find", "render_lottie", "lottie_library", "asset_library"),
    ),
    (
        "zdjecia",
        "Zdjęcia i obrazy",
        "Zdjęcie wraca poprawione, powiększone albo bez tła. "
        "Niczego nie instalujesz i nie uczysz się programu graficznego.",
        ("enhance_photo", "retouch_portrait", "restore_faces", "upscale_image",
         "colorize_photo", "remove_background", "change_background", "erase_objects",
         "inpaint_photo", "blur_background_by_depth", "depth_map", "animate_photo", "find_faces",
         "convert_images", "imagemagick"),
    ),
    (
        "dokumenty",
        "Dokumenty i PDF",
        "Stos skanów, umów i faktur zamienia się w tekst, w którym da się szukać. "
        "Dokumenty rozdzielisz, złożysz na nowo i wyciągniesz z nich dane.",
        ("ocr_documents", "enhance_document_scan", "detect_document_boundaries", "pdf_merge",
         "pdf_split", "pdf_edit_pages", "convert_documents", "extract_text", "view_pages",
         "write_document", "translate_document", "check_grammar", "typeset_document",
         "convert_text_format", "analyze_document_structure", "read_document_aloud"),
    ),
    (
        "wiedza",
        "Wiedza i wyszukiwanie",
        "Pytasz własnymi słowami, a odpowiedź przychodzi z Twoich dokumentów, ze stron "
        "i z publikacji naukowych — razem z adresem źródła.",
        ("index_documents", "search_documents", "knowledge_save", "knowledge_read",
         "knowledge_notes", "web_search", "web_fetch_page", "browser_open", "browser_click",
         "browser_type", "browser_scroll", "browser_back", "scholar_search", "scholar_paper"),
    ),
    (
        "poczta",
        "Poczta i kalendarz",
        "Skrzynka i terminarz stoją w tym samym oknie co reszta pracy. "
        "Odpowiedź przygotowuje Nexus, wysyłasz ją Ty.",
        ("mail_list", "mail_read", "mail_search", "mail_draft", "mail_send",
         "calendar_list", "calendar_create", "calendar_update", "calendar_delete"),
    ),
    (
        "dzwiek",
        "Dźwięk i wideo",
        "Nagranie wraca jako tekst z napisami i podziałem na mówców. "
        "Ze zdjęć i klipów powstaje gotowy film, a z opisu — animacja.",
        ("video_compose", "audio_compose", "transcribe_audio", "transcribe_speakers", "media_process", "clean_audio",
         "split_audio_tracks", "edit_subtitles", "video_to_gif", "animate_explainer"),
    ),
    (
        "strony",
        "Strony internetowe",
        "Opisujesz stronę, oglądasz szkic i sam zatwierdzasz publikację. "
        "Każdą wersję da się zapisać i cofnąć.",
        ("site_kit_catalog", "site_from_kit", "site_from_template", "asset_to_site", "site_fonts_local", "site_vendor_assets",
         "site_list", "site_read_file", "site_write_file",
         "site_import_file", "site_delete_file", "site_save_version", "site_publish", "site_unpublish",
         "web_audit", "web_screenshot", "site_optimize_assets"),
    ),
    (
        "pliki",
        "Pliki i chmura",
        "Pliki zadania idą do archiwum albo do Twojej chmury osobistej, nie na cudzy dysk. "
        "Widzisz je potem także na telefonie.",
        ("inspect_files", "create_archive", "extract_archive",
         "cloud_browse", "cloud_import", "cloud_save"),
    ),
    (
        "aplikacje",
        "Aplikacje i kod",
        "Panel, landing albo sklep powstaje z gotowej aplikacji przebranej w Twoją markę. "
        "Obok stoi kontrola jakości kodu projektu.",
        ("app_templates", "app_from_template", "code_check"),
    ),
    (
        "komputer",
        "Twój komputer",
        "Nexus znajdzie plik na dysku, sprawdzi stan sprzętu, zrobi zrzut okna i wykona polecenie. "
        "Połączenie z komputerem jest domyślnie wyłączone — włączasz je sam.",
        ("pc_info", "pc_find_files", "pc_read_file", "pc_screenshot", "pc_powershell"),
    ),
]

# Przykład mówi, co użytkownik ma napisać, żeby narzędzie weszło do gry. Ma go każde
# narzędzie: w katalogu na stronie pusty przykład wygląda jak luka w ofercie.
PRZYKLADY: dict[str, str] = {
    "design_vector": "Zaprojektuj logo dla mojej firmy — znak i nazwa, wersja do druku.",
    "design_compose": "Zrób baner na stronę z tym zdjęciem i hasłem u góry.",
    "enhance_photo": "Odśwież to zdjęcie z lat 90. i popraw kolory.",
    "retouch_portrait": "Przygotuj z tego zdjęcia portret do CV.",
    "upscale_image": "Powiększ ten skan czterokrotnie, ma iść do druku.",
    "remove_background": "Wytnij produkt z tła i zapisz z przezroczystością.",
    "change_background": "Zamień tło na jednolite szare, jak w studiu.",
    "erase_objects": "Usuń przechodnia z lewej strony kadru.",
    "ocr_documents": "Rozpoznaj tekst z tych skanów i zrób przeszukiwalny PDF.",
    "detect_document_boundaries": "Ten PDF to kilka dokumentów — podziel go i nazwij według treści.",
    "pdf_merge": "Połącz te faktury w jeden plik w kolejności dat.",
    "pdf_split": "Wytnij z umowy strony 12–18.",
    "write_document": "Napisz pismo do ubezpieczyciela w DOCX na podstawie tych dokumentów.",
    "translate_document": "Przetłumacz tę instrukcję na angielski, zachowaj układ.",
    "check_grammar": "Sprawdź ten tekst przed wysłaniem.",
    "index_documents": "Dodaj te dokumenty do bazy wiedzy.",
    "search_documents": "Gdzie w moich dokumentach jest mowa o karencji?",
    "web_search": "Znajdź aktualne stawki i podaj źródła.",
    "scholar_search": "Poszukaj publikacji o pompach ciepła w budynkach z lat 90.",
    "mail_search": "Znajdź ostatnią wiadomość od księgowej.",
    "mail_draft": "Przygotuj odpowiedź z terminem, który mi pasuje.",
    "calendar_create": "Wpisz spotkanie z klientem we wtorek o 10.",
    "colorize_photo": "Pokoloruj to zdjęcie dziadków z lat 50.",
    "animate_photo": "Zrób z tego zdjęcia krótki film na Instagram.",
    "animate_explainer": "Wytłumacz mi na animacji, jak działa procent składany.",
    "typeset_document": "Złóż z tego ofertę do druku, w jednym stylu i z naszym logo.",
    "transcribe_speakers": "Spisz tę rozmowę z zaznaczeniem, kto co powiedział.",
    "read_document_aloud": "Przeczytaj mi ten raport na głos, posłucham w samochodzie.",
    "restore_faces": "Twarze na tym starym zdjęciu są rozmyte — odtwórz je.",
    "inpaint_photo": "Usuń ten samochód z lewej strony zdjęcia.",
    "blur_background_by_depth": "Rozmyj tło tak, żeby wyglądało jak z lustrzanki.",
    "icon_find": "Wstaw tu ikonę koperty w tym samym stylu co reszta.",
    "video_to_gif": "Zrób GIF-a z fragmentu 00:10–00:15 tego filmu.",
    "web_audit": "Sprawdź, czy moja strona nie ma błędów dostępności.",
    "find_faces": "Rozdziel te dwieście zdjęć z wesela według osób.",
    "code_check": "Przejrzyj ten projekt pod kątem błędów i podatności.",
    "site_fonts_local": "Przenieś kroje mojej strony z Google na nasz serwer.",
    "site_vendor_assets": "Ściągnij na nasz serwer wszystko, co strona bierze z obcych serwerów.",
    "app_templates": "Jakie gotowe aplikacje masz na serwerze?",
    "app_from_template": "Załóż mi panel zamówień z gotowego szablonu i przebierz go w moją markę.",
    "clean_audio": "To nagranie jest zaszumione — wyczyść je przed spisaniem.",
    "split_audio_tracks": "Wyciągnij z tego utworu sam wokal.",
    "transcribe_audio": "Zamień to nagranie w notatkę ze spotkania.",
    "media_process": "Wytnij z nagrania fragment 00:30–02:00 i zapisz jako MP3.",
    "video_compose": "Złóż z tych dziesięciu zdjęć filmik promocyjny 9:16 z napisami i spokojnym podkładem.",
    "audio_compose": "Zrób spot radiowy: trzy zdania lektora i muzyka w tle.",
    "site_publish": "Opublikuj tę stronę pod moim adresem.",
    "site_from_kit": "Zrób stronę dla mojej kancelarii — poważną, z cennikiem i kontaktem.",
    "site_from_template": "Weź ten gotowy szablon bloga i zrób z niego moją stronę.",
    "lottie_library": "Wstaw na stronę animowaną ikonę ładowania.",
    "asset_library": "Pokaż, jakie masz ilustracje i tła do strony.",
    "asset_to_site": "Wstaw na stronę animowane tło zamiast płaskiego koloru.",
    "site_kit_catalog": "Pokaż, jakie masz wzory stron dla restauracji.",
    "browser_open": "Wejdź na tę stronę i sprawdź, czy mają jeszcze wolne terminy.",
    "browser_type": "Poszukaj tego na ich stronie i powiedz, co znalazłeś.",
    "create_archive": "Spakuj te pliki do jednego archiwum.",
    "cloud_save": "Zapisz wynik w mojej chmurze, w katalogu Faktury.",
    "pc_find_files": "Znajdź na moim komputerze umowę najmu z zeszłego roku.",
    "pc_screenshot": "Zrób zrzut mojego ekranu i powiedz, co jest nie tak.",
    "render_lottie": "Zrób z tej animacji zwykły film, żeby dało się ją wstawić na stronę.",
    "depth_map": "Policz, co jest na tym zdjęciu bliżej, a co dalej — potrzebuję maski pierwszego planu.",
    "convert_images": "Zamień te zdjęcia na PNG i złóż je w jeden PDF.",
    "imagemagick": "Przytnij to zdjęcie do kwadratu i dodaj białą ramkę.",
    "enhance_document_scan": "Ten skan jest krzywy i szary — wyprostuj go i wybiel tło.",
    "pdf_edit_pages": "Usuń z tego PDF-u puste strony i obróć te położone bokiem.",
    "convert_documents": "Zamień ten dokument Worda na PDF.",
    "extract_text": "Wyciągnij z tego PDF-u sam tekst.",
    "view_pages": "Pokaż mi strony 3–5 tego dokumentu.",
    "convert_text_format": "Zrób z tego tekstu e-booka do czytnika.",
    "analyze_document_structure": "Wyciągnij z tej umowy tabelę z terminami, nie sam tekst.",
    "knowledge_save": "Zapisz tę stronę w kolekcji Dotacje.",
    "knowledge_read": "Pokaż, co mam zebrane w kolekcji Dotacje.",
    "knowledge_notes": "Dopisz do tej kolekcji notatkę z wnioskami z dzisiejszego czytania.",
    "web_fetch_page": "Przeczytaj tę stronę i powiedz, co z niej wynika.",
    "browser_click": "Kliknij przycisk Dalej i pokaż, co się pojawiło.",
    "browser_scroll": "Przewiń niżej i sprawdź, czy jest tam cennik.",
    "browser_back": "Wróć na poprzednią stronę.",
    "scholar_paper": "Pokaż szczegóły tej pracy i gotowy przypis.",
    "mail_list": "Co przyszło dziś na skrzynkę?",
    "mail_read": "Otwórz ostatnią wiadomość od biura i powiedz, czego dotyczy.",
    "mail_send": "Wyślij tę odpowiedź do klienta.",
    "calendar_list": "Co mam w kalendarzu w przyszłym tygodniu?",
    "calendar_update": "Przesuń spotkanie z czwartku na piątek na 14.",
    "calendar_delete": "Usuń z kalendarza odwołane szkolenie.",
    "edit_subtitles": "Te napisy spóźniają się o dwie sekundy — popraw czasy.",
    "site_list": "Pokaż moje strony i stan ich publikacji.",
    "site_read_file": "Pokaż, co jest teraz na stronie kontaktowej.",
    "site_write_file": "Zmień tekst na stronie głównej na ten nowy.",
    "site_import_file": "Wstaw moje logo na stronę.",
    "site_delete_file": "Usuń ze strony niepotrzebną podstronę z cennikiem.",
    "site_save_version": "Zapisz obecną wersję strony, zanim zacznę zmieniać układ.",
    "site_unpublish": "Zdejmij tę stronę z sieci.",
    "web_screenshot": "Pokaż, jak moja strona wygląda na telefonie.",
    "site_optimize_assets": "Strona wolno się ładuje — odchudź zdjęcia.",
    "inspect_files": "Sprawdź, czy w tym PDF-ie jest tekst, czy sam skan.",
    "extract_archive": "Rozpakuj to archiwum i rozpoznaj tekst we wszystkich skanach.",
    "cloud_browse": "Co mam w chmurze w katalogu Umowy?",
    "cloud_import": "Weź z mojej chmury faktury z marca.",
    "pc_info": "Komputer zwalnia — sprawdź, co go obciąża.",
    "pc_read_file": "Pokaż, co jest w tym pliku na moim pulpicie.",
    "pc_powershell": "Zrób miejsce na dysku C — wyczyść pliki tymczasowe.",
}


# Nazwa, którą widzi człowiek. Identyfikator z rejestru jest techniczny i po angielsku;
# na stronie i w aplikacji nie ma prawa się pojawić sam.
ETYKIETY: dict[str, str] = {
    "calendar_create": "Wpisz wydarzenie",
    "calendar_delete": "Usuń wydarzenie",
    "calendar_list": "Przejrzyj kalendarz",
    "calendar_update": "Zmień wydarzenie",
    "animate_photo": "Ożyw zdjęcie filmem",
    "animate_explainer": "Zrób animację wyjaśniającą",
    "analyze_document_structure": "Rozbierz dokument na części",
    "blur_background_by_depth": "Rozmyj tło jak obiektyw",
    "code_check": "Sprawdź jakość kodu",
    "site_fonts_local": "Kroje strony z serwera",
    "site_vendor_assets": "Zasoby strony z naszego serwera",
    "app_templates": "Gotowe aplikacje serwera",
    "app_from_template": "Załóż aplikację z szablonu",
    "site_optimize_assets": "Odchudź pliki strony",
    "web_audit": "Zbadaj stronę WWW",
    "web_screenshot": "Zrób zrzut strony",
    "browser_open": "Otwórz stronę w przeglądarce",
    "browser_click": "Kliknij na stronie",
    "browser_type": "Wypełnij pole na stronie",
    "browser_scroll": "Przewiń stronę",
    "browser_back": "Wróć na poprzednią stronę",
    "site_kit_catalog": "Przejrzyj wzory witryn",
    "site_from_kit": "Zbuduj witrynę z wzoru",
    "site_from_template": "Witryna z gotowego szablonu",
    "convert_text_format": "Zmień format tekstu",
    "depth_map": "Policz mapę głębi",
    "find_faces": "Znajdź osoby na zdjęciach",
    "edit_subtitles": "Popraw napisy",
    "icon_find": "Znajdź ikonę",
    "inpaint_photo": "Usuń duży element",
    "read_document_aloud": "Przeczytaj dokument na głos",
    "render_lottie": "Zamień animację Lottie",
    "lottie_library": "Gotowe animacje Lottie",
    "asset_library": "Biblioteka materiałów",
    "asset_to_site": "Materiał na stronę",
    "restore_faces": "Odtwórz twarze na zdjęciu",
    "transcribe_speakers": "Spisz rozmowę z mówcami",
    "typeset_document": "Złóż dokument do druku",
    "video_to_gif": "Zrób GIF z filmu",
    "change_background": "Zmień tło zdjęcia",
    "clean_audio": "Oczyść nagranie",
    "colorize_photo": "Pokoloruj czarno-białe",
    "design_compose": "Złóż baner lub post",
    "design_vector": "Zaprojektuj grafikę",
    "check_grammar": "Sprawdź tekst",
    "cloud_browse": "Przejrzyj chmurę",
    "cloud_import": "Pobierz z chmury",
    "cloud_save": "Zapisz w chmurze",
    "convert_documents": "Przekonwertuj dokument",
    "convert_images": "Przekonwertuj obraz",
    "create_archive": "Spakuj pliki",
    "detect_document_boundaries": "Rozdziel stos skanów",
    "enhance_document_scan": "Popraw skan",
    "enhance_photo": "Popraw zdjęcie",
    "erase_objects": "Wymaż obiekt",
    "extract_archive": "Rozpakuj archiwum",
    "extract_text": "Wyciągnij tekst",
    "imagemagick": "Obróbka na życzenie",
    "index_documents": "Dodaj do bazy wiedzy",
    "inspect_files": "Sprawdź pliki",
    "knowledge_notes": "Notatki w bazie wiedzy",
    "knowledge_read": "Czytaj bazę wiedzy",
    "knowledge_save": "Zapisz źródło",
    "mail_draft": "Przygotuj szkic",
    "mail_list": "Przejrzyj pocztę",
    "mail_read": "Przeczytaj wiadomość",
    "mail_search": "Znajdź wiadomość",
    "mail_send": "Wyślij wiadomość",
    "media_process": "Przetwórz audio i wideo",
    "video_compose": "Złóż film ze zdjęć i klipów",
    "audio_compose": "Złóż spot albo intro dźwiękowe",
    "ocr_documents": "Rozpoznaj tekst ze skanu",
    "pc_find_files": "Znajdź plik na komputerze",
    "pc_info": "Stan komputera",
    "pc_powershell": "Wykonaj polecenie",
    "pc_read_file": "Podejrzyj plik na komputerze",
    "pc_screenshot": "Zrzut ekranu komputera",
    "pdf_edit_pages": "Poukładaj strony PDF",
    "pdf_merge": "Połącz w jeden PDF",
    "pdf_split": "Podziel PDF",
    "remove_background": "Wytnij z tła",
    "retouch_portrait": "Wyretuszuj portret",
    "scholar_paper": "Szczegóły publikacji",
    "scholar_search": "Szukaj publikacji naukowych",
    "search_documents": "Szukaj w swoich dokumentach",
    "site_delete_file": "Usuń plik strony",
    "site_import_file": "Dodaj plik do strony",
    "site_list": "Twoje strony",
    "site_publish": "Opublikuj stronę",
    "split_audio_tracks": "Rozdziel ścieżki utworu",
    "site_read_file": "Odczytaj plik strony",
    "site_save_version": "Zapisz wersję strony",
    "site_unpublish": "Wycofaj publikację",
    "site_write_file": "Zapisz plik strony",
    "transcribe_audio": "Przepisz nagranie",
    "translate_document": "Przetłumacz dokument",
    "upscale_image": "Powiększ obraz",
    "view_pages": "Pokaż strony",
    "web_fetch_page": "Pobierz stronę",
    "web_search": "Szukaj w sieci",
    "write_document": "Napisz dokument",
}

# Skróty, po których nie kończy się zdanie — inaczej „(np.” urywa opis w połowie.
SKROTY = ("np", "tj", "itp", "itd", "m.in", "ok", "tzn", "min", "godz", "ang", "zob")


def pierwsze_zdanie(opis: str) -> str:
    """Pierwsze pełne zdanie opisu, złożone w jedną linię.

    Zdanie kończy kropka, wykrzyknik albo pytajnik. **Nie kończy go dwukropek**: dwukropek
    zapowiada wyliczenie, więc cięcie na nim zostawiało w katalogu opisy urwane w pół myśli
    („…w zbiorze Iconify (ponad 400 tys. znaków:”). Z tego samego powodu nie tniemy w środku
    nawiasu — koniec zdania nie wypada nigdy między otwarciem a domknięciem.
    """
    tekst = re.sub(r"\s+", " ", opis).strip()
    for dopasowanie in re.finditer(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])", tekst):
        poczatek = tekst[: dopasowanie.start()]
        # Nawias przed skrótem („(np.”) nie może zmylić rozpoznania skrótu.
        ostatnie = poczatek.rsplit(" ", 1)[-1].strip("([{\u201e\u201c\"'").rstrip(".:").lower()
        if ostatnie in SKROTY:
            continue
        if poczatek.count("(") != poczatek.count(")"):
            continue
        return poczatek
    return tekst


def main() -> int:
    from nexus.tools import registry

    opisy = {nazwa: registry._tools[nazwa].description for nazwa in registry.names()}
    przypisane = {nazwa for _, _, _, nazwy in DZIEDZINY for nazwa in nazwy}

    braki = sorted(set(opisy) - przypisane)
    nadmiar = sorted(przypisane - set(opisy))
    if nadmiar:
        print(f"katalog narzędzi: w spisie są nieistniejące narzędzia: {nadmiar}", file=sys.stderr)
        return 1
    bez_etykiety = sorted(set(opisy) - set(ETYKIETY))
    if bez_etykiety:
        print(f"katalog narzędzi: narzędzia bez polskiej nazwy: {bez_etykiety}", file=sys.stderr)
        return 1
    if braki:
        # Nowe narzędzie bez dziedziny jest usterką spisu, nie powodem do przemilczenia.
        print(f"katalog narzędzi: narzędzia bez dziedziny: {braki}", file=sys.stderr)
        return 1

    dziedziny = [
        {
            "id": klucz,
            "tytul": tytul,
            "opis": opis,
            "narzedzia": [
                {
                    "id": nazwa,
                    "nazwa": ETYKIETY[nazwa],
                    # Pierwsze zdanie opisu z rejestru wystarcza jako zdanie do czytania.
                    "opis": pierwsze_zdanie(opisy[nazwa]),
                    "przyklad": PRZYKLADY.get(nazwa, ""),
                }
                for nazwa in nazwy
            ],
        }
        for klucz, tytul, opis, nazwy in DZIEDZINY
    ]

    tresc = (
        "// Katalog narzędzi agenta. Wynik frontend/scripts/narzedzia.py — nie edytować ręcznie.\n"
        "// Źródło prawdy: rejestr backend/nexus/tools (ten sam, z którego korzysta serwer MCP).\n\n"
        "export type Narzedzie = { id: string; nazwa: string; opis: string; przyklad: string };\n"
        "export type DziedzinaNarzedzi = { id: string; tytul: string; opis: string; narzedzia: Narzedzie[] };\n\n"
        f"export const DZIEDZINY: DziedzinaNarzedzi[] = {json.dumps(dziedziny, ensure_ascii=False, indent=2)};\n\n"
        f"export const LICZBA_NARZEDZI = {len(opisy)};\n"
    )
    cel = REPO / "frontend" / "src" / "dane" / "narzedzia.ts"
    cel.parent.mkdir(parents=True, exist_ok=True)
    cel.write_text(tresc, encoding="utf-8")
    print(f"katalog narzędzi: {len(opisy)} narzędzi w {len(dziedziny)} dziedzinach")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
