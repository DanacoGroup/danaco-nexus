// Panel rozszerzenia (strona chrome-extension:// w ramce wstrzykniętej na stronę):
// pasek szybkich akcji, wybór opinii i ramka Nexusa w trybie ?widok=panel.

import type {
  AkcjaMenu,
  DoTresci,
  Kontekst,
  Mozliwosci,
  OpiniaSkrot,
  WynikKontekstu,
  WynikWstawiania,
  Zakres,
  ZTresci,
} from "../wspolne/komunikaty";
import { TYP_PORTU } from "../wspolne/komunikaty";
import { IKONY, logo } from "../wspolne/ikony";
import { formularzPolaczenia } from "../wspolne/polaczenie";
import { wczytaj, zapisz, type Ustawienia } from "../wspolne/ustawienia";
import { MostNexusa } from "./most";
import { JEZYKI, polecenie, type Akcja } from "./polecenia";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const CZAS_GOTOWOSCI_MS = 20000;
type BezNumeru<T> = T extends unknown ? Omit<T, "nr"> : never;

let ustawienia: Ustawienia;
let most: MostNexusa | null = null;
let port: MessagePort | null = null;
let numer = 0;
let strona = { host: "", tytul: "", ukrytyPrzycisk: false };
let mozliwosci: Mozliwosci = { zrzut: false, menu: false, skroty: false, opcje: false };
const oczekiwane = new Map<number, (dane: unknown) => void>();

// ---------- komunikaty ----------

function pokazKomunikat(tekst: string, blad = false): void {
  const el = $("komunikat");
  el.textContent = tekst;
  el.classList.toggle("blad", blad);
  el.classList.add("widoczny");
  clearTimeout(Number(el.dataset.czas));
  el.dataset.czas = String(setTimeout(() => el.classList.remove("widoczny"), blad ? 6000 : 3500));
}

async function doTla<T>(komunikat: { type: string }): Promise<T | null> {
  try {
    if (!globalThis.chrome?.runtime?.sendMessage) return null;
    return ((await chrome.runtime.sendMessage(komunikat)) as T) ?? null;
  } catch {
    return null;
  }
}

/** Zapytanie do skryptu treści (przez prywatny port) z odpowiedzią. */
function doTresci<T>(komunikat: BezNumeru<Extract<DoTresci, { nr: number }>>, czas = 8000): Promise<T | null> {
  if (!port) return Promise.resolve(null);
  const nr = ++numer;
  return new Promise((gotowe) => {
    const limit = setTimeout(() => {
      oczekiwane.delete(nr);
      gotowe(null);
    }, czas);
    oczekiwane.set(nr, (dane) => {
      clearTimeout(limit);
      gotowe(dane as T);
    });
    port!.postMessage({ ...komunikat, nr } as DoTresci);
  });
}

function doTresciBezOdpowiedzi(komunikat: DoTresci): void {
  port?.postMessage(komunikat);
}

function naKomunikatTresci(dane: ZTresci): void {
  switch (dane?.type) {
    case "odpowiedz":
      oczekiwane.get(dane.nr)?.(dane.dane);
      oczekiwane.delete(dane.nr);
      break;
    case "pole":
      $("pole-info").textContent = dane.aktywne ? `Wstaw → ${dane.opis}` : "";
      break;
    case "strona":
      strona = { host: String(dane.host), tytul: String(dane.tytul), ukrytyPrzycisk: !!dane.ukrytyPrzycisk };
      odswiezPrzyciskUkrycia();
      break;
    case "sprawdz-oczekujace":
      void sprawdzOczekujace();
      break;
    default:
      break;
  }
}

