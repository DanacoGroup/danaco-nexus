import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BrakKredytow } from "./BrakKredytow";
import { Kredyty } from "./Kredyty";
import { MojaSubskrypcja } from "./MojaSubskrypcja";
import { Plany } from "./Plany";
import { StanPlanu } from "./StanPlanu";
import { odczytajPowrot } from "./index";
import {
  kwota,
  opisOkresu,
  opisOkresuProbnego,
  oszczednoscRoczna,
  planBiezacy,
  platnosciApi,
  type CennikInfo,
  type FakturaInfo,
  type KredytyInfo,
  type KuponInfo,
  type PakietyInfo,
  type PlanInfo,
  type StanSprzedazy,
  type SubskrypcjaInfo,
} from "./api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// Wszystkie trzy plany są płatne; najniższy zaczyna się okresem próbnym z podaniem karty.
const PLAN_OSOBISTY: PlanInfo = {
  kod: "osobisty",
  nazwa: "Osobisty",
  opis: "Dla jednej osoby.",
  bezplatny: false,
  znacznik: "7 dni próbnych",
  zawartosc: ["Rozmowa z Nexusem, także głosowa"],
  kredyty_okresowo: 2000,
  okres_probny_dni: 7,
  przestrzen_mb: 1024,
  skrzynki_poczty: 1,
  wersjonowanie: false,
  synchronizacja: true,
  probny: { dni: 7, przestrzen_mb: 100, kredyty: 300, skrzynki: 0, wersjonowanie: 0, synchronizacja: 0 },
  limity: { zadania_rownolegle: 1, plik_mb: 2048, automatyzacje: 0, konta: 1 },
  cena_miesiac_gr: 0,
  cena_rok_gr: 0,
  do_kupienia: { miesiac: false, rok: false },
};

const PLAN_PRO: PlanInfo = {
  kod: "pro",
  nazwa: "Pro",
  opis: "Dla codziennej pracy.",
  bezplatny: false,
  znacznik: "",
  zawartosc: ["Wszystko z planu Osobistego"],
  kredyty_okresowo: 20000,
  okres_probny_dni: 0,
  przestrzen_mb: 1024,
  skrzynki_poczty: 1,
  wersjonowanie: false,
  synchronizacja: true,
  probny: { dni: 0, przestrzen_mb: 100, kredyty: 300, skrzynki: 0, wersjonowanie: 0, synchronizacja: 0 },
  limity: { zadania_rownolegle: 4, plik_mb: 2048, automatyzacje: 20, konta: 1 },
  cena_miesiac_gr: 4900,
  cena_rok_gr: 49000,
  do_kupienia: { miesiac: true, rok: true },
};

const PLAN_ZESPOL: PlanInfo = {
  kod: "zespol",
  nazwa: "Zespół",
  opis: "Dla najcięższej pracy.",
  bezplatny: false,
  znacznik: "",
  zawartosc: ["Wszystko z planu Pro"],
  kredyty_okresowo: 60000,
  okres_probny_dni: 0,
  przestrzen_mb: 1024,
  skrzynki_poczty: 1,
  wersjonowanie: false,
  synchronizacja: true,
  probny: { dni: 0, przestrzen_mb: 100, kredyty: 300, skrzynki: 0, wersjonowanie: 0, synchronizacja: 0 },
  limity: { zadania_rownolegle: 8, plik_mb: 2048, automatyzacje: 100, konta: 5 },
  cena_miesiac_gr: 9900,
  cena_rok_gr: 99000,
  do_kupienia: { miesiac: true, rok: true },
};

const KUPON_LATO: KuponInfo = {
  kod: "LATO2026",
  rabat_procent: 20,
  rabat_gr: 0,
  waluta: "pln",
  opis: "Lato 2026",
  wygasa_at: null,
};

