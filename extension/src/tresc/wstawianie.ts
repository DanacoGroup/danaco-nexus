// Śledzenie ostatnio aktywnego pola tekstowego i wstawianie do niego odpowiedzi.
//
// Wstawianie najpierw próbuje document.execCommand("insertText") – działa z historią
// cofania i z edytorami (React, Gmail, Booking). Gdy przeglądarka tego nie obsłuży,
// wartość jest ustawiana natywnym setterem prototypu (omija śledzenie wartości Reacta),
// a potem wysyłane są zdarzenia input i change.

const TYPY_TEKSTOWE = new Set(["", "text", "search", "email", "url", "tel"]);

/** Czy element jest edytowalnym polem tekstowym. */
export function jestEdytowalne(el: Element | null | undefined): el is HTMLElement {
  if (!el || el.nodeType !== 1) return false;
  const tag = el.tagName;
  if (tag === "TEXTAREA") {
    const pole = el as HTMLTextAreaElement;
    return !pole.disabled && !pole.readOnly;
  }
  if (tag === "INPUT") {
    const pole = el as HTMLInputElement;
    const typ = (pole.getAttribute("type") ?? "").toLowerCase();
    return TYPY_TEKSTOWE.has(typ) && !pole.disabled && !pole.readOnly;
  }
  return edytowalnyKorzen(el) !== null;
}

/** Korzeń obszaru contenteditable, w którym leży element (albo null). */
export function edytowalnyKorzen(el: Element): HTMLElement | null {
  const html = el as HTMLElement;
  const edytowalny = html.isContentEditable || (() => {
    // jsdom nie wylicza isContentEditable – zapas na atrybutach.
    const przodek = el.closest("[contenteditable]");
    return !!przodek && przodek.getAttribute("contenteditable") !== "false";
  })();
  if (!edytowalny) return null;
  let korzen: HTMLElement = html;
  for (let w = html.parentElement; w; w = w.parentElement) {
    const atrybut = w.getAttribute("contenteditable");
    if (atrybut === "false") break;
    if (w.isContentEditable || atrybut !== null) korzen = w;
    else if (!w.closest("[contenteditable]")) break;
  }
  return korzen;
}

/** Krótki opis pola dla użytkownika („pole Odpowiedź”, „edytor treści”). */
export function opisPola(el: HTMLElement): string {
  const etykieta =
    el.getAttribute("aria-label") ||
    el.getAttribute("placeholder") ||
    (el.id ? el.ownerDocument.querySelector(`label[for="${el.id.replace(/["\\]/g, "\\$&")}"]`)?.textContent : "") ||
    el.closest("label")?.textContent ||
    el.getAttribute("name") ||
    "";
  const krotka = etykieta.replace(/\s+/g, " ").trim().slice(0, 40);
  if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") return krotka ? `pole „${krotka}”` : "pole tekstowe";
  return krotka ? `edytor „${krotka}”` : "edytor tekstu";
}

function celZdarzenia(zdarzenie: Event): Element | null {
  const sciezka = typeof zdarzenie.composedPath === "function" ? zdarzenie.composedPath() : [];
  const pierwszy = (sciezka[0] ?? zdarzenie.target) as Element | null;
  return pierwszy && pierwszy.nodeType === 1 ? pierwszy : null;
}

/** Zapamiętuje ostatnio aktywne pole (także w otwartych Shadow DOM strony). */
export class SledzeniePol {
  private pole: HTMLElement | null = null;
  private zakres: Range | null = null;
  private zastap: HTMLElement | null = null;
  private readonly odbiorcy: Array<(pole: HTMLElement | null) => void> = [];

  constructor(
    private readonly doc: Document,
    private readonly pomin: (el: Element) => boolean = () => false,
  ) {}

  podlacz(): void {
    this.doc.addEventListener("focusin", this.naFokus, true);
    this.doc.addEventListener("selectionchange", this.naZaznaczenie, true);
  }

  odlacz(): void {
    this.doc.removeEventListener("focusin", this.naFokus, true);
    this.doc.removeEventListener("selectionchange", this.naZaznaczenie, true);
  }

