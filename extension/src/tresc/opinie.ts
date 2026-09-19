// Rozpoznawanie opinii, komentarzy i wiadomości na stronie – do szybkiej akcji „Odpowiedz”.
//
// Znane serwisy mają własne selektory (Booking.com – strona publiczna i panel partnera,
// Google Maps / Profil Firmy, Gmail, Outlook, Roundcube). Układ tych stron zmienia się
// bez zapowiedzi, więc zawsze działa też heurystyka ogólna (itemprop=review, klasy
// „review/opinia/comment”), a gdy nic nie pasuje – użytkownik może użyć zaznaczenia.

import type { OpiniaSkrot } from "../wspolne/komunikaty";
import { HOST_PANELU, skroc, tekstElementu } from "./ekstraktor";

export type Serwis =
  | "booking"
  | "booking-partner"
  | "google-maps"
  | "google-firma"
  | "gmail"
  | "outlook"
  | "poczta"
  | "inne";

export interface ZnalezionaOpinia extends OpiniaSkrot {
  element: Element;
  pole: HTMLElement | null;
}

const LIMIT_OPINII = 50;
const LIMIT_TEKSTU = 5000;

/** Rozpoznaje serwis po adresie strony. */
export function wykryjSerwis(adres: string): Serwis {
  let url: URL;
  try {
    url = new URL(adres);
  } catch {
    return "inne";
  }
  const host = url.hostname;
  if (host === "admin.booking.com" || host.endsWith(".admin.booking.com") || host === "partner.booking.com") {
    return "booking-partner";
  }
  if (host === "booking.com" || host.endsWith(".booking.com")) return "booking";
  if (host === "mail.google.com") return "gmail";
  if (host === "business.google.com") return "google-firma";
  if (/^(www\.)?google\.[a-z.]+$/.test(host) && url.pathname.startsWith("/maps")) return "google-maps";
  if (host === "maps.google.com" || host.startsWith("maps.google.")) return "google-maps";
  if (/^(www\.)?google\.[a-z.]+$/.test(host)) return "google-firma";
  if (/(^|\.)outlook\.(live|office|office365)\.com$/.test(host) || host === "outlook.cloud.microsoft") return "outlook";
  if (/^(mail|poczta|webmail|roundcube)\./.test(host)) return "poczta";
  return "inne";
}

interface Regula {
  karta: string;
  rodzaj: OpiniaSkrot["rodzaj"];
  tekst?: string[];
  autor?: string[];
  ocena?: string[];
  data?: string[];
}

const REGULY: Partial<Record<Serwis, Regula[]>> = {
  booking: [
    {
      karta: '[data-testid="review-card"], [data-testid="featuredreview"], .c-review-block, .review_item',
      rodzaj: "opinia",
      tekst: [
        '[data-testid="review-title"]',
        '[data-testid="review-positive-text"]',
        '[data-testid="review-negative-text"]',
        ".c-review__body",
        ".review_item_review_content",
      ],
      autor: ['[data-testid="review-avatar"] .a3332d346a', '[data-testid="review-avatar"]', ".bui-avatar-block__title"],
      ocena: ['[data-testid="review-score"]', ".bui-review-score__badge"],
      data: ['[data-testid="review-date"]', ".c-review-block__date"],
    },
  ],
  "booking-partner": [
    {
      karta:
        '[data-test-id*="review" i]:not(input):not(textarea), [data-testid*="review-card" i], .review-card, .review-block, .guest-review, [class*="ReviewCard"], [class*="review-item" i]',
      rodzaj: "opinia",
      tekst: ['[class*="review-text" i]', '[class*="comment" i]', '[data-test-id*="text" i]'],
      autor: ['[class*="guest-name" i]', '[class*="author" i]', '[data-test-id*="name" i]'],
      ocena: ['[class*="score" i]', '[data-test-id*="score" i]'],
      data: ["time", '[class*="date" i]'],
    },
  ],
  "google-maps": [
    {
      karta: "div.jftiEf[data-review-id], div[data-review-id][aria-label]",
      rodzaj: "opinia",
      tekst: [".wiI7pd", '[data-expandable-section] span', ".MyEned"],
      autor: [".d4r55", ".WNxzHc button", '[class*="author" i]'],
      ocena: ['[role="img"][aria-label*="gwiazd" i]', '[role="img"][aria-label*="star" i]', ".kvMYJc"],
      data: [".rsqaWe", ".xRkPPb"],
    },
  ],
  "google-firma": [
    {
      karta: "div[data-review-id], .gws-localreviews__google-review, [jscontroller][data-google-review-id]",
      rodzaj: "opinia",
      tekst: ['[data-expandable-section]', ".review-full-text", ".Jtu6Td", ".OA1nbd", "span[jscontroller]"],
      autor: [".TSUbDb", ".TSUbDb a", ".Vpc5Fe", '[class*="author" i]'],
      ocena: ['[role="img"][aria-label*="gwiazd" i]', '[role="img"][aria-label*="star" i]', ".lTi8oc"],
      data: [".dehysf", ".y3Ibjb"],
    },
  ],
  gmail: [
    {
      karta: "div.adn.ads, div.gs",
      rodzaj: "wiadomosc",
      tekst: ["div.a3s"],
      autor: ["span.gD", ".go"],
      data: ["span.g3"],
    },
  ],
  outlook: [
    {
      karta: '[aria-label="Treść wiadomości"], [aria-label="Message body"], div[role="document"]',
      rodzaj: "wiadomosc",
    },
  ],
  poczta: [
    {
      karta: "#messagebody, .message-htmlpart, .message-part, #message-content .body, .mail-body",
      rodzaj: "wiadomosc",
    },
  ],
};

