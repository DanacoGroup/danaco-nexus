// Wyprzedzające pobranie pakietu okna nie obciąża strony produktu.
//
// Pomiar Lighthouse'em na wydaniu 21.09.2026 (`/`, profil mobilny): największym pobraniem
// strony publicznej był `Workspace-*.js` — 560 kB, więcej niż oba nagrania hero razem.
// Wyprzedzenie dodano tego samego dnia po to, żeby zalogowany nie oglądał zasłony na czas
// pobrania; ustawione bez warunku kazało jednak płacić za to każdemu, kto pierwszy raz
// wchodzi na stronę produktu i nigdy się nie zaloguje.
//
// Reguły nie da się sprawdzić w jsdom (nie pobiera modułów), więc test czyta źródło.

import { describe, expect, it } from "vitest";
import zrodloApp from "../App.tsx?raw";

describe("wyprzedzające pobranie pakietu okna", () => {
  it("stoi pod warunkiem, a nie bezwarunkowo", () => {
    const wiersze = zrodloApp.split("\n");
    const numer = wiersze.findIndex((w) => w.includes('void import("./shell/Workspace")'));
    expect(numer).toBeGreaterThan(-1);
    // Warunek stoi w wierszu bezpośrednio nad pobraniem.
    expect(wiersze[numer - 1]).toContain('location.pathname !== "/"');
    expect(wiersze[numer - 1]).toContain("bylZalogowany()");
  });

  it("ślad logowania kasuje wyłącznie odpowiedź 401, nie zerwane łącze", () => {
    expect(zrodloApp).toContain("zapamietajZalogowanie(true)");
    // Zerwane łącze ani błąd serwera nie są wylogowaniem: skasowany wtedy ślad zabrałby
    // wyprzedzające pobranie przy następnym wejściu, choć konto jest całe.
    expect(zrodloApp).toContain("awaria.status === 401) zapamietajZalogowanie(false)");
  });

  it("odczyt i zapis śladu przeżywa zablokowane dane witryny", () => {
    // Prywatne okno potrafi rzucić wyjątkiem przy samym dotknięciu `localStorage`.
    const czytanie = zrodloApp.slice(zrodloApp.indexOf("function bylZalogowany"));
    expect(czytanie.slice(0, czytanie.indexOf("}\n\n"))).toContain("catch");
    const zapis = zrodloApp.slice(zrodloApp.indexOf("function zapamietajZalogowanie"));
    expect(zapis.slice(0, zapis.indexOf("}\n\n"))).toContain("catch");
  });
});
