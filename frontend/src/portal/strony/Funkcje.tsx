// Funkcje: pełny wykaz możliwości pogrupowany według obszaru pracy.

import { okruszki, usePozycjonowanie } from "../seo";
import { FUNKCJONALNOSCI } from "../tresc";
import { sciezka } from "../trasy";
import { NaglowekStrony, OdsylaczPrzycisk } from "../ui";

const OPIS =
  "Wszystko, co Nexus robi po zalogowaniu — w podziale na obszary pracy. Zadanie zlecasz jednym zdaniem, narzędzia agent dobiera sam.";

export function Funkcje() {
  usePozycjonowanie({
    tytul: "Funkcje",
    opis: OPIS,
    sciezka: sciezka("funkcje"),
    dane: okruszki([
      { nazwa: "Portal", sciezka: sciezka("glowna") },
      { nazwa: "Funkcje", sciezka: sciezka("funkcje") },
    ]),
  });

  const grupy = [...new Set(FUNKCJONALNOSCI.map((funkcja) => funkcja.grupa))];
  return (
    <>
      <NaglowekStrony tytul="Co Nexus załatwi za Ciebie" opis={OPIS} />
      {grupy.map((grupa, indeks) => (
        // Identyfikator z indeksu: nazwy grup bywają wielowyrazowe, a spacja w `aria-labelledby`
        // rozdziela listę identyfikatorów i sekcja straciłaby nazwę dostępną.
        <section key={grupa} aria-labelledby={`grupa-${indeks}`} className="mt-10">
          <h2 id={`grupa-${indeks}`} className="font-heading text-xl font-semibold text-fg">
            {grupa}
          </h2>
          <ul className="mt-4 grid gap-4 sm:grid-cols-2">
            {FUNKCJONALNOSCI.filter((funkcja) => funkcja.grupa === grupa).map((funkcja) => (
              <li key={funkcja.nazwa} className="rounded-xl border border-line bg-raised p-4">
                <h3 className="font-heading text-base font-semibold text-fg">{funkcja.nazwa}</h3>
                <p className="mt-1.5 text-sm text-muted">{funkcja.opis}</p>
              </li>
            ))}
          </ul>
        </section>
      ))}
      <div className="mt-10 flex flex-wrap gap-3">
        <OdsylaczPrzycisk adres="/wyprobuj">Zobacz to w działaniu</OdsylaczPrzycisk>
        <OdsylaczPrzycisk adres={sciezka("dokumentacja")} wariant="drugorzedny">
          Szczegóły w dokumentacji
        </OdsylaczPrzycisk>
      </div>
    </>
  );
}
