// Pasek konta próbnego: jedyne miejsce, w którym aplikacja mówi, że praca toczy się
// na koncie tymczasowym. Gość ma pełne okno, więc bez tego paska nie miałby skąd
// wiedzieć, że rozmowy i pliki znikną wraz z kontem.

import { useEffect, useState } from "react";
import { platnosciApi } from "../platnosci/api";

export function PasekKontaProbnego({ onZaloz }: { onZaloz: () => void }) {
  const [saldo, setSaldo] = useState<number | null>(null);

  useEffect(() => {
    let aktualne = true;
    platnosciApi
      .kredyty()
      .then((stan) => {
        if (aktualne) setSaldo(stan.saldo);
      })
      .catch(() => undefined);
    return () => {
      aktualne = false;
    };
  }, []);

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line/60 bg-raised/70 px-4 py-2 text-sm">
      <span className="font-medium text-fg">Konto próbne</span>
      <span className="text-muted">
        Pracujesz w pełnej aplikacji. Rozmowy i pliki znikną razem z kontem próbnym.
      </span>
      {saldo !== null && (
        <span className="text-subtle tabular-nums">{saldo.toLocaleString("pl-PL")} kredytów</span>
      )}
      <button
        type="button"
        onClick={onZaloz}
        className="ml-auto rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-on-accent"
      >
        Załóż konto
      </button>
    </div>
  );
}
