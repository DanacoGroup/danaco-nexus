// Treść dokumentów prawnych portalu: polityka prywatności, regulamin i informacja o plikach cookie.
//
// Dokumenty opisują stan faktyczny produktu. Każda wymieniona kategoria danych, nazwa ciasteczka,
// okres przechowywania i limit ma odpowiednik w kodzie serwera (backend/nexus/**) albo w kliencie.
// Zmiana zachowania kodu wymaga zmiany tych tekstów — inaczej dokument przestaje być prawdziwy.

export interface SekcjaPrawna {
  /** Kotwica w adresie strony i identyfikator nagłówka drugiego stopnia. */
  id: string;
  tytul: string;
  /** Treść w Markdown (akapity, listy, tabele) renderowana komponentem Markdown. */
  tresc: string;
}

export interface DokumentPrawny {
  tytul: string;
  opis: string;
  wersja: string;
  obowiazujeOd: string;
  sekcje: SekcjaPrawna[];
}

/** Dane administratora i usługodawcy. Puste pola nie trafiają na stronę, dopóki nie zostaną uzupełnione. */
export const ADMINISTRATOR = {
  nazwa: "Danaco Holding Group Sp. z o.o.",
  produkt: "Danaco Nexus",
  poczta: "support@danaco-group.pl",
  witryna: "https://danaco-nexus.pl",
  /** Numer KRS, NIP i adres siedziby — do uzupełnienia przez właściciela produktu. */
  daneRejestrowe: "",
};

const WERSJA = "1.0";
const OBOWIAZUJE_OD = "20 września 2026";

const REJESTR = ADMINISTRATOR.daneRejestrowe ? `\n\n${ADMINISTRATOR.daneRejestrowe}` : "";