  /** Powiadamia o zmianie aktywnego pola. */
  naZmiane(odbiorca: (pole: HTMLElement | null) => void): void {
    this.odbiorcy.push(odbiorca);
  }

  /** Ostatnie pole, o ile nadal jest w dokumencie i edytowalne. */
  ostatnie(): HTMLElement | null {
    if (this.pole && this.pole.isConnected && jestEdytowalne(this.pole)) return this.pole;
    return null;
  }

  /** Ustawia pole docelowe (np. pole odpowiedzi wybranej opinii). */
  ustaw(pole: HTMLElement | null): void {
    this.pole = pole ? (pole.tagName === "TEXTAREA" || pole.tagName === "INPUT" ? pole : edytowalnyKorzen(pole) ?? pole) : null;
    this.zakres = null;
    for (const odbiorca of this.odbiorcy) odbiorca(this.pole);
  }

  /** Następne wstawienie do tego pola zastąpi całą jego treść (np. po „Popraw tekst”). */
  zastapCalosc(pole: HTMLElement): void {
    this.zastap = pole;
  }

  /** Treść pola (do „Popraw tekst”). */
  tresc(pole: HTMLElement): string {
    if (pole.tagName === "TEXTAREA" || pole.tagName === "INPUT") return (pole as HTMLInputElement).value;
    return pole.innerText ?? pole.textContent ?? "";
  }

  /** Wstawia tekst w ostatnie pole; false, gdy nie ma pola (wtedy panel kopiuje do schowka). */
  wstaw(tekst: string): boolean {
    const pole = this.ostatnie();
    if (!pole) return false;
    const calosc = this.zastap === pole;
    this.zastap = null;
    return wstawTekst(pole, tekst, { calosc, zakres: calosc ? null : this.zakres });
  }

  private readonly naFokus = (zdarzenie: Event): void => {
    const cel = celZdarzenia(zdarzenie);
    if (!cel || this.pomin(cel) || !jestEdytowalne(cel)) return;
    const pole = cel.tagName === "TEXTAREA" || cel.tagName === "INPUT" ? (cel as HTMLElement) : edytowalnyKorzen(cel);
    if (!pole || pole === this.pole) return;
    this.pole = pole;
    this.zakres = null;
    this.zastap = null;
    for (const odbiorca of this.odbiorcy) odbiorca(pole);
  };

  private readonly naZaznaczenie = (): void => {
    const pole = this.pole;
    if (!pole || pole.tagName === "TEXTAREA" || pole.tagName === "INPUT") return;
    const zaznaczenie = this.doc.getSelection();
    if (!zaznaczenie || zaznaczenie.rangeCount === 0) return;
    const zakres = zaznaczenie.getRangeAt(0);
    if (pole.contains(zakres.commonAncestorContainer)) this.zakres = zakres.cloneRange();
  };
}

interface OpcjeWstawiania {
  /** Zastąp całą treść pola zamiast wstawiać w miejscu kursora. */
  calosc?: boolean;
  /** Zapamiętany zakres kursora w polu contenteditable. */
  zakres?: Range | null;
}

function natywnySetter(pole: HTMLInputElement | HTMLTextAreaElement): ((v: string) => void) | undefined {
  const widok = pole.ownerDocument.defaultView;
  const prototyp = pole.tagName === "TEXTAREA" ? widok?.HTMLTextAreaElement.prototype : widok?.HTMLInputElement.prototype;
  return prototyp ? Object.getOwnPropertyDescriptor(prototyp, "value")?.set : undefined;
}

function zdarzeniaZmiany(pole: HTMLElement, tekst: string, poExecCommand: boolean): void {
  const widok = pole.ownerDocument.defaultView;
  if (!poExecCommand) {
    const Zdarzenie = widok?.InputEvent ?? InputEvent;
    pole.dispatchEvent(new Zdarzenie("input", { bubbles: true, composed: true, inputType: "insertText", data: tekst }));
  }
  pole.dispatchEvent(new (widok?.Event ?? Event)("change", { bubbles: true }));
}

