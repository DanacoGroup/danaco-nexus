// Znacznik „są nowe zmiany”: czy od ostatniego zajrzenia wyszło nowe wydanie.
//
// Ustawienia mają sekcję „Co nowego” z wykazem zmian bieżącego wydania, ale nic o niej
// nie mówiło — produkt zmienia się po kilkanaście razy dziennie, a jedyną informacją
// o nowym wydaniu było to, że coś wygląda inaczej. Kropka przy „Więcej” (tam, gdzie
// mieszkają Ustawienia) prowadzi do wykazu i gaśnie, gdy ktoś go otworzy.

import { useEffect, useState } from "react";
import { apiRequest } from "./api";

const KLUCZ = "nexus:nowosci-wydanie";

/** Ostatnie wydanie, którego wykaz zmian ktoś na tym urządzeniu oglądał. */
function ostatnieObejrzane(): string {
  try {
    return window.localStorage.getItem(KLUCZ) ?? "";
  } catch {
    // Tryb prywatny albo zablokowane dane witryny — kropka zapala się co wydanie i tyle.
    return "";
  }
}

/** Zapamiętuje, że wykaz zmian tego wydania został obejrzany. */
export function oznaczNowosciPrzeczytane(wydanie: string): void {
  if (!wydanie) return;
  try {
    window.localStorage.setItem(KLUCZ, wydanie);
  } catch {
    // Jak wyżej: brak pamięci nie może przerwać rysowania widoku.
  }
  window.dispatchEvent(new CustomEvent("nexus:nowosci-przeczytane"));
}

/** Czy jest nowe wydanie, którego wykazu zmian nikt tu jeszcze nie otwierał.
 *
 * Pytanie idzie raz na uruchomienie okna: wydanie zmienia się przy wdrożeniu, a nie
 * w trakcie pracy, więc odpytywanie w kółko dokładałoby ruchu bez żadnego zysku.
 * Hak woła powłoka jeden raz i podaje wynik obu odmianom paska modułów (bok na
 * komputerze, dół na telefonie) — obie są w drzewie, jedną chowa arkusz stylów.
 */
export function useNieprzeczytaneNowosci(): boolean {
  const [wydanie, setWydanie] = useState("");
  const [obejrzane, setObejrzane] = useState(ostatnieObejrzane);

  useEffect(() => {
    let zywy = true;
    void apiRequest<{ wydanie: string; pozycje: unknown[] }>("GET", "/api/nowosci")
      .then((dane) => {
        if (zywy && dane.pozycje.length) setWydanie(dane.wydanie);
      })
      .catch(() => undefined);
    const odswiez = () => setObejrzane(ostatnieObejrzane());
    window.addEventListener("nexus:nowosci-przeczytane", odswiez);
    return () => {
      zywy = false;
      window.removeEventListener("nexus:nowosci-przeczytane", odswiez);
    };
  }, []);

  return Boolean(wydanie) && wydanie !== obejrzane;
}