const STAN_BEZPLATNY: StanSprzedazy = {
  kod: "plan_bezplatny",
  tytul: "Plan Osobisty",
  komunikat: "Pracujesz na planie bez opłat.",
  dzialanie: "wybierz_plan",
  etykieta_dzialania: "Wybierz plan",
  ton: "informacja",
};

function subskrypcja(zmiany: Partial<SubskrypcjaInfo> = {}): SubskrypcjaInfo {
  return {
    stan: STAN_BEZPLATNY,
    faktura_do_zaplaty: null,
    ma_platny_plan: false,
    plan: "osobisty",
    nazwa_planu: "Osobisty",
    status: "brak",
    okres: "",
    okres_od: null,
    okres_do: null,
    anuluj_na_koniec: false,
    ma_konto_stripe: false,
    limity: PLAN_OSOBISTY.limity,
    ...zmiany,
  };
}

function cennik(zmiany: Partial<CennikInfo> = {}): CennikInfo {
  return {
    waluta: "pln",
    sprzedaz_aktywna: true,
    plany: [PLAN_OSOBISTY, PLAN_PRO],
    subskrypcja: subskrypcja(),
    ...zmiany,
  };
}

const FAKTURA_OTWARTA: FakturaInfo = {
  id: "f1",
  numer: "NEXUS-2026-0001",
  kwota_gr: 4900,
  waluta: "pln",
  status: "open",
  pdf_url: "",
  strona_url: "https://stripe.test/faktury/in_1",
  wystawiona_at: "2026-02-16T00:00:00+00:00",
  oplacona_at: null,
};

describe("pomocnicze funkcje sprzedaży", () => {
  it("zapisuje kwoty w złotych bez zbędnej końcówki", () => {
    // Intl rozdziela liczbę i walutę spacją nierozdzielającą – porównujemy po jej zamianie.
    const zwykle = (wartosc: number) => kwota(wartosc).replace(/ /g, " ");
    expect(zwykle(4900)).toBe("49 zł");
    expect(zwykle(4999)).toBe("49,99 zł");
  });

  it("liczy korzyść z płatności rocznej", () => {
    expect(oszczednoscRoczna(PLAN_PRO)).toBe(17);
    expect(oszczednoscRoczna(PLAN_OSOBISTY)).toBe(0);
  });

  it("opisuje okres próbny tylko tam, gdzie go jest", () => {
    expect(opisOkresuProbnego(PLAN_OSOBISTY)).toMatch(/Pierwsze 7 dni bez opłaty/);
    expect(opisOkresuProbnego(PLAN_OSOBISTY)).toMatch(/przechodzi w płatny/);
    expect(opisOkresuProbnego(PLAN_PRO)).toBe("");
  });

  it("podaje zakres okresu próbnego, a nie samą liczbę dni", () => {
    // Karta planu obiecuje 1 GB, pocztę i synchronizację, a serwer przez te 7 dni daje
    // 100 MB i nic poza tym. Zdanie o okresie próbnym musi powiedzieć to wprost —
    // inaczej użytkownik pozna różnicę dopiero odmową przyjęcia pliku.
    const zdanie = opisOkresuProbnego(PLAN_OSOBISTY);
    expect(zdanie).toMatch(/300 kredytów/);
    expect(zdanie).toMatch(/100 MB/);
    expect(zdanie).not.toMatch(/1 GB/);
    expect(zdanie).toMatch(/bez poczty, synchronizacji i wersji plików/);
  });

  it("pomija zastrzeżenie, gdy okres próbny obejmuje pełen zakres planu", () => {
    const pelny: PlanInfo = {
      ...PLAN_OSOBISTY,
      probny: { dni: 7, przestrzen_mb: 1024, kredyty: 2000, skrzynki: 1, wersjonowanie: 1, synchronizacja: 1 },
    };
    const zdanie = opisOkresuProbnego(pelny);
    expect(zdanie).toMatch(/1 GB miejsca/);
    expect(zdanie).not.toMatch(/, bez /);
  });

  it("nazywa okres rozliczeniowy", () => {
    expect(opisOkresu("rok")).toBe("rozliczenie roczne");
    expect(opisOkresu("")).toBe("");
  });

  it("rozpoznaje plan bieżący wraz z okresem", () => {
    const platny = subskrypcja({ plan: "pro", okres: "miesiac", ma_platny_plan: true });
    expect(planBiezacy(PLAN_PRO, platny, "miesiac")).toBe(true);
    expect(planBiezacy(PLAN_PRO, platny, "rok")).toBe(false);
    expect(planBiezacy(PLAN_OSOBISTY, subskrypcja(), "miesiac")).toBe(true);
  });

  it("czyta wynik powrotu ze Stripe", () => {
    expect(odczytajPowrot("?zakup=udany&sesja=cs_1")).toEqual({ wynik: "udany", sesja: "cs_1" });
    expect(odczytajPowrot("?zakup=anulowany").wynik).toBe("anulowany");
    expect(odczytajPowrot("?powrot=rozliczenia").wynik).toBe("rozliczenia");
    expect(odczytajPowrot("").wynik).toBe("");
  });
});

