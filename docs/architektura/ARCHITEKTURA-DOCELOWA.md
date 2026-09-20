# Danaco Nexus — Architektura docelowa

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
| **Tytuł** | Architektura docelowa — warstwy, skalowanie poziome, kolejka zadań, magazyn plików, obserwowalność, kopie zapasowe, wdrożenia, hartowanie |
| **Klasa dokumentu** | Specyfikacja docelowa |
| **Odbiorcy** | architekt · zespół backendu · administrator serwera · osoba decydująca o kosztach |
| **Przeznaczenie** | Rozstrzyga, jak system ma być zbudowany, żeby dało się go utrzymywać, skalować i odtwarzać. Z tego dokumentu wynikają etapy [Roadmapy](ROADMAPA.md) i pozycje [Backlogu](BACKLOG.md). |
| **Zakres** | Warstwy i granice, model wykonania zadań, trwałość, magazyn plików, tożsamość i uprawnienia, obserwowalność, kopie zapasowe, strategia wdrożeń, hartowanie, koszty i wybory technologiczne |
| **Poza zakresem** | Stan faktyczny — [Stan obecny](STAN-OBECNY.md); kolejność prac — [Roadmapa](ROADMAPA.md); wycena zadań — [Backlog](BACKLOG.md); warstwa projektowa — [System projektowy](../../design-system/DESIGN_SYSTEM.md) |
| **Dokument nadrzędny** | [Stan obecny](STAN-OBECNY.md) — każda zmiana w tym dokumencie odnosi się do konkretnego ograniczenia opisanego tam w rozdziale 20 |
| **Dokumenty powiązane** | [Roadmapa](ROADMAPA.md) · [Backlog](BACKLOG.md) · [README pakietu](README.md) · [`docs/PLAN-ROZWOJU.md`](../PLAN-ROZWOJU.md) |
| **Źródła normatywne** | kod repozytorium w rewizji `ddfac78`; odsyłacze `plik:linia` wskazują miejsca, które zmiana dotyka |
| **Zasada nadrzędna** | Każda zmiana architektury ma nazwane ograniczenie, które usuwa. Bez takiego ograniczenia zmiana nie wchodzi do dokumentu. |

## Spis treści

