# Moduł Research i Baza wiedzy

Gałąź: `modul/research`. Wzorce: Sider Deep Research, Scholar Research i Wisebase.

- **Research** (`/m/research`) – badanie tematu w wielu źródłach: pytanie, rodzaj (Deep Research –
  sieć; Scholar – tylko prace naukowe), głębokość, kolekcja na źródła. Postęp na żywo (wyszukiwania,
  przeczytane strony), raport w Markdown z klikalnymi przypisami `[n]`, lista źródeł i panel
  źródła obok raportu (podgląd treści strony, zapis w bazie wiedzy), „Dopytaj w czacie”, kopiowanie
  i pobranie raportu jako `.md`.
- **Baza wiedzy** (`/m/wiedza`) – kolekcje stron, plików, prac naukowych i notatek; dodawanie adresu
  (HTML lub PDF), pliku (PDF, TXT/MD/CSV/HTML, dokumenty biurowe przez Apache Tika) i notatki
  Markdown; wyszukiwanie po znaczeniu; rozmowa z wybranymi dokumentami albo całą kolekcją.

## Budowa

| Warstwa | Pliki |
|---|---|
| Pobieranie stron, SSRF, wyszukiwarka | `backend/nexus/research/web.py` |
| Bazy prac naukowych, cytowania APA | `backend/nexus/research/scholar.py` |
| Zapis i indeksowanie (wspólne dla API i narzędzi) | `backend/nexus/research/store.py` |
| Tabele | `backend/nexus/models/research.py` |
| API `/api/research` | `backend/nexus/api/modules/research.py` |
| Narzędzia agenta | `backend/nexus/tools/research.py` |
| Instrukcja trybu `research` | `backend/nexus/agent/tryby/research.md` |
| Interfejs | `frontend/src/modules/research/`, `frontend/src/modules/wiedza/` |

### Tabele

- `research_collections` – kolekcje (nazwa, opis).
- `research_sources` – źródła: rodzaj (`strona`, `plik`, `praca`, `tekst`), adres, tytuł, treść,
  metadane (opis, witryna, autorzy, DOI, rok, cytowanie), powiązany plik, stan indeksu.
- `research_notes` – notatki (Markdown), opcjonalnie powiązane ze źródłem.
- `research_reports` – badania: rozmowa z raportem, rodzaj, pytanie, głębokość, kolekcja.

Treść źródeł i notatek trafia do Qdrant przez istniejący `nexus/knowledge.py`; identyfikator
źródła lub notatki pełni w indeksie rolę `file_id`, więc `search_documents` z `file_ids`
przeszukuje wybrane dokumenty bazy wiedzy. Indeksowanie w API odbywa się w tle (po odpowiedzi);
błąd bazy wektorowej nie blokuje zapisu – źródło ma wtedy `index_error` i przycisk „Indeksuj ponownie”.

### Narzędzia agenta

| Narzędzie | Opis |
|---|---|
| `web_fetch_page` | Strona HTML/PDF/tekst → czysty tekst, tytuł, metadane; czytanie częściami (`offset`). |
| `web_search` | Wyszukiwarka zapasowa (SearXNG, gdy ustawiono `NEXUS_RESEARCH_SEARXNG_URL`, inaczej DuckDuckGo HTML). |
| `scholar_search` | OpenAlex + Semantic Scholar + arXiv + Crossref równolegle; scalanie po DOI/tytule; lata, dziedzina. |
| `scholar_paper` | Szczegóły pracy po DOI, arXiv, OpenAlex, Semantic Scholar lub tytule (TL;DR, odwołania, APA). |
| `knowledge_save` | Zapis źródła (pobranie strony albo podana treść) w kolekcji; ten sam adres jest aktualizowany. |
| `knowledge_notes` | Dodawanie i przegląd notatek. |
| `knowledge_read` | Treść źródła/notatki, spis kolekcji albo lista kolekcji. |

### Ochrona SSRF

