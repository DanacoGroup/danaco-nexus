// Warstwa ruchu: budowa znaku w momentach, klatka zastępcza tła i kaskada wejścia.
// Sam ruch opisuje CSS — tutaj sprawdzamy to, co widzi drzewo dostępności i układ.

import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { kaskada, useWidocznosc } from "../wejscia";
import { klatkaZastepcza } from "../tla";
import { PrzejscieWidoku } from "../PrzejscieWidoku";
import { TloNaZywo } from "../TloNaZywo";
import { ZnakRuchu, type MomentZnaku } from "../ZnakRuchu";

// Bez `globals: true` biblioteka nie podpina sprzątania sama — bez tego kolejne testy
// szukają elementów w ciele dokumentu zostawionym przez poprzednie.
afterEach(cleanup);

const MOMENTY: MomentZnaku[] = [
  "spoczynek",
  "uruchomienie",
  "uruchomienie-krotkie",
  "logowanie",
  "mysli",
  "sukces",
  "blad",
  "brak-polaczenia",
  "wylogowanie",
  "instalacja",
];

describe("ZnakRuchu", () => {
  it("oznacza moment atrybutem, na którym stoją reguły ruchu", () => {
    for (const moment of MOMENTY) {
      const { container, unmount } = render(<ZnakRuchu moment={moment} />);
      const znak = container.querySelector("svg");
      expect(znak?.getAttribute("data-moment")).toBe(moment);
      expect(znak?.getAttribute("data-widoczny")).toBeTruthy();
      unmount();
    }
  });

  it("bez etykiety jest ozdobą, z etykietą ma nazwę dostępną", () => {
    const { container, unmount } = render(<ZnakRuchu moment="mysli" />);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    unmount();

    render(<ZnakRuchu moment="sukces" etykieta="Zadanie zakończone" />);
    expect(screen.getByRole("img", { name: "Zadanie zakończone" })).toBeTruthy();
  });

  it("ma wszystkie części potrzebne momentom: łuk w dwóch połowach, iskrę, punkt i poświatę", () => {
    const { container } = render(<ZnakRuchu moment="uruchomienie" />);
    for (const czesc of ["aura", "luk-szary", "luk", "polowa-lewa", "polowa-prawa", "rozblysk", "iskra", "punkt"]) {
      expect(container.querySelector(`.znak-ruch__${czesc}`)).toBeTruthy();
    }
  });
});

describe("Tło na żywo", () => {
  it("podaje klatkę zastępczą w obu proporcjach, zanim scena się zbuduje", () => {
    const { container } = render(<TloNaZywo nazwa="aurora" />);
    const warstwa = container.querySelector<HTMLElement>(".ruch-tlo");
    expect(warstwa).toBeTruthy();
    expect(warstwa!.getAttribute("aria-hidden")).toBe("true");
    expect(warstwa!.style.getPropertyValue("--klatka")).toContain("aurora-1920x1080.avif");
    expect(warstwa!.style.getPropertyValue("--klatka-pion")).toContain("aurora-1170x2532.avif");
  });

  it("nie podaje klatki dla teł rysowanych samym CSS", () => {
    expect(klatkaZastepcza("swit")).toEqual({});
    expect(klatkaZastepcza("ziarno")).toEqual({});
  });
});

describe("Kaskada wejścia", () => {
  it("liczy opóźnienie z tokenów, a nie z wartości czasu w kodzie", () => {
    const styl = kaskada(3) as Record<string, string>;
    expect(styl["--ui-opoznienie"]).toBe("calc(var(--stagger-step) * min(3, var(--stagger-max)))");
  });
});

/** Obserwator do testów: trzyma obserwowane węzły i na żądanie zgłasza wejście w kadr. */
class ObserwatorKadru {
  static ostatni: ObserwatorKadru | null = null;
  cele = new Set<Element>();

  constructor(private readonly wywolanie: IntersectionObserverCallback) {
    ObserwatorKadru.ostatni = this;
  }

  observe(cel: Element) {
    this.cele.add(cel);
  }

  unobserve(cel: Element) {
    this.cele.delete(cel);
  }

  disconnect() {
    this.cele.clear();
  }

  zglos(wartosc: boolean) {
    const wpisy = [...this.cele].map((cel) => ({ target: cel, isIntersecting: wartosc }));
    this.wywolanie(wpisy as unknown as IntersectionObserverEntry[], this as unknown as IntersectionObserver);
  }
}

