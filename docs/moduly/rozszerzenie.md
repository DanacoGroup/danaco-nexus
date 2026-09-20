# Moduł „rozszerzenie” – Danaco Nexus w przeglądarce

Rozszerzenie Manifest V3 dla Chrome, Edge i Danaco Lynx (Electron). Na każdej stronie
dodaje wysuwany z prawej strony panel Nexusa (wzorzec: Sider): streszczenie strony,
odpowiedź na opinię lub wiadomość, poprawienie i tłumaczenie tekstu, pytanie o stronę
oraz wstawienie odpowiedzi w pole na stronie.

## Spis treści

1. [Instalacja](#instalacja)
2. [Funkcje](#funkcje)
3. [Architektura](#architektura)
4. [Wymagania wobec serwera (tryb osadzony)](#wymagania-wobec-serwera-tryb-osadzony)
5. [Bezpieczeństwo](#bezpieczeństwo)
6. [Danaco Lynx i przeglądarki z niepełnym API](#danaco-lynx-i-przeglądarki-z-niepełnym-api)
7. [Budowa i testy](#budowa-i-testy)
8. [Pliki](#pliki)

## Instalacja

1. Zbuduj paczkę: `extension/buduj.sh` → `.tmp/rozszerzenie/out/nexus-rozszerzenie/`
   (katalog rozpakowany) i `.tmp/rozszerzenie/out/nexus-rozszerzenie.zip`.
2. Chrome/Edge: `chrome://extensions` (`edge://extensions`) → tryb dewelopera →
   „Załaduj rozpakowane” → katalog `nexus-rozszerzenie`.
   Danaco Lynx: katalog rozpakowanego rozszerzenia w ustawieniach rozszerzeń przeglądarki.
3. W Nexusie: moduł **Urządzenia** → nowe urządzenie rodzaju „rozszerzenie” → skopiuj klucz `nxd_…`
   (pokazywany tylko raz).
4. Wklej klucz na stronie opcji rozszerzenia (ikona rozszerzenia → Opcje) albo – gdy przeglądarka
   nie ma strony opcji – w samym panelu (formularz „Połącz rozszerzenie z Nexusem”). Rozszerzenie
   sprawdza klucz zapytaniem `GET /api/rozszerzenie/konfiguracja`.

## Funkcje

| Funkcja | Działanie |
|---|---|
| Panel boczny | Pływający przycisk przy prawej krawędzi (przeciągany w pionie), skróty **Alt+N** i **Ctrl+Shift+Spacja**, ikona na pasku; szerokość zmieniana przeciągnięciem lewej krawędzi (320–900 px, zapamiętywana); **Esc** zamyka. Przycisk można ukryć na wybranej stronie. |
| Kontekst strony | Tytuł, adres, zaznaczony tekst albo czytelna treść strony (własny ekstraktor w stylu Readability: ocena bloków tekstu, pominięcie nawigacji, stopek, reklam, elementów ukrytych; limit 24 000 znaków). Opcjonalnie zrzut widocznej karty (JPEG) – przełącznik „Zrzut”. |
| Streść | Kontekst: treść strony; polecenie streszczenia w punktach, wysyłane od razu. |
| Odpowiedz | Lista rozpoznanych opinii/komentarzy/wiadomości (autor, ocena, data, fragment); najechanie podświetla opinię na stronie; wybór wysyła opinię z poleceniem odpowiedzi właściciela (dla e-maili – odpowiedzi na wiadomość). Gdy przy opinii jest pole odpowiedzi, „Wstaw” trafia właśnie tam. Zapas: „Użyj zaznaczonego tekstu”. |
| Popraw | Zaznaczenie w aktywnym polu albo cała jego treść; „Wstaw” zastępuje wtedy całą treść pola poprawioną wersją. |
| Przetłumacz | Zaznaczenie albo treść strony; język docelowy z listy w panelu. |
| Zapytaj | Dołącza kontekst strony (zaznaczenie albo treść) bez wysyłania – pytanie wpisujesz w polu wiadomości Nexusa (`nexus:prompt` z `send: false`). |
| Wstawianie | `nexus:insert` → ostatnio aktywne pole (textarea, input tekstowy, contenteditable, także w otwartym Shadow DOM strony): `execCommand("insertText")` (historia cofania, edytory), a gdy to niemożliwe – natywny setter wartości i zdarzenia `input`/`change` (React, Vue). Bez pola – kopia do schowka z komunikatem. |
| Menu kontekstowe | „Zapytaj Nexusa o zaznaczenie”, „Przetłumacz w Nexusie”, „Odpowiedz z Nexusem”, „Streść stronę w Nexusie”. |

Rozpoznawane serwisy (poza heurystyką ogólną `itemprop=review`, klasy `review/opinia/comment`):
Booking.com (strona obiektu i panel partnera `admin.booking.com`), Mapy Google i Profil Firmy
w Google, Gmail, Outlook w przeglądarce, Roundcube i inne `mail.*`/`poczta.*`/`webmail.*`.
Selektory tych serwisów są dopasowane do ich obecnego kodu i mogą się zdezaktualizować, gdy serwis
zmieni układ – wtedy działa heurystyka albo zaznaczenie tekstu.

## Architektura

```
strona WWW (np. admin.booking.com)
  └─ skrypt treści tresc.js (świat izolowany)
       ├─ <danaco-nexus> z zamkniętym Shadow DOM: przycisk, panel, podświetlenie
       │    └─ iframe chrome-extension://…/panel.html#k=<jednorazowy klucz>
       │         ├─ pasek akcji, lista opinii, formularz połączenia
       │         └─ iframe https://danaco-nexus.pl/?widok=panel   ← umowa postMessage „nexus:*”
       ├─ ekstraktor treści, rozpoznawanie opinii, śledzenie aktywnego pola, wstawianie
       └─ MessagePort ↔ panel (prywatny kanał, klucz z adresu ramki)
tło tlo.js (service worker): ikona, skróty, menu kontekstowe, zrzut karty (captureVisibleTab)
```

Panel nie używa `chrome.sidePanel` – jest wstrzykiwany, więc działa także w Danaco Lynx.

Umowa z trybem osadzonym Nexusa (realizuje ją strumień „start”):

| Kierunek | Komunikat |
|---|---|
| panel rozszerzenia → Nexus | `{type:"nexus:auth", token}` po każdym `nexus:ready`; `{type:"nexus:context", context:{kind:"page", title, url, text, image?}}`; `{type:"nexus:prompt", text, send}` |
| Nexus → panel rozszerzenia | `{type:"nexus:ready"}`, `{type:"nexus:insert", text}`, `{type:"nexus:copy", text}` |

Komunikaty do Nexusa są wysyłane z `targetOrigin` = adres serwera; odpowiedzi są przyjmowane
tylko z ramki Nexusa i z pochodzenia serwera. Do czasu `nexus:ready` komunikaty czekają w kolejce.

API serwera: `GET /api/rozszerzenie/konfiguracja` (klucz urządzenia) →
`{wersja, urzadzenie, panel: "/?widok=panel", rozszerzenie: {wersja_minimalna}}`.
Ustawienie `NEXUS_ROZSZERZENIE_WERSJA_MINIMALNA` (domyślnie `0.1.0`).
CORS pozostaje zamknięty: strony rozszerzenia mają uprawnienie do hosta i nie potrzebują nagłówków CORS.

## Wymagania wobec serwera (tryb osadzony)

Obecne nagłówki bezpieczeństwa (`X-Frame-Options: DENY`, `frame-ancestors 'none'`) blokują
osadzenie Nexusa w panelu. Test e2e w Chromium 1243 potwierdził, że **Chromium sprawdza
`frame-ancestors` dla wszystkich przodków ramki – także dla strony, na której działa
rozszerzenie**. Dlatego nie wystarcza `frame-ancestors chrome-extension://<id>` ani
`'self' chrome-extension:`.

Dla odpowiedzi `/?widok=panel` (i tylko dla niej) serwer powinien wysyłać:

```
Content-Security-Policy: … frame-ancestors 'self' https: chrome-extension: moz-extension:
(bez nagłówka X-Frame-Options)
```

Zabezpieczenia, które czynią to bezpiecznym (do realizacji w trybie osadzonym aplikacji):

1. W trybie `?widok=panel` aplikacja przyjmuje `nexus:auth`, `nexus:context` i `nexus:prompt`
   wyłącznie wtedy, gdy `event.source === window.parent` i `event.origin` zaczyna się od
   `chrome-extension://` lub `moz-extension://` (albo pochodzi z innej zaufanej powłoki: Android,
   Desktop). Test e2e potwierdza, że wiadomości wysłane przez stronę mają jej pochodzenie.
2. Ciasteczko sesji (`SameSite=Lax`) nie jest wysyłane w ramce osadzonej w obcej witrynie, więc
   obca strona, która sama osadzi `?widok=panel`, dostaje niezalogowany panel bez klucza.
3. Panel wysyła `nexus:ready` i czeka na klucz – bez klucza nie pokazuje danych użytkownika.

## Bezpieczeństwo

- Klucz urządzenia leży wyłącznie w `chrome.storage.local` rozszerzenia (zapas: `localStorage`
  pochodzenia `chrome-extension://`), nigdy w magazynie odwiedzanej strony. Skrypt treści go nie czyta.
  Pole klucza nie pokazuje zapisanej wartości.
- Panel jest w zamkniętym Shadow DOM, a jego ramki są poza `window.frames` strony (sprawdzone e2e).
- Kanał skrypt treści ↔ panel to prywatny `MessagePort` przekazany raz, z losowym kluczem z adresu
  ramki. Ponowne załadowanie ramki (np. nawigacja wymuszona przez stronę) tworzy nową ramkę z nowym
  kluczem. Panel traktuje port jako źródło danych (treść strony, wynik wstawiania) – polecenia dla
  Nexusa powstają tylko z kliknięć w panelu i z tła rozszerzenia (menu kontekstowe).
- Treść stron, opinii i wiadomości trafia do Nexusa jako kontekst (dane), nie jako polecenie;
  wstawianie tekstu na stronę następuje wyłącznie po kliknięciu „Wstaw” w Nexusie. Rozszerzenie
  niczego nie wysyła w imieniu użytkownika – publikację odpowiedzi użytkownik zatwierdza sam na stronie.
- Adres serwera: tylko HTTPS (HTTP wyłącznie dla `127.0.0.1`/`localhost` – serwer testowy),
  bez danych logowania w adresie.

## Danaco Lynx i przeglądarki z niepełnym API

Danaco Lynx ładuje rozpakowane rozszerzenia Chrome, ale Electron udostępnia tylko część API
`chrome.*`. Rozszerzenie wykrywa każdą funkcję przed użyciem:

| Funkcja | Wymagane API | Bez API |
|---|---|---|
| Panel, przycisk, skrót na stronie, kontekst, szybkie akcje, lista opinii, wstawianie | skrypt treści, `chrome.runtime.getURL`, `web_accessible_resources` | – (wymagane minimum) |
| Klucz i ustawienia | `chrome.storage.local` | `localStorage` stron rozszerzenia; skrypt treści używa ustawień domyślnych (przycisk widoczny, szerokość 420 px) |
| Strona opcji | `chrome.runtime.openOptionsPage` | formularz połączenia w panelu (ikona ustawień) |
| Zrzut karty | `chrome.tabs.captureVisibleTab` | przełącznik „Zrzut” ukryty |
| Menu kontekstowe | `chrome.contextMenus` | brak menu; te same akcje w panelu |
| Skróty przeglądarki, ikona na pasku | `chrome.commands`, `chrome.action` | skrót Alt+N / Ctrl+Shift+Spacja obsługuje skrypt treści (gdy fokus jest na stronie) |
| Wstrzyknięcie do kart otwartych przed instalacją | `chrome.scripting` | przeładowanie karty |

Niesprawdzone w samym Danaco Lynx (brak tej przeglądarki w środowisku testów): czy Lynx uruchamia
service worker MV3, czy obsługuje `web_accessible_resources` dla ramek i `chrome.storage.local`.
Jeżeli Lynx nie ładuje ramek `chrome-extension://` na stronach WWW, panel się nie pojawi – wtedy
potrzebna jest obsługa po stronie Lynx (np. natywny panel z `?widok=panel` i tą samą umową postMessage).

## Budowa i testy

```bash
cd extension
npm ci
npm run typecheck      # tsc --noEmit
npm test               # vitest (jsdom): ekstraktor, wstawianie, opinie, most, ustawienia
./buduj.sh             # katalog rozpakowany + ZIP w .tmp/rozszerzenie/out/
```

Test end-to-end na serwerze (Chromium z Playwright, rozpakowane rozszerzenie, serwer testowy
Nexusa na SQLite pod `127.0.0.1:18913`):

```bash
extension/e2e/uruchom.sh /danaco/projekty/danaco-nexus/.tmp/rozszerzenie 18913
```

Strony `admin.booking.com` i `danaco-nexus.pl` są podstawiane przez `context.route` (bez sieci):
strona testowa z opiniami (`e2e/strona-opinie.html`) i atrapa trybu panelu (`e2e/atrapa-panelu.html`).
Test sprawdza wstrzyknięcie panelu, `nexus:auth`, kontekst strony i opinii, polecenia, wstawianie
(textarea, contenteditable, zastąpienie treści), zrzut karty, akcję z menu kontekstowego, izolację
od skryptów strony, skróty, nagłówki `frame-ancestors` oraz ekran opcji z prawdziwym serwerem.

Wersja rozszerzenia pochodzi z `extension/manifest.json`; ikony z pakietu marki (`logo/pwa`).

## Pliki

| Plik | Rola |
|---|---|
| `extension/manifest.json` | Manifest V3 (uprawnienia: storage, contextMenus, scripting, clipboardWrite; hosty: `<all_urls>`) |
| `extension/src/tresc/` | skrypt treści: panel (`panel-host.ts`), ekstraktor, opinie, wstawianie, skrót |
| `extension/src/panel/` | panel: pasek akcji, most do Nexusa (`most.ts`), polecenia akcji |
| `extension/src/opcje/` | strona opcji |
| `extension/src/wspolne/` | ustawienia, komunikaty, formularz połączenia, ikony |
| `extension/src/tlo.ts` | service worker |
| `extension/buduj.mjs`, `buduj.sh` | budowa (esbuild) i paczka ZIP |
| `extension/testy/` | testy vitest |
| `extension/e2e/` | test Playwright i skrypt uruchomienia |
| `backend/nexus/api/modules/rozszerzenie.py` | `GET /api/rozszerzenie/konfiguracja` |