describe("widok stanu sprzedaży", () => {
  it("prowadzi do cennika, gdy konto jest na planie bezpłatnym", async () => {
    const wybierz = vi.fn();
    render(
      <StanPlanu
        stan={STAN_BEZPLATNY}
        faktura={null}
        zajety={false}
        onWybierzPlan={wybierz}
        onPortal={vi.fn()}
      />,
    );
    expect(screen.getByText("Plan Osobisty")).toBeTruthy();
    screen.getByRole("button", { name: "Wybierz plan" }).click();
    await waitFor(() => expect(wybierz).toHaveBeenCalled());
  });

  it("przy odrzuconej płatności prowadzi do zapłaty faktury", () => {
    render(
      <StanPlanu
        stan={{
          kod: "platnosc_odrzucona",
          tytul: "Płatność została odrzucona",
          komunikat: "Popraw dane karty albo zapłać fakturę.",
          dzialanie: "zaplac_fakture",
          etykieta_dzialania: "Zapłać fakturę",
          ton: "blad",
        }}
        faktura={FAKTURA_OTWARTA}
        zajety={false}
        onWybierzPlan={vi.fn()}
        onPortal={vi.fn()}
      />,
    );
    const odsylacz = screen.getByRole("link", { name: /Zapłać fakturę/ });
    expect(odsylacz.getAttribute("href")).toBe(FAKTURA_OTWARTA.strona_url);
  });
});

