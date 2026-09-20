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
      {zrodla.webm && <source src={zrodla.webm} type="video/webm" />}
      {zrodla.mp4 && <source src={zrodla.mp4} type="video/mp4" />}
    </video>
  );
}
