// Dokumenty prawne opisują stan faktyczny produktu, więc da się je sprawdzić tak jak kod.
// Test pilnuje tych twierdzeń, które przy zmianie zachowania serwera stają się nieprawdziwe
// i których czytelnik sam nie zweryfikuje: przechowywania haseł, rozdzielenia kont, wykazu
// pamięci przeglądarki, odpłatności planów i kierunku rozmowy głosowej.

import { describe, expect, it } from "vitest";
import { COOKIES, POLITYKA_PRYWATNOSCI, REGULAMIN, type DokumentPrawny } from "./tresc-prawna";

function sekcja(dokument: DokumentPrawny, id: string): string {
  const znaleziona = dokument.sekcje.find((pozycja) => pozycja.id === id);
  if (!znaleziona) throw new Error(`Brak rozdziału „${id}” w dokumencie „${dokument.tytul}”.`);
  return znaleziona.tresc;
}

function calosc(dokument: DokumentPrawny): string {
  return dokument.sekcje.map((pozycja) => `${pozycja.tytul}\n${pozycja.tresc}`).join("\n");
}

describe("budowa dokumentów prawnych", () => {
  for (const dokument of [POLITYKA_PRYWATNOSCI, REGULAMIN, COOKIES]) {
    it(`„${dokument.tytul}” ma niepuste rozdziały o niepowtarzalnych kotwicach`, () => {
      const identyfikatory = dokument.sekcje.map((pozycja) => pozycja.id);
      expect(new Set(identyfikatory).size).toBe(identyfikatory.length);
      for (const pozycja of dokument.sekcje) {
        expect(pozycja.tytul.trim().length, pozycja.id).toBeGreaterThan(0);
        expect(pozycja.tresc.trim().length, pozycja.id).toBeGreaterThan(0);
      }
    });
  }
});

describe("polityka prywatności — przechowywanie haseł", () => {
  const bezpieczenstwo = sekcja(POLITYKA_PRYWATNOSCI, "bezpieczenstwo");

  it("ogranicza obietnicę skrótu Argon2 do hasła konta", () => {
    expect(bezpieczenstwo).toContain("Hasło Twojego konta zapisujemy wyłącznie jako skrót algorytmem Argon2");
    // Zdanie o „hasłach” bez zawężenia obejmowałoby też hasło skrzynki, które czytelne być musi.
    expect(bezpieczenstwo).not.toContain("Hasła zapisujemy wyłącznie jako skrót");
    expect(bezpieczenstwo).not.toContain("Nie przechowujemy haseł w postaci jawnej");
  });

  it("mówi wprost, że hasło podłączonej skrzynki zostaje czytelne", () => {
    expect(bezpieczenstwo).toMatch(/hasłem do skrzynki pocztowej/);
    expect(bezpieczenstwo).toMatch(/w postaci czytelnej/);
    expect(bezpieczenstwo).toMatch(/loguje się nim w Twoim imieniu/);
  });
});

