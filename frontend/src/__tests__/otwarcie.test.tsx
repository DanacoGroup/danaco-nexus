// Otwarcie strony produktu: jedna plansza zamiast dwóch.
//
// Przedtem po ekranie ładowania marki wchodziła jeszcze nakładka Reacta z nagraniem
// `intro-znaku` — pakiet aplikacji wczytywał się ponad sekundę, więc odwiedzający widział
// otwarcie, potem gotową stronę, a potem znowu zasłonę z tym samym znakiem. Teraz otwarcie
// rysuje wyłącznie ekran ładowania, a strona czeka z wejściem na jego sygnał.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render } from "@testing-library/react";
import { otwarcieZagra, useOtwarcie } from "../ruch/otwarcie";
// Treść dokumentu i źródła strony produktu jako tekst — bez `node:fs`, którego interfejs
// nie ma w typach (`tsconfig` zna tylko `vite/client` i `vitest/globals`).
import html from "../../index.html?raw";
import opcje from "../../public/ladowanie/opcje.js?raw";
import ladowanie from "../../public/ladowanie/ladowanie.js?raw";
import landing from "../landing/Landing.tsx?raw";
import { Login } from "../components/Login";

function Sonda() {
  return <span data-stan={useOtwarcie() ? "gra" : "po"}>stan</span>;
}

function stan(): string | null {
  return document.querySelector("span")?.getAttribute("data-stan") ?? null;
}

// Wstrzymanie wejścia ma termin ważności liczony od otwarcia dokumentu
// (`GRANICA_WSTRZYMANIA_MS`), a w przeglądarce mierzy go `performance.now()`. W teście ten
// sam zegar liczy od startu procesu vitest, więc po kilkudziesięciu plikach w tym samym
// wątku granica była już przekroczona, zanim ten plik ruszył — testy przechodziły albo nie
// w zależności od tego, co uruchomiono wcześniej. Zatrzymanie zegara na zerze bierze je
// z powrotem pod kontrolę: sprawdzamy zachowanie, a nie szybkość maszyny.
beforeEach(() => {
  vi.spyOn(performance, "now").mockReturnValue(0);
});

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
  document.documentElement.classList.remove("dn-ladowanie-trwa");
  document.querySelectorAll(".dn-ladowanie").forEach((w) => w.remove());
});

describe("otwarcie strony produktu", () => {
  function plansza(...klasy: string[]) {
    document.documentElement.classList.add("dn-ladowanie-trwa");
    const warstwa = document.createElement("div");
    warstwa.className = ["dn-ladowanie", ...klasy].join(" ");
    document.body.appendChild(warstwa);
    return warstwa;
  }

  it("wstrzymuje wejście, dopóki plansza zasłania stronę", () => {
    plansza();
    expect(otwarcieZagra()).toBe(true);
    render(<Sonda />);
    expect(stan()).toBe("gra");
  });

  it("puszcza wejście z chwilą, gdy łuk rusza w stronę hero", () => {
    plansza();
    render(<Sonda />);
    expect(stan()).toBe("gra");
    act(() => {
      window.dispatchEvent(new CustomEvent("dn:ladowanie-przejscie", { detail: { pominiete: false, czas: 900 } }));
    });
    expect(stan()).toBe("po");
  });

  it("nie wstrzymuje niczego, gdy plansza już przelatuje w hero", () => {
    plansza("dn-ladowanie--przejscie");
    expect(otwarcieZagra()).toBe(false);
    render(<Sonda />);
    expect(stan()).toBe("po");
  });

  it("nie wstrzymuje niczego, gdy plansza została pominięta", () => {
    plansza("dn-ladowanie--pomin");
    expect(otwarcieZagra()).toBe(false);
  });

  it("nie wstrzymuje niczego, gdy plansza zeszła, zanim pakiet ruszył", () => {
    // Na produkcji plansza potrafi zejść przed wykonaniem pakietu aplikacji — wtedy
    // `dn:ladowanie-przejscie` przepada, bo nie ma jeszcze kto go usłyszeć.
    document.documentElement.classList.add("dn-ladowanie-koniec");
    expect(otwarcieZagra()).toBe(false);
    render(<Sonda />);
    expect(stan()).toBe("po");
    document.documentElement.classList.remove("dn-ladowanie-koniec");
  });

  it("po granicy czasu nie wstrzymuje wejścia", () => {
    // Na łączu tak wolnym, że sam pakiet aplikacji wchodzi później niż granica,
    // wstrzymania nie ma wcale: pierwsze wyrysowanie i tak jest później.
    const poprzednie = performance.now;
    performance.now = () => 5000;
    plansza();
    expect(otwarcieZagra()).toBe(false);
    render(<Sonda />);
    expect(stan()).toBe("po");
    performance.now = poprzednie;
  });

  it("przy ograniczonym ruchu nie wstrzymuje wejścia", () => {
    // Wejście jest wtedy skrócone do 0,01 ms, ale „animation-play-state: paused”
    // zatrzymałoby je i tak w pierwszej klatce — czyli przy kryciu zero.
    const poprzednie = window.matchMedia;
    window.matchMedia = ((zapytanie: string) =>
      ({
        matches: zapytanie.includes("prefers-reduced-motion"),
        media: zapytanie,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }) as unknown as MediaQueryList) as typeof window.matchMedia;
    plansza();
    expect(otwarcieZagra()).toBe(false);
    render(<Sonda />);
    expect(stan()).toBe("po");
    window.matchMedia = poprzednie;
  });

  it("nie wstrzymuje niczego, gdy planszy w ogóle nie ma", () => {
    expect(otwarcieZagra()).toBe(false);
    render(<Sonda />);
    expect(stan()).toBe("po");
  });
});

