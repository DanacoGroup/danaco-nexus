// Pasek wykorzystania dostępu w wersji kieszonkowej — do menu konta.
//
// Stan dostępu był tylko w module Płatności: żeby sprawdzić, ile zostało, trzeba było
// wyjść z rozmowy. Tutaj ten sam pasek, bez liczb i bez historii, w rozmiarze, który
// mieści się pod nazwą konta.
//
// Ten plik celowo nie sięga do `platnosci/index.tsx`: panel boczny nie ma powodu wciągać
// całego modułu sprzedaży do swojej paczki.

import { useEffect, useState } from "react";
import { platnosciApi, type KredytyInfo } from "./api";

const BARWY: Record<KredytyInfo["stan"], string> = {
  w_porzadku: "bg-accent-fill",
  konczy_sie: "bg-warning",
  wyczerpany: "bg-danger",
};

const OPISY: Record<KredytyInfo["stan"], string> = {
  w_porzadku: "Dostęp w tym okresie",
  konczy_sie: "Dostęp dobiega końca",
  wyczerpany: "Dostęp wyczerpany",
};

export function PasekDostepu({ onOtworz }: { onOtworz?: () => void }) {
  const [stan, setStan] = useState<KredytyInfo | null>(null);

  useEffect(() => {
    let aktualne = true;
    platnosciApi
      .kredyty()
      .then((dane) => {
        if (aktualne) setStan(dane);
      })
      .catch(() => undefined);
    return () => {
      aktualne = false;
    };
  }, []);

  if (!stan) return null;
  const procent = Math.round(Math.min(1, Math.max(0, stan.zuzycie)) * 100);
  const tresc = (
    <>
      <span className="flex items-center justify-between gap-2 text-xs">
        <span className={stan.stan === "w_porzadku" ? "text-muted" : "text-warning"}>{OPISY[stan.stan]}</span>
        {onOtworz && <span className="text-subtle">Szczegóły</span>}
      </span>
      <span
        className="mt-1.5 block h-1.5 w-full overflow-hidden rounded-full bg-hover"
        role="meter"
        aria-valuenow={procent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Wykorzystanie dostępu"
      >
        <span className={`block h-full rounded-full ${BARWY[stan.stan]}`} style={{ width: `${procent}%` }} />
      </span>
    </>
  );

  if (!onOtworz) return <div className="px-3 py-2.5">{tresc}</div>;
  return (
    <button type="button" onClick={onOtworz} className="block w-full px-3 py-2.5 text-left transition-colors hover:bg-hover">
      {tresc}
    </button>
  );
}
