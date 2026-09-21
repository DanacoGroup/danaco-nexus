// Treść stron stałych portalu (Oferta, Funkcje, Kontakt) i pytań na stronie cennika.
// Samych planów tu nie ma: cennik bierze je z serwera (`/api/platnosci/plany`), bo cena,
// dostępność i zakres planu zmieniają się w katalogu płatności, a nie w tekście strony.
// Materiał redakcyjny trzymany osobno od układu – zmiana tekstu nie wymaga zmian w komponentach.

export interface PozycjaOferty {
  nazwa: string;
  opis: string;
  dla: string;
  zakres: string[];
}

export interface Funkcjonalnosc {
  nazwa: string;
  opis: string;
  grupa: string;
}


export const OFERTA: PozycjaOferty[] = [
  {
    nazwa: "Cała praca w jednym oknie",
    opis: "Rozmowa z agentem, poczta, kalendarz, pliki i chmura osobista stoją obok siebie pod jednym logowaniem. Koniec z przeklejaniem tego samego między sześcioma programami.",
    dla: "Jedna osoba albo mały zespół",
    zakres: [
      "Rozmowy z historią i załącznikami",
      "Poczta i kalendarz w jednym miejscu",
      "Jedno okno na komputerze, telefonie i tablecie",
    ],
  },
  {
    nazwa: "Papier zamieniony w dane",
    opis: "Skan faktury, umowa i pismo z urzędu wchodzą jako zdjęcie, a wychodzą jako przeszukiwalny PDF, tabela z kwotami albo lista terminów.",
    dla: "Biuro rachunkowe, dział administracji",
    zakres: ["OCR skanów i zdjęć z językiem polskim", "Eksport do PDF, DOCX i arkuszy", "Wyszukiwanie w całym archiwum"],
  },
  {
    nazwa: "Temat zbadany, źródła pod ręką",
    opis: "Nexus przegląda strony i prace naukowe, zapisuje materiał w kolekcji i składa raport, w którym każde zdanie ma przypis do źródła.",
    dla: "Analitycy, zespoły projektowe",
    zakres: ["Kolekcje źródeł i notatek", "Raporty z przypisami", "Wyszukiwanie po znaczeniu"],
  },
  {
    nazwa: "Grafika zaprojektowana, nie wyszukana",
    opis: "Logo, plakat, okładka, ulotka, ikona, baner i post powstają od zera — w rozmowie, z plikiem wektorowym do dalszej edycji i PDF-em gotowym do druku. Bez programu graficznego i bez szukania gotowców.",
    dla: "Firma bez własnego grafika",
    zakres: [
      "Projekt wektorowy: logo, znak, plakat, ulotka, ikona, infografika",
      "Pliki w trzech postaciach: PNG do sieci, SVG do edycji, PDF do druku",
      "Skład banerów, postów i miniatur z Twoich zdjęć i tekstów",
    ],
  },
  {
    nazwa: "Zdjęcia, nagrania i tłumaczenia",
    opis: "Korekta i powiększanie zdjęć, usuwanie tła, transkrypcja nagrań z napisami, tłumaczenie dokumentów z zachowaniem układu.",
    dla: "Marketing, szkolenia, praca z materiałem",
    zakres: ["Obróbka zdjęć i powiększanie AI", "Transkrypcja, napisy i streszczenia nagrań", "Tłumaczenie DOCX, PPTX i PDF"],
  },
  {
    nazwa: "Praca nad repozytorium i stroną",
    opis: "Sesje pracy nad projektem: przegląd zmian, uruchamianie testów, podgląd. Obok twórca stron, który publikuje witrynę pod adresem Nexusa.",
    dla: "Zespoły wytwórcze",
    zakres: [
      "Przestrzenie projektów i sesje kodu",
      "Uruchamianie testów z historią",
      "Publikacja strony pod adresem Nexusa, w postaci /s/nazwa-strony/",
    ],
  },
];