export const POLITYKA_PRYWATNOSCI: DokumentPrawny = {
  tytul: "Polityka prywatności",
  opis: "Jakie dane zbiera Danaco Nexus, po co, na jakiej podstawie, jak długo je trzyma i co trafia do modelu językowego.",
  wersja: WERSJA,
  obowiazujeOd: OBOWIAZUJE_OD,
  sekcje: [
    {
      id: "administrator",
      tytul: "1. Administrator danych i kontakt",
      tresc: `Administratorem Twoich danych osobowych jest **${ADMINISTRATOR.nazwa}** — producent i operator usługi ${ADMINISTRATOR.produkt}.${REJESTR}

We wszystkich sprawach dotyczących danych osobowych, w tym przy korzystaniu z praw opisanych w rozdziale 9, napisz na adres **${ADMINISTRATOR.poczta}**.

Administrator nie korzysta z zewnętrznych narzędzi analitycznych ani reklamowych. Nie prowadzi profilowania odwiedzających i nie sprzedaje danych.

Do działania usługi potrzebni są natomiast dostawcy zewnętrzni: dostawca modelu językowego (Anthropic), usługa mowy Google Cloud, Stripe, serwer poczty i usługa powiadomień przeglądarki. Pełny wykaz wraz z zakresem przekazywanych danych podaje rozdział 6.`,
    },
    {
      id: "zakres",
      tytul: "2. Czego dotyczy ta polityka",
      tresc: `Polityka obejmuje wszystkie części produktu ${ADMINISTRATOR.produkt}:

- stronę produktu i portal pod adresem ${ADMINISTRATOR.witryna},
- konto klienta zakładane w portalu,
- aplikację Nexus (rozmowy z agentem, rozmowa głosowa, pliki, poczta, kalendarz, chmura osobista, baza wiedzy),
- wejście bez rejestracji pod adresem \`/wyprobuj\`, czyli tę samą aplikację na koncie próbnym,
- okno aplikacji dodane z przeglądarki na telefonie, tablecie albo komputerze — ta sama usługa, jedno logowanie.

Każde konto ma w Nexusie własną przestrzeń. Rozmowy, pliki, przebiegi zadań, podłączone skrzynki pocztowe, spis Twoich kolekcji bazy wiedzy i materiały badawcze są przypisane do konta, które je założyło, i widzi je wyłącznie jego właściciel — także wtedy, gdy ta sama osoba ma u nas kilka kont. Na urządzeniu nie zostaje nic poza oknem aplikacji.

Dotyczy to również wyszukiwania po znaczeniu: każdy fragment zaindeksowany w bazie wiedzy nosi znacznik konta, a wyszukiwanie przeszukuje wyłącznie fragmenty tego konta, z którego pyta agent.

Ile miejsca ma konto, rozstrzyga wybrany plan: 100 MB w okresie próbnym, 1 GB w planie Osobistym, 2 GB w planie Pro i 10 GB w planie Grupa. Przestrzeń jest wspólna dla plików, poczty i chmury osobistej; po jej zapełnieniu kolejny plik nie zostanie przyjęty, dopóki czegoś nie usuniesz albo nie przejdziesz na wyższy plan.

Polityka nie obejmuje serwisów, do których przejdziesz z odsyłacza w wynikach pracy agenta ani kont poczty i kalendarza, którymi zarządzasz u swoich dostawców.`,
    },
    {
      id: "kategorie",
      tytul: "3. Jakie dane zbieramy",
      tresc: `Wykaz odpowiada temu, co zapisuje kod serwera. Nie ma tu kategorii zbieranych „na wszelki wypadek”.

| Kategoria | Co dokładnie | Skąd pochodzi |
|---|---|---|
| Konto klienta portalu | adres poczty, hasło wyłącznie jako skrót Argon2, imię lub nazwa, nazwa firmy, wybrany plan, daty założenia, zmiany i ostatniego logowania | formularz rejestracji i profil |
| Sesja i logowanie | skrót tokenu sesji, adres IP, nagłówek przeglądarki (User-Agent), daty założenia, ostatniej aktywności i wygaśnięcia | zapisywane automatycznie przy logowaniu |
| Odzyskiwanie hasła | skrót tokenu jednorazowego, data utworzenia, wygaśnięcia i użycia | formularz odzyskiwania hasła |
| Potwierdzenie adresu poczty | skrót tokenu jednorazowego, data utworzenia, wygaśnięcia i użycia | odsyłacz potwierdzający wysłany po rejestracji |
| Wiadomość z formularza kontaktu | imię lub nazwa, adres poczty, temat, treść wiadomości, data i stan obsługi | formularz kontaktu |
| Praca z agentem | rozmowy i ich tytuły, wiadomości, przebiegi zadań wraz z liczbą zużytych tokenów, wywołania narzędzi z danymi wejściowymi i podsumowaniem wyniku | Twoje polecenia w aplikacji |
| Rozmowa głosowa | nagranie Twojej wypowiedzi z mikrofonu, rozpoznany z niego tekst oraz tekst odpowiedzi czytanej na głos | włączenie rozmowy głosowej w aplikacji |
| Pliki | nazwa, typ, rozmiar, suma kontrolna SHA-256, ścieżka w magazynie na serwerze oraz sama treść pliku | pliki przesłane przez Ciebie i wytworzone przez narzędzia |
| Baza wiedzy | fragmenty wskazanych przez Ciebie dokumentów i ich reprezentacje liczbowe w bazie wektorowej na serwerze | indeksowanie, o które poprosisz |
| Moduł badawczy | kolekcje, źródła, notatki i raporty, które zapiszesz | Twoja praca w module |
| Poczta | dane konta poczty (adres, serwery, login i hasło) w pliku konfiguracji na serwerze oraz treść czytanych i wysyłanych wiadomości wraz z załącznikami i adresami korespondentów | podłączenie konta poczty i praca w module Poczta |
| Kalendarz | wydarzenia wraz z terminem, opisem, miejscem i uczestnikami | kalendarz CalDAV chmury osobistej |
| Chmura osobista | nazwy, ścieżki i treść plików oraz folderów | magazyn Nextcloud tej instalacji |
| Klucze urządzeń | nazwa i rodzaj urządzenia, skrót klucza, data ostatniego użycia | włączenie połączenia z komputerem albo dodatku do przeglądarki |
| Powiadomienia | adres punktu odbioru powiadomień w przeglądarce, klucze szyfrujące, nagłówek przeglądarki, nazwa urządzenia | zgoda na powiadomienia udzielona w przeglądarce |
| Płatności | wybrany plan, okres i stan subskrypcji wraz z datą końca okresu próbnego, identyfikatory klienta i subskrypcji w Stripe, numer, kwota i stan faktury, odsyłacze do dokumentu, treść zdarzeń rozliczeniowych | zakup planu i przedłużenie zakresu pracy |
| Kredyty konta | saldo kredytów, suma przydzielonych i zużytych oraz księga zmian: data, liczba kredytów, powód, saldo po operacji i wskazanie zadania, którego dotyczy | przydział z planu, dokupiony pakiet i praca agenta |
| Pokaz bez konta | sesja gościa, adres IP, pliki wgrane na pokaz i treść wiadomości do agenta | wejście na stronę pokazu |

Nagranie z mikrofonu leży w katalogu roboczym serwera tylko na czas rozpoznania mowy i jest kasowane zaraz po nim. Zapisany zostaje rozpoznany tekst, jeżeli wyślesz go jako wiadomość do agenta.

Wiadomości poczty, wydarzenia kalendarza i pliki chmury osobistej zostają tam, gdzie są: na serwerze Twojego dostawcy poczty oraz w chmurze osobistej tej instalacji. Nexus nie prowadzi ich własnej kopii. Do bazy trafia wyłącznie to, co powstaje w czasie pracy: treść rozmowy z agentem, pliki, które zapiszesz, oraz działanie przygotowane do zatwierdzenia — wysyłka wiadomości albo usunięcie wydarzenia — razem z jego treścią.

Numerów kart płatniczych nie przyjmujemy i nie przechowujemy — dane karty podajesz bezpośrednio na stronie Stripe.`,
    },
    {
      id: "podstawy",
      tytul: "4. Po co i na jakiej podstawie",
      tresc: `| Cel | Dane | Podstawa prawna |
|---|---|---|
| Założenie i prowadzenie konta, udostępnienie aplikacji, praca agenta na Twoje polecenie | konto, sesje, rozmowy, pliki, baza wiedzy, moduł badawczy, klucze urządzeń | art. 6 ust. 1 lit. b RODO — wykonanie umowy |
| Rozmowa głosowa: rozpoznanie Twojej wypowiedzi i przeczytanie odpowiedzi na głos | nagranie z mikrofonu, rozpoznany tekst, tekst czytany na głos | art. 6 ust. 1 lit. b RODO — wykonanie umowy |
| Praca z pocztą, kalendarzem i chmurą osobistą na Twoje polecenie | dane konta poczty, treść wiadomości wraz z załącznikami i adresami korespondentów, wydarzenia kalendarza, pliki chmury osobistej, działanie przygotowane do zatwierdzenia | art. 6 ust. 1 lit. b RODO — wykonanie umowy |
| Sprzedaż planu, rozliczenie subskrypcji, wystawienie faktury | dane subskrypcji i faktur | art. 6 ust. 1 lit. b RODO oraz art. 6 ust. 1 lit. c RODO — obowiązek podatkowy i rachunkowy |
| Rozliczenie kredytów: przydział z planu, dopisanie dokupionego pakietu, naliczenie za wykonane zadanie i pokazanie Ci, za co kredyty zeszły | saldo kredytów i księga ich zmian | art. 6 ust. 1 lit. b RODO — wykonanie umowy |
| Potwierdzenie, że adres poczty należy do Ciebie | adres poczty, skrót tokenu jednorazowego, daty | art. 6 ust. 1 lit. b RODO — wykonanie umowy |
| Bezpieczeństwo: rozpoznanie nadużyć, ograniczenie tempa prób logowania i odzyskiwania hasła, wygaszanie sesji | adres IP, nagłówek przeglądarki, skróty tokenów, daty aktywności | art. 6 ust. 1 lit. f RODO — prawnie uzasadniony interes w ochronie usługi |
| Odpowiedź na wiadomość z formularza kontaktu | imię, adres poczty, treść wiadomości | art. 6 ust. 1 lit. f RODO — prawnie uzasadniony interes w obsłudze zapytania |
| Udostępnienie pokazu bez konta wraz z limitami chroniącymi serwer | sesja gościa, adres IP, pliki i wiadomości pokazu | art. 6 ust. 1 lit. f RODO — prawnie uzasadniony interes w prezentacji produktu i ochronie zasobów |
| Wysyłka powiadomień do przeglądarki | punkt odbioru i klucze szyfrujące | art. 6 ust. 1 lit. a RODO — zgoda udzielona w przeglądarce |
| Obrona przed roszczeniami i dochodzenie roszczeń | dane konta, rozliczeń i korespondencji | art. 6 ust. 1 lit. f RODO — prawnie uzasadniony interes |

Podanie adresu poczty i hasła jest konieczne do założenia konta. Bez nich nie da się zawrzeć umowy. Pozostałe dane profilu podajesz dobrowolnie.`,
    },
    {
      id: "model",
      tytul: "5. Co trafia do modelu językowego",
      tresc: `Rozumowanie i planowanie wykonuje model językowy dostarczany przez **Anthropic PBC** (Stany Zjednoczone). Wskazujemy tego dostawcę, bo obowiązek informacyjny tego wymaga; nazw i wersji modeli nie podajemy, ponieważ dobieramy je sami i zmieniamy bez wpływu na zakres przetwarzanych danych opisany niżej.

Anthropic nie jest jedynym odbiorcą. Rozmowa głosowa korzysta z usługi mowy Google Cloud, a wysyłka wiadomości — z serwera poczty. Ten rozdział opisuje wyłącznie model językowy; komplet odbiorców podaje rozdział 6.

**Do modelu trafia:**

- treść Twojej wiadomości do agenta,
- fragmenty i podglądy plików, które agent musi przeczytać, aby wykonać zadanie,
- wyniki narzędzi uruchomionych na serwerze, na przykład rozpoznany tekst, wypis katalogu albo wynik wyszukiwania,
- historia bieżącej rozmowy w zakresie potrzebnym do jej kontynuowania,
- stałe polecenie systemowe opisujące zasady pracy agenta i wykaz dostępnych narzędzi.

**Do modelu nie trafia:**

- pełna treść plików, których zadanie nie wymaga — pliki zostają w przestrzeni Twojego konta,
- baza wiedzy i indeks znaczeniowy; wyszukiwanie po znaczeniu wykonuje serwer,
- hasła, skróty haseł, tokeny sesji ani klucze urządzeń,
- dane kont klientów, faktury i dane rozliczeniowe.

Gdy poprosisz o pracę z siecią, agent może użyć narzędzi wyszukiwania i odczytu stron działających po stronie Anthropic. Zapytanie i adres strony trafiają wtedy do Anthropic. Narzędzia badawcze Nexusa łączą się z wyszukiwarką i serwisami naukowymi bezpośrednio z serwera Danaco, z pominięciem Anthropic.

Zakres przetwarzania po stronie Anthropic — w tym to, czy przekazane treści mogą posłużyć do rozwoju modeli — wynika z warunków usługi, na której działa silnik Nexusa. Warunki te opisuje Anthropic w swoich dokumentach.

Agent pracuje wyłącznie narzędziami zarejestrowanymi w Nexusie. Działanie na Twoim komputerze — polecenie systemowe, odczyt pliku, zrzut okna — jest możliwe dopiero po włączeniu połączenia z komputerem i wymaga Twojego potwierdzenia za każdym razem.`,
    },
    {
      id: "odbiorcy",
      tytul: "6. Komu powierzamy dane",
      tresc: `| Odbiorca | Rola | Co otrzymuje | Kiedy |
|---|---|---|---|
| Anthropic PBC (model językowy) | podmiot przetwarzający | treść bieżącego zadania w zakresie opisanym w rozdziale 5 | przy każdym poleceniu dla agenta |
| Google (usługa mowy Google Cloud) | podmiot przetwarzający | nagranie Twojej wypowiedzi z mikrofonu wraz z kodem języka oraz tekst, który agent ma przeczytać na głos | przy rozmowie głosowej, gdy na serwerze jest zapisany klucz Google Cloud — wtedy mowę rozpoznaje Google, a model lokalny jest zapasem |
| Stripe | podmiot przetwarzający | adres poczty i nazwa klienta, wybrany plan, dane płatności podane w kasie Stripe | wyłącznie przy zakupie i obsłudze planu płatnego |
| Dostawca serwera poczty | odbiorca techniczny | adres odbiorcy, temat i treść wysyłanej wiadomości | przy wiadomościach portalu o odzyskaniu hasła, zmianie hasła i usunięciu konta, jeżeli wysyłka przez serwer SMTP jest włączona, oraz gdy zatwierdzisz wysyłkę zleconą agentowi |
| Dostawca usługi powiadomień przeglądarki | odbiorca techniczny | adres punktu odbioru i zaszyfrowana treść powiadomienia | gdy włączysz powiadomienia |
| Serwisy wskazane w zadaniu | odbiorca | zapytanie wyszukiwania i adres strony | gdy zlecisz zadanie badawcze |

Dane mogą też zostać udostępnione organom uprawnionym na podstawie przepisów prawa. Poza tymi przypadkami nie przekazujemy ich nikomu.`,
    },
    {
      id: "poza-eog",
      tytul: "7. Przekazanie poza Europejski Obszar Gospodarczy",
      tresc: `Część usług, z których korzysta Nexus, jest świadczona przez dostawców spoza Europejskiego Obszaru Gospodarczego albo z użyciem infrastruktury położonej poza nim:

- **Anthropic PBC (model językowy)** — treść bieżącego zadania w zakresie opisanym w rozdziale 5,
- **Google (usługa mowy Google Cloud)** — nagranie wypowiedzi z mikrofonu i tekst czytany na głos; dane idą do punktów końcowych \`speech.googleapis.com\` i \`texttospeech.googleapis.com\`,
- **Stripe** — dane zakupu i rozliczenia planu płatnego,
- **dostawca usługi powiadomień przeglądarki** — zależnie od przeglądarki, z której korzystasz,
- **dostawca serwera poczty** — zależnie od tego, który serwer obsługuje wysyłkę.

Takie przekazanie odbywa się wyłącznie na podstawie instrumentu przewidzianego w rozdziale V RODO wskazanego w umowie zawartej z danym dostawcą — decyzji o odpowiednim stopniu ochrony albo standardowych klauzul umownych.

Kopię lub opis zastosowanego zabezpieczenia otrzymasz po napisaniu na ${ADMINISTRATOR.poczta}.`,
    },
    {
      id: "okresy",
      tytul: "8. Jak długo przechowujemy dane",
      tresc: `| Dane | Okres |
|---|---|
| Konto próbne („Wypróbuj bez rejestracji”) | 2 dni od założenia; potem usuwane automatycznie razem z rozmowami, plikami i pozostałymi danymi konta |
| Konto klienta portalu | do czasu usunięcia konta; usunięcie jest nieodwracalne i kasuje konto wraz z sesjami, tokenami odzyskiwania oraz rozmowami, plikami, bazą wiedzy, stronami, projektami i chmurą konta |
| Sesja portalu | do wygaśnięcia ciasteczka (domyślnie 14 dni) albo do 7 dni bezczynności — rozstrzyga krótszy termin; rekordy wygasłe są kasowane przy kolejnym logowaniu |
| Sesja aplikacji | do wygaśnięcia (domyślnie 30 dni) albo do wylogowania |
| Token odzyskiwania hasła | do użycia albo do wygaśnięcia (domyślnie 30 minut) |
| Token potwierdzenia adresu poczty | do użycia albo do wygaśnięcia (24 godziny) |
| Rozmowy, pliki, wyniki narzędzi, baza wiedzy, materiały badawcze | do czasu, aż je usuniesz; mieszczą się w przestrzeni konta, którą wyznacza plan (rozdział 2) |
| Saldo kredytów i księga ich zmian | przez czas prowadzenia konta, a następnie przez okres rozliczenia subskrypcji i przedawnienia roszczeń — księga jest dowodem, za co kredyty zostały naliczone |
| Nagranie rozmowy głosowej | kasowane z serwera zaraz po rozpoznaniu mowy; rozpoznany tekst zostaje tylko wtedy, gdy wyślesz go jako wiadomość — wtedy trwa tak jak rozmowy. Okres po stronie Google wynika z warunków tej usługi |
| Wiadomości poczty, wydarzenia kalendarza, pliki chmury osobistej | Nexus nie prowadzi ich kopii: zostają odpowiednio na serwerze Twojego dostawcy poczty i w chmurze osobistej, do czasu, aż je usuniesz |
| Dane konta poczty w pliku konfiguracji na serwerze | do usunięcia tego konta w module Poczta |
| Działanie przygotowane do zatwierdzenia (wysyłka wiadomości, zmiana w kalendarzu) | do zatwierdzenia albo odrzucenia, a potem jeszcze 30 dni jako historia w module Poczta i Kalendarz |
| Wiadomość z formularza kontaktu | do załatwienia sprawy, a następnie przez okres przedawnienia roszczeń |
| Faktury i dane rozliczeniowe | przez okres wymagany przepisami podatkowymi i o rachunkowości |
| Kopie zapasowe serwera | 14 dni; dane usunięte z konta znikają z kopii najpóźniej po tym czasie, a kopia służy wyłącznie odtworzeniu usługi po awarii |
| Dziennik zdarzeń rozliczeniowych | przez okres rozliczenia subskrypcji i przedawnienia roszczeń |
| Klucz urządzenia | do odwołania klucza w ustawieniach |
| Subskrypcja powiadomień | do wycofania zgody w przeglądarce albo do trwałego błędu doręczenia |
| Sesja pokazu bez konta | 30 minut; po tym czasie sesja i wgrane pliki gościa są kasowane |`,
    },
    {
      id: "prawa",
      tytul: "9. Twoje prawa",
      tresc: `Przysługuje Ci prawo do:

- **dostępu** do danych i uzyskania ich kopii,
- **sprostowania** danych nieprawidłowych lub niekompletnych,
- **usunięcia** danych; konto klienta usuniesz samodzielnie w panelu — operacja wymaga hasła i słowa potwierdzenia, i jest nieodwracalna,
- **ograniczenia przetwarzania**,
- **przenoszenia** danych przetwarzanych na podstawie umowy lub zgody,
- **sprzeciwu** wobec przetwarzania opartego na prawnie uzasadnionym interesie,
- **cofnięcia zgody** w każdej chwili; cofnięcie nie wpływa na zgodność z prawem przetwarzania sprzed cofnięcia.

Żądanie skieruj na ${ADMINISTRATOR.poczta}. Odpowiadamy bez zbędnej zwłoki, najpóźniej w terminie miesiąca od otrzymania żądania.

Masz też prawo wnieść skargę do Prezesa Urzędu Ochrony Danych Osobowych, ul. Stawki 2, 00-193 Warszawa.`,
    },
    {
      id: "bezpieczenstwo",
      tytul: "10. Jak chronimy dane",
      tresc: `- Hasło Twojego konta zapisujemy wyłącznie jako skrót algorytmem Argon2. Nie trzymamy go w postaci jawnej i nie jesteśmy w stanie go odczytać — przy logowaniu porównujemy same skróty.
- Inaczej jest z hasłem do skrzynki pocztowej, którą podłączasz sam. Musi zostać w postaci czytelnej, bo serwer loguje się nim w Twoim imieniu przy każdym sprawdzeniu i wysłaniu wiadomości. Leży w pliku na serwerze dostępnym wyłącznie dla konta usługi, osobnym dla każdego konta użytkownika. Usuniesz je, kasując konto poczty w module Poczta. Tak samo przechowywane jest hasło aplikacji do chmury osobistej.
- Ciasteczko sesji ma flagi \`HttpOnly\` i \`SameSite=Lax\`. Flagę \`Secure\` włącza ustawienie serwera \`NEXUS_COOKIE_SECURE\`, domyślnie włączone; nie zależy ona od tego, czy dane połączenie jest szyfrowane. W bazie leży wyłącznie skrót tokenu, nie sam token.
- Połączenie z serwerem idzie przez HTTPS.
- Liczba prób logowania, odzyskiwania hasła, wysyłki formularza kontaktu i usunięcia konta jest ograniczona w czasie.
- Żądania zmieniające stan wymagają nagłówka aplikacji, co blokuje żądania wywołane z obcej witryny.
- Odzyskiwanie hasła nie ujawnia, czy dany adres jest zarejestrowany; czas odpowiedzi jest wyrównany.
- Sesja portalu wygasa po okresie bezczynności, niezależnie od daty wygaśnięcia ciasteczka.
- Rozpoznawanie tekstu, poprawa obrazu, transkrypcja wgranych nagrań i wyszukiwanie po znaczeniu wykonuje sama usługa, bez przekazywania plików dostawcom zewnętrznym.
- Wyjątkiem jest rozmowa głosowa: nagranie z mikrofonu i tekst czytany na głos przechodzą przez Google Cloud Speech (rozdziały 6 i 7). Gdy usługa jest niedostępna, rozpoznawanie i czytanie przejmują modele własne Nexusa.
- Konto próbne zakładane przy wejściu bez rejestracji ma własną przestrzeń jak każde inne konto, mniejszy przydział i termin ważności; po jego upływie rozmowy i pliki tego konta są kasowane.`,
    },
    {
      id: "decyzje",
      tytul: "11. Decyzje automatyczne i profilowanie",
      tresc: `Nie podejmujemy wobec Ciebie decyzji opierających się wyłącznie na zautomatyzowanym przetwarzaniu, które wywoływałyby skutki prawne lub w podobny sposób istotnie na Ciebie wpływały.

Agent przygotowuje wyniki pracy, ale działania zmieniające stan poza Nexusem — wysłanie wiadomości, usunięcie wydarzenia w kalendarzu, polecenie na Twoim komputerze — wykonuje dopiero po Twoim zatwierdzeniu w interfejsie.`,
    },
    {
      id: "zmiany",
      tytul: "12. Zmiany polityki",
      tresc: `Politykę zmieniamy, gdy zmienia się sposób działania produktu albo przepisy. Nową wersję publikujemy na tej stronie wraz z datą, od której obowiązuje.

O zmianie istotnie wpływającej na Twoje prawa informujemy na adres poczty przypisany do konta, z wyprzedzeniem co najmniej 14 dni.`,
    },
  ],
};

