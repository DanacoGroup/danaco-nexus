# Portal produktowy danaco-nexus.pl

Portal to publiczna, wielosekcyjna witryna produktowa z własnym zapleczem treści (CMS na bazie
aplikacji), kontami klientów i kanałami dla wyszukiwarek. Działa w tej samej aplikacji co Danaco
Nexus, ale jest od niej oddzielony: własne trasy, własna nawigacja, własna sesja klienta.

## Architektura

| Warstwa | Pliki | Zadanie |
|---|---|---|
| Model danych | `backend/nexus/models/portal.py` | Tabele treści, kont, sesji, tokenów i wiadomości |
| Logika treści | `backend/nexus/portal/tresc.py`, `repozytorium.py` | Adresy, zajawki, indeks wyszukiwania, zapis i odczyt |
| Konta klientów | `backend/nexus/portal/konta.py` | Rejestracja, sesje, profil, potwierdzenie adresu, odzyskiwanie hasła, usunięcie konta |
| Poczta | `backend/nexus/portal/poczta_portalu.py` | Interfejs nadawcy, dwie implementacje i treści wiadomości |
| Kanały SEO | `backend/nexus/portal/kanaly.py` | Atom 1.0, `sitemap.xml`, `robots.txt` |
| Konfiguracja | `backend/nexus/portal/ustawienia.py` | Zmienne `NEXUS_PORTAL_*` |
| API | `backend/nexus/api/modules/portal.py` | Routery: publiczny, kanały, administrator, konto |
| Interfejs | `frontend/src/portal/**` | Strony portalu, trasowanie, metadane, formularze |

Tabele są rejestrowane tak jak w pozostałych modułach: plik `nexus/models/portal.py` jest
importowany przez `nexus.models.extra_columns()`, więc `Database.create_schema()` tworzy je przy
starcie API i procesu roboczego. Jedyna zmiana w istniejącej tabeli to kolumna
`portal_users.email_confirmed_at` zgłoszona w `COLUMNS`; `create_schema()` dopisuje ją przy starcie,
więc migracja nie ma kroku ręcznego.

## Model danych

### `portal_content` — treść portalu

Jedna tabela obsługuje cztery rodzaje treści (`kind`): `blog`, `wiedza`, `dokumentacja`, `strona`.
Wszystkie mają ten sam zestaw pól, więc osobne tabele powielałyby zapytania listujące i wyszukiwanie.

| Kolumna | Typ | Opis |
|---|---|---|
| `id` | UUID | Klucz główny |
| `kind` | tekst(20) | Rodzaj treści |
| `slug` | tekst(120) | Adres pozycji, unikalny w obrębie rodzaju |
| `title` | tekst(200) | Tytuł |
| `excerpt` | tekst | Zajawka; pusta powstaje z początku treści |
| `body` | tekst | Treść w Markdown |
| `author` | tekst(120) | Autor |
| `tags` | JSON | Znaczniki (do 12, po 40 znaków) |
| `status` | tekst(20) | `szkic` albo `opublikowany` |
| `seo` | JSON | `meta_title`, `meta_description`, `og_image`, `canonical`, `noindex` |
| `position` | liczba | Kolejność w spisie dokumentacji |
| `search_text` | tekst | Tytuł, zajawka, znaczniki i treść bez znaków diakrytycznych |
| `created_at`, `updated_at`, `published_at` | znacznik czasu | Daty; `published_at` puste dla szkicu |

### Pozostałe tabele

- `portal_users` — konto klienta: adres e-mail (unikalny), skrót hasła Argon2, nazwa, firma, plan,
  znacznik aktywności, data potwierdzenia adresu (`email_confirmed_at`, pusta = niepotwierdzony),
  daty, ostatnie logowanie.
- `portal_sessions` — sesja klienta: skrót tokenu (klucz główny), konto, daty, adres IP, przeglądarka.
- `portal_password_resets` — token odzyskiwania hasła: skrót tokenu, konto, data wygaśnięcia, data użycia.
- `portal_email_confirmations` — token potwierdzenia adresu: te same pola co token odzyskiwania.
- `portal_messages` — wiadomość z formularza kontaktowego.

## Wyszukiwanie pełnotekstowe