export const FUNKCJONALNOSCI: Funkcjonalnosc[] = [
  { grupa: "Rozmowa", nazwa: "Historia rozmów", opis: "Wątki z załącznikami, wynikami narzędzi i powrotem do wcześniejszych tur — wracasz do sprawy sprzed miesiąca bez szukania." },
  { grupa: "Rozmowa", nazwa: "Mowa", opis: "Dyktujesz zamiast pisać, a odpowiedź słyszysz jednym z trzydziestu polskich głosów. Działa na komputerze i w telefonie." },
  { grupa: "Rozmowa", nazwa: "Praca w tle", opis: "Długie zadania idą własnym torem: widzisz każdy krok z nazwą narzędzia i czasem, a rozmowę prowadzisz dalej." },
  { grupa: "Dokumenty", nazwa: "Rozpoznawanie tekstu", opis: "OCR skanów, zdjęć i plików PDF z prostowaniem stron. Wynik wygląda jak oryginał, ale da się w nim szukać." },
  { grupa: "Dokumenty", nazwa: "Konwersja formatów", opis: "PDF, DOCX, PPTX, arkusze, obrazy i pliki dźwiękowe w obie strony — bez instalowania pakietu biurowego." },
  { grupa: "Dokumenty", nazwa: "Składanie i dzielenie PDF", opis: "Podział pliku na osobne dokumenty, scalanie, zmiana kolejności stron i wykrywanie granic dokumentów w stosie skanów." },
  { grupa: "Dokumenty", nazwa: "Tłumaczenie dokumentów", opis: "DOCX, PPTX i PDF z zachowaniem układu: tabele, podpisy i numeracja zostają na swoim miejscu." },
  { grupa: "Biuro", nazwa: "Poczta", opis: "Wiele kont IMAP i SMTP, podpisy HTML i wyszukiwanie wiadomości. Odpowiedź przygotowuje Nexus, wysyłasz ją Ty." },
  { grupa: "Biuro", nazwa: "Kalendarz", opis: "Kalendarze CalDAV chmury osobistej: dzień, tydzień i miesiąc, terminy widoczne także w telefonie." },
  { grupa: "Biuro", nazwa: "Chmura osobista", opis: "Od 1 GB do 10 GB zależnie od planu, wspólnie na pliki i pocztę. W planie Pro i wyżej wersje plików i synchronizacja z komputerem." },
  { grupa: "Obraz i dźwięk", nazwa: "Obróbka zdjęć", opis: "Korekta kolorów i ostrości, powiększanie AI, usuwanie i podmiana tła, wymazywanie zbędnych obiektów." },
  { grupa: "Obraz i dźwięk", nazwa: "Nagrania", opis: "Transkrypcja ze znacznikami czasu, napisy SRT i VTT, wycinanie fragmentów i streszczenie spotkania." },
  { grupa: "Wiedza i badania", nazwa: "Baza wiedzy", opis: "Kolekcje źródeł i notatek indeksowane znaczeniowo — pytasz własnymi słowami, dostajesz fragment i źródło." },
  { grupa: "Wiedza i badania", nazwa: "Badania", opis: "Przegląd stron i prac naukowych, zapis materiału w kolekcji i raport z przypisami do każdego twierdzenia." },
  { grupa: "Wytwarzanie", nazwa: "Sesje kodu", opis: "Praca nad repozytorium z historią zmian i uruchamianiem testów w oknie aplikacji." },
  { grupa: "Wytwarzanie", nazwa: "Twórca stron", opis: "Opisujesz stronę, oglądasz szkic na żywo, a publikację pod adresem Nexusa (/s/nazwa-strony/) zatwierdzasz sam. Własnej domeny Nexus nie podpina." },
  { grupa: "Urządzenia", nazwa: "Aplikacja na urządzeniu", opis: "Instalacja z przeglądarki na komputerze i telefonie: własne okno, ikona na pulpicie, powiadomienia." },
  { grupa: "Urządzenia", nazwa: "Pomoc przy komputerze", opis: "Po włączeniu połączenia agent znajdzie plik, sprawdzi stan sprzętu i zrobi zrzut okna — zmiany dopiero po Twojej zgodzie." },
];

