import { afterEach, describe, expect, it, vi } from "vitest";
import { SledzeniePol, jestEdytowalne, opisPola, wstawTekst } from "../src/tresc/wstawianie";

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

describe("rozpoznawanie pól", () => {
  it("akceptuje pola tekstowe i edytory, odrzuca pozostałe", () => {
    document.body.innerHTML = `
      <textarea id="a"></textarea><textarea id="b" readonly></textarea>
      <input id="c"><input id="d" type="email"><input id="e" type="checkbox"><input id="f" type="password">
      <div id="g" contenteditable="true"><p id="h">x</p></div><div id="i">zwykły</div>`;
    const el = (id: string) => document.getElementById(id);
    expect(jestEdytowalne(el("a"))).toBe(true);
    expect(jestEdytowalne(el("b"))).toBe(false);
    expect(jestEdytowalne(el("c"))).toBe(true);
    expect(jestEdytowalne(el("d"))).toBe(true);
    expect(jestEdytowalne(el("e"))).toBe(false);
    expect(jestEdytowalne(el("f"))).toBe(false);
    expect(jestEdytowalne(el("g"))).toBe(true);
    expect(jestEdytowalne(el("h"))).toBe(true);
    expect(jestEdytowalne(el("i"))).toBe(false);
  });

  it("opisuje pole etykietą", () => {
    document.body.innerHTML = `<label for="o">Twoja odpowiedź</label><textarea id="o"></textarea><div contenteditable aria-label="Treść"></div>`;
    expect(opisPola(document.getElementById("o")!)).toBe("pole „Twoja odpowiedź”");
    expect(opisPola(document.querySelector("[contenteditable]") as HTMLElement)).toBe("edytor „Treść”");
  });
});

describe("wstawianie tekstu", () => {
  it("wstawia w miejscu kursora w textarea i wysyła input oraz change", () => {
    document.body.innerHTML = `<textarea id="t">Dzień dobry,  Pozdrawiamy</textarea>`;
    const pole = document.getElementById("t") as HTMLTextAreaElement;
    const zdarzenia: string[] = [];
    pole.addEventListener("input", (e) => zdarzenia.push(`input:${(e as InputEvent).data}`));
    pole.addEventListener("change", () => zdarzenia.push("change"));
    pole.setSelectionRange(13, 13);
    expect(wstawTekst(pole, "dziękujemy!")).toBe(true);
    expect(pole.value).toBe("Dzień dobry, dziękujemy! Pozdrawiamy");
    expect(pole.selectionStart).toBe(24);
    expect(zdarzenia).toEqual(["input:dziękujemy!", "change"]);
  });

  it("zastępuje zaznaczenie i – na życzenie – całą treść", () => {
    document.body.innerHTML = `<input id="i" value="stary tekst">`;
    const pole = document.getElementById("i") as HTMLInputElement;
    pole.setSelectionRange(0, 5);
    wstawTekst(pole, "nowy");
    expect(pole.value).toBe("nowy tekst");
    wstawTekst(pole, "całkiem inny", { calosc: true });
    expect(pole.value).toBe("całkiem inny");
  });

  it("omija śledzenie wartości frameworka (setter na instancji)", () => {
    document.body.innerHTML = `<textarea id="t"></textarea>`;
    const pole = document.getElementById("t") as HTMLTextAreaElement;
    // Symulacja Reacta: własny setter na instancji, który nie zmienia widocznej wartości.
    let sledzona = "";
    Object.defineProperty(pole, "value", {
      configurable: true,
      get: () => Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.get!.call(pole),
      set: (v: string) => {
        sledzona = v;
      },
    });
    expect(wstawTekst(pole, "Odpowiedź")).toBe(true);
    expect(pole.value).toBe("Odpowiedź");
    expect(sledzona).toBe("");
  });

  it("korzysta z execCommand, gdy przeglądarka go obsługuje", () => {
    document.body.innerHTML = `<textarea id="t">abc</textarea>`;
    const pole = document.getElementById("t") as HTMLTextAreaElement;
    pole.setSelectionRange(3, 3);
    const exec = vi.fn((_polecenie: string, _ui: boolean, tekst: string) => {
      pole.setRangeText(tekst, pole.selectionStart!, pole.selectionEnd!, "end");
      return true;
    });
    Object.defineProperty(document, "execCommand", { configurable: true, value: exec });
    const input = vi.fn();
    pole.addEventListener("input", input);
    expect(wstawTekst(pole, "def")).toBe(true);
    expect(exec).toHaveBeenCalledWith("insertText", false, "def");
    expect(pole.value).toBe("abcdef");
    // Prawdziwy execCommand sam wysyła input – rozszerzenie nie dubluje zdarzenia.
    expect(input).not.toHaveBeenCalled();
    delete (document as unknown as Record<string, unknown>).execCommand;
  });

  it("wstawia do edytora contenteditable z zachowaniem podziału wierszy", () => {
    document.body.innerHTML = `<div id="e" contenteditable="true"><p>Szanowna Pani,</p></div>`;
    const edytor = document.getElementById("e")!;
    const input = vi.fn();
    edytor.addEventListener("input", input);
    expect(wstawTekst(edytor, "dziękujemy za opinię.\nZapraszamy ponownie!")).toBe(true);
    expect(edytor.textContent).toBe("Szanowna Pani,dziękujemy za opinię.Zapraszamy ponownie!");
    expect(edytor.querySelectorAll("br")).toHaveLength(1);
    expect(input).toHaveBeenCalledTimes(1);
  });

  it("zastępuje całą treść edytora", () => {
    document.body.innerHTML = `<div id="e" contenteditable="true">Tekst z błendami</div>`;
    const edytor = document.getElementById("e")!;
    wstawTekst(edytor, "Tekst z błędami", { calosc: true });
    expect(edytor.textContent).toBe("Tekst z błędami");
  });
});

