// Pakiet motion/start jest podpięty do konkretnych chwil w aplikacji. Test pilnuje,
// że każda nazwa użyta w kodzie istnieje w katalogu — inaczej zmiana nazwy pliku
// zostawiłaby puste miejsce tam, gdzie miał być ruch, i nikt by tego nie zauważył.

import { describe, expect, it } from "vitest";
import { START } from "../../media/katalog";
import { BEZ_PODPISU, zrodlaStartu, type IdStartu } from "../NagranieStartu";

/** Nazwy podpięte w kodzie aplikacji i strony produktu.
 *
 * Wykaz nie jest spisem całego pakietu, tylko tego, co naprawdę gra. Ubyły z niego trzy
 * ujęcia i każde z innego powodu: `intro-znaku` (otwarcie strony rysuje ekran ładowania
 * marki, a nagranie było drugą planszą pod rząd), `logowanie-ciemny` i `logowanie-jasny`
 * (makiety produktu z cudzym adresem i powitaniem „Dzień dobry, Dariuszu” — domknięcie
 * logowania rysuje teraz znak) oraz `moment-mysli` (obok animowanego znaku w rozmowie
 * wyglądało jak dwa znaki naraz).
 */
const UZYWANE: IdStartu[] = [
  "moment-blad",
  "moment-brak-polaczenia",
  "moment-instalacja",
  "moment-sukces",
  "moment-wylogowanie",
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
    // Pakiet ma osiemnaście ujęć startowych, ale trzy z nich do `public` nie trafiają
    // (`POMIJANE_NAGRANIA` w `frontend/scripts/zasoby.py`): makieta logowania w trzech
    // wariantach pokazuje formularz z prawdziwym adresem właściciela i powitanie
    // „Dzień dobry, Dariuszu”. Spis powstaje z katalogu publicznego, więc ich tu nie ma.
    expect(START.length).toBe(15);
    expect(START.map((pozycja) => pozycja.id).filter((id) => id.startsWith("logowanie"))).toEqual([]);
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