export const PYTANIA: { pytanie: string; odpowiedz: string }[] = [
  {
    pytanie: "Ile kosztuje Nexus na start?",
    odpowiedz:
      "Plan Osobisty zaczyna się od 7 dni próbnych i obejmuje rozmowę z Nexusem, pracę na plikach, OCR, wyszukiwanie i chmurę osobistą. Plany Pro i Grupa dokładają szerszy zakres pracy i więcej zadań naraz.",
  },
  {
    pytanie: "Gdzie przechowywane są dane?",
    odpowiedz:
      "W przestrzeni Twojego konta — od 1 GB w planie Osobistym do 10 GB w planie Grupa; przez pierwsze 7 dni 100 MB. Pliki, rozmowy, poczta i kalendarz widzi wyłącznie właściciel konta. Poza tę przestrzeń wychodzi tylko to, czego wymaga bieżące zadanie — trafia do modelu, który prowadzi rozmowę.",
  },
  {
    pytanie: "Czy potrzebna jest instalacja na komputerze?",
    odpowiedz:
      "Nie. Wystarczy przeglądarka. Aplikację możesz dodatkowo dodać jako osobne okno na komputerze i telefonie — trwa to kilka sekund i nie wymaga sklepu z aplikacjami.",
  },
  {
    pytanie: "Jak zacząć bez zakładania konta?",
    odpowiedz:
      "Pod adresem /wyprobuj otwiera się pełna aplikacja na koncie próbnym — bez rejestracji, bez karty, bez instalacji. Pracujesz w niej tak jak klienci: opisujesz zadanie, dołączasz pliki, odbierasz wynik. Rozmowy i pliki znikają razem z kontem próbnym, więc to miejsce na sprawdzenie, a nie na pracę, której szkoda stracić.",
  },
  {
    pytanie: "Jak wygląda uruchomienie?",
    odpowiedz:
      "Zakładasz konto w portalu swoim adresem e-mail i tym samym adresem oraz hasłem logujesz się do aplikacji — jedno konto prowadzi subskrypcję i wpuszcza do Nexusa. Niczego nie instalujesz na serwerze: Nexus otwierasz w przeglądarce, a jeśli chcesz, dodajesz jako osobne okno na komputerze i telefonie. Dostęp do poczty, kalendarza i chmury ustawiasz raz, przy pierwszym uruchomieniu.",
  },
  {
    pytanie: "Pod jakim adresem staje opublikowana strona?",
    odpowiedz:
      "Pod adresem Nexusa, w postaci /s/nazwa-strony/ — publikację zatwierdzasz sam, agent może o nią tylko poprosić. Własnej domeny Nexus na razie nie podpina.",
  },
  {
    pytanie: "Co Nexus robi sam, a co dopiero po zatwierdzeniu?",
    odpowiedz:
      "Sam czyta, szuka, przelicza i przygotowuje pliki. Na Twój przycisk czeka to, co wychodzi poza Nexusa i widzi to ktoś jeszcze: wysłanie wiadomości e-mail, usunięcie wydarzenia z kalendarza, publikacja strony i polecenie zmieniające Twój komputer.",
  },
  {
    pytanie: "Czy pracę widać na telefonie?",
    odpowiedz:
      "Tak. Ta sama rozmowa, te same pliki i te same zadania są w telefonie, w przeglądarce i w aplikacji na komputerze, bo wszystko leży na serwerze. Zadanie zlecone rano na komputerze dokończysz w drodze.",
  },
];

export const KONTAKT = {
  adresPoczty: "support@danaco-group.pl",
  opis: "Odpowiadamy w dni robocze. Napisz, co chcesz załatwiać w Nexusie — dobierzemy plan i podpowiemy, od czego zacząć.",
};
