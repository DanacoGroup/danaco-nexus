// Panel klienta pokazywał zakres planu z pliku z tekstem portalu — a ten obiecywał
// „Automatyzacje według harmonogramu”, których katalog płatności nie zna. Zakres planu
// należy do katalogu, więc panel ma go brać z serwera.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// `vi.mock` jest wynoszone nad deklaracje, więc atrapa musi powstać razem z nim.
const { cennikPubliczny } = vi.hoisted(() => ({ cennikPubliczny: vi.fn() }));

vi.mock("../platnosci/api", async (oryginal) => {
  const rzeczywisty = await oryginal<typeof import("../platnosci/api")>();
  return { ...rzeczywisty, platnosciApi: { ...rzeczywisty.platnosciApi, cennikPubliczny } };
});

import { PanelKlienta } from "../portal/strony/PanelKlienta";
import type { ProfilKlienta } from "../portal/api";

const KONTO = {
  email: "klient@example.com",
  name: "Klient",
  plan: "pro",
  created_at: "2026-09-01T10:00:00Z",
  adres_potwierdzony: true,
} as unknown as ProfilKlienta;

beforeEach(() => cennikPubliczny.mockReset());
afterEach(cleanup);

describe("panel klienta", () => {
  it("bierze zakres planu z katalogu płatności", async () => {
    cennikPubliczny.mockResolvedValue({
      waluta: "PLN",
      sprzedaz_aktywna: true,
      plany: [
        { kod: "pro", nazwa: "Pro", opis: "Dla pracujących codziennie.", zawartosc: ["Więcej zadań naraz"] },
      ],
    });

    render(<PanelKlienta konto={KONTO} odswiez={() => undefined} />);

    await waitFor(() => expect(screen.getByText(/Więcej zadań naraz/)).toBeTruthy());
    expect(screen.queryByText(/Automatyzacje według harmonogramu/)).toBeNull();
  });

  it("milczy o zakresie, gdy katalog nie zna planu konta", async () => {
    // Konto może stać na planie wycofanym z katalogu. Karta nie zmyśla wtedy zakresu —
    // odsyła do cennika, gdzie stoi zawsze aktualny.
    cennikPubliczny.mockResolvedValue({ waluta: "PLN", sprzedaz_aktywna: true, plany: [] });

    render(<PanelKlienta konto={KONTO} odswiez={() => undefined} />);

    await waitFor(() => expect(screen.getByText(/Zakres planu jest na stronie cennika/)).toBeTruthy());
    // Nazwa planu z konta zostaje — to jedyne, co wiadomo na pewno.
    expect(screen.getByText("pro")).toBeTruthy();
  });
});
