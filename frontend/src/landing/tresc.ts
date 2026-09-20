// Treść strony produktu. Źródło: landing/LANDING_PAGE_SPEC.md, rozdz. 7 (dokument wiążący).

// Liczba narzędzi pochodzi z rejestru agenta — wpisana ręcznie rozjechałaby się z aplikacją.
import { LICZBA_NARZEDZI } from "../dane/narzedzia";

export const HERO_FAKTY = [
  "61 narzędzi w jednej rozmowie",
  "Rozmowa głosowa po polsku",
  "Pliki do 2 GB",
  "Windows, Android, iPhone",
];

/** Pasek „Powiedz to własnymi słowami” — dwa tory przesuwające się w przeciwne strony. */
export const ZDANIA_TOR_1 = [
  "Odśwież zdjęcie babci",
  "Przeczytaj Zosi bajkę o smoku",
  "Streść umowę najmu",
  "Zaplanuj sobotę w Kazimierzu",
  "Popraw skan faktury",
  "Co ugotować z tego, co w lodówce?",
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
  "Zapisz wyniki w chmurze",
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
    opis: "Korekta kolorów, kontrastu i ostrości. Ogród znów jest zielony.",
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
    opis: "Zdjęcie trafia na kartkę A5 z życzeniami. Ciepłymi, ale bez wierszyka.",
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
    opis: "Mów zamiast pisać. Nexus słucha i odpowiada po polsku — także wtedy, gdy trzeba przeczytać bajkę o smoku, który bał się ciemności.",
    narzedzia: "Tryb rozmowy głosowej · Whisper · Piper",
    szeroka: true,
  },
  {
    rodzaj: "praca",
    naglowek: "Krzywe zdjęcie faktury. Czysty PDF.",
    opis: "Poprawa skanu, OCR po polsku i odczyt kwoty z terminem.",
    narzedzia: "enhance_document_scan · ocr_documents",
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
    opis: "Pytaj, zlecaj, zmieniaj zdanie. Nexus pamięta całą rozmowę i Twoje pliki.",
    narzedzia: "Rozumowanie modelu · view_pages",
  },
  {
    rodzaj: "praca",
    naglowek: "Pliki pod tym samym dachem.",
    opis: "Nextcloud pod adresem Nexusa, jedno logowanie, synchronizacja z komputerem i telefonem.",
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
    naglowek: "Zdjęcie bez tła. Bez programu graficznego.",
    opis: "Wytnij tło, wstaw nowe, zetrzyj z kadru to, co przeszkadza. Mówisz, co ma zniknąć — reszta dzieje się sama.",
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
    opis: "Opisujesz, co ma być na stronie, i oglądasz ją na żywo. Pod publicznym adresem staje dopiero wtedy, gdy Ty ją zatwierdzisz.",
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
    wynik: ["Smok, który bał się ciemności", "Gosia czyta · 6 min"],
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
    opis: "Własna przestrzeń w chmurze Nexusa: 1 GB w planie Osobistym, 2 GB w Pro, 10 GB w Zespole. Pliki, wyniki i historia rozmów są widoczne wyłącznie dla Ciebie; usuwasz je, kiedy chcesz.",
  },
  {
    tytul: "Narzędzia pracują na miejscu",
    opis: "OCR, poprawa obrazu, transkrypcja i wyszukiwanie po znaczeniu wykonuje sama usługa — nie wysyłamy Twoich plików do obcych dostawców.",
  },
  {
    tytul: "Zamknięty zestaw uprawnień",
    opis: `Agent sięga wyłącznie po ${LICZBA_NARZEDZI} narzędzi zarejestrowanych w Nexusie i pracuje w Twojej przestrzeni — nie ma wstępu ani do cudzych kont, ani poza nie. Do sieci wychodzi wtedy, gdy poprosisz o zbadanie tematu.`,
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
  { liczba: "3", podpis: "polskie głosy do czytania" },
];

/**
 * „Czym to się różni od czatu z AI” — odpowiedź na pytanie, które gość zadaje przed cennikiem.
 * Każda różnica ma pokrycie w rejestrze narzędzi albo w module aplikacji.
 */
export const ROZNICE = [
  {
    tytul: "Oddaje plik, nie instrukcję",
    opis: `Zamiast opisu „jak to zrobić” dostajesz PDF, DOCX, XLSX, archiwum ZIP albo poprawione zdjęcie. Pracę wykonuje ${LICZBA_NARZEDZI} narzędzi Nexusa, nie Ty po drugiej stronie okna.`,
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
  { tytul: "Nic nie jest zamknięte", opis: "Wyniki w PDF, DOCX, TXT, XLSX i archiwum ZIP." },
];

export const TECHNOLOGIE = [
  "Silnik Nexusa",
  "Whisper",
  "Piper",
  "Real-ESRGAN",
  "Tesseract",
  "LibreOffice",
  "Qdrant",
  "Nextcloud",
];

export interface Plan {
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
      "Chmura osobista",
      "Aplikacja na komputer i telefon",
    ],
  },
  {
    nazwa: "Pro",
    znacznik: "Wkrótce",
    dostepny: false,
    dlaKogo: "Dla tych, którzy używają Nexusa codziennie i dużo.",
    cena: "Cena przy starcie",
    przycisk: "Powiadom mnie",
    zawartosc: [
      "Wszystko z planu Osobistego",
      "Więcej zadań jednocześnie",
      "Automatyzacje według harmonogramu",
      "Pierwszeństwo w pomocy technicznej",
    ],
  },
  {
    nazwa: "Zespół",
    znacznik: "Wkrótce",
    dostepny: false,
    dlaKogo: "Dla rodziny albo małego zespołu na wspólnych plikach.",
    cena: "Cena przy starcie",
    przycisk: "Powiadom mnie",
    zawartosc: [
      "Wszystko z planu Pro",
      "Osobne konta dla każdej osoby",
      "Wspólne katalogi i baza wiedzy",
      "Role, uprawnienia i dziennik działań",
    ],
  },
];

