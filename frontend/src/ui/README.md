# Biblioteka komponentów — `frontend/src/ui`

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Rodzaj** | Warstwa kliencka — biblioteka komponentów React |
| **Opis** | Komponenty i warstwa ruchu zbudowane wprost ze specyfikacji `ui-kit/COMPONENT_LIBRARY.md`, tokenów `design-tokens/dist/tokens.css` i wytycznych `motion/MOTION_GUIDELINES.md`. |
| **Wersja** | etap 1 |
| **Status** | Deweloperski |
| **Data** | 2026-09-20 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Biblioteka komponentów Danaco Nexus — wykaz, API, przykłady, podłączenie |
| **Klasa dokumentu** | Dokumentacja modułu |
| **Odbiorcy** | deweloper warstwy klienckiej · projektant |
| **Zakres** | Komponenty w `frontend/src/ui`, warstwa ruchu, arkusz `ruch.css` |
| **Poza zakresem** | Wartości wizualne (tokeny), reguły ogólne (system projektowy), ekrany aplikacji |
| **Dokumenty nadrzędne** | [Biblioteka komponentów](../../../ui-kit/COMPONENT_LIBRARY.md) · [System projektowy](../../../design-system/DESIGN_SYSTEM.md) |
| **Dokumenty powiązane** | [Tokeny projektowe](../../../design-tokens/README.md) · [Wytyczne ruchu](../../../motion/MOTION_GUIDELINES.md) |
| **Zasada nadrzędna** | Żadnej wartości wizualnej wpisanej wprost — kolor, odstęp, promień, czas i krzywa pochodzą z tokenu albo z klasy Tailwinda zdefiniowanej w `frontend/src/styles.css`. |

## Spis treści

