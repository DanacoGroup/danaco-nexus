// Treść strony produktu. Źródło: landing/LANDING_PAGE_SPEC.md, rozdz. 7 (dokument wiążący).

// Liczba narzędzi pochodzi z rejestru agenta — wpisana ręcznie rozjechałaby się z aplikacją.
import { LICZBA_NARZEDZI } from "../dane/narzedzia";

export const HERO_FAKTY = [
  // Pierwsza kapsuła niesie główny przekaz strony — ma stać w pierwszym ekranie,
  // a nie dopiero w sekcji różnic w połowie strony.
  "Opisujesz wynik, dostajesz plik",
  `${LICZBA_NARZEDZI} narzędzi w jednej rozmowie`,
  "Wejście bez rejestracji",
  "Pliki do 2 GB",
  "Windows, Android, iPhone",
];

/** Pasek „Powiedz to własnymi słowami” — dwa tory przesuwające się w przeciwne strony. */
export const ZDANIA_TOR_1 = [
  "Odśwież zdjęcie babci",
  "Przeczytaj Zosi bajkę o smoku",
  "Streść umowę najmu",
  "Zaplanuj sobotę w Kazimierzu",
  "Przepisz 300 faktur ze skanów",
  "Ułóż obiad z tego, co w lodówce",
  "Zrób notatkę z zebrania",
  "Odpowiedz na wiadomość od księgowej",
  "Przetłumacz instrukcję z niemieckiego",
];

export const ZDANIA_TOR_2 = [
  "Znajdź gwarancję na pralkę",
  "Powiększ zdjęcie z gór do 50 × 70 cm",
  "Napisz pismo do wspólnoty",
  "Zmniejsz 312 zdjęć z wakacji",
  "Wypisz terminy z pisma z urzędu",
  "Zaprojektuj logo i wizytówkę",
  "Zrób kartkę na 80. urodziny",
  "Wytnij tło z tego zdjęcia",
  "Wpisz wizytę u dentysty do kalendarza",
];

export interface Krok {
  numer: string;
  tytul: string;
  opis: string;
  znacznik: string;
}

/** „Jedno zdanie. Cztery kroki.” — droga od wyblakłej odbitki do kartki do druku. */
export const KROKI: Krok[] = [
  {
    numer: "1",
    tytul: "Stara odbitka.",
    opis: "Wyblakły skan z 1974 roku. Nexus ogląda zdjęcie i planuje kolejne kroki.",
    znacznik: "Analiza zdjęcia · 800 × 800 px",
  },
  {
    numer: "2",
    tytul: "Kolory wracają.",
    opis: "Nexus poprawia kolory, kontrast i ostrość. Bez programu graficznego po Twojej stronie.",
    znacznik: "Korekta zdjęcia · kolory, kontrast, ostrość",
  },
  {
    numer: "3",
    tytul: "Cztery razy większe.",
    opis: "Powiększenie AI z odtworzeniem szczegółów — ostro nawet na dużym wydruku.",
    znacznik: "Powiększenie AI · 800 → 3200 px",
  },
  {
    numer: "4",
    tytul: "Kartka urodzinowa.",
    opis: "Zdjęcie trafia na kartkę A5 z życzeniami. Plik PDF pobierasz gotowy do druku.",
    znacznik: "kartka-babcia-80.pdf · A5 · gotowa do druku",
  },
];

export type Rodzaj = "zycie" | "praca";

export interface Karta {
  rodzaj: Rodzaj;
  naglowek: string;
  opis: string;
  narzedzia: string;
  szeroka?: boolean;
}

