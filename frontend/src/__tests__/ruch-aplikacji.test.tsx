// Ruch w samym oknie aplikacji: znak reaguje na stan, a przełącznik „ograniczony ruch” działa.
//
// Pakiet motion był podpięty do strony produktu i do katalogu możliwości, ale w oknie
// stało płaskie logo — po aplikacji nie było widać, że cokolwiek się dzieje.

import { afterEach, describe, expect, it, beforeEach, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

// Preferencje trzymają kopię w pamięci modułu, a zapis idzie na konto — tu wystarczy echo.
vi.mock("../api", () => ({
  apiRequest: vi.fn(async (_metoda: string, _adres: string, cialo?: unknown) => cialo ?? {}),
}));
import { AssistantMessage } from "../components/Turns";
import { ograniczonyRuch, zapiszPreferencje, zastosujRuch } from "../preferencje";
import type { AssistantTurn } from "../api";

function tura(status: string): AssistantTurn {
  return { type: "assistant", run_id: "r1", items: [], status, error: "", created_at: "2026-09-20T22:00:00Z" };
}

function znak(kontener: HTMLElement): SVGElement | null {
  return kontener.querySelector("svg.znak-ruch");
}

describe("znak przy odpowiedzi", () => {
  afterEach(cleanup);
  beforeEach(async () => {
    localStorage.clear();
    await zapiszPreferencje({ ograniczony_ruch: false });
  });

  it("pulsuje, gdy agent pracuje", () => {
    const { container } = render(<AssistantMessage turn={tura("running")} onPreview={() => {}} />);
    expect(znak(container)?.getAttribute("data-moment")).toBe("mysli");
  });

  it("rozbłyska po skończonej turze — ale tylko przy ostatniej odpowiedzi", () => {
    const { container } = render(<AssistantMessage turn={tura("done")} onPreview={() => {}} ostatnia />);
    expect(znak(container)?.getAttribute("data-moment")).toBe("sukces");
    cleanup();
    // Historia rozmowy zostaje spokojna: przewijanie wstecz nie ma migać pięćdziesiąt razy.
    const starsza = render(<AssistantMessage turn={tura("done")} onPreview={() => {}} />);
    expect(znak(starsza.container)).toBeNull();
  });

  it("gaśnie przy niepowodzeniu i przy anulowaniu", () => {
    const { container } = render(<AssistantMessage turn={tura("failed")} onPreview={() => {}} />);
    expect(znak(container)?.getAttribute("data-moment")).toBe("blad");
    cleanup();
    const drugi = render(<AssistantMessage turn={tura("cancelled")} onPreview={() => {}} />);
    expect(znak(drugi.container)?.getAttribute("data-moment")).toBe("blad");
  });
});

describe("ograniczony ruch", () => {
  afterEach(async () => {
    cleanup();
    delete document.documentElement.dataset.ruch;
    // Kopia preferencji żyje w pamięci modułu — bez tego kolejny plik testowy dostaje
    // wyciszony ruch po tym.
    await zapiszPreferencje({ ograniczony_ruch: false });
  });
  beforeEach(async () => {
    localStorage.clear();
    await zapiszPreferencje({ ograniczony_ruch: false });
  });

  it("ustawienie konta zdejmuje ruch tak samo jak ustawienie systemu", async () => {
    expect(ograniczonyRuch()).toBe(false);
    await zapiszPreferencje({ ograniczony_ruch: true });
    expect(ograniczonyRuch()).toBe(true);
  });

  it("znacznik na korzeniu dokumentu pozwala wyciszyć też animacje w CSS", async () => {
    zastosujRuch();
    expect(document.documentElement.dataset.ruch).toBe("pelny");
    await zapiszPreferencje({ ograniczony_ruch: true });
    zastosujRuch();
    expect(document.documentElement.dataset.ruch).toBe("ograniczony");
  });

  it("przy ograniczonym ruchu przy odpowiedzi stoi zwykły znak, bez animacji", async () => {
    await zapiszPreferencje({ ograniczony_ruch: true });
    const { container } = render(<AssistantMessage turn={tura("running")} onPreview={() => {}} />);
    expect(znak(container)).toBeNull();
    // Zamiast animowanego znaku zostaje zwykły znaczek — miejsce awatara nie może zniknąć.
    expect(container.querySelector('img[src="/znak/symbol.svg"]')).not.toBeNull();
  });
});