/** Jednorazowe przyjęcie portu od skryptu treści – tylko z kluczem z adresu tej ramki. */
function przyjmijPort(): void {
  const klucz = new URLSearchParams(location.hash.slice(1)).get("k");
  window.addEventListener("message", (e: MessageEvent) => {
    const dane = e.data as { type?: string; klucz?: string } | null;
    if (port || !klucz || dane?.type !== TYP_PORTU || dane.klucz !== klucz || !e.ports[0]) return;
    port = e.ports[0];
    port.onmessage = (zdarzenie: MessageEvent<ZTresci>) => naKomunikatTresci(zdarzenie.data);
  });
}

// ---------- schowek i wstawianie ----------

async function kopiuj(tekst: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(tekst);
    return true;
  } catch {
    const pole = document.createElement("textarea");
    pole.value = tekst;
    pole.style.cssText = "position:fixed;opacity:0;top:0;left:0";
    document.body.append(pole);
    pole.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    pole.remove();
    return ok;
  }
}

async function wstaw(tekst: string): Promise<void> {
  const wynik = await doTresci<WynikWstawiania>({ type: "wstaw", tekst });
  if (wynik?.ok) {
    pokazKomunikat(`Wstawiono do: ${wynik.opis ?? "pole na stronie"}.`);
    return;
  }
  const skopiowano = await kopiuj(tekst);
  pokazKomunikat(
    skopiowano
      ? "Nie wybrano pola na stronie – tekst skopiowano do schowka. Kliknij pole i wklej (Ctrl+V)."
      : "Nie wybrano pola, a przeglądarka zablokowała schowek. Kliknij pole na stronie i spróbuj ponownie.",
    !skopiowano,
  );
}

// ---------- ramka Nexusa ----------

function nakladka(tresc: Array<Node | string>): HTMLElement {
  const el = document.createElement("div");
  el.className = "nakladka";
  el.append(...tresc);
  return el;
}

function przycisk(tekst: string, klasa: string, akcja: () => void): HTMLButtonElement {
  const el = document.createElement("button");
  el.type = "button";
  el.className = klasa;
  el.textContent = tekst;
  el.addEventListener("click", akcja);
  return el;
}

function pokazLogowanie(): void {
  most?.zamknij();
  most = null;
  ustawAkcje(false);
  const kontener = document.createElement("div");
  const tytul = document.createElement("strong");
  tytul.textContent = "Połącz rozszerzenie z Nexusem";
  const glowna = $("glowna");
  glowna.replaceChildren(nakladka([tytul, kontener]));
  void formularzPolaczenia(kontener, (nowe) => {
    ustawienia = nowe;
    if (nowe.klucz) setTimeout(zaladujNexusa, 600);
  });
}

function zaladujNexusa(): void {
  if (!ustawienia.klucz) {
    pokazLogowanie();
    return;
  }
  most?.zamknij();
  const glowna = $("glowna");
  const ramka = document.createElement("iframe");
  ramka.title = "Rozmowa z Nexusem";
  ramka.src = `${ustawienia.serwer}/?widok=panel`;
  ramka.setAttribute("allow", "clipboard-write; clipboard-read; microphone");
  const ladowanie = nakladka(["Łączenie z Nexusem…"]);
  glowna.replaceChildren(ramka, ladowanie);
  ustawAkcje(false);
  const limit = setTimeout(() => {
    if (most?.czyGotowy) return;
    const opis = document.createElement("span");
    opis.textContent =
      "Nexus nie odpowiada w trybie panelu. Sprawdź adres serwera i klucz w ustawieniach albo otwórz Nexusa w nowej karcie.";
    ladowanie.replaceChildren(
      Object.assign(document.createElement("strong"), { textContent: "Brak połączenia" }),
      opis,
      przycisk("Spróbuj ponownie", "glowny", zaladujNexusa),
      przycisk("Ustawienia", "drugorzedny", otworzUstawienia),
    );
  }, CZAS_GOTOWOSCI_MS);
  most = new MostNexusa(window, ramka, ustawienia.serwer, ustawienia.klucz, {
    gotowy: () => {
      clearTimeout(limit);
      ladowanie.remove();
      ustawAkcje(true);
      void sprawdzOczekujace();
    },
    wstaw: (tekst) => void wstaw(tekst),
    kopiuj: (tekst) =>
      void kopiuj(tekst).then((ok) => pokazKomunikat(ok ? "Skopiowano do schowka." : "Nie udało się skopiować.", !ok)),
  });
}

