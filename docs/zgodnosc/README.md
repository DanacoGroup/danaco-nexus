# Danaco Nexus — Zgodność prawna i ochrona danych

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Rodzaj** | Personal AI Workspace |
| **Producent** | Danaco Holding Group Sp. z o.o. |
| **Twórca** | Dariusz Naharnowicz |
| **Wersja** | etap 1B |
| **Status** | Deweloperski |
| **Data** | 2026-09-21 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Zgodność prawna produktu — dokumenty publikowane i dokumentacja wewnętrzna |
| **Klasa dokumentu** | Opis stanu wykonania |
| **Odbiorcy** | właściciel produktu · radca prawny · deweloper warstwy klienckiej · weryfikator |
| **Przeznaczenie** | Wskazuje, gdzie leżą dokumenty prawne produktu, skąd pochodzi ich treść i co trzeba zrobić, żeby odsyłacze ze stopki prowadziły do istniejących stron. |
| **Zakres** | Polityka prywatności, regulamin, informacja o plikach cookie, rejestr czynności przetwarzania, mapa danych w kodzie |
| **Poza zakresem** | Bezpieczeństwo powierzchni publicznej — para P10; nawigacja i stopka — para P7; mapa witryny — para P6 |
| **Źródła normatywne** | `frontend/src/portal/tresc-prawna.ts` · `backend/nexus/models/**` · `backend/nexus/portal/**` · `backend/nexus/platnosci/**` |
| **Zasada nadrzędna** | Dokument prawny opisuje stan faktyczny produktu. Każda wymieniona kategoria danych ma odpowiednik w kodzie; kategoria bez pokrycia w kodzie jest usterką dokumentu, nie kodu. |

## Spis treści

