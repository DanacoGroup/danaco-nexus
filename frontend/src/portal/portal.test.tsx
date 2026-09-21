import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { parseRoute, routePath } from "../shell/route";
import { czyPortal, parsujTrase, rodzajTresci, sciezka } from "./trasy";
import { okruszki, usePozycjonowanie, witryna } from "./seo";
import { dataPolska, komunikat, brakSesji } from "./api";
import { ApiError } from "../api";
import { DostawcaNawigacji, Odsylacz, Okruszki, Pole } from "./ui";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.head.querySelectorAll("[data-portal-seo]").forEach((element) => element.remove());
});

describe("trasy portalu", () => {
  it("rozpoznaje strony stałe", () => {
    expect(parsujTrase("/portal")).toEqual({ strona: "glowna", slug: null, parametr: "" });
    expect(parsujTrase("/portal/").strona).toBe("glowna");
    expect(parsujTrase("/portal/oferta").strona).toBe("oferta");
    expect(parsujTrase("/portal/cennik").strona).toBe("cennik");
    expect(parsujTrase("/portal/panel").strona).toBe("panel");
    expect(parsujTrase("/portal/admin").strona).toBe("admin");
  });

  it("rozpoznaje pozycje treści", () => {
    expect(parsujTrase("/portal/blog/pierwsze-kroki")).toEqual({
      strona: "blog",
      slug: "pierwsze-kroki",
      parametr: "",
    });
    expect(parsujTrase("/portal/wiedza/ocr-dokumentow").strona).toBe("wiedza");
    expect(parsujTrase("/portal/dokumentacja/instalacja").slug).toBe("instalacja");
    expect(parsujTrase("/portal/s/regulamin")).toEqual({ strona: "strona", slug: "regulamin", parametr: "" });
  });

  it("odrzuca błędne i zbyt głębokie adresy", () => {
    expect(parsujTrase("/portal/blog/Zły Adres").strona).toBe("nieznana");
    expect(parsujTrase("/portal/blog/a/b").strona).toBe("nieznana");
    expect(parsujTrase("/portal/nie-ma").strona).toBe("nieznana");
    expect(parsujTrase("/portal/s").strona).toBe("nieznana");
  });

  it("czyta zapytanie wyszukiwania i token odzyskiwania", () => {
    expect(parsujTrase("/portal/szukaj", "?q=pompy").parametr).toBe("pompy");
    expect(parsujTrase("/portal/konto", "?token=abc123").parametr).toBe("abc123");
  });

  it("buduje adresy i rozpoznaje przynależność do portalu", () => {
    expect(sciezka("glowna")).toBe("/portal");
    expect(sciezka("blog")).toBe("/portal/blog");
    expect(sciezka("blog", "wpis")).toBe("/portal/blog/wpis");
    expect(sciezka("strona", "regulamin")).toBe("/portal/s/regulamin");
    expect(czyPortal("/portal")).toBe(true);
    expect(czyPortal("/portalowy")).toBe(false);
    expect(czyPortal("/m/kod")).toBe(false);
  });

  it("wiąże stronę z rodzajem treści w API", () => {
    expect(rodzajTresci("blog")).toBe("blog");
    expect(rodzajTresci("dokumentacja")).toBe("dokumentacja");
    expect(rodzajTresci("cennik")).toBeNull();
  });
});

describe("trasowanie aplikacji", () => {
  it("kieruje adresy /portal do portalu, nie do czatu", () => {
    expect(parseRoute("/portal", "")).toEqual({ view: "portal" });
    expect(parseRoute("/portal/blog/wpis", "")).toEqual({ view: "portal" });
    expect(routePath({ view: "portal" })).toBe("/portal");
  });

  it("nie zmienia pozostałych tras aplikacji", () => {
    expect(parseRoute("/", "")).toEqual({ view: "chat", conversationId: null });
    expect(parseRoute("/m/kod", "")).toEqual({ view: "module", moduleId: "kod" });
    expect(parseRoute("/start", "")).toEqual({ view: "landing" });
    expect(parseRoute("/portalowy", "")).toEqual({ view: "chat", conversationId: null });
  });
});

