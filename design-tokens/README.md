# Danaco Nexus — Tokeny projektowe

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Rodzaj** | Personal AI Workspace |
| **Opis** | Osobisty agent AI do pracy i rozrywki, działający na serwerze Danaco i otwierany jako aplikacja PWA we własnym oknie: czat z modelem Claude, analiza dokumentów, OCR, poprawa skanów, obróbka zdjęć, wyszukiwanie wiedzy, chmura plików. |
| **Producent** | Danaco Holding Group Sp. z o.o. |
| **Twórca** | Dariusz Naharnowicz |
| **Wersja** | etap 1 — projekt |
| **Status** | Deweloperski |
| **Data** | 2026-09-19 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Tokeny projektowe — architektura, konwencja nazw, budowanie, mapowanie na Tailwind CSS 4 |
| **Klasa dokumentu** | Specyfikacja docelowa |
| **Odbiorcy** | projektant · deweloper warstwy klienckiej |
| **Przeznaczenie** | Wyjaśnia, skąd pochodzi każda wartość wizualna Danaco Nexus i jak dostarczyć ją do aplikacji bez przepisywania wartości. |
| **Zakres** | Pliki `*.json` w tym katalogu, generator `build.py`, wynik `dist/tokens.css`, konwencja nazw, zasady dodawania tokenów, mapowanie na `@theme` Tailwind CSS 4 |
| **Poza zakresem** | Znaczenie i zasady użycia tokenów w interfejsie — [System projektowy](../design-system/DESIGN_SYSTEM.md); zużycie tokenów w komponentach — [Biblioteka komponentów](../ui-kit/COMPONENT_LIBRARY.md) |
| **Dokument nadrzędny** | [System projektowy](../design-system/DESIGN_SYSTEM.md) |
| **Dokumenty powiązane** | [Biblioteka komponentów](../ui-kit/COMPONENT_LIBRARY.md) |
| **Źródła normatywne** | `design-tokens/*.json` (format W3C Design Tokens) · `frontend/src/styles.css` (nazwy ról semantycznych) |
| **Zasada nadrzędna** | Wartość wizualna istnieje wyłącznie jako token w pliku JSON; `dist/tokens.css` i każda inna postać są wynikiem generatora, nie źródłem. |

## Spis treści