1. [Cele i ograniczenia brzegowe](#1-cele-i-ograniczenia-brzegowe)
2. [Warstwy](#2-warstwy)
3. [Obraz docelowy](#3-obraz-docelowy)
4. [Bezstanowa warstwa aplikacji](#4-bezstanowa-warstwa-aplikacji)
5. [Warstwa wykonawcza i powinowactwo sesji](#5-warstwa-wykonawcza-i-powinowactwo-sesji)
6. [Kolejka zadań](#6-kolejka-zadań)
7. [Magazyn plików](#7-magazyn-plików)
8. [Trwałość i schemat bazy](#8-trwałość-i-schemat-bazy)
9. [Strumieniowanie i kanały czasu rzeczywistego](#9-strumieniowanie-i-kanały-czasu-rzeczywistego)
10. [Tożsamość, uprawnienia, audyt](#10-tożsamość-uprawnienia-audyt)
11. [Hartowanie wykonania narzędzi](#11-hartowanie-wykonania-narzędzi)
12. [Obserwowalność](#12-obserwowalność)
13. [Kopie zapasowe i odtworzenie](#13-kopie-zapasowe-i-odtworzenie)
14. [Strategia wdrożeń](#14-strategia-wdrożeń)
15. [Skalowanie poziome — plan zdolności](#15-skalowanie-poziome--plan-zdolności)
16. [Decyzje i odrzucone warianty](#16-decyzje-i-odrzucone-warianty)
17. [Kryteria odbioru architektury](#17-kryteria-odbioru-architektury)

---

## 1. Cele i ograniczenia brzegowe

### Cele

| Cel | Miara docelowa |
|---|---|
| Przeżywalność restartu | żadne zlecone zadanie nie ginie przy restarcie API ani procesu roboczego |
| Skalowanie poziome API | co najmniej trzy repliki API za wspólnym brzegiem, bez zmiany zachowania |
| Skalowanie poziome wykonania | co najmniej trzy procesy robocze, także na osobnych maszynach |
| Odtwarzalność | pełne odtworzenie z kopii zapasowej w ustalonym czasie, ćwiczone okresowo |
| Widoczność | każdy błąd produkcyjny ma ślad z identyfikatorem przebiegu i metryką |
| Bezpieczeństwo | każde działanie nieodwracalne jest zapisane w dzienniku audytowym |

### Ograniczenia brzegowe, których nie zmieniamy

1. **Model wdrożenia**: tylko serwer Danaco, klient jest cienką instalacją. Nie ma
   wariantu samodzielnego hostowania u odbiorcy.
2. **Agent działa przez Claude Code CLI na subskrypcji**, nie przez API Anthropic
   (`backend/nexus/agent/runner.py:325-348`, `runner.py:230-236`). To oznacza, że
   wykonanie zadania jest **procesem systemowym**, a nie wywołaniem HTTP — każdy projekt
   skalowania musi to uwzględnić.
3. **Sesja CLI trzyma kontekst rozmowy w pliku** w profilu
   (`runner.py:209-214`). To jest źródło powinowactwa opisanego w rozdziale 5.
4. **Wdrożenie bez Dockera**, w katalogu projektu, pod systemd
   (`deploy/instalacja.sh:1-13`). Docelowa architektura tego nie odwraca; dodaje
   deklaratywność i powtarzalność w obecnym modelu.
5. **Jeden użytkownik–właściciel**. Wielodostępność nie jest celem; celem jest rozdzielenie
   ról technicznych (administrator, urządzenie, integracja) i audyt.

---

## 2. Warstwy

```
┌──────────────────────────────────────────────────────────────────────────┐
│  W0  BRZEG            Caddy: TLS, HSTS, limity ciała, limit częstości,   │
│                       SSO do chmury, kierowanie po rodzaju ruchu         │
├──────────────────────────────────────────────────────────────────────────┤
│  W1  APLIKACJA        API (N replik, bezstanowe): REST, SSE, WebSocket,  │
│                       walidacja, autoryzacja, serwowanie interfejsu      │
├──────────────────────────────────────────────────────────────────────────┤
│  W2  WYKONANIE        procesy robocze (N, z powinowactwem rozmowy):      │
│                       przebieg agenta, serwer MCP, narzędzia             │
│                       procesy pomocnicze: notifier, indexer, media       │
├──────────────────────────────────────────────────────────────────────────┤
│  W3  DANE             PostgreSQL (prawda) · Valkey (sygnały, blokady)    │
│                       Qdrant (wektory) · magazyn obiektowy (pliki)       │
├──────────────────────────────────────────────────────────────────────────┤
│  W4  INTEGRACJE       Nextcloud · IMAP/SMTP · CalDAV · sieć · bazy nauki │
│                       komputer użytkownika (przekaźnik pc_*)             │
└──────────────────────────────────────────────────────────────────────────┘
```

Reguły granic:

| Reguła | Uzasadnienie |
|---|---|
| W1 nie wykonuje pracy długiej ani obliczeń modeli | jedna pętla zdarzeń obsługuje strumienie; obliczenia je zatrzymują (dziś: `backend/nexus/api/app.py:78-86`) |
| W1 nie trzyma stanu, który przeżywa żądanie | inaczej repliki się rozjeżdżają (dziś: `auth.py:60-83`, `tworczy/zadania.py:57-78`, `modules/pulpit.py:53-55`) |
| W2 nie jest wywoływane z W1 synchronicznie | jedynym kontraktem jest kolejka i zdarzenia |
| W3 jest jedynym miejscem trwałego stanu | plik na dysku repliki nie jest stanem trwałym |
| W4 zawsze za limitem czasu i z obsługą niedostępności | integracja zewnętrzna nie może zatrzymać przebiegu (wzorzec z `research/scholar.py:1-7`) |

---

## 3. Obraz docelowy

```
                       klienci: PWA · Desktop · Android · rozszerzenie
                                        │ HTTPS / WSS
                    ┌───────────────────▼────────────────────┐
                    │  Caddy (brzeg)                          │
                    │  TLS · HSTS · limit częstości · SSO      │
                    │  /api/* i /  → pula API                  │
                    └───────┬─────────────────────┬───────────┘
                            │                     │
                 ┌──────────▼────────┐ ┌──────────▼────────┐      … N replik
                 │  API #1 (bezstan.) │ │  API #2 (bezstan.) │
                 └──────┬──────┬──────┘ └──────┬──────┬──────┘
                        │      │               │      │
         zapis/odczyt ──┘      └── sygnały ────┘      └── strumienie
                        │               │                   │
   ┌────────────────────▼──┐  ┌─────────▼────────┐  ┌───────▼──────────────┐
   │ PostgreSQL            │  │ Valkey            │  │ magazyn obiektowy    │
   │ • runs (kolejka)      │  │ • pub/sub zdarzeń │  │ • pliki użytkownika  │
   │ • rozmowy, wiadomości │  │ • limity częstości│  │ • wyniki narzędzi    │
   │ • pliki (metadane)    │  │ • blokady wyboru  │  │ • migawki sesji CLI  │
   │ • audyt               │  │ • rejestr gniazd  │  └──────────────────────┘
   └────────────────────┬──┘  └─────────┬────────┘
                        │ SKIP LOCKED   │ budzenie
            ┌───────────▼───────────────▼───────────────────────────┐
            │  pula procesów roboczych (N, etykieta = pula sesji)    │
            │   ├─ przebieg agenta → claude -p → MCP → narzędzia     │
            │   ├─ notifier (jeden aktywny, wybór przez blokadę)     │
            │   ├─ indexer (osadzenia, Qdrant)                       │
            │   └─ media (obrazy, tłumaczenia — dzisiejsze „zadania”)│
            └───────────────────────┬───────────────────────────────┘
                                    │
                         Qdrant · Nextcloud · poczta · sieć
```

Zmiany względem stanu obecnego, wprost:

| Element | Dziś | Docelowo |
|---|---|---|
| API | jeden proces (`deploy/systemd/danaco-nexus-api.service:18`) | pula replik, bezstanowa |
| Obliczenia mowy i osadzeń | w procesie API (`app.py:78-86`) | osobne procesy warstwy W2 |
| Zadania modułów twórczych | pamięć procesu API (`tworczy/zadania.py:57-78`) | tabela zadań + proces `media` |
| Powiadomienia push | każda replika (`modules/push.py:50-54`) | jeden proces `notifier` z wyborem przez blokadę |
| Pliki | dysk lokalny (`storage.py:56-72`) | magazyn obiektowy za tym samym interfejsem |
| Schemat bazy | `create_all` + `ADD COLUMN` (`db.py:243-260`) | migracje wersjonowane |
| Limit logowań | pamięć procesu (`auth.py:60-83`) | licznik w Valkey |
| Rejestr gniazd komputerów | pamięć procesu (`modules/pulpit.py:53-55`) | rejestr w Valkey z dzierżawą |

---

## 4. Bezstanowa warstwa aplikacji

Warunek konieczny skalowania: proces API można zabić w dowolnej chwili i uruchomić
drugi, bez zmiany zachowania systemu.

### 4.1 Wyniesienie stanu

| Stan dzisiaj w pamięci | Miejsce docelowe | Mechanizm |
|---|---|---|
| `LoginThrottle` (`auth.py:60-83`) | Valkey | licznik z oknem przesuwnym na klucz `nexus:limit:login:<ip>` |
| `JobRegistry` (`tworczy/zadania.py:57-78`) | PostgreSQL + proces `media` | nowa tabela zadań modułowych, ten sam kontrakt REST dla interfejsu |
| `_connections` (`modules/pulpit.py:53-55`) | Valkey | hasz `nexus:pc:online` już istnieje (`backend/nexus/pulpit.py:31-33`); dochodzi dzierżawa gniazda z identyfikatorem repliki |
| `_digests` (`modules/pobieranie.py:27`) | Valkey albo plik obok instalatora | suma liczona przy publikacji, nie przy żądaniu |
| `push_public_key`, `push_sender` (`modules/push.py:38-54`) | proces `notifier` | API tylko wystawia klucz publiczny i przyjmuje subskrypcje |

### 4.2 Wyniesienie obliczeń

`VoiceEngine` i `KnowledgeBase` są ładowane w procesie API (`app.py:78-86`). Docelowo:

- **mowa** — osobna usługa lokalna z własnym limitem współbieżności; API przekazuje
  nagranie i odbiera tekst. Modele pozostają na serwerze (treść nie wychodzi na zewnątrz),
  zgodnie z dzisiejszą zasadą (`backend/nexus/knowledge.py:1-5`);
- **osadzenia** — proces `indexer` obsługujący indeksowanie i wyszukiwanie; API i narzędzia
  rozmawiają z nim przez kolejkę albo lokalny punkt końcowy, zamiast ładować model
  w każdym procesie (dziś model jest w słowniku klasy — `knowledge.py:61-79`).

Zysk jest mierzalny: profil pamięci procesu API spada do wartości przewidywalnej, a czas
odpowiedzi strumienia przestaje zależeć od tego, czy ktoś równolegle indeksuje dokument.

### 4.3 Kontrakt repliki

Replika API musi spełniać cztery warunki:

1. Cały stan zapisuje w W3 albo odrzuca żądanie.
2. Ma punkt gotowości `GET /api/health` (istnieje — `app.py:106-108`) oraz nowy punkt
   „gotów do ruchu”, który sprawdza bazę i Valkey.
3. Kończy pracę łagodnie: przestaje przyjmować nowe połączenia, domyka strumienie SSE
   komunikatem końcowym i zamyka pulę bazy (dziś `app.py:88-89`).
4. Nie posiada zadań w tle innych niż obsługa żądań.

---

## 5. Warstwa wykonawcza i powinowactwo sesji

To najtrudniejsza część, bo wynika z natury Claude Code CLI.

### 5.1 Problem

Kontekst rozmowy jest przechowywany w pliku sesji w profilu CLI
(`runner.py:209-214`). Proces roboczy, który podejmie kolejne zadanie tej samej rozmowy,
musi widzieć ten sam plik. Gdy go nie widzi, kod zachowuje się poprawnie, ale traci
kontekst: tworzy nową sesję i dokleja streszczenie ostatnich 16 wiadomości
(`runner.py:704-752`, `runner.py:131-132`). To jest degradacja jakości, nie awaria —
i dlatego łatwo ją przeoczyć.

### 5.2 Rozwiązanie: pula sesji z powinowactwem

```
Run(queued, pula = hash(conversation_id) % liczba_pul)
        │
        ├── proces roboczy #1  (pule 0)   ── profil CLI #0 na dysku lokalnym
        ├── proces roboczy #2  (pule 1)   ── profil CLI #1
        └── proces roboczy #3  (pule 2)   ── profil CLI #2
                 │
                 └─ po zakończeniu przebiegu: migawka pliku sesji do magazynu obiektowego
                    przy zmianie puli (przeniesienie, awaria węzła): odtworzenie z migawki
```

- Kolumna `runs.pool` (albo wyliczenie z `conversation_id`) wchodzi do zapytania
  pobierającego zadanie (`worker.py:35-50`), obok istniejącego warunku wykluczającego
  równoległość w rozmowie (`worker.py:40-42`).
- Proces roboczy startuje z etykietą puli w konfiguracji.
- Zmiana liczby pul jest operacją planowaną (jak zmiana liczby partycji), nie
  automatyczną — dzięki temu nie ma cichego gubienia kontekstu.
- Migawka pliku sesji po każdym przebiegu daje odporność na utratę węzła; odtworzenie
  jest tańsze niż streszczenie i nie gubi szczegółów.

Wariant prostszy, dopuszczalny jako etap pośredni: **współdzielony system plików** dla
`claude_profile_dir`, `files_dir`, `kod_dir` i katalogu stron. Zdejmuje problem od razu,
kosztem zależności od magazynu sieciowego i jego opóźnień. Rekomendacja: zacząć od
współdzielonego systemu plików dla katalogu danych, a powinowactwo wprowadzić, gdy
procesy robocze wyjdą poza jedną maszynę.

### 5.3 Procesy pomocnicze

| Proces | Zadanie | Powód wydzielenia |
|---|---|---|
| `notifier` | nasłuch `nexus:run-finished`, wysyłka Web Push | dziś działa w każdej replice API (`modules/push.py:50-54`) — przy wielu replikach powiadomienie poszłoby wielokrotnie |
| `indexer` | osadzenia i operacje na Qdrant | model osadzeń zajmuje pamięć w każdym procesie, który go dotknie (`knowledge.py:70-79`) |
| `media` | obróbka obrazów, tłumaczenia dokumentów | dziś w pamięci API (`tworczy/zadania.py:1-6`) |
| `porzadki` | usuwanie porzuconych plików roboczych, starych zdarzeń, wygasłych sesji | dziś brak w kodzie |

Jeden aktywny `notifier` zapewnia dzierżawa w Valkey (klucz z terminem ważności,
odnawiany) albo blokada doradcza PostgreSQL — ten sam mechanizm, którego kod już używa
przy tworzeniu schematu (`db.py:249-251`).

---

## 6. Kolejka zadań

Kolejka zostaje w PostgreSQL. Uzasadnienie: zlecenie i wiadomość użytkownika powstają
w jednej transakcji (`conversations.py:310-331`), więc broker zewnętrzny wprowadziłby
rozbieżność, której dzisiaj nie ma. `FOR UPDATE SKIP LOCKED` (`worker.py:48`) obsługuje
wiele procesów roboczych bez dodatkowej usługi.

Co dochodzi:

| Zdolność | Realizacja | Ograniczenie, które usuwa |
|---|---|---|
| Priorytety | kolumna `priority`, sortowanie przed `created_at` | zadanie głosowe czeka dziś za sześciogodzinnym badaniem (`config.py:117`) |
| Pule sesji | kolumna `pool` w warunku wyboru | powinowactwo z rozdziału 5 |
| Ponowienia | `attempts`, `max_attempts`, `next_attempt_at`; ponowienie tylko dla błędów przejściowych (start CLI, niedostępność usługi) | dziś każdy błąd kończy zadanie (`runner.py:663-668`) |
| Kolejka martwych zadań | status `dead` po wyczerpaniu prób, z zachowaniem diagnostyki | dziś brak |
| Widoczność | widok „głębokość kolejki, wiek najstarszego zadania, zadania na pulę” | dziś tylko lista aktywnych (`modules/w_toku.py:19-58`) |
| Limit zadań na źródło | licznik w Valkey dla zleceń z modułu Agenci (`modules/agenci.py:202`) | dziś nic nie ogranicza liczby zadań w tle |
| Twardy limit podagentów | zliczanie zdarzeń `tool.started` z opisem agenta w przebiegu i przerwanie po przekroczeniu | dziś limit jest tylko prośbą w prompcie (`agent/prompt.py:71-72`) |

Zasada ponowień: ponawiamy wyłącznie błędy, które nie zużyły limitu konta. Błąd modelu,
przekroczenie limitu konta i anulowanie nie są ponawiane — inaczej system spala
subskrypcję. Klasyfikacja ma się opierać na wzorcach, które kod już rozpoznaje
(`runner.py:118-125`).

---

## 7. Magazyn plików

Docelowo pliki trafiają do magazynu obiektowego zgodnego z S3 (MinIO albo Garage,
uruchamiane tak jak reszta usług — w katalogu projektu, pod systemd, na pętli zwrotnej).

Interfejs zostaje bez zmian: `FileStorage` ma dziś cztery metody
(`storage.py:63-109`) i to one stają się kontraktem:

```
FileStorage (interfejs)
├── path_of / open_stream      odczyt po kluczu
├── save_stream                zapis strumienia z limitem i SHA-256
├── import_file                przeniesienie wyniku narzędzia
└── delete                     usunięcie

  implementacje: DyskLokalny (dzisiejsza)  ·  Obiektowy (docelowa)
```

Ustalenia:

1. `StoredFile.storage_path` (`db.py:174`) staje się **kluczem obiektu**, nie ścieżką.
   Dzisiejszy układ `xx/<uuid><rozszerzenie>` (`storage.py:67-72`) nadaje się bez zmian.
2. Narzędzia pracują na plikach lokalnie — pobranie do katalogu roboczego przebiegu
   i odesłanie wyniku, w miejscu, gdzie dziś jest `ToolContext.file`
   (`tools/base.py:106-112`) i `FileService.store_outputs` (`file_service.py:41-67`).
   Reszta kodu narzędzi nie wie o zmianie.
3. Miniatury (`api/files.py:129-143`) przechodzą do osobnego prefiksu w magazynie.
4. Pobieranie idzie przez API (kontrola dostępu), z możliwością adresów podpisanych dla
   dużych plików, gdy pomiar pokaże, że to konieczne.
5. Migracja: jednorazowy przebieg kopiujący istniejące pliki i weryfikujący SHA-256 —
   suma jest już zapisana przy zapisie (`storage.py:81-94`, `db.py:173`), więc weryfikacja
   nie wymaga niczego nowego.

Poza magazynem obiektowym zostaje to, co musi być systemem plików: profil CLI, projekty
modułu Kod i katalog roboczy narzędzi. Dla nich rozwiązaniem jest współdzielony system
plików albo powinowactwo z rozdziału 5.

---

## 8. Trwałość i schemat bazy

### 8.1 Migracje

`create_all` plus ręczne `ALTER TABLE … ADD COLUMN` (`db.py:243-260`) wystarczają do
dodawania kolumn i nie wystarczają do niczego więcej. Docelowo:

- wersjonowane migracje (Alembic) z rewizją zapisaną w bazie;
- migracja uruchamiana **jako osobny krok wdrożenia**, nie przy starcie procesu —
  dziś schemat tworzy zarówno API (`app.py:72`), jak i proces roboczy (`worker.py:101`);
- każda migracja odwracalna albo jawnie oznaczona jako nieodwracalna;
- zgodność wstecz na czas wdrożenia kroczącego: najpierw kolumna opcjonalna, potem
  wypełnienie, potem wymagalność (wzorzec „rozszerz–przenieś–zawęź”);
- mechanizm `COLUMNS` (`db.py:42-44`, `models/__init__.py:14-21`) zostaje wygaszony po
  przeniesieniu istniejących wpisów do migracji.

### 8.2 Nowe tabele

| Tabela | Rola | Zastępuje |
|---|---|---|
| `module_jobs` | zadania modułów twórczych: rodzaj, status, postęp, wynik, właściciel, czas | `JobRegistry` w pamięci (`tworczy/zadania.py:57-78`) |
| `audit_log` | działanie, podmiot (sesja albo urządzenie), przedmiot, wynik, czas, adres | brak w kodzie |
| `device_tokens` — rozszerzenie | `expires_at`, `scope`, `last_ip` | dzisiejszy rekord bez terminu (`db.py:106-120`) |
| `runs` — rozszerzenie | `priority`, `pool`, `attempts`, `next_attempt_at` | rozdział 6 |

### 8.3 Cykl życia danych

Dziś nic nie jest usuwane automatycznie poza plikami roboczymi przebiegu
(`runner.py:822`) i zakończonymi zadaniami modułów po 6 godzinach
(`tworczy/zadania.py:28`). Docelowo proces `porzadki` egzekwuje zasady:

| Dane | Zasada |
|---|---|
| `run_events` | pełna treść przez 30 dni, potem tylko zdarzenia kluczowe |
| `sessions` | usunięcie po wygaśnięciu (`db.py:100`) |
| pliki bez rozmowy | oznaczenie po 90 dniach, usunięcie po potwierdzeniu |
| pliki robocze `dane/app/work` | usunięcie katalogów starszych niż limit czasu zadania |
| sesje CLI w profilu | migawka do magazynu, usunięcie lokalne po 30 dniach |
| kolekcje Qdrant | usunięcie wektorów plików nieistniejących w bazie |

---

## 9. Strumieniowanie i kanały czasu rzeczywistego

Model pozostaje: **PostgreSQL jest prawdą, Valkey tylko budzi** (`events.py:1-6`).
To dobry wybór i nie wymaga zmiany. Zmieniają się trzy rzeczy.

1. **Strumień przeżywa zmianę repliki.** Dziś wznowienie działa przez `Last-Event-ID`
   (`runs.py:76-82`) i to wystarcza, bo kursor jest kluczem w bazie. Warunek: brzeg nie
   może wymagać powinowactwa dla SSE — i nie wymaga, bo każda replika odczyta te same
   zdarzenia.
2. **WebSocket komputera dostaje rejestr rozproszony.** Dzierżawa gniazda w Valkey
   (`nexus:pc:lease:<device>` z identyfikatorem repliki i terminem) zastępuje słownik
   w pamięci (`modules/pulpit.py:53-55`). Nowe połączenie unieważnia dzierżawę, a replika
   trzymająca stare gniazdo zamyka je po otrzymaniu sygnału. Kanały żądań i odpowiedzi
   już są rozproszone (`backend/nexus/pulpit.py:47-54`), więc zmiana dotyczy wyłącznie
   rejestru.
3. **Wsteczne ciśnienie.** Strumień pobiera do 500 zdarzeń naraz (`runs.py:99`). Docelowo
   dochodzi ograniczenie liczby równoległych strumieni na sesję oraz zwięzła forma
   zdarzeń postępu, żeby jedno bardzo aktywne zadanie nie dominowało ruchu.

---

## 10. Tożsamość, uprawnienia, audyt

### 10.1 Podmioty

```
                       ┌─────────────────────────────────────┐
                       │  Podmiot                            │
                       ├──────────────┬──────────────────────┤
  ciasteczko sesji ───▶│ administrator│ pełne uprawnienia    │
  Bearer nxd_…     ───▶│ urządzenie   │ zakres + termin      │
  Bearer nxi_…     ───▶│ integracja   │ zakres wąski, audyt  │
                       └──────────────┴──────────────────────┘
```

- **Administrator** — jak dziś (`auth.py:118-139`), dodatkowo drugi składnik
  uwierzytelniania (klucz dostępu albo kod jednorazowy) przy logowaniu z nowego urządzenia.
- **Urządzenie** — klucz zyskuje `expires_at` i `scope`. Rodzaje już istnieją
  (`db.py:117`, sprawdzenie rodzaju `desktop` w `modules/pulpit.py:73`), więc zakres
  naturalnie odwzorowuje rodzaj: `desktop` (przekaźnik `pc_*` i czat), `android`,
  `rozszerzenie` (tylko panel i konfiguracja — `modules/rozszerzenie.py:24-33`).
- **Integracja** — nowy rodzaj podmiotu dla automatyzacji korzystających z
  `api.danaco-nexus.pl` (`deploy/caddy/danaco-nexus.caddy:40-65`), z wąskim zakresem
  i obowiązkowym audytem.

### 10.2 Autoryzacja

Dziś zależność `require_session` jest jedynym sprawdzeniem i daje wszystko albo nic
(`auth.py:118-139`). Docelowo: deklaracja wymaganego zakresu na poziomie routera modułu,
egzekwowana tą samą zależnością. Moduły są już podłączane automatycznie
(`api/modules/__init__.py:16-26`), więc deklaracja zakresu może być atrybutem pliku modułu.

### 10.3 Audyt

Do `audit_log` trafia każde działanie zmieniające stan poza rozmową: wydanie i cofnięcie
klucza (`modules/urzadzenia.py:56`, `urzadzenia.py:68`), zatwierdzenie wysyłki poczty
(`api/modules/poczta.py:440`), usunięcie wydarzenia (`api/modules/kalendarz.py:139-167`),
zgoda na polecenie PowerShell (`tools/pc.py:224-241`), publikacja i cofnięcie publikacji
strony (`tools/strony.py:164`, `strony.py:189`), usunięcie rozmowy
(`conversations.py:113-140`) i projektu (`modules/kod.py:258`).

Wpis zawiera: czas, podmiot, rodzaj działania, przedmiot, wynik, adres źródłowy oraz
`run_id`, gdy działanie pochodzi od agenta. Dziennik jest tylko do dopisywania.

---

## 11. Hartowanie wykonania narzędzi

Dzisiejszy poziom: brak powłoki, limit czasu, anulowanie, pliki po identyfikatorach
(`tools/base.py:133-173`, `tools/base.py:106-112`). To dobra podstawa. Docelowo dochodzą
trzy warstwy.

| Warstwa | Środek | Ograniczenie, które usuwa |
|---|---|---|
| Zasoby | uruchamianie programów zewnętrznych w jednostce przejściowej systemd z limitem pamięci, procesora i czasu | jedno wywołanie ImageMagick albo Real-ESRGAN może dziś zająć cały procesor (`tools/images.py:474`, `config.py:53`) |
| System plików | dostęp tylko do katalogu roboczego przebiegu i wskazanych plików wejściowych | narzędzia dziedziczą uprawnienia procesu serwera MCP (`tools/base.py:146-155`) |
| Sieć | narzędzia bez potrzeby sieci uruchamiane bez dostępu do sieci; narzędzia sieciowe z listą docelowych hostów | dziś ochrona jest w warstwie adresów (`research/web.py:1-7`), nie w warstwie procesu |

Dodatkowo:

- **tryb `code`**: dzisiejsze reguły blokujące polecenia sieciowe i podnoszące uprawnienia
  (`runner.py:91-115`) są „w dobrej wierze” (komentarz `runner.py:89-90`). Docelowo
  przebieg w trybie `code` działa w katalogu projektu z odciętą siecią, a git ma dostęp
  tylko przez wyznaczone polecenie;
- **limit wielkości wyniku**: dziś 60 000 znaków w narzędziu (`tools/base.py:32`)
  i limit tokenów wyjścia MCP (`runner.py:245`) — zostaje, uzupełniony o limit liczby
  plików wynikowych na wywołanie;
- **weryfikacja programów** przy starcie (`doctor.py:48-66`) staje się warunkiem gotowości
  procesu roboczego, nie tylko poleceniem diagnostycznym.

---

## 12. Obserwowalność

Trzy filary, każdy z konkretnym punktem zaczepienia w dzisiejszym kodzie.

### 12.1 Dzienniki

Format strukturalny JSON w miejscu dzisiejszego formatu tekstowego
(`logging_setup.py:9`), z polami stałymi: `czas`, `poziom`, `proces`, `moduł`,
`run_id`, `conversation_id`, `device_id`, `request_id`. Identyfikator żądania nadaje
brzeg i przekazuje nagłówkiem; API dokłada go do kontekstu dziennika.

### 12.2 Metryki

Punkt `GET /metrics` na osobnym porcie (nieosiągalny z zewnątrz, jak reszta usług).
Zestaw minimalny:

| Metryka | Źródło |
|---|---|
| głębokość kolejki, wiek najstarszego zadania | `runs` (`db.py:180-197`) |
| przebiegi w podziale na status i tryb | `runs.status`, `Conversation.meta["mode"]` (`runner.py:186-190`) |
| czas przebiegu, liczba tur, tokeny | `runs.usage` (`runner.py:683-693`) |
| wywołania narzędzi: liczba, czas, błędy | `tool_calls` (`db.py:213-227`) |
| otwarte strumienie SSE, rozłączenia | `api/runs.py:74-119` |
| stan przekaźnika komputera | hasz `nexus:pc:online` (`backend/nexus/pulpit.py:31-33`) |
| wykorzystanie limitów konta Claude | `Setting("claude.limity")` (`runner.py:1066-1081`) |
| dostępność usług pomocniczych | kontrole `doctor` (`doctor.py:136-234`) |

### 12.3 Ślady

OpenTelemetry z jednym identyfikatorem śladu na przebieg: żądanie HTTP → wpis do kolejki
→ podjęcie przez proces roboczy → wywołania narzędzi → zdarzenia. `run_id` jest naturalnym
kluczem korelacji, bo występuje w każdej warstwie (`db.py:151`, `db.py:207`, `db.py:219`,
`mcp_server.py:70`).

### 12.4 Poziomy usługi

| Wskaźnik | Cel |
|---|---|
| Dostępność API | 99,5% miesięcznie |
| Czas do pierwszego znaku odpowiedzi | poniżej 3 s dla trybu `chat` w 90% przypadków |
| Zadania zakończone błędem wewnętrznym | poniżej 1% |
| Opóźnienie zdarzenia w strumieniu | poniżej 500 ms od zapisu w bazie |

---

## 13. Kopie zapasowe i odtworzenie

Dziś nie ma niczego (rozdział 21 [Stanu obecnego](STAN-OBECNY.md)). Docelowy zestaw:

```
   PostgreSQL ──► kopia bazowa co dobę + ciągła archiwizacja dziennika WAL
   pliki      ──► magazyn obiektowy z wersjonowaniem + kopia na drugi nośnik
   Qdrant     ──► migawka kolekcji co dobę (odtwarzalne także przez ponowne indeksowanie)
   sekrety    ──► kopia szyfrowana, odrębny klucz, odrębne miejsce
   konfiguracja ─► .env i jednostki systemd w kopii razem z rewizją repozytorium
```

| Parametr | Wartość docelowa |
|---|---|
| RPO (dopuszczalna utrata danych) | 15 minut dla bazy, 24 godziny dla wektorów |
| RTO (czas odtworzenia) | 4 godziny do pełnej sprawności |
| Retencja | 7 kopii dobowych, 4 tygodniowe, 6 miesięcznych |
| Test odtworzenia | raz na kwartał, na osobnej maszynie, z zapisem wyniku |
| Szyfrowanie kopii | tak, klucz poza serwerem produkcyjnym |

Odtworzenie musi być opisane jako procedura krok po kroku i przećwiczone; kopia, której
nie odtworzono, nie jest kopią. Qdrant ma niższy priorytet, bo wektory da się odtworzyć
z plików i bazy przez ponowne indeksowanie (`knowledge.py:92-123`).

---

## 14. Strategia wdrożeń

### 14.1 Potok

```
commit ──► bramki jakości ──► budowa artefaktów ──► wydanie ──► wdrożenie ──► kontrola
            ruff                interfejs (vite)      znacznik    migracja      zdrowie
            pytest              APK (podpisany)       wersji      API krocząco  dym
            tsc + vitest        instalator Windows                worker drain  wycofanie
            testy rozszerzenia  paczka rozszerzenia
```

Bramki istnieją w repozytorium jako polecenia (`backend/pyproject.toml:40-59`,
`frontend/package.json:9-14`, `extension/e2e/uruchom.sh`), brakuje wyłącznie
automatycznego uruchamiania. Potok może działać na tym samym serwerze — nie wymaga usługi
zewnętrznej.

### 14.2 Wdrożenie bez przerwy

| Składnik | Sposób |
|---|---|
| Migracja bazy | osobny krok przed wdrożeniem, zgodna wstecz |
| API | wdrożenie kroczące replika po replice, z kontrolą gotowości |
| Proces roboczy | `SIGTERM`, dokończenie bieżących przebiegów, start nowej wersji — mechanizm już jest (`worker.py:160-169`, `deploy/systemd/danaco-nexus-worker.service:21-22`) |
| Interfejs | zasoby z sumą w nazwie są niezmienne (`app.py:41`, `app.py:112-113`); powiadomienie o nowej wersji obsługuje klient (`frontend/src/pwa.ts:43-51`) |
| Klienci | wersja minimalna sprawdzana po stronie serwera — wzorzec istnieje dla rozszerzenia (`config.py:161`, `modules/rozszerzenie.py:33`); do rozszerzenia na Desktop i Android |
| Wycofanie | poprzednia wersja pozostaje na dysku; wycofanie to przełączenie dowiązania i restart |

### 14.3 Środowiska

Minimum dwa: produkcyjne i próbne na tym samym serwerze, w osobnym katalogu, z osobnym
klastrem bazy i osobnym portem. Skrypt instalacyjny jest już sparametryzowany katalogiem
projektu (`deploy/instalacja.sh:19`), więc koszt jest niewielki, a zysk duży: migracje
i wdrożenia są ćwiczone, zanim dotkną danych właściciela.

---

## 15. Skalowanie poziome — plan zdolności

| Wymiar | Dziś | Etap 1 | Etap docelowy |
|---|---|---|---|
| Repliki API | 1 (`danaco-nexus-api.service:18`) | 2 na jednej maszynie | 3+ , możliwe na wielu maszynach |
| Procesy robocze | 1 proces × 4 przebiegi (`config.py:37`) | 2 procesy | N procesów z pulami sesji |
| Równoległe przebiegi | 4 | 8 | ograniczone limitem konta Claude, nie kodem |
| Miejsce plików | dysk lokalny | dysk lokalny | magazyn obiektowy |
| Przepustowość strumieni | jedna pętla zdarzeń | dwie | liniowo z replikami |

Granicą górną nie jest kod, tylko **limit subskrypcji konta Claude** — system już go
odczytuje i pokazuje (`runner.py:1066-1081`, `modules/agenci.py:91-110`). Dlatego
planowanie zdolności musi zaczynać się od tej wielkości, a nie od liczby rdzeni.

Skutki uboczne skalowania, które trzeba przewidzieć:

- więcej równoległych przebiegów to więcej równoległych procesów CLI i serwerów MCP —
  każdy z własnym połączeniem do bazy (`mcp_server.py:67`); pula połączeń PostgreSQL musi
  być policzona, a nie domyślna;
- narzędzia obrazowe i Real-ESRGAN liczą na procesorze (`agent/prompt.py:42-43`), więc
  wzrost równoległości przebiegów bez limitu zasobów pogorszy czas odpowiedzi czatu;
- indeksowanie w Qdrant konkuruje o pamięć z modelem osadzeń — stąd osobny proces
  `indexer` z rozdziału 5.

---

## 16. Decyzje i odrzucone warianty

| Decyzja | Wybór | Odrzucone | Uzasadnienie |
|---|---|---|---|
| Broker kolejki | PostgreSQL `SKIP LOCKED` | RabbitMQ, Redis Streams, Celery | zlecenie powstaje w jednej transakcji z wiadomością (`conversations.py:310-331`); broker rozbiłby atomowość i dołożył usługę do utrzymania |
| Magazyn plików | obiektowy zgodny z S3, samodzielnie hostowany | dysk lokalny, usługa zewnętrzna | dysk blokuje skalowanie; usługa zewnętrzna łamie zasadę „dane nie opuszczają serwera” (`knowledge.py:1-5`) |
| Kontekst rozmowy | sesja CLI + powinowactwo + migawka | streszczenie zamiast sesji | streszczenie już istnieje jako awaryjne (`runner.py:721-752`) i jest gorszej jakości — nie może być normą |
| Konteneryzacja | pozostajemy przy systemd, dodajemy odtwarzalność instalacji | Docker/Kubernetes | wdrożenie jest jednoserwerowe i świadomie bez Dockera (`deploy/instalacja.sh:1-2`); orkiestracja dołożyłaby warstwę bez odbiorcy |
| Migracje | Alembic | dalsze `create_all` + `ADD COLUMN` | dzisiejszy mechanizm nie obsługuje zmiany typu, usunięcia ani wycofania (`db.py:243-260`) |
| Metryki | Prometheus na porcie wewnętrznym | brak / tylko dzienniki | bez liczb nie da się planować zdolności ani wykryć regresji |
| Uwierzytelnianie klientów | klucze urządzeń z zakresem i terminem | wspólny klucz, klucz bezterminowy | dziś klucz jest bezterminowy i pełnozakresowy (`db.py:106-120`) |
| Wielodostępność | poza zakresem | konta i role użytkowników | model wdrożenia zakłada jednego właściciela; rozdzielamy tylko role techniczne |

---

## 17. Kryteria odbioru architektury

| Kryterium | Sposób sprawdzenia |
|---|---|
| API jest bezstanowe | zabicie repliki w trakcie pracy nie przerywa zadania ani strumienia; druga replika obsługuje wznowienie po `Last-Event-ID` |
| Zadania przeżywają restart | restart API i procesu roboczego w trakcie pracy: żadne zadanie nie znika, zadania modułowe mają status w bazie |
| Powiadomienie wysyłane raz | przy dwóch replikach API jedno zakończone zadanie daje dokładnie jedno powiadomienie push |
| Kolejka ma priorytety i ponowienia | zadanie głosowe wyprzedza badanie; błąd przejściowy jest ponawiany, błąd modelu nie |
| Pliki w magazynie obiektowym | odczyt i zapis działa z dwóch maszyn; suma SHA-256 zgodna dla całego zbioru |
| Migracje wersjonowane | wdrożenie na pustej bazie i na kopii produkcyjnej kończy się tą samą rewizją; wycofanie działa |
| Obserwowalność | dla dowolnego zadania z ostatnich 30 dni da się pokazać ślad, metryki i dzienniki po `run_id` |
| Kopie zapasowe | kwartalny test odtworzenia na osobnej maszynie mieści się w RTO i ma zapisany wynik |
| Audyt | każde działanie z rozdziału 10.3 ma wpis w `audit_log` |
| Hartowanie narzędzi | wywołanie narzędzia nie przekracza przydzielonych zasobów i nie widzi plików spoza katalogu roboczego |
| Wdrożenie bez przerwy | wydanie nowej wersji nie przerywa trwającego przebiegu ani otwartego strumienia |
| Klucze urządzeń | klucz ma termin, zakres i widoczne ostatnie użycie; wygasły klucz jest odrzucany |

---

*Koniec dokumentu. Architektura docelowa — Specyfikacja docelowa, wersja 1.0, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Warunki korzystania: [DO DECYZJI OPERATORA] — repozytorium nie zawiera pliku licencji. Kontakt: support@danaco-group.pl*
