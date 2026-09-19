import { afterEach, describe, expect, it, vi } from "vitest";
import { MostNexusa } from "../src/panel/most";
import { polecenie } from "../src/panel/polecenia";
import { jestSkrotemPanelu } from "../src/tresc/skrot";
import { sprawdzPolaczenie } from "../src/wspolne/polaczenie";
import { DOMYSLNE, normalizujSerwer, poprawnyKlucz, wczytaj, zapisz } from "../src/wspolne/ustawienia";

const SERWER = "https://danaco-nexus.pl";

function ramkaNexusa() {
  const ramka = document.createElement("iframe");
  document.body.append(ramka);
  const wyslane: Array<{ dane: unknown; pochodzenie: string }> = [];
  vi.spyOn(ramka.contentWindow!, "postMessage").mockImplementation(((dane: unknown, pochodzenie: string) => {
    wyslane.push({ dane, pochodzenie });
  }) as typeof window.postMessage);
  return { ramka, wyslane };
}

function zRamki(ramka: HTMLIFrameElement, dane: unknown, origin = SERWER): void {
  window.dispatchEvent(new MessageEvent("message", { data: dane, origin, source: ramka.contentWindow }));
}

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("most do ramki Nexusa", () => {
  it("kolejkuje komunikaty do nexus:ready, potem wysyła klucz i kolejkę", () => {
    const { ramka, wyslane } = ramkaNexusa();
    const gotowy = vi.fn();
    const most = new MostNexusa(window, ramka, SERWER, "nxd_klucz", { gotowy, wstaw: vi.fn(), kopiuj: vi.fn() });
    most.wyslij({ type: "nexus:context", context: { kind: "page", title: "T", url: "https://x.pl/", text: "treść" } });
    most.wyslij({ type: "nexus:prompt", text: "Streść", send: true });
    expect(wyslane).toHaveLength(0);
    zRamki(ramka, { type: "nexus:ready" });
    expect(gotowy).toHaveBeenCalledOnce();
    expect(wyslane.map((w) => (w.dane as { type: string }).type)).toEqual(["nexus:auth", "nexus:context", "nexus:prompt"]);
    expect(wyslane[0].dane).toEqual({ type: "nexus:auth", token: "nxd_klucz" });
    expect(wyslane.every((w) => w.pochodzenie === SERWER)).toBe(true);
    most.zamknij();
  });

  it("ignoruje komunikaty z innego pochodzenia lub innego okna", () => {
    const { ramka, wyslane } = ramkaNexusa();
    const wstaw = vi.fn();
    const most = new MostNexusa(window, ramka, SERWER, "nxd_klucz", { gotowy: vi.fn(), wstaw, kopiuj: vi.fn() });
    zRamki(ramka, { type: "nexus:ready" }, "https://zly.example.com");
    window.dispatchEvent(new MessageEvent("message", { data: { type: "nexus:insert", text: "x" }, origin: SERWER, source: window }));
    expect(wyslane).toHaveLength(0);
    expect(wstaw).not.toHaveBeenCalled();
    expect(most.czyGotowy).toBe(false);
    most.zamknij();
  });

  it("przekazuje nexus:insert i nexus:copy", () => {
    const { ramka } = ramkaNexusa();
    const wstaw = vi.fn();
    const kopiuj = vi.fn();
    const most = new MostNexusa(window, ramka, SERWER, "nxd_klucz", { gotowy: vi.fn(), wstaw, kopiuj });
    zRamki(ramka, { type: "nexus:insert", text: "Dziękujemy za opinię!" });
    zRamki(ramka, { type: "nexus:copy", text: "Kopia" });
    zRamki(ramka, { type: "nexus:insert", text: 42 });
    expect(wstaw).toHaveBeenCalledExactlyOnceWith("Dziękujemy za opinię!");
    expect(kopiuj).toHaveBeenCalledExactlyOnceWith("Kopia");
    most.zamknij();
  });
});

describe("polecenia szybkich akcji", () => {
  it("dobiera treść do rodzaju i języka", () => {
    expect(polecenie("stresc")).toMatchObject({ send: true });
    expect(polecenie("odpowiedz", { rodzaj: "wiadomosc" }).text).toContain("wiadomość e-mail");
    expect(polecenie("odpowiedz").text).toContain("opinię");
    expect(polecenie("przetlumacz", { jezyk: "niemiecki" }).text).toContain("na język niemiecki");
    expect(polecenie("zapytaj")).toEqual({ text: "", send: false });
  });
});

