// Odczyt preferencji „ograniczony ruch”. Jedno źródło dla animacji sterowanych skryptem.
//
// Liczy się jedno i drugie: ustawienie systemu (media query) oraz przełącznik na koncie.
// Wcześniej hook widział tylko media query, więc przełącznik w Ustawieniach wyciszał
// nagrania, ale nie przejścia widoków — ustawienie działało w połowie.

import { useEffect, useState } from "react";
import { ograniczonyRuch, przySmianiePreferencji, zastosujRuch } from "../preferencje";

const ZAPYTANIE = "(prefers-reduced-motion: reduce)";

export function useReducedMotion(): boolean {
  const [ograniczony, setOgraniczony] = useState(ograniczonyRuch);

  useEffect(() => {
    const odswiez = () => {
      const stan = ograniczonyRuch();
      setOgraniczony(stan);
      zastosujRuch(stan);
    };
    odswiez();
    const odepnij = przySmianiePreferencji(odswiez);
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return odepnij;
    const lista = window.matchMedia(ZAPYTANIE);
    lista.addEventListener("change", odswiez);
    return () => {
      odepnij();
      lista.removeEventListener("change", odswiez);
    };
  }, []);

  return ograniczony;
}
