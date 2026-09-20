// Widoczność w wyszukiwarkach dla ekranów poza portalem: strona produktu i piaskownica.
//
// Aplikacja jest jednostronicowa, więc znaczniki z index.html opisują tylko pierwszy ekran.
// Ten moduł podmienia je przy każdej zmianie ekranu: tytuł, opis, adres kanoniczny, Open Graph
// i regułę dla robotów. Ekrany za logowaniem dostają „noindex”, bo gość nie ma tam czego oglądać,
// oraz własny opis i podgląd — inaczej odsyłacz do logowania pokazywałby treść poprzedniego ekranu.

import { SCIEZKA, type Screen } from "./shell/route";

const WITRYNA = "Danaco Nexus";
const OBRAZ = "/og.png";
const OBRAZ_OPIS = "Znak Danaco Nexus i hasło „Powiedz, co zrobić. Odbierz gotowe.”";
const TYTUL_APLIKACJI = WITRYNA;
const ZNACZNIK = "data-seo-ekran";

interface MetadaneEkranu {
  tytul: string;
  opis: string;
  /** Adres kanoniczny ekranu; strona produktu spod „/start” wskazuje korzeń witryny. */
  sciezka: string;
  spoleczny: { tytul: string; opis: string };
  dane?: Record<string, unknown>[];
}

/** Ekrany dostępne bez logowania. Pozostałe nie trafiają do wyszukiwarek. */
const PUBLICZNE: Partial<Record<Screen, MetadaneEkranu>> = {
  landing: {
    tytul: "Danaco Nexus — osobisty asystent AI w chmurze",
    opis:
      "Osobisty asystent AI: stare zdjęcia jak nowe, plany, notatki z nagrań, rozmowa głosowa" +
      " po polsku i porządek w dokumentach. Piszesz, co ma powstać — odbierasz gotowy plik.",
    sciezka: "/",
    spoleczny: {
      tytul: "Danaco Nexus — powiedz, co zrobić. Odbierz gotowe.",
      opis: "Twój osobisty agent AI do pracy i do życia. Do 10 GB własnej przestrzeni w chmurze, 7 dni bez opłaty.",
    },
  },
  demo: {
    tytul: "Wypróbuj Danaco Nexus bez konta — pełna aplikacja",
    opis:
      "Otwiera się ta sama aplikacja, z której korzystają klienci: rozmowa, pliki i narzędzia" +
      " na własnym koncie próbnym. Bez rejestracji, bez karty, bez instalacji.",
    sciezka: SCIEZKA.piaskownica,
    spoleczny: {
      tytul: "Wypróbuj Danaco Nexus bez konta",
      opis: "Pełna aplikacja na koncie próbnym: rozmowa, pliki i narzędzia. Bez rejestracji.",
    },
    dane: [
      {
        "@context": "https://schema.org",
        "@type": "WebPage",
        name: "Wypróbuj Danaco Nexus bez konta",
        description: "Wejście do aplikacji Danaco Nexus na koncie próbnym, bez rejestracji.",
        inLanguage: "pl-PL",
        isPartOf: { "@type": "WebSite", name: WITRYNA },
      },
    ],
  },
};

/** Opis zastępczy dla ekranów bez wpisu w PUBLICZNE: powłoka aplikacji, logowanie, panel. */
const APLIKACJA: Omit<MetadaneEkranu, "sciezka"> = {
  tytul: TYTUL_APLIKACJI,
  opis: "Osobista przestrzeń pracy z agentem Danaco Nexus: rozmowa, pliki i sprawy w jednym oknie.",
  spoleczny: {
    tytul: "Danaco Nexus",
    opis: "Osobista przestrzeń pracy z agentem AI. Zaloguj się, aby wrócić do swoich spraw.",
  },
};

function adresBezwzgledny(sciezka: string): string {
  return new URL(sciezka, window.location.origin).toString();
}

/** Ustawia znacznik meta po nazwie albo właściwości; brakujący element dopisuje do nagłówka. */
function ustawMeta(atrybut: "name" | "property", klucz: string, wartosc: string): void {
  const wybor = `meta[${atrybut}="${klucz}"]`;
  let element = document.head.querySelector<HTMLMetaElement>(wybor);
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute(atrybut, klucz);
    document.head.append(element);
  }
  element.setAttribute("content", wartosc);
}

function ustawKanoniczny(adres: string | null): void {
  let element = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  // Adres kanoniczny na stronie wyłączonej z indeksowania byłby sprzecznym sygnałem — usuwamy go.
  if (!adres) {
    element?.remove();
    return;
  }
  if (!element) {
    element = document.createElement("link");
    element.rel = "canonical";
    document.head.append(element);
  }
  element.href = adres;
}

function ustawDaneStrukturalne(dane: Record<string, unknown>[] | undefined): void {
  for (const element of Array.from(document.head.querySelectorAll(`[${ZNACZNIK}]`))) element.remove();
  for (const pozycja of dane ?? []) {
    const skrypt = document.createElement("script");
    skrypt.type = "application/ld+json";
    skrypt.textContent = JSON.stringify(pozycja);
    skrypt.setAttribute(ZNACZNIK, "1");
    document.head.append(skrypt);
  }
}

export function applyIndexing(screen: Screen): void {
  const metadane = PUBLICZNE[screen];
  const tresc = metadane ?? APLIKACJA;
  const adres = adresBezwzgledny(metadane ? metadane.sciezka : window.location.pathname);
  const obraz = adresBezwzgledny(OBRAZ);
  document.title = tresc.tytul;
  ustawDaneStrukturalne(metadane?.dane);
  ustawMeta("name", "robots", metadane ? "index, follow, max-image-preview:large" : "noindex, nofollow");
  ustawKanoniczny(metadane ? adres : null);
  ustawMeta("name", "description", tresc.opis);
  ustawMeta("property", "og:type", "website");
  ustawMeta("property", "og:site_name", WITRYNA);
  ustawMeta("property", "og:locale", "pl_PL");
  ustawMeta("property", "og:url", adres);
  ustawMeta("property", "og:title", tresc.spoleczny.tytul);
  ustawMeta("property", "og:description", tresc.spoleczny.opis);
  ustawMeta("property", "og:image", obraz);
  ustawMeta("property", "og:image:alt", OBRAZ_OPIS);
  ustawMeta("name", "twitter:card", "summary_large_image");
  ustawMeta("name", "twitter:title", tresc.spoleczny.tytul);
  ustawMeta("name", "twitter:description", tresc.spoleczny.opis);
  ustawMeta("name", "twitter:image", obraz);
  ustawMeta("name", "twitter:image:alt", OBRAZ_OPIS);
}