const OGOLNE: Regula[] = [
  {
    karta:
      '[itemprop="review"], [itemtype*="schema.org/Review"], [class*="review" i]:not(input):not(textarea):not(button), [id*="review" i]:not(input):not(textarea), [data-testid*="review" i], [class*="opini" i]:not(input):not(textarea), [class*="recenzj" i]',
    rodzaj: "opinia",
    tekst: ['[itemprop="reviewBody"]', '[itemprop="description"]'],
    autor: ['[itemprop="author"]', '[class*="author" i]', '[class*="autor" i]', '[class*="user" i]'],
    ocena: ['[itemprop="ratingValue"]', '[class*="rating" i]', '[class*="ocena" i]', '[class*="score" i]'],
    data: ['[itemprop="datePublished"]', "time"],
  },
  {
    karta: '[class*="comment" i]:not(input):not(textarea):not(button), [class*="komentarz" i], [id^="comment-"]',
    rodzaj: "komentarz",
    autor: ['[class*="author" i]', '[class*="autor" i]', "cite", ".fn"],
    data: ["time", '[class*="date" i]'],
  },
];

function jestPanelem(el: Element): boolean {
  return el.tagName.toLowerCase() === HOST_PANELU || !!el.closest(HOST_PANELU);
}

function pierwszyTekst(karta: Element, selektory: string[] | undefined, atrybuty = false): string | undefined {
  for (const selektor of selektory ?? []) {
    let el: Element | null = null;
    try {
      el = karta.querySelector(selektor);
    } catch {
      continue;
    }
    if (!el) continue;
    const wartosc = atrybuty
      ? el.getAttribute("aria-label") || el.getAttribute("content") || el.getAttribute("title") || el.textContent
      : el.getAttribute("content") || el.textContent;
    const czysty = (wartosc ?? "").replace(/\s+/g, " ").trim();
    if (czysty) return czysty.slice(0, 120);
  }
  return undefined;
}

function tekstKarty(karta: Element, regula: Regula): string {
  const fragmenty: string[] = [];
  const widziane = new Set<Element>();
  for (const selektor of regula.tekst ?? []) {
    let elementy: Element[] = [];
    try {
      elementy = Array.from(karta.querySelectorAll(selektor));
    } catch {
      continue;
    }
    for (const el of elementy) {
      if (Array.from(widziane).some((w) => w.contains(el) || el.contains(w))) continue;
      const tekst = tekstElementu(el, true);
      if (tekst) {
        fragmenty.push(tekst);
        widziane.add(el);
      }
    }
  }
  const tekst = fragmenty.length ? fragmenty.join("\n") : tekstElementu(karta, true);
  return skroc(tekst, LIMIT_TEKSTU).tekst;
}