function ustawAkcje(wlaczone: boolean): void {
  for (const el of Array.from($("akcje").querySelectorAll("button"))) el.disabled = !wlaczone;
}

// ---------- szybkie akcje ----------

async function kontekst(zakres: Zakres, id?: string): Promise<WynikKontekstu> {
  const wynik = await doTresci<WynikKontekstu>({ type: "kontekst", zakres, id });
  return wynik ?? { ok: false, blad: "Strona nie odpowiada – odśwież kartę i spróbuj ponownie." };
}

async function zrzutEkranu(): Promise<string | undefined> {
  if (!mozliwosci.zrzut || !($("zrzut") as HTMLInputElement).checked) return undefined;
  await doTresci({ type: "ukryj-na-chwile" }, 2000);
  const wynik = await doTla<{ ok: boolean; obraz?: string; blad?: string }>({ type: "nexus-ext:zrzut" });
  doTresciBezOdpowiedzi({ type: "pokaz" });
  if (!wynik?.ok) pokazKomunikat(`Zrzut ekranu niedostępny: ${wynik?.blad ?? "brak odpowiedzi"}`, true);
  return wynik?.obraz;
}

async function wyslijDoNexusa(k: Kontekst, akcja: Akcja, rodzaj?: OpiniaSkrot["rodzaj"]): Promise<void> {
  if (!most) return;
  const obraz = await zrzutEkranu();
  const tresc: Kontekst = obraz ? { ...k, image: obraz } : k;
  const { text, send } = polecenie(akcja, { rodzaj, jezyk: ustawienia.jezyk });
  most.wyslij({ type: "nexus:context", context: tresc });
  most.wyslij({ type: "nexus:prompt", text, send });
}

async function wykonaj(akcja: Akcja): Promise<void> {
  zamknijOpinie();
  if (akcja === "odpowiedz") {
    await pokazOpinie();
    return;
  }
  let wynik: WynikKontekstu;
  if (akcja === "stresc") wynik = await kontekst("strona");
  else if (akcja === "popraw") wynik = await kontekst("pole");
  else wynik = await kontekst("auto");
  if (!wynik.ok || !wynik.kontekst) {
    pokazKomunikat(wynik.blad ?? "Nie udało się odczytać strony.", true);
    return;
  }
  await wyslijDoNexusa(wynik.kontekst, akcja);
  if (akcja === "popraw" && wynik.zrodlo === "pole") {
    pokazKomunikat("„Wstaw” przy odpowiedzi zastąpi treść pola poprawioną wersją.");
  }
}

function zamknijOpinie(): void {
  const sekcja = $("opinie");
  sekcja.hidden = true;
  sekcja.replaceChildren();
  $("akcje").querySelector('[data-akcja="odpowiedz"]')?.setAttribute("aria-pressed", "false");
  doTresciBezOdpowiedzi({ type: "podswietl", id: null });
}

async function odpowiedzNa(zakres: Zakres, id?: string): Promise<void> {
  const wynik = await kontekst(zakres, id);
  if (!wynik.ok || !wynik.kontekst) {
    pokazKomunikat(wynik.blad ?? "Nie udało się odczytać opinii.", true);
    return;
  }
  zamknijOpinie();
  await wyslijDoNexusa(wynik.kontekst, "odpowiedz", wynik.rodzaj);
}

