// Ekran uruchomienia aplikacji: nagranie z pakietu motion/start zamiast pustego tła.
//
// Zanim powłoka wie, czy ktoś jest zalogowany, okno stało puste — zwłaszcza w wersji
// zainstalowanej wyglądało to na zawieszenie. Pakiet ruchu ma na tę chwilę gotowe
// ujęcia (osobne dla komputera i telefonu, osobne dla motywu jasnego i ciemnego).

import { NagranieStartu, ograniczonyRuch, type IdStartu } from "../ruch";

/** Ujęcie dobrane do urządzenia i motywu; krótkie warianty dla wejścia bez oczekiwania. */
export function nazwaUruchomienia(krotkie = false): IdStartu {
  const telefon = typeof window !== "undefined" && window.matchMedia?.("(max-width: 767px)").matches;
  const jasny = typeof document !== "undefined" && !document.documentElement.classList.contains("dark");
  if (krotkie) return telefon ? "uruchomienie-krotkie-telefon-ciemny" : "uruchomienie-krotkie-komputer-ciemny";
  if (telefon) return jasny ? "uruchomienie-telefon-jasny" : "uruchomienie-telefon-ciemny";
  return jasny ? "uruchomienie-komputer-jasny" : "uruchomienie-komputer-ciemny";
}

export function EkranStartowy({ krotkie = false }: { krotkie?: boolean }) {
  if (ograniczonyRuch()) return <div className="h-full bg-app" />;
  return (
    <div className="flex h-full items-center justify-center overflow-hidden bg-app">
      <NagranieStartu nazwa={nazwaUruchomienia(krotkie)} petla className="size-full object-cover" />
    </div>
  );
}
