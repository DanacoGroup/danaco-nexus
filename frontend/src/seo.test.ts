import { beforeEach, describe, expect, it } from "vitest";
import { applyIndexing } from "./seo";

// Wpięcia modułu nie ma: applyIndexing wywołuje się z App.tsx, a ten plik należy do pary P9.
// Treść wywołania opisuje sprawozdanie jako patch. Do czasu jego wykonania ekrany poza portalem
// zostają przy znacznikach z index.html.

const GLOWA = `
  <meta name="description" content="opis z index.html" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <meta property="og:title" content="tytuł z index.html" />
  <meta property="og:description" content="opis społeczny z index.html" />
  <meta property="og:url" content="https://danaco-nexus.pl/" />
  <meta name="twitter:title" content="tytuł z index.html" />
  <meta name="twitter:description" content="opis społeczny z index.html" />
`;

const meta = (wybor: string): string =>
  document.head.querySelector<HTMLMetaElement>(wybor)?.getAttribute("content") ?? "";
const kanoniczny = (): string | null =>
  document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.getAttribute("href") ?? null;

beforeEach(() => {
  document.head.innerHTML = GLOWA;
  window.history.replaceState(null, "", "/");
});

describe("applyIndexing", () => {
  it("strona produktu dostaje własny tytuł, opis i adres kanoniczny", () => {
    applyIndexing("landing");
    expect(document.title).toContain("Danaco Nexus");
    expect(meta('meta[name="robots"]')).toBe("index, follow, max-image-preview:large");
    expect(kanoniczny()).toBe("http://localhost:3000/");
    expect(meta('meta[name="description"]')).toContain("Osobisty asystent AI");
  });

  it("piaskownica ma własne metadane, kanoniczny /wyprobuj i dane strukturalne", () => {
    applyIndexing("demo");
    expect(document.title).toBe("Wypróbuj Danaco Nexus bez konta — pełna aplikacja");
    expect(kanoniczny()).toBe("http://localhost:3000/wyprobuj");
    expect(meta('meta[property="og:url"]')).toBe("http://localhost:3000/wyprobuj");
    const dane = document.head.querySelectorAll('script[type="application/ld+json"][data-seo-ekran]');
    expect(dane).toHaveLength(1);
    expect(JSON.parse(dane[0].textContent ?? "{}")["@type"]).toBe("WebPage");
  });

  it("ekran za logowaniem: noindex, brak kanonicznego i brak danych strukturalnych", () => {
    applyIndexing("demo");
    window.history.replaceState(null, "", "/zaloguj");
    applyIndexing("login");
    expect(meta('meta[name="robots"]')).toBe("noindex, nofollow");
    expect(kanoniczny()).toBeNull();
    expect(document.head.querySelectorAll("[data-seo-ekran]")).toHaveLength(0);
  });

  it("ekran za logowaniem nie zostawia opisu ani podglądu poprzedniego ekranu", () => {
    applyIndexing("demo");
    window.history.replaceState(null, "", "/zaloguj");
    applyIndexing("login");
    for (const wybor of [
      'meta[name="description"]',
      'meta[property="og:title"]',
      'meta[property="og:description"]',
      'meta[name="twitter:title"]',
      'meta[name="twitter:description"]',
    ]) {
      expect(meta(wybor)).not.toContain("Wypróbuj");
      expect(meta(wybor)).not.toContain("index.html");
    }
    expect(meta('meta[property="og:url"]')).toBe("http://localhost:3000/zaloguj");
  });
});
