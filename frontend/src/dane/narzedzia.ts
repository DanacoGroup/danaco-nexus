// Katalog narzędzi agenta. Wynik frontend/scripts/narzedzia.py — nie edytować ręcznie.
// Źródło prawdy: rejestr backend/nexus/tools (ten sam, z którego korzysta serwer MCP).

export type Narzedzie = { id: string; nazwa: string; opis: string; przyklad: string };
export type DziedzinaNarzedzi = { id: string; tytul: string; opis: string; narzedzia: Narzedzie[] };

export const DZIEDZINY: DziedzinaNarzedzi[] = [
  {
    "id": "projekt",
    "tytul": "Projektowanie grafiki",
    "opis": "Logo, plakat, okładka, ulotka, ikona, baner, post — projekt powstaje od zera, z plikiem wektorowym do edycji i PDF‑em do druku.",
    "narzedzia": [
      {
        "id": "design_vector",
        "nazwa": "Zaprojektuj grafikę",
        "opis": "Projektuje grafikę wektorową od zera: logo, znak, plakat, okładka, ulotka, wizytówka, ikona, diagram, infografika, etykieta, post do mediów społecznościowych.",
        "przyklad": "Zaprojektuj logo dla mojej firmy — znak i nazwa, wersja do druku."
      },
      {
        "id": "design_compose",
        "nazwa": "Złóż baner lub post",
        "opis": "Składa gotowe elementy w jeden kadr: baner, miniatura, post, okładka, plansza porównawcza, kolaż.",
        "przyklad": "Zrób baner na stronę z tym zdjęciem i hasłem u góry."
      },
      {
        "id": "icon_find",
        "nazwa": "Znajdź ikonę",
        "opis": "Znajduje gotową ikonę w zbiorze Iconify (ponad 400 tys. znaków:",
        "przyklad": "Wstaw tu ikonę koperty w tym samym stylu co reszta."
      },
      {
        "id": "render_lottie",
        "nazwa": "Zamień animację Lottie",
        "opis": "Zamienia animację Lottie (.json albo .lottie — format animacji z sieci i z pakietów graficznych) w plik, który da się obejrzeć i wstawić:",
        "przyklad": ""
      },
      {
        "id": "lottie_library",
        "nazwa": "Gotowe animacje Lottie",
        "opis": "Spis gotowych animacji Lottie leżących na serwerze — animacje interfejsu, ikony w ruchu, wskaźniki ładowania, ilustracje.",
        "przyklad": "Wstaw na stronę animowaną ikonę ładowania."
      },
      {
        "id": "asset_library",
        "nazwa": "Biblioteka materiałów",
        "opis": "Co leży w bibliotekach materiałów serwera: ilustracje SVG, wzory i tekstury teł, gradienty, makiety urządzeń (dział „grafika”), animowane tła WebGL, biblioteki animacji i shadery (dział „ruch”), dźwięki, podkłady muzyczne, LUT-y i przejścia wideo (dział „media”).",
        "przyklad": "Pokaż, jakie masz ilustracje i tła do strony."
      }
    ]
  },
  {
    "id": "zdjecia",
    "tytul": "Zdjęcia i obrazy",
    "opis": "Poprawa, retusz, powiększanie, tło, montaż — bez programu graficznego.",
    "narzedzia": [
      {
        "id": "enhance_photo",
        "nazwa": "Popraw zdjęcie",
        "opis": "Profesjonalna korekta zdjęć (np. ogłoszenia nieruchomości, produkty): balans bieli, poziomy, ekspozycja, cienie/światła, kontrast lokalny, nasycenie, temperatura barwowa, odszumianie, wyostrzenie, prostowanie pionów i perspektywy.",
        "przyklad": "Odśwież to zdjęcie z lat 90. i popraw kolory."
      },
      {
        "id": "retouch_portrait",
        "nazwa": "Wyretuszuj portret",
        "opis": "Naturalny retusz portretu: wygładzenie skóry z zachowaniem tekstury, delikatne rozjaśnienie cieni, ocieplenie i wyostrzenie detali.",
        "przyklad": "Przygotuj z tego zdjęcia portret do CV."
      },
      {
        "id": "restore_faces",
        "nazwa": "Odtwórz twarze na zdjęciu",
        "opis": "Rekonstruuje twarze na zdjęciu zniszczonym, rozmytym, drobnym albo mocno skompresowanym (CodeFormer lub GFPGAN): odtwarza oczy, usta i kontury, których w pliku po prostu nie ma.",
        "przyklad": "Twarze na tym starym zdjęciu są rozmyte — odtwórz je."
      },
      {
        "id": "upscale_image",
        "nazwa": "Powiększ obraz",
        "opis": "Powiększa i rekonstruuje szczegóły obrazu siecią Real-ESRGAN (AI, na CPU – może trwać kilka minut dla dużych zdjęć).",
        "przyklad": "Powiększ ten skan czterokrotnie, ma iść do druku."
      },
      {
        "id": "colorize_photo",
        "nazwa": "Pokoloruj czarno-białe",
        "opis": "Koloryzuje zdjęcie czarno-białe albo sepiowe (model DDColor).",
        "przyklad": "Pokoloruj to zdjęcie dziadków z lat 50."
      },
      {
        "id": "remove_background",
        "nazwa": "Wytnij z tła",
        "opis": "Usuwa tło ze zdjęcia (AI, rembg): wynik PNG z przezroczystym tłem – do sklepów, ogłoszeń, grafik.",
        "przyklad": "Wytnij produkt z tła i zapisz z przezroczystością."
      },
      {
        "id": "change_background",
        "nazwa": "Zmień tło zdjęcia",
        "opis": "Zmienia tło zdjęcia: wycina obiekt (rembg) i nakłada go na jednolity kolor, gradient, inne zdjęcie albo rozmyte oryginalne tło (efekt portretowy).",
        "przyklad": "Zamień tło na jednolite szare, jak w studiu."
      },
      {
        "id": "erase_objects",
        "nazwa": "Wymaż obiekt",
        "opis": "Gumka: usuwa ze zdjęcia wskazane obiekty (napis, znak wodny, przewód, przypadkową osobę) i wypełnia miejsce tłem z otoczenia (inpainting OpenCV).",
        "przyklad": "Usuń przechodnia z lewej strony kadru."
      },
      {
        "id": "inpaint_photo",
        "nazwa": "Usuń duży element",
        "opis": "Usuwa ze zdjęcia duży element i dorysowuje to, co było za nim (model LaMa): przechodnia, samochód, kosz na śmieci, słup, byłego partnera, a w trybie „rysy” także rysy, zagięcia i kurz ze skanu starej odbitki.",
        "przyklad": "Usuń ten samochód z lewej strony zdjęcia."
      },
      {
        "id": "blur_background_by_depth",
        "nazwa": "Rozmyj tło jak obiektyw",
        "opis": "Rozmywa tło zdjęcia tak, jak robi to jasny obiektyw: mapa głębi rozdziela plany, więc rozmycie narasta wraz z odległością od wybranego planu, zamiast kończyć się na ostrej obwódce wokół wyciętego obiektu.",
        "przyklad": "Rozmyj tło tak, żeby wyglądało jak z lustrzanki."
      },
      {
        "id": "depth_map",
        "nazwa": "Policz mapę głębi",
        "opis": "Liczy mapę głębi zdjęcia (Depth Anything V2):",
        "przyklad": ""
      },
      {
        "id": "animate_photo",
        "nazwa": "Ożyw zdjęcie filmem",
        "opis": "Zamienia zdjęcie w krótki film z efektem paralaksy 2.5D: mapa głębi rozdziela plany, kamera przesuwa się nad kadrem, a odsłonięte miejsca są dopełniane.",
        "przyklad": "Zrób z tego zdjęcia krótki film na Instagram."
      },
      {
        "id": "find_faces",
        "nazwa": "Znajdź osoby na zdjęciach",
        "opis": "Znajduje twarze na zdjęciach i — na życzenie — grupuje zdjęcia tej samej osoby (InsightFace).",
        "przyklad": "Rozdziel te dwieście zdjęć z wesela według osób."
      },
      {
        "id": "convert_images",
        "nazwa": "Przekonwertuj obraz",
        "opis": "Konwertuje obrazy między formatami (JPG, PNG, WEBP, TIFF, BMP, PDF), opcjonalnie zmniejsza je i łączy wiele obrazów w jeden PDF.",
        "przyklad": ""
      },
      {
        "id": "imagemagick",
        "nazwa": "Obróbka na życzenie",
        "opis": "Uruchamia ImageMagick (magick) z listą operacji na jednym obrazie, gdy potrzebna jest obróbka, której nie obejmują inne narzędzia (np. przycięcie, obramowanie, sepia, zmiana rozmiaru, kolorystyka).",
        "przyklad": ""
      }
    ]
  },
  {
    "id": "dokumenty",
    "tytul": "Dokumenty i PDF",
    "opis": "Skany, umowy, faktury, pisma: rozpoznanie tekstu, porządkowanie, składanie i dzielenie.",
    "narzedzia": [
      {
        "id": "ocr_documents",
        "nazwa": "Rozpoznaj tekst ze skanu",
        "opis": "Rozpoznaje tekst (OCR, Tesseract) w skanach PDF i zdjęciach dokumentów.",
        "przyklad": "Rozpoznaj tekst z tych skanów i zrób przeszukiwalny PDF."
      },
      {
        "id": "enhance_document_scan",
        "nazwa": "Popraw skan",
        "opis": "Poprawia jakość skanów i zdjęć dokumentów: wykrycie kartki i korekta perspektywy, prostowanie, odszumianie, wyrównanie oświetlenia/cieni i wybielenie tła, usunięcie czarnych krawędzi, opcjonalnie unpaper, wyostrzenie tekstu i czerń-biel.",
        "przyklad": ""
      },
      {
        "id": "detect_document_boundaries",
        "nazwa": "Rozdziel stos skanów",
        "opis": "Analizuje wielodokumentowy PDF (np. skan wielu pism naraz) strona po stronie: nagłówki i stopki (z OCR, jeśli brak tekstu), numeracja „strona X z Y”, puste strony (separatory), tytuły dokumentów i podobieństwo nagłówków.",
        "przyklad": "Ten PDF to kilka dokumentów — podziel go i nazwij według treści."
      },
      {
        "id": "pdf_merge",
        "nazwa": "Połącz w jeden PDF",
        "opis": "Łączy pliki w jeden PDF w podanej kolejności.",
        "przyklad": "Połącz te faktury w jeden plik w kolejności dat."
      },
      {
        "id": "pdf_split",
        "nazwa": "Podziel PDF",
        "opis": "Dzieli PDF na osobne pliki według zakresów stron, bez utraty jakości (strony kopiowane 1:1).",
        "przyklad": "Wytnij z umowy strony 12–18."
      },
      {
        "id": "pdf_edit_pages",
        "nazwa": "Poukładaj strony PDF",
        "opis": "Edytuje strony PDF: wybór i zmiana kolejności stron, usuwanie stron, obracanie.",
        "przyklad": ""
      },
      {
        "id": "convert_documents",
        "nazwa": "Przekonwertuj dokument",
        "opis": "Konwertuje dokumenty pakietem LibreOffice (DOC/DOCX/ODT/RTF/XLS/XLSX/ODS/CSV/PPT/PPTX/ ODP/HTML/TXT ⇄ PDF, DOCX, ODT, XLSX itd.) oraz grafikę wektorową SVG do PDF/PNG (Inkscape).",
        "przyklad": ""
      },
      {
        "id": "extract_text",
        "nazwa": "Wyciągnij tekst",
        "opis": "Odczytuje tekst z pliku: warstwę tekstową PDF (strona po stronie), dokumenty DOCX/XLSX/PPTX/ODT/RTF/HTML/TXT (Apache Tika).",
        "przyklad": ""
      },
      {
        "id": "view_pages",
        "nazwa": "Pokaż strony",
        "opis": "Pokazuje wybrane strony dokumentu (PDF, DOCX/XLSX/PPTX po konwersji) lub obraz jako podgląd, abyś mógł ocenić treść, układ, jakość albo granice dokumentów.",
        "przyklad": ""
      },
      {
        "id": "write_document",
        "nazwa": "Napisz dokument",
        "opis": "Tworzy plik z treści przygotowanej przez Ciebie: raport, podsumowanie, pismo, zestawienie.",
        "przyklad": "Napisz pismo do ubezpieczyciela w DOCX na podstawie tych dokumentów."
      },
      {
        "id": "translate_document",
        "nazwa": "Przetłumacz dokument",
        "opis": "Tłumaczy dokument na inny język z zachowaniem układu i formatowania:",
        "przyklad": "Przetłumacz tę instrukcję na angielski, zachowaj układ."
      },
      {
        "id": "check_grammar",
        "nazwa": "Sprawdź tekst",
        "opis": "Sprawdza pisownię, gramatykę, interpunkcję i styl (LanguageTool, domyślnie polski).",
        "przyklad": "Sprawdź ten tekst przed wysłaniem."
      },
      {
        "id": "typeset_document",
        "nazwa": "Złóż dokument do druku",
        "opis": "Składa dokument do druku programem Typst: raport, oferta handlowa, CV, broszura, plakat tekstowy albo umowa (paragrafy § i miejsce na podpisy stron).",
        "przyklad": "Złóż z tego ofertę do druku, w jednym stylu i z naszym logo."
      },
      {
        "id": "convert_text_format",
        "nazwa": "Zmień format tekstu",
        "opis": "Przekształca tekst między formatami wydawniczymi programem pandoc:",
        "przyklad": ""
      },
      {
        "id": "analyze_document_structure",
        "nazwa": "Rozbierz dokument na części",
        "opis": "Rozbiera dokument na strukturę programem Docling: nagłówki, akapity w kolejności czytania i tabele odtworzone jako dane.",
        "przyklad": ""
      },
      {
        "id": "read_document_aloud",
        "nazwa": "Przeczytaj dokument na głos",
        "opis": "Czyta cały dokument na głos i zapisuje to jako plik dźwiękowy (głosy Piper, po polsku).",
        "przyklad": "Przeczytaj mi ten raport na głos, posłucham w samochodzie."
      }
    ]
  },
  {
    "id": "wiedza",
    "tytul": "Wiedza i wyszukiwanie",
    "opis": "Własne dokumenty jako pamięć agenta oraz źródła z sieci i z publikacji naukowych.",
    "narzedzia": [
      {
        "id": "index_documents",
        "nazwa": "Dodaj do bazy wiedzy",
        "opis": "Dodaje dokumenty do prywatnej bazy wiedzy (Qdrant), aby można je było później wyszukiwać po treści i znaczeniu.",
        "przyklad": "Dodaj te dokumenty do bazy wiedzy."
      },
      {
        "id": "search_documents",
        "nazwa": "Szukaj w swoich dokumentach",
        "opis": "Wyszukuje semantycznie w prywatnej bazie wiedzy (wszystkie zaindeksowane dokumenty, także z innych rozmów).",
        "przyklad": "Gdzie w moich dokumentach jest mowa o karencji?"
      },
      {
        "id": "knowledge_save",
        "nazwa": "Zapisz źródło",
        "opis": "Zapisuje źródło (stronę, pracę naukową albo tekst) w bazie wiedzy użytkownika – w kolekcji wskazanej id lub nazwą (nieistniejąca kolekcja o podanej nazwie zostanie utworzona).",
        "przyklad": ""
      },
      {
        "id": "knowledge_read",
        "nazwa": "Czytaj bazę wiedzy",
        "opis": "Czyta bazę wiedzy: z source_id – treść źródła (długie czytaj częściami: offset/next_offset), z note_id – notatkę, z collection – spis źródeł i notatek kolekcji, bez parametrów – listę kolekcji.",
        "przyklad": ""
      },
      {
        "id": "knowledge_notes",
        "nazwa": "Notatki w bazie wiedzy",
        "opis": "Notatki w bazie wiedzy: action=add zapisuje notatkę (np. wnioski z badania, streszczenie źródła) w kolekcji, action=list zwraca notatki kolekcji (lub wszystkie), opcjonalnie filtrowane tekstem.",
        "przyklad": ""
      },
      {
        "id": "web_search",
        "nazwa": "Szukaj w sieci",
        "opis": "Wyszukiwarka internetowa Nexusa (SearXNG albo DuckDuckGo): tytuły, adresy i fragmenty wyników.",
        "przyklad": "Znajdź aktualne stawki i podaj źródła."
      },
      {
        "id": "web_fetch_page",
        "nazwa": "Pobierz stronę",
        "opis": "Pobiera stronę WWW (HTML, PDF lub tekst) i zwraca jej czysty tekst z tytułem i metadanymi (opis, witryna, autor, data publikacji, język, adres kanoniczny).",
        "przyklad": ""
      },
      {
        "id": "browser_open",
        "nazwa": "Otwórz stronę w przeglądarce",
        "opis": "Otwiera stronę w przeglądarce i zostawia ją otwartą — kolejne wywołania browser_click, browser_type, browser_scroll i browser_back działają na tej samej karcie.",
        "przyklad": "Wejdź na tę stronę i sprawdź, czy mają jeszcze wolne terminy."
      },
      {
        "id": "browser_click",
        "nazwa": "Kliknij na stronie",
        "opis": "Klika element na otwartej stronie (przycisk, odsyłacz, zakładkę) i zwraca nowy stan strony.",
        "przyklad": ""
      },
      {
        "id": "browser_type",
        "nazwa": "Wypełnij pole na stronie",
        "opis": "Wpisuje tekst w pole na otwartej stronie i (domyślnie) zatwierdza Enterem.",
        "przyklad": "Poszukaj tego na ich stronie i powiedz, co znalazłeś."
      },
      {
        "id": "browser_scroll",
        "nazwa": "Przewiń stronę",
        "opis": "Przewija otwartą stronę i zwraca treść, która po przewinięciu weszła w pole widzenia.",
        "przyklad": ""
      },
      {
        "id": "browser_back",
        "nazwa": "Wróć na poprzednią stronę",
        "opis": "Wraca na poprzednią stronę w otwartej karcie.",
        "przyklad": ""
      },
      {
        "id": "scholar_search",
        "nazwa": "Szukaj publikacji naukowych",
        "opis": "Wyszukuje prace naukowe w OpenAlex, Semantic Scholar, arXiv i Crossref (równolegle), scala duplikaty i zwraca: tytuł, autorów, rok, czasopismo, DOI, abstrakt, liczbę cytowań, link do PDF w otwartym dostępie oraz gotowe cytowanie APA.",
        "przyklad": "Poszukaj publikacji o pompach ciepła w budynkach z lat 90."
      },
      {
        "id": "scholar_paper",
        "nazwa": "Szczegóły publikacji",
        "opis": "Szczegóły pracy naukowej: pełny abstrakt, autorzy, czasopismo, cytowania (także wpływowe), liczba odwołań, TL;DR, dziedziny, słowa kluczowe, link do PDF w otwartym dostępie i cytowanie APA.",
        "przyklad": ""
      }
    ]
  },
  {
    "id": "poczta",
    "tytul": "Poczta i kalendarz",
    "opis": "Czytanie, szukanie i redagowanie wiadomości oraz prowadzenie terminarza.",
    "narzedzia": [
      {
        "id": "mail_list",
        "nazwa": "Przejrzyj pocztę",
        "opis": "Najnowsze wiadomości e-mail użytkownika z folderu (domyślnie Odebrane), lista folderów konta i lista wszystkich kont pocztowych użytkownika. account='wszystkie' przegląda Odebrane wszystkich kont naraz.",
        "przyklad": ""
      },
      {
        "id": "mail_read",
        "nazwa": "Przeczytaj wiadomość",
        "opis": "Czyta wiadomość e-mail (nagłówki, treść tekstowa, lista załączników); opcjonalnie pobiera załączniki do rozmowy.",
        "przyklad": ""
      },
      {
        "id": "mail_search",
        "nazwa": "Znajdź wiadomość",
        "opis": "Wyszukuje wiadomości e-mail po tekście (temat, treść, adresy), nadawcy, zakresie dat i stanie przeczytania.",
        "przyklad": "Znajdź ostatnią wiadomość od księgowej."
      },
      {
        "id": "mail_draft",
        "nazwa": "Przygotuj szkic",
        "opis": "Zapisuje szkic wiadomości e-mail w folderze Szkice skrzynki użytkownika (nie wysyła).",
        "przyklad": "Przygotuj odpowiedź z terminem, który mi pasuje."
      },
      {
        "id": "mail_send",
        "nazwa": "Wyślij wiadomość",
        "opis": "Przygotowuje wiadomość e-mail do wysłania.",
        "przyklad": ""
      },
      {
        "id": "calendar_list",
        "nazwa": "Przejrzyj kalendarz",
        "opis": "Wydarzenia z kalendarza użytkownika (Nextcloud) w zakresie dat, z listą kalendarzy.",
        "przyklad": ""
      },
      {
        "id": "calendar_create",
        "nazwa": "Wpisz wydarzenie",
        "opis": "Dodaje wydarzenie do kalendarza użytkownika (spotkanie, termin, przypomnienie).",
        "przyklad": "Wpisz spotkanie z klientem we wtorek o 10."
      },
      {
        "id": "calendar_update",
        "nazwa": "Zmień wydarzenie",
        "opis": "Zmienia wydarzenie w kalendarzu (tytuł, czas, miejsce, opis, przypomnienie, powtarzanie).",
        "przyklad": ""
      },
      {
        "id": "calendar_delete",
        "nazwa": "Usuń wydarzenie",
        "opis": "Prosi o usunięcie wydarzenia z kalendarza.",
        "przyklad": ""
      }
    ]
  },
  {
    "id": "dzwiek",
    "tytul": "Dźwięk i wideo",
    "opis": "Transkrypcja nagrań, oczyszczanie mowy, rozdzielanie ścieżek, cięcie, montaż filmu ze zdjęć i animacja.",
    "narzedzia": [
      {
        "id": "video_compose",
        "nazwa": "Złóż film ze zdjęć i klipów",
        "opis": "Składa gotowy film ze zdjęć i klipów: filmik promocyjny, zapowiedź, portfolio, rolkę na media społecznościowe.",
        "przyklad": "Złóż z tych dziesięciu zdjęć filmik promocyjny 9:16 z napisami i spokojnym podkładem."
      },
      {
        "id": "audio_compose",
        "nazwa": "Złóż spot albo intro dźwiękowe",
        "opis": "Składa gotowy materiał dźwiękowy: spot radiowy, intro do podcastu, zapowiedź, wiadomość głosową z podkładem.",
        "przyklad": "Zrób spot radiowy: trzy zdania lektora i muzyka w tle."
      },
      {
        "id": "transcribe_audio",
        "nazwa": "Przepisz nagranie",
        "opis": "Zamienia mowę z nagrania audio lub wideo na tekst (Whisper): transkrypcja ze znacznikami czasu, wykrycie języka, napisy SRT/VTT.",
        "przyklad": "Zamień to nagranie w notatkę ze spotkania."
      },
      {
        "id": "transcribe_speakers",
        "nazwa": "Spisz rozmowę z mówcami",
        "opis": "Spisuje rozmowę z podziałem na mówców i z czasem każdego wypowiedzianego słowa (WhisperX).",
        "przyklad": "Spisz tę rozmowę z zaznaczeniem, kto co powiedział."
      },
      {
        "id": "media_process",
        "nazwa": "Przetwórz audio i wideo",
        "opis": "Przetwarza audio i wideo FFmpeg: konwersja formatu, wyodrębnienie ścieżki audio, wycięcie fragmentu, kompresja i zmiana rozdzielczości wideo, normalizacja głośności (EBU R128), klatka podglądu.",
        "przyklad": "Wytnij z nagrania fragment 00:30–02:00 i zapisz jako MP3."
      },
      {
        "id": "clean_audio",
        "nazwa": "Oczyść nagranie",
        "opis": "Usuwa z nagrania mowy szum, wiatr, brum i pogłos (DeepFilterNet 3).",
        "przyklad": "To nagranie jest zaszumione — wyczyść je przed spisaniem."
      },
      {
        "id": "split_audio_tracks",
        "nazwa": "Rozdziel ścieżki utworu",
        "opis": "Rozdziela nagranie muzyczne na osobne ścieżki (Demucs): wokal, perkusja, bas i reszta — albo sam wokal i podkład.",
        "przyklad": "Wyciągnij z tego utworu sam wokal."
      },
      {
        "id": "edit_subtitles",
        "nazwa": "Popraw napisy",
        "opis": "Poprawia gotowy plik napisów SRT: przesuwa czasy o stałą wartość, rozciąga je liniowo, gdy napisy rozjeżdżają się do końca filmu, łączy dwie wersje językowe w jeden plik, usuwa powtórzone kwestie i naprawia uszkodzony zapis.",
        "przyklad": ""
      },
      {
        "id": "video_to_gif",
        "nazwa": "Zrób GIF z filmu",
        "opis": "Składa GIF z fragmentu filmu w jakości, jakiej nie daje zwykła konwersja: klatki idą z FFmpeg, a barwy dobiera gifski osobno dla każdej klatki.",
        "przyklad": "Zrób GIF-a z fragmentu 00:10–00:15 tego filmu."
      },
      {
        "id": "animate_explainer",
        "nazwa": "Zrób animację wyjaśniającą",
        "opis": "Renderuje animację wyjaśniającą z opisanej sceny (silnik Manim): rysujący się wykres, przekształcający się wzór, schemat wchodzący element po elemencie, oś czasu, porównanie.",
        "przyklad": "Wytłumacz mi na animacji, jak działa procent składany."
      }
    ]
  },
  {
    "id": "strony",
    "tytul": "Strony internetowe",
    "opis": "Tworzenie i publikowanie stron z poziomu rozmowy, z wersjami i wycofaniem.",
    "narzedzia": [
      {
        "id": "site_kit_catalog",
        "nazwa": "Przejrzyj wzory witryn",
        "opis": "Co zestaw Danaco Web Kit ma do zaoferowania przy budowie witryny: presety branżowe (gotowa struktura i treści), motywy, kroje nagłówkowe, gotowe sekcje z nazwami i opisami, szablony aplikacji oraz kolekcja szablonów otwartych.",
        "przyklad": "Pokaż, jakie masz wzory stron dla restauracji."
      },
      {
        "id": "site_from_kit",
        "nazwa": "Zbuduj witrynę z wzoru",
        "opis": "Buduje kompletną witrynę z zestawu Danaco Web Kit i wstawia ją do szkicu strony użytkownika.",
        "przyklad": "Zrób stronę dla mojej kancelarii — poważną, z cennikiem i kontaktem."
      },
      {
        "id": "site_from_template",
        "nazwa": "Witryna z gotowego szablonu",
        "opis": "Wstawia do szkicu strony użytkownika gotową, już zbudowaną witrynę z kolekcji szablonów otwartych (81 pozycji z gotową witryną: blogi, portfolio, dokumentacja, panele, landingi, sklepy, strony wydarzeń).",
        "przyklad": "Weź ten gotowy szablon bloga i zrób z niego moją stronę."
      },
      {
        "id": "asset_to_site",
        "nazwa": "Materiał na stronę",
        "opis": "Wstawia materiał z biblioteki serwera do szkicu strony użytkownika: ilustrację, wzór tła, plik animowanego tła, dźwięk.",
        "przyklad": "Wstaw na stronę animowane tło zamiast płaskiego koloru."
      },
      {
        "id": "site_fonts_local",
        "nazwa": "Kroje strony z serwera",
        "opis": "Przenosi kroje strony z serwerów Google na serwer Danaco: wycina z lokalnego repozytorium podzbiór z polskimi znakami, wkłada pliki .woff2 do szkicu strony, dopisuje arkusz `kroje/kroje.css` i podmienia odsyłacze do fonts.googleapis.com na własny arkusz (usuwając przy okazji `preconnect` do Google).",
        "przyklad": "Przenieś kroje mojej strony z Google na nasz serwer."
      },
      {
        "id": "site_vendor_assets",
        "nazwa": "Zasoby strony z naszego serwera",
        "opis": "Ściąga do strony użytkownika pliki, które wczytuje ona z cudzych serwerów (skrypty i arkusze z CDN-ów, zdjęcia ze stocków), i podmienia odwołania na własne.",
        "przyklad": "Ściągnij na nasz serwer wszystko, co strona bierze z obcych serwerów."
      },
      {
        "id": "site_list",
        "nazwa": "Twoje strony",
        "opis": "Lista stron WWW użytkownika albo – z podanym adresem – lista plików szkicu strony (ścieżki, rozmiary, stan publikacji i wersje).",
        "przyklad": ""
      },
      {
        "id": "site_read_file",
        "nazwa": "Odczytaj plik strony",
        "opis": "Odczytuje plik tekstowy szkicu strony (HTML, CSS, JS, JSON, SVG…) przed jego zmianą.",
        "przyklad": ""
      },
      {
        "id": "site_write_file",
        "nazwa": "Zapisz plik strony",
        "opis": "Zapisuje (tworzy albo zastępuje w całości) plik tekstowy szkicu strony:",
        "przyklad": ""
      },
      {
        "id": "site_import_file",
        "nazwa": "Dodaj plik do strony",
        "opis": "Kopiuje plik z rozmowy (obraz, logo, czcionkę, wideo, PDF) do szkicu strony pod podaną ścieżką, aby można go było użyć w HTML/CSS (np. <img src=\"img/logo.png\">).",
        "przyklad": ""
      },
      {
        "id": "site_delete_file",
        "nazwa": "Usuń plik strony",
        "opis": "Usuwa plik ze szkicu strony.",
        "przyklad": ""
      },
      {
        "id": "site_save_version",
        "nazwa": "Zapisz wersję strony",
        "opis": "Zapisuje bieżący szkic strony jako wersję (użytkownik może do niej wrócić w module Strony).",
        "przyklad": ""
      },
      {
        "id": "site_publish",
        "nazwa": "Opublikuj stronę",
        "opis": "Zgłasza prośbę o publikację strony pod publicznym adresem /s/<adres>/.",
        "przyklad": "Opublikuj tę stronę pod moim adresem."
      },
      {
        "id": "site_unpublish",
        "nazwa": "Wycofaj publikację",
        "opis": "Wycofuje publikację strony – adres publiczny przestaje działać (szkic i wersje zostają).",
        "przyklad": ""
      },
      {
        "id": "web_audit",
        "nazwa": "Zbadaj stronę WWW",
        "opis": "Bada gotową stronę WWW: dostępność według WCAG 2.1 AA (pa11y: brak opisów obrazów, za słaby kontrast, pola bez etykiet) oraz szybkość, dobre praktyki i SEO (Lighthouse, oceny 0–100).",
        "przyklad": "Sprawdź, czy moja strona nie ma błędów dostępności."
      },
      {
        "id": "web_screenshot",
        "nazwa": "Zrób zrzut strony",
        "opis": "Robi zrzut strony WWW w przeglądarce (Playwright) i pokazuje go w rozmowie — szkicu z modułu Strony albo publicznego adresu, w szerokości telefonu, tabletu lub komputera, w trybie jasnym lub ciemnym.",
        "przyklad": ""
      },
      {
        "id": "site_optimize_assets",
        "nazwa": "Odchudź pliki strony",
        "opis": "Odchudza pliki graficzne w szkicu strony bez zmiany wyglądu:",
        "przyklad": ""
      }
    ]
  },
  {
    "id": "pliki",
    "tytul": "Pliki i chmura",
    "opis": "Porządek w plikach: przegląd, archiwa i prywatna chmura zamiast cudzego dysku.",
    "narzedzia": [
      {
        "id": "inspect_files",
        "nazwa": "Sprawdź pliki",
        "opis": "Sprawdza pliki: typ, rozmiar, liczbę stron, obecność warstwy tekstowej PDF, wymiary i metryki jakości obrazów (jasność, kontrast, ostrość, szum, zafarb, pochylenie tekstu), parametry audio/wideo i zawartość archiwów ZIP.",
        "przyklad": ""
      },
      {
        "id": "create_archive",
        "nazwa": "Spakuj pliki",
        "opis": "Pakuje wskazane pliki do archiwum ZIP (np. wszystkie wyniki zadania do pobrania naraz).",
        "przyklad": "Spakuj te pliki do jednego archiwum."
      },
      {
        "id": "extract_archive",
        "nazwa": "Rozpakuj archiwum",
        "opis": "Rozpakowuje archiwum ZIP; każdy plik staje się osobnym plikiem rozmowy, który możesz dalej przetwarzać (np. OCR wsadowy dokumentów z archiwum).",
        "przyklad": ""
      },
      {
        "id": "cloud_browse",
        "nazwa": "Przejrzyj chmurę",
        "opis": "Wyświetla zawartość katalogu w chmurze osobistej użytkownika (Nextcloud): podkatalogi i pliki z rozmiarem i datą zmiany.",
        "przyklad": ""
      },
      {
        "id": "cloud_import",
        "nazwa": "Pobierz z chmury",
        "opis": "Pobiera pliki z chmury osobistej do rozmowy (każdy plik dostaje file_id do dalszej obróbki).",
        "przyklad": ""
      },
      {
        "id": "cloud_save",
        "nazwa": "Zapisz w chmurze",
        "opis": "Zapisuje pliki rozmowy (np. wyniki OCR, poprawione zdjęcia) w chmurze osobistej użytkownika, we wskazanym katalogu.",
        "przyklad": "Zapisz wynik w mojej chmurze, w katalogu Faktury."
      }
    ]
  },
  {
    "id": "aplikacje",
    "tytul": "Aplikacje i kod",
    "opis": "Gotowe aplikacje webowe z serwera — panel, landing, sklep — przebrane w Twoją markę, plus kontrola jakości kodu projektu.",
    "narzedzia": [
      {
        "id": "app_templates",
        "nazwa": "Gotowe aplikacje serwera",
        "opis": "Wykaz gotowych aplikacji webowych leżących na serwerze — 35 pozycji: panele administracyjne, dashboardy, landingi i strony produktowe na React, Vue, Next, Nuxt, Astro, Bootstrap i Tailwindzie.",
        "przyklad": "Jakie gotowe aplikacje masz na serwerze?"
      },
      {
        "id": "app_from_template",
        "nazwa": "Załóż aplikację z szablonu",
        "opis": "Zakłada nowy projekt w module Kod z gotowego szablonu aplikacji (spis: app_templates).",
        "przyklad": "Załóż mi panel zamówień z gotowego szablonu i przebierz go w moją markę."
      },
      {
        "id": "code_check",
        "nazwa": "Sprawdź jakość kodu",
        "opis": "Kontroluje jakość kodu: podatności i pułapki (semgrep), klucze i hasła wpisane wprost w kod (gitleaks), znane podatności bibliotek projektu (osv-scanner), skopiowane fragmenty (jscpd), błędy Pythona (ruff), błędy skryptów powłoki (shellcheck), literówki (typos).",
        "przyklad": "Przejrzyj ten projekt pod kątem błędów i podatności."
      }
    ]
  },
  {
    "id": "komputer",
    "tytul": "Twój komputer",
    "opis": "Nexus sięga do komputera, gdy zgodzisz się na połączenie: znajduje pliki, robi zrzut, wykonuje polecenie.",
    "narzedzia": [
      {
        "id": "pc_info",
        "nazwa": "Stan komputera",
        "opis": "Stan komputera użytkownika z Nexus Desktop (Windows): system, procesor, pamięć RAM (zajęta/wolna), dyski (wolne miejsce), czas pracy i procesy zużywające najwięcej pamięci.",
        "przyklad": ""
      },
      {
        "id": "pc_find_files",
        "nazwa": "Znajdź plik na komputerze",
        "opis": "Wyszukuje pliki na komputerze użytkownika (Nexus Desktop) po nazwie i/lub treści w katalogach użytkownika (Pulpit, Dokumenty, Pobrane, OneDrive…) albo wskazanych katalogach.",
        "przyklad": "Znajdź na moim komputerze umowę najmu z zeszłego roku."
      },
      {
        "id": "pc_read_file",
        "nazwa": "Podejrzyj plik na komputerze",
        "opis": "Podgląd pliku lub katalogu na komputerze użytkownika (Nexus Desktop): tekst pliku, obraz jako podgląd, zawartość katalogu, metadane.",
        "przyklad": ""
      },
      {
        "id": "pc_screenshot",
        "nazwa": "Zrzut ekranu komputera",
        "opis": "Zrzut ekranu komputera użytkownika (Nexus Desktop): cały ekran albo okno aktywne przed otwarciem Nexusa.",
        "przyklad": "Zrób zrzut mojego ekranu i powiedz, co jest nie tak."
      },
      {
        "id": "pc_powershell",
        "nazwa": "Wykonaj polecenie",
        "opis": "Wykonuje polecenie Windows PowerShell na komputerze użytkownika (Nexus Desktop): diagnoza i naprawy (miejsce na dysku, pamięć, usługi, sieć, dziennik zdarzeń, pliki tymczasowe).",
        "przyklad": ""
      }
    ]
  }
];

export const LICZBA_NARZEDZI = 101;
