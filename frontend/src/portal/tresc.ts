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
    opis: "Rozmowa z Nexusem, poczta, kalendarz, pliki i chmura osobista stoją obok siebie pod jednym logowaniem. Nie przeklejasz tego samego między sześcioma programami.",
    dla: "Jedna osoba albo kilkuosobowy zespół",
    zakres: [
      "Rozmowy z historią i załącznikami",
      "Poczta i kalendarz w jednym miejscu",
      "Chmura osobista pod adresem cloud.danaco-nexus.pl",
      "Jedno okno na komputerze, telefonie i tablecie",
    ],
  },
  {
    nazwa: "Skany zamienione w dane",
    opis: "Skan faktury, umowa i pismo z urzędu wchodzą jako zdjęcie, a wracają jako przeszukiwalny PDF, tabela z kwotami albo lista terminów.",
    dla: "Biuro rachunkowe, dział administracji",
    zakres: [
      "Rozpoznawanie tekstu ze skanów i zdjęć z językiem polskim",
      "Stos skanów rozdzielony na osobne dokumenty",
      "Eksport do PDF, DOCX i arkusza",
      "Wyszukiwanie w całym archiwum",
    ],
  },
  {
    nazwa: "Rozeznanie z przypisami do źródeł",
    opis: "Nexus przegląda strony i prace naukowe, odkłada materiał w kolekcji i składa raport, w którym każde twierdzenie ma przypis do źródła.",
    dla: "Analityk, zespół przygotowujący decyzję",
    zakres: [
      "Kolekcje źródeł i notatek",
      "Raport z przypisem przy każdym twierdzeniu",
      "Pytanie własnymi słowami, odpowiedź z fragmentem i adresem źródła",
    ],
  },
  {
    nazwa: "Projekt graficzny od zera",
    opis: "Logo, plakat, okładka, ulotka, ikona, baner i post powstają w rozmowie, bez programu graficznego i bez szukania gotowców.",
    dla: "Firma bez własnego grafika",
    zakres: [
      "Projekt wektorowy: logo, znak, plakat, ulotka, ikona, infografika",
      "Trzy postacie pliku: PNG do sieci, SVG do edycji, PDF do druku",
      "Skład banerów, postów i miniatur z Twoich zdjęć i tekstów",
    ],
  },
  {
    nazwa: "Zdjęcia i nagrania",
    opis: "Zdjęcie dostaje korektę i większy format. Nagranie wraca jako tekst z podziałem na mówców i jako plik z napisami.",
    dla: "Zespół marketingu, dział szkoleń",
    zakres: [
      "Korekta kolorów, powiększanie i usuwanie tła",
      "Transkrypcja z rozpoznaniem mówców",
      "Napisy SRT i VTT oraz streszczenie spotkania",
    ],
  },
  {
    nazwa: "Tłumaczenie dokumentów",
    opis: "Pliki DOCX, PPTX i PDF wracają w innym języku z nienaruszonym układem.",
    dla: "Firma pracująca z zagranicznym kontrahentem",
    zakres: [
      "Tłumaczenie DOCX, PPTX i PDF z zachowaniem układu",
      "Tabele, podpisy i numeracja zostają na swoim miejscu",
      "Dokument wraca w formacie, w którym przyszedł",
    ],
  },
  {
    nazwa: "Praca nad repozytorium i stroną",
    opis: "Sesja pracy nad projektem obejmuje przegląd zmian, uruchomienie testów i podgląd. Obok stoi twórca stron, który publikuje witrynę pod adresem Nexusa.",
    dla: "Zespół wytwórczy, osoba stawiająca stronę firmy",
    zakres: [
      "Przestrzenie projektów i sesje kodu",
      "Uruchamianie testów z historią",
      "Publikacja strony pod adresem Nexusa, w postaci /s/nazwa-strony/",
    ],
  },
  {
    nazwa: "Pomoc przy Twoim komputerze",
    opis: "Po włączeniu połączenia Nexus znajdzie plik na dysku, sprawdzi stan sprzętu i zrobi zrzut okna. Zmiany wykonuje dopiero po Twojej zgodzie.",
    dla: "Osoba pracująca na własnym sprzęcie, bez wsparcia informatyka",
    zakres: [
      "Szukanie plików i sprawdzanie stanu sprzętu",
      "Zrzut okna i odczyt tego, co widać na ekranie",
      "Połączenie domyślnie wyłączone, włączasz je sam",
    ],
  },
];

