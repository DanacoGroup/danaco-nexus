import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PlikiPage } from "../modules/pliki/PlikiPage";
import { module as modulPlikow } from "../modules/pliki";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const KATALOGI = [
  { id: "k1", parent_id: null, nazwa: "Faktury", opis: "", rodzaj: "projekt", kolor: "", przypiety: true, plikow: 2, updated_at: "2026-09-20T10:00:00Z" },
  { id: "k2", parent_id: null, nazwa: "Zdjęcia z wakacji", opis: "", rodzaj: "katalog", kolor: "", przypiety: false, plikow: 0, updated_at: "2026-09-20T10:00:00Z" },
];

const ZAWARTOSC = {
  pliki: [
    { id: "p1", name: "scan_0012.pdf", tytul: "Umowa najmu", mime: "application/pdf", size: 1024, created_at: "2026-09-20T10:00:00Z", katalog_id: "k1" },
    { id: "p2", name: "morze.jpg", tytul: "", mime: "image/jpeg", size: 2048, created_at: "2026-09-19T10:00:00Z", katalog_id: null },
  ],
  przestrzen: { zajete: 3072, limit: 1073741824, opis_limitu: "1 GB", plan: "Osobisty" },
};

function serwer(zawartosc = ZAWARTOSC) {
  const wywolania: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      wywolania.push(String(url));
      const dane = String(url).includes("/katalogi") ? KATALOGI : zawartosc;
      return new Response(JSON.stringify(dane), { headers: { "content-type": "application/json" } });
    }),
  );
  return wywolania;
}

describe("przestrzeń plików", () => {
  it("pokazuje katalogi użytkownika, pliki i zajęte miejsce", async () => {
    serwer();
    render(<PlikiPage />);
    await waitFor(() => expect(screen.getByText("Faktury")).toBeTruthy());
    expect(screen.getByText("Zdjęcia z wakacji")).toBeTruthy();
    // Własny tytuł wygrywa z nazwą z dysku, ale nazwa nadal jest widoczna.
    expect(screen.getByText("Umowa najmu")).toBeTruthy();
    expect(screen.getByText("scan_0012.pdf")).toBeTruthy();
    expect(screen.getByText("morze.jpg")).toBeTruthy();
    expect(screen.getByText("z 1 GB")).toBeTruthy();
    expect(screen.getByText("Plan Osobisty")).toBeTruthy();
  });

  it("filtr rodzaju pyta serwer o wskazaną grupę", async () => {
    const wywolania = serwer();
    render(<PlikiPage />);
    await waitFor(() => expect(screen.getByText("Faktury")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Zdjęcia" }));
    await waitFor(() => expect(wywolania.some((url) => url.includes("rodzaj=zdjecia"))).toBe(true));
  });

  it("wyszukiwanie trafia do zapytania", async () => {
    const wywolania = serwer();
    render(<PlikiPage />);
    await waitFor(() => expect(screen.getByText("Faktury")).toBeTruthy());
    fireEvent.change(screen.getByPlaceholderText("Szukaj po nazwie…"), { target: { value: "umowa" } });
    await waitFor(() => expect(wywolania.some((url) => url.includes("q=umowa"))).toBe(true), { timeout: 2000 });
  });

  it("pusty katalog tłumaczy, co zrobić, zamiast pokazywać pustkę", async () => {
    serwer({ pliki: [], przestrzen: ZAWARTOSC.przestrzen });
    render(<PlikiPage />);
    await waitFor(() => expect(screen.getByText("Tu jeszcze nic nie ma")).toBeTruthy());
    expect(screen.getByText(/Dodaj pliki albo poproś Nexusa/)).toBeTruthy();
  });

  it("moduł ma krótką etykietę mieszczącą się w pasku", () => {
    expect(modulPlikow.id).toBe("pliki");
    expect(modulPlikow.label.length).toBeLessThanOrEqual(9);
  });
});
