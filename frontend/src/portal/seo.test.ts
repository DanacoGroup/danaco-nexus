import { describe, expect, it } from "vitest";
import { oferta, type PlanOferty } from "./seo";

interface Pozycja {
  sku: string;
  price: string;
  availability: string;
}
interface Zbiorcza {
  priceCurrency: string;
  lowPrice: string;
  highPrice: string;
  offerCount: number;
  offers: Pozycja[];
}
interface Produkt {
  "@type": string;
  url: string;
  offers: Zbiorcza;
}

const PLANY: PlanOferty[] = [
  { kod: "start", nazwa: "Start", opis: "Plan na początek", cenaMiesiacGr: 0, doKupienia: false },
  { kod: "praca", nazwa: "Praca", opis: "Plan do pracy", cenaMiesiacGr: 4900, doKupienia: true },
  { kod: "zespol", nazwa: "Zespół", opis: "Plan dla zespołu", cenaMiesiacGr: 12900, doKupienia: false },
];

const dane = (plany: PlanOferty[] = PLANY): Produkt | null =>
  oferta({ opis: "Plany korzystania", waluta: "PLN", sciezka: "/portal/cennik", plany }) as Produkt | null;

describe("oferta", () => {
  it("opisuje plany płatne jako AggregateOffer z widełkami cen", () => {
    const wynik = dane() as Produkt;
    expect(wynik["@type"]).toBe("Product");
    expect(wynik.url).toBe("http://localhost:3000/portal/cennik");
    expect(wynik.offers.priceCurrency).toBe("PLN");
    expect(wynik.offers.lowPrice).toBe("49.00");
    expect(wynik.offers.highPrice).toBe("129.00");
    expect(wynik.offers.offerCount).toBe(2);
  });

  it("plan bez ceny nie trafia do oferty, a dostępność zależy od możliwości zakupu", () => {
    const pozycje = (dane() as Produkt).offers.offers;
    expect(pozycje.map((pozycja) => pozycja.sku)).toEqual(["praca", "zespol"]);
    expect(pozycje[0].availability).toBe("https://schema.org/InStock");
    expect(pozycje[1].availability).toBe("https://schema.org/PreOrder");
  });

  it("cennik bez ani jednej ceny nie daje danych strukturalnych", () => {
    expect(dane([PLANY[0]])).toBeNull();
  });
});
