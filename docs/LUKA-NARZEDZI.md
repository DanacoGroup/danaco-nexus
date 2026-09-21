# Programy na serwerze bez narzędzia agenta

Stan na 20 września 2026, wieczorem. Rejestr `backend/nexus/tools/` liczy **101 narzędzi**
(rano było 59); stoi za nimi ponad trzydzieści programów i bibliotek. W `/danaco/programy`
leży **53 katalogi** programów i bibliotek (doszły: `grafika`, `motion-zasoby`,
`media-zasoby`) — reszta nie ma żadnego narzędzia, więc agent nie może ich użyć, choćby
użytkownik wprost o to poprosił.

Ten dokument jest wykazem tej luki, a nie obietnicą. Każda pozycja ma wpisaną funkcję,
którą dałaby użytkownikowi, i szacunek pracy.

## Podpięte dziś

ImageMagick · LibreOffice · Inkscape · FFmpeg i ffprobe · Real-ESRGAN · Tesseract ·
unpaper · rembg · Apache Tika · PyMuPDF · OpenCV · Pillow · pikepdf · reportlab ·
LanguageTool · Whisper · Piper · Qdrant · Node.js · Playwright.

Dołożone 20 września: **DDColor** (koloryzacja), **DeepFilterNet 3** (odszumianie mowy),
**Depth Anything V2** i **LaMa** (głębia, rozmycie tła, ożywienie zdjęcia, usuwanie
obiektów), **Demucs** (rozdzielenie ścieżek), **CodeFormer** (rekonstrukcja twarzy),
**Typst** i **Tectonic** (skład do druku), **pandoc**, **Docling**, **Iconify**,
**Lottie**, **gifski**, **oxipng**, **svgo**, **semgrep**, **ruff**, **shellcheck**,
**typos**, **pa11y**, **WhisperX** (mówcy w transkrypcji).

Dołożone wieczorem 20 września: **przeglądarka** (Playwright sterowany krok po kroku —
`browser_open`, `browser_click`, `browser_type`, `browser_scroll`, `browser_back`),
**Danaco Web Kit** (12 presetów branżowych, 50 motywów, 261 sekcji w 34 rodzinach, 65 typów podstron,
18 krojów nagłówkowych i kolekcja 113 szablonów otwartych — 81 z gotową witryną — z 2221 blokami — `site_kit_catalog`,
`site_from_kit`) oraz **Manim** (`animate_explainer`, animacja wyjaśniająca renderowana
w piaskownicy). **InsightFace** przestał być pozycją pominiętą: `find_faces` działa,
a warunki licencyjne i podstawa przetwarzania są opisane w rejestrze czynności (CZ-14).
**Uwaga z 21 września**: licencja modeli jest niekomercyjna, a produkt jest już
sprzedawany — sprawa czeka na rozstrzygnięcie właściciela (rejestr CZ-14).

Dołożone późnym wieczorem 20 września — kontrole projektu w `code_check`: **gitleaks**
(klucze i hasła wpisane wprost w kod; uruchamiany z `--redact`, więc sama wartość sekretu
nie wraca do rozmowy), **osv-scanner** (znane podatności bibliotek projektu wg bazy OSV)
i **jscpd** (skopiowane fragmenty kodu). Razem z semgrep, ruff, shellcheck i typos daje to
siedem kontroli pod jednym narzędziem.

