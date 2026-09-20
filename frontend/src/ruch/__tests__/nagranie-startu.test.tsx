// Pakiet motion/start jest podpięty do konkretnych chwil w aplikacji. Test pilnuje,
// że każda nazwa użyta w kodzie istnieje w katalogu — inaczej zmiana nazwy pliku
// zostawiłaby puste miejsce tam, gdzie miał być ruch, i nikt by tego nie zauważył.

import { describe, expect, it } from "vitest";
import { START } from "../../media/katalog";
import { BEZ_PODPISU, zrodlaStartu, type IdStartu } from "../NagranieStartu";

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

  it("momenty z wariantem bez podpisu mają plik w katalogu publicznym", async () => {
    // Nagrania mają wypaloną planszę opisową z demonstracji dla zespołu. W aplikacji
    // gra wariant `-alfa`, więc wykaz w komponencie musi zgadzać się z tym, co leży
    // na dysku — inaczej użytkownik zobaczy podpis „Intro znaku · 2200 ms”.
    // Import przez zmienną: tsconfig aplikacji nie ma typów Node, a ten test biegnie
    // wyłącznie w vitest, gdzie moduł jest dostępny.
    const modul = "node:fs";
    const fs = (await import(/* @vite-ignore */ modul)) as {
      readdirSync: (sciezka: string) => string[];
    };
    const pliki = new Set(fs.readdirSync("public/ruch/start"));
    for (const nazwa of BEZ_PODPISU) {
      expect(pliki.has(`${nazwa}-alfa.webm`), `${nazwa}-alfa.webm`).toBe(true);
    }
  });
});
