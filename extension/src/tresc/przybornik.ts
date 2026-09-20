// Przybornik zaznaczenia: skróty przy kursorze, bez otwierania okna aplikacji.
//
// Panel boczny jest dobry, gdy ktoś chce rozmawiać. Częściej jednak wystarczy jedna
// czynność na zaznaczonym fragmencie: przetłumacz, skróć, popraw, sprawdź kod. Wtedy
// otwieranie czatu jest drogą okrężną — człowiek chce wyniku, nie rozmowy.
//
// Przybornik jest niewidoczny, dopóki nic nie jest zaznaczone. Po zaznaczeniu tekstu
// pojawia się tuż przy nim, pokazuje skróty ustawione przez użytkownika, a wynik
// wraca do banera obok. Kliknięcie gdziekolwiek indziej zamyka wszystko.
//
// Całość mieszka w zamkniętym Shadow DOM: style strony nie wpływają na przybornik,
// a skrypty strony nie sięgną do jego elementów ani do treści odpowiedzi.

import type { SkrotPrzybornika, Ustawienia } from "../wspolne/ustawienia";

/** Najkrótsze zaznaczenie, przy którym przybornik ma sens (poniżej to zwykle klik). */
const MIN_ZNAKOW = 3;
/** Górna granica wysyłanego fragmentu — ta sama, której pilnuje serwer. */
const MAX_ZNAKOW = 20_000;
/** Odstęp przybornika od zaznaczenia, żeby nie zasłaniał tekstu. */
const ODSTEP = 10;

const STYL = `
:host { all: initial; }
.pasek, .baner {
  position: fixed; z-index: 2147483645;
  /* Barwy wpisane wprost: arkusz trafia do drzewa cienia obcej strony, bez zmiennych
     aplikacji. Wartości odpowiadają rolom z design-tokens (app, line, hover, accent). */
  background: #0D0F17; border: 1px solid #292C37; border-radius: 12px;
  box-shadow: 0 8px 28px rgba(0,0,0,.42);
  font: 13px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; color: #E9EAF0;
}
.pasek { display: flex; gap: 2px; padding: 4px; max-width: min(92vw, 640px); flex-wrap: wrap; }
.pasek button {
  all: unset; padding: 6px 10px; border-radius: 8px; cursor: pointer; white-space: nowrap;
  font: inherit; color: #E9EAF0;
}
.pasek button:hover, .pasek button:focus-visible { background: #292C37; outline: none; }
.pasek button:focus-visible { box-shadow: 0 0 0 2px #A298FE inset; }
.baner { max-width: min(92vw, 460px); padding: 12px 14px; display: grid; gap: 10px; }
.tresc { max-height: 42vh; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
.stopka { display: flex; gap: 8px; align-items: center; justify-content: flex-end; }
.stopka button {
  all: unset; padding: 5px 10px; border-radius: 8px; cursor: pointer; font: inherit;
  border: 1px solid #292C37; color: #E9EAF0;
}
.stopka button:hover, .stopka button:focus-visible { background: #292C37; outline: none; }
.stopka .glowny { background: #7B5CFF; border-color: #7B5CFF; color: #fff; }
.stan { color: #9AA0B4; }
.blad { color: #FF8A8A; }
[hidden] { display: none !important; }
`;

interface Polozenie {
  x: number;
  y: number;
}

/** Wynik akcji zwrócony przez serwer albo powód, dla którego go nie ma. */
type Odpowiedz = { wynik: string } | { blad: string };

export interface PrzybornikOpcje {
  /** Wysyła akcję do tła rozszerzenia (ono zna klucz urządzenia, skrypt treści nie). */
  wykonaj: (polecenie: string, tekst: string) => Promise<Odpowiedz>;
}

export class Przybornik {
  private readonly cien: ShadowRoot;
  private readonly pasek: HTMLDivElement;
  private readonly baner: HTMLDivElement;
  private readonly tresc: HTMLDivElement;
  private readonly kopiuj: HTMLButtonElement;
  private skroty: SkrotPrzybornika[] = [];
  private wlaczony = true;
  private zaznaczenie = "";
  private ostatniWynik = "";

  constructor(
    private readonly opcje: PrzybornikOpcje,
    korzen: HTMLElement,
  ) {
    this.cien = korzen.attachShadow({ mode: "closed" });
    const styl = document.createElement("style");
    styl.textContent = STYL;

    this.pasek = document.createElement("div");
    this.pasek.className = "pasek";
    this.pasek.hidden = true;

    this.baner = document.createElement("div");
    this.baner.className = "baner";
    this.baner.hidden = true;
    this.tresc = document.createElement("div");
    this.tresc.className = "tresc";
    const stopka = document.createElement("div");
    stopka.className = "stopka";
    this.kopiuj = document.createElement("button");
    this.kopiuj.className = "glowny";
    this.kopiuj.textContent = "Kopiuj";
    this.kopiuj.addEventListener("click", () => void this.skopiuj());
    const zamknij = document.createElement("button");
    zamknij.textContent = "Zamknij";
    zamknij.addEventListener("click", () => this.schowaj());
    stopka.append(this.kopiuj, zamknij);
    this.baner.append(this.tresc, stopka);

    this.cien.append(styl, this.pasek, this.baner);
    this.nasluchuj();
  }

