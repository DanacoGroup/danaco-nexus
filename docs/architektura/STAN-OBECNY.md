# Danaco Nexus — Architektura stanu obecnego

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Rodzaj** | Personal AI Workspace |
| **Opis** | Osobisty agent AI działający na serwerze Danaco: rozmowa z modelem Claude przez Claude Code CLI, narzędzia na plikach, OCR, obrazy, poczta, kalendarz, chmura osobista, baza wiedzy, moduł Kod, klienci PWA / Android / Windows / rozszerzenie przeglądarki. |
| **Producent** | Danaco Holding Group Sp. z o.o. |
| **Twórca** | Dariusz Naharnowicz |
| **Wersja** | 1.1 |
| **Status** | Deweloperski |
| **Data** | 2026-09-21 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Architektura stanu obecnego — komponenty, granice, przepływy, model danych, uwierzytelnianie, kolejka zadań, strumieniowanie |
| **Klasa dokumentu** | Opis stanu faktycznego (inwentaryzacja) |
| **Odbiorcy** | architekt · zespół backendu · zespół klientów · administrator serwera |
| **Przeznaczenie** | Jedno źródło prawdy o tym, jak system jest zbudowany dzisiaj. Punkt odniesienia dla [Architektury docelowej](ARCHITEKTURA-DOCELOWA.md), [Roadmapy](ROADMAPA.md) i [Backlogu](BACKLOG.md). |
| **Zakres** | Backend FastAPI (`backend/nexus`), przebieg agenta, rejestr narzędzi, moduły API, frontend React (`frontend/src`), powłoka Electron (`desktop/`), aplikacja Android (`android/`), rozszerzenie przeglądarki (`extension/`), warstwa danych, konfiguracja i wdrożenie (`deploy/`, `.env.example`) |
| **Poza zakresem** | Warstwa projektowa — [System projektowy](../../design-system/DESIGN_SYSTEM.md); opisy funkcjonalne modułów — [`docs/moduly/`](../moduly/); plan strumieni prac — [`docs/PLAN-ROZWOJU.md`](../PLAN-ROZWOJU.md) |
| **Dokument nadrzędny** | brak — dokument źródłowy dla pakietu architektury |
| **Dokumenty powiązane** | [Architektura docelowa](ARCHITEKTURA-DOCELOWA.md) · [Roadmapa](ROADMAPA.md) · [Backlog](BACKLOG.md) · [README pakietu](README.md) |
| **Źródła normatywne** | kod repozytorium `/danaco/projekty/danaco-nexus`: rewizja `f0a53ff` plus niezatwierdzone zmiany w drzewie roboczym (stan z 21 września). Każde twierdzenie ma odsyłacz `plik:linia`; przy niezatwierdzonych zmianach numery wierszy mogą być przesunięte — nazwa symbolu jest pewniejsza niż numer |
| **Zasada nadrzędna** | Opisujemy wyłącznie to, co jest w kodzie. Gdy funkcji nie ma, dokument mówi „brak w kodzie”, a nie „planowane”. |

> **Uwaga o numerach wierszy (21.09.2026).** Opis stanu jest aktualny na 21 września
> (rewizja `f0a53ff` plus niezatwierdzone zmiany w drzewie roboczym), ale odsyłacze
> `plik:linia` policzono jeszcze dla rewizji `ddfac78`. Od tego czasu weszło kilkanaście
> wydań, więc numery bywają przesunięte — np. `app.py:106-108` nie wskazuje już
> `/api/health`. Nazwy plików, funkcji i opis zachowania są nadal aktualne; przy numerze
> wiersza warto sprawdzić kod, zanim się go zacytuje.

## Spis treści