Biblioteki materiałów (`/danaco/programy/grafika`, `/danaco/programy/motion-zasoby`,
`/danaco/programy/media-zasoby`) — zbudowane tego wieczoru orkiestracją agentów z weryfikatorem,
wszystko na licencjach z allowlisty (MIT, Apache-2.0, BSD, ISC, CC0, CC-BY-4.0, OFL). Agent ma do
nich `asset_library` (spis z zawężaniem) i `asset_to_site` (wstawienie pliku do szkicu strony).
Stan: grafika 27 zestawów (unDraw 1415 ilustracji, Carbon 6315 piktogramów, Twemoji 4027,
Open Peeps, Humaaans, wzory, tekstury, gradienty, makiety urządzeń), ruch 43 zestawy (tła WebGL
Vanta i tsParticles, shadery GLSL, animate.css, AOS, anime.js, kolejne zbiory Lottie), media
19 zestawów (dźwięki interfejsu Kenney CC0, podkłady muzyczne, LUT-y `.cube`, przejścia
GL Transitions, materiały PBR ambientCG, mapy oświetlenia HDRI i sceny Blendera z Poly Haven).
Razem 17 058 plików materiałów w trzech działach (po odsianiu plików budowy paczek, aplikacji przykładowych i testów, które zestawy niosą ze sobą jako repozytoria autorów).
Odrzucone i dlaczego: `odrzucone.json` w każdym dziale — m.in. Storyset (zakaz dalszej
dystrybucji), DrawKit (zakaz rozpowszechniania zbioru), OpenMoji (klauzula SA).

Biblioteka sekcji urosła tego wieczoru orkiestracją agentów ze 148 do **261 sekcji
w 34 rodzinach** (były 22). Domknięta została m.in. rodzina `forms/`: o 22:58 osiem
katalogów na dziewięć stało pustych, o 23:30 każdy ma komplet
(`Section.astro` + `schema.ts` + `example.json` + `meta.json` z polskim opisem).
Katalog bez składnika nie trafia do spisu — `site_kit_catalog` podaje tylko sekcje, które
naprawdę da się użyć.

Szablony aplikacji: w `/danaco/programy/web/kit/apps` leżą kompletne aplikacje webowe
z opisem `danaco-szablon.json` (marka, tokeny, kroje, polecenia dev/build), a **żadne
narzędzie ich nie czytało** — dla agenta nie istniały. Domykają to `app_templates` (spis)
i `app_from_template` (projekt w module Kod z kopii szablonu, bez `node_modules` i bez
historii gita autora). Sprawdzenie na szablonie `next-dashboard`: 89 plików, 633 kB, projekt
gotowy od razu. Do tego 33 aplikacje i panele leżące w kolekcji szablonów otwartych
(`charakter: [panel, aplikacja]` w `meta.json`) — razem **35 szablonów aplikacji** na React,
Vue, Next, Nuxt, Astro, Bootstrapie i Tailwindzie, każdy z licencją i adresem źródła.

Montaż filmu: biblioteki materiałów były, ale nie było czym ich złożyć — `media_process`
przerabiał **jedno gotowe nagranie**, więc na „zrób filmik promocyjny z tych zdjęć” agent nie
miał odpowiedzi. Domyka to `video_compose` (FFmpeg + Pillow): ujęcia ze zdjęć i klipów, ruch
kamery na każdym zdjęciu (zoompan), napisy rysowane do nakładki PNG, przenikanie między
ujęciami (xfade) i podkład z biblioteki `media-zasoby/muzyka` zapętlany na długość filmu.
Kadr 16:9, 9:16, 1:1 i 4:5. Pomiar: trzy ujęcia po 1,5 s w 1080 × 1920 z podkładem — 1,6 s.
W interfejsie: Studio → zakładka „Montaż”.

Biblioteka animacji Lottie: serwer miał sam odtwarzacz i **zero gotowych animacji**. Wgrane
**451 animacji** z `airbnb/lottie-android` (Apache-2.0) do `/danaco/programy/web/lottie/animacje/`
wraz z wykazem `indeks.json`; agent ma do nich `lottie_library` (spis z zawężaniem po nazwie),
a `render_lottie` przyjmuje teraz pozycję biblioteki zamiast pliku od użytkownika. Render animacji
240 px do GIF-a: 2,5 s. Zastrzeżenie licencyjne: Apache-2.0 obejmuje repozytorium; pojedyncze
animacje pochodzą od autorów społeczności, więc przy użyciu komercyjnym warto sprawdzić autora.

