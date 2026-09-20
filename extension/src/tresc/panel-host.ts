// Wstrzykiwany panel boczny: pływający przycisk przy prawej krawędzi i wysuwany panel
// z ramką strony rozszerzenia (panel.html). Wszystko w zamkniętym Shadow DOM – style
// strony nie wpływają na panel, a skrypty strony nie sięgną do jego elementów.
//
// Nie korzysta z chrome.sidePanel (brak w Danaco Lynx i starszych przeglądarkach).

import { TYP_PORTU } from "../wspolne/komunikaty";
import { logo } from "../wspolne/ikony";
import { HOST_PANELU } from "./ekstraktor";

const STYL = `
:host { all: initial; }
.przycisk {
  position: fixed; right: 0; top: var(--nx-gora, 62%); z-index: 2147483646;
  /* Barwy wpisane wprost: ten arkusz trafia do drzewa cienia obcej strony, bez zmiennych aplikacji.
     Wartości odpowiadają rolom z design-tokens: app, line, hover, accent i barwie marki Iris. */
  width: 40px; height: 44px; padding: 0 0 0 8px; border: 1px solid #292C37; border-right: 0;
  border-radius: 12px 0 0 12px; background: #0D0F17; box-shadow: 0 4px 18px rgba(0,0,0,.28);
  display: flex; align-items: center; cursor: pointer; transform: translateX(10px);
  transition: transform .15s ease, background .15s ease; touch-action: none;
}
.przycisk:hover, .przycisk:focus-visible { transform: translateX(0); background: #292C37; outline: none; }
.przycisk:focus-visible { box-shadow: 0 0 0 2px #A298FE; }
.przycisk[hidden] { display: none; }
.panel {
  position: fixed; top: 0; right: 0; bottom: 0; z-index: 2147483647;
  width: var(--nx-szerokosc, 420px); max-width: 100vw; background: #0D0F17;
  border-left: 1px solid #292C37; box-shadow: -8px 0 32px rgba(0,0,0,.35);
  transform: translateX(105%); transition: transform .2s ease; visibility: hidden;
}
.panel.otwarty { transform: translateX(0); visibility: visible; }
.panel.ukryty-na-chwile { visibility: hidden !important; transition: none; }
.uchwyt { position: absolute; left: -4px; top: 0; bottom: 0; width: 8px; cursor: ew-resize; z-index: 1; }
.uchwyt:hover, .uchwyt.aktywny { background: linear-gradient(90deg, transparent 3px, #7B5CFF 3px, #7B5CFF 5px, transparent 5px); }
iframe { border: 0; width: 100%; height: 100%; display: block; color-scheme: normal; }
.oslona { position: fixed; inset: 0; z-index: 2147483647; cursor: ew-resize; display: none; }
.oslona.aktywna { display: block; }
.podswietlenie {
  position: fixed; z-index: 2147483645; pointer-events: none; border: 2px solid #7B5CFF;
  border-radius: 8px; background: rgba(123,92,255,.10); display: none; transition: all .12s ease;
}
@media (prefers-reduced-motion: reduce) { .panel, .przycisk, .podswietlenie { transition: none; } }
@media print { .przycisk, .panel, .podswietlenie { display: none !important; } }
`;

export interface OpcjePanelu {
  szerokosc: number;
  przycisk: boolean;
  /** Adres strony panelu (chrome.runtime.getURL("panel.html")). */
  adresPanelu: string;
  /** Nowy port do panelu (po każdym załadowaniu ramki). */
  naPort: (port: MessagePort) => void;
  naSzerokosc: (szerokosc: number) => void;
  naOtwarcie?: (otwarty: boolean) => void;
}

function losowyKlucz(): string {
  const bajty = new Uint8Array(18);
  crypto.getRandomValues(bajty);
  return Array.from(bajty, (b) => b.toString(16).padStart(2, "0")).join("");
}

export class PanelHost {
  readonly host: HTMLElement;
  private readonly cien: ShadowRoot;
  private readonly przycisk: HTMLButtonElement;
  private readonly panel: HTMLDivElement;
  private readonly oslona: HTMLDivElement;
  private readonly ramkaPodswietlenia: HTMLDivElement;
  private ramka: HTMLIFrameElement | null = null;
  private otwarty = false;
  private ostatniePrzelaczenie = 0;
  private odtworzenia: number[] = [];

