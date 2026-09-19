// Ekstraktor czytelnej treści strony (w stylu Readability, bez zależności).
//
// Kolejność: zaznaczony tekst → główny artykuł (ocena bloków tekstu) → cała strona.
// Strona nie jest modyfikowana: drzewo DOM jest tylko przeglądane.

export const LIMIT_ZNAKOW = 24000;
export const HOST_PANELU = "danaco-nexus";

const POMIJANE = new Set([
  "SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "SVG", "CANVAS", "IFRAME", "OBJECT", "EMBED",
  "VIDEO", "AUDIO", "SELECT", "OPTION", "BUTTON", "INPUT", "TEXTAREA", "HEAD", "LINK", "META",
]);
const OBUDOWA = new Set(["NAV", "FOOTER", "ASIDE", "HEADER", "FORM", "DIALOG", "MENU"]);
const BLOKOWE = new Set([
  "ADDRESS", "ARTICLE", "BLOCKQUOTE", "DD", "DIV", "DL", "DT", "FIELDSET", "FIGCAPTION", "FIGURE",
  "H1", "H2", "H3", "H4", "H5", "H6", "HR", "LI", "MAIN", "OL", "P", "PRE", "SECTION", "TABLE",
  "TBODY", "THEAD", "TFOOT", "TR", "UL", "DETAILS", "SUMMARY",
]);
const PLUS = /article|body|content|entry|hentry|main|page|post|text|blog|story|tresc|artykul|review|opini/i;
const MINUS =
  /comment|meta|footer|footnote|sidebar|sponsor|advert|\bads?\b|share|social|nav|menu|cookie|consent|banner|promo|related|popup|modal|breadcrumb|newsletter|stopka|reklam/i;

export interface Tresc {
  tekst: string;
  zrodlo: "zaznaczenie" | "artykul" | "strona";
  skrocono: boolean;
}

function ukryty(el: Element): boolean {
  if (el.id === HOST_PANELU || el.tagName.toLowerCase() === HOST_PANELU) return true;
  if ((el as HTMLElement).hidden || el.getAttribute("aria-hidden") === "true") return true;
  const styl = (el as HTMLElement).style;
  if (styl && (styl.display === "none" || styl.visibility === "hidden")) return true;
  const widok = el.ownerDocument.defaultView;
  if (widok && typeof widok.getComputedStyle === "function") {
    const obliczony = widok.getComputedStyle(el);
    if (obliczony.display === "none" || obliczony.visibility === "hidden") return true;
  }
  return false;
}

function pominiety(el: Element, wObudowie: boolean): boolean {
  if (POMIJANE.has(el.tagName.toUpperCase())) return true;
  if (!wObudowie && OBUDOWA.has(el.tagName)) return true;
  const rola = el.getAttribute("role");
  if (!wObudowie && (rola === "navigation" || rola === "banner" || rola === "contentinfo")) return true;
  return ukryty(el);
}

