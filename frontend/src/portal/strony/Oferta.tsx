// Oferta: zestawienie zastosowań produktu wraz z zakresem prac i adresatem.

import { okruszki, usePozycjonowanie } from "../seo";
import { OFERTA } from "../tresc";
import { sciezka } from "../trasy";
import { Karta, NaglowekStrony, OdsylaczPrzycisk, Okruszki, Sekcja } from "../ui";

const OPIS =
  "Od skanu faktury, przez skrzynkę i kalendarz, po raport z przypisami i stronę opublikowaną pod adresem Nexusa. Przy każdej pozycji widać zakres i adresata.";

/** Ograniczenia wypisane wprost — czytelnik ma je poznać przed założeniem konta, nie po nim. */
const GRANICE = [
  "Własnej domeny Nexus nie podpina. Opublikowana strona stoi pod adresem Nexusa, w postaci /s/nazwa-strony/.",
  "Nexus pracuje przez internet. Bez połączenia aplikacja się nie otworzy.",
  "Treść polecenia i dołączone pliki trafiają do modelu, który prowadzi rozmowę.",
  "Wysłanie wiadomości, usunięcie wydarzenia i publikację strony zatwierdzasz sam.",
];

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
      <Okruszki
        pozycje={[
          { nazwa: "Portal", sciezka: sciezka("glowna") },
          { nazwa: "Oferta", sciezka: sciezka("oferta") },
        ]}
      />
      <div className="mt-4">
        <NaglowekStrony tytul="Osiem rodzajów pracy, które Nexus przejmuje w całości" opis={OPIS} />
      </div>
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
      <Sekcja tytul="Od czego zależy cena" opis="Cena zależy od planu.">
        <p className="max-w-2xl text-muted">
          Osobisty, Pro i Grupa różnią się miejscem w chmurze, liczbą skrzynek pocztowych i liczbą zadań
          prowadzonych naraz. Plan Osobisty zaczyna się od 7&nbsp;dni próbnych ze 100&nbsp;MB miejsca. Plan Grupa
          liczy się za użytkownika i daje wspólny zakres pracy.
        </p>
      </Sekcja>

      <Sekcja tytul="Granice produktu" opis="Cztery ograniczenia, o których mówimy przed założeniem konta.">
        <ul className="flex max-w-2xl flex-col gap-1.5 text-sm text-muted">
          {GRANICE.map((element) => (
            <li key={element} className="flex gap-2">
              <span aria-hidden="true" className="text-accent">
                •
              </span>
              {element}
            </li>
          ))}
        </ul>
      </Sekcja>

      <p className="max-w-2xl text-muted">
        Przepisz jeden skan na koncie próbnym, a plik dostaniesz w tej samej rozmowie.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
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