Zapytanie jest dzielone na słowa (bez znaków diakrytycznych, małymi literami); wszystkie muszą
wystąpić w kolumnie `search_text`. Kolejność wyników ustala ocena liczona po stronie aplikacji:
trafienie w tytule waży 8, w zajawce i znacznikach 3, w treści 1. Rozwiązanie jest przenośne —
działa tak samo w PostgreSQL produkcji i w SQLite testów, bez rozszerzeń bazy. Przy bardzo dużej
liczbie pozycji warto przejść na `tsvector` z indeksem GIN; interfejs repozytorium tego nie zmienia.

## Trasy API

### Publiczne (bez logowania)

| Metoda | Adres | Opis |
|---|---|---|
| GET | `/api/portal/tresci?typ=&tag=&q=&strona=&na_stronie=` | Lista opublikowanych treści |
| GET | `/api/portal/tresci/{rodzaj}/{slug}` | Pozycja treści z metadanymi SEO i pozycjami powiązanymi |
| GET | `/api/portal/znaczniki?typ=` | Znaczniki z liczbą pozycji |
| GET | `/api/portal/szukaj?q=&typ=&limit=` | Wyszukiwanie pełnotekstowe |
| GET | `/api/portal/stan` | Czy rejestracja jest otwarta i czy trwa sesja administratora |
| POST | `/api/portal/kontakt` | Formularz kontaktowy (nagłówek `X-Nexus-Request`, limit tempa) |
| GET | `/portal/atom.xml`, `/portal/rss.xml` | Kanał Atom 1.0 z wpisami bloga |
| GET | `/sitemap.xml` | Mapa witryny |
| GET | `/robots.txt` | Reguły dla robotów |

### Konto klienta (`/api/portal/konto`)

| Metoda | Adres | Opis |
|---|---|---|
| POST | `/rejestracja` | Zakłada konto i loguje je od razu (limit tempa, można wyłączyć) |
| POST | `/logowanie` | Logowanie klienta (limit tempa nieudanych prób) |
| POST | `/wylogowanie` | Kończy bieżącą sesję i kasuje ciasteczko |
| GET | `/ja` | Profil zalogowanego klienta |
| PATCH | `/profil` | Zmiana nazwy i firmy |
| POST | `/haslo` | Zmiana hasła (wymaga obecnego, limit tempa, kończy wszystkie sesje) |
| POST | `/odzyskiwanie` | Prośba o jednorazowy odsyłacz; odpowiedź nie zdradza, czy konto istnieje |
| POST | `/odzyskiwanie/potwierdz` | Ustawienie hasła tokenem (limit tempa) |
| POST | `/potwierdzenie` | Potwierdzenie adresu tokenem z wiadomości; działa bez logowania (limit tempa) |
| POST | `/potwierdzenie/wyslij` | Nowy odsyłacz potwierdzający dla zalogowanego konta (limit tempa) |
| POST | `/usuniecie` | Nieodwracalne usunięcie konta (hasło i słowo `USUWAM`, limit tempa) |

Wszystkie punkty zmieniające stan wymagają nagłówka `X-Nexus-Request`. Usunięcie konta kasuje
rekord klienta razem z jego sesjami, tokenami odzyskiwania i tokenami potwierdzenia adresu, kasuje
ciasteczko sesji i zwalnia adres e-mail — tego samego adresu można użyć do założenia nowego konta.

### Administrator (`/api/portal/admin`, wymaga sesji administratora)

`GET /tresci`, `POST /tresci`, `GET /tresci/{id}`, `PATCH /tresci/{id}`,
`POST /tresci/{id}/publikacja`, `DELETE /tresci/{id}`, `GET /wiadomosci`, `GET /klienci`.

## Uwierzytelnianie

Portal ma dwa rozłączne poziomy dostępu:

1. **Administrator (redakcja treści)** — istniejąca sesja aplikacji: ciasteczko `nexus_session`,
   zależność `nexus.api.auth.require_session`, nagłówek `X-Nexus-Request` przy zmianach stanu.
   Portal nie zmienia ani nie osłabia tego mechanizmu; panel administratora w interfejsie odsyła
   do zwykłego logowania aplikacji (`/zaloguj?next=/portal/admin`).
