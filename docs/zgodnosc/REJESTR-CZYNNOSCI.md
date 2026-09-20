# Danaco Nexus — Rejestr czynności przetwarzania

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Rodzaj** | Personal AI Workspace |
| **Producent** | Danaco Holding Group Sp. z o.o. |
| **Twórca** | Dariusz Naharnowicz |
| **Wersja** | etap 1B |
| **Status** | Deweloperski |
| **Data** | 2026-09-20 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Rejestr czynności przetwarzania danych osobowych — art. 30 ust. 1 RODO |
| **Klasa dokumentu** | Rejestr |
| **Odbiorcy** | administrator danych · radca prawny · organ nadzorczy |
| **Przeznaczenie** | Wykazuje czynności przetwarzania prowadzone przez produkt Danaco Nexus wraz z celem, podstawą prawną, kategoriami osób i danych, odbiorcami oraz terminem usunięcia. |
| **Zakres** | Portal produktowy, konta klientów, aplikacja Nexus, rozmowa głosowa, poczta, kalendarz i chmura osobista, pokaz bez konta, płatności, powiadomienia |
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
| Rozdzielenie kont | rozmowy, pliki, sesje, klucze urządzeń i kolekcje modułu badawczego mają kolumnę `owner_id` (`db.py:45-52`, `models/research.py:28`); zapytania ograniczają się do konta z sesji (`auth.wlasciciel`). Przestrzeń jednego konta wyznacza jego plan: 100 MB w okresie próbnym, 1 GB w planie Osobistym, 2 GB w Pro, 10 GB w Zespole (`platnosci/plany.py`, `platnosci/uprawnienia.py:limity_uzytkownika`, sprawdzenie `api/files.py`). Wyjątki opisuje rozdz. 5 |
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
| Kategorie danych | treść wiadomości do agenta, fragmenty i podglądy czytanych plików, wyniki narzędzi, historia bieżącej rozmowy, stałe polecenie systemowe; przy pracy z siecią także zapytanie wyszukiwania i adres strony |
| Czego nie obejmuje | pełna treść plików niepotrzebnych do zadania, baza wiedzy i indeks znaczeniowy, hasła i skróty haseł, tokeny sesji, klucze urządzeń, dane kont i rozliczeń |
| Miejsce w kodzie | `backend/nexus/agent/runner.py`, `backend/nexus/agent/prompt.py`; model domyślny i zapasowy — `backend/nexus/config.py` |
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
| Idempotencja zdarzeń rozliczeniowych i weryfikacja podpisu webhooka | `backend/nexus/platnosci/**` |

### CZ-14. Rozpoznawanie twarzy na zdjęciach użytkownika

| Pozycja | Treść |
|---|---|
| Cel | Porządkowanie zbioru zdjęć według osób na prośbę użytkownika (narzędzie `find_faces`) |
| Podstawa prawna | **do rozstrzygnięcia przed wejściem na rynek** — wizerunek twarzy przetwarzany w celu jednoznacznej identyfikacji to dane biometryczne (art. 9 ust. 1 RODO); potrzebna wyraźna zgoda (art. 9 ust. 2 lit. a) albo rezygnacja z funkcji |
| Kategorie osób | użytkownik oraz każda osoba widoczna na wgranych przez niego zdjęciach |
| Kategorie danych | położenie twarzy w kadrze, 512-wymiarowe wektory cech, przypisanie zdjęć do grup |
| Miejsce w kodzie | `backend/nexus/tools/studio.py` (`find_faces`), program `danaco-twarze-indeks` (InsightFace) |
| Odbiorcy | brak — model liczy na tym serwerze, nic nie wychodzi na zewnątrz |
| Przekazanie poza EOG | nie |
| Termin usunięcia | wynik jest plikiem rozmowy i podlega CZ-4; wektory nie są przechowywane poza tym plikiem |
| Zastrzeżenie licencyjne | modele InsightFace mają licencję **wyłącznie niekomercyjną**. Dopóki produkt nie jest sprzedawany, funkcja działa zgodnie z licencją; przed sprzedażą trzeba wymienić model na komercyjny albo uzyskać zgodę autorów |

## 5. Braki rejestru

| Brak | Skutek |
|---|---|
| Dane rejestrowe administratora | rejestr niekompletny w części identyfikacyjnej (art. 30 ust. 1 lit. a RODO) |
| Podstawa przetwarzania danych biometrycznych i licencja modeli twarzy | CZ-14 działa dziś na modelach niekomercyjnych i bez wyraźnej zgody. Obie sprawy trzeba zamknąć przed uruchomieniem sprzedaży: zgoda przy pierwszym użyciu funkcji oraz model o licencji komercyjnej |
| Rozdzielenie kont nie obejmuje chmury osobistej ani kalendarza | `CloudService` i `CalendarClient` logują się jednym kontem Nextcloud (`settings.chmura_user`, `chmura_token_file` — `cloud_service.py:96-103`, `calendar.py:105-112`). Pliki i wydarzenia są wspólne dla całej instalacji; rozdz. 3 polityki mówi więc o „magazynie tej instalacji”, a nie o magazynie konta |
| Umowy powierzenia z Anthropic, Google i Stripe | CZ-6, CZ-7 i CZ-11 nie mają udokumentowanej podstawy powierzenia |
| Kwalifikacja dostawcy serwera poczty portalu | rozdz. 3 tego rejestru i rozdz. 6 polityki opisują go jako odbiorcę technicznego. Jeżeli właściciel produktu uzna, że dostawca przechowuje wiadomości portalu na zlecenie Danaco, potrzebna będzie umowa z art. 28 RODO i zmiana obu dokumentów |
| Wskazanie instrumentu przekazania poza EOG | CZ-6, CZ-7, CZ-8 i CZ-11 opisują przekazanie ogólnie (art. 30 ust. 1 lit. e RODO) |
| Rozstrzygnięcie, czy rozmowa głosowa ma iść przez Google | dziś decyduje o tym obecność pliku z kluczem, a nie osobne ustawienie; wyłączenie wymaga usunięcia klucza albo zmiany `NEXUS_VOICE_GOOGLE_KEY_FILE`. Bez świadomej decyzji właściciela produktu nagranie głosu trafia do Google przy każdej wypowiedzi |
| Warunki usługi Google Cloud w zakresie wykorzystania przekazanych nagrań | rejestr nie rozstrzyga, co Google robi z nagraniem po rozpoznaniu; potrzebne potwierdzenie umową, tak jak przy Anthropic |
| Rozstrzygnięcie, czy wyznaczono inspektora ochrony danych | rejestr pozostawia pole puste |
| Ocena skutków dla ochrony danych | do rozważenia dla CZ-5 i CZ-6 ze względu na zakres materiałów przekazywanych agentowi |

---

*Koniec dokumentu. Rejestr czynności przetwarzania — etap 1B, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · etap 1B · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Kontakt: support@danaco-group.pl*
