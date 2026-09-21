// Wersja mobilna: nawigacja strony produktu i pusty ekran rozmowy na telefonie.
//
// Pasek strony chował wszystkie odsyłacze poniżej `lg`, a „Zaloguj się” poniżej `sm` —
// na telefonie zostawał sam przycisk instalacji i do cennika czy logowania trzeba było
// przewinąć całą stronę do stopki. Pusty ekran rozmowy stawiał z kolei osiem kafli
// w jednej kolumnie, czyli półtora ekranu przewijania przed polem wiadomości.

import { afterEach, describe, expect, it } from "vitest";
import sidebarSource from "../components/Sidebar.tsx?raw";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MenuMobilne } from "../landing/Landing";
import { SEKCJE_NAWIGACJI } from "../landing/sekcje";
import { EkranWylogowania } from "../shell/EkranWylogowania";
import { PasekKontaProbnego } from "../shell/PasekKontaProbnego";

afterEach(cleanup);

/** Element jest schowany na telefonie, jeśli ma klasę `hidden` bez wariantu `max-`. */
function schowanyNaTelefonie(element: Element | null): boolean {
  const klasy = String(element?.className ?? "").split(/\s+/);
  return klasy.includes("hidden") && klasy.some((k) => /^(sm|md|lg|xl):(inline|block|flex|grid)/.test(k));
}

describe("pasek konta próbnego na telefonie", () => {
  it("ma krótszą wersję zdania i pełną dopiero od `sm`", () => {
    const { container } = render(<PasekKontaProbnego onZaloz={() => undefined} />);
    const pelne = [...container.querySelectorAll("span")].find((s) =>
      s.textContent?.includes("Pracujesz w pełnej aplikacji"),
    );
    const krotkie = [...container.querySelectorAll("span")].find(
      (s) => s.textContent === "dane znikną po wyjściu",
    );
    expect(schowanyNaTelefonie(pelne ?? null)).toBe(true);
    expect(krotkie).toBeTruthy();
    expect(String(krotkie?.className)).toContain("sm:hidden");
  });

  it("przycisk „Załóż konto” nie kurczy się przy wąskim ekranie", () => {
    render(<PasekKontaProbnego onZaloz={() => undefined} />);
    const przycisk = screen.getByRole("button", { name: "Załóż konto" });
    expect(przycisk.className).toContain("shrink-0");
  });

  it("wywołuje założenie konta po kliknięciu", () => {
    let wywolane = false;
    render(<PasekKontaProbnego onZaloz={() => (wywolane = true)} />);
    fireEvent.click(screen.getByRole("button", { name: "Załóż konto" }));
    expect(wywolane).toBe(true);
  });
});