describe("ekran planów", () => {
  it("mówi wprost, że sprzedaż nie jest włączona i nie stawia planu jako dostępnego", () => {
    // Serwer przy wyłączonej sprzedaży zwraca do_kupienia=false dla każdego planu płatnego.
    const wstrzymany: PlanInfo = { ...PLAN_PRO, do_kupienia: { miesiac: false, rok: false } };
    render(
      <Plany cennik={cennik({ sprzedaz_aktywna: false, plany: [PLAN_OSOBISTY, wstrzymany] })} />,
    );
    expect(screen.getByText("Sprzedaż nie jest jeszcze włączona")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Wkrótce" }).hasAttribute("disabled")).toBe(true);
  });

  it("opisuje plan niedostępny w sprzedaży", () => {
    const wstrzymany: PlanInfo = { ...PLAN_PRO, do_kupienia: { miesiac: false, rok: false } };
    render(<Plany cennik={cennik({ plany: [wstrzymany] })} />);
    expect(screen.getByRole("button", { name: "Wkrótce" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(/Damy znać, gdy ruszy/)).toBeTruthy();
  });

  it("przy opłaconym planie proponuje zmianę planu", () => {
    const platna = subskrypcja({ plan: "pro", okres: "miesiac", ma_platny_plan: true, status: "aktywna" });
    render(<Plany cennik={cennik({ subskrypcja: platna })} />);
    expect(screen.getByRole("button", { name: "Plan aktywny" }).hasAttribute("disabled")).toBe(true);
  });

  it("przy zmianie planu wysyła sprawdzony kod rabatowy", async () => {
    const przejscie = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, assign: przejscie },
    });
    vi.spyOn(platnosciApi, "kupon").mockResolvedValue(KUPON_LATO);
    const zakup = vi.spyOn(platnosciApi, "zakup").mockResolvedValue({
      url: "https://billing.stripe.test/bps_1",
      tryb: "portal",
      plan: "zespol",
      okres: "miesiac",
    });
    const platna = subskrypcja({ plan: "pro", okres: "miesiac", ma_platny_plan: true, status: "aktywna" });
    render(<Plany cennik={cennik({ plany: [PLAN_PRO, PLAN_ZESPOL], subskrypcja: platna })} />);
    fireEvent.change(screen.getByLabelText("Kod rabatowy"), { target: { value: "LATO2026" } });
    screen.getByRole("button", { name: "Sprawdź" }).click();
    await waitFor(() => expect(screen.getByText(/Kod LATO2026 działa/)).toBeTruthy());
    screen.getByRole("button", { name: "Zmień na ten plan" }).click();
    await waitFor(() => expect(zakup).toHaveBeenCalledWith("zespol", "miesiac", "LATO2026"));
    expect(screen.getByText(/Zmianę na plan Zespół \(rozliczenie miesięczne\)/)).toBeTruthy();
    expect(przejscie).toHaveBeenCalledWith("https://billing.stripe.test/bps_1");
  });
});

describe("moja subskrypcja", () => {
  it("pozwala zrezygnować z opłaconego planu i wskazuje skutek", async () => {
    vi.spyOn(platnosciApi, "faktury").mockResolvedValue([]);
    render(
      <MojaSubskrypcja
        subskrypcja={subskrypcja({
          plan: "pro",
          nazwa_planu: "Pro",
          status: "aktywna",
          okres: "miesiac",
          ma_platny_plan: true,
          ma_konto_stripe: true,
        })}
        onZmienPlan={vi.fn()}
        onPortal={vi.fn()}
        onOdswiez={vi.fn()}
      />,
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "Zrezygnuj z planu" })).toBeTruthy());
    expect(screen.getByText(/Plan działa do końca opłaconego okresu/)).toBeTruthy();
  });

  it("wskazuje zapłatę zaległej faktury", async () => {
    vi.spyOn(platnosciApi, "faktury").mockResolvedValue([FAKTURA_OTWARTA]);
    render(
      <MojaSubskrypcja
        subskrypcja={subskrypcja({ ma_platny_plan: true, ma_konto_stripe: true, status: "zalegla" })}
        onZmienPlan={vi.fn()}
        onPortal={vi.fn()}
        onOdswiez={vi.fn()}
      />,
    );
    await waitFor(() => expect(screen.getByRole("link", { name: /Zapłać fakturę/ })).toBeTruthy());
  });

  it("po zakupie pobiera faktury prosto ze Stripe", async () => {
    const pobranie = vi.spyOn(platnosciApi, "faktury").mockResolvedValue([]);
    render(
      <MojaSubskrypcja
        subskrypcja={subskrypcja({ ma_platny_plan: true, ma_konto_stripe: true })}
        poZakupie
        onZmienPlan={vi.fn()}
        onPortal={vi.fn()}
        onOdswiez={vi.fn()}
      />,
    );
    await waitFor(() => expect(pobranie).toHaveBeenCalledWith(true));
  });
});

const SALDO: KredytyInfo = {
  saldo: 120,
  przydzielone: 2000,
  zuzyte: 1880,
  historia: [
    { id: "1", zmiana: -80, saldo_po: 120, powod: "przebieg", opis: "", run_id: "r1", kiedy: "2026-09-20T10:00:00Z" },
  ],
};

