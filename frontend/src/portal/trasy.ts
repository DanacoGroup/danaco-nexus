// Trasowanie portalu: ścieżki /portal/… (funkcje czyste). Prefiks oddziela witrynę od aplikacji
// użytkownika i od stron Twórcy stron, więc żaden adres portalu nie przesłania adresu aplikacji.

export type PortalStrona =
  | "glowna"
  | "oferta"
  | "funkcje"
  | "narzedzia"
  | "zastosowania"
  | "cennik"
  | "kontakt"
  | "dokumentacja"
  | "blog"
  | "wiedza"
  | "strona"
  | "szukaj"
  | "konto"
  | "panel"
  | "admin"
  | "prywatnosc"
  | "regulamin"
  | "cookies"
  | "nieznana";

export interface PortalTrasa {
  strona: PortalStrona;
  /** Adres pozycji treści albo null dla listy. */
  slug: string | null;
  /** Zapytanie wyszukiwania albo token odzyskiwania hasła. */
  parametr: string;
}

export const PREFIKS = "/portal";
const SLUG = /^[a-z0-9][a-z0-9-]{0,119}$/;
// Sekcje z listą i pozycją: /portal/<sekcja>[/<adres>].
const Z_POZYCJA: Record<string, PortalStrona> = {
  blog: "blog",
  wiedza: "wiedza",
  dokumentacja: "dokumentacja",
  s: "strona",
};
const PROSTE: Record<string, PortalStrona> = {
  "": "glowna",
  oferta: "oferta",
  funkcje: "funkcje",
  narzedzia: "narzedzia",
  zastosowania: "zastosowania",
  cennik: "cennik",
  kontakt: "kontakt",
  szukaj: "szukaj",
  konto: "konto",
  panel: "panel",
  admin: "admin",
  prywatnosc: "prywatnosc",
  regulamin: "regulamin",
  cookies: "cookies",
};

/** Czy adres należy do portalu. */
export function czyPortal(pathname: string): boolean {
  return pathname === PREFIKS || pathname.startsWith(`${PREFIKS}/`);
}

/** Trasa portalu z adresu; nieznane ścieżki dają stronę „nieznana” (odpowiednik 404). */
export function parsujTrase(pathname: string, search = ""): PortalTrasa {
  const params = new URLSearchParams(search);
  const parametr = (params.get("q") ?? params.get("token") ?? "").slice(0, 200);
  const czesci = pathname.replace(/\/+$/, "").slice(PREFIKS.length).split("/").filter(Boolean);
  if (czesci.length === 0) return { strona: "glowna", slug: null, parametr };
  const [sekcja, adres, nadmiar] = czesci;
  if (nadmiar !== undefined) return { strona: "nieznana", slug: null, parametr };
  if (adres === undefined) {
    const strona = PROSTE[sekcja] ?? Z_POZYCJA[sekcja];
    if (strona === "strona") return { strona: "nieznana", slug: null, parametr };
    return { strona: strona ?? "nieznana", slug: null, parametr };
  }
  const zPozycja = Z_POZYCJA[sekcja];
  if (!zPozycja || !SLUG.test(adres)) return { strona: "nieznana", slug: null, parametr };
  return { strona: zPozycja, slug: adres, parametr };
}

/** Adres trasy portalu. */
export function sciezka(strona: PortalStrona, slug: string | null = null): string {
  if (strona === "glowna") return PREFIKS;
  const sekcja = strona === "strona" ? "s" : strona;
  return slug ? `${PREFIKS}/${sekcja}/${slug}` : `${PREFIKS}/${sekcja}`;
}

/** Czy pozycja nawigacji jest bieżąca — także niżej w sekcji, ale nie przy wspólnym przedrostku. */
export function czyAktywna(pathname: string, adres: string): boolean {
  const biezacy = pathname.replace(/\/+$/, "") || PREFIKS;
  return biezacy === adres || biezacy.startsWith(`${adres}/`);
}

/** Rodzaj treści w API dla strony portalu (null, gdy strona go nie pobiera). */
export function rodzajTresci(strona: PortalStrona): "blog" | "wiedza" | "dokumentacja" | "strona" | null {
  switch (strona) {
    case "blog":
      return "blog";
    case "wiedza":
      return "wiedza";
    case "dokumentacja":
      return "dokumentacja";
    case "strona":
      return "strona";
    default:
      return null;
  }
}
