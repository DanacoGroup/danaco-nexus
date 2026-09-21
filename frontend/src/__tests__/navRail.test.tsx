import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { BottomBar, CHAT_ENTRY, NavRail, VOICE_ENTRY, grupyNawigacji, navEntries, podzialPaska, type NavEntry } from "../shell/ModuleNav";
import { MODULES } from "../modules/registry";

afterEach(cleanup);

function ikona() {
  return <svg />;
}

const DUZO: NavEntry[] = Array.from({ length: 18 }, (_, numer) => ({
  id: `modul-${numer}`,
  label: `Moduł ${numer}`,
  description: `Opis ${numer}`,
  icon: ikona,
}));

describe("pasek modułów", () => {
  it("pokazuje wszystkie pozycje, także gdy jest ich więcej niż mieści ekran", () => {
    render(<NavRail entries={DUZO} activeId="modul-0" onSelect={() => undefined} />);
    for (const pozycja of DUZO) {
      expect(screen.getByRole("button", { name: pozycja.label })).toBeTruthy();
    }
  });

  it("lista modułów jest przewijalna, a nie przycięta", () => {
    const { container } = render(<NavRail entries={DUZO} activeId="modul-0" onSelect={() => undefined} />);
    const lista = container.querySelector("nav div.overflow-y-auto");
    expect(lista).toBeTruthy();
    expect(lista?.className).toContain("min-h-0");
    expect(lista?.className).toContain("flex-1");
  });

  it("zaznacza aktywny moduł atrybutem aria-current", () => {
    render(<NavRail entries={DUZO} activeId="modul-7" onSelect={() => undefined} />);
    expect(screen.getByRole("button", { name: "Moduł 7" }).getAttribute("aria-current")).toBe("page");
  });

  it("wykaz pozycji zaczyna się czatem i głosem, a dalej idą moduły rejestru", () => {
    const pozycje = navEntries(MODULES);
    expect(pozycje[0].id).toBe(CHAT_ENTRY.id);
    expect(pozycje[1].id).toBe(VOICE_ENTRY.id);
    expect(pozycje.length).toBe(MODULES.length + 2);
    // Moduł „Narzędzia" musi być na liście — to on pokazuje pełny zakres agenta.
    expect(pozycje.some((pozycja) => pozycja.id === "mozliwosci")).toBe(true);
  });
});

describe("etykiety modułów", () => {
  it("mieszczą się w pasku 88 px — najwyżej 11 znaków", () => {
    // Dłuższa etykieta jest ucinana wielokropkiem i moduł przestaje być rozpoznawalny
    // („Narzę…”, „Kalen…”). Pasek ma 88 px, etykieta stoi pod ikoną i ma do dyspozycji
    // około 76 px — przy kroju interfejsu w 11 px mieści się jedenaście znaków.
    for (const modul of MODULES) {
      expect(modul.label.length, `etykieta „${modul.label}” jest za długa`).toBeLessThanOrEqual(11);
    }
    for (const pozycja of [CHAT_ENTRY, VOICE_ENTRY]) {
      expect(pozycja.label.length).toBeLessThanOrEqual(11);
    }
  });

  it("każdy moduł trafia do którejś grupy paska", () => {
    // Grupa „Pozostałe” jest siatką bezpieczeństwa, nie miejscem docelowym: nowy moduł
    // ma dostać swoje miejsce w wykazie, a nie lądować na końcu bez związku z resztą.
    const wszystkie = navEntries(MODULES);
    const grupy = grupyNawigacji(wszystkie);
    const zgrupowane = grupy.flatMap((grupa) => grupa.pozycje);
    expect(zgrupowane.length).toBe(wszystkie.length);
    expect(grupy.map((grupa) => grupa.tytul)).not.toContain("Pozostałe");
  });
});

// --- arkusz „Więcej” na telefonie ---------------------------------------------------------
//
// Arkusz był siatką osiemnastu jednakowych kafli: zasłaniał trzy czwarte ekranu, a każda
// pozycja wyglądała tak samo ważna i nie mówiła nic poza nazwą. Teraz każda forma ma swoje
// zadanie — wyszukiwarka, szybki wybór, zgrupowana lista z opisami, osobny pasek obsługi
// konta na dole. Testy pilnują, że te formy są i że się nie zlewają z powrotem w jedną.

