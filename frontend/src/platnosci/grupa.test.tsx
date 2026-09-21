// Panel grupy: co widzi założyciel, co widzi członek i czego nikt nie zrobi przypadkiem.
//
// Plan „Grupa” dawało się kupić, ale nie dawało się nikogo do grupy dodać. Testy pilnują
// tego, co w tym panelu kosztuje pieniądze albo odbiera komuś dostęp: kto może zapraszać,
// kto kogo usuwa i czy rzeczy nieodwracalne nie stoją na wierzchu jako zwykłe przyciski.

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Grupa } from "./Grupa";
import { grupaApi, type GrupaInfo } from "./api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const SZEF = {
  uzytkownik_id: "1",
  email: "szef@example.com",
  nazwa: "Szef",
  rola: "zalozyciel" as const,
  to_ja: true,
};
const PRACOWNIK = {
  uzytkownik_id: "2",
  email: "pracownik@example.com",
  nazwa: "Pracownik",
  rola: "czlonek" as const,
  to_ja: false,
};

function grupa(nadpisz: Partial<GrupaInfo> = {}): GrupaInfo {
  return {
    id: "g1",
    nazwa: "Kancelaria",
    jestem_zalozycielem: true,
    miejsca: 5,
    czlonkowie: [SZEF, PRACOWNIK],
    zaproszenia: [],
    ...nadpisz,
  };
}

describe("panel grupy", () => {
  it("bez grupy tłumaczy, na czym polega plan, i pozwala ją założyć", async () => {
    vi.spyOn(grupaApi, "moja").mockResolvedValue({ grupa: null, miejsca: 5 });
    const zaloz = vi.spyOn(grupaApi, "zaloz").mockResolvedValue({ grupa: grupa() });
    render(<Grupa />);
    await screen.findByText(/kupuje ją\s+założyciel/);
    fireEvent.change(screen.getByLabelText("Nazwa grupy"), { target: { value: "Kancelaria" } });
    fireEvent.click(screen.getByRole("button", { name: "Załóż grupę" }));
    await waitFor(() => expect(zaloz).toHaveBeenCalledWith("Kancelaria"));
  });

  it("założycielowi mówi wprost, że to z jego puli schodzi praca całej grupy", async () => {
    vi.spyOn(grupaApi, "moja").mockResolvedValue({ grupa: grupa() });
    render(<Grupa />);
    expect(await screen.findByText(/z Twojej puli dostępu/)).toBeTruthy();
    expect(screen.getByText(/2 z 5 miejsc/)).toBeTruthy();
  });

  it("członkowi nie pokazuje zapraszania ani rozwiązania grupy", async () => {
    vi.spyOn(grupaApi, "moja").mockResolvedValue({
      grupa: grupa({ jestem_zalozycielem: false, czlonkowie: [{ ...SZEF, to_ja: false }, { ...PRACOWNIK, to_ja: true }] }),
    });
    render(<Grupa />);
    await screen.findByText(/wspólnej puli założyciela/);
    expect(screen.queryByRole("button", { name: "Zaproś" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Rozwiąż grupę" })).toBeNull();
  });

  it("usunięcie i przekazanie roli stoją pod trzema kropkami, a nie na wierzchu", async () => {
    vi.spyOn(grupaApi, "moja").mockResolvedValue({ grupa: grupa() });
    render(<Grupa />);
    await screen.findByText("Kancelaria");
    expect(screen.queryByRole("menuitem", { name: "Usuń z grupy" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Działania: pracownik@example.com" }));
    expect(screen.getByRole("menuitem", { name: "Usuń z grupy" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "Przekaż rolę założyciela" })).toBeTruthy();
  });

  it("założyciel nie ma przy sobie żadnych działań — najpierw musi przekazać rolę", async () => {
    vi.spyOn(grupaApi, "moja").mockResolvedValue({ grupa: grupa() });
    render(<Grupa />);
    await screen.findByText("Kancelaria");
    expect(screen.queryByRole("button", { name: "Działania: szef@example.com" })).toBeNull();
  });

  it("zaproszenie oddaje odsyłacz do przekazania, bo poczta bywa nieskonfigurowana", async () => {
    vi.spyOn(grupaApi, "moja").mockResolvedValue({ grupa: grupa() });
    vi.spyOn(grupaApi, "zapros").mockResolvedValue({
      grupa: grupa({ zaproszenia: [{ email: "nowy@example.com", wygasa: "2026-10-04T00:00:00Z" }] }),
      odsylacz: "/portal/grupa?zaproszenie=abc",
    });
    render(<Grupa />);
    await screen.findByText("Kancelaria");
    fireEvent.change(screen.getByLabelText("Adres osoby zapraszanej"), {
      target: { value: "nowy@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Zaproś" }));
    expect(await screen.findByText(/\/portal\/grupa\?zaproszenie=abc/)).toBeTruthy();
  });

  it("przy komplecie miejsc nie da się zaprosić kolejnej osoby", async () => {
    vi.spyOn(grupaApi, "moja").mockResolvedValue({
      grupa: grupa({ miejsca: 2 }),
    });
    render(<Grupa />);
    await screen.findByText(/komplet/);
    expect(screen.getByRole("button", { name: "Zaproś" }).hasAttribute("disabled")).toBe(true);
  });
});

describe("cena planu grupowego", () => {
  it("jest podawana jako cena za osobę, a nie za całą grupę", async () => {
    // 49 zł obok samego „/ miesiąc” czytałoby się jak rachunek całej grupy — a to
    // kilka razy mniej, niż klient naprawdę zapłaci.
    const { Plany } = await import("./Plany");
    const { PLAN_ZA_UZYTKOWNIKA } = await import("./api");
    const plan = {
      kod: PLAN_ZA_UZYTKOWNIKA,
      nazwa: "Grupa",
      opis: "Dla rodziny albo małego zespołu.",
      bezplatny: false,
      znacznik: "",
      zawartosc: [],
      limity: { plik_mb: 2048 },
      ceny: { miesiac: 4900, rok: 49000 },
      do_kupienia: { miesiac: true, rok: true },
      okres_probny_dni: 0,
    } as unknown as Parameters<typeof Plany>[0]["cennik"]["plany"][number];
    const cennik = {
      waluta: "pln",
      plany: [plan],
      sprzedaz: { aktywna: true, komunikat: "" } as unknown,
      subskrypcja: { stan: "brak", plan: "", okres: "", faktura_do_zaplaty: null } as unknown,
    } as unknown as Parameters<typeof Plany>[0]["cennik"];
    render(<Plany cennik={cennik} />);
    expect(screen.getByText(/za osobę/)).toBeTruthy();
  });
});