/** Funkcje — siatka bento. Siedem kart „Życie”, siedem „Praca”. */
export const KARTY: Karta[] = [
  {
    rodzaj: "zycie",
    naglowek: "Bajka na dobranoc, czytana na głos.",
    opis: "Mów, zamiast pisać. Nexus słucha po polsku i czyta odpowiedź na głos — także bajkę o smoku, który bał się ciemności.",
    narzedzia: "Tryb rozmowy głosowej · czytanie odpowiedzi na głos",
    szeroka: true,
  },
  {
    rodzaj: "praca",
    naglowek: "Krzywe zdjęcie faktury. Czysty PDF.",
    opis: "Nexus prostuje skan, rozpoznaje tekst po polsku i wypisuje kwotę z terminem. Z 300 zdjęć składa jedną tabelę.",
    narzedzia: "enhance_document_scan · ocr_documents",
  },
  {
    rodzaj: "praca",
    naglowek: "Logo, ulotka i plakat do druku.",
    opis: "Opisujesz, co ma powstać. Odbierasz projekt w trzech postaciach: PNG do sieci, SVG do edycji, PDF do druku.",
    narzedzia: "design_vector · design_compose",
  },
  {
    rodzaj: "zycie",
    naglowek: "Sobota w Kazimierzu.",
    opis: "Weekend, przeprowadzka, plan treningów — w PDF albo w arkuszu.",
    narzedzia: "write_document",
  },
  {
    rodzaj: "praca",
    naglowek: "Godzina nagrania. Jedna strona notatek.",
    opis: "Transkrypcja, streszczenie i lista zadań z każdego spotkania.",
    narzedzia: "transcribe_audio · write_document",
  },
  {
    rodzaj: "praca",
    naglowek: "Pytasz własnymi słowami.",
    opis: "Wyszukiwanie po znaczeniu we wszystkich zaindeksowanych dokumentach. Dostajesz fragment i źródło.",
    narzedzia: "index_documents · search_documents",
  },
  {
    rodzaj: "zycie",
    naglowek: "312 zdjęć z wakacji. Jedno polecenie.",
    opis: "Korekta, zmniejszenie do wysyłki rodzinie, archiwum ZIP i zapis w chmurze.",
    narzedzia: "enhance_photo · convert_images · create_archive · cloud_save",
  },
  {
    rodzaj: "zycie",
    naglowek: "Kolacja z tego, co w lodówce.",
    opis: "Wypisujesz, co masz w lodówce, i dostajesz przepis z listą zakupów. Zmieniasz zdanie — Nexus pamięta całą rozmowę.",
    narzedzia: "web_search · write_document",
  },
  {
    rodzaj: "zycie",
    naglowek: "Filmik ze zdjęć z wakacji.",
    opis: "Wskazujesz zdjęcia i klipy, Nexus składa z nich film z napisami i podkładem. Wynik nadaje się na telefon i na ekran.",
    narzedzia: "video_compose · video_to_gif",
  },
  {
    rodzaj: "praca",
    naglowek: "Pismo do ubezpieczyciela.",
    opis: "Dołączasz dokumenty sprawy i mówisz, o co chodzi. Wracasz z gotowym pismem w DOCX i PDF.",
    narzedzia: "ocr_documents · write_document",
  },
  {
    rodzaj: "praca",
    naglowek: "Pliki pod tym samym dachem.",
    opis: "Chmura osobista pod adresem Nexusa, jedno logowanie, pliki i wyniki w jednym miejscu. Synchronizacja z komputerem i telefonem — od planu Pro.",
    narzedzia: "cloud_browse · cloud_import · cloud_save",
  },
  {
    rodzaj: "praca",
    naglowek: "Skrzynka odpisana. Termin w kalendarzu.",
    opis: "Nexus czyta pocztę, szuka w niej konkretnej sprawy i pisze odpowiedź. Wysyła dopiero wtedy, gdy ją przeczytasz i klikniesz „Wyślij”.",
    narzedzia: "mail_search · mail_read · mail_draft · calendar_create",
  },
  {
    rodzaj: "praca",
    naglowek: "Temat zbadany. Każde zdanie ze źródłem.",
    opis: "Nexus przegląda strony i prace naukowe, zapisuje materiał w bazie wiedzy i oddaje raport z przypisami — bez wklejania odsyłaczy po kolei.",
    narzedzia: "web_search · web_fetch_page · scholar_search · knowledge_save",
  },
  {
    rodzaj: "praca",
    naglowek: "Sięga do Twojego komputera.",
    opis: "Znajdzie plik na dysku, sprawdzi stan sprzętu, zrobi zrzut okna. Połączenie z komputerem włączasz sam, a polecenie, które coś zmienia, czeka na Twoją zgodę.",
    narzedzia: "pc_find_files · pc_info · pc_screenshot · pc_powershell",
  },
  {
    rodzaj: "zycie",
    naglowek: "Tło wycięte, obiekt starty z kadru.",
    opis: "Wytnij tło, wstaw nowe, usuń z kadru to, co przeszkadza. Mówisz, co ma zniknąć — resztę robi Nexus.",
    narzedzia: "remove_background · change_background · erase_objects",
  },
  {
    rodzaj: "zycie",
    naglowek: "Instrukcja po niemiecku. Czytasz po polsku.",
    opis: "Tłumaczenie DOCX, PPTX i PDF z zachowaniem układu — tabele, podpisy i numeracja zostają na swoim miejscu.",
    narzedzia: "translate_document",
  },
  {
    rodzaj: "zycie",
    naglowek: "Strona dla klubu. Adres jeszcze tego dnia.",
    opis: "Opisujesz, co ma być na stronie, i oglądasz ją na żywo. Publikujesz sam, a strona staje pod adresem /s/nazwa-strony/.",
    narzedzia: "site_write_file · site_save_version · site_publish",
  },
];