export const FUNKCJONALNOSCI: Funkcjonalnosc[] = [
  {
    grupa: "Rozmowa",
    nazwa: "Historia rozmów",
    opis: "Każda sprawa zostaje w swoim wątku razem z plikami i wynikami. Do rozmowy sprzed miesiąca wracasz bez szukania.",
  },
  {
    grupa: "Rozmowa",
    nazwa: "Mowa",
    opis: "Dyktujesz, zamiast pisać, a odpowiedź słyszysz polskim głosem. Działa w przeglądarce na komputerze i w telefonie.",
  },
  {
    grupa: "Rozmowa",
    nazwa: "Praca w tle",
    opis: "Długie zadanie idzie własnym torem. Widzisz każdy krok z nazwą narzędzia i czasem, a rozmowę prowadzisz dalej.",
  },
  {
    grupa: "Dokumenty",
    nazwa: "Rozpoznawanie tekstu",
    opis: "Skan, zdjęcie i PDF wracają jako plik, w którym da się szukać. Nexus prostuje krzywe strony i rozpoznaje polskie znaki.",
  },
  {
    grupa: "Dokumenty",
    nazwa: "Zamiana formatów",
    opis: "PDF, DOCX, PPTX, arkusze, obrazy i nagrania w obie strony. Nie instalujesz pakietu biurowego.",
  },
  {
    grupa: "Dokumenty",
    nazwa: "Porządek w PDF",
    opis: "Stos skanów rozdzielony na osobne dokumenty, pliki połączone w jeden, strony ustawione po kolei.",
  },
  {
    grupa: "Dokumenty",
    nazwa: "Tłumaczenie dokumentów",
    opis: "DOCX, PPTX i PDF wracają w innym języku z nienaruszonym układem. Tabele, podpisy i numeracja zostają na miejscu.",
  },
  {
    grupa: "Dokumenty",
    nazwa: "Skład do druku",
    opis: "Oferta, raport, CV i umowa złożone tak, jak składa je drukarnia — z krojem, światłem i numeracją stron.",
  },
  {
    grupa: "Biuro",
    nazwa: "Poczta",
    opis: "Podłączasz swoje skrzynki i czytasz je w tym samym oknie co resztę pracy. Odpowiedź przygotowuje Nexus, wysyłasz ją Ty.",
  },
  {
    grupa: "Biuro",
    nazwa: "Kalendarz",
    opis: "Terminy w widoku dnia, tygodnia i miesiąca. Te same wydarzenia widzisz na komputerze i w telefonie.",
  },
  {
    grupa: "Biuro",
    nazwa: "Chmura osobista",
    opis: "Od 1 GB do 10 GB zależnie od planu, wspólnie na pliki i pocztę. W planie Pro i wyżej wersje plików oraz synchronizacja z komputerem.",
  },
  {
    grupa: "Biuro",
    nazwa: "Pliki i archiwa",
    opis: "Wyniki zadania pakujesz w jedno archiwum albo odkładasz w chmurze. Nexus sprawdzi też, co jest w pliku, zanim zacznie pracę.",
  },
  {
    grupa: "Obraz i dźwięk",
    nazwa: "Projekt graficzny",
    opis: "Logo, plakat, ulotka, ikona i baner powstają od zera w rozmowie. Dostajesz PNG do sieci, SVG do edycji i PDF do druku.",
  },
  {
    grupa: "Obraz i dźwięk",
    nazwa: "Obróbka zdjęć",
    opis: "Korekta kolorów i ostrości, powiększanie bez rozmycia, usuwanie i podmiana tła, wymazywanie zbędnych obiektów.",
  },
  {
    grupa: "Obraz i dźwięk",
    nazwa: "Transkrypcja nagrań",
    opis: "Nagranie wraca jako tekst ze znacznikami czasu i podziałem na mówców, razem z plikiem napisów SRT lub VTT.",
  },
  {
    grupa: "Obraz i dźwięk",
    nazwa: "Montaż filmu",
    opis: "Ze zdjęć i klipów powstaje gotowy film z napisami i podkładem, w kadrze pionowym albo poziomym.",
  },
  {
    grupa: "Obraz i dźwięk",
    nazwa: "Animacja wyjaśniająca",
    opis: "Wykres, wzór albo schemat pokazany w ruchu, gdy rzecz trudniej opisać słowami niż zobaczyć.",
  },
  {
    grupa: "Wiedza i badania",
    nazwa: "Baza wiedzy",
    opis: "Własne dokumenty, w których pytasz własnymi słowami. Odpowiedź wraca z fragmentem, nazwą pliku i numerem strony.",
  },
  {
    grupa: "Wiedza i badania",
    nazwa: "Przegląd źródeł",
    opis: "Nexus czyta strony i prace naukowe, odkłada je w kolekcji i składa raport z przypisem przy każdym twierdzeniu.",
  },
  {
    grupa: "Wiedza i badania",
    nazwa: "Praca w przeglądarce",
    opis: "Nexus otwiera stronę, klika i wypełnia pola, gdy sam tekst nie wystarcza. Sięganie do cudzych stron włączasz osobno.",
  },
  {
    grupa: "Wytwarzanie",
    nazwa: "Sesje kodu",
    opis: "Praca nad repozytorium w oknie aplikacji: przegląd zmian, uruchamianie testów, historia przebiegów.",
  },
  {
    grupa: "Wytwarzanie",
    nazwa: "Twórca stron",
    opis: "Opisujesz stronę, oglądasz szkic na żywo, a publikację pod adresem Nexusa (/s/nazwa-strony/) zatwierdzasz sam. Własnej domeny Nexus nie podpina.",
  },
  {
    grupa: "Wytwarzanie",
    nazwa: "Gotowe aplikacje",
    opis: "Panel, stronę sprzedażową albo sklep zakładasz z gotowego szablonu i przebierasz w swoją markę, zamiast pisać go od zera.",
  },
  {
    grupa: "Urządzenia",
    nazwa: "Aplikacja na urządzeniu",
    opis: "Instalacja z przeglądarki na komputerze i telefonie: własne okno, ikona na pulpicie, powiadomienia. Bez sklepu z aplikacjami.",
  },
  {
    grupa: "Urządzenia",
    nazwa: "Pomoc przy komputerze",
    opis: "Po włączeniu połączenia Nexus znajdzie plik na dysku, sprawdzi stan sprzętu i zrobi zrzut okna. Zmiany wykonuje po Twojej zgodzie.",
  },
];

