// Komunikaty między częściami rozszerzenia.
//
// Skrypt treści ↔ panel (strona rozszerzenia w ramce): prywatny MessagePort przekazany
// raz, z jednorazowym kluczem z adresu ramki. Panel traktuje port jako źródło DANYCH
// (kontekst strony, wynik wstawiania) – nigdy jako polecenie wysłania wiadomości do
// Nexusa; to zlecają wyłącznie kliknięcia w panelu i tło rozszerzenia.
//
// Panel ↔ tło: chrome.runtime.sendMessage (zrzut karty, akcje z menu kontekstowego).
// Panel ↔ Nexus (ramka ?widok=panel): window.postMessage wg umowy „nexus:*”.

/**
 * strona – czytelna treść strony; zaznaczenie – tylko zaznaczony tekst; auto – zaznaczenie
 * albo strona; pole – zaznaczenie w aktywnym polu albo cała jego treść; opinia – wybrana opinia.
 */
export type Zakres = "strona" | "zaznaczenie" | "auto" | "pole" | "opinia";

export interface Kontekst {
  kind: "page" | "screen";
  title: string;
  url: string;
  text: string;
  image?: string;
}

export interface OpiniaSkrot {
  id: string;
  rodzaj: "opinia" | "wiadomosc" | "komentarz";
  serwis: string;
  autor?: string;
  ocena?: string;
  data?: string;
  tekst: string;
  /** Czy przy opinii znaleziono pole odpowiedzi (tam trafi „Wstaw”). */
  poleOdpowiedzi: boolean;
}

/** Panel → skrypt treści. */
export type DoTresci =
  | { type: "kontekst"; nr: number; zakres: Zakres; id?: string }
  | { type: "opinie"; nr: number }
  | { type: "wstaw"; nr: number; tekst: string }
  | { type: "podswietl"; id: string | null }
  | { type: "ukryj-na-chwile"; nr: number }
  | { type: "pokaz" }
  | { type: "zamknij" }
  | { type: "przelacz" };

/** Skrypt treści → panel. */
export type ZTresci =
  | { type: "odpowiedz"; nr: number; dane: unknown }
  | { type: "otwarto" }
  | { type: "strona"; host: string; tytul: string; ukrytyPrzycisk: boolean }
  | { type: "pole"; aktywne: boolean; opis: string }
  | { type: "sprawdz-oczekujace" };

export interface WynikKontekstu {
  ok: boolean;
  kontekst?: Kontekst;
  /** Skąd pochodzi tekst (do opisu w panelu). */
  zrodlo?: "zaznaczenie" | "artykul" | "strona" | "pole" | "opinia";
  rodzaj?: OpiniaSkrot["rodzaj"];
  blad?: string;
}

export interface WynikWstawiania {
  ok: boolean;
  /** Opis pola, do którego wstawiono tekst. */
  opis?: string;
}

/** Akcja zlecona z menu kontekstowego przeglądarki. */
export interface AkcjaMenu {
  akcja: "zapytaj" | "przetlumacz" | "odpowiedz" | "stresc";
  tekst: string;
  tytul: string;
  adres: string;
}

/** Komunikaty chrome.runtime (panel/treść → tło i tło → treść). */
export type DoTla =
  | { type: "nexus-ext:zrzut" }
  | { type: "nexus-ext:oczekujace" }
  | { type: "nexus-ext:opcje" }
  | { type: "nexus-ext:mozliwosci" }
  | { type: "nexus-ext:szybka-akcja"; polecenie: string; tekst: string; adres: string };

/** Odpowiedź na szybką akcję przybornika: sama treść albo zdanie o tym, czego brakuje. */
export type WynikSzybkiejAkcji = { wynik: string } | { blad: string };

export type TloDoTresci = { type: "nexus-ext:przelacz" } | { type: "nexus-ext:otworz" };

export interface Mozliwosci {
  zrzut: boolean;
  menu: boolean;
  skroty: boolean;
  opcje: boolean;
}

export const TYP_PORTU = "nexus-ext:port";
