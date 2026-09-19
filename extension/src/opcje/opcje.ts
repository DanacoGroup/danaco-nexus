// Strona opcji: połączenie z Nexusem (adres + klucz urządzenia) i ustawienia panelu.

import type { Mozliwosci } from "../wspolne/komunikaty";
import { logo } from "../wspolne/ikony";
import { formularzPolaczenia } from "../wspolne/polaczenie";
import { wczytaj, zapisz } from "../wspolne/ustawienia";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

async function mozliwosci(): Promise<Mozliwosci | null> {
  try {
    return ((await chrome.runtime.sendMessage({ type: "nexus-ext:mozliwosci" })) as Mozliwosci) ?? null;
  } catch {
    return null;
  }
}

async function rysujUkryte(): Promise<void> {
  const ustawienia = await wczytaj(true);
  const kontener = $("ukryte");
  kontener.replaceChildren();
  if (!ustawienia.ukryteHosty.length) return;
  const opis = document.createElement("p");
  opis.className = "pomoc";
  opis.textContent = "Przycisk ukryty na stronach:";
  const lista = document.createElement("ul");
  for (const host of ustawienia.ukryteHosty) {
    const pozycja = document.createElement("li");
    const przywroc = document.createElement("button");
    przywroc.type = "button";
    przywroc.className = "link";
    przywroc.textContent = "pokaż";
    przywroc.addEventListener("click", async () => {
      await zapisz({ ukryteHosty: ustawienia.ukryteHosty.filter((h) => h !== host) }, true);
      void rysujUkryte();
    });
    pozycja.append(`${host} – `, przywroc);
    lista.append(pozycja);
  }
  kontener.append(opis, lista);
}

async function start(): Promise<void> {
  $("znak").innerHTML = logo(28);
  try {
    $("wersja").textContent = `Wersja rozszerzenia ${chrome.runtime.getManifest().version}`;
  } catch {
    $("wersja").textContent = "";
  }
  await formularzPolaczenia($("polaczenie"), () => undefined);

  const ustawienia = await wczytaj(true);
  const przycisk = $<HTMLInputElement>("przycisk");
  przycisk.checked = ustawienia.przycisk;
  przycisk.addEventListener("change", () => void zapisz({ przycisk: przycisk.checked }, true));
  await rysujUkryte();

  const m = await mozliwosci();
  const funkcje: Array<[string, boolean | undefined]> = [
    ["Panel boczny, kontekst strony, szybkie akcje, wstawianie tekstu", true],
    ["Zrzut widocznej karty (chrome.tabs.captureVisibleTab)", m?.zrzut],
    ["Menu kontekstowe (chrome.contextMenus)", m?.menu],
    ["Skróty przeglądarki (chrome.commands) – skrót na stronie działa zawsze", m?.skroty],
  ];
  const lista = $("funkcje");
  for (const [nazwa, dostepna] of funkcje) {
    const pozycja = document.createElement("li");
    pozycja.textContent = `${dostepna ? "dostępne" : "niedostępne"} – ${nazwa}`;
    lista.append(pozycja);
  }
}

void start();