async function pokazOpinie(): Promise<void> {
  const sekcja = $("opinie");
  const opinie = (await doTresci<OpiniaSkrot[]>({ type: "opinie" })) ?? [];
  $("akcje").querySelector('[data-akcja="odpowiedz"]')?.setAttribute("aria-pressed", "true");
  const naglowek = document.createElement("div");
  naglowek.className = "opinie-naglowek";
  naglowek.append(
    Object.assign(document.createElement("span"), {
      textContent: opinie.length ? `Wybierz, na co odpowiedzieć (${opinie.length}):` : "Nie rozpoznano opinii na tej stronie.",
    }),
    przycisk("Zamknij", "link", zamknijOpinie),
  );
  const lista = document.createElement("ul");
  for (const opinia of opinie) {
    const pozycja = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "opinia";
    const meta = document.createElement("div");
    meta.className = "opinia-meta";
    meta.append(Object.assign(document.createElement("strong"), { textContent: opinia.autor || rodzajOpisu(opinia.rodzaj) }));
    if (opinia.ocena) meta.append(Object.assign(document.createElement("span"), { textContent: opinia.ocena }));
    if (opinia.data) meta.append(Object.assign(document.createElement("span"), { textContent: opinia.data }));
    const tekst = document.createElement("div");
    tekst.className = "opinia-tekst";
    tekst.textContent = opinia.tekst;
    btn.append(meta, tekst);
    if (opinia.poleOdpowiedzi) {
      btn.append(Object.assign(document.createElement("div"), { className: "opinia-pole", textContent: "Znaleziono pole odpowiedzi – „Wstaw” trafi tam." }));
    }
    btn.addEventListener("mouseenter", () => doTresciBezOdpowiedzi({ type: "podswietl", id: opinia.id }));
    btn.addEventListener("focus", () => doTresciBezOdpowiedzi({ type: "podswietl", id: opinia.id }));
    btn.addEventListener("click", () => void odpowiedzNa("opinia", opinia.id));
    pozycja.append(btn);
    lista.append(pozycja);
  }
  const zapas = document.createElement("p");
  zapas.className = "pusto";
  zapas.append(
    opinie.length ? "Nie ma jej na liście? " : "Zaznacz tekst opinii lub wiadomości na stronie i ",
    przycisk(opinie.length ? "Użyj zaznaczonego tekstu" : "użyj zaznaczenia", "link", () => void odpowiedzNa("zaznaczenie")),
  );
  sekcja.replaceChildren(naglowek, lista, zapas);
  sekcja.hidden = false;
}

function rodzajOpisu(rodzaj: OpiniaSkrot["rodzaj"]): string {
  return rodzaj === "wiadomosc" ? "Wiadomość" : rodzaj === "komentarz" ? "Komentarz" : "Opinia";
}

/** Akcja zlecona z menu kontekstowego (pobierana z tła – nie z portu strony). */
async function sprawdzOczekujace(): Promise<void> {
  if (!most?.czyGotowy) return;
  const akcja = await doTla<AkcjaMenu>({ type: "nexus-ext:oczekujace" });
  if (!akcja) return;
  if (akcja.akcja === "stresc") {
    await wykonaj("stresc");
    return;
  }
  if (!akcja.tekst) {
    if (akcja.akcja === "odpowiedz") await pokazOpinie();
    return;
  }
  const k: Kontekst = { kind: "page", title: akcja.tytul, url: akcja.adres, text: akcja.tekst };
  const mapa: Record<Exclude<AkcjaMenu["akcja"], "stresc">, Akcja> = {
    zapytaj: "zapytaj",
    przetlumacz: "przetlumacz",
    odpowiedz: "odpowiedz",
  };
  await wyslijDoNexusa(k, mapa[akcja.akcja]);
}

// ---------- ustawienia ----------

async function otworzUstawienia(): Promise<void> {
  if (mozliwosci.opcje && (await doTla<boolean>({ type: "nexus-ext:opcje" }))) return;
  // Brak strony opcji (np. Danaco Lynx) – formularz w panelu.
  most?.zamknij();
  most = null;
  const kontener = document.createElement("div");
  const glowna = $("glowna");
  glowna.replaceChildren(
    nakladka([
      Object.assign(document.createElement("strong"), { textContent: "Ustawienia połączenia" }),
      kontener,
      przycisk("Wróć do rozmowy", "drugorzedny", zaladujNexusa),
    ]),
  );
  await formularzPolaczenia(kontener, (nowe) => {
    ustawienia = nowe;
  });
}

