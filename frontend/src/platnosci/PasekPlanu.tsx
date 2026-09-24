// Pasek nad rozmową, gdy dostęp w okresie dobiega końca albo się wyczerpał.
//
// Zmiana planu była wyłącznie w module Płatności: na telefonie pod „Więcej”, na komputerze
// w menu konta. Właściciel, który szukał wyższego planu z wnętrza aplikacji, nie znalazł
// go wcale. Pasek pojawia się dokładnie wtedy, gdy wyższy plan jest potrzebny, i prowadzi
// prosto do wyboru planu. Przy dostępie „w porządku” nie zajmuje miejsca.

import { useEffect, useState } from "react";
import { platnosciApi, type KredytyInfo } from "./api";

const OPISY: Record<Exclude<KredytyInfo["stan"], "w_porzadku">, string> = {
  konczy_sie: "Dostęp w tym okresie dobiega końca.",
  wyczerpany: "Dostęp w tym okresie się wyczerpał.",
};

export function PasekPlanu({ onZmienPlan }: { onZmienPlan: () => void }) {
  const [stan, setStan] = useState<KredytyInfo["stan"] | null>(null);

  useEffect(() => {
    let aktualne = true;
    platnosciApi
      .kredyty()
      .then((dane) => {
        if (aktualne) setStan(dane.stan);
      })
      .catch(() => undefined);
    return () => {
      aktualne = false;
    };
  }, []);

  if (!stan || stan === "w_porzadku") return null;
  return (
    <div className="flex flex-nowrap items-center gap-3 border-b border-line/60 bg-raised/70 px-4 py-2 text-sm">
      <span className={`min-w-0 truncate ${stan === "wyczerpany" ? "text-danger" : "text-warning"}`}>{OPISY[stan]}</span>
      <button
        type="button"
        onClick={onZmienPlan}
        className="ml-auto shrink-0 rounded-lg bg-accent-fill px-3 py-1.5 text-sm font-medium text-on-accent transition-colors hover:bg-accent-fill-hover"
      >
        Zmień plan
      </button>
    </div>
  );
}