describe("wpięcie planszy w dokument", () => {
  it("ogranicza czekanie na gotowość", () => {
    // Domyślne dziesięć sekund to wieczność na ekranie: przy kiepskim łączu plansza
    // trzymałaby stronę pod zasłoną dłużej, niż ktokolwiek zechce patrzeć na znak.
    expect(opcje).toContain("maks: 4000");
  });

  it("nie kasuje otwarcia na gotowej stronie", () => {
    // Domyślny próg 150 ms znosił planszę, gdy strona była gotowa szybciej — czyli
    // przy pamięci podręcznej i szybkim łączu otwarcia nie było w ogóle.
    expect(opcje).toContain("prog: 0");
  });

  it("podaje opcje osobnym plikiem, nie skryptem w treści strony", () => {
    // Nagłówek Content-Security-Policy aplikacji ma „script-src 'self'” bez
    // „'unsafe-inline'”: skrypt wpisany w stronę wprost nie wykona się na produkcji
    // ani razu, a plansza wróci do domyślnego progu i zniknie na gotowej stronie.
    expect(html).toContain('<script src="/ladowanie/opcje.js" defer></script>');
    expect(html).not.toMatch(/<script>[^<]*DanacoLadowanieOpcje/);
  });

  it("ustawia opcje przed skryptem planszy", () => {
    expect(html.indexOf("/ladowanie/opcje.js")).toBeLessThan(html.indexOf("/ladowanie/ladowanie.js"));
  });

  it("gra raz na sesję przeglądarki", () => {
    expect(html).toContain('data-raz="sesja"');
  });

  it("nie zostawia w stronie produktu drugiej planszy", () => {
    // Nakładka `Otwarcie` z nagraniem `intro-znaku` grała już po ekranie ładowania marki
    // — ten sam znak drugi raz, biały i bez Aurory.
    expect(landing).not.toContain("<Otwarcie");
    expect(landing).toContain("data-dn-brama");
  });
});

describe("otwarcie ekranu logowania", () => {
  function plansza(...klasy: string[]) {
    document.documentElement.classList.add("dn-ladowanie-trwa");
    const warstwa = document.createElement("div");
    warstwa.className = ["dn-ladowanie", ...klasy].join(" ");
    document.body.appendChild(warstwa);
    return warstwa;
  }

  function karta(): Element | null {
    return document.querySelector(".logowanie");
  }

  it("karta logowania czeka, aż plansza naprawdę zejdzie", () => {
    plansza();
    render(<Login onLoggedIn={() => undefined} />);
    // Pauza w pierwszej klatce `rise` znaczy krycie zero — karty nie widać.
    expect(karta()?.getAttribute("data-otwarcie")).toBe("gra");
    // Strona produktu wchodzi już przy **początku** przelotu, bo znak wtapia się w łuk
    // hero. Na logowaniu łuku hero nie ma, znak gaśnie w miejscu — więc początek
    // przelotu niczego tu nie zwalnia, inaczej gasnący znak leżałby na formularzu.
    act(() => {
      window.dispatchEvent(new CustomEvent("dn:ladowanie-przejscie", { detail: { pominiete: false, czas: 900 } }));
    });
    expect(karta()?.getAttribute("data-otwarcie")).toBe("gra");
    act(() => {
      window.dispatchEvent(new CustomEvent("dn:ladowanie-koniec", { detail: { pominiete: false, czas: 1220 } }));
    });
    expect(karta()?.getAttribute("data-otwarcie")).toBe("po");
  });

  it("plansza zdjęta bez przelotu nie wstrzymuje karty", () => {
    plansza("dn-ladowanie--pomin");
    render(<Login onLoggedIn={() => undefined} />);
    expect(karta()?.getAttribute("data-otwarcie")).toBe("po");
  });

  it("bez planszy karta wchodzi od razu", () => {
    render(<Login onLoggedIn={() => undefined} />);
    expect(karta()?.getAttribute("data-otwarcie")).toBe("po");
  });
});

describe("przelot planszy bez bramy", () => {
  it("nie rozdyma znaku do rozmiaru ekranu, gdy nie ma w co wlecieć", () => {
    // Plansza kończy się przelotem: łuk znaku wlatuje w łuk hero. Na logowaniu i w oknie
    // aplikacji łuku hero nie ma, a zapasowy cel miał promień 0,7 szerokości ekranu —
    // biały pałąk szedł wtedy przez całą stronę, w poprzek karty logowania. Czytamy plik,
    // który naprawdę trafia do przeglądarki (`frontend/public` to kopia z `landing/`).
    expect(ladowanie).not.toContain("Math.max(W, H) * 0.7");
    // Bez bramy cel jest tożsamy ze znakiem: nic nie leci, znak gaśnie w miejscu.
    const zapas = ladowanie.slice(ladowanie.indexOf("function mierzBrame"));
    const koniec = zapas.indexOf("function klatka");
    expect(zapas.slice(0, koniec)).toContain("r: LUK.r * k");
  });
});