export const REGULAMIN: DokumentPrawny = {
  tytul: "Regulamin",
  opis: "Zasady korzystania z Danaco Nexus: zakres usług, konto, plany i płatności, reklamacje i odpowiedzialność.",
  wersja: WERSJA,
  obowiazujeOd: OBOWIAZUJE_OD,
  sekcje: [
    {
      id: "postanowienia",
      tytul: "1. Postanowienia ogólne",
      tresc: `Regulamin określa zasady świadczenia usług drogą elektroniczną w ramach produktu ${ADMINISTRATOR.produkt}, dostępnego pod adresem ${ADMINISTRATOR.witryna}.

Usługodawcą jest **${ADMINISTRATOR.nazwa}**.${REJESTR}

Kontakt: ${ADMINISTRATOR.poczta}.

W regulaminie używamy następujących pojęć:

- **Usługa** — ${ADMINISTRATOR.produkt} wraz z portalem i aplikacją. Aplikację dodaje się z przeglądarki jako osobne okno na telefonie, tablecie albo komputerze; to ta sama usługa i to samo konto, nie osobny produkt do kupienia.
- **Użytkownik** — osoba korzystająca z Usługi, w tym osoba korzystająca z pokazu bez konta.
- **Konto** — konto klienta zakładane w portalu.
- **Agent** — część Usługi wykonująca zadania na polecenie Użytkownika przy udziale modelu językowego dostawcy wskazanego w polityce prywatności.
- **Plan** — zakres Usługi wybrany przez Użytkownika. Wszystkie plany są płatne.
- **Zakres pracy** — ilość pracy Agenta przypadająca na okres rozliczeniowy planu. Rozlicza ją wewnętrzna jednostka Usługodawcy, której Użytkownik nie kupuje osobno i nie przelicza: w Usłudze widzi wykorzystanie zakresu, a nie liczbę jednostek. Po wyczerpaniu zakresu dostęp przedłuża się kwotą wskazaną przez Użytkownika.`,
    },
    {
      id: "uslugi",
      tytul: "2. Zakres usług",
      tresc: `Usługodawca świadczy następujące usługi:

1. **Portal** — dostęp do treści informacyjnych, dokumentacji, bloga i centrum wiedzy oraz formularz kontaktu. Nie wymaga Konta.
2. **Konto klienta** — rejestracja, logowanie, profil, wgląd w plan i faktury, odzyskiwanie hasła, usunięcie Konta.
3. **Aplikacja Nexus** — rozmowa z Agentem, praca na plikach, rozpoznawanie tekstu, konwersje dokumentów i obrazów, transkrypcja nagrań, poczta, kalendarz, chmura osobista, baza wiedzy, moduł badawczy, tworzenie stron oraz rozmowa głosowa.
4. **Wejście bez rejestracji** — pod adresem \`/wyprobuj\` Usługodawca zakłada Konto próbne i udostępnia na nim Aplikację Nexus w pełnym zakresie funkcji, z przydziałem kredytów i przestrzeni okresu próbnego oraz terminem ważności. Po jego upływie Konto próbne wraz z rozmowami i plikami jest kasowane. Założenie Konta klienta przenosi pracę na konto stałe.

Agent działa wyłącznie narzędziami zarejestrowanymi w Usłudze. Usługodawca nie obiecuje funkcji spoza tego zestawu; aktualny wykaz podaje strona **Funkcje** i dokumentacja.`,
    },
    {
      id: "wymagania",
      tytul: "3. Wymagania techniczne",
      tresc: `Do korzystania z Usługi potrzebne są:

- urządzenie z dostępem do internetu,
- aktualna przeglądarka obsługująca JavaScript i pliki cookie; na telefonach z Androidem Chrome, Edge lub Samsung Internet, na iPhonie i iPadzie Safari, na komputerach Edge lub Chrome,
- aktywny adres poczty elektronicznej — do założenia Konta.

Usługę można zainstalować jako aplikację we własnym oknie. Instalacja nie jest obowiązkowa; Usługa działa też w zwykłej karcie przeglądarki.

Korzystanie z internetu wiąże się z ryzykiem typowym dla sieci publicznej. Usługodawca zaleca aktualne oprogramowanie i ochronę urządzenia.`,
    },
    {
      id: "konto",
      tytul: "4. Konto klienta",
      tresc: `1. Umowa o prowadzenie Konta zostaje zawarta z chwilą poprawnej rejestracji.
2. Hasło musi mieć co najmniej 12 znaków. Przechowujemy wyłącznie jego skrót algorytmem Argon2.
3. Użytkownik odpowiada za zachowanie hasła w poufności i za działania podjęte z użyciem jego Konta.
4. Rejestracja może być czasowo zamknięta; informuje o tym formularz rejestracji.
5. Sesja wygasa po upływie ważności albo po 7 dniach bezczynności. Wygaśnięcie sesji nie usuwa Konta.
6. Użytkownik może w każdej chwili usunąć Konto w panelu klienta. Operacja wymaga hasła i słowa potwierdzenia, jest **nieodwracalna** i kasuje Konto wraz z sesjami, tokenami odzyskiwania hasła oraz danymi aplikacji: rozmowami, plikami, bazą wiedzy, stronami, projektami i chmurą. Konta z opłacanym planem nie da się usunąć przed rezygnacją z planu.
7. Usługodawca może zablokować lub usunąć Konto, gdy Użytkownik rażąco narusza regulamin albo przepisy prawa, po uprzednim wezwaniu do zaprzestania naruszenia, chyba że naruszenie zagraża bezpieczeństwu Usługi lub innych osób.`,
    },
    {
      id: "plany",
      tytul: "5. Plany i płatności",
      tresc: `1. Usługa jest dostępna w planach **Osobisty**, **Pro** i **Grupa**. Zakres każdego planu podaje strona **Cennik**.
2. Wszystkie trzy plany są płatne. Plan Osobisty zaczyna się okresem próbnym: przez pierwsze 7 dni nie pobieramy opłaty, kartę podajesz od razu przy zakupie, a po upływie tych dni subskrypcja przechodzi w płatną bez dodatkowego kroku. Rezygnacja przed końcem okresu próbnego nie kosztuje nic.
3. Plan **Grupa** rozlicza się za każdego użytkownika: liczbę miejsc wskazuje Użytkownik przy zakupie, a cena jest iloczynem ceny za miejsce i liczby miejsc. Zakres pracy w grupie jest wspólny i przedłuża go założyciel grupy; rolę założyciela można przekazać innemu członkowi grupy.
4. Ceny i limity planów rozstrzyga serwer. Cena widoczna w kasie płatności jest ceną wiążącą.
5. Płatności obsługuje **Stripe**. Dane karty podajesz bezpośrednio na stronie Stripe; Usługodawca ich nie przyjmuje ani nie przechowuje.
6. Subskrypcję rozlicza się w okresie miesięcznym albo rocznym, z góry, w złotych, i odnawia automatycznie na kolejny okres.
7. Faktury wystawia Stripe. Wykaz faktur i odsyłacze do dokumentów są dostępne w panelu klienta.
8. Rezygnację zgłasza się w panelu rozliczeniowym. Subskrypcja kończy się z upływem opłaconego okresu; do tego czasu Usługa działa bez zmian.
9. Kod rabatowy jest sprawdzany przed zakupem. Kod nieważny, wykorzystany albo przeterminowany nie obniża ceny.
10. Brak zapłaty w terminie skutkuje przejściem subskrypcji w stan zaległy, a po bezskutecznym upływie terminu — utratą uprawnień planu i zatrzymaniem pracy Agenta do czasu uregulowania płatności.
11. Plan obejmuje zakres pracy Agenta na każdy okres rozliczeniowy. Każde zadanie zmniejsza pozostały zakres, a po jego wyczerpaniu Usługa nie przyjmuje kolejnego zlecenia i informuje o tym w interfejsie. Wykorzystanie zakresu i historię zdarzeń pokazuje Aplikacja.
12. Zakres można przedłużyć poza subskrypcją, wskazując kwotę (nie mniejszą niż kwota minimalna podana w Aplikacji). Jest to płatność jednorazowa; przeliczenie kwoty na zakres pracy prowadzi Usługodawca według przelicznika obowiązującego w chwili zapłaty, a zakres dopisuje się po potwierdzeniu wpłaty przez Stripe.`,
    },
    {
      id: "odstapienie",
      tytul: "6. Odstąpienie od umowy",
      tresc: `Użytkownik będący konsumentem albo przedsiębiorcą na prawach konsumenta może odstąpić od umowy zawartej na odległość w terminie 14 dni od jej zawarcia, bez podania przyczyny. Oświadczenie wystarczy wysłać na ${ADMINISTRATOR.poczta}.

Jeżeli Użytkownik zażąda rozpoczęcia świadczenia przed upływem terminu na odstąpienie i przyjmie do wiadomości, że traci wtedy prawo odstąpienia, prawo to wygasa z chwilą pełnego wykonania usługi. Przy świadczeniu częściowym Użytkownik płaci za część wykonaną do chwili odstąpienia.

Zwrot zapłaty następuje tym samym sposobem, którym dokonano płatności, w terminie 14 dni od otrzymania oświadczenia.`,
    },
    {
      id: "zasady",
      tytul: "7. Zasady korzystania",
      tresc: `Użytkownik zobowiązuje się nie:

- przekazywać treści bezprawnych ani naruszających prawa osób trzecich,
- używać Usługi do działań zagrażających bezpieczeństwu systemów teleinformatycznych,
- obchodzić limitów Usługi, w tym limitów pokazu bez konta, ani automatyzować obejścia rejestracji,
- udostępniać Konta osobom trzecim wbrew warunkom wybranego planu,
- podejmować działań obciążających serwer w sposób wykraczający poza zwykłe korzystanie z Usługi.

Użytkownik odpowiada za zgodność z prawem materiałów, które przekazuje Agentowi, w szczególności za podstawę przetwarzania danych osobowych osób trzecich zawartych w tych materiałach.`,
    },
    {
      id: "tresci",
      tytul: "8. Twoje pliki i treści",
      tresc: `1. Pliki, rozmowy i wyniki pracy pozostają Twoje. Usługodawca nie nabywa do nich praw.
2. Usługodawca przetwarza je wyłącznie w zakresie koniecznym do wykonania Twojego polecenia i do świadczenia Usługi.
3. Wyniki pracy pobierzesz w formatach otwartych — PDF, DOCX, TXT, XLSX oraz archiwum ZIP. Usługodawca nie zamyka wyników we własnym formacie.
4. Treści usuwasz samodzielnie. Usunięcie Konta nie zastępuje usunięcia danych aplikacji, jeżeli korzystasz z niej niezależnie od Konta klienta.`,
    },
    {
      id: "agent",
      tytul: "9. Praca agenta i granice odpowiedzialności za wynik",
      tresc: `1. Agent korzysta z modelu językowego dostawcy wskazanego w polityce prywatności. Zakres danych przekazywanych do modelu opisuje ta sama polityka.
2. Wynik pracy modelu może zawierać błędy, pominięcia i treści nieaktualne. **Wynik wymaga sprawdzenia przez Użytkownika** przed użyciem, zwłaszcza w sprawach urzędowych, rozliczeniowych, prawnych i medycznych.
3. Usługa nie jest poradą prawną, podatkową ani medyczną.
4. Rozpoznawanie pisma odręcznego działa wyraźnie słabiej niż rozpoznawanie druku.
5. Działania zmieniające stan poza Usługą — wysłanie wiadomości, usunięcie wydarzenia w kalendarzu, polecenie systemowe na komputerze Użytkownika — wykonują się dopiero po zatwierdzeniu przez Użytkownika.
6. Zadanie Agenta ma ograniczony czas wykonania; zadanie przekraczające ten czas jest przerywane, a Użytkownik widzi komunikat.`,
    },
    {
      id: "dostepnosc",
      tytul: "10. Dostępność usługi i etap rozwoju",
      tresc: `Usługa jest udostępniana na etapie rozwojowym. Zakres funkcji, wygląd i limity mogą się zmieniać, a przerwy techniczne są możliwe.

Usługodawca dokłada starań, aby Usługa działała bez zakłóceń, ale nie gwarantuje nieprzerwanej dostępności. O planowanej przerwie dłuższej niż dwie godziny informuje w portalu z wyprzedzeniem.

Usługodawca nie odpowiada za przerwy wynikające z siły wyższej, awarii po stronie dostawców zewnętrznych ani z działań Użytkownika.

W stosunku do Użytkownika niebędącego konsumentem odpowiedzialność Usługodawcy ogranicza się do szkody rzeczywistej i do wysokości opłat wniesionych za ostatnie dwanaście miesięcy. Ograniczenie nie dotyczy szkody wyrządzonej umyślnie.`,
    },
    {
      id: "reklamacje",
      tytul: "11. Reklamacje",
      tresc: `Reklamację składa się na adres ${ADMINISTRATOR.poczta}. W zgłoszeniu podaj adres poczty przypisany do Konta, opis problemu i oczekiwany sposób załatwienia sprawy.

Reklamację rozpatrujemy w terminie 14 dni od otrzymania i odpowiadamy na adres, z którego ją wysłano.

Konsument może skorzystać z pozasądowych sposobów rozpatrywania reklamacji i dochodzenia roszczeń, w tym z mediacji przy wojewódzkim inspektoracie Inspekcji Handlowej oraz z pomocy miejskiego lub powiatowego rzecznika konsumentów.`,
    },
    {
      id: "dane",
      tytul: "12. Dane osobowe",
      tresc: `Zasady przetwarzania danych osobowych opisuje polityka prywatności, a zasady zapisu informacji na urządzeniu — informacja o plikach cookie. Odsyłacze do obu dokumentów są pod tekstem regulaminu.

Jeżeli Użytkownik przekazuje Agentowi materiały zawierające dane osobowe osób trzecich, pozostaje administratorem tych danych, a Usługodawca przetwarza je na jego polecenie.`,
    },
    {
      id: "zmiany",
      tytul: "13. Zmiany regulaminu",
      tresc: `Usługodawca może zmienić regulamin z ważnych przyczyn: zmiany przepisów, zmiany zakresu Usługi albo zmiany sposobu rozliczeń.

O zmianie informujemy w portalu i na adres poczty przypisany do Konta, z wyprzedzeniem co najmniej 14 dni. Użytkownik, który nie akceptuje zmiany, może przed jej wejściem w życie usunąć Konto albo zrezygnować z subskrypcji bez dodatkowych kosztów.

Do umów zawartych przed zmianą stosuje się regulamin w brzmieniu z dnia zawarcia umowy, chyba że zmiana wynika z bezwzględnie obowiązującego przepisu.`,
    },
    {
      id: "koncowe",
      tytul: "14. Postanowienia końcowe",
      tresc: `W sprawach nieuregulowanych regulaminem stosuje się prawo polskie, w szczególności Kodeks cywilny, ustawę o świadczeniu usług drogą elektroniczną i ustawę o prawach konsumenta.

Wybór prawa polskiego nie pozbawia konsumenta ochrony wynikającej z bezwzględnie obowiązujących przepisów państwa jego zwykłego pobytu.

Spory z Użytkownikiem niebędącym konsumentem rozstrzyga sąd właściwy dla siedziby Usługodawcy.

Regulamin obowiązuje od ${OBOWIAZUJE_OD}, wersja ${WERSJA}.`,
    },
  ],
};