describe("dane strukturalne", () => {
  it("buduje okruszki z bezwzględnymi adresami", () => {
    const dane = okruszki([
      { nazwa: "Portal", sciezka: "/portal" },
      { nazwa: "Blog", sciezka: "/portal/blog" },
    ]) as { itemListElement: { position: number; item: string }[] };
    expect(dane.itemListElement[1].position).toBe(2);
    expect(dane.itemListElement[1].item).toContain("/portal/blog");
  });

  it("opisuje witrynę i wyszukiwanie", () => {
    const dane = witryna();
    expect(dane[0]["@type"]).toBe("Organization");
    expect(dane[1]["@type"]).toBe("WebSite");
  });
});

function StronaProbna() {
  usePozycjonowanie({
    tytul: "Cennik",
    opis: "Plany korzystania z narzędzia.",
    sciezka: "/portal/cennik",
    dane: { "@context": "https://schema.org", "@type": "WebPage" },
  });
  return <h1>Cennik</h1>;
}

describe("metadane strony", () => {
  it("ustawia tytuł, opis, Open Graph, kanoniczny i dane strukturalne", () => {
    const { unmount } = render(<StronaProbna />);
    expect(document.title).toBe("Cennik — Danaco Nexus");
    expect(document.head.querySelector('meta[name="description"]')?.getAttribute("content")).toBe(
      "Plany korzystania z narzędzia.",
    );
    expect(document.head.querySelector('meta[property="og:title"]')).not.toBeNull();
    expect(document.head.querySelector('link[rel="canonical"]')?.getAttribute("href")).toContain(
      "/portal/cennik",
    );
    expect(document.head.querySelector('script[type="application/ld+json"]')).not.toBeNull();
    unmount();
    expect(document.head.querySelector("[data-portal-seo]")).toBeNull();
  });
});

