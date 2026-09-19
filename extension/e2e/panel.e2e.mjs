// Test end-to-end rozszerzenia w Chromium (Playwright, rozpakowane rozszerzenie).
//
//   node e2e/panel.e2e.mjs <katalog-rozpakowanego-rozszerzenia>
//
// Strony https://admin.booking.com/… i https://danaco-nexus.pl/… są podstawiane przez
// context.route (bez sieci): strona testowa z opiniami i atrapa trybu ?widok=panel.
// Opcjonalnie NEXUS_TEST_SERWER + NEXUS_TEST_KLUCZ: prawdziwy serwer testowy Nexusa
// do sprawdzenia ekranu opcji (GET /api/rozszerzenie/konfiguracja z kluczem urządzenia).

import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE ?? "/danaco/programy/node/lib/node_modules/playwright");

const KATALOG = dirname(fileURLToPath(import.meta.url));
const ROZSZERZENIE = resolve(process.argv[2] ?? join(KATALOG, "..", "..", ".tmp", "rozszerzenie", "out", "nexus-rozszerzenie"));
const STRONA = readFileSync(join(KATALOG, "strona-opinie.html"), "utf8");
const ATRAPA = readFileSync(join(KATALOG, "atrapa-panelu.html"), "utf8");
const ADRES_STRONY = "https://admin.booking.com/hotel/hoteladmin/opinie";
// Wartość testowa (nie jest kluczem żadnego serwera).
const KLUCZ_TESTOWY = `nxd_${"t".repeat(43)}`;

const wyniki = [];
function sprawdz(nazwa, warunek, szczegoly = "") {
  wyniki.push({ nazwa, ok: !!warunek, szczegoly });
  console.log(`${warunek ? "OK  " : "BŁĄD"} ${nazwa}${szczegoly ? ` – ${szczegoly}` : ""}`);
}

async function czekaj(fn, czas = 8000, krok = 100) {
  const koniec = Date.now() + czas;
  for (;;) {
    const wynik = await fn();
    if (wynik) return wynik;
    if (Date.now() > koniec) return null;
    await new Promise((r) => setTimeout(r, krok));
  }
}

const profil = mkdtempSync(join(process.env.NEXUS_E2E_TMP ?? tmpdir(), "nexus-rozszerzenie-"));
const context = await chromium.launchPersistentContext(profil, {
  channel: "chromium",
  headless: true,
  viewport: { width: 1400, height: 900 },
  args: [`--disable-extensions-except=${ROZSZERZENIE}`, `--load-extension=${ROZSZERZENIE}`],
});

let naglowekRamki = "";
await context.route("https://danaco-nexus.pl/**", (trasa) =>
  trasa.fulfill({
    status: 200,
    contentType: "text/html; charset=utf-8",
    headers: naglowekRamki ? { "Content-Security-Policy": naglowekRamki } : {},
    body: ATRAPA,
  }),
);
await context.route("https://admin.booking.com/**", (trasa) =>
  trasa.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: STRONA }),
);

