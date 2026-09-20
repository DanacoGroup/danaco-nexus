// Oferta: zestawienie zastosowań produktu wraz z zakresem prac i adresatem.

import { okruszki, usePozycjonowanie } from "../seo";
import { OFERTA } from "../tresc";
import { sciezka } from "../trasy";
import { Karta, NaglowekStrony, OdsylaczPrzycisk } from "../ui";

const OPIS =
  "Pięć rodzajów pracy, które Nexus przejmuje w całości: od skanu faktury, przez skrzynkę i kalendarz, po raport z przypisami i stronę opublikowaną pod adresem Nexusa.";

export function Oferta() {
  usePozycjonowanie({
    tytul: "Oferta",
    opis: OPIS,
    sciezka: sciezka("oferta"),
    dane: okruszki([
      { nazwa: "Portal", sciezka: sciezka("glowna") },
      { nazwa: "Oferta", sciezka: sciezka("oferta") },
    ]),
  });

  return (
    <>
      <NaglowekStrony tytul="Pięć rodzajów pracy, które przejmujemy w całości" opis={OPIS} />
      <ul className="mt-8 grid gap-6 lg:grid-cols-2">
        {OFERTA.map((pozycja) => (
          <li key={pozycja.nazwa}>
            <Karta className="flex h-full flex-col gap-4">
              <div>
                <h2 className="font-heading text-xl font-semibold text-fg">{pozycja.nazwa}</h2>
                <p className="mt-2 text-muted">{pozycja.opis}</p>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-fg">Zakres</h3>
                <ul className="mt-2 flex flex-col gap-1.5 text-sm text-muted">
                  {pozycja.zakres.map((element) => (
                    <li key={element} className="flex gap-2">
                      <span aria-hidden="true" className="text-accent">
                        •
                      </span>
                      {element}
                    </li>
                  ))}
                </ul>
              </div>
              <p className="mt-auto text-sm text-subtle">Adresat: {pozycja.dla}</p>
            </Karta>
          </li>
        ))}
      </ul>
      <div className="mt-10 flex flex-wrap gap-3">
        <OdsylaczPrzycisk adres="/wyprobuj">Wejdź bez rejestracji</OdsylaczPrzycisk>
        <OdsylaczPrzycisk adres={sciezka("cennik")} wariant="drugorzedny">
          Zobacz plany i ceny
        </OdsylaczPrzycisk>
        <OdsylaczPrzycisk adres={sciezka("kontakt")} wariant="drugorzedny">
          Zapytaj o swoją sprawę
        </OdsylaczPrzycisk>
      </div>
    </>
  );
}
