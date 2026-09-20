# Danaco Nexus — Audyt interfejsu i warstwy wizualnej

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Rodzaj** | Personal AI Workspace |
| **Opis** | Osobisty agent AI do pracy i rozrywki, działający na serwerze Danaco i otwierany jako aplikacja PWA we własnym oknie. |
| **Producent** | Danaco Holding Group Sp. z o.o. |
| **Twórca** | Dariusz Naharnowicz |
| **Wersja** | etap 1B |
| **Status** | Deweloperski |
| **Data** | 2026-09-20 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Audyt interfejsu, grafiki i treści produktu — ustalenia i wykonane naprawy |
| **Klasa dokumentu** | Raport ustaleń |
| **Odbiorcy** | właściciel produktu · deweloper warstwy klienckiej · projektant |
| **Przeznaczenie** | Wykaz usterek zastanych w warstwie wizualnej i treściowej produktu wraz z opisem naprawy, tak aby dało się je sprawdzić i odtworzyć. |
| **Zakres** | Aplikacja PWA, strona produktu, powłoka Nexus Desktop, rozszerzenie przeglądarki, aplikacja Android, konfiguracja wdrożenia |
| **Poza zakresem** | Architektura rdzenia — [docs/architektura](architektura/README.md); treść pakietów marki — katalogi `branding/`, `logo/`, `motion/`, `landing/`, `promocja/` |
| **Dokumenty powiązane** | [Wdrożenie systemu projektowego](../design-system/WDROZENIE.md) · [System projektowy](../design-system/DESIGN_SYSTEM.md) · [Specyfikacja strony produktu](../landing/LANDING_PAGE_SPEC.md) |
| **Metoda** | Przegląd kodu, zrzuty ekranu w obu motywach przy szerokościach 390, 834 i 1440 px, `pa11y` (WCAG 2.2 AA), kontrole `tsc`, `vitest`, `pytest`, `ruff` |

## Spis treści

