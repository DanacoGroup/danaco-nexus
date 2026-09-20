// Strona opcji: połączenie z Nexusem (adres + klucz urządzenia) i ustawienia panelu.

import type { Mozliwosci } from "../wspolne/komunikaty";
import { logo } from "../wspolne/ikony";
import { formularzPolaczenia } from "../wspolne/polaczenie";
import { LIMIT_SKROTOW, wczytaj, zapisz, type SkrotPrzybornika } from "../wspolne/ustawienia";

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

/** Rysuje listę skrótów przybornika: nazwa przycisku, treść polecenia, usunięcie.
 *
 * Każda zmiana zapisuje się od razu — to ustawienie, nie formularz z „Zapisz”, więc
 * osobny przycisk zatwierdzania byłby tylko dodatkowym krokiem do zapomnienia.
 */
async function rysujSkroty(): Promise<void> {
  const ustawienia = await wczytaj(true);
  const kontener = $("skroty");
  kontener.replaceChildren();

  const zapiszSkroty = async (skroty: SkrotPrzybornika[]) => {
    await zapisz({ skroty }, true);
    void rysujSkroty();
  };

  for (const [indeks, skrot] of ustawienia.skroty.entries()) {
    const wiersz = document.createElement("div");
    wiersz.className = "wiersz";

    const nazwa = document.createElement("input");
    nazwa.type = "text";
    nazwa.value = skrot.nazwa;
    nazwa.maxLength = 40;
    nazwa.setAttribute("aria-label", "Napis na przycisku");
    nazwa.addEventListener("change", () => {
      const zmienione = [...ustawienia.skroty];
      zmienione[indeks] = { ...skrot, nazwa: nazwa.value };
      void zapiszSkroty(zmienione);
    });

    const polecenie = document.createElement("input");
    polecenie.type = "text";
    polecenie.value = skrot.polecenie;
    polecenie.maxLength = 2000;
    polecenie.setAttribute("aria-label", "Polecenie dla modelu");
    polecenie.addEventListener("change", () => {
      const zmienione = [...ustawienia.skroty];
      zmienione[indeks] = { ...skrot, polecenie: polecenie.value };
      void zapiszSkroty(zmienione);
    });

    const usun = document.createElement("button");
    usun.type = "button";
    usun.className = "link";
    usun.textContent = "usuń";
    usun.setAttribute("aria-label", `Usuń skrót ${skrot.nazwa}`);
    usun.addEventListener("click", () => {
      void zapiszSkroty(ustawienia.skroty.filter((pozycja) => pozycja.id !== skrot.id));
    });

    wiersz.append(nazwa, polecenie, usun);
    kontener.append(wiersz);
  }

  if (!ustawienia.skroty.length) {
    const pusto = document.createElement("p");
    pusto.className = "pomoc";
    pusto.textContent = "Brak skrótów — przybornik się nie pokaże, dopóki nie dodasz pierwszego.";
    kontener.append(pusto);
  }

  const dodaj = $<HTMLButtonElement>("dodaj-skrot");
  dodaj.disabled = ustawienia.skroty.length >= LIMIT_SKROTOW;
  dodaj.onclick = () => {
    if (ustawienia.skroty.length >= LIMIT_SKROTOW) return;
    const nowy: SkrotPrzybornika = {
      id: `skrot-${Date.now().toString(36)}`,
      nazwa: "Nowy skrót",
      polecenie: "Opisz tu, co model ma zrobić z zaznaczonym tekstem.",
    };
    void zapiszSkroty([...ustawienia.skroty, nowy]);
  };
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

  const przybornik = $<HTMLInputElement>("przybornik");
  przybornik.checked = ustawienia.przybornik;
  przybornik.addEventListener("change", () => void zapisz({ przybornik: przybornik.checked }, true));
  await rysujSkroty();

  const m = await mozliwosci();
  const funkcje: Array<[string, boolean | undefined]> = [
    ["Panel boczny, przybornik zaznaczenia, kontekst strony, wstawianie tekstu", true],
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
