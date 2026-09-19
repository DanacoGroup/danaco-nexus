// Formularz połączenia z Nexusem (adres serwera + klucz urządzenia) – wspólny dla
// strony opcji i panelu (w przeglądarkach bez strony opcji, np. Danaco Lynx).

import { normalizujSerwer, poprawnyKlucz, wczytaj, zapisz, type Ustawienia } from "./ustawienia";

export interface WynikSprawdzenia {
  ok: boolean;
  komunikat: string;
}

/** Sprawdza klucz na serwerze (GET /api/rozszerzenie/konfiguracja z kluczem urządzenia). */
export async function sprawdzPolaczenie(serwer: string, klucz: string, pobierz: typeof fetch = fetch): Promise<WynikSprawdzenia> {
  let odpowiedz: Response;
  try {
    odpowiedz = await pobierz(`${serwer}/api/rozszerzenie/konfiguracja`, {
      headers: { Authorization: `Bearer ${klucz}` },
      credentials: "omit",
      cache: "no-store",
    });
  } catch {
    return { ok: false, komunikat: "Brak połączenia z serwerem (adres, sieć albo przeglądarka blokuje żądanie)." };
  }
  if (odpowiedz.status === 401) return { ok: false, komunikat: "Klucz jest nieważny albo został cofnięty." };
  if (odpowiedz.status === 404) {
    return { ok: true, komunikat: "Serwer odpowiada, ale nie ma modułu rozszerzenia – zaktualizuj Nexusa." };
  }
  if (!odpowiedz.ok) return { ok: false, komunikat: `Serwer zwrócił błąd ${odpowiedz.status}.` };
  try {
    const dane = (await odpowiedz.json()) as { urzadzenie?: { name?: string } | null; wersja?: string };
    const nazwa = dane.urzadzenie?.name ? ` jako „${dane.urzadzenie.name}”` : "";
    return { ok: true, komunikat: `Połączono${nazwa}. Nexus ${dane.wersja ?? ""}`.trim() };
  } catch {
    return { ok: true, komunikat: "Połączono." };
  }
}

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  atrybuty: Record<string, string> = {},
  tekst = "",
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [nazwa, wartosc] of Object.entries(atrybuty)) el.setAttribute(nazwa, wartosc);
  if (tekst) el.textContent = tekst;
  return el;
}

/**
 * Rysuje formularz w kontenerze. `naZapis` dostaje zapisane ustawienia.
 * Klucz nie jest nigdy pokazywany – pole jest puste, a opis mówi, czy klucz zapisano.
 */
export async function formularzPolaczenia(
  kontener: HTMLElement,
  naZapis: (ustawienia: Ustawienia) => void,
): Promise<void> {
  const ustawienia = await wczytaj(true);
  kontener.replaceChildren();
  const form = element("form", { class: "formularz", novalidate: "" });
  const poleSerwera = element("input", {
    id: "nx-serwer",
    type: "url",
    autocomplete: "url",
    spellcheck: "false",
    placeholder: "https://danaco-nexus.pl",
  });
  poleSerwera.value = ustawienia.serwer;
  const poleKlucza = element("input", {
    id: "nx-klucz",
    type: "password",
    autocomplete: "off",
    spellcheck: "false",
    placeholder: ustawienia.klucz ? "Klucz zapisany – wklej nowy, aby zmienić" : "nxd_…",
  });
  const stan = element("p", { class: "stan", role: "status", "aria-live": "polite" });
  const zapiszPrzycisk = element("button", { type: "submit", class: "glowny" }, "Zapisz i połącz");
  const usun = element("button", { type: "button", class: "drugorzedny" }, "Usuń klucz");
  usun.hidden = !ustawienia.klucz;

  form.append(
    element("label", { for: "nx-serwer" }, "Adres serwera Nexusa"),
    poleSerwera,
    element("label", { for: "nx-klucz" }, "Klucz urządzenia"),
    poleKlucza,
    element(
      "p",
      { class: "pomoc" },
      "Klucz utworzysz w Nexusie: moduł Urządzenia → Nowe urządzenie → rodzaj „Rozszerzenie przeglądarki”. " +
        "Klucz jest pokazywany tylko raz – wklej go tutaj. Przechowywany jest wyłącznie w tej przeglądarce.",
    ),
    element("div", { class: "przyciski" }),
    stan,
  );
  form.querySelector(".przyciski")!.append(zapiszPrzycisk, usun);
  kontener.append(form);

  const pokazStan = (tekst: string, blad: boolean) => {
    stan.textContent = tekst;
    stan.classList.toggle("blad", blad);
  };

  usun.addEventListener("click", async () => {
    const nowe = await zapisz({ klucz: "" }, true);
    usun.hidden = true;
    poleKlucza.placeholder = "nxd_…";
    pokazStan("Klucz usunięty z tej przeglądarki.", false);
    naZapis(nowe);
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const serwer = normalizujSerwer(poleSerwera.value);
    if (!serwer) {
      pokazStan("Podaj adres HTTPS serwera, np. https://danaco-nexus.pl.", true);
      poleSerwera.focus();
      return;
    }
    const wklejony = poleKlucza.value.trim();
    const klucz = wklejony || ustawienia.klucz;
    if (!klucz) {
      pokazStan("Wklej klucz urządzenia.", true);
      poleKlucza.focus();
      return;
    }
    if (!poprawnyKlucz(klucz)) {
      pokazStan("To nie wygląda na klucz urządzenia – powinien zaczynać się od „nxd_”.", true);
      poleKlucza.focus();
      return;
    }
    zapiszPrzycisk.disabled = true;
    pokazStan("Sprawdzanie połączenia…", false);
    const wynik = await sprawdzPolaczenie(serwer, klucz);
    zapiszPrzycisk.disabled = false;
    if (!wynik.ok && wynik.komunikat.startsWith("Klucz")) {
      pokazStan(wynik.komunikat, true);
      return;
    }
    const nowe = await zapisz({ serwer, klucz }, true);
    Object.assign(ustawienia, nowe);
    poleKlucza.value = "";
    poleKlucza.placeholder = "Klucz zapisany – wklej nowy, aby zmienić";
    usun.hidden = false;
    pokazStan(wynik.ok ? wynik.komunikat : `Zapisano. ${wynik.komunikat}`, !wynik.ok);
    naZapis(nowe);
  });
}
