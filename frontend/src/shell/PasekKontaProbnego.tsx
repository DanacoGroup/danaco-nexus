// Pasek konta próbnego: jedyna informacja, że praca toczy się na koncie tymczasowym.

import { useEffect, useState } from "react";
import { platnosciApi, type KredytyInfo } from "../platnosci/api";

/** Zdanie o pozostałym dostępie — bez liczb, tak jak wszędzie indziej w produkcie. */
const OPISY: Record<KredytyInfo["stan"], string> = {
  w_porzadku: "",
  konczy_sie: "Dostęp konta próbnego dobiega końca.",
  wyczerpany: "Dostęp konta próbnego się wyczerpał.",
};

export function PasekKontaProbnego({ onZaloz }: { onZaloz: () => void }) {
  const [dostep, setDostep] = useState<KredytyInfo | null>(null);

  useEffect(() => {
    let aktualne = true;
    platnosciApi
      .kredyty()
      .then((stan) => {
        if (aktualne) setDostep(stan);
      })
      .catch(() => undefined);
    return () => {
      aktualne = false;
    };
  }, []);

  return (
    <div className="flex flex-nowrap items-center gap-x-3 gap-y-1 border-b border-line/60 bg-raised/70 px-4 py-2 text-sm sm:flex-wrap">
      <span className="shrink-0 font-medium whitespace-nowrap text-fg">Konto próbne</span>
      {/* Na telefonie pasek ma być jednym wierszem nad rozmową, a nie akapitem: pełne
        zdanie zajmowało tam trzy linijki i spychało pole wiadomości poza ekran. */}
      <span className="hidden text-muted sm:inline">
        Pracujesz w pełnej aplikacji. Rozmowy i pliki znikną razem z kontem próbnym.
      </span>
      {/* Krótsze zdanie na telefonie: poprzednie („dane znikną razem z kontem”) nie mieściło
        się w wierszu obok przycisku i kończyło wielokropkiem w połowie wyrazu. */}
      <span className="min-w-0 truncate text-muted sm:hidden">dane znikną po wyjściu</span>
      {dostep && OPISY[dostep.stan] && (
        <span className={dostep.stan === "wyczerpany" ? "text-danger" : "text-warning"}>
          {OPISY[dostep.stan]}
        </span>
      )}
      <button
        type="button"
        onClick={onZaloz}
        // „accent-fill”, nie „accent”: biel na akcencie tekstowym daje 2,48:1 (DESIGN_SYSTEM, 4.4).
        className="ml-auto shrink-0 rounded-lg bg-accent-fill px-3 py-1.5 text-sm font-medium text-on-accent transition-colors hover:bg-accent-fill-hover"
      >
        Załóż konto
      </button>
    </div>
  );
}
