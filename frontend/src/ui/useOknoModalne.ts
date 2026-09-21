// Klawiatura dla nakładek modalnych rysowanych bez elementu <dialog>: uwięzienie fokusu,
// Esc i powrót fokusu do wyzwalacza (WCAG 2.2: 2.1.2, 2.4.3).

import { useEffect, useRef, type RefObject } from "react";

const OGNISKOWALNE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "video[controls]",
  "audio[controls]",
  "[tabindex]:not([tabindex='-1'])",
].join(", ");

function dostepna(element: HTMLElement): boolean {
  if (element.hidden || element.closest("[aria-hidden='true'], [inert]")) return false;
  const styl = getComputedStyle(element);
  return styl.display !== "none" && styl.visibility !== "hidden";
}

function ogniskowalne(panel: HTMLElement): HTMLElement[] {
  return [...panel.querySelectorAll<HTMLElement>(OGNISKOWALNE)].filter(dostepna);
}

/** Trzyma fokus w nakładce, zamyka ją Esc i oddaje fokus wyzwalaczowi. Panel wymaga `tabIndex={-1}`. */
export function useOknoModalne(panel: RefObject<HTMLElement | null>, onZamknij: () => void): void {
  // Zamknięcie w referencji: w zależnościach efektu każde przerysowanie zabierałoby fokus.
  const zamknij = useRef(onZamknij);
  zamknij.current = onZamknij;

  useEffect(() => {
    const element = panel.current;
    if (!element) return;
    const poprzedni = document.activeElement as HTMLElement | null;
    const pierwszy = ogniskowalne(element)[0];
    (pierwszy ?? element).focus();

    const naKlawisz = (zdarzenie: KeyboardEvent) => {
      if (zdarzenie.key === "Escape") {
        zdarzenie.stopPropagation();
        zamknij.current();
        return;
      }
      if (zdarzenie.key !== "Tab") return;
      const lista = ogniskowalne(element);
      if (lista.length === 0) {
        zdarzenie.preventDefault();
        element.focus();
        return;
      }
      const skrajny = zdarzenie.shiftKey ? lista[0] : lista[lista.length - 1];
      const cel = zdarzenie.shiftKey ? lista[lista.length - 1] : lista[0];
      if (document.activeElement === skrajny || !element.contains(document.activeElement)) {
        zdarzenie.preventDefault();
        cel?.focus();
      }
    };

    document.addEventListener("keydown", naKlawisz, true);
    return () => {
      document.removeEventListener("keydown", naKlawisz, true);
      if (poprzedni?.isConnected) poprzedni.focus();
    };
  }, [panel]);
}
