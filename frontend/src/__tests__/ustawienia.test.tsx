// Ustawienia konta: preferencje mają działać, a nie tylko się wyświetlać.

import { afterEach, describe, expect, it, beforeEach, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DOMYSLNE, preferencje, zapiszPreferencje } from "../preferencje";
import { apiRequest } from "../api";
import { CoNowego } from "../modules/ustawienia";

vi.mock("../api", () => ({
  apiRequest: vi.fn(async (_metoda: string, _adres: string, cialo?: unknown) => cialo ?? {}),
}));

describe("preferencje konta", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("bez zapisanych danych zwraca komplet wartości domyślnych", () => {
    expect(preferencje()).toMatchObject(DOMYSLNE);
  });

  it("zapis działa od razu lokalnie, zanim odpowie serwer", async () => {
    const obietnica = zapiszPreferencje({ wysylka: "ctrl-enter" });
    // Kopia lokalna jest ustawiona synchronicznie — przełącznik ma zadziałać pod palcem.
    expect(preferencje().wysylka).toBe("ctrl-enter");
    await obietnica;
    expect(preferencje().wysylka).toBe("ctrl-enter");
  });

  it("uzupełnia braki wartościami domyślnymi zamiast zwracać undefined", async () => {
    await zapiszPreferencje({ motyw: "light" });
    const dane = preferencje();
    expect(dane.motyw).toBe("light");
    expect(dane.modul_startowy).toBe(DOMYSLNE.modul_startowy);
  });
});

describe("co nowego", () => {
  afterEach(cleanup);

  it("pokazuje zmiany wydania i chowa nadmiar pod przyciskiem", async () => {
    const pozycje = Array.from({ length: 6 }, (_, i) => ({
      tytul: `Zmiana ${i + 1}`,
      tresc: `Opis zmiany ${i + 1}.`,
      rodzaj: "Zmieniono",
    }));
    vi.mocked(apiRequest).mockImplementation(async (_metoda: string, adres: string) =>
      adres === "/api/nowosci" ? { pozycje, wszystkich: 6, wydanie: "2026-09-21" } : {},
    );

    render(<CoNowego />);

    expect(await screen.findByText("Zmiana 1")).toBeTruthy();
    expect(screen.queryByText("Zmiana 5")).toBeNull();
    fireEvent.click(screen.getByText(/Pokaż pozostałe \(2\)/));
    expect(screen.getByText("Zmiana 6")).toBeTruthy();
  });

  it("bez zmian w dzienniku nie pokazuje pustej sekcji", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ pozycje: [], wszystkich: 0, wydanie: "" });

    const { container } = render(<CoNowego />);
    await waitFor(() => expect(container.textContent).not.toContain("Co nowego"));
  });
});
