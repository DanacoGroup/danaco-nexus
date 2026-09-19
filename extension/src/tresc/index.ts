// Skrypt treści: panel boczny na każdej stronie, kontekst strony, wstawianie odpowiedzi.

import type { DoTresci, TloDoTresci, WynikKontekstu, WynikWstawiania, ZTresci } from "../wspolne/komunikaty";
import { normalizujSerwer, obserwuj, wczytaj, zapisz } from "../wspolne/ustawienia";
import { tytulStrony, trescStrony, wyodrebnij, zaznaczonyTekst, skroc, LIMIT_ZNAKOW, HOST_PANELU } from "./ekstraktor";
import { skrot, znajdzOpinie, type ZnalezionaOpinia } from "./opinie";
import { PanelHost } from "./panel-host";
import { jestSkrotemPanelu } from "./skrot";
import { SledzeniePol, opisPola } from "./wstawianie";

declare global {
  interface Window {
    __danacoNexusRozszerzenie?: boolean;
  }
}

const NAZWY_SERWISOW: Record<string, string> = {
  booking: "Booking.com",
  "booking-partner": "Booking.com – panel partnera",
  "google-maps": "Mapy Google",
  "google-firma": "Profil Firmy w Google",
  gmail: "Gmail",
  outlook: "Outlook",
  poczta: "poczta w przeglądarce",
};

function kontekstStrony(tekst: string): WynikKontekstu["kontekst"] {
  return { kind: "page", title: tytulStrony(document), url: location.href, text: tekst };
}

