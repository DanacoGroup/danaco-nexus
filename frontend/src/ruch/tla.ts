// Leniwe wczytanie teł z pakietu `landing/tla`; moduły rejestrują się w `window.DanacoTla`.
// API i opcje: landing/tla/README.md, rozdz. 3.

import type { CSSProperties } from "react";

export type NazwaTla = "aurora" | "luk" | "konstelacja" | "noc" | "swit" | "ziarno";

export interface UchwytTla {
  element: HTMLElement;
  obsluguje?: boolean;
  zatrzymaj(): void;
  wznow(): void;
  zniszcz(): void;
}

export interface ModulTla {
  mount(element: HTMLElement, opcje?: Record<string, unknown>): UchwytTla;
  wersja: string;
}

declare global {
  interface Window {
    DanacoTla?: Partial<Record<NazwaTla, ModulTla>>;
  }
}

/** Tła wydane do katalogu publicznego przez `zasoby.py`. */
const WYDANE: NazwaTla[] = ["aurora", "luk", "swit", "ziarno"];

/** Tła wydane i rysowane w WebGL — tylko te podlegają bramkom z rozdz. 9 specyfikacji. */
export type NazwaTlaWebGL = Extract<NazwaTla, "aurora" | "luk">;

const WEBGL: NazwaTla[] = ["aurora", "luk", "konstelacja", "noc"];

/** Tła ze zrzutem zastępczym; świt i ziarno rysuje sam CSS. */
const ZE_ZRZUTEM: NazwaTla[] = ["aurora", "luk", "konstelacja", "noc"];

function pasuje(zapytanie: string): boolean {
  return window.matchMedia(zapytanie).matches;
}

/**
 * Warunki pełnych teł WebGL z `landing/LANDING_PAGE_SPEC.md`, rozdz. 9: ekran od progu
 * `--breakpoint-lg`, wskaźnik precyzyjny, motyw ciemny, bez `saveData` i bez ograniczonego
 * ruchu. Poza nimi zostaje klatka zastępcza w CSS — to jest budżet TBT telefonu z rozdz. 11.
 */
export function pelneTlo(nazwa: NazwaTla): boolean {
  if (!WEBGL.includes(nazwa)) return true;
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  const polaczenie = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
  if (polaczenie?.saveData === true) return false;
  if (!document.documentElement.classList.contains("dark")) return false;
  const prog = getComputedStyle(document.documentElement).getPropertyValue("--breakpoint-lg").trim();
  if (!prog) return false;
  return (
    pasuje(`(min-width: ${prog})`) &&
    pasuje("(pointer: fine)") &&
    !pasuje("(prefers-reduced-motion: reduce)")
  );
}

const wczytane = new Map<NazwaTla, Promise<ModulTla | null>>();

function dolaczArkusz(adres: string): void {
  if (document.querySelector(`link[href="${adres}"]`)) return;
  const wezel = document.createElement("link");
  wezel.rel = "stylesheet";
  wezel.href = adres;
  document.head.appendChild(wezel);
}

function dolaczSkrypt(adres: string): Promise<void> {
  return new Promise((gotowe, blad) => {
    const istniejacy = document.querySelector<HTMLScriptElement>(`script[src="${adres}"]`);
    if (istniejacy) {
      gotowe();
      return;
    }
    const wezel = document.createElement("script");
    wezel.src = adres;
    wezel.onload = () => gotowe();
    wezel.onerror = () => blad(new Error(adres));
    document.head.appendChild(wezel);
  });
}

/** Zwraca moduł tła albo `null`. Klasa `dn-js` mówi arkuszom pakietu, że skrypt działa. */
export function wczytajTlo(nazwa: NazwaTla): Promise<ModulTla | null> {
  const zapamietane = wczytane.get(nazwa);
  if (zapamietane) return zapamietane;
  const zadanie = (async () => {
    if (typeof document === "undefined" || !WYDANE.includes(nazwa)) return null;
    document.documentElement.classList.add("dn-js");
    dolaczArkusz(`/tla/${nazwa}/${nazwa}.css`);
    try {
      await dolaczSkrypt(`/tla/${nazwa}/${nazwa}.js`);
    } catch {
      return null;
    }
    return window.DanacoTla?.[nazwa] ?? null;
  })();
  wczytane.set(nazwa, zadanie);
  return zadanie;
}

/** Klatka zastępcza pod płótnem WebGL; wariant pionowy dla proporcji telefonu. */
export function klatkaZastepcza(nazwa: NazwaTla): CSSProperties {
  if (!ZE_ZRZUTEM.includes(nazwa)) return {};
  const zbior = (rozmiar: string) =>
    `image-set(url("/tla/${nazwa}/${nazwa}-${rozmiar}.avif") type("image/avif"), url("/tla/${nazwa}/${nazwa}-${rozmiar}.webp") type("image/webp"))`;
  return { "--klatka": zbior("1920x1080"), "--klatka-pion": zbior("1170x2532") } as CSSProperties;
}