describe("elementy interfejsu", () => {
  it("odsyłacz portalu nawiguje bez przeładowania strony", async () => {
    const nawiguj = vi.fn();
    render(
      <DostawcaNawigacji nawiguj={nawiguj}>
        <Odsylacz adres="/portal/blog">Blog</Odsylacz>
      </DostawcaNawigacji>,
    );
    const odsylacz = screen.getByRole("link", { name: "Blog" });
    expect(odsylacz.getAttribute("href")).toBe("/portal/blog");
    odsylacz.click();
    await waitFor(() => expect(nawiguj).toHaveBeenCalledWith("/portal/blog"));
  });

  it("pole formularza ma etykietę powiązaną z kontrolką i komunikat błędu", () => {
    render(<Pole etykieta="Adres e-mail" wartosc="" naZmiane={() => {}} blad="Podaj adres." wymagane />);
    const kontrolka = screen.getByRole("textbox", { name: /Adres e-mail/ });
    expect(kontrolka.getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText("Podaj adres.")).toBeTruthy();
  });

  it("okruszki oznaczają bieżącą stronę", () => {
    render(
      <DostawcaNawigacji nawiguj={() => {}}>
        <Okruszki
          pozycje={[
            { nazwa: "Portal", sciezka: "/portal" },
            { nazwa: "Blog", sciezka: "/portal/blog" },
          ]}
        />
      </DostawcaNawigacji>,
    );
    expect(screen.getByText("Blog").getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Portal" })).toBeTruthy();
  });
});

describe("powłoka portalu", () => {
  it("pokazuje nawigację, obszar treści i odsyłacz pomijający nawigację", async () => {
    vi.stubGlobal("fetch", async (adres: string) => {
      const dane = adres.includes("/konto/ja")
        ? { detail: "Wymagane logowanie." }
        : adres.includes("/stan")
          ? { registration_open: true, admin: false }
          : { items: [], total: 0, page: 1, pages: 1, per_page: 10 };
      return new Response(JSON.stringify(dane), {
        status: adres.includes("/konto/ja") ? 401 : 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    const { Portal } = await import("./Portal");
    render(<Portal />);
    expect(screen.getByRole("link", { name: "Przejdź do treści" })).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Nawigacja portalu" })).toBeTruthy();
    expect(screen.getByRole("main")).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1, name: "Powiedz, co ma powstać. Odbierz gotowy plik." })).toBeTruthy(),
    );
  });

  it("trzyma pasek w jednym wierszu: krótka nawigacja i zawsze dostępne menu", async () => {
    vi.stubGlobal("fetch", async (adres: string) => {
      const dane = adres.includes("/konto/ja")
        ? { detail: "Wymagane logowanie." }
        : adres.includes("/stan")
          ? { registration_open: true, admin: false }
          : { items: [], total: 0, page: 1, pages: 1, per_page: 10 };
      return new Response(JSON.stringify(dane), {
        status: adres.includes("/konto/ja") ? 401 : 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    const { Portal } = await import("./Portal");
    render(<Portal />);
    // Pasmo treści daje na nazwy 650 px; pięć pozycji zajmuje 482 px, dziewięć zajmowało 874 px
    // i spychało akcje do drugiego wiersza. Reszta mapy portalu jest pod „Menu”.
    const pasek = within(screen.getByRole("navigation", { name: "Nawigacja portalu" }));
    const nazwy = pasek.getAllByRole("link").map((odsylacz) => odsylacz.textContent);
    expect(nazwy).toEqual(["Oferta", "Funkcje", "Zastosowania", "Narzędzia agenta", "Cennik"]);
    const przyciskMenu = screen.getByRole("button", { name: "Menu" });
    expect(przyciskMenu.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(przyciskMenu);
    const menu = within(screen.getByRole("navigation", { name: "Menu portalu" }));
    for (const nazwa of ["Dokumentacja", "Blog", "Centrum wiedzy", "Kontakt"]) {
      expect(menu.getByRole("link", { name: nazwa })).toBeTruthy();
    }
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByRole("button", { name: "Menu" }).getAttribute("aria-expanded")).toBe("false");
  });
});

describe("puste sekcje portalu", () => {
  // Pusta sekcja radziła wcześniej „zajrzyj do dokumentacji”, a dokumentacja bywa pusta
  // tak samo — rada prowadziła donikąd. Test pilnuje, że zostają wyjścia, które działają
  // niezależnie od tego, czy redakcja zdążyła cokolwiek opublikować.
  it("blog bez wpisów podaje dwa działające wyjścia", async () => {
    vi.stubGlobal("fetch", async (adres: string) =>
      new Response(JSON.stringify(adres.includes("znaczniki") ? [] : { items: [], total: 0, page: 1, pages: 1, per_page: 9 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { ListaWpisow } = await import("./strony/ListaWpisow");
    render(
      <DostawcaNawigacji nawiguj={() => {}}>
        <ListaWpisow strona="blog" rodzaj="blog" tytul="Blog" opis="Materiały o pracy z Danaco Nexus." />
      </DostawcaNawigacji>,
    );
    await waitFor(() => expect(screen.getByText("Ta sekcja czeka na pierwsze materiały.")).toBeTruthy());
    expect(screen.getByRole("link", { name: "wypróbuj Nexusa bez rejestracji" }).getAttribute("href")).toBe("/wyprobuj");
    expect(screen.getByRole("link", { name: "napisz, czego potrzebujesz" }).getAttribute("href")).toBe("/portal/kontakt");
    expect(screen.queryByText(/Zajrzyj do dokumentacji/)).toBeNull();
  });

  it("dokumentacja bez spisu nie każe wybierać zagadnienia ze spisu", async () => {
    vi.stubGlobal("fetch", async () =>
      new Response(JSON.stringify({ items: [], total: 0, page: 1, pages: 1, per_page: 50 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { Dokumentacja } = await import("./strony/Dokumentacja");
    render(
      <DostawcaNawigacji nawiguj={() => {}}>
        <Dokumentacja slug={null} />
      </DostawcaNawigacji>,
    );
    await waitFor(() => expect(screen.getByText(/Spis dokumentacji jeszcze powstaje/)).toBeTruthy());
    expect(screen.queryByText(/Wybierz zagadnienie ze spisu obok/)).toBeNull();
    expect(screen.getByRole("link", { name: "wypróbuj Nexusa bez rejestracji" })).toBeTruthy();
  });
});

describe("pomocnicze funkcje API", () => {
  it("rozpoznaje brak sesji i przepisuje komunikat błędu", () => {
    expect(brakSesji(new ApiError(401, "Wymagane logowanie."))).toBe(true);
    expect(brakSesji(new ApiError(500, "Błąd"))).toBe(false);
    expect(komunikat(new ApiError(422, "Adres zajęty."))).toBe("Adres zajęty.");
    expect(komunikat(null, "Zapasowy")).toBe("Zapasowy");
  });

  it("formatuje datę po polsku", () => {
    expect(dataPolska("2026-09-20T10:00:00+00:00")).toContain("2026");
    expect(dataPolska(null)).toBe("");
    expect(dataPolska("nie-data")).toBe("");
  });
});
