# Moduły twórcze (`modul/tworczy`)

Cztery moduły aplikacji wzorowane na narzędziach Sider (Web Creator, Image Upscaler,
Background Changer, Tłumacz): **Strony**, **Obrazy**, **Tłumacz**, **Studio**.

## Spis treści

1. [Przegląd plików](#przegląd-plików)
2. [Strony – Twórca stron](#strony--twórca-stron)
3. [Obrazy](#obrazy)
4. [Tłumacz](#tłumacz)
5. [Studio audio/wideo](#studio-audiowideo) — w tym [montaż filmu](#montaż-film-ze-zdjęć-i-klipów) i [spot dźwiękowy](#spot-i-intro-dźwiękowe)
6. [Zadania w tle modułów](#zadania-w-tle-modułów)
7. [Konfiguracja](#konfiguracja)
8. [Testy](#testy)
9. [Uwagi do scalenia](#uwagi-do-scalenia)

## Przegląd plików

| Warstwa | Pliki |
|---|---|
| Logika | `backend/nexus/tworczy/strony.py` (magazyn stron), `obrazy.py` (tło, gumka), `tlumaczenie.py` (tłumacz i dokumenty), `zadania.py` (zadania w tle API) |
| Narzędzia agenta | `backend/nexus/tools/strony.py`, `obrazy.py`, `tlumacz.py` |
| API | `backend/nexus/api/modules/strony.py` (też `/s/…`), `obrazy.py`, `tlumacz.py` |
| Tryb rozmowy | `backend/nexus/agent/tryby/strona.md` |
| Interfejs | `frontend/src/modules/strony/`, `obrazy/`, `tlumacz/`, `studio/`, wspólne: `frontend/src/modules/_tworczy/` (bez `index.tsx`, więc nie jest modułem) |
| Testy | `backend/tests/test_tworczy.py`, `frontend/src/__tests__/tworczy.test.tsx` |

## Strony – Twórca stron

**Przepływ:** użytkownik podaje nazwę i opis → `POST /api/strony` zakłada stronę
(tymczasowy `index.html`) i rozmowę z `meta = {"mode": "strona", "site": "<adres>"}` →
interfejs wysyła opis jako pierwszą wiadomość → agent buduje stronę narzędziami `site_*` →
podgląd obok rozmowy odświeża się po każdym `tool.finished` narzędzia `site_*`.

Każda wiadomość z modułu zaczyna się znacznikiem `[Strona: <adres>]` (w interfejsie ukrytym),
więc agent zna adres niezależnie od tego, jak tryb rozmowy trafia do promptu.

**Dane na dysku** (`<NEXUS_DATA_DIR>/strony/`):

| Ścieżka | Zawartość |
|---|---|
| `<adres>/` | szkic (edytuje agent) |
| `.opublikowane/<adres>/` | zamrożona kopia publiczna |
| `.wersje/<adres>/vNNNN/` | migawki (maks. 50; wersja powstaje przy publikacji, przywróceniu i na żądanie) |
| `.meta/<adres>.json` | tytuł, opis, rozmowa, wersje, stan publikacji, prośba o publikację |
| `.klucz` | klucz HMAC adresów podglądu (600, tworzony raz) |

**Narzędzia agenta:** `site_list`, `site_read_file`, `site_write_file`, `site_import_file`
(plik z rozmowy → np. `img/logo.png`), `site_delete_file`, `site_save_version`,
`site_publish` (**tylko prośba** – publikuje użytkownik przyciskiem), `site_unpublish`.
Ścieżki: względne, segmenty `[A-Za-z0-9_][A-Za-z0-9._-]*`, bez `..` i plików ukrytych,
maks. 8 poziomów, dozwolone rozszerzenia statyczne (HTML/CSS/JS/JSON/SVG/obrazy/czcionki/media/PDF);
limit strony `NEXUS_TWORCZY_SITE_MAX_MB`.

**API** (`/api/strony`, sesja wymagana): lista, tworzenie, szczegóły z plikami i adresem
podglądu, zmiana tytułu/opisu, usunięcie, `POST /{adres}/rozmowa`, `GET /{adres}/pliki/{ścieżka}`,
`POST /{adres}/wersje`, `POST /{adres}/wersje/{id}/przywroc`, `POST /{adres}/publikuj`,
`POST /{adres}/wycofaj`, `POST /{adres}/odrzuc-publikacje`.

**Serwowanie i bezpieczeństwo:**

- `GET /s/<adres>/…` – publiczne, wyłącznie kopia opublikowana (`404.html` strony, gdy jest).
- `GET /api/strony/<adres>/podglad/<token>/…` – szkic; token HMAC ważny 12 h wydaje tylko
  `GET /api/strony/<adres>` po zalogowaniu (ramka nie potrzebuje ciasteczka).
- Pliki stron mają własną politykę CSP z `sandbox` bez `allow-same-origin`: dokument ma
  pochodzenie `null`, nie czyta ciasteczek ani magazynu, a `fetch` do `/api` blokuje
  `connect-src https:` i brak CORS. Skrypty tylko własne i z CDN (unpkg, jsDelivr, cdnjs, esm.sh,
  cdn.tailwindcss.com), `frame-ancestors 'self'`, `X-Frame-Options: SAMEORIGIN`,
  `Access-Control-Allow-Origin: *` (moduły ES i czcionki strony z pochodzenia `null`).
- Podgląd w interfejsie: `<iframe sandbox="allow-scripts allow-forms allow-popups allow-modals">`.
- Service worker PWA nie przechwytuje `/s/…` (`navigateFallbackDenylist` w `vite.config.ts`).
- Adres katalogu bez kreski na końcu (`/s/firma/cennik`) dostaje przekierowanie 308 na adres
  z kreską. Bez tego przeglądarka bierze ostatni człon za plik i liczy ścieżki względne od
  katalogu wyżej — podstrona otwarta z menu traci arkusze i nawigację.

**Ścieżki i zasoby przy wstawianiu witryny:**

Zestaw i szablony budują witryny ze ścieżkami od korzenia domeny (`/_astro/…`, `/cennik`),
a strona użytkownika stoi pod `/s/<adres>/`. `_wstaw_do_szkicu` (`tools/kit_www.py`)
przelicza je przy wstawianiu na ścieżki względne — atrybuty `href`, `src`, `poster`,
`srcset` oraz `url(…)` w arkuszach — i dokłada kreskę odsyłaczom do podstron. Pomiar na
witrynie presetu `saas`: 8118 poprawek w 228 plikach.

Czego **nie** przelicza i dlaczego: ścieżek w JavaScripcie (tam `"/login"` bywa adresem,
kluczem albo tekstem) oraz adresów z protokołem. Jedno i drugie wraca w polu `uwagi`
wyniku razem z nazwami serwerów, z których witryna pobiera zasoby.

Sprzątanie po szablonie idzie dwoma narzędziami: `site_fonts_local` przenosi kroje
z repozytorium serwera (bez pobierania), `site_vendor_assets` ściąga resztę — skrypty
i arkusze z CDN-ów, zdjęcia ze stocków — do katalogu `zewnetrzne/<serwer>/` i podmienia
odwołania. Rozróżniamy zasób od odsyłacza: `href` na `<link rel="stylesheet">` to arkusz
do pobrania, `href` na `<a>` to cudza strona i zostaje. `rel="canonical"` też zostaje, ale
jest zgłaszany osobno — wskazuje witrynę autora szablonu jako „prawdziwy adres” podstrony
(24 z 81 szablonów kolekcji). Po co to wszystko: [rejestr czynności, CZ-15](../zgodnosc/REJESTR-CZYNNOSCI.md).

## Obrazy

| Operacja | Narzędzie | Technika |
|---|---|---|
| Usuń tło | `remove_background` | rembg (`/danaco/programy/bin/rembg`, domyślnie bria-rmbg ≈ 45–80 s; tryb szybki isnet-general-use ≈ 8–12 s) |
| Zmień tło | `change_background` | wycinek (alfa) na kolor, gradient, inne zdjęcie (dopasowanie „cover”) albo rozmyte tło (obiekt usuwany inpaintingiem przed rozmyciem – bez poświaty) |
| Gumka | `erase_objects` | maska z pędzla (PNG z płótna, alfa = pociągnięcia) lub prostokąty → `cv2.inpaint` (Telea/NS) |
| Powiększ | `upscale_image` (istniejące) | Real-ESRGAN |

Interfejs: podgląd przed/po z suwakiem (mysz, dotyk, strzałki), historia wyników sesji
(„Edytuj dalej wynik” pozwala łączyć operacje), pobieranie wyniku.

## Tłumacz

- **Tekst** (`POST /api/tlumacz/tekst`): tłumaczenie na bieżąco (1,2 s po przerwie w pisaniu),
  wybór języków (28), styl (neutralny, formalny, swobodny, marketingowy, techniczny, prosty),
  słowniczek terminów, wykrywanie języka źródłowego, zamiana kierunku, kopiowanie.
- **Dokumenty** (`POST /api/tlumacz/dokument` → zadanie w tle, narzędzie `translate_document`):
  - DOCX – akapity treści, tabel, pól tekstowych, nagłówków i stopek; przebiegi o tym samym
    formatowaniu są grupowane, a grupy oznaczane `<1>…</1>` – tłumacz zachowuje znaczniki, więc
    pogrubienia i kursywy trafiają na właściwe fragmenty (przy zgubionych znacznikach tekst
    trafia do pierwszego przebiegu); przebiegi z grafiką i polami są nietykane,
  - PPTX – pola tekstowe, grupy, tabele, notatki slajdów,
  - PDF z tekstem cyfrowym – redakcja wyłącznie tekstu bloków (grafika i obrazy zostają),
    tłumaczenie w tym samym miejscu (`insert_htmlbox`: wielkość, kolor, pogrubienie bloku;
    ramka poszerzana do wolnego miejsca, a zbyt długi tekst zmniejszany),
  - TXT/MD – akapity.
- Tłumaczy Claude przez Claude Code CLI (`claude -p --output-format json --json-schema …
  --tools "" --no-session-persistence`, model `NEXUS_TWORCZY_TRANSLATE_MODEL`), partiami do
  6000 znaków, bez duplikatów; przy niezgodnej liczbie segmentów partia jest powtarzana
  pojedynczo. Treść dokumentu to dane – instrukcja systemowa zabrania wykonywania poleceń z niej.

## Studio audio/wideo

Odtwarzacz z zaznaczaniem fragmentu („Teraz” ustawia początek/koniec z pozycji odtwarzania),
akcje: transkrypcja, napisy SRT/VTT, streszczenie (opcjonalnie notatka DOCX), wycięcie
fragmentu, konwersja, wyodrębnienie dźwięku, wyrównanie głośności, kompresja wideo.
Akcja tworzy rozmowę z nagraniem i precyzyjnym poleceniem (istniejące narzędzia
`transcribe_audio`, `media_process`, `write_document`); wynik i dalsza rozmowa o nagraniu są
w panelu obok, z przejściem do pełnego czatu.

### Montaż: film ze zdjęć i klipów

Druga zakładka Studia składa **nowy** materiał, zamiast przerabiać gotowy. Wgrywasz paczkę
zdjęć (i klipów) naraz, ustawiasz kolejność ujęć strzałkami, a przy każdym czas, napis
i ruch kamery; nad całością: napis otwierający, kadr (16:9, 9:16, 1:1, 4:5), przejście
i nastrój podkładu. Przycisk „Złóż film” wysyła jedno polecenie do `video_compose`
(`backend/nexus/tools/montaz.py`).

Co robi narzędzie:

| Element | Jak powstaje |
|---|---|
| ruch kamery na zdjęciu | `zoompan` FFmpeg — najazd, odjazd, panorama w lewo/prawo |
| klip krótszy od ujęcia | `tpad` przytrzymuje ostatnią klatkę, `trim` ucina do zamówionej długości |
| napis | nakładka PNG rysowana Pillow (polskie znaki i cudzysłowy psuły cytowanie `drawtext`) |
| czytelność napisu | rozmyty cień pod literami + przyciemnienie dobrane do jasności kadru |
| przejście | `xfade` — 26 przejść wbudowanych i 21 własnych z `media-zasoby/przejscia/xfade-danaco` |
| lektor | zdanie ujęcia czytane silnikiem rozmowy głosowej (Piper), wstawione `adelay` od początku tego ujęcia |
| podkład | plik z `media-zasoby/muzyka` zapętlony `-stream_loop` na długość filmu, z wyciszeniem; pod lektorem schodzi do 35% |

Podkładu nie wybiera użytkownik: wskazuje nastrój (firmowy, energiczny, spokojny, kinowy,
sygnał), a utwór dobiera agent z biblioteki serwera przez `asset_library` i mówi, co wybrał.

Lektor jest polem przy ujęciu, nie osobnym krokiem: wpisane zdanie czyta głos serwera od
początku tego ujęcia. Sprawdzenie, że naprawdę go słychać, idzie przez rozpoznanie mowy
z gotowego filmu (`test_lektor_czyta_zdania_ujec_i_slychac_go_nad_muzyka`) — samo
zmiksowanie ścieżek niczego by nie dowiodło.

### Spot i intro dźwiękowe

`audio_compose` (to samo miejsce w kodzie co montaż filmu) składa sam dźwięk: kwestie
lektora po kolei z przerwami między zdaniami, podkład z `media-zasoby/muzyka` wchodzący
przed pierwszym zdaniem, schodzący pod głos i wybrzmiewający po ostatnim. Bez kwestii
oddaje sam podkład przycięty do zadanej długości — na tło pod czyjeś nagranie. Wynik to
MP3 192 kb/s. Interfejsu nie ma: narzędzie wywołuje agent z rozmowy.

## Zadania w tle modułów

Obrazy i dokumenty są przetwarzane w procesie API (`nexus/tworczy/zadania.py`): te same
narzędzia co agent, wywoływane bez modelu, stan w pamięci procesu (6 h po zakończeniu),
wyniki zapisywane w magazynie plików (`origin = "result"`, bez rozmowy). Interfejs odpytuje
`GET /api/<moduł>/zadania/{id}`, anuluje `DELETE`. Restart API przerywa trwające zadania.

## Konfiguracja

Blok `# --- moduł tworczy ---` w `Settings` i `.env.example`:

| Zmienna | Domyślnie |
|---|---|
| `NEXUS_TWORCZY_SITE_MAX_MB` | `200` |
| `NEXUS_TWORCZY_REMBG_BIN` | `/danaco/programy/bin/rembg` |
| `NEXUS_TWORCZY_REMBG_MODEL` | puste (model domyślny rembg: bria-rmbg) |
| `NEXUS_TWORCZY_REMBG_FAST_MODEL` | `isnet-general-use` |
| `NEXUS_TWORCZY_TRANSLATE_MODEL` | `claude-sonnet-5` |
| `NEXUS_TWORCZY_TRANSLATE_TIMEOUT_S` | `300` |
| `NEXUS_TWORCZY_TRANSLATE_BATCH_CHARS` | `6000` |

Nowa zależność: `python-pptx`. Moduł nie wymaga żadnych poświadczeń poza tokenem Claude,
który Nexus już ma.

## Testy

- `pytest tests/test_tworczy.py` – ścieżki i adresy (próby wyjścia poza katalog), magazyn,
  wersje i publikacja, narzędzia stron, API (podgląd z tokenem, CSP, `/s/` przed i po
  publikacji, CSRF), kompozycja tła (kolor, gradient, obraz, rozmycie), inpainting, narzędzia
  obrazów i zadania API, znaczniki fragmentów, parsowanie wyniku CLI, tłumaczenie DOCX/PPTX/PDF/MD
  z atrapą tłumacza, API tłumacza.
- `vitest` – adresy stron, znacznik strony, czas nagrań i polecenia Studia, odpytywanie zadań,
  suwak przed/po, rejestracja modułów.

## Uwagi do scalenia

- `frontend/vite.config.ts`: dopisane `/^\/s\//` w `navigateFallbackDenylist`.
- Etykiety nowych narzędzi (`site_*`, `remove_background`, `change_background`,
  `erase_objects`, `translate_document`) warto dopisać do `TOOL_LABELS` w `frontend/src/runState.ts`.
- `nexus/tworczy/tlumaczenie.py` importuje `cli_environment` z `nexus/agent/runner.py`
  (strumień `agenci`) – przy zmianie nazwy trzeba poprawić import.
- Instrukcja `tryby/strona.md` jest plikiem danych – przy instalacji innej niż `-e` musi trafić
  do pakietu (package data), razem z pozostałymi plikami `tryby/`.