  constructor(
    private readonly doc: Document,
    private readonly opcje: OpcjePanelu,
  ) {
    this.host = doc.createElement(HOST_PANELU);
    this.cien = this.host.attachShadow({ mode: "closed" });
    const styl = doc.createElement("style");
    styl.textContent = STYL;
    this.przycisk = doc.createElement("button");
    this.przycisk.className = "przycisk";
    this.przycisk.type = "button";
    this.przycisk.title = "Danaco Nexus (Alt+N)";
    this.przycisk.setAttribute("aria-label", "Otwórz panel Danaco Nexus");
    this.przycisk.innerHTML = logo(24);
    this.przycisk.hidden = !opcje.przycisk;
    this.panel = doc.createElement("div");
    this.panel.className = "panel";
    this.panel.setAttribute("role", "complementary");
    this.panel.setAttribute("aria-label", "Danaco Nexus");
    const uchwyt = doc.createElement("div");
    uchwyt.className = "uchwyt";
    uchwyt.title = "Przeciągnij, aby zmienić szerokość";
    this.panel.append(uchwyt);
    this.oslona = doc.createElement("div");
    this.oslona.className = "oslona";
    this.ramkaPodswietlenia = doc.createElement("div");
    this.ramkaPodswietlenia.className = "podswietlenie";
    this.cien.append(styl, this.ramkaPodswietlenia, this.przycisk, this.panel, this.oslona);
    this.ustawSzerokosc(opcje.szerokosc);
    this.podlaczPrzycisk();
    this.podlaczUchwyt(uchwyt);
  }

  zamontuj(): void {
    // Poza <body>: aplikacje stron (React, Vue) nie usuną panelu przy przerysowaniu.
    if (!this.host.isConnected) this.doc.documentElement.append(this.host);
  }

  get czyOtwarty(): boolean {
    return this.otwarty;
  }

  otworz(): void {
    if (!this.ramka) this.utworzRamke();
    this.otwarty = true;
    this.panel.classList.add("otwarty");
    this.przycisk.setAttribute("aria-expanded", "true");
    this.opcje.naOtwarcie?.(true);
    // Fokus do panelu, aby Escape i skróty działały od razu.
    setTimeout(() => this.ramka?.focus(), 220);
  }

  zamknij(): void {
    this.otwarty = false;
    this.panel.classList.remove("otwarty");
    this.przycisk.setAttribute("aria-expanded", "false");
    this.podswietl(null);
    this.opcje.naOtwarcie?.(false);
  }

  /** Przełącza panel; ignoruje podwójne wywołanie (skrót przeglądarki + skrót strony). */
  przelacz(): void {
    const teraz = Date.now();
    if (teraz - this.ostatniePrzelaczenie < 300) return;
    this.ostatniePrzelaczenie = teraz;
    if (this.otwarty) this.zamknij();
    else this.otworz();
  }

  ustawSzerokosc(szerokosc: number): void {
    this.panel.style.setProperty("--nx-szerokosc", `${Math.round(szerokosc)}px`);
  }

  ustawPrzycisk(widoczny: boolean): void {
    this.przycisk.hidden = !widoczny;
  }

  /** Ukrywa panel na czas zrzutu ekranu (bez animacji). */
  async ukryjNaChwile(): Promise<void> {
    this.panel.classList.add("ukryty-na-chwile");
    this.przycisk.style.visibility = "hidden";
    this.ramkaPodswietlenia.style.display = "none";
    await new Promise<void>((gotowe) => requestAnimationFrame(() => requestAnimationFrame(() => gotowe())));
  }

  pokaz(): void {
    this.panel.classList.remove("ukryty-na-chwile");
    this.przycisk.style.visibility = "";
  }