describe("polityka prywatności — przestrzeń konta i kredyty", () => {
  it("rozdział o zakresie wiąże przestrzeń konta z planem, a nie z jedną wartością", () => {
    const zakres = sekcja(POLITYKA_PRYWATNOSCI, "zakres");
    for (const fragment of ["rozmowy", "skrzynki pocztowe", "100 MB", "1 GB", "2 GB", "10 GB"]) {
      expect(zakres, fragment).toContain(fragment);
    }
    // Przestrzeń bierze się z planu (backend/nexus/platnosci/plany.py), więc polityka nie
    // może podawać jednej liczby dla wszystkich kont — plan wejściowy ma jej dwukrotnie mniej,
    // a okres próbny dwudziestokrotnie.
    expect(zakres).not.toContain("Na pliki jednego konta przypada 2 GB");
  });

  it("mówi o rozdzieleniu wyszukiwania po znaczeniu, bo indeks filtruje po koncie", () => {
    const zakres = sekcja(POLITYKA_PRYWATNOSCI, "zakres");
    // Każdy fragment niesie w ładunku `owner_id`, a wyszukiwanie dokłada warunek na to pole
    // (backend/nexus/knowledge.py). Polityka nie może już straszyć wspólnym indeksem.
    expect(zakres).not.toContain("we wspólnym indeksie tej instalacji, bez podziału na konta");
    expect(zakres).not.toMatch(/fragment dokumentu zaindeksowanego z innego konta/);
    expect(zakres).toContain("nosi znacznik konta");
    expect(zakres).toMatch(/przeszukuje wyłącznie fragmenty tego konta/);
  });

  it("wymienia kredyty jako kategorię danych, cel przetwarzania i pozycję okresu przechowywania", () => {
    expect(sekcja(POLITYKA_PRYWATNOSCI, "kategorie")).toContain("Kredyty konta");
    expect(sekcja(POLITYKA_PRYWATNOSCI, "podstawy")).toContain("Rozliczenie kredytów");
    expect(sekcja(POLITYKA_PRYWATNOSCI, "okresy")).toContain("Saldo kredytów i księga ich zmian");
  });
});

describe("polityka prywatności — rozmowa głosowa", () => {
  it("stawia Google Cloud jako pierwszy, a modele własne jako zapas", () => {
    const bezpieczenstwo = sekcja(POLITYKA_PRYWATNOSCI, "bezpieczenstwo");
    const kolejnosc = bezpieczenstwo.indexOf("Google Cloud Speech");
    expect(kolejnosc).toBeGreaterThan(-1);
    expect(bezpieczenstwo.indexOf("modele własne Nexusa")).toBeGreaterThan(kolejnosc);
    expect(sekcja(POLITYKA_PRYWATNOSCI, "odbiorcy")).toContain("model lokalny jest zapasem");
  });
});

describe("informacja o plikach cookie — pamięć przeglądarki", () => {
  const pamiec = sekcja(COOKIES, "pamiec");

  it("wymienia każdy wpis, który klient zapisuje w przeglądarce", () => {
    for (const klucz of ["nexus-theme", "nexus-voice", "nexus.research.preferencje", "dn-ladowanie", "nexus-share"]) {
      expect(pamiec, klucz).toContain(klucz);
    }
  });

  it("nie twierdzi, że pamięć podręczna nigdy nie zawiera plików użytkownika", () => {
    expect(pamiec).not.toContain("Pamięć podręczna nie zawiera Twoich plików");
    expect(pamiec).toMatch(/pliki leżą wyłącznie na Twoim urządzeniu/);
  });

  it("rozdział o zgodzie uzasadnia także zasobnik udostępniania", () => {
    expect(sekcja(COOKIES, "zgoda")).toContain("nexus-share");
  });
});

describe("regulamin — zakres usługi i plany", () => {
  const tekst = calosc(REGULAMIN);

  it("nie sprzedaje aplikacji na komputer ani dodatku do przeglądarki jako osobnych produktów", () => {
    expect(sekcja(REGULAMIN, "postanowienia")).not.toContain("aplikacją na komputer i telefon");
    expect(sekcja(REGULAMIN, "postanowienia")).toContain("nie osobny produkt do kupienia");
  });

  it("nie nazywa żadnego planu bezpłatnym", () => {
    expect(tekst).not.toContain("bezpłatn");
    expect(sekcja(REGULAMIN, "plany")).toContain("Wszystkie trzy plany są płatne");
  });

  it("opisuje okres próbny, kredyty i pakiety", () => {
    const plany = sekcja(REGULAMIN, "plany");
    expect(plany).toContain("7 dni");
    expect(plany).toMatch(/saldo wyczerpane|saldzie wyczerpanym/);
    expect(plany).toContain("pakiecie");
    expect(sekcja(REGULAMIN, "postanowienia")).toContain("**Kredyt**");
  });
});
