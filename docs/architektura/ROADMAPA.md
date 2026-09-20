# Danaco Nexus — Roadmapa wdrożenia architektury

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
| **Tytuł** | Roadmapa wdrożenia — etapy przejścia od stanu obecnego do architektury docelowej wraz z kryteriami odbioru |
| **Klasa dokumentu** | Plan wdrożenia |
| **Odbiorcy** | architekt · zespół backendu · administrator serwera · właściciel produktu |
| **Przeznaczenie** | Ustala kolejność prac i warunek zamknięcia każdego etapu. Etap uznaje się za zamknięty wyłącznie po spełnieniu wszystkich kryteriów odbioru. |
| **Zakres** | Siedem etapów: fundament jakości, odzyskanie stanu, obserwowalność, skalowanie poziome, magazyn i dane, hartowanie, praca wielomaszynowa |
| **Poza zakresem** | Uzasadnienia architektoniczne — [Architektura docelowa](ARCHITEKTURA-DOCELOWA.md); opis stanu — [Stan obecny](STAN-OBECNY.md); rozbicie na zadania — [Backlog](BACKLOG.md) |
| **Dokument nadrzędny** | [Architektura docelowa](ARCHITEKTURA-DOCELOWA.md) |
| **Dokumenty powiązane** | [Stan obecny](STAN-OBECNY.md) · [Backlog](BACKLOG.md) · [README pakietu](README.md) · [`docs/PLAN-ROZWOJU.md`](../PLAN-ROZWOJU.md) |
| **Źródła normatywne** | kryteria odbioru rozdziału 17 [Architektury docelowej](ARCHITEKTURA-DOCELOWA.md#17-kryteria-odbioru-architektury) |
| **Zasada nadrzędna** | Najpierw to, co chroni dane i pozwala zauważyć awarię. Skalowanie dopiero po tym, jak system da się obserwować i odtworzyć. |

## Spis treści

1. [Zasady układania kolejności](#1-zasady-układania-kolejności)
2. [Przegląd etapów](#2-przegląd-etapów)
3. [Etap 1 — Fundament jakości i odtwarzalność](#3-etap-1--fundament-jakości-i-odtwarzalność)
4. [Etap 2 — Odzyskanie stanu z pamięci procesu](#4-etap-2--odzyskanie-stanu-z-pamięci-procesu)
5. [Etap 3 — Obserwowalność](#5-etap-3--obserwowalność)
6. [Etap 4 — Skalowanie poziome na jednej maszynie](#6-etap-4--skalowanie-poziome-na-jednej-maszynie)
7. [Etap 5 — Magazyn plików i cykl życia danych](#7-etap-5--magazyn-plików-i-cykl-życia-danych)
8. [Etap 6 — Hartowanie i audyt](#8-etap-6--hartowanie-i-audyt)
9. [Etap 7 — Praca wielomaszynowa](#9-etap-7--praca-wielomaszynowa)
10. [Ryzyka i sposób prowadzenia](#10-ryzyka-i-sposób-prowadzenia)

---

## 1. Zasady układania kolejności

| Zasada | Konsekwencja |
|---|---|
| Najpierw ochrona danych | kopie zapasowe i migracje wyprzedzają każdą zmianę architektoniczną |
| Najpierw widoczność | nie zmieniamy tego, czego nie potrafimy zmierzyć przed zmianą i po niej |
| Zmiana bez zmiany kontraktu | interfejs REST i zdarzenia SSE pozostają zgodne; klienci nie są przebudowywani przy okazji |
| Jeden powód zmiany na etap | etap ma jedno zdanie celu; gdy potrzeba dwóch — to dwa etapy |
| Każdy etap kończy się dowodem | kryterium odbioru jest sprawdzalne poleceniem albo obserwacją, nie opinią |

---

## 2. Przegląd etapów

```
Etap 1  Fundament jakości          bramki, migracje, kopie zapasowe, środowisko próbne
   │                                „da się bezpiecznie zmieniać i odtworzyć”
   ▼
Etap 2  Odzyskanie stanu            zadania modułowe w bazie, limity w Valkey, notifier
   │                                „restart nic nie gubi”
   ▼
Etap 3  Obserwowalność              dzienniki JSON, metryki, ślady, alarmy
   │                                „widać, co się dzieje i co się zepsuło”
   ▼
Etap 4  Skalowanie poziome          wiele replik API, wydzielone obliczenia, rejestr gniazd
   │                                „można dołożyć replikę”
   ▼
Etap 5  Magazyn i dane              magazyn obiektowy, priorytety i ponowienia, porządki
   │                                „dane nie są przywiązane do dysku"
   ▼
Etap 6  Hartowanie i audyt          zakresy kluczy, audyt, limity zasobów narzędzi, 2FA
   │                                „każde działanie ma ślad i granicę”
   ▼
Etap 7  Praca wielomaszynowa        pule sesji, migawki sesji CLI, wdrożenie kroczące
                                    „system przeżywa utratę maszyny”
```

| Etap | Cel jednym zdaniem | Główne ryzyko przy pominięciu |
|---|---|---|
| 1 | System da się zmieniać i odtworzyć bez utraty danych. | utrata rozmów, plików i wektorów przy awarii dysku |
| 2 | Żaden restart nie gubi zleconej pracy. | zadanie modułu znika przy wdrożeniu (`backend/nexus/tworczy/zadania.py:57-78`) |
| 3 | Awarię widać zanim zgłosi ją użytkownik. | cicha degradacja (np. utrata kontekstu sesji CLI) |
| 4 | Ruch obsługuje więcej niż jeden proces. | jedna pętla zdarzeń dla strumieni, głosu i osadzeń (`backend/nexus/api/app.py:78-86`) |
| 5 | Pliki i zadania nie zależą od konkretnego dysku. | brak możliwości przeniesienia i skalowania |
| 6 | Każde działanie ma granicę i ślad. | brak rozliczalności działań agenta w imieniu użytkownika |
| 7 | Utrata maszyny nie kończy usługi. | pojedynczy punkt awarii |

---

## 3. Etap 1 — Fundament jakości i odtwarzalność

**Cel.** System da się zmieniać i odtworzyć bez utraty danych.

**Zakres.**

1. Potok bramek jakości uruchamiany automatycznie: `ruff`, `pytest`,
   `tsc --noEmit`, `vitest`, testy rozszerzenia. Polecenia istnieją
   (`backend/pyproject.toml:40-59`, `frontend/package.json:9-14`), brakuje wyzwalacza.
2. Migracje wersjonowane (Alembic): rewizja początkowa odwzorowuje obecny schemat
   (`backend/nexus/db.py:83-227`, `backend/nexus/models/*.py`), migracja staje się osobnym
   krokiem wdrożenia zamiast tworzenia schematu przy starcie procesów
   (`backend/nexus/api/app.py:72`, `backend/nexus/worker.py:101`).
3. Kopie zapasowe: kopia bazowa PostgreSQL z ciągłą archiwizacją dziennika, kopia katalogu
   plików, migawka kolekcji Qdrant, kopia sekretów szyfrowana osobnym kluczem.
4. Procedura odtworzenia opisana krok po kroku i przećwiczona na osobnej maszynie.
5. Środowisko próbne w osobnym katalogu, z osobnym klastrem bazy i portem; skrypt
   instalacyjny jest już sparametryzowany katalogiem (`deploy/instalacja.sh:19`).

**Kryteria odbioru.**

| # | Kryterium | Dowód |
|---|---|---|
| 1.1 | Każda zmiana w repozytorium uruchamia komplet bramek | wynik potoku dla ostatnich pięciu zmian |
| 1.2 | Pusta baza i kopia produkcyjna dochodzą do tej samej rewizji migracji | dwa przebiegi migracji z zapisem rewizji |
| 1.3 | Start API i procesu roboczego nie zmienia schematu | migracja wykonana ręcznie; procesy startują na gotowym schemacie |
| 1.4 | Kopia bazy powstaje codziennie, dziennik archiwizowany ciągle | katalog kopii z siedmioma dobowymi pozycjami |
| 1.5 | Odtworzenie z kopii na osobnej maszynie mieści się w 4 godzinach | zapis z ćwiczenia: czas rozpoczęcia, zakończenia, wynik `doctor` |
| 1.6 | Środowisko próbne działa i ma własne dane | `GET /api/health` na porcie próbnym, brak dostępu do danych produkcyjnych |

---

## 4. Etap 2 — Odzyskanie stanu z pamięci procesu

**Cel.** Żaden restart nie gubi zleconej pracy.

**Zakres.**

1. Tabela `module_jobs` zastępuje rejestr w pamięci
   (`backend/nexus/tworczy/zadania.py:57-78`); kontrakt REST modułów Obrazy i Tłumacz
   pozostaje bez zmian (`backend/nexus/api/modules/obrazy.py:142`,
   `backend/nexus/api/modules/tlumacz.py:91`).
2. Wykonanie tych zadań przenosi się z procesu API do procesu `media`.
3. Licznik nieudanych logowań przechodzi do Valkey (dziś `backend/nexus/api/auth.py:60-83`).
4. Nasłuch `nexus:run-finished` wychodzi z procesu API do procesu `notifier`
   z wyborem jednego aktywnego przez dzierżawę (dziś `backend/nexus/api/modules/push.py:50-54`).
5. Suma kontrolna instalatorów liczona przy publikacji, nie przy żądaniu
   (dziś `backend/nexus/api/modules/pobieranie.py:27`).

**Kryteria odbioru.**

| # | Kryterium | Dowód |
|---|---|---|
| 2.1 | Restart API w trakcie obróbki obrazu nie gubi zadania | zadanie po restarcie ma status w bazie i kończy się wynikiem |
| 2.2 | Limit logowań przeżywa restart | ósma nieudana próba, restart, dziewiąta nadal odrzucona kodem 429 |
| 2.3 | Powiadomienie push wysyłane dokładnie raz | dwa procesy API, jedno zakończone zadanie, jedno powiadomienie |
| 2.4 | Proces API nie ma zadań w tle poza obsługą żądań | przegląd `lifespan` i routerów: brak `create_task` długożyjących |
| 2.5 | Kontrakt REST modułów nie zmienił się | testy modułów Obrazy i Tłumacz przechodzą bez zmian w kliencie |

---

## 5. Etap 3 — Obserwowalność

**Cel.** Awarię widać, zanim zgłosi ją użytkownik.

**Zakres.**

1. Dzienniki w formacie JSON z polami stałymi i identyfikatorem żądania
   (dziś format tekstowy — `backend/nexus/logging_setup.py:9`).
2. Punkt `GET /metrics` na porcie wewnętrznym; zestaw metryk z rozdziału 12.2
   [Architektury docelowej](ARCHITEKTURA-DOCELOWA.md#122-metryki).
3. Ślady OpenTelemetry korelowane po `run_id` (`backend/nexus/db.py:151`,
   `db.py:207`, `db.py:219`, `backend/nexus/mcp_server.py:70`).
4. Alarmy: głębokość kolejki, wiek najstarszego zadania, udział zadań zakończonych błędem,
   niedostępność usługi pomocniczej, wykorzystanie limitu konta Claude powyżej progu
   (próg istnieje w kodzie — `backend/nexus/agent/runner.py:135`).
5. Wskaźnik cichej degradacji: liczba przebiegów, które nie wznowiły sesji CLI i użyły
   streszczenia historii (`backend/nexus/agent/runner.py:704-752`).

**Kryteria odbioru.**

| # | Kryterium | Dowód |
|---|---|---|
| 3.1 | Dla dowolnego zadania z ostatnich 30 dni da się pokazać ślad, metryki i dzienniki po `run_id` | trzy losowe zadania, trzy komplety danych |
| 3.2 | Metryki obejmują kolejkę, przebiegi, narzędzia, strumienie i limit konta | odczyt `/metrics` z nazwami z rozdziału 12.2 |
| 3.3 | Alarm zadziała przy sztucznie wywołanej awarii | zatrzymanie Qdrant → alarm w mniej niż 5 minut |
| 3.4 | Utrata sesji CLI jest widoczna jako metryka, nie jako cisza | wymuszone usunięcie pliku sesji podnosi licznik |
| 3.5 | Dzienniki nie zawierają treści rozmów ani sekretów | przegląd próbki z produkcji |

---

## 6. Etap 4 — Skalowanie poziome na jednej maszynie

**Cel.** Ruch obsługuje więcej niż jeden proces.

**Zakres.**

1. Dwie repliki API za Caddy; brzeg bez wymagania powinowactwa dla SSE.
2. Wydzielenie obliczeń mowy i osadzeń z procesu API
   (dziś `backend/nexus/api/app.py:78-86`) do procesów `mowa` i `indexer`.
3. Rejestr gniazd komputerów przenosi się do Valkey z dzierżawą
   (dziś `backend/nexus/api/modules/pulpit.py:53-55`); kanały żądań i odpowiedzi już są
   rozproszone (`backend/nexus/pulpit.py:47-54`).
4. Drugi proces roboczy; policzona pula połączeń PostgreSQL z uwzględnieniem serwerów MCP
   (każdy ma własne połączenie — `backend/nexus/mcp_server.py:67`).
5. Punkt gotowości repliki sprawdzający bazę i Valkey.

**Kryteria odbioru.**

| # | Kryterium | Dowód |
|---|---|---|
| 4.1 | Zabicie repliki w trakcie pracy nie przerywa zadania ani strumienia | strumień wznawia się przez `Last-Event-ID` na drugiej replice |
| 4.2 | Nexus Desktop podłączony do repliki A odbiera żądanie `pc_*` zlecone przez przebieg obsługiwany gdzie indziej | przebieg z narzędziem `pc_info` kończy się poprawnie |
| 4.3 | Drugie połączenie tego samego komputera zamyka pierwsze niezależnie od repliki | kod zamknięcia 4409 na pierwszym gnieździe |
| 4.4 | Zużycie pamięci procesu API jest przewidywalne | pomiar przed i po wydzieleniu obliczeń |
| 4.5 | Liczba połączeń do PostgreSQL mieści się w limicie przy maksymalnej równoległości | pomiar przy ośmiu równoległych przebiegach |

---

## 7. Etap 5 — Magazyn plików i cykl życia danych

**Cel.** Pliki i zadania nie zależą od konkretnego dysku.

**Zakres.**

1. Magazyn obiektowy zgodny z S3 jako druga implementacja `FileStorage`
   (`backend/nexus/storage.py:56-109`); przełączenie konfiguracją.
2. Migracja istniejących plików z weryfikacją SHA-256 (suma jest w bazie —
   `backend/nexus/db.py:173`).
3. Miniatury i pliki wynikowe narzędzi przez ten sam interfejs
   (`backend/nexus/api/files.py:129-143`, `backend/nexus/file_service.py:41-67`).
4. Kolejka zyskuje priorytet, ponowienia dla błędów przejściowych i kolejkę martwych zadań
   (dziś `backend/nexus/worker.py:35-50`, obsługa błędu `backend/nexus/agent/runner.py:663-668`).
5. Proces `porzadki` egzekwuje zasady cyklu życia z rozdziału 8.3
   [Architektury docelowej](ARCHITEKTURA-DOCELOWA.md#83-cykl-życia-danych).

**Kryteria odbioru.**

| # | Kryterium | Dowód |
|---|---|---|
| 5.1 | Odczyt i zapis plików działa z dwóch procesów na różnych ścieżkach | przesłanie pliku przez replikę A, odczyt przez replikę B |
| 5.2 | Migracja zachowała integralność | suma SHA-256 zgodna dla 100% rekordów |
| 5.3 | Zadanie głosowe wyprzedza długie badanie | pomiar czasu oczekiwania przy zajętej kolejce |
| 5.4 | Błąd przejściowy jest ponawiany, błąd modelu nie | wymuszona niedostępność usługi → ponowienie; błąd modelu → brak ponowienia |
| 5.5 | Porządki usuwają pliki robocze i stare zdarzenia | pomiar zajętości katalogu i tabeli przed i po |

---

## 8. Etap 6 — Hartowanie i audyt

**Cel.** Każde działanie ma granicę i ślad.

**Zakres.**

1. Klucze urządzeń z terminem ważności i zakresem
   (dziś bez obu — `backend/nexus/db.py:106-120`); zakres odwzorowuje rodzaj urządzenia.
2. Drugi składnik uwierzytelniania administratora przy logowaniu z nowego urządzenia
   (dziś samo hasło — `backend/nexus/api/auth.py:142-205`).
3. Dziennik audytowy dla działań z rozdziału 10.3
   [Architektury docelowej](ARCHITEKTURA-DOCELOWA.md#103-audyt).
4. Ograniczenie częstości żądań w Valkey dla całego API
   (dziś tylko logowanie — `backend/nexus/api/auth.py:60-83`).
5. Limity zasobów dla programów zewnętrznych uruchamianych przez narzędzia
   (`backend/nexus/tools/base.py:133-173`) i odcięcie sieci dla narzędzi, które jej nie
   potrzebują.
6. Twardy limit równoległych podagentów po stronie serwera
   (dziś prośba w prompcie — `backend/nexus/agent/prompt.py:71-72`).
7. Tryb `code` z odciętą siecią zamiast reguł „w dobrej wierze”
   (`backend/nexus/agent/runner.py:89-115`).

**Kryteria odbioru.**

| # | Kryterium | Dowód |
|---|---|---|
| 6.1 | Wygasły klucz urządzenia jest odrzucany | żądanie z kluczem po terminie → 401 |
| 6.2 | Klucz rozszerzenia nie otwiera modułu Kod ani przekaźnika `pc_*` | dwa żądania poza zakresem → 403 |
| 6.3 | Każde działanie z listy audytu ma wpis | dziesięć działań, dziesięć wpisów z podmiotem i wynikiem |
| 6.4 | Nadmiarowy ruch jest ograniczany | seria żądań powyżej progu → 429, bez wpływu na inne sesje |
| 6.5 | Narzędzie nie przekracza przydzielonych zasobów | wymuszone powiększanie dużego obrazu nie wysyca maszyny |
| 6.6 | Przebieg w trybie `code` nie ma dostępu do sieci | próba połączenia z wnętrza przebiegu kończy się błędem |
| 6.7 | Liczba równoległych podagentów nie przekracza ustawionej | przebieg z żądaniem 40 podagentów wykonuje najwyżej tyle, ile w konfiguracji |

---

## 9. Etap 7 — Praca wielomaszynowa

**Cel.** Utrata maszyny nie kończy usługi.

**Zakres.**

1. Pule sesji: kolumna wyznaczająca pulę w zapytaniu pobierającym zadanie
   (`backend/nexus/worker.py:35-50`), etykieta puli w konfiguracji procesu roboczego.
2. Migawki plików sesji CLI do magazynu obiektowego po każdym przebiegu
   (`backend/nexus/agent/runner.py:209-214`) i odtwarzanie przy zmianie puli.
3. Wdrożenie kroczące replik API i drenaż procesów roboczych — mechanizm drenażu już
   istnieje (`backend/nexus/worker.py:160-169`).
4. Sprawdzanie wersji minimalnej klienta dla Nexus Desktop i Androida — wzorzec istnieje
   dla rozszerzenia (`backend/nexus/config.py:161`,
   `backend/nexus/api/modules/rozszerzenie.py:33`).
5. Automatyczna aktualizacja Nexus Desktop (dziś brak w kodzie).

**Kryteria odbioru.**

| # | Kryterium | Dowód |
|---|---|---|
| 7.1 | Rozmowa zachowuje kontekst mimo pracy wielu procesów roboczych | licznik użycia streszczenia z kryterium 3.4 pozostaje na zeru |
| 7.2 | Utrata maszyny z procesem roboczym nie gubi zadań | zadania wracają do kolejki i kończą się na innej maszynie |
| 7.3 | Wydanie nowej wersji nie przerywa trwającego przebiegu ani strumienia | wdrożenie w trakcie długiego badania |
| 7.4 | Stary klient jest rozpoznany i poproszony o aktualizację | żądanie z wersją poniżej minimalnej → komunikat, nie błąd |
| 7.5 | Nexus Desktop aktualizuje się bez ręcznej instalacji | wydanie nowej wersji, aktualizacja bez udziału użytkownika |

---

## 10. Ryzyka i sposób prowadzenia

| Ryzyko | Skutek | Przeciwdziałanie |
|---|---|---|
| Cicha utrata kontekstu sesji CLI przy wielu procesach roboczych | pogorszenie jakości odpowiedzi bez żadnego błędu | metryka z kryterium 3.4 **przed** etapem 4; pule sesji w etapie 7 |
| Limit subskrypcji konta Claude | skalowanie nie przekłada się na przepustowość | planowanie zdolności od limitu, nie od rdzeni; alarm przy 90% (`backend/nexus/agent/runner.py:135`) |
| Migracja plików do magazynu obiektowego | ryzyko utraty przy błędzie | kopia przed migracją, weryfikacja SHA-256, przełączenie konfiguracją z możliwością powrotu |
| Migracje schematu na żywej bazie | przerwa albo niezgodność wersji | wzorzec „rozszerz–przenieś–zawęź”, ćwiczenie na środowisku próbnym |
| Zakresy kluczy urządzeń | zablokowanie działającego klienta | wprowadzenie w trybie ostrzegawczym (wpis w audycie bez odrzucenia), dopiero potem egzekwowanie |
| Rozrost zakresu etapu | etap nigdy się nie kończy | jedno zdanie celu na etap; nowe pomysły trafiają do [Backlogu](BACKLOG.md), nie do trwającego etapu |
| Praca równoległa z rozwojem funkcji | konflikt zmian | etapy 1–3 nie zmieniają kontraktu API, więc mogą iść równolegle ze strumieniami funkcjonalnymi z [`docs/PLAN-ROZWOJU.md`](../PLAN-ROZWOJU.md) |

Sposób prowadzenia:

1. Etap zaczyna się od zapisania stanu wyjściowego miar, których dotyczy.
2. Zmiany wchodzą pojedynczo, każda z kompletem bramek jakości.
3. Etap zamyka przegląd kryteriów odbioru z dowodami; brak dowodu oznacza etap otwarty.
4. Po każdym etapie [Stan obecny](STAN-OBECNY.md) jest aktualizowany — rozdziały 20 i 21
   mają się kurczyć.

---

*Koniec dokumentu. Roadmapa wdrożenia — Plan wdrożenia, wersja 1.0, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Warunki korzystania: [DO DECYZJI OPERATORA] — repozytorium nie zawiera pliku licencji. Kontakt: support@danaco-group.pl*