export interface Pora {
  godzina: string;
  pora: string;
  tytul: string;
  opis: string;
  wynik: string[];
}

/** „Jeden dzień z Nexusem” — trzy pory dnia w barwach Aurory. */
export const DZIEN: Pora[] = [
  {
    godzina: "7:40",
    pora: "Rano",
    tytul: "Notatka głosowa w drodze",
    opis: "Nagrywasz, co trzeba dziś załatwić. Nexus zamienia to w listę.",
    wynik: ["Odebrać paczkę z automatu", "Zadzwonić do hydraulika", "Kupić świeczki na tort"],
  },
  {
    godzina: "11:20",
    pora: "W pracy",
    tytul: "Umowa na 14 stron",
    opis: "Potrzebujesz tylko terminów. Nexus czyta całość i wypisuje najważniejsze.",
    wynik: ["Wypowiedzenie 3 miesiące", "Waloryzacja od 1 stycznia", "Kaucja zwrot w 30 dni"],
  },
  {
    godzina: "20:30",
    pora: "Wieczorem",
    tytul: "Bajka o smoku",
    opis: "Zosia chce bajkę. Nexus ją napisze i przeczyta na głos — spokojnie, po polsku.",
    wynik: ["Smok, który bał się ciemności", "Czytanie na głos · 6 min"],
  },
];

export interface FilmPromocyjny {
  /** Identyfikator w atrybutach dostępności i kluczach listy. */
  id: string;
  tytul: string;
  /** Jedno zdanie pod tytułem — czym ten film różni się od drugiego. */
  opis: string;
  /** Plakat pod przyciskiem odtwarzania i jako `poster` odtwarzacza. */
  plakat: string;
  /** Krótka pętla bez dźwięku puszczana pod przyciskiem. */
  zajawka: string;
  /** Źródła odtwarzacza: WebM przed MP4 — przeglądarka bierze pierwsze, które zna. */
  zrodla: { plik: string; typ: string }[];
  /** Napisy WebVTT: kod języka → adres pliku. */
  napisy: { jezyk: string; etykieta: string; plik: string }[];
}

