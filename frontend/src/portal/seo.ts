// Metadane strony portalu: tytuł, opis, Open Graph, adres kanoniczny i dane strukturalne schema.org.
//
// Portal jest aplikacją jednostronicową, więc znaczniki head wymieniane są przy każdej zmianie
// trasy: te z index.html w miejscu i przywracane po wyjściu, dopisane — z atrybutem
// data-portal-seo, który znika razem z nimi. Strona nigdy nie ma dwóch opisów.

import { useEffect } from "react";

export interface DanePozycjonowania {
  tytul: string;
  opis: string;
  /** Ścieżka kanoniczna w tej witrynie, np. /portal/blog/pierwsze-kroki. */
  sciezka: string;
  obraz?: string;
  /** Opis obrazu podglądu; bez niego stosowany jest opis obrazu marki. */
  obrazOpis?: string;
  rodzaj?: "website" | "article";
  noindex?: boolean;
  /** Dane strukturalne schema.org (JSON-LD). */
  dane?: Record<string, unknown> | Record<string, unknown>[];
}

const ZNACZNIK = "data-portal-seo";
const NAZWA_WITRYNY = "Danaco Nexus";
const OBRAZ_DOMYSLNY = "/og.png";
const OBRAZ_OPIS_DOMYSLNY = "Znak Danaco Nexus i hasło „Powiedz, co zrobić. Odbierz gotowe.”";
const ROBOTY_INDEKSUJ = "index, follow, max-image-preview:large";

function adresBezwzgledny(sciezka: string): string {
  if (typeof window === "undefined") return sciezka;
  return new URL(sciezka, window.location.origin).toString();
}

/** Zapamiętane wartości znaczników z index.html, przywracane po opuszczeniu portalu. */
type Przywrocenie = () => void;

function ustawMeta(
  przywrocenia: Przywrocenie[],
  atrybut: "name" | "property",
  klucz: string,
  wartosc: string,
): void {
  if (!wartosc) return;
  const istniejacy = document.head.querySelector<HTMLMetaElement>(`meta[${atrybut}="${klucz}"]:not([${ZNACZNIK}])`);
  if (istniejacy) {
    const poprzednia = istniejacy.getAttribute("content") ?? "";
    przywrocenia.push(() => istniejacy.setAttribute("content", poprzednia));
    istniejacy.setAttribute("content", wartosc);
    return;
  }
  const element = document.createElement("meta");
  element.setAttribute(atrybut, klucz);
  element.setAttribute("content", wartosc);
  element.setAttribute(ZNACZNIK, "1");
  document.head.appendChild(element);
}

/** Adres kanoniczny; strona wyłączona z indeksowania nie deklaruje żadnego. */
function ustawKanoniczny(przywrocenia: Przywrocenie[], adres: string | null): void {
  const istniejacy = document.head.querySelector<HTMLLinkElement>(`link[rel="canonical"]:not([${ZNACZNIK}])`);
  if (istniejacy) {
    const poprzedni = istniejacy.getAttribute("href") ?? "";
    przywrocenia.push(() => istniejacy.setAttribute("href", poprzedni));
    if (!adres) {
      istniejacy.remove();
      przywrocenia.push(() => document.head.appendChild(istniejacy));
      return;
    }
    istniejacy.setAttribute("href", adres);
    return;
  }
  if (!adres) return;
  const element = document.createElement("link");
  element.rel = "canonical";
  element.href = adres;
  element.setAttribute(ZNACZNIK, "1");
  document.head.appendChild(element);
}

function wyczysc(): void {
  for (const element of Array.from(document.head.querySelectorAll(`[${ZNACZNIK}]`))) element.remove();
}

/** Okruszki nawigacji jako dane strukturalne (BreadcrumbList). */
export function okruszki(pozycje: { nazwa: string; sciezka: string }[]): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: pozycje.map((pozycja, indeks) => ({
      "@type": "ListItem",
      position: indeks + 1,
      name: pozycja.nazwa,
      item: adresBezwzgledny(pozycja.sciezka),
    })),
  };
}

/** Dane strukturalne artykułu (wpis bloga, artykuł bazy wiedzy, strona dokumentacji). */
export function artykul(dane: {
  tytul: string;
  opis: string;
  sciezka: string;
  autor: string;
  opublikowano: string | null;
  zmieniono: string;
  typ?: "BlogPosting" | "TechArticle" | "Article";
}): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": dane.typ ?? "BlogPosting",
    headline: dane.tytul,
    description: dane.opis,
    inLanguage: "pl-PL",
    mainEntityOfPage: adresBezwzgledny(dane.sciezka),
    datePublished: dane.opublikowano ?? undefined,
    dateModified: dane.zmieniono,
    author: { "@type": dane.autor ? "Person" : "Organization", name: dane.autor || NAZWA_WITRYNY },
    publisher: { "@type": "Organization", name: NAZWA_WITRYNY },
  };
}

/** Plan cennika dla danych strukturalnych; kwoty w groszach, jak w API sprzedaży. */
export interface PlanOferty {
  kod: string;
  nazwa: string;
  opis: string;
  cenaMiesiacGr: number;
  doKupienia: boolean;
}

