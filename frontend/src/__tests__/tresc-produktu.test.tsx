// Treść dla użytkownika: język polski, jedna nazwa na byt, liczby z rejestru i obietnice
// pokrywające się z tym, co produkt robi. Testy pilnują tekstów, których nie widać w typach.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ODSYLACZE_PRAWNE } from "../landing/Landing";
import {
  DZIEN,
  FILMY,
  GWARANCJE,
  KARTY,
  KROKI,
  LICZBY,
  NAGRANIA,
  PLANY,
  PYTANIA as PYTANIA_PRODUKTU,
  ROZNICE,
  ZASADY,
} from "../landing/tresc";
import { Brama, SekcjaCennik, SekcjaFilmy } from "../landing/sekcje";
import { LICZBA_NARZEDZI } from "../dane/narzedzia";
import { module as modulChmury } from "../modules/cloud";
import { module as modulStron } from "../modules/strony";
import { nazwaRodzaju } from "../modules/research";
import { FUNKCJONALNOSCI, OFERTA, PYTANIA } from "../portal/tresc";
import { Funkcje } from "../portal/strony/Funkcje";
import { parsujTrase } from "../portal/trasy";
// Źródło strony produktu jako tekst: hero jest w JSX, więc nie da się go objąć
// przez stałe treści, a to właśnie w nim przeżyła obietnica „pod swoim adresem”.
import zrodloLandingu from "../landing/Landing.tsx?raw";

afterEach(() => {
  cleanup();
  document.head.querySelectorAll("[data-portal-seo]").forEach((element) => element.remove());
});

describe("moduł Badania", () => {
  it("nazywa rodzaj badania po polsku", () => {
    expect(nazwaRodzaju("scholar")).toBe("Prace naukowe");
    expect(nazwaRodzaju("deep")).toBe("Sieć");
  });
});

describe("stopka strony produktu", () => {
  it("prowadzi do polityki prywatności, regulaminu i plików cookie", () => {
    const adresy = ODSYLACZE_PRAWNE.map((pozycja) => pozycja.adres);
    expect(adresy).toEqual(["/portal/prywatnosc", "/portal/regulamin", "/portal/cookies"]);
    expect(adresy.map((adres) => parsujTrase(adres).strona)).toEqual(["prywatnosc", "regulamin", "cookies"]);
    expect(ODSYLACZE_PRAWNE.map((pozycja) => pozycja.etykieta)).toEqual([
      "Polityka prywatności",
      "Regulamin",
      "Pliki cookie",
    ]);
  });
});

describe("liczba narzędzi na stronie produktu", () => {
  const teksty = [
    ...GWARANCJE.map((pozycja) => pozycja.opis),
    ...ROZNICE.map((pozycja) => pozycja.opis),
    ...LICZBY.map((pozycja) => `${pozycja.liczba} ${pozycja.podpis}`),
  ];

  it("podaje liczbę z rejestru agenta", () => {
    expect(LICZBY[0]).toEqual({ liczba: String(LICZBA_NARZEDZI), podpis: "narzędzi w rejestrze agenta" });
    expect(teksty.filter((tekst) => tekst.includes(`${LICZBA_NARZEDZI} narzędzi`)).length).toBeGreaterThan(1);
  });

  it("nie wpisuje żadnej innej liczby narzędzi", () => {
    for (const tekst of teksty) {
      for (const [, liczba] of tekst.matchAll(/(\d+)\s+narzędzi/g)) {
        expect(liczba).toBe(String(LICZBA_NARZEDZI));
      }
    }
  });
});

describe("nagłówki strony produktu", () => {
  it("nie powtarza tego samego nagłówka", () => {
    const naglowki = [
      ...KROKI.map((pozycja) => pozycja.tytul),
      ...KARTY.map((pozycja) => pozycja.naglowek),
      ...DZIEN.map((pozycja) => pozycja.tytul),
      ...NAGRANIA.map((pozycja) => pozycja.tytul),
      ...ROZNICE.map((pozycja) => pozycja.tytul),
      ...ZASADY.map((pozycja) => pozycja.tytul),
      ...GWARANCJE.map((pozycja) => pozycja.tytul),
    ];
    expect(new Set(naglowki).size).toBe(naglowki.length);
  });
});

