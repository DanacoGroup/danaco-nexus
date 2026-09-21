// Nowa wersja ma się zgłosić tam, gdzie użytkownik patrzy — także na telefonie.
//
// Do 21.09.2026 jedynym miejscem był przycisk w stopce panelu rozmów. Pomiar na zbudowanym
// interfejsie: na szerokości 390 px panel ma `visibility: hidden`, więc na telefonie —
// podstawowym miejscu tej aplikacji, bo klient to instalacja PWA — komunikat był dostępny
// dopiero po otwarciu szuflady z historią.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const stan = { updateReady: false, canInstall: false, iosHint: false };
const odswiez = vi.fn();

vi.mock("../pwa", () => ({
  usePwa: () => ({ ...stan, install: async () => undefined, update: odswiez }),
  isStandalone: () => false,
  isIos: () => false,
  setupPwa: () => undefined,
}));

afterEach(() => {
  cleanup();
  stan.updateReady = false;
  odswiez.mockClear();
});

describe("pasek nowej wersji", () => {
  it("milczy, dopóki nie ma czego wczytać", async () => {
    const { PasekAktualizacji } = await import("../shell/PasekAktualizacji");
    const { container } = render(<PasekAktualizacji />);
    expect(container.firstChild).toBeNull();
  });

  it("po zgłoszeniu nowej wersji podaje ją i przycisk odświeżenia", async () => {
    stan.updateReady = true;
    const { PasekAktualizacji } = await import("../shell/PasekAktualizacji");
    render(<PasekAktualizacji />);
    expect(screen.getByText("Jest nowa wersja")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Odśwież" }));
    expect(odswiez).toHaveBeenCalledTimes(1);
  });

  it("„Później” chowa pasek, ale nie przeładowuje aplikacji", async () => {
    stan.updateReady = true;
    const { PasekAktualizacji } = await import("../shell/PasekAktualizacji");
    const { container } = render(<PasekAktualizacji />);
    fireEvent.click(screen.getByRole("button", { name: "Później" }));
    expect(container.firstChild).toBeNull();
    expect(odswiez).not.toHaveBeenCalled();
  });

  it("nie chowa się na telefonie — stoi obok pasków „brak połączenia” i „konto próbne”", async () => {
    stan.updateReady = true;
    const { PasekAktualizacji } = await import("../shell/PasekAktualizacji");
    const { container } = render(<PasekAktualizacji />);
    const klasy = String((container.firstChild as HTMLElement).className).split(/\s+/);
    expect(klasy).not.toContain("hidden");
    expect(klasy).not.toContain("md:flex");
  });
});
