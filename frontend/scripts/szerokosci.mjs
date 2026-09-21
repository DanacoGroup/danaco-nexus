#!/usr/bin/env node
// Szuka poziomego przelewu na telefonie: strony, które da się przewinąć w bok.
//
// Przelew bierze się zwykle stąd, że pozycja siatki ma domyślnie „min-width: auto”
// i jeden długi, nierozdzielny ciąg (wyliczenie formatów, adres, nazwa pliku) rozpycha
// kolumnę ponad szerokość ekranu. Na desktopie nie widać tego wcale — dlatego pomiar.
//
// Uruchomienie (na zbudowanym pliku, wystawionym pod dowolnym adresem):
//
//   node frontend/scripts/szerokosci.mjs http://127.0.0.1:8992
//
// Kod wyjścia 1, gdy którakolwiek trasa się przelewa — nadaje się do kontroli w CI.

import { createRequire } from "node:module";

const { chromium } = createRequire(import.meta.url)("playwright");

const BAZA = process.argv[2] || "http://127.0.0.1:8992";
const SZEROKOSC = Number(process.argv[3] || 390);

const TRASY = [
  "/",
  "/cennik",
  "/mozliwosci",
  "/o-nas",
  "/kontakt",
  "/portal",
  "/portal/oferta",
  "/portal/funkcje",
  "/portal/zastosowania",
  "/portal/narzedzia",
  "/portal/cennik",
  "/portal/kontakt",
  "/portal/szukaj",
  "/portal/dokumentacja",
  "/portal/blog",
  "/portal/wiedza",
  "/portal/prywatnosc",
  "/portal/regulamin",
  "/portal/cookies",
];

const przegladarka = await chromium.launch();
const karta = await (
  await przegladarka.newContext({ viewport: { width: SZEROKOSC, height: 844 } })
).newPage();

let przelewy = 0;
for (const trasa of TRASY) {
  await karta.goto(BAZA + trasa, { waitUntil: "networkidle" });
  await karta.waitForTimeout(600);
  const pomiar = await karta.evaluate(() => {
    const limit = document.documentElement.clientWidth;
    const winni = [];
    // Element szerszy od ekranu nie jest sam w sobie usterką — tabela w przewijanej
    // poziomo ramce ma tak być. Winowajców wypisujemy dopiero, gdy przewija się strona.
    if (document.documentElement.scrollWidth <= limit + 1) {
      return { szerokosc: document.documentElement.scrollWidth, limit, winni };
    }
    for (const element of document.querySelectorAll("*")) {
      const ramka = element.getBoundingClientRect();
      if (ramka.width <= limit + 1) continue;
      // Interesuje nas najbardziej zewnętrzny winowajca, nie cała gałąź pod nim.
      const rodzic = element.parentElement?.getBoundingClientRect();
      if (rodzic && rodzic.width > limit + 1) continue;
      const klasa = String(element.className).split(" ")[0] || "";
      const tekst = (element.textContent || "").trim().slice(0, 40);
      winni.push(`${element.tagName.toLowerCase()}.${klasa} (${Math.round(ramka.width)}px) „${tekst}”`);
    }
    return { szerokosc: document.documentElement.scrollWidth, limit, winni: winni.slice(0, 4) };
  });
  const przelew = pomiar.szerokosc > pomiar.limit + 1;
  if (przelew) przelewy += 1;
  const stan = przelew ? `PRZELEW ${pomiar.szerokosc}px (ekran ${pomiar.limit}px)` : "ok";
  const szczegoly = pomiar.winni.length ? ` :: ${pomiar.winni.join(" | ")}` : "";
  console.log(`${trasa.padEnd(24)} ${stan}${szczegoly}`);
}

await przegladarka.close();
console.log(przelewy ? `\nTras z przelewem: ${przelewy}.` : "\nŻadna trasa się nie przelewa.");
process.exit(przelewy ? 1 : 0);