const PAKIETY: PakietyInfo = {
  sprzedaz: true,
  pakiety: [
    { kod: "maly", nazwa: "Mały pakiet", opis: "Na dokończenie zadania.", kredyty: 5000, do_kupienia: true },
    { kod: "duzy", nazwa: "Duży pakiet", opis: "Duże zadanie jednorazowe.", kredyty: 60000, do_kupienia: false },
  ],
};

describe("ekran planów: kredyty i okres próbny", () => {
  it("podaje liczbę kredytów planu — jedyny egzekwowany limit", () => {
    render(<Plany cennik={cennik({ plany: [PLAN_PRO] })} />);
    expect(screen.getByText(/20[\s\u00a0\u202f]?000 kredytów/)).toBeTruthy();
    expect(screen.getByText("na okres rozliczeniowy")).toBeTruthy();
  });

  it("przy planie z okresem próbnym mówi o nim obok przycisku zakupu", () => {
    const probny: PlanInfo = { ...PLAN_OSOBISTY, do_kupienia: { miesiac: true, rok: true }, cena_miesiac_gr: 2900 };
    render(<Plany cennik={cennik({ plany: [probny], subskrypcja: subskrypcja({ plan: "pro" }) })} />);
    expect(screen.getByText(/Pierwsze 7 dni bez opłaty/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Wybierz plan" })).toBeTruthy();
  });
});

describe("saldo kredytów i pakiety", () => {
  it("pozwala dokupić pakiet i przechodzi do płatności", async () => {
    const przejscie = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, assign: przejscie },
    });
    vi.spyOn(platnosciApi, "kredyty").mockResolvedValue(SALDO);
    vi.spyOn(platnosciApi, "pakiety").mockResolvedValue(PAKIETY);
    const zakup = vi
      .spyOn(platnosciApi, "zakupPakietu")
      .mockResolvedValue({ url: "https://checkout.stripe.test/cs_2", tryb: "checkout", pakiet: "maly" });
    render(<Kredyty />);
    const przycisk = await screen.findByRole("button", { name: /Mały pakiet/ });
    // Pakiet bez ceny w Stripe nie może się pojawić jako do kupienia.
    expect(screen.queryByRole("button", { name: /Duży pakiet/ })).toBeNull();
    przycisk.click();
    await waitFor(() => expect(zakup).toHaveBeenCalledWith("maly"));
    expect(przejscie).toHaveBeenCalledWith("https://checkout.stripe.test/cs_2");
  });

  it("bez uruchomionej sprzedaży mówi wprost, że dokupienie będzie możliwe później", async () => {
    vi.spyOn(platnosciApi, "kredyty").mockResolvedValue(SALDO);
    vi.spyOn(platnosciApi, "pakiety").mockResolvedValue({
      sprzedaz: false,
      pakiety: PAKIETY.pakiety.map((pozycja) => ({ ...pozycja, do_kupienia: false })),
    });
    render(<Kredyty />);
    expect(await screen.findByText(/Dokupienie kredytów będzie możliwe/)).toBeTruthy();
  });

  it("brak listy pakietów nie przesłania salda", async () => {
    vi.spyOn(platnosciApi, "kredyty").mockResolvedValue(SALDO);
    vi.spyOn(platnosciApi, "pakiety").mockRejectedValue(new Error("brak połączenia"));
    render(<Kredyty />);
    expect(await screen.findByText("Kredyty")).toBeTruthy();
    expect(screen.queryByText(/Dokup kredyty/)).toBeNull();
  });
});

describe("stan braku kredytów w rozmowie", () => {
  it("podaje powód odmowy i prowadzi do dokupienia", () => {
    const dokup = vi.fn();
    render(
      <BrakKredytow
        komunikat="Skończyły się kredyty na tym koncie."
        onDokup={dokup}
        onZamknij={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert").textContent).toMatch(/Skończyły się kredyty/);
    screen.getByRole("button", { name: "Dokup kredyty" }).click();
    expect(dokup).toHaveBeenCalled();
  });
});