Naprawione tego samego wieczoru: **presety Web Kitu w ogóle nie dawały się zbudować** —
dziewięć na dwanaście kończyło budowę błędem „nieznany typ podstrony”, bo mapy stron
nazywają część podstron po swojemu (`menu`, `product-index`, `courses-index`, `article`,
`changelog-entry`), a rdzeń zna 35 typów i krótką listę nazw zastępczych. Rdzeń leży
w `/danaco/programy` (tylko do odczytu), więc `site_from_kit` uzupełnia mapę w wygenerowanym
projekcie tuż przed budową. Po zmianie budują się wszystkie dwanaście: od 45 (personal-brand)
do 235 podstron (legal-portal), każdy w 2–4 s.

Sprawdzone na prawdziwych plikach, nie tylko w testach: koloryzacja małego zdjęcia —
5 s (wczytanie modelu 4,4 s, praca 0,6 s); ożywienie zdjęcia — film 1440×1080, 90 klatek,
3 s materiału powstaje w 11 s (głębia 4,8 s, warstwy 3,1 s, render 3,3 s).

## Gotowe w kodzie, czeka na administratora

| Funkcja | Czego brakuje |
|---|---|
| Podział transkrypcji na mówców (`transcribe_speakers`, `mowcy = prawda`) | modelu `pyannote` w `/danaco/programy/modele/audio/pyannote` (znacznik `GOTOWE` nie istnieje). Narzędzie mówi to wprost i proponuje transkrypcję bez rozdzielania głosów, więc nie jest to usterka — ale funkcja jest niedostępna, dopóki model nie zostanie pobrany jednorazowo przez administratora |

## Co zostało świadomie pominięte

| Program | Dlaczego nie |
|---|---|
| **GIMP** (Script-Fu) | pokrywa się z `imagemagick`. Zastrzeżenie o wykonywaniu kodu od modelu straciło moc — piaskownica (`agent/piaskownica.py`) robi to bezpiecznie i tak właśnie działa `animate_explainer` — ale sam powód „to samo, co mamy” zostaje |
| **Blender** | render Cycles zajmuje serwer na kwadranse; wymaga kolejki zadań długich i limitów, których produkt jeszcze nie ma |
| **surowy FFmpeg** | konwersje, przycinanie i kompresję ma `media_process`; FFmpeg jest pod spodem |
| **`k6`, `autocannon`, `hyperfine`, `git-lfs`, `gh`** | narzędzia wytwórcze zespołu, nie funkcje dla użytkownika produktu |
| **`depcruise`, `madge`, `knip`, `scc`, `tokei`** | analiza granic modułów i statystyki repozytorium: przydatne przy pracy nad tym projektem, ale dla właściciela konta w module Kod to wykresy, nie odpowiedzi. Do rozważenia, gdy moduł Kod dostanie widok architektury |
| **`lnav`** | czytnik dzienników serwera — dziennik instalacji jest nasz, nie użytkownika |
| **32 szablony kolekcji bez gotowej witryny** | mają wyłącznie źródło. Dosiew magazynu pnpm i budowa (20 września, wieczorem) przeszły dla ośmiu projektów Next.js, ale dały artefakty serwerowe bez arkuszy stylów — usunięte. Reszta wymaga bazy danych, kluczy API albo sieci w trakcie renderu. `site_kit_catalog` oznacza je `gotowa_witryna: false`, a `site_from_template` odmawia z wyjaśnieniem |

## Kolejność dalszej pracy

1. **Blender** — dopiero gdy będzie kolejka zadań długich i limit czasu renderu na konto.
2. **zoekt** — szybkie wyszukiwanie w dużym repozytorium dla modułu Kod, gdy projekty urosną.
3. **Szablony Typst** — `typeset_document` ma sześć układów (raport, oferta, CV, broszura,
   plakat, umowa). Do rozważenia kolejne pod konkretne zastosowania: faktura i katalog
   produktów. Obie potrzebują jednak danych, których dziś narzędzie nie przyjmuje (pozycje
   z ceną i stawką podatku, zdjęcia produktów), więc to nie jest sam szablon.
