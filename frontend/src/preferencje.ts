// Preferencje konta: ustawienia, które jadą za użytkownikiem, a nie za przeglądarką.
//
// Motyw i głos siedziały dotąd wyłącznie w `localStorage`. Po zalogowaniu na telefonie
// albo po wyczyszczeniu danych witryny wszystko wracało do stanu fabrycznego, a rzeczy,
// które dotyczą pracy (czym wysyła się wiadomość, od czego zaczyna się dzień), nie miały
// gdzie zamieszkać. Źródłem prawdy jest teraz konto (`/api/konto/preferencje`).
//
// Kopia w `localStorage` zostaje, bo część miejsc potrzebuje odpowiedzi natychmiast,
// jeszcze przed pierwszym żądaniem: okno wysyła wiadomość Enterem, zanim serwer zdąży
// odpowiedzieć, a motyw musi stać, zanim pokaże się pierwsza klatka.

import { apiRequest } from "./api";

export interface Preferencje {
  motyw: "system" | "dark" | "light";
  ograniczony_ruch: boolean;
  wysylka: "enter" | "ctrl-enter";
  modul_startowy: string;
  glos: string;
}

export const DOMYSLNE: Preferencje = {
  motyw: "dark",
  ograniczony_ruch: false,
  wysylka: "enter",
  modul_startowy: "chat",
  glos: "",
};

const KLUCZ = "nexus:preferencje";
const ZDARZENIE = "nexus:preferencje-zmiana";

let pamiec: Preferencje | null = null;

function zOdczytu(): Preferencje {
  try {
    const zapisane = window.localStorage.getItem(KLUCZ);
    if (!zapisane) return { ...DOMYSLNE };
    return { ...DOMYSLNE, ...(JSON.parse(zapisane) as Partial<Preferencje>) };
  } catch {
    return { ...DOMYSLNE };
  }
}

/** Preferencje bez czekania na serwer: ostatni znany stan albo wartości domyślne. */
export function preferencje(): Preferencje {
  if (!pamiec) pamiec = zOdczytu();
  return pamiec;
}

function zapamietaj(nowe: Preferencje): Preferencje {
  pamiec = nowe;
  try {
    window.localStorage.setItem(KLUCZ, JSON.stringify(nowe));
  } catch {
    // Tryb prywatny albo zablokowane dane witryny — zostaje pamięć procesu.
  }
  window.dispatchEvent(new CustomEvent(ZDARZENIE, { detail: nowe }));
  return nowe;
}

/** Pobiera preferencje konta i zapisuje kopię lokalną. */
export async function wczytajPreferencje(): Promise<Preferencje> {
  const dane = await apiRequest<Partial<Preferencje>>("GET", "/api/konto/preferencje");
  return zapamietaj({ ...DOMYSLNE, ...dane });
}

/** Zapisuje zmienione pola na koncie; zwraca pełny, zaktualizowany zestaw. */
export async function zapiszPreferencje(zmiany: Partial<Preferencje>): Promise<Preferencje> {
  // Kopia lokalna idzie od razu: przełącznik ma zadziałać pod palcem, a nie po odpowiedzi.
  zapamietaj({ ...preferencje(), ...zmiany });
  const dane = await apiRequest<Partial<Preferencje>>("PUT", "/api/konto/preferencje", zmiany);
  return zapamietaj({ ...DOMYSLNE, ...dane });
}

/** Nasłuch zmian preferencji w tym oknie (zwraca funkcję odpinającą). */
export function przySmianiePreferencji(uchwyt: (dane: Preferencje) => void): () => void {
  const sluchacz = (zdarzenie: Event) => uchwyt((zdarzenie as CustomEvent<Preferencje>).detail);
  window.addEventListener(ZDARZENIE, sluchacz);
  return () => window.removeEventListener(ZDARZENIE, sluchacz);
}

/** Czy ruch ma być ograniczony: ustawienie systemu albo własne ustawienie konta.

 Ustawienia systemu nigdy nie łamiemy. Własny przełącznik („Ustawienia → Wygląd i ruch”)
 pozwala wyciszyć animacje komuś, kto systemu zmieniać nie chce albo nie może.
 */
export function ograniczonyRuch(): boolean {
  if (typeof window === "undefined") return false;
  if (preferencje().ograniczony_ruch) return true;
  if (typeof window.matchMedia !== "function") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Przenosi ustawienie na korzeń dokumentu, żeby widziały je też animacje w CSS.

 Bez tego przełącznik wyciszał wyłącznie animacje sterowane skryptem, a kaskady,
 przejścia widoków i ruch znaku szły dalej — ustawienie, które działa w połowie, jest
 gorsze niż jego brak.
 */
export function zastosujRuch(ograniczony = ograniczonyRuch()): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.ruch = ograniczony ? "ograniczony" : "pelny";
}
