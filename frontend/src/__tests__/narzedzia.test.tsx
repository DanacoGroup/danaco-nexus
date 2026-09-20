import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { DZIEDZINY, LICZBA_NARZEDZI } from "../dane/narzedzia";
import { nagranieNarzedzia } from "../modules/mozliwosci/ruch";
import { Narzedzia } from "../portal/strony/Narzedzia";

// Projekt nie ma wspólnego pliku przygotowania testów, więc sprzątamy drzewo sami —
// bez tego nazwy narzędzi z poprzedniego renderu mieszają się z bieżącym.
afterEach(cleanup);

describe("katalog narzędzi", () => {
  it("wymienia każde narzędzie rejestru dokładnie raz", () => {
    const wszystkie = DZIEDZINY.flatMap((grupa) => grupa.narzedzia.map((n) => n.id));
    expect(wszystkie.length).toBe(LICZBA_NARZEDZI);
    expect(new Set(wszystkie).size).toBe(LICZBA_NARZEDZI);
  });

  it("każde narzędzie ma polską nazwę i opis bez urwanego zdania", () => {
    for (const grupa of DZIEDZINY) {
      for (const narzedzie of grupa.narzedzia) {
        expect(narzedzie.nazwa).not.toBe("");
        expect(narzedzie.nazwa).not.toMatch(/[a-z]_[a-z]/);
        expect(narzedzie.opis.length).toBeGreaterThan(10);
        expect(narzedzie.opis).not.toMatch(/\(np\.$/);
      }
    }
  });

  it("każda dziedzina ma narzędzie z nagraniem, więc sekcja nigdy nie jest bez ruchu", () => {
    for (const grupa of DZIEDZINY) {
      expect(grupa.narzedzia.some((n) => nagranieNarzedzia(n.id))).toBe(true);
    }
  });

  it("strona portalu pokazuje wszystkie dziedziny i liczbę narzędzi", () => {
    render(<Narzedzia />);
    // Treść nagłówka należy do dziedziny treści i bywa przepisywana — sprawdzamy, że
    // jest jeden nagłówek strony, a nie jakie ma dokładnie brzmienie.
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    for (const grupa of DZIEDZINY) {
      expect(screen.getByRole("heading", { level: 2, name: grupa.tytul })).toBeTruthy();
    }
    expect(screen.getByText(`Wszystkich narzędzi: ${LICZBA_NARZEDZI}`)).toBeTruthy();
  });
});

describe("sekcja strony produktu", () => {
  it("pokazuje zakładkę każdej dziedziny i listę narzędzi wybranej", async () => {
    const { SekcjaNarzedzi } = await import("../landing/SekcjaNarzedzi");
    // Zapytania w obrębie wyrenderowanego drzewa: nazwy narzędzi powtarzają się
    // w innych testach tego pliku, a `screen` widzi cały dokument.
    const { getAllByRole, getByText } = render(<SekcjaNarzedzi />);
    const zakladki = getAllByRole("tab");
    expect(zakladki.length).toBe(DZIEDZINY.length);
    expect(zakladki[0].getAttribute("aria-selected")).toBe("true");
    for (const narzedzie of DZIEDZINY[0].narzedzia) {
      expect(getByText(narzedzie.nazwa)).toBeTruthy();
    }
  });

  it("kliknięcie zakładki przełącza opisywaną dziedzinę", async () => {
    const { SekcjaNarzedzi } = await import("../landing/SekcjaNarzedzi");
    const { getAllByRole, getByRole } = render(<SekcjaNarzedzi />);
    fireEvent.click(getAllByRole("tab")[1]);
    expect(getByRole("heading", { level: 3, name: DZIEDZINY[1].tytul })).toBeTruthy();
    expect(getAllByRole("tab")[1].getAttribute("aria-selected")).toBe("true");
  });
});