  /** Obrys elementu strony (np. opinii wskazanej na liście w panelu). */
  podswietl(el: Element | null): void {
    const ramka = this.ramkaPodswietlenia;
    if (!el || !el.isConnected) {
      ramka.style.display = "none";
      return;
    }
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    const rysuj = () => {
      const r = el.getBoundingClientRect();
      Object.assign(ramka.style, {
        display: "block",
        left: `${r.left - 4}px`,
        top: `${r.top - 4}px`,
        width: `${r.width + 8}px`,
        height: `${r.height + 8}px`,
      });
    };
    rysuj();
    setTimeout(rysuj, 350);
  }

  private utworzRamke(): void {
    this.ramka?.remove();
    const klucz = losowyKlucz();
    const ramka = this.doc.createElement("iframe");
    ramka.src = `${this.opcje.adresPanelu}#k=${klucz}`;
    ramka.title = "Danaco Nexus";
    ramka.setAttribute("allow", "clipboard-write; clipboard-read; microphone");
    let zaladowano = false;
    ramka.addEventListener("load", () => {
      if (zaladowano) {
        // Ponowne załadowanie ramki (np. nawigacja wymuszona przez stronę) –
        // nowa ramka z nowym kluczem zamiast przekazywania portu nieznanej treści.
        this.odtworzRamke();
        return;
      }
      zaladowano = true;
      const kanal = new MessageChannel();
      const pochodzenie = new URL(this.opcje.adresPanelu).origin;
      ramka.contentWindow?.postMessage({ type: TYP_PORTU, klucz }, pochodzenie, [kanal.port2]);
      this.opcje.naPort(kanal.port1);
    });
    this.ramka = ramka;
    this.panel.append(ramka);
  }

  private odtworzRamke(): void {
    const teraz = Date.now();
    this.odtworzenia = this.odtworzenia.filter((t) => teraz - t < 60000);
    if (this.odtworzenia.length >= 5) return;
    this.odtworzenia.push(teraz);
    this.utworzRamke();
  }

  private podlaczPrzycisk(): void {
    let start: { y: number; gora: number } | null = null;
    let przeciagany = false;
    this.przycisk.addEventListener("pointerdown", (e) => {
      start = { y: e.clientY, gora: this.przycisk.getBoundingClientRect().top };
      przeciagany = false;
      this.przycisk.setPointerCapture(e.pointerId);
    });
    this.przycisk.addEventListener("pointermove", (e) => {
      if (!start) return;
      const przesuniecie = e.clientY - start.y;
      if (Math.abs(przesuniecie) > 5) przeciagany = true;
      if (przeciagany) {
        const wysokosc = this.doc.documentElement.clientHeight || 800;
        const gora = Math.min(wysokosc - 48, Math.max(8, start.gora + przesuniecie));
        this.przycisk.style.setProperty("--nx-gora", `${gora}px`);
      }
    });
    this.przycisk.addEventListener("pointerup", () => {
      start = null;
    });
    this.przycisk.addEventListener("click", () => {
      if (przeciagany) {
        przeciagany = false;
        return;
      }
      this.przelacz();
    });
  }

  private podlaczUchwyt(uchwyt: HTMLElement): void {
    let aktywny = false;
    uchwyt.addEventListener("pointerdown", (e) => {
      aktywny = true;
      uchwyt.classList.add("aktywny");
      // Osłona nad ramką, żeby ruch myszy nie ginął w iframe.
      this.oslona.classList.add("aktywna");
      e.preventDefault();
    });
    this.oslona.addEventListener("pointermove", (e) => {
      if (!aktywny) return;
      const szerokosc = Math.min(900, Math.max(320, (this.doc.documentElement.clientWidth || 1200) - e.clientX));
      this.ustawSzerokosc(szerokosc);
    });
    const koniec = (e: PointerEvent) => {
      if (!aktywny) return;
      aktywny = false;
      uchwyt.classList.remove("aktywny");
      this.oslona.classList.remove("aktywna");
      const szerokosc = Math.min(900, Math.max(320, (this.doc.documentElement.clientWidth || 1200) - e.clientX));
      this.opcje.naSzerokosc(szerokosc);
    };
    this.oslona.addEventListener("pointerup", koniec);
    this.oslona.addEventListener("pointerleave", koniec);
  }
}
