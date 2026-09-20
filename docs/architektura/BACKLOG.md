# Danaco Nexus — Backlog architektoniczny

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Rodzaj** | Personal AI Workspace |
| **Opis** | Osobisty agent AI działający na serwerze Danaco: rozmowa z modelem Claude przez Claude Code CLI, narzędzia na plikach, OCR, obrazy, poczta, kalendarz, chmura osobista, baza wiedzy, moduł Kod, klienci PWA / Android / Windows / rozszerzenie przeglądarki. |
| **Producent** | Danaco Holding Group Sp. z o.o. |
| **Twórca** | Dariusz Naharnowicz |
| **Wersja** | 1.0 |
| **Status** | Deweloperski |
| **Data** | 2026-09-20 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Backlog architektoniczny — zadania wdrożenia architektury docelowej z uzasadnieniem, zakresem plików, szacunkiem, zależnościami i priorytetem |
| **Klasa dokumentu** | Rejestr zadań |
| **Odbiorcy** | zespół backendu · zespół klientów · administrator serwera · właściciel produktu |
| **Przeznaczenie** | Rozbicie etapów [Roadmapy](ROADMAPA.md) na zadania nadające się do podjęcia bez dopytywania. Każde zadanie ma nazwane pliki i powód istnienia. |
| **Zakres** | 64 zadania w ośmiu grupach: siedem odpowiada etapom roadmapy, ósma zbiera pozycje niezależne |
| **Poza zakresem** | Zadania funkcjonalne (nowe moduły, nowe narzędzia) — te prowadzi [`docs/PLAN-ROZWOJU.md`](../PLAN-ROZWOJU.md); uzasadnienia architektoniczne — [Architektura docelowa](ARCHITEKTURA-DOCELOWA.md) |
| **Dokument nadrzędny** | [Roadmapa](ROADMAPA.md) |
| **Dokumenty powiązane** | [Stan obecny](STAN-OBECNY.md) · [Architektura docelowa](ARCHITEKTURA-DOCELOWA.md) · [README pakietu](README.md) |
| **Źródła normatywne** | odsyłacze `plik:linia` w kolumnie „Zakres plików” wskazują miejsca, które zadanie zmienia |
| **Zasada nadrzędna** | Identyfikatorem zadania jest jego nazwa opisowa, nie kod literowo-numeryczny. Nazwa ma mówić, czego zadanie dotyczy. |

## Spis treści

