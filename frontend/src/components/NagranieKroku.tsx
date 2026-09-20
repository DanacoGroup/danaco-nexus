// Nagranie pracującego narzędzia w karcie kroku.
//
// Strona produktu pokazuje przy każdej dziedzinie ujęcie z pakietu motion/stany. Dopóki
// te same ujęcia nie pojawiały się w samej aplikacji, obietnica ze strony była pusta:
// ktoś oglądał ruch w witrynie, wchodził do okna i widział sam wiersz tekstu. Klip leci
// wyłącznie w czasie pracy narzędzia i tylko wtedy, gdy pakiet ma ujęcie dla tego narzędzia.

import { useEffect, useRef } from "react";
import { odtworz } from "../modules/mozliwosci/odtwarzanie";
import { nagranieNarzedzia } from "../modules/mozliwosci/ruch";

/** Czy system prosi o ograniczenie ruchu (ustawienie dostępności przeglądarki). */
function ograniczonyRuch(): boolean {
  if (typeof window.matchMedia !== "function") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function NagranieKroku({ narzedzie }: { narzedzie: string }) {
  const wideo = useRef<HTMLVideoElement>(null);
  const nagranie = nagranieNarzedzia(narzedzie);

  useEffect(() => {
    const element = wideo.current;
    if (element && !ograniczonyRuch()) odtworz(element);
  }, [narzedzie]);

  if (!nagranie || ograniczonyRuch()) return null;
  return (
    <div className="mt-2.5 ml-7 overflow-hidden rounded-xl border border-line/60 bg-app">
      <video
        ref={wideo}
        key={narzedzie}
        className="aspect-video max-h-28 w-full object-cover"
        muted
        loop
        playsInline
        preload="metadata"
        aria-hidden="true"
      >
        {nagranie.webm && <source src={nagranie.webm} type="video/webm" />}
        {nagranie.mp4 && <source src={nagranie.mp4} type="video/mp4" />}
      </video>
    </div>
  );
}
