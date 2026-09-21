// Tło rozszerzenia (service worker): ikona na pasku, skróty, menu kontekstowe, zrzut karty.
//
// Każde API spoza podstawy jest sprawdzane przed użyciem – w przeglądarkach z niepełnym
// API rozszerzeń (Danaco Lynx) panel działa wtedy z przycisku i skrótu na stronie.

import type { AkcjaMenu, DoTla, Mozliwosci, TloDoTresci, WynikSzybkiejAkcji } from "./wspolne/komunikaty";
import { wczytaj } from "./wspolne/ustawienia";
import { przeladujSkrypt } from "./wspolne/zakres";

const MENU: Array<{ id: AkcjaMenu["akcja"]; tytul: string; konteksty: string[] }> = [
  { id: "zapytaj", tytul: "Zapytaj Nexusa o zaznaczenie", konteksty: ["selection"] },
  { id: "przetlumacz", tytul: "Przetłumacz w Nexusie", konteksty: ["selection"] },
  { id: "odpowiedz", tytul: "Odpowiedz z Nexusem", konteksty: ["selection", "editable"] },
  { id: "stresc", tytul: "Streść stronę w Nexusie", konteksty: ["page"] },
];

/** Akcje z menu czekające, aż panel w danej karcie je odbierze. */
const oczekujace = new Map<number, AkcjaMenu>();

function mozliwosci(): Mozliwosci {
  return {
    zrzut: typeof chrome.tabs?.captureVisibleTab === "function",
    menu: !!chrome.contextMenus?.create,
    skroty: !!chrome.commands?.onCommand,
    opcje: typeof chrome.runtime?.openOptionsPage === "function",
  };
}

async function doKarty(kartaId: number, komunikat: TloDoTresci): Promise<void> {
  try {
    await chrome.tabs.sendMessage(kartaId, komunikat);
  } catch {
    // Karta otwarta przed instalacją rozszerzenia – wstrzyknięcie skryptu, jeśli wolno.
    if (!chrome.scripting?.executeScript) return;
    try {
      await chrome.scripting.executeScript({ target: { tabId: kartaId }, files: ["tresc.js"] });
      await new Promise((gotowe) => setTimeout(gotowe, 150));
      await chrome.tabs.sendMessage(kartaId, komunikat);
    } catch {
      // Strona zastrzeżona (chrome://, sklep rozszerzeń) – panel nie może się tam pojawić.
    }
  }
}

function utworzMenu(): void {
  if (!chrome.contextMenus?.create) return;
  chrome.contextMenus.removeAll(() => {
    for (const pozycja of MENU) {
      const contexts = pozycja.konteksty as unknown as chrome.contextMenus.CreateProperties["contexts"];
      chrome.contextMenus.create({ id: pozycja.id, title: pozycja.tytul, contexts });
    }
  });
}

try {
  chrome.runtime.onInstalled?.addListener(utworzMenu);
  chrome.runtime.onStartup?.addListener(utworzMenu);
} catch {
  // brak zdarzeń cyklu życia
}

// Skrypt treści chodzi tylko tam, gdzie użytkownik na to pozwolił. Rejestrację
// odświeżamy przy starcie i po każdej zmianie zgód — także wtedy, gdy zgoda zostanie
// cofnięta w ustawieniach przeglądarki, o czym rozszerzenie nie jest pytane.
void przeladujSkrypt();
try {
  chrome.permissions?.onAdded?.addListener(() => void przeladujSkrypt());
  chrome.permissions?.onRemoved?.addListener(() => void przeladujSkrypt());
} catch {
  // brak zdarzeń uprawnień
}

/** Wykonuje szybką akcję przybornika na serwerze Nexusa.
 *
 * Bez klucza urządzenia nie ma czym się uwierzytelnić — wtedy zamiast błędu HTTP
 * użytkownik dostaje zdanie o tym, co ma zrobić, bo to najczęstsza przyczyna odmowy.
 */
