// Pakiet motion/start jest podpięty do konkretnych chwil w aplikacji. Test pilnuje,
// że każda nazwa użyta w kodzie istnieje w katalogu — inaczej zmiana nazwy pliku
// zostawiłaby puste miejsce tam, gdzie miał być ruch, i nikt by tego nie zauważył.

import { describe, expect, it } from "vitest";
import { START } from "../../media/katalog";
import { zrodlaStartu, type IdStartu } from "../NagranieStartu";

/** Nazwy podpięte w kodzie aplikacji i strony produktu. */
const UZYWANE: IdStartu[] = [
  "intro-znaku",
  "logowanie-ciemny",
  "logowanie-jasny",
  "moment-brak-polaczenia",
  "moment-instalacja",
  "moment-mysli",
  "moment-sukces",
  "uruchomienie-komputer-ciemny",
  "uruchomienie-komputer-jasny",
  "uruchomienie-krotkie-komputer-ciemny",
  "uruchomienie-krotkie-telefon-ciemny",
  "uruchomienie-telefon-ciemny",
  "uruchomienie-telefon-jasny",
];

describe("nagrania startowe", () => {
  it.each(UZYWANE)("%s ma źródła w katalogu", (nazwa) => {
    const zrodla = zrodlaStartu(nazwa);
    expect(zrodla).not.toBeNull();
    expect(zrodla?.webm).toBeTruthy();
    expect(zrodla?.mp4).toBeTruthy();
  });

  it("katalog nie zgubił żadnej pozycji pakietu", () => {
    expect(START.length).toBe(18);
  });
});
