import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useOknoModalne } from "../useOknoModalne";

afterEach(cleanup);

function Nakladka({ onZamknij }: { onZamknij: () => void }) {
  const nakladka = useRef<HTMLDivElement>(null);
  useOknoModalne(nakladka, onZamknij);
  return (
    <div ref={nakladka} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Podgląd">
      <button type="button">Pobierz</button>
      <button type="button">Zamknij</button>
    </div>
  );
}

function Ekran({ otwarte, onZamknij }: { otwarte: boolean; onZamknij: () => void }) {
  return (
    <>
      <button type="button">Otwórz podgląd</button>
      {otwarte ? <Nakladka onZamknij={onZamknij} /> : null}
    </>
  );
}

describe("useOknoModalne", () => {
  it("przenosi fokus do pierwszej kontrolki nakładki", () => {
    render(<Ekran otwarte onZamknij={() => undefined} />);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Pobierz" }));
  });

  it("zawraca tabulację z ostatniej kontrolki na pierwszą", () => {
    render(<Ekran otwarte onZamknij={() => undefined} />);
    const ostatnia = screen.getByRole("button", { name: "Zamknij" });
    ostatnia.focus();
    fireEvent.keyDown(ostatnia, { key: "Tab" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Pobierz" }));
  });

  it("zawraca Shift+Tab z pierwszej kontrolki na ostatnią", () => {
    render(<Ekran otwarte onZamknij={() => undefined} />);
    const pierwsza = screen.getByRole("button", { name: "Pobierz" });
    fireEvent.keyDown(pierwsza, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Zamknij" }));
  });

  it("zamyka nakładkę klawiszem Esc", () => {
    const zamknij = vi.fn();
    render(<Ekran otwarte onZamknij={zamknij} />);
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(zamknij).toHaveBeenCalledOnce();
  });

  it("oddaje fokus elementowi, z którego nakładkę otwarto", () => {
    const { rerender } = render(<Ekran otwarte={false} onZamknij={() => undefined} />);
    const wyzwalacz = screen.getByRole("button", { name: "Otwórz podgląd" });
    wyzwalacz.focus();
    rerender(<Ekran otwarte onZamknij={() => undefined} />);
    expect(document.activeElement).not.toBe(wyzwalacz);
    rerender(<Ekran otwarte={false} onZamknij={() => undefined} />);
    expect(document.activeElement).toBe(wyzwalacz);
  });
});