1. [Zakres i metoda](#1-zakres-i-metoda)
2. [Obraz całości](#2-obraz-całości)
3. [Procesy i granice](#3-procesy-i-granice)
   - [3.1 Proces API](#31-proces-api)
   - [3.2 Proces roboczy](#32-proces-roboczy)
   - [3.3 Serwer MCP narzędzi](#33-serwer-mcp-narzędzi)
4. [Przebieg agenta](#4-przebieg-agenta)
5. [Kolejka zadań](#5-kolejka-zadań)
6. [Strumieniowanie zdarzeń](#6-strumieniowanie-zdarzeń)
7. [Kanał WebSocket komputera](#7-kanał-websocket-komputera)
8. [Model danych](#8-model-danych)
9. [Uwierzytelnianie i autoryzacja](#9-uwierzytelnianie-i-autoryzacja)
10. [Narzędzia agenta](#10-narzędzia-agenta)
11. [Moduły API](#11-moduły-api)
12. [Warstwa kliencka](#12-warstwa-kliencka)
    - [12.1 Aplikacja PWA](#121-aplikacja-pwa)
    - [12.2 Nexus Desktop](#122-nexus-desktop)
    - [12.3 Aplikacja Android](#123-aplikacja-android)
    - [12.4 Rozszerzenie przeglądarki](#124-rozszerzenie-przeglądarki)
13. [Magazyn plików i baza wiedzy](#13-magazyn-plików-i-baza-wiedzy)
14. [Integracje zewnętrzne](#14-integracje-zewnętrzne)
15. [Konfiguracja](#15-konfiguracja)
16. [Wdrożenie](#16-wdrożenie)
17. [Bezpieczeństwo — stan faktyczny](#17-bezpieczeństwo--stan-faktyczny)
18. [Obserwowalność — stan faktyczny](#18-obserwowalność--stan-faktyczny)
19. [Jakość i testy](#19-jakość-i-testy)
20. [Ograniczenia stanu obecnego](#20-ograniczenia-stanu-obecnego)
21. [Czego nie ma w kodzie](#21-czego-nie-ma-w-kodzie)

---

## 1. Zakres i metoda

Dokument powstał z lektury kodu, nie z opisów. Każde zdanie o działaniu systemu ma
odsyłacz do pliku i numeru linii. Ścieżki są podane względem katalogu repozytorium
`/danaco/projekty/danaco-nexus`.

Rozmiary warstw (stan na dzień dokumentu):

| Warstwa | Miara |
|---|---|
| Backend Python | 91 plików `.py` pod kontrolą wersji, 20 690 linii w `backend/nexus/**` |
| Narzędzia agenta | 91 rejestracji `@registry.register` w `backend/nexus/tools/*.py` |
| Moduły API | 16 modułów w `backend/nexus/api/modules/` (17 plików wraz z `__init__.py`) |
| Moduły interfejsu | 12 katalogów z `index.tsx` w `frontend/src/modules/` |
| Testy backendu | 6 109 linii w `backend/tests/` |
| Klienci | `desktop/` (Electron), `android/` (Capacitor + Kotlin), `extension/` (MV3) |

---

## 2. Obraz całości

```
   przeglądarka / PWA        Nexus Desktop (Windows)      Android (Capacitor)      rozszerzenie MV3
        │ HTTPS                 │ HTTPS + WebSocket           │ HTTPS/WebView          │ HTTPS
        │ ciasteczko sesji      │ Bearer nxd_…                │ Bearer nxd_…           │ Bearer nxd_…
        └───────────────┬───────┴──────────────┬──────────────┴───────────┬────────────┘
                        ▼                      ▼                          ▼
        ┌───────────────────────────────────────────────────────────────────────────┐
        │  Caddy hosta (deploy/caddy/danaco-nexus.caddy)                             │
        │  danaco-nexus.pl · api.danaco-nexus.pl · cloud.danaco-nexus.pl (SSO)       │
        └───────────────────────────────┬───────────────────────────────────────────┘
                                        ▼  127.0.0.1:8930
        ┌───────────────────────────────────────────────────────────────────────────┐
        │  danaco-nexus-api  (uvicorn, JEDEN proces)                                 │
        │  routery: auth, conversations, files, runs, voice + modules/*.py           │
        │  stan w procesie: LoginThrottle, JobRegistry, WebSocket komputerów,        │
        │                   VoiceEngine (Whisper/Piper), KnowledgeBase (fastembed)   │
        └───┬───────────────┬────────────────────┬──────────────────┬───────────────┘
            │ kolejka       │ SSE               │ Redis pub/sub     │ pliki
            ▼ (tabela runs) ▼                   ▼                   ▼
        ┌────────────────────────────┐   ┌──────────────┐   ┌────────────────────┐
        │ danaco-nexus-worker         │   │ Valkey       │   │ dane/app/files     │
        │ claim FOR UPDATE SKIP LOCKED│   │ (gniazdo UNIX)│  │ (dysk lokalny)     │
        │ worker_concurrency = 4      │   └──────────────┘   └────────────────────┘
        └───────────┬────────────────┘
                    │ podproces na zadanie
                    ▼
        ┌──────────────── piaskownica bwrap ─────────┐
        │ claude -p --output-format stream-json       │
        │   widzi: katalog projektu, profil sesji,    │
        │   katalog zadania, /danaco/programy (ro)    │
        │   └─ przelotka node → gniazdo uniksowe ─────┼──┐
        └────────────────────────────────────────────┘  │
                                                         ▼
                                    ┌───────────────────────────────┐
                                    │ python -m nexus.mcp_server    │ ← 101 narzędzi
                                    │ (poza piaskownicą: kod i baza)│
                                    └───────────────────────────────┘
                    │
   PostgreSQL 5433 (gniazdo UNIX) · Qdrant 6335 · LanguageTool 8010 · Nextcloud 8940
   Tika · Tesseract · LibreOffice · FFmpeg · ImageMagick · Real-ESRGAN · rembg
```

Twierdzenia poparte kodem: montowanie routerów — `backend/nexus/api/app.py:100-104`;
pojedynczy proces uvicorn bez `--workers` — `deploy/systemd/danaco-nexus-api.service:18`;
kolejka w PostgreSQL — `backend/nexus/worker.py:35-50`; serwer MCP uruchamiany przez CLI —
`backend/nexus/agent/runner.py:257-268`.

---

## 3. Procesy i granice

System składa się z trzech rodzajów procesów Pythona oraz usług pomocniczych
uruchamianych przez systemd (`deploy/systemd/`).

### 3.1 Proces API

Fabryka aplikacji: `backend/nexus/api/app.py:64`. W `lifespan`
(`backend/nexus/api/app.py:68-89`) powstają wszystkie obiekty współdzielone:

| Obiekt | Miejsce | Uwaga |
|---|---|---|
| `Database` | `app.py:71-72` | tworzy schemat przy starcie (`create_schema`) |
| `FileStorage` | `app.py:75` | katalog `data_dir/files` (`config.py:97-100`) |
| `LoginThrottle` | `app.py:76` | licznik nieudanych logowań **w pamięci procesu** (`auth.py:60-83`) |
| `EventBus` | `app.py:77` | Redis pub/sub albo odpytywanie bazy (`events.py:35-50`) |
| `VoiceEngine` | `app.py:78-80` | modele mowy ładowane do pamięci procesu API (`voice.py:1-7`) |
| `KnowledgeBase` | `app.py:81-86` | klient Qdrant + model osadzeń fastembed (`knowledge.py:58-82`) |

Routery stałe (`auth`, `conversations`, `files`, `runs`, `voice`) są dołączane jawnie,
a moduły z `backend/nexus/api/modules/` wykrywane automatycznie przez `pkgutil`
(`backend/nexus/api/modules/__init__.py:16-26`, wywołanie w `app.py:103-104`).

Dokumentacja OpenAPI jest wyłączona (`docs_url=None`, `redoc_url=None`, `openapi_url=None`
— `app.py:95-97`). Jedyny punkt kontrolny to `GET /api/health` (`app.py:106-108`).

Aplikacja serwuje też zbudowany interfejs: katalog `assets` z nieskończonym buforowaniem
(`app.py:45-51`, `app.py:112-113`), a wszystkie pozostałe ścieżki spadają do `index.html`
(`app.py:121-135`). Pliki PWA (`sw.js`, `manifest.webmanifest`, `index.html`, …) są
oznaczane `no-cache` (`app.py:38-40`).

Nagłówki bezpieczeństwa dodaje jedno middleware (`app.py:54-61`) z listy w `app.py:25-36`
(CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`).

### 3.2 Proces roboczy

`backend/nexus/worker.py:76-177`. Jeden proces wykonuje do `worker_concurrency`
przebiegów naraz (semafor — `worker.py:85-86`, domyślnie 4 — `config.py:37`).
Pętla główna (`worker.py:99-144`) czeka na powiadomienie z kanału `nexus:queue`
albo odpytuje bazę co sekundę (`worker.py:31`, `worker.py:117`).

Zatrzymanie jest łagodne: `SIGTERM` przestawia flagę (`worker.py:95-97`, `worker.py:185-187`),
trwające przebiegi są dokańczane przez `worker_stop_grace_s` (`worker.py:160-169`,
`config.py:118`), a jednostka systemd daje na to 120 s (`deploy/systemd/danaco-nexus-worker.service:25-26`).

Kod procesu roboczego pochodzi z wydania (`WorkingDirectory=wydania/produkcja/backend`),
tak samo jak kod API — `wypchnij.sh` i `cofnij.sh` przestawiają obie jednostki naraz.
Przedsionek ma własny proces roboczy (`danaco-nexus-worker-przedsionek.service`), bo
kolejką jest tabela `runs` w bazie, a przedsionek pracuje na własnej bazie.

Zadania po niespodziewanym zatrzymaniu procesu są odzyskiwane po 3 minutach bez pulsu
(`worker.py:32`, `worker.py:63-73`, wywołanie co 60 s — `worker.py:119-127`).

### 3.3 Serwer MCP narzędzi

`backend/nexus/mcp_server.py:62-164`. Uruchamiany przez Claude Code CLI na czas
jednego zadania, z konfiguracji zapisywanej do pliku tymczasowego
(`runner.py:257-268`, `runner.py:768-769`). Identyfikator zadania i rozmowy przychodzi
przez zmienne środowiskowe `NEXUS_RUN_ID` i `NEXUS_CONVERSATION_ID`
(`mcp_server.py:70-72`).

Narzędzia wykonują się w puli wątków (`mcp_server.py:69`, `mcp_server.py:127`), a postęp
trafia do tabeli `run_events` i budzi strumień SSE (`mcp_server.py:76-79`,
`mcp_server.py:97-103`). Pliki wynikowe przechodzą do magazynu przez `FileService`
(`mcp_server.py:128`, `backend/nexus/file_service.py:41-67`).

Granica jest ostra: serwer MCP to osobny proces z własnym połączeniem do bazy
(`mcp_server.py:67`), więc narzędzia nie współdzielą pamięci ani z API, ani z procesem
roboczym.

Od wprowadzenia piaskownicy serwer MCP **nie jest** uruchamiany przez CLI: potrzebuje kodu
Nexusa, środowiska Pythona i bazy, czyli dokładnie tego, czego agent widzieć nie może.
Uruchamia go proces roboczy poza piaskownicą, a CLI łączy się z nim przez gniazdo uniksowe
w katalogu zadania (`backend/nexus/agent/most_mcp.py`). Z punktu widzenia CLI to nadal
zwykły serwer MCP „stdio”; z punktu widzenia agenta kod Nexusa nie istnieje.

Samo gniazdo leży **poza** katalogiem zadania, we własnym krótkim katalogu
(`most_mcp.KATALOG_GNIAZD`, prawa `0600`): ścieżka gniazda uniksowego mieści się w ~108
bajtach, a katalog zadania bywa głębszy. Do piaskownicy wchodzi jako osobne montowanie.
Drogę sprawdza `backend/tests/test_most_mcp.py` — razem z granicami (puste środowisko
przelotki, sprzątanie po zamknięciu) i z przebiegiem końca do końca: klient MCP uruchamia
przelotkę w Node tym samym poleceniem, które trafia do `--mcp-config`, i odbiera wykaz
narzędzi przez gniazdo.

### 3.4 Piaskownica procesu CLI

`backend/nexus/agent/piaskownica.py`. Proces Claude Code CLI startuje w osobnej przestrzeni
montowań (`bwrap --unshare-all --share-net`). Widzi:

* katalog projektu użytkownika, profil sesji CLI i katalog roboczy zadania — do zapisu;
* `/usr`, `/etc` i `/danaco/programy` — do odczytu (biblioteki systemowe i łańcuch narzędzi,
  bez którego moduł Kod nie miałby czym budować ani testować);
* `/run/systemd/resolve` — bez tego katalogu nie działa rozwiązywanie nazw.

Środowisko procesu powstaje od zera (`--clearenv` plus wykaz dodający
`piaskownica.ZMIENNE_DOZWOLONE`): do środka wchodzi `PATH`, `HOME`, język i katalog
tymczasowy, a proces CLI dodatkowo własne zmienne `CLAUDE_*`, `MCP_*` i `GIT_*`. Żadnej
zmiennej `NEXUS_*` — adres bazy i ścieżki do plików z kluczami zostają po stronie serwera.

Nie widzi kodu Nexusa, pozostałych projektów na dysku, katalogu producenta, kluczy ani
wydań. Wcześniej ograniczenie było wyłącznie instrukcją w opisie trybu Kod („nie wychodź
poza katalog projektu”), a `Read` i `Bash` przyjmują ścieżki bezwzględne — egzekwuje je
więc dopiero jądro. Wyłącznik: `agent_piaskownica=false` (świadoma decyzja operatora;
przy braku `bwrap` proces roboczy zapisuje ostrzeżenie w dzienniku).

Tej samej piaskownicy używa narzędzie `animate_explainer`, które renderuje scenę Manim
pisaną przez model — tam dodatkowo bez wyjścia do sieci (`siec=False`).

---

## 4. Przebieg agenta

Agent nie korzysta z API Anthropic. Każde zadanie to uruchomienie Claude Code CLI
w trybie `-p --output-format stream-json` (`backend/nexus/agent/runner.py:325-348`).

```
Run(queued)
   │ worker.claim_next()                          worker.py:53-60
   ▼
AgentRunner.execute(run_id)                       runner.py:629
   │ 1. odczyt Run + Conversation + Message       runner.py:631-641
   │ 2. tryb rozmowy z Conversation.meta["mode"]  runner.py:186-190
   │ 3. emit run.started                          runner.py:646
   ▼
_run_cli()                                        runner.py:754
   │ sesja CLI: --session-id albo --resume        runner.py:704-719
   │ brak pliku sesji → streszczenie historii     runner.py:721-752
   │ katalog roboczy dane/app/work/cli-<run_id>   runner.py:764-765
   │ mcp.json z jednym serwerem „nexus”           runner.py:768-769
   ▼
subprocess: claude -p …  (start_new_session=True) runner.py:771-780
   │  stdin: [streszczenie] + treść wiadomości    runner.py:790-792
   │  stdout: strumień JSON linia po linii        runner.py:835-848
   ├── system.init            → notice o MCP      runner.py:869-886
   ├── stream_event           → text.delta        runner.py:906-925
   ├── assistant              → Message + ToolCall runner.py:927-984
   ├── user (tool_results)    → tool.finished     runner.py:985-1056
   ├── system.task_*          → postęp podagenta  runner.py:887-904
   └── rate_limit_event       → Setting „claude.limity” runner.py:1066-1081
   ▼
Run(done | failed | cancelled) + run.completed/failed/cancelled   runner.py:669-682
```

Istotne własności:

- **Zestaw narzędzi** jest budowany dla każdego przebiegu: narzędzia Nexusa przez MCP
  plus wybrane wbudowane narzędzia CLI (`runner.py:271-280`). Reszta wbudowanych narzędzi
  jest jawnie zakazana listą `DISALLOWED_TOOLS` (`runner.py:61-88`), a zgody są wyłączone
  (`--permission-prompts none`, `runner.py:345-347`).
- **Tryby rozmowy**: `chat`, `research`, `code`, `strona` (`runner.py:116`). Instrukcja trybu
  pochodzi z pliku `backend/nexus/agent/tryby/<tryb>.md` (`runner.py:192-199`); istnieją
  pliki `code.md`, `research.md`, `strona.md` — dla trybu `chat` instrukcji nie ma i funkcja
  zwraca pusty napis.
- **Tryb `code`** włącza narzędzia plikowe CLI i dokleja katalog projektu
  (`runner.py:278-279`, `runner.py:358-359`), a polecenia sieciowe i podnoszące uprawnienia
  blokuje listą reguł `CODE_BASH_DENY` (`runner.py:91-115`). Komentarz w kodzie nazywa to
  ograniczeniem „w dobrej wierze”, nie piaskownicą (`runner.py:89-90`).
- **Podagenci**: definicja typu `pomocnik` przekazywana przez `--agents`
  (`runner.py:283-302`, `runner.py:352-357`); podagent nie może zlecać dalej
  (`runner.py:288`). Limit równoległych podagentów jest wyłącznie instrukcją w prompcie
  (`backend/nexus/agent/prompt.py:71-72`, `config.py:116`) — **nie ma twardego egzekwowania
  w kodzie**.
- **Token konta**: środowisko CLI usuwa klucze API i ustawia token OAuth z profilu
  (`runner.py:225-254`, `runner.py:217-223`).
- **Anulowanie**: osobne zadanie odpytuje bazę co sekundę i przy okazji odświeża puls
  przebiegu (`runner.py:824-831`), a przerwanie kończy całą grupę procesów
  (`runner.py:779`, `runner.py:798-805`).
- **Sprzątanie po biegu**: blok `finally` anuluje cztery zadania pomocnicze (obserwator
  anulowania, czytnik stderr, dwa oczekiwania) i **zbiera je** przez `asyncio.gather`
  z `return_exceptions=True`. Zebranie jest istotne, nie kosmetyczne: `cancel()` zaznacza
  tylko prośbę, a obserwator anulowania jest w tej chwili w sesji bazy i ma jeszcze wycofać
  transakcję. Przy pętli zdarzeń zamykanej zaraz po biegu — czyli w testach —
  niezebrane zadanie potrafiło zablokować `asyncio.runners._cancel_all_tasks`
  na zawsze i wieszało całą bramkę wydania (21.09.2026).
- **Limit czasu**: 120 minut domyślnie, 360 minut dla trybu badań
  (`runner.py:202-206`, `config.py:33`, `config.py:117`).

---

## 5. Kolejka zadań

Kolejka to tabela `runs` w PostgreSQL — bez brokera.

Zlecenie powstaje w `POST /api/conversations/{id}/messages`
(`backend/nexus/api/conversations.py:283-333`): wiadomość użytkownika i rekord `Run`
zapisywane są w jednej transakcji (`conversations.py:310-331`), po czym publikowane jest
powiadomienie na kanale `nexus:queue` (`conversations.py:332`).

Pobranie zadania to jedno zapytanie (`backend/nexus/worker.py:35-50`):

```sql
UPDATE runs SET status='running', worker_id=:worker, started_at=now(), heartbeat_at=now()
WHERE id = (
    SELECT r.id FROM runs r
    WHERE r.status = 'queued'
      AND NOT EXISTS (SELECT 1 FROM runs o
                      WHERE o.conversation_id = r.conversation_id AND o.status = 'running')
    ORDER BY r.created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1)
RETURNING id
```

Konsekwencje wynikające wprost z tego zapytania i z kodu:

| Własność | Stan | Odsyłacz |
|---|---|---|
| Wiele procesów roboczych naraz | obsługiwane (`SKIP LOCKED`) | `worker.py:48` |
| Szeregowanie w obrębie rozmowy | jedno zadanie na rozmowę | `worker.py:40-42` |
| Druga wiadomość przy trwającym zadaniu | odrzucona kodem 409 | `conversations.py:292-298` |
| Priorytety zadań | brak w kodzie | — |
| Ponowienia i kolejka martwych zadań | brak w kodzie | — |
| Odzyskiwanie po awarii procesu | po 3 min bez pulsu → `failed` | `worker.py:63-73` |
| Wariant SQLite (testy) | osobne zapytanie bez blokad | `worker.py:49-50` |

Poza tą kolejką istnieje **druga, niezależna kolejka w pamięci procesu API** dla zadań
modułów twórczych (obrazy, tłumaczenie dokumentów) — `backend/nexus/tworczy/zadania.py:1-6`,
rejestr `zadania.py:57-78`, limit 200 zadań i sześciogodzinne przechowywanie wyników
(`zadania.py:27-28`). Zadania te nie przeżywają restartu API.

---

## 6. Strumieniowanie zdarzeń

Źródłem prawdy jest tabela `run_events`; Redis służy wyłącznie do budzenia strumieni
(`backend/nexus/events.py:1-6`).

```
worker / mcp_server ──INSERT run_events──► PostgreSQL
        │                                      ▲
        └──PUBLISH nexus:run:<id>──► Valkey     │ SELECT id > kursor
                                        │       │
przeglądarka ──GET /api/runs/{id}/events┴───► API ──► text/event-stream
      ▲ Last-Event-ID / ?after=<id>                    id: <RunEvent.id>
      └──────────── automatyczne wznowienie (retry: 2000) ──────────────
```

- Endpoint SSE: `backend/nexus/api/runs.py:74-119`. Subskrypcja kanału jest zakładana
  **przed** pierwszym odczytem bazy, więc żadne powiadomienie nie ginie (`runs.py:88-89`).
- Wznowienie po zerwaniu: nagłówek `Last-Event-ID` albo parametr `after`
  (`runs.py:76`, `runs.py:82`); identyfikatorem jest klucz główny `RunEvent.id`
  (`runs.py:104`).
- Podtrzymanie połączenia co 15 s (`runs.py:24`, `runs.py:110-112`), oczekiwanie na
  powiadomienie 5 s (`runs.py:23`).
- Zdarzenia końcowe zamykają strumień (`runs.py:21`, `runs.py:105-106`).
- Bez Redisa strumień odpytuje bazę co 0,25 s (`events.py:26`, `events.py:110-113`).
  Awaria Redisa wyłącza go na 30 s i przechodzi na odpytywanie (`events.py:27`,
  `events.py:52-54`).
- Caddy przekazuje strumień bez buforowania (`flush_interval -1` —
  `deploy/caddy/danaco-nexus.caddy:32`), API dodaje `X-Accel-Buffering: no`
  (`runs.py:118`).

Typy zdarzeń, które klient obsługuje jawnie: `run.started`, `text.block`, `text.delta`,
`thinking.delta`, `tool.pending`, `tool.started`, `tool.progress`, `tool.finished`,
`notice`, `run.completed`, `run.failed`, `run.cancelled` (`frontend/src/api.ts:227-240`).
Strona serwera emituje je w `runner.py:646`, `runner.py:884-885`, `runner.py:902-904`,
`runner.py:921-923`, `runner.py:944-945`, `runner.py:677` oraz w serwerze MCP
(`mcp_server.py:100-103`).

Kanały Redis: `nexus:run:<id>` (zdarzenia zadania), `nexus:queue` (nowe zadanie),
`nexus:run-finished` (zakończenie, dla powiadomień push) — `events.py:21-25`.

---

## 7. Kanał WebSocket komputera

Jedyny WebSocket w systemie obsługuje Nexus Desktop:
`backend/nexus/api/modules/pulpit.py:105`. Protokół jest opisany w nagłówku pliku
(`pulpit.py:1-14`): komunikaty `auth`, `ping`, `response` od komputera oraz `ready`,
`pong`, `request`, `cancel`, `error` od serwera.

```
narzędzie pc_* (proces MCP)
   │ SUBSCRIBE nexus:pc:resp:<request_id>       backend/nexus/pulpit.py:52-54
   │ PUBLISH  nexus:pc:<device_id>:req          backend/nexus/pulpit.py:47-49
   ▼
Valkey ──► proces API z otwartym gniazdem ──► WebSocket ──► Nexus Desktop
                        ▲                                        │
                        └──── PUBLISH nexus:pc:resp:<id> ◄───────┘
   hash nexus:pc:online — lista podłączonych komputerów          pulpit.py:31-33
```

Uwierzytelnienie: klucz urządzenia rodzaju `desktop`
(`backend/nexus/api/modules/pulpit.py:67-76`), przekazywany nagłówkiem `Authorization`
albo pierwszym komunikatem (`pulpit.py:89-102`), z ponownym sprawdzeniem co 60 s
(`pulpit.py:47`, `pulpit.py:79-82`).

Ograniczenie: rejestr otwartych gniazd żyje w pamięci jednego procesu API
(`pulpit.py:53-55`). Przy kilku procesach API dwa okna tego samego komputera nie
wykryłyby się nawzajem. Wariant bez Redisa (`MemoryBroker` —
`backend/nexus/pulpit.py:57-61`) działa wyłącznie, gdy API i narzędzia są w jednym procesie,
czyli w testach.

Polecenia PowerShell zmieniające system wymagają zgody na komputerze użytkownika
(`backend/nexus/tools/pc.py:224-241`, limity czasu `config.py:94-95`).

---

## 8. Model danych

Wszystkie tabele są definiowane deklaratywnie na `nexus.db.Base`. Typ JSON ma wariant
`JSONB` dla PostgreSQL (`backend/nexus/db.py:36`), klucze całkowite — `BigInteger`
z wariantem `Integer` dla SQLite (`db.py:37`).

### Tabele rdzenia (`backend/nexus/db.py`)

| Tabela | Klasa | Linie | Rola |
|---|---|---|---|
| `settings` | `Setting` | 83-90 | ustawienia klucz–wartość (hasło administratora, stan limitów konta Claude) |
| `sessions` | `UserSession` | 93-103 | sesje administratora (przechowywany skrót tokenu) |
| `device_tokens` | `DeviceToken` | 106-120 | klucze urządzeń `nxd_…` (skrót, rodzaj, cofnięcie) |
| `conversations` | `Conversation` | 123-134 | rozmowa, identyfikator sesji CLI, `meta` z trybem i przestrzenią |
| `messages` | `Message` | 137-156 | historia w formacie Messages API, wyłącznie dopisywana |
| `files` | `StoredFile` | 159-177 | pliki wgrane i wytworzone (ścieżka względna, SHA-256, znacznik indeksacji) |
| `runs` | `Run` | 180-197 | zadania agenta: status, puls, `worker_id`, zużycie |
| `run_events` | `RunEvent` | 200-210 | zdarzenia strumienia SSE (indeks `run_id, id` — `db.py:204`) |
| `tool_calls` | `ToolCall` | 213-227 | rejestr wywołań narzędzi z czasem trwania i plikami wynikowymi |

### Tabele modułów (`backend/nexus/models/`)

| Tabela | Klasa | Plik i linie | Rola |
|---|---|---|---|
| `biuro_oczekujace` | `PendingAction` | `models/biuro.py:15-31` | działanie przygotowane przez agenta, czekające na zatwierdzenie |
| `push_subscriptions` | `PushSubscription` | `models/push.py:14-27` | subskrypcje Web Push |
| `research_collections` | `KnowledgeCollection` | `models/research.py:20-29` | kolekcja bazy wiedzy |
| `research_sources` | `KnowledgeSource` | `models/research.py:32-54` | źródło (strona, plik, praca, tekst) |
| `research_notes` | `KnowledgeNote` | `models/research.py:57-73` | notatka w kolekcji |
| `research_reports` | `ResearchReport` | `models/research.py:76-96` | badanie prowadzone w osobnej rozmowie |

### Zarządzanie schematem

Schemat powstaje przez `Base.metadata.create_all` przy starcie API i procesu roboczego
(`db.py:243-260`, wywołania `app.py:72` i `worker.py:101`). Dla PostgreSQL całość jest
objęta blokadą doradczą, żeby dwa procesy nie tworzyły tabel naraz (`db.py:249-251`).

Nowe kolumny w istniejących tabelach dopisuje lista `COLUMNS` (`db.py:42-44`) uzupełniana
przez moduły (`models/__init__.py:14-21`) i wykonywana jako `ALTER TABLE … ADD COLUMN`
(`db.py:254-260`).

**Alembic ani żaden inny system migracji nie występuje w repozytorium.** Mechanizm nie
obsługuje zmiany typu kolumny, usunięcia kolumny, zmiany nazwy ani wycofania zmiany.

### Stan poza bazą

Część stanu żyje wyłącznie na dysku, bez odwzorowania w bazie:

| Dane | Miejsce | Odsyłacz |
|---|---|---|
| Treść plików | `dane/app/files/<2 znaki>/<uuid><rozszerzenie>` | `storage.py:67-72` |
| Miniatury | `dane/app/cache/thumbnails/<uuid>.jpg` | `api/files.py:135-139` |
| Projekty modułu Kod | `dane/app/kod/<nazwa>` | `config.py:124-127`, `agent/przestrzenie.py:10-20` |
| Strony WWW (szkice, wersje, publikacje) | `dane/app/strony/…` | `tworczy/strony.py:3-8` |
| Sesje Claude Code CLI | `dane/claude-profil/projects/*/<id>.jsonl` | `runner.py:209-214` |
| Token OAuth konta Claude | `dane/claude-profil/oauth-token` | `runner.py:217-223` |
| Konfiguracja poczty | `dane/app/poczta.json` | `mail.py:3-6`, `config.py:85` |
| Klucz VAPID | `dane/app/vapid` (prawa 600) | `push_service.py:53-75` |
| Hasło aplikacji chmury | `dane/app/chmura-token` | `config.py:52` |

---

## 9. Uwierzytelnianie i autoryzacja

System ma **jedno konto administratora** (`backend/nexus/api/auth.py:27-29`), ustawiane
poleceniem `python -m nexus.cli set-password` (`backend/nexus/cli.py:48-58`,
`auth.py:46-57`). Brak w kodzie ról, wielu użytkowników i podziału uprawnień.

### Ścieżka przeglądarki

1. `POST /api/auth/login` z nagłówkiem `X-Nexus-Request: 1` (`auth.py:142-146`).
2. Weryfikacja hasła Argon2 (`auth.py:32`, `auth.py:171-177`), z automatycznym
   przeliczeniem skrótu, gdy parametry się zmieniły (`auth.py:190-193`).
3. Losowy token 32-bajtowy w ciasteczku `HttpOnly`, `Secure`, `SameSite=Lax`
   (`auth.py:179`, `auth.py:194-204`); w bazie wyłącznie skrót SHA-256 (`auth.py:41-43`).
4. Każde żądanie: `require_session` (`auth.py:118-139`) — sprawdza ważność sesji
   i dla metod zmieniających stan wymaga nagłówka `X-Nexus-Request` (ochrona CSRF,
   `auth.py:137-138`).

Ograniczenie prób logowania: 8 nieudanych prób na adres IP w 15 minut
(`config.py:67`, `auth.py:60-83`, `auth.py:150-153`). Licznik jest strukturą w pamięci
procesu — restart API kasuje historię, a drugi proces API miałby własny licznik.

### Ścieżka urządzeń

Klucz `nxd_…` wydaje `POST /api/urzadzenia` (`backend/nexus/api/modules/urzadzenia.py:56`),
a urządzenie wysyła go w nagłówku `Authorization: Bearer` (`auth.py:93-115`). Takie
żądania nie używają ciasteczek, więc nie wymagają nagłówka CSRF (`auth.py:118-124`).
Klucz jest przechowywany w bazie jako skrót (`db.py:115`), można go cofnąć
(`db.py:120`, `urzadzenia.py:68`).

**Brak w kodzie**: terminu ważności klucza urządzenia, automatycznej rotacji oraz
ograniczenia zakresu (klucz daje pełny dostęp do API tak samo jak sesja przeglądarki).

### Logowanie jednokrotne do chmury

`GET /api/auth/sso` (`auth.py:235-256`) jest wywoływane przez `forward_auth` Caddy
(`deploy/caddy/danaco-nexus.caddy:87-91`). Przy ważnej sesji zwraca nagłówek
`X-Nexus-User` z nazwą konta Nextcloud; Caddy najpierw usuwa ten nagłówek przychodzący od
klienta (`danaco-nexus.caddy:84`). Ciasteczko obejmuje domenę nadrzędną
(`config.py:65`, `auth.py:202-203`).

Stan od 24.09.2026: nagłówek dostaje sesja właściciela instalacji (konto techniczne) oraz konto
klienta, które ma własne konto Nextcloud `nexus-<owner>` — zakładane przy pierwszym wejściu do
chmury, gdy plan obejmuje synchronizację (Pro, Grupa), przez `occ` (`backend/nexus/chmura_konta.py`).
Pozostałe konta dostają `204` bez nagłówka; ich pliki są w `/Konta/<owner>` konta technicznego
i widzą je wyłącznie przez moduł Pliki. Przegląd izolacji: `docs/zgodnosc/IZOLACJA-KONT.md`.

### Trasy publiczne

| Trasa | Uwierzytelnianie | Odsyłacz |
|---|---|---|
| `GET /api/health` | brak | `app.py:106-108` |
| `GET /` i `GET /{path}` (interfejs) | brak | `app.py:121-135`, `modules/osadzanie.py:29-45` |
| `GET /pobierz` i `GET /pobierz/{plik}` | brak, biała lista trzech nazw | `modules/pobieranie.py:19-26`, `pobieranie.py:66-79` |
| `GET /s/{adres}/{ścieżka}` (opublikowane strony) | brak — treść publiczna | `modules/strony.py:363-366` |
| `GET /api/strony/{adres}/podglad/{token}/…` | token podglądu | `modules/strony.py:369-379` |
| `GET /api/auth/sso` | sprawdza ciasteczko, sama trasa otwarta | `auth.py:235` |
| `WS /api/pulpit/ws` | klucz urządzenia rodzaju `desktop` | `modules/pulpit.py:105-116` |

---

## 10. Narzędzia agenta

Narzędzia są rejestrowane dekoratorem w modułach `backend/nexus/tools/*.py`, które pakiet
importuje automatycznie (`backend/nexus/tools/__init__.py:15-17`). Rejestr trzyma je
w stałej kolejności, co stabilizuje prefiks pamięci podręcznej modelu
(`backend/nexus/tools/base.py:222-254`).

W repozytorium jest **91 zarejestrowanych narzędzi**. Tabela niżej wymienia trzon; pełny,
zawsze aktualny wykaz z polskimi nazwami i przykładami wypisuje `frontend/scripts/narzedzia.py`
do `frontend/src/dane/narzedzia.ts` (to samo źródło zasila moduł Możliwości i portal).
Dołożone we wrześniu 2026: przeglądarka (`browser_*`, `tools/przegladarka.py`), zestaw witryn
(`site_kit_catalog`, `site_from_kit`, `tools/kit_www.py`) i animacja wyjaśniająca
(`animate_explainer`, `tools/animacja.py`).

| Grupa | Narzędzia | Plik |
|---|---|---|
| Pliki i tekst | `inspect_files`, `view_pages`, `extract_text` | `tools/files.py:144,189,252` |
| OCR | `ocr_documents` | `tools/ocr.py:60` |
| PDF | `pdf_split`, `pdf_merge`, `pdf_edit_pages`, `detect_document_boundaries` | `tools/pdf.py:104,130,162,228` |
| Obrazy | `enhance_document_scan`, `enhance_photo`, `retouch_portrait`, `upscale_image`, `imagemagick`, `convert_images` | `tools/images.py:142,247,324,369,474,514` |
| Obrazy twórcze | `remove_background`, `change_background`, `erase_objects` | `tools/obrazy.py:98,140,196` |
| Dokumenty | `convert_documents`, `write_document`, `check_grammar` | `tools/office.py:53,136,191` |
| Multimedia | `media_process`, `transcribe_audio` | `tools/media.py:40`, `tools/speech.py:59` |
| Archiwa | `create_archive`, `extract_archive` | `tools/archive.py:29,52` |
| Baza wiedzy | `index_documents`, `search_documents` | `tools/knowledge.py:36,73` |
| Research | `web_fetch_page`, `web_search`, `scholar_search`, `scholar_paper`, `knowledge_save`, `knowledge_notes`, `knowledge_read` | `tools/research.py:69,98,129,166,199,291,357` |
| Chmura | `cloud_browse`, `cloud_import`, `cloud_save` | `tools/cloud.py:207,229,272` |
| Poczta | `mail_list`, `mail_search`, `mail_read`, `mail_draft`, `mail_send` | `tools/poczta.py:186,236,261,303,333` |
| Kalendarz | `calendar_list`, `calendar_create`, `calendar_update`, `calendar_delete` | `tools/kalendarz.py:81,105,131,156` |
| Komputer użytkownika | `pc_info`, `pc_find_files`, `pc_read_file`, `pc_powershell`, `pc_screenshot` | `tools/pc.py:167,179,194,225,245` |
| Strony WWW | `site_list`, `site_read_file`, `site_write_file`, `site_import_file`, `site_delete_file`, `site_save_version`, `site_publish`, `site_unpublish` | `tools/strony.py:31,73,92,112,135,150,164,189` |
| Tłumaczenie | `translate_document` | `tools/tlumacz.py:43` |

Wspólne zasady wymuszone szkieletem (`backend/nexus/tools/base.py`):

- narzędzie deklaruje model wejścia pydantic z zakazem pól nadmiarowych
  (`base.py:43-46`) i dostaje z niego schemat JSON (`base.py:192-198`);
- pliki są wskazywane wyłącznie identyfikatorem, nigdy ścieżką (`base.py:106-112`,
  `file_service.py:23-34`);
- programy zewnętrzne są uruchamiane bez powłoki, z limitem czasu i możliwością
  anulowania (`base.py:133-173`);
- katalog roboczy narzędzia jest usuwany po wywołaniu (`base.py:175-177`,
  `mcp_server.py:136-137`);
- wynik tekstowy jest skracany do 60 000 znaków (`base.py:32`, `base.py:271-275`).

**Działania w imieniu użytkownika wymagają zatwierdzenia.** `mail_send` nie wysyła
wiadomości, tylko tworzy `PendingAction` (`tools/poczta.py:332-357`,
`backend/nexus/oczekujace.py:37-46`); wysyłką steruje interfejs modułu Poczta
(`api/modules/poczta.py:440`). Tak samo działa usuwanie wydarzeń kalendarza
(`oczekujace.py:19`, `api/modules/kalendarz.py:139-167`). Podwójne wykonanie blokuje
`claim` z blokadą wiersza (`oczekujace.py:77-85`).

---

## 11. Moduły API

Każdy plik `backend/nexus/api/modules/<moduł>.py` z obiektem `router` jest podłączany
automatycznie (`api/modules/__init__.py:16-26`).

| Moduł | Prefiks | Zakres | Odsyłacz |
|---|---|---|---|
| `agenci` | `/api/agenci` | podgląd wszystkich zadań, drzewo podagentów, zlecanie zadań w tle, stan limitów konta | `modules/agenci.py:22`, `agenci.py:113`, `agenci.py:202` |
| `cloud` | `/api/cloud` | przeglądarka Nextcloud: lista, kosz, wersje, udostępnienia, przesyłanie kawałkami | `modules/cloud.py:35-530` |
| `kalendarz` | `/api/kalendarz` | kalendarze CalDAV, wydarzenia, działania oczekujące | `modules/kalendarz.py:20-193` |
| `kod` | `/api/kod` | projekty (git init / clone), drzewo plików, git, sesje programistyczne | `modules/kod.py:35`, `kod.py:215-255` |
| `obrazy` | `/api/obrazy` | zadania obróbki obrazów (tło, gumka, powiększanie) | `modules/obrazy.py:24-148` |
| `osadzanie` | `/` | strona główna z trybem `?widok=panel` i własnym `frame-ancestors` | `modules/osadzanie.py:21-45` |
| `pobieranie` | `/pobierz` | publiczne pobieranie trzech instalatorów z sumą SHA-256 | `modules/pobieranie.py:22-79` |
| `poczta` | `/api/poczta` | skrzynki IMAP, szkice, kolejka wiadomości do zatwierdzenia | `modules/poczta.py:47-491` |
| `pulpit` | `/api/pulpit` | WebSocket komputerów i lista podłączonych | `modules/pulpit.py:44`, `pulpit.py:105`, `pulpit.py:222` |
| `push` | `/api/push` | klucz VAPID, subskrypcje, powiadomienie próbne | `modules/push.py:62-142` |
| `research` | `/api/research` | kolekcje, źródła, notatki, badania, rozmowa z dokumentami | `modules/research.py:26-744` |
| `rozszerzenie` | `/api/rozszerzenie` | konfiguracja dla rozszerzenia i weryfikacja klucza | `modules/rozszerzenie.py:19-33` |
| `strony` | `/api/strony` + `/s/…` | szkice, wersje i publikacja stron WWW | `modules/strony.py:61-62`, `strony.py:382-384` |
| `tlumacz` | `/api/tlumacz` | tłumaczenie tekstu i dokumentów (zadania) | `modules/tlumacz.py:17-97` |
| `urzadzenia` | `/api/urzadzenia` | wydawanie i cofanie kluczy urządzeń | `modules/urzadzenia.py:20-68` |
| `w_toku` | `/api/w-toku` | lista wszystkich aktywnych zadań z ostatnim narzędziem | `modules/w_toku.py:13-58` |

Moduł `push` ma własny `lifespan` routera: przy starcie API tworzy klucz VAPID i uruchamia
nasłuch kanału `nexus:run-finished` (`modules/push.py:35-59`). Nasłuch działa w **każdym**
procesie API, więc przy wielu replikach każda z nich rozesłałaby to samo powiadomienie.

---

## 12. Warstwa kliencka

### 12.1 Aplikacja PWA

Stos: React 19.3 (`frontend/package.json:20-21`), Vite 8.3
(`frontend/package.json:29`), Tailwind CSS 4.3 przez `@tailwindcss/vite`
(`frontend/package.json:24-25,31`), TypeScript 7 (`frontend/package.json:32`),
`vite-plugin-pwa` 1.3 (`frontend/package.json:34`).

Struktura:

```
frontend/src
 ├─ main.tsx          motyw przed renderem, rejestracja SW poza trybem panelu
 ├─ App.tsx           własny router na history API; Landing / Workspace / PanelApp
 ├─ api.ts            jeden klient HTTP + SSE
 ├─ shell/            Workspace, PanelApp, TasksPanel, useChat, sse, route, embed, push
 ├─ components/       Composer, Turns, Markdown, Sidebar, FileCard, PreviewModal, Login
 ├─ modules/          12 modułów wykrywanych automatycznie + biblioteki _biuro, _tworczy
 ├─ landing/          publiczna strona produktu
 └─ styles.css + tokens.css  (tokens.css kopiowany z design-tokens, nie edytowany ręcznie)
```

- **Rejestr modułów**: `import.meta.glob("./*/index.tsx", {eager: true})` z sortowaniem po
  `order` (`frontend/src/modules/registry.ts:31-40`); kontrakt modułu `NexusModule`
  (`registry.ts:16-29`). Moduły: `research` (30), `wiedza` (31), `cloud` (40), `poczta` (41),
  `kalendarz` (42), `kod` (60), `strony` (60), `obrazy` (62), `tlumacz` (64), `studio` (66),
  `agenci` (70), `urzadzenia` (900). Katalogi `_biuro` i `_tworczy` nie są modułami —
  nie pasują do wzorca glob i pełnią rolę bibliotek współdzielonych.
- **Routing** jest własny, bez biblioteki: wzorce `/c/<uuid>` i `/m/<id>`
  (`frontend/src/shell/route.ts:13-25`), decyzja o ekranie w `route.ts:47-55`,
  nawigacja przez `pushState`/`popstate` (`frontend/src/App.tsx:36-137`).
- **Klient HTTP**: `apiFetch` i `request` w `frontend/src/api.ts:97-124`; nagłówek
  `X-Nexus-Request: 1` dodawany zawsze poza trybem klucza urządzenia
  (`api.ts:77`, `api.ts:92-94`).
- **SSE**: gdy działa ciasteczko sesji — natywny `EventSource`
  (`api.ts:244-267`); w trybie klucza urządzenia — własny czytnik przez `fetch`,
  bo `EventSource` nie wysyła nagłówka `Authorization`
  (`frontend/src/shell/sse.ts:66-114`), z własnym parserem (`sse.ts:11-54`),
  wznowieniem po `Last-Event-ID` (`sse.ts:85`) i przerwaniem bez ponowień przy
  401/403/404 (`sse.ts:87-90`).
- **Stan aplikacji** jest wyłącznie lokalny w hookach Reacta — w kodzie nie ma
  zustand, Reduxa ani `createContext`. Stan czatu trzyma `useChat`
  (`frontend/src/shell/useChat.ts`), listę zadań — `TasksPanel` odpytujący API co 3 s
  przy aktywnych zadaniach i co 15 s w spoczynku (`frontend/src/shell/TasksPanel.tsx:10-11`).
- **Motyw**: `dark | light | system` w `localStorage` pod kluczem `nexus-theme`
  (`frontend/src/theme.ts:5,9-17`), przełączany klasą na `<html>` (`theme.ts:24-28`).
- **PWA**: manifest i Workbox w `frontend/vite.config.ts:13-100`; buforowana jest wyłącznie
  powłoka, a `/api/*`, `/share-target`, `/pobierz`, `?widok=panel` i `/s/*` zawsze idą
  z sieci (`vite.config.ts:88-95`). Udostępnianie z systemu obsługuje service worker
  (`frontend/public/share-target.js:7-38`), Web Push — ten sam worker
  (`share-target.js:52-98`). Zainstalowana aplikacja sprawdza aktualizacje co godzinę
  (`frontend/src/pwa.ts:51`).
- **Tryb panelu**: `?widok=panel` renderuje wyłącznie `PanelApp`
  (`frontend/src/App.tsx:24-34`), który czeka 1,2 s na klucz od strony nadrzędnej, zanim
  spróbuje sesji z ciasteczka (`frontend/src/shell/PanelApp.tsx:27,110-112`). Serwer
  poluzowuje dla tego widoku `frame-ancestors` (`backend/nexus/api/modules/osadzanie.py:29-45`,
  lista w `config.py:136`).

### 12.2 Nexus Desktop

Electron 44 z instalatorem NSIS dla Windows x64 (`desktop/package.json:20-21`,
`desktop/package.json:36-46`), identyfikator `pl.danaco.nexus.desktop`
(`desktop/package.json:24`).

- Okno ładuje **zdalny adres** serwera (`desktop/src/main.js:194`), domyślnie
  `https://danaco-nexus.pl` (`desktop/src/config.js:9`); lokalnie są tylko strony
  pomocnicze w `desktop/src/ui`.
- Izolacja: `contextIsolation: true`, `sandbox: true`, własna partycja sesji
  (`desktop/src/main.js:158`, `main.js:23`).
- Integracja systemowa: zasobnik (`main.js:326-356`), skróty globalne
  (`main.js:255-269`), autostart (`main.js:247-253`), zamykanie do zasobnika
  (`main.js:521-523`).
- Klucz urządzenia jest pobierany z zalogowanej sesji okna przez `POST /api/urzadzenia`
  (`main.js:298-317`) i zapisywany zaszyfrowany mechanizmem systemowym
  (`desktop/src/config.js:69-98`), z walidacją formatu (`config.js:86`).
- Lokalny agent łączy się przez WebSocket `${serwer}/api/pulpit/ws`
  (`desktop/src/agent/connection.js:73`), uwierzytelnia pierwszym komunikatem
  (`connection.js:78-86`), pinguje co 25 s (`connection.js:9`) i ponawia połączenie
  z rosnącym odstępem do 60 s (`connection.js:104-108`).
- **Brak w kodzie**: mechanizmu automatycznej aktualizacji (`electron-updater`
  nie występuje), rejestracji własnego schematu adresów.

### 12.3 Aplikacja Android

Capacitor 8.5.2 (`android/package.json`) z modułami natywnymi w Kotlinie; WebView ładuje
zdalny adres `https://danaco-nexus.pl` (`android/capacitor.config.json:6`) z listą
dozwolonych domen (`capacitor.config.json:7`).

- Moduły natywne w pakiecie `pl.danaco.nexus`: `assist` (asystent systemowy),
  `access` (wstawianie tekstu przez usługę dostępności), `overlay` (języczek przy krawędzi,
  zrzut ekranu), `voice` (rozmowa głosowa, VAD), `sms` (szkice odpowiedzi), `notify`,
  `api` (REST i SSE), `panel`, `config`, `web`.
- Klucz urządzenia w `EncryptedSharedPreferences` opartym o Android Keystore
  (`android/android/app/src/main/java/pl/danaco/nexus/config/DeviceKeyStore.kt:24-27,42`).
- Powiadomienia są **lokalne**; Firebase ani FCM nie występują. Stan zadań po zejściu
  aplikacji w tło dogląda `WorkManager` co 30 s przez maksymalnie 3 godziny
  (`…/notify/RunWatch.kt:20-23`).
- Pobieranie plików przez systemowy `DownloadManager`, ciasteczko dołączane wyłącznie dla
  hostów Nexusa (`…/web/Downloads.kt:27-29`).
- Budowa: `minSdk 29`, `compileSdk/targetSdk 36`, klucz podpisu z pliku wskazanego
  parametrem (`android/android/app/build.gradle:6-10`), skrypt odtwarzalnej budowy
  `deploy/android/buduj-apk.sh`.

### 12.4 Rozszerzenie przeglądarki

Manifest V3 (`extension/manifest.json:2`), minimalna wersja Chrome 116
(`manifest.json:7`), service worker w tle (`manifest.json:17-19`).

- Uprawnienia: `storage`, `contextMenus`, `scripting`, `clipboardWrite`
  oraz `host_permissions: ["<all_urls>"]` (`manifest.json:26-27`).
- Skrypt treści na wszystkich stronach, tylko ramka główna (`manifest.json:28-35`);
  panel `panel.html` jako zasób dostępny ze stron (`manifest.json:36-41`).
- Panel jest wstrzykiwany w zamknięty Shadow DOM
  (`extension/src/tresc/panel-host.ts:78`), a łączność z ramką idzie przez `MessageChannel`
  z losowym kluczem w adresie (`panel-host.ts:233-244`).
- Klucz urządzenia jest sprawdzany zapytaniem
  `GET /api/rozszerzenie/konfiguracja` (`extension/src/wspolne/polaczenie.ts:13-18`,
  serwer: `backend/nexus/api/modules/rozszerzenie.py:24-33`).
- Protokół panelu (`nexus:auth`, `nexus:context`, `nexus:prompt`, `nexus:ready`,
  `nexus:insert`, `nexus:copy`) z weryfikacją źródła (`extension/src/panel/most.ts:46-47`).

---

## 13. Magazyn plików i baza wiedzy

**Pliki.** `FileStorage` zapisuje strumień na dysk lokalny, licząc po drodze SHA-256
i pilnując limitu (`backend/nexus/storage.py:74-94`); nazwa na dysku pochodzi wyłącznie
z identyfikatora (`storage.py:67-72`), więc nazwa użytkownika nigdy nie wpływa na ścieżkę.
Limit przesyłania to 2048 MB (`config.py:39`, `api/files.py:58-62`); Caddy przepuszcza
ciało do 2 GB (`deploy/caddy/danaco-nexus.caddy:18-20`).

Pobieranie wymusza `Content-Disposition: attachment` poza wąską listą bezpiecznych typów
(`api/files.py:25`, `api/files.py:91-100`). Miniatury obrazów i pierwszej strony PDF są
liczone raz i buforowane na dysku (`api/files.py:129-143`).

**Baza wiedzy.** Qdrant z osadzeniami liczonymi lokalnie modelem wielojęzycznym
(`backend/nexus/knowledge.py:1-5`, model `config.py:44`). Tekst jest dzielony na fragmenty
po 1200 znaków z zakładką 200 znaków, z zachowaniem granic akapitów
(`knowledge.py:21-22`, `knowledge.py:34-55`). Kolekcja powstaje przy pierwszym
indeksowaniu wraz z indeksem po `file_id` (`knowledge.py:84-90`). Wyszukiwanie może być
ograniczone do wskazanych dokumentów (`knowledge.py:138-154`).

Model osadzeń jest ładowany leniwie i trzymany w słowniku klasy
(`knowledge.py:61-62`, `knowledge.py:70-79`) — w procesie API oraz osobno w każdym
procesie serwera MCP.

W bazie wiedzy identyfikatorem dokumentu bywa też identyfikator źródła albo notatki
modułu Research (`backend/nexus/models/research.py:1-5`), co pozwala przeszukiwać te
same wektory narzędziem `search_documents`.

---

## 14. Integracje zewnętrzne

| Integracja | Protokół | Miejsce w kodzie | Uwagi |
|---|---|---|---|
| Claude (subskrypcja) | Claude Code CLI, `stream-json` | `agent/runner.py:325-371` | token OAuth z pliku; klucz API jest usuwany ze środowiska (`runner.py:230-236`) |
| Nextcloud — pliki | WebDAV + OCS | `cloud_service.py:1-7`, `tools/cloud.py` | konto i hasło aplikacji z `dane/app/chmura-token` |
| Nextcloud — kalendarz | CalDAV | `calendar.py:1-7` | rozwijanie zdarzeń cyklicznych po stronie serwera |
| Poczta | IMAP + SMTP, TLS/STARTTLS | `mail.py:1-12` | wiele kont, podpisy HTML, operacje synchroniczne w wątku |
| Wyszukiwanie w sieci | HTTP | `research/web.py:1-7` | ochrona przed SSRF: tylko publiczne adresy IP, sprawdzane także po przekierowaniu i przy nawiązywaniu połączenia |
| Bazy naukowe | HTTP | `research/scholar.py:1-7` | OpenAlex, Semantic Scholar, arXiv, Crossref; niedostępność jednej bazy nie przerywa wyszukiwania |
| Rozpoznawanie i synteza mowy | biblioteki lokalne + Google Cloud | `voice.py:1-7`, `voice_google.py` | modele lokalne (Whisper, Piper), klucz Google opcjonalny |
| LanguageTool, Tika, Real-ESRGAN, rembg | HTTP / proces | `config.py:46-48`, `config.py:53`, `config.py:152-154` | usługi na pętli zwrotnej albo programy z katalogu serwera |
| Web Push | VAPID | `push_service.py:34-75` | nasłuch `nexus:run-finished`, usuwanie martwych subskrypcji |
| DNS OVH | API OVH | `deploy/dns/ustaw-dns.py` | poświadczenia poza repozytorium |

---

## 15. Konfiguracja

Jedno źródło: zmienne środowiskowe z prefiksem `NEXUS_` czytane przez
`pydantic-settings` (`backend/nexus/config.py:16-19`), z 57 pozycjami w
`.env.example`. Obiekt ustawień jest tworzony raz i zapamiętywany
(`config.py:164-167`).

Grupy ustawień:

| Grupa | Przykłady | Odsyłacz |
|---|---|---|
| Baza i katalogi | `DATABASE_URL`, `DATA_DIR`, `STATIC_DIR` | `config.py:21-23` |
| Agent | `CLAUDE_BIN`, `CLAUDE_PROFILE_DIR`, `CLAUDE_MODEL`, `CLAUDE_FALLBACK_MODEL`, `CLAUDE_EFFORT` | `config.py:25-30` |
| Limity przebiegu | `MAX_TOOL_OUTPUT_TOKENS`, `RUN_TIMEOUT_MINUTES`, `TOOL_TIMEOUT_MINUTES`, `MCP_STARTUP_TIMEOUT_S` | `config.py:31-35` |
| Równoległość | `WORKER_CONCURRENCY`, `TOOL_THREADS`, `UPLOAD_LIMIT_MB` | `config.py:37-39` |
| Usługi | `REDIS_URL`, `QDRANT_URL`, `TIKA_URL`, `LANGUAGETOOL_URL`, `CHMURA_URL` | `config.py:41-52` |
| Sesje i adresy | `SESSION_DAYS`, `COOKIE_SECURE`, `COOKIE_DOMAIN`, `PUBLIC_URL`, `LOGIN_ATTEMPTS_PER_15_MIN` | `config.py:63-67` |
| Moduły | sekcje `research`, `biuro`, `pulpit`, `agenci`, `start`, `tworczy`, `rozszerzenie` | `config.py:69-161` |

Ścieżki wyliczane: `files_dir`, `cache_dir`, `work_dir`, `kod_dir`, `downloads_dir`,
`vapid_file` (`config.py:97-110`, `config.py:124-127`, `config.py:138-146`).

Sekrety leżą w plikach w katalogu danych, poza repozytorium: token Claude, hasło chmury,
konfiguracja poczty, klucz Google, klucz Semantic Scholar, klucz VAPID. Zapisują je
skrypty `deploy/zapisz-token.sh`, `deploy/zapisz-poczte.sh`,
`deploy/zapisz-klucz-google.sh`, `deploy/zapisz-klucz-semantic-scholar.sh`.

---

## 16. Wdrożenie

Wdrożenie jest **bez Dockera** (`deploy/instalacja.sh:1-2`); wszystko, co należy do
projektu, trafia do katalogu projektu (`instalacja.sh:4-13`).

```
/danaco/projekty/danaco-nexus
├── .venv/                   środowisko Pythona (uv)
├── programy/qdrant/         pobrany Qdrant v1.19.1
├── dane/postgres/           klaster PostgreSQL 18 (port 5433, gniazdo w dane/run)
├── dane/qdrant/             magazyn wektorowy
├── dane/valkey/             Valkey (bez zapisu na dysk)
├── dane/nextcloud/          chmura osobista (FrankenPHP)
├── dane/claude-profil/      profil CLI, token OAuth (prawa 700)
└── dane/app/                pliki, logi, pamięć podręczna, instalatory
```

Jednostki systemd (`deploy/systemd/`): `danaco-nexus-api`, `danaco-nexus-worker`,
`danaco-nexus-postgres`, `danaco-nexus-qdrant`, `danaco-nexus-valkey`,
`danaco-nexus-languagetool`, `danaco-nexus-chmura`, `danaco-nexus-chmura-cron.timer`
i spinający `danaco-nexus.target`.

Hartowanie jednostek: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`,
`ProtectHome`, zapis wyłącznie do `dane/`
(`deploy/systemd/danaco-nexus-api.service:21-25`,
`deploy/systemd/danaco-nexus-worker.service:29-33`).

Brzeg: Caddy hosta (`deploy/caddy/danaco-nexus.caddy`) z HSTS i `X-Robots-Tag`
(`danaco-nexus.caddy:7-13`), trzema witrynami (`:15`, `:40`, `:71`) i długimi limitami
czasu dla strumieni (`:33-36`).

Sieć: API, Qdrant, LanguageTool i Nextcloud nasłuchują wyłącznie na pętli zwrotnej;
PostgreSQL i Valkey — tylko przez gniazda UNIX (`deploy/postgres/pg_hba.conf`,
`deploy/valkey/valkey.conf`).

Aktualizacja to `git pull && deploy/instalacja.sh` — skrypt jest idempotentny
(`instalacja.sh:16`) i przebudowuje interfejs (`instalacja.sh:48-49`).

**Brak w kodzie**: CI/CD (nie ma `.github/`, `.gitlab-ci.yml` ani innej definicji
potoku), obrazów kontenerów, skryptu kopii zapasowych bazy i plików, procedury
odtworzenia, wdrożenia bez przerwy w działaniu.

---

## 17. Bezpieczeństwo — stan faktyczny

Co jest zrobione:

| Obszar | Realizacja | Odsyłacz |
|---|---|---|
| Hasło administratora | Argon2 z automatycznym przeliczaniem | `auth.py:32`, `auth.py:190-193` |
| Sesje | losowy token, w bazie tylko skrót, `HttpOnly`/`Secure`/`Lax` | `auth.py:41-43`, `auth.py:194-204` |
| CSRF | wymagany nagłówek `X-Nexus-Request` dla metod zmieniających stan | `auth.py:137-138` |
| Ograniczenie logowań | 8 prób / 15 min na adres IP | `auth.py:60-83` |
| Nagłówki | CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` | `app.py:25-36` |
| Osadzanie panelu | wyłącznie `?widok=panel` z osobną listą rodziców ramki | `modules/osadzanie.py:21-45` |
| Pliki | pobieranie jako załącznik, podgląd tylko dla bezpiecznych typów | `api/files.py:25`, `api/files.py:91-100` |
| Nazwy plików | normalizacja i usunięcie separatorów ścieżek | `storage.py:45-53` |
| Ścieżki modułów | walidacja nazw projektów i adresów stron | `agent/przestrzenie.py:10-20`, `tworczy/strony.py:10-11` |
| SSRF | lista dozwolonych adresów IP sprawdzana także po przekierowaniu i przy połączeniu | `research/web.py:1-7` |
| Narzędzia | brak powłoki, limit czasu, anulowanie, pliki po identyfikatorach | `tools/base.py:133-173`, `tools/base.py:106-112` |
| Agent | biała lista narzędzi, zakaz wbudowanych, brak hosta zgód | `runner.py:52`, `runner.py:61-88`, `runner.py:345-347` |
| Klucz API | usuwany ze środowiska procesu CLI | `runner.py:230-236` |
| Treść jako dane | instrukcja systemowa zakazuje wykonywania poleceń z dokumentów i stron | `agent/prompt.py:31-32`, `prompt.py:82` |
| Działania nieodwracalne | wysyłka poczty i usuwanie wydarzeń tylko po zatwierdzeniu | `tools/poczta.py:332-357`, `oczekujace.py:19` |
| Chmura | nagłówek tożsamości usuwany od klienta przed `forward_auth` | `danaco-nexus.caddy:84` |

Czego nie ma:

- drugiego składnika uwierzytelniania ani kluczy dostępu (passkey) — brak w kodzie;
- ograniczenia częstości żądań poza logowaniem — brak w kodzie
  (`LoginThrottle` dotyczy wyłącznie `POST /api/auth/login`);
- dziennika audytowego działań użytkownika i agenta — brak tabeli i brak zapisów;
- terminu ważności i rotacji kluczy urządzeń — `DeviceToken` nie ma pola wygaśnięcia
  (`db.py:106-120`);
- izolacji systemowej pojedynczego wywołania narzędzia (narzędzia dziedziczą uprawnienia
  procesu serwera MCP; `tools/base.py:146-155`);
- zarządzania sekretami poza plikami na dysku;
- szyfrowania danych w spoczynku (baza, pliki, Qdrant);
- skanowania zależności i podpisywania wydań (poza APK Androida).

---

## 18. Obserwowalność — stan faktyczny

- **Dzienniki**: konfiguracja wspólna dla wszystkich procesów
  (`backend/nexus/logging_setup.py:13-22`) — standardowe wyjście błędów (journald)
  i plik z rotacją 5 × 10 MB; serwer MCP pisze bez rotacji, bo procesów jest wiele
  (`logging_setup.py:17-19`, `mcp_server.py:170`). Pliki: `dane/app/logs/api.log`,
  `worker.log`, `mcp.log`.
- **Ślad przebiegu**: każdy przebieg kończy wpis z modelem, liczbą tur i tokenami
  (`runner.py:683-693`); zużycie trafia też do kolumny `runs.usage` (`db.py:193`).
- **Zdarzenia**: `run_events` są pełnym zapisem przebiegu i mogą służyć do analizy
  po fakcie (`db.py:200-210`).
- **Stan limitów konta Claude** jest zapisywany w `settings` pod kluczem `claude.limity`
  i pokazywany w module Agenci (`runner.py:1066-1081`, `modules/agenci.py:91-110`).
- **Diagnostyka**: `python -m nexus.cli doctor` sprawdza bazę, kolejkę zadań, katalog
  danych, programy, Qdrant, Tikę, LanguageTool, Redis, chmurę, modele mowy i CLI
  (`backend/nexus/cli.py`, `backend/nexus/doctor.py`). Kontrola kolejki liczy przebiegi
  stojące w `queued` dłużej niż pięć minut — po tym i tylko po tym widać instalację, która
  przyjmuje zlecenia, ale nie ma procesu roboczego dla swojej bazy. Wyjątek w pojedynczej
  kontroli jest jej wynikiem, a nie końcem diagnostyki.

**Brak w kodzie**: metryk (nie ma `/metrics` ani biblioteki Prometheusa), śladów
rozproszonych (brak OpenTelemetry), zbierania błędów (brak Sentry), logów w formacie
strukturalnym JSON, identyfikatora korelacji w nagłówkach HTTP, alarmów i definicji
poziomów usługi.

---

## 19. Jakość i testy

| Warstwa | Narzędzie | Zakres |
|---|---|---|
| Backend | pytest + pytest-asyncio (`backend/pyproject.toml:40,55-59`) | 6 109 linii w `backend/tests/`: API, agent, narzędzia, OCR, moduły biura, chmura, research, pulpit, tworczy, PostgreSQL |
| Backend — styl | ruff, `line-length = 110`, reguły `E,F,W,I,B,UP` (`backend/pyproject.toml:45-53`) | całość |
| Frontend | vitest + Testing Library, środowisko jsdom (`frontend/package.json:30,35`, `frontend/vite.config.ts:104`) | wybrane moduły |
| Frontend — typy | `tsc --noEmit` przed budową (`frontend/package.json:9`) | całość |
| Rozszerzenie | vitest + Playwright (`extension/e2e/`) | panel wstrzykiwany, prawdziwy serwer testowy |
| Android | Robolectric (`android/android/app/src/test/`) + `scripts/test-mostek.mjs` | protokół mostka, głos, API |
| Desktop | `node --test` (`desktop/test/`) | polityka PowerShell, konfiguracja |

Testy są izolowane od ustawień produkcyjnych (commit `cbf798b`). Katalog testów
instrumentowanych Androida istnieje, ale jest pusty.

**Brak w kodzie**: automatycznego uruchamiania tych bramek — nie ma definicji potoku CI,
więc przejście testów zależy od uruchomienia ręcznego.

---

## 20. Ograniczenia stanu obecnego

Zestawienie faktów, które rozstrzygają o możliwościach skalowania i odporności. Każdy
punkt jest własnością kodu, nie oceną.

| # | Ograniczenie | Skutek | Odsyłacz |
|---|---|---|---|
| 1 | API działa jako jeden proces uvicorn bez `--workers` | cały ruch HTTP, SSE i WebSocket obsługuje jedna pętla zdarzeń | `deploy/systemd/danaco-nexus-api.service:18` |
| 2 | Licznik nieudanych logowań w pamięci procesu | restart kasuje limit; druga replika miałaby własny licznik | `auth.py:60-83` |
| 3 | Zadania modułów twórczych w pamięci procesu API | restart gubi zadanie i jego wynik; brak widoczności między replikami | `tworczy/zadania.py:1-6,57-78` |
| 4 | Rejestr otwartych gniazd komputerów w pamięci procesu | wykrycie podwójnego połączenia działa tylko w jednym procesie | `modules/pulpit.py:53-55` |
| 5 | Nasłuch `nexus:run-finished` w każdym procesie API | wiele replik = wielokrotne powiadomienie push | `modules/push.py:50-54` |
| 6 | Modele mowy i osadzeń w pamięci procesu API | duże zużycie pamięci; obliczenia konkurują z obsługą żądań | `app.py:78-86`, `voice.py:1-7`, `knowledge.py:70-79` |
| 7 | Pliki na dysku lokalnym | proces API i proces roboczy muszą pracować na tym samym systemie plików | `storage.py:56-72` |
| 8 | Sesje Claude Code CLI jako pliki w profilu | proces roboczy musi widzieć ten sam profil; inaczej rozmowa traci kontekst i wraca streszczenie | `runner.py:209-214`, `runner.py:704-719` |
| 9 | Projekty modułu Kod i strony WWW na dysku lokalnym | to samo ograniczenie co wyżej, dla trybu `code` i publikacji stron | `config.py:124-127`, `tworczy/strony.py:3-8` |
| 10 | Schemat bazy tworzony przez `create_all` i ręczne `ADD COLUMN` | brak wycofania zmian, zmiany typu i usunięcia kolumny | `db.py:243-260` |
| 11 | Kolejka bez priorytetów i ponowień | długie badanie blokuje slot na 6 godzin; błąd kończy zadanie bez ponowienia | `worker.py:35-50`, `config.py:117` |
| 12 | Limit podagentów tylko w treści promptu | model może przekroczyć zakładaną równoległość | `agent/prompt.py:71-72` |
| 13 | Ograniczenie częstości tylko w wybranych miejscach | logowanie i operacje konta (`portal/konta.py`), zakładanie kont próbnych (`api/auth.py`) i terminal modułu Kod (`api/modules/kod.py`); pozostałe wywołania są nielimitowane | `auth.py:60-83`, `modules/kod.py` |
| 14 | Pamięć podręczna sum kontrolnych instalatorów w pamięci procesu | drobne, ale to kolejny stan lokalny | `modules/pobieranie.py:27` |
| 15 | Brak kopii zapasowych i procedury odtworzenia | utrata dysku oznacza utratę rozmów, plików i wektorów | brak w `deploy/` |
| 16 | Pełny przebieg testów zakleszcza się przy dwóch jednoczesnych uruchomieniach | bramka wydania staje w okolicy `test_agent.py::test_subagents_become_nested_events`; obejście to limit czasu i osobna blokada (`BRAMKA_LOCK`) | `deploy/wydania/zbuduj.sh`, `backend/tests/fake_claude.py` |
| 17 | Wspólna przestrzeń nazw projektów modułu Kod | nazwa zajęta przez inne konto jest nie do użycia, a odmowa to potwierdza (bez ujawniania właściciela) | `agent/przestrzenie.py`, `api/modules/kod.py` |

---

## 21. Czego nie ma w kodzie

Lista jest częścią opisu stanu — dokumenty pochodne nie mogą zakładać, że te rzeczy
istnieją.

- CI/CD i automatyczne bramki jakości.
- Obrazy kontenerów i deklaratywne środowisko uruchomieniowe.
- Migracje bazy danych (Alembic albo równoważne).
- Magazyn obiektowy dla plików (S3 lub zgodny); brak zmiennych i klienta.
- Kopie zapasowe bazy, plików i kolekcji Qdrant oraz test odtworzenia.
- Metryki, ślady rozproszone, zbieranie błędów, alarmy.
- Dziennik audytowy działań.
- Wielu użytkowników, role, uprawnienia; system zna jedno konto administratora.
- Ograniczenie częstości żądań poza logowaniem.
- Termin ważności i rotacja kluczy urządzeń.
- Automatyczna aktualizacja Nexus Desktop.
- Powiadomienia push na Androidzie przez usługę systemową (jest odpytywanie).
- Szyfrowanie danych w spoczynku.
- Wdrożenie bez przerwy w działaniu (obecnie restart usług przez skrypt instalacyjny).

---

*Koniec dokumentu. Architektura stanu obecnego — Opis stanu faktycznego, wersja 1.0, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Warunki korzystania: [DO DECYZJI OPERATORA] — repozytorium nie zawiera pliku licencji. Kontakt: support@danaco-group.pl*
