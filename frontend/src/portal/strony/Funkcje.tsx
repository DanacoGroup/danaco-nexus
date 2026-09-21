// Funkcje: pełny wykaz możliwości pogrupowany według obszaru pracy.

import { okruszki, usePozycjonowanie } from "../seo";
import { FUNKCJONALNOSCI } from "../tresc";
import { sciezka } from "../trasy";
import { NaglowekStrony, OdsylaczPrzycisk, Okruszki } from "../ui";

const OPIS =
  "Pełny wykaz tego, co Nexus robi po zalogowaniu, w podziale na obszary pracy. Zadanie zlecasz jednym zdaniem — narzędzia Nexus dobiera sam.";

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
      <Okruszki
        pozycje={[
          { nazwa: "Portal", sciezka: sciezka("glowna") },
          { nazwa: "Funkcje", sciezka: sciezka("funkcje") },
        ]}
      />
      <div className="mt-4">
        <NaglowekStrony tytul="Co Nexus robi po zalogowaniu" opis={OPIS} />
      </div>
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
      <p className="mt-12 text-sm text-muted">
        Wejdź na /wyprobuj i zleć jedno własne zadanie — przepisz skan, spisz nagranie albo
        zaprojektuj logo. Plik dostaniesz w tej samej rozmowie, bez rejestracji i bez karty.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <OdsylaczPrzycisk adres="/wyprobuj">Wypróbuj bez rejestracji</OdsylaczPrzycisk>
        <OdsylaczPrzycisk adres={sciezka("dokumentacja")} wariant="drugorzedny">
          Szczegóły w dokumentacji
        </OdsylaczPrzycisk>
      </div>
    </>
  );
}