/** Dwa filmy promocyjne: życie codzienne i praca zawodowa. Pliki wstawia frontend/scripts/zasoby.py. */
export const FILMY: FilmPromocyjny[] = [
  {
    id: "dzien",
    tytul: "Jeden dzień z Nexusem",
    opis: "Życie codzienne: lista zakupów z jednego zdania, odnowione zdjęcie babci, bajka czytana na dobranoc.",
    plakat: "/film/okladka.webp",
    zajawka: "/film/zajawka.webm",
    zrodla: [
      { plik: "/film/nexus-60s.webm", typ: "video/webm" },
      { plik: "/film/nexus-60s.mp4", typ: "video/mp4" },
    ],
    napisy: [
      { jezyk: "pl", etykieta: "Polski", plik: "/film/nexus-60s.pl.vtt" },
      { jezyk: "en", etykieta: "English", plik: "/film/nexus-60s.en.vtt" },
    ],
  },
  {
    id: "praca",
    tytul: "Nexus w pracy",
    opis: "Praca zawodowa: poczta i terminy, badanie tematu z przypisami, projekt graficzny, strona i kod.",
    plakat: "/film/okladka-praca.webp",
    zajawka: "/film/zajawka-praca.webm",
    zrodla: [
      { plik: "/film/nexus-praca-60s.webm", typ: "video/webm" },
      { plik: "/film/nexus-praca-60s.mp4", typ: "video/mp4" },
    ],
    napisy: [
      { jezyk: "pl", etykieta: "Polski", plik: "/film/nexus-praca-60s.pl.vtt" },
      { jezyk: "en", etykieta: "English", plik: "/film/nexus-praca-60s.en.vtt" },
    ],
  },
];

export interface Nagranie {
  plik: string;
  tytul: string;
  opis: string;
}

/** Zachowania interfejsu nagrane w pakiecie ruchu (motion/przyklady). */
export const NAGRANIA: Nagranie[] = [
  {
    plik: "/ruch/agent-status.mp4",
    tytul: "Praca agenta na widoku",
    opis: "Każdy krok ma nazwę narzędzia, stan i czas. Widzisz, co się dzieje, i możesz przerwać.",
  },
  {
    plik: "/ruch/czat-strumien.mp4",
    tytul: "Odpowiedź pisana na żywo",
    opis: "Tekst pojawia się zdanie po zdaniu, bez skoków układu i migania.",
  },
  {
    plik: "/ruch/upuszczanie-pliku.mp4",
    tytul: "Pliki prosto do rozmowy",
    opis: "Przeciągnij dokument, zdjęcie albo nagranie — Nexus przyjmuje je w miejscu upuszczenia.",
  },
  {
    plik: "/ruch/pasek-paleta.mp4",
    tytul: "Paleta poleceń Ctrl K",
    opis: "Wszystko, co Nexus potrafi, w jednym polu — bez zdejmowania rąk z klawiatury.",
  },
];

export const GWARANCJE = [
  {
    tytul: "Twoja przestrzeń, tylko Twoja",
    opis: "Własna przestrzeń w chmurze Nexusa: 1 GB w planie Osobistym, 2 GB w Pro, 10 GB w Grupie. Tylko Ty widzisz swoje pliki, wyniki i historię rozmów. Usuniesz je w dowolnej chwili.",
  },
  {
    tytul: "Serwer stoi w Polsce",
    opis: "Rozpoznawanie tekstu, poprawę zdjęć, transkrypcję i wyszukiwanie po znaczeniu liczy sama usługa. Do silnika prowadzącego rozmowę idzie treść polecenia i te fragmenty plików, których wymaga zadanie.",
  },
  {
    tytul: "Zamknięty zestaw uprawnień",
    opis: `Agent sięga wyłącznie po ${LICZBA_NARZEDZI} narzędzi zarejestrowanych w Nexusie i pracuje w Twojej przestrzeni. Do cudzych kont nie ma wstępu. Do sieci wychodzi wtedy, gdy poprosisz o zbadanie tematu.`,
  },
  {
    tytul: "Bezpieczne logowanie",
    opis: "Hasło chronione algorytmem Argon2, sesja w bezpiecznym ciasteczku, połączenie wyłącznie przez HTTPS.",
  },
];

