// Sterownik przeglądarki dla agenta: jedno okno Chromium na czas zadania, polecenia
// wierszami JSON na standardowym wejściu, odpowiedzi wierszami JSON na wyjściu.
//
// Agent miał dotąd zrzut ekranu (jednorazowe uruchomienie `playwright screenshot`) i odczyt
// treści strony po HTTP. Nie miał przeglądarki: nie mógł kliknąć, wypełnić pola ani przejść
// dalej, więc wszystko, co jest za formularzem albo za kliknięciem, było dla niego zamknięte.
//
// Strona jest danymi, nie poleceniem — ten sterownik wyłącznie wykonuje to, co przyszło od
// serwera, i odsyła stan. Adresy sprawdza strona pythonowa (ochrona przed SSRF).

import readline from "node:readline";

// Playwright stoi we wspólnych modułach serwera, a nie obok tego pliku — ESM nie czyta
// NODE_PATH, więc ścieżkę podaje serwer (NEXUS_PLAYWRIGHT) i importujemy ją wprost.
const { chromium } = await import(
  `${process.env.NEXUS_PLAYWRIGHT || "/danaco/programy/node/lib/node_modules/playwright"}/index.mjs`
);

const SZEROKOSCI = { telefon: [390, 844], tablet: [820, 1180], komputer: [1440, 900] };
const LIMIT_TEKSTU = 12000;
const LIMIT_ELEMENTOW = 60;
const CZAS_AKCJI_MS = 20000;

let przegladarka = null;
let kontekst = null;
let karta = null;

async function zapewnijKarte(urzadzenie = "komputer") {
  if (karta) return karta;
  przegladarka = await chromium.launch({ args: ["--no-sandbox"] });
  const [szerokosc, wysokosc] = SZEROKOSCI[urzadzenie] ?? SZEROKOSCI.komputer;
  kontekst = await przegladarka.newContext({
    viewport: { width: szerokosc, height: wysokosc },
    locale: "pl-PL",
    // Bez uprawnień do kamery, mikrofonu i położenia — agent ich nie potrzebuje.
    permissions: [],
  });
  kontekst.setDefaultTimeout(CZAS_AKCJI_MS);
  karta = await kontekst.newPage();
  return karta;
}

/** Elementy, w które da się kliknąć albo coś wpisać — to jest mapa strony dla modelu. */
async function elementy() {
  return karta.evaluate((limit) => {
    const widoczny = (el) => {
      const r = el.getBoundingClientRect();
      return r.width > 2 && r.height > 2 && getComputedStyle(el).visibility !== "hidden";
    };
    const nazwa = (el) =>
      (el.getAttribute("aria-label") || el.innerText || el.value || el.getAttribute("placeholder") || el.getAttribute("title") || "")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 80);
    const wynik = [];
    for (const el of document.querySelectorAll("a[href], button, input, select, textarea, [role=button], [role=link], [role=tab]")) {
      if (!widoczny(el) || wynik.length >= limit) continue;
      const rodzaj = el.tagName === "A" ? "odsyłacz" : el.tagName === "INPUT" || el.tagName === "TEXTAREA" ? "pole" : el.tagName === "SELECT" ? "lista" : "przycisk";
      const pozycja = { rodzaj, nazwa: nazwa(el) };
      if (el.tagName === "A" && el.href) pozycja.adres = el.href.slice(0, 200);
      if (el.tagName === "INPUT") pozycja.typ = el.type;
      if (pozycja.nazwa) wynik.push(pozycja);
    }
    return wynik;
  }, LIMIT_ELEMENTOW);
}

async function stan(zrzutDo) {
  const tekst = await karta.evaluate((limit) => {
    const korzen = document.querySelector("main") || document.body;
    return (korzen.innerText || "").replace(/\n{3,}/g, "\n\n").slice(0, limit);
  }, LIMIT_TEKSTU);
  const odpowiedz = {
    ok: true,
    adres: karta.url(),
    tytul: await karta.title(),
    tekst,
    elementy: await elementy(),
  };
  if (zrzutDo) {
    await karta.screenshot({ path: zrzutDo, fullPage: false });
    odpowiedz.zrzut = zrzutDo;
  }
  return odpowiedz;
}

/** Element wskazany opisem: najpierw rola i nazwa dostępna, potem widoczny tekst, na końcu selektor CSS. */
function wskaz(opis) {
  if (opis.startsWith("css=")) return karta.locator(opis.slice(4)).first();
  return karta
    .getByRole("button", { name: opis, exact: false })
    .or(karta.getByRole("link", { name: opis, exact: false }))
    .or(karta.getByLabel(opis, { exact: false }))
    .or(karta.getByPlaceholder(opis, { exact: false }))
    .or(karta.getByText(opis, { exact: false }))
    .first();
}

async function wykonaj(polecenie) {
  switch (polecenie.akcja) {
    case "otworz": {
      await zapewnijKarte(polecenie.urzadzenie);
      await karta.goto(polecenie.adres, { waitUntil: "domcontentloaded", timeout: CZAS_AKCJI_MS });
      await karta.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
      return stan(polecenie.zrzut);
    }
    case "klik":
      await wskaz(polecenie.co).click({ timeout: CZAS_AKCJI_MS });
      await karta.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
      return stan(polecenie.zrzut);
    case "wpisz":
      await wskaz(polecenie.pole).fill(polecenie.tekst, { timeout: CZAS_AKCJI_MS });
      if (polecenie.zatwierdz) {
        await karta.keyboard.press("Enter");
        await karta.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
      }
      return stan(polecenie.zrzut);
    case "przewin":
      await karta.evaluate((ile) => window.scrollBy(0, ile), polecenie.ile ?? 800);
      return stan(polecenie.zrzut);
    case "wstecz":
      await karta.goBack({ timeout: CZAS_AKCJI_MS });
      return stan(polecenie.zrzut);
    case "stan":
      return stan(polecenie.zrzut);
    case "zamknij":
      await przegladarka?.close();
      przegladarka = kontekst = karta = null;
      return { ok: true, zamkniete: true };
    default:
      return { ok: false, blad: `Nieznana akcja: ${polecenie.akcja}` };
  }
}

/** Nieudane wskazanie elementu bez listy tego, co na stronie jest, skazuje model na zgadywanie. */
async function podpowiedz() {
  if (!karta) return "";
  try {
    const nazwy = (await elementy()).map((e) => `${e.rodzaj} „${e.nazwa}”`).slice(0, 25);
    return nazwy.length ? ` Na stronie są: ${nazwy.join(", ")}.` : "";
  } catch {
    return "";
  }
}

const wejscie = readline.createInterface({ input: process.stdin });
for await (const wiersz of wejscie) {
  if (!wiersz.trim()) continue;
  let odpowiedz;
  try {
    odpowiedz = await wykonaj(JSON.parse(wiersz));
  } catch (blad) {
    const tresc = String(blad?.message || blad);
    const brakElementu = /Timeout|strict mode|resolved to 0/.test(tresc);
    odpowiedz = {
      ok: false,
      blad: (brakElementu ? "Nie znalazłem takiego elementu na stronie." : tresc.slice(0, 400)) +
        (brakElementu ? await podpowiedz() : ""),
    };
  }
  process.stdout.write(JSON.stringify(odpowiedz) + "\n");
}
await przegladarka?.close().catch(() => {});
