import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, renderHook, screen, waitFor } from "@testing-library/react";
import { Kredyty } from "../platnosci/Kredyty";
import { useChat } from "../shell/useChat";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** Dopasowanie liczby niezależne od spacji, jakiej użyje `toLocaleString("pl-PL")`. */
function liczba(wartosc: string) {
  return (tresc: string) => tresc.replace(/[\s\u00a0\u202f]/g, "") === wartosc;
}

function odpowiedz(dane: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(dane), { headers: { "content-type": "application/json" } })),
  );
}

const PELNE = {
  saldo: 1840,
  przydzielone: 2000,
  zuzyte: 160,
  historia: [
    { id: "1", zmiana: -160, saldo_po: 1840, powod: "przebieg", opis: "", run_id: "r1", kiedy: "2026-09-20T10:00:00Z" },
    { id: "2", zmiana: 2000, saldo_po: 2000, powod: "start", opis: "", run_id: null, kiedy: "2026-09-19T10:00:00Z" },
  ],
};

describe("panel kredytów", () => {
  it("pokazuje saldo i historię po polsku", async () => {
    odpowiedz(PELNE);
    render(<Kredyty />);
    await waitFor(() => expect(screen.getByText(liczba("1840"))).toBeTruthy());
    expect(screen.getByText("Praca agenta")).toBeTruthy();
    expect(screen.getByText("Przydział startowy")).toBeTruthy();
    expect(screen.getByText(liczba("+2000"))).toBeTruthy();
  });

  it("puste saldo mówi wprost, że zadania staną do czasu doładowania", async () => {
    odpowiedz({ ...PELNE, saldo: 0 });
    render(<Kredyty />);
    await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/doładowaniu/));
  });

  it("niskie saldo ostrzega, zanim zadania staną", async () => {
    odpowiedz({ ...PELNE, saldo: 50 });
    render(<Kredyty />);
    await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/niewiele kredytów/));
  });

  it("nie pokazuje niczego o silniku ani o kontach usługodawcy", async () => {
    odpowiedz(PELNE);
    const { container } = render(<Kredyty />);
    await waitFor(() => expect(screen.getByText(liczba("1840"))).toBeTruthy());
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
          ? new Response(JSON.stringify({ detail: "Skończyły się kredyty na tym koncie." }), {
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
    expect(result.current.error).toMatch(/Skończyły się kredyty/);
  });
});