describe("skrót klawiszowy", () => {
  const klawisz = (zmiany: Partial<KeyboardEvent>) =>
    ({ altKey: false, ctrlKey: false, shiftKey: false, metaKey: false, code: "", ...zmiany }) as KeyboardEvent;
  it("Alt+N i Ctrl+Shift+Spacja, ale nie AltGr+N (ń)", () => {
    expect(jestSkrotemPanelu(klawisz({ altKey: true, code: "KeyN" }))).toBe(true);
    expect(jestSkrotemPanelu(klawisz({ ctrlKey: true, shiftKey: true, code: "Space" }))).toBe(true);
    expect(jestSkrotemPanelu(klawisz({ altKey: true, ctrlKey: true, code: "KeyN" }))).toBe(false);
    expect(jestSkrotemPanelu(klawisz({ code: "KeyN" }))).toBe(false);
  });
});

describe("ustawienia", () => {
  it("normalizuje adres serwera i odrzuca niebezpieczne", () => {
    expect(normalizujSerwer("danaco-nexus.pl/")).toBe("https://danaco-nexus.pl");
    expect(normalizujSerwer("https://danaco-nexus.pl/?widok=panel")).toBe("https://danaco-nexus.pl");
    expect(normalizujSerwer("http://127.0.0.1:18913")).toBe("http://127.0.0.1:18913");
    expect(normalizujSerwer("http://danaco-nexus.pl")).toBeNull();
    expect(normalizujSerwer("javascript:alert(1)")).toBeNull();
    expect(normalizujSerwer("https://user:haslo@danaco-nexus.pl")).toBeNull();
  });

  it("sprawdza format klucza urządzenia", () => {
    expect(poprawnyKlucz("nxd_" + "a".repeat(43))).toBe(true);
    expect(poprawnyKlucz("nxd_krotki")).toBe(false);
    expect(poprawnyKlucz("sk-" + "a".repeat(43))).toBe(false);
  });

  it("bez chrome.storage: localStorage tylko na stronach rozszerzenia", async () => {
    expect(await wczytaj(false)).toEqual(DOMYSLNE);
    await zapisz({ jezyk: "niemiecki", szerokosc: 5000 }, true);
    expect((await wczytaj(true)).jezyk).toBe("niemiecki");
    expect((await wczytaj(true)).szerokosc).toBe(900);
    expect((await wczytaj(false)).jezyk).toBe(DOMYSLNE.jezyk);
  });

  it("korzysta z chrome.storage.local, gdy jest dostępne", async () => {
    const dane: Record<string, unknown> = {};
    vi.stubGlobal("chrome", {
      storage: {
        local: {
          get: async (klucz: string) => ({ [klucz]: dane[klucz] }),
          set: async (wartosci: Record<string, unknown>) => Object.assign(dane, wartosci),
        },
      },
    });
    await zapisz({ klucz: "nxd_" + "b".repeat(43) });
    expect((await wczytaj()).klucz).toBe("nxd_" + "b".repeat(43));
    expect(localStorage.length).toBe(0);
    vi.unstubAllGlobals();
  });
});

describe("sprawdzanie połączenia", () => {
  const odpowiedz = (status: number, body: unknown = {}) =>
    vi.fn(async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch;

  it("wysyła klucz w nagłówku Authorization bez ciasteczek", async () => {
    const pobierz = odpowiedz(200, { urzadzenie: { name: "Chrome" }, wersja: "0.1.0" });
    const wynik = await sprawdzPolaczenie(SERWER, "nxd_x", pobierz);
    expect(wynik).toEqual({ ok: true, komunikat: "Połączono jako „Chrome”. Nexus 0.1.0" });
    const [adres, opcje] = (pobierz as unknown as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect(adres).toBe(`${SERWER}/api/rozszerzenie/konfiguracja`);
    expect(opcje.credentials).toBe("omit");
    expect((opcje.headers as Record<string, string>).Authorization).toBe("Bearer nxd_x");
  });

  it("rozróżnia zły klucz, brak modułu i brak sieci", async () => {
    expect((await sprawdzPolaczenie(SERWER, "k", odpowiedz(401))).ok).toBe(false);
    expect((await sprawdzPolaczenie(SERWER, "k", odpowiedz(404))).ok).toBe(true);
    const siec = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;
    expect((await sprawdzPolaczenie(SERWER, "k", siec)).komunikat).toContain("Brak połączenia");
  });
});
