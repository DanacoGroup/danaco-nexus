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
| **Data** | 2026-09-21 |

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

Liczby wyżej są pomiarem z 20 września i tak zostają — dokument opisuje stan z tamtego
dnia. Dla porównania ten sam zestaw z **21 września**, z bramki wydania
`20260921-062140-f0a53ff` (`.logs/wydanie-<znacznik>.log`):

| Kontrola | Wynik 21.09 |
|---|---|
| `pytest backend/tests` | 863 zdane, 14 pominiętych (0:05:46) |
| `vitest run` | 44 pliki, 397 testów zdanych |
| `ruff check backend` | bez zastrzeżeń |
| `doctor` (na przedsionku) | 22 kontrole: 20 poprawnych, 2 z błędem — chmura wyłączona w `przedsionek.env` i ścieżka profilu CLI z doraźnego wywołania |
| serwer MCP | 101 narzędzi |
| `pa11y --standard WCAG2AA` — dokumentacja portalu (spis i dwie pozycje) | 0 zgłoszeń |
| Widoczność fokusu (WCAG 2.4.7) — 12 kroków Tab po portalu | każdy element z obrysem 2 px; pierwszy Tab to „Przejdź do treści” |
| Powiększenie 200% (WCAG 1.4.4) — `/`, `/portal`, `/portal/cennik` | brak przewijania w poziomie (szerokość dokumentu równa szerokości okna) |
| Tryb wysokiego kontrastu (`forced-colors: active`) — strona produktu i okno aplikacji | czytelne bez dodatkowych reguł; poprawiony wariant logotypu (wcześniej jasny napis na białym tle narzuconym przez system) |
| `npm test` w `extension/` | 5 plików, 62 testy zielone |
| `npm test` w `desktop/` | 65 zielonych, 2 pominięte (narzędzia plikowe na ścieżkach Windows) |
| Ruch: otwarcie witryny / logowanie / uruchomienie aplikacji / zmiana modułu | obecny w każdym z czterech miejsc; liczby i sposób pomiaru w `motion/MOTION_GUIDELINES.md`, rozdz. 26 |
| Ruch treści dochodzącej w oknie (lista plików, karty stron, gotowy obraz) | **dołożone 21.09.2026.** Czwarty pomiar potwierdził ruch przy zmianie modułu (11 animacji, pełne przejście widoku), ale treść przychodząca po odpowiedzi serwera pojawiała się skokiem. Kaskada `Stagger` miała testy i nie była w aplikacji użyta ani razu. Objęte: siatka plików, karty stron, blok wyniku w Obrazach. Strażnik: `frontend/src/__tests__/kaskada-tresci.test.tsx` |
| Dokładnie jeden `h1` na każdej stronie aplikacji | **poprawione 21.09.2026.** Pomiar na wydaniu: 16 modułów, jeden wyłom — `/m/platnosci` bez żadnego `h1` (tytuł tylko w gałęzi wczytywania i błędu), a cennik z własnym `h1` dawałby na swojej zakładce dwa. Tytuł strony dołożony, cennik zszedł na `h2`. Strażnik: `frontend/src/platnosci/platnosci.test.tsx` |
| Komunikat o nowej wersji widoczny na telefonie | **poprawione 21.09.2026.** Jedyne miejsce (stopka panelu rozmów) ma na 390 px `visibility: hidden` — zmierzone. Dołożony pasek nad rozmową na każdej szerokości, z wyborem „Odśwież / Później”. Strażnik: `frontend/src/__tests__/aktualizacja.test.tsx` |
| Strona produktu nie pobiera pakietu okna aplikacji | **poprawione 21.09.2026.** Lighthouse na wydaniu (profil mobilny): `Workspace-*.js` 560 kB — największe pobranie strony publicznej, większe niż oba nagrania hero razem; 428 kB z tego nieużyte. Wyprzedzenie stoi teraz pod warunkiem (adres aplikacji albo ślad wcześniejszego logowania). Strażnik: `frontend/src/__tests__/wyprzedzenie.test.ts` |
| Kaskada nie biegnie równocześnie z przejściem widoku | **poprawione 21.09.2026.** Pomiar na zbudowanym interfejsie: przez pierwsze 480 ms osiem pozycji animowało się przy `data-przejscie="true"`. Reguła w `ruch/wejscia.css` zdejmuje animację na czas przejścia; po nim kaskada rusza od początku. Strażnik: `backend/tests/test_srodowisko.py::test_kaskada_milczy_w_czasie_przejscia_widoku` |
| Ograniczenie ruchu zeruje także opóźnienia | **poprawione 21.09.2026.** W trybie `reduce` czas trwania spadał do 0,00001 s, a opóźnienie kaskady zostawało (0,08–0,32 s) — treść wyskakiwała schodkami. Obie gałęzie zerują teraz `animation-delay` i `transition-delay`. Strażnik: `backend/tests/test_srodowisko.py::test_ograniczony_ruch_zeruje_takze_opoznienia` |
| Strona produktu nie pobiera nagrania z sekcji instalacji | **poprawione 21.09.2026.** `NagranieStartu` ma na sztywno `preload="auto"` (słusznie w oknie aplikacji, gdzie ujęcie musi ruszyć od razu); w sekcji instalacji, daleko pod pierwszym ekranem, pobierało to 125 kB każdemu odwiedzającemu. Nagranie wchodzi teraz do strony dopiero przy zbliżeniu do widoku, a ramka trzyma proporcje z góry — CLS zostaje 0 |
| Komunikat 422 przy brakujących polach | **poprawione 21.09.2026.** Przy jednym polu „Brakuje pola «x»”, przy dwóch nagle „Nieprawidłowe wartości pól” — choć pole, którego nie przysłano, wartości nie ma. Strażnik: `backend/tests/test_api.py::test_dwa_brakujace_pola_to_brak_a_nie_bledna_wartosc` |
| Pasek błędu da się zamknąć klawiaturą | **poprawione 21.09.2026.** Komunikat nad polem wiadomości miał `role="alert"` i zamykanie kliknięciem w `div` — klawiatura nie miała czego nacisnąć. `pa11y` tego nie łapie (sprawdza znaczniki, nie zachowanie). Dołożony prawdziwy przycisk „Zamknij komunikat” |
| Tytuł okna rozróżnia moduły | **poprawione 21.09.2026.** Każdy widok nazywał się „Danaco Nexus”; przy instalacji PWA to tytuł okna w przełączniku systemu. Teraz „Pliki — Danaco Nexus” itd. Strażnik: `frontend/src/__tests__/naglowki.test.ts` |
| Menu ikony aplikacji (skróty PWA) | **uzupełnione 21.09.2026.** Jeden skrót zamiast czterech, które pokazuje system. Doszły Pliki, Obrazy, Możliwości; głos świadomie pominięty, bo `/m/glos` przy wyłączonym głosie odsyła na czat |
| Udostępnianie z innej aplikacji przed startem service workera | **poprawione 21.09.2026.** Przy pierwszym uruchomieniu po instalacji workera jeszcze nie ma — a to właśnie wtedy ktoś najczęściej próbuje udostępnić pierwszą rzecz. Zapas po stronie serwera wracał na „/” i gubił tytuł, tekst i adres. Tekst jedzie teraz adresem i trafia do pola wiadomości; pliki tą drogą nie przechodzą |
| `HEAD /api/health` | **poprawione 21.09.2026.** Zwracał 404, choć `GET` zwracał 200 — trasy FastAPI nie dokładają `HEAD` samoczynnie, więc żądanie spadało do zapasu SPA i trafiało na gałąź „wszystko pod `api/` to 404”. Sondy dostępności pytają `HEAD` |
| Brakujący plik zwraca 404, a nie stronę z kodem 200 | **poprawione 21.09.2026.** Zapas jednostronicowy odpowiadał stroną na każdy adres, także wyglądający na plik — przeglądarka dostawała HTML w miejsce nagrania, pamięci podręczne zapisywały „sukces”, a literówka w ścieżce zasobu nie odzywała się niczym. Strażnik: `backend/tests/test_api.py::test_pwa_files_served_with_cache_rules` |

