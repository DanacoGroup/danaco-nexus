// Zastosowania: konkretne sytuacje, w których Nexus zastępuje kilka programów i pół dnia pracy.
//
// Każde zastosowanie jest związane z animacją kampanijną z pakietu `promocja/kampania`
// (spis w `frontend/src/media/katalog.ts`, pole `temat`) i wymienia narzędzia, które
// naprawdę wykonują pracę — identyfikatory muszą istnieć w `frontend/src/dane/narzedzia.ts`.

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
    tytul: "Trzysta skanów faktur w jednej tabeli",
    dlaKogo: "jednoosobowa działalność, biuro rachunkowe, wspólnota mieszkaniowa",
    problem:
      "Trzysta faktur w jednym katalogu. Część to zdjęcia z telefonu, część wydruki bez warstwy tekstowej. Zestawienie powstaje ręcznie, przez trzy wieczory.",
    polecenie:
      "Pobierz z chmury katalog Faktury za trzeci kwartał, rozpoznaj kwoty i kontrahentów i zestaw wszystko w jednej tabeli XLSX z sumą według miesięcy.",
    wynik:
      "Arkusz XLSX z pozycjami, sumami miesięcznymi i odsyłaczem do pliku źródłowego przy każdej kwocie. Skany bez warstwy tekstowej przechodzą OCR po drodze — nie wskazujesz ich osobno.",
    narzedzia: ["cloud_browse", "cloud_import", "ocr_documents", "extract_text", "write_document"],
  },
  {
    id: "spotkania",
    temat: "nexus-produktywnosc",
    tytul: "Godzina nagrania to jedna strona ustaleń",
    dlaKogo: "kierownik projektu, prawnik, dziennikarz, student",
    problem:
      "Nagranie ze spotkania leży na dysku. Przesłuchanie zajmuje tyle, ile trwało spotkanie, a notatkę i tak trzeba napisać od zera.",
    polecenie:
      "Przepisz to nagranie z podziałem na mówców, wypisz ustalenia i zadania z terminami, a całość zapisz jako notatkę w DOCX.",
    wynik:
      "Transkrypcja ze znacznikami czasu i podziałem na mówców, plik DOCX z ustaleniami do rozesłania oraz napisy SRT i VTT do samego nagrania.",
    narzedzia: ["transcribe_speakers", "edit_subtitles", "write_document", "calendar_create"],
  },
  {
    id: "grafika",
    temat: "nexus-marka",
    tytul: "Logo, wizytówka i ulotka z jednego opisu",
    dlaKogo: "mała firma, warsztat, gabinet, stowarzyszenie bez własnego grafika",
    problem:
      "Firma potrzebuje znaku, wizytówki i ulotki na targi. Gotowce z sieci powtarzają się u konkurencji, a program graficzny wymaga tygodnia nauki.",
    polecenie:
      "Zaprojektuj logo warsztatu — sam znak i nazwa, kolory ciemnozielone. Na tym znaku złóż wizytówkę i ulotkę A5 z cennikiem usług.",
    wynik:
      "Projekt w trzech postaciach: PNG do sieci, SVG do dalszej edycji i PDF gotowy do druku. Poprawkę zgłaszasz zdaniem, znak zostaje ten sam.",
    narzedzia: ["design_vector", "design_compose", "icon_find", "convert_images"],
  },
  {
    id: "rodzina",
    temat: "nexus-funkcje",
    tytul: "Zdjęcia z lat 90. wyglądają jak dzisiejsze",
    dlaKogo: "każdy, kto ma pudełko odbitek albo folder zeskanowanych zdjęć",
    problem:
      "Odbitki są wyblakłe, przekrzywione, z zagięciami i datownikiem w rogu. Program graficzny wymaga nauki, a zdjęć jest sto.",
    polecenie:
      "Odśwież te zdjęcia: popraw kolory, usuń zagięcia i datownik, powiększ do jakości drukarskiej i złóż z najlepszych kartkę urodzinową.",
    wynik:
      "Poprawione pliki w oryginalnej rozdzielczości, wersje powiększone do druku i gotowy PDF kartki. Twarze na starych odbitkach Nexus odtwarza osobnym krokiem.",
    narzedzia: ["enhance_photo", "restore_faces", "erase_objects", "upscale_image", "pdf_merge"],
  },
  {
    id: "wiedza",
    temat: "nexus-wiedza",
    tytul: "Własne dokumenty odpowiadają na pytania",
    dlaKogo: "biuro rachunkowe, kancelaria, zespół techniczny",
    problem:
      "Umowy, regulaminy, instrukcje i korespondencja leżą w kilkunastu katalogach. Wyszukiwanie po nazwie pliku działa tylko wtedy, gdy nazwę się pamięta.",
    polecenie:
      "Dodaj te dokumenty do bazy wiedzy, a potem odpowiedz: jakie mamy terminy wypowiedzenia w umowach z dostawcami i gdzie to znaleźć.",
    wynik:
      "Odpowiedź zdaniami, każde z przypisem do dokumentu i strony. Baza zostaje — przy kolejnym pytaniu nie wskazujesz plików drugi raz.",
    narzedzia: ["index_documents", "search_documents", "knowledge_save", "knowledge_read"],
  },
  {
    id: "poczta",
    temat: "nexus-automatyzacja",
    tytul: "Odpowiedź na pismo gotowa do wysłania",
    dlaKogo: "każdy, kto prowadzi korespondencję zawodową",
    problem:
      "Wiadomość z załącznikiem i pytaniem o termin. Zanim cokolwiek napiszesz, trzeba zajrzeć w kalendarz, w umowę i w poprzednią korespondencję.",
    polecenie:
      "Znajdź w poczcie ostatnią wiadomość od księgowej, sprawdź załącznik, zaproponuj termin, który mam wolny, i przygotuj odpowiedź.",
    wynik:
      "Szkic w folderze Szkice — z treścią, terminem wziętym z kalendarza i odwołaniem do załącznika. Wysyłkę zatwierdzasz sam.",
    narzedzia: ["mail_search", "mail_read", "calendar_list", "mail_draft"],
  },
  {
    id: "strona",
    temat: "nexus-firmy",
    tytul: "Stronę firmową opisujesz zdaniami",
    dlaKogo: "mała firma, warsztat, gabinet, stowarzyszenie",
    problem:
      "Wizytówka w sieci czeka na swoją kolej od dwóch lat. Kreator wymaga abonamentu i wieczoru nauki, a agencja — budżetu.",
    polecenie:
      "Zrób stronę warsztatu: usługi, cennik, godziny otwarcia, mapa dojazdu i formularz kontaktowy. Zdjęcia weź z tego katalogu.",
    wynik:
      "Strona pod adresem Nexusa, w postaci /s/nazwa-strony/, z zapisanymi wersjami. Publikację zatwierdzasz sam i wycofujesz ją jednym zdaniem.",
    narzedzia: [
      "site_from_kit",
      "site_write_file",
      "site_import_file",
      "site_save_version",
      "site_publish",
    ],
  },
  {
    id: "research",
    temat: "nexus-wyszukiwanie",
    tytul: "Rozeznanie przed decyzją, z przypisami do źródeł",
    dlaKogo: "każdy przed większym wydatkiem: remont, sprzęt, inwestycja, leczenie",
    problem:
      "Wyniki wyszukiwarki to reklamy i artykuły sprzed pięciu lat. Trudno odróżnić rzetelne źródło od treści sponsorowanej.",
    polecenie:
      "Zbadaj temat pompy ciepła w domu z lat 90.: koszty, dotacje i warunki w Polsce w 2026 roku. Zrób z tego raport, w którym każde twierdzenie ma źródło.",
    wynik:
      "Raport w DOCX z sekcjami i przypisami — każdy z adresem i datą odczytu. Przy tematach naukowych Nexus sięga także do publikacji.",
    narzedzia: ["web_search", "web_fetch_page", "scholar_search", "scholar_paper", "write_document"],
  },
];