function zainstalujObserwator() {
  const poprzedni = globalThis.IntersectionObserver;
  ObserwatorKadru.ostatni = null;
  globalThis.IntersectionObserver = ObserwatorKadru as unknown as typeof IntersectionObserver;
  return () => {
    globalThis.IntersectionObserver = poprzedni;
  };
}

/** Kroki instalacji w miniaturze: lista pod przejściem widoku, odsłaniana kaskadą. */
function KrokiPodPrzejsciem({ klucz }: { klucz: string }) {
  const [lista, widoczne] = useWidocznosc<HTMLOListElement>();
  return (
    <PrzejscieWidoku klucz={klucz}>
      <ol ref={lista} data-testid="kroki" data-widoczny={widoczne ? "true" : "false"}>
        <li>{klucz}</li>
      </ol>
    </PrzejscieWidoku>
  );
}

describe("Widoczność w kadrze", () => {
  it("po przemontowaniu poddrzewa obserwuje nowy węzeł, nie stary", () => {
    const przywroc = zainstalujObserwator();
    try {
      const { rerender, getByTestId } = render(<KrokiPodPrzejsciem klucz="windows" />);
      const pierwsza = getByTestId("kroki");
      expect(ObserwatorKadru.ostatni?.cele.has(pierwsza)).toBe(true);

      rerender(<KrokiPodPrzejsciem klucz="android" />);
      const druga = getByTestId("kroki");
      expect(druga).not.toBe(pierwsza);
      expect(ObserwatorKadru.ostatni?.cele.has(pierwsza)).toBe(false);
      expect(ObserwatorKadru.ostatni?.cele.has(druga)).toBe(true);

      act(() => ObserwatorKadru.ostatni?.zglos(true));
      expect(getByTestId("kroki").getAttribute("data-widoczny")).toBe("true");
    } finally {
      przywroc();
    }
  });

  it("odsłonięta treść zostaje widoczna po kolejnej podmianie widoku", () => {
    const przywroc = zainstalujObserwator();
    try {
      const { rerender, getByTestId } = render(<KrokiPodPrzejsciem klucz="windows" />);
      act(() => ObserwatorKadru.ostatni?.zglos(true));
      rerender(<KrokiPodPrzejsciem klucz="ios" />);
      expect(getByTestId("kroki").getAttribute("data-widoczny")).toBe("true");
    } finally {
      przywroc();
    }
  });
});

describe("Przejście widoku", () => {
  afterEach(() => {
    Reflect.deleteProperty(document, "startViewTransition");
  });

  it("bez obsługi przejść podmienia treść od razu", () => {
    const { rerender, getByTestId } = render(<KrokiPodPrzejsciem klucz="windows" />);
    expect(getByTestId("kroki").textContent).toBe("windows");
    rerender(<KrokiPodPrzejsciem klucz="android" />);
    expect(getByTestId("kroki").textContent).toBe("android");
  });

  it("nazywa sam podmieniany obszar, zdejmuje nazwę korzenia i zwalnia ją po przejściu", async () => {
    const wKadrzePrzejscia: Array<{ korzen: boolean; nazwa: string; znacznik: string | null }> = [];
    const przebieg = {
      finished: Promise.resolve(),
      ready: Promise.resolve(),
      updateCallbackDone: Promise.resolve(),
      skipTransition: () => undefined,
    };
    Object.defineProperty(document, "startViewTransition", {
      configurable: true,
      writable: true,
      value: (wywolanie: () => void) => {
        wywolanie();
        const obszar = document.querySelector<HTMLElement>(".ruch-widok");
        wKadrzePrzejscia.push({
          korzen: document.documentElement.classList.contains("ruch-przejscie"),
          nazwa: obszar?.style.getPropertyValue("view-transition-name") ?? "",
          znacznik: obszar?.getAttribute("data-przejscie") ?? null,
        });
        return przebieg;
      },
    });

    const { rerender, container } = render(<KrokiPodPrzejsciem klucz="windows" />);
    rerender(<KrokiPodPrzejsciem klucz="android" />);
    await act(async () => {
      await przebieg.finished;
    });

    expect(wKadrzePrzejscia).toHaveLength(1);
    expect(wKadrzePrzejscia[0]).toEqual({ korzen: true, nazwa: "ruch-widok", znacznik: "true" });
    const obszar = container.querySelector<HTMLElement>(".ruch-widok");
    expect(document.documentElement.classList.contains("ruch-przejscie")).toBe(false);
    expect(obszar?.style.getPropertyValue("view-transition-name")).toBe("");
    expect(obszar?.hasAttribute("data-przejscie")).toBe(false);
  });
});
