// Nagranie w hero chodzi w pętli, więc ruch na stronie produktu nie kończy się sam.
// WCAG 2.2.2 wymaga wtedy sposobu zatrzymania go — te testy pilnują, żeby przycisk
// istniał, działał i żeby ręczne wstrzymanie nie było wznawiane przez obserwatora
// widoczności.

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PasekZdan } from "../landing/sekcje";
import { ScenaHero } from "../landing/ScenaHero";

beforeEach(() => {
  // Domyślnie system nie prosi o ograniczenie ruchu — inaczej scena pokazuje makietę.
  window.matchMedia = ((zapytanie: string) => ({
    matches: false,
    media: zapytanie,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
  // jsdom nie odtwarza wideo; zastępujemy metody, żeby hak miał co wywołać.
  HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  HTMLMediaElement.prototype.pause = vi.fn();
});

afterEach(cleanup);

describe("scena hero", () => {
  it("daje przycisk wstrzymania pokazu", () => {
    render(<ScenaHero />);
    expect(screen.getByRole("button", { name: "Wstrzymaj pokaz aplikacji" })).toBeTruthy();
  });

  it("po wstrzymaniu zatrzymuje nagranie i proponuje wznowienie", async () => {
    const { container } = render(<ScenaHero />);
    screen.getByRole("button", { name: "Wstrzymaj pokaz aplikacji" }).click();
    expect(await screen.findByRole("button", { name: "Wznów pokaz aplikacji" })).toBeTruthy();
    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled();
    expect(container.querySelector("video")?.hasAttribute("autoplay")).toBe(false);
  });

  it("przycisku powiększenia nie zagnieżdża w przycisku wstrzymania", () => {
    const { container } = render(<ScenaHero />);
    for (const przycisk of container.querySelectorAll("button")) {
      expect(przycisk.querySelector("button")).toBeNull();
    }
  });
});

describe("pasek przykładowych poleceń", () => {
  it("daje klawiaturze czym zatrzymać przesuw", () => {
    render(<PasekZdan />);
    const przycisk = screen.getByRole("button", { name: "Wstrzymaj przesuwanie przykładów" });
    expect(przycisk).toBeTruthy();
    // Sam `:hover`/`:focus-within` nie wystarczał: kapsuły to `<span>`, fokus tam nie wchodzi.
    expect(przycisk.closest("section")?.getAttribute("data-pasek-wstrzymany")).toBe("false");
  });

  it("po wstrzymaniu zaznacza to na sekcji i proponuje wznowienie", async () => {
    render(<PasekZdan />);
    screen.getByRole("button", { name: "Wstrzymaj przesuwanie przykładów" }).click();
    const wznow = await screen.findByRole("button", { name: "Wznów przesuwanie przykładów" });
    expect(wznow.closest("section")?.getAttribute("data-pasek-wstrzymany")).toBe("true");
  });
});
