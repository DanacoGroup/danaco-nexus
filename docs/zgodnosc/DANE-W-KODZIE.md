# Danaco Nexus — Mapa danych w kodzie

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
| **Tytuł** | Mapa danych w kodzie — dowód, że polityka prywatności opisuje stan faktyczny |
| **Klasa dokumentu** | Opis stanu wykonania |
| **Odbiorcy** | weryfikator · radca prawny · deweloper |
| **Przeznaczenie** | Wiąże każdą kategorię danych wymienioną w polityce prywatności z miejscem w kodzie, w którym te dane powstają, i odwrotnie — wykazuje, że żadna tabela z danymi osobowymi nie została w polityce pominięta. |
| **Zakres** | Tabele bazy danych, ciasteczka, pamięć przeglądarki (`localStorage` i `sessionStorage`), magazyn plików, baza wektorowa |
| **Poza zakresem** | Dzienniki systemowe serwera i kopie zapasowe — poza repozytorium |
| **Dokument nadrzędny** | [Zgodność prawna produktu](README.md) |
| **Zasada nadrzędna** | Kierunek sprawdzenia jest dwustronny: z polityki do kodu i z kodu do polityki. Tabela bez wiersza w tym dokumencie jest luką dokumentacji. |

## Spis treści

1. [Tabele bazy danych](#1-tabele-bazy-danych)
2. [Ciasteczka](#2-ciasteczka)
3. [Pamięć przeglądarki](#3-pamięć-przeglądarki)
4. [Dane poza bazą relacyjną](#4-dane-poza-bazą-relacyjną)
5. [Wyjście danych na zewnątrz](#5-wyjście-danych-na-zewnątrz)
6. [Wartości liczbowe przytoczone w dokumentach](#6-wartości-liczbowe-przytoczone-w-dokumentach)

---

## 1. Tabele bazy danych

Wykaz obejmuje wszystkie tabele deklarowane w repozytorium. Kolumna „Czynność”
odsyła do [rejestru czynności](REJESTR-CZYNNOSCI.md). Sprawdzenie kompletności:
`rg -n "__tablename__" backend/nexus/models backend/nexus/db.py backend/nexus/platnosci`.

Kolumnę `owner_id` mają `conversations`, `files`, `sessions`, `device_tokens`
(dopisywane przez `db.py:45-52`), `research_collections` (`models/research.py:28`) oraz obie
tabele kredytów. Czego ta kolumna nie obejmuje, mówi rozdz. 5 rejestru czynności.

| Tabela | Plik | Dane osobowe | Czynność |
|---|---|---|---|
| `portal_users` | `backend/nexus/models/portal.py` | tak | CZ-1 |
| `portal_sessions` | `backend/nexus/models/portal.py` | tak | CZ-2 |
| `portal_password_resets` | `backend/nexus/models/portal.py` | tak (powiązanie z kontem) | CZ-3 |
| `portal_email_confirmations` | `backend/nexus/models/portal.py` | tak (powiązanie z kontem) | CZ-3 |
| `portal_messages` | `backend/nexus/models/portal.py` | tak | CZ-4 |
| `portal_content` | `backend/nexus/models/portal.py` | nie — treść redakcyjna portalu | — |
| `grupy` | `backend/nexus/models/grupy.py` | tak (powiązanie z kontem założyciela) | do uzupełnienia przy przeglądzie |
| `grupy_czlonkowie` | `backend/nexus/models/grupy.py` | tak (powiązanie kont z grupą i rola) | do uzupełnienia przy przeglądzie |
| `grupy_zaproszenia` | `backend/nexus/models/grupy.py` | **tak — adres e-mail osoby zapraszanej**, także takiej, która nie ma konta | do uzupełnienia przy przeglądzie |
| `agenci_uzytkownika` | `backend/nexus/models/agenci.py` | tak — treść pracy (własne opisy agentów konta) | do uzupełnienia przy przeglądzie |
| `pliki_katalogi` | `backend/nexus/models/pliki.py` | tak — nazwy i opisy katalogów konta | do uzupełnienia przy przeglądzie |
| `ustawienia_konta` | `backend/nexus/models/ustawienia.py` | tak — preferencje konta | do uzupełnienia przy przeglądzie |
| `sessions` | `backend/nexus/db.py` | tak | CZ-2 |
| `settings` | `backend/nexus/db.py` | skrót hasła administratora | CZ-2 |
| `device_tokens` | `backend/nexus/db.py` | tak | CZ-9 |
| `conversations` | `backend/nexus/db.py` | tak — treść pracy | CZ-5 |
| `messages` | `backend/nexus/db.py` | tak — treść pracy | CZ-5 |
| `files` | `backend/nexus/db.py` | tak — metadane; treść w magazynie plików | CZ-5 |
| `runs` | `backend/nexus/db.py` | pośrednio — status i zużycie tokenów | CZ-5 |
| `run_events` | `backend/nexus/db.py` | tak — zdarzenia przebiegu | CZ-5 |
| `tool_calls` | `backend/nexus/db.py` | tak — dane wejściowe narzędzi | CZ-5 |
| `research_collections` | `backend/nexus/models/research.py` | tak — materiały użytkownika | CZ-5 |
| `research_sources` | `backend/nexus/models/research.py` | tak — materiały użytkownika | CZ-5 |
| `research_notes` | `backend/nexus/models/research.py` | tak — materiały użytkownika | CZ-5 |
| `research_reports` | `backend/nexus/models/research.py` | tak — materiały użytkownika | CZ-5 |
| `biuro_oczekujace` | `backend/nexus/models/biuro.py` | tak — treść wiadomości do wysłania | CZ-5 |
| `push_subscriptions` | `backend/nexus/models/push.py` | tak | CZ-8 |
| `platnosci_plany` | `backend/nexus/platnosci/model.py` | nie — katalog planów | — |
| `platnosci_subskrypcje` | `backend/nexus/platnosci/model.py` | tak | CZ-7 |
| `platnosci_faktury` | `backend/nexus/platnosci/model.py` | tak | CZ-7 |
| `platnosci_kupony` | `backend/nexus/platnosci/model.py` | nie — kody rabatowe | — |
| `platnosci_zdarzenia` | `backend/nexus/platnosci/model.py` | tak — ładunek zdarzenia Stripe | CZ-7 |
| `platnosci_kredyty` | `backend/nexus/platnosci/kredyty.py` | tak — saldo przypisane do konta | CZ-13 |
| `platnosci_kredyty_ruchy` | `backend/nexus/platnosci/kredyty.py` | tak — księga naliczeń konta | CZ-13 |

## 2. Ciasteczka

| Nazwa | Stała w kodzie | Plik | Czas życia | Zasięg |
|---|---|---|---|---|
| `nexus_session` | `COOKIE_NAME` | `backend/nexus/api/auth.py` | `settings.session_days` — domyślnie 30 dni | `/` |
| `nexus_portal` | `COOKIE_NAME` | `backend/nexus/portal/konta.py` | `PortalSettings.session_days` — domyślnie 14 dni; `BEZCZYNNOSC` 7 dni | `/` |
| `nexus_demo` | `COOKIE_NAME` | `backend/nexus/demo/sesje.py` | `Limity.zycie_minut` — 30 minut | `/api/demo` |

Wszystkie trzy ustawiane są z `httponly=True` i `samesite="lax"`, a flaga `secure`
pochodzi z `settings.cookie_secure` (domyślnie włączona) — nie z tego, czy połączenie jest
szyfrowane. Innych ciasteczek kod nie ustawia — sprawdzenie: `rg "set_cookie" backend/nexus`.

`nexus_session` i `nexus_portal` dostają `domain=settings.cookie_domain or None`
(`auth.py`, `konta.py`). Przy `NEXUS_COOKIE_DOMAIN=danaco-nexus.pl` (`.env.example`) zasięg
obejmuje domenę wraz z poddomenami, w tym `cloud.danaco-nexus.pl` — to jest mechanizm
logowania jednokrotnego do chmury. `nexus_demo` domeny nie ustawia; ogranicza go `COOKIE_PATH`.

## 3. Pamięć przeglądarki

| Klucz | Plik | Rodzaj | Zawartość |
|---|---|---|---|
| `nexus-theme` | `frontend/src/theme.ts` | `localStorage` | wybrany motyw |
| `nexus-voice` | `frontend/src/voice/VoiceMode.tsx` | `localStorage` | wybrany głos czytania |
| `nexus.research.preferencje` | `frontend/src/modules/research/index.tsx` | `localStorage` | rodzaj i głębokość badania |
| `dn-ladowanie` | `frontend/public/ladowanie/ladowanie.js:7`, zapis `:32-33` | `sessionStorage` | wartość `"1"` — ekran ładowania pokazał się już w tej sesji |
| `nexus-share` | `frontend/public/share-target.js:5`, zapis `:14-31`, odczyt i kasowanie `frontend/src/share.ts:14-28` | `Cache Storage` | pliki i tekst przekazane do Nexusa przez Web Share Target, do czasu odebrania przez aplikację |
| pamięć podręczna powłoki | `frontend/vite.config.ts:89-91` (Workbox) | `Cache Storage` | pliki statyczne aplikacji, bez danych użytkownika |

Innych wpisów klient nie zapisuje — sprawdzenie:
`rg --no-ignore "localStorage|sessionStorage|indexedDB|caches.open" frontend/src frontend/public`.
Bez członu `caches.open` wyszukiwanie pomija `nexus-share`, a to jedyny zasobnik przeglądarki,
w którym leżą pliki użytkownika — informacja o cookie (rozdz. 3) musi go wymieniać.
Przełącznik `--no-ignore` jest konieczny: katalog `frontend/public/ladowanie/` jest wyłączony
w `.gitignore:41`, bo skrypt pochodzi z pakietu marki i kopiuje go `frontend/scripts/zasoby.py:48`.
Bez tego przełącznika wyszukiwanie pomija `dn-ladowanie` i daje obraz niepełny.

Zapis `dn-ladowanie` wykonuje się przy każdym wejściu na stronę, bo skrypt jest wpięty
w `frontend/index.html:93` (`<script src="/ladowanie/ladowanie.js" data-raz="sesja">`).
Każdy odczyt i zapis jest w bloku `try`, więc blokada pamięci przeglądarki nie psuje aplikacji.

## 4. Dane poza bazą relacyjną

| Miejsce | Zawartość | Skąd |
|---|---|---|
| `data_dir/files` | treść przesłanych i wytworzonych plików | `backend/nexus/storage.py`, `file_service.py` |
| `data_dir/work` | pliki tymczasowe zadań narzędzi | `backend/nexus/tools/base.py` |
| kolekcja `nexus_documents` w bazie wektorowej | fragmenty dokumentów i ich osadzenia | `backend/nexus/knowledge.py` |
| katalog sesji pokazu | pliki gościa, kasowane po zakończeniu sesji | `backend/nexus/demo/sesje.py` |
| `claude_profile_dir` | profil Claude Code CLI wraz z tokenem konta | `backend/nexus/agent/runner.py` |
| plik konfiguracji poczty — osobny dla każdego konta użytkownika (`poczta/<konto>.json`; konto administratora zostaje przy pliku sprzed podziału) | login, hasło i adresy serwerów skrzynki, w postaci czytelnej, prawa 600 | `backend/nexus/mail.py` (`config_path`, `save_accounts`), `settings.poczta_config_file` |
| chmura osobista Nextcloud (`chmura_url`, domyślnie `http://127.0.0.1:8940`) | pliki i foldery użytkownika wraz z treścią | `backend/nexus/cloud_service.py`, `backend/nexus/config.py:49-52` |
| kalendarze CalDAV tej samej chmury (`/remote.php/dav/calendars/<user>/`) | wydarzenia wraz z terminem, opisem, miejscem i uczestnikami | `backend/nexus/calendar.py` (`CalendarClient`) |
| `chmura_token_file` | hasło aplikacji do konta Nextcloud (chmura i kalendarz) | `backend/nexus/config.py` (`chmura_token_file`) |
| `voice_google_key_file` | klucz API Google Cloud dla mowy; jego obecność włącza wysyłkę nagrań do Google | `backend/nexus/config.py:57`, `backend/nexus/voice_google.py` (`available`) |
| katalog roboczy `work_dir` — nagranie rozmowy głosowej | plik nagrania z mikrofonu, kasowany po rozpoznaniu (`NamedTemporaryFile`) | `backend/nexus/api/voice.py:59-73` |

## 5. Wyjście danych na zewnątrz

| Kierunek | Co wychodzi | Kiedy | Plik |
|---|---|---|---|
| Anthropic | treść bieżącego zadania, fragmenty plików, wyniki narzędzi, polecenie systemowe | przy każdym poleceniu dla agenta | `backend/nexus/agent/runner.py` |
| Anthropic | zapytanie wyszukiwania i adres strony | gdy agent użyje `WebSearch` lub `WebFetch` | `backend/nexus/agent/runner.py` (`WEB_TOOLS`) |
| Google Cloud — Speech-to-Text | nagranie z mikrofonu (FFmpeg przekodowuje je na 16 kHz mono PCM) i kod języka; punkt końcowy `https://speech.googleapis.com/v1/speech:recognize` | przy **każdej** transkrypcji rozmowy głosowej, o ile `GoogleSpeech.available()` znajdzie klucz; model lokalny Whisper jest zapasem | `backend/nexus/voice.py:97-99`, `backend/nexus/voice_google.py:24` |
| Google Cloud — Text-to-Speech | tekst, który agent ma przeczytać na głos; punkt końcowy `https://texttospeech.googleapis.com/v1` | gdy wybrany głos ma przedrostek `google:` (takie są wszystkie głosy chmurowe na liście) | `backend/nexus/voice.py:179-181`, `backend/nexus/voice_google.py:23` |
| wyszukiwarka i serwisy naukowe | zapytanie i adres strony, bezpośrednio z serwera Danaco | zadanie badawcze | `backend/nexus/research/web.py` |
| Stripe | adres poczty i nazwa klienta, plan, dane płatności podane w kasie | zakup i obsługa planu oraz jednorazowy zakup pakietu kredytów | `backend/nexus/platnosci/klient.py`, `backend/nexus/platnosci/pakiety.py` |
| dostawca powiadomień przeglądarki | punkt odbioru i zaszyfrowana treść powiadomienia | wysyłka powiadomienia | `backend/nexus/push_service.py` |
| serwer poczty użytkownika (IMAP i SMTP) | treść czytanych i wysyłanych wiadomości wraz z załącznikami; wysyłka po zatwierdzeniu działania | praca w module Poczta | `backend/nexus/mail.py` |
| serwer poczty portalu (SMTP) | adres odbiorcy, temat i treść wiadomości o odzyskaniu hasła, zmianie hasła i usunięciu konta | gdy `NEXUS_PORTAL_MAIL_NADAWCA=smtp` i konto poczty jest skonfigurowane; inaczej `NadawcaDoDziennika` zapisuje wiadomość w dzienniku i nic nie wysyła | `backend/nexus/portal/poczta_portalu.py` (`NadawcaSmtp`, `nadawca`) |

Stan klucza mowy na tym serwerze: plik `dane/app/google-api-key` istnieje (40 B, prawa 600),
a `.env.example` ustawia go domyślnie — czyli kierunek „Google Cloud” jest aktywny, nie hipotetyczny.

**Czego w tej tabeli nie ma i dlaczego.** Chmura osobista i kalendarz CalDAV korzystają
z `settings.chmura_url`, domyślnie `http://127.0.0.1:8940` (`backend/nexus/config.py:49`), czyli
z Nextcloud działającego na tym samym serwerze. To nie jest wyjście na zewnątrz i rozdział 4
opisuje je jako magazyn własny. Kierunkiem zewnętrznym stają się dopiero wtedy, gdy
`NEXUS_CHMURA_URL` wskaże obcy serwer — wtedy trzeba je dopisać tutaj i do rejestru czynności.

Klient nie wczytuje żadnego skryptu ani kroju z serwera zewnętrznego — kroje i tła są
serwowane z katalogu aplikacji, co opisuje `design-system/WDROZENIE.md`, rozdz. 5. Nie dotyczy
to stron publikowanych modułem Twórca stron pod `/s/<adres>`: `SITE_CSP`
(`backend/nexus/api/modules/strony.py:35-44`) dopuszcza w nich skrypty z unpkg.com,
cdn.jsdelivr.net, cdnjs.cloudflare.com, esm.sh i cdn.tailwindcss.com oraz `connect-src https:`.
Treść tych stron układa użytkownik i to on za nią odpowiada.

## 6. Wartości liczbowe przytoczone w dokumentach

| Wartość w dokumencie | Stała | Plik |
|---|---|---|
| sesja aplikacji 30 dni | `session_days` | `backend/nexus/config.py` |
| sesja portalu 14 dni | `SESSION_DAYS` (domyślna) | `backend/nexus/portal/ustawienia.py` |
| bezczynność 7 dni | `BEZCZYNNOSC` | `backend/nexus/portal/konta.py` |
| token odzyskiwania 30 minut | `RESET_TTL_MINUTES` (domyślna) | `backend/nexus/portal/ustawienia.py` |
| hasło co najmniej 12 znaków | `MIN_HASLO` | `backend/nexus/portal/konta.py` |
| pokaz: 6 wiadomości, 4 pliki po 8 MB, 500 znaków, 30 minut | `Limity` | `backend/nexus/demo/sesje.py` |
| plik do 2 GB | `upload_limit_mb` | `backend/nexus/config.py` |
| przestrzeń konta według planu: 100 MB w okresie próbnym, 1 GB Osobisty, 2 GB Pro, 10 GB Grupa | `probny_przestrzen_mb`, `przestrzen_mb` | `backend/nexus/platnosci/plany.py`, sprawdzenie `backend/nexus/api/files.py` przez `limity_uzytkownika` |
| token potwierdzenia adresu 24 godziny | `POTWIERDZENIE_WAZNE` | `backend/nexus/portal/konta.py` |
| kredyty: 1 za 1000 żetonów wejścia, 5 za 1000 wyjścia, minimum 1 za przebieg | `DOMYSLNIE_1K_WEJSCIE`, `DOMYSLNIE_1K_WYJSCIE`, `DOMYSLNIE_MINIMUM` | `backend/nexus/platnosci/kredyty.py` |
| przydział kredytów w planie: 2 000 / 20 000 / 60 000 | `kredyty_okresowo` | `backend/nexus/platnosci/plany.py` |
| okres próbny 7 dni w planie Osobistym | `okres_probny_dni` | `backend/nexus/platnosci/plany.py` |
| zadanie do 2 godzin | `run_timeout_minutes` | `backend/nexus/config.py` |
| model domyślny i zapasowy | `claude_model`, `claude_fallback_model` | `backend/nexus/config.py` |

---

*Koniec dokumentu. Mapa danych w kodzie — etap 1B, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · etap 1B · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Kontakt: support@danaco-group.pl*
