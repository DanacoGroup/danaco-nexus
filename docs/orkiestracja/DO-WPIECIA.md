# Danaco Nexus — Zmiany czekające na wpięcie

Notatka robocza prowadzącego orkiestrację. Zawiera zmiany przygotowane poza zakresem par,
które trzeba wpiąć po zamknięciu odpowiedniej fali, żeby nie nadpisać pracy specjalistów.

| Co | Gdzie wpiąć | Kiedy | Stan |
|---|---|---|---|
| `useEscZatrzymaj` z `frontend/src/shell/useEscZatrzymaj.ts` (wraz z testem `src/__tests__/escZatrzymanie.test.ts`) | `frontend/src/shell/Workspace.tsx` — zastąpić wbudowany nasłuch `Escape` wywołaniem zaczepu | po fali 1 (P1 kończy pracę w `Workspace.tsx`) | gotowe, niewpięte |
| Strony prawne P4 (`Prywatnosc.tsx`, `Regulamin.tsx`, `Cookies.tsx`) | `frontend/src/portal/trasy.ts` i nawigacja/stopka w `Portal.tsx` | po fali 2 (P7 kończy pracę w tych plikach) | zależne od raportu P4 |
| Sprostowanie treści o mowie: Google Cloud Speech i 30 głosów Chirp3-HD są pierwszym torem, Whisper i Piper zapasem (patrz README, rozdz. „Rozmowa głosowa") | `frontend/src/landing/tresc.ts` — wiersze o narzędziach, lista technologii, odpowiedź w FAQ o głosie | po fali 1 (P1 pracuje w tym pliku) | opisane, niewpięte |


| Adres `/m/glos` kończy się ekranem „Ten moduł nie jest dostępny” — „glos” nie jest modułem rejestru, tylko nakładką otwieraną z paska. Trzeba przekierować na czat i otworzyć rozmowę głosową | `frontend/src/shell/Workspace.tsx` (obsługa `activeId === "glos"`) albo `frontend/src/shell/route.ts` | po fali 1 (P1 pracuje w Workspace.tsx), przed falą 3 (P7 bierze route.ts) | usterka opisana, niepoprawiona |
| Pełny katalog nagrań w `frontend/src/media/katalog.ts` (74 pozycje: 9 filmów, 20 animacji kampanijnych, 27 animacji stanów, 18 animacji startu) | sekcje strony produktu, portal, stany interfejsu | fala 2 (P5 „Jakość wizualna") | **wpięte częściowo**: 56 z 59 narzędzi ma nagranie w katalogu możliwości; filmy kampanijne i animacje startu nadal nieużyte |
| Odsyłacze stopki strony produktu do stron prawnych | `frontend/src/landing/Landing.tsx`, tablica `STOPKA` | po fali 2 | zależne od raportu P4 |

## Kontrole po każdej fali

```
cd frontend && npm run build
cd frontend && npx vitest run
.venv/bin/python -m pytest backend/tests -q
.venv/bin/ruff check backend
cd extension && npm test
cd desktop && npm test
```

Po fali 3 dodatkowo `pa11y --standard WCAG2AA` na adresach publicznych i pomiar wydajności.

## Katalog materiałów ruchomych

`frontend/scripts/zasoby.py` przenosi do `frontend/public` **wszystkie** nagrania z pakietów
`promocja/film`, `promocja/kampania`, `motion/stany` i `motion/start` (mp4 + webm, plakaty,
napisy WebVTT) i wypisuje ich spis do `frontend/src/media/katalog.ts`. Komponenty mają czytać
spis, a nie wpisywać ścieżki ręcznie — dołożenie nagrania do pakietu wystarczy, żeby pojawiło
się w aplikacji.

| Stała | Zawartość | Ścieżka publiczna |
|---|---|---|
| `FILMY` | 9 filmów promocyjnych (6 s, 15 s ×3 kadry, 30 s ×2, 60 s ×3 warianty) | `/film/katalog/` |
| `KAMPANIA` | 20 animacji tematycznych w kadrach 16:9, 1:1, 9:16 | `/kampania/` |
| `STANY` | 27 animacji stanów aplikacji (rodziny wg `motion/stany/README.md`) | `/ruch/stany/` |
| `START` | 18 animacji ekranu startowego i logowania | `/ruch/start/` |

Pliki GIF i źródła projektowe zostają w pakietach — to te same ujęcia w formacie, którego
strona nie odtwarza. Katalog publiczny powstaje dowiązaniami twardymi, więc nie zajmuje
miejsca drugi raz. Nagrania są wyłączone z `precache` service workera
(`globIgnores` w `frontend/vite.config.ts`) i serwowane z obsługą zakresów (HTTP 206).

## Zbudowane poza parami (20 września)

| Co | Gdzie | Stan |
|---|---|---|
| Katalog narzędzi z rejestru: `frontend/scripts/narzedzia.py` → `frontend/src/dane/narzedzia.ts` (8 dziedzin, polskie nazwy, przykłady) | wpięty w `predev`/`prebuild` | działa, 59/59 narzędzi |
| Sekcja „Osiem dziedzin. Jedna rozmowa." na stronie produktu | `frontend/src/landing/SekcjaNarzedzi.tsx`, wpięta w `Landing.tsx` po `SekcjaFunkcje` | działa |
| Publiczna strona `/portal/narzedzia` | `frontend/src/portal/strony/Narzedzia.tsx`, trasa w `trasy.ts`, nawigacja i stopka w `Portal.tsx`, mapa witryny w `backend/nexus/portal/kanaly.py` | działa |
| Moduł „Narzędzia" w aplikacji (wyszukiwanie, filtr dziedzin, kliknięcie przykładu otwiera rozmowę z gotowym zdaniem) | `frontend/src/modules/mozliwosci/` + `openChat` w `ModulePageProps` i `Workspace.tsx` | działa |
| Przypisanie nagrań pracy agenta do narzędzi | `frontend/src/modules/mozliwosci/ruch.ts` | 56/59 narzędzi |
| Tryb głosowy: polskie komunikaty o mikrofonie + „Spróbuj ponownie" | `frontend/src/voice/VoiceMode.tsx` | działa, 5 testów |
| Pusta rozmowa zaczyna się od góry: powitanie „W czym mogę pomóc?” nie jest już ucięte na ekranie 720 px | `frontend/src/shell/Workspace.tsx` — przewijanie do dołu dopiero przy wypowiedziach | działa |
| Etykiety modułów mieszczące się w pasku 72 px: „Baza wiedzy” → „Wiedza”, „Urządzenia” → „Sprzęt”; test pilnuje długości do 9 znaków | `frontend/src/modules/wiedza/index.tsx`, `frontend/src/modules/urzadzenia/index.tsx`, `src/__tests__/navRail.test.tsx` | działa |
| Pasek modułów: cieniowanie przy krawędziach (widać, że lista sięga dalej niż ekran) i przewinięcie do wybranego modułu | `frontend/src/shell/ModuleNav.tsx` | działa, 4 testy |
| Kopia zapasowa: timer systemd zainstalowany i sprawdzony uruchomieniem | `danaco-nexus-kopia.timer`, kopia w `dane/kopie/` | działa |
| Klucz podpisu Androida przeniesiony z `.tmp` do `dane/app/android-keystore` i objęty kopią zapasową | `deploy/android/buduj-apk.sh`, `deploy/kopia-zapasowa.sh` | działa |
| Budowa APK: ograniczenie liczby procesów Gradle (`NEXUS_GRADLE_ROBOTNICY`, domyślnie 4) — bez tego AAPT2 nie startuje na zajętej maszynie | `deploy/android/buduj-apk.sh` | APK 12,5 MB, podpis sprawdzony |

## Nadal nieużyte materiały

- 9 filmów promocyjnych w trzech kadrach (`/film/katalog/`) — na stronie jest tylko film 60 s i zajawka.
- 20 animacji kampanijnych (`/kampania/`) — nigdzie.
- 18 animacji ekranu startowego i logowania (`/ruch/start/`) — nigdzie; `logowanie-ciemny` pokazuje
  całe przejście do aplikacji, więc nadaje się na stronę produktu, nie na ekran logowania.
- Lottie `motion/start/lottie/intro-znaku.json` — wymagałoby odtwarzacza (decyzja P5).

## Po zamknięciu wszystkich fal

1. `sudo systemctl restart danaco-nexus-api.service danaco-nexus-worker.service` — proces API
   działa na kodzie sprzed prac par, więc nowe punkty końcowe portalu (`/api/portal/stan`,
   `/api/portal/konto/ja`) zwracają 404 mimo obecności w kodzie.
2. Pełna bramka: `npm run build`, `npx vitest run`, `pytest backend/tests -q`, `ruff check backend`,
   `extension npm test`, `desktop npm test`, `pa11y --standard WCAG2AA` na adresach publicznych.
3. `deploy/android/buduj-apk.sh` — APK po zmianach w interfejsie.

## Izolacja kont, kredyty i pozycjonowanie (20 września, po fali 1)

| Co | Gdzie | Stan |
|---|---|---|
| Właściciel rozmów, plików, przebiegów, sesji i kluczy urządzeń | `backend/nexus/db.py` (`owner_id`, `ADMIN_OWNER`, migracja kolumn) | działa |
| Logowanie do aplikacji kontem portalu | `backend/nexus/api/auth.py` (`_konto_portalu`, zależność `wlasciciel`) | działa |
| Zakres zapytań po właścicielu | `api/conversations.py`, `api/files.py`, `api/runs.py` oraz moduły tworzące rozmowy (agenci, kod, research, strony, cloud, kalendarz, poczta) | działa, 8 testów |
| Limit 2 GB na konto | `backend/nexus/config.py` (`konto_limit_mb`), sprawdzenie przy przesyłaniu pliku | działa |
| Skrzynki pocztowe osobne dla kont | `backend/nexus/mail.py` (`config_path(settings, owner)`) | działa |
| Podłączanie skrzynki w aplikacji zamiast skryptu na serwerze | `api/modules/poczta.py`, `frontend/src/modules/poczta/UstawieniaKonta.tsx` | działa, 5 testów |
| Kredyty: cennik, naliczanie, księga, próg zlecenia | `backend/nexus/platnosci/kredyty.py`, `docs/platnosci/KREDYTY.md` | działa, 12 testów |
| Saldo i historia kredytów w aplikacji | `frontend/src/platnosci/Kredyty.tsx` | działa, 4 testy |
| Konto testowe bez płatności | `deploy/nexus-cli.sh konto-testowe` | działa |
| Baza wiedzy per konto: kolekcje, ich źródła i notatki | `backend/nexus/models/research.py` (`owner_id`), `research/store.py`, `api/modules/research.py` | działa, test w `test_izolacja_kont.py` |
| Ukrycie kont silnika przed użytkownikiem | `agent/runner.py` (`friendly_error`, brak powiadomień o limitach), `api/modules/agenci.py`, moduł Agenci | działa, 2 testy |
| Jedna instalacja zamiast trzech pakietów | `frontend/src/landing/InstallSection.tsx` | działa |
| Przekaz bez „prywatnego serwera”, z przestrzenią konta i 2 GB | `landing/tresc.ts`, `landing/sekcje.tsx`, `landing/Landing.tsx`, `index.html`, `src/seo.ts`, `portal/tresc.ts`, `portal/tresc-prawna.ts` | działa |

### Co zostaje do zrobienia w tym wątku

1. **Subskrypcje kluczowane kontem.** `platnosci_subskrypcje.uzytkownik` trzyma login
   właściciela instalacji, więc zakup dotyczy całej instalacji, a nie konta. Do czasu zmiany
   przydział kredytów z odnowienia trzeba wywołać ręcznie (`kredyty.przydziel_z_planu`).
2. **Odnowienie okresowe kredytów** przy zdarzeniu `invoice.paid` ze Stripe.
3. **Rotacja profili Claude Code CLI** (4 konta właściciela) z przełączeniem po limicie —
   dziś runner ma jeden profil `dane/claude-profil`.
4. **Chmura osobista per konto** — pliki Nextcloud nadal są wspólne; kolekcje bazy wiedzy
   są już rozdzielone.

## Nowy podział planów (20 września, po decyzji właściciela)

Okres próbny **nie jest osobnym planem**, tylko węższym zakresem planu, który go otwiera.
Konto bez opłaconego planu ma ten sam wąski zakres co okres próbny — żaden plan nie jest
już bezpłatny.

| | Okres próbny (7 dni) | Osobisty | Pro | Zespół |
|---|---|---|---|---|
| Przestrzeń (pliki + poczta) | 100 MB | 1 GB | 2 GB | 10 GB |
| Skrzynki pocztowe | brak | 1 | 10 | 10 |
| Wersje plików | nie | nie | tak | tak |
| Synchronizacja z komputerem | nie | tak | tak | tak |
| Kredyty na okres | 300 | 2 000 | 20 000 | 60 000 |
| Zadania naraz | 1 | 1 | 4 | 8 |
| Automatyzacje | 0 | 0 | 20 | 100 |
| Konta w zespole | 1 | 1 | 1 | 5 |

Zakres rozstrzyga serwer (`backend/nexus/platnosci/plany.py`) i wystawia go
`GET /api/platnosci/plany` w polach `przestrzen_mb`, `skrzynki_poczty`, `wersjonowanie`,
`synchronizacja` i `probny`. Limit zadań równoległych jest od teraz **egzekwowany**
w `backend/nexus/api/conversations.py`, więc wolno go sprzedawać w cenniku.

### Do zamiecenia po zakończeniu fal

Teksty witryny mówią jeszcze o „2 GB na koncie” jako wartości jednakowej dla wszystkich.
Po zmianie podziału trzeba je przepisać na wartości zależne od planu — pliki:
`frontend/src/landing/tresc.ts`, `frontend/src/landing/sekcje.tsx`, `frontend/src/seo.ts`,
`frontend/src/portal/tresc.ts`, `frontend/src/portal/tresc-prawna.ts` (i jego test).
Uwaga: „Pliki do 2 GB” w zakładce faktów to **największy pojedynczy plik**
(`NEXUS_UPLOAD_LIMIT_MB`), a nie przestrzeń konta — tego nie zmieniać.
