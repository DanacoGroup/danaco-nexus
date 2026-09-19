# Danaco Nexus

**Personal AI Workspace for Documents, Images and Automation**

Prywatny asystent AI działający na serwerze Danaco. Interfejs czatu w stylu
Claude/ChatGPT: użytkownik przesyła wiadomość i pliki, a Claude analizuje
zadanie, planuje wykonanie, sam dobiera narzędzia serwera i ich parametry,
wykonuje operacje na plikach i zwraca gotowe wyniki do pobrania.

## Spis treści

1. [Architektura](#architektura)
2. [Narzędzia agenta](#narzędzia-agenta)
3. [Wymagania](#wymagania)
4. [Wdrożenie na serwerze](#wdrożenie-na-serwerze)
5. [Konfiguracja](#konfiguracja)
6. [Rozwój i testy](#rozwój-i-testy)
7. [Bezpieczeństwo](#bezpieczeństwo)
8. [Aplikacja (PWA)](#aplikacja-pwa)
9. [Rozmowa głosowa](#rozmowa-głosowa)
9. [Adresy](#adresy)
10. [Chmura osobista](#chmura-osobista)

## Architektura

```
przeglądarka (Windows, Android, iPhone, tablet)
        │ HTTPS
      Caddy (host) ── NEXUS.DOMENA.PL → 127.0.0.1:8930
        │
  danaco-nexus-api (FastAPI + interfejs React) ──────────┐
        │ kolejka zadań (PostgreSQL)                     │ strumień zdarzeń (SSE)
  danaco-nexus-worker ──► claude -p (Claude Code CLI) ───┤
                               │ MCP (stdio)             │
                          nexus.mcp_server (narzędzia) ──┘
        │
  PostgreSQL 5433 · Qdrant 6335 · LanguageTool 8010 · Tika · Real-ESRGAN · LibreOffice …
```

Agent nie korzysta z API Anthropic. Każde zadanie uruchamia Claude Code CLI
(`claude -p --output-format stream-json`) na subskrypcji konta Claude (token OAuth
w profilu projektu). Narzędzia Nexusa dostarcza serwer MCP uruchamiany przez CLI
na czas zadania; wbudowane narzędzia CLI (Bash, Read, Write, WebFetch…) są
wyłączone. Kontekst rozmowy utrzymuje sesja CLI – pierwsze zadanie ją tworzy
(`--session-id`), kolejne wznawiają (`--resume`).

| Składnik | Rola |
|---|---|
| `frontend/` | Aplikacja PWA (React, TypeScript, Vite, Tailwind CSS): rozmowa z asystentem, załączniki (przycisk, przeciąganie, wklejanie), podgląd i pobieranie wyników, strumieniowanie odpowiedzi; instalowana na Androidzie, iPhonie i Windows. |
| `backend/nexus/api` | API: logowanie administratora, rozmowy, pliki, zadania i strumień zdarzeń SSE. |
| `backend/nexus/worker.py` | Proces roboczy: pobiera zadania z kolejki (`FOR UPDATE SKIP LOCKED`) i uruchamia dla nich agenta. |
| `backend/nexus/agent` | Przebieg agenta przez Claude Code CLI: `claude-opus-5` (zapasowy `claude-sonnet-5`), strumień `stream-json` tłumaczony na zdarzenia interfejsu, historię i rejestr wywołań narzędzi; anulowanie kończy całą grupę procesów. |
| `backend/nexus/events.py` | Powiadomienia o zdarzeniach zadań przez Redis (Valkey) – strumień SSE bez odpytywania bazy. |
| `backend/nexus/mcp_server.py` | Serwer MCP (stdio) z narzędziami Nexusa; pliki wynikowe zapisuje w magazynie, postęp w zdarzeniach zadania. |
| `backend/nexus/tools` | Narzędzia wywoływane przez Claude (tabela niżej). |
| `backend/nexus/ocr` | Rdzeń OCR: przygotowanie obrazu, Tesseract, niewidoczna warstwa tekstowa PDF, eksport TXT/DOCX. |
| PostgreSQL | Pamięć: rozmowy, wiadomości, pliki, zadania, wywołania narzędzi, zdarzenia. |
| Qdrant | Baza wiedzy: semantyczne wyszukiwanie w treści dokumentów (osadzenia liczone lokalnie). |

## Narzędzia agenta

Claude sam decyduje, których narzędzi użyć i z jakimi parametrami.

| Narzędzie | Działanie | Technologia |
|---|---|---|
| `inspect_files` | Rodzaj pliku, strony, warstwa tekstowa, metryki jakości obrazu, parametry audio/wideo, zawartość ZIP | PyMuPDF, OpenCV, FFprobe |
| `view_pages` | Podgląd stron PDF/DOCX/XLSX/PPTX i obrazów dla modelu | PyMuPDF, LibreOffice |
| `extract_text` | Tekst z PDF i dokumentów biurowych | PyMuPDF, Apache Tika |
| `ocr_documents` | OCR wsadowy, przeszukiwalny PDF (wygląd bez zmian), TXT, DOCX | Tesseract, reportlab, pikepdf |
| `enhance_document_scan` | Perspektywa, prostowanie, odszumianie, wyrównanie oświetlenia, krawędzie skanu, czerń-biel | OpenCV, unpaper |
| `enhance_photo` | Balans bieli, ekspozycja, cienie/światła, kontrast, nasycenie, wyostrzenie, proste piony | OpenCV |
| `retouch_portrait` | Naturalny retusz portretu | OpenCV |
| `upscale_image` | Powiększanie i rekonstrukcja szczegółów (AI) | Real-ESRGAN (Vulkan na CPU) |
| `imagemagick` | Dowolna obróbka z bezpiecznej listy operatorów | ImageMagick |
| `convert_images` | Konwersje formatów, łączenie obrazów w PDF | Pillow |
| `convert_documents` | DOC/DOCX/XLSX/PPTX/ODT/RTF/HTML ⇄ PDF itd., SVG → PDF/PNG | LibreOffice, Inkscape |
| `write_document` | Raporty i pisma przygotowane przez asystenta (DOCX, PDF, MD, TXT, XLSX, CSV) | python-docx, LibreOffice |
| `check_grammar` | Pisownia, gramatyka, interpunkcja, styl | LanguageTool |
| `pdf_split`, `pdf_merge`, `pdf_edit_pages` | Podział, łączenie, kolejność, obrót i usuwanie stron | PyMuPDF |
| `detect_document_boundaries` | Wykrywanie granic dokumentów w wielodokumentowym PDF | PyMuPDF, Tesseract |
| `media_process` | Konwersja, wycinanie, kompresja, normalizacja głośności, klatka podglądu | FFmpeg |
| `transcribe_audio` | Transkrypcja mowy z audio i wideo, napisy SRT/VTT | faster-whisper (Whisper) |
| `cloud_browse`, `cloud_import`, `cloud_save` | Pliki w chmurze osobistej: przeglądanie, pobieranie, zapis wyników | Nextcloud (WebDAV) |
| `create_archive`, `extract_archive` | Archiwa ZIP (z ochroną przed zip-slip i bombami ZIP) | zipfile |
| `index_documents`, `search_documents` | Indeksowanie i wyszukiwanie semantyczne dokumentów | Qdrant, fastembed |

## Wymagania

Instalacja działa bez Dockera: magazyn obrazów Dockera na tym serwerze leży na małej
partycji systemowej współdzielonej z innymi projektami, więc usługi Nexusa są
instalowane natywnie (systemd). Wszystko, co należy wyłącznie do projektu,
znajduje się w katalogu projektu (`/danaco/projekty/danaco-nexus`):

| Katalog | Zawartość |
|---|---|
| `.venv/` | środowisko Pythona 3.12 (backend) |
| `programy/qdrant/` | program Qdrant (pobierany przez skrypt instalacji) |
| `dane/postgres/` | własny klaster PostgreSQL 18 (tylko gniazdo uniksowe w `dane/run`, port 5433) |
| `dane/qdrant/` | magazyn Qdrant (127.0.0.1:6335) |
| `programy/valkey/` | Valkey – serwer zgodny z Redis (gniazdo `dane/run/valkey.sock`) |
| `dane/app/` | pliki rozmów, pamięć podręczna, logi aplikacji |
| `dane/claude-profil/` | profil Claude Code CLI projektu (sesje, token OAuth) |
| `.cache/` | pamięć podręczna pip/uv/npm (poza partycją systemową) |

Współdzielone programy serwera są tylko używane: PostgreSQL 18, Java 17,
LanguageTool, Apache Tika (tika-app), Tesseract (pol, eng, osd), unpaper,
ImageMagick, LibreOffice, Inkscape, GIMP, FFmpeg, Real-ESRGAN, Node.js
i Claude Code CLI (`/danaco/programy/node/bin/claude`). Magazyn Dockera
i usługi innych projektów pozostają nietknięte.

## Wdrożenie na serwerze

```bash
cd /danaco/projekty/danaco-nexus
deploy/instalacja.sh
```

Skrypt jest idempotentny (służy też do aktualizacji). Tworzy `.env` z
`.env.example`, instaluje zależności Pythona i buduje interfejs, pobiera Qdrant,
zakłada klaster PostgreSQL i bazę `nexus`, podłącza jednostki systemd z
`deploy/systemd/` (`systemctl link`) i uruchamia usługi:

| Usługa | Rola |
|---|---|
| `danaco-nexus-postgres` | baza (gniazdo `dane/run`, port 5433, uwierzytelnianie peer) |
| `danaco-nexus-qdrant` | baza wiedzy (127.0.0.1:6335/6336) |
| `danaco-nexus-languagetool` | sprawdzanie tekstu (127.0.0.1:8010) |
| `danaco-nexus-api` | API i interfejs (127.0.0.1:8930) |
| `danaco-nexus-worker` | proces roboczy agenta |
| `danaco-nexus-chmura` | chmura osobista Nextcloud (127.0.0.1:8940) |
| `danaco-nexus-chmura-cron.timer` | zadania w tle Nextcloud co 5 minut |
| `danaco-nexus-valkey` | Redis (Valkey): zdarzenia zadań Nexusa, pamięć podręczna i blokady chmury |
| `danaco-nexus.target` | wszystkie powyższe razem |

Usługi działają jako `danaco-serwis:danaco-user` z zabezpieczeniami systemd
(`ProtectSystem=strict`, `ProtectHome`, `NoNewPrivileges`, zapis tylko do `dane/`).

Kroki administratora po instalacji:

```bash
claude setup-token                                   # na koncie Claude właściciela
sudo -u danaco-serwis deploy/zapisz-token.sh         # wklejenie tokenu (bez echa)
deploy/nexus-cli.sh set-password                     # login: admin
deploy/nexus-cli.sh doctor --online
```

Polecenie `doctor` sprawdza bazę, katalog danych, czcionkę warstwy tekstowej,
programy narzędziowe (Tesseract z językami, LibreOffice, FFmpeg, ImageMagick,
unpaper, Inkscape), Real-ESRGAN (test na małym obrazie), Qdrant, Tika,
LanguageTool, Claude Code CLI z tokenem oraz serwer MCP (lista narzędzi).
Z `--online` wykonuje jedno krótkie zapytanie przez CLI.

Publikacja pod domeną: rekordy DNS w strefie OVH ustawia `deploy/dns/ustaw-dns.py`
(`danaco-nexus.pl`, `www`, `cloud` → serwer), a witrynę Caddy hosta opisuje
`deploy/caddy/danaco-nexus.caddy`:

```bash
deploy/dns/ustaw-dns.py
cp deploy/caddy/danaco-nexus.caddy /etc/caddy/witryny/danaco-nexus.caddy
/danaco/programy/caddy/caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload danaco-caddy
```

Aktualizacja: `git pull && deploy/instalacja.sh`.

Dziennik zdarzeń: `journalctl -u danaco-nexus-worker -u danaco-nexus-api -f` oraz
pliki w `dane/app/logs/` (`worker.log`, `api.log`, `mcp.log`).

## Aplikacja (PWA)

Nexus jest progresywną aplikacją WWW: działa w przeglądarce i instaluje się jak
zwykła aplikacja – z własną ikoną, w osobnym oknie na pełnym ekranie, bez pasków
przeglądarki.

| Urządzenie | Instalacja |
|---|---|
| Android (Chrome, Edge, Samsung Internet) | przycisk „Zainstaluj aplikację” w panelu bocznym albo menu przeglądarki → „Zainstaluj aplikację” |
| iPhone / iPad (Safari) | Udostępnij → „Do ekranu początkowego” (instrukcja w panelu bocznym) |
| Windows (Edge, Chrome) | przycisk „Zainstaluj aplikację” albo ikona instalacji w pasku adresu; okno bez paska tytułu (Window Controls Overlay) |

Elementy PWA: manifest (`display: standalone`, skrót „Nowa rozmowa”), ikony zwykłe
i maskowalne (`frontend/scripts/ikony.py`), ikona iOS, service worker (Workbox) z
powłoką aplikacji dostępną offline i komunikatem o nowej wersji. API, pliki
i strumień zadań nigdy nie są buforowane. Interfejs: Tailwind CSS 4, motyw ciemny
domyślnie (jasny i systemowy do wyboru), układ w stylu Claude/ChatGPT, obsługa
wycięć ekranu (safe area) na telefonach.

## Rozmowa głosowa

Przycisk z falą dźwięku obok pola wiadomości otwiera tryb rozmowy: Nexus słucha,
sam wykrywa koniec wypowiedzi, rozpoznaje mowę na serwerze, przekazuje ją Claude
(z dostępem do wszystkich narzędzi i plików rozmowy) i czyta odpowiedź zdanie po
zdaniu, zanim cała zostanie wygenerowana. Potem słucha dalej. Odpowiedź można
przerwać głosem albo dotknięciem kuli; mikrofon można wyciszyć, a głos zmienić
(Gosia, Magda, Marek). W trakcie rozmowy ekran się nie wygasza.

| Element | Technologia | Położenie |
|---|---|---|
| Rozpoznawanie mowy | Whisper large-v3-turbo (faster-whisper, CTranslate2, int8, CPU) | `programy/modele/whisper-large-v3-turbo` |
| Synteza mowy | Piper, polskie głosy gosia, mc_speech, darkman | `programy/modele/piper` |
| API | `/api/voice/config`, `/api/voice/transcribe`, `/api/voice/speak` | proces API (modele w pamięci) |

Wypowiedzi z rozmowy głosowej trafiają do tej samej rozmowy co tekst; Claude
dostaje wtedy wskazówkę, by odpowiadać zwięźle i bez formatowania, oraz niższy
poziom wysiłku (`NEXUS_CLAUDE_VOICE_EFFORT`, domyślnie `low`), żeby odpowiedź
przychodziła szybciej.

## Adresy

| Adres | Zawartość |
|---|---|
| `https://danaco-nexus.pl` | aplikacja (PWA) i API; `/cloud` przechodzi do chmury |
| `https://api.danaco-nexus.pl` | samo API (`/api/*`) dla integracji i automatyzacji |
| `https://cloud.danaco-nexus.pl` | chmura osobista Nextcloud z logowaniem jednokrotnym |

Logowanie jednokrotne: ciasteczko sesji Nexusa obejmuje domenę `danaco-nexus.pl`;
Caddy przed wejściem do chmury pyta Nexusa o sesję (`forward_auth` →
`/api/auth/sso`) i przekazuje tożsamość do Nextcloud (aplikacja `user_saml`, tryb
zmiennej środowiskowej). Wejście do chmury bez sesji prowadzi do logowania Nexusa
i z powrotem. Klienci synchronizacji (komputer, telefon) logują się przez
przeglądarkę tym samym mechanizmem; awaryjnie `https://cloud.danaco-nexus.pl/login?direct=1`.

## Chmura osobista

Częścią Nexusa jest chmura osobista **Nextcloud** pod adresem `cloud.danaco-nexus.pl`:
przechowywanie plików, synchronizacja z komputerem i telefonem (aplikacje Nextcloud
na Windows, Android i iOS), udostępnianie, podgląd i wyszukiwanie. Nextcloud działa
w katalogu projektu na **FrankenPHP** (pojedynczy program PHP, bez instalowania PHP
w systemie) jako usługa `danaco-nexus-chmura` na `127.0.0.1:8940`, z bazą `nextcloud`
we własnym klastrze PostgreSQL projektu. Zadania w tle wykonuje co 5 minut
`danaco-nexus-chmura-cron.timer`.

| Ścieżka | Zawartość |
|---|---|
| `programy/frankenphp/` | serwer PHP (FrankenPHP) |
| `dane/nextcloud/nextcloud/` | kod Nextcloud i jego `config/config.php` |
| `dane/nextcloud/dane/` | pliki użytkownika w chmurze |
| `deploy/chmura/` | konfiguracja serwera (`Caddyfile`), PHP i skrypt instalacji |

Asystent korzysta z chmury przez WebDAV (hasło aplikacji w `dane/app/chmura-token`):

| Narzędzie | Działanie |
|---|---|
| `cloud_browse` | przeglądanie katalogów chmury |
| `cloud_import` | pobranie plików lub całego katalogu z chmury do rozmowy |
| `cloud_save` | zapis wyników (np. PDF po OCR) we wskazanym katalogu chmury |

Przykład: „Zrób OCR wszystkich skanów z katalogu Faktury 2026 w chmurze i zapisz
przeszukiwalne PDF-y w Faktury 2026/OCR”. W interfejsie Nexusa odnośnik
„Chmura osobista” otwiera Nextcloud.

Administracja: `deploy/chmura/occ.sh` (np. `deploy/chmura/occ.sh user:resetpassword admin`
ustawia hasło logowania do chmury – hasło początkowe instalacji jest losowe).

## Konfiguracja

Ustawienia z pliku `.env` (pełna lista z opisami w `.env.example`):

| Zmienna | Znaczenie | Domyślnie |
|---|---|---|
| `NEXUS_DATABASE_URL` | Baza PostgreSQL (gniazdo projektu) | `…@/nexus?host=…/dane/run&port=5433` |
| `NEXUS_CLAUDE_BIN` | Program Claude Code CLI | `/danaco/programy/node/bin/claude` |
| `NEXUS_CLAUDE_PROFILE_DIR` | Profil CLI projektu (token w `oauth-token`) | `dane/claude-profil` |
| `NEXUS_CLAUDE_MODEL` | Model agenta | `claude-opus-5` |
| `NEXUS_CLAUDE_FALLBACK_MODEL` | Model zapasowy przy przeciążeniu | `claude-sonnet-5` |
| `NEXUS_CLAUDE_EFFORT` | Poziom wysiłku (`low`…`max`); puste = domyślny CLI | puste |
| `NEXUS_RUN_TIMEOUT_MINUTES` | Limit czasu jednego zadania | `120` |
| `NEXUS_TOOL_TIMEOUT_MINUTES` | Limit czasu jednego wywołania narzędzia | `90` |
| `NEXUS_DATA_DIR` | Katalog danych aplikacji | `dane/app` |
| `NEXUS_WORKER_CONCURRENCY` | Równolegle obsługiwane zadania | `2` |
| `NEXUS_TOOL_THREADS` | Wątki narzędzi (OCR) na zadanie | `8` |
| `NEXUS_TIKA_URL` | Serwer Tika; puste = tika-app w trybie wsadowym | puste |
| `NEXUS_UPLOAD_LIMIT_MB` | Limit rozmiaru przesyłanego pliku | `2048` |

## Rozwój i testy

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest -q          # testy narzędzi wymagają zainstalowanych programów
.venv/bin/python -m ruff check nexus tests

cd ../frontend
npm ci && npm test && npm run build
```

Testy obejmują rdzeń OCR (dokładność rozpoznawania polskiego tekstu, położenie
warstwy tekstowej na stronach obróconych), wszystkie narzędzia, API (logowanie,
CSRF, limity, kolejka, SSE) i przebieg agenta z atrapą Claude Code CLI
(`tests/fake_claude.py`), która wypisuje strumień `stream-json` i wywołuje
narzędzie przez prawdziwy serwer MCP. Testy wymagające programów narzędziowych
są pomijane, gdy programu brak; testy PostgreSQL wymagają zmiennej
`NEXUS_TEST_POSTGRES_URL` (pusta baza testowa).

## Bezpieczeństwo

- jeden użytkownik (administrator); hasło Argon2, sesje w bazie (w ciasteczku
  `HttpOnly`, `Secure`, `SameSite=Lax` tylko losowy token), ograniczenie prób logowania,
- żądania zmieniające stan wymagają nagłówka `X-Nexus-Request` (ochrona CSRF),
- nagłówki bezpieczeństwa (CSP, `X-Frame-Options`, `nosniff`); pliki pobierane jako
  załączniki, podgląd w przeglądarce tylko dla bezpiecznych typów,
- narzędzia otrzymują wyłącznie identyfikatory plików; programy zewnętrzne są
  uruchamiane bez powłoki, z limitem czasu i możliwością anulowania,
- treść plików traktowana jest przez agenta jako dane, a nie polecenia,
- agent działa przez Claude Code CLI z białą listą narzędzi (tylko serwer MCP Nexusa
  i ToolSearch); wbudowane narzędzia CLI (powłoka, pliki, sieć) są zakazane, a klucz
  API nie jest przekazywany do procesu CLI,
- token OAuth leży w profilu projektu z prawami `600` (właściciel `danaco-serwis`),
- API i usługi pomocnicze nasłuchują wyłącznie na pętli zwrotnej hosta; PostgreSQL
  tylko na gnieździe uniksowym z uwierzytelnianiem peer.