describe("strona Funkcje w portalu", () => {
  it("ma jedną nazwę w tytule i korzyść w nagłówku", () => {
    render(<Funkcje />);
    expect(document.title).toBe("Funkcje — Danaco Nexus");
    const naglowek = screen.getByRole("heading", { level: 1 }).textContent ?? "";
    // Nagłówek ma mówić, co czytelnik z tego ma — nie powtarzać nazwy zakładki. Samo
    // brzmienie jest sprawą redakcji, więc test pilnuje kształtu, a nie jednego zdania:
    // wcześniej przypięty literał psuł się przy każdej poprawce tekstu.
    expect(naglowek.trim().split(/\s+/).length).toBeGreaterThanOrEqual(3);
    expect(naglowek.trim()).not.toBe("Funkcje");
    expect(document.body.textContent).not.toContain("Funkcjonalnoś");
  });
});

describe("obietnica publikacji strony", () => {
  const teksty = [
    ...OFERTA.flatMap((pozycja) => [pozycja.opis, ...pozycja.zakres]),
    ...FUNKCJONALNOSCI.map((pozycja) => pozycja.opis),
    ...PYTANIA.map((pozycja) => `${pozycja.pytanie} ${pozycja.odpowiedz}`),
    modulStron.description,
    // Strona produktu też to obiecuje, a wcześniej test jej nie obejmował: obietnica
    // „pod swoim adresem” przeżyła w nagłówku hero, choć w portalu była już poprawiona.
    ...KARTY.map((pozycja) => `${pozycja.naglowek} ${pozycja.opis} ${pozycja.narzedzia}`),
    ...ROZNICE.map((pozycja) => pozycja.opis),
    ...KROKI.map((pozycja) => pozycja.opis),
    ...GWARANCJE.map((pozycja) => pozycja.opis),
    ...PYTANIA_PRODUKTU.map((pozycja) => `${pozycja.pytanie} ${pozycja.odpowiedz}`),
    zrodloLandingu,
  ];

  // „Swoim adresem” mówimy też o adresie e-mail przy zakładaniu konta i to jest prawda —
  // zakazana jest wyłącznie obietnica, że **strona** staje pod adresem użytkownika.
  const ADRES_UZYTKOWNIKA = /(własnym|Twoim|swoim) adresem(?!\s+(e-mail|pocztow|poczty))/i;

  it("nie obiecuje publikacji pod adresem użytkownika", () => {
    for (const tekst of teksty) {
      expect(tekst).not.toMatch(ADRES_UZYTKOWNIKA);
    }
  });

  it("podaje postać adresu, pod którym strona staje", () => {
    expect(teksty.filter((tekst) => tekst.includes("/s/nazwa-strony/")).length).toBeGreaterThan(0);
  });
});