1. [Co trzeba podłączyć](#1-co-trzeba-podłączyć)
2. [Zasady wspólne](#2-zasady-wspólne)
3. [Wykaz komponentów](#3-wykaz-komponentów)
4. [Przyciski i etykiety](#4-przyciski-i-etykiety)
5. [Pola formularzy](#5-pola-formularzy)
6. [Nakładki](#6-nakładki)
7. [Dane i stany](#7-dane-i-stany)
8. [Praca agenta i wyniki](#8-praca-agenta-i-wyniki)
9. [Paleta poleceń](#9-paleta-poleceń)
10. [Warstwa ruchu](#10-warstwa-ruchu)
11. [Odstępstwa od specyfikacji](#11-odstępstwa-od-specyfikacji)
12. [Kontrole](#12-kontrole)

---

## 1. Co trzeba podłączyć

Trzy rzeczy po stronie aplikacji — biblioteka sama ich nie wprowadza, bo leżą poza
katalogiem `frontend/src/ui`:

1. **Arkusz ruchu.** W `frontend/src/styles.css`, po `@import "./tokens.css";`, dopisz:

   ```css
   @import "./ui/ruch.css";
   ```

   Bez tego działają barwy, odstępy i układ, ale nie ma animacji wejścia, kaskady,
   szkieletu, paska nieokreślonego, oddechu karty agenta ani przejść okien.

2. **Dostawca powiadomień.** `ToastProvider` obejmuje aplikację (np. w `App.tsx`), inaczej
   `useToast()` rzuca wyjątek:

   ```tsx
   <ToastProvider>
     <App />
   </ToastProvider>
   ```

3. **Skrót palety poleceń.** `useCommandPaletteShortcut(() => setPaletaOtwarta(true))`
   w komponencie powłoki; sama `CommandPalette` jest sterowana z zewnątrz (`open`, `query`,
   `mode`, `items`).

Import: `import { Button, Dialog, useToast } from "./ui";`

## 2. Zasady wspólne

| Zasada | Realizacja |
|---|---|
| Wartości wizualne | wyłącznie `var(--token)` albo klasa Tailwinda z `styles.css` (`bg-raised`, `text-muted`, `border-line`, `shadow-floating`, `aurora-obrys`, `glow-ai`) |
| Motyw ciemny i jasny | przez role semantyczne; w kodzie nie ma gałęzi dla motywu |
| Fokus | globalny `:focus-visible` z `styles.css`; komponenty nie nadpisują pierścienia |
| Wyłączenie | `disabled` blokuje; `disabled` + `disabledReason` daje `aria-disabled` i dymek z powodem (element zostaje w kolejności tabulacji) |
| Ograniczony ruch | tokeny czasu i odległości plus `@media (prefers-reduced-motion: reduce)` w `ruch.css`; `useReducedMotion` dla animacji sterowanych skryptem |
| Ikony | prop `icon` przyjmuje węzeł Reacta (`<CheckIcon />` albo dowolny rysunek), nie nazwę z manifestu |
| Etykiety | polskie, czasownikowe; nazwy komponentów i propsów angielskie |

Typy wspólne (`types.ts`): `ControlSize`, `Tone`, `Shortcut`, `BaseProps`, `cx`,
`shortcutLabel`, `ariaKeyshortcuts`, `tokenMs`.

## 3. Wykaz komponentów

| Komponent | Plik | Rozdział ui-kit |
|---|---|---|
| `Button`, `IconButton` | `Button.tsx` | 2.1, 2.2 |
| `Input`, `SearchInput` | `Input.tsx` | 3.1, 3.3 |
| `Textarea` | `Textarea.tsx` | 3.2 |
| `Select` | `Select.tsx` | 3.4 |
| `Checkbox` | `Checkbox.tsx` | 3.5 |
| `Switch` | `Switch.tsx` | 3.7 |
| `Field` (oprawa pola) | `Field.tsx` | 3 — część wspólna |
| `Badge`, `Tag` | `Badge.tsx` | 9.1, 9.2 |
| `Card` | `Card.tsx` | 5 — część wspólna |
| `Dialog` | `Dialog.tsx` | 7.1 |
| `Sheet` | `Sheet.tsx` | — (panel wysuwany) |
| `Menu` | `Menu.tsx` | 7.2 |
| `Tooltip` | `Tooltip.tsx` | 7.4 |
| `Toast` (`ToastProvider`, `useToast`) | `Toast.tsx` | 8.1 |
| `Tabs` | `Tabs.tsx` | 9.4 |
| `Table` | `Table.tsx` | 6.1 |
| `Progress`, `ProgressRing`, `Spinner` | `Progress.tsx` | 9.5 |
| `Skeleton` | `Skeleton.tsx` | 9.6 |
| `GranicaBledu` | `GranicaBledu.tsx` | — (ostatnia siatka: zamiast pustej strony po wyjątku) |
| `EmptyState` | `EmptyState.tsx` | 9.7 |
| `Kbd` | `Kbd.tsx` | 9.8 |
| `CommandPalette` | `CommandPalette.tsx` | 10.3 |
| `AgentStatus` | `AgentStatus.tsx` | 12.1 |
| `BeforeAfterCompare` | `BeforeAfterCompare.tsx` | 12.3 |
| `useReveal`, `useReducedMotion`, `usePress`, `Stagger`, `PageTransition` | warstwa ruchu | motion 5, 11, 13, 14 |

## 4. Przyciski i etykiety

```tsx
<Button variant="primary" size="md" shortcut={["Ctrl", "⏎"]} onClick={utworz}>
  Utwórz projekt
</Button>

<Button variant="ai" iconStart={<SparkleIcon />} loading loadingLabel="Streszczam">
  Streść
</Button>

<Button variant="destructive" disabled disabledReason="Najpierw zaznacz pliki">
  Usuń 3 pliki
</Button>

<IconButton icon={<CheckIcon />} label="Pokaż panel" pressed={panelWidoczny} shortcut={["Ctrl", "B"]} />

<Tag label="OCR" icon={<SparkleIcon />} active onClick={przelacz} onRemove={usun} />
<Badge tone="success" icon={<SuccessIcon size={12} />}>Zindeksowano</Badge>
<Badge count={128} />
<Kbd keys={["Ctrl", "K"]} />
```

| `ButtonProps` | Typ | Domyślnie | Znaczenie |
|---|---|---|---|
| `variant` | `primary \| secondary \| ghost \| destructive \| ai` | `secondary` | `ai` tylko dla pracy asystenta |
| `size` | `ControlSize` | `md` | wysokość z `--control-*` |
| `iconStart`, `iconEnd` | `ReactNode` | — | rysunek ikony |
| `shortcut` | `Shortcut` | — | `Kbd` przy etykiecie + `aria-keyshortcuts` |
| `loading`, `loadingLabel` | `boolean`, `string` | `false` | `aria-busy`, wskaźnik zamiast ikony |
| `disabled`, `disabledReason` | `boolean`, `string` | `false` | z powodem: `aria-disabled` i dymek |
| `fullWidth`, `type` | `boolean`, `button \| submit` | `false`, `button` | — |

`IconButtonProps` = `ButtonProps` bez `children`/ikon plus `icon`, `label` (wymagane),
`pressed`, `tooltipSide`, `hideTooltip`.

## 5. Pola formularzy

```tsx
<Input label="Adres e-mail" type="email" value={adres} onChange={setAdres}
       description="Służbowy" error={blad} clearable iconStart={<SearchIcon />} />

<Textarea label="Instrukcja dla asystenta" value={tresc} onChange={setTresc}
          maxLength={2000} onSubmit={zapisz} />

<Select label="Język OCR" value={jezyk} onChange={setJezyk}
        options={[{ value: "pol", label: "Polski" }, { value: "eng", label: "Angielski" }]}
        description="Wykrywany automatycznie, gdy puste." />

<Checkbox checked={stan} onChange={setStan} label="Zachowaj oryginał" />
<Switch checked={pamiec} onChange={zapiszPamiec} label="Pamięć między rozmowami"
        description="Zmiana działa od razu." />

<SearchInput label="Szukaj w plikach" value={fraza} onChange={setFraza}
             semantic searching={szuka} resultCount={12} />
```

Wspólne: etykieta nad polem, pomoc i błąd powiązane przez `aria-describedby`, błąd ustawia
`aria-invalid`. `Textarea` liczy znaki (ostrzeżenie od 90% limitu, błąd po przekroczeniu)
i zatwierdza `Ctrl Enter`. `Select` to combobox + listbox: `↓` otwiera, strzałki przenoszą,
litera skacze, `Enter` wybiera, `Esc` zamyka i wraca na wyzwalacz. `Switch` z `onChange`
zwracającym obietnicę pokazuje stan zapisywania (`aria-busy`).

## 6. Nakładki

```tsx
<Dialog open={otwarte} onOpenChange={setOtwarte} variant="destructive"
        title="Usunąć 3 pliki na stałe?" description="Tej zmiany nie da się cofnąć."
        confirmLabel="Usuń 3 pliki" confirmPhrase="usuń" onConfirm={usun} />

<Sheet open={panel} onOpenChange={setPanel} title="Szczegóły pliku" side="right">…</Sheet>

<Menu trigger={<IconButton icon={<SortIcon />} label="Więcej działań" />}
      label="Działania rozmowy"
      items={[
        { id: "rename", label: "Zmień nazwę", shortcut: ["F2"], onSelect: zmienNazwe },
        { type: "separator" },
        { id: "delete", label: "Usuń", destructive: true, onSelect: usun },
      ]} />

<Tooltip content="Załącz plik" shortcut={["Ctrl", "U"]}><IconButton … /></Tooltip>

const dymki = useToast();
dymki.show({ variant: "undo", title: "Usunięto rozmowę", actions: [{ label: "Cofnij", onSelect: cofnij }] });
```

`Dialog` i `Sheet` stoją na natywnym `<dialog>`: pułapka fokusu, `Esc` i zasłona pochodzą
od przeglądarki, bez biblioteki zewnętrznej. `confirm` i `destructive` mają rolę
`alertdialog`; `confirmPhrase` blokuje przycisk główny do wpisania słowa; `form` zatwierdza
`Ctrl Enter`, a `dirty` wyłącza zamknięcie kliknięciem w zasłonę. Fokus po otwarciu trafia
na element z atrybutem `data-ui-autofokus`.

`Toast`: warianty `success`, `error` (rola `alert`, zostaje do zamknięcia), `warning`,
`info`, `progress`, `undo`. Czas widoczności czytany z tokenów `--delay-toast`
i `--delay-toast-long`; wskazanie kursorem i fokus wstrzymują odliczanie.

## 7. Dane i stany

```tsx
<Tabs label="Typy plików" value={zakladka} onChange={setZakladka}
      items={[{ value: "wszystkie", label: "Wszystkie" }, { value: "dokumenty", label: "Dokumenty", count: 128 }]}>
  {tresc}
</Tabs>

<Table
  label="Pliki"
  rows={pliki}
  rowId={(plik) => plik.id}
  columns={[
    { key: "name", label: "Nazwa", sortable: true, render: (plik) => plik.name },
    { key: "size", label: "Rozmiar", numeric: true, sortable: true, render: (plik) => plik.sizeLabel },
  ]}
  sort={sortowanie}
  onSortChange={setSortowanie}
  selectedIds={zaznaczone}
  onSelectionChange={setZaznaczone}
  onOpen={otworz}
  empty={<EmptyState title="Brak plików" primaryAction={{ label: "Prześlij pliki", onSelect: przeslij }} />}
/>

<Progress value={0.62} label="Przesyłanie 3 plików" valueText="62%, pozostało około 6 sekund" />
<Progress tone="ai" valueText="Sprawdzam plik" />   {/* nieokreślony */}
<Skeleton lines={3} />
<EmptyState variant="no-results" title="Nic nie pasuje do „aneks 2025”"
            secondaryAction={{ label: "Wyczyść filtry", onSelect: wyczysc }}
            aiAction={{ label: "Zapytaj asystenta", onSelect: zapytaj }} />
```

`Table`: nagłówki sortowalne mają `aria-sort`, zaznaczenie zbiorcze w nagłówku przyjmuje
stan mieszany, `Spacja` zaznacza wiersz, `Enter` otwiera, `loading` rysuje szkielet
w układzie kolumn. Kolumny `numeric` idą do prawej i mają cyfry tabelaryczne.

## 8. Praca agenta i wyniki

```tsx
<AgentStatus
  run={{
    id: "praca-1",
    state: "running",
    startedAt: zadanie.startedAt,
    steps: [
      { id: "1", label: "Analizuję dokument", state: "done", durationMs: 1200 },
      { id: "2", label: "Wykonuję OCR…", state: "running", tool: "tesseract",
        detail: "Tesseract · język polski · 62%", progress: 0.62,
        log: [{ at: "14:35:21", text: "tesseract skan.png -l pol --dpi 600" }] },
      { id: "3", label: "Odczytuję NIP i kwotę brutto", state: "queued" },
    ],
  }}
  onStop={zatrzymaj}
  onRetryStep={ponow}
  onSkipStep={pomin}
/>

<BeforeAfterCompare beforeUrl={przed} afterUrl={po}
                    beforeAlt="Skan faktury przed poprawą"
                    afterAlt="Skan faktury po poprawie Real-ESRGAN 4×" />
```

`AgentStatus` ma rolę `status` (`alert` przy błędzie), obrys Aurora i poświatę wyłącznie
w trakcie pracy, zegar w cyfrach tabelarycznych, listę kroków jako `<ol>`, dziennik przy
kroku bieżącym i błędnym, przycisk „Zatrzymaj” ze skrótem `Esc` oraz zwijanie
(`aria-expanded` + `aria-controls`). Stan `awaiting-input` pokazuje pytanie agenta
z przyciskami decyzji (`onAnswer`).

`BeforeAfterCompare`: uchwyt jest suwakiem (`role="slider"`), strzałki przesuwają o 5%,
`Home`/`End` do krańców; `resultOnly` chowa uchwyt i pokazuje sam wynik.

## 9. Paleta poleceń

```tsx
useCommandPaletteShortcut(() => setPaleta(true));

<CommandPalette
  open={paleta} onOpenChange={setPaleta}
  mode={tryb} onModeChange={setTryb}
  query={zapytanie} onQueryChange={setZapytanie}
  semantic={poZnaczeniu} onSemanticChange={setPoZnaczeniu}
  items={wyniki}
  loading={szuka}
  onAskAssistant={(q) => wyslijDoAsystenta(q)}
/>
```

Wzorzec combobox + listbox z grupami i `aria-activedescendant`. `↑`/`↓` wybór, `Enter`
otwiera, `Ctrl Enter` przekazuje zapytanie asystentowi, `Tab` zmienia tryb, `Backspace`
w pustym polu wychodzi z trybu, `Esc` zamyka. Znaki `>`, `@`, `#`, `?` na początku
zapytania włączają tryby: polecenia, pliki, projekty, pomoc. Panel `preview` pozycji
pokazuje się od `lg`.

## 10. Warstwa ruchu

| Element | API | Zastosowanie |
|---|---|---|
| `useReducedMotion()` | `boolean` | jedno źródło preferencji dla animacji skryptowych |
| `useReveal({ index, threshold, once })` | `{ ref, visible, props }` | wejście przy przewijaniu z kaskadą |
| `usePress({ strong, disabled })` | `{ pressed, props }` | skala `--scale-press` pod naciskiem, także z klawiatury |
| `<Stagger>` | `as`, `children` | kaskada wejścia dzieci, do `--stagger-max` kroków |
| `opoznienieKaskady(index)` | `CSSProperties` | opóźnienie dla własnych list |
| `<PageTransition viewKey>` | `viewKey`, `children` | przejście między widokami, z View Transitions API gdy dostępne |

```tsx
function Wiersz({ index, children }) {
  const { ref, props } = useReveal({ index });
  return <li ref={ref} {...props}>{children}</li>;
}

<Stagger as="ul">{pozycje.map((p) => <li key={p.id}>{p.label}</li>)}</Stagger>

<PageTransition viewKey={widok}>{ekran}</PageTransition>
```

Klasy z `ruch.css` do użycia poza komponentami: `ui-przejscie`, `ui-nacisk`,
`ui-nacisk-mocny`, `ui-wejscie`, `ui-ujawnij`, `ui-widok`, `ui-wysuw`, `ui-dymek`,
`ui-powiadomienie`, `ui-szkielet`, `ui-pasek-nieokreslony`, `ui-oddech`, `ui-kontrolka`,
`ui-warstwa`, `ui-cel-dotyku`.

Przy `prefers-reduced-motion: reduce` znikają przesunięcia i skale, pętle (oddech, błysk
szkieletu, pasek nieokreślony) są wyłączone, a `useReveal` pokazuje treść od razu.

## 11. Odstępstwa od specyfikacji

| Odstępstwo | Powód |
|---|---|
| `icon` przyjmuje węzeł Reacta zamiast `IconName` z `ui-kit/ikony/manifest.json` | aplikacja nie ma jeszcze wczytanego arkusza symboli; zmiana na nazwy będzie podmianą typu, bez zmian w układzie komponentów |
| `Dialog`, `Sheet` i `CommandPalette` bez Radix UI | wymaganie zlecenia; zachowanie modalne daje natywny `<dialog>` |
| `Table` jest ogólna (`columns`, `rows`), nie `FileTable` | `FileTable` z rozdz. 6.1 powstaje jako złożenie `Table` z `Badge` i `Menu` po stronie widoku plików |
| `Sheet` nie ma jeszcze gestu przeciągnięcia palcem (motion, rozdz. 6.2) | wymaga sprężyny i obsługi wskaźnika; do etapu z widokiem telefonu |
| Brak `Composer`, `FileCard`, `ConversationCard`, `ProjectCard`, `NotificationCenter`, `RadioGroup`, `SegmentedControl`, `Avatar`, `DropZone`, `ToolResult` | poza minimum zlecenia; `Composer` i karty istnieją już w `frontend/src/components` i `modules` |

## 12. Kontrole

```bash
cd frontend
npx vitest run src/ui   # 34 testy: dostępność, klawiatura, stan komponentów
npx tsc --noEmit        # typy całego katalogu src
```
