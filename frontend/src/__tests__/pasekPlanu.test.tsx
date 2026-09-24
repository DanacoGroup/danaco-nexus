// Pasek „Zmień plan” nad rozmową: widać go tylko wtedy, gdy wyższy plan jest potrzebny.

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const kredyty = vi.fn();

vi.mock("../platnosci/api", async (oryginal) => {
  const rzeczywisty = await oryginal<typeof import("../platnosci/api")>();
  return { ...rzeczywisty, platnosciApi: { ...rzeczywisty.platnosciApi, kredyty } };
});

const { PasekPlanu } = await import("../platnosci/PasekPlanu");

afterEach(() => kredyty.mockReset());

describe("PasekPlanu", () => {
  it("przy dostępie w porządku nie zajmuje miejsca", async () => {
    kredyty.mockResolvedValue({ stan: "w_porzadku" });
    const { container } = render(<PasekPlanu onZmienPlan={() => undefined} />);
    await waitFor(() => expect(kredyty).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });

  it("przy wyczerpanym dostępie prowadzi do zmiany planu", async () => {
    kredyty.mockResolvedValue({ stan: "wyczerpany" });
    const zmien = vi.fn();
    render(<PasekPlanu onZmienPlan={zmien} />);
    fireEvent.click(await screen.findByRole("button", { name: "Zmień plan" }));
    expect(zmien).toHaveBeenCalledOnce();
    expect(screen.getByText("Dostęp w tym okresie się wyczerpał.")).toBeTruthy();
  });
});