async function start(): Promise<void> {
  if (window.top !== window || window.__danacoNexusRozszerzenie) return;
  window.__danacoNexusRozszerzenie = true;
  const runtime = globalThis.chrome?.runtime;
  if (!runtime?.getURL) return;

  const ustawienia = await wczytaj(false);
  // Na stronie samego Nexusa panel nie jest potrzebny.
  if (normalizujSerwer(location.origin) === ustawienia.serwer) return;

  const sledzenie = new SledzeniePol(document, (el) => el.tagName.toLowerCase() === HOST_PANELU);
  sledzenie.podlacz();
  let port: MessagePort | null = null;
  let opinie: ZnalezionaOpinia[] = [];
  let czekaNaOczekujace = false;

  const wyslij = (komunikat: ZTresci) => port?.postMessage(komunikat);
  const odpowiedz = (nr: number, dane: unknown) => wyslij({ type: "odpowiedz", nr, dane });

  const przyciskWidoczny = (u = ustawienia) => u.przycisk && !u.ukryteHosty.includes(location.hostname);
  const wyslijStrone = () =>
    wyslij({
      type: "strona",
      host: location.hostname,
      tytul: tytulStrony(document),
      ukrytyPrzycisk: ustawienia.ukryteHosty.includes(location.hostname),
    });

  const panel = new PanelHost(document, {
    szerokosc: ustawienia.szerokosc,
    przycisk: przyciskWidoczny(),
    adresPanelu: runtime.getURL("panel.html"),
    naPort: (nowy) => {
      port?.close();
      port = nowy;
      port.onmessage = (e: MessageEvent<DoTresci>) => void obsluz(e.data);
      const pole = sledzenie.ostatnie();
      wyslijStrone();
      wyslij({ type: "pole", aktywne: !!pole, opis: pole ? opisPola(pole) : "" });
      if (czekaNaOczekujace) {
        czekaNaOczekujace = false;
        wyslij({ type: "sprawdz-oczekujace" });
      }
    },
    naSzerokosc: (szerokosc) => void zapisz({ szerokosc }).catch(() => undefined),
    naOtwarcie: (otwarty) => {
      if (!otwarty) return;
      wyslijStrone();
      wyslij({ type: "otwarto" });
    },
  });
  panel.zamontuj();

  sledzenie.naZmiane((pole) => wyslij({ type: "pole", aktywne: !!pole, opis: pole ? opisPola(pole) : "" }));
  obserwuj((nowe) => {
    Object.assign(ustawienia, nowe);
    panel.ustawPrzycisk(przyciskWidoczny(nowe));
    panel.ustawSzerokosc(nowe.szerokosc);
  });

  // Strony SPA potrafią podmienić <html>/<body> – panel wraca na miejsce.
  new MutationObserver(() => panel.zamontuj()).observe(document.documentElement, { childList: true });

  document.addEventListener(
    "keydown",
    (e) => {
      if (!jestSkrotemPanelu(e)) return;
      e.preventDefault();
      e.stopPropagation();
      panel.przelacz();
    },
    true,
  );

  function kontekst(zakres: string, id?: string): WynikKontekstu {
    if (zakres === "strona") {
      const tresc = trescStrony(document);
      return { ok: !!tresc.tekst, kontekst: kontekstStrony(tresc.tekst), zrodlo: tresc.zrodlo };
    }
    if (zakres === "auto") {
      const tresc = wyodrebnij(document);
      return { ok: !!tresc.tekst, kontekst: kontekstStrony(tresc.tekst), zrodlo: tresc.zrodlo };
    }
    if (zakres === "zaznaczenie") {
      const tekst = zaznaczonyTekst(document);
      if (!tekst) return { ok: false, blad: "Nie zaznaczono tekstu na stronie." };
      return { ok: true, kontekst: kontekstStrony(skroc(tekst, LIMIT_ZNAKOW).tekst), zrodlo: "zaznaczenie" };
    }
    if (zakres === "pole") {
      const pole = sledzenie.ostatnie();
      if (!pole) {
        const tekst = zaznaczonyTekst(document);
        if (tekst) return { ok: true, kontekst: kontekstStrony(tekst), zrodlo: "zaznaczenie" };
        return { ok: false, blad: "Kliknij pole z tekstem albo zaznacz tekst na stronie." };
      }
      let tekst = "";
      if (pole.tagName === "TEXTAREA" || pole.tagName === "INPUT") {
        const { selectionStart: od, selectionEnd: doo, value } = pole as HTMLTextAreaElement;
        if (od !== null && doo !== null && doo > od) tekst = value.slice(od, doo);
      } else {
        const zaznaczenie = document.getSelection();
        if (zaznaczenie && zaznaczenie.rangeCount && pole.contains(zaznaczenie.anchorNode)) tekst = zaznaczenie.toString();
      }
      if (!tekst.trim()) {
        tekst = sledzenie.tresc(pole);
        sledzenie.zastapCalosc(pole);
      }
      if (!tekst.trim()) return { ok: false, blad: "Aktywne pole jest puste." };
      return { ok: true, kontekst: kontekstStrony(skroc(tekst, LIMIT_ZNAKOW).tekst), zrodlo: "pole" };
    }
    if (zakres === "opinia") {
      const opinia = opinie.find((o) => o.id === id);
      if (!opinia || !opinia.element.isConnected) return { ok: false, blad: "Opinia zniknęła ze strony – odśwież listę." };
      if (opinia.pole) sledzenie.ustaw(opinia.pole);
      const naglowek = [
        `Serwis: ${NAZWY_SERWISOW[opinia.serwis] ?? location.hostname}`,
        opinia.autor ? `Autor: ${opinia.autor}` : "",
        opinia.ocena ? `Ocena: ${opinia.ocena}` : "",
        opinia.data ? `Data: ${opinia.data}` : "",
      ].filter(Boolean);
      return {
        ok: true,
        kontekst: {
          kind: "page",
          title: `${opinia.rodzaj === "wiadomosc" ? "Wiadomość" : opinia.rodzaj === "komentarz" ? "Komentarz" : "Opinia"}${
            opinia.autor ? ` – ${opinia.autor}` : ""
          } (${tytulStrony(document)})`,
          url: location.href,
          text: `${naglowek.join("\n")}\n\n${opinia.tekst}`,
        },
        zrodlo: "opinia",
        rodzaj: opinia.rodzaj,
      };
    }
    return { ok: false, blad: "Nieznany zakres kontekstu." };
  }

  async function obsluz(komunikat: DoTresci): Promise<void> {
    switch (komunikat.type) {
      case "kontekst":
        odpowiedz(komunikat.nr, kontekst(komunikat.zakres, komunikat.id));
        break;
      case "opinie":
        opinie = znajdzOpinie(document, location.href);
        odpowiedz(komunikat.nr, opinie.map(skrot));
        break;
      case "wstaw": {
        const pole = sledzenie.ostatnie();
        const ok = sledzenie.wstaw(String(komunikat.tekst ?? ""));
        const wynik: WynikWstawiania = { ok, opis: pole ? opisPola(pole) : undefined };
        odpowiedz(komunikat.nr, wynik);
        break;
      }
      case "podswietl":
        panel.podswietl(komunikat.id ? opinie.find((o) => o.id === komunikat.id)?.element ?? null : null);
        break;
      case "ukryj-na-chwile":
        await panel.ukryjNaChwile();
        odpowiedz(komunikat.nr, true);
        break;
      case "pokaz":
        panel.pokaz();
        break;
      case "zamknij":
        panel.zamknij();
        break;
      case "przelacz":
        panel.przelacz();
        break;
    }
  }

  try {
    runtime.onMessage?.addListener((komunikat: TloDoTresci, _nadawca, odpowiedzTlu) => {
      if (komunikat?.type === "nexus-ext:przelacz") panel.przelacz();
      if (komunikat?.type === "nexus-ext:otworz") {
        // Akcja z menu kontekstowego: panel pobierze ją z tła, gdy będzie gotowy.
        if (port) wyslij({ type: "sprawdz-oczekujace" });
        else czekaNaOczekujace = true;
        panel.otworz();
      }
      odpowiedzTlu({ ok: true });
      return false;
    });
  } catch {
    // Brak chrome.runtime.onMessage (niepełne API) – działa skrót i przycisk.
  }
}

void start();
