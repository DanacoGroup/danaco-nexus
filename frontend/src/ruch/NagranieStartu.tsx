// Odtwarzacz nagrań z pakietu motion/start.
//
// Pakiet powstał pod konkretne momenty aplikacji — uruchomienie, logowanie, myślenie,
// sukces, błąd, brak połączenia, instalację, wylogowanie — i do czasu tej zmiany żaden
// z nich nie był podpięty: okno pokazywało puste tło tam, gdzie miał być ruch.

import { useEffect, useRef } from "react";
import { START } from "../media/katalog";

/** Identyfikator nagrania startowego — typ pilnuje, że nazwa istnieje w katalogu. */
export type IdStartu = (typeof START)[number]["id"];

const WEDLUG_ID = new Map(START.map((pozycja) => [pozycja.id, pozycja.zrodla]));

export function zrodlaStartu(id: IdStartu) {
  return WEDLUG_ID.get(id) ?? null;
}

/** Momenty, które pakiet ruchu wydał także bez wypalonego podpisu (wariant `-alfa`).
 *
 * Nagrania mają na sobie planszę opisową („Intro znaku · 2200 ms”) — to podpis
 * z demonstracji dla zespołu, a nie element produktu; na produkcji nie ma czego szukać
 * na ekranie użytkownika. Ujęcie `-alfa` jest tym samym ruchem bez podpisu i
 * z przezroczystym tłem. Wykaz jest wypisany, a nie zgadywany ze ścieżki: pozostałe
 * momenty wariantu nie mają i próba pobrania go kończyłaby się błędem przy każdym
 * uruchomieniu okna.
 */
export const BEZ_PODPISU = new Set([
  "intro-znaku",
  "moment-blad",
  "moment-brak-polaczenia",
  "moment-mysli",
  "moment-sukces",
  "moment-wylogowanie",
]);

function zrodloBezPodpisu(nazwa: IdStartu, zrodla: { webm?: string }): string | null {
  if (!BEZ_PODPISU.has(nazwa) || !zrodla.webm) return null;
  return zrodla.webm.replace(/\.webm$/, "-alfa.webm");
}

/** Czy przeglądarka prosi o ograniczenie ruchu. */
export function ograniczonyRuch(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export interface NagranieStartuProps {
  nazwa: IdStartu;
  /** Nagranie chodzi w pętli (tło, stan oczekiwania) zamiast zagrać raz. */
  petla?: boolean;
  /** Wywoływane po jednorazowym odtworzeniu; z `petla` nie zadziała. */
  onKoniec?: () => void;
  className?: string;
}

/** Nagranie startowe jako warstwa dekoracyjna; przy ograniczonym ruchu nic nie rysuje. */
export function NagranieStartu({ nazwa, petla = false, onKoniec, className = "" }: NagranieStartuProps) {
  const wideo = useRef<HTMLVideoElement>(null);
  const zrodla = zrodlaStartu(nazwa);

  useEffect(() => {
    const element = wideo.current;
    if (!element) return;
    void Promise.resolve(element.play()).catch(() => onKoniec?.());
  }, [nazwa, onKoniec]);

  if (!zrodla || ograniczonyRuch()) return null;
  const bezPodpisu = zrodloBezPodpisu(nazwa, zrodla);
  return (
    <video
      ref={wideo}
      key={nazwa}
      className={className}
      muted
      playsInline
      loop={petla}
      preload="auto"
      aria-hidden="true"
      onEnded={petla ? undefined : onKoniec}
      onError={() => onKoniec?.()}
    >
      {bezPodpisu && <source src={bezPodpisu} type="video/webm" />}
      {zrodla.webm && <source src={zrodla.webm} type="video/webm" />}
      {zrodla.mp4 && <source src={zrodla.mp4} type="video/mp4" />}
    </video>
  );
}
