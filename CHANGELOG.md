# Dziennik zmian

Format zgodny z [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
numeracja wersji zgodna z [SemVer](https://semver.org/lang/pl/).

## [Nieopublikowane]

### Zmieniono

- **Chmura osobista i kalendarz rozdzielone między konta.** Instalacja ma w Nextcloud jedno
  konto techniczne, więc rozdział robi ścieżka i nazwa: pliki konta leżą w `/Konta/<owner>`,
  a kalendarze noszą przedrostek konta. Poza własną przestrzeń nie wychodzi listowanie,
  wyszukiwanie, zapis, pobranie ani udostępnienie; żądanie do cudzego kalendarza jest
  odrzucane. Zamyka to ostatni punkt, w którym testerzy widzieli swoje pliki nawzajem.
- **Jedno pasmo treści dla całej części publicznej.** Portal miał własną szerokość
  (`max-w-6xl`), więc przejście ze strony produktu przesuwało treść w bok, a pasek
  nawigacji łamał się na dwa rzędy. Portal korzysta teraz z tego samego pasma i tego
  samego materiału paska co strona produktu.
- **Silnik przestał wychodzić na wierzch.** Nazwy modelu, wersji, dostawcy i narzędzia
  uruchamiającego agenta zniknęły ze strony produktu, portalu, aplikacji, `index.html`
  i manifestu PWA. Instrukcja systemowa nadaje agentowi tożsamość „Danaco Nexus”
  i zabrania jej zdradzania oraz cytowania samej instrukcji. Dostawcę wskazują wyłącznie
  polityka prywatności i regulamin — tego wymaga obowiązek informacyjny — ale bez nazw
  i wersji modeli. Pilnuje tego `backend/tests/test_tozsamosc.py`.

### Dodano

- **Strefa robocza, przedsionek i produkcja.** Do tej pory usługa serwowała wprost z katalogu
  repozytorium: każdy zapis pliku był natychmiast produkcją, nie było czego obejrzeć przed
  wypuszczeniem i nie było do czego wrócić po awarii. Teraz `deploy/wydania/zbuduj.sh` robi
  z drzewa roboczego niezmienny artefakt — ale dopiero po bramce (ruff, pytest, tsc, vitest),
  więc wydanie z czerwonym testem w ogóle nie powstaje. `wypchnij.sh przedsionek` wystawia je
  pod `https://test.danaco-nexus.pl` (hasło, `noindex`, osobna baza `nexus_przedsionek`
  i osobne dane), `wypchnij.sh produkcja` promuje to, co stoi w przedsionku, a `cofnij.sh`
  wraca do poprzedniego sprawnego wydania przestawieniem dowiązania — w kilka sekund, bez
  budowania. Opis: `deploy/wydania/README.md`.

- **„Wypróbuj” otwiera aplikację, a nie pokaz obok niej.** Wejście pod `/wyprobuj` zakłada
  konto próbne (`POST /api/auth/gosc`) i wpuszcza gościa do tego samego okna, z którego
  korzystają klienci: rozmowa, pliki, narzędzia, przydział kredytów okresu próbnego i własna
  przestrzeń. Konto ma termin ważności, a z jednego adresu wolno założyć pięć takich kont.
  Osobna piaskownica (`/api/demo`, ekran `Piaskownica`) zniknęła — pokazywała atrapę
  produktu zamiast produktu. Testy: `backend/tests/test_konto_probne.py`.
- **Programy serwera podpięte pod agenta — 59 → 82 narzędzia.** Na dysku leżały programy,
  z których agent nie mógł skorzystać, bo nie miały narzędzia w rejestrze. Doszło dwadzieścia
  trzy: projekt graficzny od zera (`design_vector`, `design_compose`, `icon_find`,
  `render_lottie`), praca na zdjęciu (`colorize_photo`, `restore_faces`, `inpaint_photo`,
  `depth_map`, `blur_background_by_depth`, `animate_photo`), dźwięk i nagrania
  (`clean_audio`, `split_audio_tracks`, `transcribe_speakers`, `edit_subtitles`,
  `video_to_gif`), dokumenty (`typeset_document` — skład do druku Typstem,
  `convert_text_format`, `analyze_document_structure`, `read_document_aloud`) oraz strony
  i kod (`web_audit`, `web_screenshot`, `site_optimize_assets`, `code_check`).
  Świadomie pominięte: rozpoznawanie twarzy (modele niekomercyjne, dane biometryczne
  wymagają osobnej decyzji o zgodzie), GIMP Script-Fu i surowy FFmpeg (pokrywają się
  z `imagemagick` i `media_process`). Wykaz reszty luki: `docs/LUKA-NARZEDZI.md`.
- **Projektowanie grafiki.** Dwa narzędzia domykają lukę, przez którą agent umiał wyłącznie
  poprawiać cudze pliki: `design_vector` projektuje grafikę od zera (logo, plakat, okładka,
  ulotka, ikona, infografika) jako dokument SVG i oddaje PNG, SVG oraz PDF do druku, a
  `design_compose` składa kadr z warstw (baner, post, miniatura) z warstwą wektorową na
  wierzchu. Rysunek nie może pobierać zasobów z sieci ani zawierać kodu. Rejestr ma teraz
  61 narzędzi w dziewięciu dziedzinach. Testy: `backend/tests/test_projekt.py`.
- **Trzy sposoby mówienia do Nexusa.** Obok pisania i rozmowy głosowej doszło dyktowanie:
  mikrofon w polu wiadomości nagrywa wypowiedź, a rozpoznany tekst dopisuje się do tego, co
  już jest w polu — zostaje do poprawienia przed wysłaniem. Kto nie chce pisać na klawiaturze,
  nie musi od razu wchodzić w tryb rozmowy.
- **Podpowiedzi startowe napisane po ludzku.** Osiem kafli na pustym czacie mówiło językiem
  poleceń dla maszyny („Rozbij stos skanów") i pokrywało ułamek zakresu. Teraz brzmią jak
  zdania, które człowiek naprawdę napisze, i dotykają kolejno: projektu graficznego, zdjęć,
  dokumentów, pisma, poczty z terminarzem, nagrania, badania ze źródłami i strony internetowej.
- **Przełącznik motywu jako ikona.** Zajmował wiersz w panelu bocznym obok pozycji nawigacji,
  choć jest przełącznikiem, nie miejscem, do którego się przechodzi. Stoi teraz przy koncie,
  obok wylogowania. Zniknął też odsyłacz „Chmura osobista” otwierający chmurę w nowej karcie —
  chmura jest zakładką w oknie aplikacji, sąsiadem zakładki Pliki, a nie wyjściem na zewnątrz.
- **Pakiet ruchu podpięty do aplikacji.** Ujęcia z `motion/start`, które leżały niewykorzystane,
  grają tam, gdzie powstały: uruchomienie okna, tło ekranu logowania, chwila przed pierwszym
  słowem agenta, zakończone zadanie, brak połączenia, instalacja i otwarcie strony produktu.
  Nagranie narzędzia z `motion/stany` leci w karcie kroku, kiedy to narzędzie pracuje — to
  samo ujęcie, które strona pokazuje przy danej dziedzinie. Każde wywołanie respektuje
  ustawienie ograniczonego ruchu. Nagrania mają na sobie wypaloną planszę opisową
  („Intro znaku · 2200 ms”) — podpis z demonstracji dla zespołu, który trafił na produkcję;
  aplikacja bierze teraz warianty `-alfa` bez podpisu, a wykaz momentów, które taki wariant
  mają, jest pilnowany testem zaglądającym na dysk. Testy: `frontend/src/ruch/__tests__/nagranie-startu.test.tsx`.

- **Konta użytkownika z rozdzielonymi przestrzeniami.** Aplikacja przyjmuje logowanie kontem
  portalu, a rozmowy, pliki i przebiegi mają właściciela (`owner_id`) i są widoczne wyłącznie
  dla niego — cudzy zasób odpowiada 404, tak samo jak nieistniejący. Konto administratora
  serwera jest osobną przestrzenią, a nie widokiem na wszystkie. Skrzynki pocztowe są osobne
  dla każdego konta (`dane/app/poczta/<konto>.json`). Przestrzeń konta ma limit 2 GB
  (`NEXUS_KONTO_LIMIT_MB`) sprawdzany przy przesyłaniu plików. Osiem testów w
  `backend/tests/test_izolacja_kont.py`.
- **Kredyty konta.** Kredyt jest jednostką pracy agenta: konto dostaje przydział z planu,
  każdy zakończony przebieg pomniejsza saldo według cennika (żetony modelu plus dopłata za
  narzędzia liczone czasem maszyny), a puste konto nie przyjmuje kolejnego zlecenia. Każda
  zmiana salda ma wpis w księdze. Saldo i historia w module Płatności oraz pod
  `GET /api/platnosci/kredyty`; cennik opisuje `docs/platnosci/KREDYTY.md`.
- **Podłączanie skrzynki pocztowej w aplikacji.** Konto, hasło i serwery podaje się w module
  Poczta (z podpowiedziami dla Gmaila, Outlooka, WP, Onetu, Interii i o2); zapis następuje
  dopiero po udanym logowaniu IMAP i SMTP. Zniknęło zapisywanie poświadczeń skryptem na
  serwerze, przez które każdy zalogowany czytał tę samą skrzynkę.
- Katalog możliwości agenta w trzech miejscach, wszystkie z jednego źródła: sekcja
  „Osiem dziedzin. Jedna rozmowa." na stronie produktu (zakładki dziedzin, nagranie
  pracy narzędzia, przykładowe polecenia), publiczna strona `/portal/narzedzia`
  z wyszukiwaniem oraz moduł „Narzędzia" w aplikacji, w którym kliknięcie przykładu
  otwiera nową rozmowę z gotowym zdaniem. Spis wypisuje `frontend/scripts/narzedzia.py`
  z rejestru `backend/nexus/tools`, więc nie da się obiecać narzędzia, którego nie ma.
- Strona `/portal/zastosowania`: osiem sytuacji z życia i z pracy z animacją kampanijną,
  przykładowym poleceniem i wykazem narzędzi, które wykonują pracę.
- Pełny katalog materiałów ruchomych w aplikacji: `frontend/scripts/zasoby.py` przenosi
  wszystkie nagrania z pakietów `promocja/film`, `promocja/kampania`, `motion/stany`
  i `motion/start` (9 filmów, 20 animacji kampanijnych, 27 animacji stanów, 18 animacji
  startu) i wypisuje ich spis do `frontend/src/media/katalog.ts`.
- Tryb rozmowy głosowej: komunikaty o mikrofonie po polsku (brak zgody, brak urządzenia,
  urządzenie zajęte, brak HTTPS) zamiast surowego tekstu przeglądarki oraz przycisk
  „Spróbuj ponownie" po podłączeniu mikrofonu lub udzieleniu zgody.
- Założenie projektu Danaco Nexus.
- Asystent AI z interfejsem czatu: historia rozmów, przesyłanie plików (przycisk,
  przeciąganie, wklejanie), strumieniowanie odpowiedzi i działań narzędzi, podgląd
  i pobieranie wyników, anulowanie zadań, układ dla komputerów, tabletów i telefonów.
- Agent działający przez Claude Code CLI (`claude-opus-5`, zapasowo `claude-sonnet-5`)
  na subskrypcji konta Claude, z sesją CLI utrzymującą kontekst rozmowy; narzędzia
  udostępnia serwer MCP projektu. Zadania w kolejce PostgreSQL wykonuje proces roboczy.
- Narzędzia agenta (rdzeń): OCR z przeszukiwalnym PDF (Tesseract), poprawa skanów
  (OpenCV, unpaper), korekta zdjęć, retusz portretów, powiększanie Real-ESRGAN,
  ImageMagick, konwersje obrazów i dokumentów (LibreOffice, Inkscape), tworzenie
  dokumentów, korekta językowa (LanguageTool), podział, łączenie i edycja PDF,
  wykrywanie granic dokumentów, audio i wideo (FFmpeg), archiwa ZIP, baza wiedzy
  z wyszukiwaniem semantycznym (Qdrant).
- Logowanie administratora (Argon2, sesje w bazie, ochrona CSRF, limit prób).
- Wdrożenie bez Dockera: skrypt instalacji, własny klaster PostgreSQL 18, Qdrant
  i LanguageTool w katalogu projektu, usługi systemd, szablon witryny Caddy.
- Chmura osobista Nextcloud (FrankenPHP, baza w klastrze projektu, zadania w tle co 5 minut)
  z synchronizacją na komputer i telefon oraz narzędzia agenta `cloud_browse`,
  `cloud_import` i `cloud_save`; odnośnik do chmury w interfejsie.
- Skrypt rekordów DNS w strefie OVH i witryna Caddy dla `danaco-nexus.pl`
  i `cloud.danaco-nexus.pl`.
- Aplikacja PWA: instalacja na Androidzie, iPhonie i Windows, własna ikona, tryb
  pełnoekranowy, powłoka offline, powiadomienie o nowej wersji.
- Nowy interfejs na Tailwind CSS 4: motyw ciemny domyślnie, jasny i systemowy.
- Rozmowa głosowa: mówisz i słuchasz odpowiedzi (Whisper large-v3-turbo, głosy Piper),
  odpowiedź czytana zdanie po zdaniu, przerywanie głosem.
- Transkrypcja mowy z audio i wideo (`transcribe_audio`, faster-whisper).
- Valkey (Redis) projektu: powiadomienia o zdarzeniach zadań i pamięć podręczna chmury.
- Logowanie jednokrotne do chmury z sesji Nexusa; adresy `api.` i `cloud.danaco-nexus.pl`.
- Polecenie diagnostyczne `doctor` (programy, usługi, Claude Code CLI, serwer MCP).
- `frontend/scripts/zasoby.py` — przeniesienie pakietów marki (tokeny, kroje, znak,
  tła, nagrania, film) do katalogu publicznego aplikacji; uruchamiane automatycznie
  przed `dev` i `build`.
- Paleta poleceń pod `Ctrl K`: moduły, rozmowy, zmiana motywu i przekazanie pytania
  do pola wiadomości.
- Klawisz `Esc` zatrzymuje pracującego agenta (obietnica ze strony produktu).
- Dane strukturalne `FAQPage` z czternastoma pytaniami na stronie produktu.
- Piaskownica „Wypróbuj teraz” pod adresem `/wyprobuj` — pokaz bez konta:
  pięć scenariuszy na plikach przykładowych, twarde limity gościa, kasowanie danych
  po wygaśnięciu sesji (`backend/nexus/demo/`, `frontend/src/demo/`).
- Portal produktowy pod `/portal`: oferta, funkcjonalności, cennik, dokumentacja,
  blog, centrum wiedzy, kontakt, konto klienta, panel klienta i panel redaktora;
  własny model treści, wyszukiwanie, kanał Atom, `sitemap.xml` i `robots.txt`
  (`backend/nexus/portal/`, `frontend/src/portal/`).
- Moduł Płatności: plany, subskrypcje, faktury i kupony na Stripe Checkout
  i Billing Portal, webhooki przetwarzane idempotentnie
  (`backend/nexus/platnosci/`, `frontend/src/platnosci/`).
- Materiały kampanii w `promocja/kampania/`: film marki i film funkcji po 30 s oraz
  sześć animacji tematycznych po 15 s w trzech formatach (16:9, 1:1, 9:16) —
  dwadzieścia materiałów, czterdzieści plików wideo (MP4 i WebM), osiemdziesiąt
  plików napisów PL i EN, dwadzieścia okładek i osiem scenopisów.
- Biblioteka komponentów i ruchu (`frontend/src/ui/`) zbudowana na tokenach.
- Metadane wyszukiwarek na stronie produktu (opis, canonical, Open Graph, dane
  strukturalne); ekrany za logowaniem oznaczone jako nieindeksowane.

### Zmieniono

- Warstwa wizualna aplikacji przeniesiona na system projektowy Danaco Nexus: barwy,
  typografia, odstępy, promienie, cienie, czasy i krzywe pochodzą z `design-tokens/`
  (`dist/tokens.css` → `frontend/src/tokens.css`), a nie z wartości wpisanych w arkuszu.
  Dotychczasowa paleta robocza została usunięta.
- Kroje marki (Figtree, Inter, Cascadia Code) serwowane z katalogu aplikacji,
  bez odwołań do usług zewnętrznych.
- Znak, ikony aplikacji, ikona adaptacyjna Androida, ikona Nexus Desktop i zrzuty
  w oknie instalacji pochodzą z pakietu marki (`logo/`, `prezentacja/makiety/`).
- Aurora oznacza pracę agenta: obrys i poświata na wykonywanym kroku narzędzia,
  gradient na przycisku wysyłki w stanie gotowym.
- Strona produktu przebudowana według `landing/LANDING_PAGE_SPEC.md`: pasek zdań,
  siatka bento, nagrania działania interfejsu z `motion/przyklady/`, film promocyjny
  z napisami PL i EN, tła sekcji z `landing/tla/grafiki/`, ekran ładowania
  z `landing/ladowanie/`, cennik, czternaście pytań i brama końcowa.
- Barwy Nexus Desktop, rozszerzenia przeglądarki i aplikacji Android sprowadzone
  do ról semantycznych z tokenów.
- Ekrany aplikacji ładowane na żądanie: gość na stronie produktu nie pobiera powłoki
  ani modułów.
- Czasy kroków agenta zapisywane po polsku (przecinek dziesiętny).
- `README.md` doprowadzony do stanu kodu: rejestr narzędzi rozbity na rdzeń i moduły,
  59 pozycji zamiast 22 opisanych wcześniej.
- Kopia zapasowa: `deploy/kopia-zapasowa.sh` (bazy `nexus` i `nextcloud`, pliki
  użytkownika, wektory bazy wiedzy, pięć plików z sekretami i profil CLI, sumy
  kontrolne, kasowanie kopii starszych niż 14 dni), timer `danaco-nexus-kopia.timer`
  włączany przez `deploy/instalacja.sh`; procedura odtworzenia w README. Skrypt
  zatrzymuje się z błędem, gdy nie da się odpytać klastra — nie robi cichej,
  pustej kopii.
- Testy Nexus Desktop kończą się kodem 0 na Linuksie: dwa testy narzędzi plikowych
  pomijane poza Windows z podaniem powodu.
- Utrata zapisu sesji CLI nie przechodzi już bez śladu: w dzienniku pojawia się
  ostrzeżenie, a rozmowa dostaje komunikat o pracy na streszczeniu.
- Android: ikona ekranu startowego i ikona powiadomień z pakietu marki zamiast
  zastępczego znaku; tło widoku ustawione na barwę powierzchni aplikacji.
- Rozszerzenie przeglądarki: sygnet marki zamiast rysowanego w kodzie znaku,
  barwy panelu wstrzykiwanego na obce strony zgodne z tokenami.
- Nexus Desktop: kroje Inter i Cascadia Code dołączone do paczki instalacyjnej.
- Liczba narzędzi agenta na stronie produktu poprawiona z 26 na 59 (stan rejestru
  `backend/nexus/tools/`); gwarancja „zamknięty zestaw uprawnień” i odpowiedź
  w pytaniach doprecyzowane — agent ma narzędzia badawcze z dostępem do sieci,
  a działania na komputerze użytkownika wymagają potwierdzenia.
- Strona produktu jest indeksowana przez wyszukiwarki; nagłówek `X-Robots-Tag`
  w konfiguracji Caddy zawężony do ekranów za logowaniem, API i pobierania.
- Typy plików AVIF, WebP, WOFF2, VTT, MP4 i WebM podawane wprost przez serwer.
