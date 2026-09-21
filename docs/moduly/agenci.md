# Moduł agenci: wiele sesji, podagenci, tryby rozmów, moduł Kod

Gałąź `modul/agenci`. Zakres: proces roboczy wykonujący kilka zadań naraz, orkiestracja
podagentów Claude Code widoczna w czacie, tryby rozmów (`chat`, `research`, `code`,
`strona`), powiadomienie o zakończeniu zadania, moduł **Kod** (projekty i sesje
programistyczne) oraz moduł **Agenci** (podgląd wszystkich sesji).

## Spis treści

1. [Wiele sesji równolegle](#wiele-sesji-równolegle)
2. [Podagenci](#podagenci)
3. [Tryby rozmów](#tryby-rozmów)
4. [Moduł Kod](#moduł-kod)
5. [Moduł Agenci](#moduł-agenci)
6. [Ustawienia](#ustawienia)
7. [Bezpieczeństwo i ryzyko](#bezpieczeństwo-i-ryzyko)
8. [Testy](#testy)

## Wiele sesji równolegle

| Element | Działanie |
|---|---|
| `worker_concurrency` | domyślnie **4** zadania naraz w jednym procesie roboczym (wcześniej 2) |
| Kolejność w rozmowie | bez zmian: kolejne wiadomości jednej rozmowy czekają na zakończenie poprzedniej |
| Anulowanie | jak dotąd: `POST /api/runs/{id}/cancel` kończy całą grupę procesów CLI (z serwerem MCP i podagentami) |
| Zatrzymanie procesu | po `SIGTERM` bieżące zadania mają `worker_stop_grace_s` (90 s) na zakończenie, potem są przerywane ze statusem „przerwane (restart procesu roboczego)” – mieści się w `TimeoutStopSec=120` |
| Odzyskiwanie | co 60 s (nie tylko przy starcie) zadania bez sygnału życia od 3 min są oznaczane jako przerwane – nie blokują już rozmowy |
| SQLite | kolejka działa też na SQLite (testy, rozwój) – bez `FOR UPDATE SKIP LOCKED` |

Każde zadanie to osobny proces `claude -p` z własnym serwerem MCP. Cztery równoległe
zadania to cztery sesje konta Claude naraz, a każda może uruchomić podagentów – limit
5-godzinny i tygodniowy konta wyczerpuje się szybciej. Ograniczenia ryzyka:

- runner zapisuje stan limitów ze zdarzeń `rate_limit_event` CLI (ustawienie
  `claude.limity` w tabeli `settings`) i przy wykorzystaniu ≥ 90% dodaje w czacie
  ostrzeżenie; moduł Agenci pokazuje paski wykorzystania,
- instrukcja systemowa każe zlecać podagentom tylko zadania dzielące się na niezależne
  części i ogranicza ich liczbę naraz (`agenci_max_podagentow`),
- `NEXUS_CLAUDE_SUBAGENT_MODEL=claude-sonnet-5` przenosi pracę podagentów na tańszy model,
- `NEXUS_WORKER_CONCURRENCY` można w każdej chwili zmniejszyć (restart procesu roboczego).

## Podagenci

Claude Code CLI 2.1.270 (sprawdzone na serwerze):

- `--tools "ToolSearch,Agent,WebSearch,WebFetch"` ogranicza **wbudowane** narzędzia całej
  sesji – podagenci dziedziczą ten zestaw (próba: podagent `general-purpose` nie miał
  dostępu do Bash), a MCP ogranicza `--strict-mcp-config` do serwera Nexusa,
- `--agents` definiuje podagenta `pomocnik` z jawną listą narzędzi (narzędzia Nexusa,
  ToolSearch, sieć; w trybie `code` także narzędzia programistyczne) – bez narzędzia Agent,
  więc nie zleca pracy dalej,
- `--forward-subagent-text` przekazuje tekst podagentów w strumieniu (zdarzenia
  `assistant` z `parent_tool_use_id`),
- podagenci domyślnie pracują w tle: wynik narzędzia Agent to „Async agent launched…”,
  postęp przychodzi w `system/task_progress`, wynik w `system/task_notification`,
  a CLI rozpoczyna kolejną turę (nowy `init` i drugi `result`).

Tłumaczenie strumienia (`backend/nexus/agent/runner.py`) na zdarzenia interfejsu – bez
nowych typów zdarzeń SSE, więc starsi klienci wyświetlają podagentów jak zwykłe narzędzia:

| Strumień CLI | Zdarzenie Nexusa |
|---|---|
| `tool_use` Agent (bez rodzica) | `tool.started` z `name: "podagent"` i `agent: {description, subagent_type, background}` |
| `tool_use` z `parent_tool_use_id` | `tool.started` z `parent_tool_use_id` |
| tekst podagenta | `text.block` + `text.delta` z `parent_tool_use_id` |
| `task_progress`, uruchomienie w tle | `tool.progress` z `tool_use_id` podagenta |
| wynik narzędzia Agent albo `task_notification` | `tool.finished` podagenta (podsumowanie i pliki wszystkich jego narzędzi) |

Historia rozmowy zawiera tylko wpisy agenta głównego; podagent zostaje w niej jako
narzędzie `podagent` z podsumowaniem i plikami. Wywołania narzędzi podagentów są
w tabeli `tool_calls`. Zużycie przebiegu to suma wszystkich tur CLI.

Interfejs (`frontend/src/runState.ts`, `frontend/src/components/Turns.tsx`): podagent to
element narzędzia z polem `agent` (`AgentItem`, zagnieżdżone `agent.items`); w czacie
zwijany blok „Podagent: <opis>” ze stanem, liczbą narzędzi, postępem, plikami i po
rozwinięciu – własnym tekstem, narzędziami i ewentualnymi kolejnymi podagentami.
Postęp narzędzia MCP trafia do właściwego wywołania dzięki identyfikatorowi
`_meta["claudecode/toolUseId"]` z żądania MCP (gdy CLI go przekazuje; w przeciwnym razie –
jak dotąd – do ostatniego trwającego wywołania o tej nazwie).

## Tryby rozmów

`Conversation.meta.mode ∈ {chat, research, code, strona}` (nieznany = `chat`).

| Tryb | Zmiana w poleceniu CLI |
|---|---|
| każdy | `--append-system-prompt` z pliku `backend/nexus/agent/tryby/<tryb>.md`, jeśli istnieje |
| `research` | limit czasu `run_timeout_research_minutes` (360 min) zamiast `run_timeout_minutes` |
| `code` | narzędzia Read, Write, Edit, Glob, Grep, Bash; katalog roboczy = projekt; `--add-dir <projekt>`, `--permission-mode acceptEdits`; autor commitów z `kod_git_*` |

Pliki `research.md` i `strona.md` dostarczają strumienie `research` i `tworczy`; ten
strumień dostarcza `code.md`. Narzędzia WebSearch i WebFetch są włączone ustawieniem
`claude_web_tools` (domyślnie tak). We wszystkich trybach `--permission-prompts none`:
wszystko, co wymagałoby zgody, jest odrzucane.

Po zakończeniu każdego zadania runner publikuje w Redis kanał `nexus:run-finished`
z JSON `{"run_id", "conversation_id", "status", "title"}` (`EventBus.notify_finished`) –
strumień `start` wysyła na tej podstawie Web Push.

## Moduł Kod

Projekty leżą w `<data_dir>/kod/<nazwa>` (produkcyjnie `dane/app/kod/`). Nazwa: litery,
cyfry, `._-`, do 64 znaków. Rozmowa programistyczna to zwykła rozmowa z
`meta = {"mode": "code", "workspace": "<nazwa>"}` – w czacie widać ją jak każdą inną.

API (`backend/nexus/api/modules/kod.py`, wymaga sesji):

| Metoda i adres | Działanie |
|---|---|
| `GET /api/kod/projekty` | lista projektów (gałąź, data zmiany) |
| `POST /api/kod/projekty` `{name, repo_url}` | `git init` z pierwszym commitem albo `git clone` (tylko `https://`, bez danych logowania, parametrów i adresów lokalnych; bez podmodułów) |
| `DELETE /api/kod/projekty/{nazwa}` | usuwa katalog (409, gdy w projekcie trwa zadanie) |
| `GET …/{nazwa}/drzewo?sciezka=` | zawartość katalogu (bez `.git`) |
| `GET …/{nazwa}/plik?sciezka=` | treść pliku do podglądu (do `kod_file_preview_kb`, pliki binarne bez treści) |
| `GET …/{nazwa}/pobierz?sciezka=` | pobranie pliku |
| `GET …/{nazwa}/zip` (`?git=1`) | cały projekt jako ZIP |
| `GET …/{nazwa}/git/status`, `git/diff?sciezka=`, `git/log`, `git/commit/{hash}` | zmiany, różnice (także nowych plików), historia, jeden commit |
| `GET`/`POST …/{nazwa}/rozmowy` | rozmowy trybu `code` projektu / nowa rozmowa |

Ścieżki są sprawdzane (`nexus/agent/przestrzenie.py`): bez ścieżek bezwzględnych,
liter dysków, `..` i dowiązań prowadzących poza projekt.

Interfejs (`frontend/src/modules/kod/`): lista projektów (tworzenie, klonowanie), drzewo
plików, podgląd z numeracją wierszy i podświetlaniem składni (highlight.js – rdzeń z 23
językami), zakładki „Zmiany” i „Historia” z kolorowanymi różnicami, pobranie ZIP; po
prawej (na telefonie – zakładka) sesja Claude Code: wybór rozmowy projektu, polecenia,
strumień odpowiedzi z narzędziami i podagentami, zatrzymanie, „W czacie”. Po zakończeniu
zadania drzewo i zmiany odświeżają się.

## Moduł Agenci

API (`backend/nexus/api/modules/agenci.py`):

| Metoda i adres | Działanie |
|---|---|
| `GET /api/agenci/zadania?zakonczone=20` | zadania w toku i zakończone w ostatnich 24 h: tryb, czas, liczba narzędzi, ostatnia czynność, drzewo podagentów (stan, postęp, podsumowanie); konfiguracja (miejsca, kolejka) i limity konta |
| `POST /api/agenci/zadania` `{text, mode, workspace}` | nowe zadanie w tle: osobna rozmowa w wybranym trybie i wiadomość w kolejce |

Anulowanie – istniejące `POST /api/runs/{id}/cancel`.

Interfejs (`frontend/src/modules/agenci/`): odświeżany co 2,5 s widok zadań w toku
i zakończonych z drzewem podagentów, przyciski „Anuluj” i przejście do rozmowy, formularz
„Nowe zadanie w tle” (tryb, projekt dla trybu Kod), paski limitów 5-godzinnego
i tygodniowego.

## Ustawienia

Blok `# --- moduł agenci ---` w `backend/nexus/config.py` i `.env.example`:

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `NEXUS_WORKER_CONCURRENCY` | `4` | liczba zadań wykonywanych naraz |
| `NEXUS_CLAUDE_SUBAGENTS` | `true` | narzędzie Agent i podagent `pomocnik` |
| `NEXUS_CLAUDE_WEB_TOOLS` | `true` | WebSearch i WebFetch |
| `NEXUS_CLAUDE_SUBAGENT_MODEL` | pusty | model podagentów (pusty = główny) |
| `NEXUS_AGENCI_MAX_PODAGENTOW` | `15` | liczba podagentów naraz podawana w instrukcji |
| `NEXUS_RUN_TIMEOUT_RESEARCH_MINUTES` | `360` | limit czasu trybu `research` |
| `NEXUS_WORKER_STOP_GRACE_S` | `90` | czas na dokończenie zadań przy zatrzymaniu |
| `NEXUS_KOD_GIT_NAME`, `NEXUS_KOD_GIT_EMAIL` | `Danaco Nexus`, `nexus@danaco-nexus.pl` | autor commitów w projektach |
| `NEXUS_KOD_CLONE_TIMEOUT_S` | `600` | limit czasu klonowania |
| `NEXUS_KOD_FILE_PREVIEW_KB` | `1024` | największy podgląd pliku |

## Bezpieczeństwo i ryzyko

Tryb `code` daje agentowi Bash. Ograniczenia:

1. usługa działa jako `danaco-serwis` z `ProtectSystem=strict`, `ProtectHome`,
   `NoNewPrivileges` – zapis tylko w `dane/`,
2. katalog roboczy i `--add-dir` to katalog projektu; `acceptEdits` akceptuje edycje
   w katalogach roboczych, a działania wymagające zgody (według zasad Claude Code m.in.
   zapis poza katalogami roboczymi) są odrzucane, bo zgody są wyłączone
   (`--permission-prompts none`; zapis poza projektem nie był sprawdzany próbą),
3. reguły `--disallowed-tools` blokują m.in. `sudo`, `su`, `curl`, `wget`, `ssh`, `scp`,
   `rsync`, `nc`, `git push/fetch/pull/remote`, `npm publish`, `systemctl` (sprawdzone:
   `curl` odrzucony), a instrukcja `tryby/code.md` zabrania wychodzenia poza projekt,
   poleceń sieciowych i czytania sekretów.

**To już nie jest ograniczenie „w dobrej wierze”.** Od 20 września 2026 proces CLI startuje
w osobnej przestrzeni montowań (`bwrap`, `backend/nexus/agent/piaskownica.py`): widzi katalog
projektu, profil sesji, katalog roboczy zadania i łańcuch narzędzi `/danaco/programy`
do odczytu — i nic poza tym. Kodu Nexusa, pozostałych projektów, katalogu producenta i kluczy
w tej przestrzeni po prostu nie ma, więc `Read` i `Bash` nie mają skąd ich wziąć. Serwer
narzędzi MCP potrzebuje kodu i bazy, więc stoi **poza** piaskownicą i rozmawia z CLI przez
gniazdo w katalogu zadania (`agent/most_mcp.py`). Środowisko procesu powstaje od zera
(`--clearenv` plus wykaz dodający): wchodzą `PATH`, `HOME`, język, katalog tymczasowy
i własne zmienne CLI (`CLAUDE_*`, `MCP_*`, `GIT_*`) — żadnej zmiennej `NEXUS_*`, więc
adres bazy i ścieżki do plików z kluczami zostają po stronie serwera.
Testy: `backend/tests/test_piaskownica.py`.

**Ryzyko rezydualne:** sieć zostaje włączona (bez niej nie ma połączenia z silnikiem modelu),
więc program uruchomiony w projekcie może wyjść do internetu; reguły `--disallowed-tools`
i instrukcja trybu ograniczają to tylko po stronie poleceń agenta. Łańcuch narzędzi jest
wspólny dla wszystkich kont — to programy, nie dane, ale ich obecność da się wykryć.
Źródłem zagrożenia pozostaje złośliwa treść w projekcie (np. sklonowane repozytorium
z instrukcjami dla modelu): może zużyć zakres pracy konta i wysłać w świat to, co jest
w tym projekcie. Zalecenie: klonować tylko zaufane repozytoria.

Podagenci korzystają z tych samych narzędzi co sesja – nie rozszerzają uprawnień. Treść
stron (WebFetch) i plików to dane, nie polecenia (instrukcja systemowa i instrukcja
podagenta).

## Testy

| Plik | Zakres |
|---|---|
| `backend/tests/test_agent.py` | pełna ścieżka z atrapą CLI: scenariusz `agents` (podagent na pierwszym planie z narzędziem MCP, podagent w tle, `task_progress`, `task_notification`, dwie tury, ostrzeżenie o limicie), tryb `code` w katalogu projektu, 4 sesje równolegle w procesie roboczym (SQLite), przerwanie przy zatrzymaniu |
| `backend/tests/test_agenci.py` | flagi CLI trybów, zapis powiadomienia `nexus:run-finished`, kolejka na SQLite, bezpieczne ścieżki, adresy klonowania, `git status`, API modułów Kod (cykl życia projektu z git) i Agenci |
| `frontend/src/__tests__/podagenci.test.ts` | zagnieżdżanie zdarzeń podagentów w `runState` |
| `frontend/src/__tests__/moduly-agenci-kod.test.tsx` | drzewo podagentów, czas trwania, podświetlanie (kodowanie HTML), blok podagenta w czacie |

Próba na prawdziwym CLI (serwer, katalog `.tmp/agenci`, model `claude-sonnet-5`): tryb
`code` z podagentem – podagent w tle utworzył `hello.py` (Write) i uruchomił go (Bash),
`curl` został odrzucony, zdarzenia zagnieżdżone i wynik podagenta zapisane poprawnie.
