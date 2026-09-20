// Esc zatrzymuje bieg agenta, ale nie wtedy, gdy klawisz należy do otwartego okna.

import { describe, expect, it } from "vitest";
import { czyZatrzymac } from "../shell/useEscZatrzymaj";

function dokument(html: string): Document {
  const d = document.implementation.createHTMLDocument("proba");
  d.body.innerHTML = html;
  return d;
}

describe("czyZatrzymac", () => {
  it("zatrzymuje bieg przy pustym ekranie", () => {
    expect(czyZatrzymac({ key: "Escape", defaultPrevented: false }, dokument(""))).toBe(true);
  });

  it("pomija inne klawisze", () => {
    expect(czyZatrzymac({ key: "Enter", defaultPrevented: false }, dokument(""))).toBe(false);
  });

  it("pomija zdarzenie już obsłużone", () => {
    expect(czyZatrzymac({ key: "Escape", defaultPrevented: true }, dokument(""))).toBe(false);
  });

  it("oddaje klawisz otwartemu oknu dialogowemu", () => {
    expect(czyZatrzymac({ key: "Escape", defaultPrevented: false }, dokument('<div role="dialog"></div>'))).toBe(false);
  });

  it("oddaje klawisz otwartemu elementowi dialog", () => {
    expect(czyZatrzymac({ key: "Escape", defaultPrevented: false }, dokument("<dialog open></dialog>"))).toBe(false);
  });
});
