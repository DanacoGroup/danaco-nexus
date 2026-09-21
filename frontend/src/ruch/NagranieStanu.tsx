// Odtwarzacz nagrań z pakietu motion/stany.
//
// Pakiet ma 26 ujęć opisujących stany aplikacji (upuszczanie pliku, pusta rozmowa, brak
// wyników, przesyłanie, synchronizacja). Do tej pory używała ich wyłącznie strona produktu
// i katalog „Możliwości” — w samym oknie te stany były wierszem tekstu na pustym tle.

import { useEffect, useRef } from "react";
import { STANY } from "../media/katalog";
import { ograniczonyRuch } from "../preferencje";

/** Identyfikator nagrania stanu — typ pilnuje, że nazwa istnieje w katalogu. */
export type IdStanu = (typeof STANY)[number]["id"];

const WEDLUG_ID = new Map(STANY.map((pozycja) => [pozycja.id, pozycja.zrodla]));

/** Źródła nagrania stanu. Pakiet wydał stany w samym MP4; pole `webm` zostaje na przyszłość. */
export function zrodlaStanu(id: IdStanu): { mp4?: string; webm?: string } | null {
  return WEDLUG_ID.get(id) ?? null;
}

export interface NagranieStanuProps {
  nazwa: IdStanu;
  /** Pętla ma sens tam, gdzie stan trwa (przeciąganie pliku, pusty ekran). */
  petla?: boolean;
  className?: string;
}

/** Nagranie stanu jako warstwa dekoracyjna; przy ograniczonym ruchu nic nie rysuje. */
export function NagranieStanu({ nazwa, petla = true, className = "" }: NagranieStanuProps) {
  const wideo = useRef<HTMLVideoElement>(null);
  const zrodla = zrodlaStanu(nazwa);

  useEffect(() => {
    const element = wideo.current;
    if (!element) return;
    // Nagranie stanu pojawia się razem ze stanem, więc gra od razu — nie ma tu
    // przewijania, przy którym warto byłoby czekać na pole widzenia.
    void Promise.resolve(element.play()).catch(() => undefined);
  }, [nazwa]);

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
    >
      {zrodla.webm && <source src={zrodla.webm} type="video/webm" />}
      {zrodla.mp4 && <source src={zrodla.mp4} type="video/mp4" />}
    </video>
  );
}