export const PYTANIA: { pytanie: string; odpowiedz: string }[] = [
  {
    pytanie: "Jak zacząć bez zakładania konta?",
    odpowiedz:
      "Pod adresem /wyprobuj otwiera się pełna aplikacja na koncie próbnym — bez rejestracji, bez karty, bez instalacji. Pracujesz w niej tak jak klienci: opisujesz zadanie, dołączasz pliki, odbierasz wynik. Rozmowy i pliki znikają razem z kontem próbnym, więc to miejsce na sprawdzenie, a nie na pracę, której szkoda stracić.",
  },
  {
    pytanie: "Czy trzeba coś instalować?",
    odpowiedz:
      "Nie. Wystarczy przeglądarka. Nexusa możesz dodatkowo otworzyć jako osobne okno na komputerze i telefonie, zainstalować jako aplikację na Androidzie albo pobrać Nexus Desktop na Windows. Każda z nich jest tylko dodatkiem do przeglądarki.",
  },
  {
    pytanie: "Jak wygląda uruchomienie konta?",
    odpowiedz:
      "Zakładasz konto w portalu swoim adresem e-mail i tym samym adresem logujesz się do aplikacji — jedno konto prowadzi subskrypcję i wpuszcza do Nexusa. Na serwerze niczego nie instalujesz. Dostęp do poczty, kalendarza i chmury ustawiasz raz, przy pierwszym uruchomieniu.",
  },
  {
    pytanie: "Ile kosztuje Nexus na start?",
    odpowiedz:
      "Plan Osobisty otwiera 7 dni próbnych: kartę podajesz od razu, a po tym czasie subskrypcja przechodzi w płatną. Obejmuje rozmowę, pracę na plikach, rozpoznawanie tekstu ze skanów, wyszukiwanie i chmurę osobistą. Plan Pro dokłada wersje plików, synchronizację i cztery zadania naraz, a plan Grupa — osobne konta dla całego zespołu.",
  },
  {
    pytanie: "Co się dzieje po siedmiu dniach próbnych?",
    odpowiedz:
      "Plan Osobisty przechodzi w płatny i dostajesz jego pełny zakres: 1 GB zamiast 100 MB oraz pocztę, której w tych dniach nie ma. Kartę podajesz na początku, więc niczego nie potwierdzasz drugi raz. Jeśli nie chcesz płatnego planu, rezygnujesz przed końcem tych dni.",
  },
  {
    pytanie: "Czy mogę zrezygnować?",
    odpowiedz:
      "Tak, w każdej chwili — w aplikacji, na ekranie „Moja subskrypcja”. Rezygnację potwierdzasz w rozliczeniach, plan działa do końca opłaconego okresu, a dane zostają na koncie.",
  },
  {
    pytanie: "Gdzie leżą moje dane?",
    odpowiedz:
      "Na serwerze w Polsce, w przestrzeni Twojego konta. Plan Osobisty daje 1 GB, Pro 2 GB, Grupa 10 GB, a pierwsze 7 dni 100 MB. Na Twoim urządzeniu zostaje sam interfejs.",
  },
  {
    pytanie: "Kto widzi moje pliki?",
    odpowiedz:
      "Pliki, rozmowy, pocztę i kalendarz widzi wyłącznie właściciel konta. Poza tę przestrzeń wychodzi tylko to, czego wymaga bieżące zadanie: treść polecenia i dołączone pliki trafiają do modelu, który prowadzi rozmowę. Funkcje sięgające danych osób trzecich — rozpoznawanie twarzy, odczyt stron, SMS-y i ekran telefonu — są domyślnie wyłączone i wymagają osobnej zgody.",
  },
  {
    pytanie: "Co się dzieje z danymi po usunięciu konta?",
    odpowiedz:
      "Konto usuwasz sam w panelu klienta. Operacja wymaga hasła i słowa potwierdzenia, kasuje konto razem z sesjami i tokenami odzyskiwania hasła, i nie da się jej cofnąć. Zanim ją potwierdzisz, pobierz to, co chcesz zachować.",
  },
  {
    pytanie: "Co z pocztą — czy dostaję własny adres?",
    odpowiedz:
      "Tak. Plan Osobisty daje jeden adres w domenie Nexusa, a plany Pro i Grupa do dziesięciu. Możesz też podłączyć własne konta IMAP i SMTP; wiadomości zostają wtedy u Twojego dostawcy, bo Nexus nie prowadzi ich kopii. Skrzynki działają przy aktywnej subskrypcji, poza okresem próbnym.",
  },
  {
    pytanie: "Pod jakim adresem staje opublikowana strona?",
    odpowiedz:
      "Pod adresem Nexusa, w postaci /s/nazwa-strony/. Publikację zatwierdzasz sam, agent może o nią tylko poprosić. Własnej domeny Nexus na razie nie podpina.",
  },
  {
    pytanie: "Co Nexus robi sam, a co dopiero po zatwierdzeniu?",
    odpowiedz:
      "Sam czyta, szuka, przelicza i przygotowuje pliki. Na Twój przycisk czeka to, co wychodzi poza Nexusa i widzi to ktoś jeszcze. Tak działa wysyłka wiadomości, usunięcie wydarzenia z kalendarza, publikacja strony i polecenie na Twoim komputerze.",
  },
  {
    pytanie: "Czy pracę widać na telefonie?",
    odpowiedz:
      "Tak. Ta sama rozmowa, te same pliki i te same zadania są w telefonie, w przeglądarce i w aplikacji na komputerze, bo wszystko leży na serwerze. Zadanie zlecone rano na komputerze dokończysz w drodze.",
  },
];

export const KONTAKT = {
  adresPoczty: "support@danaco-group.pl",
  opis: "Odpowiadamy w dni robocze na podany adres. Napisz, co masz do zrobienia i na jakich plikach pracujesz — wskażemy plan i pierwsze zadanie.",
};