describe("cennik na stronie produktu i w portalu", () => {
  // Katalog planów (backend/nexus/platnosci/plany.py) nie ma planu bezpłatnego: wszystkie trzy
  // poziomy są płatne, a Osobisty otwiera 7 dni próbnych z kartą podaną od razu. Obietnica
  // darmowego produktu na stronie sprzedażowej byłaby więc nieprawdziwa wobec tego, co dzieje
  // się po siódmym dniu, a tego czytelnik sam nie sprawdzi.
  const DARMOWE = /bezpłatn|za darmo|bez opłat|0 zł/;

  it("nie obiecuje planu bez opłaty w danych planów", () => {
    for (const plan of PLANY) {
      expect(`${plan.znacznik} ${plan.cena}`, plan.nazwa).not.toMatch(DARMOWE);
    }
  });

  // Katalog planów zna limit „automatyzacje”, ale modułu, w którym dałoby się je ustawić,
  // w produkcie nie ma (`backend/nexus/platnosci/uprawnienia.py`). Dopóki go nie ma, karta
  // planu nie może ich obiecywać — kupujący sprawdzi to pierwszego dnia.
  it("nie obiecuje automatyzacji, których produkt jeszcze nie robi", () => {
    for (const plan of PLANY) {
      expect(plan.zawartosc.join(" "), plan.nazwa).not.toMatch(/automatyzacj/i);
    }
  });

  it("odpowiada o cenie okresem próbnym, nie bezpłatnością", () => {
    const oCenie = PYTANIA_PRODUKTU.filter((pozycja) => pozycja.pytanie.includes("kosztuje"));
    expect(oCenie.length).toBeGreaterThan(0);
    for (const pozycja of [...oCenie, ...PYTANIA_PRODUKTU, ...PYTANIA]) {
      expect(pozycja.odpowiedz, pozycja.pytanie).not.toMatch(DARMOWE);
    }
    for (const pozycja of oCenie) {
      expect(pozycja.odpowiedz).toContain("7 dni próbnych");
    }
  });

  it("nie obiecuje bezpłatności w sekcjach, które widzi gość", () => {
    const { container: cennik, unmount } = render(<SekcjaCennik />);
    expect(cennik.textContent).not.toMatch(DARMOWE);
    expect(cennik.textContent).toContain("7 dni próbnych");
    unmount();

    const { container: brama } = render(<Brama instaluj={null} />);
    expect(brama.textContent).not.toMatch(DARMOWE);
    expect(brama.textContent).toContain("7 dni próbnych");
  });
});

describe("uruchomienie opisane w portalu", () => {
  // Klient dostaje cienką instalację z przeglądarki i loguje się kontem portalu
  // (backend/nexus/api/auth.py, `_konto_portalu`). Odesłanie go do polecenia na serwerze
  // kazałoby mu zrobić coś, czego w tym modelu wdrożenia nie ma jak wykonać.
  const uruchomienie = PYTANIA.find((pozycja) => pozycja.pytanie.includes("uruchomienie"));

  it("nie odsyła klienta do polecenia na serwerze ani do konta administratora", () => {
    expect(uruchomienie).toBeTruthy();
    expect(uruchomienie?.odpowiedz).not.toMatch(/nexus-cli|set-password|administrator/i);
  });

  it("mówi, że do aplikacji wpuszcza konto portalu", () => {
    expect(uruchomienie?.odpowiedz).toContain("konto w portalu");
    expect(uruchomienie?.odpowiedz).toMatch(/logujesz się do aplikacji/);
  });
});

describe("podpowiedź synchronizacji kalendarza", () => {
  it("wskazuje moduł o nazwie, którą widzi użytkownik", () => {
    // Instrukcja w module Kalendarz odsyła do „moduł Chmura → Synchronizacja”; test pilnuje obu nazw.
    expect(modulChmury.label).toBe("Chmura");
  });
});

describe("sekcja z filmami na stronie produktu", () => {
  it("pokazuje oba filmy z tytułem i zdaniem opisu", () => {
    render(<SekcjaFilmy />);
    expect(screen.getByRole("heading", { level: 2 }).textContent).toContain("Nexusa w działaniu");
    FILMY.forEach((film) => {
      expect(screen.getByRole("heading", { level: 3, name: film.tytul })).toBeTruthy();
      expect(screen.getByText(film.opis)).toBeTruthy();
    });
  });

  it("opisuje oba zakresy: życie codzienne i pracę zawodową", () => {
    const opisy = FILMY.map((film) => film.opis.toLowerCase());
    expect(opisy.some((opis) => opis.includes("życie codzienne"))).toBe(true);
    expect(opisy.some((opis) => opis.includes("praca zawodowa"))).toBe(true);
  });

  it("po kliknięciu plakatu otwiera film w powiększeniu", () => {
    render(<SekcjaFilmy />);
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByLabelText(/Odtwórz film „Nexus w pracy”/));
    expect(screen.getByRole("dialog").getAttribute("aria-label")).toContain("Nexus w pracy");
    fireEvent.click(screen.getByRole("button", { name: "Zamknij" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
