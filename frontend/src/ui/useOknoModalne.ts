// Obsługa klawiatury dla nakładek modalnych rysowanych bez elementu <dialog>.
//
// Okna z ui-kitu stoją na natywnym <dialog>, więc uwięzienie fokusu, Esc i zasłonę daje
// przeglądarka. Nakładki zbudowane z <div role="dialog" aria-modal="true"> nie mają nic
// z tego: fokus zostaje pod zasłoną, tabulacja wychodzi na stronę w tle, a po zamknięciu
// nie wraca tam, skąd przyszła. Ten hook domyka te trzy braki (WCAG 2.2: 2.1.2, 2.4.3).

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

/** Czy kontrolka nadaje się na cel fokusu — bez miar pikselowych, więc też poza przeglądarką. */
function dostepna(element: HTMLElement): boolean {
  if (element.hidden || element.closest("[aria-hidden='true'], [inert]")) return false;
  const styl = getComputedStyle(element);
  return styl.display !== "none" && styl.visibility !== "hidden";
}

function ogniskowalne(panel: HTMLElement): HTMLElement[] {
  return [...panel.querySelectorAll<HTMLElement>(OGNISKOWALNE)].filter(dostepna);
}

/**
 * Trzyma fokus w nakładce, zamyka ją klawiszem Esc i oddaje fokus elementowi,
 * z którego nakładkę otwarto.
 *
 * @param panel Węzeł nakładki; musi przyjmować fokus (atrybut `tabIndex={-1}`).
 * @param onZamknij Zamknięcie nakładki — wywoływane po Esc.
 */
export function useOknoModalne(panel: RefObject<HTMLElement | null>, onZamknij: () => void): void {
  // Uchwyt w referencji: gdyby zamknięcie weszło do zależności efektu, każde przerysowanie
  // nakładki (np. miernik głośności w rozmowie głosowej) zabierałoby fokus na jej początek.
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