1. [Jak czytać tabele](#1-jak-czytać-tabele)
2. [Grupa: fundament jakości i odtwarzalność](#2-grupa-fundament-jakości-i-odtwarzalność)
3. [Grupa: odzyskanie stanu z pamięci procesu](#3-grupa-odzyskanie-stanu-z-pamięci-procesu)
4. [Grupa: obserwowalność](#4-grupa-obserwowalność)
5. [Grupa: skalowanie poziome](#5-grupa-skalowanie-poziome)
6. [Grupa: magazyn plików i cykl życia danych](#6-grupa-magazyn-plików-i-cykl-życia-danych)
7. [Grupa: hartowanie i audyt](#7-grupa-hartowanie-i-audyt)
8. [Grupa: praca wielomaszynowa](#8-grupa-praca-wielomaszynowa)
9. [Zadania poza etapami](#9-zadania-poza-etapami)
10. [Podsumowanie nakładu](#10-podsumowanie-nakładu)

---

## 1. Jak czytać tabele

| Kolumna | Znaczenie |
|---|---|
| **Identyfikator** | nazwa opisowa zadania, używana w zależnościach i w opisie zmiany |
| **Tytuł** | co zadanie robi, w jednym zdaniu |
| **Uzasadnienie** | ograniczenie ze [Stanu obecnego](STAN-OBECNY.md#20-ograniczenia-stanu-obecnego) albo kryterium z [Architektury docelowej](ARCHITEKTURA-DOCELOWA.md#17-kryteria-odbioru-architektury), które zadanie usuwa |
| **Zakres plików** | pliki i miejsca, których zadanie dotyka |
| **Szacunek** | dni pracy jednej osoby, przedział |
| **Zależności** | identyfikatory zadań, które muszą być gotowe wcześniej |
| **Priorytet** | krytyczny · wysoki · średni · niski |

Priorytet oznacza pilność, nie trudność. „Krytyczny” to zadanie, którego brak grozi utratą
danych albo cichą degradacją bez możliwości wykrycia.

---

## 2. Grupa: fundament jakości i odtwarzalność

| Identyfikator | Tytuł | Uzasadnienie | Zakres plików | Szacunek | Zależności | Priorytet |
|---|---|---|---|---|---|---|
| `kopia-bazy` | Kopia bazowa PostgreSQL z ciągłą archiwizacją dziennika | Brak jakichkolwiek kopii zapasowych; awaria dysku = utrata rozmów, plików i zadań | `deploy/` (nowy skrypt i jednostka `.timer`), `deploy/systemd/` | 3–4 d | — | krytyczny — **wykonane 2026-09-20 (`deploy/kopia-zapasowa.sh`, `danaco-nexus-kopia.timer`); archiwizacja dziennika WAL do zrobienia** |
| `kopia-plikow` | Kopia katalogu plików i sekretów | `dane/app/files`, `dane/claude-profil/oauth-token`, `dane/app/poczta.json`, `dane/app/vapid` nie są nigdzie kopiowane | `deploy/`, `backend/nexus/config.py:97-100` (ścieżki) | 2–3 d | — | krytyczny — **wykonane 2026-09-20 — pliki, sekrety i profil CLI w kopii dobowej** |
| `kopia-qdrant` | Migawka kolekcji Qdrant | Wektory są odtwarzalne, ale odtworzenie trwa; migawka skraca RTO | `deploy/qdrant/`, `backend/nexus/knowledge.py:92-123` | 1–2 d | `kopia-bazy` | wysoki — **wykonane 2026-09-20 — katalog `storage` w kopii dobowej** |
| `procedura-odtworzenia` | Procedura odtworzenia i ćwiczenie na osobnej maszynie | Kopia bez przećwiczonego odtworzenia nie jest kopią | `docs/architektura/` (procedura), `deploy/` | 2–3 d | `kopia-bazy`, `kopia-plikow`, `kopia-qdrant` | krytyczny — **procedura w README; ćwiczenie odtworzenia na osobnej maszynie do zrobienia** |
| `migracje-schematu` | Wprowadzenie migracji wersjonowanych (Alembic) | `create_all` + `ALTER TABLE ADD COLUMN` nie obsługuje zmiany typu, usunięcia i wycofania — `backend/nexus/db.py:243-260` | `backend/nexus/db.py:42-44,243-260`, `backend/nexus/models/__init__.py:14-21`, nowy katalog migracji | 4–6 d | `kopia-bazy` | krytyczny |
| `migracja-jako-krok-wdrozenia` | Wyjęcie tworzenia schematu ze startu procesów | Schemat tworzą dziś równolegle API i proces roboczy — `backend/nexus/api/app.py:72`, `backend/nexus/worker.py:101` | `backend/nexus/api/app.py:68-89`, `backend/nexus/worker.py:99-101`, `deploy/instalacja.sh` | 1–2 d | `migracje-schematu` | wysoki |
| `potok-bramek` | Automatyczne uruchamianie bramek jakości przy każdej zmianie | Bramki istnieją jako polecenia, nic ich nie wyzwala — `backend/pyproject.toml:40-59`, `frontend/package.json:9-14` | nowa definicja potoku, `deploy/` | 3–4 d | — | wysoki |
| `srodowisko-probne` | Druga instalacja na tym samym serwerze, z własnym klastrem i portem | Nie ma gdzie ćwiczyć migracji i wdrożeń przed dotknięciem danych właściciela | `deploy/instalacja.sh:19-33`, `deploy/systemd/` | 3–4 d | `migracje-schematu` | wysoki |
| `aktualizacja-dokumentacji-rdzenia` | Doprowadzenie `README.md` i `CHANGELOG.md` do stanu kodu | `README.md:24-58` i `CHANGELOG.md:17` mówią o 22 narzędziach, w kodzie jest 59; opis architektury nie wspomina o modułach ani klientach | `README.md`, `CHANGELOG.md` | 1–2 d | — | średni |

---

## 3. Grupa: odzyskanie stanu z pamięci procesu

| Identyfikator | Tytuł | Uzasadnienie | Zakres plików | Szacunek | Zależności | Priorytet |
|---|---|---|---|---|---|---|
| `zadania-modulowe-w-bazie` | Tabela `module_jobs` zamiast rejestru w pamięci | Zadania obróbki obrazów i tłumaczeń giną przy restarcie API — `backend/nexus/tworczy/zadania.py:1-6,57-78` | `backend/nexus/tworczy/zadania.py`, nowy `backend/nexus/models/tworczy.py`, `backend/nexus/api/modules/obrazy.py:69-148`, `backend/nexus/api/modules/tlumacz.py:77-97` | 5–7 d | `migracje-schematu` | krytyczny |
| `proces-media` | Wydzielenie wykonania zadań modułowych do osobnego procesu | Obróbka obrazu blokuje pętlę zdarzeń obsługującą strumienie | nowy `backend/nexus/media_worker.py`, `deploy/systemd/`, `backend/nexus/tworczy/zadania.py` | 4–5 d | `zadania-modulowe-w-bazie` | wysoki |
| `limit-logowan-w-valkey` | Przeniesienie licznika nieudanych logowań do Valkey | Licznik w pamięci procesu znika po restarcie i nie działa przy wielu replikach — `backend/nexus/api/auth.py:60-83` | `backend/nexus/api/auth.py:60-83,148-178`, `backend/nexus/api/app.py:76` | 2–3 d | — | wysoki |
| `proces-notifier` | Wydzielenie nasłuchu `nexus:run-finished` z procesu API | Nasłuch działa w każdej replice; przy dwóch replikach powiadomienie poszłoby dwa razy — `backend/nexus/api/modules/push.py:50-54` | nowy `backend/nexus/notifier.py`, `backend/nexus/api/modules/push.py:35-59`, `backend/nexus/push_service.py`, `deploy/systemd/` | 3–4 d | — | wysoki |
| `wybor-jednego-notifiera` | Dzierżawa wyznaczająca jeden aktywny proces powiadomień | Bez wyboru dwie instancje `notifier` powielą powiadomienia | `backend/nexus/notifier.py`, `backend/nexus/events.py` | 2 d | `proces-notifier` | wysoki |
| `sumy-instalatorow-przy-publikacji` | Liczenie sum kontrolnych instalatorów przy publikacji | Pamięć podręczna sum żyje w procesie API — `backend/nexus/api/modules/pobieranie.py:27,37-47` | `backend/nexus/api/modules/pobieranie.py:27-63`, `deploy/android/buduj-apk.sh` | 1–2 d | — | niski |
| `gotowosc-repliki` | Punkt „gotów do ruchu” sprawdzający bazę i Valkey | `GET /api/health` nie sprawdza zależności — `backend/nexus/api/app.py:106-108` | `backend/nexus/api/app.py:106-108` | 1–2 d | — | średni |

---

## 4. Grupa: obserwowalność

| Identyfikator | Tytuł | Uzasadnienie | Zakres plików | Szacunek | Zależności | Priorytet |
|---|---|---|---|---|---|---|
| `dzienniki-strukturalne` | Dzienniki w formacie JSON z polami stałymi | Format tekstowy uniemożliwia filtrowanie po `run_id` — `backend/nexus/logging_setup.py:9-22` | `backend/nexus/logging_setup.py` | 2–3 d | — | wysoki |
| `identyfikator-zadania-w-kontekscie` | Przenoszenie `run_id`, `conversation_id` i identyfikatora żądania do kontekstu dziennika | Bez korelacji nie da się złożyć historii jednego przebiegu z trzech procesów | `backend/nexus/logging_setup.py`, `backend/nexus/agent/runner.py:683-693`, `backend/nexus/mcp_server.py:70-79`, `backend/nexus/api/app.py:54-61` | 3–4 d | `dzienniki-strukturalne` | wysoki |
| `metryki-podstawowe` | Punkt `/metrics` na porcie wewnętrznym z metrykami kolejki i przebiegów | Brak jakichkolwiek metryk; planowanie zdolności odbywa się na wyczucie | nowy moduł metryk, `backend/nexus/api/app.py:91-104`, `deploy/systemd/danaco-nexus-api.service` | 4–5 d | — | wysoki |
| `metryki-narzedzi` | Metryki wywołań narzędzi: liczba, czas, błędy, pliki wynikowe | `tool_calls` zawiera dane, nikt ich nie agreguje — `backend/nexus/db.py:213-227` | moduł metryk, `backend/nexus/mcp_server.py:118-148` | 2–3 d | `metryki-podstawowe` | średni |
| `metryka-utraty-sesji` | Licznik przebiegów, które nie wznowiły sesji CLI i użyły streszczenia | Najgroźniejsza cicha degradacja: kontekst ginie, a system nie zgłasza błędu — `backend/nexus/agent/runner.py:704-752` | `backend/nexus/agent/runner.py:704-719`, moduł metryk | 1–2 d | `metryki-podstawowe` | krytyczny |
| `slady-rozproszone` | Ślady OpenTelemetry korelowane po `run_id` | Przebieg przechodzi przez trzy procesy; dziś nie da się go prześledzić | `backend/nexus/api/app.py`, `backend/nexus/worker.py`, `backend/nexus/agent/runner.py`, `backend/nexus/mcp_server.py` | 5–7 d | `identyfikator-zadania-w-kontekscie` | średni |
| `alarmy` | Alarmy dla kolejki, błędów, niedostępności usług i limitu konta Claude | Awaria usługi pomocniczej jest dziś widoczna dopiero w objawach | konfiguracja alarmów, `backend/nexus/doctor.py:136-234`, `backend/nexus/agent/runner.py:135` | 3–4 d | `metryki-podstawowe` | wysoki |
| `przeglad-dziennikow-pod-katem-danych` | Sprawdzenie, czy dzienniki nie zawierają treści rozmów i sekretów | Wymóg odbioru etapu 3; dziś brak świadomej kontroli | `backend/nexus/logging_setup.py`, `backend/nexus/agent/runner.py:665`, `backend/nexus/mcp_server.py:134` | 1–2 d | `dzienniki-strukturalne` | średni |

---

## 5. Grupa: skalowanie poziome

| Identyfikator | Tytuł | Uzasadnienie | Zakres plików | Szacunek | Zależności | Priorytet |
|---|---|---|---|---|---|---|
| `rejestr-gniazd-w-valkey` | Rejestr połączeń komputerów z dzierżawą zamiast słownika w pamięci | Wykrycie podwójnego połączenia działa tylko w jednym procesie — `backend/nexus/api/modules/pulpit.py:53-55` | `backend/nexus/api/modules/pulpit.py:53-160`, `backend/nexus/pulpit.py:31-54` | 4–5 d | `limit-logowan-w-valkey` | wysoki |
| `proces-mowy` | Wydzielenie rozpoznawania i syntezy mowy z procesu API | Modele mowy zajmują pamięć procesu API i konkurują z obsługą strumieni — `backend/nexus/api/app.py:78-80`, `backend/nexus/voice.py:1-7` | nowy proces, `backend/nexus/api/voice.py:33-88`, `backend/nexus/voice.py`, `deploy/systemd/` | 5–7 d | `gotowosc-repliki` | wysoki |
| `proces-indeksujacy` | Wydzielenie osadzeń i operacji Qdrant do procesu `indexer` | Model osadzeń ładuje się w każdym procesie, który go dotknie — `backend/nexus/knowledge.py:61-79` | nowy proces, `backend/nexus/knowledge.py`, `backend/nexus/research/store.py`, `backend/nexus/tools/knowledge.py` | 5–7 d | `gotowosc-repliki` | wysoki |
| `dwie-repliki-api` | Uruchomienie drugiej repliki API za Caddy | Cały ruch obsługuje jedna pętla zdarzeń — `deploy/systemd/danaco-nexus-api.service:18` | `deploy/systemd/danaco-nexus-api.service`, `deploy/caddy/danaco-nexus.caddy:30-37` | 2–3 d | `limit-logowan-w-valkey`, `proces-notifier`, `rejestr-gniazd-w-valkey`, `zadania-modulowe-w-bazie` | wysoki |
| `pula-polaczen-bazy` | Policzenie i ustawienie puli połączeń z uwzględnieniem serwerów MCP | Każdy serwer MCP otwiera własne połączenie — `backend/nexus/mcp_server.py:67`; przy większej równoległości limit bazy zostanie przekroczony | `backend/nexus/db.py:233-241`, `deploy/postgres/`, `backend/nexus/config.py:37` | 2–3 d | `dwie-repliki-api` | wysoki |
| `drugi-proces-roboczy` | Uruchomienie drugiego procesu roboczego | Podwojenie przepustowości bez zmian w kodzie kolejki — `backend/nexus/worker.py:35-50` | `deploy/systemd/danaco-nexus-worker.service` | 1 d | `pula-polaczen-bazy`, `metryka-utraty-sesji` | średni |
| `limit-strumieni-na-sesje` | Ograniczenie liczby równoległych strumieni SSE na sesję | Brak wstecznego ciśnienia; jedno aktywne zadanie może zdominować ruch — `backend/nexus/api/runs.py:74-119` | `backend/nexus/api/runs.py`, `backend/nexus/api/auth.py` | 2 d | `dwie-repliki-api` | niski |

---

## 6. Grupa: magazyn plików i cykl życia danych

| Identyfikator | Tytuł | Uzasadnienie | Zakres plików | Szacunek | Zależności | Priorytet |
|---|---|---|---|---|---|---|
| `interfejs-magazynu` | Wydzielenie interfejsu magazynu z dzisiejszej implementacji dyskowej | Warunek podmiany; dziś klasa jest jednocześnie interfejsem i implementacją — `backend/nexus/storage.py:56-109` | `backend/nexus/storage.py`, `backend/nexus/file_service.py`, `backend/nexus/api/files.py` | 2–3 d | — | wysoki |
| `magazyn-obiektowy` | Implementacja magazynu zgodnego z S3 i jego uruchomienie | Pliki na dysku lokalnym wiążą API i proces roboczy z jedną maszyną — `backend/nexus/storage.py:56-72` | `backend/nexus/storage.py`, `backend/nexus/config.py`, `deploy/systemd/`, `.env.example` | 6–8 d | `interfejs-magazynu` | wysoki |
| `migracja-plikow` | Przeniesienie istniejących plików z weryfikacją SHA-256 | Migracja bez weryfikacji jest nie do przyjęcia; suma jest już w bazie — `backend/nexus/db.py:173` | jednorazowy skrypt w `deploy/`, `backend/nexus/storage.py` | 3–4 d | `magazyn-obiektowy`, `kopia-plikow` | wysoki |
| `pliki-robocze-narzedzi` | Pobieranie i odsyłanie plików narzędzi przez interfejs magazynu | Narzędzia dostają dziś ścieżkę na dysku — `backend/nexus/tools/base.py:106-112`, `backend/nexus/file_service.py:23-67` | `backend/nexus/tools/base.py`, `backend/nexus/file_service.py` | 3–4 d | `magazyn-obiektowy` | wysoki |
| `miniatury-w-magazynie` | Przeniesienie pamięci podręcznej miniatur do magazynu | Miniatury są liczone i trzymane na dysku repliki — `backend/nexus/api/files.py:129-143` | `backend/nexus/api/files.py` | 1–2 d | `magazyn-obiektowy` | średni |
| `priorytety-kolejki` | Priorytet zadania w wyborze z kolejki | Zadanie głosowe czeka za sześciogodzinnym badaniem — `backend/nexus/worker.py:35-50`, `backend/nexus/config.py:117` | `backend/nexus/worker.py:35-50`, `backend/nexus/db.py:180-197`, `backend/nexus/api/conversations.py:310-316` | 3–4 d | `migracje-schematu` | wysoki |
| `ponowienia-zadan` | Ponowienia dla błędów przejściowych i kolejka martwych zadań | Każdy błąd kończy zadanie; awaria startu CLI wygląda jak błąd użytkownika — `backend/nexus/agent/runner.py:663-668`, `runner.py:118-125` | `backend/nexus/worker.py`, `backend/nexus/agent/runner.py:663-668`, `backend/nexus/db.py:180-197` | 4–5 d | `priorytety-kolejki` | wysoki |
| `widocznosc-kolejki` | Widok głębokości kolejki, wieku zadań i podziału na pule | Dziś widać tylko listę aktywnych — `backend/nexus/api/modules/w_toku.py:19-58` | `backend/nexus/api/modules/w_toku.py`, `backend/nexus/api/modules/agenci.py:113-200`, moduł metryk | 2–3 d | `metryki-podstawowe` | średni |
| `proces-porzadkow` | Proces egzekwujący cykl życia danych | Nic nie usuwa starych zdarzeń, wygasłych sesji, plików bez rozmowy i katalogów roboczych | nowy proces, `backend/nexus/db.py:93-103,200-210`, `backend/nexus/config.py:107-110`, `deploy/systemd/` | 4–5 d | `magazyn-obiektowy` | średni |
| `limit-zadan-w-tle` | Ograniczenie liczby zadań zlecanych przez moduł Agenci | Nic nie ogranicza liczby zadań zlecanych naraz — `backend/nexus/api/modules/agenci.py:202` | `backend/nexus/api/modules/agenci.py:202-224`, licznik w Valkey | 2 d | `limit-logowan-w-valkey` | średni |

---

## 7. Grupa: hartowanie i audyt

| Identyfikator | Tytuł | Uzasadnienie | Zakres plików | Szacunek | Zależności | Priorytet |
|---|---|---|---|---|---|---|
| `dziennik-audytowy` | Tabela audytu i zapis działań zmieniających stan | Brak rozliczalności działań wykonywanych w imieniu użytkownika | nowy `backend/nexus/models/audyt.py`, `backend/nexus/api/modules/urzadzenia.py:56,68`, `backend/nexus/api/modules/poczta.py:440`, `backend/nexus/api/modules/kalendarz.py:139-167`, `backend/nexus/api/conversations.py:113-140`, `backend/nexus/api/modules/kod.py:258` | 5–6 d | `migracje-schematu` | wysoki |
| `termin-klucza-urzadzenia` | Termin ważności i widoczne ostatnie użycie klucza urządzenia | Klucz jest bezterminowy — `backend/nexus/db.py:106-120` | `backend/nexus/db.py:106-120`, `backend/nexus/api/auth.py:96-115`, `backend/nexus/api/modules/urzadzenia.py`, `frontend/src/modules/urzadzenia/` | 3–4 d | `migracje-schematu` | wysoki |
| `zakres-klucza-urzadzenia` | Zakres uprawnień klucza odwzorowany na rodzaj urządzenia | Klucz rozszerzenia daje dziś ten sam dostęp co sesja przeglądarki — `backend/nexus/api/auth.py:118-124` | `backend/nexus/api/auth.py:96-139`, `backend/nexus/api/modules/__init__.py:16-26`, wszystkie moduły API | 5–7 d | `termin-klucza-urzadzenia`, `dziennik-audytowy` | wysoki |
| `drugi-skladnik-logowania` | Drugi składnik uwierzytelniania administratora | Dostęp do wszystkich danych właściciela chroni dziś samo hasło — `backend/nexus/api/auth.py:142-205` | `backend/nexus/api/auth.py`, `backend/nexus/cli.py:48-58`, `frontend/src/components/Login.tsx` | 5–7 d | `dziennik-audytowy` | wysoki |
| `ograniczenie-czestosci-api` | Ograniczenie częstości żądań dla całego API | Limit obejmuje dziś wyłącznie logowanie — `backend/nexus/api/auth.py:60-83` | `backend/nexus/api/app.py:99`, nowe middleware, Valkey | 3–4 d | `limit-logowan-w-valkey` | wysoki |
| `limity-zasobow-narzedzi` | Uruchamianie programów zewnętrznych z limitem pamięci, procesora i czasu | Jedno wywołanie powiększania obrazu może wysycić maszynę — `backend/nexus/tools/base.py:133-173` | `backend/nexus/tools/base.py:133-173`, `deploy/systemd/` | 4–5 d | — | wysoki |
| `izolacja-plikowa-narzedzi` | Ograniczenie widoczności systemu plików do katalogu roboczego przebiegu | Narzędzia dziedziczą uprawnienia procesu serwera MCP — `backend/nexus/tools/base.py:146-155` | `backend/nexus/tools/base.py`, `backend/nexus/mcp_server.py:93-137` | 5–7 d | `limity-zasobow-narzedzi` | średni |
| `tryb-code-bez-sieci` | Odcięcie sieci dla przebiegów w trybie `code` | Reguły blokujące są „w dobrej wierze”, nie piaskownicą — `backend/nexus/agent/runner.py:89-115` | `backend/nexus/agent/runner.py:89-115,754-780`, `deploy/systemd/` | 4–6 d | `limity-zasobow-narzedzi` | średni |
| `twardy-limit-podagentow` | Egzekwowanie limitu równoległych podagentów po stronie serwera | Limit jest dziś prośbą w prompcie — `backend/nexus/agent/prompt.py:71-72`, `backend/nexus/config.py:116` | `backend/nexus/agent/runner.py:956-1056`, `backend/nexus/config.py:116` | 3–4 d | `metryki-narzedzi` | średni |
| `przeglad-uprawnien-rozszerzenia` | Zawężenie uprawnień rozszerzenia przeglądarki | `host_permissions: ["<all_urls>"]` przy MV3 to najszersze możliwe uprawnienie — `extension/manifest.json:26-27` | `extension/manifest.json`, `extension/src/tlo.ts:28-39` | 2–3 d | — | średni |
| `szyfrowanie-w-spoczynku` | Szyfrowanie danych w spoczynku dla bazy, plików i kopii | Dane osobiste i poczta leżą bez szyfrowania | `deploy/`, `deploy/postgres/`, magazyn obiektowy | 4–6 d | `magazyn-obiektowy`, `kopia-bazy` | średni |
| `skanowanie-zaleznosci` | Regularne sprawdzanie zależności Pythona i Node pod kątem podatności | Brak jakiejkolwiek kontroli zależności | potok bramek, `backend/pyproject.toml`, `frontend/package.json`, `desktop/package.json`, `extension/package.json` | 2–3 d | `potok-bramek` | średni |

---

## 8. Grupa: praca wielomaszynowa

| Identyfikator | Tytuł | Uzasadnienie | Zakres plików | Szacunek | Zależności | Priorytet |
|---|---|---|---|---|---|---|
| `pule-sesji` | Powinowactwo rozmowy do puli procesów roboczych | Bez powinowactwa kolejny przebieg rozmowy może trafić na proces bez pliku sesji i cicho stracić kontekst — `backend/nexus/agent/runner.py:209-214,704-719` | `backend/nexus/worker.py:35-60`, `backend/nexus/db.py:180-197`, `backend/nexus/config.py` | 5–7 d | `metryka-utraty-sesji`, `migracje-schematu` | wysoki |
| `migawki-sesji-cli` | Zapis i odtwarzanie plików sesji CLI z magazynu | Utrata maszyny oznacza utratę kontekstu wszystkich rozmów | `backend/nexus/agent/runner.py:209-214,704-752`, `backend/nexus/storage.py` | 4–5 d | `magazyn-obiektowy`, `pule-sesji` | wysoki |
| `wdrozenie-kroczace` | Wdrożenie replik API po kolei z kontrolą gotowości | Dziś wdrożenie to restart usług przez skrypt instalacyjny — `deploy/instalacja.sh:16` | `deploy/instalacja.sh`, `deploy/systemd/`, `deploy/caddy/danaco-nexus.caddy` | 3–4 d | `gotowosc-repliki`, `dwie-repliki-api` | średni |
| `wersja-minimalna-klientow` | Sprawdzanie wersji minimalnej dla Nexus Desktop i Androida | Wzorzec istnieje tylko dla rozszerzenia — `backend/nexus/config.py:161`, `backend/nexus/api/modules/rozszerzenie.py:33` | `backend/nexus/config.py`, nowy moduł API albo rozszerzenie istniejącego, `desktop/src/main.js`, `android/…/config/NexusConfig.kt` | 3–4 d | — | średni |
| `aktualizacja-desktop` | Automatyczna aktualizacja Nexus Desktop | Brak mechanizmu aktualizacji; użytkownik musi pobrać instalator ręcznie | `desktop/package.json:14,23-60`, `desktop/src/main.js`, `backend/nexus/api/modules/pobieranie.py` | 4–6 d | `wersja-minimalna-klientow` | średni |
| `powiadomienia-android` | Powiadomienia wypychane zamiast odpytywania na Androidzie | Aplikacja odpytuje stan co 30 s przez maksymalnie 3 godziny — `android/…/notify/RunWatch.kt:20-23` | `android/android/app/src/main/java/pl/danaco/nexus/notify/`, `backend/nexus/push_service.py` | 5–7 d | `proces-notifier` | niski |

---

## 9. Zadania poza etapami

Zadania, które nie blokują żadnego etapu, ale usuwają realne niedogodności.

| Identyfikator | Tytuł | Uzasadnienie | Zakres plików | Szacunek | Zależności | Priorytet |
|---|---|---|---|---|---|---|
| `kolejnosc-modulow-interfejsu` | Rozdzielenie jednakowych wartości `order` w rejestrze modułów | Moduły `kod` i `strony` mają obie wartość 60, więc kolejność w nawigacji zależy od kolejności wpisów — `frontend/src/modules/kod/index.tsx:583`, `frontend/src/modules/strony/index.tsx:30` | `frontend/src/modules/kod/index.tsx`, `frontend/src/modules/strony/index.tsx` | 0,5 d | — | niski |
| `instrukcja-trybu-chat` | Uzupełnienie brakującej instrukcji trybu `chat` albo usunięcie trybu z listy | `MODES` zawiera `chat`, ale pliku `tryby/chat.md` nie ma, więc instrukcja jest pusta — `backend/nexus/agent/runner.py:116,192-199` | `backend/nexus/agent/tryby/`, `backend/nexus/agent/runner.py:116` | 0,5 d | — | niski |
| `testy-instrumentowane-androida` | Wypełnienie pustego katalogu testów instrumentowanych | Katalog istnieje, testów nie ma; budowa APK nie sprawdza zachowania interfejsu | `android/android/app/src/androidTest/` | 3–5 d | `potok-bramek` | niski |
| `kontrakt-zdarzen-sse` | Spisanie kontraktu typów zdarzeń jako jednego źródła dla serwera i klientów | Lista typów jest dziś powtórzona po obu stronach — `backend/nexus/agent/runner.py` (emisje) i `frontend/src/api.ts:227-240` | `docs/architektura/`, `frontend/src/api.ts`, `backend/nexus/agent/runner.py` | 2–3 d | — | średni |
| `limit-rozmiaru-historii` | Ograniczenie objętości historii pobieranej przy otwarciu rozmowy | Historia rozmowy jest pobierana w całości — `backend/nexus/api/conversations.py:227-271` | `backend/nexus/api/conversations.py:227-271`, `frontend/src/shell/useChat.ts` | 3–4 d | — | średni |

---

## 10. Podsumowanie nakładu

| Grupa | Zadań | Nakład (dni, przedział) |
|---|---|---|
| Fundament jakości i odtwarzalność | 9 | 20–30 |
| Odzyskanie stanu z pamięci procesu | 7 | 18–25 |
| Obserwowalność | 8 | 21–30 |
| Skalowanie poziome | 7 | 21–28 |
| Magazyn plików i cykl życia danych | 10 | 30–40 |
| Hartowanie i audyt | 12 | 45–62 |
| Praca wielomaszynowa | 6 | 24–33 |
| Poza etapami | 5 | 9–13 |
| **Razem** | **64 pozycje w 8 grupach** | **188–261 dni pracy jednej osoby** |

Rozkład priorytetów:

| Priorytet | Liczba zadań | Charakter |
|---|---|---|
| krytyczny | 6 | ochrona danych i wykrywanie cichej degradacji |
| wysoki | 31 | warunki skalowania i bezpieczeństwa |
| średni | 21 | trwałość operacyjna i wygoda utrzymania |
| niski | 6 | uporządkowanie i drobne niedogodności |

Szacunki dotyczą pracy jednej osoby znającej repozytorium i nie obejmują przestojów na
uzgodnienia. Przedział odzwierciedla niepewność, nie zapas.

---

*Koniec dokumentu. Backlog architektoniczny — Rejestr zadań, wersja 1.0, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Warunki korzystania: [DO DECYZJI OPERATORA] — repozytorium nie zawiera pliku licencji. Kontakt: support@danaco-group.pl*