function odswiezPrzyciskUkrycia(): void {
  const el = $<HTMLButtonElement>("ukryj-przycisk");
  el.hidden = !strona.host || !ustawienia.przycisk;
  el.textContent = strona.ukrytyPrzycisk ? "Pokaż przycisk na tej stronie" : "Ukryj przycisk na tej stronie";
}

async function przelaczUkrycie(): Promise<void> {
  if (!strona.host) return;
  const hosty = new Set(ustawienia.ukryteHosty);
  if (hosty.has(strona.host)) hosty.delete(strona.host);
  else hosty.add(strona.host);
  ustawienia = await zapisz({ ukryteHosty: [...hosty] }, true);
  strona.ukrytyPrzycisk = hosty.has(strona.host);
  odswiezPrzyciskUkrycia();
  pokazKomunikat(strona.ukrytyPrzycisk ? "Przycisk ukryty – panel otworzysz skrótem Alt+N." : "Przycisk znów widoczny.");
}

// ---------- start ----------

async function start(): Promise<void> {
  przyjmijPort();
  $("znak").innerHTML = logo(20);
  $("nowa-karta").innerHTML = IKONY.nowaKarta;
  $("ustawienia").innerHTML = IKONY.ustawienia;
  $("zamknij").innerHTML = IKONY.zamknij;
  $("zrzut-ikona").innerHTML = IKONY.aparat;
  const ikonyAkcji: Record<Akcja, string> = {
    stresc: IKONY.stresc,
    odpowiedz: IKONY.odpowiedz,
    popraw: IKONY.popraw,
    przetlumacz: IKONY.tlumacz,
    zapytaj: IKONY.pytanie,
  };
  for (const el of Array.from($("akcje").querySelectorAll<HTMLButtonElement>("button[data-akcja]"))) {
    const akcja = el.dataset.akcja as Akcja;
    el.insertAdjacentHTML("afterbegin", ikonyAkcji[akcja]);
    el.addEventListener("click", () => void wykonaj(akcja));
  }

  ustawienia = await wczytaj(true);
  mozliwosci = (await doTla<Mozliwosci>({ type: "nexus-ext:mozliwosci" })) ?? mozliwosci;
  $("zrzut-etykieta").hidden = !mozliwosci.zrzut;
  const zrzut = $<HTMLInputElement>("zrzut");
  zrzut.checked = ustawienia.zrzut;
  zrzut.addEventListener("change", () => void zapisz({ zrzut: zrzut.checked }, true).then((u) => (ustawienia = u)));
  const jezyk = $<HTMLSelectElement>("jezyk");
  for (const nazwa of JEZYKI) jezyk.append(new Option(nazwa, nazwa, false, nazwa === ustawienia.jezyk));
  jezyk.addEventListener("change", () => void zapisz({ jezyk: jezyk.value }, true).then((u) => (ustawienia = u)));

  $("zamknij").addEventListener("click", () => doTresciBezOdpowiedzi({ type: "zamknij" }));
  $("ustawienia").addEventListener("click", () => void otworzUstawienia());
  $("nowa-karta").addEventListener("click", () => window.open(`${ustawienia.serwer}/`, "_blank", "noopener"));
  $("ukryj-przycisk").addEventListener("click", () => void przelaczUkrycie());
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") doTresciBezOdpowiedzi({ type: "zamknij" });
    if (e.altKey && !e.ctrlKey && e.code === "KeyN") {
      e.preventDefault();
      doTresciBezOdpowiedzi({ type: "przelacz" });
    }
  });

  zaladujNexusa();
}

void start();