1. [Ocena stanu zastanego](#1-ocena-stanu-zastanego)
2. [Ustalenia i naprawy](#2-ustalenia-i-naprawy)
3. [Pomiary po naprawie](#3-pomiary-po-naprawie)
4. [Sprawy otwarte](#4-sprawy-otwarte)

---

## 1. Ocena stanu zastanego

Produkt miał dwie rozjeżdżające się warstwy wizualne. Pierwsza — kompletny system
projektowy z tokenami, krojami, znakiem, wytycznymi ruchu, tłami, nagraniami i filmem
promocyjnym — leżała w katalogach `design-tokens/`, `design-system/`, `logo/`, `motion/`,
`landing/` i `promocja/` i nie była w ogóle użyta w kodzie. Druga — doraźna paleta
wpisana wprost w `frontend/src/styles.css`, rysowany w kodzie znak zastępczy i własne
wartości barw w powłoce desktopowej, rozszerzeniu i aplikacji Android — była tym, co
widział użytkownik.

Skutek: produkt nie wyglądał jak marka, której księgę sam nosi w repozytorium, a strona
produktu obiecywała rzeczy, których aplikacja nie robiła.

## 2. Ustalenia i naprawy

### 2.1 Warstwa wizualna

| Ustalenie | Naprawa |
|---|---|
| Barwy, kroje, promienie i cienie wpisane wprost w arkuszu; tokeny nieużywane | `frontend/src/styles.css` zbudowany na `design-tokens/dist/tokens.css`; doraźna paleta usunięta |
| Kroje marki (Figtree, Inter, Cascadia Code) leżały tylko w pakiecie strony | serwowane z `/kroje/`, wstępnie pobierane w `index.html` |
| Znak rysowany w kodzie (litera „N” na fiolecie) zamiast sygnetu z pakietu | `Logo` podaje `logo/svg/symbol.svg`; doszły `Mark` i `Logotype` |
| Generator ikon zastępczych (`frontend/scripts/ikony.py`) nadpisywał ikony marki | plik usunięty; ikony pochodzą z `logo/pwa/` |
| Ikona Nexus Desktop, ikona zasobnika i ikony Androida były zastępcze | podmienione na pakiet marki; ikona adaptacyjna Androida z gradientem Aurory i warstwą jednobarwną |
| Ekran startowy i powiadomienia Androida wciąż rysowały zastępczy znak („N” na fiolecie) | oba rysunki przepisane na sygnet z pakietu marki; tło widoku z barwy powierzchni aplikacji |
| Rozszerzenie przeglądarki rysowało zastępczy znak i wstrzykiwało na obce strony starą paletę | sygnet z pakietu marki w `extension/src/wspolne/ikony.ts`; barwy panelu wstrzykiwanego sprowadzone do ról z tokenów |
| Nexus Desktop odwoływał się do krojów, których na Windows może nie być | Inter i Cascadia Code dołączone do paczki (`desktop/assets/kroje`) |
| Zrzuty w oknie instalacji PWA nie przedstawiały produktu | skalowane z makiet `prezentacja/makiety/` |
| Powłoka desktopowa, rozszerzenie i Android miały własne palety | sprowadzone do ról semantycznych z tokenów |
| Podświetlanie składni w module Kod na przypadkowych barwach | przeniesione na skale bazowe tokenów (świadomy wyjątek, opisany) |

### 2.2 Błędy interfejsu

| Ustalenie | Naprawa |
|---|---|
| `bg-accent` używane jako wypełnienie przycisku — w motywie ciemnym biały napis na jasnym fiolecie nie spełniał AA | 33 miejsca przeniesione na `bg-accent-fill` / `hover:bg-accent-fill-hover` |
| Znak asystenta rozciągał się w pionie w kolumnie rozmowy (reset ustawia `img { height: auto }`) | rozmiar podawany wprost w komponencie |
| Czasy kroków agenta z kropką dziesiętną („1.2 s”) | zapis polski przez `toLocaleString("pl-PL")` |
| Pole wiadomości i wybór plików bez nazwy dostępnej dla czytnika ekranu (3 zgłoszenia `pa11y`) | dodane `aria-label` |
| Etykieta „Baza wiedzy” ucinana w pasku modułów | skrócona do „Wiedza”; pozycje paska zmniejszone, mieści się więcej modułów |
| Tekst panelu w przeglądarce mówił o „rodzicu panelu” | przepisany na język produktu |
| Testy Nexus Desktop przechodziły na czerwono na Linuksie, bo narzędzia `pc_*` liczą ścieżki w postaci Windows | dwa testy plikowe pomijane poza Windows z podaniem powodu; zestaw kończy się kodem 0 |
| Portal otwierał się z widocznym pierścieniem fokusu na nagłówku | przeniesienie uwagi tylko przy zmianie trasy, nie przy pierwszym wejściu |
| Portal miał nazwę produktu jako zwykły tekst zamiast logotypu marki | podstawiony komponent `Logotype` |
| Mapa witryny pomijała stronę produktu („/”) i piaskownicę | dopisane z priorytetami 1,0 i 0,7 |
| Podpowiedź w polu wiadomości łamała się na dwa wiersze na telefonie | skrócona do „Napisz do Nexusa…” |
| Piaskownica pokazywała przy błędzie samą linię tekstu bez ramy strony | ekran z znakiem, nagłówkiem, komunikatem i powrotem na stronę produktu |

### 2.3 Braki względem systemu projektowego

| Ustalenie | Naprawa |
|---|---|
| Aurora nie oznaczała pracy agenta | obrys i poświata na wykonywanym kroku narzędzia i na karcie podagenta; gradient na przycisku wysyłki w stanie gotowym |
| Zasada „klawiatura jest pierwszym wskaźnikiem” bez pokrycia — brak palety poleceń | paleta pod `Ctrl K` (moduły, rozmowy, motyw, przekazanie pytania do rozmowy) |
| Obietnica „Esc zatrzymuje agenta” (system projektowy i strona produktu) nie działała | `Esc` zatrzymuje bieg, gdy nie jest otwarte okno dialogowe |
| Materiały ruchome i film promocyjny nigdzie nieużyte | sekcja „Widać, co robi. I kiedy skończy.” z czterema nagraniami; film 60 s z napisami PL i EN; ekran ładowania z pakietu; kampania dwudziestu nowych materiałów w `promocja/kampania/` |
| Tła sekcji z `landing/tla/` nieużyte | pięć teł w AVIF z zapasem WebP, z przygaszeniem chroniącym kontrast tekstu |

### 2.4 Treść i uczciwość przekazu

| Ustalenie | Naprawa |
|---|---|
| Strona podawała 26 narzędzi agenta; rejestr `backend/nexus/tools/` ma 59 | liczba poprawiona w sekcji funkcji i w sekcji zaufania |
| Gwarancja „Agent nie ma dostępu do powłoki systemu ani do sieci” była nieprawdziwa — istnieją `pc_powershell`, `pc_read_file`, `pc_screenshot`, `web_search`, `web_fetch_page` | gwarancja i odpowiedź w pytaniach przepisane: agent pracuje wyłącznie zarejestrowanymi narzędziami, działania na komputerze użytkownika idą przez Nexus Desktop i wymagają potwierdzenia, do sieci wychodzą tylko narzędzia badawcze |
| Strona mówiła „na Twoim własnym serwerze”, co jest sprzeczne z ustaleniem właściciela (model wdrożenia: wyłącznie serwer Danaco) | treść przepisana zgodnie ze specyfikacją strony |
| Portal powtarzał sformułowanie „na własnym serwerze” | zamienione na „na serwerze Danaco” |
| Trzy różne cenniki: strona produktu (Osobisty/Pro/Zespół), portal (Start/Praca/Zespół) i katalog modułu Płatności | portal sprowadzony do planów ze specyfikacji; znacznik „Dostępny” w barwie powodzenia, wezwanie planu bezpłatnego prowadzi do instalacji |

### 2.5 Wydajność, wyszukiwarki i serwowanie

| Ustalenie | Naprawa |
|---|---|
| Gość na stronie produktu pobierał całą powłokę aplikacji z modułami (807 kB) | ekrany ładowane na żądanie; strona produktu to 75 kB + 14 kB (gzip) |
| `X-Robots-Tag: noindex` w konfiguracji Caddy obejmował także stronę produktu | nagłówek zawężony do ekranów za logowaniem, API i pobierania; strona produktu indeksowana |
| Brak metadanych strony produktu (opis, canonical, Open Graph, dane strukturalne) | uzupełnione; `FAQPage` z czternastoma pytaniami; tytuł i `robots` ustawiane zależnie od ekranu |
| Serwer nie podawał typu dla AVIF, WebP, WOFF2, VTT, MP4 i WebM | typy wpisane wprost w `backend/nexus/api/app.py` |
| Tła, nagrania i film trafiały do pamięci podręcznej aplikacji | wyłączone z prekeszowania — powłoka offline pozostaje lekka |

### 2.6 Porządek w repozytorium

| Ustalenie | Naprawa |
|---|---|
| Kopie z telefonu (SMS, wykazy połączeń, ustawienia aplikacji) w `design-system/Apps/` | katalog dopisany do `.gitignore`, żeby nie trafił do repozytorium; **pliki wymagają decyzji właściciela — dane osobowe** |
| Pliki marki kopiowane ręcznie, bez procedury | `frontend/scripts/zasoby.py` przenosi pakiety przed `dev` i `build`; wyniki pominięte w repozytorium |

## 3. Pomiary po naprawie

| Kontrola | Wynik |
|---|---|
| `pa11y --standard WCAG2AA` — `/start`, `/portal`, `/portal/cennik`, `/portal/kontakt`, `/wyprobuj` | 0 zgłoszeń na każdej stronie |
| `pa11y --standard WCAG2AA` — powłoka aplikacji (rozmowa z krokami agenta) | 0 zgłoszeń |
| `npm run build` (z `tsc --noEmit`) | przechodzi |
| `npx vitest run` | 154 testy, wszystkie zielone |
| `pytest backend/tests/test_portal.py -q` | 31 testów zielonych |
| `pytest backend/tests -q` | 372 zielone, 14 pominiętych |
| `ruff check backend` | bez zastrzeżeń |
| `npm test` w `extension/` | 51 testów zielonych; paczka buduje się z ikonami marki |
| `npm test` w `desktop/` | 67 testów: 65 zielonych, 2 pominięte (narzędzia plikowe działają na ścieżkach Windows) |
| `caddy validate` na `deploy/caddy/danaco-nexus.caddy` | *Valid configuration* |
| Synteza i rozpoznawanie mowy | pierwszy tor Google (30 głosów Chirp3-HD, domyślnie Achernar); zapas na serwerze: Whisper large-v3-turbo i trzy głosy Piper (Gosia, Magda, Marek) — synteza 0,6 s, rozpoznanie 2,6 s, tekst odtworzony poprawnie |
| `deploy/nexus-cli.sh doctor` | 21 kontroli poprawnych, 0 z błędem; serwer MCP zgłasza 59 narzędzi |
| `deploy/kopia-zapasowa.sh` (przebieg próbny) | zrzuty `nexus` (114 pozycji TOC) i `nextcloud`, pliki, wektory, sekrety z prawami 600, sumy kontrolne; kod wyjścia 0 |
| Strona produktu, gzip | 75 kB skrypt wspólny + 14 kB strona + 19 kB arkusz |

## 4. Sprawy otwarte

| Sprawa | Stan |
|---|---|
| `design-system/Apps/` — kopie SMS i wykazów połączeń (30 MB, 11 plików) | do decyzji właściciela: usunąć albo przenieść poza repozytorium; katalog jest już pominięty w `.gitignore` |
| Pakiety marki poza kontrolą wersji (1,9 GB: `promocja` 708 MB, `branding` 593 MB, `landing` 395 MB, `motion` 112 MB, pozostałe) | katalogi są nieśledzone; `git add .` wciągnąłby je do historii. Do decyzji właściciela: Git LFS, osobne repozytorium materiałów albo pozostawienie poza repozytorium z kopią zapasową |
| Test uruchomieniowy Nexus Desktop (`npm run smoke`) | nie wykonany: pobieranie binariów Electrona nie doszło do skutku na maszynie roboczej |
| Tła na żywo (WebGL) z `landing/tla/` | w pracy pary P5 (orkiestracja dziedzinowa) |
| Scena produktu w oknie na stronie | statyczna; pętla trzech spraw z prototypu do podpięcia — w zakresie pary P5 |
| Test klawisza `Esc` zatrzymującego bieg | zachowanie sprawdzone ręcznie; test automatyczny wymaga atrapy całej powłoki |

---

*Koniec dokumentu. Audyt interfejsu i warstwy wizualnej — etap 1B, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · etap 1B · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Kontakt: support@danaco-group.pl*