Po dzisiejszej pracy nad dostępnością i po poprawce sprzątania biegu agenta — ten sam
zestaw z bramki `20260921-082213-f0a53ff`:

| Kontrola | Wynik (wydanie 08:22) |
|---|---|
| `pytest backend/tests` | **876 zdanych**, 14 pominiętych, 1 odrzucony (0:05:50) — było 863 |
| `vitest run` | 46 plików, **404 testy zdane** — było 44 pliki i 397 |
| `ruff check backend` | bez zastrzeżeń |
| `depcruise --validate` na `frontend/src` | brak naruszeń (531 modułów, 1 381 zależności) |
| `madge --circular` | brak cykli importów (256 plików) |
| `semgrep --config=auto backend/nexus` | 5 trafień, wszystkie fałszywe (zgodność z Pythonem 3.6, stała `text()` w `worker.py`) |
| `languagetool -l pl` na tekstach dla klienta | 2 trafienia, oba fałszywe (nazwa „Brave”, poprawne „na ile”) |
| `pa11y --standard WCAG2AA` na stronie produktu po zmianach | 0 zgłoszeń |
| Hamulce ruchu (WCAG 2.2.2) | dołożone w hero i w pasku przykładów; sprawdzone w przeglądarce, także w trybie wysokiego kontrastu |
| Przemiatanie 16 modułów | każdy pokazuje treść; jedyne błędy konsoli to 503 chmury i kalendarza celowo wyłączonych na przedsionku |
| Pętla produktowa (gość → rozmowa → agent → narzędzie → plik) | PDF 64 585 B w przestrzeni użytkownika, pierwsza odpowiedź po 4 s |
| `deploy/nexus-cli.sh doctor` (produkcja) | **27 kontroli: 25 poprawnych, 2 z błędem** — licencja InsightFace przy włączonej sprzedaży i nadawca poczty portalu; obie to decyzje właściciela. Trzy kontrole dołożone dziś: licencje narzędzi, miejsce na dysku, kopia zapasowa |
| `pa11y --standard WCAG2AA` w oknie aplikacji (`/`, `/m/pliki`, `/m/ustawienia`, `/m/mozliwosci`) | 0 zgłoszeń — razem z dziesięcioma adresami publicznymi **czternaście powierzchni** |

