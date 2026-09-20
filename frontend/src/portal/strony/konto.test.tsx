// Testy strony konta klienta: walidacja hasła w przeglądarce, zmiana hasła, dwustopniowe usunięcie
// konta, wylogowanie, ustawienie hasła z odsyłacza, odsyłacz otwarty w zalogowanej przeglądarce
// oraz potwierdzenie adresu e-mail.

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Konto } from "./Konto";
import { DostawcaNawigacji } from "../ui";
import type { ProfilKlienta } from "../api";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/portal/konto");
  document.head.querySelectorAll("[data-portal-seo]").forEach((element) => element.remove());
});

const KLIENT: ProfilKlienta = {
  id: "8f1f2f6a-1f3a-4a2b-9c4d-5e6f70819293",
  email: "klient@example.com",
  name: "Jan Kowalski",
  company: "Danaco",
  plan: "osobisty",
  email_confirmed: true,
  created_at: "2026-01-15T10:00:00+00:00",
  last_login_at: "2026-09-19T08:30:00+00:00",
};

const KLIENT_BEZ_POTWIERDZENIA: ProfilKlienta = { ...KLIENT, email_confirmed: false };

/** Otwiera stronę konta z odsyłacza potwierdzającego adres. */
function odsylaczPotwierdzenia(token: string) {
  window.history.replaceState({}, "", `/portal/konto?potwierdzenie=${token}`);
}

interface Wywolanie {
  adres: string;
  dane: Record<string, unknown> | undefined;
}