try {
  const sw = context.serviceWorkers()[0] ?? (await context.waitForEvent("serviceworker", { timeout: 15000 }));
  const idRozszerzenia = new URL(sw.url()).host;
  const pochodzenieRozszerzenia = `chrome-extension://${idRozszerzenia}`;
  sprawdz("rozszerzenie załadowane (service worker)", !!idRozszerzenia, idRozszerzenia);
  await sw.evaluate(
    (klucz) => chrome.storage.local.set({ "nexus-rozszerzenie": { serwer: "https://danaco-nexus.pl", klucz } }),
    KLUCZ_TESTOWY,
  );

  const ramki = (strona) => ({
    panel: strona.frames().find((f) => f.url().startsWith(`${pochodzenieRozszerzenia}/panel.html`)),
    nexus: strona.frames().find((f) => f.url().startsWith("https://danaco-nexus.pl/?widok=panel")),
  });
  const odebrane = (nexus, typ) =>
    nexus.evaluate((t) => window.__odebrane.filter((m) => m.data.type === t), typ).catch(() => []);
  const czekajNaKomunikat = async (nexus, typ, ile, czas = 8000) =>
    czekaj(async () => {
      const lista = await odebrane(nexus, typ);
      return lista.length >= ile ? lista[ile - 1] : null;
    }, czas);

  // ---------- scenariusz główny: frame-ancestors dopuszcza rozszerzenie ----------
  naglowekRamki = `frame-ancestors ${pochodzenieRozszerzenia}`;
  const strona = await context.newPage();
  await strona.goto(ADRES_STRONY);
  const host = await strona.waitForSelector("danaco-nexus", { state: "attached", timeout: 10000 }).catch(() => null);
  sprawdz("skrypt treści wstrzyknął panel (<danaco-nexus>, zamknięty Shadow DOM)", !!host);
  sprawdz(
    "Shadow DOM panelu niedostępny dla skryptów strony",
    await strona.evaluate(() => document.querySelector("danaco-nexus")?.shadowRoot === null),
  );

  // Pływający przycisk przy prawej krawędzi (62% wysokości, 44 px).
  await strona.mouse.click(1400 - 14, Math.round(900 * 0.62) + 22);
  const r1 = await czekaj(async () => {
    const r = ramki(strona);
    return r.panel && r.nexus ? r : null;
  }, 10000);
  sprawdz("kliknięcie przycisku otwiera panel z ramką Nexusa ?widok=panel", !!r1);
  if (!r1) throw new Error("Panel się nie otworzył – dalsze kroki bez sensu.");
  const { panel, nexus } = r1;

  const auth = await czekajNaKomunikat(nexus, "nexus:auth", 1);
  sprawdz("nexus:auth po nexus:ready z kluczem urządzenia", auth?.data.token === KLUCZ_TESTOWY);
  sprawdz("komunikaty do Nexusa pochodzą z rozszerzenia", auth?.origin === pochodzenieRozszerzenia, auth?.origin);
  await panel.waitForSelector('[data-akcja="stresc"]:not([disabled])', { timeout: 5000 });

  // Streść stronę → kontekst strony (artykuł) + polecenie.
  await panel.click('[data-akcja="stresc"]');
  const kontekst1 = await czekajNaKomunikat(nexus, "nexus:context", 1);
  const polecenie1 = await czekajNaKomunikat(nexus, "nexus:prompt", 1);
  const k1 = kontekst1?.data.context;
  sprawdz(
    "Streść: nexus:context z tytułem, adresem i treścią artykułu",
    k1?.kind === "page" && k1?.url === ADRES_STRONY && k1?.title.includes("Opinie gości") && k1?.text.includes("Średnia ocena wynosi 8,3"),
    k1 ? `${k1.text.length} znaków` : "brak",
  );
  sprawdz("Streść: treść bez nawigacji i stopki", k1 && !k1.text.includes("Rezerwacje") && !k1.text.includes("© 2026"));
  sprawdz("Streść: nexus:prompt z send=true", polecenie1?.data.send === true && polecenie1?.data.text.startsWith("Streść"));

  // Odpowiedz na opinię: lista rozpoznanych opinii → wybór → kontekst opinii.
  await panel.click('[data-akcja="odpowiedz"]');
  await panel.waitForSelector(".opinia", { timeout: 5000 });
  const liczbaOpinii = await panel.locator(".opinia").count();
  sprawdz("Odpowiedz: rozpoznano 2 opinie z panelu partnera Booking", liczbaOpinii === 2, String(liczbaOpinii));
  sprawdz("Odpowiedz: przy opinii znaleziono pole odpowiedzi", (await panel.locator(".opinia-pole").count()) === 2);
  await panel.locator(".opinia").first().click();
  const kontekst2 = await czekajNaKomunikat(nexus, "nexus:context", 2);
  const polecenie2 = await czekajNaKomunikat(nexus, "nexus:prompt", 2);
  sprawdz(
    "Odpowiedz: kontekst zawiera autora, ocenę i treść opinii",
    kontekst2?.data.context.text.includes("Autor: Marek") &&
      kontekst2?.data.context.text.includes("Ocena: 7,5") &&
      kontekst2?.data.context.text.includes("klimatyzacja głośno"),
  );
  sprawdz("Odpowiedz: polecenie odpowiedzi właściciela", polecenie2?.data.text.includes("odpowiedź właściciela"));

  // Wstaw: nexus:insert → pole odpowiedzi wybranej opinii.
  const odpowiedz = "Dziękujemy, Panie Marku, za opinię. Sprawdzimy klimatyzację w pokoju.";
  await nexus.evaluate((t) => (window.__doWstawienia = t), odpowiedz);
  await nexus.click("#wstaw");
  const wstawione = await czekaj(async () => (await strona.inputValue("#odp1")) === odpowiedz, 5000);
  sprawdz("Wstaw: tekst trafił do pola odpowiedzi opinii (#odp1)", !!wstawione, await strona.inputValue("#odp1"));
  const zdarzenia = await strona.evaluate(() => window.__zdarzenia);
  sprawdz(
    "Wstaw: strona dostała zdarzenia input i change",
    zdarzenia.some(([t, id]) => t === "input" && id === "odp1") && zdarzenia.some(([t, id]) => t === "change" && id === "odp1"),
  );

  // Wstaw do edytora contenteditable (ostatnio kliknięte pole).
  await strona.click("#edytor");
  await nexus.evaluate(() => (window.__doWstawienia = "Zapraszamy ponownie!"));
  await nexus.click("#wstaw");
  const edytor = await czekaj(async () => (await strona.textContent("#edytor"))?.includes("Zapraszamy ponownie!"), 5000);
  sprawdz("Wstaw: edytor contenteditable", !!edytor);

  // Popraw tekst: cała treść aktywnego pola → „Wstaw” zastępuje treść.
  await strona.fill("#zwykle", "Tekts z błedem");
  await strona.focus("#zwykle");
  await panel.click('[data-akcja="popraw"]');
  const kontekst3 = await czekajNaKomunikat(nexus, "nexus:context", 3);
  sprawdz("Popraw: kontekstem jest treść aktywnego pola", kontekst3?.data.context.text === "Tekts z błedem");
  await nexus.evaluate(() => (window.__doWstawienia = "Tekst z błędem"));
  await nexus.click("#wstaw");
  const poprawione = await czekaj(async () => (await strona.inputValue("#zwykle")) === "Tekst z błędem", 5000);
  sprawdz("Popraw: „Wstaw” zastąpił całą treść pola", !!poprawione, await strona.inputValue("#zwykle"));

  // Zrzut widocznej karty (chrome.tabs.captureVisibleTab), jeśli przeglądarka go ma.
  const zrzutDostepny = await panel.isVisible("#zrzut-etykieta");
  sprawdz("Zrzut: przeglądarka udostępnia captureVisibleTab (przełącznik widoczny)", zrzutDostepny);
  if (zrzutDostepny) {
    await panel.check("#zrzut");
    await panel.click('[data-akcja="stresc"]');
    const kontekst4 = await czekajNaKomunikat(nexus, "nexus:context", 4, 10000);
    const obraz = kontekst4?.data.context.image ?? "";
    sprawdz("Zrzut: kontekst z obrazem JPEG (data URL)", obraz.startsWith("data:image/jpeg;base64,"), `${obraz.length} znaków`);
    await panel.uncheck("#zrzut");
  }

  // Akcja z menu kontekstowego (symulacja kliknięcia: ta sama funkcja tła).
  const przed = (await odebrane(nexus, "nexus:context")).length;
  await sw.evaluate(async (adres) => {
    const [karta] = await chrome.tabs.query({ url: `${adres}*` });
    await globalThis.nexusZlecAkcje(karta.id, { akcja: "przetlumacz", tekst: "Dzień dobry, pokój jest gotowy.", tytul: "t", adres });
  }, ADRES_STRONY);
  const kontekst5 = await czekajNaKomunikat(nexus, "nexus:context", przed + 1);
  const polecenia = await odebrane(nexus, "nexus:prompt");
  sprawdz(
    "Menu kontekstowe → Przetłumacz: zaznaczenie trafia do Nexusa z poleceniem tłumaczenia",
    kontekst5?.data.context.text === "Dzień dobry, pokój jest gotowy." && polecenia.at(-1)?.data.text.includes("Przetłumacz"),
  );

  // Strona nie może wysłać poleceń do ramki Nexusa (inne pochodzenie).
  await strona.evaluate(() => {
    const wszystkie = [];
    const zbierz = (w) => {
      for (let i = 0; i < w.frames.length; i += 1) {
        wszystkie.push(w.frames[i]);
        zbierz(w.frames[i]);
      }
    };
    zbierz(window);
    for (const ramka of wszystkie) ramka.postMessage({ type: "nexus:prompt", text: "atak", send: true }, "*");
  });
  await new Promise((r) => setTimeout(r, 500));
  const odrzucone = await nexus.evaluate(() => window.__odrzucone.map((m) => m.origin));
  const przyjeteAtaki = (await odebrane(nexus, "nexus:prompt")).filter((m) => m.data.text === "atak");
  sprawdz(
    "Wiadomości strony do ramki Nexusa mają pochodzenie strony (do odrzucenia przez panel)",
    przyjeteAtaki.length === 0 && odrzucone.includes("https://admin.booking.com"),
  );

  // Escape w panelu zamyka, Alt+N otwiera ponownie.
  await panel.press("body", "Escape");
  const ramkaPanelu = await panel.frameElement();
  const zamkniety = await czekaj(async () => !(await ramkaPanelu.isVisible()), 3000);
  sprawdz("Escape zamyka panel", !!zamkniety);
  await strona.click("h1");
  await strona.keyboard.press("Alt+N");
  const otwarty = await czekaj(async () => ramkaPanelu.isVisible(), 3000);
  sprawdz("Alt+N otwiera panel", !!otwarty);

  // ---------- nagłówki ramki Nexusa: co musi wysłać serwer ----------
  const probaNaglowka = async (naglowek) => {
    naglowekRamki = naglowek;
    const s = await context.newPage();
    await s.goto(`${ADRES_STRONY}?proba=${encodeURIComponent(naglowek)}`);
    await s.waitForSelector("danaco-nexus", { state: "attached" });
    await s.keyboard.press("Control+Shift+Space");
    const gotowy = await czekaj(async () => {
      const { nexus: n } = ramki(s);
      if (!n) return false;
      return (await odebrane(n, "nexus:auth")).length > 0;
    }, 6000);
    await s.close();
    return !!gotowy;
  };
  sprawdz(
    "frame-ancestors 'none' (obecny nagłówek produkcji) blokuje panel",
    !(await probaNaglowka("frame-ancestors 'none'")),
  );
  sprawdz("frame-ancestors chrome-extension: (cały schemat) wystarcza", await probaNaglowka("frame-ancestors 'self' chrome-extension:"));

  // ---------- ekran opcji z prawdziwym serwerem testowym ----------
  if (process.env.NEXUS_TEST_SERWER && process.env.NEXUS_TEST_KLUCZ) {
    const opcje = await context.newPage();
    await opcje.goto(`${pochodzenieRozszerzenia}/opcje.html`);
    await opcje.fill("#nx-serwer", process.env.NEXUS_TEST_SERWER);
    await opcje.fill("#nx-klucz", process.env.NEXUS_TEST_KLUCZ);
    await opcje.click("button[type=submit]");
    const stan = await czekaj(async () => {
      const tekst = (await opcje.textContent(".stan")) ?? "";
      return tekst && !tekst.startsWith("Sprawdzanie") ? tekst : null;
    }, 8000);
    sprawdz("Opcje: połączenie z serwerem testowym kluczem urządzenia (bez CORS)", stan?.startsWith("Połączono jako"), stan ?? "");
    await opcje.fill("#nx-klucz", `nxd_${"z".repeat(43)}`);
    await opcje.click("button[type=submit]");
    const stanZly = await czekaj(async () => {
      const tekst = (await opcje.textContent(".stan")) ?? "";
      return tekst.startsWith("Klucz") ? tekst : null;
    }, 8000);
    sprawdz("Opcje: zły klucz odrzucony", !!stanZly, stanZly ?? "");
    const zapisany = await sw.evaluate(() => chrome.storage.local.get("nexus-rozszerzenie"));
    sprawdz(
      "Opcje: zapisano tylko poprawny klucz",
      zapisany["nexus-rozszerzenie"].klucz === process.env.NEXUS_TEST_KLUCZ,
    );
  }
} catch (blad) {
  sprawdz("przebieg testu bez wyjątku", false, String(blad?.stack ?? blad));
} finally {
  await context.close();
  rmSync(profil, { recursive: true, force: true });
}

const bledy = wyniki.filter((w) => !w.ok);
console.log(`\n${wyniki.length - bledy.length}/${wyniki.length} sprawdzeń zaliczonych.`);
process.exit(bledy.length ? 1 : 0);