function execInsert(doc: Document, tekst: string): boolean {
  try {
    return typeof doc.execCommand === "function" && doc.execCommand("insertText", false, tekst) === true;
  } catch {
    return false;
  }
}

function wstawDoPola(pole: HTMLInputElement | HTMLTextAreaElement, tekst: string, calosc: boolean): boolean {
  const doc = pole.ownerDocument;
  const przed = pole.value;
  let od = przed.length;
  let doo = przed.length;
  try {
    if (calosc) {
      od = 0;
    } else if (pole.selectionStart !== null && pole.selectionEnd !== null) {
      od = pole.selectionStart;
      doo = pole.selectionEnd;
    }
    pole.setSelectionRange(od, doo);
  } catch {
    // Typy pól bez zaznaczenia (email) – dopisanie na końcu lub zastąpienie całości.
    if (calosc) od = 0;
  }
  const oczekiwana = przed.slice(0, od) + tekst + przed.slice(doo);
  if (execInsert(doc, tekst) && pole.value === oczekiwana) {
    zdarzeniaZmiany(pole, tekst, true);
    return true;
  }
  const setter = natywnySetter(pole);
  if (setter) setter.call(pole, oczekiwana);
  else pole.value = oczekiwana;
  try {
    const kursor = od + tekst.length;
    pole.setSelectionRange(kursor, kursor);
  } catch {
    // jak wyżej
  }
  zdarzeniaZmiany(pole, tekst, false);
  return pole.value === oczekiwana;
}

function wstawDoEdytora(korzen: HTMLElement, tekst: string, opcje: OpcjeWstawiania): boolean {
  const doc = korzen.ownerDocument;
  const zaznaczenie = doc.getSelection();
  let zakres: Range;
  if (opcje.calosc) {
    zakres = doc.createRange();
    zakres.selectNodeContents(korzen);
  } else if (opcje.zakres && korzen.contains(opcje.zakres.commonAncestorContainer)) {
    zakres = opcje.zakres;
  } else if (zaznaczenie && zaznaczenie.rangeCount > 0 && korzen.contains(zaznaczenie.getRangeAt(0).commonAncestorContainer)) {
    zakres = zaznaczenie.getRangeAt(0);
  } else {
    zakres = doc.createRange();
    zakres.selectNodeContents(korzen);
    zakres.collapse(false);
  }
  if (zaznaczenie) {
    zaznaczenie.removeAllRanges();
    zaznaczenie.addRange(zakres);
  }
  const przed = korzen.textContent ?? "";
  if (execInsert(doc, tekst) && (korzen.textContent ?? "") !== przed) {
    zdarzeniaZmiany(korzen, tekst, true);
    return true;
  }
  zakres.deleteContents();
  const fragment = doc.createDocumentFragment();
  tekst.split("\n").forEach((linia, i) => {
    if (i > 0) fragment.appendChild(doc.createElement("br"));
    if (linia) fragment.appendChild(doc.createTextNode(linia));
  });
  const ostatni = fragment.lastChild;
  zakres.insertNode(fragment);
  if (ostatni && zaznaczenie) {
    const kursor = doc.createRange();
    kursor.setStartAfter(ostatni);
    kursor.collapse(true);
    zaznaczenie.removeAllRanges();
    zaznaczenie.addRange(kursor);
  }
  zdarzeniaZmiany(korzen, tekst, false);
  return true;
}

/** Wstawia tekst w pole formularza lub edytor contenteditable. */
export function wstawTekst(pole: HTMLElement, tekst: string, opcje: OpcjeWstawiania = {}): boolean {
  try {
    pole.focus({ preventScroll: true });
  } catch {
    pole.focus();
  }
  if (pole.tagName === "TEXTAREA" || pole.tagName === "INPUT") {
    return wstawDoPola(pole as HTMLTextAreaElement, tekst, !!opcje.calosc);
  }
  const korzen = edytowalnyKorzen(pole);
  return korzen ? wstawDoEdytora(korzen, tekst, opcje) : false;
}
