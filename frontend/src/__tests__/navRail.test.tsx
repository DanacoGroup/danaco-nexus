import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { CHAT_ENTRY, NavRail, VOICE_ENTRY, navEntries, type NavEntry } from "../shell/ModuleNav";
import { MODULES } from "../modules/registry";

afterEach(cleanup);

function ikona() {
  return <svg />;
}

const DUZO: NavEntry[] = Array.from({ length: 18 }, (_, numer) => ({
  id: `modul-${numer}`,
  label: `Moduł ${numer}`,
  description: `Opis ${numer}`,
  icon: ikona,
}));

describe("pasek modułów", () => {
  it("pokazuje wszystkie pozycje, także gdy jest ich więcej niż mieści ekran", () => {
    render(<NavRail entries={DUZO} activeId="modul-0" onSelect={() => undefined} />);
    for (const pozycja of DUZO) {
      expect(screen.getByRole("button", { name: pozycja.label })).toBeTruthy();
    }
  });

  it("lista modułów jest przewijalna, a nie przycięta", () => {
    const { container } = render(<NavRail entries={DUZO} activeId="modul-0" onSelect={() => undefined} />);
    const lista = container.querySelector("nav div.overflow-y-auto");
    expect(lista).toBeTruthy();
    expect(lista?.className).toContain("min-h-0");
    expect(lista?.className).toContain("flex-1");
  });

  it("zaznacza aktywny moduł atrybutem aria-current", () => {
    render(<NavRail entries={DUZO} activeId="modul-7" onSelect={() => undefined} />);
    expect(screen.getByRole("button", { name: "Moduł 7" }).getAttribute("aria-current")).toBe("page");
  });

  it("wykaz pozycji zaczyna się czatem i głosem, a dalej idą moduły rejestru", () => {
    const pozycje = navEntries(MODULES);
    expect(pozycje[0].id).toBe(CHAT_ENTRY.id);
    expect(pozycje[1].id).toBe(VOICE_ENTRY.id);
    expect(pozycje.length).toBe(MODULES.length + 2);
    // Moduł „Narzędzia" musi być na liście — to on pokazuje pełny zakres agenta.
    expect(pozycje.some((pozycja) => pozycja.id === "mozliwosci")).toBe(true);
  });
});

describe("etykiety modułów", () => {
  it("mieszczą się w pasku 72 px — najwyżej 9 znaków", () => {
    // Dłuższa etykieta jest ucinana wielokropkiem i moduł przestaje być rozpoznawalny
    // („Baza wi…”, „Urządze…”). Umowa `NexusModule.label`: 1–2 krótkie słowa.
    for (const modul of MODULES) {
      expect(modul.label.length, `etykieta „${modul.label}” jest za długa`).toBeLessThanOrEqual(9);
    }
    for (const pozycja of [CHAT_ENTRY, VOICE_ENTRY]) {
      expect(pozycja.label.length).toBeLessThanOrEqual(9);
    }
  });
});
