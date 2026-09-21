// Puste stany modułów: ekran bez danych ma mówić, co moduł potrafi, a nie tylko
// pokazywać ramkę na plik. Testy pilnują tego, czego nie widać w typach.

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
  listaStron.mockResolvedValue([]);
  katalogKitu.mockResolvedValue({
    dostepny: true,
    motywy: ["premium-dark"],
    presety: [
      { preset: "law-firm", nazwa: "Kancelaria prawna", opis: "" },
      { preset: "restaurant", nazwa: "Restauracja i gastronomia", opis: "" },
    ],
    szablony: [{ id: "astro-blog", nazwa: "Astro Blog", charakter: ["blog"], podstrony: 8, licencja: "MIT" }],
  });
});

describe("moduł Strony bez żadnej strony", () => {
  it("proponuje gotowe układy branżowe, a nie tylko puste pole opisu", async () => {
    const { SiteList } = await import("../modules/strony/SiteList");
    render(<SiteList onOpen={() => undefined} />);
    expect(await screen.findByText("Kancelaria prawna")).toBeTruthy();
    expect(screen.getByText("Restauracja i gastronomia")).toBeTruthy();
    // Nazwa techniczna zostaje widoczna — to ona idzie do agenta.
    expect(screen.getByText("law-firm")).toBeTruthy();
  });

  it("obok presetów pokazuje gotowe witryny z kolekcji, z licencją przy każdej", async () => {
    const { SiteList } = await import("../modules/strony/SiteList");
    render(<SiteList onOpen={() => undefined} />);
    expect(await screen.findByText("Astro Blog")).toBeTruthy();
    expect(screen.getByText("8 podstron · MIT")).toBeTruthy();
  });

  it("nie pokazuje sekcji układów, gdy zestawu nie ma na serwerze", async () => {
    katalogKitu.mockResolvedValue({ dostepny: false, presety: [], motywy: [], szablony: [] });
    const { SiteList } = await import("../modules/strony/SiteList");
    render(<SiteList onOpen={() => undefined} />);
    await waitFor(() => expect(listaStron).toHaveBeenCalled());
    expect(screen.queryByText("Albo zacznij od gotowego układu")).toBeNull();
    expect(screen.queryByText("Gotowe witryny z kolekcji")).toBeNull();
  });
});

describe("moduł Studio bez wgranego nagrania", () => {
  it("wypisuje, co zrobi z nagraniem", async () => {
    const { module: studio } = await import("../modules/studio");
    render(<studio.Page openConversation={() => undefined} openModule={() => undefined} openChat={() => undefined} />);
    expect(screen.getByText("Co Studio zrobi z nagraniem")).toBeTruthy();
    expect(screen.getByText("Transkrypcja")).toBeTruthy();
    expect(screen.getByText("Napisy")).toBeTruthy();
    expect(screen.getByText("Kompresja wideo")).toBeTruthy();
  });
});


describe("moduł Obrazy bez wgranego zdjęcia", () => {
  it("mówi, co zrobi ze zdjęciem, zamiast pokazywać samą ramkę na plik", async () => {
    const { module: obrazy } = await import("../modules/obrazy");
    render(<obrazy.Page openConversation={() => undefined} openModule={() => undefined} openChat={() => undefined} />);
    expect(screen.getByText("Zdjęcie produktu bez tła")).toBeTruthy();
    expect(screen.getByText("Małe zdjęcie do druku")).toBeTruthy();
  });
});

describe("znaczniki strony dla wyszukiwarek", () => {
  it("ekran publiczny dostaje indeksowanie, a ekran za logowaniem — noindex", async () => {
    // Regresja: moduł `seo` istniał, ale nikt go nie wołał, więc wyszukiwarka widziała
    // znaczniki z `index.html` niezależnie od tego, co jest na ekranie.
    const { applyIndexing } = await import("../seo");
    const roboty = () => document.querySelector('meta[name="robots"]')?.getAttribute("content");

    applyIndexing("landing");
    expect(roboty()).toContain("index, follow");
    expect(document.title.length).toBeGreaterThan(0);

    applyIndexing("app");
    expect(roboty()).toContain("noindex");
  });
});