2. **Klient portalu** — osobne konto i osobne ciasteczko `nexus_portal`, zbudowane na tych samych
   podstawach: hasła haszuje Argon2 (`auth.hasher`), w bazie leży wyłącznie skrót tokenu SHA-256
   (`auth.token_hash`), ciasteczko jest `HttpOnly`, `SameSite=Lax` i `Secure` zgodnie z ustawieniem
   aplikacji, a żądania zmieniające stan wymagają nagłówka `X-Nexus-Request`.

Sesja administratora nie daje dostępu do panelu klienta ani odwrotnie.

Ograniczenie tempa (licznik `auth.LoginThrottle`, okno 15 minut, osobny dla każdej operacji i adresu
IP) obejmuje logowanie klienta, rejestrację, zmianę hasła, odzyskiwanie hasła, potwierdzenie
odzyskiwania, usunięcie konta i formularz kontaktowy. Zmiana hasła — także przez token odzyskiwania
— kończy wszystkie sesje konta i unieważnia pozostałe tokeny.

Licznik żyje w pamięci jednego procesu roboczego API (`nexus.api.auth.LoginThrottle` trzyma zwykły
słownik w instancji, a instancje siedzą w `app.state.portal_throttles`). Wynikają z tego trzy
następstwa, o których wdrażający musi wiedzieć: przy `N` procesach roboczych rzeczywisty limit jest
`N` razy wyższy od wartości ze zmiennej, restart procesu zeruje zliczenia, a zmiana zmiennej
`NEXUS_PORTAL_*_PROBY_15MIN` zakłada nowy licznik (dotychczasowe zliczenia przepadają, ale limit
obowiązuje od następnego żądania — bez restartu).

Zmiana hasła kasuje też ciasteczko `nexus_portal` w odpowiedzi, więc przeglądarka nie nosi
unieważnionego tokenu do końca jego ważności. Nowe hasło musi się różnić od obecnego — sprawdza to
`konta.sprawdz_nowe_haslo` po stronie serwera, nie tylko formularz.

### Adres klienta w liczniku prób

We wdrożeniu adres klienta wyznacza **uvicorn**, zanim żądanie dojdzie do aplikacji. Usługa startuje
z `--proxy-headers --forwarded-allow-ips 127.0.0.1`
(`deploy/systemd/danaco-nexus-api.service`), więc `ProxyHeadersMiddleware` przyjmuje
`X-Forwarded-For` tylko od Caddy z pętli zwrotnej, bierze z listy ostatni wpis spoza zaufanych
adresów i **podmienia nim `request.client`**. Do licznika trafia zatem adres wyliczony przez
uvicorn, a nie odczytany z nagłówka przez kod portalu.

Klucz licznika ustala `konta.adres_klienta` (`backend/nexus/portal/konta.py`), nie `auth.client_ip`.
Funkcja jest drugą linią obrony — liczy się, gdy API uruchomiono bez powyższych przełączników:

- jeżeli adres gniazda nie należy do `SIECI_PROXY` (`127.0.0.0/8`, `::1/128`), nagłówek jest
  pomijany i liczy się sam adres gniazda; tak wygląda każde żądanie w bieżącym wdrożeniu, bo
  uvicorn wstawił tam już adres klienta;
- jeżeli adres gniazda jest z pętli zwrotnej, brany jest **ostatni** wpis nagłówka — ten dopisuje
  proxy z adresu, który samo zobaczyło; wpisy wcześniejsze przysyła klient i nie wolno im wierzyć.