/** Pole odpowiedzi w karcie opinii lub tuż obok (do trzech poziomów wyżej). */
function poleOdpowiedzi(karta: Element): HTMLElement | null {
  const selektor = 'textarea, [contenteditable=""], [contenteditable="true"], [contenteditable="plaintext-only"]';
  let zakres: Element | null = karta;
  for (let poziom = 0; zakres && poziom < 3; poziom += 1, zakres = zakres.parentElement) {
    const pola = Array.from(zakres.querySelectorAll<HTMLElement>(selektor)).filter(
      (pole) => !(pole as HTMLTextAreaElement).disabled && !(pole as HTMLTextAreaElement).readOnly,
    );
    if (pola.length === 1) return pola[0];
    if (pola.length > 1) return null;
  }
  return null;
}

function kandydaci(korzen: ParentNode, regula: Regula): Element[] {
  try {
    return Array.from(korzen.querySelectorAll(regula.karta)).filter((el) => !jestPanelem(el));
  } catch {
    return [];
  }
}

/** Z listy kandydatów zostawia karty: bez kontenerów list i bez elementów zagnieżdżonych. */
function wybierzKarty(lista: Element[]): Element[] {
  const zbior = lista.filter((el) => {
    const dlugosc = (el.textContent ?? "").replace(/\s+/g, " ").trim().length;
    return dlugosc >= 20;
  });
  const bezKontenerow = zbior.filter((el) => zbior.filter((inny) => inny !== el && el.contains(inny)).length < 2);
  return bezKontenerow.filter((el) => !bezKontenerow.some((inny) => inny !== el && inny.contains(el)));
}

function dokumenty(doc: Document): Document[] {
  const wynik = [doc];
  // Klienty poczty (Roundcube) pokazują treść w ramce z tej samej domeny.
  for (const ramka of Array.from(doc.querySelectorAll("iframe"))) {
    try {
      const wewnetrzny = ramka.contentDocument;
      if (wewnetrzny?.body) wynik.push(wewnetrzny);
    } catch {
      // Ramka z innej domeny – niedostępna.
    }
  }
  return wynik;
}

/** Znajduje opinie/wiadomości na stronie. */
export function znajdzOpinie(doc: Document, adres = doc.location?.href ?? ""): ZnalezionaOpinia[] {
  const serwis = wykryjSerwis(adres);
  const reguly = [...(REGULY[serwis] ?? []), ...OGOLNE];
  const wynik: ZnalezionaOpinia[] = [];
  const zajete: Element[] = [];
  for (const dokument of dokumenty(doc)) {
    for (const regula of reguly) {
      const karty = wybierzKarty(kandydaci(dokument, regula)).filter(
        (karta) => !zajete.some((inna) => inna.contains(karta) || karta.contains(inna)),
      );
      for (const karta of karty) {
        const tekst = tekstKarty(karta, regula);
        if (tekst.length < 20) continue;
        zajete.push(karta);
        const pole = poleOdpowiedzi(karta);
        wynik.push({
          id: `op-${wynik.length + 1}`,
          rodzaj: regula.rodzaj,
          serwis,
          autor: pierwszyTekst(karta, regula.autor),
          ocena: pierwszyTekst(karta, regula.ocena, true),
          data: pierwszyTekst(karta, regula.data),
          tekst,
          poleOdpowiedzi: pole !== null,
          element: karta,
          pole,
        });
        if (wynik.length >= LIMIT_OPINII) return wynik;
      }
      // Dla znanego serwisu reguła szczegółowa wystarcza – heurystyki tylko jako zapas.
      if (wynik.length && !OGOLNE.includes(regula)) break;
    }
  }
  return wynik;
}

/** Wersja bez referencji do DOM – do przesłania panelowi. */
export function skrot(opinia: ZnalezionaOpinia): OpiniaSkrot {
  const { element: _element, pole: _pole, ...reszta } = opinia;
  return { ...reszta, tekst: reszta.tekst.slice(0, 600) };
}
