// Adres modułu po polsku prowadzi do modułu, a nie do komunikatu o braku instalacji.
//
// Cztery moduły mają w pasku nawigacji inną nazwę niż identyfikator w adresie: `cloud`
// („Chmura”), `research` („Badania”), `urzadzenia` („Sprzęt”) i `mozliwosci` („Narzędzia”).
// Kto przepisał adres z nazwy na pasku albo dostał go od kogoś, trafiał pod `/m/chmura`
// na „Moduł «chmura» nie jest zainstalowany w tej wersji Nexusa” — moduł był na miejscu,
// tylko pod inną nazwą.

import { describe, expect, it } from "vitest";
import { findModule, MODULES } from "../modules/registry";

describe("adresy modułów", () => {
  it("polska nazwa otwiera moduł chmury", () => {
    expect(findModule("chmura")?.id).toBe("cloud");
  });

  it("polska nazwa otwiera moduł badań", () => {
    expect(findModule("badania")?.id).toBe("research");
  });

  it("nazwa z paska otwiera sprzęt i narzędzia", () => {
    expect(findModule("sprzet")?.id).toBe("urzadzenia");
    expect(findModule("narzedzia")?.id).toBe("mozliwosci");
  });

  it("identyfikator nadal działa", () => {
    expect(findModule("cloud")?.id).toBe("cloud");
    expect(findModule("research")?.id).toBe("research");
  });

  it("nieznany adres nadal jest nieznany", () => {
    expect(findModule("czegos-takiego-nie-ma")).toBeUndefined();
    expect(findModule(null)).toBeUndefined();
  });

  it("żaden alias nie zasłania innego modułu", () => {
    const zajete = new Set(MODULES.map((m) => m.id));
    for (const m of MODULES) for (const alias of m.aliasy ?? []) expect(zajete.has(alias)).toBe(false);
  });

  it("aliasy się nie powtarzają", () => {
    const wszystkie = MODULES.flatMap((m) => [...(m.aliasy ?? [])]);
    expect(new Set(wszystkie).size).toBe(wszystkie.length);
  });
});