export const LICZBY = [
  { liczba: String(LICZBA_NARZEDZI), podpis: "narzędzi w rejestrze agenta" },
  { liczba: "2 GB", podpis: "największy plik" },
  { liczba: "6 h", podpis: "najdłuższe zadanie badawcze" },
  // Wcześniej stała tu liczba głosów czytających. Katalog głosów pobiera się z usługi mowy
  // i zmienia bez naszego udziału, więc liczba na stronie rozjeżdżała się z aplikacją.
  { liczba: "15", podpis: "modułów w aplikacji" },
];

/**
 * „Czym to się różni od czatu z AI” — odpowiedź na pytanie, które gość zadaje przed cennikiem.
 * Każda różnica ma pokrycie w rejestrze narzędzi albo w module aplikacji.
 */
export const ROZNICE = [
  {
    tytul: "Kończy gotowym plikiem",
    opis: `Zamiast opisu „jak to zrobić” dostajesz PDF, DOCX, XLSX, archiwum ZIP albo poprawione zdjęcie. Pracę wykonuje ${LICZBA_NARZEDZI} narzędzi Nexusa.`,
  },
  {
    tytul: "Pamięta Twoje pliki",
    opis: "Dokumenty, nagrania i notatki zostają w Twojej przestrzeni i są przeszukiwane po znaczeniu. Nie wklejasz tej samej umowy po raz trzeci.",
  },
  {
    tytul: "Widzisz każdy krok",
    opis: "Karta pracy pokazuje nazwę narzędzia i czas kroku. Zadanie zatrzymasz w każdej chwili — na komputerze klawiszem Esc.",
  },
  {
    tytul: "Jedno okno zamiast sześciu",
    opis: "Rozmowa, poczta, kalendarz, chmura osobista, dokumenty i badania stoją obok siebie, pod jednym logowaniem.",
  },
];

// „Widzisz każdy krok” mówi już karta w sekcji różnic — na jednej stronie ten nagłówek pada raz.
export const ZASADY = [
  { tytul: "Zatrzymasz w każdej chwili", opis: "Przycisk zatrzymania, na komputerze klawisz Esc." },
  { tytul: "Wyniki w otwartych formatach", opis: "PDF, DOCX, TXT, XLSX i archiwum ZIP — otwierasz je, czym chcesz." },
];

// Pasek faktów pod liczbami. Wcześniej stały tu nazwy silników i modeli, których czytelnik
// nie ma jak sprawdzić i które nie mówią mu nic o jego własnej pracy.
export const TECHNOLOGIE = [
  "Serwer w Polsce",
  "Połączenie HTTPS",
  "Hasło chronione Argon2",
  "OCR z językiem polskim",
  "Chmura osobista",
  "Wyszukiwanie po znaczeniu",
  "Napisy SRT i VTT",
  "Eksport PDF, DOCX, XLSX",
];

export interface Plan {
  /** Kod planu z katalogu serwera — po nim dobieramy żywą cenę i dostępność zakupu. */
  kod: string;
  nazwa: string;
  znacznik: string;
  dostepny: boolean;
  dlaKogo: string;
  cena: string;
  przycisk: string;
  zawartosc: string[];
}

