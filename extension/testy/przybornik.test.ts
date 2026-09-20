// Przybornik zaznaczenia: pojawia się przy zaznaczeniu, wykonuje skrót, oddaje wynik.
//
// Testy pilnują tego, co widzi i robi człowiek: że przybornik stoi schowany, dopóki
// nic nie jest zaznaczone, że pokazuje skróty użytkownika, że wysyła jego polecenie
// wraz z zaznaczeniem i że kliknięcie obok wszystko zamyka.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { Przybornik } from "../src/tresc/przybornik";
import { DOMYSLNE, oczyscSkroty, type Ustawienia } from "../src/wspolne/ustawienia";

/** Podstawia zaznaczenie o znanym położeniu — jsdom nie liczy układu strony. */
function zaznacz(tekst: string): void {
  const zakres = {
    getBoundingClientRect: () => ({ left: 100, top: 200, width: 80, height: 18 }) as DOMRect,
  };
  vi.spyOn(document, "getSelection").mockReturnValue({
    toString: () => tekst,
    rangeCount: tekst ? 1 : 0,
    getRangeAt: () => zakres as unknown as Range,
  } as unknown as Selection);
}

function ustawienia(skroty = DOMYSLNE.skroty): Ustawienia {
  return { ...DOMYSLNE, skroty, przybornik: true };
}

type Wykonanie = (polecenie: string, tekst: string) => Promise<{ wynik: string } | { blad: string }>;

function zamontuj(wykonaj: Wykonanie = vi.fn(async () => ({ wynik: "gotowe" }))) {
  const gospodarz = document.createElement("div");
  document.body.append(gospodarz);
  // Drzewo cienia jest zamknięte, więc do sprawdzania sięgamy po uchwyt z attachShadow.
  const oryginal = gospodarz.attachShadow.bind(gospodarz);
  let cien: ShadowRoot | null = null;
  gospodarz.attachShadow = (init) => {
    cien = oryginal({ ...init, mode: "open" });
    return cien;
  };
  const przybornik = new Przybornik({ wykonaj }, gospodarz);
  return { przybornik, cien: cien as unknown as ShadowRoot, wykonaj };
}

function przyciski(cien: ShadowRoot): HTMLButtonElement[] {
  const pasek = cien.querySelector(".pasek") as HTMLDivElement;
  return pasek.hidden ? [] : [...pasek.querySelectorAll("button")];
}

describe("przybornik zaznaczenia", () => {
  beforeEach(() => {
    document.body.replaceChildren();
    vi.restoreAllMocks();
  });

  it("stoi schowany, dopóki nic nie jest zaznaczone", () => {
    const { przybornik, cien } = zamontuj();
    przybornik.ustaw(ustawienia());
    zaznacz("");
    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    expect((cien.querySelector(".pasek") as HTMLDivElement).hidden).toBe(true);
  });

  it("pokazuje skróty użytkownika po zaznaczeniu tekstu", async () => {
    const { przybornik, cien } = zamontuj();
    przybornik.ustaw(ustawienia([{ id: "a", nazwa: "Przetłumacz", polecenie: "Przetłumacz to." }]));
    zaznacz("fragment do przetłumaczenia");
    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    await vi.waitFor(() => expect(przyciski(cien)).toHaveLength(1));
    expect(przyciski(cien)[0].textContent).toBe("Przetłumacz");
  });

  it("nie reaguje na zaznaczenie krótsze niż trzy znaki", async () => {
    const { przybornik, cien } = zamontuj();
    przybornik.ustaw(ustawienia());
    zaznacz("ab");
    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    await new Promise((gotowe) => setTimeout(gotowe, 5));
    expect(przyciski(cien)).toHaveLength(0);
  });

  it("wysyła polecenie skrótu razem z zaznaczeniem i pokazuje wynik", async () => {
    const wykonaj = vi.fn(async () => ({ wynik: "Przetłumaczona treść" }));
    const { przybornik, cien } = zamontuj(wykonaj);
    przybornik.ustaw(ustawienia([{ id: "a", nazwa: "Przetłumacz", polecenie: "Przetłumacz to." }]));
    zaznacz("source text");
    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    await vi.waitFor(() => expect(przyciski(cien)).toHaveLength(1));

    przyciski(cien)[0].click();
    await vi.waitFor(() => {
      expect((cien.querySelector(".baner") as HTMLDivElement).hidden).toBe(false);
      expect((cien.querySelector(".tresc") as HTMLDivElement).textContent).toBe("Przetłumaczona treść");
    });
    expect(wykonaj).toHaveBeenCalledWith("Przetłumacz to.", "source text");
  });

  it("pokazuje powód, gdy akcja się nie udała", async () => {
    const wykonaj = vi.fn(async () => ({ blad: "Brak połączenia z Nexusem." }));
    const { przybornik, cien } = zamontuj(wykonaj);
    przybornik.ustaw(ustawienia([{ id: "a", nazwa: "Skróć", polecenie: "Skróć." }]));
    zaznacz("dowolny tekst");
    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    await vi.waitFor(() => expect(przyciski(cien)).toHaveLength(1));

    przyciski(cien)[0].click();
    await vi.waitFor(() =>
      expect((cien.querySelector(".tresc") as HTMLDivElement).textContent).toBe("Brak połączenia z Nexusem."),
    );
    // Nie ma czego kopiować, więc przycisk kopiowania znika.
    expect((cien.querySelector(".stopka button") as HTMLButtonElement).hidden).toBe(true);
  });

  it("kliknięcie poza przybornikiem zamyka go", async () => {
    const { przybornik, cien } = zamontuj();
    przybornik.ustaw(ustawienia());
    zaznacz("fragment tekstu");
    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    await vi.waitFor(() => expect(przyciski(cien).length).toBeGreaterThan(0));

    document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    expect((cien.querySelector(".pasek") as HTMLDivElement).hidden).toBe(true);
    expect((cien.querySelector(".baner") as HTMLDivElement).hidden).toBe(true);
  });

  it("wyłączony w ustawieniach nie pokazuje się wcale", async () => {
    const { przybornik, cien } = zamontuj();
    przybornik.ustaw({ ...ustawienia(), przybornik: false });
    zaznacz("fragment tekstu");
    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    await new Promise((gotowe) => setTimeout(gotowe, 5));
    expect(przyciski(cien)).toHaveLength(0);
  });
});

describe("oczyszczanie skrótów", () => {
  it("odrzuca pozycje bez nazwy albo bez polecenia", () => {
    const wynik = oczyscSkroty([
      { id: "a", nazwa: "Dobry", polecenie: "Zrób coś." },
      { id: "b", nazwa: "   ", polecenie: "Puste imię." },
      { id: "c", nazwa: "Bez polecenia", polecenie: "" },
      "nie obiekt",
    ]);
    expect(wynik.map((s) => s.nazwa)).toEqual(["Dobry"]);
  });

  it("usuwa powtórzone identyfikatory", () => {
    const wynik = oczyscSkroty([
      { id: "a", nazwa: "Pierwszy", polecenie: "Raz." },
      { id: "a", nazwa: "Drugi", polecenie: "Dwa." },
    ]);
    expect(wynik).toHaveLength(1);
  });

  it("pusta lista zostaje pusta — to wybór użytkownika, nie brak ustawień", () => {
    expect(oczyscSkroty([])).toEqual([]);
  });

  it("brak ustawienia daje zestaw startowy", () => {
    expect(oczyscSkroty(undefined).length).toBeGreaterThan(0);
  });
});
