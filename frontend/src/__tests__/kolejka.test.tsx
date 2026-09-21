// Zadanie stojące w kolejce wygląda jak praca w toku: te same migające kropki. Gdy procesu
// roboczego nie ma, użytkownik patrzy na nie w nieskończoność i nic mu tego nie prostuje.
// Ten test pilnuje komunikatu, który po progu mówi wprost, że zadanie czeka.

import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AssistantMessage } from "../components/Turns";
import type { AssistantTurn } from "../api";

function tura(status: AssistantTurn["status"]): AssistantTurn {
  return {
    type: "assistant",
    run_id: "11111111-1111-4111-8111-111111111111",
    items: [],
    status,
    error: "",
    created_at: new Date("2026-09-21T06:00:00Z").toISOString(),
  };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

describe("zadanie w kolejce", () => {
  it("milczy, zanim czekanie zrobi się nietypowe", () => {
    render(<AssistantMessage turn={tura("queued")} onPreview={() => undefined} />);

    act(() => vi.advanceTimersByTime(30_000));

    expect(screen.queryByText(/czeka w kolejce/i)).toBeNull();
  });

  it("mówi wprost, gdy zadanie stoi w kolejce dłużej niż zwykle", () => {
    render(<AssistantMessage turn={tura("queued")} onPreview={() => undefined} />);

    act(() => vi.advanceTimersByTime(60_000));

    expect(screen.getByText(/czeka w kolejce dłużej niż zwykle/i)).toBeTruthy();
  });

  it("nie odzywa się przy pracy, która już ruszyła", () => {
    render(<AssistantMessage turn={tura("running")} onPreview={() => undefined} />);

    act(() => vi.advanceTimersByTime(120_000));

    expect(screen.queryByText(/czeka w kolejce/i)).toBeNull();
  });
});

describe("nieudany i anulowany bieg", () => {
  function zTrescia(status: AssistantTurn["status"], error: string): AssistantTurn {
    return { ...tura(status), error };
  }

  it("niepowodzenie jest ogłaszane czytnikowi ekranu", () => {
    // Komunikat pojawia się **po** wysłaniu wiadomości, więc bez roli czytnik ekranu
    // przemilcza go i osoba niewidoma zostaje z ciszą zamiast z informacją o błędzie.
    render(
      <AssistantMessage
        turn={zTrescia("failed", "Coś poszło nie tak po naszej stronie.")}
        onPreview={() => undefined}
      />,
    );
    const pole = screen.getByRole("alert");
    expect(pole.textContent).toContain("Coś poszło nie tak");
  });

  it("anulowanie ogłasza się spokojnie, bo wywołał je użytkownik", () => {
    render(
      <AssistantMessage turn={zTrescia("cancelled", "Zadanie zatrzymane.")} onPreview={() => undefined} />,
    );
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("Zadanie zatrzymane.");
  });
});