export const PLANY: Plan[] = [
  {
    kod: "osobisty",
    nazwa: "Osobisty",
    // Znacznik i cena idą za katalogiem planów (backend/nexus/platnosci/plany.py): plan jest
    // płatny od początku, a 7 dni próbnych to tryb tego samego planu, nie osobna oferta.
    znacznik: "7 dni próbnych",
    dostepny: true,
    dlaKogo: "Dla jednej osoby — do pracy i do życia.",
    cena: "Cena przy starcie",
    przycisk: "Zainstaluj aplikację",
    zawartosc: [
      "Rozmowa z Nexusem, także głosowa",
      "Zdjęcia, dokumenty i nagrania",
      "OCR z językiem polskim",
      "Wyszukiwanie w Twoich plikach",
      // Przestrzeń konta jest jedna i wspólna (`plany.py`: „wspólna dla plików rozmów,
      // chmury osobistej i skrzynek”). „Chmura — 1 GB” czytało się tak, jakby pliki
      // rozmów miały osobny zapas.
      "1 GB na pliki, pocztę i chmurę",
      "Adres e-mail w domenie Nexusa — w przygotowaniu",
      "Aplikacja na komputer i telefon",
    ],
  },
  {
    kod: "pro",
    nazwa: "Pro",
    znacznik: "Dostępny",
    dostepny: true,
    dlaKogo: "Dla osób, które pracują w Nexusie codziennie.",
    cena: "Cena z serwera",
    przycisk: "Wybierz plan",
    zawartosc: [
      "Wszystko z planu Osobistego",
      "Cztery zadania naraz zamiast jednego",
      "2 GB na pliki, pocztę i chmurę",
      // Zamiast „automatyzacji według harmonogramu”: katalog planów takiej pozycji nie zna
      // (`platnosci/uprawnienia.py` — „automatyzacje nie mają jeszcze modułu”), a karta
      // planu na stronie sprzedażowej nie może obiecywać czegoś, czego produkt nie robi.
      // Z tego samego powodu adresy w domenie Nexusa są „w przygotowaniu”: usługa poczty
      // jest dopiero planem (docs/poczta/PLAN-USLUGI-POCZTY.md), a własne skrzynki IMAP
      // podłącza się bez limitu planu.
      "Do 10 adresów e-mail w domenie Nexusa — w przygotowaniu",
      "Wersje plików i synchronizacja z urządzeniami",
    ],
  },
  {
    kod: "zespol",
    nazwa: "Grupa",
    znacznik: "Dostępny",
    dostepny: true,
    dlaKogo: "Dla rodziny albo małego zespołu na wspólnych plikach.",
    cena: "Cena z serwera",
    przycisk: "Wybierz plan",
    zawartosc: [
      "Wszystko z planu Pro",
      "10 GB na pliki, pocztę i chmurę",
      "Cena za każdego użytkownika w grupie",
      "Wspólny zakres pracy — przedłuża go założyciel",
      "Zaproszenia adresem e-mail",
      "Rolę założyciela można przekazać",
    ],
  },
];

