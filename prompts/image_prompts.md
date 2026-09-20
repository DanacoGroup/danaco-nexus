# Danaco Nexus — Prompty do generatorów obrazów

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Rodzaj** | Personal AI Workspace |
| **Opis** | Osobisty agent AI działający na serwerze Danaco, dostępny przez aplikację PWA: rozmowa z Claude, zdjęcia i wspomnienia, twórczość, czytanie na głos, plany i codzienne sprawy, dokumenty i OCR, przetwarzanie plików, automatyzacje, wyszukiwanie wiedzy i chmura plików. |
| **Producent** | Danaco Holding Group Sp. z o.o. |
| **Twórca** | Dariusz Naharnowicz |
| **Wersja** | etap 1 (projekt) |
| **Status** | Deweloperski |
| **Data** | 2026-09-19 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Prompty do generatorów obrazów |
| **Klasa dokumentu** | Specyfikacja docelowa |
| **Odbiorcy** | projektant · autor treści strony produktu · wykonawca obrazów (Midjourney, SDXL, Flux, DALL·E) |
| **Przeznaczenie** | Dokument daje gotowe, powtarzalne prompty do dziesięciu obrazów atmosferycznych marki wraz z parametrami i kryteriami przyjęcia. |
| **Zakres** | Hero · Dashboard · OCR · AI Assistant · Knowledge Base · File Processing · Wspomnienia · Twórczość · Podróże i plany · Wieczór i rozrywka; różnice składni generatorów; wspólne przyrostki stylu; ocena próbek SDXL-Turbo. |
| **Poza zakresem** | Zasady stylu ilustracji wektorowych i fotografii — [Księga marki](../branding/BRAND_GUIDE.md) rozdz. 6 i 7; układ strony produktu — zespół strony produktu. |
| **Dokument nadrzędny** | [Księga marki](../branding/BRAND_GUIDE.md) |
| **Dokumenty powiązane** | [Księga marki — styl ilustracji](../branding/BRAND_GUIDE.md#6-styl-ilustracji) · [Plansza porównawcza próbek](../branding/ilustracje/sdxl/plansza-porownawcza.png) |
| **Źródła normatywne** | `design-tokens/colors.json` (wartości HEX) · `branding/etap-0/zespol-C/v3-personal-ai-os/README.md` (historia znaku) |
| **Zasada nadrzędna** | Obraz atmosferyczny tworzy nastrój i nigdy nie udaje interfejsu, danych ani znaku — gdy kadr wymaga jednego z nich, wstawia się prawdziwy zrzut albo oryginalny plik znaku. |

## Spis treści

1. [Czym są obrazy atmosferyczne marki](#1-czym-są-obrazy-atmosferyczne-marki)
2. [Różnice składni generatorów](#2-różnice-składni-generatorów)
   - [2.1 Zestawienie](#21-zestawienie)
   - [2.2 Wnioski z próbek SDXL-Turbo](#22-wnioski-z-próbek-sdxl-turbo)
3. [Wspólne przyrostki stylu marki](#3-wspólne-przyrostki-stylu-marki)
   - [3.1 Przyrostek pozytywny](#31-przyrostek-pozytywny)
   - [3.2 Przyrostek negatywny](#32-przyrostek-negatywny)
   - [3.3 Paleta w promptach](#33-paleta-w-promptach)
4. [Hero](#4-hero)
5. [Dashboard](#5-dashboard)
6. [OCR](#6-ocr)
7. [AI Assistant](#7-ai-assistant)
8. [Knowledge Base](#8-knowledge-base)
9. [File Processing](#9-file-processing)
10. [Wspomnienia](#10-wspomnienia)
11. [Twórczość](#11-twórczość)
12. [Podróże i plany](#12-podróże-i-plany)
13. [Wieczór i rozrywka](#13-wieczór-i-rozrywka)
14. [Próbki SDXL-Turbo — pochodzenie i ocena](#14-próbki-sdxl-turbo--pochodzenie-i-ocena)
15. [Kryteria odbioru](#15-kryteria-odbioru)

---

## 1. Czym są obrazy atmosferyczne marki

Obraz atmosferyczny to rastrowy obraz nastroju na stronę produktu, do materiałów
społecznościowych i na tło ekranów powitalnych. Nie objaśnia funkcji — od tego są
ilustracje wektorowe pustych stanów (typ A w [Księdze marki](../branding/BRAND_GUIDE.md#6-styl-ilustracji)).
Obraz atmosferyczny (typ B) pokazuje **przestrzeń**, **światło** i **materię**: ciemne,
spokojne wnętrze, jedno źródło światła w barwach Aurory, szkło i półprzezroczystość.

Dziesięć obrazów odpowiada dziesięciu miejscom strony produktu. Sześć pierwszych dotyczy
funkcji zamówionych w zleceniu, cztery ostatnie — życia prywatnego, bo Nexus jest agentem
osobistym, a nie wyłącznie narzędziem pracy:

| Prompt | Miejsce użycia | Proporcje podstawowe | Próbki SDXL-Turbo |
|---|---|---|---|
| Hero | pierwszy ekran strony produktu, grafika Open Graph (wariant) | 16:9 · 4:5 (telefon) | `hero-a.png` · `hero-b.png` · `hero-a-2048.webp` |
| Dashboard | tło pod prawdziwym zrzutem aplikacji w sekcji „Twoja przestrzeń” | 16:10 | `dashboard-a.png` · `dashboard-b.png` |
| OCR | sekcja „Dokumenty i skany” | 3:2 · 4:5 | `ocr-a.png` · `ocr-b.png` |
| AI Assistant | sekcja „Asystent”, tło ekranu powitalnego, media społecznościowe | 1:1 · 4:5 | `asystent-a.png` · `asystent-b.png` |
| Knowledge Base | sekcja „Wiedza i wyszukiwanie” | 3:2 | `wiedza-a.png` · `wiedza-b.png` |
| File Processing | pas między sekcjami funkcji | 21:9 · 16:9 | `pliki-a.png` · `pliki-b.png` |
| Wspomnienia | sekcja „Zdjęcia i wspomnienia”, ekran albumu | 4:5 · 3:2 | `wspomnienia-a.png` · `wspomnienia-b.png` |
| Twórczość | sekcja „Twórz z Nexusem”, ekran twórczości | 1:1 · 3:2 | `tworczosc-a.png` · `tworczosc-b.png` |
| Podróże i plany | sekcja „Plany i codzienność”, grafiki sezonowe | 16:9 · 4:5 | `podroze-a.png` · `podroze-b.png` |
| Wieczór i rozrywka | sekcja „Wieczorem”, tapeta wieczorna | 4:5 · 9:16 · 16:9 | `wieczor-a.png` · `wieczor-b.png` |

Wszystkie próbki leżą w katalogu `branding/ilustracje/sdxl/`; zestawia je
[plansza porównawcza](../branding/ilustracje/sdxl/plansza-porownawcza.png).

---

## 2. Różnice składni generatorów

### 2.1 Zestawienie

Tabela zbiera różnice, które wpływają na zapis promptu. Jeden prompt główny w każdym
rozdziale jest napisany prozą i działa bez zmian w Midjourney, Flux i DALL·E; dla SDXL
podano osobną, krótszą postać.

| Cecha | Midjourney (v6 i nowsze) | SDXL 1.0 / SDXL-Turbo | Flux.1 (dev, pro) | DALL·E 3 / GPT Image |
|---|---|---|---|---|
| Długość promptu | do kilkuset znaków, proza | **77 tokenów CLIP** na koder; nadmiar jest obcinany | długa proza (koder T5, kilkaset tokenów) | długa proza; model sam przepisuje prompt |
| Prompt negatywny | parametr `--no robot, brain, text` | osobne pole; w **SDXL-Turbo przy guidance 0 pole nie działa** | brak; wykluczenia prozą („no text, no logos”) | brak; wykluczenia prozą |
| Wagi słów | `słowo::2`, `::-0.5` | `(słowo:1.2)` w ComfyUI i A1111 | brak | brak |
| Proporcje | `--ar 16:9` | szerokość × wysokość w pikselach (wielokrotność 64) | szerokość × wysokość | `1792x1024`, `1024x1792`, `1024x1024` |
| Ziarno | `--seed 1107` | parametr `seed` | parametr `seed` | brak kontroli |
| Styl | `--style raw` (mniej upiększeń), `--stylize 0–1000` | model i sampler | `guidance` 2,5–4 | `style: natural` zamiast `vivid` |
| Kolory HEX | ignorowane jako liczby; działa nazwa barwy | ignorowane; działa nazwa barwy | częściowo rozumiane | częściowo rozumiane |
| Tekst w obrazie | zawodny | zawodny | dobry | dobry |

**Konwencja parametrów marki.** Ziarna marki to **1107** (wariant A) i **2214**
(wariant B). Te same ziarna podaje się we wszystkich generatorach, które je przyjmują —
ułatwia to odtworzenie obrazu po zmianie promptu.

| Generator | Parametry domyślne marki |
|---|---|
| Midjourney | `--style raw --stylize 120 --chaos 5 --seed 1107` + `--ar` z rozdziału |
| SDXL 1.0 (bazowy) | 30 kroków · CFG 5,5 · sampler DPM++ 2M Karras · 1344 × 768 (16:9) albo 1024 × 1024 |
| SDXL-Turbo (serwer) | 4 kroki · guidance 0,0 · 512 × 512 · float32, `variant="fp16"` · powiększenie Real-ESRGAN ×4 |
| Flux.1 dev | 28 kroków · guidance 3,5 · 1344 × 768 (16:9) |
| DALL·E 3 | `size: 1792x1024` · `quality: hd` · `style: natural` |

### 2.2 Wnioski z próbek SDXL-Turbo

Próbki wygenerowano na serwerze bez karty GPU (ok. 10 s na obraz 512 × 512 przy 4
krokach). Z dwóch rund wynikają cztery reguły pisania promptów dla tego modelu:

| Obserwacja | Reguła |
|---|---|
| Słowo „rose” jako nazwa barwy dało różę w szklanej kuli (`asystent-b.png`) | nazw barw będących przedmiotami nie używa się; zamiast „rose” — „pink”, zamiast „apricot” — „warm orange” |
| Scena z dwoma obiektami i relacją (kartka **i** promień nad nią) traci jeden obiekt (`ocr-a.png`, `ocr-b.png`) | jeden obiekt główny na prompt; relację buduje się w montażu dwóch obrazów |
| „Glass tiles” i „squares” dają mozaikę pikseli (`pliki-a.png`, `pliki-b.png`) | formy prostokątne nazywa się „panels”, „cards”, „sheets”, nigdy „tiles”, „squares”, „grid” |
| Model rozjaśnia tło mimo „deep navy darkness” — wszystkie próbki mają tło jaśniejsze niż `neutral-950` | ciemność zapisuje się na **początku** promptu; tło przyciemnia się w obróbce (krzywe), nie promptem |

Prompty pierwszej rundy mieściły się w limicie 77 tokenów (63–72 tokeny), więc
niepowodzenia nie wynikają z obcięcia, tylko z nadmiaru pojęć w jednej scenie.

---

## 3. Wspólne przyrostki stylu marki

### 3.1 Przyrostek pozytywny

Przyrostek dopisuje się na końcu promptu głównego. Postać pełna służy generatorom
z długim promptem, postać krótka — SDXL.

**Pełny (Midjourney, Flux, DALL·E):**

```text
dark premium minimal aesthetic, deep navy-graphite darkness, a single soft light source
blending warm orange, pink, violet and sky blue, frosted glass and translucent materials,
matte surfaces, calm and quiet mood, generous negative space, cinematic lighting,
photorealistic 3d render, high dynamic range, subtle film grain
```

**Krótki (SDXL, SDXL-Turbo; ok. 20 tokenów):**

```text
dark navy background, soft aurora light, frosted glass, minimal, cinematic
```

### 3.2 Przyrostek negatywny

W SDXL wpisuje się go w pole promptu negatywnego, w Midjourney po `--no` (bez słowa
„no”), we Flux i DALL·E — jako zdanie „Avoid: …” na końcu promptu.

```text
robot, android, humanoid, cyborg, brain, neurons, circuit board, binary code, matrix rain,
digital rain, glowing blue grid, pixel mosaic, hologram face, face, person, hands, text,
letters, numbers, watermark, logo, signature, user interface text, cluttered, busy,
cyberpunk city, neon signs, lens flare, oversaturated, washed out, low contrast, noisy,
jpeg artifacts, deformed, rose flower
```

**Postać Midjourney:**

```text
--no robot, android, brain, circuit board, binary code, matrix, pixel mosaic, face, person, text, letters, watermark, logo, cyberpunk, neon signs, lens flare
```

### 3.3 Paleta w promptach

Generatory nie odczytują wartości HEX jako koloru. W promptach używa się nazw barw
z kolumny „Nazwa w prompcie”; wartości HEX służą do oceny wyniku i do korekty barwnej
w obróbce.

| Rola | Token | HEX | Nazwa w prompcie |
|---|---|---|---|
| Tło, ciemność | `color.neutral.950` | `#0D0F17` | deep navy-graphite darkness |
| Powierzchnia, podłoga | `color.neutral.900` · `color.neutral.800` | `#191B25` · `#292C37` | dark matte graphite surface |
| Światło ciepłe | `color.brand.apricot` | `#FF8A5B` | warm orange / soft apricot glow |
| Światło energii | `color.brand.rose` | `#F2528F` | pink (nigdy „rose”) |
| Światło AI | `color.brand.iris` | `#7B5CFF` | violet |
| Światło chłodne | `color.brand.sky` | `#3BA7FF` | sky blue |
| Jasne refleksy | `color.neutral.50` | `#F9FAFE` | soft white highlights |

**Proporcja barw w kadrze:** ciemność `#0D0F17`–`#292C37` co najmniej 60 % powierzchni,
światło Aurory najwyżej 25 %, jasne refleksy najwyżej 5 %. Ciepłe barwy (orange, pink)
leżą po stronie źródła światła, chłodne (violet, sky blue) — na krawędziach i w cieniach.

---

## 4. Hero

| Pole | Ustalenie |
|---|---|
| **Cel i miejsce użycia** | Pierwszy ekran strony produktu za nagłówkiem „Your Personal AI Workspace”; wariant 1200 × 630 jako tło grafiki Open Graph w kampaniach. Obraz ma powiedzieć: to Twoja przestrzeń, a AI jest w niej obecna. |
| **Kompozycja** | Szklany łuk (drzwi, sklepienie) w prawej tercji kadru; pod łukiem, na podłodze, mała kula światła. Lewe 45 % kadru puste — miejsce na nagłówek i przycisk. |
| **Kadr** | Plan ogólny z poziomu oczu, obiektyw 35 mm, przysłona f/2.8; łuk zajmuje 55–65 % wysokości kadru. |
| **Światło** | Jedno źródło: kula pod łukiem i poświata we wnętrzu łuku; ciepło (orange, pink) nisko, chłód (violet, sky blue) w górze łuku. Delikatna mgła wolumetryczna. |
| **Paleta HEX** | `#0D0F17` · `#191B25` · `#FF8A5B` · `#F2528F` · `#7B5CFF` · `#3BA7FF` · `#F9FAFE` |
| **Materiały** | Szkło matowe (frosted glass) z jasną krawędzią; matowa, lekko odbijająca podłoga z grafitu. |
| **Nastrój** | Spokój, intymność, zaproszenie do środka; premium bez przepychu. |
| **Proporcje** | 16:9 (1920 × 1080, 2560 × 1440) · 4:5 dla telefonu (1080 × 1350) · 1200 × 630 dla Open Graph |

**Prompt główny:**

```text
A single softly glowing arch of frosted glass standing in a dark, minimal architectural
space, placed in the right third of the frame. A small luminous sphere of light rests on
the floor beneath the arch. Inside the arch the light blends from warm orange and pink near
the floor to violet and sky blue at the top. Deep navy-graphite darkness around, faint
reflection on a matte graphite floor, thin volumetric haze, large empty dark area on the
left side for a headline. Calm, intimate, premium product photography, 35mm lens, f/2.8.
```

**Prompt SDXL (runda 1 — źródło próbek):**

```text
a softly glowing translucent frosted glass arch standing in a dark minimal room, a small
luminous orb resting beneath the arch, warm apricot and rose light fading into violet and
blue, volumetric haze, product photography, deep navy graphite darkness, soft aurora light
apricot pink violet sky blue, frosted glass, minimal, premium, calm, cinematic lighting,
high detail
```

**Prompt SDXL (postać zalecona do dalszej pracy):**

```text
dark navy background, a softly glowing frosted glass arch in a dark minimal room, a small
luminous orb on the floor beneath the arch, warm orange and pink light fading into violet
and blue, volumetric haze, minimal, cinematic
```

**Prompt negatywny:** przyrostek z [rozdz. 3.2](#32-przyrostek-negatywny) oraz
`door frame, wooden door, church, gothic window, neon tube, sign`.

| Generator | Parametry |
|---|---|
| Midjourney | `--ar 16:9 --style raw --stylize 120 --chaos 5 --seed 1107` |
| SDXL 1.0 | 1344 × 768 · 30 kroków · CFG 5,5 · DPM++ 2M Karras · seed 1107 |
| SDXL-Turbo | 512 × 512 · 4 kroki · guidance 0,0 · seed 1107 / 2214 · Real-ESRGAN ×4 |
| Flux.1 dev | 1344 × 768 · 28 kroków · guidance 3,5 · seed 1107 |
| DALL·E 3 | `1792x1024` · `hd` · `natural` |

**Wariant alternatywny 1 — wnętrze łuku:** kadr od środka łuku na zewnątrz, łuk jako
rama obrazu, kula światła na pierwszym planie, rozmyta.

```text
View from inside a frosted glass arch looking out into a dark minimal space, the arch
framing the image, a small luminous sphere of warm orange and pink light in the soft-focus
foreground, violet and sky blue glow on the glass edges, deep navy darkness, calm, cinematic.
```

**Wariant alternatywny 2 — pora wieczoru:** światło przesunięte ku chłodnej części
Aurory (violet, sky blue), ciepło tylko w kuli; na kampanie wieczorne i motyw ciemny.

```text
A frosted glass arch in a dark minimal room at night, cool violet and sky blue light on
the glass, only the small sphere beneath the arch glows warm orange, deep navy-graphite
darkness, quiet, minimal, premium, 35mm, shallow depth of field.
```

**Kryteria akceptacji:**

- łuk czytelny jako architektura (drzwi, sklepienie), nie jako logo ani litera;
- kula światła leży pod łukiem i jest najjaśniejszym punktem kadru;
- lewe 45 % kadru ciemne i jednolite — nagłówek w kolorze `fg` osiąga kontrast co najmniej 7:1;
- po przyciemnieniu tło mieści się w zakresie `#0D0F17`–`#191B25`;
- brak tekstu, postaci i przedmiotów codziennego użytku.

**Zakazy:** biały łuk na kaflu (to znak, nie ilustracja); neonowe rurki; drzwi drewniane
i okna gotyckie; więcej niż jeden łuk; łuk przecięty krawędzią kadru.

---

## 5. Dashboard

Nazwa promptu pochodzi ze zlecenia i pozostaje identyfikatorem pliku; w tekstach
interfejsu obowiązuje nazwa „Wskaźniki” albo „Przestrzeń”.

| Pole | Ustalenie |
|---|---|
| **Cel i miejsce użycia** | Tło sekcji „Twoja przestrzeń” strony produktu; na obraz nakłada się **prawdziwy** zrzut aplikacji. Obraz daje głębię i światło, nie treść. |
| **Kompozycja** | Trzy do pięciu półprzezroczystych, szklanych paneli w różnych głębokościach, ułożonych asymetrycznie; środek kadru wolny na zrzut aplikacji. |
| **Kadr** | Plan średni, lekko z góry (10–15°), obiektyw 50 mm, mała głębia ostrości — panele dalsze rozmyte. |
| **Światło** | Obrysowe (rim light) w barwie violet i sky blue na krawędziach paneli; ciepła, rozmyta poświata orange za panelami. |
| **Paleta HEX** | `#0D0F17` · `#191B25` · `#292C37` · `#7B5CFF` · `#3BA7FF` · `#FF8A5B` |
| **Materiały** | Szkło matowe o zaokrąglonych narożach, cienkie jasne krawędzie; bez ramek metalowych. |
| **Nastrój** | Porządek, lekkość, skupienie. |
| **Proporcje** | 16:10 (1920 × 1200) · 16:9 |

**Prompt główny:**

```text
Three to five translucent frosted glass panels with softly rounded corners floating at
different depths in a dark, empty space, arranged asymmetrically around an empty center.
Thin violet and sky blue rim light on the panel edges, a soft warm orange glow far behind
them. The panels are blank, without any text or interface. Deep navy-graphite darkness,
shallow depth of field, distant panels blurred. Calm, orderly, premium 3d render, 50mm.
```

**Prompt SDXL (krótki, runda 2 — źródło próbek):**

```text
dark navy room, three floating translucent glass rectangles at different depths, soft
violet and blue rim light, warm orange glow behind them, minimal 3d render, cinematic,
dark empty space
```

**Prompt negatywny:** przyrostek z [rozdz. 3.2](#32-przyrostek-negatywny) oraz
`display case, showcase, cabinet, box, frame, screen with charts, graphs, numbers`.

| Generator | Parametry |
|---|---|
| Midjourney | `--ar 16:10 --style raw --stylize 100 --chaos 5 --seed 1107` |
| SDXL 1.0 | 1216 × 768 · 30 kroków · CFG 5,5 · DPM++ 2M Karras · seed 1107 |
| SDXL-Turbo | 512 × 512 · 4 kroki · guidance 0,0 · seed 1107 / 2214 |
| Flux.1 dev | 1216 × 768 · 28 kroków · guidance 3,5 · seed 1107 |
| DALL·E 3 | `1792x1024` · `hd` · `natural` |

**Wariant alternatywny 1 — jeden panel główny:** jeden duży panel na wprost, dwa mniejsze
rozmyte w tle; pod zrzut pojedynczego okna.

```text
One large blank frosted glass panel facing the camera in dark space, two smaller panels
blurred far behind, violet and sky blue edge light, faint warm glow behind, deep navy
darkness, minimal, premium 3d render.
```

**Wariant alternatywny 2 — widok z boku:** panele ustawione w szeregu, widziane pod kątem
45°, jak karty w szufladzie; pod sekcję „Wszystko w jednym miejscu”.

```text
A row of blank frosted glass panels standing one behind another, seen at a 45 degree angle,
soft violet light passing through them, warm orange glow at the far end, dark matte floor,
deep navy darkness, minimal, cinematic.
```

**Kryteria akceptacji:** panele puste (bez wykresów, liczb, tekstu); środek kadru ciemny
i spokojny na zrzut; co najmniej trzy plany głębi; barwa krawędzi w zakresie violet–sky blue.

**Zakazy:** wykresy, liczby i fikcyjne interfejsy; gabloty i skrzynie (błąd próbki
`dashboard-a.png`); monitory i laptopy; pomarańczowe plamy wewnątrz paneli.

---

## 6. OCR

| Pole | Ustalenie |
|---|---|
| **Cel i miejsce użycia** | Sekcja „Dokumenty i skany” strony produktu; obraz pokazuje przemianę papieru w czytelny tekst cyfrowy bez pokazywania samego tekstu. |
| **Kompozycja** | Jedna kartka papieru na ciemnym, matowym blacie, lekko skośnie; w poprzek kartki cienka linia światła. Część kartki nad linią ostra i jasna, pod linią — przygaszona. |
| **Kadr** | Makro z góry pod kątem 30°, obiektyw 100 mm, bardzo mała głębia ostrości. |
| **Światło** | Linia skanowania w barwie violet przechodząca w sky blue; ciepły, rozproszony odblask orange na papierze po stronie przeskanowanej. |
| **Paleta HEX** | `#0D0F17` · `#191B25` · `#F9FAFE` · `#7B5CFF` · `#3BA7FF` · `#FF8A5B` |
| **Materiały** | Papier matowy o widocznym włóknie, bez nadruku albo z nieczytelnymi, rozmytymi wierszami; blat z grafitu. |
| **Nastrój** | Precyzja, czystość, cisza. |
| **Proporcje** | 3:2 (1800 × 1200) · 4:5 (1080 × 1350) |

**Prompt główny:**

```text
Macro photograph of a single sheet of matte paper lying slightly diagonal on a dark graphite
desk. A thin line of violet light fading into sky blue crosses the page horizontally like a
scanner beam. The part of the page above the beam looks crisp and bright, the part below
is dimmer and softer. Faint blurred lines suggest text but nothing is legible. A soft warm
orange reflection on the paper. Deep navy-graphite darkness, 100mm macro lens, very shallow
depth of field, calm and precise.
```

**Prompt SDXL (krótki, runda 2 — źródło próbek):**

```text
macro photo, a single sheet of paper on a black desk in darkness, a thin glowing violet
laser line scanning across the paper, soft blue light, dark navy background, minimal, cinematic
```

**Zalecenie dla SDXL:** model gubi kartkę, gdy w scenie jest też promień. Kartkę
generuje się osobnym promptem („a single sheet of blank white paper on a dark graphite desk,
macro, top light, dark navy background”), a linię światła dokłada w obróbce warstwą
gradientu Iris → Sky w trybie „screen”.

**Prompt negatywny:** przyrostek z [rozdz. 3.2](#32-przyrostek-negatywny) oraz
`scanner machine, printer, laser show, red laser, legible text, handwriting, stack of papers`.

| Generator | Parametry |
|---|---|
| Midjourney | `--ar 3:2 --style raw --stylize 80 --seed 1107` |
| SDXL 1.0 | 1216 × 832 · 30 kroków · CFG 6 · DPM++ 2M Karras · seed 1107 |
| SDXL-Turbo | 512 × 512 · 4 kroki · guidance 0,0 · seed 1107 / 2214 |
| Flux.1 dev | 1216 × 832 · 28 kroków · guidance 3,5 · seed 1107 |
| DALL·E 3 | `1792x1024` · `hd` · `natural` |

**Wariant alternatywny 1 — zdjęcie z telefonu:** zamiast kartki — pognieciony paragon albo
zdjęcie dokumentu z krzywą perspektywą, prostowane przez światło; pod funkcję poprawy skanów.

```text
A slightly crumpled paper receipt on a dark graphite desk, one half flattened and bright under
a thin violet and sky blue line of light, the other half creased and dim, macro, deep navy
darkness, minimal, precise.
```

**Wariant alternatywny 2 — plik PDF w szkle:** kartka przechodzi w taflę szkła po drugiej
stronie linii światła.

```text
A sheet of paper on a dark desk turning into a thin pane of frosted glass where a violet
line of light crosses it, paper texture on one side, clean glass on the other, deep navy
darkness, macro, cinematic.
```

**Kryteria akceptacji:** kartka papieru obecna i rozpoznawalna; linia światła przecina
kartkę, nie tło; żaden fragment tekstu nie jest czytelny; tło ciemne.

**Zakazy:** czerwony laser; urządzenia (skaner, drukarka); czytelny tekst w dowolnym
języku; stosy dokumentów kojarzące się z biurokracją.

---

## 7. AI Assistant

| Pole | Ustalenie |
|---|---|
| **Cel i miejsce użycia** | Sekcja „Asystent” strony produktu, tło ekranu powitalnego aplikacji (z przyciemnieniem), grafiki do mediów społecznościowych. Kula światła jest obrazem punktu ze znaku: AI obecna u Ciebie. |
| **Kompozycja** | Jedna szklana kula światła unosząca się nisko nad matową powierzchnią, w złotym podziale kadru; wyraźne odbicie w powierzchni. |
| **Kadr** | Plan bliski, z poziomu powierzchni, obiektyw 85 mm, tło całkowicie rozmyte. |
| **Światło** | Kula jest źródłem światła: wnętrze ciepłe (orange, pink), krawędź chłodna (violet, sky blue); miękka poświata na powierzchni pod kulą. |
| **Paleta HEX** | `#0D0F17` · `#191B25` · `#FF8A5B` · `#F2528F` · `#7B5CFF` · `#3BA7FF` |
| **Materiały** | Szkło przezroczyste z wewnętrznym, mglistym światłem; matowy grafit. |
| **Nastrój** | Obecność, bliskość, gotowość — asystent czeka, nie narzuca się. |
| **Proporcje** | 1:1 (1080 × 1080) · 4:5 (1080 × 1350) · 9:16 (tapeta telefonu) |

**Prompt główny:**

```text
A small sphere of clear glass filled with soft misty light, hovering just above a dark matte
graphite surface. The core of the sphere glows warm orange and pink, the rim of the glass
turns violet and sky blue. A gentle glow and a clear reflection on the surface beneath it.
Deep navy-graphite darkness, completely blurred background, 85mm lens, intimate and quiet
atmosphere, premium 3d render.
```

**Prompt SDXL (krótki, runda 1 — źródło próbek):**

```text
a small luminous sphere of soft light hovering above a dark matte surface, gentle apricot
rose violet and blue glow around it, soft reflection on the surface, intimate quiet
atmosphere, 3d render, deep navy graphite darkness, soft aurora light apricot pink violet
sky blue, frosted glass, minimal, premium, calm, cinematic lighting, high detail
```

Postać zalecona do dalszej pracy zastępuje „apricot rose” słowami „warm orange pink”
(patrz [rozdz. 2.2](#22-wnioski-z-próbek-sdxl-turbo)).

**Prompt negatywny:** przyrostek z [rozdz. 3.2](#32-przyrostek-negatywny) oraz
`crystal ball, fortune teller, flower inside, planet, eye, face`.

| Generator | Parametry |
|---|---|
| Midjourney | `--ar 1:1 --style raw --stylize 150 --seed 1107` |
| SDXL 1.0 | 1024 × 1024 · 30 kroków · CFG 5,5 · DPM++ 2M Karras · seed 1107 |
| SDXL-Turbo | 512 × 512 · 4 kroki · guidance 0,0 · seed 1107 / 2214 |
| Flux.1 dev | 1024 × 1024 · 28 kroków · guidance 3,5 · seed 1107 |
| DALL·E 3 | `1024x1024` · `hd` · `natural` |

**Wariant alternatywny 1 — oddech:** kula w trzech fazach jasności ustawionych obok siebie;
do animacji ekranu startowego (klatki kluczowe).

```text
Three identical small glass spheres of soft light in a row above a dark matte surface, the
left one dim, the middle one brighter, the right one fully glowing warm orange and pink with
a violet rim, deep navy darkness, minimal, premium 3d render.
```

**Wariant alternatywny 2 — pod dachem:** kula pod niskim, szklanym łukiem widzianym z boku;
łączy obraz asystenta z historią znaku.

```text
A small glowing glass sphere resting under a low frosted glass arch, seen from the side,
warm orange and pink core, violet and sky blue rim, dark matte graphite surface, deep navy
darkness, quiet, intimate, cinematic.
```

**Kryteria akceptacji:** jedna kula; wnętrze ciepłe, krawędź chłodna; odbicie w powierzchni;
tło bez szczegółów.

**Zakazy:** kryształowa kula wróżki; przedmioty wewnątrz kuli (błąd próbki `asystent-b.png`);
oczy, twarze; planety i kosmos.

---

## 8. Knowledge Base

| Pole | Ustalenie |
|---|---|
| **Cel i miejsce użycia** | Sekcja „Wiedza i wyszukiwanie” strony produktu: dokumenty użytkownika tworzą bazę, którą przeszukuje się po znaczeniu. |
| **Kompozycja** | Kilka półprzezroczystych kart ułożonych w głąb; od kart biegną cienkie nici światła i zbiegają się w jednym ciepłym punkcie po prawej stronie kadru. |
| **Kadr** | Plan średni, lekko z boku, obiektyw 50 mm, średnia głębia ostrości. |
| **Światło** | Punkt zbiegu nici jest źródłem światła (orange, pink); nici violet i sky blue; krawędzie kart jasne. |
| **Paleta HEX** | `#0D0F17` · `#191B25` · `#7B5CFF` · `#3BA7FF` · `#FF8A5B` · `#F2528F` |
| **Materiały** | Szkło matowe (karty), światło w postaci cienkich, ostrych nici. |
| **Nastrój** | Porządek, związki, odkrycie. |
| **Proporcje** | 3:2 (1800 × 1200) · 16:9 |

**Prompt główny:**

```text
Several blank translucent frosted glass cards stacked loosely in depth on the left side of a
dark space. Thin threads of violet and sky blue light run from the cards and converge into a
single small warm point of orange and pink light on the right. The cards have bright thin
edges and no text. Deep navy-graphite darkness, 50mm lens, medium depth of field, calm and
orderly, premium 3d render.
```

**Prompt SDXL (krótki, runda 1 — źródło próbek):**

```text
stacks of translucent frosted glass cards floating in dark space, connected by thin threads
of soft violet and blue light, warm glow at the center, abstract 3d render, depth of field,
deep navy graphite darkness, soft aurora light apricot pink violet sky blue, frosted glass,
minimal, premium, calm, cinematic lighting, high detail
```

**Prompt negatywny:** przyrostek z [rozdz. 3.2](#32-przyrostek-negatywny) oraz
`network graph, nodes and edges diagram, constellation map, books, library shelves, tiles`.

| Generator | Parametry |
|---|---|
| Midjourney | `--ar 3:2 --style raw --stylize 120 --chaos 5 --seed 1107` |
| SDXL 1.0 | 1216 × 832 · 30 kroków · CFG 5,5 · DPM++ 2M Karras · seed 1107 |
| SDXL-Turbo | 512 × 512 · 4 kroki · guidance 0,0 · seed 1107 / 2214 |
| Flux.1 dev | 1216 × 832 · 28 kroków · guidance 3,5 · seed 1107 |
| DALL·E 3 | `1792x1024` · `hd` · `natural` |

**Wariant alternatywny 1 — wyszukiwanie:** jedna karta wysunięta z szeregu i oświetlona,
pozostałe w półmroku; pod komunikat „znajdź po znaczeniu”.

```text
A long row of blank frosted glass cards in dark space, one card pulled slightly forward and
lit by a warm orange and pink glow, the rest dim with violet edges, deep navy darkness,
minimal, premium 3d render.
```

**Wariant alternatywny 2 — warstwy:** karty ułożone poziomo jak warstwy osadu, światło
przenika z dołu.

```text
Thin horizontal sheets of frosted glass layered like strata in dark space, soft violet and
sky blue light rising through them from a warm orange source below, deep navy darkness,
minimal, cinematic.
```

**Kryteria akceptacji:** karty puste i rozpoznawalne jako karty; nici światła zbiegają się
w jednym punkcie; kompozycja ma wyraźną oś (od lewej ku prawej).

**Zakazy:** diagram węzłów i krawędzi w stylu grafu sieci; książki i półki; chaos kafli
bez osi (błąd próbki `wiedza-b.png`).

---

## 9. File Processing

| Pole | Ustalenie |
|---|---|
| **Cel i miejsce użycia** | Poziomy pas między sekcjami funkcji strony produktu: pliki przechodzą przez przestrzeń Nexusa i wychodzą uporządkowane. |
| **Kompozycja** | Szereg szklanych arkuszy przesuwających się od lewej ku prawej przez pierścień (łuk) światła; arkusze po lewej przygaszone i nieregularne, po prawej — jasne, równe. |
| **Kadr** | Panorama z boku, obiektyw 35 mm, ruch zaznaczony delikatnym rozmyciem po lewej. |
| **Światło** | Pierścień światła w pełnej Aurorze (orange → pink → violet → sky blue); arkusze przejmują barwę po przejściu przez pierścień. |
| **Paleta HEX** | `#0D0F17` · `#191B25` · `#FF8A5B` · `#F2528F` · `#7B5CFF` · `#3BA7FF` · `#F9FAFE` |
| **Materiały** | Szkło matowe (arkusze), światło (pierścień). |
| **Nastrój** | Płynność, przemiana, sprawczość. |
| **Proporcje** | 21:9 (2520 × 1080) · 16:9 |

**Prompt główny:**

```text
A row of thin frosted glass sheets moving from left to right through a softly glowing ring of
light in a dark space. The ring blends warm orange, pink, violet and sky blue. Sheets on the
left are dim, uneven and slightly blurred by motion; sheets on the right are bright, clean and
evenly aligned. Deep navy-graphite darkness, dark matte floor with faint reflections, 35mm,
wide panoramic composition, calm, premium 3d render.
```

**Prompt SDXL (krótki, runda 2 — źródło próbek):**

```text
dark navy background, a row of small translucent glass squares passing through a glowing
ring of warm orange, pink and violet light, minimal 3d render, cinematic, dark empty space
```

**Postać zalecona dla SDXL** (po wnioskach z [rozdz. 2.2](#22-wnioski-z-próbek-sdxl-turbo)):

```text
dark navy background, five thin frosted glass sheets standing in a row, a glowing ring of
warm orange pink and violet light in the middle, side view, minimal 3d render, cinematic
```

**Prompt negatywny:** przyrostek z [rozdz. 3.2](#32-przyrostek-negatywny) oraz
`tiles, squares, grid, mosaic, pixels, conveyor belt, factory, paper documents, folders icons`.

| Generator | Parametry |
|---|---|
| Midjourney | `--ar 21:9 --style raw --stylize 120 --chaos 8 --seed 1107` |
| SDXL 1.0 | 1536 × 640 · 30 kroków · CFG 5,5 · DPM++ 2M Karras · seed 1107 |
| SDXL-Turbo | 512 × 512 · 4 kroki · guidance 0,0 · seed 1107 / 2214 |
| Flux.1 dev | 1536 × 640 · 28 kroków · guidance 3,5 · seed 1107 |
| DALL·E 3 | `1792x1024` (kadrowanie do 21:9) · `hd` · `natural` |

**Wariant alternatywny 1 — z góry:** widok z góry na strumień arkuszy przechodzący przez
łuk; pod sekcję automatyzacji.

```text
Top-down view of frosted glass sheets flowing in a gentle curve through an arch of soft
aurora light, dim before the arch, bright after it, dark graphite floor, deep navy darkness,
minimal, premium 3d render.
```

**Wariant alternatywny 2 — jeden arkusz:** jeden arkusz w połowie drogi przez pierścień —
połowa matowa, połowa czysta i jasna.

```text
A single sheet of frosted glass halfway through a glowing ring of warm orange, pink, violet
and sky blue light, the part behind the ring dull and matte, the part in front clear and
bright, deep navy darkness, side view, minimal, cinematic.
```

**Kryteria akceptacji:** czytelny kierunek ruchu od lewej ku prawej; widoczna różnica
„przed” i „po”; pierścień zawiera wszystkie cztery barwy Aurory w stałej kolejności.

**Zakazy:** mozaika kwadratów i siatka pikseli (błąd próbek `pliki-a.png`, `pliki-b.png`);
taśmociąg i hala; ikony folderów i dokumentów.

---

## 10. Wspomnienia

| Pole | Ustalenie |
|---|---|
| **Cel i miejsce użycia** | Sekcja „Zdjęcia i wspomnienia” strony produktu, reklama w mediach społecznościowych, tło ekranu albumu. Obraz mówi: Twoje rodzinne zdjęcia wracają do życia i są bezpieczne. |
| **Kompozycja** | Kilka starych odbitek fotograficznych rozłożonych na ciemnym, drewnianym stole; jedna odbitka na pierwszym planie, jaśniejsza i odnowiona, pozostałe przygaszone. Ciepłe światło lampy spoza kadru. |
| **Kadr** | Plan bliski z góry pod kątem 45°, obiektyw 50 mm, mała głębia ostrości — ostra tylko odbitka odnowiona. |
| **Światło** | Ciepła lampa (warm orange) z lewej góry; chłodna, fioletowa poświata na krawędziach odbitek w cieniu. |
| **Paleta HEX** | `#0D0F17` · `#191B25` · `#FF8A5B` · `#F2528F` · `#7B5CFF` · `#F9FAFE` |
| **Materiały** | Papier fotograficzny z białym marginesem, lekko pozaginany; drewno ciemne, matowe; szkło (ramka albo lupa) opcjonalnie. |
| **Nastrój** | Czułość, nostalgia, spokój — bez smutku. |
| **Proporcje** | 4:5 (1080 × 1350) · 3:2 (1800 × 1200) |

**Prompt główny:**

```text
A few old printed family photographs with white borders scattered on a dark wooden table,
seen from above at 45 degrees. The photographs show seaside landscapes and houses, no
recognizable faces. One photograph in the foreground looks freshly restored, crisp and
bright; the others are faded and slightly curled. Warm orange lamp light from the upper
left, soft violet glow on the edges in shadow, deep navy-graphite darkness around, 50mm lens,
shallow depth of field, tender and nostalgic, calm, cinematic.
```

**Prompt SDXL (runda 3 — źródło próbek):**

```text
dark navy background, an old printed photograph of a seaside landscape lying on a dark wooden
table, warm orange lamp light, soft violet glow at the edges, nostalgic, calm, minimal,
cinematic
```

**Prompt negatywny:** przyrostek z [rozdz. 3.2](#32-przyrostek-negatywny) oraz
`portrait, faces, people, wedding, funeral, sepia filter, instagram frame, polaroid logo, scratches everywhere`.

| Generator | Parametry |
|---|---|
| Midjourney | `--ar 4:5 --style raw --stylize 100 --seed 1107` |
| SDXL 1.0 | 896 × 1152 · 30 kroków · CFG 5,5 · DPM++ 2M Karras · seed 1107 |
| SDXL-Turbo | 512 × 512 · 4 kroki · guidance 0,0 · seed 1107 / 2214 |
| Flux.1 dev | 896 × 1152 · 28 kroków · guidance 3,5 · seed 1107 |
| DALL·E 3 | `1024x1792` (kadrowanie do 4:5) · `hd` · `natural` |

**Wariant alternatywny 1 — przed i po:** jedna odbitka przecięta linią światła — połowa
wyblakła i porysowana, połowa odnowiona.

```text
A single old photograph of a seaside house on a dark table, a thin line of soft violet light
crossing it, the left half faded and scratched, the right half restored with clear warm
colors, deep navy darkness, macro, calm, cinematic.
```

**Wariant alternatywny 2 — album:** otwarty album ze zdjęciami przy lampie, kubek herbaty
na brzegu kadru.

```text
An open photo album on a dark wooden table at night, warm orange lamp light on the pages,
a cup of tea at the edge of the frame, photographs of landscapes without faces, soft violet
shadows, deep navy darkness, cozy, calm, cinematic.
```

**Kryteria akceptacji:** odbitki rozpoznawalne jako stare zdjęcia; żadnych rozpoznawalnych
twarzy; jedna odbitka wyraźnie jaśniejsza (odnowiona); ciepło lampy dominuje nad chłodem.

**Zakazy:** portrety wygenerowane jako „prawdziwa rodzina”; filtr sepii na całym kadrze;
motywy żałoby (znicze, klepsydry); ramki i logotypy serwisów fotograficznych.

---

## 11. Twórczość

| Pole | Ustalenie |
|---|---|
| **Cel i miejsce użycia** | Sekcja „Twórz z Nexusem” strony produktu (ilustracje z opisu, kartki, bajki); tło ekranu twórczości w aplikacji. Obraz mówi: pomysł użytkownika staje się rzeczą. |
| **Kompozycja** | Jeden arkusz papieru na ciemnym blacie; na arkuszu świecący rysunek akwarelą — mały, przyjazny smok; obok ołówek. Rysunek jest jedynym źródłem światła. |
| **Kadr** | Widok z góry, obiektyw 50 mm, arkusz zajmuje 50–60 % kadru, lekko skośnie. |
| **Światło** | Rysunek świeci od środka: warm orange i pink w sercu, violet na obrzeżach; otoczenie ciemne. |
| **Paleta HEX** | `#0D0F17` · `#191B25` · `#FF8A5B` · `#F2528F` · `#7B5CFF` · `#3BA7FF` · `#F9FAFE` |
| **Materiały** | Papier akwarelowy o widocznej fakturze, grafit ołówka, matowy blat. |
| **Nastrój** | Radość tworzenia, ciekawość, ciepło. |
| **Proporcje** | 1:1 (1080 × 1080) · 3:2 |

**Prompt główny:**

```text
Top view of a single sheet of textured watercolor paper lying slightly diagonal on a dark matte
desk. On the paper, a small friendly dragon painted in watercolor glows softly from within,
warm orange and pink at its heart, violet and sky blue at the edges of the paint. A pencil
lies next to the sheet. The drawing is the only light source; deep navy-graphite darkness
around. 50mm lens, joyful and warm, minimal, cinematic.
```

**Prompt SDXL (runda 3 — źródło próbek):**

```text
dark navy background, top view of a single sheet of paper with a glowing watercolor drawing
of a small friendly dragon, warm orange, pink and violet light, minimal, cinematic
```

**Prompt negatywny:** przyrostek z [rozdz. 3.2](#32-przyrostek-negatywny) oraz
`scary dragon, fire, monster, anime style, cartoon characters, cluttered desk, many sheets`.

| Generator | Parametry |
|---|---|
| Midjourney | `--ar 1:1 --style raw --stylize 180 --seed 1107` |
| SDXL 1.0 | 1024 × 1024 · 30 kroków · CFG 6 · DPM++ 2M Karras · seed 1107 |
| SDXL-Turbo | 512 × 512 · 4 kroki · guidance 0,0 · seed 1107 / 2214 |
| Flux.1 dev | 1024 × 1024 · 28 kroków · guidance 3,5 · seed 1107 |
| DALL·E 3 | `1024x1024` · `hd` · `natural` |

**Wariant alternatywny 1 — kartka urodzinowa:** złożona kartka stojąca na stole, na froncie
świecący balon albo tort narysowany akwarelą.

```text
A folded greeting card standing on a dark table, on its front a softly glowing watercolor
drawing of a birthday cake with one candle, warm orange and pink light, violet shadows,
deep navy darkness, minimal, cinematic.
```

**Wariant alternatywny 2 — z opisu do obrazu:** pusty arkusz po lewej, ten sam arkusz
z gotowym rysunkiem po prawej, między nimi smuga światła Aurory.

```text
Two sheets of paper side by side on a dark desk, the left one blank, the right one with a
glowing watercolor drawing of a small lighthouse, a soft ribbon of warm orange, pink and
violet light flowing from left to right, deep navy darkness, top view, minimal.
```

**Kryteria akceptacji:** rysunek wygląda na wykonany ręcznie (akwarela, ołówek), nie jak
render; postać przyjazna; jedno źródło światła; brak tekstu na arkuszu.

**Zakazy:** groźne stwory i ogień; styl kreskówek znanych wytwórni; podpis, napis
„Happy Birthday” i inne teksty wygenerowane w obrazie; bałagan na biurku.

---

## 12. Podróże i plany

| Pole | Ustalenie |
|---|---|
| **Cel i miejsce użycia** | Sekcja „Plany i codzienność” strony produktu (plan wycieczki, plan dnia, przepis, lista zakupów); grafiki sezonowe (wakacje, ferie). |
| **Kompozycja** | Rozłożona papierowa mapa na ciemnym stole nocą; jeden mały, ciepły punkt światła oznacza cel; obok kubek i notes. Linia trasy zaznaczona cienką nicią światła. |
| **Kadr** | Plan średni z góry pod kątem 60°, obiektyw 35 mm, głębia ostrości średnia. |
| **Światło** | Punkt celu (warm orange) i nić trasy (violet → sky blue); otoczenie w półmroku. |
| **Paleta HEX** | `#0D0F17` · `#191B25` · `#292C37` · `#FF8A5B` · `#7B5CFF` · `#3BA7FF` |
| **Materiały** | Papier mapy z zagięciami, ceramika kubka, matowe drewno. |
| **Nastrój** | Ciekawość, wyczekiwanie, spokój przed wyjazdem. |
| **Proporcje** | 16:9 · 4:5 |

**Prompt główny:**

```text
An unfolded paper map on a dark wooden table at night, seen from above at 60 degrees.
A single small warm orange point of light glows on the map, marking a destination; a thin
thread of violet and sky blue light traces a winding route towards it. A ceramic mug and a
small notebook at the edge of the frame. The map has no readable names. Deep navy-graphite
darkness, 35mm lens, curious and calm, anticipation before a trip, cinematic.
```

**Prompt SDXL (runda 3 — źródło próbek):**

```text
dark navy background, an open paper map on a dark table at night, one small warm orange
glowing light marking a place on the map, soft violet and blue ambient light, minimal, cinematic
```

**Prompt negatywny:** przyrostek z [rozdz. 3.2](#32-przyrostek-negatywny) oraz
`readable place names, country borders of real countries, GPS app interface, smartphone, pins, red markers`.

| Generator | Parametry |
|---|---|
| Midjourney | `--ar 16:9 --style raw --stylize 120 --seed 1107` |
| SDXL 1.0 | 1344 × 768 · 30 kroków · CFG 5,5 · DPM++ 2M Karras · seed 1107 |
| SDXL-Turbo | 512 × 512 · 4 kroki · guidance 0,0 · seed 1107 / 2214 |
| Flux.1 dev | 1344 × 768 · 28 kroków · guidance 3,5 · seed 1107 |
| DALL·E 3 | `1792x1024` · `hd` · `natural` |

**Wariant alternatywny 1 — plan dnia:** notes z ręcznie rysowaną osią dnia, nad nim łuk
światła od świtu (orange) do zmierzchu (sky blue).

```text
An open paper notebook on a dark table with a hand-drawn timeline of the day, above it a
soft arc of light going from warm orange on the left to sky blue on the right like the path
of the sun, deep navy darkness, top view, minimal, calm.
```

**Wariant alternatywny 2 — kuchnia wieczorem:** deska z ziołami i miska w ciepłym świetle
okapu; pod sekcję przepisów.

```text
A wooden cutting board with fresh herbs and a ceramic bowl on a dark kitchen counter in the
evening, warm orange light from above, soft violet shadows, deep navy darkness, calm,
minimal, cinematic, no people.
```

**Kryteria akceptacji:** mapa bez czytelnych nazw i granic prawdziwych państw; jeden punkt
celu; trasa jako cienka nić światła; nastrój spokojny, bez stylistyki folderu turystycznego.

**Zakazy:** interfejsy map z telefonu; czerwone pinezki; zabytki rozpoznawalne jako
konkretne miejsce (chyba że dla kampanii lokalnej); walizki i samoloty jako klisze.

---

## 13. Wieczór i rozrywka

| Pole | Ustalenie |
|---|---|
| **Cel i miejsce użycia** | Sekcja „Wieczorem” strony produktu (bajka na dobranoc czytana na głos, zagadki, muzyka, porządkowanie zdjęć przy herbacie); tapeta ekranu w godzinach wieczornych. |
| **Kompozycja** | Otwarta książka dla dzieci na kołdrze; nad stronami unosi się mała, ciepła kula światła — głos, który czyta. Reszta pokoju w półmroku. |
| **Kadr** | Plan bliski z poziomu łóżka, obiektyw 50 mm, bardzo mała głębia ostrości. |
| **Światło** | Kula nad książką (warm orange, pink) jako jedyne źródło; cienie violet i sky blue. |
| **Paleta HEX** | `#0D0F17` · `#191B25` · `#FF8A5B` · `#F2528F` · `#7B5CFF` · `#3BA7FF` |
| **Materiały** | Papier książki, miękka tkanina kołdry, światło. |
| **Nastrój** | Przytulność, bezpieczeństwo, cisza przed snem. |
| **Proporcje** | 4:5 · 9:16 (tapeta telefonu) · 16:9 |

**Prompt główny:**

```text
An open children's picture book resting on a soft blanket in a dark bedroom at night. A small
warm sphere of light floats just above the pages, glowing orange and pink at its core with a
violet rim, gently lighting the paper. The illustrations in the book are soft and blurred,
with no readable text. Violet and sky blue shadows, deep navy-graphite darkness, 50mm lens,
very shallow depth of field, cozy, safe, quiet, cinematic.
```

**Prompt SDXL (runda 3 — źródło próbek):**

```text
dark navy bedroom at night, an open children's book on a bed, a small warm glowing sphere of
light floating above the pages, soft violet and blue shadows, cozy, calm, cinematic
```

**Prompt negatywny:** przyrostek z [rozdz. 3.2](#32-przyrostek-negatywny) oraz
`child, person, face, sleeping kid, toys brand, tablet, smartphone screen, readable text, scary shadows`.

| Generator | Parametry |
|---|---|
| Midjourney | `--ar 4:5 --style raw --stylize 150 --seed 1107` |
| SDXL 1.0 | 896 × 1152 · 30 kroków · CFG 5,5 · DPM++ 2M Karras · seed 1107 |
| SDXL-Turbo | 512 × 512 · 4 kroki · guidance 0,0 · seed 1107 / 2214 |
| Flux.1 dev | 896 × 1152 · 28 kroków · guidance 3,5 · seed 1107 |
| DALL·E 3 | `1024x1792` · `hd` · `natural` |

**Wariant alternatywny 1 — salon:** kanapa, koc i kubek herbaty, na stoliku kula światła
nad stosem odbitek; wieczorne porządkowanie zdjęć.

```text
A cozy living room at night, a blanket on a sofa and a cup of tea on a low table, a small
warm glowing sphere of light hovering above a stack of printed photographs, violet shadows,
deep navy darkness, calm, cinematic, no people.
```

**Wariant alternatywny 2 — zagadki:** trzy kartki z rysunkami-zagadkami ułożone w wachlarz,
jedna odwrócona, nad nią świecący znak zapytania ze światła.

```text
Three small paper cards fanned out on a dark table, one card face down, above it a soft
glowing question mark made of warm orange and violet light, deep navy darkness, playful,
minimal, cinematic.
```

**Kryteria akceptacji:** brak postaci (dzieci nie pokazuje się w obrazach generowanych);
kula światła czytelna jako źródło; ciepło dominuje; obraz ciemny, ale nie ponury.

**Zakazy:** dzieci i twarze; ekrany urządzeń; motywy strachu (cienie potworów, burza);
marki zabawek i postaci licencjonowane.

---

## 14. Próbki SDXL-Turbo — pochodzenie i ocena

Próbki wygenerowano 2026-09-19 w trzech rundach modelem SDXL-Turbo (`/danaco/programy/modele/sdxl-turbo`,
float32, `variant="fp16"`), 512 × 512 px, 4 kroki, guidance 0,0, ziarna 1107 (A) i
2214 (B). Pierwsza runda używała przyrostka „deep navy graphite darkness, soft aurora light
apricot pink violet sky blue, frosted glass, minimal, premium, calm, cinematic lighting, high
detail”; druga runda (OCR, Dashboard, File Processing) i trzecia (Wspomnienia, Twórczość, Podróże
i plany, Wieczór i rozrywka) — promptów skróconych bez przyrostka.
Próbki pierwszej rundy dla tych trzech promptów odrzucono i nie weszły do repozytorium
(OCR — faktura papieru bez promienia; Dashboard — ściana z szyb; File Processing — siatka kafli).

Przebieg generowania i oceny, od promptu do pliku w repozytorium:

```
prompt SDXL ──► SDXL-Turbo 512 px ──► ocena na planszy ──┬──► użyteczna ──► Real-ESRGAN ×4 ──► WebP 2048 px
   (rozdz. 4–13)    (A: 1107, B: 2214)                   ├──► warunkowo ──► kadrowanie, przyciemnienie w obróbce
                                                         └──► odrzucona ──► wniosek do rozdz. 2.2
```

| Plik | Prompt | Runda | Ocena | Uzasadnienie |
|---|---|---|---|---|
| `hero-a.png` | Hero | 1 | **użyteczna** | szklany łuk, ciepłe wnętrze, spokój; brak kuli światła, tło za jasne — do przyciemnienia |
| `hero-a-2048.webp` | Hero | 1 | **użyteczna** | powiększenie Real-ESRGAN ×4 próbki `hero-a.png` (2048 × 2048) |
| `hero-b.png` | Hero | 1 | warunkowo | łuk świeci jak neon, dominuje orange; wyłącznie wariant sezonowy |
| `dashboard-a.png` | Dashboard | 2 | odrzucona | gablota zamiast paneli |
| `dashboard-b.png` | Dashboard | 2 | warunkowo | trzy panele w głębi zgodnie z promptem; tło zbyt fioletowe |
| `ocr-a.png` | OCR | 2 | odrzucona | promień bez kartki |
| `ocr-b.png` | OCR | 2 | odrzucona | podwójna linia i szum; najwyżej faktura |
| `asystent-a.png` | AI Assistant | 1 | **użyteczna** | szklana kula z odbiciem — najbliżej stylu marki |
| `asystent-b.png` | AI Assistant | 1 | odrzucona | róża w kuli (słowo „rose”) |
| `wiedza-a.png` | Knowledge Base | 1 | warunkowo | szklane karty, dobre światło; brak nici, zbyt gęsto |
| `wiedza-b.png` | Knowledge Base | 1 | odrzucona | chaos kafli |
| `pliki-a.png` | File Processing | 2 | odrzucona | mozaika pikseli — motyw zakazany |
| `pliki-b.png` | File Processing | 2 | odrzucona | jak wariant A |
| `wspomnienia-a.png` | Wspomnienia | 3 | odrzucona | lampa na stole, brak odbitki |
| `wspomnienia-b.png` | Wspomnienia | 3 | warunkowo | lampa, stół i morze w tle — nastrój trafny, zdjęcia brak; tło pod tekst |
| `tworczosc-a.png` | Twórczość | 3 | odrzucona | smok groźny, styl naklejki |
| `tworczosc-b.png` | Twórczość | 3 | warunkowo | akwarela na papierze, czytelna jako „ilustracja z opisu”; jasny arkusz dominuje |
| `podroze-a.png` | Podróże i plany | 3 | odrzucona | mapa świata z rozpoznawalnymi kontynentami |
| `podroze-b.png` | Podróże i plany | 3 | warunkowo | świecące trasy na mapie; pseudonapisy do rozmycia |
| `wieczor-a.png` | Wieczór i rozrywka | 3 | warunkowo | przytulna sypialnia z książką, bez kuli światła |
| `wieczor-b.png` | Wieczór i rozrywka | 3 | **użyteczna** | książka na łóżku i świecąca kula nad stronami — zgodna z promptem |

**Bilans:** 21 plików — 4 użyteczne (w tym jedno powiększenie), 7 warunkowo, 10 odrzuconych.
W rundzie 3 (tematy z życia, prompty krótkie według rozdz. 2.2) model radził sobie lepiej
ze scenami wnętrz (sypialnia, stół z lampą) niż z przedmiotem na pierwszym planie
(odbitka zdjęcia) — tę samą słabość co w OCR widać przy wspomnieniach.
SDXL-Turbo na procesorze nadaje się do szkiców nastroju i tła o jednym obiekcie (łuk,
kula). Obrazy z relacją dwóch obiektów (OCR, File Processing) trzeba wykonać w
Midjourney albo we Flux według promptów głównych, albo zmontować z osobnych obrazów.

Plansza zbiorcza: [plansza-porownawcza.png](../branding/ilustracje/sdxl/plansza-porownawcza.png).

---

## 15. Kryteria odbioru

Obraz atmosferyczny przyjmuje się do użycia, gdy spełnia wszystkie warunki:

| Warunek | Sposób sprawdzenia |
|---|---|
| Kryteria akceptacji rozdziału danego promptu spełnione | przegląd obrazu wobec listy rozdziału |
| Brak motywów z przyrostka negatywnego (rozdz. 3.2) | przegląd w powiększeniu 100 % |
| Ciemność co najmniej 60 % kadru, tło w zakresie `#0D0F17`–`#191B25` po obróbce | próbnik barw w edytorze, histogram |
| Tekst nałożony na obraz osiąga kontrast co najmniej 4,5:1 (7:1 dla nagłówka hero) | pomiar na najjaśniejszym fragmencie pod tekstem |
| Rozdzielczość docelowa osiągnięta bez widocznych artefaktów powiększenia | podgląd 100 % po Real-ESRGAN |
| Plik skompresowany (WebP albo AVIF) i opisany tekstem alternatywnym albo oznaczony jako ozdobny | `cwebp` / `avifenc`; przegląd kodu strony |
| Ziarno, generator i prompt zapisane przy pliku | wpis w tabeli rozdz. 14 albo w metadanych pliku (`exiftool`) |

---

*Koniec dokumentu. Prompty do generatorów obrazów — Specyfikacja docelowa, etap 1, 2026-09-19.*

---
*Danaco Nexus — Personal AI Workspace · etap 1 · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Kontakt: support@danaco-group.pl*