/** Tekst z zachowaniem struktury (nagłówki, akapity, listy, tabele). */
export function tekstElementu(korzen: Element, zachowajObudowe = false): string {
  const czesci: string[] = [];
  const nowaLinia = () => czesci.push("\n");

  const idz = (wezel: Node): void => {
    if (wezel.nodeType === 3) {
      czesci.push((wezel.textContent ?? "").replace(/\s+/g, " "));
      return;
    }
    if (wezel.nodeType !== 1) return;
    const el = wezel as Element;
    if (el !== korzen && pominiety(el, zachowajObudowe)) return;
    const tag = el.tagName.toUpperCase();
    if (tag === "BR") {
      nowaLinia();
      return;
    }
    const naglowek = /^H([1-6])$/.exec(tag);
    const blok = BLOKOWE.has(tag);
    if (blok) nowaLinia();
    if (naglowek) czesci.push(`${"#".repeat(Number(naglowek[1]))} `);
    if (tag === "LI") czesci.push("- ");
    if (tag === "IMG") {
      const alt = el.getAttribute("alt")?.trim();
      if (alt) czesci.push(` [obraz: ${alt}] `);
    }
    for (const dziecko of Array.from(el.childNodes)) idz(dziecko);
    if (tag === "TD" || tag === "TH") czesci.push(" | ");
    if (blok) nowaLinia();
  };
  idz(korzen);
  return czesci
    .join("")
    .split("\n")
    .map((linia) => linia.replace(/[ \t]+/g, " ").replace(/\s*\|\s*$/, "").trim())
    .join("\n")
    .replace(/\n(?:- |#+ )?\n/g, "\n\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function dlugoscTekstu(el: Element): number {
  return (el.textContent ?? "").replace(/\s+/g, " ").trim().length;
}

function gestoscLinkow(el: Element): number {
  const calosc = dlugoscTekstu(el);
  if (!calosc) return 0;
  let linki = 0;
  for (const a of Array.from(el.querySelectorAll("a"))) linki += dlugoscTekstu(a);
  return linki / calosc;
}

function wagaKlasy(el: Element): number {
  const nazwa = `${el.getAttribute("class") ?? ""} ${el.id}`;
  let waga = 0;
  if (PLUS.test(nazwa)) waga += 25;
  if (MINUS.test(nazwa)) waga -= 25;
  const tag = el.tagName;
  if (tag === "ARTICLE" || tag === "MAIN") waga += 30;
  if (el.getAttribute("itemprop") === "articleBody" || el.getAttribute("role") === "main") waga += 30;
  return waga;
}

function wewnatrzPominietego(el: Element, korzen: Element): boolean {
  for (let w: Element | null = el; w && w !== korzen; w = w.parentElement) {
    if (pominiety(w, false)) return true;
  }
  return false;
}

/** Najlepszy kandydat na główną treść (lub null, gdy strona nie ma wyraźnego artykułu). */
export function znajdzArtykul(doc: Document): Element | null {
  const body = doc.body;
  if (!body) return null;
  const oceny = new Map<Element, number>();
  const akapity = body.querySelectorAll("p, pre, blockquote, td, li, h2, h3, div");
  for (const akapit of Array.from(akapity)) {
    // Div liczy się jako akapit tylko wtedy, gdy nie zawiera innych bloków.
    if (akapit.tagName === "DIV" && akapit.querySelector("p, div, ul, ol, table, pre, blockquote, article, section")) {
      continue;
    }
    const tekst = (akapit.textContent ?? "").replace(/\s+/g, " ").trim();
    if (tekst.length < 25 || wewnatrzPominietego(akapit, body)) continue;
    const punkty = 1 + (tekst.match(/[,.;:]/g)?.length ?? 0) * 0.5 + Math.min(tekst.length / 100, 3);
    const rodzic = akapit.parentElement;
    if (!rodzic) continue;
    oceny.set(rodzic, (oceny.get(rodzic) ?? wagaKlasy(rodzic)) + punkty);
    const dziadek = rodzic.parentElement;
    if (dziadek && dziadek !== doc.documentElement) {
      oceny.set(dziadek, (oceny.get(dziadek) ?? wagaKlasy(dziadek)) + punkty / 2);
    }
  }
  let najlepszy: Element | null = null;
  let najlepszaOcena = 0;
  for (const [el, ocena] of oceny) {
    const wynik = ocena * (1 - gestoscLinkow(el));
    if (wynik > najlepszaOcena) {
      najlepszy = el;
      najlepszaOcena = wynik;
    }
  }
  if (!najlepszy) return null;
  // Artykuł rozbity na kilka sekcji: wspinaczka, dopóki rodzic ma wyraźnie więcej treści.
  let biezacy = najlepszy;
  while (biezacy.parentElement && biezacy.parentElement !== body) {
    const rodzic = biezacy.parentElement;
    if (MINUS.test(`${rodzic.getAttribute("class") ?? ""} ${rodzic.id}`)) break;
    if (dlugoscTekstu(biezacy) >= dlugoscTekstu(rodzic) * 0.6) {
      biezacy = rodzic;
      continue;
    }
    break;
  }
  return biezacy;
}

/** Skraca tekst do limitu na granicy akapitu lub zdania. */
export function skroc(tekst: string, limit = LIMIT_ZNAKOW): { tekst: string; skrocono: boolean } {
  if (tekst.length <= limit) return { tekst, skrocono: false };
  let ciecie = tekst.lastIndexOf("\n", limit);
  if (ciecie < limit * 0.8) ciecie = tekst.lastIndexOf(". ", limit) + 1;
  if (ciecie < limit * 0.8) ciecie = limit;
  return { tekst: `${tekst.slice(0, ciecie).trimEnd()}\n[…treść skrócona]`, skrocono: true };
}

/** Zaznaczony tekst: najpierw w polu formularza, potem w dokumencie. */
export function zaznaczonyTekst(doc: Document): string {
  const aktywny = doc.activeElement;
  if (aktywny && (aktywny.tagName === "TEXTAREA" || aktywny.tagName === "INPUT")) {
    try {
      const { selectionStart: od, selectionEnd: doo, value } = aktywny as HTMLInputElement;
      if (od !== null && doo !== null && doo > od) return value.slice(od, doo).trim();
    } catch {
      // Pola typu email/number nie obsługują zaznaczenia.
    }
  }
  return (doc.getSelection()?.toString() ?? "").trim();
}

/** Czytelna treść strony (bez zaznaczenia): artykuł albo cała strona. */
export function trescStrony(doc: Document, limit = LIMIT_ZNAKOW): Tresc {
  const artykul = znajdzArtykul(doc);
  if (artykul) {
    const tekst = tekstElementu(artykul);
    if (tekst.length >= 200) return { ...skroc(tekst, limit), zrodlo: "artykul" };
  }
  const tekst = doc.body ? tekstElementu(doc.body) : "";
  return { ...skroc(tekst, limit), zrodlo: "strona" };
}

/** Treść do kontekstu: zaznaczenie (jeśli jest) albo czytelna treść strony. */
export function wyodrebnij(doc: Document, limit = LIMIT_ZNAKOW): Tresc {
  const zaznaczenie = zaznaczonyTekst(doc);
  if (zaznaczenie) return { ...skroc(zaznaczenie, limit), zrodlo: "zaznaczenie" };
  return trescStrony(doc, limit);
}

/** Tytuł strony (og:title jako zapas). */
export function tytulStrony(doc: Document): string {
  const tytul = doc.title?.trim();
  if (tytul) return tytul;
  return doc.querySelector('meta[property="og:title"]')?.getAttribute("content")?.trim() ?? doc.location?.hostname ?? "";
}
