// Klawisz Esc zatrzymuje pracującego agenta (DESIGN_SYSTEM, rozdz. 2 — „praca agenta
// jest jawna i przerywalna”). Gdy otwarte jest okno dialogowe albo arkusz, klawisz
// należy do niego i przebieg zostaje bez zmian.

import { useEffect, useRef } from "react";

/** Nasłuch klawisza Esc, aktywny tylko wtedy, gdy trwa bieg. */
export function useEscZatrzymaj(biegTrwa: boolean, zatrzymaj: () => void): void {
  const uchwyt = useRef(zatrzymaj);
  uchwyt.current = zatrzymaj;
  useEffect(() => {
    if (!biegTrwa) return;
    const onKey = (event: KeyboardEvent) => {
      if (!czyZatrzymac(event, document)) return;
      event.preventDefault();
      uchwyt.current();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [biegTrwa]);
}

/** Czy to zdarzenie ma zatrzymać bieg (funkcja czysta — do testu bez powłoki). */
export function czyZatrzymac(event: Pick<KeyboardEvent, "key" | "defaultPrevented">, dokument: Document): boolean {
  if (event.key !== "Escape" || event.defaultPrevented) return false;
  return dokument.querySelector('[role="dialog"], dialog[open]') === null;
}
