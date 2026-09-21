// Znacznik „są nowe zmiany”: kropka przy „Więcej” zapala się przy nowym wydaniu i gaśnie,
// gdy ktoś otworzy wykaz zmian w Ustawieniach.
//
// Produkt zmienia się po kilkanaście razy dziennie, a jedyną informacją o nowym wydaniu
// było to, że coś wygląda inaczej — sekcja „Co nowego” siedziała w Ustawieniach i nic
// do niej nie prowadziło.

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, waitFor } from "@testing-library/react";

const zapytanie = vi.fn();
vi.mock("../api", () => ({ apiRequest: (...args: unknown[]) => zapytanie(...args) }));
import { oznaczNowosciPrzeczytane, useNieprzeczytaneNowosci } from "../nowosci";

function Sonda() {
  return <span data-stan={useNieprzeczytaneNowosci() ? "nowe" : "nic"}>stan</span>;
}

function stan(): string | null {
  return document.querySelector("span")?.getAttribute("data-stan") ?? null;
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  zapytanie.mockReset();
});

describe("nowości w wydaniu", () => {
  it("zapala się, gdy wydanie jest nowe", async () => {
    zapytanie.mockResolvedValue({ wydanie: "2026-09-21", pozycje: [{ tytul: "A", tresc: "B" }] });
    render(<Sonda />);
    await waitFor(() => expect(stan()).toBe("nowe"));
  });

  it("milczy, gdy wykaz tego wydania już oglądano", async () => {
    window.localStorage.setItem("nexus:nowosci-wydanie", "2026-09-21");
    zapytanie.mockResolvedValue({ wydanie: "2026-09-21", pozycje: [{ tytul: "A", tresc: "B" }] });
    render(<Sonda />);
    await new Promise((ok) => setTimeout(ok, 30));
    expect(stan()).toBe("nic");
  });

  it("milczy, gdy wydanie nie ma czym się pochwalić", async () => {
    zapytanie.mockResolvedValue({ wydanie: "2026-09-21", pozycje: [] });
    render(<Sonda />);
    await new Promise((ok) => setTimeout(ok, 30));
    expect(stan()).toBe("nic");
  });

  it("gaśnie, gdy wykaz zostanie otwarty", async () => {
    zapytanie.mockResolvedValue({ wydanie: "2026-09-21", pozycje: [{ tytul: "A", tresc: "B" }] });
    render(<Sonda />);
    await waitFor(() => expect(stan()).toBe("nowe"));
    act(() => oznaczNowosciPrzeczytane("2026-09-21"));
    expect(stan()).toBe("nic");
  });

  it("nie przewraca się, gdy przeglądarka nie daje pamięci", async () => {
    const pamiec = window.localStorage.getItem.bind(window.localStorage);
    window.localStorage.getItem = () => {
      throw new Error("brak dostępu do danych witryny");
    };
    zapytanie.mockResolvedValue({ wydanie: "2026-09-21", pozycje: [{ tytul: "A", tresc: "B" }] });
    render(<Sonda />);
    await waitFor(() => expect(stan()).toBe("nowe"));
    window.localStorage.getItem = pamiec;
  });

  it("pyta serwer raz na wywołanie haka", async () => {
    // Powłoka woła hak jeden raz i podaje wynik obu odmianom paska modułów (bok na
    // komputerze, dół na telefonie) — inaczej każde otwarcie okna posyłałoby to samo
    // pytanie dwa razy.
    zapytanie.mockResolvedValue({ wydanie: "2026-09-21", pozycje: [{ tytul: "A", tresc: "B" }] });
    render(<Sonda />);
    await waitFor(() => expect(stan()).toBe("nowe"));
    expect(zapytanie).toHaveBeenCalledTimes(1);
  });
});
