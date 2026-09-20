import { describe, expect, it, vi, afterEach } from "vitest";
import { bladMikrofonu } from "../voice/VoiceMode";

function blad(nazwa: string): DOMException {
  return new DOMException("Requested device not found", nazwa);
}

describe("bladMikrofonu", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("tłumaczy brak zgody i podpowiada, co zrobić", () => {
    expect(bladMikrofonu(blad("NotAllowedError"))).toMatch(/Zezwól na mikrofon/);
  });

  it("tłumaczy brak urządzenia zamiast pokazywać komunikat przeglądarki", () => {
    const tekst = bladMikrofonu(blad("NotFoundError"));
    expect(tekst).toMatch(/Nie znaleziono mikrofonu/);
    expect(tekst).not.toMatch(/Requested device/);
  });

  it("tłumaczy zajęte urządzenie", () => {
    expect(bladMikrofonu(blad("NotReadableError"))).toMatch(/zajęty przez inny program/);
  });

  it("w kontekście bez HTTPS kieruje na bezpieczny adres", () => {
    vi.stubGlobal("isSecureContext", false);
    expect(bladMikrofonu(new Error("boom"))).toMatch(/HTTPS/);
  });

  it("nieznany błąd zamienia na komunikat produktowy", () => {
    vi.stubGlobal("isSecureContext", true);
    const tekst = bladMikrofonu("cokolwiek");
    expect(tekst).toMatch(/Nie udało się uruchomić mikrofonu/);
  });
});
