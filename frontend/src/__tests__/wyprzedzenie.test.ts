// Wyprzedzające pobranie pakietu okna nie obciąża strony produktu.
//
// Pomiar Lighthouse'em na wydaniu 21.09.2026 (`/`, profil mobilny): największym pobraniem
// strony publicznej był `Workspace-*.js` — 560 kB, więcej niż oba nagrania hero razem.
// Od 23.09.2026 „/” jest zawsze stroną produktu, a aplikacja stoi pod `/czat`: strona
// wraca z `App` przed `MainApp`, więc pobranie w `MainApp` jej nie dotyczy.
//
// Reguły nie da się sprawdzić w jsdom (nie pobiera modułów), więc test czyta źródło.

import { afterEach, describe, expect, it } from "vitest";
import zrodloApp from "../App.tsx?raw";
import zrodloSladu from "../sladLogowania.ts?raw";
import { wejscieDoAplikacji, zapamietajZalogowanie } from "../sladLogowania";

describe("wyprzedzające pobranie pakietu okna", () => {
  it("stoi w MainApp, do którego strona produktu nie dochodzi", () => {
    const pobranie = zrodloApp.indexOf('void import("./shell/Workspace")');
    const mainApp = zrodloApp.indexOf("function MainApp(");
    const strona = zrodloApp.indexOf('if (route.view === "landing") {');
    expect(pobranie).toBeGreaterThan(-1);
    expect(strona).toBeGreaterThan(-1);
    expect(strona).toBeLessThan(mainApp);
    expect(pobranie).toBeGreaterThan(mainApp);
  });

  it("ślad logowania kasuje wyłącznie odpowiedź 401, nie zerwane łącze", () => {
    expect(zrodloApp).toContain("zapamietajZalogowanie(true)");
    // Zerwane łącze ani błąd serwera nie są wylogowaniem.
    expect(zrodloApp).toContain("awaria.status === 401) zapamietajZalogowanie(false)");
  });

  it("odczyt i zapis śladu przeżywa zablokowane dane witryny", () => {
    // Prywatne okno potrafi rzucić wyjątkiem przy samym dotknięciu `localStorage`.
    const czytanie = zrodloSladu.slice(zrodloSladu.indexOf("function bylZalogowany"));
    expect(czytanie.slice(0, czytanie.indexOf("}\n\n"))).toContain("catch");
    const zapis = zrodloSladu.slice(zrodloSladu.indexOf("function zapamietajZalogowanie"));
    expect(zapis.slice(0, zapis.indexOf("}\n\n"))).toContain("catch");
  });
});

describe("wejście do aplikacji ze strony produktu", () => {
  afterEach(() => zapamietajZalogowanie(false));

  it("gość dostaje logowanie, zalogowany — okno aplikacji", () => {
    expect(wejscieDoAplikacji()).toEqual({ adres: "/zaloguj", etykieta: "Zaloguj się" });
    zapamietajZalogowanie(true);
    expect(wejscieDoAplikacji()).toEqual({ adres: "/czat", etykieta: "Otwórz aplikację" });
  });
});