/** Podstawia fetch zapisujący żądania; odpowiedź można zmienić dla wybranego adresu. */
function podstawFetch(odpowiedz: (adres: string) => { status?: number; dane?: unknown } = () => ({})) {
  const wywolania: Wywolanie[] = [];
  vi.stubGlobal("fetch", async (adres: string, init: RequestInit = {}) => {
    wywolania.push({ adres, dane: init.body ? JSON.parse(String(init.body)) : undefined });
    const { status = 200, dane = { ok: true } } = odpowiedz(adres);
    return new Response(JSON.stringify(dane), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  return wywolania;
}

function pokaz(
  wlasciwosci: Partial<Parameters<typeof Konto>[0]> = {},
  nawiguj: (sciezka: string) => void = () => {},
) {
  const dane = { konto: null, odswiez: () => {}, rejestracjaOtwarta: true, token: "", ...wlasciwosci };
  return render(
    <DostawcaNawigacji nawiguj={nawiguj}>
      <Konto {...dane} />
    </DostawcaNawigacji>,
  );
}

function wpisz(etykieta: RegExp, wartosc: string) {
  fireEvent.change(screen.getByLabelText(etykieta), { target: { value: wartosc } });
}

describe("konto gościa", () => {
  it("nie wysyła rejestracji ze zbyt krótkim hasłem", async () => {
    const wywolania = podstawFetch();
    pokaz();
    fireEvent.click(screen.getByRole("button", { name: "Załóż konto" }));
    wpisz(/Adres e-mail/, "nowy@example.com");
    wpisz(/Hasło/, "krotkie");
    fireEvent.click(screen.getByRole("button", { name: "Załóż konto" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("za krótkie"));
    expect(wywolania).toEqual([]);
  });

  it("po prośbie o odzyskanie nie zdradza, czy konto istnieje", async () => {
    const wywolania = podstawFetch();
    pokaz();
    fireEvent.click(screen.getByRole("button", { name: "Nie pamiętam hasła" }));
    wpisz(/Adres e-mail/, "kto@example.com");
    fireEvent.click(screen.getByRole("button", { name: "Odzyskaj hasło" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Jeżeli konto o tym adresie istnieje"));
    expect(wywolania[0].adres).toBe("/api/portal/konto/odzyskiwanie");
  });
});

describe("ustawienie hasła z odsyłacza", () => {
  it("sprawdza długość hasła, a po zapisie odsyła do logowania", async () => {
    const wywolania = podstawFetch();
    const nawiguj = vi.fn();
    pokaz({ token: "token-odzyskiwania" }, nawiguj);
    wpisz(/Nowe hasło/, "krotkie");
    fireEvent.click(screen.getByRole("button", { name: "Zapisz hasło" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(wywolania).toEqual([]);

    wpisz(/Nowe hasło/, "dostatecznie-dlugie-haslo");
    fireEvent.click(screen.getByRole("button", { name: "Zapisz hasło" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Przejdź do logowania" })).toBeTruthy());
    expect(wywolania[0].adres).toBe("/api/portal/konto/odzyskiwanie/potwierdz");
    expect(wywolania[0].dane).toEqual({ token: "token-odzyskiwania", password: "dostatecznie-dlugie-haslo" });
    fireEvent.click(screen.getByRole("button", { name: "Przejdź do logowania" }));
    expect(nawiguj).toHaveBeenCalledWith("/portal/konto");
  });

  it("mówi zalogowanemu klientowi, co zrobić z odsyłaczem", () => {
    podstawFetch();
    pokaz({ konto: KLIENT, token: "token-odzyskiwania" });
    expect(screen.getByRole("status").textContent).toContain("zalogowanej przeglądarce");
    expect(screen.getByRole("heading", { name: "Zmiana hasła" })).toBeTruthy();
  });

  it("po zmianie hasła nie zostawia baneru o odsyłaczu", async () => {
    podstawFetch();
    pokaz({ konto: KLIENT, token: "token-odzyskiwania" });
    wpisz(/Obecne hasło/, "haslo-klienta-portalu");
    wpisz(/Nowe hasło/, "nowe-haslo-portalu");
    fireEvent.click(screen.getByRole("button", { name: "Zmień hasło" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Hasło zmienione" })).toBeTruthy());
    expect(screen.queryByText(/zalogowanej przeglądarce/)).toBeNull();
  });

  it("po zmianie hasła zdejmuje zużyty token z adresu", async () => {
    podstawFetch();
    const nawiguj = vi.fn();
    const odswiez = vi.fn();
    pokaz({ konto: KLIENT, token: "token-odzyskiwania", odswiez }, nawiguj);
    wpisz(/Obecne hasło/, "haslo-klienta-portalu");
    wpisz(/Nowe hasło/, "nowe-haslo-portalu");
    fireEvent.click(screen.getByRole("button", { name: "Zmień hasło" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Zaloguj się ponownie" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Zaloguj się ponownie" }));
    expect(nawiguj).toHaveBeenCalledWith("/portal/konto");
    expect(odswiez).toHaveBeenCalled();
  });

  it("po usunięciu konta z otwartym odsyłaczem też wraca na czysty adres", async () => {
    podstawFetch();
    const nawiguj = vi.fn();
    pokaz({ konto: KLIENT, token: "token-odzyskiwania" }, nawiguj);
    fireEvent.click(screen.getByRole("button", { name: "Chcę usunąć konto" }));
    wpisz(/^Hasło/, "haslo-klienta-portalu");
    wpisz(/Potwierdzenie/, "usuwam");
    fireEvent.click(screen.getByRole("button", { name: "Usuń konto na zawsze" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Konto usunięte" })).toBeTruthy());
    expect(screen.queryByText(/zalogowanej przeglądarce/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Wróć na stronę konta" }));
    expect(nawiguj).toHaveBeenCalledWith("/portal/konto");
  });
});

describe("zmiana hasła w profilu", () => {
  it("nie wysyła hasła powtarzającego obecne", async () => {
    const wywolania = podstawFetch();
    pokaz({ konto: KLIENT });
    wpisz(/Obecne hasło/, "haslo-klienta-portalu");
    wpisz(/Nowe hasło/, "haslo-klienta-portalu");
    fireEvent.click(screen.getByRole("button", { name: "Zmień hasło" }));
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Nowe hasło musi się różnić od obecnego.",
    );
    expect(wywolania).toEqual([]);
  });

  it("po zmianie zostawia samo potwierdzenie zamiast kontrolek konta", async () => {
    const wywolania = podstawFetch();
    pokaz({ konto: KLIENT });
    wpisz(/Obecne hasło/, "haslo-klienta-portalu");
    wpisz(/Nowe hasło/, "nowe-haslo-portalu");
    fireEvent.click(screen.getByRole("button", { name: "Zmień hasło" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Hasło zmienione" })).toBeTruthy());
    expect(wywolania[0].dane).toEqual({
      current_password: "haslo-klienta-portalu",
      new_password: "nowe-haslo-portalu",
    });
    expect(screen.queryByRole("button", { name: "Zapisz profil" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Zmień hasło" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Przejdź do panelu klienta" })).toBeNull();
    expect(screen.getByRole("button", { name: "Zaloguj się ponownie" })).toBeTruthy();
  });

  it("pokazuje komunikat serwera, gdy obecne hasło jest błędne", async () => {
    podstawFetch(() => ({ status: 401, dane: { detail: "Obecne hasło jest nieprawidłowe." } }));
    pokaz({ konto: KLIENT });
    wpisz(/Obecne hasło/, "nie-to-haslo-wcale");
    wpisz(/Nowe hasło/, "nowe-haslo-portalu");
    fireEvent.click(screen.getByRole("button", { name: "Zmień hasło" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Obecne hasło jest nieprawidłowe.");
    expect(screen.getByRole("heading", { name: "Dane konta" })).toBeTruthy();
  });
});

describe("usunięcie konta", () => {
  it("odsłania formularz dopiero po prośbie i wymaga słowa potwierdzenia", async () => {
    const wywolania = podstawFetch();
    pokaz({ konto: KLIENT });
    expect(screen.queryByLabelText(/Potwierdzenie/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Chcę usunąć konto" }));
    wpisz(/^Hasło/, "haslo-klienta-portalu");
    wpisz(/Potwierdzenie/, "usun");
    fireEvent.click(screen.getByRole("button", { name: "Usuń konto na zawsze" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("USUWAM"));
    expect(wywolania).toEqual([]);
  });

  it("po usunięciu nie zostawia żadnego działania na koncie", async () => {
    const wywolania = podstawFetch();
    pokaz({ konto: KLIENT });
    fireEvent.click(screen.getByRole("button", { name: "Chcę usunąć konto" }));
    wpisz(/^Hasło/, "haslo-klienta-portalu");
    wpisz(/Potwierdzenie/, "usuwam");
    fireEvent.click(screen.getByRole("button", { name: "Usuń konto na zawsze" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Konto usunięte" })).toBeTruthy());
    expect(wywolania[0].adres).toBe("/api/portal/konto/usuniecie");
    expect(wywolania[0].dane).toEqual({ password: "haslo-klienta-portalu", confirmation: "usuwam" });
    expect(screen.queryByRole("button", { name: "Zapisz profil" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Wyloguj się" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Przejdź do panelu klienta" })).toBeNull();
  });
});

describe("wylogowanie", () => {
  it("kończy sesję i odświeża widok konta", async () => {
    const wywolania = podstawFetch();
    const odswiez = vi.fn();
    pokaz({ konto: KLIENT, odswiez });
    fireEvent.click(screen.getByRole("button", { name: "Wyloguj się" }));
    await waitFor(() => expect(odswiez).toHaveBeenCalled());
    expect(wywolania[0].adres).toBe("/api/portal/konto/wylogowanie");
  });
});

describe("potwierdzenie adresu e-mail", () => {
  it("potwierdza adres tokenem z odsyłacza i odsyła na czysty adres konta", async () => {
    const wywolania = podstawFetch();
    const nawiguj = vi.fn();
    const odswiez = vi.fn();
    odsylaczPotwierdzenia("token-potwierdzenia");
    pokaz({ odswiez }, nawiguj);
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain("Adres e-mail został potwierdzony"),
    );
    expect(wywolania[0].adres).toBe("/api/portal/konto/potwierdzenie");
    expect(wywolania[0].dane).toEqual({ token: "token-potwierdzenia" });
    fireEvent.click(screen.getByRole("button", { name: "Przejdź do konta" }));
    expect(nawiguj).toHaveBeenCalledWith("/portal/konto");
    expect(odswiez).toHaveBeenCalled();
  });

  it("pokazuje komunikat serwera, gdy odsyłacz jest zużyty", async () => {
    podstawFetch(() => ({ status: 422, dane: { detail: "Odsyłacz wygasł albo został już użyty." } }));
    odsylaczPotwierdzenia("token-zuzyty");
    pokaz();
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Odsyłacz wygasł albo został już użyty.",
    );
    expect(screen.queryByRole("button", { name: "Zaloguj się do portalu" })).toBeNull();
  });

  it("pokazuje niepotwierdzony adres i wysyła odsyłacz ponownie", async () => {
    const wywolania = podstawFetch();
    pokaz({ konto: KLIENT_BEZ_POTWIERDZENIA });
    expect(screen.getByRole("heading", { name: "Adres e-mail bez potwierdzenia" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Wyślij odsyłacz ponownie" }));
    await waitFor(() =>
      expect(screen.getByText(/Wysłaliśmy odsyłacz/)).toBeTruthy(),
    );
    expect(wywolania[0].adres).toBe("/api/portal/konto/potwierdzenie/wyslij");
  });

  it("nie pokazuje paska, gdy adres jest potwierdzony", () => {
    podstawFetch();
    pokaz({ konto: KLIENT });
    expect(screen.queryByRole("heading", { name: "Adres e-mail bez potwierdzenia" })).toBeNull();
  });
});
