# Danaco Nexus — Rejestr czynności przetwarzania

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
| **Tytuł** | Rejestr czynności przetwarzania danych osobowych — art. 30 ust. 1 RODO |
| **Klasa dokumentu** | Rejestr |
| **Odbiorcy** | administrator danych · radca prawny · organ nadzorczy |
| **Przeznaczenie** | Wykazuje czynności przetwarzania prowadzone przez produkt Danaco Nexus wraz z celem, podstawą prawną, kategoriami osób i danych, odbiorcami oraz terminem usunięcia. |
| **Zakres** | Portal produktowy, konta klientów, aplikacja Nexus, rozmowa głosowa, poczta, kalendarz i chmura osobista, pokaz bez konta, płatności, powiadomienia, strony publikowane przez użytkowników |
| **Poza zakresem** | Przetwarzanie prowadzone przez użytkownika na własnych materiałach — tam administratorem pozostaje użytkownik |
| **Dokument nadrzędny** | [Zgodność prawna produktu](README.md) |
| **Źródła normatywne** | `backend/nexus/models/**` · `backend/nexus/db.py` · `backend/nexus/platnosci/model.py` · `backend/nexus/platnosci/kredyty.py` · `backend/nexus/demo/sesje.py` |
| **Zasada nadrzędna** | Rejestr wymienia wyłącznie czynności prowadzone przez kod, który istnieje w repozytorium. Czynność planowana trafia do rejestru dopiero razem ze swoim kodem. |

## Spis treści

