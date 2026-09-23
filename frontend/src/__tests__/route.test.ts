import { describe, expect, it } from "vitest";
import { parseRoute, resolveScreen, routePath, safeNext } from "../shell/route";

const ID = "0b8f3c1e-3c52-4d0f-9d61-8c1a2b3c4d5e";

describe("parseRoute", () => {
  it("rozpoznaje trasy aplikacji", () => {
    expect(parseRoute("/czat", "")).toEqual({ view: "chat", conversationId: null });
    expect(parseRoute(`/c/${ID}`, "")).toEqual({ view: "chat", conversationId: ID });
    expect(parseRoute("/m/urzadzenia", "")).toEqual({ view: "module", moduleId: "urzadzenia" });
    expect(parseRoute("/m/deep-research/", "")).toEqual({ view: "module", moduleId: "deep-research" });
    // W pasku „Czat” stoi obok modułów, więc adres /m/czat jest naturalny — ma prowadzić
    // do rozmowy, a nie do planszy „moduł nie jest zainstalowany”.
    for (const nazwa of ["czat", "chat", "rozmowa"]) {
      expect(parseRoute(`/m/${nazwa}`, "")).toEqual({ view: "chat", conversationId: null });
    }
    expect(parseRoute("/zaloguj", "?next=/m/kod")).toEqual({ view: "login" });
    expect(parseRoute("/start", "")).toEqual({ view: "landing" });
  });

  it("tryb osadzony ma pierwszeństwo przed ścieżką", () => {
    expect(parseRoute("/", "?widok=panel")).toEqual({ view: "panel" });
    expect(parseRoute("/", "?source=pwa&widok=panel")).toEqual({ view: "panel" });
    expect(parseRoute("/", "?widok=inny")).toEqual({ view: "landing" });
  });

  it("„/” w przeglądarce to strona produktu, także ze znacznikami kampanii", () => {
    expect(parseRoute("/", "")).toEqual({ view: "landing" });
    expect(parseRoute("/", "?utm_source=facebook")).toEqual({ view: "landing" });
  });

  it("„/” jest wejściem do aplikacji przy starcie, skrótach, udostępnianiu i powrocie z chmury", () => {
    for (const zapytanie of ["?source=pwa", "?source=shortcut", "?share=1", "?tekst=abc", "?next=cloud"]) {
      expect(parseRoute("/", zapytanie)).toEqual({ view: "chat", conversationId: null });
    }
  });

  it("w oknie aplikacji na Androida i komputer „/” otwiera aplikację", () => {
    expect(parseRoute("/", "", true)).toEqual({ view: "chat", conversationId: null });
    expect(parseRoute("/start", "", true)).toEqual({ view: "landing" });
  });

  it("nieznane i błędne adresy prowadzą do czatu", () => {
    expect(parseRoute("/c/nie-uuid", "")).toEqual({ view: "chat", conversationId: null });
    expect(parseRoute("/m/../x", "")).toEqual({ view: "chat", conversationId: null });
    expect(parseRoute("/cokolwiek", "")).toEqual({ view: "chat", conversationId: null });
  });

  it("routePath odwraca parseRoute", () => {
    for (const path of ["/czat", `/c/${ID}`, "/m/urzadzenia", "/zaloguj", "/start"]) {
      expect(routePath(parseRoute(path, ""))).toBe(path);
    }
    expect(routePath({ view: "panel" })).toBe("/?widok=panel");
    expect(routePath({ view: "chat", conversationId: null })).toBe("/czat");
  });
});

describe("resolveScreen", () => {
  it("niezalogowany: strona startowa na /, logowanie dla czatu, rozmów, modułów i powrotu do chmury", () => {
    expect(resolveScreen(parseRoute("/", ""), false)).toBe("landing");
    expect(resolveScreen(parseRoute("/czat", ""), false)).toBe("login");
    expect(resolveScreen(parseRoute("/", "?next=cloud"), false)).toBe("login");
    expect(resolveScreen(parseRoute(`/c/${ID}`, ""), false)).toBe("login");
    expect(resolveScreen(parseRoute("/m/kod", ""), false)).toBe("login");
    expect(resolveScreen(parseRoute("/zaloguj", ""), false)).toBe("login");
  });

  it("zalogowany: aplikacja pod /czat; strona produktu pod / i panel dostępne zawsze", () => {
    expect(resolveScreen(parseRoute("/czat", ""), true)).toBe("app");
    expect(resolveScreen(parseRoute("/", ""), true)).toBe("landing");
    expect(resolveScreen(parseRoute("/zaloguj", ""), true)).toBe("app");
    expect(resolveScreen(parseRoute("/start", ""), true)).toBe("landing");
    expect(resolveScreen(parseRoute("/start", ""), false)).toBe("landing");
    expect(resolveScreen(parseRoute("/", "?widok=panel"), false)).toBe("panel");
  });
});

describe("safeNext", () => {
  it("przepuszcza tylko ścieżki tej witryny", () => {
    expect(safeNext("/m/urzadzenia")).toBe("/m/urzadzenia");
    expect(safeNext(`/c/${ID}`)).toBe(`/c/${ID}`);
    expect(safeNext("cloud")).toBeNull();
    expect(safeNext("//zly.pl/x")).toBeNull();
    expect(safeNext("https://zly.pl")).toBeNull();
    expect(safeNext("/\\zly.pl")).toBeNull();
    expect(safeNext(null)).toBeNull();
  });
});
