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

## Architektura

```
przeglądarka (Windows, Android, iPhone, tablet)
        │ HTTPS
      Caddy (host) ── NEXUS.DOMENA.PL → 127.0.0.1:8930
        │
  api (FastAPI + interfejs React) ──────────┐
        │ kolejka zadań (PostgreSQL)        │ strumień zdarzeń (SSE)
  worker (agent Claude + narzędzia) ────────┘
        │
  PostgreSQL · Qdrant · Apache Tika · LanguageTool · Real-ESRGAN (host)
```

| Składnik | Rola |
|---|---|
| `frontend/` | Aplikacja WWW (React, TypeScript, Vite): historia rozmów, czat, załączniki (przycisk, przeciąganie, wklejanie), podgląd i pobieranie wyników, strumieniowanie odpowiedzi. |
| `backend/nexus/api` | API: logowanie administratora, rozmowy, pliki, zadania i strumień zdarzeń SSE. |
| `backend/nexus/worker.py` | Proces roboczy: pobiera zadania z kolejki (`FOR UPDATE SKIP LOCKED`) i prowadzi pętlę agenta. |
| `backend/nexus/agent` | Pętla agenta: `claude-opus-5`, myślenie adaptacyjne, strumieniowanie, pamięć podręczna promptu, server-side fallbacks, zapis każdego kroku. |
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
| `create_archive`, `extract_archive` | Archiwa ZIP (z ochroną przed zip-slip i bombami ZIP) | zipfile |
| `index_documents`, `search_documents` | Indeksowanie i wyszukiwanie semantyczne dokumentów | Qdrant, fastembed |

## Wymagania

- serwer z Dockerem i Docker Compose (magazyn obrazów na partycji z ok. 10 GB wolnego miejsca),
- klucz API Anthropic (`ANTHROPIC_API_KEY`),
- Caddy na hoście z domeną wskazującą serwer (rekord DNS A),
- Real-ESRGAN (`realesrgan-ncnn-vulkan` z modelami) w katalogu hosta montowanym do procesu roboczego.

Serwer `danaco-server` ma dwie cechy, które uwzględnia konfiguracja stosu:

- **zapora hosta blokuje ruch wychodzący kontenerów w sieci mostkowej** (`FORWARD DROP`) –
  proces roboczy działa w sieci hosta, a usługi pomocnicze nasłuchują tylko na `127.0.0.1`;
  obrazy buduje skrypt `deploy/build.sh` z opcją `--network host`,
- **Docker przechowuje obrazy w magazynie containerd na partycji systemowej** (9,6 GB) –
  przed pierwszą budową trzeba przenieść magazyn na `/danaco` skryptem
  `deploy/przeniesienie-containerd.sh` (wymaga uprawnień root i krótkiego restartu Dockera).

## Wdrożenie na serwerze

```bash
cd /danaco/projekty/danaco-nexus
cp .env.example .env            # uzupełnić ANTHROPIC_API_KEY i POSTGRES_PASSWORD
mkdir -p data/app data/postgres data/qdrant
sudo ./deploy/przeniesienie-containerd.sh   # jednorazowo, patrz „Wymagania”
./deploy/build.sh
docker compose up -d
docker compose exec api python -m nexus.cli set-password   # login: admin
docker compose exec worker python -m nexus.cli doctor --online
```

Polecenie `doctor` sprawdza bazę, katalog danych, czcionkę warstwy tekstowej,
programy narzędziowe (Tesseract z językami, LibreOffice, FFmpeg, ImageMagick,
unpaper, Inkscape), Real-ESRGAN (test na małym obrazie), usługi Qdrant, Tika
i LanguageTool oraz klucz API Claude (odczyt metadanych modelu, bez
generowania tokenów).

Publikacja pod domeną (plik witryny Caddy, zgodnie z konwencją serwera):

```bash
sed 's/NEXUS.DOMENA.PL/nexus.twoja-domena.pl/' deploy/caddy/danaco-nexus.caddy \
    > /etc/caddy/witryny/danaco-nexus.caddy
caddy validate --config /etc/caddy/Caddyfile && caddy reload --config /etc/caddy/Caddyfile
```

Aktualizacja: `git pull && ./deploy/build.sh && docker compose up -d`.

Dziennik zdarzeń: `docker compose logs -f worker api` oraz pliki w `data/app/logs/`.

## Konfiguracja

Ustawienia z pliku `.env` (pełna lista z opisami w `.env.example`):

| Zmienna | Znaczenie | Domyślnie |
|---|---|---|
| `ANTHROPIC_API_KEY` | Klucz API Claude | – (wymagany) |
| `POSTGRES_PASSWORD` | Hasło bazy stosu | – (wymagany) |
| `NEXUS_ANTHROPIC_MODEL` | Model agenta | `claude-opus-5` |
| `NEXUS_ANTHROPIC_EFFORT` | Poziom wysiłku (`low`…`max`); puste = `high` | puste |
| `NEXUS_PORT` | Port API na `127.0.0.1` | `8930` |
| `NEXUS_DATA_DIR` | Katalog danych | `./data` |
| `NEXUS_WORKER_CONCURRENCY` | Równolegle obsługiwane zadania | `2` |
| `NEXUS_TOOL_THREADS` | Wątki narzędzi (OCR) na zadanie | `8` |
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
CSRF, limity, kolejka, SSE) i pętlę agenta z atrapą klienta Claude. Testy
wymagające programów narzędziowych są pomijane, gdy programu brak.

## Bezpieczeństwo

- jeden użytkownik (administrator); hasło Argon2, sesje w bazie (w ciasteczku
  `HttpOnly`, `Secure`, `SameSite=Lax` tylko losowy token), ograniczenie prób logowania,
- żądania zmieniające stan wymagają nagłówka `X-Nexus-Request` (ochrona CSRF),
- nagłówki bezpieczeństwa (CSP, `X-Frame-Options`, `nosniff`); pliki pobierane jako
  załączniki, podgląd w przeglądarce tylko dla bezpiecznych typów,
- narzędzia otrzymują wyłącznie identyfikatory plików; programy zewnętrzne są
  uruchamiane bez powłoki, z limitem czasu i możliwością anulowania,
- treść plików traktowana jest przez agenta jako dane, a nie polecenia,
- API i usługi pomocnicze nasłuchują wyłącznie na pętli zwrotnej hosta.