Zakres zaufania obejmuje wyłącznie pętlę zwrotną, bo odwrotne proxy stoi na tej samej maszynie.
Szersze zakresy prywatne (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`) obejmowałyby
hosty, które pośrednikiem nie są, a każdy taki host mógłby podstawić do licznika dowolny adres.
Proxy w innym miejscu sieci wymaga zmiany `SIECI_PROXY` razem z `--forwarded-allow-ips`.

`auth.client_ip` bierze **pierwszy** wpis nagłówka i robi to niezależnie od tego, co ustalił
uvicorn, więc jednym nagłówkiem da się rozsypać licznik nieudanych logowań administratora na
dowolnie wiele kluczy. Dziś `client_ip` jest już odporny na podszycie (ufa nagłówkowi tylko od
własnego proxy i bierze ostatni wpis), więc `/api/auth/login` liczy próby po prawdziwym adresie.

Warunek wdrożeniowy: API stoi za Caddy na `127.0.0.1:8930` i nie jest wystawione na świat innym
portem. Jeżeli przed Caddy stanie kolejne proxy (CDN), ostatni wpis nagłówka przestanie być adresem
klienta — wtedy proxy brzegowe musi nadpisywać `X-Forwarded-For`, a nie dopisywać do niego.

### Wygaszanie sesji

Sesja klienta gaśnie z dwóch niezależnych powodów; rozstrzyga ten, który wypada wcześniej:

1. **Czas życia** — `NEXUS_PORTAL_SESSION_DAYS` od zalogowania (kolumna `expires_at`, zarazem czas
   życia ciasteczka).
2. **Bezczynność** — `konta.BEZCZYNNOSC` (7 dni) od ostatniego żądania (kolumna `last_seen_at`,
   odświeżana nie częściej niż co pięć minut, żeby nie zapisywać przy każdym żądaniu).

Wygasłe i bezczynne sesje są usuwane z bazy przy najbliższym logowaniu (`konta.usun_wygasle`).

### Odzyskiwanie hasła

Prośba o odzyskanie zawsze kończy się odpowiedzią `{"ok": true}` — niezależnie od tego, czy adres
jest zarejestrowany, czy konto jest aktywne. Komunikat w interfejsie jest jeden („jeżeli konto
istnieje, wysłaliśmy odsyłacz”), a każda prośba liczy się do limitu tempa, więc odpowiedzi nie da
się użyć do sprawdzania, kto ma konto. Token jest losowy (32 bajty), w bazie leży wyłącznie jego
skrót SHA-256, działa raz (kolumna `used_at`) i wygasa po `NEXUS_PORTAL_RESET_TTL_MINUTES`.
Wydanie nowego tokenu unieważnia wcześniejsze tokeny tego konta.

### Potwierdzenie adresu poczty

Rejestracja zakłada konto, loguje je od razu i wydaje jednorazowy token potwierdzenia adresu
(`konta.token_potwierdzenia`, ważność `konta.POTWIERDZENIE_WAZNE` = 24 godziny, w bazie wyłącznie
skrót SHA-256). Odsyłacz prowadzi na `{base_url}/portal/konto?potwierdzenie={token}`.

Potwierdzenie **niczego nie blokuje**: konto działa od pierwszej sekundy, także wtedy, gdy wysyłka
nie jest skonfigurowana i wiadomość trafiła wyłącznie do dziennika. Brak potwierdzenia jest stanem
widocznym, nie karą — profil zwraca `email_confirmed`, a strona konta pokazuje kartę „Adres e-mail
bez potwierdzenia” z przyciskiem „Wyślij odsyłacz ponownie”. Wybrano to zamiast warunku
„potwierdzenie tylko przy nadawcy SMTP”, bo instalacja bez poczty nie wysyła też odsyłaczy do
zmiany hasła, a klient i tak musi wiedzieć, że jego adres jest niesprawdzony.

`POST /api/portal/konto/potwierdzenie` przyjmuje token bez logowania (klient klika w wiadomości,
niekoniecznie w tej samej przeglądarce). Token działa raz; zużyty albo przeterminowany daje `422`
z komunikatem „Odsyłacz wygasł albo został już użyty”. `POST /api/portal/konto/potwierdzenie/wyslij`
wymaga sesji klienta, unieważnia poprzedni token konta i ma ograniczone tempo
(`NEXUS_PORTAL_RESET_PROBY_15MIN`) — każda prośba liczy się do limitu, więc jednym kontem nie da
się zasypać skrzynki. Adres już potwierdzony daje `{"ok": true}` bez nowej wiadomości.

## Wysyłka poczty

`nexus.portal.poczta_portalu` definiuje interfejs `NadawcaPoczty` i dwie implementacje:

- `NadawcaDoDziennika` (domyślna) — zapisuje treść wiadomości w dzienniku aplikacji
  (`nexus.portal.poczta` na poziomie INFO). Token odzyskiwania trafia do dziennika, nie do skrzynki.
- `NadawcaSmtp` — wysyła przez konto SMTP aplikacji (`nexus.mail`, plik `NEXUS_POCZTA_CONFIG_FILE`).

Funkcja `poczta_portalu.wyslij` jest jedynym wejściem używanym przez API: przy błędzie wysyłki
zapisuje treść w dzienniku, więc żadna wiadomość nie ginie po cichu. Wysyłka jest synchroniczna
(`smtplib`, limit `NEXUS_POCZTA_TIMEOUT_S`), dlatego punkty API wołają ją przez `asyncio.to_thread` —
niedostępny serwer poczty spowalnia jedno żądanie, nie zatrzymuje pętli zdarzeń całego procesu. Portal wysyła cztery wiadomości:
odsyłacz potwierdzający adres po rejestracji (`tresc_potwierdzenia_adresu`), odsyłacz do ustawienia
nowego hasła (`tresc_odzyskiwania`), powiadomienie o zmianie hasła (`tresc_zmiany_hasla` — także po
odzyskaniu, żeby klient zauważył zmianę, której nie zlecił) oraz potwierdzenie usunięcia konta
(`tresc_usuniecia_konta`).

**Do podłączenia przed uruchomieniem produkcyjnym:** ustaw `NEXUS_PORTAL_MAIL_NADAWCA=smtp`,
skonfiguruj konto pocztowe skryptem `deploy/zapisz-poczte.sh` i podaj adres nadawcy w
`NEXUS_PORTAL_MAIL_FROM` (pusty = adres konta domyślnego). Bez tego rejestracja, potwierdzenie
adresu i odzyskiwanie hasła działają, ale użytkownik nie otrzyma odsyłacza — jeżeli konto SMTP jest
niedostępne, wysyłka wraca do dziennika, a w dzienniku pojawia się ostrzeżenie.

## Strony interfejsu

Wszystkie ścieżki mają prefiks `/portal`. Wybór jest świadomy: aplikacja użytkownika zajmuje `/`,
`/c/<rozmowa>`, `/m/<moduł>`, `/zaloguj` i `/start`, a strony publikowane przez Twórcę stron `/s/…`.
Prefiks gwarantuje, że żaden adres portalu nie przesłoni adresu aplikacji, a `robots.txt` może
otworzyć część produktową i zamknąć aplikację jedną regułą.

| Ścieżka | Strona |
|---|---|
| `/portal` | Strona główna portalu |
| `/portal/oferta` | Oferta |
| `/portal/funkcje` | Funkcje |
| `/portal/cennik` | Cennik i najczęstsze pytania |
| `/portal/dokumentacja`, `/portal/dokumentacja/<slug>` | Dokumentacja ze spisem treści |
| `/portal/blog`, `/portal/blog/<slug>` | Blog: lista i wpis |
| `/portal/wiedza`, `/portal/wiedza/<slug>` | Centrum wiedzy |
| `/portal/s/<slug>` | Strona statyczna z bazy treści |
| `/portal/szukaj?q=` | Wyszukiwanie |
| `/portal/konto` | Konto: logowanie, rejestracja, odzyskiwanie i zmiana hasła, profil, wylogowanie, usunięcie konta |
| `/portal/panel` | Panel klienta (subskrypcja, dane konta) |
| `/portal/admin` | Panel administratora (redagowanie treści) |

Trasowanie portalu jest wewnętrzne (`frontend/src/portal/trasy.ts`). W trasowaniu aplikacji
(`frontend/src/shell/route.ts`) dopisana jest jedna trasa `portal`, a `frontend/src/App.tsx` podpina
ekran przez `React.lazy`. Każda strona portalu jest osobnym pakietem ładowanym na żądanie.

## Pozycjonowanie i wydajność

- `frontend/src/portal/seo.ts` ustawia na każdej stronie tytuł, opis, Open Graph, adres kanoniczny,
  `robots: noindex` tam, gdzie treść nie należy do indeksu (konto, panele, wyszukiwarka) oraz dane
  strukturalne schema.org: `Organization` i `WebSite` na stronie głównej, `BlogPosting`, `Article`
  i `TechArticle` w pozycjach treści, `BreadcrumbList` w ścieżce nawigacji, `FAQPage` w cenniku.
- Redaktor może nadpisać tytuł, opis, obraz i adres kanoniczny w metadanych SEO pozycji. Adresy są
  sprawdzane: dozwolona jest ścieżka tej witryny albo pełny adres `http(s)`.
- Strony ładują się przez `React.lazy`. Listy i artykuły mają zastępniki o wysokości docelowej
  treści, więc pobranie danych nie przesuwa układu.
- Kanały i mapa witryny są serwowane z nagłówkiem `Cache-Control: public, max-age=300`.

## Dostępność (WCAG 2.2 AA)

- Odsyłacz „Przejdź do treści” na początku strony, jeden nagłówek `h1` na stronę, nagłówki sekcji
  w kolejności, obszary `header`, `nav`, `main`, `footer` z etykietami.
- Po zmianie trasy uwaga przenosi się na nagłówek strony, a widok wraca na górę.
- Każde pole formularza ma etykietę `label` powiązaną identyfikatorem, komunikat błędu wskazany
  przez `aria-describedby` i `aria-invalid`; komunikaty błędów mają rolę `alert`, potwierdzenia `status`.
- Bieżąca pozycja nawigacji i okruszków jest oznaczona `aria-current`, przyciski filtrów mają
  `aria-pressed`, menu na telefonie `aria-expanded` i `aria-controls`.
- Barwy pochodzą wyłącznie z ról semantycznych arkusza aplikacji (`frontend/src/styles.css`),
  które spełniają progi kontrastu w obu motywach. Widoczny pierścień fokusu na wszystkich kontrolkach.

## Konfiguracja wdrożenia

Zmienne środowiskowe (sekcja „moduł portal” w `.env.example`):

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `NEXUS_PORTAL_PUBLIC_URL` | `NEXUS_PUBLIC_URL` albo `https://danaco-nexus.pl` | Adres bazowy w mapie witryny, kanale Atom i wiadomościach |
| `NEXUS_PORTAL_MAIL_NADAWCA` | `dziennik` | `dziennik` albo `smtp` |
| `NEXUS_PORTAL_MAIL_FROM` | pusty | Adres nadawcy; pusty = adres konta domyślnego |
| `NEXUS_PORTAL_RESET_TTL_MINUTES` | `30` | Czas życia tokenu odzyskiwania (5–240) |
| `NEXUS_PORTAL_SESSION_DAYS` | `14` | Czas życia sesji klienta (1–90) |
| `NEXUS_PORTAL_REJESTRACJA` | `wlaczona` | `wlaczona` albo `wylaczona` |
| `NEXUS_PORTAL_LOGIN_PROBY_15MIN` | `8` | Limit nieudanych logowań i rejestracji z jednego IP |
| `NEXUS_PORTAL_RESET_PROBY_15MIN` | `5` | Limit prób odzyskiwania hasła i potwierdzania adresu z jednego IP |
| `NEXUS_PORTAL_KONTAKT_PROBY_15MIN` | `5` | Limit zgłoszeń z formularza kontaktowego z jednego IP |

Kroki wdrożeniowe:

1. Ustaw `NEXUS_PORTAL_PUBLIC_URL` na rzeczywisty adres witryny — bez niego mapa witryny i kanał
   Atom wskazują adres domyślny.
2. Podłącz wysyłkę poczty (sekcja „Wysyłka poczty”).
3. Zaloguj się kontem administratora aplikacji i wejdź na `/portal/admin`. Załóż strony
   dokumentacji (`position` ustala kolejność w spisie) i pierwsze wpisy bloga, a następnie je opublikuj.
4. Zgłoś `https://<adres>/sitemap.xml` w narzędziach dla webmasterów. Mapa obejmuje strony stałe
   i opublikowane treści bez znacznika `noindex`.
5. Jeżeli portal ma być zamknięty dla nowych klientów, ustaw `NEXUS_PORTAL_REJESTRACJA=wylaczona`.

## Testy

- `backend/tests/test_portal.py` — przetwarzanie treści, ochrona punktów edycyjnych (sesja i CSRF),
  publikacja, unikalność adresów, wyszukiwanie, kanały SEO, konta, odzyskiwanie hasła, limity tempa,
  wygaszanie sesji po bezczynności, treść komunikatów błędów, usunięcie konta, kasowanie ciasteczka
  po zmianie hasła, odrzucenie hasła powtarzającego obecne, potwierdzenie adresu poczty (odsyłacz po
  rejestracji, token jednorazowy, token przeterminowany, konto działające bez skonfigurowanej
  wysyłki, limit ponownej wysyłki), pominięcie nagłówka przekierowania w żądaniu z sieci prywatnej,
  wysyłka poczty poza pętlą zdarzeń oraz awaryjny zapis wiadomości w dzienniku.
- `frontend/src/portal/portal.test.tsx` — trasowanie portalu i aplikacji, metadane head, dane
  strukturalne, dostępność pól formularza i okruszków.
- `frontend/src/portal/strony/konto.test.tsx` — ścieżki strony konta: walidacja hasła przed
  wysłaniem, ustawienie hasła z odsyłacza, zmiana hasła (także komunikat serwera przy złym haśle),
  dwustopniowe usunięcie konta ze słowem potwierdzenia, wylogowanie, stan po zakończeniu sesji,
  zdjęcie zużytego tokenu z adresu po zmianie hasła i po usunięciu konta oraz potwierdzenie adresu
  e-mail. Plik leży obok `Konto.tsx`, który sprawdza.

## Strona konta

`frontend/src/portal/strony/Konto.tsx` obsługuje cztery stany: gościa (logowanie, rejestracja,
odzyskiwanie hasła w jednej karcie), ustawienie hasła z tokenu (`/portal/konto?token=…`),
potwierdzenie adresu z tokenu (`/portal/konto?potwierdzenie=…`) i konto zalogowane (dane konta,
zmiana hasła, wylogowanie, usunięcie konta).

Potwierdzenie adresu ma pierwszeństwo przed pozostałymi stanami i nie wymaga niczego od klienta:
token idzie na serwer od razu po otwarciu odsyłacza, a klient widzi wynik i przycisk „Przejdź do
konta”, który wraca na `/portal/konto` bez parametru. Zalogowane konto z niepotwierdzonym adresem
dostaje nad kartami pasek „Adres e-mail bez potwierdzenia” z przyciskiem „Wyślij odsyłacz ponownie”;
pasek nie blokuje żadnej kontrolki, bo konto działa niezależnie od potwierdzenia.

Po zmianie hasła i po usunięciu konta serwer kończy wszystkie sesje, więc widok nie odświeża profilu
w tle — zastępuje karty konta jednym potwierdzeniem i przyciskiem następnego kroku („Zaloguj się
ponownie”, „Wróć na stronę konta”). Inaczej komunikat zniknąłby razem z odmontowanym widokiem, a obok
zostałyby czynne przyciski konta, które już nie działa. Usunięcie konta jest dwustopniowe: przycisk
odsłania formularz, a formularz wymaga hasła i wpisania słowa `USUWAM` (to samo słowo sprawdza serwer).

Odsyłacz odzyskiwania otwarty w przeglądarce z trwającą sesją nie znika bez śladu: strona pokazuje
komunikat, że hasło zmienia się w karcie „Zmiana hasła”, a token zostaje ważny do czasu użycia albo
wygaśnięcia. Komunikat stoi wewnątrz widoku konta, więc znika razem z kartami, gdy sesja się kończy —
nie zostaje obok potwierdzenia zmiany hasła ze sprzeczną instrukcją.

Przycisk następnego kroku wraca na `/portal/konto` **bez** parametru `token`. Zmiana hasła kasuje
wszystkie tokeny odzyskiwania konta, więc token z adresu jest już martwy; gdyby został, strona
otworzyłaby formularz „Ustaw nowe hasło”, a zapis skończyłby się komunikatem „Odsyłacz wygasł albo
został już użyty”.

## Adres klienta w licznikach tempa — zrobione

Rozdział opisywał wcześniej patch do wykonania w `backend/nexus/api/auth.py`, bo `client_ip`
czytał `X-Forwarded-For` samodzielnie i brał **pierwszy** wpis. Zmiana jest wykonana, i to
szerzej niż w szkicu: nagłówek liczy się wyłącznie w żądaniu z pętli zwrotnej (czyli od
własnego proxy), a brany jest jego **ostatni** wpis — ten dopisuje Caddy z adresu, który sam
zobaczył. Wpisy wcześniejsze przysyła klient, więc nie mają wpływu na klucz licznika.

Kod: `auth.py` — `SIECI_PROXY`, `_proxy_zaufane`, `client_ip`. Dotyczy to wszystkich liczników
opartych o adres: logowania administratora, limitu kont próbnych i tempa piaskownicy.

Testy: `backend/tests/test_bezpieczenstwo.py` —
`test_naglowek_przekazania_nie_omija_licznika_logowan` i bliźniaczy test dla kont próbnych;
oba przechodzą. Warunek wdrożeniowy bez zmian: usługa startuje z
`--proxy-headers --forwarded-allow-ips 127.0.0.1`, a API nie jest wystawione innym portem.

## Sprawy otwarte

- Ograniczenie tempa jest lokalne dla procesu roboczego (pamięć instancji `LoginThrottle`). Przy
  wielu procesach limit mnoży się przez ich liczbę, a restart zeruje liczniki. Wspólny licznik
  wymaga magazynu poza procesem (Redis jest już w zależnościach aplikacji) i należy do dziedziny
  bezpieczeństwa powierzchni publicznej.
- ~~Logowanie administratora da się obejść nagłówkiem `X-Forwarded-For`~~ — zrobione:
  `client_ip` ufa nagłówkowi tylko od własnego proxy i bierze ostatni wpis (rozdział „Adres
  klienta w licznikach tempa”). Pilnuje tego test w `test_bezpieczenstwo.py`.
- Rejestracja odpowiada `422` z informacją, że adres jest zajęty — to celowy kompromis na rzecz
  czytelności (odzyskiwanie hasła, które jest ścieżką atakującego, adresu nie zdradza).
- Strona konta czyta parametr `potwierdzenie` wprost z adresu (`window.location.search`), bo
  `frontend/src/portal/trasy.ts` należy do dziedziny nawigacji i przekazuje stronie jeden parametr.
  Gdy ten plik będzie zmieniany, parametr wypada przenieść do `parsujTrase`.
- Wyszukiwanie działa na `LIKE` **od początku wyrazu** (od 21.09.2026 — wcześniej trafiało
  w środek, więc „or” pasowało do „który”). Dopasowanie jest po rdzeniu, nie po formie:
  „moduły” nie znajdzie tekstu, w którym stoi tylko „modułów”. Przy większej bibliotece
  treści warto dodać indeks pełnotekstowy PostgreSQL.
- **Poczta portalu nie dochodzi do klienta.** `NEXUS_PORTAL_MAIL_NADAWCA` nie jest ustawione,
  więc obowiązuje nadawca „dziennik”: potwierdzenie adresu i odsyłacz do nowego hasła są
  tylko zapisywane w dzienniku aplikacji. Konto działa bez potwierdzenia (logowanie sprawdza
  wyłącznie hasło), więc boli to w jednym miejscu — **odzyskaniu hasła**. Włączenie wysyłki:
  `deploy/zapisz-poczte.sh` (poświadczenia skrzynki), potem `NEXUS_PORTAL_MAIL_NADAWCA=smtp`.
  Stan sprawdza kontrola „poczta portalu” w `deploy/nexus-cli.sh doctor`.
- Plan subskrypcji (`portal_users.plan`) jest opisowy — nie ma rozliczeń ani zmiany planu z panelu.
- Wiadomości z formularza kontaktowego są tylko odczytywane w panelu; nie ma oznaczania jako
  załatwione ani powiadomienia pocztą.

## Pierwsze materiały

Blog, centrum wiedzy i dokumentacja są puste — sekcje zachowują się poprawnie, ale spis nie
ma ani jednej pozycji. W `docs/portal/tresci-startowe/` leży pięć gotowych materiałów
dokumentacji wraz z opisem publikacji. Treść mieszka w bazie (adres, zajawkę i indeks
wyszukiwania tworzy dopiero zapis), a pliki są jej wersją źródłową — wczytuje je polecenie:

```
deploy/nexus-cli.sh materialy-portalu --katalog docs/portal/tresci-startowe
```

Domyślnie powstają szkice; publikacja zostaje osobną decyzją (`--opublikuj` albo panel
administratora). Powtórne wczytanie nadpisuje pozycję o tym samym adresie, więc poprawiony
plik wystarczy podać ponownie.