describe("śledzenie ostatniego pola", () => {
  it("pamięta ostatnie pole po utracie fokusu i wstawia do niego", () => {
    document.body.innerHTML = `<textarea id="a"></textarea><button id="b">x</button><danaco-nexus id="p"></danaco-nexus>`;
    const sledzenie = new SledzeniePol(document, (el) => el.tagName.toLowerCase() === "danaco-nexus");
    const zmiany: Array<HTMLElement | null> = [];
    sledzenie.naZmiane((pole) => zmiany.push(pole));
    sledzenie.podlacz();
    const pole = document.getElementById("a") as HTMLTextAreaElement;
    pole.focus();
    (document.getElementById("b") as HTMLButtonElement).focus();
    expect(sledzenie.ostatnie()).toBe(pole);
    expect(zmiany).toEqual([pole]);
    expect(sledzenie.wstaw("Odpowiedź Nexusa")).toBe(true);
    expect(pole.value).toBe("Odpowiedź Nexusa");
    sledzenie.odlacz();
  });

  it("zwraca false, gdy nie było pola (panel skopiuje do schowka)", () => {
    const sledzenie = new SledzeniePol(document);
    expect(sledzenie.wstaw("x")).toBe(false);
  });

  it("zapomina pole usunięte ze strony", () => {
    document.body.innerHTML = `<input id="a">`;
    const sledzenie = new SledzeniePol(document);
    sledzenie.podlacz();
    (document.getElementById("a") as HTMLInputElement).focus();
    document.body.innerHTML = "";
    expect(sledzenie.ostatnie()).toBeNull();
    sledzenie.odlacz();
  });

  it("wykrywa pola w otwartym Shadow DOM strony", () => {
    document.body.innerHTML = `<div id="h"></div>`;
    const cien = document.getElementById("h")!.attachShadow({ mode: "open" });
    cien.innerHTML = `<textarea></textarea>`;
    const sledzenie = new SledzeniePol(document);
    sledzenie.podlacz();
    const pole = cien.querySelector("textarea")!;
    pole.focus();
    expect(sledzenie.ostatnie()).toBe(pole);
    sledzenie.odlacz();
  });

  it("po „Popraw tekst” zastępuje całą treść pola, potem wraca do wstawiania", () => {
    document.body.innerHTML = `<textarea id="a">Tekts z błedem</textarea>`;
    const sledzenie = new SledzeniePol(document);
    sledzenie.podlacz();
    const pole = document.getElementById("a") as HTMLTextAreaElement;
    pole.focus();
    sledzenie.zastapCalosc(pole);
    sledzenie.wstaw("Tekst z błędem");
    expect(pole.value).toBe("Tekst z błędem");
    pole.setSelectionRange(pole.value.length, pole.value.length);
    sledzenie.wstaw(".");
    expect(pole.value).toBe("Tekst z błędem.");
    sledzenie.odlacz();
  });

  it("ustawia pole docelowe wskazane przez opinię", () => {
    document.body.innerHTML = `<input id="a"><div id="e" contenteditable="true"><span id="s">x</span></div>`;
    const sledzenie = new SledzeniePol(document);
    sledzenie.ustaw(document.getElementById("s"));
    expect(sledzenie.ostatnie()).toBe(document.getElementById("e"));
  });
});
