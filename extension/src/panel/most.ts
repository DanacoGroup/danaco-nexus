// Most do ramki Nexusa (?widok=panel) wg umowy trybu osadzonego.
//
// Rodzic → panel: nexus:auth, nexus:context, nexus:prompt (targetOrigin = adres serwera).
// Panel → rodzic: nexus:ready, nexus:insert, nexus:copy – przyjmowane tylko z tej ramki
// i z pochodzenia serwera.

import type { Kontekst } from "../wspolne/komunikaty";

export type DoNexusa =
  | { type: "nexus:auth"; token: string }
  | { type: "nexus:context"; context: Kontekst }
  | { type: "nexus:prompt"; text: string; send?: boolean };

export interface ZdarzeniaMostu {
  gotowy: () => void;
  wstaw: (tekst: string) => void;
  kopiuj: (tekst: string) => void;
}

const LIMIT_TEKSTU = 100000;

export class MostNexusa {
  private gotowy = false;
  private kolejka: DoNexusa[] = [];

  constructor(
    private readonly okno: Window,
    private readonly ramka: HTMLIFrameElement,
    private readonly serwer: string,
    private readonly klucz: string,
    private readonly zdarzenia: ZdarzeniaMostu,
  ) {
    okno.addEventListener("message", this.naWiadomosc);
  }

  get czyGotowy(): boolean {
    return this.gotowy;
  }

  zamknij(): void {
    this.okno.removeEventListener("message", this.naWiadomosc);
    this.kolejka = [];
  }

  /** Wysyła komunikat (albo kolejkuje do nexus:ready). */
  wyslij(komunikat: DoNexusa): void {
    if (!this.gotowy) {
      this.kolejka.push(komunikat);
      return;
    }
    this.ramka.contentWindow?.postMessage(komunikat, this.serwer);
  }

  private readonly naWiadomosc = (e: MessageEvent): void => {
    if (e.origin !== this.serwer || e.source !== this.ramka.contentWindow) return;
    const dane = e.data as { type?: unknown; text?: unknown } | null;
    if (!dane || typeof dane.type !== "string") return;
    if (dane.type === "nexus:ready") {
      // Każde nexus:ready (także po przeładowaniu ramki) = ponowne przekazanie klucza.
      this.gotowy = true;
      this.ramka.contentWindow?.postMessage({ type: "nexus:auth", token: this.klucz } satisfies DoNexusa, this.serwer);
      const oczekujace = this.kolejka;
      this.kolejka = [];
      for (const komunikat of oczekujace) this.wyslij(komunikat);
      this.zdarzenia.gotowy();
      return;
    }
    const tekst = typeof dane.text === "string" ? dane.text.slice(0, LIMIT_TEKSTU) : "";
    if (dane.type === "nexus:insert" && tekst) this.zdarzenia.wstaw(tekst);
    if (dane.type === "nexus:copy" && tekst) this.zdarzenia.kopiuj(tekst);
  };
}