1. [Co powstało](#1-co-powstało)
2. [Skąd pochodzi treść dokumentów](#2-skąd-pochodzi-treść-dokumentów)
3. [Trasowanie](#3-trasowanie)
4. [Utrzymanie: kiedy dokument trzeba zmienić](#4-utrzymanie-kiedy-dokument-trzeba-zmienić)
5. [Sprawy do rozstrzygnięcia przez właściciela produktu](#5-sprawy-do-rozstrzygnięcia-przez-właściciela-produktu)
6. [Gotowe brzmienie brakujących akapitów polityki](#6-gotowe-brzmienie-brakujących-akapitów-polityki-do-zatwierdzenia)

---

## 1. Co powstało

| Dokument | Miejsce | Adres publiczny |
|---|---|---|
| Polityka prywatności | `frontend/src/portal/strony/Prywatnosc.tsx` | `/portal/prywatnosc` |
| Regulamin | `frontend/src/portal/strony/Regulamin.tsx` | `/portal/regulamin` |
| Informacja o plikach cookie | `frontend/src/portal/strony/Cookies.tsx` | `/portal/cookies` |
| Treść wszystkich trzech dokumentów | `frontend/src/portal/tresc-prawna.ts` | — |
| Rejestr czynności przetwarzania | [REJESTR-CZYNNOSCI.md](REJESTR-CZYNNOSCI.md) | — |
| Mapa danych w kodzie | [DANE-W-KODZIE.md](DANE-W-KODZIE.md) | — |

Treść jest oddzielona od układu tak samo jak w `frontend/src/portal/tresc.ts`: strona
renderuje dane, redakcja zmienia wyłącznie `tresc-prawna.ts`. Każdy rozdział jest osobną
sekcją z własną kotwicą, więc do pojedynczego postanowienia da się odesłać adresem.

Wartości wizualne pochodzą z ról semantycznych (`bg-raised`, `border-line`, `text-muted`,
`text-accent`, `font-heading`); treść rozdziałów renderuje komponent `Markdown`, którego
typografia jest w całości opisana tokenami w `frontend/src/styles.css`.

## 2. Skąd pochodzi treść dokumentów

Dokumenty nie są wzorcem z sieci. Każde twierdzenie ma źródło w kodzie — pełne
zestawienie podaje [mapa danych w kodzie](DANE-W-KODZIE.md). Najważniejsze zależności:

| Twierdzenie w dokumencie | Źródło |
|---|---|
| Trzy ciasteczka: `nexus_session`, `nexus_portal`, `nexus_demo` | `backend/nexus/api/auth.py`, `backend/nexus/portal/konta.py`, `backend/nexus/demo/sesje.py` |
| Flagi `HttpOnly`, `SameSite=Lax`; `Secure` z ustawienia, nie z rodzaju połączenia | te same pliki, wywołania `set_cookie`; `settings.cookie_secure` — `backend/nexus/config.py:64` |
| Zasięg `nexus_session` i `nexus_portal` obejmuje poddomeny | `domain=settings.cookie_domain or None` — `backend/nexus/api/auth.py:244`, `backend/nexus/portal/konta.py:189`; `NEXUS_COOKIE_DOMAIN` — `.env.example:60` |
| Sesja portalu: 14 dni, wygaszanie po 7 dniach bezczynności | `backend/nexus/portal/ustawienia.py`, `konta.py` (`BEZCZYNNOSC`) |
| Sesja aplikacji: 30 dni | `backend/nexus/config.py` (`session_days`) |
| Token odzyskiwania hasła: 30 minut | `backend/nexus/portal/ustawienia.py` (`reset_ttl_minutes`) |
| Hasło konta wyłącznie jako skrót Argon2, minimum 12 znaków | `backend/nexus/portal/konta.py` (`MIN_HASLO`, `auth.hasher.hash`), `backend/nexus/api/auth.py:49-52` |
| Hasło podłączonej skrzynki i hasło do chmury przechowywane czytelnie, bo serwer loguje się nimi w imieniu użytkownika | `backend/nexus/mail.py` (`config_path`, `save_accounts`), `settings.chmura_token_file` |
| Każde konto ma własną przestrzeń; na pliki przypada 2 GB | `owner_id` w `backend/nexus/db.py:45-52` i `models/research.py:28`, `auth.wlasciciel`, `mail.config_path`; limit `config.py:86-87` i `api/files.py:73-79` |
| Kredyty konta i księga ich zmian | `backend/nexus/platnosci/kredyty.py`, `docs/platnosci/KREDYTY.md`, `GET /api/platnosci/kredyty` |
| Usunięcie konta wymaga hasła i słowa potwierdzenia, jest nieodwracalne | `backend/nexus/api/modules/portal.py`, `konta.py` (`usun_konto`) |
| Limity pokazu bez konta: 6 wiadomości, 4 pliki po 8 MB, 500 znaków, 30 minut | `backend/nexus/demo/sesje.py` (`Limity`) |
| Trzy klucze pamięci lokalnej i wpis pamięci sesji `dn-ladowanie` | `frontend/src/theme.ts`, `frontend/src/voice/VoiceMode.tsx`, `frontend/src/modules/research/index.tsx`, `frontend/public/ladowanie/ladowanie.js:32-33` |
| Zasobnik `nexus-share` z plikami przekazanymi przez „Udostępnij” | `frontend/public/share-target.js:14-31`, `frontend/src/share.ts:14-28` |
| Brak analityki i ciasteczek podmiotów trzecich | brak skryptów zewnętrznych w `frontend/index.html` |
| Co trafia do modelu Claude, model domyślny i zapasowy | `backend/nexus/agent/runner.py`, `backend/nexus/agent/prompt.py`, `backend/nexus/config.py` |
| Wyszukiwanie i odczyt stron po stronie Anthropic | `backend/nexus/agent/runner.py` (`WEB_TOOLS`) |
| Rozmowa głosowa przez Google Cloud: nagranie i tekst czytany na głos, model lokalny jako zapas | `backend/nexus/voice.py:97-99` i `:179-181`, `backend/nexus/voice_google.py`, `settings.voice_google_key_file` |
| Serwer poczty jako odbiorca: wiadomości portalu i wysyłka zlecona agentowi | `backend/nexus/portal/poczta_portalu.py` (`NadawcaSmtp`), `backend/nexus/mail.py` |
| Poczta, kalendarz i chmura osobista jako kategorie danych | `backend/nexus/mail.py`, `backend/nexus/calendar.py`, `backend/nexus/cloud_service.py`, `backend/nexus/config.py:49-52` |
| Strony użytkownika pod `/s/<adres>` mogą wczytywać skrypty zewnętrzne | `backend/nexus/api/modules/strony.py:35-44` (`SITE_CSP`) |
| Plany Osobisty, Pro, Grupa — wszystkie płatne; Osobisty z 7-dniowym okresem próbnym | `backend/nexus/platnosci/plany.py` (`KATALOG`, `okres_probny_dni`), `backend/nexus/platnosci/uslugi.py` |
| Pakiety kredytów do dokupienia poza subskrypcją | `backend/nexus/platnosci/pakiety.py`, `POST /api/platnosci/pakiety/checkout` |
| Płatności i faktury przez Stripe, bez przyjmowania danych kart | `backend/nexus/platnosci/klient.py`, `docs/platnosci/README.md` |
| Działania poza Nexusem dopiero po zatwierdzeniu | `backend/nexus/models/biuro.py` (`PendingAction`), `desktop/src/agent/powershellPolicy.js` |

## 3. Trasowanie

Trzy strony prawne są osiągalne: mają wartości w typie `PortalStrona` i wpisy w mapie
`PROSTE` (`frontend/src/portal/trasy.ts:23-25`, `:57-59`) oraz gałęzie w `Zawartosc`
(`frontend/src/portal/Portal.tsx:343-348`). Odsyłacze prowadzą do nich ze stopki portalu
(`Portal.tsx:79-81`). Sprawdza to `frontend/src/__tests__/tresc-produktu.test.tsx` — przypadek „prowadzi do polityki prywatności, regulaminu i plików cookie”. (Do 21.09.2026 stała tu nazwa `frontend/src/portal/weryfikacja-p7.test.tsx`, czyli pliku, którego w repozytorium nie ma.)

Do mapy witryny trafiają przez `STRONY_STALE` (`backend/nexus/portal/kanaly.py:32-34`,
para P6). Trasowanie jest zamknięte — nie zostaje tu nic do zrobienia.

## 4. Utrzymanie: kiedy dokument trzeba zmienić

Zmiana w kodzie wymaga zmiany dokumentu w następujących przypadkach:

| Zmiana w kodzie | Co poprawić |
|---|---|
| Nowa tabela w `backend/nexus/models/**` albo nowa kolumna z danymi osobowymi | rozdz. 3 polityki, rejestr czynności, mapa danych |
| Nowe ciasteczko albo zmiana czasu życia sesji | rozdz. 2 informacji o cookie, rozdz. 8 polityki |
| Nowy klucz w `localStorage`, `sessionStorage` albo nowy zasobnik `Cache Storage` | rozdz. 3 informacji o cookie |
| Zmiana cennika kredytów, przydziału w planie albo katalogu pakietów | rozdz. 3, 4 i 8 polityki, rozdz. 5 regulaminu, CZ-13 rejestru, rozdz. 6 mapy danych |
| Nowa tabela z `owner_id` albo zmiana zakresu rozdzielenia kont | rozdz. 2 polityki, CZ-5 i rozdz. 5 rejestru |
| Nowy dostawca zewnętrzny (analityka, wysyłka, magazyn) | rozdz. 6 i 7 polityki, rejestr czynności; analityka wymaga też okna zgody |
| Zmiana zakresu danych przekazywanych do Claude | rozdz. 5 polityki |
| Dodanie albo usunięcie klucza Google Cloud dla mowy (`voice_google_key_file`) | rozdz. 3, 6, 7 i 10 polityki, CZ-11 rejestru, rozdz. 5 mapy danych |
| Zmiana `NEXUS_CHMURA_URL` na adres poza serwerem Danaco | rozdz. 3, 6 i 7 polityki, CZ-12 rejestru, rozdz. 4 i 5 mapy danych |
| Rozliczenie planu Grupa za każdego użytkownika i wspólny zakres pracy | rozdz. 5 regulaminu; `backend/nexus/platnosci/grupy.py` |
| Rozdzielenie kolekcji w bazie wektorowej albo chmury osobistej między konta | rozdz. 2 i 3 polityki, rozdz. 5 rejestru — dziś opisują stan nierozdzielony |
| Zmiana limitów pokazu bez konta | rozdz. 2 regulaminu |

Każda zmiana dokumentu podnosi `WERSJA` i `OBOWIAZUJE_OD` w `tresc-prawna.ts`. Reguła
działa od pierwszej publikacji: dopóki strony nie są osiągalne (rozdz. 3), redakcja pracuje
na wersji 1.0 z datą pierwszego wydania, bo nie ma wersji wcześniejszej, od której
czytelnik miałby odróżnić obecną.

## 5. Sprawy do rozstrzygnięcia przez właściciela produktu

| Sprawa | Dlaczego |
|---|---|
| Dane rejestrowe spółki: KRS, NIP, adres siedziby | pole `ADMINISTRATOR.daneRejestrowe` jest puste; ustawa o świadczeniu usług drogą elektroniczną wymaga podania danych usługodawcy |
| Inspektor ochrony danych — czy wyznaczony | polityka nie twierdzi ani że jest, ani że go nie ma |
| Rodzaj konta Anthropic, na które zalogowany jest Claude Code CLI | od tego zależy, czy przekazane treści mogą posłużyć do rozwoju modeli; polityka odsyła dziś do warunków konta, zamiast rozstrzygać |
| Umowa powierzenia przetwarzania z Anthropic, Google i ze Stripe | art. 28 RODO; bez niej rejestr czynności ma lukę |
| Kwalifikacja dostawcy serwera poczty portalu | **stan na 21.09.2026: poczta portalu nie jest wysyłana** — `NEXUS_PORTAL_MAIL_NADAWCA` nie jest ustawione, więc wiadomości trafiają do dziennika aplikacji, a nie do żadnego dostawcy. Sprawa staje się aktualna dopiero po włączeniu wysyłki SMTP. Polityka (rozdz. 6) i rejestr (rozdz. 3) opisują dostawcę zgodnie jako odbiorcę technicznego. Jeżeli dostawca przechowuje wiadomości portalu na zlecenie Danaco, potrzebna jest umowa z art. 28 RODO i zmiana obu dokumentów |
| Czy rozmowa głosowa ma iść przez Google Cloud | dziś rozstrzyga o tym obecność pliku `dane/app/google-api-key`, a nie osobne ustawienie produktu; przy kluczu nagranie głosu trafia do Google przy każdej wypowiedzi (CZ-11) |
| Instrument przekazania poza EOG | rozdz. 7 polityki wskazuje rozdział V RODO ogólnie, bo konkretny instrument wynika z umowy |
| **Polityka opisuje pokaz bez konta, do którego nie ma wejścia** | polityka i rejestr wymieniają „Pokaz bez konta” (sesja gościa, adres IP, pliki wgrane na pokaz) jako czynność przetwarzania, a interfejs pokazu nie istnieje: `/wyprobuj` zakłada konto próbne i wpuszcza do pełnej aplikacji, zaplecze `/api/demo/*` nie jest z niczego wywoływane. Do rozstrzygnięcia razem z losem tego zaplecza: albo wraca interfejs, albo znika opis |
| **Polityka prywatności milczy o rozpoznawaniu twarzy** | `frontend/src/portal/tresc-prawna.ts` wymienia kategorie danych (konto, sesje, rozmowy, pliki, kredyty, pokaz…), ale **ani razu nie pada w niej słowo „twarz” ani „biometr”**, choć narzędzie `find_faces` liczy 512-wymiarowe wektory cech twarzy z wgranych zdjęć (CZ-14). Zasada nadrzędna tego pakietu mówi, że każda kategoria danych ma mieć odpowiednik w polityce — tu jest odwrotnie: kategoria istnieje w kodzie, a nie ma jej w dokumencie. Do rozstrzygnięcia razem z podstawą przetwarzania (art. 9 RODO). Ta sama luka dotyczy **zaproszeń do grupy**: tabela `grupy_zaproszenia` trzyma adres e-mail osoby zapraszanej, także takiej, która nie ma konta — polityka opisuje plan Grupa (regulamin, pkt 3), ale nie mówi, że przetwarzamy dane osoby trzeciej |
| **Polityka milczy o tym, że dodatek czyta strony** | rozszerzenie ma `host_permissions: ["<all_urls>"]` i na polecenie użytkownika odczytuje tytuł, adres i treść odwiedzanej strony (do 24 000 znaków), po czym wysyła je do rozmowy i do modelu (`extension/src/tresc/index.ts:35-37`, `ekstraktor.ts`). W polityce rozszerzenie pada raz, przy kluczach urządzeń — o czytaniu stron nie ma ani słowa. Gotowy tekst: rozdz. 6.3 |
| **Licencja modeli rozpoznawania twarzy** | modele InsightFace (`find_faces`, CZ-14) mają licencję wyłącznie niekomercyjną. Warunek „dopóki produkt nie jest sprzedawany” przestał obowiązywać 21.09.2026 — sprzedaż jest włączona. Do decyzji: model komercyjny, zgoda autorów albo wyłączenie funkcji |
| **Polityka i rejestr milczały o SMS-ach z telefonu** | aplikacja Android ma funkcję „Szkice odpowiedzi na SMS”: po włączeniu i nadaniu `READ_SMS` odczytuje ostatnie wiadomości i **wysyła wybrany wątek na serwer** jako nową rozmowę (`sms/SmsActivity.kt:142-143`). Treść SMS-a to dane osobowe nadawcy, który z Danaco umowy nie zawierał. Dopisane 21.09.2026: **CZ-16** w rejestrze, gotowy tekst w rozdz. 6.3a |
| **Polityka i rejestr milczały o zawartości ekranu telefonu** | języczek przy krawędzi otwiera panel Nexusa nad dowolną aplikacją; przycisk „ekran” wysyła zrzut (`MediaProjection`) i/lub tekst odczytany przez usługę dostępności (`overlay/EdgeTabService.kt`). To najszersza kategoria danych w produkcie — na ekranie może być wszystko. Dopisane 21.09.2026: **CZ-17**, gotowy tekst w rozdz. 6.3b |
| **Jedno pytanie zamiast czterech: rola administratora wobec danych osób trzecich** | twarze ze zdjęć, treść cudzych stron z dodatku, SMS-y i zawartość ekranu to cztery funkcje i **jedno** rozstrzygnięcie: albo administratorem tych danych jest użytkownik (a Danaco jest podmiotem przetwarzającym — wtedy potrzebna umowa powierzenia dla klientów biznesowych), albo Danaco (wtedy każda czynność potrzebuje własnej podstawy z art. 6, a przy danych szczególnej kategorii z art. 9). Od tego zależy brzmienie czterech akapitów polityki. Opis obu dróg: rozdz. 6.3c |
| Przegląd prawniczy całości | przytoczone przepisy i terminy wymagają potwierdzenia przez radcę prawnego przed publikacją |

## 6. Gotowe brzmienie brakujących akapitów polityki (do zatwierdzenia)

**Pięć** luk — rozpoznawanie twarzy, zaproszenia do grupy, treść stron czytana przez
dodatek do przeglądarki oraz (znalezione 21.09.2026 przy przeglądzie klienta Android)
treść SMS-ów i zawartość ekranu telefonu — nie wymaga decyzji biznesowej co do **treści**,
tylko zatwierdzenia i wskazania podstawy prawnej. Żeby nie zostawiać właścicielowi samego
opisu problemu, niżej stoi tekst gotowy do wklejenia.

Cztery z nich stawiają przy tym **jedno wspólne pytanie** o rolę administratora wobec
danych osób trzecich — opisane osobno w §6.3c. Warto zacząć od niego, bo rozstrzyga
brzmienie pozostałych.
**Do polityki nie został wpisany** — dokument prawny zmienia się z podpisem właściciela,
nie decyzją wykonawcy.

### 6.1 Dwa wiersze do tabeli „3. Jakie dane zbieramy”

```
| Rozpoznawanie twarzy | położenie twarzy na zdjęciu oraz liczbowa reprezentacja jej cech (wektor 512 wymiarów), a przy grupowaniu — przypisanie twarzy z różnych zdjęć do tej samej osoby; wynik zapisujemy jako plik w Twojej przestrzeni | zlecenie zadania „znajdź twarze” albo „pogrupuj zdjęcia po osobach” na Twoich zdjęciach |
| Zaproszenia do grupy | adres poczty osoby zapraszanej, skrót tokenu zaproszenia, kto zaprosił, data wygaśnięcia i przyjęcia | zaproszenie wysłane przez założyciela grupy — także do osoby, która nie ma jeszcze konta |
```

### 6.2 Akapit pod tabelą

```
Wektory cech twarzy są danymi biometrycznymi w rozumieniu art. 4 pkt 14 RODO, a ich
przetwarzanie w celu identyfikacji osoby podlega art. 9. Nexus liczy je wyłącznie na
zdjęciach, które sam wgrasz, i wyłącznie na Twoje zlecenie; wynik trafia do Twojej
przestrzeni jako plik i nie jest porównywany z żadną bazą poza Twoimi zdjęciami. Jeżeli
na zdjęciach są inne osoby, to Ty decydujesz o tym przetwarzaniu i Ciebie dotyczy obowiązek
posiadania podstawy prawnej wobec nich. Plik z wynikiem usuwasz tak jak każdy inny plik.

Adres poczty osoby, którą zapraszasz do grupy, przetwarzamy po to, żeby doręczyć jej
zaproszenie i powiązać przyjęcie z właściwą grupą. Zaproszenie wygasa, a niewykorzystane
usuwamy razem z grupą.
```

### 6.3 Trzecia luka, znaleziona 21.09.2026: treść cudzych stron z rozszerzenia

Rozszerzenie przeglądarki ma `host_permissions: ["<all_urls>"]` i **czyta treść
odwiedzanych stron**: `extension/src/tresc/ekstraktor.ts` wyodrębnia artykuł (limit
24 000 znaków), `opinie.ts` — opinie, a menu kontekstowe bierze zaznaczenie. Wysyłany
ładunek to `{ kind: "page", title, url, text }` (`extension/src/tresc/index.ts:35-37`),
czyli **tytuł, adres i treść cudzej strony** — dalej do modelu.

W polityce prywatności rozszerzenie pada **raz**, i to przy zupełnie innej kategorii:
„Klucze urządzeń … dodatek do przeglądarki”. O czytaniu stron nie ma tam ani słowa.
To ta sama klasa luki co biometria: kategoria istnieje w produkcie, a nie ma jej
w dokumencie, który czyta klient.

Gotowy wiersz do tabeli „3. Jakie dane zbieramy”:

```
| Praca z dodatkiem do przeglądarki | tytuł i adres strony, którą otwierasz w przeglądarce, oraz jej treść (zaznaczenie, artykuł albo cała strona, do 24 000 znaków); przy włączonym ustawieniu także zrzut widocznej karty | Twoje polecenie w dodatku: otwarcie panelu albo pozycja z menu kontekstowego |
```

Akapit pod tabelę:

```
Dodatek do przeglądarki nie czyta stron w tle. Treść odczytujemy dopiero wtedy, gdy sam
o to poprosisz — otwierając panel dodatku albo wybierając pozycję z menu po zaznaczeniu
tekstu — i tylko z karty, w której to robisz. Odczytana treść trafia tą samą drogą co
wiadomość napisana w oknie: do Twojej rozmowy i do modelu, który ją prowadzi. Strony
nie modyfikujemy poza miejscem, w które sam każesz wstawić odpowiedź.

Dodatek potrafi też dołączyć zrzut widocznej karty — przydaje się, gdy pytanie dotyczy
tego, co widać, a nie tego, co da się odczytać jako tekst. To ustawienie jest **domyślnie
wyłączone** i włączasz je sam w opcjach dodatku.
```

Na plus obecnego zachowania (i warto to w polityce nazwać): dodatek **nie czyta stron
w tle**, a zrzut karty jest **domyślnie wyłączony** (`extension/src/wspolne/ustawienia.ts:68`).
Opis w polityce nie musi więc niczego obiecywać na wyrost — wystarczy, żeby mówił prawdę.

Możliwość do rozważenia (nie zmieniam sam, bo to decyzja o zachowaniu produktu):
dzisiejsze ustawienie `ukryteHosty` chowa **pływający przycisk**, ale skrypt treści i tak
wchodzi na każdą stronę `http(s)` (`extension/manifest.json`, `content_scripts.matches`).
Nic stamtąd nie wychodzi bez polecenia, ale klient, który chce mieć Nexusa **wyłączonego**
na stronie banku, nie ma dziś takiego przełącznika — ma tylko ukrycie przycisku. Gdyby
polityka miała obiecywać więcej niż „nie czytamy w tle”, to jest miejsce, w którym produkt
musiałby dołożyć wyłącznik per adres.

Do rozstrzygnięcia razem z tym wpisem: czy strony, na których użytkownik pracuje dodatkiem,
mogą zawierać dane osób trzecich (zwykle tak) i co z tego wynika dla podstawy przetwarzania —
tak samo jak przy zdjęciach w `find_faces`.

### 6.3a Czwarta luka, znaleziona 21.09.2026: treść SMS-ów z aplikacji Android

Klient Android ma funkcję „Szkice odpowiedzi na SMS” (przełącznik w ustawieniach,
uprawnienie `READ_SMS` nadawane osobno). Po włączeniu aplikacja odczytuje do 300 ostatnich
wiadomości, pokazuje 50 wątków, a wybrany wątek **wysyła na serwer** jako nową rozmowę,
żeby model napisał szkic odpowiedzi (`android/.../sms/SmsActivity.kt:142-143`).

Polityka prywatności nie wspomina o SMS-ach ani słowem. Rejestr czynności też ich nie
zawierał — dopisałem **CZ-16**.

Gotowe brzmienie do tabeli „3. Jakie dane zbieramy”:

> | Treść wiadomości SMS (tylko aplikacja Android, tylko po włączeniu funkcji „Szkice
> odpowiedzi na SMS” i nadaniu uprawnienia) | numer nadawcy, treść, data i kierunek
> wiadomości z wybranego wątku | przygotowanie przez asystenta szkicu odpowiedzi na Twoją
> prośbę |

Gotowy akapit pod tabelą:

> **SMS-y.** Jeżeli włączysz w aplikacji Android funkcję „Szkice odpowiedzi na SMS”
> i nadasz jej uprawnienie do czytania wiadomości, przy każdym użyciu wybierasz jeden wątek —
> i dopiero wtedy jego treść trafia na nasz serwer jako nowa rozmowa, na tych samych
> zasadach co wszystko, co piszesz Nexusowi. Aplikacja nie czyta wiadomości w tle, nie
> przechowuje ich na telefonie i nie wysyła niczego bez Twojego kliknięcia. Pamiętaj, że
> w wątku są też słowa drugiej strony — wysyłasz wtedy również cudzą wiadomość.

Do rozstrzygnięcia razem z tym wpisem — i jest to **ta sama sprawa co przy zdjęciach
z `find_faces` i przy stronach z dodatku**: nadawca SMS-a nie zawarł z Danaco żadnej umowy
i o niczym nie wie, a jego wiadomość bywa danymi szczególnej kategorii (art. 9 RODO) —
wystarczy SMS z przychodni albo z banku. Trzy funkcje, jedno pytanie: kto jest
administratorem danych osób trzecich, które użytkownik sam wnosi do Nexusa.

### 6.3b Piąta luka: zawartość ekranu telefonu

Ta sama aplikacja Android ma języczek przy krawędzi ekranu, który otwiera panel Nexusa nad
dowolną inną aplikacją. Przycisk „ekran” w panelu wysyła do asystenta **zrzut ekranu**
(`MediaProjection`, zgoda systemowa za każdym razem) i/lub **tekst odczytany z widoku**
przez opcjonalną usługę dostępności. Polityka o tym nie mówi; rejestr też nie mówił —
dopisałem **CZ-17**.

Gotowe brzmienie do tabeli „3. Jakie dane zbieramy”:

> | Zawartość ekranu telefonu (tylko aplikacja Android, tylko po naciśnięciu przycisku
> „ekran” w panelu) | zrzut ekranu i/lub tekst widoczny w aplikacji pod panelem, tytuł okna |
> odpowiedź asystenta na to, co masz właśnie przed sobą |

Gotowy akapit pod tabelą:

> **Zawartość ekranu.** Panel Nexusa można otworzyć nad inną aplikacją. Jeżeli naciśniesz
> w nim przycisk „ekran”, wyślesz nam zrzut tego, co widać, albo tekst z tej aplikacji —
> po to, żeby asystent mógł się do tego odnieść. Za każdym razem prosi o to system, a poza
> tym momentem aplikacja nie patrzy na Twój ekran i nic z niego nie zbiera. Pamiętaj, że
> na zrzucie znajdzie się **wszystko**, co w tej chwili widać — także cudze wiadomości,
> nazwiska czy dane, które akurat masz otwarte.

To jest najszersza kategoria danych w całym produkcie: na ekranie może być dosłownie
wszystko. Warto rozważyć własne ostrzeżenie w aplikacji przy pierwszym użyciu — zgoda
systemowa mówi tylko o „przechwytywaniu zawartości ekranu” i nie wspomina, dokąd ona trafia.

### 6.3c Jedno pytanie zamiast czterech

Luki 6.3, 6.3a i 6.3b oraz zastrzeżenie przy CZ-14 wyglądają na cztery osobne sprawy, ale
sprowadzają się do jednej:

| Funkcja | Czyje dane użytkownik wnosi |
|---|---|
| `find_faces` (CZ-14) | twarze osób widocznych na jego zdjęciach |
| dodatek do przeglądarki (6.3) | treść stron, które ogląda — w tym cudze profile i wiadomości |
| szkice odpowiedzi na SMS (CZ-16, 6.3a) | wiadomości od nadawców, którzy o Nexusie nie wiedzą |
| zawartość ekranu telefonu (CZ-17, 6.3b) | cokolwiek akurat widać, łącznie z cudzą korespondencją |

W każdym z tych przypadków dane trafiają do Nexusa **z woli użytkownika**, ale dotyczą osób,
które nie zawarły z Danaco umowy i nie wyraziły zgody. Rozstrzygnięcie jest jedno i dotyczy
wszystkich czterech naraz:

* albo **administratorem tych danych jest użytkownik**, a Danaco jest podmiotem
  przetwarzającym (wtedy potrzebna jest umowa powierzenia — dla klienta biznesowego
  to warunek zgodnego korzystania z produktu, a dla konsumenta wyjątek „na użytek własny”
  z art. 2 ust. 2 lit. c RODO),
* albo **administratorem jest Danaco**, a wtedy dla każdej z tych czynności trzeba wskazać
  podstawę z art. 6 (i art. 9 tam, gdzie dane są szczególnej kategorii).

Wybór wpływa na treść polityki, na wzór umowy i na to, czy przed pierwszym użyciem którejś
z tych funkcji ma stanąć osobne pytanie. Dlatego proponuję podjąć tę decyzję **raz, dla
wszystkich czterech**, zamiast czterech razy osobno.

### 6.4 Czego to nie rozstrzyga

- **Podstawa prawna z art. 9** dla biometrii: zgoda (art. 9 ust. 2 lit. a) czy uznanie,
  że administratorem tego przetwarzania jest wyłącznie użytkownik, a Nexus jest tu
  podmiotem przetwarzającym. Od tego zależy, czy przed pierwszym użyciem `find_faces`
  ma stanąć pytanie o zgodę.
- **Licencja modeli InsightFace** (rozdz. 5) — bez jej rozstrzygnięcia opis w polityce
  i tak dotyczyłby funkcji, której nie wolno sprzedawać.
Rejestru czynności to **nie** dotyczy: CZ-14 opisuje już i kategorie danych
(„położenie twarzy w kadrze, 512-wymiarowe wektory cech, przypisanie zdjęć do grup”),
i nierozstrzygniętą podstawę z art. 9. Luka jest wyłącznie po stronie dokumentu, który
czyta klient.

---

*Koniec dokumentu. Zgodność prawna produktu — etap 1B, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · etap 1B · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Kontakt: support@danaco-group.pl*
