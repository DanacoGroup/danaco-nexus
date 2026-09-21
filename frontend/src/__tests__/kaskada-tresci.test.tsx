// Kaskada wejścia obejmuje treść, która **dochodzi** po odpowiedzi serwera.
//
// Pomiar na wydaniu 21 września pokazał, że zmiana modułu w oknie rusza się (przejście
// widoku), ale to, co przychodzi chwilę później — lista plików, karty stron — pojawiało
// się skokiem. Komponent `Stagger` miał testy i nie był użyty w aplikacji ani razu.
// Te testy pilnują, żeby z powrotem nie wypadł, i żeby nie wszedł tam, gdzie zderzyłby
// się z przejściem widoku (motion, rozdz. 5 i 13).

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const listaStron = vi.fn();
const katalogKitu = vi.fn();

vi.mock("../modules/strony/api", async (oryginal) => {
  const rzeczywisty = await oryginal<typeof import("../modules/strony/api")>();
  return {
    ...rzeczywisty,
    sitesApi: { ...rzeczywisty.sitesApi, list: listaStron, kit: katalogKitu },
  };
});

afterEach(cleanup);

beforeEach(() => {
  katalogKitu.mockResolvedValue({ dostepny: false, motywy: [], presety: [], szablony: [] });
  listaStron.mockResolvedValue(
    ["pierwsza", "druga", "trzecia", "czwarta", "piata", "szosta"].map((adres, numer) => ({
      address: adres,
      title: `Strona ${numer + 1}`,
      description: "",
      updated_at: "2026-09-21T08:00:00Z",
      published_at: null,
      publish_request: null,
    })),
  );
});

describe("karty stron dochodzące z serwera", () => {
  it("wchodzą kaskadą, a nie skokiem", async () => {
    const { SiteList } = await import("../modules/strony/SiteList");
    const { container } = render(<SiteList onOpen={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Strona 1")).toBeTruthy());

    const karty = [...container.querySelectorAll("article")];
    expect(karty.length).toBe(6);
    for (const karta of karty) expect(karta.className).toContain("ui-wejscie");
  });

  it("opóźnienie rośnie po kolei i zatrzymuje się na czwartym kroku", async () => {
    const { SiteList } = await import("../modules/strony/SiteList");
    const { container } = render(<SiteList onOpen={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Strona 1")).toBeTruthy());

    const karty = [...container.querySelectorAll<HTMLElement>("article")];
    const opoznienia = karty.map((karta) => karta.style.getPropertyValue("--ui-opoznienie"));
    expect(opoznienia[0]).toContain("* 0");
    expect(opoznienia[3]).toContain("* 3");
    // Piąta i szósta karta wchodzą razem z czwartą — kaskada nie ciągnie się w nieskończoność.
    expect(opoznienia[4]).toContain("* 4");
    expect(opoznienia[5]).toContain("* 4");
  });
});
