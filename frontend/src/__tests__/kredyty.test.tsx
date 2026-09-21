import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, renderHook, screen, waitFor } from "@testing-library/react";
import { Kredyty } from "../platnosci/Kredyty";
import { useChat } from "../shell/useChat";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function odpowiedz(dane: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(dane), { headers: { "content-type": "application/json" } })),
  );
}

const DOLADOWANIE = {
  minimum_gr: 1000,
  maksimum_gr: 500_000,
  kwoty_szybkie_gr: [2000, 5000, 7000, 15_000],
  sprzedaz: true,
};

const PELNE = {
  zuzycie: 0.08,
  stan: "w_porzadku",
  wyczerpane: false,
  historia: [
    { powod: "przebieg", opis: "", kiedy: "2026-09-20T10:00:00Z" },
    { powod: "start", opis: "", kiedy: "2026-09-19T10:00:00Z" },
  ],
  doladowanie: DOLADOWANIE,
};

describe("panel wykorzystania dostępu", () => {
  it("pokazuje pasek i historię po polsku, bez liczb", async () => {
    odpowiedz(PELNE);
    const { container } = render(<Kredyty />);
    await waitFor(() => expect(screen.getByRole("meter", { name: "Wykorzystanie dostępu" })).toBeTruthy());
    expect(screen.getByText("Praca agenta")).toBeTruthy();
    expect(screen.getByText("Dostęp na start")).toBeTruthy();
    // Kredyt jest jednostką rozliczeniową między nami a dostawcą — nie pada na ekranie.
    expect((container.textContent ?? "").toLowerCase()).not.toContain("kredyt");
  });

  it("wyczerpany dostęp mówi wprost, że zadania staną", async () => {
    odpowiedz({ ...PELNE, zuzycie: 1, stan: "wyczerpany", wyczerpane: true });
    render(<Kredyty />);
    await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/wyczerpał/));
  });

  it("kończący się dostęp ostrzega, zanim zadania staną", async () => {
    odpowiedz({ ...PELNE, zuzycie: 0.93, stan: "konczy_sie" });
    render(<Kredyty />);
    await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/dobiega końca/));
  });

  it("nie pokazuje niczego o silniku ani o kontach usługodawcy", async () => {
    odpowiedz(PELNE);
    const { container } = render(<Kredyty />);
    await waitFor(() => expect(screen.getByRole("meter", { name: "Wykorzystanie dostępu" })).toBeTruthy());
    const tresc = (container.textContent ?? "").toLowerCase();
    for (const slowo of ["claude", "anthropic", "limit 5", "token", "api"]) {
      expect(tresc).not.toContain(slowo);
    }
  });
});

describe("odmowa z braku kredytów w rozmowie", () => {
  it("jest osobnym stanem, nie zwykłym błędem", async () => {
    // Rozmowa powstaje, dopiero wysłanie wiadomości kończy się odmową 402.
    vi.stubGlobal(
      "fetch",
      vi.fn(async (adres: string) =>
        String(adres).endsWith("/messages")
          ? new Response(JSON.stringify({ detail: "Dostęp na tym koncie się wyczerpał." }), {
              status: 402,
              headers: { "content-type": "application/json" },
            })
          : new Response(JSON.stringify({ id: "r1", title: "Nowa", updated_at: "", active: false }), {
              headers: { "content-type": "application/json" },
            }),
      ),
    );
    const { result } = renderHook(() => useChat({ onUnauthorized: vi.fn() }));
    await act(async () => {
      await result.current.send("policz to", []);
    });
    await waitFor(() => expect(result.current.brakKredytow).toBe(true));
    expect(result.current.error).toMatch(/się wyczerpał/);
  });
});