export const COOKIES: DokumentPrawny = {
  tytul: "Pliki cookie",
  opis: "Trzy ciasteczka niezbędne do działania usługi, wpisy pamięci przeglądarki, dwa zasobniki pamięci podręcznej, zero narzędzi śledzących.",
  wersja: WERSJA,
  obowiazujeOd: OBOWIAZUJE_OD,
  sekcje: [
    {
      id: "czym-sa",
      tytul: "1. Czym są pliki cookie",
      tresc: `Pliki cookie to małe pliki tekstowe zapisywane przez serwis w przeglądarce. Przy kolejnym żądaniu przeglądarka odsyła je z powrotem, dzięki czemu serwer rozpoznaje trwającą sesję.

Obok ciasteczek przeglądarka udostępnia pamięć lokalną (\`localStorage\`), pamięć sesji (\`sessionStorage\`) oraz pamięć podręczną aplikacji. Nexus korzysta z każdej z nich — wykaz podają rozdziały 2 i 3.

**Nexus nie używa ciasteczek analitycznych, reklamowych ani ciasteczek podmiotów trzecich.** Na stronach Nexusa — w portalu, w aplikacji i w pokazie bez konta — nie ma skryptów śledzących, pikseli ani wtyczek serwisów społecznościowych.

Osobną sprawą są strony zbudowane przez użytkowników modułem Twórca stron i publikowane pod adresami \`/s/<adres>\`. Ich treść układa autor strony, a zasady bezpieczeństwa serwera dopuszczają w nich skrypty z zewnętrznych sieci dostarczania treści (unpkg.com, cdn.jsdelivr.net, cdnjs.cloudflare.com, esm.sh, cdn.tailwindcss.com) oraz połączenia do innych serwerów. Za to, co taka strona zapisuje w Twojej przeglądarce i dokąd wysyła dane, odpowiada jej autor; ta informacja tego nie obejmuje.`,
    },
    {
      id: "wykaz",
      tytul: "2. Jakie ciasteczka zapisuje Nexus",
      tresc: `| Nazwa | Do czego służy | Zasięg | Czas życia |
|---|---|---|---|
| \`nexus_session\` | utrzymanie sesji zalogowanego użytkownika aplikacji | domena \`danaco-nexus.pl\` wraz z poddomenami, w tym \`cloud.danaco-nexus.pl\` — jedno logowanie do aplikacji i chmury osobistej | domyślnie 30 dni |
| \`nexus_portal\` | utrzymanie sesji konta klienta w portalu | domena \`danaco-nexus.pl\` wraz z poddomenami | domyślnie 14 dni; sesja wygasa też po 7 dniach bezczynności |
| \`nexus_demo\` | utrzymanie sesji pokazu bez konta | wyłącznie ścieżka \`/api/demo\` | 30 minut |

Domenę dwóch pierwszych ciasteczek ustawia serwer (\`NEXUS_COOKIE_DOMAIN\`). Gdy pole jest puste, ciasteczko obowiązuje wyłącznie w tej domenie, która je zapisała, bez poddomen.

Wszystkie trzy są **niezbędne do działania usługi**. Każde ma flagę \`HttpOnly\`, czyli nie jest czytelne dla skryptów na stronie, oraz \`SameSite=Lax\`, co blokuje wysyłkę przy żądaniach z obcych witryn. Flagę \`Secure\` włącza ustawienie serwera \`NEXUS_COOKIE_SECURE\`, domyślnie włączone; nie zależy ona od tego, czy dane połączenie jest szyfrowane.

Ciasteczko przechowuje wyłącznie losowy token. W bazie po stronie serwera leży jego skrót, nigdy sam token.`,
    },
    {
      id: "pamiec",
      tytul: "3. Pamięć przeglądarki",
      tresc: `| Wpis | Rodzaj pamięci | Co przechowuje |
|---|---|---|
| \`nexus-theme\` | lokalna | wybrany motyw: ciemny, jasny albo zgodny z systemem |
| \`nexus-voice\` | lokalna | wybrany głos czytania odpowiedzi |
| \`nexus.research.preferencje\` | lokalna | ostatnio wybrany rodzaj i głębokość badania w module badawczym |
| \`dn-ladowanie\` | sesji | wartość „1”: ekran ładowania pokazał się już w tej sesji przeglądarki |
| powłoka aplikacji | podręczna | pliki samej strony — skrypty, style, ikony i kroje pisma |
| \`nexus-share\` | podręczna | pliki i tekst, które wysyłasz do Nexusa przyciskiem „Udostępnij” w innej aplikacji — do chwili, aż okno Nexusa je odbierze |

Trzy pierwsze klucze leżą w pamięci lokalnej (\`localStorage\`) i zapamiętują Twoje ustawienia interfejsu. Wpis \`dn-ladowanie\` leży w pamięci sesji (\`sessionStorage\`) i znika po zamknięciu karty; ustawia go skrypt ekranu ładowania przy każdym wejściu na stronę.

Zainstalowana aplikacja trzyma w pamięci podręcznej pliki swojej powłoki, aby otwierała się szybko i działała przy słabym połączeniu. Tych plików nie ma sensu wiązać z Tobą — są takie same dla wszystkich.

Osobno działa zasobnik \`nexus-share\`. Powstaje wyłącznie wtedy, gdy sam wybierzesz Nexusa w systemowym menu „Udostępnij”: przekazane pliki i tekst muszą gdzieś poczekać, zanim okno aplikacji zdąży się otworzyć. Zapisuje je mechanizm aplikacji działający w tle w Twojej przeglądarce. Po otwarciu okna Nexus odczytuje zawartość, dołącza ją do nowej wiadomości i kasuje cały zasobnik. Do tej chwili pliki leżą wyłącznie na Twoim urządzeniu — na serwer trafiają dopiero wtedy, gdy wyślesz wiadomość.

Poza treścią, którą sam udostępniasz i wysyłasz, żaden z tych wpisów nie jest wysyłany na serwer i żaden nie służy rozpoznawaniu Cię między sesjami. Gdy przeglądarka blokuje taki zapis, aplikacja działa dalej, a wybór obowiązuje do zamknięcia karty.`,
    },
    {
      id: "zgoda",
      tytul: "4. Dlaczego nie ma okna zgody",
      tresc: `Zgody wymaga zapis informacji na urządzeniu, który nie jest konieczny do świadczenia usługi żądanej przez użytkownika. Zasadę tę wyraża art. 397 ustawy z 12 lipca 2024 r. — Prawo komunikacji elektronicznej.

Wszystkie trzy ciasteczka Nexusa służą utrzymaniu sesji, o którą prosi sam użytkownik: logując się albo uruchamiając pokaz. Bez nich logowanie nie działa. Nie zbieramy przy tym danych o zachowaniu na potrzeby analityki ani reklamy.

Przepis obejmuje każdy zapis informacji w Twoim urządzeniu, nie tylko pliki cookie. Dotyczy więc także wpisów z rozdziału 3. Trzy klucze pamięci lokalnej zapamiętują ustawienia, o które sam prosisz, wybierając motyw, głos albo tryb badania. Wpis \`dn-ladowanie\` służy wyświetleniu strony, o którą prosisz: pilnuje, by ekran ładowania pokazał się raz na sesję. Pamięć podręczna powłoki jest warunkiem działania aplikacji dodanej do ekranu. Zasobnik \`nexus-share\` powstaje wyłącznie w odpowiedzi na Twoje polecenie „Udostępnij” i znika, gdy aplikacja odbierze przekazaną treść. Żaden z nich nie zbiera danych o zachowaniu ani nie trafia na serwer bez Twojego polecenia.

Dlatego Nexus nie wyświetla okna zgody na pliki cookie. Gdyby w przyszłości pojawiło się narzędzie wymagające zgody, zapytamy o nią osobno, przed jego uruchomieniem.`,
    },
    {
      id: "zarzadzanie",
      tytul: "5. Zarządzanie plikami cookie",
      tresc: `Pliki cookie skasujesz i zablokujesz w ustawieniach przeglądarki — zwykle w sekcji „Prywatność i bezpieczeństwo”. Możesz też otworzyć Nexusa w oknie prywatnym; ciasteczka znikną wtedy po jego zamknięciu.

Zablokowanie ciasteczek Nexusa uniemożliwia zalogowanie się do aplikacji i do konta klienta oraz uruchomienie pokazu bez konta. Treści informacyjne portalu pozostaną dostępne.

Sesję kończysz też sam: wylogowaniem w aplikacji albo zakończeniem pokazu. Serwer kasuje wtedy ciasteczko i unieważnia sesję po swojej stronie.`,
    },
    {
      id: "powiadomienia",
      tytul: "6. Powiadomienia w przeglądarce",
      tresc: `Powiadomienia o zakończonym zadaniu działają na osobnej zgodzie, której udziela się w oknie przeglądarki. Nie korzystają z plików cookie.

Po włączeniu powiadomień Nexus zapisuje adres punktu odbioru wskazany przez przeglądarkę oraz klucze potrzebne do zaszyfrowania treści. Zgodę wycofasz w ustawieniach witryny w przeglądarce — wtedy doręczanie przestaje działać.`,
    },
    {
      id: "zmiany",
      tytul: "7. Zmiany tej informacji",
      tresc: `Wykaz aktualizujemy, gdy zmienia się zestaw ciasteczek albo wpisów pamięci przeglądarki zapisywanych przez produkt. Nową wersję publikujemy na tej stronie wraz z datą, od której obowiązuje.

Szerszy opis przetwarzania danych zawiera polityka prywatności.`,
    },
  ],
};