Dozwolone są tylko `http`/`https` z publicznym adresem IP (`ipaddress.is_global`, bez adresów
grupowych, z rozpakowaniem IPv4 w IPv6). Blokowane są m.in. `localhost`, `*.local`, sieci prywatne,
`100.64/10`, `169.254/16`, liczbowe zapisy adresów (`2130706433`, `0x7f.0.0.1`) i adresy z danymi
logowania. Sprawdzenie następuje przed każdym żądaniem i po każdym przekierowaniu, a klient
produkcyjny (`safe_client`) łączy się wyłącznie z już sprawdzonym adresem IP (własny backend
`httpcore`), więc podmiana DNS między sprawdzeniem a połączeniem (DNS rebinding) nie działa.
Proxy z otoczenia są wyłączone. Limit rozmiaru: `NEXUS_RESEARCH_PAGE_MAX_MB`.

### API (`/api/research`, sesja lub klucz urządzenia; zmiany wymagają `X-Nexus-Request: 1` w przeglądarce)

| Metoda i ścieżka | Opis |
|---|---|
| `GET/POST /kolekcje`, `PATCH/DELETE /kolekcje/{id}` | Kolekcje (usunięcie usuwa też źródła, notatki i indeks). |
| `GET/POST /kolekcje/{id}/zrodla` | Lista źródeł; dodanie `{url}` / `{file_id}` / `{title, content}`. |
| `GET/PATCH/DELETE /zrodla/{id}`, `POST /zrodla/{id}/indeksuj` | Źródło z treścią, zmiana tytułu lub kolekcji, usunięcie, ponowne indeksowanie. |
| `GET/POST /kolekcje/{id}/notatki`, `PATCH/DELETE /notatki/{id}` | Notatki. |
| `GET /szukaj?q=&collection_id=` | Wyszukiwanie semantyczne (źródła i notatki). |
| `POST /podglad {url}` | Treść strony bez zapisu (panel źródła). |
| `POST /badania {question, kind, depth, collection_id?, save_sources}` | Nowe badanie: rozmowa z `meta = {"mode": "research", "depth", "research_kind", "collection_id"}` i wysłane pytanie; zwraca `id`, `conversation_id`, `run_id`. |
| `GET /badania`, `GET/DELETE /badania/{id}` | Lista badań ze stanem zadania; raport (tekst ostatniej odpowiedzi agenta); usunięcie z listy (rozmowa zostaje). |
| `POST /rozmowa {source_ids?, note_ids?, collection_id?, question?}` | Rozmowa z dokumentami: `meta = {"mode": "chat", "knowledge": {...}}`, pierwsza wiadomość zawiera spis dokumentów i sposób ich czytania. |

## Ustawienia (`.env`, blok „moduł research”)

`NEXUS_RESEARCH_PAGE_MAX_MB`, `NEXUS_RESEARCH_PAGE_MAX_CHARS`, `NEXUS_RESEARCH_FETCH_TIMEOUT_S`,
`NEXUS_RESEARCH_CONTACT_EMAIL` (OpenAlex/Crossref „polite pool”), `NEXUS_RESEARCH_SEARXNG_URL`,
`NEXUS_RESEARCH_SEMANTIC_SCHOLAR_KEY_FILE`.

Klucz Semantic Scholar jest opcjonalny (bez niego wspólny limit zapytań kończy się często
odpowiedzią 429 – narzędzie ponawia raz i zwraca wyniki pozostałych baz). Zapis klucza:
`sudo -u danaco-serwis deploy/zapisz-klucz-semantic-scholar.sh`.

## Zależności od innych strumieni

- **agenci**: dołącza `backend/nexus/agent/tryby/research.md` do promptu rozmów z `meta.mode == "research"`
  i włącza WebSearch/WebFetch CLI. Do tego czasu parametry badania i najważniejsze zasady raportu
  są w samej pierwszej wiadomości, a agent ma zapasowe `web_search` i `web_fetch_page`.
- **start**: powłoka z nawigacją modułów wyświetla `/m/research` i `/m/wiedza`; `openConversation`
  otwiera rozmowę z raportem lub z dokumentami. Otwarte badanie jest w adresie jako `?badanie=<id>`.

## Znane ograniczenia

- arXiv odrzuca kodem 406 część zapytań wyszukiwania wysyłanych przez httpx (te same zapytania
  z urllib/curl przechodzą) – `scholar.py` ma zapasową ścieżkę przez `urllib`.
- DuckDuckGo w wersji HTML może okresowo blokować zapytania automatyczne; stabilniejsza jest
  własna instancja SearXNG.
- Strony renderowane wyłącznie przez JavaScript zwracają mało treści (brak przeglądarki bezgłowej
  w `web_fetch_page`).