describe("menu strony produktu na telefonie", () => {
  it("jest zwinięte, dopóki nikt go nie otworzy", () => {
    render(<MenuMobilne aktywna="funkcje" />);
    const przycisk = screen.getByRole("button", { name: "Otwórz menu" });
    expect(przycisk.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("link", { name: "Cennik" })).toBeNull();
  });

  it("po otwarciu podaje wszystkie sekcje paska oraz logowanie i wypróbowanie", () => {
    render(<MenuMobilne aktywna="funkcje" />);
    fireEvent.click(screen.getByRole("button", { name: "Otwórz menu" }));
    for (const { etykieta } of SEKCJE_NAWIGACJI) {
      expect(screen.getByRole("link", { name: etykieta })).toBeTruthy();
    }
    expect(screen.getByRole("link", { name: "Zaloguj się" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Wypróbuj bez rejestracji" })).toBeTruthy();
  });

  it("zaznacza sekcję, na której stoi strona", () => {
    render(<MenuMobilne aktywna="cennik" />);
    fireEvent.click(screen.getByRole("button", { name: "Otwórz menu" }));
    const cennik = screen.getByRole("link", { name: "Cennik" });
    expect(cennik.getAttribute("aria-current")).toBe("true");
  });

  it("zamyka się po wybraniu pozycji i po klawiszu Escape", () => {
    render(<MenuMobilne aktywna="funkcje" />);
    fireEvent.click(screen.getByRole("button", { name: "Otwórz menu" }));
    fireEvent.click(screen.getByRole("link", { name: "Cennik" }));
    expect(screen.queryByRole("link", { name: "Cennik" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Otwórz menu" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("link", { name: "Cennik" })).toBeNull();
  });

  it("znika na dużym ekranie, gdzie pasek pokazuje odsyłacze wprost", () => {
    const { container } = render(<MenuMobilne aktywna="funkcje" />);
    expect(String(container.firstElementChild?.className)).toContain("lg:hidden");
  });
});

describe("ekran wylogowania", () => {
  it("melduje wylogowywanie i pokazuje ujęcie zamknięcia sesji", () => {
    const { container } = render(<EkranWylogowania onKoniec={() => undefined} />);
    expect(screen.getByRole("status", { name: "Wylogowywanie" })).toBeTruthy();
    expect(container.querySelector("video")).toBeTruthy();
  });

  it("przechodzi dalej po zakończeniu ujęcia", () => {
    let gotowe = false;
    const { container } = render(<EkranWylogowania onKoniec={() => (gotowe = true)} />);
    fireEvent.ended(container.querySelector("video")!);
    expect(gotowe).toBe(true);
  });

  it("nie zatrzymuje wyjścia, gdy nagranie się nie wczyta", () => {
    let gotowe = false;
    const { container } = render(<EkranWylogowania onKoniec={() => (gotowe = true)} />);
    fireEvent.error(container.querySelector("video")!);
    expect(gotowe).toBe(true);
  });
});

describe("nagrania na stronie", () => {
  it("stają, gdy wyjdą z pola widzenia, i wracają, gdy w nie wejdą", async () => {
    // Pętla chodząca przez całą wizytę dekoduje obraz, którego nikt nie widzi.
    const { useOdtwarzajWWidoku } = await import("../ruch");
    const { renderHook } = await import("@testing-library/react");

    type Zgloszenie = (wpisy: Array<{ isIntersecting: boolean }>) => void;
    let zglos: Zgloszenie | undefined;
    const pierwotny = window.IntersectionObserver;
    // @ts-expect-error — atrapa obserwatora na czas testu
    window.IntersectionObserver = class {
      constructor(fn: Zgloszenie) {
        zglos = fn;
      }
      observe() {}
      disconnect() {}
    };

    const element = document.createElement("video");
    let grane = 0;
    let stanie = 0;
    element.play = () => {
      grane += 1;
      return Promise.resolve();
    };
    element.pause = () => {
      stanie += 1;
    };
    renderHook(() => useOdtwarzajWWidoku({ current: element }));

    zglos?.([{ isIntersecting: true }]);
    expect(grane).toBe(1);
    zglos?.([{ isIntersecting: false }]);
    expect(stanie).toBe(1);
    zglos?.([{ isIntersecting: true }]);
    expect(grane).toBe(2);

    window.IntersectionObserver = pierwotny;
  });
});

describe("wejście i wyjście z aplikacji", () => {
  it("logowanie nie puszcza filmu o logowaniu pod formularzem", async () => {
    // Ujęcie „logowanie” pokazuje to, co dopiero ma się wydarzyć, a chodziło w tle pól,
    // w których człowiek właśnie pisze.
    const { Login } = await import("../components/Login");
    const { container } = render(<Login onLoggedIn={() => undefined} />);
    expect(container.querySelector("video")).toBeNull();
    expect(screen.getByRole("button", { name: "Zaloguj się" })).toBeTruthy();
  });
});

describe("panel rozmów na telefonie", () => {
  // Przesunięty za krawędź panel dalej stoi w kolejności tabulacji i w drzewie
  // dostępności: pomiar na ekranie 390 px pokazał pięć takich kontrolek („Zamknij
  // panel”, pole szukania, „Nowa rozmowa”, „Więcej działań”, przycisk konta).
  const zrodlo = sidebarSource;

  it("schowany panel znika też dla klawiatury", () => {
    expect(zrodlo).toContain('invisible -translate-x-full');
  });

  it("na komputerze panel zostaje widoczny", () => {
    expect(zrodlo).toContain("md:visible");
  });

  it("chowanie nadal jest płynne", () => {
    expect(zrodlo).toContain("transition-[transform,visibility]");
  });
});