## 4. Sprawy otwarte

| Sprawa | Stan |
|---|---|
| `design-system/Apps/` — kopie SMS i wykazów połączeń (30 MB, 11 plików) | do decyzji właściciela: usunąć albo przenieść poza repozytorium; katalog jest już pominięty w `.gitignore` |
| Pakiety marki poza kontrolą wersji (1,9 GB: `promocja` 708 MB, `branding` 593 MB, `landing` 395 MB, `motion` 112 MB, pozostałe) | katalogi są nieśledzone; `git add .` wciągnąłby je do historii. Do decyzji właściciela: Git LFS, osobne repozytorium materiałów albo pozostawienie poza repozytorium z kopią zapasową |
| Test uruchomieniowy Nexus Desktop (`npm run smoke`) | **Sprostowanie 21.09.2026 wieczorem:** `xvfb-run` i `Xvfb` **są** na serwerze (`/usr/bin/`), a `xvfb-run -a xdpyinfo` podaje działający ekran `:101`. Wcześniejsza próba padała na „Missing X server” najpewniej dlatego, że nie istniał katalog `/tmp/.X11-unix` (powstał dopiero przy dzisiejszym uruchomieniu). Pod `xvfb-run` test **przechodzi do końca** po naprawieniu usterki, którą przy okazji odsłonił: `WindowHelper.start()` nie nasłuchiwał zdarzenia `error` ze `spawn`, więc nieudane uruchomienie PowerShella wywracało proces główny Electrona zamiast zostać obsłużone. Raport: wszystkie pięć okien wczytane (główne z `danaco-nexus.pl`, języczek, pasek panelu, panel, ustawienia), zrzuty zapisane. `ok: false` wynika wyłącznie z rzeczy niedostępnych poza Windows (PowerShell, ścieżka `C:\`). Uruchomienie: `xvfb-run -a npx electron . --smoke-test --disable-gpu`. Same testy jednostkowe pulpitu przechodzą: 67 przypadków, 65 zdanych, 2 pominięte (ścieżki Windows) |
| Tła na żywo (WebGL) z `landing/tla/` | zamknięte 21.09.2026: wydane są cztery tła (`tla.ts:28`) — `aurora` (WebGL, hero strony produktu, `Landing.tsx:320`), `luk` (WebGL, `sekcje.tsx:690`), `swit` (`PasSwitu`) i `ziarno` (`WarstwaZiarna`). `konstelacja` i `noc` są w typie i w katalogu, ale świadomie poza wykazem wydanych — to nie luka, tylko zapas |
| Scena produktu w oknie na stronie | zamknięte 21.09.2026 inaczej, niż zakładano: zamiast skryptu odgrywającego trzy sprawy hero pokazuje nagranie uruchomienia aplikacji z pakietu ruchu (`ScenaHero.tsx`), a makieta została jako zapas przy ograniczonym ruchu i błędzie wczytania. Specyfikacja strony (rozdz. 7.3) opisywała dalej stary pomysł i wskazywała trzy kadry, których nigdy nie zrobiono — przepisana na stan faktyczny |
| Test klawisza `Esc` zatrzymującego bieg | zamknięte: decyzja „zatrzymać czy nie” wyszła z powłoki do `shell/useEscZatrzymaj.ts` i ma pięć testów (`frontend/src/__tests__/escZatrzymanie.test.ts`) — atrapa powłoki okazała się niepotrzebna |

### Ruch, którego nie dało się zatrzymać (WCAG 2.2.2) — naprawione

Nagranie w hero ma `autoplay loop` i obieg 2,9 s, więc ruch trwa tak długo, jak długo ktoś
jest na stronie. Kryterium 2.2.2 wymaga przy ruchu dłuższym niż pięć sekund sposobu
zatrzymania go; odtwarzanie było wiązane wyłącznie z widocznością (`useOdtwarzajWWidoku`),
żadnego sterowania dla oglądającego nie było. Specyfikacja strony opisywała przycisk
„Wstrzymaj pokaz”, ale w kodzie po nim nie zostało nic.

Dołożone: przycisk „Wstrzymaj pokaz / Wznów pokaz” w lewym dolnym rogu sceny, zawsze
widoczny (nie na najechanie — sterowania nie można ukrywać przed klawiaturą). Ręczne
wstrzymanie ma pierwszeństwo przed obserwatorem widoczności, więc przewinięcie strony go
nie cofa, a `autoPlay` elementu jest związane z tym samym stanem — ponowne zamontowanie
nagrania nie wznawia ruchu. Przycisk powiększenia i przycisk wstrzymania są rodzeństwem,
nie zagnieżdżeniem (zagnieżdżony `<button>` to nieprawidłowy HTML i klawiatura go nie
osiąga) — pilnuje tego trzeci przypadek w `frontend/src/__tests__/scena-hero.test.tsx`.

### Ten sam brak w pasku przykładowych poleceń

Po naprawie hero przejrzałem wszystkie animacje `infinite` w arkuszach
(`styles.css`, `ui/ruch.css`, `ruch/znak.css` — 15 sztuk). Czternaście to drobne wskaźniki
stanu (oddech znaku, migotanie kursora, pasek nieokreślonego postępu) — ruch wskaźnika
postępu jest w 2.2.2 wprost wyłączony, a reszta nie niesie treści. Piętnasta niosła:
przesuw kapsuł w pasku „Powiedz to własnymi słowami”.

Brak był jeden: **klawiatura nie miała czym zatrzymać**. `.pasek-tor:hover,
.pasek-tor:focus-within` — kapsuły są `<span>`, więc `:focus-within` nie ma szans zadziałać.
Mechanizm niedostępny z klawiatury nie spełnia 2.2.2.

Naprawione: `[data-pasek-wstrzymany="true"] .pasek-tor` dostaje `animation-play-state:
paused`, a sekcja — przycisk „Wstrzymaj / Wznów” w prawym górnym rogu. Dwa przypadki
w `frontend/src/__tests__/scena-hero.test.tsx`.

**Sprostowanie do pierwszej wersji tego wpisu.** Napisałem tu, że drugie zatrzymanie —
poza polem widzenia — jest martwe, bo żaden arkusz nie czyta `data-widoczny`. To nieprawda
i wzięła się z niedokończonego przeszukania: sprawdziłem `styles.css` i `ui/ruch.css`,
a reguła stoi w **trzecim** arkuszu, `ruch/wejscia.css:33`, i jest tam od wydania
`ba5aa5c`. Dołożony przeze mnie powielony selektor został zdjęty. Nauczka: przy twierdzeniu
„nikt tego nie czyta” przeszukuje się **wszystkie** arkusze, a nie te, które akurat mam otwarte.

### To, o co właściciel pytał wprost: „animacja jest albo źle zrobiona, albo uszkodzona”

Wcześniejsze pomiary ruchu liczyły **animacje**, a nie oglądały obrazu — i dlatego
przechodziły. Dopiero zrzut otwarcia logowania klatka po klatce pokazał, co widać naprawdę:
przez kartę logowania, w poprzek pól formularza, szedł **biały pałąk przez cały ekran**.

Przyczyna była w ekranie ładowania (`frontend/public/ladowanie/ladowanie.js`). Plansza
kończy się przelotem: łuk znaku wlatuje w łuk nagłówka strony produktu. Celu szuka
selektorem, a gdy go nie znajdzie, brała zapasowy o promieniu **0,7 szerokości ekranu**.
Na stronie produktu łuk jest zawsze — więc defektu nie było widać nigdy. Na logowaniu
i w oknie aplikacji łuku nie ma.

Naprawione u źródła: bez bramy cel jest tożsamy ze znakiem, więc nic nie leci — znak gaśnie
w miejscu. Do tego karta logowania czeka, aż plansza naprawdę zejdzie (`useOtwarcie(true)`),
zamiast wchodzić pod gasnącym znakiem.

Po drodze wyszło, że pierwsze wstrzymanie karty **nie działało wcale**: karta miała
narzędziową klasę `animate-rise`, a skrót `animation` z warstwy narzędzi zeruje
`animation-play-state`. Widać to było wyłącznie w pomiarze (`opacity` formularza 1 mimo
`data-otwarcie="gra"`) — na oko wyglądało jak działające. Karta ma własną klasę wejścia.

| Chwila | Przed | Po |
|---|---|---|
| 300 ms | karta widoczna pod planszą | karta niewidoczna, na ekranie sam znak |
| 700 ms | **biały pałąk przez cały ekran, w poprzek pól** | znak gaśnie w miejscu |
| 1100 ms | karta czysta | plansza zeszła, karta wchodzi |

Strona produktu bez zmian: w 700 ms znak nadal wlatuje w łuk hero (zrzut
`landing-otw-700.png`), a ruch wygasa do jednej animacji po 2,4 s.

---

*Koniec dokumentu. Audyt interfejsu i warstwy wizualnej — etap 1B, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · etap 1B · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Kontakt: support@danaco-group.pl*
