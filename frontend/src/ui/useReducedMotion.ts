// Odczyt preferencji „ograniczony ruch”. Jedno źródło dla animacji sterowanych skryptem.

import { useEffect, useState } from "react";

const ZAPYTANIE = "(prefers-reduced-motion: reduce)";

function odczytaj(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia(ZAPYTANIE).matches;
}

export function useReducedMotion(): boolean {
  const [ograniczony, setOgraniczony] = useState(odczytaj);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const lista = window.matchMedia(ZAPYTANIE);
    const zmiana = (zdarzenie: MediaQueryListEvent) => setOgraniczony(zdarzenie.matches);
    setOgraniczony(lista.matches);
    lista.addEventListener("change", zmiana);
    return () => lista.removeEventListener("change", zmiana);
  }, []);

  return ograniczony;
}