1. [Administrator i dane kontaktowe](#1-administrator-i-dane-kontaktowe)
2. [Czynności przetwarzania](#2-czynności-przetwarzania)
3. [Role administratora i podmiotu przetwarzającego](#3-role-administratora-i-podmiotu-przetwarzającego)
4. [Środki techniczne i organizacyjne](#4-środki-techniczne-i-organizacyjne)
5. [Braki rejestru](#5-braki-rejestru)

---

## 1. Administrator i dane kontaktowe

| Pozycja | Wartość |
|---|---|
| Administrator | Danaco Holding Group Sp. z o.o. |
| Dane rejestrowe | do uzupełnienia — patrz [README, rozdz. 5](README.md#5-sprawy-do-rozstrzygnięcia-przez-właściciela-produktu) |
| Kontakt w sprawach danych | support@danaco-group.pl |
| Inspektor ochrony danych | nierozstrzygnięte |

## 2. Czynności przetwarzania

### CZ-1. Prowadzenie konta klienta portalu

| Pozycja | Treść |
|---|---|
| Cel | Rejestracja, logowanie, prowadzenie profilu, wgląd w plan i faktury |
| Podstawa prawna | art. 6 ust. 1 lit. b RODO |
| Kategorie osób | klienci i osoby rejestrujące konto |
| Kategorie danych | adres poczty, skrót hasła (Argon2), imię lub nazwa, nazwa firmy, kod planu, daty założenia, zmiany i ostatniego logowania |
| Miejsce w kodzie | tabela `portal_users` — `backend/nexus/models/portal.py` |
| Odbiorcy | brak |
| Przekazanie poza EOG | nie |
| Termin usunięcia | do usunięcia konta przez klienta (`konta.usun_konto`) |

### CZ-2. Utrzymanie sesji i ochrona logowania

| Pozycja | Treść |
|---|---|
| Cel | Utrzymanie zalogowania, wygaszanie sesji bezczynnych, ograniczenie tempa prób logowania i odzyskiwania hasła |
| Podstawa prawna | art. 6 ust. 1 lit. b oraz art. 6 ust. 1 lit. f RODO |
| Kategorie osób | klienci portalu, użytkownik aplikacji |
| Kategorie danych | skrót tokenu sesji, adres IP (do 64 znaków), nagłówek User-Agent (do 300 znaków), daty założenia, ostatniej aktywności i wygaśnięcia |
| Miejsce w kodzie | tabele `portal_sessions` i `sessions` — `backend/nexus/models/portal.py`, `backend/nexus/db.py` |
| Odbiorcy | brak |
| Przekazanie poza EOG | nie |
| Termin usunięcia | wygaśnięcie ciasteczka (portal 14 dni, aplikacja 30 dni) albo 7 dni bezczynności; kasowanie przy kolejnym logowaniu (`konta.usun_wygasle`) |

### CZ-3. Odzyskiwanie hasła i potwierdzenie adresu poczty

| Pozycja | Treść |
|---|---|
| Cel | Wydanie jednorazowego tokenu: do ustawienia nowego hasła oraz do potwierdzenia, że adres poczty należy do zakładającego konto |
| Podstawa prawna | art. 6 ust. 1 lit. b RODO |
| Kategorie osób | klienci portalu |
| Kategorie danych | skrót tokenu (SHA-256), daty utworzenia, wygaśnięcia i użycia, powiązanie z kontem |
| Miejsce w kodzie | tabele `portal_password_resets` i `portal_email_confirmations` — `backend/nexus/models/portal.py`; `konta.token_odzyskiwania`, `konta.token_potwierdzenia` |
| Odbiorcy | dostawca serwera SMTP użytego do wysyłki wiadomości, jeżeli wysyłka jest włączona |
| Przekazanie poza EOG | zależne od wybranego serwera poczty |
| Termin usunięcia | do użycia tokenu albo do wygaśnięcia: odzyskiwanie hasła domyślnie 30 minut, potwierdzenie adresu 24 godziny (`konta.POTWIERDZENIE_WAZNE`) |

### CZ-4. Obsługa formularza kontaktu

| Pozycja | Treść |
|---|---|
| Cel | Odpowiedź na zapytanie wysłane z portalu |
| Podstawa prawna | art. 6 ust. 1 lit. f RODO — obsługa zapytania nadawcy |
| Kategorie osób | osoby piszące przez formularz |
| Kategorie danych | imię lub nazwa, adres poczty, temat, treść wiadomości, data, stan obsługi |
| Miejsce w kodzie | tabela `portal_messages` — `backend/nexus/models/portal.py` |
| Odbiorcy | brak |
| Przekazanie poza EOG | nie |
| Termin usunięcia | do załatwienia sprawy, następnie przez okres przedawnienia roszczeń |

### CZ-5. Praca agenta na materiałach użytkownika

| Pozycja | Treść |
|---|---|
| Cel | Wykonanie zadania zleconego agentowi: rozmowa, praca na plikach, rozpoznawanie tekstu, konwersje, transkrypcja wgranych nagrań, wyszukiwanie po znaczeniu. Rozmowę głosową opisuje CZ-11, a pracę z pocztą, kalendarzem i chmurą osobistą — CZ-12 |
| Podstawa prawna | art. 6 ust. 1 lit. b RODO; wobec danych osób trzecich zawartych w materiałach administratorem pozostaje użytkownik |
| Kategorie osób | użytkownik oraz osoby, których dane znajdują się w przekazanych materiałach |
| Kategorie danych | rozmowy i wiadomości, pliki wraz z treścią, metadane plików (nazwa, typ, rozmiar, SHA-256), wywołania narzędzi z danymi wejściowymi, przebiegi zadań i zużycie tokenów, fragmenty dokumentów i ich osadzenia w bazie wektorowej, materiały modułu badawczego |
| Rozdzielenie kont | rozmowy, pliki, sesje, klucze urządzeń i kolekcje modułu badawczego mają kolumnę `owner_id` (`db.py:45-52`, `models/research.py:28`); zapytania ograniczają się do konta z sesji (`auth.wlasciciel`). Przestrzeń jednego konta wyznacza jego plan: 100 MB w okresie próbnym, 1 GB w planie Osobistym, 2 GB w Pro, 10 GB w Grupie (`platnosci/plany.py`, `platnosci/uprawnienia.py:limity_uzytkownika`, sprawdzenie `api/files.py`). Wyjątki opisuje rozdz. 5 |
| Miejsce w kodzie | tabele `conversations`, `messages`, `files`, `runs`, `run_events`, `tool_calls` — `backend/nexus/db.py`; `research_*` — `backend/nexus/models/research.py`; kolekcja `nexus_documents` w bazie wektorowej |
| Odbiorcy | Anthropic — w zakresie treści bieżącego zadania (CZ-6) |
| Przekazanie poza EOG | tak, w zakresie CZ-6 |
| Termin usunięcia | do usunięcia przez użytkownika |

### CZ-6. Przekazanie treści zadania do modelu Claude

| Pozycja | Treść |
|---|---|
| Cel | Rozumowanie i planowanie wykonywane przez model językowy na polecenie użytkownika |
| Podstawa prawna | art. 6 ust. 1 lit. b RODO — element usługi zamówionej przez użytkownika |
| Kategorie osób | użytkownik oraz osoby, których dane znajdują się w przekazanych materiałach |
| Kategorie danych | treść wiadomości do agenta, fragmenty i podglądy czytanych plików, wyniki narzędzi, historia bieżącej rozmowy, stałe polecenie systemowe; przy pracy z siecią także zapytanie wyszukiwania, adres strony oraz — przy pracy w przeglądarce (`browser_*`) — tekst i wykaz elementów odwiedzanej strony, a gdy użytkownik o to poprosi, treść wpisywana w jej pola |
| Czego nie obejmuje | pełna treść plików niepotrzebnych do zadania, baza wiedzy i indeks znaczeniowy, hasła i skróty haseł, tokeny sesji, klucze urządzeń, dane kont i rozliczeń |
| Miejsce w kodzie | `backend/nexus/agent/runner.py`, `backend/nexus/agent/prompt.py`; praca w przeglądarce — `backend/nexus/tools/przegladarka.py`, `backend/nexus/tworczy/przegladarka.py`; model domyślny i zapasowy — `backend/nexus/config.py` |
| Odbiorcy | Anthropic |
| Przekazanie poza EOG | tak — instrument do potwierdzenia umową (README, rozdz. 5) |
| Termin usunięcia | po stronie Anthropic według warunków konta, na które zalogowany jest Claude Code CLI |

### CZ-7. Sprzedaż planów i rozliczenia

| Pozycja | Treść |
|---|---|
| Cel | Zakup planu, rozliczenie subskrypcji, wystawienie i udostępnienie faktury |
| Podstawa prawna | art. 6 ust. 1 lit. b RODO oraz art. 6 ust. 1 lit. c RODO |
| Kategorie osób | klienci kupujący plan płatny |
| Kategorie danych | identyfikator użytkownika, kod planu, okres, stan subskrypcji, identyfikatory klienta i subskrypcji w Stripe, numer, kwota i stan faktury, adresy dokumentu, kod rabatowy, treść zdarzeń rozliczeniowych |
| Miejsce w kodzie | tabele `platnosci_subskrypcje`, `platnosci_faktury`, `platnosci_kupony`, `platnosci_zdarzenia` — `backend/nexus/platnosci/model.py` |
| Odbiorcy | Stripe |
| Przekazanie poza EOG | tak — instrument do potwierdzenia umową |
| Termin usunięcia | faktury i dane rozliczeniowe przez okres wymagany przepisami podatkowymi i o rachunkowości |

Numery kart płatniczych nie są przyjmowane ani przechowywane przez Nexusa; dane karty
klient podaje bezpośrednio w kasie Stripe.

### CZ-8. Powiadomienia w przeglądarce

| Pozycja | Treść |
|---|---|
| Cel | Powiadomienie o zakończonym zadaniu agenta |
| Podstawa prawna | art. 6 ust. 1 lit. a RODO — zgoda udzielona w przeglądarce |
| Kategorie osób | użytkownicy, którzy włączyli powiadomienia |
| Kategorie danych | adres punktu odbioru, klucze `p256dh` i `auth`, nazwa urządzenia, nagłówek User-Agent, data ostatniej wysyłki, liczba błędów |
| Miejsce w kodzie | tabela `push_subscriptions` — `backend/nexus/models/push.py`; wysyłka — `backend/nexus/push_service.py` |
| Odbiorcy | dostawca usługi powiadomień przeglądarki |
| Przekazanie poza EOG | tak, zależnie od przeglądarki |
| Termin usunięcia | do wycofania zgody albo do trwałego błędu doręczenia |

### CZ-9. Klucze urządzeń

| Pozycja | Treść |
|---|---|
| Cel | Uwierzytelnienie połączenia pomocniczego: klienta na komputerze, klienta na telefonie i dodatku do przeglądarki. Rodzaj zapisuje kolumna `kind` (`android`, `desktop`, `rozszerzenie`, `inne` — `api/modules/urzadzenia.py:25`). Nie są to osobne produkty; usługą jest portal wraz z aplikacją w przeglądarce |
| Podstawa prawna | art. 6 ust. 1 lit. b RODO |
| Kategorie osób | użytkownik aplikacji |
| Kategorie danych | nazwa i rodzaj urządzenia, skrót klucza, data utworzenia i ostatniego użycia, znacznik odwołania |
| Miejsce w kodzie | tabela `device_tokens` — `backend/nexus/db.py` |
| Odbiorcy | brak |
| Przekazanie poza EOG | nie |
| Termin usunięcia | do odwołania klucza |

### CZ-10. Konto próbne (wejście bez rejestracji)

Pod adresem `/wyprobuj` serwer zakłada zwykłe konto klienta z technicznym adresem
(`probny-<losowe>@goscie.danaco-nexus.local`) i wydaje na nie sesję. Gość pracuje w pełnej
aplikacji, na własnej przestrzeni — czynności przetwarzania są więc te same co dla konta
założonego w portalu (CZ-1 … CZ-9, CZ-11, CZ-12), tyle że konto ma termin ważności.

| Pozycja | Treść |
|---|---|
| Cel | Udostępnienie produktu do wypróbowania bez rejestracji, przy zachowaniu limitów chroniących serwer |
| Podstawa prawna | art. 6 ust. 1 lit. f RODO — prezentacja produktu i ochrona zasobów |
| Kategorie osób | odwiedzający, który wszedł pod `/wyprobuj` |
| Kategorie danych | token sesji, adres IP i nagłówek przeglądarki (limit kont z jednego adresu), techniczny adres konta, saldo kredytów; dalej jak dla konta klienta — rozmowy, pliki, przebiegi |
| Miejsce w kodzie | `backend/nexus/api/auth.py` (`gosc`, `_konto_goscia`, `LimitKontGoscia`) |
| Odbiorcy | Anthropic — w zakresie CZ-6 |
| Przekazanie poza EOG | tak, w zakresie CZ-6 |
| Termin usunięcia | wygaśnięcie sesji konta próbnego (2 dni od założenia); wraz z kontem kasowane są jego rozmowy, pliki i przebiegi |

### CZ-11. Rozmowa głosowa i przekazanie nagrania do Google

| Pozycja | Treść |
|---|---|
| Cel | Rozpoznanie wypowiedzi użytkownika z mikrofonu i przeczytanie odpowiedzi agenta na głos |
| Podstawa prawna | art. 6 ust. 1 lit. b RODO — element usługi uruchamianej przez użytkownika |
| Kategorie osób | użytkownik aplikacji oraz osoby, których dane padną w wypowiedzi |
| Kategorie danych | nagranie wypowiedzi z mikrofonu (po przekodowaniu na 16 kHz mono PCM), kod języka, rozpoznany tekst, tekst odpowiedzi czytanej na głos |
| Miejsce w kodzie | `backend/nexus/api/voice.py`, `backend/nexus/voice.py` (`transcribe`, `speak`), `backend/nexus/voice_google.py` |
| Odbiorcy | Google — Cloud Speech-to-Text (`https://speech.googleapis.com/v1/speech:recognize`) i Cloud Text-to-Speech (`https://texttospeech.googleapis.com/v1`) |
| Warunek przekazania | obecność klucza API w pliku `voice_google_key_file` (`GoogleSpeech.available()`, `voice_google.py:61-62`). Klucz na tym serwerze istnieje — `dane/app/google-api-key`, 40 B, prawa 600; `.env.example` ustawia go domyślnie. Przy kluczu Google rozpoznaje mowę **jako pierwszy** (`voice.py:97-99`), a model lokalny Whisper jest zapasem; synteza idzie do Google dla głosów z przedrostkiem `google:` (`voice.py:179-181`) |
| Przekazanie poza EOG | tak — instrument do potwierdzenia umową (README, rozdz. 5) |
| Termin usunięcia | nagranie w katalogu roboczym kasowane zaraz po rozpoznaniu (`NamedTemporaryFile`, `api/voice.py:59-73`); rozpoznany tekst — jak CZ-5, gdy użytkownik wyśle go jako wiadomość; po stronie Google według warunków usługi |

### CZ-12. Poczta, kalendarz i chmura osobista

| Pozycja | Treść |
|---|---|
| Cel | Czytanie i wysyłanie wiadomości, odczyt i zmiana wydarzeń kalendarza, praca na plikach chmury osobistej na polecenie użytkownika |
| Podstawa prawna | art. 6 ust. 1 lit. b RODO; wobec danych osób trzecich w korespondencji i wydarzeniach administratorem pozostaje użytkownik |
| Kategorie osób | użytkownik, jego korespondenci, uczestnicy wydarzeń oraz osoby, których dane są w plikach chmury |
| Kategorie danych | dane konta poczty (adres, serwery, login, hasło) w pliku konfiguracji; nagłówki, treść i załączniki wiadomości; wydarzenia wraz z terminem, opisem, miejscem i uczestnikami; nazwy, ścieżki i treść plików chmury; działanie przygotowane do zatwierdzenia wraz z jego treścią |
| Miejsce w kodzie | `backend/nexus/mail.py` (imaplib, smtplib; `mail.config_path` — plik `poczta/<konto>.json` osobny dla każdego konta użytkownika, konto administratora zostaje przy pliku sprzed podziału), `backend/nexus/calendar.py` (CalDAV), `backend/nexus/cloud_service.py` (WebDAV), tabela `biuro_oczekujace` — `backend/nexus/models/biuro.py` |
| Odbiorcy | serwer poczty wskazany w konfiguracji konta (IMAP i SMTP). Chmura i kalendarz to Nextcloud pod `settings.chmura_url`, domyślnie `http://127.0.0.1:8940`, czyli ten sam serwer — bez odbiorcy zewnętrznego, dopóki adres nie zostanie zmieniony |
| Przekazanie poza EOG | zależne od wybranego serwera poczty; chmura i kalendarz — nie, przy adresie domyślnym |
| Termin usunięcia | wiadomości i wydarzenia — po stronie odpowiednio serwera poczty i chmury, do usunięcia przez użytkownika; działanie oczekujące — do zatwierdzenia, odrzucenia albo błędu |

### CZ-13. Kredyty konta i księga ich zmian

| Pozycja | Treść |
|---|---|
| Cel | Rozliczenie pracy agenta w jednostkach kupionych przez klienta: przydział z planu i z dokupionego pakietu, naliczenie za wykonany przebieg, zatrzymanie zleceń przy saldzie wyczerpanym oraz odpowiedź na pytanie „za co zeszły mi kredyty” |
| Podstawa prawna | art. 6 ust. 1 lit. b RODO — rozliczenie usługi zamówionej przez klienta |
| Kategorie osób | klienci korzystający z agenta |
| Kategorie danych | identyfikator konta, saldo, suma przydzielonych i zużytych kredytów; w księdze — zmiana salda, saldo po operacji, powód, opis, identyfikator przebiegu i data |
| Miejsce w kodzie | tabele `platnosci_kredyty` i `platnosci_kredyty_ruchy` — `backend/nexus/platnosci/kredyty.py`; katalog pakietów `platnosci/pakiety.py`; punkt końcowy `GET /api/platnosci/kredyty` |
| Odbiorcy | Stripe — wyłącznie w zakresie zapłaty za pakiet albo plan (CZ-7); sama księga kredytów nie wychodzi na zewnątrz |
| Przekazanie poza EOG | nie |
| Termin usunięcia | przez czas prowadzenia konta, a następnie przez okres rozliczenia subskrypcji i przedawnienia roszczeń — księga jest dowodem naliczenia |

Przelicznik kredytów jest wewnętrzną ceną Danaco (`docs/platnosci/KREDYTY.md`). Warunki i limity
po stronie dostawcy modelu nie trafiają ani do interfejsu, ani do komunikatów błędu; pilnuje tego
`backend/tests/test_kredyty.py`.

## 3. Role administratora i podmiotu przetwarzającego

| Zakres | Rola Danaco | Uwaga |
|---|---|---|
| Konto klienta, sesje, rozliczenia, kredyty i ich księga, formularz kontaktu, pokaz bez konta | administrator | dane zbierane przez usługodawcę na własne potrzeby |
| Materiały wgrane przez użytkownika do pracy agenta | podmiot przetwarzający wobec danych osób trzecich zawartych w tych materiałach | administratorem pozostaje użytkownik — zapisano to w rozdz. 12 regulaminu |
| Rozmowa głosowa, poczta, kalendarz i chmura osobista | jak wyżej: administrator wobec danych konta, podmiot przetwarzający wobec danych osób trzecich w wypowiedziach, korespondencji i wydarzeniach | CZ-11 i CZ-12 |
| Strona opublikowana przez użytkownika pod `/s/<adres>/` | podmiot przetwarzający (hosting) wobec odwiedzających | administratorem jest użytkownik: to on decyduje o treści strony i o tym, czy zostawia na niej odwołania do cudzych serwerów (CZ-15) |
| Anthropic, Google (usługa mowy), Stripe | podmioty przetwarzające wobec Danaco | wymagana umowa powierzenia (art. 28 RODO) |
| Dostawca serwera poczty | odbiorca techniczny — przenosi wiadomość do adresata, nie przetwarza jej na zlecenie Danaco w innym celu | ta sama kwalifikacja co w rozdz. 6 polityki prywatności. Konto poczty w module Poczta należy do użytkownika i to on wybiera dostawcę; przy wiadomościach portalu (`NadawcaSmtp`) rozstrzygnięcie, czy potrzebna jest umowa z art. 28 RODO, jest w rozdz. 5 |

## 4. Środki techniczne i organizacyjne

| Środek | Gdzie |
|---|---|
| Hasła kont wyłącznie jako skrót Argon2, minimum 12 znaków, ponowne haszowanie przy zmianie parametrów | `auth.hasher.hash` — `api/auth.py:49-52` (administrator) i `portal/konta.py:141-146`, `:164-170` (klient); próg długości `konta.MIN_HASLO` |
| Hasła do usług podłączanych przez użytkownika **nie są** skrótem — muszą dać się odczytać, bo serwer loguje się nimi w jego imieniu | skrzynka pocztowa: plik `poczta/<konto>.json`, prawa 600, zapis atomowy — `mail.save_accounts`; chmura i kalendarz: `settings.chmura_token_file`. Polityka mówi o tym w rozdz. 10 |
| W bazie skrót tokenu, nigdy sam token — sesje, odzyskiwanie hasła, klucze urządzeń, punkty odbioru powiadomień | `backend/nexus/db.py`, `models/portal.py`, `models/push.py` |
| Ciasteczka `HttpOnly`, `SameSite=Lax`, `Secure` | `api/auth.py:235-245`, `portal/konta.py:181-190`, `api/modules/demo.py:113-121` — w `demo/sesje.py` leżą wyłącznie stałe `COOKIE_NAME` i `COOKIE_PATH` (`:24-25`). Ciasteczko pokazu jako jedyne nie dostaje `domain`; ogranicza je ścieżka `/api/demo` |
| Nagłówek żądania aplikacji jako ochrona przed CSRF | `konta.sprawdz_naglowek`, `auth.require_session` |
| Rozdzielenie kont: rozmowy, pliki, sesje, klucze urządzeń i kolekcje modułu badawczego mają `owner_id`, a skrzynka pocztowa własny plik konfiguracji | `db.py:45-52`, `models/research.py:28`, `auth.wlasciciel`, `mail.config_path`. Zakres rozdzielenia i jego luki — CZ-5 oraz rozdz. 5 |
| Przestrzeń jednego konta na pliki według planu (100 MB / 1 GB / 2 GB / 10 GB), sprawdzana przed przyjęciem pliku | `platnosci/plany.py`, `platnosci/uprawnienia.py` (`limity_uzytkownika`), `api/files.py`; test `backend/tests/test_izolacja_kont.py::test_limit_przestrzeni_konta` |
| Kredyty jako zawór na zużycie: przebieg zawsze kosztuje, saldo nie schodzi poniżej zera, puste konto nie przyjmuje zlecenia | `platnosci/kredyty.py`, test `backend/tests/test_kredyty.py` |
| Ograniczenie tempa prób logowania, odzyskiwania, kontaktu i usunięcia konta | `backend/nexus/api/modules/portal.py` |
| Brak wskazówki, czy adres jest zarejestrowany; wyrównany czas odpowiedzi | `konta.HASLO_ZASTEPCZE` |
| Wygaszanie sesji bezczynnej niezależnie od ważności ciasteczka | `konta.BEZCZYNNOSC` |
| Narzędzia agenta — rozpoznawanie tekstu, obróbka obrazu, konwersje, transkrypcja wgranych nagrań (Whisper) i osadzenia (fastembed) — liczą się na serwerze, bez usług zewnętrznych; wyjątkiem są narzędzia sieciowe (CZ-6) oraz poczta, kalendarz i chmura (CZ-12) | `backend/nexus/tools/**`, `backend/nexus/knowledge.py` |
| Rozmowa głosowa **nie** działa wyłącznie lokalnie: przy kluczu Google Cloud nagranie i tekst idą do Google, a model lokalny jest zapasem — patrz CZ-11 | `backend/nexus/voice.py`, `backend/nexus/voice_google.py` |
| Działanie na komputerze użytkownika dopiero po potwierdzeniu | `backend/nexus/models/biuro.py`, `desktop/src/agent/powershellPolicy.js` |
| Środowisko procesu modelu budowane od zera — adres bazy, ścieżki do plików z kluczami i adresy usług wewnętrznych nie wchodzą do piaskownicy | `backend/nexus/agent/piaskownica.py` (`--clearenv`, `ZMIENNE_DOZWOLONE`, `srodowisko`); test `test_srodowisko_serwera_nie_wchodzi_do_piaskownicy` |
| Proces modelu w zamkniętej przestrzeni montowań: widzi katalog projektu użytkownika, profil sesji, katalog zadania i łańcuch narzędzi serwera do odczytu — nie widzi kodu produktu, pozostałych projektów na dysku, katalogu producenta ani kluczy | `backend/nexus/agent/piaskownica.py` (`bwrap`), wpięcie w `agent/runner.py`; test `backend/tests/test_piaskownica.py` |
| Serwer narzędzi poza piaskownicą, dostępny dla modelu wyłącznie przez gniazdo — kodu produktu i poświadczeń bazy nie da się z wnętrza przeczytać | `backend/nexus/agent/most_mcp.py` |
| Kod pisany przez model (scena animacji) renderowany w piaskownicy bez wyjścia do sieci | `backend/nexus/tools/animacja.py` |
| Adresy podawane narzędziom sieciowym i przeglądarce sprawdzane przed połączeniem: sieć wewnętrzna serwera i adresy prywatne odrzucane | `backend/nexus/research/web.py` (`check_url`); test `backend/tests/test_przegladarka_agenta.py` |
| Idempotencja zdarzeń rozliczeniowych i weryfikacja podpisu webhooka | `backend/nexus/platnosci/**` |

### CZ-14. Rozpoznawanie twarzy na zdjęciach użytkownika

| Pozycja | Treść |
|---|---|
| Cel | Porządkowanie zbioru zdjęć według osób na prośbę użytkownika (narzędzie `find_faces`) |
| Podstawa prawna | **Rozstrzygnięte 21.09.2026**: wobec **użytkownika** — art. 6 ust. 1 lit. b RODO (wykonanie umowy). Wobec **osób widocznych na zdjęciach** administratorem jest **użytkownik**, a Danaco jest podmiotem przetwarzającym (art. 28 RODO) — to on kieruje narzędzie na konkretne zdjęcie i on odpowiada za podstawę, w tym za art. 9, gdy wizerunek służy jednoznacznej identyfikacji. Dla klienta biznesowego potrzebna umowa powierzenia; dla konsumenta w sprawach osobistych wchodzi wyłączenie z art. 2 ust. 2 lit. c |
| Kategorie osób | użytkownik oraz każda osoba widoczna na wgranych przez niego zdjęciach |
| Kategorie danych | położenie twarzy w kadrze, 512-wymiarowe wektory cech, przypisanie zdjęć do grup |
| Miejsce w kodzie | `backend/nexus/tools/studio.py` (`find_faces`), program `danaco-twarze-indeks` (InsightFace) |
| Odbiorcy | brak — model liczy na tym serwerze, nic nie wychodzi na zewnątrz |
| Przekazanie poza EOG | nie |
| Termin usunięcia | wynik jest plikiem rozmowy i podlega CZ-4; wektory nie są przechowywane poza tym plikiem |
| Zastrzeżenie licencyjne | modele InsightFace mają licencję **wyłącznie niekomercyjną**. Warunek „dopóki produkt nie jest sprzedawany” **przestał obowiązywać 21.09.2026**: sprzedaż jest włączona (Stripe skonfigurowany, `/api/platnosci/cennik` na produkcji zwraca `sprzedaz_aktywna: true`). Do rozstrzygnięcia przez właściciela: wymiana modelu na komercyjny, zgoda autorów albo wyłączenie `find_faces` do czasu jednego z dwóch pierwszych |

### CZ-15. Strona użytkownika opublikowana pod `/s/<adres>/`

| Pozycja | Treść |
|---|---|
| Cel | Udostępnienie w internecie witryny, którą użytkownik zbudował w module Strony |
| Podstawa prawna | art. 6 ust. 1 lit. b RODO — wykonanie umowy z użytkownikiem. Wobec **odwiedzających** stronę administratorem jest użytkownik, nie Danaco; Danaco jest podmiotem przetwarzającym (hosting) |
| Kategorie osób | odwiedzający opublikowaną stronę |
| Kategorie danych | adres IP i nagłówki żądania w dzienniku serwera; dane, które sam użytkownik umieści na stronie |
| Miejsce w kodzie | `backend/nexus/api/modules/strony.py` (`_serve`, `published_file`), magazyn `nexus/tworczy/strony.py` |
| Odbiorcy | **zależy od treści strony.** Gotowe szablony wczytują zasoby z cudzych serwerów — przegląd kolekcji z 20 września 2026: 48 z 81 zbudowanych szablonów sięga po sieć, najczęściej po kroje Google (`fonts.googleapis.com`, `fonts.gstatic.com`), dalej `cdn.jsdelivr.net` i `images.unsplash.com`. Każde takie odwołanie wysyła adres IP odwiedzającego do właściciela tego serwera |
| Przekazanie poza EOG | tak, gdy na stronie zostaną odwołania do zasobów z sieci (Google, CDN-y) |
| Ograniczenie ryzyka | `site_from_template` i `site_from_kit` wypisują w wyniku, z jakich serwerów strona korzysta. Kroje przenosi na serwer Danaco `site_fonts_local` (repozytorium 2050 rodzin, podzbiór z polskimi znakami), resztę — skrypty, arkusze, zdjęcia — ściąga `site_vendor_assets`. Sprawdzone na szablonie `accessible-astro-dashboard`: 38 odwołań do cudzych serwerów przed, 8 po (zostają same adresy kanoniczne autora, które niczego nie pobierają); żądań do Google po operacji: 0 |
| Termin usunięcia | do czasu wycofania publikacji przez użytkownika (`site_unpublish`) albo usunięcia strony |

### CZ-16. Szkice odpowiedzi na SMS-y (aplikacja Android)

Dopisane 21.09.2026 po przeglądzie uprawnień klienta Android. Czynności **nie było
w rejestrze**, choć funkcja jest w kodzie i w ustawieniach aplikacji.

| Pozycja | Treść |
|---|---|
| Cel | Napisanie przez model szkicu odpowiedzi na wybrany wątek SMS, na żądanie użytkownika |
| Podstawa prawna | wobec **użytkownika** — art. 6 ust. 1 lit. b RODO. Wobec **nadawców wiadomości** — **rozstrzygnięte 21.09.2026**: administratorem jest użytkownik (to on wybiera wątek i wysyła go do asystenta), Danaco jest podmiotem przetwarzającym. Treść SMS-a bywa szczególnej kategorii (art. 9), np. wiadomość z przychodni — odpowiedzialność za podstawę spoczywa wtedy na użytkowniku, dlatego warto mu to powiedzieć przy włączaniu funkcji |
| Kategorie osób | użytkownik oraz **każda osoba, która wysłała mu SMS** w odczytanym zakresie |
| Kategorie danych | numer nadawcy, treść wiadomości, data, kierunek (przychodząca/wychodząca); odczyt obejmuje do 300 ostatnich wiadomości, na ekran trafia 50 wątków |
| Miejsce w kodzie | `android/.../sms/SmsReader.kt` (odczyt przez `Telephony.Sms`), `android/.../sms/SmsActivity.kt:142-143` (założenie rozmowy i przekazanie wątku do serwera), przełącznik „Szkice odpowiedzi na SMS” w `settings/SettingsActivity.kt` |
| Uprawnienie systemowe | `android.permission.READ_SMS`, nadawane osobno i tylko po włączeniu funkcji |
| Odbiorcy | serwer Danaco (rozmowa zakładana przez `api.createConversation`), a dalej **model Claude przez Claude Code CLI** — tak jak każda treść rozmowy (CZ-3) |
| Przekazanie poza EOG | tak, na tych samych zasadach co pozostałe rozmowy |
| Termin usunięcia | treść wątku staje się zwykłą rozmową i podlega CZ-4 (usuwana razem z rozmową) |
| Zastrzeżenie | odczyt sam w sobie niczego nie wysyła i nic nie zapisuje na telefonie — ale **funkcja jako całość wysyła**. Komentarz w `SmsReader.kt` mówił wcześniej „nic nie jest zapisywane ani wysyłane”, co było prawdą o tym pliku i nieprawdą o funkcji; poprawiony 21.09.2026 |
| Uwaga dystrybucyjna | `READ_SMS` jest w Google Play uprawnieniem zastrzeżonym (wymaga bycia domyślną aplikacją SMS albo zatwierdzonego wyjątku). Dziś APK jest rozprowadzany poza sklepem, więc zasada nie ma zastosowania — ale ma ją, gdyby aplikacja miała trafić do Play |

### CZ-17. Zawartość ekranu telefonu przekazana do panelu (aplikacja Android)

Dopisane 21.09.2026, razem z CZ-16, po przeglądzie uprawnień klienta Android.

| Pozycja | Treść |
|---|---|
| Cel | Odpowiedź asystenta na to, co użytkownik ma właśnie na ekranie — panel Nexusa otwierany języczkiem nad dowolną aplikacją |
| Podstawa prawna | wobec **użytkownika** — art. 6 ust. 1 lit. b RODO. Wobec **osób, których dane widać na ekranie** — **rozstrzygnięte 21.09.2026**: administratorem jest użytkownik, Danaco jest podmiotem przetwarzającym. Zrzut powstaje wyłącznie na jego kliknięcie i to on decyduje, co w tej chwili widać |
| Kategorie osób | użytkownik oraz każda osoba, której dane są widoczne na ekranie w chwili zrzutu (czyjaś wiadomość, czyjś e-mail, czyjś profil) |
| Kategorie danych | zrzut ekranu jako obraz (`ScreenContent.dataUrl`) oraz/albo tekst odczytany z widoku przez usługę dostępności; tytuł okna |
| Miejsce w kodzie | `android/.../overlay/EdgeTabService.kt` (`sendScreen`, `MediaProjection`), `android/.../access/NexusAccessibilityService.kt` (odczyt tekstu), `android/.../assist/ScreenContent.kt` |
| Warunki uruchomienia | nakładka wymaga `SYSTEM_ALERT_WINDOW`; zrzut — **zgody systemowej za każdym razem**; odczyt tekstu — usługi dostępności włączanej ręcznie w ustawieniach systemu. Nic nie dzieje się w tle ani bez naciśnięcia przycisku w panelu |
| Odbiorcy | serwer Danaco, a dalej model Claude przez Claude Code CLI — jak każda treść rozmowy (CZ-3) |
| Przekazanie poza EOG | tak, na tych samych zasadach co pozostałe rozmowy |
| Termin usunięcia | zrzut i tekst stają się treścią rozmowy i podlegają CZ-4 |
| Uwaga | to jest najszersza kategoria danych w całym produkcie: na ekranie może być **wszystko**, łącznie z danymi szczególnej kategorii. Warto rozważyć ostrzeżenie w aplikacji przy pierwszym użyciu — dziś zgoda systemowa mówi tylko o „przechwytywaniu zawartości ekranu”, nie o tym, dokąd ona trafia |

## 5. Braki rejestru

| Brak | Skutek |
|---|---|
| Dane rejestrowe administratora | rejestr niekompletny w części identyfikacyjnej (art. 30 ust. 1 lit. a RODO) |
| Podstawa przetwarzania danych biometrycznych i licencja modeli twarzy | CZ-14 działa dziś na modelach niekomercyjnych i bez wyraźnej zgody. Termin „przed uruchomieniem sprzedaży” **już minął**: sprzedaż włączono 21.09.2026 (wydanie „Sprzedaż włączona: produkty w Stripe, ceny z serwera, plan Grupa”), a funkcja `find_faces` jest w rejestrze narzędzi i dostępna dla płacących klientów. Do zamknięcia niezwłocznie: zgoda przy pierwszym użyciu funkcji oraz model o licencji komercyjnej — albo wyłączenie funkcji do czasu rozstrzygnięcia |
| Rozdzielenie kont w chmurze i kalendarzu opiera się na nazwie, nie na osobnym koncie | `CloudService` i `CalendarClient` nadal logują się jednym kontem Nextcloud (`settings.chmura_user`, `chmura_token_file`), ale każde konto pracuje w swoim zakresie: pliki w `/Konta/<owner>` (`cloud_service.katalog_konta`), kalendarze z przedrostkiem `konto-<owner>-` (`calendar.przedrostek_konta`), a żądania poza ten zakres są odrzucane. Rozdział trzyma się więc kodu Nexusa — administrator Nextcloud widzi wszystko |
| Umowy powierzenia z Anthropic, Google i Stripe | CZ-6, CZ-7 i CZ-11 nie mają udokumentowanej podstawy powierzenia |
| Kwalifikacja dostawcy serwera poczty portalu | rozdz. 3 tego rejestru i rozdz. 6 polityki opisują go jako odbiorcę technicznego. Jeżeli właściciel produktu uzna, że dostawca przechowuje wiadomości portalu na zlecenie Danaco, potrzebna będzie umowa z art. 28 RODO i zmiana obu dokumentów |
| Wskazanie instrumentu przekazania poza EOG | CZ-6, CZ-7, CZ-8 i CZ-11 opisują przekazanie ogólnie (art. 30 ust. 1 lit. e RODO) |
| Rozstrzygnięcie, czy rozmowa głosowa ma iść przez Google | dziś decyduje o tym obecność pliku z kluczem, a nie osobne ustawienie; wyłączenie wymaga usunięcia klucza albo zmiany `NEXUS_VOICE_GOOGLE_KEY_FILE`. Bez świadomej decyzji właściciela produktu nagranie głosu trafia do Google przy każdej wypowiedzi |
| Warunki usługi Google Cloud w zakresie wykorzystania przekazanych nagrań | rejestr nie rozstrzyga, co Google robi z nagraniem po rozpoznaniu; potrzebne potwierdzenie umową, tak jak przy Anthropic |
| Zasoby z cudzych serwerów na stronach użytkowników | CZ-15: narzędzia (`site_fonts_local`, `site_vendor_assets`) zdejmują je na życzenie, a `site_publish` wymienia to, co zostało, zanim użytkownik potwierdzi publikację. Czego nadal nie ma: twardej blokady — użytkownik może opublikować stronę mimo ostrzeżenia. To świadomy wybór (strona jest jego), ale przed sprzedażą warto rozstrzygnąć, czy wystarczy |
| Rozstrzygnięcie, czy wyznaczono inspektora ochrony danych | rejestr pozostawia pole puste |
| Ocena skutków dla ochrony danych | do rozważenia dla CZ-5 i CZ-6 ze względu na zakres materiałów przekazywanych agentowi |

---

*Koniec dokumentu. Rejestr czynności przetwarzania — etap 1B, 2026-09-21.*

---
*Danaco Nexus — Personal AI Workspace · etap 1B · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Kontakt: support@danaco-group.pl*