async function szybkaAkcja(
  komunikat: Extract<DoTla, { type: "nexus-ext:szybka-akcja" }>,
): Promise<WynikSzybkiejAkcji> {
  const ustawienia = await wczytaj();
  if (!ustawienia.klucz) {
    return { blad: "Najpierw wpisz klucz urządzenia w opcjach rozszerzenia." };
  }
  let odpowiedz: Response;
  try {
    odpowiedz = await fetch(`${ustawienia.serwer}/api/rozszerzenie/szybka-akcja`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${ustawienia.klucz}` },
      body: JSON.stringify({
        polecenie: komunikat.polecenie,
        tekst: komunikat.tekst,
        adres: komunikat.adres,
      }),
    });
  } catch {
    return { blad: "Brak połączenia z Nexusem." };
  }
  if (!odpowiedz.ok) {
    const tresc = (await odpowiedz.json().catch(() => null)) as { detail?: string } | null;
    return { blad: tresc?.detail || `Nexus odmówił (${odpowiedz.status}).` };
  }
  const dane = (await odpowiedz.json()) as { wynik?: string };
  return dane.wynik ? { wynik: dane.wynik } : { blad: "Nexus nie zwrócił treści." };
}

/** Zapamiętuje akcję dla karty i otwiera w niej panel (panel pobierze akcję z tła). */
async function zlecAkcje(kartaId: number, akcja: AkcjaMenu): Promise<void> {
  oczekujace.set(kartaId, { ...akcja, tekst: akcja.tekst.slice(0, 24000) });
  await doKarty(kartaId, { type: "nexus-ext:otworz" });
}

// Dostępne tylko w kontekście tła rozszerzenia – dla testów end-to-end (menu kontekstowe
// przeglądarki nie da się kliknąć z Playwrighta).
(globalThis as unknown as { nexusZlecAkcje?: typeof zlecAkcje }).nexusZlecAkcje = zlecAkcje;

try {
  chrome.contextMenus?.onClicked.addListener((info, karta) => {
    if (karta?.id === undefined || karta.id < 0) return;
    void zlecAkcje(karta.id, {
      akcja: info.menuItemId as AkcjaMenu["akcja"],
      tekst: info.selectionText ?? "",
      tytul: karta.title ?? "",
      adres: info.pageUrl ?? karta.url ?? "",
    });
  });
} catch {
  // brak menu kontekstowego
}

try {
  chrome.action?.onClicked.addListener((karta) => {
    if (karta.id !== undefined) void doKarty(karta.id, { type: "nexus-ext:przelacz" });
  });
} catch {
  // brak ikony na pasku
}

try {
  chrome.commands?.onCommand.addListener((polecenie, karta) => {
    if (!polecenie.startsWith("przelacz-panel")) return;
    const zKarta = (id?: number) => id !== undefined && void doKarty(id, { type: "nexus-ext:przelacz" });
    if (karta?.id !== undefined) zKarta(karta.id);
    else chrome.tabs.query({ active: true, currentWindow: true }, (karty) => zKarta(karty[0]?.id));
  });
} catch {
  // brak skrótów przeglądarki – skrót obsługuje skrypt treści
}

chrome.runtime.onMessage.addListener((komunikat: DoTla, nadawca, odpowiedz) => {
  const karta = nadawca.tab;
  // Komunikaty przyjmujemy wyłącznie od własnych stron i skryptów rozszerzenia.
  if (nadawca.id !== chrome.runtime.id) return false;
  switch (komunikat?.type) {
    case "nexus-ext:mozliwosci":
      odpowiedz(mozliwosci());
      return false;
    case "nexus-ext:oczekujace": {
      const akcja = karta?.id !== undefined ? oczekujace.get(karta.id) : undefined;
      if (karta?.id !== undefined) oczekujace.delete(karta.id);
      odpowiedz(akcja ?? null);
      return false;
    }
    case "nexus-ext:opcje":
      if (chrome.runtime.openOptionsPage) void chrome.runtime.openOptionsPage();
      odpowiedz(!!chrome.runtime.openOptionsPage);
      return false;
    case "nexus-ext:szybka-akcja":
      // Klucz urządzenia zna wyłącznie tło; skrypt treści nigdy go nie widzi, więc
      // żądanie do Nexusa składamy tutaj, a do strony wraca sama treść odpowiedzi.
      szybkaAkcja(komunikat)
        .then(odpowiedz)
        .catch((blad: unknown) => odpowiedz({ blad: String((blad as Error)?.message ?? blad) }));
      return true;
    case "nexus-ext:zrzut":
      if (!mozliwosci().zrzut || !karta) {
        odpowiedz({ ok: false, blad: "Ta przeglądarka nie udostępnia zrzutów karty." });
        return false;
      }
      chrome.tabs
        .captureVisibleTab(karta.windowId, { format: "jpeg", quality: 72 })
        .then((obraz) => odpowiedz({ ok: true, obraz }))
        .catch((blad: unknown) => odpowiedz({ ok: false, blad: String((blad as Error)?.message ?? blad) }));
      return true;
    default:
      return false;
  }
});