/** Cena schema.org: kwota dziesiętna, waluta osobnym polem. */
function cena(groszy: number): string {
  return (groszy / 100).toFixed(2);
}

/**
 * Dane strukturalne oferty dla strony cennika (Product z AggregateOffer).
 *
 * Plan bez ceny czeka na start sprzedaży i do danych nie trafia — Offer bez kwoty jest niepoprawny;
 * gdy żaden plan nie ma ceny, wynikiem jest null. Opis podaje strona.
 */
export function oferta(dane: {
  opis: string;
  waluta: string;
  sciezka: string;
  plany: PlanOferty[];
}): Record<string, unknown> | null {
  const platne = dane.plany.filter((plan) => plan.cenaMiesiacGr > 0);
  if (platne.length === 0) return null;
  const kwoty = platne.map((plan) => plan.cenaMiesiacGr);
  const adres = adresBezwzgledny(dane.sciezka);
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: NAZWA_WITRYNY,
    description: dane.opis,
    url: adres,
    brand: { "@type": "Brand", name: NAZWA_WITRYNY },
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: dane.waluta,
      lowPrice: cena(Math.min(...kwoty)),
      highPrice: cena(Math.max(...kwoty)),
      offerCount: platne.length,
      offers: platne.map((plan) => ({
        "@type": "Offer",
        name: plan.nazwa,
        description: plan.opis,
        sku: plan.kod,
        price: cena(plan.cenaMiesiacGr),
        priceCurrency: dane.waluta,
        url: adres,
        availability: plan.doKupienia ? "https://schema.org/InStock" : "https://schema.org/PreOrder",
      })),
    },
  };
}

/** Dane strukturalne witryny i wydawcy (strona główna portalu). */
export function witryna(): Record<string, unknown>[] {
  return [
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      name: NAZWA_WITRYNY,
      url: adresBezwzgledny("/"),
      logo: adresBezwzgledny("/icons/icon-512.png"),
      description: "Prywatny asystent AI do pracy z dokumentami, pocztą, kalendarzem i wiedzą.",
    },
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      name: NAZWA_WITRYNY,
      url: adresBezwzgledny("/"),
      inLanguage: "pl-PL",
      // Bez SearchAction: pole wyszukiwania w wynikach wymaga strony wyników otwartej dla robota,
      // a /portal/szukaj jest zamknięte w robots.txt (backend/nexus/portal/kanaly.py, ZAMKNIETE)
      // i ma noindex. Deklaracja celu niedostępnego dla robota byłaby sygnałem sprzecznym.
    },
  ];
}

/** Ustawia znaczniki head dla bieżącej strony portalu. */
export function usePozycjonowanie(dane: DanePozycjonowania): void {
  const klucz = JSON.stringify(dane);
  useEffect(() => {
    const poprzedniTytul = document.title;
    const przywrocenia: Przywrocenie[] = [];
    const pelny = `${dane.tytul} — ${NAZWA_WITRYNY}`;
    const obraz = adresBezwzgledny(dane.obraz ?? OBRAZ_DOMYSLNY);
    const obrazOpis = dane.obraz ? (dane.obrazOpis ?? dane.tytul) : OBRAZ_OPIS_DOMYSLNY;
    document.title = pelny;
    wyczysc();
    ustawMeta(przywrocenia, "name", "description", dane.opis);
    ustawMeta(przywrocenia, "name", "robots", dane.noindex ? "noindex, follow" : ROBOTY_INDEKSUJ);
    ustawKanoniczny(przywrocenia, dane.noindex ? null : adresBezwzgledny(dane.sciezka));
    ustawMeta(przywrocenia, "property", "og:title", pelny);
    ustawMeta(przywrocenia, "property", "og:description", dane.opis);
    ustawMeta(przywrocenia, "property", "og:type", dane.rodzaj ?? "website");
    ustawMeta(przywrocenia, "property", "og:url", adresBezwzgledny(dane.sciezka));
    ustawMeta(przywrocenia, "property", "og:site_name", NAZWA_WITRYNY);
    ustawMeta(przywrocenia, "property", "og:locale", "pl_PL");
    ustawMeta(przywrocenia, "property", "og:image", obraz);
    ustawMeta(przywrocenia, "property", "og:image:alt", obrazOpis);
    ustawMeta(przywrocenia, "name", "twitter:card", "summary_large_image");
    ustawMeta(przywrocenia, "name", "twitter:title", pelny);
    ustawMeta(przywrocenia, "name", "twitter:description", dane.opis);
    ustawMeta(przywrocenia, "name", "twitter:image", obraz);
    ustawMeta(przywrocenia, "name", "twitter:image:alt", obrazOpis);

    if (dane.dane) {
      const skrypt = document.createElement("script");
      skrypt.type = "application/ld+json";
      skrypt.textContent = JSON.stringify(dane.dane);
      skrypt.setAttribute(ZNACZNIK, "1");
      document.head.appendChild(skrypt);
    }
    return () => {
      wyczysc();
      for (const przywroc of przywrocenia.reverse()) przywroc();
      document.title = poprzedniTytul;
    };
    // Znaczniki zależą wyłącznie od wartości danych – klucz zapobiega odtwarzaniu ich co render.
  }, [klucz]); // eslint-disable-line react-hooks/exhaustive-deps
}