  /** Przyjmuje bieżące ustawienia; pusty zestaw skrótów wyłącza przybornik. */
  ustaw(ustawienia: Ustawienia): void {
    this.wlaczony = ustawienia.przybornik !== false;
    this.skroty = ustawienia.skroty ?? [];
    if (!this.wlaczony || !this.skroty.length) this.schowaj();
  }

  private nasluchuj(): void {
    // `mouseup` zamiast `selectionchange`: ten drugi sypie zdarzeniami w trakcie
    // przeciągania myszą i przybornik migotałby przy każdym pikselu zaznaczenia.
    document.addEventListener("mouseup", () => window.setTimeout(() => this.sprawdzZaznaczenie(), 0), true);
    document.addEventListener("keyup", (zdarzenie) => {
      // Zaznaczenie klawiaturą (Shift + strzałki, Ctrl+A) też ma otwierać przybornik.
      if (zdarzenie.shiftKey || zdarzenie.key === "a") window.setTimeout(() => this.sprawdzZaznaczenie(), 0);
    }, true);
    document.addEventListener("mousedown", (zdarzenie) => {
      if (!this.cien.contains(zdarzenie.target as Node)) this.schowaj();
    }, true);
    document.addEventListener("keydown", (zdarzenie) => {
      if (zdarzenie.key === "Escape") this.schowaj();
    }, true);
    window.addEventListener("scroll", () => this.schowaj(), { passive: true, capture: true });
  }

  private sprawdzZaznaczenie(): void {
    if (!this.wlaczony || !this.skroty.length) return;
    const zaznaczone = document.getSelection();
    const tekst = (zaznaczone?.toString() ?? "").trim();
    if (tekst.length < MIN_ZNAKOW || !zaznaczone || zaznaczone.rangeCount === 0) {
      if (this.baner.hidden) this.schowaj();
      return;
    }
    const ramka = zaznaczone.getRangeAt(0).getBoundingClientRect();
    if (!ramka.width && !ramka.height) return;
    this.zaznaczenie = tekst.slice(0, MAX_ZNAKOW);
    this.pokazPasek({ x: ramka.left + ramka.width / 2, y: ramka.top });
  }

  private pokazPasek(srodek: Polozenie): void {
    this.baner.hidden = true;
    this.pasek.replaceChildren(
      ...this.skroty.map((skrot) => {
        const przycisk = document.createElement("button");
        przycisk.textContent = skrot.nazwa;
        przycisk.title = skrot.polecenie;
        przycisk.addEventListener("click", () => void this.wykonaj(skrot));
        return przycisk;
      }),
    );
    this.pasek.hidden = false;
    this.ustawPolozenie(this.pasek, srodek);
  }

  /** Umieszcza element nad zaznaczeniem, a przy górnej krawędzi okna — pod nim. */
  private ustawPolozenie(element: HTMLElement, srodek: Polozenie): void {
    element.style.left = "0px";
    element.style.top = "0px";
    const ramka = element.getBoundingClientRect();
    const lewo = Math.min(
      Math.max(ODSTEP, srodek.x - ramka.width / 2),
      Math.max(ODSTEP, window.innerWidth - ramka.width - ODSTEP),
    );
    const nad = srodek.y - ramka.height - ODSTEP;
    element.style.left = `${Math.round(lewo)}px`;
    element.style.top = `${Math.round(nad >= ODSTEP ? nad : srodek.y + ODSTEP)}px`;
  }

  private async wykonaj(skrot: SkrotPrzybornika): Promise<void> {
    const kotwica = this.pasek.getBoundingClientRect();
    const srodek = { x: kotwica.left + kotwica.width / 2, y: kotwica.top };
    this.pasek.hidden = true;
    this.pokazBaner(`${skrot.nazwa}…`, srodek, "stan");
    const odpowiedz = await this.opcje.wykonaj(skrot.polecenie, this.zaznaczenie);
    if ("blad" in odpowiedz) {
      this.pokazBaner(odpowiedz.blad, srodek, "blad");
      return;
    }
    this.ostatniWynik = odpowiedz.wynik;
    this.pokazBaner(odpowiedz.wynik, srodek, "");
  }

  private pokazBaner(tekst: string, srodek: Polozenie, klasa: string): void {
    this.tresc.textContent = tekst;
    this.tresc.className = `tresc ${klasa}`.trim();
    this.kopiuj.hidden = klasa !== "";
    this.baner.hidden = false;
    this.ustawPolozenie(this.baner, srodek);
  }

  private async skopiuj(): Promise<void> {
    if (!this.ostatniWynik) return;
    try {
      await navigator.clipboard.writeText(this.ostatniWynik);
      this.kopiuj.textContent = "Skopiowane";
      window.setTimeout(() => (this.kopiuj.textContent = "Kopiuj"), 1200);
    } catch {
      this.kopiuj.textContent = "Nie udało się";
      window.setTimeout(() => (this.kopiuj.textContent = "Kopiuj"), 1600);
    }
  }

  schowaj(): void {
    this.pasek.hidden = true;
    this.baner.hidden = true;
    this.ostatniWynik = "";
  }
}