1. [Czym są tokeny Danaco Nexus](#1-czym-są-tokeny-danaco-nexus)
2. [Architektura trzech warstw](#2-architektura-trzech-warstw)
   - [2.1 Warstwa bazowa](#21-warstwa-bazowa)
   - [2.2 Warstwa marki](#22-warstwa-marki)
   - [2.3 Warstwa semantyczna](#23-warstwa-semantyczna)
3. [Pliki źródłowe](#3-pliki-źródłowe)
4. [Konwencja nazw](#4-konwencja-nazw)
5. [Budowanie](#5-budowanie)
6. [Mapowanie na Tailwind CSS 4](#6-mapowanie-na-tailwind-css-4)
7. [Zmiany wprowadzone w etapie 1](#7-zmiany-wprowadzone-w-etapie-1)
8. [Dodawanie i zmiana tokenu](#8-dodawanie-i-zmiana-tokenu)
9. [Kryteria odbioru](#9-kryteria-odbioru)

---

## 1. Czym są tokeny Danaco Nexus

Token to nazwana wartość projektowa: kolor, rozmiar, czas, cień, promień. Wszystkie
wartości wizualne aplikacji, strony produktu, makiet i materiałów marki pochodzą z tokenów.
Wartość wpisana wprost w komponencie (`#754DF7`, `margin: 13px`) jest usterką.

```
design-tokens/*.json  ──python3 build.py──▶  dist/tokens.css  ──@import──▶  frontend / makiety
   (źródło prawdy)                            (wynik, bez edycji)           (@theme Tailwind 4)
```

---

## 2. Architektura trzech warstw

```
┌───────────────────────────────────────────────────────────────────────────┐
│ WARSTWA 3 · SEMANTYCZNA   --app --fg --accent --danger …   (.dark / :root) │  ← komponenty
├───────────────────────────────────────────────────────────────────────────┤
│ WARSTWA 2 · MARKA         --color-brand-aurora, -iris, -sky, -apricot …     │  ← znak, AI
├───────────────────────────────────────────────────────────────────────────┤
│ WARSTWA 1 · BAZOWA        --color-neutral-50…950, --space-4, --radius-md …  │  ← tylko warstwy 2–3
└───────────────────────────────────────────────────────────────────────────┘
```

Zależności biegną wyłącznie w dół. Komponent odwołuje się do warstwy semantycznej
(kolory) albo do skal bez znaczenia kolorystycznego (odstępy, promienie, typografia,
czasy). Komponent nie odwołuje się do skali koloru bazowego. Wyjątki są nazwane
w [Systemie projektowym](../design-system/DESIGN_SYSTEM.md) (dymek podpowiedzi,
awatar użytkownika, uchwyt porównania przed i po).

### 2.1 Warstwa bazowa

| Grupa | Plik | Przykład zmiennej | Zmienia się z motywem |
|---|---|---|---|
| Skale kolorów 50–950 (OKLCH → sRGB) | `colors.json` | `--color-primary-600` | nie |
| Rodziny, rozmiary, grubości, interlinia, światło, cyfry | `typography.json` | `--font-size-md` | nie |
| Odstępy w siatce 4 px i role odstępów | `spacing.json` | `--space-4`, `--space-role-inset-card` | nie |
| Promienie | `radius.json` | `--radius-lg` | nie |
| Czasy, krzywe, dystanse, sprężyna, opóźnienia | `animation.json` | `--duration-base`, `--delay-tooltip` | nie |
| Ikony: rozmiary, obrys, siatka | `icons.json` | `--icon-size-md` | nie |
| Punkty łamania, szerokości, kontrolki, warstwy | `layout.json` | `--breakpoint-md`, `--control-md`, `--z-dialog` | nie |
| Krycie, rozmycie tła, obrysy | `effects.json` | `--opacity-disabled`, `--blur-md` | nie |

### 2.2 Warstwa marki

Kolory znaku (`apricot`, `rose`, `iris`, `sky`, `ink`, `night`, `cream`) i trzy gradienty.
Gradienty należą do znaku i do elementów pracy AI; nie są kolorem tekstu ani dużej
powierzchni.

| Token | Postać | Zastosowanie |
|---|---|---|
| `--color-brand-aurora` | 135°, Apricot 0% → Rose 38% → Iris 72% → Sky 100% | znak, ikona, ekran startowy, awatar asystenta, przycisk wysyłki aktywny |
| `--color-brand-aurora-cool` | 135°, Iris → Sky | wskaźniki pracy agenta, obrys pracującego `AgentStatus`, pasek postępu AI |
| `--color-brand-aurora-cool-fill` | 135°, `primary.600` → `info.700` | wypełnienie przycisku AI z białym tekstem (≥ 5,05:1 na całej długości) |

### 2.3 Warstwa semantyczna

Role kolorów noszą nazwy zgodne z `frontend/src/styles.css`. Motyw jasny siedzi
w `:root`, ciemny w `.dark` (klasa na `<html>`). Cienie mają osobne wartości dla motywów
i trafiają do tych samych bloków (`--shadow-soft`, `--shadow-medium`, `--shadow-hard`,
`--shadow-floating`, `--shadow-glass`, `--shadow-glow-ai`). Pełna tabela ról z wartościami
i kontrastami: [System projektowy, rozdz. 4](../design-system/DESIGN_SYSTEM.md#4-kolory).

```
app side raised hover bubble code glass scrim                    ← powierzchnie
line line-strong line-control focus-ring                         ← obrysy
fg muted subtle                                                  ← tekst
accent accent-hover accent-fill accent-fill-hover accent-soft on-accent
success warning danger info  (+ -soft)  danger-fill danger-fill-hover
```

---

## 3. Pliki źródłowe

| Plik | Grupy najwyższego poziomu | Liczba tokenów |
|---|---|---|
| `colors.json` | `color.neutral`, `color.primary`, `color.success`, `color.warning`, `color.error`, `color.info`, `color.brand`, `color.white`, `color.dark`, `color.light` | 66 bazowych, 12 marki, 1 biel, 2 × 31 ról |
| `typography.json` | `font.family`, `font.weight`, `font.size`, `font.line-height`, `font.letter-spacing`, `font.numeric`, `typography` | 3 + 4 + 12 + 4 + 5 + 1 + 13 stylów |
| `spacing.json` | `space`, `space-role` | 15 + 10 |
| `radius.json` | `radius` | 8 |
| `shadows.json` | `shadow.dark`, `shadow.light` | 2 × 6 |
| `animation.json` | `duration`, `easing`, `distance`, `spring`, `delay`, `scale`, `stagger`, `gesture` | 7 + 5 + 3 + 1 + 7 + 5 + 2 + 2 |
| `icons.json` | `icon` | 14 |
| `layout.json` | `breakpoint`, `layout`, `control`, `z` | 5 + 15 + 6 + 11 |
| `effects.json` | `opacity`, `blur`, `border` | 5 + 3 + 5 |
| `build.py` | — | generator |
| `dist/tokens.css` | — | wynik, 339 deklaracji |

Skale kolorów niosą wartość OKLCH w polu `$extensions.pl.danaco.oklch`. Wartość w `$value`
jest przeliczeniem do sRGB z dopasowaniem nasycenia do gamy — to ją czyta przeglądarka.

```json
"600": {
  "$type": "color",
  "$value": "#754DF7",
  "$extensions": { "pl.danaco.oklch": "oklch(0.566 0.238 286.9)" }
}
```

---

## 4. Konwencja nazw

| Reguła | Tak | Nie |
|---|---|---|
| kebab-case, ścieżka JSON sklejona myślnikiem | `color.brand.aurora-cool` → `--color-brand-aurora-cool` | `--colorBrandAuroraCool` |
| rola, nie wygląd | `--danger`, `--line-control` | `--red`, `--gray-border` |
| role semantyczne bez przedrostka (zgodność z `styles.css`) | `--accent-soft` | `--color-accent-soft` w warstwie 3 |
| stan jako przyrostek roli | `--accent-fill-hover`, `--danger-fill-hover` | `--hover-accent-fill` |
| tło stanu jako `-soft` | `--success-soft` | `--success-bg`, `--success-light` |
| skale liczbowe jak w Tailwind | `--space-4` = 16 px, `--space-0-5` = 2 px | `--space-16px`, `--spacing-md` |
| jedno pojęcie, jedna nazwa | `--line` | `--border` obok `--line` |

Style tekstu wychodzą jako skrót `font` i osobny tracking:

```css
.dialog__tytul {
  font: var(--text-style-h4);
  letter-spacing: var(--text-style-h4-tracking);
}
```

---

## 5. Budowanie

```bash
python3 design-tokens/build.py
# /danaco/projekty/danaco-nexus/design-tokens/dist/tokens.css (…)
```

Generator nie ma zależności poza biblioteką standardową Pythona 3. Rozwiązuje odwołania
`{color.neutral.950}` do `var(--color-neutral-950)`, składa gradienty (135°), cienie
wielowarstwowe, style tekstu, a typ `object` (sprężyna) rozkłada na osobne zmienne
(`--spring-default-stiffness`, `--spring-default-damping`, `--spring-default-mass`).

| Wejście (`$type`) | Wyjście CSS |
|---|---|
| `color` | wartość HEX albo `var(--…)` |
| `dimension`, `duration`, `number`, `string`, `fontWeight` | wartość bez zmian |
| `fontFamily` | lista z cudzysłowami przy nazwach ze spacją |
| `cubicBezier` | `cubic-bezier(…)` |
| `shadow` | lista warstw, `inset`, gdy wskazano |
| `gradient` | `linear-gradient(135deg, …)` |
| `typography` | skrót `font` + `--text-style-*-tracking` |
| `object` | jedna zmienna na pole: `--{ścieżka}-{pole}` |

Po każdej zmianie JSON: zbuduj, uruchom kontrolę kontrastu opisaną
w [Systemie projektowym, rozdz. 4.4](../design-system/DESIGN_SYSTEM.md#44-tabela-kontrastów),
przerenderuj makiety `ui-kit/podglad/*.html`.

---

## 6. Mapowanie na Tailwind CSS 4

Tailwind 4 czyta zmienne z bloku `@theme`. Aplikacja już używa `@theme inline` z rolami
semantycznymi. Docelowo `frontend/src/styles.css` importuje `tokens.css` i zastępuje
własne bloki `:root` i `.dark` — wartości przestają być wpisane w arkuszu aplikacji,
a nazwy klas (`bg-app`, `text-muted`, `border-line`) pozostają bez zmian.

```css
@import "tailwindcss";
@import "../../design-tokens/dist/tokens.css";   /* :root = jasny, .dark = ciemny */
@plugin "@tailwindcss/typography";

@custom-variant dark (&:where(.dark, .dark *));

@theme inline {
  /* role semantyczne — nazwy klas bez zmian względem obecnego styles.css */
  --color-app: var(--app);
  --color-side: var(--side);
  --color-raised: var(--raised);
  --color-hover: var(--hover);
  --color-bubble: var(--bubble);
  --color-line: var(--line);
  --color-line-strong: var(--line-strong);
  --color-line-control: var(--line-control);        /* nowe */
  --color-fg: var(--fg);
  --color-muted: var(--muted);
  --color-subtle: var(--subtle);                    /* nowe w styles.css */
  --color-accent: var(--accent);
  --color-accent-hover: var(--accent-hover);
  --color-accent-fill: var(--accent-fill);
  --color-accent-fill-hover: var(--accent-fill-hover);
  --color-accent-soft: var(--accent-soft);
  --color-on-accent: var(--on-accent);
  --color-success: var(--success);
  --color-success-soft: var(--success-soft);
  --color-warning: var(--warning);
  --color-warning-soft: var(--warning-soft);
  --color-danger: var(--danger);
  --color-danger-soft: var(--danger-soft);
  --color-danger-fill: var(--danger-fill);
  --color-danger-fill-hover: var(--danger-fill-hover);
  --color-info: var(--info);
  --color-info-soft: var(--info-soft);
  --color-code: var(--code);
  --color-glass: var(--glass);
  --color-scrim: var(--scrim);
  --color-focus-ring: var(--focus-ring);

  /* typografia */
  --font-sans: var(--font-family-ui);
  --font-heading: var(--font-family-heading);
  --font-mono: var(--font-family-code);

  /* promienie: rounded-md = 10 px, rounded-xl = 20 px */
  --radius-xs: 4px;  --radius-sm: 6px;  --radius-md: 10px;
  --radius-lg: 14px; --radius-xl: 20px; --radius-2xl: 28px;

  /* cienie zależne od motywu */
  --shadow-soft: var(--shadow-soft);
  --shadow-floating: var(--shadow-floating);
  --shadow-glow-ai: var(--shadow-glow-ai);

  /* czasy i krzywe */
  --ease-standard: var(--easing-standard);
  --ease-enter: var(--easing-enter);
  --ease-exit: var(--easing-exit);
}
```

Uwagi do mapowania:

| Zagadnienie | Rozstrzygnięcie |
|---|---|
| Nazwy `--breakpoint-*`, `--blur-*` | pokrywają się z przestrzeniami nazw Tailwind 4; wartości z `tokens.css` są wtedy od razu progami `md:` i klasami `backdrop-blur-md` |
| `@media` nie czyta `var()` | Tailwind 4 rozwija progi z `@theme` w czasie budowy; w czystym CSS progi pobiera się z tabeli w `layout.json`, nie wpisuje z pamięci |
| Promienie w `@theme` jako liczby | `@theme inline` z `var()` działa dla kolorów; dla `--radius-*` Tailwind tworzy klasy także z `var()`, ale liczby wpisane wyżej ułatwiają podgląd w edytorze — muszą być równe `radius.json` |
| Odstępy | Tailwind 4 liczy `p-4` jako `calc(var(--spacing) * 4)`; przy `--spacing: 4px` skala `space.*` pokrywa się z klasami Tailwind jeden do jednego |
| Rozmiary tekstu | `text-[15px]` w obecnym kodzie zastępuje `--text-base: var(--font-size-base)` w `@theme` |
| Cienie zależne od motywu | `--shadow-*` w `.dark` nadpisuje wartość z `:root`, klasa `shadow-floating` działa w obu motywach |

---

## 7. Zmiany wprowadzone w etapie 1

Inne zespoły pracują na nazwach tokenów; nazwy nie zmieniły się. Zmieniły się wartości
poniższych ról oraz doszły nowe tokeny.

**Zmiany wartości istniejących tokenów:**

| Motyw | Rola | Było | Jest | Powód |
|---|---|---|---|---|
| ciemny | `raised` | `neutral.800` | `neutral.900` | 800 równał się `hover`, `line` i `bubble`; linia podziału i wskazanie kursorem w menu i oknie były niewidoczne |
| ciemny | `muted` | `neutral.400` | `neutral.300` | przesunięcie hierarchii tekstu, aby `subtle` spełniał 4,5:1 |
| ciemny | `subtle` | `neutral.500` | `neutral.400` | 4,07:1 na `side`, 3,30:1 na starym `raised` |
| ciemny | `accent-fill-hover` | `primary.500` | `primary.700` | biel na `primary.500` 3,55:1 |
| ciemny | `accent-soft` | `primary.950` | `#7B5CFF29` (Iris 16%) | pełne nasycenie dawało ciężki fiolet zaznaczonych wierszy |
| jasny | `muted` | `neutral.600` | `neutral.700` | przesunięcie hierarchii tekstu |
| jasny | `subtle` | `neutral.500` | `neutral.600` | 3,77–4,22:1 |
| jasny | `accent` | `primary.600` | `primary.700` | 4,29:1 na nowym `accent-soft`, 3,93:1 na `hover` |
| jasny | `accent-hover` | `primary.700` | `primary.800` | następstwo zmiany `accent` |
| jasny | `accent-soft` | `primary.50` | `primary.100` | `primary.50` nieodróżnialny od `app` |
| jasny | `info` | `info.600` | `info.700` | 4,34:1 na `app`, 4,23:1 na `info-soft` |
| oba | `easing.emphasized` | `[0.2, 0, 0, 1.1]` (przebieg 0,65%) | `[0.2, 0, 0, 1.25]` (przebieg 3,3%) | zgłoszenie zespołu „Ruch”: przebieg był niewidoczny; ta sama rodzina co `standard`, więc start ruchu bez zmian |
| oba | opisy `duration.base`, `duration.slow`, `easing.enter`, `easing.emphasized` | wejście wiadomości = `slow` + `emphasized` | wejście wiadomości = `base` + `enter`; `emphasized` — znak, dymek powiadomienia, elementy AI | rozstrzygnięcie integracji: ruch nie opóźnia czytania |

**Nowe tokeny:**

| Grupa | Tokeny |
|---|---|
| Role semantyczne | `line-control`, `glass`, `danger-fill-hover` |
| Marka | `color.brand.aurora-cool-fill` |
| Typografia | `font.numeric.tabular` |
| Układ (`layout.json`) | `breakpoint.*`, `layout.*`, `control.*` (28/32/36/40/44 i `touch-target`), `z.*` |
| Efekty (`effects.json`) | `opacity.*`, `blur.*`, `border.width.*`, `border.style.drop` |
| Ruch — skala, kaskada, gest (`animation.json`) | `scale.press` 0,97 · `scale.press-strong` 0,94 · `scale.enter` 0,98 · `scale.pop` 0,6 · `scale.dot-min` 0,85 · `stagger.step` 80 ms · `stagger.max` 4 · `gesture.drawer-distance` 0,4 · `gesture.drawer-velocity` 500 px/s |
| Sprężyna w CSS | `--spring-default-stiffness` 380 · `--spring-default-damping` 34 · `--spring-default-mass` 1 (generator emituje typ `object`) |
| Ikony | `icon.stroke.at-md` 1,67 px — obrys ikony 20 px przy skalowaniu wektorowym, jak w `ui-kit/ikony` |
| Marka | `color.brand.logotype-secondary-on-light` → `neutral.500`, `color.brand.logotype-secondary-on-dark` → `neutral.400` — człon „danaco” logotypu |
| Ruch (`animation.json`) | `delay.*` — opóźnienia i czasy życia: dymek podpowiedzi, szkielet, dymek powiadomienia, potwierdzenie „Skopiowano”, limit wczytywania |
| Rozszerzenia | `$extensions.pl.danaco.oklch` przy każdym stopniu skal |

---

## 8. Dodawanie i zmiana tokenu

```
potrzeba wartości
   │
   ├─ czy istnieje token o tej roli? ── tak ──▶ użyj go
   │
   ├─ czy istnieje stopień skali bliski o ≤ 2 px / jeden stopień? ── tak ──▶ użyj stopnia
   │
   └─ wartość powtarza się w ≥ 2 miejscach? ── nie ──▶ zostań przy istniejącym tokenie
                                            └─ tak ──▶ dopisz token w JSON,
                                                       zbuduj, sprawdź kontrast,
                                                       wpisz w rozdz. 7 tego pliku
```

| Czynność | Kto | Warunek |
|---|---|---|
| Dodanie tokenu | zespół „Design System” | nazwa roli, opis `$description`, wpis w tabeli zmian |
| Zmiana wartości | zespół „Design System” | ponowna kontrola kontrastu wszystkich par z udziałem tokenu, przerenderowane makiety |
| Zmiana nazwy | nie wykonuje się w etapie 1 | nazwy są kontraktem z warstwą kliencką |

---

## 9. Kryteria odbioru

| Kryterium | Sposób sprawdzenia |
|---|---|
| `dist/tokens.css` odpowiada JSON | `python3 design-tokens/build.py` nie zmienia pliku w repozytorium |
| Kontrast par semantycznych | tabela w [Systemie projektowym](../design-system/DESIGN_SYSTEM.md#44-tabela-kontrastów) bez pozycji „NIE” |
| Brak wartości wpisanych na sztywno w makietach | `grep -E '#[0-9A-Fa-f]{6}' ui-kit/podglad/podglad.css` zwraca zero wyników |
| Nazwy ról zgodne z `styles.css` | każda rola z `styles.css` istnieje w `color.dark` i `color.light` |

---

*Koniec dokumentu. Tokeny projektowe — Specyfikacja docelowa, etap 1, 2026-09-19.*

---
*Danaco Nexus — Personal AI Workspace · etap 1 · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Warunki korzystania: [DO DECYZJI OPERATORA] — repozytorium nie zawiera pliku licencji. Kontakt: support@danaco-group.pl*
