import { describe, expect, it } from "vitest";
import { speakable, takeSentences } from "../voice/sentences";

describe("takeSentences", () => {
  it("returns complete sentences and keeps the unfinished tail", () => {
    const text = "Sprawdziłem fakturę numer siedem. Kwota brutto wynosi tysiąc osiemset. Termin";
    const { chunks, next } = takeSentences(text, 0, false);
    expect(chunks).toEqual(["Sprawdziłem fakturę numer siedem.", "Kwota brutto wynosi tysiąc osiemset."]);
    expect(text.slice(next).trim()).toBe("Termin");
  });

  it("joins short sentences and flushes the rest at the end", () => {
    const text = "Dobrze. Już. Zrobione w całości, plik jest gotowy";
    expect(takeSentences(text, 0, false).chunks).toEqual([]);
    expect(takeSentences(text, 0, true).chunks).toEqual(["Dobrze. Już. Zrobione w całości, plik jest gotowy"]);
  });

  it("continues from the previous position", () => {
    const text = "Pierwsze zdanie jest dość długie. Drugie zdanie też jest dość długie.";
    const first = takeSentences(text, 0, false);
    expect(first.chunks).toEqual(["Pierwsze zdanie jest dość długie.", "Drugie zdanie też jest dość długie."]);
    expect(takeSentences(text, first.next, true).chunks).toEqual([]);
  });

  it("does not split numbers with decimal separators", () => {
    const text = "Kwota wynosi 1 845.00 zł brutto za całość usługi.";
    expect(takeSentences(text, 0, false).chunks).toEqual(["Kwota wynosi 1 845.00 zł brutto za całość usługi."]);
  });
});

describe("speakable", () => {
  it("removes markdown and code", () => {
    expect(speakable("**Kwota:** 10 zł ```kod``` [link](http://x)").replace(/\s+/g, " ").trim()).toBe(
      "Kwota: 10 zł link",
    );
  });
});