describe("arkusz modułów na telefonie", () => {
  const WPISY: NavEntry[] = [
    CHAT_ENTRY,
    VOICE_ENTRY,
    ...["pliki", "cloud", "wiedza", "poczta", "kalendarz", "obrazy", "kod", "ustawienia", "platnosci"].map(
      (id) => ({ id, label: id, description: `Opis modułu ${id}`, icon: ikona }),
    ),
  ];

  function otworz() {
    render(<BottomBar entries={WPISY} activeId="chat" onSelect={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: /Więcej/ }));
    return screen.getByRole("dialog", { name: "Wszystkie moduły" });
  }

  it("ma wyszukiwarkę, bo przy kilkunastu modułach szybciej się wpisuje niż szuka wzrokiem", () => {
    otworz();
    expect(screen.getByRole("searchbox", { name: "Szukaj modułu" })).toBeTruthy();
  });

  it("zawęża listę do wpisanego słowa, także bez polskich znaków", () => {
    otworz();
    fireEvent.change(screen.getByRole("searchbox", { name: "Szukaj modułu" }), {
      target: { value: "poczt" },
    });
    expect(screen.getByRole("button", { name: /poczta/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^obrazy/ })).toBeNull();
  });

  it("pokazuje opis przy każdej pozycji, a nie samą nazwę", () => {
    otworz();
    expect(screen.getByText("Opis modułu kod")).toBeTruthy();
  });

  it("dzieli pozycje na grupy zamiast sypać wszystkim naraz", () => {
    const arkusz = otworz();
    const naglowki = [...arkusz.querySelectorAll("div.uppercase")].map((el) => el.textContent);
    expect(naglowki).toContain("Rozmowa");
    expect(naglowki).toContain("Biuro");
  });

  it("obsługę konta trzyma osobno, pod kreską — to nie są narzędzia do pracy", () => {
    const arkusz = otworz();
    const stopka = arkusz.querySelector("div.border-t");
    expect(stopka?.textContent).toContain("ustawienia");
    expect(stopka?.textContent).toContain("platnosci");
  });

  it("nie zjada całego ekranu i przewija się w środku", () => {
    const arkusz = otworz();
    expect(arkusz.className).toContain("max-h-[78dvh]");
    expect(arkusz.querySelector("div.overflow-y-auto")).toBeTruthy();
  });

  it("zostaje otwarty, gdy kursor wejdzie w pole wyszukiwania", () => {
    // Dolny pasek chowa się na czas pisania. Dopóki chowanie obejmowało cały komponent,
    // ustawienie kursora w polu wyszukiwania arkusza zamykało arkusz w tej samej chwili,
    // w której się otwierał.
    otworz();
    const pole = screen.getByRole("searchbox", { name: "Szukaj modułu" });
    fireEvent.focusIn(pole);
    expect(screen.getByRole("dialog", { name: "Wszystkie moduły" })).toBeTruthy();
  });

  it("gdy nic nie pasuje, mówi to wprost zamiast pokazywać pustkę", () => {
    otworz();
    fireEvent.change(screen.getByRole("searchbox", { name: "Szukaj modułu" }), {
      target: { value: "nieistniejace" },
    });
    expect(screen.getByText("Nic takiego tu nie ma.")).toBeTruthy();
  });
});


describe("nadmiar paska komputera", () => {
  it("rzadsze moduły schodzą pod „Więcej”, a codzienne zostają w pasku", () => {
    const { pasek, wiecej } = podzialPaska(navEntries(MODULES));
    const wPasku = pasek.map((pozycja) => pozycja.id);
    const podWiecej = wiecej.map((pozycja) => pozycja.id);
    expect(wPasku).toContain("chat");
    expect(wPasku).toContain("pliki");
    expect(wPasku).toContain("kod");
    expect(podWiecej).toContain("ustawienia");
    expect(podWiecej).toContain("platnosci");
    // Żadna pozycja nie może wypaść z obu list.
    expect(pasek.length + wiecej.length).toBe(navEntries(MODULES).length);
  });

  it("pasek rysuje przycisk „Więcej” zamiast ukrywać pozycje poza widokiem", () => {
    render(<NavRail entries={navEntries(MODULES)} activeId="chat" onSelect={() => undefined} />);
    expect(screen.getByText("Więcej")).toBeTruthy();
    // Moduł spod „Więcej” nie stoi w pasku jako osobna pozycja.
    expect(screen.queryByRole("button", { name: /^Płatności$/ })).toBeNull();
  });

  it("gdy pracujemy w module spod „Więcej”, przycisk pokazuje jego nazwę", () => {
    render(<NavRail entries={navEntries(MODULES)} activeId="ustawienia" onSelect={() => undefined} />);
    expect(screen.getByText("Ustawienia")).toBeTruthy();
    expect(screen.queryByText("Więcej")).toBeNull();
  });
});
