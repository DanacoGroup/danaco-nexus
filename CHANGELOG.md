# Dziennik zmian

Format zgodny z [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
numeracja wersji zgodna z [SemVer](https://semver.org/lang/pl/).

## [Nieopublikowane]

### Bezpieczeństwo

- **Agent konta klienta nie sięga już do danych innych kont (24.09.2026).** Serwer narzędzi
  wystawia te same narzędzia każdemu kontu, a kilka z nich nie było zawężonych do konta,
  dla którego pracuje agent: `cloud_browse`, `cloud_import` i `cloud_save` działały na korzeniu
  konta technicznego Nextcloud (pliki właściciela i przestrzenie wszystkich kont),
  `knowledge_read` i `knowledge_notes` czytały kolekcje, źródła i notatki wszystkich kont,
  a narzędzia przyjmowały plik dowolnego konta po numerze. W module Pliki kosz chmury
  pokazywał klientowi pliki usunięte przez innych i pozwalał je przywrócić. Sprawdzone w bazie
  produkcyjnej: żaden agent klienta nie wywołał narzędzi chmury ani bazy wiedzy, a baza wiedzy
  była pusta — luki nie zostały wykorzystane.
- **Powiadomienia push, szkice maili i zadania modułów należą do konta.** Zakończone zadanie
  wysyłało tytuł rozmowy na urządzenia wszystkich kont, lista oczekujących maili i usunięć
  wydarzeń pokazywała propozycje wszystkich kont (z adresatami i treścią), a stan zadania
  modułu twórczego dało się odczytać po numerze z innego konta. W produkcji nie było ani
  subskrypcji push, ani oczekujących działań. Pełny przegląd: `docs/zgodnosc/IZOLACJA-KONT.md`.

### Dodano

- **Materiały portalu wczytane do bazy (24.09.2026).** Dokumentację, centrum wiedzy i blog
  napisano 21 września, ale do bazy — z której portal je pokazuje — trafiło tylko 5 z 24
  materiałów, i to w starszych wersjach. Dokumentacja (9 stron) jest teraz opublikowana
  w wersji z repozytorium, a 10 poradników i 5 wpisów czeka w panelu portalu jako szkice
  do przejrzenia i publikacji. Sprawdzone przed nadpisaniem: każda strona w bazie była
  wcześniejszą wersją pliku z historii gita, bez poprawek naniesionych w panelu.
- **Własna chmura dla planów z synchronizacją.** Konto z planem Pro albo Grupa dostaje przy
  pierwszym wejściu do chmury własne konto Nextcloud (`nexus-<konto>`) z limitem przestrzeni
  planu; pliki z dotychczasowego folderu przechodzą tam same. Logowanie do chmury, także
  z aplikacji Nextcloud na komputerze i telefonie, idzie przez Nexusa. Pozostałe plany pracują
  jak dotąd w module Pliki, a ekran synchronizacji mówi, w którym planie ją znajdą. Nowe konta
  Nextcloud zaczynają bez przykładowych plików. Kalendarze konta przechodzą do tego konta
  razem z wydarzeniami, więc w planach Pro i Grupa kalendarz synchronizuje się z telefonem
  przez CalDAV z loginem konta, a nie konta technicznego.

### Poprawiono

- **Usunięcie konta usuwa dane, a nie tylko logowanie.** Konto portalu jest kontem aplikacji,
  a jego usunięcie kasowało wyłącznie rekord konta i sesje portalu: rozmowy, pliki, baza wiedzy,
  strony, projekty i przestrzeń w chmurze zostawały na serwerze bez właściciela, a sesja okna
  aplikacji działała dalej do wygaśnięcia. Teraz znikają razem z kontem (zostają dokumenty
  rozliczeniowe). Konta z opłacanym planem nie da się usunąć przed rezygnacją z planu — inaczej
  Stripe pobierałby opłaty za konto, którego już nie ma.
- **Konta próbne znikają po dwóch dniach, jak obiecuje portal.** Nic ich dotąd nie sprzątało
  (w produkcji było ich 73). Proces roboczy usuwa raz na godzinę konta próbne starsze niż
  dwa dni i bez ważnej sesji, razem z rozmowami i plikami.
- Ekran synchronizacji kalendarza nie podaje kontom klientów loginu konta technicznego i przy
  odmowie pokazuje komunikat zamiast niekończącego się ładowania.
- Adres `danaco-nexus.pl` zawsze otwiera stronę produktu, także zalogowanym; aplikacja stoi
  pod `/czat`. Zalogowany widzi na stronie „Otwórz aplikację” zamiast „Zaloguj się”.
  Poprawka tej zmiany (331bb5d): „Nowa rozmowa”, zamknięcie rozmowy oraz Czat i Głos bez
  otwartej rozmowy prowadziły na „/”, czyli na stronę produktu — w oknie zostało pięć
  nawigacji do starego adresu. Wykryte próbą w przeglądarce na produkcji 24.09.
- Wyniki agenta i modułów twórczych zapisują się na konto zlecającego — klient mógł nie
  pobrać wyniku własnego zlecenia, bo plik należał do konta właściciela instalacji.
- Wpisy bazy wiedzy trafiają do indeksu z właścicielem; wcześniej wyszukiwanie filtrowane
  po koncie nie znajdowało ich wcale (`nexus-cli.sh przeindeksuj-wiedze` poprawia stare wpisy).
- Zmiana planu widoczna z wnętrza aplikacji: moduł „Twój plan” i pasek „Zmień plan”, gdy
  dostęp w okresie dobiega końca.

### Dodano

- **Strona produktu przestała pobierać pakiet okna aplikacji.** Wyprzedzające pobranie
  `Workspace` dołożono po to, żeby zalogowany nie oglądał zasłony na czas ściągania pakietu —
  ale stało bez warunku, więc płacił za nie **każdy**, także ktoś, kto pierwszy raz wszedł
  na stronę produktu i nigdy się nie zaloguje. Pomiar Lighthouse'em (profil mobilny,
  dławienie łącza): `Workspace-*.js` to 560 kB i największe pobranie strony publicznej,
  więcej niż oba nagrania hero razem. Teraz pakiet wyprzedza tylko pod adresem aplikacji
  (`/c/…`, `/m/…`, `/wyprobuj`) albo gdy na tym urządzeniu ktoś już był zalogowany — ślad
  w `localStorage`, wyłącznie jako podpowiedź wydajnościowa. Brak śladu (prywatne okno,
  wyczyszczone dane) niczego nie psuje: pakiet pobiera się wtedy po odpowiedzi o sesji,
  z zasłoną ekranu startowego. Ślad kasuje wyłącznie odpowiedź `401` — zerwane łącze ani
  błąd serwera nie są wylogowaniem i nie mogą zabierać wyprzedzenia komuś, kto ma konto.

- **Kopia zapasowa obejmuje wreszcie kod.** Kopia robiła bazy, pliki użytkowników,
  wektory, materiały marki i sekrety — wszystko oprócz kodu, bo założono, że kod chroni git.
  Nie chronił: drzewo robocze ma ponad dwieście sześćdziesiąt zmienionych plików poza
  commitami, a 21 września jedno nieostrożne `git checkout --` skasowało z niego kilkaset
  wierszy pracy (odzyskane wyłącznie z zapisu rozmowy). Nowy składnik `zrodla.tar.zst` waży
  **12 MB** przy 1,9 GB materiałów; poza kopią zostają `node_modules`, `dist`, `build`,
  `.gradle` i wtyczki generowane przez Capacitora — razem ponad 110 MB, które odtwarza
  instalacja. Diagnostyka sprawdza teraz nie tylko wiek kopii, ale i to, czy jej składniki
  w ogóle powstały: skrypt kończy każdy krok `|| true`, więc brakujący element nie zgłaszał
  się sam. Kopia leży nadal na tym samym dysku — to zmniejszenie szkody, nie kopia zdalna.

- **Bramka wydania sprawdza, czy testowała ten sam kod, który wydaje.** Bramka liczy
  kilkanaście minut i czyta drzewo robocze w kilku momentach: pytest na początku, testy
  interfejsu w środku, budowa na końcu. Gdy źródła zmienią się w międzyczasie, wydanie
  powstaje z innego kodu niż ten, który przeszedł testy — a znacznik niesie tylko skrót
  commita, więc po artefakcie tego nie widać. Zdarzyło się to 21 września trzy razy w ciągu
  godziny i za każdym razem po cichu. Bramka liczy teraz sumę kontrolną treści plików
  źródłowych na starcie i sprawdza ją ponownie przed skopiowaniem artefaktu; różnica
  przerywa budowę z komunikatem zamiast wydawać niesprawdzony kod. Koszt: 16 ms na
  9 MB źródeł, dwa razy na bieg. Dwa pliki odtwarzane przez haki budowy
  (`frontend/src/tokens.css`, `frontend/src/dane/narzedzia.ts`) są z pomiaru wyłączone.

- **Wydanie zabiera ze sobą źródła klientów.** Artefakt miał dotąd `frontend/dist` — kod
  zbudowany, bez map źródeł — i nie dawało się z niego odtworzyć tego, z czego powstał.
  Kopia zapasowa serwera obejmuje dane użytkowników, nie repozytorium, więc jedynym
  miejscem, gdzie żyły źródła, było drzewo robocze na jednym dysku, z ponad dwustu
  sześćdziesięcioma zmienionymi plikami poza commitami. Teraz każde wydanie niesie katalog
  `zrodla/`: `frontend/src`, skrypty budowy, `desktop/src`, `extension` i `android/scripts`.
  Koszt to niecałe 3 MB przy wydaniu ważącym ok. 7 MB. Materiały źródłowe (`landing/`
  395 MB, `motion/` 114 MB) zostają poza wydaniem — ich wynik jest już w `frontend/dist`.
  To **nie zastępuje** kopii zapasowej repozytorium ani wysłania zmian na zdalne
  repozytorium; zmniejsza tylko szkodę, gdy tego dysku zabraknie.

- **Bramka wydania sprawdza sekrety.** Klucz wpisany do repozytorium „na chwilę”
  zostaje w historii na zawsze i zauważa się go dopiero po wycieku — dziś ten produkt ma
  już klucz Stripe, więc rzecz przestała być teoretyczna. Nowy pierwszy krok bramki to
  `gitleaks detect` na całej historii: ćwierć sekundy na 115 commitów. Skan zgłaszał dotąd
  dziesięć trafień, wszystkie fałszywe (hasła kont testowych i jedna stała w skrypcie
  zasobów) — a skan, który zawsze świeci na czerwono, przestaje cokolwiek znaczyć.
  `.gitleaks.toml` zawęża **wyłącznie** regułę ogólną i **wyłącznie** w tych plikach;
  prawdziwy klucz w pliku testu nadal zatrzymuje bramkę, co sprawdziłem podstawionym
  tokenem GitHuba. Bez `gitleaks` na ścieżce krok mówi o pominięciu i idzie dalej.

- **O nowej wersji aplikacja mówi także na telefonie.** Komunikat „nowa wersja” miał
  dotąd jedno miejsce: przycisk w stopce panelu rozmów. Pomiar na zbudowanym interfejsie
  pokazał, że na szerokości 390 px panel ma `visibility: hidden` — a telefon jest
  podstawowym miejscem tej aplikacji, bo klient to instalacja PWA. Użytkownik telefonu
  dowiadywał się o aktualizacji wyłącznie wtedy, gdy sam otworzył szufladę z historią
  rozmów; service worker sprawdza wersję co godzinę, więc gotowa aktualizacja mogła czekać
  dowolnie długo. Pasek stoi teraz nad rozmową, obok pasków „brak połączenia” i „konto
  próbne”, na każdej szerokości. Nie znika sam — odświeżenie przeładowuje aplikację, więc
  decyzję podejmuje użytkownik („Odśwież” albo „Później”).

- **Treść, która dochodzi w oknie aplikacji, wchodzi kaskadą.** Pomiar na wydaniu
  `20260921-100926-f0a53ff`, kliknięciem w pasku modułów, potwierdził, że sama zmiana
  modułu rusza się jak trzeba — jedenaście animacji w szczycie, pełne przejście widoku.
  Ale to, co przychodzi chwilę później, pojawiało się skokiem: siatka plików po odpowiedzi
  serwera, karty stron, gotowy obraz po pracy narzędzia. Komponent kaskady
  (`frontend/src/ui/Stagger.tsx`) miał komplet testów i nie był w aplikacji użyty ani
  razu — żył wyłącznie na stronie produktu i w portalu. Teraz obejmuje siatkę plików,
  karty stron, blok wyniku w Obrazach i wyniki wyszukiwania w Bazie wiedzy. Kaskada trzyma się kluczy Reacta, więc przy
  filtrowaniu listy animują się tylko nowe pozycje, a te, które już były, stoją.
  Granica jest świadoma: treść montowana **razem** z widokiem ruchu nie dostaje, bo
  biegłaby równolegle z przejściem — dwa ruchy na jednej zmianie czytają się jak usterka.
  Pomiar na zbudowanym interfejsie pokazał, że sama ostrożność w doborze miejsc nie
  wystarcza: przy szybkiej odpowiedzi serwera lista bywa na miejscu od razu i kaskada
  ruszała razem z przejściem (osiem pozycji przez pierwsze 480 ms). Kaskada milczy teraz
  na czas przejścia i rusza dopiero po nim — zmierzone: 0 animacji w trakcie przejścia,
  8 w chwili jego końca.

- **Diagnostyka pilnuje, czy kopia zapasowa w ogóle powstaje.** Kopia robi się z timera
  i nie mówi o sobie nic, dopóki nie jest potrzebna. Zepsuty timer, pełny dysk albo
  zmieniona ścieżka wychodzą dopiero w dniu, w którym trzeba coś odtworzyć — czyli
  najgorszym możliwym. Nowa kontrola „kopia zapasowa” podaje znacznik najnowszej kopii,
  jej wiek i liczbę kopii na dysku, a powyżej czterdziestu ośmiu godzin (dwie przepuszczone
  doby) zgłasza błąd i wskazuje `danaco-nexus-kopia.timer`.

- **Diagnostyka pilnuje miejsca na dysku i liczby wydań.** Każde wydanie waży ok. 0,65 GB,
  a powstaje ich po kilkanaście dziennie; nic ich nie kasuje samoczynnie — `sprzataj.sh`
  uruchamia człowiek. Brak miejsca odbija się naraz na bazie, kopii zapasowej i pracy
  agenta, a widać go dopiero po awarii. Nowa kontrola „miejsce na dysku” podaje wolne
  miejsce, liczy wydania i przy ponad dwudziestu podpowiada sprzątanie; poniżej 10%
  wolnego zgłasza błąd. Dziś: 363 GB wolnego (39%), 89 wydań.

- **Diagnostyka pyta, czy nie sprzedajemy funkcji, której licencja zabrania sprzedaży.**
  `find_faces` działa na modelach InsightFace o licencji **wyłącznie niekomercyjnej**.
  Dopóki produkt nie był sprzedawany, warunek był spełniony; przestał być w chwili wpisania
  klucza Stripe — i nikt tego nie zauważył, bo nic się nie zepsuło. Nowa kontrola „licencje
  narzędzi” zgłasza błąd, gdy sprzedaż jest włączona, a w rejestrze stoi narzędzie z tego
  wykazu. Sprzeczność jest teraz widoczna przy każdym wdrożeniu, a nie tylko w dokumencie
  zgodności. Rozstrzygnięcie (model komercyjny, zgoda autorów albo wyłączenie funkcji)
  pozostaje decyzją właściciela.

- **To samo dla obietnicy o przestrzeni.** Cennik na stronie idzie z serwera, ale zdanie
  „1 GB w planie Osobistym, 2 GB w Pro, 10 GB w Grupie” jest wpisane w tekst na stałe —
  zmiana pojemności w katalogu planów nie ruszyłaby go. Nowy test wymaga, żeby dla każdego
  planu z katalogu tekst strony podawał jego nazwę i jego pojemność. Dziś zgadza się
  w trzech planach na trzy.

- **Obietnica „101 narzędzi” na stronie nie miała żadnego zabezpieczenia.** Katalog narzędzi
  w interfejsie powstaje ze skryptu, ale nic nie pilnowało, żeby go po dołożeniu narzędzia
  uruchomić — a liczba wchodzi wprost w zdania sprzedażowe i w nagłówek „Zobacz wszystkie N”.
  Nowy test porównuje katalog strony z rejestrem narzędzi serwera: zgłasza i brakujące
  pozycje, i rozjazd liczby. Dziś zgadza się co do jednego: 101 = 101.

- **Błąd w danych żądania pokazywał się jako „Błąd serwera (422)”.** Domyślna odpowiedź
  FastAPI na nieprawidłowe dane to lista obiektów z angielskim opisem („Input should be
  a valid integer…”). Interfejs bierze treść błędu tylko wtedy, gdy jest napisem, więc
  z tego zostawało użytkownikowi „Błąd serwera (422)” — komunikat **nieprawdziwy** (to nie
  serwer się pomylił, tylko dane) i nic nie mówiący. Odpowiedź ma teraz polskie zdanie
  ze wskazaniem pola **i powodu** („Pole «strona» musi być liczbą.”, „Brakuje pola «email».”,
  „Pole «text» jest za długie.”), a wykaz pól zostaje osobno, do diagnozy.

- **„Wybierz zagadnienie ze spisu obok” — na telefonie obok niczego nie było.** Spis treści
  dokumentacji stoi obok tekstu dopiero na szerokim ekranie; na telefonie jest **nad** nim.
  Zdanie kazało więc szukać czegoś, czego w tamtym miejscu nie ma. Teraz brzmi „ze spisu
  treści” i jest prawdziwe w obu układach. Ta sama pomyłka była jeszcze w dwóch miejscach:
  w twórcy stron („zobaczysz efekt na żywo **obok**” — poniżej szerokości `lg` podgląd
  siedzi w zakładce, nie obok) i w synchronizacji chmury („zeskanuj kod QR **obok**” —
  kod stoi w osobnej sekcji **nad** kartami platform, na każdej szerokości).

- **Szukanie znaku `%` oddawało wszystko.** Wyszukiwanie plików (`/api/pliki?q=…`)
  i notatek w module Badania wstawiało tekst od użytkownika wprost do wzorca `LIKE`.
  `%` i `_` są tam znakami wieloznacznymi, więc zapytanie „50%” zwracało **wszystkie**
  pozycje, a „raport_2026” trafiało też w „raport-2026”. Oba miejsca zasłaniają teraz
  te znaki. To samo dotyczyło **znacznika** na portalu: słowa zapytania przechodzą przez
  filtr, który przepuszcza tylko litery i cyfry, ale znacznik szedł do wzorca prosto
  z adresu — `?tag=%` pasowało do każdej pozycji w bazie.

- **Wyszukiwarka portalu nie znała polskiej odmiany.** Dopasowanie działa od początku
  wyrazu, a polszczyzna odmienia końcówki — więc klient piszący „faktury” **nie znajdował**
  artykułu, w którym stoi „fakturach”, bo żadne z tych słów nie jest początkiem drugiego.
  Sprawdzone na przedsionku: „faktury” → 0 wyników, „faktur” → 1, „fakturach” → 1.
  Obok całego słowa próbujemy teraz jego rdzeni (najwyżej dwie litery krócej, nie poniżej
  czterech znaków), więc „umowa” trafia w „umowy” i „umowie”, a „faktury” w „fakturach”.
  Krótkich słów („ai”, „ocr”, „kody”) nie skracamy wcale. Ocena trafności liczy się z tych
  samych rdzeni — inaczej pozycja znaleziona rdzeniem spadałaby na koniec listy.

- **Mapa modułów na portalu nie wymieniała Płatności.** Artykuł „Co gdzie znajdziesz” jest
  pierwszym miejscem, do którego zagląda klient, który czegoś nie może znaleźć — a brakowało
  w nim akurat tego modułu, w którym załatwia się subskrypcję i faktury. Moduł dopisany,
  a nowy test pilnuje, żeby każdy moduł z rejestru interfejsu miał w tym artykule swój wiersz.
  Przy okazji w `deploy/wydania/README.md` stoi teraz wprost, że poprawka w pliku sama nie
  dochodzi do klienta: portal czyta bazę i materiały trzeba wczytać poleceniem.

- **Udostępnianie do Nexusa z innych aplikacji ma wreszcie testy.** Web Share Target to
  wejście ogłoszone w manifeście PWA: system pokazuje Nexusa na liście „Udostępnij”,
  service worker odkłada treść do pamięci podręcznej, a okno ją stamtąd odbiera. Cała ta
  droga nie miała ani jednego testu, a gdy się zepsuje, udostępnienie kończy się pustą
  rozmową i niczym więcej. Przy okazji naprawiona usterka, którą te testy odsłoniły:
  nazwa pliku wracała przez `decodeURIComponent` **bez zabezpieczenia**, a ta funkcja rzuca
  wyjątek na niepełnym kodowaniu (samotny „%”). Service worker zawsze koduje nazwę, ale to
  osobny plik z własnym cyklem życia — po wydaniu w przeglądarce jeszcze przez chwilę
  pracuje poprzednia wersja. Jedna taka nazwa przewracała **całe** odebranie, razem
  z pozostałymi plikami i tekstem. Cztery nowe przypadki: bez znacznika w adresie nic się nie dzieje,
  plik i tekst wracają (z nazwą rozkodowaną z nagłówka), adres wraca do „/”, a pamięć
  podręczna jest kasowana, żeby odświeżenie nie odebrało tego samego drugi raz.

- **Most do serwera MCP ma wreszcie testy.** `nexus/agent/most_mcp.py` był jedynym plikiem
  w module agenta, którego nie dotykał żaden test — a to jedyna droga agenta do narzędzi,
  kiedy działa piaskownica (testy przebiegu agenta pracują z wyłączoną piaskownicą i idą
  serwerem MCP wprost). Trzy nowe przypadki sprawdzają granice (gniazdo poza katalogiem
  zadania, prawa `0600`, puste środowisko przelotki, sprzątanie po zamknięciu) i całą drogę
  naprawdę: klient MCP uruchamia przelotkę w Node tym samym poleceniem, które trafia do
  `--mcp-config`, a wykaz narzędzi wraca przez gniazdo.

- **Pokazu w hero nie dało się zatrzymać.** Scena produktu to nagranie z `autoplay loop`
  o obiegu 2,9 s — ruch nie kończy się więc sam, dopóki ktoś patrzy na stronę, a WCAG 2.2.2
  wymaga przy takim ruchu sposobu wstrzymania go. Przycisku nie było: specyfikacja strony
  opisywała „Wstrzymaj pokaz” pod oknem, ale w kodzie nie został po nim ślad. Scena ma teraz
  przycisk „Wstrzymaj pokaz / Wznów pokaz” w lewym dolnym rogu. Wstrzymanie jest mocniejsze
  niż obserwator widoczności: przewinięcie strony w dół i z powrotem nie wznawia ruchu,
  którego ktoś przed chwilą świadomie nie chciał.

- **Paska przykładowych poleceń nie dało się zatrzymać z klawiatury.** Dwa tory kapsuł
  przesuwają się w pętli (70 i 80 s na obieg), więc ruch nigdy się nie kończy, a WCAG 2.2.2
  wymaga przy takim ruchu sposobu wstrzymania go. Zatrzymanie było jedno — `:hover`
  i `:focus-within` — a kapsuły to zwykłe `<span>`, do których fokus nie wchodzi: myszą
  dało się pasek zatrzymać, klawiaturą nie było czym. Pasek ma teraz przycisk
  „Wstrzymaj / Wznów”. (Zatrzymanie poza polem widzenia działało już wcześniej — regułę
  ma `ruch/wejscia.css`.)

- **Logotyp znikał w trybie wysokiego kontrastu.** Wariant logotypu dobiera motyw
  aplikacji, ale przy `forced-colors` barwy narzuca system: jasny napis lądował na białym
  tle narzuconym przez Windows i przestawał być widoczny (obrazów tryb wysokiego kontrastu
  nie przemalowuje). W tym trybie wariant idzie teraz za schematem systemu, a nie za naszym
  motywem. Poza nim nic się nie zmienia.

- **Jedno zdanie zamiast białej kartki bez JavaScriptu.** Ani powłoka aplikacji, ani portal
  nie mają wersji serwerowej, więc przeglądarka z wyłączonym JavaScriptem pokazywała pustą
  stronę. `index.html` ma teraz `<noscript>` z wyjaśnieniem i adresem kontaktu (styl wpisany
  wprost, bo arkusz stylów też wchodzi dopiero z modułem).

- **Siatka pod interfejsem (`GranicaBledu`).** Gdy którykolwiek komponent rzucił wyjątek
  w trakcie rysowania, React zdejmował **całe** drzewo i użytkownik zostawał z pustą
  stroną — bez słowa wyjaśnienia i bez wyjścia; w kodzie nie było ani granicy błędu, ani
  globalnego przechwytywania. Teraz w takim miejscu staje zdanie („Twoje rozmowy i pliki
  są na serwerze — odświeżenie nic nie kasuje”) i przycisk odświeżenia, a treść wyjątku
  idzie do konsoli przeglądarki, nie na ekran.

- **Bramka wydania sprawdza programy narzędzi ścieżką usługi.** Testy tego nie łapały:
  przy braku programu pomijają przypadek, zamiast zgłosić błąd — dlatego pięć kontroli
  `code_check` i cały skład Typsta mogły być martwe, a bramka świeciła na zielono. Nowy
  krok bramki czyta `PATH` z `.env` (czyli ścieżkę, która obowiązuje po wdrożeniu, a nie
  tę z powłoki dewelopera) i przerywa budowę, gdy któregoś programu tam nie ma.

- **Diagnostyka pyta, czy poczta portalu ma jak dojść.** Portal wysyła dwie wiadomości,
  bez których konta nie da się używać: potwierdzenie adresu przy rejestracji i odsyłacz do
  nowego hasła. Domyślny nadawca zapisuje je **do dziennika**, a ekran i tak mówi
  „wysłaliśmy odsyłacz” — brak wysyłki wychodzi dopiero wtedy, gdy klient czeka na
  wiadomość, która nigdy nie przyjdzie. Nowa kontrola „poczta portalu” zgłasza to jako błąd,
  gdy rejestracja jest otwarta **albo gdy są już założone konta** — zamknięcie rejestracji
  nie zdejmuje sprawy, bo odzyskanie hasła dotyczy kont, które istnieją. Przechodzi dopiero
  wtedy, gdy nikt nie czeka: rejestracja zamknięta i baza kont pusta.

- **Diagnostyka pyta o programy narzędzi.** Nowa kontrola „programy narzędzi” sprawdza, czy
  każdy program wywoływany przez narzędzia agenta jest na ścieżce usługi — to jedyny sposób,
  żeby dowiedzieć się o braku wcześniej niż użytkownik, bo narzędzie widnieje w rejestrze
  niezależnie od tego, czy jego program istnieje. Test pilnuje, żeby lista w `doctor`
  nadążała za źródłami narzędzi (w obie strony).

- **Umowa wśród szablonów składu (`typeset_document`).** Narzędzie składało raport, ofertę,
  CV, broszurę i plakat — umowy, czyli dokumentu, o który prosi się najczęściej zaraz po
  ofercie, nie było. Nowy układ: pismo szeryfowe i szersze marginesy (umowę czyta się
  linijka po linijce, często z dopiskami), tytuł na środku zamiast reklamowego pasa,
  strony i data zawarcia pod tytułem, rozdziały numerowane paragrafami — bo tak się je
  cytuje — i miejsce na podpisy obu stron na końcu.

- **Proces roboczy przedsionka (`danaco-nexus-worker-przedsionek.service`).** Przedsionek
  miał API bez wykonawcy: kolejką zadań jest tabela `runs` w bazie, a przedsionek pracuje na
  własnej bazie, więc jedyny proces roboczy — ten produkcyjny — nigdy nie widział jego zleceń.
  Skutek: wysłana tam wiadomość dostawała kod 202 i nie działo się nic, bez słowa na ekranie;
  w bazie stały przebiegi `queued` sprzed kilku godzin. Nowa jednostka pracuje na kodzie
  z wydania stojącego w przedsionku i na jego danych, bierze jedno zadanie naraz
  (`NEXUS_WORKER_CONCURRENCY=1` w `przedsionek.env`). Po włączeniu zaległa kolejka
  opróżniła się w kilka sekund. Produkcji usterka nie dotyczyła.

- **Wczytywanie materiałów portalu z plików
  (`python -m nexus.cli materialy-portalu`).** Treść portalu mieszka w bazie, bo to z niej
  powstają adresy, zajawki, indeks wyszukiwania i mapa witryny — do tej pory jedyną drogą
  do niej było wklejanie tekstu pozycja po pozycji w panelu administratora. Polecenie
  wczytuje cały katalog plików `NN-adres.md` za jednym razem: numer w nazwie ustala
  kolejność w spisie, nazwa staje się adresem, nagłówek `# ` tytułem (i znika z treści, bo
  stronę pozycji rysuje tytuł osobno). Domyślnie zapisuje szkice — publikacja zostaje
  osobną decyzją (`--opublikuj`). Wczytanie jest powtarzalne: pozycja o tym samym adresie
  zostaje nadpisana, a nie powielona, więc poprawiony plik wystarczy wczytać ponownie.

- **Szkice pierwszych materiałów dokumentacji portalu
  (`docs/portal/tresci-startowe/`).** Blog, centrum wiedzy i dokumentacja mają dziś zero
  pozycji, więc odwiedzający trafia na puste sekcje. Pięć gotowych tekstów — pierwsze
  uruchomienie, jak zlecać zadania, ustawienia okna, pliki i chmura, mapa modułów —
  opisują wyłącznie zachowanie sprawdzone w działającym wydaniu. Wczytuje je polecenie
  opisane wyżej; README w katalogu podaje drogę publikacji, znaczenie nazw plików
  i zasadę pisania akapitów w jednym wierszu.

- **Sprzątanie starych wydań (`deploy/wydania/sprzataj.sh`).** Każde wydanie to pełna
  kopia artefaktu — z nagraniami kampanii 652 MB — a bramka buduje je kilka razy
  dziennie: na dysku leżało 56 wydań, razem 36 GB, bez żadnego mechanizmu kasowania.
  Skrypt bez argumentów wyłącznie pokazuje, co poszłoby do usunięcia; zostawia pięć
  najnowszych (`--ile N`) oraz wydania wskazane przez przedsionek, produkcję
  i `POPRZEDNIA-PRODUKCJA`. Usuwa dopiero `--wykonaj` — decyzja należy do człowieka;
  razem z wydaniem kasuje jego dziennik budowy.

- **Zestaw Danaco Web Kit po orkiestracji agentów z weryfikatorem:** motywy 10 → **50**
  (30 branżowych i 10 stylowych, każdy z polskim opisem, charakterem i sprawdzonym
  kontrastem — 100 par motyw/tryb bez ani jednego niespełnionego progu), sekcje 148 → **261**
  w 34 rodzinach, typy podstron 35 → **65**. Weryfikator liczył wszystko od nowa i budował
  witryny: 20 budów na nowych motywach (45–235 podstron), dwie regresyjne na starych.
  Dziesięciu pierwotnych motywów przebieg nie ruszył — sprawdzone przebudową i porównaniem
  bit po bicie. Po całej rozbudowie sprawdziłem jeszcze wszystkie dwanaście presetów
  branżowych: każdy buduje się bez błędu (45–235 podstron), więc urośnięcie biblioteki
  niczego nie zepsuło.

- **Montaż filmu ze zdjęć (`video_compose`, Studio → „Montaż”).** Nexus umiał dotąd
  wyłącznie przerabiać gotowe nagranie — nie umiał go *złożyć*, więc na „zrób filmik
  promocyjny z tych zdjęć” nie miał czym odpowiedzieć. Narzędzie bierze listę ujęć,
  każde zdjęcie ożywia ruchem kamery (najazd, odjazd, panorama), nakłada napis
  z przyciemnieniem pod spodem, spina ujęcia przenikaniem i podkłada muzykę z biblioteki
  serwera (`/danaco/programy/media-zasoby/muzyka`, 148 nagrań w odmianach: firmowy,
  spokojny, energetyczny, kinowy, sygnały). Kadr do wyboru: 16:9, 9:16, 1:1, 4:5.
  Napisy rysuje Pillow do przezroczystej nakładki, nie `drawtext` FFmpeg — polskie znaki
  i cudzysłowy w tekście użytkownika łamały cytowanie filtru. W Studiu doszła zakładka
  „Montaż”: wgranie paczki zdjęć naraz, kolejność ujęć strzałkami, czas i napis na
  każdym, wybór nastroju podkładu. Przejścia to 26 wbudowanych w FFmpeg **oraz 21 własnych
  z biblioteki serwera** (`media-zasoby/przejscia/xfade-danaco`) — zegar, żaluzje, schody,
  spirala, rozbłysk bielą; do tej pory leżały na dysku bez możliwości użycia.
  Przyciemnienie pod napisem dobiera się do jasności kadru: na ciemnym zdjęciu tylko muśnie,
  na jasnym przyciemni wyraźnie — stałe przyciemnienie zabijało rysunek na ciemnych ujęciach.
  Klip krótszy od zamówionego ujęcia nie urywa filmu — ostatnia klatka czeka (`tpad`).
  **Film mówi:** każde ujęcie może mieć zdanie lektora, czytane od początku tego ujęcia
  tym samym silnikiem co rozmowa głosowa (Piper, po polsku); podkład schodzi pod głos do
  35% głośności, żeby zdanie było słychać. Sprawdzone przez rozpoznanie mowy z gotowego
  filmu: wszystkie trzy zdania wróciły z transkrypcji w kolejności ujęć. Test sprawdza
  rdzenie słów, nie pełne formy — rozpoznanie mowy myli końcówki („wymiar” potrafi wrócić
  jako „wymian”) i na jednym słowie test byłby chwiejny; pierwszy przebieg bramki to
  pokazał.
  Rejestr narzędzi: 95 → 96 (z szablonami aplikacji niżej — 98).

- **„Co nowego” w Ustawieniach.** Produkt zmienia się po kilkanaście razy dziennie,
  a użytkownik nie miał gdzie tego zobaczyć — jedyną informacją o nowym wydaniu było to,
  że coś wygląda inaczej. Sekcja czyta dziennik zmian **tego wydania** (jest w artefakcie
  obok kodu), więc nie trzeba pisać listy drugi raz ani pamiętać o jej aktualizacji.
  Pokazuje cztery pozycje, reszta pod przyciskiem. Wpisy w dzienniku pisze się dla kogoś,
  kto wchodzi w kod, więc do okna idzie sam tytuł i pierwsze zdania (do 220 znaków);
  składnia Markdowna zostaje po drodze — razem z wyróżnieniami, które w dzienniku
  przechodzą przez złamanie wiersza.
- **Spot i intro dźwiękowe (`audio_compose`).** Z listy, o którą prosiłeś, brakowało
  dźwięku: `media_process` przerabiał gotowe nagranie, `read_document_aloud` czytał dokument,
  ale nic nie **składało** materiału. Narzędzie bierze kwestie lektora po kolei (głos serwera,
  po polsku, z przerwami między zdaniami) i podkład z biblioteki — muzyka wchodzi przed
  pierwszym zdaniem, schodzi pod głos i wybrzmiewa po ostatnim. Bez kwestii daje sam podkład
  przycięty z wyciszeniem. Sprawdzone przez rozpoznanie mowy z gotowego pliku: kwestie wracają
  w kolejności. Rejestr narzędzi: 99 → 100.
- **Zasoby strony ściągane z cudzych serwerów na własny (`site_vendor_assets`).** Kroje
  to była pierwsza połowa sprawy; druga to skrypty i arkusze z CDN-ów oraz zdjęcia ze
  stocków — w kolekcji sięga po nie 44 z 81 zbudowanych szablonów. Narzędzie przechodzi
  szkic, pobiera te pliki do katalogu `zewnetrzne/<serwer>/` i podmienia odwołania
  (z uwzględnieniem zagnieżdżenia podstrony). Rozróżnia zasób od odsyłacza: `href` na
  `<link>` to arkusz do pobrania, `href` na `<a>` to cudza strona i zostaje nietknięty.
  Adresy przechodzą przez tę samą blokadę co badania sieciowe (tylko http/https, tylko
  publiczne adresy IP), plik ma limit 8 MB, a błąd przy jednym pliku nie przekreśla reszty.
  Kroje Google pomija — te przenosi `site_fonts_local`. Rejestr narzędzi: 100 → 101.
- **Kroje strony z serwera zamiast z Google (`site_fonts_local`).** Gotowe szablony
  wczytują kroje z `fonts.googleapis.com` — 44 z 81 zbudowanych szablonów kolekcji sięga po
  zasoby z sieci, a kroje Google są w tym najczęstsze. To nie jest kwestia wyglądu: każde
  wejście na stronę wysyła adres IP odwiedzającego do Google, więc strona firmowa musi to
  wpisać do informacji o przetwarzaniu. Narzędzie czyta rodziny z odsyłaczy w szkicu,
  wycina z lokalnego repozytorium (2050 rodzin) podzbiór Latin + Latin Extended z polskimi
  znakami programem serwera `danaco-kroj`, wkłada `.woff2` i licencję OFL do szkicu, składa
  `kroje/kroje.css` i podmienia odsyłacze — razem z `preconnect` do Google i `@import`
  w arkuszach. Rodzina spoza repozytorium (krój firmowy, płatny) zostaje bez zmian i wraca
  w wyniku. Rejestr narzędzi: 98 → 99. Rejestr czynności przetwarzania dostał pozycję
  **CZ-15** (strona opublikowana pod `/s/<adres>/`): kto jest administratorem wobec
  odwiedzających, jakie dane wychodzą przy odwołaniach do cudzych serwerów i czym to
  ograniczamy.
- **Szablony aplikacji przestały być niewidoczne (`app_templates`, `app_from_template`).**
  W `/danaco/programy/web/kit/apps` leżą kompletne aplikacje webowe z opisem
  `danaco-szablon.json` (marka, tokeny, kroje, polecenia dev/build), ale **żadne narzędzie
  ich nie czytało** — na „zrób mi panel” agent pisał aplikację od zera zamiast wziąć gotową.
  Teraz jeden spis pokazuje, co jest, a drugie narzędzie zakłada z wybranej pozycji projekt
  w module Kod (bez `node_modules` i bez historii gita autora) i podaje, które pliki trzeba
  przebrać w markę użytkownika. W „Możliwościach” doszła dziedzina „Aplikacje i kod”;
  `code_check` przeniósł się tam z „Twojego komputera”, gdzie nie miał czego szukać.
  Rejestr narzędzi: 96 → 98. **Spis nie kończy się na dwóch pozycjach zestawu Danaco**:
  w kolekcji szablonów otwartych leżały 33 gotowe aplikacje i panele (AdminLTE, CoreUI,
  Tabler, TailAdmin, shadcn-admin, Vuestic, Sakai, Horizon UI…), oznaczone w metadanych
  jako `charakter: [panel, aplikacja]` — narzędzie ich nie czytało, bo patrzyło tylko
  w `kit/apps`. Razem: **35 szablonów aplikacji**, każdy z licencją, stosem
  technologicznym i adresem źródła. Projekt powstaje z katalogu `zrodlo/` (do edycji),
  nie z `witryna/` (zbudowanej). Szablony zestawu Danaco niosą mapę marki (`pliki_marki`,
  `tokeny`); te z kolekcji jej nie mają, więc wynik mówi wprost, gdzie szukać nazwy i barw
  autora, zamiast zostawiać agenta ze zgadywaniem.

- **Dokumentacja zgodności: trzecia luka polityki opisana z gotowym tekstem.** Dodatek do
  przeglądarki ma dostęp do wszystkich adresów i na polecenie użytkownika odczytuje tytuł,
  adres i treść odwiedzanej strony (do 24 000 znaków), a przy włączonym ustawieniu także
  zrzut widocznej karty. W polityce prywatności rozszerzenie pada raz, przy kluczach
  urządzeń — o czytaniu stron nie ma ani słowa. `docs/zgodnosc/README.md` ma teraz rozdz. 6.3
  z gotowym wierszem tabeli i akapitem do wklejenia. Samej polityki nie zmieniam: dokument
  prawny zmienia właściciel.

- **Presety Web Kitu dają się w końcu zbudować.** Dziewięć presetów na dwanaście kończyło
  budowę błędem „nieznany typ podstrony”: mapy stron nazywają część podstron po swojemu
  („menu”, „product-index”, „courses-index”, „article”), a rdzeń zestawu zna 35 typów
  i krótką listę nazw zastępczych. Rdzeń leży w katalogu programów serwera, więc
  `site_from_kit` uzupełnia tę mapę w wygenerowanym projekcie tuż przed budową. Sprawdzone
  budową wszystkich dwunastu presetów: agency 55, ecommerce-showcase 101, education 87,
  institution 167, law-firm 221, legal-portal 235, local-services 133, medical 77,
  personal-brand 45, real-estate 74, restaurant 53, saas 96 podstron — każdy w 2–4 s.
  Statyczny test (`test_kazdy_preset_ma_pokryte_typy_podstron`) pilnuje, żeby nowy preset
  nie wszedł z typem bez odpowiednika.
- **Rejestr narzędzi agenta: 91 → 95.** Doszły `lottie_library` (spis animacji na serwerze),
  `asset_library` i `asset_to_site` (biblioteki materiałów) oraz `site_from_template` (gotowa
  witryna z kolekcji wprost do szkicu strony).
- **Biblioteki materiałów serwera w rejestrze narzędzi.** Na serwerze leżą gotowe materiały —
  ilustracje SVG, wzory i tekstury teł, gradienty, makiety urządzeń, animowane tła WebGL,
  shadery, biblioteki animacji CSS, dźwięki, podkłady muzyczne, LUT-y i przejścia wideo — ale
  dla agenta nie istniały, bo nic ich nie wypisywało. `asset_library` pokazuje, co jest
  (z zawężaniem po nazwie i dziale), `asset_to_site` wstawia wybrany plik do szkicu strony.
  Ścieżka materiału jest rozwiązywana wyłącznie wewnątrz katalogu działu — „..” odpada.
  Same biblioteki (ilustracje unDraw, Carbon, Twemoji, Open Peeps, Humaaans, wzory, tekstury,
  gradienty, makiety, tła WebGL, shadery, dźwięki, podkłady, LUT-y, przejścia) leżą
  w `/danaco/programy`, nie w repozytorium — korzysta z nich każdy projekt na serwerze,
  a repozytorium nie puchnie. Materiał, którego tutejsze programy nie otworzą (dziewięć LUT-ów
  ACES z niestandardowym zakresem wejścia), leży osobno w `nieobslugiwane-ffmpeg` i nie trafia
  do spisu — dla programów do montażu jest poprawny, więc go nie kasujemy. Stan po instalacji: grafika 27 zestawów (m.in. unDraw 1415
  ilustracji, Carbon 6315 piktogramów, Twemoji 4027, Open Peeps), ruch 43 zestawy (tła WebGL,
  shadery, biblioteki animacji, kolejne animacje Lottie), media 19 zestawów (dźwięki CC0,
  podkłady, LUT-y, przejścia GL Transitions). Wszystko na licencjach z allowlisty; licencja
  każdego zestawu jest w manifeście i wraca w spisie narzędzia.
- **Biblioteka animacji Lottie na serwerze.** Był sam odtwarzacz i zero animacji — „ożywienie”
  strony albo materiału oznaczało, że użytkownik musi przynieść plik. Teraz na serwerze leży
  **451 animacji** (`airbnb/lottie-android`, Apache-2.0) z wykazem; `lottie_library` je wyszukuje,
  a `render_lottie` renderuje wybraną pozycję do MP4, WEBM, GIF-a albo klatki PNG bez pliku od
  użytkownika. Nazwa animacji jest sprawdzana wzorcem i rozwiązywana wyłącznie wewnątrz biblioteki.
- **Kolekcja szablonów otwartych w końcu widoczna i użyteczna.** `site_kit_catalog`
  zgłaszał zero szablonów, bo czytał wyłącznie zbiorczy wykaz, który bywa starszy od kolekcji
  albo go w ogóle nie ma. Teraz spis idzie ze stanu na dysku: `meta.json` każdego szablonu
  plus sprawdzenie, czy ma gotową, zbudowaną witrynę. Kolekcja urosła tego wieczoru ze 74 do
  113 szablonów, a gotowych witryn z 42 do 81. Wstawienie sprawdzone na całej kolekcji:
  80 z 81 wchodzi do szkicu bez błędu; jedna przekracza limit 2000 plików strony i mówi o tym
  przed kopiowaniem, a nie w jego połowie. Ośmiu szablonów Next.js dobudowanych wcześniej
  nie ma w tej liczbie — dały artefakty serwerowe bez arkuszy stylów i zostały usunięte.
  Nowe narzędzie `site_from_template` wstawia taką witrynę do szkicu strony bez budowania —
  w sekundy (witryna na 135 podstron — 0,75 s), razem z informacją o licencji szablonu.
  Pojedynczy plik spoza wykazu typów szkicu (animacja Rive, mapa źródeł, `.htaccess`)
  jest pomijany z adnotacją, a nie wywala całej witryny — sprawdzone wstawieniem
  wszystkich 42 gotowych szablonów. W module Strony obie drogi stoją obok
  siebie: „Albo zacznij od gotowego układu” (preset branżowy, treści po polsku, budowa
  w minuty) i „Gotowe witryny z kolekcji” (projekt otwarty, od ręki, licencja przy każdej
  pozycji).
- **Gotowe układy branżowe w module Strony.** Na serwerze stoi Danaco Web Kit z presetami
  i motywami, ale moduł pokazywał wyłącznie puste pole „opisz stronę”. `GET /api/strony/kit`
  podaje presety z polskimi nazwami, a pusty moduł proponuje je jednym kliknięciem —
  witrynę buduje z nich agent narzędziem `site_from_kit`.
- **Limit kont próbnych na adres IP: 5 → 20 (i do ustawienia).** Pięć kont na dobę z jednego
  adresu blokowało całe biuro i użytkowników jednego operatora komórkowego — wszyscy siedzą za
  wspólnym adresem, a „Wejdź bez rejestracji” jest główną drogą wejścia ze strony produktu.
  Limit jest teraz w ustawieniach (`goscie_na_adres`), więc da się go zmienić bez zmiany kodu.
- **Znaczniki strony w końcu zmieniają się razem z ekranem.** Moduł `seo.ts` (tytuł, opis,
  adres kanoniczny, Open Graph, reguła dla robotów) istniał, ale nikt go nie wołał — aplikacja
  jest jednostronicowa, więc wyszukiwarka i podgląd odsyłacza widziały znaczniki z `index.html`
  niezależnie od tego, co jest na ekranie, a ekrany za logowaniem nie dostawały „noindex”.
  Teraz `App` aktualizuje je przy każdej zmianie ekranu; pilnuje tego test.
- **Podgląd odsyłacza działa też dla robotów bez JavaScriptu.** Facebook, LinkedIn, Slack
  i WhatsApp nie uruchamiają skryptów — widzą wyłącznie HTML z serwera, więc każdy odsyłacz
  do cennika, funkcji czy wpisu bloga pokazywał ten sam tytuł i opis z `index.html`. Serwer
  podmienia teraz znaczniki w serwowanym dokumencie: adresy stałe z wykazu
  (`backend/nexus/api/znaczniki.py`), a wpisy bloga, artykuły bazy wiedzy i dokumentację —
  z danych w bazie, razem z `og:image` i regułą `noindex` ze szkicu. Adresy aplikacji idą bez
  zmian, więc zachowują żądania warunkowe i nie kosztują ani jednego zapytania do bazy.
- **Podpowiedź „Strona, która żyje”.** Pusty czat proponował osiem rezultatów, ale żaden nie
  mówił, że strona może mieć animowane tło i ilustracje z biblioteki serwera zamiast płaskiego
  koloru. Dziewiąta podpowiedź to pokazuje.
- **Puste moduły mówią, co potrafią.** Studio wypisuje osiem działań, jakie wykona
  z nagraniem, Baza wiedzy proponuje gotowe nazwy kolekcji, Poczta pokazuje obsługiwanych
  dostawców i to, co zrobi ze skrzynką. Pole na plik ma własną wysokość zamiast paska
  na środku pustego ekranu.
- **Strefa robocza, przedsionek i produkcja.** Do tej pory usługa serwowała wprost z katalogu
  repozytorium: każdy zapis pliku był natychmiast produkcją, nie było czego obejrzeć przed
  wypuszczeniem i nie było do czego wrócić po awarii. Teraz `deploy/wydania/zbuduj.sh` robi
  z drzewa roboczego niezmienny artefakt — ale dopiero po bramce (ruff, pytest, tsc, vitest),
  więc wydanie z czerwonym testem w ogóle nie powstaje. `wypchnij.sh przedsionek` wystawia je
  pod `https://test.danaco-nexus.pl` (hasło, `noindex`, osobna baza `nexus_przedsionek`
  i osobne dane), `wypchnij.sh produkcja` promuje to, co stoi w przedsionku, a `cofnij.sh`
  wraca do poprzedniego sprawnego wydania przestawieniem dowiązania — w kilka sekund, bez
  budowania. Opis: `deploy/wydania/README.md`.

- **„Wypróbuj” otwiera aplikację, a nie pokaz obok niej.** Wejście pod `/wyprobuj` zakłada
  konto próbne (`POST /api/auth/gosc`) i wpuszcza gościa do tego samego okna, z którego
  korzystają klienci: rozmowa, pliki, narzędzia, przydział kredytów okresu próbnego i własna
  przestrzeń. Konto ma termin ważności, a z jednego adresu wolno założyć pięć takich kont.
  Osobna piaskownica (`/api/demo`, ekran `Piaskownica`) zniknęła — pokazywała atrapę
  produktu zamiast produktu. Testy: `backend/tests/test_konto_probne.py`.
- **Programy serwera podpięte pod agenta — 59 → 82 narzędzia.** Na dysku leżały programy,
  z których agent nie mógł skorzystać, bo nie miały narzędzia w rejestrze. Doszło dwadzieścia
  trzy: projekt graficzny od zera (`design_vector`, `design_compose`, `icon_find`,
  `render_lottie`), praca na zdjęciu (`colorize_photo`, `restore_faces`, `inpaint_photo`,
  `depth_map`, `blur_background_by_depth`, `animate_photo`), dźwięk i nagrania
  (`clean_audio`, `split_audio_tracks`, `transcribe_speakers`, `edit_subtitles`,
  `video_to_gif`), dokumenty (`typeset_document` — skład do druku Typstem,
  `convert_text_format`, `analyze_document_structure`, `read_document_aloud`) oraz strony
  i kod (`web_audit`, `web_screenshot`, `site_optimize_assets`, `code_check`).
  Świadomie pominięte: rozpoznawanie twarzy (modele niekomercyjne, dane biometryczne
  wymagają osobnej decyzji o zgodzie), GIMP Script-Fu i surowy FFmpeg (pokrywają się
  z `imagemagick` i `media_process`). Wykaz reszty luki: `docs/LUKA-NARZEDZI.md`.
- **Projektowanie grafiki.** Dwa narzędzia domykają lukę, przez którą agent umiał wyłącznie
  poprawiać cudze pliki: `design_vector` projektuje grafikę od zera (logo, plakat, okładka,
  ulotka, ikona, infografika) jako dokument SVG i oddaje PNG, SVG oraz PDF do druku, a
  `design_compose` składa kadr z warstw (baner, post, miniatura) z warstwą wektorową na
  wierzchu. Rysunek nie może pobierać zasobów z sieci ani zawierać kodu. Rejestr ma teraz
  61 narzędzi w dziewięciu dziedzinach. Testy: `backend/tests/test_projekt.py`.
- **Sprzedaż włączona.** Konto Stripe było wspólne dla projektów Danaco, ale produktów
  Nexusa nigdy w nim nie założono — stąd „Cena przy starcie” i przycisk „Powiadom mnie”
  zamiast zakupu. `deploy/stripe-zaloz-produkty.py` zakłada je idempotentnie (rozpoznaje
  po `metadata.nexus`, więc powtórne uruchomienie niczego nie dubluje) i wypisuje gotowe
  wpisy do `.env`. Ceny: Osobisty 89 zł/mies. (890/rok), Pro 199 (1990), Grupa 49 za
  użytkownika (490); pakiety kredytów 5 000 za 79 zł, 20 000 za 249 zł, 60 000 za 599 zł —
  przy największym stawka za kredyt schodzi do poziomu planu Pro. Rok to dziesięciokrotność
  miesiąca, czyli dwa miesiące w prezencie.
- **Cennik na stronie czyta ceny z serwera.** Karty planów miały kwoty i przyciski wpisane
  w treść strony, więc mówiły o niedostępnej sprzedaży także wtedy, gdy ceny już były
  w Stripe. Teraz kwota, znacznik i przycisk pochodzą z `GET /api/platnosci/cennik`,
  a treść strony zostaje przy tym, czego serwer nie zna: dla kogo jest plan i co obejmuje.
  Przy wyłączonej sprzedaży albo braku odpowiedzi wracamy do treści statycznej.
- **Plan „Zespół” to teraz „Grupa”.** Cena liczy się za każdego użytkownika, a zakres pracy
  jest wspólny i przedłuża go założyciel grupy; rolę założyciela można przekazać. Nazwa,
  opis i lista funkcji mówią to samo co katalog planów i co Stripe. Mechanikę tego planu
  opisuje osobny wpis niżej.
- **Włączenie sprzedaży jednym poleceniem** (`deploy/zapisz-stripe.sh`). Moduł płatności
  był gotowy — plany, kredyty, pakiety, faktury, kupony, portal rozliczeniowy, webhooki —
  ale bez poświadczeń konta Stripe `sprzedaz_aktywna` jest fałszem i cennik pokazuje
  „powiadom mnie” zamiast przycisku zakupu. Skrypt pyta o klucz i ceny, zapisuje sekrety
  z prawami 600, uzupełnia `.env`, restartuje API i sprawdza, czy cennik naprawdę wystawia
  zakup. Przyjmuje klucze prawdziwe i testowe — o tym, czym sprzedajemy, decyduje właściciel.
- **Synchronizacja i wersje plików zaczynają się w planie Pro.** Plan Osobisty miał
  w katalogu `synchronizacja=True`, choć to właśnie synchronizacja i wersjonowanie mają być
  powodem przejścia wyżej. Katalog planów i lista funkcji na stronie mówią teraz to samo.
- **Przycisk instalacji w pasku przestał się łamać na telefonie.** Pełna nazwa „Zainstaluj
  aplikację” schodziła przy 390 px do dwóch wierszy i rozpychała nagłówek; na wąskim ekranie
  zostaje samo „Zainstaluj”, a pełne wezwanie i tak stoi w hero kilka centymetrów niżej.
- **Kalendarz konta nie wita już czerwonym paskiem.** Moduł i agent pytają o kalendarz
  równolegle przy pierwszym wejściu na konto; obie próby zakładały tę samą kolekcję,
  a przegrywająca dostawała z Nextcloud 500 zamiast 405 i użytkownik widział „utworzenie
  kalendarza konta nie powiodło się” nad działającym kalendarzem. Teraz przed ogłoszeniem
  awarii sprawdzamy stan faktyczny: gdy kalendarz jest, nie ma o czym mówić.
- **Słowo „kredyt” zniknęło z tego, co widzi klient.** Pasek wykorzystania był już bez
  liczb, ale obok stały zdania, które je przywracały: cennik tłumaczył, czym jest kredyt,
  opis okresu próbnego obiecywał „300 kredytów”, a regulamin opisywał nieistniejące już
  „pakiety kredytów”. Wszystkie trzy mówią teraz o zakresie pracy i o przedłużeniu dostępu
  kwotą — czyli o tym, co klient naprawdę kupuje i widzi. Regulamin dostał przy okazji
  poprawny opis przelicznika kwoty na zakres. Ten sam przegląd objął treści portalu
  (opis planu Grupa, odpowiedź w „Najczęstszych pytaniach”) i katalog planów po stronie
  serwera, żeby jedno i drugie mówiło to samo.
- **Bramka wydania nie wisi już w nieskończoność.** Dwa pełne przebiegi testów naraz
  potrafią się zakleszczyć w okolicy `test_agent.py::test_subagents_become_nested_events`
  (atrapa CLI uruchamia prawdziwy serwer MCP jako proces wnuka). Budowa stała wtedy
  godzinami i trzymała blokadę bramki, więc żadne kolejne wydanie nie mogło powstać.
  Teraz przebieg ma limit czasu i zrzut stosów (`faulthandler`), a blokadę bramki da się
  wskazać osobno (`BRAMKA_LOCK=…`), żeby po zakleszczeniu uruchomić budowę obok zamiast
  czekać na proces, który nigdy nie skończy. Samo zakleszczenie zostaje do zdiagnozowania.
- **Plan Grupa przestał być samym opisem w cenniku.** Dało się go kupić, ale nie dało się
  nikogo do grupy dodać. Teraz jest mechanika: założyciel zakłada grupę, zaprasza adresem
  e-mail (jednorazowy odsyłacz z terminem ważności), a praca każdego członka schodzi ze
  wspólnej puli — czyli z konta założyciela, bo to on płaci za każde miejsce. Rolę
  założyciela można przekazać innemu członkowi; założyciel nie wyjdzie z grupy, dopóki
  tego nie zrobi, żeby nie została grupa bez płatnika. Konto należy najwyżej do jednej
  grupy, a zaproszenie działa tylko z adresu, na który je wystawiono.
  Panel w module Płatności trzyma się tej samej zasady co reszta interfejsu: skład to
  lista z rolami, zaproszenie to jedno pole, a rzeczy nieodwracalne (usunięcie kogoś,
  przekazanie roli, rozwiązanie grupy) stoją pod trzema kropkami.
  Rozliczenie jest naprawdę za użytkownika: w kasie Stripe kupujący ustala liczbę miejsc
  (od 2 do 20), a 49 zł mnoży się przez tę liczbę — wcześniej była to cena całej grupy,
  czyli co innego, niż mówi cennik. Liczbę opłaconych miejsc zapisuje webhook i to ona,
  a nie limit z katalogu planów, rozstrzyga, ile osób zmieści się w grupie.
  Testy: `backend/tests/test_grupy.py`, `frontend/src/platnosci/grupa.test.tsx`.
- **Terminal modułu Kod: nazwa programu, limit tempa, wykaz właścicieli pod blokadą.**
  Trzy usterki zgłoszone przez parę P10. (1) Wykaz dozwolonych programów sprawdzał samą
  nazwę pliku, więc `./git` z własnego projektu przechodził jako „git” — program podaje się
  teraz nazwą, a ścieżkę rozwiązuje PATH piaskownicy. (2) Wykonywanie poleceń nie miało
  ograniczenia tempa, a każde polecenie to proces, który potrafi zająć rdzeń na minuty;
  jest limit na konto (60 poleceń na pięć minut). (3) Wykaz właścicieli projektów czytał
  i zapisywał się bez blokady, a każdy błąd odczytu dawał pusty wykaz — czyli po cichu
  przepisywał projekty wszystkich kont na właściciela instalacji. Teraz odczyt-zmiana-zapis
  idzie pod `flock`, a uszkodzony plik kończy się odmową, nie zmianą właściciela.
- **Środowisko serwera przestało wchodzić do piaskownicy.** `bwrap` bez `--clearenv`
  dziedziczy całe środowisko procesu roboczego, a w nim stoją adres bazy, ścieżki do plików
  z kluczem Stripe i hasłem chmury oraz adresy usług wewnętrznych. Z konta próbnego
  wystarczyło `node -p process.env` w terminalu modułu Kod, żeby to wypisać — plików
  z sekretami nie było widać, ale mapa do nich już tak. Teraz środowisko powstaje od zera
  z wykazu dodającego (`piaskownica.srodowisko`): do środka wchodzi `PATH`, `HOME`, język
  i katalog tymczasowy, a proces CLI dodatkowo własne zmienne `CLAUDE_*`, `MCP_*` i `GIT_*`.
  Żadnej zmiennej `NEXUS_*`. Wykaz jest dodający, nie odejmujący — nowa zmienna
  konfiguracji nie przecieka sama z siebie. Testy: `backend/tests/test_piaskownica.py`
  (podstawiona zmienna z sekretem nie dociera do wnętrza).
  Usterkę zgłosiła para P10 z fali „dostępność, wydajność, bezpieczeństwo”.
- **Agent nie widzi już plików serwera.** Instrukcja trybu Kod mówiła „nie wychodź poza
  katalog projektu”, ale niczego to nie egzekwowało: `Read` i `Bash` przyjmują ścieżki
  bezwzględne, więc sesja programistyczna mogła przeczytać kod samego Nexusa, cudze projekty
  na dysku i katalog producenta. Teraz proces CLI startuje w osobnej przestrzeni montowań
  (`bwrap`): widzi katalog projektu użytkownika, profil sesji, katalog roboczy zadania oraz
  łańcuch narzędzi `/danaco/programy` do odczytu — i nic poza tym. Reszty dysku w tej
  przestrzeni po prostu nie ma, więc nie da się jej ani odczytać, ani wymienić.
  Serwer narzędzi MCP potrzebuje kodu Nexusa i bazy, więc został **poza** piaskownicą:
  CLI rozmawia z nim przez gniazdo w katalogu zadania (`nexus/agent/most_mcp.py`).
  Testy: `backend/tests/test_piaskownica.py`.
- **Agent dostał przeglądarkę.** Miał wyszukiwarkę, odczyt strony po HTTP i jednorazowy
  zrzut — czyli wszystko, co zaczyna się od kliknięcia, było dla niego zamknięte: zakładka,
  rozwijana lista, wyszukiwarka wewnątrz serwisu, formularz, strona doczytywana skryptem.
  Teraz ma jedno okno Chromium na czas zadania: `browser_open`, `browser_click`,
  `browser_type`, `browser_scroll`, `browser_back`. Każde działanie zwraca adres, tytuł,
  tekst i wykaz elementów, w które da się kliknąć — model wskazuje je napisem widocznym na
  stronie, a przy chybieniu dostaje listę tego, co na stronie jest. Adresy przechodzą przez
  tę samą ochronę przed SSRF co odczyt po HTTP; sieć wewnętrzna serwera zostaje zamknięta.
- **Animacja wyjaśniająca zamiast obrazka.** Na serwerze stał silnik Manim i nie był
  podpięty do niczego, więc „wytłumacz mi to na animacji” kończyło się statycznym rysunkiem.
  Narzędzie `animate_explainer` renderuje scenę pisaną przez agenta: rysujący się wykres,
  przekształcający wzór, schemat wchodzący element po elemencie. Scena to kod, więc render
  idzie przez tę samą piaskownicę co sesja programistyczna — bez wyjścia do sieci i bez
  dostępu do czegokolwiek poza katalogiem zadania. Narzędzi agenta: 83 → 91.
- **Witryny powstają z zestawu Danaco Web Kit, a nie od pustego pliku.** Na serwerze stał
  gotowy warsztat — 12 presetów branżowych, 11 motywów, 147 sekcji, 36 typów podstron,
  18 krojów nagłówkowych i kolekcja 74 szablonów otwartych z 2744 blokami — i nie był
  podpięty do niczego. Doszły dwa narzędzia: `site_kit_catalog` pokazuje, co jest do
  wzięcia, a `site_from_kit` generuje witrynę z presetu i motywu, buduje ją offline
  (zależności ze wspólnego magazynu pnpm) i wstawia gotowe pliki do szkicu strony
  użytkownika. Publikuje dalej wyłącznie człowiek przyciskiem.
  Sprawdzone na prawdziwym presecie: „law-firm” daje 221 podstron zbudowanych offline
  w dwie sekundy — 486 plików i 21 MB, czyli mieści się w limitach szkicu strony.
- **Angielskie napisy zniknęły z modułu Badania.** Historia badań podpisywała wyniki
  „Deep Research” i „Scholar Research”, a tytuły raportów zaczynały się od „Research:”
  i „Scholar:” — w produkcie, który cały jest po polsku. Teraz to „Sieć” i „Prace naukowe”,
  a nowe raporty noszą tytuł „Badanie sieci: …” albo „Prace naukowe: …”. Nazwa kolekcji
  domyślnej zostaje w bazie bez zmian (to identyfikator, nie etykieta) — zmienia się tylko
  jej opis w oknie wyboru.
- **Żądanie warunkowe z gwiazdką odpowiada zgodnie z normą.** `If-None-Match: *` znaczy
  „dowolna wersja tego zasobu” (RFC 9110 §13.1.2) — skoro plik istnieje, należy odpowiedzieć
  304. Gwiazdka wpadała w porównanie znaczników, nie pasowała do żadnego i serwer odsyłał
  całą treść przy każdym odświeżeniu.
- **Nazwa zajętego projektu nie mówi, czyj on jest.** Katalogi projektów leżą we wspólnej
  przestrzeni nazw, więc 409 potwierdzało zajętość także wtedy, gdy projekt należał do kogoś
  innego, i komunikat mówił „Projekt o tej nazwie już istnieje”. Teraz mówi tylko tyle,
  że nazwa odpada.
- **Plakaty filmów w formacie WebP.** Dwie okładki ważyły 940 KB w PNG przy 78 KB w WebP,
  a obie wersje leżały obok siebie na dysku; strona pobierała cięższą. Oszczędność:
  861 KB na pierwszym wejściu.
- **Portal przestał zapisywać błąd w konsoli przy każdym wejściu.** Sprawdzenie, czy ktoś
  jest zalogowany, szło przez `/api/portal/konto/ja` — zasób chroniony, który gościowi
  odpowiada 401. Przeglądarka odnotowywała to jako błąd na każdej stronie publicznej,
  choć nic złego się nie działo. Doszedł punkt `GET /api/portal/konto/sesja`: pytanie
  o stan, nie o zasób, więc brak sesji to zwykła odpowiedź `{"konto": null}`. Zasób
  chroniony nadal odmawia — to nie jest obejście uwierzytelnienia.
- **Konto w panelu bocznym otwiera menu.** Pozycja z nazwą użytkownika miała obok dwie
  ikony bez nazwy i nic poza nimi — ustawienia, wygląd i rozliczenia leżały rozsypane po
  modułach, a stanu dostępu nie dało się sprawdzić bez wyjścia z rozmowy. Teraz to jedno
  wejście: pasek wykorzystania dostępu (bez liczb, jak wszędzie), Ustawienia, Plan i dostęp,
  przełącznik motywu z nazwą tego, co jest ustawione, i wylogowanie.
- **Dwa menu w panelu przestały się powtarzać.** Trzy kropki u góry i konto na dole
  oferowały to samo (Ustawienia, Wyloguj), więc trzeba było zgadywać, czym się różnią.
  Trzy kropki dotyczą teraz wyłącznie panelu rozmów (zwijanie), a wszystko, co dotyczy
  konta, stoi w menu konta.
- **Uszkodzony wykaz właścicieli projektów daje czytelną odmowę, nie pięćsetkę.**
  Odmowa jest chwilowa i mówi, co się stało; wcześniej wychodził z tego błąd wewnętrzny.
- **Pasek modułów bez napisów nad grupami.** Nagłówki „ROZMOWA”, „TWOJE RZECZY” i reszta
  musiały być skracane do wersalików wysokich na 10 px w pasku szerokim na 88 px —
  czytało się je gorzej, niż gdyby ich nie było. Podział został, ale robi go odstęp
  i kreska; czytnik ekranu dostaje go przez `aria-label` grupy.
- **Wejście na konto próbne ma to samo domknięcie co logowanie.** Pasek postępu znikał,
  a okno aplikacji pojawiało się w tej samej klatce. Teraz po założeniu konta leci ujęcie
  z pakietu ruchu — jedno miejsce (`ruch/EkranPrzejscia.tsx`) obsługuje logowanie, wejście
  gościa i wylogowanie, więc wszystkie trzy przejścia zachowują się tak samo.
- **Ekran logowania przestał puszczać film o logowaniu.** Ujęcie „logowanie” pokazuje to,
  co dopiero ma się wydarzyć, a chodziło w tle formularza, pod polami, w których człowiek
  właśnie pisze. Zostało spokojne tło; ujęcie gra po udanym logowaniu, jako przejście do
  aplikacji — tak jak ujęcie wylogowania przy wyjściu.
- **Zmiana modułu jest widoczna.** Aplikacja podmieniała cały obszar bez śladu ruchu, więc
  nie było widać, że to zmiana widoku, a nie przeładowanie. Przejście bierze sam podmieniany
  obszar, więc pasek modułów i panel rozmów stoją nieruchomo.
- **Otwarcie strony nie nakłada się już na wejście nagłówka.** Sygnał „plansza schodzi”
  szedł w chwili rozpoczęcia zanikania: znak był jeszcze na ekranie, a pod nim leciały już
  słowa nagłówka — z boku wyglądało to jak dwie animacje naraz. Strona rusza teraz dopiero
  wtedy, gdy plansza zejdzie do końca.
- **Moduł Kod przestał wyglądać na niegotowy.** Ekran bez wybranego projektu zajmuje trzy
  czwarte okna, a stała na nim jedna linijka na środku pustki. Teraz jest tam nazwa, zdanie
  o tym, co moduł naprawdę robi, i przycisk „Nowy projekt” — czyli to, co człowiek ma zrobić
  dalej. Podgląd pliku bez wyboru tłumaczy, skąd wziąć plik i gdzie są zmiany; sesja zaczyna
  się trzema gotowymi zdaniami do kliknięcia zamiast akapitu z przykładem w cudzysłowie,
  który trzeba było przepisać ręcznie. Kolumna projektów nazywa się „Projekty”, a nie drugi
  raz „Kod”.
- **Strona produktu ma nawigację na telefonie.** Pasek chował wszystkie odsyłacze poniżej
  `lg`, a „Zaloguj się” poniżej `sm` — na telefonie zostawał sam przycisk instalacji i do
  cennika, pytań czy logowania trzeba było przewinąć dwadzieścia parę tysięcy pikseli do
  stopki. Doszło menu: wszystkie sekcje paska, wypróbowanie i logowanie, zamykane Escape
  i wyborem pozycji. Testy: `frontend/src/__tests__/mobil.test.tsx`.
- **Propozycje na pustym ekranie dostały hierarchię.** Osiem jednakowych kafli czytało się
  jak spis treści — wszystko wyglądało tak samo ważne, więc oko nie miało się czego złapać.
  Zostały dwie karty z opisem, które mają zaczepić, i sześć jednowierszowych podpowiedzi,
  bo do nich wystarczy sama nazwa rezultatu. Opis dalszych widać po najechaniu.
- **Arkusz „Więcej” przestał być kalkulatorem.** Osiemnaście jednakowych kafli zasłaniało
  trzy czwarte ekranu i każda pozycja wyglądała tak samo ważna, choć mówiła tylko nazwę.
  Teraz każda forma ma swoje zadanie: pole wyszukiwania dla tych, którzy wiedzą, czego
  szukają (szuka też bez polskich znaków); wiersz szybkiego wyboru dla czterech rzeczy
  codziennych; zgrupowana lista z jednozdaniowym opisem przy każdej pozycji zamiast siatki
  ikon; ustawienia i rozliczenia w osobnym pasku pod kreską, bo to nie są narzędzia do
  pracy. Arkusz ma limit wysokości i przewija się w środku.
  Przy okazji wyszła usterka, która by go uziemiła: pasek dolny chowa się na czas pisania,
  a nowe pole wyszukiwania ustawia w nim kursor — arkusz zamykał się w tej samej chwili,
  w której się otwierał. Chowanie obejmuje teraz sam pasek, nie arkusz.
- **Pusty ekran rozmowy mieści się na telefonie.** Osiem kafli podpowiedzi w jednej kolumnie
  to było półtora ekranu przewijania, zanim człowiek dochodził do pola wiadomości; do tego
  podpowiedź o skrócie Ctrl+K na urządzeniu bez klawiatury i trzywierszowy pasek konta
  próbnego. Na telefonie zostają cztery kafle, krótsze zdanie w pasku i żadnych skrótów
  klawiszowych; od `sm` wszystko wraca.
- **Wyjście z aplikacji ma swoje domknięcie.** Pakiet ruchu wydał osobne ujęcie na
  wylogowanie i jako jedyne nie było podpięte: kliknięcie „Wyloguj” gasiło okno w tej samej
  klatce, co wyglądało na awarię, nie na zamknięcie sesji. Sesja zamyka się dalej od razu —
  ujęcie przykrywa tylko ten moment i ma bezpiecznik, gdyby się nie wczytało. Przy
  `prefers-reduced-motion` przejście jest natychmiastowe.
- **Nagrania na stronie stają, gdy nikt na nie nie patrzy.** Scena produktu w hero i dwie
  zajawki filmów chodziły w pętli przez całą wizytę — także kilkanaście tysięcy pikseli
  niżej, gdzie ich nie widać. Procesor dekodował wtedy obraz, którego nie ma na ekranie,
  a na telefonie schodziła z tego bateria. Odtwarzanie jest teraz związane z widocznością
  (`useOdtwarzajWWidoku`): wchodzi w kadr — gra, wychodzi — staje. Ten sam hak obsługuje
  ujęcia z pakietu ruchu, więc reguła jest jedna dla całej strony.
- **Animacja instalacji pokazuje wreszcie animację, a nie czarny prostokąt.** Scena
  z pakietu ruchu ma 1920 × 1080 px, ale cały ruch — okno instalacji, oderwanie ikony, lot
  i lądowanie w doku — mieści się w środkowej kolumnie (35–65% szerokości) i schodzi z góry
  na dół. Pokazana w całości była w siedmiu dziesiątych pusta: widać było czarne pole
  i pasek ikon przy dolnej krawędzi. Ujęcie jest teraz przycięte do tego, co się w nim
  dzieje (720 × 840 px, kadr zmierzony na pierwszej i ostatniej klatce), a sekcja pokazuje
  je w rozmiarze, w którym dok i ikona są czytelne.
- **Kreska w stopce idzie po krawędzi treści.** Obramowanie stało na paśmie treści, które
  ma własne odstępy boczne — linia wychodziła o te odstępy poza tekst z obu stron i nie
  trzymała się kolumn wyżej. Dotyczyło stopki strony produktu i stopki portalu.
- **Regulamin zgodny z tym, co jest w sprzedaży.** Paragraf o planach mówił, że Pro
  i „Zespół” są oznaczone jako „Wkrótce” i nie podają ceny — a ceny stoją w Stripe i zakup
  działa. Plan nazywa się „Grupa”, a jego paragraf opisuje wreszcie rozliczenie za
  użytkownika, wspólny zakres pracy i przekazanie roli założyciela.
- **Cennik: koniec z „Wkrótce” przy planach, które da się kupić.** Znacznik z treści strony
  jest wartością zastępczą na czas, gdy serwer milczy; przy włączonej sprzedaży mówił
  nieprawdę o planach Pro i Grupa. Karty dostały też rozwijane „Co dokładnie obejmuje”
  z pełnym zakresem planu i limitem pliku prosto z serwera — wcześniej karta kończyła się
  na sześciu hasłach i po resztę trzeba było iść do portalu.
- **Sekcja pytań nie zasłania już strony.** Dwadzieścia pozycji jedna pod drugą było dłuższe
  niż cała reszta strony. Widać sześć pierwszych; resztę otwiera przycisk.
- **Animacja instalacji przestała się urywać.** Ujęcie „moment-instalacja” trwa 1200 ms,
  a grało od razu po wczytaniu strony — zanim ktokolwiek zszedł do sekcji „Instalacja”,
  było po wszystkim i zostawała zamrożona ostatnia klatka. Teraz startuje dopiero, gdy
  sekcja wejdzie w pole widzenia, i wraca co trzy sekundy. Przy okazji zniknęła z niego
  wypalona plansza „Instalacja zakończona · 1200 ms” — to był podpis z pokazu dla zespołu,
  nie element produktu (nagranie `-alfa`, jak w pozostałych momentach).
- **Moduł Agenci pozwala wreszcie tworzyć agentów.** Nazywał się „Agenci”, a dało się
  w nim wyłącznie zlecić zadanie w tle — żadnego agenta nie można było zdefiniować.
  Teraz użytkownik zapisuje własne specjalizacje (nazwa, opis, instrukcja, tryb, projekt)
  i uruchamia je jednym kliknięciem; instrukcja dokleja się do zadania, więc agent trzyma
  swoją rolę. Zestaw startowy: Redaktor, Analityk, Sekretarz. Agenci należą do konta
  i nie przeciekają między kontami. Testy: `backend/tests/test_wlasni_agenci.py`.
- **Kalendarz przestał być samą tabelą.** Obok siatki stoi kolumna „Co przed Tobą”
  z najbliższymi terminami oraz pole, w którym zleca się pracę Nexusowi wprost z kontekstu
  dnia — wcześniej po każde zlecenie trzeba było wracać do czatu i opisywać terminy od nowa.
- **Moduł Kod: terminal i podział okna.** Doszła zakładka Terminal — polecenie wykonuje
  się w katalogu projektu i widać surowe wyjście, zamiast czytać relację agenta.
  To celowo nie jest powłoka: jedno polecenie naraz, bez potoków i przekierowań, wyłącznie
  z wykazu programów (`git`, `npm`, `pytest`, `ruff`, `go`, `cargo`…), z limitem czasu
  i obciętym wyjściem. Sesję można też rozdzielić na dwie obok siebie, żeby prowadzić dwa
  wątki naraz. Testy: `backend/tests/test_kod_terminal.py`.
- **Przybornik zaznaczenia w przeglądarce — praca bez otwierania okna.** Panel boczny
  jest dobry, gdy ktoś chce rozmawiać; częściej wystarczy jedna czynność na zaznaczonym
  fragmencie. Rozszerzenie pokazuje teraz przy kursorze pasek ze skrótami użytkownika —
  niewidoczny, dopóki nic nie jest zaznaczone — a wynik wraca do banera obok, z kopiowaniem
  jednym kliknięciem. Kliknięcie gdziekolwiek indziej zamyka wszystko. Skróty układa sobie
  użytkownik w opcjach rozszerzenia: każdy to zwykłe zdanie dla modelu, więc tłumacz ustawi
  sobie inne niż programista. Zestaw startowy: przetłumacz, wyjaśnij, skróć, popraw, rozwiń,
  odpowiedz, sprawdź kod. Po stronie serwera obsługuje to `POST /api/rozszerzenie/szybka-akcja`:
  jedno pytanie bez narzędzi, bez zapisu w historii rozmów, rozliczane kredytami. Zaznaczenie
  trafia do modelu opisane jako dane, nigdy jako polecenie — pochodzi z obcej strony.
  Testy: `extension/testy/przybornik.test.ts`, `backend/tests/test_przybornik.py`.
- **Rozpoznawanie twarzy** (`find_faces`): wykrywanie twarzy i grupowanie zdjęć tej samej
  osoby — do porządkowania archiwum rodzinnego. Czynność jest opisana w rejestrze RODO
  (CZ-14) wraz z dwiema sprawami do zamknięcia przed wejściem do sklepów z aplikacjami:
  licencją modeli InsightFace i podstawą przetwarzania danych biometrycznych.
- **Trzy sposoby mówienia do Nexusa.** Obok pisania i rozmowy głosowej doszło dyktowanie:
  mikrofon w polu wiadomości nagrywa wypowiedź, a rozpoznany tekst dopisuje się do tego, co
  już jest w polu — zostaje do poprawienia przed wysłaniem. Kto nie chce pisać na klawiaturze,
  nie musi od razu wchodzić w tryb rozmowy.
- **Podpowiedzi startowe napisane po ludzku.** Osiem kafli na pustym czacie mówiło językiem
  poleceń dla maszyny („Rozbij stos skanów") i pokrywało ułamek zakresu. Teraz brzmią jak
  zdania, które człowiek naprawdę napisze, i dotykają kolejno: projektu graficznego, zdjęć,
  dokumentów, pisma, poczty z terminarzem, nagrania, badania ze źródłami i strony internetowej.
- **Przełącznik motywu jako ikona.** Zajmował wiersz w panelu bocznym obok pozycji nawigacji,
  choć jest przełącznikiem, nie miejscem, do którego się przechodzi. Stoi teraz przy koncie,
  obok wylogowania. Zniknął też odsyłacz „Chmura osobista” otwierający chmurę w nowej karcie —
  chmura jest zakładką w oknie aplikacji, sąsiadem zakładki Pliki, a nie wyjściem na zewnątrz.
- **Pakiet ruchu podpięty do aplikacji.** Ujęcia z `motion/start`, które leżały niewykorzystane,
  grają tam, gdzie powstały: uruchomienie okna, tło ekranu logowania, chwila przed pierwszym
  słowem agenta, zakończone zadanie, brak połączenia, instalacja i otwarcie strony produktu.
  Nagranie narzędzia z `motion/stany` leci w karcie kroku, kiedy to narzędzie pracuje — to
  samo ujęcie, które strona pokazuje przy danej dziedzinie. Każde wywołanie respektuje
  ustawienie ograniczonego ruchu. Nagrania mają na sobie wypaloną planszę opisową
  („Intro znaku · 2200 ms”) — podpis z demonstracji dla zespołu, który trafił na produkcję;
  aplikacja bierze teraz warianty `-alfa` bez podpisu, a wykaz momentów, które taki wariant
  mają, jest pilnowany testem zaglądającym na dysk. Testy: `frontend/src/ruch/__tests__/nagranie-startu.test.tsx`.

- **Konta użytkownika z rozdzielonymi przestrzeniami.** Aplikacja przyjmuje logowanie kontem
  portalu, a rozmowy, pliki i przebiegi mają właściciela (`owner_id`) i są widoczne wyłącznie
  dla niego — cudzy zasób odpowiada 404, tak samo jak nieistniejący. Konto administratora
  serwera jest osobną przestrzenią, a nie widokiem na wszystkie. Skrzynki pocztowe są osobne
  dla każdego konta (`dane/app/poczta/<konto>.json`). Przestrzeń konta ma limit 2 GB
  (`NEXUS_KONTO_LIMIT_MB`) sprawdzany przy przesyłaniu plików. Osiem testów w
  `backend/tests/test_izolacja_kont.py`.
- **Kredyty konta.** Kredyt jest jednostką pracy agenta: konto dostaje przydział z planu,
  każdy zakończony przebieg pomniejsza saldo według cennika (żetony modelu plus dopłata za
  narzędzia liczone czasem maszyny), a puste konto nie przyjmuje kolejnego zlecenia. Każda
  zmiana salda ma wpis w księdze. Saldo i historia w module Płatności oraz pod
  `GET /api/platnosci/kredyty`; cennik opisuje `docs/platnosci/KREDYTY.md`.
- **Podłączanie skrzynki pocztowej w aplikacji.** Konto, hasło i serwery podaje się w module
  Poczta (z podpowiedziami dla Gmaila, Outlooka, WP, Onetu, Interii i o2); zapis następuje
  dopiero po udanym logowaniu IMAP i SMTP. Zniknęło zapisywanie poświadczeń skryptem na
  serwerze, przez które każdy zalogowany czytał tę samą skrzynkę.
- Katalog możliwości agenta w trzech miejscach, wszystkie z jednego źródła: sekcja
  „Osiem dziedzin. Jedna rozmowa." na stronie produktu (zakładki dziedzin, nagranie
  pracy narzędzia, przykładowe polecenia), publiczna strona `/portal/narzedzia`
  z wyszukiwaniem oraz moduł „Narzędzia" w aplikacji, w którym kliknięcie przykładu
  otwiera nową rozmowę z gotowym zdaniem. Spis wypisuje `frontend/scripts/narzedzia.py`
  z rejestru `backend/nexus/tools`, więc nie da się obiecać narzędzia, którego nie ma.
- Strona `/portal/zastosowania`: osiem sytuacji z życia i z pracy z animacją kampanijną,
  przykładowym poleceniem i wykazem narzędzi, które wykonują pracę.
- Pełny katalog materiałów ruchomych w aplikacji: `frontend/scripts/zasoby.py` przenosi
  wszystkie nagrania z pakietów `promocja/film`, `promocja/kampania`, `motion/stany`
  i `motion/start` (9 filmów, 20 animacji kampanijnych, 27 animacji stanów, 18 animacji
  startu) i wypisuje ich spis do `frontend/src/media/katalog.ts`.
- Tryb rozmowy głosowej: komunikaty o mikrofonie po polsku (brak zgody, brak urządzenia,
  urządzenie zajęte, brak HTTPS) zamiast surowego tekstu przeglądarki oraz przycisk
  „Spróbuj ponownie" po podłączeniu mikrofonu lub udzieleniu zgody.
- Założenie projektu Danaco Nexus.
- Asystent AI z interfejsem czatu: historia rozmów, przesyłanie plików (przycisk,
  przeciąganie, wklejanie), strumieniowanie odpowiedzi i działań narzędzi, podgląd
  i pobieranie wyników, anulowanie zadań, układ dla komputerów, tabletów i telefonów.
- Agent działający przez Claude Code CLI (`claude-opus-5`, zapasowo `claude-sonnet-5`)
  na subskrypcji konta Claude, z sesją CLI utrzymującą kontekst rozmowy; narzędzia
  udostępnia serwer MCP projektu. Zadania w kolejce PostgreSQL wykonuje proces roboczy.
- Narzędzia agenta (rdzeń): OCR z przeszukiwalnym PDF (Tesseract), poprawa skanów
  (OpenCV, unpaper), korekta zdjęć, retusz portretów, powiększanie Real-ESRGAN,
  ImageMagick, konwersje obrazów i dokumentów (LibreOffice, Inkscape), tworzenie
  dokumentów, korekta językowa (LanguageTool), podział, łączenie i edycja PDF,
  wykrywanie granic dokumentów, audio i wideo (FFmpeg), archiwa ZIP, baza wiedzy
  z wyszukiwaniem semantycznym (Qdrant).
- Logowanie administratora (Argon2, sesje w bazie, ochrona CSRF, limit prób).
- Wdrożenie bez Dockera: skrypt instalacji, własny klaster PostgreSQL 18, Qdrant
  i LanguageTool w katalogu projektu, usługi systemd, szablon witryny Caddy.
- Chmura osobista Nextcloud (FrankenPHP, baza w klastrze projektu, zadania w tle co 5 minut)
  z synchronizacją na komputer i telefon oraz narzędzia agenta `cloud_browse`,
  `cloud_import` i `cloud_save`; odnośnik do chmury w interfejsie.
- Skrypt rekordów DNS w strefie OVH i witryna Caddy dla `danaco-nexus.pl`
  i `cloud.danaco-nexus.pl`.
- Aplikacja PWA: instalacja na Androidzie, iPhonie i Windows, własna ikona, tryb
  pełnoekranowy, powłoka offline, powiadomienie o nowej wersji.
- Nowy interfejs na Tailwind CSS 4: motyw ciemny domyślnie, jasny i systemowy.
- Rozmowa głosowa: mówisz i słuchasz odpowiedzi (Whisper large-v3-turbo, głosy Piper),
  odpowiedź czytana zdanie po zdaniu, przerywanie głosem.
- Transkrypcja mowy z audio i wideo (`transcribe_audio`, faster-whisper).
- Valkey (Redis) projektu: powiadomienia o zdarzeniach zadań i pamięć podręczna chmury.
- Logowanie jednokrotne do chmury z sesji Nexusa; adresy `api.` i `cloud.danaco-nexus.pl`.
- Polecenie diagnostyczne `doctor` (programy, usługi, Claude Code CLI, serwer MCP).
- `frontend/scripts/zasoby.py` — przeniesienie pakietów marki (tokeny, kroje, znak,
  tła, nagrania, film) do katalogu publicznego aplikacji; uruchamiane automatycznie
  przed `dev` i `build`.
- Paleta poleceń pod `Ctrl K`: moduły, rozmowy, zmiana motywu i przekazanie pytania
  do pola wiadomości.
- Klawisz `Esc` zatrzymuje pracującego agenta (obietnica ze strony produktu).
- Dane strukturalne `FAQPage` z czternastoma pytaniami na stronie produktu.
- Piaskownica „Wypróbuj teraz” pod adresem `/wyprobuj` — pokaz bez konta:
  pięć scenariuszy na plikach przykładowych, twarde limity gościa, kasowanie danych
  po wygaśnięciu sesji (`backend/nexus/demo/`, `frontend/src/demo/`).
- Portal produktowy pod `/portal`: oferta, funkcjonalności, cennik, dokumentacja,
  blog, centrum wiedzy, kontakt, konto klienta, panel klienta i panel redaktora;
  własny model treści, wyszukiwanie, kanał Atom, `sitemap.xml` i `robots.txt`
  (`backend/nexus/portal/`, `frontend/src/portal/`).
- Moduł Płatności: plany, subskrypcje, faktury i kupony na Stripe Checkout
  i Billing Portal, webhooki przetwarzane idempotentnie
  (`backend/nexus/platnosci/`, `frontend/src/platnosci/`).
- Materiały kampanii w `promocja/kampania/`: film marki i film funkcji po 30 s oraz
  sześć animacji tematycznych po 15 s w trzech formatach (16:9, 1:1, 9:16) —
  dwadzieścia materiałów, czterdzieści plików wideo (MP4 i WebM), osiemdziesiąt
  plików napisów PL i EN, dwadzieścia okładek i osiem scenopisów.
- Biblioteka komponentów i ruchu (`frontend/src/ui/`) zbudowana na tokenach.
- Metadane wyszukiwarek na stronie produktu (opis, canonical, Open Graph, dane
  strukturalne); ekrany za logowaniem oznaczone jako nieindeksowane.

### Zmieniono

- **Mapa danych w kodzie nie znała sześciu tabel.** `docs/zgodnosc/DANE-W-KODZIE.md` stawia
  zasadę „tabela bez wiersza w tym dokumencie jest luką dokumentacji”, a porównanie
  `Base.metadata.tables` z treścią dokumentu pokazało brak sześciu: `grupy`,
  `grupy_czlonkowie`, `grupy_zaproszenia`, `agenci_uzytkownika`, `pliki_katalogi`,
  `ustawienia_konta`. Najważniejsza z nich trzyma **adres e-mail osoby zapraszanej do
  grupy**, także takiej, która nie ma konta. Wiersze dopisane; przypisanie do czynności
  przetwarzania zostawione do przeglądu prawnego.

- **Blokada bramki nie zostawia już śmieci w korzeniu repozytorium.** `BRAMKA_LOCK` jest
  ścieżką pliku blokady, więc podanie samej nazwy (`BRAMKA_LOCK=gate7`) tworzyło pusty plik
  tam, skąd uruchomiono skrypt. Nazwa bez ukośnika oznacza teraz plik w `wydania/`.

- **Wydanie przestało kopiować te same nagrania od nowa.** Artefakt waży 652 MB, z czego
  589 MB to filmy galerii i kampanii — identyczne w każdym wydaniu, a właściwy kod strony
  to 1,4 MB. Przy kilkunastu wydaniach dziennie katalog `wydania` urósł do 48 GB. Kopia
  gotowego interfejsu idzie teraz przez `rsync --link-dest` do poprzedniego wydania: plik
  bez zmian staje się twardym dowiązaniem, zmieniony kopiuje się normalnie. Wydania są
  tylko do odczytu, `sprzataj.sh` usuwa całe katalogi, a kopia zapasowa obejmuje źródło
  nagrań (`frontend/public`), nie wydania — współdzielenie i-węzłów niczego nie psuje.
  Bez rsynca albo przy pierwszym wydaniu skrypt kopiuje po staremu. Przy okazji znika
  koszt po stronie użytkownika: dowiązany plik zachowuje czas modyfikacji z poprzedniego
  wydania, więc ETag nagrania przestaje się zmieniać po każdym wdrożeniu i przeglądarka
  nie ściąga tych samych 400 MB filmów jeszcze raz.

- **Portal obiecywał pokaz, którego nie ma.** Odpowiedź „Jak zacząć bez zakładania konta?”
  mówiła o pięciu gotowych zadaniach pod `/wyprobuj` (faktura ze skanu, stare zdjęcie…).
  Ten ekran zniknął dawno temu — `/wyprobuj` zakłada konto próbne i wpuszcza do pełnej
  aplikacji, a w `frontend/src/demo/` został sam `WejscieGoscia.tsx`; żaden kod interfejsu
  nie sięga do `/api/demo`. Odpowiedź opisuje teraz to, co gość naprawdę zastanie.
  `docs/demo/README.md` też mówił o ekranie „do podpięcia” — rozdział opisuje stan
  faktyczny i zostawia właścicielowi decyzję, czy zaplecze pokazu (pięć scenariuszy,
  `/api/demo/*`) ma doczekać własnego ekranu, czy zniknąć.
- **Trzy inne miejsca w dokumentacji mówiły o stanie sprzed wdrożeń.** Płatności:
  „brakuje wyłącznie konfiguracji Stripe”, a cennik na produkcji odpowiada
  `sprzedaz_aktywna: true`. Roadmapa i architektura docelowa: „bramki istnieją,
  brakuje automatu” — bez wzmianki, że `deploy/wydania/zbuduj.sh` spina je w jeden
  bieg i bez kompletu zielonych nie wypuszcza wydania. Wszystkie trzy opisują teraz
  stan z dzisiaj.

- **Dokumentacja portalu przestała straszyć niezałataną dziurą.** `docs/portal/README.md`
  opisywał patch „do wykonania” w `auth.py` — licznik nieudanych logowań miał dać się
  obejść nagłówkiem `X-Forwarded-For`. Kod jest poprawiony od dawna i szerzej niż
  w szkicu: nagłówek liczy się wyłącznie w żądaniu z pętli zwrotnej i brany jest jego
  ostatni wpis (`SIECI_PROXY`, `_proxy_zaufane`, `client_ip`), a pilnują tego dwa testy
  w `test_bezpieczenstwo.py`. Rozdział i lista spraw otwartych mówią teraz, jak jest.

- **Jeden tytuł strony na każdej szerokości.** Przemiatanie nagłówków (liczone tylko
  elementy widoczne) pokazało dwie odwrotne usterki. Na komputerze pięć modułów nie miało
  żadnego `h1`: poczta, kalendarz i chmura rysują go tylko w gałęzi z pełnym interfejsem,
  więc w stanie „niepodłączone” znikał, a wiedza i badania miały tytuł jako `h2`. Na
  telefonie siedem modułów miało dwa `h1` naraz — pasek kompaktowy powłoki i własny
  nagłówek modułu: sześć razy z tą samą nazwą („Obrazy”, „Studio”, „Strony”, „Tłumacz”,
  „Ustawienia”, „Agenci”) i raz z dwiema różnymi („Kod” w pasku, „Projekty” w kolumnie).
  Pasek jest teraz etykietą (`p`), a tytuł niesie wyłącznie moduł: widoczny tam, gdzie
  był, i `sr-only` tam, gdzie widocznego nie ma (poczta, kalendarz, chmura, wiedza,
  badania oraz pliki na telefonie). Wygląd bez zmian, a na każdej szerokości jest dokładnie
  jeden `h1`.

- **Nieistniejąca strona portalu też zwraca 404.** Po poprawce dla wpisów został drugi
  przypadek miękkiego 404: adres w rodzaju `/portal/takiej-strony-nie-ma` odpowiadał
  kodem 200 z powłoką. Serwer sprawdza teraz adres na liście stron z mapy witryny
  (`nexus.portal.kanaly.STRONY_STALE` — jedno źródło dla mapy i dla tej kontroli) plus
  cztery strony zamknięte przed robotami: wyszukiwarka, konto klienta, panel klienta
  i panel administratora. Nowa strona portalu i tak musi trafić do tej listy, bo inaczej
  nie ma jej ani w mapie witryny, ani we własnych znacznikach podglądu — a teraz pilnuje
  tego test, który czyta spis stron wprost z `frontend/src/portal/trasy.ts`.

- **Dwie karty podpowiedzi na pustym czacie stoją równo.** Przycisk domyślnie centruje
  swoją treść w pionie, więc karta z krótszym opisem miała tytuł jedenaście pikseli
  niżej niż sąsiednia — na ekranie, który widać po każdym uruchomieniu. Karty układają
  treść od góry (`flex flex-col items-start`).

- **Każde ze 101 narzędzi ma podgląd na karcie.** „Co potrafi Nexus” dobiera do karty
  nagranie z pakietu ruchu, ale wykaz przypisań obejmował 69 pozycji — pozostałe 32
  (wyszukiwanie ikon, biblioteki Lottie i materiałów, przeglądarka agenta, napisy,
  większość narzędzi stron) pokazywały sam znak na szarym tle i wyglądały na
  niedokończone. Wykaz jest domknięty: każda pozycja bierze nagranie sąsiada z tej samej
  rodziny, więc nie przybył ani jeden plik.

- **Koniec cyklu importów w warstwie ruchu.** `ruch/EkranPrzejscia.tsx` brał `ZnakRuchu`,
  `NagranieStartu` i `ograniczonyRuch` z beczki `ruch/index.ts`, a ta eksportuje ten sam
  plik — madge pokazywał cykl `ruch/index.ts > ruch/EkranPrzejscia.tsx`. Import idzie
  teraz wprost do sąsiadów; po zmianie „No circular dependency found” na 252 plikach.

- **Zapasowe pobranie z arXiv ma limit rozmiaru.** Gdy brama arXiv odrzuca zapytanie
  httpx kodem 406, moduł badawczy powtarza je biblioteką standardową — i czytał
  odpowiedź bez żadnego pułapu (`response.read()`), więc obca brama mogła oddać dowolnie
  duży dokument. Teraz obowiązuje 8 MB (odpowiedź dla setki prac to ułamek megabajta),
  a przekroczenie kończy się czytelnym błędem zamiast rosnącym zużyciem pamięci.
  Znalezione przemiataniem semgrep regułami z serwera.

- **Nagłówki w pustych modułach bez przeskoku.** Przemiatanie struktury nagłówków
  (13 modułów i 15 stron portalu) znalazło trzy miejsca ze skokiem z `h1` na `h3`:
  pustostan poczty, kalendarza i chmury stoi wprost pod tytułem modułu, a `EmptyState`
  zawsze rysował `h3`. Komponent przyjmuje teraz poziom nagłówka; w tych trzech
  miejscach jest `h2`, w pustostanach zagnieżdżonych w sekcji z własnym `h2` zostaje
  `h3`. Portal: po jednym `h1` na stronę, zero przeskoków.

- **Puste sekcje portalu przestały odsyłać donikąd.** Blog i centrum wiedzy bez wpisów
  radziły „zajrzyj do dokumentacji”, dokumentacja bez spisu — „wybierz zagadnienie ze
  spisu obok”, a wyszukiwarka bez trafień — „przejrzyj spis dokumentacji”. Wszystkie trzy
  rady prowadziły do miejsca, które też jest puste (blog, wiedza i dokumentacja mają dziś
  zero pozycji). Teraz każda pusta sekcja mówi, jak jest, i podaje dwa wyjścia, które
  działają niezależnie od redakcji: wypróbowanie Nexusa bez rejestracji i kontakt.
  Dokumentacja pobiera przy okazji spis raz zamiast dwa razy.

- **Odsyłacz do strony portalu pokazuje jej własny opis.** Znaczniki z serwera miały
  tylko trzy strony portalu (cennik, funkcje, kontakt) — pozostałe dziewięć dostawało je
  dopiero od przeglądarki, a Facebook, LinkedIn, Slack i komunikatory skryptów nie
  uruchamiają: wrzucony odsyłacz do oferty, zastosowań, dokumentacji, bloga, centrum
  wiedzy, narzędzi, polityki prywatności, regulaminu i plików cookie pokazywał opis całej
  witryny. Wszystkie dziewięć ma teraz własny tytuł, opis, Open Graph i adres kanoniczny
  w HTML-u z serwera. Tytuł kanału Atom dostał pauzę zamiast półpauzy — zgodnie z resztą
  materiałów marki.

- **Nieistniejący wpis portalu zwraca 404.** Adres w rodzaju `/portal/blog/czegos-takiego-nie-ma`
  odpowiadał kodem 200 z powłoką aplikacji — to „miękkie 404”: wyszukiwarka trzyma taki
  adres w indeksie i pokazuje go zamiast działającej strony. Serwer rozpoznaje teraz
  adresy pozycji portalu (`sciezka_tresci`) i przy braku wpisu odsyła 404 z tą samą
  powłoką. Awaria bazy nie jest brakiem wpisu: wtedy odpowiedź zostaje przy 200, żeby
  chwilowy błąd nie wyrzucił opublikowanego wpisu z wyników wyszukiwania.

- **Logotyp pobiera tylko ten plik, który widać.** W drzewie stały oba warianty
  (jasny i ciemny), a jeden był chowany klasą `dark:hidden` — przeglądarka pobiera
  obrazek także przy `display: none`, więc każde wejście ciągnęło 9 kB grafiki, której
  nikt nie zobaczy; w pasku i stopce portalu razem 18 kB. Teraz wariant wybiera stan
  motywu (obserwator klasy `.dark`), więc przełączenie motywu nadal podmienia logotyp
  od razu. Test: `frontend/src/__tests__/logotyp.test.tsx`.

- **Strona produktu mówi prawdę o mowie.** Tekst obiecywał „mowę rozpoznaje Whisper,
  odpowiedź czyta Piper jednym z trzech polskich głosów”, a od czasu wpięcia klucza
  Google pierwszym torem jest Cloud Speech i trzydzieści głosów Chirp3-HD; modele na
  serwerze są zapasem na brak sieci (README, rozdz. „Rozmowa głosowa”). Poprawione
  w odpowiedzi na pytanie o głos, w podpisie karty, na liście technologii i w opisie
  „Mowa” w portalu. Zamyka pozycję z `docs/orkiestracja/DO-WPIECIA.md`, która od dnia
  opisania stała jako „opisane, niewpięte”.

- **API na osobnej domenie kompresuje odpowiedzi.** `danaco-nexus.pl` miało
  `encode zstd gzip`, a `api.danaco-nexus.pl` — po którym chodzą integracje — nie, więc
  ten sam JSON szedł tam nieskompresowany. Wyrównane; strumień zdarzeń zadań nadal idzie
  bez buforowania (`flush_interval -1`). Zmiana wymaga przeładowania Caddy hosta.

- **HEAD odpowiada tym samym co GET.** Trasa zbiorcza serwera przyjmowała wyłącznie
  `GET`, więc `HEAD` na pliku albo stronie kończyło się 405 — a tym pytają sprawdzarki
  odsyłaczy, monitoring dostępności i pośredniki, zanim cokolwiek pobiorą. Teraz
  odpowiedź ma ten sam status i nagłówki (`etag`, `content-length`, `cache-control`),
  tylko bez ciała, zgodnie z RFC 9110 §9.3.2.

- **Adres /m/czat otwiera rozmowę.** W pasku „Czat” stoi obok modułów i nazywa się tak
  samo, ale w rejestrze modułem nie jest — wejście pod `/m/czat` (zakładka, wpisany
  adres) kończyło się planszą „Moduł »czat« nie jest zainstalowany w tej wersji
  Nexusa”. Trasowanie rozpoznaje teraz `czat`, `chat` i `rozmowa` jako rozmowę, tak jak
  już wcześniej rozpoznawało `/m/glos` jako nakładkę głosową.

- **Pasek portalu mieści się w jednym wierszu.** Pomiar na siedmiu szerokościach
  (1024–1920 px) pokazał 108 px wysokości wszędzie powyżej 1280 px: dziewięć nazw
  zajmowało 874 px przy 650 px dostępnych, więc „Szukaj”, „Konto klienta” i
  „Aplikacja” spadały pod spód. W pasku zostaje ścieżka produktu — Oferta, Funkcje,
  Zastosowania, Narzędzia agenta, Cennik (482 px) — a Dokumentacja, Blog, Centrum
  wiedzy i Kontakt przechodzą pod przycisk „Menu”, który jest teraz widoczny także na
  dużym ekranie i rozwija pełną mapę portalu. Po zmianie pasek ma 64 px na każdej
  z mierzonych szerokości. Rozwinięcie zamyka Escape i wchodzi ruchem (`ui-wejscie`),
  tak samo jak menu na stronie produktu.
- **Wąski telefon dostaje sam znak zamiast logotypu.** Przy 360 px — najczęstszej
  szerokości ekranu Androida — logotyp z napisem (151 px) nie mieścił się obok
  „Aplikacji” i „Menu” i pasek miał 98 px zamiast 64 px. Poniżej 390 px zostaje sam łuk
  (23 px); od 390 px w górę logotyp jest jak był.

- **Plan nazywa się wszędzie tak samo.** Katalog planów i portal mówiły „Grupa”, a
  strona produktu w trzech miejscach „Zespół” — ta sama oferta pod dwiema nazwami.
  Teksty na stronie produktu, komentarz w `config.py` i dokumentacja (płatności,
  kredyty, rejestr czynności, plan poczty) idą teraz za katalogiem
  (`backend/nexus/platnosci/plany.py`): Osobisty, Pro, Grupa.
- **Karty cennika podają przestrzeń.** Lista w karcie planu wymieniała „Chmura
  osobista” bez liczby, choć opis Open Graph i odpowiedzi w pytaniach mówią o 1 GB,
  2 GB i 10 GB. Każda karta pokazuje teraz swoją wielkość — i mówi o niej tak jak katalog
  planów: „2 GB na pliki, pocztę i chmurę”, bo przestrzeń konta jest jedna i wspólna dla
  plików rozmów, chmury i skrzynek. „Chmura — 2 GB” czytało się jak osobny zapas.
- **Podpis wybranej głębokości badania czytelny.** Pomiar kontrastu w całym oknie
  (13 modułów, tekst kontra tło składane z przezroczystościami) znalazł jedno miejsce
  poniżej progu: podpis pod wybraną głębokością w module Badania był bielą przy 80%
  krycia na wypełnieniu Iris — 3,6 przy 11 px, próg WCAG 1.4.3 to 4,5. Pełna biel daje
  5,5 i nadal czyta się jako podpis, bo jest mniejsza i lżejsza od nazwy.

- **Schowany panel rozmów zniknął też dla klawiatury.** Na telefonie panel jest przesuwany
  za krawędź ekranu (`-translate-x-full`), ale przesunięcie nie wyjmuje go z kolejności
  tabulacji ani z drzewa dostępności: pomiar na ekranie 390 px pokazał **pięć kontrolek,
  które można było wybrać, choć ich nie widać** — „Zamknij panel”, pole szukania rozmów,
  „Nowa rozmowa”, „Więcej działań” i przycisk konta. Schowany panel dostaje teraz
  `visibility: hidden` (na komputerze `md:visible`, bo tam nie ma go czym wysuwać).
  `visibility` zmienia się skokowo dopiero na koniec przejścia, więc wysuwanie wygląda
  tak samo jak dotąd. Ta sama pułapka była w module Pliki: przyciski „Zmień” i „Usuń”
  przy katalogu wychodziły spod `opacity-0` dopiero po najechaniu myszą, a tabulacja
  zatrzymywała się na nich mimo to — teraz odsłania je także ustawienie ostrości.

- **Usterki dostępności z audytu Lighthouse (oś axe).** Cztery znaczki niosły nazwę
  w `aria-label` na zwykłym `span` bez roli — ARIA in HTML tego zabrania, więc nazwa mogła
  w ogóle nie dotrzeć do czytnika ekranu. Kropka rodzaju karty w sekcji „Funkcje” i kropka
  „nieprzeczytana” w Poczcie dostały rolę `img`, wskaźnik pracy w Badaniach rolę `status`. Przycisk odtwarzania filmu miał widoczny podpis („60 s ·
  lektor PL · napisy PL i EN”), którego nie było w jego nazwie dostępnej — to łamie
  WCAG 2.5.3 („Label in Name”): czytnik ekranu czyta jedno, a sterowanie głosem szuka
  drugiego. Ten sam podpis wchodzi więc teraz do nazwy dostępnej co do znaku (jedna stała
  w kodzie na oba miejsca), a `aria-hidden` na podpisie chroni przed przeczytaniem go dwa
  razy. Ocena dostępności strony produktu w Lighthouse: 97 → 100.

- **Karta strony w mediach społecznościowych podaje prawdziwą przestrzeń.** `og:description`
  i `twitter:description` obiecywały „2 GB na start”, a plan Osobisty daje 1 GB — 2 GB jest
  dopiero w Pro. Treść samej strony była poprawna (100 MB przez 7 dni próbnych, 1 GB
  w Osobistym, 2 GB w Pro, 10 GB w Zespole), rozmijał się z nią wyłącznie opis karty.

- **Widać, że wyszło nowe wydanie.** Ustawienia mają sekcję „Co nowego” z wykazem zmian
  bieżącego wydania, ale nic do niej nie prowadziło: produkt zmienia się po kilkanaście
  razy dziennie, a jedyną informacją o nowym wydaniu było to, że coś wygląda inaczej.
  Przy „Więcej” w pasku modułów (tam mieszkają Ustawienia) zapala się teraz kropka, gdy
  wyszło wydanie, którego wykazu na tym urządzeniu jeszcze nie otwierano — i gaśnie, gdy
  ktoś go otworzy. Pytanie o wydanie idzie raz na uruchomienie okna; brak pamięci
  przeglądarki (tryb prywatny) niczego nie psuje.

- **Jedno otwarcie zamiast dwóch — i zawsze.** Pomiar w przeglądarce pokazał, skąd brało
  się wrażenie zepsutej animacji na wejściu: strona ma ekran ładowania marki
  (`public/ladowanie/ladowanie.js` — iskra rysuje łuk znaku pociągnięciem światła, punkt
  opada, Aurora rozlewa się z punktu, łuk przelatuje w łuk nagłówka), a **na wierzchu
  dokładała się druga plansza**: nakładka Reacta z nagraniem `intro-znaku`. Pakiet
  aplikacji wchodzi po ponad sekundzie, więc kolejność na ekranie była taka: otwarcie
  marki, gotowa strona, a po chwili znowu zasłona z tym samym znakiem — tym razem białym,
  bez Aurory. Do tego ekran ładowania **kasował się sam**, gdy strona była gotowa szybciej
  niż w 150 ms (pamięć podręczna, szybkie łącze) — wtedy otwarcia nie było w ogóle.
  Teraz otwarcie jest jedno, rysuje je ekran ładowania i gra zawsze przy pierwszym wejściu
  w sesji (`prog: 0`), a strona czeka z wejściem nagłówka na jego sygnał
  (`dn:ladowanie-przejscie`). Ustawienie idzie osobnym plikiem (`/ladowanie/opcje.js`),
  a nie skryptem wpisanym w stronę: nagłówek Content-Security-Policy aplikacji ma
  `script-src 'self'` bez `'unsafe-inline'`, więc wersja wpisana wprost w dokument działała
  wyłącznie na serwerze deweloperskim, a na produkcji nie wykonała się ani razu. Plik jest
  wyjęty spod `.gitignore` (`frontend/public/ladowanie/` to skład kopii z pakietu marki):
  bez tego w świeżym klonie otwarcie wracałoby do domyślnego progu, czyli znikałoby na
  gotowej stronie — dokładnie ta usterka, od której się zaczęło. Strona
  czyta też stan planszy prosto z dokumentu, nie tylko ze zdarzenia — plansza potrafi zejść,
  zanim pakiet aplikacji się wykona, i sygnał nie miał wtedy kogo zastać — a wtedy nagłówek
  stał w pierwszej klatce (przy kryciu zero) przez kilka sekund. Samo czekanie ma teraz
  sufit: 1,4 s **od otwarcia dokumentu** na wejście strony i 4 s na gotowość planszy —
  element o kryciu zero nie liczy się do „największego wyrysowania treści”, więc bez sufitu
  wynik czekałby dokładnie tyle, co plansza. Limit liczony od dokumentu, a nie od chwili
  powstania komponentu, nie psuje choreografii: na normalnym łączu pakiet wchodzi ok. 450 ms,
  a przelot zaczyna się ok. 600 ms, czyli grubo przed limitem; na łączu tak wolnym, że sam
  pakiet wchodzi później, wstrzymania nie ma wcale.

  **Pomiar.** To samo wydanie przed i po, ten sam host, Lighthouse: zmierzone w przeglądarce
  LCP **1201 ms → 409 ms**. Wynik symulowany (Lantern, dławione łącze) idzie w drugą stronę:
  4,0 s → 5,2 s, ocena wydajności 81 → 74. Rozjazd bierze się stąd, że Lantern nie dławi
  zegarów strony, tylko przelicza zapisany przebieg na modelowe łącze: plansza i wejście
  dzieją się w nim w czasie rzeczywistym, a reszta w spowolnionym. Prawdziwej przeglądarce
  nowe otwarcie wyrysowuje treść trzy razy szybciej; gorszy jest wyłącznie model. Przy ograniczonym ruchu
  strona nie czeka na planszę w ogóle. Łuk znaku dostał wreszcie swój cel: łuk hero ma
  znacznik `data-dn-brama` opisany tak, żeby przelot kończył się dokładnie na nim, a nie na
  zastępczym rozchodzącym się kole. Nakładka `Otwarcie` i jej style zniknęły.

- **Uruchomienie aplikacji: plansza czeka na sesję, zamiast ustępować drugiemu ujęciu.**
  Okno grało tak samo dwa razy — ekran ładowania marki, a za nim ujęcie `uruchomienie-*`
  trzymane sztucznym minimum 820 ms. Teraz aplikacja zgłasza pobranie sesji ekranowi
  ładowania (`DanacoLadowanie.czekaj`), więc plansza schodzi dopiero nad gotowym oknem;
  ujęcie uruchomienia zostaje wyłącznie na wypadek długiego oczekiwania (słaba sieć,
  zimny serwer) i w zwykłym otwarciu nie pokazuje się wcale.

- **Pola formularzy wreszcie słuchają podanej szerokości.** Wspólne pole (`ui/Field`)
  dokładało sobie `w-full` nawet wtedy, gdy wywołujący podał własną szerokość: `w-full`
  i `w-44` to dwie klasy tej samej warstwy, więc o zwycięzcy decydowała kolejność
  w arkuszu, a nie w atrybucie — i zawsze wygrywała pełna szerokość. W Tłumaczu pasek
  wyboru języków rozjeżdżał się przez to na komputerze na cztery kontrolki na całą
  szerokość, jedna pod drugą, zamiast stać w jednym wierszu; to samo dotyczyło sześciu
  innych miejsc (Ustawienia, sesja Kodu). Pole dokłada `w-full` tylko wtedy, gdy
  szerokości nikt nie podał.

- **Kalendarz i Chmura przed podłączeniem przestały wyglądać na awarię.** Konto bez własnej
  przestrzeni w chmurze (m.in. konto próbne) dostawało z serwera 503 z komunikatem dla
  administratora — „Kalendarz nie jest skonfigurowany (brak adresu chmury lub hasła
  aplikacji)”, „Chmura osobista nie jest skonfigurowana (brak adresu Nextcloud lub hasła
  aplikacji)” — i oba moduły stawiały go na czerwonym pasku alarmowym nad pustą siatką
  tygodnia albo pustym folderem. Teraz ten jeden przypadek ma w obu własny stan: spokojne
  wyjaśnienie, skąd biorą się terminy i pliki oraz co można zrobić w międzyczasie.
  Pozostałe błędy dalej idą na pasek, bo są błędami. Oba stany dają też coś do zrobienia
  teraz: Chmura otwiera moduł „Pliki”, Kalendarz zaczyna rozmowę o planie tygodnia.
  Przy okazji korzeń ścieżki w Chmurze nazywa się „Chmura”, a nie „Cloud” — było to jedyne
  angielskie słowo na tym ekranie, tuż pod nagłówkiem „Chmura”.

- **Komunikaty błędów nie wypisują już wnętrzności serwera.** W czterech miejscach treść
  wyjątku szła wprost do odpowiedzi API: wyszukiwanie po znaczeniu odsyłało `Baza wektorowa
  jest niedostępna: <treść wyjątku>` (komunikat biblioteki razem z adresem i portem usługi),
  chmura w trzech miejscach `Brak połączenia z chmurą: <treść wyjątku>` (adres serwera
  Nextcloud), a odczyt tekstu z pliku — wyjątek parsera ze ścieżką pliku na dysku serwera.
  Użytkownik i tak nie mógł z tym nic zrobić. Szczegół idzie teraz do dziennika serwera,
  a do rozmowy wraca jedno zdanie o tym, co się stało i co zrobić.

- **Adres modułu spod nazwy z paska przestał prowadzić donikąd.** Cztery moduły mają
  w pasku nawigacji inną nazwę niż identyfikator w adresie: `cloud` („Chmura”),
  `research` („Badania”), `urzadzenia` („Sprzęt”) i `mozliwosci` („Narzędzia”).
  Kto przepisał adres z nazwy na pasku albo dostał go od kogoś, trafiał pod `/m/chmura`
  na komunikat „Moduł «chmura» nie jest zainstalowany w tej wersji Nexusa” — moduł był na
  miejscu, tylko pod inną nazwą. Rejestr modułów przyjmuje teraz `aliasy`, powłoka sprowadza
  alias do identyfikatora (podświetlenie paska i przejście widoku działają jak zwykle),
  a test pilnuje, żeby żaden alias nie zasłaniał innego modułu.

- **Domknięcie logowania bez cudzego imienia na ekranie.** Po zalogowaniu (i po wejściu
  na konto próbne) grało ujęcie `logowanie-ciemny`/`logowanie-jasny` z pakietu ruchu.
  Przejrzane klatka po klatce okazało się makietą produktu, a nie ruchem znaku: widać na
  nim cudzy formularz logowania z wpisanym adresem i powitanie „Dzień dobry, Dariuszu”.
  Każdy użytkownik dostawał więc po swoim zalogowaniu obce imię i drugi raz czynność,
  którą przed chwilą wykonał — w kadrze 1920 × 1080 obciętym do okna, więc nieczytelnym.
  W to miejsce wchodzi znak w ruchu (moment `logowanie`, 1440 ms): ta sama choreografia,
  barwy marki, skaluje się do każdego ekranu. `EkranPrzejscia` przyjmuje teraz `moment`
  obok `nazwa`; wylogowanie zostaje przy swoim ujęciu, bo tamto jest ruchem znaku.
  Same nagrania (trzy warianty) przestały też trafiać do katalogu publicznego
  (`POMIJANE_NAGRANIA` w `frontend/scripts/zasoby.py`): nieużywany plik nie ma po co leżeć
  pod publicznym adresem razem z adresem e-mail w kadrze. Spis ujęć startowych powstaje
  z katalogu publicznego, więc zszedł z 18 pozycji na 15.

- **Pusty moduł przestał być wąskim paskiem pośrodku ekranu.** Wspólny pusty stan modułów
  biurowych trzymał treść w `max-w-sm` (384 px) bez względu na to, ile jej jest. Na ekranie
  komputera Poczta łamała przez to opis na cztery wiersze, a lista czterech rzeczy, które
  Nexus zrobi ze skrzynką, ściskała się w dwie wąskie kolumny — moduł wyglądał na
  niedokończony. Domyślna szerokość idzie na `max-w-md` (jeden akapit), a stan z bogatszą
  treścią podaje własną (Poczta: `max-w-2xl`).

- **Okno aplikacji przestało stać w miejscu.** Pakiet ruchu był podpięty do strony
  produktu i do katalogu „Możliwości”, a w samym oknie stało płaskie logo: pomiar
  w przeglądarce pokazał, że po wejściu do aplikacji nie odtwarza się **ani jedno**
  ujęcie. Teraz: znak w pustej rozmowie oddycha (nowy moment `spoczynek` — cykl cztery
  razy wolniejszy niż pętla myślenia, żeby stany się nie myliły), znak przy każdej
  odpowiedzi pulsuje w trakcie pracy, rozbłyska po skończonej turze i gaśnie przy
  niepowodzeniu, a ujęcie uruchomienia dostało 820 ms minimum — wcześniej sesja
  rozstrzygała się szybciej niż jedna klatka i animacji startu nikt nie widział. Ten sam
  oddech dostał ekran logowania — okno ma wyglądać na włączone, zanim ktokolwiek się zaloguje.
  Doszły też ujęcia stanów z pakietu `motion/stany`, dotąd używane wyłącznie na stronie
  produktu: przeciąganie pliku nad oknem (`upuszczanie`), pusta lista rozmów
  (`pusta-rozmowa`) i brak wyników wyszukiwania (`brak-wynikow`). Odtwarza je nowy
  `NagranieStanu` — ten sam wzorzec co `NagranieStartu`, z tym samym wyłącznikiem ruchu.
  Dwa ujęcia po obejrzeniu wyniku z aplikacji **zdjęto**: `moment-mysli` dublowało znak przy
  tej samej odpowiedzi (dwa znaki obok siebie czytały się jak podwojone logo), a stany
  w pasku bocznym to ujęcia pełnoklatkowe, które w kolumnie szerokiej na 112 px wyglądają
  jak ciemny prostokąt. Zostały tam, gdzie mają miejsce: nakładka upuszczania pliku.
  Sprawdzone pomiarem na wdrożonym wydaniu: `znak-oddech` biegnie (cykl 9,6 s, skala rośnie
  między odczytami), a w czasie pracy agenta znak stoi na momencie `mysli`.
- **Przełącznik „ograniczony ruch” zaczął działać w całości.** Wyciszał wyłącznie
  nagrania sterowane skryptem; kaskady, przejścia widoków i ruch znaku szły dalej, bo
  CSS znał tylko ustawienie systemu. Reguła mieszka teraz w jednym miejscu
  (`preferencje.ts`), a `zastosujRuch()` stawia na korzeniu dokumentu `data-ruch`, pod
  który podpięte są te same wyłączenia co pod `prefers-reduced-motion`. Trzy osobne kopie
  tej reguły (hook, karta kroku, odtwarzacz nagrań) zniknęły.
- **Gotowe sekcje Web Kitu przestały być bezimienne.** `site_kit_catalog` podawał same
  nazwy rodzin („hero”, „pricing”, „faq”) i liczbę sekcji — agent wiedział, że są, ale
  nie mógł wskazać żadnej, więc pisał je od zera. Teraz spis oddaje pozycje z nazwą, polskim
  opisem, wariantami i tagami, a `szukaj_sekcji` zawęża je po treści zapytania („cennik
  z przełącznikiem”, „kalkulator wyceny”). Katalogi bez składnika `Section.astro` odpadają
  — takie katalogi obiecują sekcje, których nie ma. Biblioteka urosła w tym czasie ze 148
  do 261 sekcji w 34 rodzinach (orkiestracja agentów), więc spis z zawężaniem przestał być
  wygodą, a stał się warunkiem korzystania z niej.
  Sprawdzone przebiegiem: preset `saas` z dołożoną sekcją `pricing/calculator`
  (`sections: [{use: …, props: …}]` w `site.yaml`, props wprost z `example.json`) buduje się
  i sekcja jest w gotowym HTML-u — 96 podstron.
- **Filmy mają wreszcie miniatury.** `/api/files/{id}/thumbnail` robił miniaturę obrazu
  i pierwszej strony PDF, a dla wideo oddawał 404 — w wykazie plików film był szarym
  prostokątem, a w storyboardzie montażu po ujęciu nie było widać, co w nim jest. Teraz
  klatkę wyjmuje FFmpeg (sekunda od początku, żeby ominąć czarną planszę) i wpada do tej
  samej pamięci podręcznej co reszta.
- **Ścieżki „/assets/…” w gotowych szablonach są prostowane przy wstawianiu.** Strony
  użytkowników stoją pod adresem `/s/<adres>/`, więc odwołanie liczone od korzenia domeny
  trafiało w pustkę — szablon wchodził do szkicu bez stylów i z martwym menu. Do tej pory
  `site_from_template` tylko o tym uprzedzał; teraz przelicza ścieżki na względne
  (atrybuty `href`, `src`, `poster`, `srcset` i `url(…)` w arkuszach) według zagnieżdżenia
  pliku i mówi w wyniku, ile ich poprawił. Adresy z protokołem (`https://`, `//cdn…`)
  zostają nietknięte — ostrzeżenie o zasobach z sieci nadal jest.
  **To samo dotyczyło witryn z presetów** (`site_from_kit`): Astro buduje je ze ścieżkami
  od korzenia (`/_astro/…`, `/_themes/…`, `/cennik`), więc **każda** witryna wstawiona do
  szkicu miała martwe style, kroje i całe menu. Sprawdzone na witrynie presetu `saas`:
  8118 poprawionych ścieżek w 228 plikach, podstrony otwierają się pod `/s/<adres>/`
  z pełnym wyglądem i działającą nawigacją. Odsyłacz do podstrony dostaje przy okazji
  kreskę na końcu (`/cennik` → `./cennik/`), a serwer przekierowuje adres bez kreski na
  adres z kreską (308) — bez tego przeglądarka bierze ostatni człon za plik i podstrona
  otwarta z menu znów traci arkusze.
- **Open Doodles przestało być zestawem bez ani jednej ilustracji.** Zestaw przyszedł jako
  33 komponenty React z rysunkiem w środku, więc w spisie materiałów figurował z liczbą
  `liczba_svg: 0` — agent nie miał z niego czego wziąć. Rysunki zostały wyciągnięte do
  zwykłych plików SVG (`ilustracje/open-doodles/svg/`, barwy zestawu: kreska #1F2430,
  akcent #FF5678), sprawdzone renderem i opisane w `SVG-SKAD.txt` — licencja bez zmian (MIT).
- **Spis materiałów przestał proponować pliki budowy paczki.** Zestawy przychodzą czasem
  z całym repozytorium autora, więc `rollup.config.js`, aplikacja przykładowa i testy
  trafiały na początek spisu ilustracji. Teraz odpadają (`POMIJANE`, `POMIJANE_KATALOGI`
  w `backend/nexus/tools/zasoby.py`); `examples/` zostaje świadomie — three.js trzyma tam
  dodatki, z których agent korzysta.
- **Ustawienia na telefonie przestały wychodzić poza ekran.** Kafle sekcji brały
  szerokość najdłuższej treści (adres e-mail konta próbnego to jeden nierozdzielny wyraz)
  — pomiar w przeglądarce: kafel 506 px w kolumnie szerokiej na 358 px, więc pola, adres
  i przycisk kończyły się za krawędzią. Brakowało `min-w-0` na elemencie siatki.
- **Zakładki Chmury na telefonie zawijają się zamiast chować za krawędzią.** Pasek
  („Pliki · Ulubione · Kosz · Synchronizacja”) przewijał się w bok, ale nic tego nie
  zapowiadało — ostatnia zakładka po prostu kończyła się za ekranem. Na wąskim ekranie
  pasek zawija się teraz do dwóch rzędów; od `md` wraca kolumna z boku.
- **Podpis modułu na telefonie nie urywa się w pół słowa.** Przy nagłówku z przyciskami
  („Studio” z przełącznikiem Nagranie/Montaż) podpis przegrywał o miejsce i kończył się
  na „Nagranie: transkrypcja, n…”. Na wąskim ekranie schodzi teraz pod tytuł, na całą
  szerokość; na szerokim zostaje jak był. Przegląd ośmiu modułów przy 390 px: nigdzie nie
  ma poziomego przewijania.
- **Publikacja strony mówi, co jeszcze wychodzi do cudzych serwerów.** Odwołania do CDN-ów
  i cudzy adres kanoniczny były zgłaszane przy wstawianiu szablonu — czyli kilkanaście kroków
  przed publikacją, gdy jeszcze nikogo nie dotyczyły. `site_publish` sprawdza to teraz
  ponownie i oddaje w polu `do_sprzatniecia`, z poleceniem wymienienia tego użytkownikowi,
  zanim kliknie potwierdzenie. Rejestr czynności (CZ-15) mówił, że takiej kontroli brakuje;
  ten brak jest zamknięty.
- **Cudzy adres kanoniczny w szablonie jest zgłaszany.** 24 z 81 zbudowanych szablonów
  kolekcji ma w podstronach `<link rel="canonical">` albo `og:url` wskazujący witrynę
  autora. Zostawione mówi wyszukiwarce, że strona użytkownika jest kopią tamtej — wynik
  `site_from_template` wymienia teraz te adresy z licznikiem. Przy okazji `canonical`
  i `alternate` przestały być liczone jako „zasób z sieci”: niczego nie pobierają, a
  zawyżały licznik i mieszały dwie różne sprawy (stąd 48 → 44 szablonów z zasobami z sieci).
- **Ostrzeżenie o zasobach z sieci mówi, z jakich serwerów.** Podawało samą liczbę
  („witryna ma 559 odwołań”), z czego nie wynikało, co pobrać. Teraz wymienia serwery
  z licznikiem (`cdn.jsdelivr.net (557)`, `fonts.googleapis.com (16)`), a kroje z Google
  dostają osobną uwagę: to nie jest kwestia wyglądu, tylko wysyłki adresu IP
  odwiedzającego do Google — a serwer ma 2050 rodzin krojów u siebie. Przegląd kolekcji:
  48 z 81 zbudowanych szablonów sięga po zasoby z sieci.
- **Adresy w skryptach są zgłaszane, a nie po cichu przepisywane.** Przeliczanie ścieżek
  obejmuje HTML i CSS; w JavaScripcie ten sam zapis („/login”) bywa adresem strony, kluczem
  albo zwykłym tekstem, więc automat pomyliłby je ze sobą. Zamiast tego wynik mówi, ile
  takich adresów zostało i gdzie ich szukać — sprawdzone na szablonie panelu, który po
  wstawieniu przekierowywał na „/login” poza stroną użytkownika.
- **Spis szablonów aplikacji przestał zalewać odpowiedź.** Pełny wykaz z opisami to było
  12 777 znaków w jednym wyniku; teraz domyślnie 12 pozycji (4851 znaków), z liczbą
  wszystkich i podpowiedzią, czym zawęzić. Zawężanie działa też po stosie — „react”, „vue”,
  „next” dają odpowiednio po sześć pozycji.
- **Wykaz szablonów przestał kłamać o stanie zbudowania.** 21 pozycji w
  `/danaco/programy/web/kolekcja` miało w `meta.json` `zbudowany: true` bez katalogu
  `witryna/` na dysku. Sam katalog narzędzia czytał ze stanu plików, więc agent nie był
  wprowadzany w błąd, ale wpisy czytają też inne projekty serwera — zostały poprawione.

- **Ustawienia przestały być trzema kafelkami.** Moduł miał wybór motywu, natywną listę
  głosów i cztery odsyłacze — i to było wszystko, co dawało się ustawić na koncie. Teraz
  są: profil (nazwa, firma, adres, plan) i zmiana hasła, praca (czym wysyła się wiadomość,
  od czego zaczyna się dzień), ograniczony ruch niezależny od ustawienia systemu, głos
  z próbką do odsłuchania, powiadomienia tej przeglądarki, wykaz zalogowanych przeglądarek
  z wylogowaniem pozostałych i eksport danych konta do JSON (RODO, art. 20). Preferencje
  trzyma konto (`/api/konto/preferencje`, tabela `ustawienia_konta`), nie `localStorage`,
  więc jadą za użytkownikiem na telefon i po wyczyszczeniu danych witryny. Każde
  ustawienie jest podpięte pod działające API — przełącznik, który niczego nie zmienia,
  jest gorszy niż jego brak. Pilnuje tego `backend/tests/test_konto.py`.
- **Plansza otwarcia i ujęcie instalacji w ciasnym kadrze.** Intro znaku było nagrane
  w kadrze 1440 × 810, w którym sam znak zajmował 25% szerokości: przy wysokości 42vh
  schodził do ~160 px i pierwsze pół sekundy wyglądało jak pusty czarny ekran. Scena ma
  teraz kadr kwadratowy 640 × 640 ze znakiem na 62% szerokości, a pod nim dochodzi
  logotyp. Ujęcie instalacji dostało kadr 760 × 600 z ramą pulpitu, która zostaje przez
  całe nagranie, i kończy się otwartym oknem aplikacji — wcześniej scena była w 70% pusta
  i wyglądała jak czarny prostokąt z paskiem ikon przy dolnej krawędzi.
- **Moduł Kod przestał być pięcioma kolumnami bez hierarchii.** Pasek zaczyna się nazwą
  projektu i gałęzią, pobranie paczki i usunięcie projektu zeszły pod „⋯” (naga ikona
  kosza stała tuż obok pobierania), lista sesji korzysta z listy wyboru produktu zamiast
  natywnego `select`, a po otwarciu projektu środkowa kolumna od razu pokazuje README
  zamiast zdania w pustce.
- **Pasek modułów mieści się w oknie laptopa.** Osiemnaście pozycji nie mieściło się
  w pasku i cztery ostatnie stały poza widokiem. Wiersze są ciaśniejsze, a Narzędzia,
  Sprzęt, Płatności i Ustawienia zeszły pod przycisk „Więcej” z menu — te same pozycje
  są też w menu konta w panelu rozmów.
- **Natywne pola wyboru w barwach produktu.** W modułach zostało kilkanaście zwykłych
  `select`-ów (języki, kalendarze, formaty, konta pocztowe); każdy rysował się strzałką
  i tłem systemu i w motywie ciemnym odstawał od reszty. Jedna reguła w `styles.css`
  ustawia je wszystkie; `ui/Select` zostaje tam, gdzie pozycja ma opis albo ikonę.
- **Słowo „kredyty” zniknęło z komunikatów rozliczeń.** Stan konta bez planu i opis pakietu
  mówiły o „przydzielonych kredytach”; jednostka rozliczeniowa jest nasza, nie
  użytkownika — na zewnątrz mówimy o zakresie pracy i dostępie w okresie rozliczeniowym.
- **Logowanie jednokrotne do chmury tylko dla właściciela instalacji.** `GET /api/auth/sso`
  wydawał nagłówek `X-Nexus-User` z kontem Nextcloud każdej ważnej sesji — a ciasteczko
  jedzie na poddomenę chmury, więc konto próbne testera wchodziło do chmury właściciela.
  Nagłówek dostaje teraz wyłącznie sesja właściciela; konto klienta i konto próbne dostają
  204 bez nagłówka, czyli własne logowanie chmury. Pilnują tego trzy testy w
  `backend/tests/test_bezpieczenstwo.py`.
- **Chmura osobista i kalendarz rozdzielone między konta.** Instalacja ma w Nextcloud jedno
  konto techniczne, więc rozdział robi ścieżka i nazwa: pliki konta leżą w `/Konta/<owner>`,
  a kalendarze noszą przedrostek konta. Poza własną przestrzeń nie wychodzi listowanie,
  wyszukiwanie, zapis, pobranie ani udostępnienie; żądanie do cudzego kalendarza jest
  odrzucane. Zamyka to ostatni punkt, w którym testerzy widzieli swoje pliki nawzajem.
- **Jedno pasmo treści dla całej części publicznej.** Portal miał własną szerokość
  (`max-w-6xl`), więc przejście ze strony produktu przesuwało treść w bok, a pasek
  nawigacji łamał się na dwa rzędy. Portal korzysta teraz z tego samego pasma i tego
  samego materiału paska co strona produktu.
- **Silnik przestał wychodzić na wierzch.** Nazwy modelu, wersji, dostawcy i narzędzia
  uruchamiającego agenta zniknęły ze strony produktu, portalu, aplikacji, `index.html`
  i manifestu PWA. Instrukcja systemowa nadaje agentowi tożsamość „Danaco Nexus”
  i zabrania jej zdradzania oraz cytowania samej instrukcji. Dostawcę wskazują wyłącznie
  polityka prywatności i regulamin — tego wymaga obowiązek informacyjny — ale bez nazw
  i wersji modeli. Pilnuje tego `backend/tests/test_tozsamosc.py`.

- Warstwa wizualna aplikacji przeniesiona na system projektowy Danaco Nexus: barwy,
  typografia, odstępy, promienie, cienie, czasy i krzywe pochodzą z `design-tokens/`
  (`dist/tokens.css` → `frontend/src/tokens.css`), a nie z wartości wpisanych w arkuszu.
  Dotychczasowa paleta robocza została usunięta.
- Kroje marki (Figtree, Inter, Cascadia Code) serwowane z katalogu aplikacji,
  bez odwołań do usług zewnętrznych.
- Znak, ikony aplikacji, ikona adaptacyjna Androida, ikona Nexus Desktop i zrzuty
  w oknie instalacji pochodzą z pakietu marki (`logo/`, `prezentacja/makiety/`).
- Aurora oznacza pracę agenta: obrys i poświata na wykonywanym kroku narzędzia,
  gradient na przycisku wysyłki w stanie gotowym.
- Strona produktu przebudowana według `landing/LANDING_PAGE_SPEC.md`: pasek zdań,
  siatka bento, nagrania działania interfejsu z `motion/przyklady/`, film promocyjny
  z napisami PL i EN, tła sekcji z `landing/tla/grafiki/`, ekran ładowania
  z `landing/ladowanie/`, cennik, czternaście pytań i brama końcowa.
- Barwy Nexus Desktop, rozszerzenia przeglądarki i aplikacji Android sprowadzone
  do ról semantycznych z tokenów.
- Ekrany aplikacji ładowane na żądanie: gość na stronie produktu nie pobiera powłoki
  ani modułów.
- Czasy kroków agenta zapisywane po polsku (przecinek dziesiętny).
- `README.md` doprowadzony do stanu kodu: rejestr narzędzi rozbity na rdzeń i moduły,
  59 pozycji zamiast 22 opisanych wcześniej.
- Kopia zapasowa: `deploy/kopia-zapasowa.sh` (bazy `nexus` i `nextcloud`, pliki
  użytkownika, wektory bazy wiedzy, pięć plików z sekretami i profil CLI, sumy
  kontrolne, kasowanie kopii starszych niż 14 dni), timer `danaco-nexus-kopia.timer`
  włączany przez `deploy/instalacja.sh`; procedura odtworzenia w README. Skrypt
  zatrzymuje się z błędem, gdy nie da się odpytać klastra — nie robi cichej,
  pustej kopii.
- Testy Nexus Desktop kończą się kodem 0 na Linuksie: dwa testy narzędzi plikowych
  pomijane poza Windows z podaniem powodu.
- Utrata zapisu sesji CLI nie przechodzi już bez śladu: w dzienniku pojawia się
  ostrzeżenie, a rozmowa dostaje komunikat o pracy na streszczeniu.
- Android: ikona ekranu startowego i ikona powiadomień z pakietu marki zamiast
  zastępczego znaku; tło widoku ustawione na barwę powierzchni aplikacji.
- Rozszerzenie przeglądarki: sygnet marki zamiast rysowanego w kodzie znaku,
  barwy panelu wstrzykiwanego na obce strony zgodne z tokenami.
- Nexus Desktop: kroje Inter i Cascadia Code dołączone do paczki instalacyjnej.
- Liczba narzędzi agenta na stronie produktu poprawiona z 26 na 59 (stan rejestru
  `backend/nexus/tools/`); gwarancja „zamknięty zestaw uprawnień” i odpowiedź
  w pytaniach doprecyzowane — agent ma narzędzia badawcze z dostępem do sieci,
  a działania na komputerze użytkownika wymagają potwierdzenia.
- Strona produktu jest indeksowana przez wyszukiwarki; nagłówek `X-Robots-Tag`
  w konfiguracji Caddy zawężony do ekranów za logowaniem, API i pobierania.
- Typy plików AVIF, WebP, WOFF2, VTT, MP4 i WebM podawane wprost przez serwer.

### Naprawiono

- **Rola administratora wobec danych osób trzecich — rozstrzygnięta.** Cztery funkcje
  wnoszą do Nexusa dane osób, które nie zawarły z Danaco umowy: rozpoznawanie twarzy,
  czytanie stron przez dodatek, szkice odpowiedzi na SMS i zawartość ekranu telefonu.
  Decyzja właściciela: **administratorem jest użytkownik**, Danaco jest podmiotem
  przetwarzającym. Zapisane w rejestrze (CZ-14, CZ-16, CZ-17) i w dokumencie zgodności
  (§6.3c) razem ze skutkami: umowa powierzenia dla klientów biznesowych, wyłączenie
  „na użytek własny” dla konsumentów i obowiązki z art. 28 oraz art. 30 ust. 2.

- **Ograniczenie ruchu wycisza też opóźnienia, nie tylko czasy trwania.** Obie gałęzie
  — systemowa (`prefers-reduced-motion`) i z ustawień konta (`data-ruch="ograniczony"`) —
  zerowały czas trwania animacji i przejść, ale zostawiały opóźnienie kaskady nietknięte.
  Pomiar na wydaniu: czas 0,00001 s, opóźnienie dalej 0,08–0,32 s. Przy `fill: both`
  znaczyło to, że treść stoi na kryciu 0 i wyskakuje schodkami, jedna pozycja po drugiej —
  czyli dokładnie to, czego ktoś z włączonym ograniczeniem ruchu chce uniknąć. Teraz obie
  gałęzie zerują również `animation-delay` i `transition-delay`. Dotyczy całej strony
  produktu i portalu, gdzie kaskada była używana od dawna.

- **Portal dostał dziesięć napisanych materiałów.** Baza produkcyjna nie miała ani jednej
  pozycji: Dokumentacja, Blog i Centrum wiedzy były puste, a pięć adresów dokumentacji
  z mapy witryny zwracało 404. Napisane od zera pięć wpisów bloga (czym jest praca
  z agentem, dzień z Nexusem poza księgowością, po co ruch w interfejsie, gdzie mieszkają
  dane, co się ostatnio zmieniło) i pięć opracowań centrum wiedzy (częste pytania, jak
  opisać zadanie, własna witryna, formaty plików, klienci na urządzeniach). Tabela formatów
  sprawdzona z `ACCEPTED_FILES` w kodzie, nie z pamięci. Mapa witryny urosła z 15 do
  30 adresów. Podział działów zapisany w `README.md` obu katalogów, żeby się nie dublowały:
  dokumentacja opisuje ekrany, wiedza uczy jak, blog mówi co nowego.

- **Zajawki na kartach spisu sklejały śródtytuł z akapitem.** Zajawka powstawała z całej
  treści sprowadzonej do jednej linii, więc w portalu czytało się „…co widać gołym okiem.
  Ruch w oknie aplikacji Treść, która dociera po odpowiedzi serwera…”. Teraz bierze
  **wstęp** materiału — czyli to, co autor napisał na zachętę. Materiał zaczynający się
  od razu śródtytułem zachowuje się jak dotąd, a zajawka wpisana ręcznie wygrywa z obiema.

- **Poczta portalu przestała obiecywać wiadomości, których nie wysyła.** Bez podłączonej
  skrzynki wiadomości trafiają do dziennika aplikacji, a ekran mówił „wysłaliśmy odsyłacz,
  sprawdź skrzynkę”. Przy odzyskiwaniu hasła znaczyło to, że ktoś czeka na coś, co nie
  przyjdzie, i nie ma jak się dowiedzieć dlaczego. Serwer podaje teraz `poczta_dziala`
  w `/api/portal/stan`, ekran „Nie pamiętam hasła” uprzedza **przed** wpisaniem adresu
  i kieruje na Kontakt, a pasek potwierdzenia adresu w profilu dodaje, że potwierdzenie
  niczego nie blokuje. Po podłączeniu skrzynki komunikaty wracają same.

- **Kontrola licencji narzędzi rozróżnia zakupy próbne od sprzedaży.** Sprzedaż jest
  włączona po to, żeby testerzy robili zakupy kartami próbnymi — a kontrola zapalała
  czerwone światło przy każdym wdrożeniu, przez co ostrzeżenie zaczynało być tłem. Klucz
  testowy Stripe (`sk_test_…`) daje teraz opis stanu, a nie błąd; przy kluczu produkcyjnym
  ostrzeżenie wraca samo, bez niczyjej zmiany w kodzie.

- **Piąta luka zgodności: zawartość ekranu telefonu.** Aplikacja Android ma języczek
  otwierający panel Nexusa nad dowolną inną aplikacją; przycisk „ekran” wysyła do asystenta
  zrzut ekranu (zgoda systemowa za każdym razem) i/lub tekst odczytany przez opcjonalną
  usługę dostępności. Ani polityka, ani rejestr o tym nie mówiły. To najszersza kategoria
  danych w produkcie — na ekranie może być dosłownie wszystko. Dopisany **CZ-17**
  i §6.3b z gotowym brzmieniem akapitu polityki. Przegląd całego manifestu przy okazji:
  czternaście uprawnień, wszystkie faktycznie używane — problemem nie był nadmiar
  uprawnień, tylko brak opisu trzech z nich w dokumentach.

- **Czwarta luka zgodności: SMS-y z aplikacji Android.** Klient Android ma funkcję
  „Szkice odpowiedzi na SMS” — po włączeniu i nadaniu uprawnienia `READ_SMS` odczytuje
  ostatnie wiadomości, a wybrany wątek wysyła na serwer jako nową rozmowę. Funkcja jest
  zrobiona ostrożnie (opt-in, osobna zgoda systemowa, nic w tle, wybór jednego wątku),
  ale **nie było jej ani w polityce prywatności, ani w rejestrze czynności** — słowo „SMS”
  nie padało w `docs/zgodnosc/` ani razu. Treść wiadomości to dane osobowe nadawcy, który
  z Danaco umowy nie zawierał, a bywa, że dane szczególnej kategorii. Dopisany wpis
  **CZ-16** do rejestru i §6.3a do dokumentu zgodności, z gotowym brzmieniem akapitu
  polityki do zatwierdzenia. Poprawiony też mylący komentarz w `SmsReader.kt` („nic nie
  jest zapisywane ani wysyłane” — prawda o tym pliku, nieprawda o funkcji).

- **Tekst udostępniony przed startem service workera przestał ginąć.** Manifest PWA ma
  `share_target`, więc system proponuje Nexusa w menu „Udostępnij”. Obsługuje to service
  worker — ale przy **pierwszym uruchomieniu po instalacji** workera jeszcze nie ma, a to
  właśnie wtedy ktoś najczęściej próbuje udostępnić pierwszą rzecz. Żądanie trafiało wtedy
  na zapas po stronie serwera, który wracał na stronę główną i gubił po cichu tytuł, tekst
  i adres. Teraz serwer przenosi tekst adresem, a aplikacja wstawia go do pola wiadomości.
  Pliki tą drogą nie przechodzą — przekierowanie ich nie unosi — i to jest uczciwa granica
  tego zapasu.

- **Wydanie i kopia zapasowa niosą komplet źródeł.** Do `zrodla/` brakowało kodu ekranu
  ładowania marki (`landing/ladowanie/*.js|css`, wykluczonego razem z 395 MB materiałów,
  choć to kod), pliku `frontend/public/ladowanie/opcje.js` (jedyne źródło w katalogu, który
  w całości jest w `.gitignore`), testów i zasobów pulpitu oraz `.gitignore`
  i `.gitleaks.toml`. Bez nich odtworzenie z wydania nie byłoby wierne.

- **Brakujący plik dostawał 200 i stronę aplikacji zamiast 404.** Zapas jednostronicowy
  łapał każdy adres — także taki, który wygląda na plik. `GET /ruch/stany/ilustracja.webm`
  (plik nie istnieje) zwracał 200 i 7909 bajtów HTML-a. Przeglądarka brała wtedy po cichu
  następne źródło, pamięci podręczne zapisywały „sukces” dla czegoś, czego nie ma,
  a literówka w ścieżce zasobu nie odzywała się niczym. Teraz adres z kropką w ostatnim
  członie, którego nie ma na dysku, dostaje 404 — adresy aplikacji kropki nie mają, więc
  rozróżnienie jest jednoznaczne, a strony użytkownika spod `/s/` obsługuje wcześniejszy
  router.

- **`HEAD /api/health` zwracał 404, choć `GET` zwracał 200.** Trasy FastAPI (`APIRoute`)
  nie dokładają `HEAD` samoczynnie — inaczej niż zwykłe trasy Starlette. Żądanie spadało
  więc do zapasu SPA (ten `HEAD` przyjmuje) i trafiało tam na gałąź „wszystko pod `api/`
  to 404”. Sondy dostępności pytają zwykle metodą `HEAD`, bo nie potrzebują ciała
  odpowiedzi, więc monitor zgłaszałby działającą usługę jako niedostępną.

- **Pasek błędu nad polem wiadomości da się zamknąć klawiaturą.** Komunikat miał
  `role="alert"` i zamykanie kliknięciem w cały pasek — czyli `div` z `onClick`, który
  nie trafia w kolejność tabulacji i nie reaguje na Enter. Kto pracuje klawiaturą albo
  czytnikiem ekranu, zostawał z komunikatem na stałe. Dołożony prawdziwy przycisk
  „Zamknij komunikat”; zamykanie kliknięciem w pasek zostaje. `pa11y` tego nie łapał —
  sprawdza znaczniki statyczne i nie wie, że `div` niesie zachowanie.

- **Menu ikony aplikacji dostało cztery skróty zamiast jednego.** Android i Windows
  pokazują po długim przytrzymaniu (albo prawym przycisku) do czterech pozycji; manifest
  miał jedną, więc menu było niemal puste. Doszły Pliki, Obrazy i Możliwości. Skrótu do
  rozmowy głosowej **nie ma świadomie**: `/m/glos` nie jest modułem rejestru, tylko
  nakładką, i przy wyłączonym głosie odsyła na czat — sprawdzone w przeglądarce.

- **Odcisk źródeł w bramce obejmuje też konfigurację budowy interfejsu.** Pierwsza wersja
  pilnowała `frontend/src`, ale nie `vite.config.ts` (który niesie cały manifest PWA
  i reguły service workera), `index.html`, `package.json` ani `tsconfig.json` — a zmiana
  w nich też zmienia wynik budowy.

- **Tytuł okna mówi, co jest na ekranie.** Każdy widok aplikacji nazywał się tak samo —
  „Danaco Nexus” — bo znaczniki strony znają tylko rodzaj ekranu, nie moduł. Przy
  zainstalowanej aplikacji to jest tytuł w przełączniku okien systemu, a przy kilku
  otwartych kartach jedyny sposób odróżnienia ich od siebie. Teraz okno nazywa się
  „Pliki — Danaco Nexus”, „Obrazy — Danaco Nexus”, a na czacie tytułem rozmowy.
  Nazwy pochodzą z rejestru modułów, więc tytuł ustawia powłoka: rejestr ładuje się
  `eager`, a wciągnięcie go do `App.tsx` przyniosłoby z powrotem wszystkie strony modułów
  do pakietu startowego, czyli odwróciłoby dzisiejsze odchudzenie strony produktu.

- **Brakujące pola przestały być „nieprawidłowymi wartościami”.** Przy jednym polu
  odpowiedź 422 mówiła poprawnie „Brakuje pola «x»”, a przy dwóch nagle „Nieprawidłowe
  wartości pól «x», «y»” — choć pole, którego nie przysłano, żadnej wartości nie ma.
  Użytkownik czytał z tego, że wpisał coś źle, i szukał błędu tam, gdzie go nie było.

- **Strona produktu nie pobiera nagrania z sekcji instalacji, dopóki nikt tam nie zajrzy.**
  Nagranie „moment-instalacja” (125 kB) wczytywało się każdemu, kto tylko otworzył stronę,
  choć sekcja leży daleko pod pierwszym ekranem. Wchodzi teraz do strony dopiero, gdy
  zbliża się do widoku; ramka trzyma proporcje z góry, więc przesunięcia układu nadal
  nie ma (CLS 0).

- **Dwa ekrany aplikacji odzyskały nagłówek.** Tytuł „Płatności” stał tylko w gałęzi
  wczytywania i w gałęzi błędu — gotowa strona nie miała nagłówka pierwszego stopnia
  wcale (zmierzone na wydaniu: `/m/platnosci`, zero widocznych `h1`, jedyny taki moduł
  z szesnastu). Czytnik ekranu nie miał od czego zacząć strony. Cennik z kolei miał
  własny `h1`, więc po wejściu na zakładkę „Plany i ceny” byłyby dwa — cennik jest teraz
  sekcją drugiego stopnia. Ten sam brak miał ekran „ten moduł nie jest dostępny”
  (`/m/<nieznany>`): komunikat był na miejscu i po polsku, ale stał jako `h2`, bo nagłówek
  strony niesie zwykle sama strona modułu — której tam z definicji nie ma.

- **Test rozłączenia komputera przestał mierzyć obciążenie maszyny.** Sprzątanie
  rozłączenia czeka na zadanie przekazujące żądania najwyżej dwie sekundy i dopiero potem
  skreśla komputer z listy podłączonych; test czekał na zniknięcie 2,5 s. Pół sekundy zapasu
  starczało na pustej maszynie i nie starczało, gdy w tle szła budowa wydania — wariant
  redisowy wyglądał wtedy na zepsuty, choć kod był w porządku. Budżet czekania liczy się
  teraz z limitu sprzątania, więc obie liczby nie mogą się rozjechać. Komplet testów pulpitu
  na Valkeyu: 17 zdanych, oba warianty brokera.

- **Nexus Desktop zawieszał się, gdy proces pomocniczy nie mógł wystartować.**
  `WindowHelper.start()` uruchamia PowerShell i nasłuchuje jego wyjścia, ale **nie**
  nasłuchiwał zdarzenia `error` samego `spawn`. Node zamienia takie zdarzenie bez słuchacza
  w nieobsłużony wyjątek w procesie głównym Electrona — a cała reszta kodu jest napisana
  tak, żeby brak procesu pomocniczego **przeżyć** (`this.ready.catch(...)` i
  `state.helper.start().catch(...)`). Ta odporność nie działała. Widać to było dopiero poza
  Windows: test uruchomieniowy startował, zapisywał pierwszy wiersz dziennika i stawał —
  nie odpalał się nawet jego własny bezpiecznik 150 s. Po dołożeniu nasłuchu test
  **przechodzi do końca**: wszystkie pięć okien się wczytuje (główne z `danaco-nexus.pl`,
  języczek, pasek panelu, panel, ustawienia), powstają zrzuty i raport. Na Windows nic się
  nie zmienia; zmienia się to, co dzieje się, gdy PowerShella nie ma albo jest zablokowany.

- **Nieudane zadanie nie było ogłaszane czytnikowi ekranu.** Komunikat o błędzie biegu
  pojawia się w rozmowie **po** wysłaniu wiadomości, czyli wtedy, gdy nikt już na to
  miejsce nie patrzy. Pole nie miało roli, więc czytnik ekranu je przemilczał i osoba
  niewidoma zostawała z ciszą zamiast z informacją, że zadanie się nie udało. Niepowodzenie
  ogłasza się teraz stanowczo (`role="alert"`), a anulowanie spokojnie (`role="status"`) —
  bo to użytkownik je wywołał i wie, co się stało. Automat tego nie łapał: `pa11y` sprawdza
  znaczniki na stronie, a nie to, co pojawia się później.

- **Dziennik zmian miał po dwie sekcje tego samego rodzaju.** Pod jednym nagłówkiem
  `[Nieopublikowane]` stały dwie sekcje „Dodano” i dwie „Zmieniono” — starsze wpisy nigdy
  nie zostały scalone z nowszymi. Plik deklaruje format Keep a Changelog, a ten zna jedną
  sekcję danego rodzaju na wydanie; czytającego wprost dziennik dwa takie same nagłówki
  wprowadzały w błąd. Sekcje scalone (238 pozycji przed i po), kolejność od najnowszych.
  W oknie „Co nowego” nic się nie zmienia: interfejs czyta rodzaj przy każdej pozycji,
  a nie sam nagłówek.


- **Mignięcie czerni między ekranem startowym a oknem.** Zasłoną na czas pobierania
  pakietu okna była pusta powierzchnia w barwie tła. Tuż przedtem stał tam ekran startowy
  ze znakiem marki — więc znak znikał, przez ułamek sekundy było czarno i dopiero potem
  wchodziło okno. Zmierzone na wejściu „bez rejestracji” (przedsionek): ekran startowy
  widoczny do ~2,2 s, czarno do ~2,5 s, pasek modułów o 2 522 ms. Za progiem logowania
  zasłoną jest teraz ten sam ekran startowy, więc nic nie znika i nic nie miga. Strona
  produktu i portal zostają przy pustej powierzchni — tam ekran startowy byłby nie na miejscu.
  Dodatkowo pakiet ekranu, który zaraz wejdzie, pobiera się **równolegle** z pytaniem
  o sesję, więc w zwykłym otwarciu zasłony nie widać wcale: pakiet jest na miejscu, zanim
  wiadomo, kto patrzy.

- **Otwarcie logowania i okna aplikacji: znak marki rozdymał się w pałąk przez cały ekran.**
  Ekran ładowania kończy się przelotem — łuk znaku wlatuje w łuk nagłówka strony produktu.
  Celu szuka selektorem, a gdy go nie znajdzie, brał zapasowy o promieniu **0,7 szerokości
  ekranu**. Na stronie produktu łuk jest zawsze, więc nikt tego nie widział; na logowaniu
  i w oknie aplikacji łuku nie ma — i przez blisko sekundę biały pałąk szedł **przez kartę
  logowania**, w poprzek pól formularza. Dokładnie to widać było jako „animacja albo źle
  zrobiona, albo uszkodzona”. Bez celu nie ma teraz przelotu: znak gaśnie w miejscu.
  Dodatkowo karta logowania czeka, aż plansza naprawdę zejdzie — wcześniej wchodziła pod
  gasnącym znakiem. (Karta dostała przy okazji własną klasę wejścia zamiast narzędziowej:
  skrót `animation` z warstwy narzędzi zerował `animation-play-state` i wstrzymanie
  nie działało wcale.)

- **Bramka wydania testowała interfejs na plikach z poprzedniej budowy.** Krok „testy
  interfejsu” wołał `npx vitest run`, czyli z pominięciem haków npm, i stoi **przed** budową
  interfejsu. Część testów czyta pliki generowane ze źródeł (ekran ładowania w
  `frontend/public` jest kopią z `landing/`), więc sprawdzały to, co zostało po poprzednim
  przebiegu, a nie bieżące źródła. Krok woła teraz `npm test`, a ten przez `pretest`
  przegenerowuje zasoby i katalog narzędzi.

- **`npm test` nie przygotowywał sobie zasobów, choć dokumentacja tak mówiła.** Skrypt
  `frontend/scripts/narzedzia.py` opisuje siebie jako „uruchamiane razem z `zasoby.py`
  przed `dev`, `build` i `test`”, a hak `pretest` nie istniał — były tylko `predev`
  i `prebuild`. W tym repozytorium nie było tego widać, bo katalog `frontend/public`
  leży na dysku po poprzednich budowach; na świeżym klonie `npm test` szedł na plikach,
  których jeszcze nie ma. Hak dołożony (0,04 s na przebieg).

- **Cała obsługa wdrożenia była poza repozytorium.** `.gitignore` miał wiersz `wydania/`
  — bez ukośnika, a taki wzorzec dopasowuje **każdy** katalog o tej nazwie, na dowolnej
  głębokości. Obok zamierzonego `wydania/` (artefakty budowy) złapał `deploy/wydania/`,
  czyli `zbuduj.sh`, `wypchnij.sh`, `cofnij.sh`, `sprzataj.sh`, `wersje.sh` i README.
  Świeży klon nie miał czym zbudować ani wypchnąć wydania, a poprawki w tych skryptach
  nie były nigdzie zapisane. Ten sam wzorzec w wierszu `dane/` złapał `frontend/src/dane/`
  — katalog z kodem, w którym leży ręcznie pisane `zastosowania.ts`. Oba katalogi są znowu
  widoczne dla gita; pliki `.env` z `deploy/wydania/` zostają pominięte.

- **Sprzątanie po rozłączonym komputerze mogło stanąć albo zginąć bez śladu.** Po
  rozłączeniu gniazda serwer czekał na zadanie przekazujące **bez limitu** (a ono wisi na
  odczycie z kanału Redisa), a samo skreślenie komputera z listy podłączonych szło przez
  `suppress(Exception)` — który nie łapie `CancelledError`, więc w anulowanym zadaniu
  przepadało po cichu. Teraz czekanie ma limit dwóch sekund, skreślenie idzie przez
  `asyncio.shield`, a nieudana próba zostawia ostrzeżenie w dzienniku. **Uwaga:** to nie
  domyka jeszcze całej sprawy — przy brokerze Redisa komputer nadal potrafi zostać na
  liście do wygaśnięcia wpisu (90 s); opis i sposób odtworzenia w raporcie.

- **Strony publiczne portalu pokazywały komunikaty pisane do kogoś innego.** Cennik,
  strona główna, wpisy, dokumentacja i wyszukiwanie przepisywały na ekran treść odpowiedzi
  serwera. Ta treść jest pisana do zalogowanego klienta albo do administratora — przy 401
  odwiedzający, który wszedł z wyszukiwarki, dostawał **„Wymagane logowanie.”** na stronie,
  na której nie ma czego logować. Teraz jest jedno zdanie po naszej stronie („Nie udało się
  pobrać treści. Odśwież stronę za chwilę albo napisz do nas.”), a szczegół idzie do konsoli
  przeglądarki. Komunikaty serwera zostają tam, gdzie niosą treść: przy formularzach
  kontaktu i konta, gdzie mówią, co poprawić.

- **Bieg agenta zostawiał po sobie zadania w trakcie sprzątania.** Po zakończeniu biegu
  `AgentRunner` anulował swoje zadania pomocnicze (obserwator anulowania, czytnik stderr,
  dwa oczekiwania), ale żadnego nie zbierał — a `cancel()` sam niczego nie kończy, tylko
  zaznacza prośbę. Obserwator anulowania w tej chwili siedzi w sesji bazy i ma jeszcze
  wycofać transakcję. W usłudze pętla zdarzeń żyje dalej i zdąży to dokończyć; przy pętli
  zamykanej zaraz po biegu — czyli w testach — zamykanie potrafiło stanąć **na zawsze**
  i przez to wieszało całą bramkę wydania aż do limitu czasu. Bieg czeka teraz, aż jego
  zadania naprawdę się skończą.

- **Bramka wydania mówi, na czym stanęła.** Przy błędzie kończyła się na nagłówku kroku,
  a powód leżał w osobnym dzienniku wydania. Teraz wypisuje krok, kod wyjścia, ścieżkę
  dziennika i jego piętnaście ostatnich wierszy.

- **Skrypt Stripe wpisywał do konfiguracji wartość bez cudzysłowów.** `deploy/zapisz-stripe.sh`
  zapisywał cennik `printf '%s=%s'`, więc przy kolejnym uruchomieniu średniki wróciłyby do
  pliku bez cudzysłowów i znowu rozbiłyby polecenia administracyjne. Zapis idzie teraz
  w cudzysłowach.

- **Wszystkie polecenia administracyjne były zepsute.** `deploy/nexus-cli.sh` wczytuje
  konfigurację poleceniem `source`, a wartości z niecytowanym średnikiem i spacją rozpadają
  się wtedy na osobne polecenia: cennik Stripe (`kod:okres=price_…;kod:okres=price_…`)
  kończył pracę skryptu komunikatem „command not found”, zanim cokolwiek się wykonało.
  systemd czyta ten sam plik inaczej, więc usługi działały i nic nie zwracało uwagi.
  Wartości są ujęte w cudzysłowy, a `backend/tests/test_srodowisko.py` pilnuje, żeby wzór
  konfiguracji dał się wczytać powłoką i żeby cudzysłowy nie weszły do samej wartości.
  Po poprawce `deploy/nexus-cli.sh doctor` przechodzi 23 kontrole bez błędu.

- **Osiem programów leżało poza ścieżką usług, więc całe funkcje odmawiały pracy.**
  `PATH` w `.env` wymieniał trzy katalogi `/danaco/programy`, a narzędzia agenta wywołują
  programy z sześciu. Skutek widać było dopiero przy użyciu: `typeset_document` odpowiadał
  „Skład dokumentów (Typst) jest niedostępne na tym serwerze” — czyli cały skład do druku
  nie działał; `video_to_gif` tak samo; `code_check` tracił pięć kontroli z siedmiu
  (gitleaks, osv-scanner, ruff, shellcheck, typos), a `convert_documents` konwersje przez
  pandoca. `PATH` obejmuje teraz wszystkie sześć katalogów, a komentarz w `.env.example`
  wiąże każdy z narzędziem, którego dotyczy.

- **Moduł Urządzenia kazał szukać w telefonie funkcji, której tam nie ma.** Podpowiedź przy
  nowym kluczu mówiła: „W aplikacji Nexus na telefonie wybierz »Połącz z serwerem« i zeskanuj
  kod QR”. Aplikacja Android nie ma ani tego ekranu, ani czytnika kodów — zakłada klucz sama
  przy pierwszym zalogowaniu (manifest nie rejestruje schematu `danaconexus://`). Podpowiedź
  mówi teraz to, co telefon robi naprawdę; kod QR zostaje dla urządzeń wpisywanych ręcznie.

- **Agent wtrącał zdania po angielsku.** Zapowiedzi przed użyciem narzędzia („I'll load the
  typesetting tool…”) pokazywały się w polskiej rozmowie. Zasada w podpowiedzi mówiła
  „pisz po polsku”; mówi teraz wprost, że dotyczy to także jednozdaniowych zapowiedzi.

- **Nieoczekiwany błąd pokazywał użytkownikowi wnętrze serwera.** Przebieg agenta
  i zadania modułowe wpisywały do komunikatu treść wyjątku („Błąd wewnętrzny: …”), a w niej
  bywa ścieżka na dysku producenta albo fragment zapytania do bazy — czyli dokładnie to,
  czego użytkownik widzieć nie powinien i co i tak nic mu nie mówi. Treść wyjątku zostaje
  teraz w dzienniku, a na ekran idzie zdanie do przeczytania wraz ze skrótem numeru
  przebiegu, po którym da się znaleźć wpis w dzienniku przy zgłoszeniu.

- **Karta planu Pro na stronie sprzedażowej też obiecywała automatyzacje.** Ten sam
  nieistniejący punkt stał w `landing/tresc.ts`, czyli na najbardziej widocznej stronie
  produktu — obok rozwijanego zakresu prosto z serwera, który go nie wymieniał. W jego
  miejsce weszły pozycje, które katalog planów faktycznie zna: cztery zadania naraz,
  dziesięć adresów w domenie Nexusa, wersje plików i synchronizacja. Test
  `tresc-produktu` pilnuje, żeby słowo „automatyzacje” nie wróciło do kart planów, dopóki
  nie wróci sama funkcja.

- **Panel klienta obiecywał funkcję, której nie ma.** Zakres planu brał się z kopii
  w pliku z treścią portalu, a ta wymieniała „Automatyzacje według harmonogramu” — katalog
  płatności takiej pozycji nie zna (`uprawnienia.py`: „automatyzacje nie mają jeszcze
  modułu”). Panel czyta teraz plan z katalogu (`/api/platnosci/cennik`) po kodzie albo
  nazwie; gdy katalog nie zna planu konta, karta nie zmyśla zakresu, tylko odsyła do
  cennika. Nieużywana już lista planów zniknęła z `portal/tresc.ts` razem z resztą
  nieaktualnych obietnic („Cena przy starcie — wkrótce” przy planie, który ma cenę).

- **Wyszukiwarka portalu trafiała w środek wyrazów.** Warunek `LIKE '%slowo%'` uznawał
  za trafienie dowolny fragment: zapytanie „or” pasowało do „który” i wyciągało z bazy
  wszystko, więc wynik wyglądał, jakby wyszukiwarka zgadywała. Dopasowanie idzie teraz
  do początku wyrazu — „modul” nadal znajduje „moduł” i „modułu”, „or” nie znajduje już
  „który”. Ocena trafności liczy tak samo jak warunek.

- **Diagnostyka przewracała się na pierwszej kontroli, która zawiodła.** `doctor` wywołuje
  `ffmpeg` przy sprawdzaniu rozpoznawania mowy; brak programu wychodził jako
  `FileNotFoundError` i przerywał całe polecenie w połowie — reszty kontroli nikt już nie
  zobaczył, choć właśnie po to się je uruchamia. Wyjątek w kontroli jest teraz jej wynikiem
  („kontrola przerwana”), a brak `ffmpeg` — zwykłym brakiem programu.

- **Diagnostyka nie pytała, czy ktokolwiek odbiera zadania.** Nowa kontrola „kolejka zadań”
  liczy przebiegi stojące w stanie `queued` dłużej niż pięć minut i wskazuje proces roboczy
  tej bazy. To jedyny ślad, po którym widać instalację przyjmującą zlecenia bez wykonawcy —
  dokładnie tę usterkę, którą miał przedsionek.

- **Panel zadań nie mówił, jak długo zadanie czeka.** Pozycja w kolejce pokazywała samo
  „W kolejce”, więc zadanie czekające kwadrans wyglądało jak dopiero wysłane. Teraz stoi
  przy nim czas czekania — ten sam, co przy pracy w toku.

- **Zadanie stojące w kolejce udawało pracę w toku.** Tura w stanie „queued” rysowała
  dokładnie to samo co praca trwająca: migające kropki, bez końca i bez słowa. Tak wyglądał
  przedsionek bez procesu roboczego — wiadomość przyjęta, kropki migają, nic się nie dzieje.
  Po czterdziestu pięciu sekundach w kolejce tura mówi teraz wprost, że zadanie czeka
  dłużej niż zwykle, i podpowiada, co zrobić. Praca, która już ruszyła, nie zmienia
  zachowania.

- **Przy wyłączonej piaskownicy narzędzia brały kod z innego miejsca niż agent.** Gdy
  `agent_piaskownica=False`, serwer MCP ze stu jeden narzędziami uruchamia CLI w przestrzeni
  użytkownika — pakietu `nexus` przy bieżącym katalogu tam nie ma, więc import spadał na
  instalację edytowalną z `.venv`, czyli na stan roboczy repozytorium, niezależnie od
  wydania. Konfiguracja podaje teraz `PYTHONPATH` wyliczony z miejsca, z którego pakiet
  załadował się w procesie roboczym. (Przy włączonej piaskownicy — tak jest domyślnie —
  serwer startuje poza piaskownicą z mostu, dziedzicząc katalog procesu roboczego, więc
  ten problem go nie dotyczył.)

- **Świeża instalacja nie miała z czego wstać.** `deploy/instalacja.sh` budował
  `frontend/dist`, ale nigdy nie tworzył wydania, a usługi produkcji biorą kod i interfejs
  z `wydania/produkcja` — na nowej maszynie nie startowały. Instalator przechodzi teraz
  bramkę i wypycha pierwsze wydanie, gdy `wydania/produkcja` jeszcze nie ma; istniejącej
  instalacji ten krok nie dotyka.

- **Produkcyjny proces roboczy chodził na stanie roboczym repozytorium.** Usługa API bierze
  kod z wydania (`wydania/produkcja/backend`), ale proces roboczy — czyli sam agent — miał
  `WorkingDirectory` ustawione na `backend/` w repozytorium. Pracował więc na kodzie, który
  nie przeszedł bramki, zmieniał się przy każdej edycji pliku i którego `cofnij.sh` nie
  cofał: cofnięcie przywracało poprzednie API i zostawiało agenta na nowym kodzie. Teraz
  obie jednostki biorą kod z tego samego wydania, a `wypchnij.sh` i `cofnij.sh` restartują
  je obie (`daemon-reload` przed restartem, bo jednostki są dowiązaniami do repozytorium;
  brakującą jednostkę skrypt pomija z komunikatem zamiast przerywać wypchnięcie).
