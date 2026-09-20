// Scena produktu w hero: nagranie uruchomienia aplikacji z pakietu ruchu.
//
// Wcześniej stała tu makieta złożona ręcznie z elementów interfejsu. Pakiet motion ma
// gotowe nagranie tego samego ekranu — lepiej dopracowane i w ruchu, więc pokazuje
// produkt, zamiast go opisywać. Makieta zostaje jako zapas: przy ograniczonym ruchu
// w systemie i gdy nagranie się nie wczyta.
//
// Kliknięcie powiększa scenę na pełny ekran — na stronie produktu makieta bez
// powiększenia jest bezużyteczna, bo szczegółów interfejsu nie da się odczytać.

import { useEffect, useRef, useState } from "react";
import { CloseIcon } from "../components/icons";
import { odtworz } from "../modules/mozliwosci/odtwarzanie";
import { HeroMock } from "./HeroMock";

const NAGRANIE = "/ruch/start/uruchomienie-komputer-ciemny";

/** Czy system prosi o ograniczenie ruchu. */
function ograniczonyRuch(): boolean {
  return typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

export function ScenaHero() {
  const [bezRuchu, setBezRuchu] = useState(true);
  const [awaria, setAwaria] = useState(false);
  const [powiekszona, setPowiekszona] = useState(false);
  const wideo = useRef<HTMLVideoElement>(null);

  useEffect(() => setBezRuchu(ograniczonyRuch()), []);

  useEffect(() => {
    if (!powiekszona) return;
    const naKlawisz = (zdarzenie: KeyboardEvent) => {
      if (zdarzenie.key === "Escape") setPowiekszona(false);
    };
    document.addEventListener("keydown", naKlawisz);
    return () => document.removeEventListener("keydown", naKlawisz);
  }, [powiekszona]);

  if (bezRuchu || awaria) return <HeroMock />;

  const film = (klasa: string) => (
    <video
      ref={wideo}
      className={klasa}
      muted
      loop
      playsInline
      autoPlay
      preload="metadata"
      poster={`${NAGRANIE}.png`}
      aria-hidden="true"
      onError={() => setAwaria(true)}
      onLoadedData={(zdarzenie) => odtworz(zdarzenie.currentTarget)}
    >
      <source src={`${NAGRANIE}.webm`} type="video/webm" />
      <source src={`${NAGRANIE}.mp4`} type="video/mp4" />
    </video>
  );

  return (
    <>
      <button
        type="button"
        onClick={() => setPowiekszona(true)}
        aria-label="Powiększ podgląd aplikacji"
        className="group relative mx-auto block w-full max-w-[1040px] cursor-zoom-in overflow-hidden rounded-xl border border-line-strong bg-app shadow-[var(--shadow-floating)] md:rounded-2xl"
      >
        {film("block w-full")}
        <span className="absolute right-4 bottom-4 rounded-full bg-app/85 px-3 py-1.5 text-xs text-fg opacity-0 backdrop-blur transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
          Powiększ
        </span>
      </button>

      {powiekszona && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Podgląd aplikacji"
          className="fixed inset-0 z-50 grid place-items-center bg-scrim p-4 backdrop-blur-sm"
          onClick={() => setPowiekszona(false)}
        >
          <div className="w-full max-w-[min(96vw,1600px)]" onClick={(zdarzenie) => zdarzenie.stopPropagation()}>
            {film("w-full rounded-xl border border-line-strong shadow-[var(--shadow-floating)]")}
          </div>
          <button
            type="button"
            onClick={() => setPowiekszona(false)}
            aria-label="Zamknij podgląd"
            className="absolute top-4 right-4 grid size-11 place-items-center rounded-full bg-raised text-fg transition-colors hover:bg-hover"
          >
            <CloseIcon size={20} />
          </button>
        </div>
      )}
    </>
  );
}