export const PYTANIA = [
  {
    pytanie: "Gdzie trzymacie moje pliki?",
    odpowiedz:
      "W Twojej przestrzeni w chmurze Nexusa. Ile miejsca, rozstrzyga plan: 100 MB przez pierwsze 7 dni, 1 GB w planie Osobistym, 2 GB w Pro i 10 GB w Grupie. Trafiają tam przesłane pliki, wyniki pracy, historia rozmów i indeks wiedzy. Przestrzeń jest przypisana do Twojego konta: nikt inny, kto korzysta z Nexusa, nie zobaczy jej zawartości.",
  },
  {
    pytanie: "Czy muszę coś instalować?",
    odpowiedz:
      "Nie. Jest jedna instalacja i trwa kilka sekund: dodajesz Nexusa z przeglądarki, a on otwiera się we własnym oknie z ikoną na pulpicie i ekranie głównym. Nie ma drugiej wersji do pobrania ani sklepu z aplikacjami — możesz też pracować w zwykłej karcie przeglądarki.",
  },
  {
    pytanie: "Czy to działa jak zwykła aplikacja?",
    odpowiedz:
      "Tak. Nexus otwiera się we własnym oknie, bez paska adresu, ma ikonę na pulpicie lub ekranie głównym i widać go w przełączniku aplikacji. Nowe wersje instalują się same — po aktualizacji zobaczysz krótki komunikat. Na Androidzie możesz też udostępniać do Nexusa pliki z innych aplikacji.",
  },
  {
    pytanie: "Na jakich urządzeniach działa Nexus?",
    odpowiedz:
      "Na telefonach z Androidem (Chrome, Edge, Samsung Internet), na iPhonie i iPadzie (Safari) oraz na komputerach z Windows (Edge, Chrome). Na innych komputerach działa w każdej nowoczesnej przeglądarce.",
  },
  {
    pytanie: "Czy moje dane wychodzą poza Nexusa?",
    odpowiedz:
      "Tylko w zakresie potrzebnym do zadania: treść Twojej wiadomości oraz fragmenty i podglądy plików, które agent musi przeczytać. Pliki w całości, historia rozmów i indeks wiedzy zostają w Twojej przestrzeni. Pełny wykaz dostawców, którym powierzamy przetwarzanie, znajdziesz w polityce prywatności.",
  },
  {
    // Pytanie o pierwszy krok stoi w szóstce widocznej od razu: sekcja pytań jest ostatnim
    // miejscem, w którym czytelnik jeszcze waha się przed wejściem do aplikacji.
    pytanie: "Od czego zacząć?",
    odpowiedz:
      "Od jednego własnego zadania. Wejdź na danaco-nexus.pl/wyprobuj, wgraj skan albo nagranie i napisz jednym zdaniem, co ma z niego powstać. Plik odbierzesz w tej samej rozmowie. Gdy wynik Cię przekona, załóż konto — wtedy rozmowy i pliki zostaną przy Tobie.",
  },
  {
    pytanie: "Co Nexus liczy u siebie?",
    odpowiedz:
      "Rozpoznawanie tekstu ze skanów, powiększanie zdjęć, transkrypcję nagrań i wyszukiwanie po znaczeniu liczy sama usługa, na serwerze w Polsce. Rozumowanie i plan zadania prowadzi silnik Nexusa: idzie do niego treść polecenia i te fragmenty plików, których zadanie wymaga. Niczego nie wybierasz — przy przeciążeniu Nexus sam przechodzi na silnik zapasowy.",
  },
  {
    pytanie: "Czy OCR dobrze radzi sobie z polskim tekstem?",
    odpowiedz:
      "Tak, OCR pracuje ze słownikiem języka polskiego. Przed rozpoznaniem Nexus prostuje strony, usuwa szum i rozjaśnia obraz. Wynik wygląda jak oryginał, ale da się w nim szukać: PDF albo tekst w DOCX i TXT. Druk rozpoznaje się wyraźnie lepiej niż pismo odręczne.",
  },
  {
    pytanie: "Jakie są limity plików i zadań?",
    odpowiedz:
      "Jeden plik może mieć do 2 GB — niezależnie od planu. Przestrzeń całego konta zależy już od planu: 1 GB w Osobistym, 2 GB w Pro, 10 GB w Grupie. Zwykłe zadanie trwa najwyżej 2 godziny, a raport badawczy — do 6 godzin.",
  },
  {
    pytanie: "Czym jest chmura osobista?",
    odpowiedz:
      "To Twój dysk w Nexusie: przechowuje pliki i wyniki pracy, a asystent pobiera z niego pliki i zapisuje w nim wyniki. W planach Pro i Grupa dostajesz też własne konto pod adresem cloud.danaco-nexus.pl — z synchronizacją z komputerem i telefonem i udostępnianiem. Logujesz się raz: sesja Nexusa otwiera też chmurę.",
  },
  {
    pytanie: "Ile kosztuje Nexus?",
    odpowiedz:
      "Każdy z trzech planów kosztuje. Plan Osobisty zaczyna się od 7 dni próbnych. Kartę podajesz od razu, a po tym czasie subskrypcja przechodzi w płatną. Rezygnację składasz w dowolnym dniu okresu próbnego. Ceny podamy przed startem sprzedaży.",
  },
  {
    pytanie: "Jak Nexus chroni dostęp do moich danych?",
    odpowiedz:
      "Hasło chroni algorytm Argon2, a sesja żyje w ciasteczku, do którego skrypty stron nie mają dostępu. Każda zmiana na koncie wymaga dodatkowego potwierdzenia z aplikacji, więc obca strona nie podszyje się pod Twoją sesję. Rozmowy, pliki i skrzynka należą do jednego konta, a agent pracuje tylko w jego granicach.",
  },
  {
    pytanie: "Czy mogę wyeksportować swoje dane?",
    odpowiedz:
      "Tak. Pliki i wyniki pobierzesz w każdej chwili, pojedynczo albo jako archiwum ZIP. Katalogi chmury synchronizujesz na dysk komputera. Wyniki powstają w standardowych formatach (PDF, DOCX, TXT, XLSX), więc nic nie jest zamknięte w Nexusie.",
  },
  {
    pytanie: "Czy mogę przerwać zadanie w trakcie?",
    odpowiedz:
      "Tak. Przycisk zatrzymania (na komputerze także klawisz Esc) kończy całe zadanie wraz ze wszystkimi uruchomionymi narzędziami. Pliki przesłane do rozmowy zostają.",
  },
  {
    pytanie: "Czy Nexus działa bez internetu?",
    odpowiedz:
      "Okno otwiera się bez połączenia i pokazuje interfejs, ale wykonanie zadania wymaga połączenia z Nexusem.",
  },
  {
    pytanie: "Czy mogę zobaczyć Nexusa bez zakładania konta?",
    odpowiedz:
      "Tak. Pod adresem danaco-nexus.pl/wyprobuj otwiera się ta sama aplikacja, z której korzystają klienci: rozmowa, pliki i narzędzia. Konto próbne zakłada się w tle. Bez rejestracji, bez podawania adresu poczty i bez karty. Konto próbne ma mniejszy przydział i wygasa; założenie zwykłego konta zachowuje rozmowy i pliki.",
  },
  {
    pytanie: "Czy Nexus obsłuży moją pocztę i kalendarz?",
    odpowiedz:
      "Tak. Podłączasz konta IMAP i SMTP — także kilka naraz, z własnymi podpisami. Nexus czyta skrzynkę, wyszukuje w niej sprawy i przygotowuje odpowiedzi, ale wiadomość trafia do „Oczekujących”: wysyłasz ją Ty, przyciskiem. Kalendarz działa przez CalDAV chmury osobistej — w planach Pro i Grupa terminy widać też w telefonie.",
  },
  {
    pytanie: "Czy Nexus szuka w internecie?",
    odpowiedz:
      "Wtedy, gdy o to poprosisz. Moduł Badania przegląda strony i prace naukowe, zapisuje źródła w bazie wiedzy i składa raport z przypisami. Podczas zwykłej rozmowy agent do sieci nie wychodzi.",
  },
  {
    pytanie: "Co Nexus może zrobić na moim komputerze?",
    odpowiedz:
      "Tyle, na ile mu pozwolisz — i dopiero wtedy, gdy sam włączysz połączenie z komputerem. Agent znajdzie wtedy plik na dysku, odczyta go, sprawdzi stan sprzętu i zrobi zrzut okna. Polecenie, które zmienia system, wstrzymuje się i czeka na Twoją zgodę. Dopóki połączenia nie włączysz, Twój komputer pozostaje poza zasięgiem.",
  },
  {
    pytanie: "Czy Nexus zbuduje stronę internetową?",
    odpowiedz:
      "Tak. Opisujesz, co ma być na stronie, i oglądasz szkic na żywo w module Strony. Każda wersja zostaje zapisana, więc wrócisz do poprzedniej. Publikację zatwierdzasz sam — agent może o nią tylko poprosić. Strona staje pod adresem /s/nazwa-strony/; własnej domeny Nexus nie podpina.",
  },
  {
    pytanie: "Czy mogę mówić do Nexusa po polsku?",
    odpowiedz:
      "Tak, w obie strony. Dyktujesz, zamiast pisać, a odpowiedź Nexus czyta na głos po polsku. Rozmowę głosową prowadzisz na komputerze i w telefonie: w kuchni, w samochodzie i przy czytaniu dziecku bajki. Wykonanie zadania wymaga połączenia z Nexusem.",
  },
];
