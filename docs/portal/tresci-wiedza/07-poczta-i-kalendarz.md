# Jak podłączyć pocztę i kalendarz

Nexus czyta Twoją dotychczasową skrzynkę, a nie zakłada nowej. Przed podłączeniem warto
przygotować dwie rzeczy: dane serwerów od swojego dostawcy i osobne hasło do aplikacji.
Poniżej to, co rozstrzyga o powodzeniu, i to, po co warto sięgnąć zaraz potem.

## Hasło do aplikacji zamiast hasła do konta

Więksi dostawcy poczty nie wpuszczają programów zewnętrznych na zwykłe hasło. Zamiast
niego generuje się osobne hasło do aplikacji, w ustawieniach bezpieczeństwa konta
pocztowego. Jest ono odwoływalne pojedynczo, więc odcięcie Nexusa nie rusza Twojego
logowania do poczty.

Nexus zapisuje to hasło na serwerze, w pliku dostępnym tylko dla usługi Nexusa, i nigdy nie odsyła go do przeglądarki.

## Adresy serwerów

Przy popularnych dostawcach adresy i porty wpisują się same po podaniu adresu pocztowego.
Przy skrzynce firmowej weź je od administratora albo z pomocy hostingu: osobno serwer
odbioru i osobno serwer wysyłki, każdy z numerem portu i rodzajem szyfrowania.

Połączenie sprawdza się przed zapisaniem konta. Ten jeden krok oszczędza szukania przyczyny
w wiadomościach, które nie wychodzą.

## Ile miejsca zajmie poczta

Podłączona skrzynka zostaje u Twojego dostawcy. Nexus czyta wiadomości z jego serwera
i nie robi ich kopii, więc sama poczta nie zajmuje przestrzeni konta, bez względu na liczbę
i wielkość skrzynek. Miejsce zajmują dopiero załączniki, o których pobranie do rozmowy
poprosisz Nexusa: zapisują się wtedy jako pliki konta.

## Odpowiedzi, które wysyłasz Ty

Nexus czyta wątek, przygotowuje odpowiedź i zatrzymuje się przed wysłaniem. Przycisk
naciskasz sam. Tej granicy nie da się wyłączyć ustawieniem.

Korzystaj z niej inaczej niż przy zwykłym czacie: poproś o odpowiedź razem z uzasadnieniem
stanowiska, przeczytaj jedno i drugie, a potem wyślij albo popraw.

## Kalendarz i chmura osobista

Kalendarz stoi na chmurze osobistej, a terminy widzisz i dodajesz w module Kalendarz.
W planach Pro i Grupa pokaże je także systemowa aplikacja kalendarza
w telefonie. Podłączasz ją protokołem CalDAV do własnego konta w chmurze: adres i nazwę
użytkownika podaje moduł Kalendarz pod ikoną synchronizacji z telefonem, a hasłem jest hasło
aplikacji utworzone w chmurze (Ustawienia → Bezpieczeństwo), nie hasło do Nexusa.

Usunięcie wydarzenia również czeka na Twoje zatwierdzenie. Dodanie i przesunięcie spotkania
Nexus wprowadza od razu, bez szkicu. Gdy poprosisz o ułożenie planu przyciskiem „Zaplanuj
z Nexusem”, najpierw przejrzy Twoje terminy, żeby nie nakładać nowych spotkań na istniejące.

## Praca, która się opłaca po podłączeniu

- **Przegląd skrzynki** — „Streść wiadomości z ostatniej doby i zaznacz te, które wymagają
  odpowiedzi dzisiaj”.
- **Termin z wątku** — „Załóż spotkanie z terminem z tej korespondencji i dopisz adres
  z podpisu”.
- **Odpowiedź z załącznikiem** — „Odpowiedz na to zapytanie i dołącz cennik z modułu Pliki”.

## Od czego zacząć

Przygotuj hasło do aplikacji i dane serwerów, a potem przejdź przez ekran podłączenia
w module Poczta. Zaraz po podłączeniu skrzynki poproś o streszczenie nieprzeczytanych
wiadomości — zobaczysz przygotowaną odpowiedź, zanim cokolwiek wyślesz.
