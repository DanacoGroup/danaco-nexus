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
    nazwa: "Koniec z przekładaniem",
    opis: "Przestajesz być przenośnikiem między sześcioma programami. Plik, o którym mówisz, jest tym samym plikiem, który Nexus otwiera, poprawia i odsyła pocztą — bez pobierania, wgrywania i szukania go potem w katalogu pobranych.",
    dla: "Jedna osoba albo mały zespół",
    zakres: [
      "Rozmowy z historią i plikami",
      "Poczta i kalendarz na miejscu",
      "Chmura osobista pod jednym logowaniem",
      "Komputer, telefon, tablet",
    ],
  },
  {
    nazwa: "Stos skanów",
    opis: "Stos skanów przestaje być dniem przepisywania. Wrzucasz trzysta zdjęć faktur i dostajesz arkusz z datami i kwotami oraz PDF, w którym da się szukać — a pozycje niepewne Nexus oznacza, zamiast je zgadywać.",
    dla: "Biuro rachunkowe",
    zakres: [
      "Odczyt tekstu po polsku",
      "Stos dzielony na dokumenty",
      "Wynik w PDF, DOCX i arkuszu",
      "Szukanie w całym archiwum",
    ],
  },
  {
    nazwa: "Materiał do decyzji",
    opis: "Sprawdzasz jedno zdanie zamiast wierzyć całemu streszczeniu. Każde twierdzenie w raporcie ma przypis do źródła, więc spór o wniosek kończy się otwarciem strony, a nie powtórnym czytaniem trzydziestu kart.",
    dla: "Analityk przed decyzją",
    zakres: [
      "Kolekcje źródeł i notatek",
      "Przypis przy każdym twierdzeniu",
      "Pytanie własnymi słowami",
    ],
  },
  {
    nazwa: "Znak i materiały",
    opis: "Nie wybierasz już między szablonem, który nie pasuje, a fakturą ze studia. Opisujesz, czym firma się zajmuje, i dostajesz znak w trzech postaciach — w tym plik wektorowy, który grafik przejmie, gdy zechcesz go zatrudnić.",
    dla: "Firma bez grafika",
    zakres: [
      "Logo, plakat, ulotka, ikona",
      "PNG do sieci, SVG do edycji",
      "PDF gotowy do druku",
    ],
  },
  {
    nazwa: "Spotkania i zdjęcia",
    opis: "Spotkanie kończy się wtedy, kiedy się kończy — nie wtedy, gdy ktoś je spisze. Z nagrania wraca notatka z podziałem na mówców i lista zadań z terminami, a ze zdjęcia materiał, który można pokazać klientowi.",
    dla: "Marketing i szkolenia",
    zakres: [
      "Korekta, powiększanie, usuwanie tła",
      "Transkrypcja z podziałem na mówców",
      "Napisy SRT i VTT",
    ],
  },
  {
    nazwa: "Dokumenty w obcym języku",
    opis: "Tłumaczenie przestaje oznaczać składanie dokumentu od nowa. Umowa wraca po angielsku z tą samą numeracją paragrafów, więc odwołanie „zgodnie z § 7” nadal wskazuje to, co wskazywało.",
    dla: "Praca z zagranicznym kontrahentem",
    zakres: [
      "Tabele i numeracja bez zmian",
      "Podpisy na swoim miejscu",
      "Ten sam format na wyjściu",
    ],
  },
  {
    nazwa: "Witryna firmy",
    opis: "Strona staje w dniu, w którym się na nią zdecydujesz. Opisujesz ją zdaniami, oglądasz szkic obok rozmowy i publikujesz własnym przyciskiem — poprawka po dwóch tygodniach też jest zdaniem, nie zleceniem.",
    dla: "Firma stawiająca stronę",
    zakres: [
      "Szkic strony na żywo",
      "Publikacja pod adresem Nexusa",
      "Wersje i powrót do poprzedniej",
    ],
  },
  {
    nazwa: "Twój komputer",
    opis: "Przestajesz szukać pliku po katalogach. Po włączeniu połączenia Nexus znajdzie go na dysku i sprawdzi stan sprzętu; każdą zmianę na komputerze pokazuje w całości i czeka na Twój przycisk.",
    dla: "Praca bez informatyka",
    zakres: [
      "Szukanie plików na dysku",
      "Stan sprzętu i zrzut okna",
      "Połączenie włączasz sam",
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
      "Konto usuwasz sam w panelu klienta. Operacja wymaga hasła i słowa potwierdzenia, kasuje konto razem z rozmowami, plikami, bazą wiedzy, stronami, projektami i chmurą, i nie da się jej cofnąć. Zanim ją potwierdzisz, pobierz to, co chcesz zachować. Zostają wyłącznie dokumenty rozliczeniowe, które przechowujemy z mocy prawa.",
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
