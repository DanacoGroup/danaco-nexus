// Zastosowania: konkretne sytuacje, w których Nexus zastępuje kilka programów i pół dnia pracy.
//
// Każde zastosowanie jest związane z animacją kampanijną z pakietu `promocja/kampania`
// (spis w `frontend/src/media/katalog.ts`, pole `temat`) i wymienia narzędzia, które
// naprawdę wykonują pracę — identyfikatory muszą istnieć w `frontend/src/dane/narzedzia.ts`,
// czego pilnuje test `src/__tests__/zastosowania.test.ts`.

export interface Zastosowanie {
  id: string;
  /** Temat animacji kampanijnej: `nexus-<temat>-<kadr>` w katalogu materiałów. */
  temat: string;
  tytul: string;
  dlaKogo: string;
  /** Sytuacja wyjściowa — co człowiek ma na biurku, zanim cokolwiek zrobi. */
  problem: string;
  /** Zdanie, które wpisuje albo mówi do Nexusa. */
  polecenie: string;
  /** Co dostaje z powrotem. */
  wynik: string;
  /** Narzędzia, które wykonują pracę (identyfikatory rejestru). */
  narzedzia: string[];
}

export const ZASTOSOWANIA: Zastosowanie[] = [
  {
    id: "faktury",
    temat: "nexus-analityka",
    tytul: "Kwartał w liczbach, nie w segregatorze",
    dlaKogo: "jednoosobowa działalność, biuro, wspólnota mieszkaniowa",
    problem:
      "Sto kilkadziesiąt faktur w PDF-ach i skanach. Część to zdjęcia z telefonu, część wydruki bez warstwy tekstowej. Zestawienie robi się ręcznie, w arkuszu, przez trzy wieczory.",
    polecenie:
      "Pobierz z chmury katalog Faktury za trzeci kwartał, rozpoznaj kwoty i kontrahentów i zestaw wszystko w jednej tabeli XLSX z sumą według miesięcy.",
    wynik:
      "Arkusz z pozycjami, sumami i odsyłaczem do pliku źródłowego przy każdej kwocie. Pliki bez warstwy tekstowej przechodzą OCR po drodze — nie trzeba ich wskazywać osobno.",
    narzedzia: ["cloud_browse", "cloud_import", "ocr_documents", "extract_text", "write_document"],
  },
  {
    id: "spotkania",
    temat: "nexus-produktywnosc",
    tytul: "Godzina nagrania to jedna strona ustaleń",
    dlaKogo: "kierownik projektu, prawnik, dziennikarz, student",
    problem:
      "Nagranie ze spotkania leży na dysku. Przesłuchanie zajmuje tyle samo, ile trwało spotkanie, a notatki i tak trzeba napisać od zera.",
    polecenie:
      "Przepisz to nagranie, wypisz ustalenia i zadania z terminami, a całość zapisz jako notatkę w DOCX.",
    wynik:
      "Transkrypcja ze znacznikami czasu, lista ustaleń i zadań z przypisanymi osobami oraz gotowy dokument do rozesłania.",
    narzedzia: ["transcribe_audio", "write_document", "calendar_create"],
  },
  {
    id: "rodzina",
    temat: "nexus-marka",
    tytul: "Zdjęcia z lat 90. wyglądają jak dzisiejsze",
    dlaKogo: "każdy, kto ma pudełko odbitek albo folder zeskanowanych zdjęć",
    problem:
      "Odbitki są wyblakłe, przekrzywione, z zagięciami i datownikiem w rogu. Program graficzny wymaga nauki, a zdjęć jest sto.",
    polecenie:
      "Odśwież te zdjęcia: popraw kolory, usuń zagięcia i datownik, powiększ do jakości drukarskiej i zrób z najlepszych kartkę na 80. urodziny babci.",
    wynik:
      "Poprawione pliki w oryginalnej rozdzielczości i powiększone wersje do druku, a na końcu gotowy plik kartki w PDF.",
    narzedzia: ["enhance_photo", "erase_objects", "upscale_image", "convert_images", "pdf_merge"],
  },
  {
    id: "wiedza",
    temat: "nexus-wiedza",
    tytul: "Własne dokumenty jako pamięć, nie jako katalog",
    dlaKogo: "biuro rachunkowe, kancelaria, zespół techniczny",
    problem:
      "Umowy, regulaminy, instrukcje i korespondencja leżą w kilkunastu katalogach. Wyszukiwanie po nazwie pliku działa tylko wtedy, gdy pamięta się nazwę.",
    polecenie:
      "Dodaj te dokumenty do bazy wiedzy, a potem odpowiedz: jakie mamy terminy wypowiedzenia w umowach z dostawcami i gdzie to jest napisane.",
    wynik:
      "Odpowiedź zdaniami, każde z przypisem do dokumentu i strony. Baza zostaje — kolejne pytania nie wymagają wskazywania plików.",
    narzedzia: ["index_documents", "search_documents", "knowledge_save", "knowledge_read"],
  },
  {
    id: "poczta",
    temat: "nexus-automatyzacja",
    tytul: "Skrzynka, która nie czeka do wieczora",
    dlaKogo: "każdy, kto prowadzi korespondencję zawodową",
    problem:
      "Wiadomości z załącznikami, terminami i pytaniami, na które odpowiedź wymaga zajrzenia w kalendarz i w dokumenty.",
    polecenie:
      "Znajdź w poczcie ostatnią wiadomość od księgowej, sprawdź załącznik, zaproponuj termin, który mam wolny, i przygotuj odpowiedź.",
    wynik:
      "Szkic w Szkicach — z treścią, terminem i odwołaniem do załącznika. Nexus nie wysyła nic bez zatwierdzenia.",
    narzedzia: ["mail_search", "mail_read", "calendar_list", "mail_draft"],
  },
  {
    id: "strona",
    temat: "nexus-firmy",
    tytul: "Strona firmowa opisana zdaniami",
    dlaKogo: "mała firma, warsztat, gabinet, stowarzyszenie",
    problem:
      "Wizytówka w sieci jest potrzebna od dwóch lat. Kreator wymaga abonamentu i wieczoru na naukę, a agencja — budżetu.",
    polecenie:
      "Zrób stronę warsztatu: usługi, cennik, godziny otwarcia, mapa dojazdu i formularz kontaktowy. Zdjęcia weź z tego katalogu.",
    wynik:
      "Gotowa strona pod publicznym adresem, z zapisanymi wersjami i możliwością wycofania publikacji jednym zdaniem.",
    narzedzia: ["site_write_file", "site_import_file", "site_save_version", "site_publish"],
  },
  {
    id: "research",
    temat: "nexus-wyszukiwanie",
    tytul: "Rozeznanie z przypisami zamiast dziesięciu kart przeglądarki",
    dlaKogo: "każdy przed większą decyzją: remont, sprzęt, inwestycja, leczenie",
    problem:
      "Wyniki wyszukiwarki to reklamy i artykuły sprzed pięciu lat. Trudno odróżnić źródło od treści sponsorowanej.",
    polecenie:
      "Zbadaj temat pompy ciepła w domu z lat 90.: koszty, dotacje i warunki w Polsce w 2026 roku. Zrób raport z przypisami do źródeł.",
    wynik:
      "Raport z sekcjami i przypisami, każdy z adresem i datą. Przy tematach naukowych Nexus sięga też do publikacji, nie tylko do stron.",
    narzedzia: ["web_search", "web_fetch_page", "scholar_search", "scholar_paper", "write_document"],
  },
  {
    id: "komputer",
    temat: "nexus-funkcje",
    tytul: "Pomoc przy komputerze, bez zdalnego pulpitu",
    dlaKogo: "osoba, której komputer „zaczął zwalniać”",
    problem:
      "Opisanie usterki przez telefon nie działa. Zdalny pulpit oznacza wpuszczenie kogoś do wszystkiego.",
    polecenie:
      "Sprawdź, czemu komputer zwolnił, i znajdź, co zajmuje miejsce na dysku.",
    wynik:
      "Stan systemu, lista największych katalogów i propozycja, co usunąć. Każde połączenie z komputerem wymaga zgody, a zrzut ekranu robi się na żądanie — nie w tle.",
    narzedzia: ["pc_info", "pc_find_files", "pc_screenshot", "pc_powershell"],
  },
];
