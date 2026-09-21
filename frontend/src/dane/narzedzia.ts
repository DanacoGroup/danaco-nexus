// Katalog narzędzi agenta. Wynik frontend/scripts/narzedzia.py — nie edytować ręcznie.
// Źródło prawdy: rejestr backend/nexus/tools (ten sam, z którego korzysta serwer MCP).

export type Narzedzie = { id: string; nazwa: string; opis: string; przyklad: string };
export type DziedzinaNarzedzi = { id: string; tytul: string; opis: string; narzedzia: Narzedzie[] };

export const DZIEDZINY: DziedzinaNarzedzi[] = [
  {
    "id": "projekt",
    "tytul": "Projektowanie grafiki",
    "opis": "Logo, plakat, ulotka, ikona, baner i post powstają od zera, w rozmowie. Dostajesz plik wektorowy do dalszej edycji i PDF gotowy do druku.",
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
        "opis": "Znajduje gotową ikonę i wstawia ją do projektu albo do strony.",
        "przyklad": "Wstaw tu ikonę koperty w tym samym stylu co reszta."
      },
      {
        "id": "render_lottie",
        "nazwa": "Zamień animację Lottie",
        "opis": "Zamienia gotową animację z sieci albo z pakietu graficznego w zwykły film lub obrazek.",
        "przyklad": "Zrób z tej animacji zwykły film, żeby dało się ją wstawić na stronę."
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
        "opis": "Pokazuje, jakie gotowe materiały leżą na serwerze, zanim zaczniesz szukać ich w sieci.",
        "przyklad": "Pokaż, jakie masz ilustracje i tła do strony."
      }
    ]
  },
  {
    "id": "zdjecia",
    "tytul": "Zdjęcia i obrazy",
    "opis": "Zdjęcie wraca poprawione, powiększone albo bez tła. Niczego nie instalujesz i nie uczysz się programu graficznego.",
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
        "opis": "Odtwarza twarze na zdjęciu zniszczonym, rozmytym, drobnym albo mocno skompresowanym.",
        "przyklad": "Twarze na tym starym zdjęciu rozmyły się — odtwórz je."
      },
      {
        "id": "upscale_image",
        "nazwa": "Powiększ obraz",
        "opis": "Powiększa zdjęcie i dorysowuje szczegóły, zamiast rozmywać piksele.",
        "przyklad": "Powiększ ten skan czterokrotnie, ma iść do druku."
      },
      {
        "id": "colorize_photo",
        "nazwa": "Pokoloruj czarno-białe",
        "opis": "Nadaje barwy zdjęciu czarno-białemu albo sepiowemu.",
        "przyklad": "Pokoloruj to zdjęcie dziadków z lat 50."
      },
      {
        "id": "remove_background",
        "nazwa": "Wytnij z tła",
        "opis": "Usuwa tło ze zdjęcia i zostawia sam obiekt na przezroczystym tle.",
        "przyklad": "Wytnij produkt z tła i zapisz z przezroczystością."
      },
      {
        "id": "change_background",
        "nazwa": "Zmień tło zdjęcia",
        "opis": "Podmienia tło zdjęcia na jednolity kolor, gradient, inne zdjęcie albo rozmycie jak w portrecie.",
        "przyklad": "Zamień tło na jednolite szare jak w studiu."
      },
      {
        "id": "erase_objects",
        "nazwa": "Wymaż obiekt",
        "opis": "Wymazuje ze zdjęcia napis, znak wodny, przewód albo przypadkową osobę.",
        "przyklad": "Usuń przechodnia z lewej strony kadru."
      },
      {
        "id": "inpaint_photo",
        "nazwa": "Usuń duży element",
        "opis": "Usuwa ze zdjęcia duży element i dorysowuje to, co było za nim.",
        "przyklad": "Usuń ten samochód z lewej strony zdjęcia."
      },
      {
        "id": "blur_background_by_depth",
        "nazwa": "Rozmyj tło jak obiektyw",
        "opis": "Rozmywa tło zdjęcia tak, jak robi to jasny obiektyw.",
        "przyklad": "Rozmyj tło tak, żeby wyglądało jak z lustrzanki."
      },
      {
        "id": "depth_map",
        "nazwa": "Policz mapę głębi",
        "opis": "Liczy, jak daleko od aparatu leży każdy punkt zdjęcia.",
        "przyklad": "Policz, co jest na tym zdjęciu bliżej, a co dalej — potrzebuję maski pierwszego planu."
      },
      {
        "id": "animate_photo",
        "nazwa": "Ożyw zdjęcie filmem",
        "opis": "Zamienia zdjęcie w krótki film, w którym kamera przesuwa się nad kadrem.",
        "przyklad": "Zrób z tego zdjęcia krótki film na Instagram."
      },
      {
        "id": "find_faces",
        "nazwa": "Znajdź osoby na zdjęciach",
        "opis": "Znajduje twarze na zdjęciach i — na życzenie — układa razem zdjęcia tej samej osoby.",
        "przyklad": "Rozdziel te dwieście zdjęć z wesela według osób."
      },
      {
        "id": "convert_images",
        "nazwa": "Przekonwertuj obraz",
        "opis": "Zamienia obrazy na inny format i na życzenie składa je w jeden PDF.",
        "przyklad": "Zamień te zdjęcia na PNG i złóż je w jeden PDF."
      },
      {
        "id": "imagemagick",
        "nazwa": "Obróbka na życzenie",
        "opis": "Wykonuje na obrazie obróbkę, której nie obejmuje żadne inne narzędzie: przycięcie, obramowanie, sepię, zmianę rozmiaru, korektę barw.",
        "przyklad": "Przytnij to zdjęcie do kwadratu i dodaj białą ramkę."
      }
    ]
  },
  {
    "id": "dokumenty",
    "tytul": "Dokumenty i PDF",
    "opis": "Stos skanów, umów i faktur zamienia się w tekst, w którym da się szukać. Dokumenty rozdzielisz, złożysz na nowo i wyciągniesz z nich dane.",
    "narzedzia": [
      {
        "id": "ocr_documents",
        "nazwa": "Rozpoznaj tekst ze skanu",
        "opis": "Rozpoznaje tekst w skanach PDF i na zdjęciach dokumentów, także po polsku.",
        "przyklad": "Rozpoznaj tekst z tych skanów i zrób przeszukiwalny PDF."
      },
      {
        "id": "enhance_document_scan",
        "nazwa": "Popraw skan",
        "opis": "Doprowadza skan albo zdjęcie dokumentu do postaci, z której da się czytać i rozpoznawać tekst.",
        "przyklad": "Ten skan jest krzywy i szary — wyprostuj go i wybiel tło."
      },
      {
        "id": "detect_document_boundaries",
        "nazwa": "Rozdziel stos skanów",
        "opis": "Znajduje w jednym PDF granice między dokumentami, gdy w stosie skanów leży kilka pism naraz.",
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
        "opis": "Dzieli PDF na osobne pliki według zakresów stron, bez utraty jakości.",
        "przyklad": "Wytnij z umowy strony 12–18."
      },
      {
        "id": "pdf_edit_pages",
        "nazwa": "Poukładaj strony PDF",
        "opis": "Porządkuje strony w PDF: zmienia ich kolejność, usuwa zbędne i obraca te położone bokiem.",
        "przyklad": "Usuń z tego PDF-u puste strony i obróć te położone bokiem."
      },
      {
        "id": "convert_documents",
        "nazwa": "Przekonwertuj dokument",
        "opis": "Zamienia dokument na inny format: na PDF, do edytora tekstu, do arkusza albo do prezentacji.",
        "przyklad": "Zamień ten dokument Worda na PDF."
      },
      {
        "id": "extract_text",
        "nazwa": "Wyciągnij tekst",
        "opis": "Wyciąga z pliku sam tekst, bez układu i grafiki.",
        "przyklad": "Wyciągnij z tego PDF-u sam tekst."
      },
      {
        "id": "view_pages",
        "nazwa": "Pokaż strony",
        "opis": "Pokazuje wybrane strony dokumentu albo obraz, żeby dało się ocenić treść, układ i jakość.",
        "przyklad": "Pokaż mi strony 3–5 tego dokumentu."
      },
      {
        "id": "write_document",
        "nazwa": "Napisz dokument",
        "opis": "Zapisuje przygotowaną treść jako gotowy plik: raport, podsumowanie, pismo, zestawienie.",
        "przyklad": "Napisz pismo do ubezpieczyciela w DOCX na podstawie tych dokumentów."
      },
      {
        "id": "translate_document",
        "nazwa": "Przetłumacz dokument",
        "opis": "Tłumaczy dokument na inny język i zostawia układ na miejscu.",
        "przyklad": "Przetłumacz tę instrukcję na angielski, zachowaj układ."
      },
      {
        "id": "check_grammar",
        "nazwa": "Sprawdź tekst",
        "opis": "Sprawdza polską pisownię, gramatykę, interpunkcję i styl, zanim tekst pójdzie dalej.",
        "przyklad": "Sprawdź ten tekst przed wysłaniem."
      },
      {
        "id": "typeset_document",
        "nazwa": "Złóż dokument do druku",
        "opis": "Składa dokument do druku tak, żeby wyglądał zawodowo, a nie jak wydruk z edytora tekstu.",
        "przyklad": "Złóż z tego ofertę do druku, w jednym stylu i z naszym logo."
      },
      {
        "id": "convert_text_format",
        "nazwa": "Zmień format tekstu",
        "opis": "Zamienia tekst w książkę do czytnika, plik dla wydawnictwa albo czysty zapis do dalszej pracy.",
        "przyklad": "Zrób z tego tekstu e-booka do czytnika."
      },
      {
        "id": "analyze_document_structure",
        "nazwa": "Rozbierz dokument na części",
        "opis": "Rozbiera dokument na części i odtwarza z niego tabele jako dane, a nie jako obrazek.",
        "przyklad": "Wyciągnij z tej umowy tabelę z terminami, nie sam tekst."
      },
      {
        "id": "read_document_aloud",
        "nazwa": "Przeczytaj dokument na głos",
        "opis": "Czyta cały dokument na głos po polsku i zapisuje to jako plik dźwiękowy.",
        "przyklad": "Przeczytaj mi ten raport na głos, posłucham w samochodzie."
      }
    ]
  },
  {
    "id": "wiedza",
    "tytul": "Wiedza i wyszukiwanie",
    "opis": "Pytasz własnymi słowami, a odpowiedź przychodzi z Twoich dokumentów, ze stron i z publikacji naukowych — razem z adresem źródła.",
    "narzedzia": [
      {
        "id": "index_documents",
        "nazwa": "Dodaj do bazy wiedzy",
        "opis": "Dodaje dokumenty do prywatnej bazy wiedzy, żeby dało się w nich szukać własnymi słowami.",
        "przyklad": "Dodaj te dokumenty do bazy wiedzy."
      },
      {
        "id": "search_documents",
        "nazwa": "Szukaj w swoich dokumentach",
        "opis": "Znajduje w Twoich dokumentach odpowiedź na pytanie zadane własnymi słowami.",
        "przyklad": "Gdzie w moich dokumentach jest mowa o karencji?"
      },
      {
        "id": "knowledge_save",
        "nazwa": "Zapisz źródło",
        "opis": "Odkłada stronę, pracę naukową albo własny tekst do bazy wiedzy, w wybranej kolekcji.",
        "przyklad": "Zapisz tę stronę w kolekcji Dotacje."
      },
      {
        "id": "knowledge_read",
        "nazwa": "Czytaj bazę wiedzy",
        "opis": "Otwiera to, co leży w bazie wiedzy: zapisane źródło, notatkę, spis kolekcji albo jej zawartość.",
        "przyklad": "Pokaż, co mam zebrane w kolekcji Dotacje."
      },
      {
        "id": "knowledge_notes",
        "nazwa": "Notatki w bazie wiedzy",
        "opis": "Dopisuje własne wnioski do kolekcji w bazie wiedzy i oddaje je na żądanie.",
        "przyklad": "Dopisz do tej kolekcji notatkę z wnioskami z dzisiejszego czytania."
      },
      {
        "id": "web_search",
        "nazwa": "Szukaj w sieci",
        "opis": "Szuka w sieci i zwraca tytuły, adresy oraz fragmenty wyników.",
        "przyklad": "Znajdź aktualne stawki i podaj źródła."
      },
      {
        "id": "web_fetch_page",
        "nazwa": "Pobierz stronę",
        "opis": "Pobiera stronę i oddaje jej czysty tekst razem z tytułem, autorem i datą publikacji.",
        "przyklad": "Przeczytaj tę stronę i powiedz, co z niej wynika."
      },
      {
        "id": "browser_open",
        "nazwa": "Otwórz stronę w przeglądarce",
        "opis": "Otwiera stronę w przeglądarce i zostawia ją otwartą, żeby dało się na niej klikać i pisać.",
        "przyklad": "Wejdź na tę stronę i sprawdź, czy mają jeszcze wolne terminy."
      },
      {
        "id": "browser_click",
        "nazwa": "Kliknij na stronie",
        "opis": "Klika element na otwartej stronie (przycisk, odsyłacz, zakładkę) i zwraca nowy stan strony.",
        "przyklad": "Kliknij przycisk Dalej i pokaż, co się pojawiło."
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
        "przyklad": "Przewiń niżej i sprawdź, czy jest tam cennik."
      },
      {
        "id": "browser_back",
        "nazwa": "Wróć na poprzednią stronę",
        "opis": "Wraca na poprzednią stronę w otwartej karcie.",
        "przyklad": "Wróć na poprzednią stronę."
      },
      {
        "id": "scholar_search",
        "nazwa": "Szukaj publikacji naukowych",
        "opis": "Przeszukuje cztery bazy publikacji naukowych naraz i scala powtórzone pozycje.",
        "przyklad": "Poszukaj publikacji o pompach ciepła w budynkach z lat 90."
      },
      {
        "id": "scholar_paper",
        "nazwa": "Szczegóły publikacji",
        "opis": "Pokazuje wszystko, co wiadomo o jednej pracy naukowej, razem z gotowym przypisem.",
        "przyklad": "Pokaż szczegóły tej pracy i gotowy przypis."
      }
    ]
  },
  {
    "id": "poczta",
    "tytul": "Poczta i kalendarz",
    "opis": "Skrzynka i terminarz stoją w tym samym oknie co reszta pracy. Odpowiedź przygotowuje Nexus, wysyłasz ją Ty.",
    "narzedzia": [
      {
        "id": "mail_list",
        "nazwa": "Przejrzyj pocztę",
        "opis": "Pokazuje najnowsze wiadomości z wybranego folderu, a także foldery i konta pocztowe.",
        "przyklad": "Co przyszło dziś na skrzynkę?"
      },
      {
        "id": "mail_read",
        "nazwa": "Przeczytaj wiadomość",
        "opis": "Otwiera wiadomość i pokazuje nadawcę, temat, treść oraz listę załączników.",
        "przyklad": "Otwórz ostatnią wiadomość od biura i powiedz, czego dotyczy."
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
        "opis": "Zapisuje szkic odpowiedzi w folderze Szkice Twojej skrzynki.",
        "przyklad": "Przygotuj odpowiedź z terminem, który mi pasuje."
      },
      {
        "id": "mail_send",
        "nazwa": "Wyślij wiadomość",
        "opis": "Przygotowuje wiadomość, którą wysyłasz sam jednym przyciskiem.",
        "przyklad": "Wyślij tę odpowiedź do klienta."
      },
      {
        "id": "calendar_list",
        "nazwa": "Przejrzyj kalendarz",
        "opis": "Pokazuje wydarzenia z wybranego zakresu dat razem z listą Twoich kalendarzy.",
        "przyklad": "Co mam w kalendarzu w przyszłym tygodniu?"
      },
      {
        "id": "calendar_create",
        "nazwa": "Wpisz wydarzenie",
        "opis": "Dodaje do kalendarza spotkanie, termin albo przypomnienie.",
        "przyklad": "Wpisz spotkanie z klientem we wtorek o 10."
      },
      {
        "id": "calendar_update",
        "nazwa": "Zmień wydarzenie",
        "opis": "Zmienia wydarzenie w kalendarzu (tytuł, czas, miejsce, opis, przypomnienie, powtarzanie).",
        "przyklad": "Przesuń spotkanie z czwartku na piątek na 14."
      },
      {
        "id": "calendar_delete",
        "nazwa": "Usuń wydarzenie",
        "opis": "Usuwa wydarzenie z kalendarza po Twoim zatwierdzeniu.",
        "przyklad": "Usuń z kalendarza odwołane szkolenie."
      }
    ]
  },
  {
    "id": "dzwiek",
    "tytul": "Dźwięk i wideo",
    "opis": "Nagranie wraca jako tekst z napisami i podziałem na mówców. Ze zdjęć i klipów powstaje gotowy film, a z opisu — animacja.",
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
        "opis": "Zamienia mowę z nagrania audio albo wideo w tekst ze znacznikami czasu.",
        "przyklad": "Zamień to nagranie w notatkę ze spotkania."
      },
      {
        "id": "transcribe_speakers",
        "nazwa": "Spisz rozmowę z mówcami",
        "opis": "Spisuje rozmowę z zaznaczeniem, kto co powiedział, i z czasem każdego słowa.",
        "przyklad": "Spisz tę rozmowę z zaznaczeniem, kto co powiedział."
      },
      {
        "id": "media_process",
        "nazwa": "Przetwórz audio i wideo",
        "opis": "Tnie, konwertuje i odchudza nagrania dźwiękowe oraz filmy.",
        "przyklad": "Wytnij z nagrania fragment 00:30–02:00 i zapisz jako MP3."
      },
      {
        "id": "clean_audio",
        "nazwa": "Oczyść nagranie",
        "opis": "Usuwa z nagrania mowy szum, wiatr, brum i pogłos.",
        "przyklad": "W tym nagraniu słychać szum — wyczyść je przed spisaniem."
      },
      {
        "id": "split_audio_tracks",
        "nazwa": "Rozdziel ścieżki utworu",
        "opis": "Rozdziela nagranie muzyczne na osobne ścieżki: wokal, perkusja, bas i reszta albo sam wokal i podkład.",
        "przyklad": "Wyciągnij z tego utworu sam wokal."
      },
      {
        "id": "edit_subtitles",
        "nazwa": "Popraw napisy",
        "opis": "Naprawia gotowy plik napisów SRT, gdy rozjeżdżają się z obrazem albo mają uszkodzony zapis.",
        "przyklad": "Te napisy spóźniają się o dwie sekundy — popraw czasy."
      },
      {
        "id": "video_to_gif",
        "nazwa": "Zrób GIF z filmu",
        "opis": "Składa GIF z fragmentu filmu w jakości, jakiej nie daje zwykła konwersja.",
        "przyklad": "Zrób GIF-a z fragmentu 00:10–00:15 tego filmu."
      },
      {
        "id": "animate_explainer",
        "nazwa": "Zrób animację wyjaśniającą",
        "opis": "Robi krótką animację, która tłumaczy rzecz trudną do opisania słowami.",
        "przyklad": "Wytłumacz mi na animacji, jak działa procent składany."
      }
    ]
  },
  {
    "id": "strony",
    "tytul": "Strony internetowe",
    "opis": "Opisujesz stronę, oglądasz szkic i sam zatwierdzasz publikację. Każdą wersję da się zapisać i cofnąć.",
    "narzedzia": [
      {
        "id": "site_kit_catalog",
        "nazwa": "Przejrzyj wzory witryn",
        "opis": "Pokazuje, z czego można zbudować witrynę, zanim powstanie pierwsza strona.",
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
        "opis": "Wstawia do Twojego szkicu gotową, już zbudowaną witrynę z kolekcji szablonów otwartych.",
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
        "opis": "Przenosi kroje pisma Twojej strony z serwerów Google na serwer Danaco.",
        "przyklad": "Przenieś kroje mojej strony z Google na nasz serwer."
      },
      {
        "id": "site_vendor_assets",
        "nazwa": "Zasoby strony z naszego serwera",
        "opis": "Ściąga na nasz serwer wszystko, co Twoja strona bierze z cudzych serwerów.",
        "przyklad": "Ściągnij na nasz serwer wszystko, co strona bierze z obcych serwerów."
      },
      {
        "id": "site_list",
        "nazwa": "Twoje strony",
        "opis": "Pokazuje Twoje strony, a dla wskazanego adresu — pliki jej szkicu.",
        "przyklad": "Pokaż moje strony i stan ich publikacji."
      },
      {
        "id": "site_read_file",
        "nazwa": "Odczytaj plik strony",
        "opis": "Odczytuje plik tekstowy szkicu strony (HTML, CSS, JS, JSON, SVG…) przed jego zmianą.",
        "przyklad": "Pokaż, co jest teraz na stronie kontaktowej."
      },
      {
        "id": "site_write_file",
        "nazwa": "Zapisz plik strony",
        "opis": "Zapisuje plik szkicu strony — tworzy nowy albo zastępuje istniejący w całości.",
        "przyklad": "Zmień tekst na stronie głównej na ten nowy."
      },
      {
        "id": "site_import_file",
        "nazwa": "Dodaj plik do strony",
        "opis": "Wkłada do strony plik z rozmowy: zdjęcie, logo, krój pisma, film albo PDF.",
        "przyklad": "Wstaw moje logo na stronę."
      },
      {
        "id": "site_delete_file",
        "nazwa": "Usuń plik strony",
        "opis": "Usuwa plik ze szkicu strony.",
        "przyklad": "Usuń ze strony niepotrzebną podstronę z cennikiem."
      },
      {
        "id": "site_save_version",
        "nazwa": "Zapisz wersję strony",
        "opis": "Zapisuje bieżący szkic strony jako wersję (użytkownik może do niej wrócić w module Strony).",
        "przyklad": "Zapisz obecną wersję strony, zanim zacznę zmieniać układ."
      },
      {
        "id": "site_publish",
        "nazwa": "Opublikuj stronę",
        "opis": "Wystawia stronę pod publicznym adresem /s/<adres>/ po Twoim zatwierdzeniu.",
        "przyklad": "Opublikuj tę stronę pod moim adresem."
      },
      {
        "id": "site_unpublish",
        "nazwa": "Wycofaj publikację",
        "opis": "Wycofuje publikację strony – adres publiczny przestaje działać (szkic i wersje zostają).",
        "przyklad": "Zdejmij tę stronę z sieci."
      },
      {
        "id": "web_audit",
        "nazwa": "Zbadaj stronę WWW",
        "opis": "Sprawdza gotową stronę pod kątem dostępności, szybkości i widoczności w wyszukiwarkach.",
        "przyklad": "Sprawdź, czy moja strona nie ma błędów dostępności."
      },
      {
        "id": "web_screenshot",
        "nazwa": "Zrób zrzut strony",
        "opis": "Robi zrzut strony i pokazuje go w rozmowie, zamiast zgadywać, jak strona wygląda.",
        "przyklad": "Pokaż, jak moja strona wygląda na telefonie."
      },
      {
        "id": "site_optimize_assets",
        "nazwa": "Odchudź pliki strony",
        "opis": "Odchudza pliki graficzne strony, nie zmieniając jej wyglądu.",
        "przyklad": "Strona wolno się ładuje — odchudź zdjęcia."
      }
    ]
  },
  {
    "id": "pliki",
    "tytul": "Pliki i chmura",
    "opis": "Pliki zadania idą do archiwum albo do Twojej chmury osobistej, nie na cudzy dysk. Widzisz je potem także na telefonie.",
    "narzedzia": [
      {
        "id": "inspect_files",
        "nazwa": "Sprawdź pliki",
        "opis": "Mówi, co jest w pliku i w jakim jest stanie, zanim zacznie się obróbka.",
        "przyklad": "Sprawdź, czy w tym PDF-ie jest tekst, czy sam skan."
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
        "opis": "Rozpakowuje archiwum ZIP i wkłada każdy plik osobno do rozmowy.",
        "przyklad": "Rozpakuj to archiwum i rozpoznaj tekst we wszystkich skanach."
      },
      {
        "id": "cloud_browse",
        "nazwa": "Przejrzyj chmurę",
        "opis": "Pokazuje, co leży w katalogu Twojej chmury osobistej: podkatalogi i pliki z rozmiarem i datą.",
        "przyklad": "Co mam w chmurze w katalogu Umowy?"
      },
      {
        "id": "cloud_import",
        "nazwa": "Pobierz z chmury",
        "opis": "Wciąga pliki z chmury osobistej do rozmowy, żeby dało się je od razu obrobić.",
        "przyklad": "Weź z mojej chmury faktury z marca."
      },
      {
        "id": "cloud_save",
        "nazwa": "Zapisz w chmurze",
        "opis": "Odkłada pliki z rozmowy w Twojej chmurze osobistej, we wskazanym katalogu.",
        "przyklad": "Zapisz wynik w mojej chmurze, w katalogu Faktury."
      }
    ]
  },
  {
    "id": "aplikacje",
    "tytul": "Aplikacje i kod",
    "opis": "Panel, strona sprzedażowa albo sklep powstaje z gotowej aplikacji przebranej w Twoją markę. Obok stoi kontrola jakości kodu projektu.",
    "narzedzia": [
      {
        "id": "app_templates",
        "nazwa": "Gotowe aplikacje serwera",
        "opis": "Pokazuje 35 gotowych aplikacji webowych leżących na serwerze.",
        "przyklad": "Jakie gotowe aplikacje masz na serwerze?"
      },
      {
        "id": "app_from_template",
        "nazwa": "Załóż aplikację z szablonu",
        "opis": "Zakłada nowy projekt z gotowego szablonu aplikacji i otwiera go w module Kod.",
        "przyklad": "Załóż mi panel zamówień z gotowego szablonu i przebierz go w moją markę."
      },
      {
        "id": "code_check",
        "nazwa": "Sprawdź jakość kodu",
        "opis": "Przegląda projekt i wypisuje błędy, podatności oraz hasła zostawione wprost w kodzie.",
        "przyklad": "Przejrzyj ten projekt pod kątem błędów i podatności."
      }
    ]
  },
  {
    "id": "komputer",
    "tytul": "Twój komputer",
    "opis": "Nexus znajdzie plik na dysku, sprawdzi stan sprzętu, zrobi zrzut okna i wykona polecenie. Połączenie z komputerem jest domyślnie wyłączone — włączasz je sam.",
    "narzedzia": [
      {
        "id": "pc_info",
        "nazwa": "Stan komputera",
        "opis": "Mówi, w jakim stanie jest Twój komputer: pamięć, dyski, czas pracy i najcięższe programy.",
        "przyklad": "Komputer zwalnia — sprawdź, co go obciąża."
      },
      {
        "id": "pc_find_files",
        "nazwa": "Znajdź plik na komputerze",
        "opis": "Znajduje na Twoim komputerze plik po nazwie albo po treści.",
        "przyklad": "Znajdź na moim komputerze umowę najmu z zeszłego roku."
      },
      {
        "id": "pc_read_file",
        "nazwa": "Podejrzyj plik na komputerze",
        "opis": "Pokazuje plik albo katalog z Twojego komputera, bez przenoszenia go na serwer.",
        "przyklad": "Pokaż, co jest w tym pliku na moim pulpicie."
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
        "opis": "Wykonuje na Twoim komputerze polecenie, które diagnozuje albo naprawia usterkę.",
        "przyklad": "Zrób miejsce na dysku C — wyczyść pliki tymczasowe."
      }
    ]
  }
];

export const LICZBA_NARZEDZI = 101;