export const PYTANIA = [
  {
    pytanie: "Gdzie są przechowywane moje pliki?",
    odpowiedz:
      "W Twojej przestrzeni w chmurze Nexusa. Ile miejsca, rozstrzyga plan: 100 MB przez pierwsze 7 dni, 1 GB w planie Osobistym, 2 GB w Pro i 10 GB w Zespole. Trafiają tam przesłane pliki, wyniki pracy, historia rozmów i indeks wiedzy. Przestrzeń jest przypisana do Twojego konta: nikt inny, kto korzysta z Nexusa, nie zobaczy jej zawartości.",
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
    pytanie: "Co Nexus liczy u siebie?",
    odpowiedz:
      "Rozumowanie i planowanie prowadzi model najwyższej klasy, a przy przeciążeniu Nexus sam przechodzi na zapasowy — nie musisz nic wybierać. Rozpoznawanie tekstu ze skanów, powiększanie zdjęć, transkrypcja nagrań i wyszukiwanie po znaczeniu liczą się w samej usłudze.",
  },
  {
    pytanie: "Czy OCR dobrze radzi sobie z polskim tekstem?",
    odpowiedz:
      "Tak. Nexus używa Tesseracta z modelem języka polskiego, a przed rozpoznaniem prostuje, odszumia i rozjaśnia obraz. Wynik to przeszukiwalny PDF, który wygląda jak oryginał, albo tekst w DOCX i TXT. Pismo odręczne rozpoznaje się wyraźnie słabiej niż druk — także pismo lekarzy.",
  },
  {
    pytanie: "Jakie są limity plików i zadań?",
    odpowiedz:
      "Jeden plik może mieć do 2 GB — niezależnie od planu. Przestrzeń całego konta zależy już od planu: 1 GB w Osobistym, 2 GB w Pro, 10 GB w Zespole. Zwykłe zadanie trwa najwyżej 2 godziny, a raport badawczy — do 6 godzin.",
  },
  {
    pytanie: "Czym jest chmura osobista?",
    odpowiedz:
      "To Twój dysk w Nexusie, pod adresem cloud.danaco-nexus.pl. Przechowuje pliki, synchronizuje je z komputerem i telefonem i pozwala je udostępniać. Logujesz się raz — sesja Nexusa otwiera też chmurę. Asystent pobiera z niej pliki i zapisuje w niej wyniki.",
  },
  {
    pytanie: "Ile kosztuje Nexus?",
    odpowiedz:
      "Wszystkie trzy plany są płatne. Plan Osobisty zaczyna się od 7 dni próbnych: kartę podajesz od razu, a po tym czasie subskrypcja przechodzi w płatną bez dodatkowego kroku — wcześniej możesz zrezygnować. Ceny podamy przed startem sprzedaży.",
  },
  {
    pytanie: "Jak Nexus chroni dostęp do moich danych?",
    odpowiedz:
      "Hasło jest chronione algorytmem Argon2, a sesja żyje w ciasteczku niedostępnym dla skryptów. Zmiany wymagają nagłówka chroniącego przed atakami CSRF. Każde konto ma osobną przestrzeń: rozmowy, pliki i skrzynka pocztowa są przypisane do właściciela, a agent pracuje wyłącznie w jej granicach i wyłącznie narzędziami zarejestrowanymi w Nexusie.",
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
      "Tak. Pod adresem danaco-nexus.pl/wyprobuj otwiera się ta sama aplikacja, z której korzystają klienci — rozmowa, pliki i narzędzia — tyle że na koncie próbnym zakładanym w tle. Bez rejestracji, bez podawania adresu poczty i bez karty. Konto próbne ma mniejszy przydział i wygasa; założenie zwykłego konta zachowuje rozmowy i pliki.",
  },
  {
    pytanie: "Czy Nexus obsłuży moją pocztę i kalendarz?",
    odpowiedz:
      "Tak. Podłączasz konta IMAP i SMTP — także kilka naraz, z własnymi podpisami. Nexus czyta skrzynkę, wyszukuje w niej sprawy i przygotowuje odpowiedzi, ale wiadomość trafia do „Oczekujących”: wysyłasz ją Ty, przyciskiem. Kalendarz działa przez CalDAV chmury osobistej, więc terminy widać też w telefonie.",
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
      "Tak. Opisujesz, co ma być na stronie, i oglądasz szkic na żywo w module Strony. Każda wersja zostaje zapisana, więc możesz wrócić do poprzedniej. Publikację pod publicznym adresem zatwierdzasz sam — agent może o nią tylko poprosić.",
  },
  {
    pytanie: "Czy mogę mówić do Nexusa po polsku?",
    odpowiedz:
      "Tak, i to w obie strony. Mowę rozpoznaje Whisper, a odpowiedź czyta Piper jednym z trzech polskich głosów. Rozmowę głosową prowadzisz w aplikacji na komputerze i w telefonie — przydaje się w kuchni, w samochodzie i przy czytaniu dziecku bajki.",
  },
];
