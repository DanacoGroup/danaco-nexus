// Znak Danaco Nexus w ruchu: jeden komponent na wszystkie momenty stanu aplikacji.
// Geometria z `logo/svg/symbol.svg` (siatka 84 × 84), choreografia z motion/start/README.md.
// Ruch opisuje arkusz `znak.css`; tutaj jest tylko budowa SVG i pilnowanie pola widzenia.

import { useEffect, useId, useRef, useState } from "react";

/** Momenty znaku odpowiadające stanom aplikacji (motion/start/README.md, rozdz. 8). */
export type MomentZnaku =
  | "spoczynek"
  | "uruchomienie"
  | "uruchomienie-krotkie"
  | "logowanie"
  | "mysli"
  | "sukces"
  | "blad"
  | "brak-polaczenia"
  | "wylogowanie"
  | "instalacja";

const LUK = "M23 63V41A19 19 0 0 1 61 41V63";
const POLOWA_LEWA = "M23 63V41A19 19 0 0 1 42 22";
const POLOWA_PRAWA = "M61 63V41A19 19 0 0 0 42 22";

export interface ZnakRuchuProps {
  moment: MomentZnaku;
  /** Bok znaku w pikselach CSS. */
  rozmiar?: number;
  /** Nazwa dostępna; bez niej znak jest ozdobą i znika dla czytnika ekranu. */
  etykieta?: string;
  /** Zmiana wartości odtwarza moment jeszcze raz (np. drugi sukces z rzędu). */
  odtworzenie?: number;
  className?: string;
}

export function ZnakRuchu({ moment, rozmiar = 84, etykieta, odtworzenie = 0, className = "" }: ZnakRuchuProps) {
  const id = useId().replace(/:/g, "");
  const element = useRef<SVGSVGElement>(null);
  const [widoczny, setWidoczny] = useState(true);

  useEffect(() => {
    const cel = element.current;
    if (!cel || typeof IntersectionObserver === "undefined") return;
    const obserwator = new IntersectionObserver((wpisy) => setWidoczny(wpisy.some((wpis) => wpis.isIntersecting)));
    obserwator.observe(cel);
    return () => obserwator.disconnect();
  }, []);

  return (
    <svg
      ref={element}
      key={`${moment}-${odtworzenie}`}
      className={`znak-ruch ${className}`}
      width={rozmiar}
      height={rozmiar}
      viewBox="0 0 84 84"
      data-moment={moment}
      data-widoczny={widoczny ? "true" : "false"}
      role={etykieta ? "img" : undefined}
      aria-hidden={etykieta ? undefined : true}
    >
      {etykieta ? <title>{etykieta}</title> : null}
      <defs>
        <linearGradient id={`${id}-aurora`} gradientUnits="userSpaceOnUse" x1="17" y1="16" x2="67" y2="69">
          <stop offset="0" stopColor="var(--color-brand-apricot)" />
          <stop offset="0.38" stopColor="var(--color-brand-rose)" />
          <stop offset="0.72" stopColor="var(--color-brand-iris)" />
          <stop offset="1" stopColor="var(--color-brand-sky)" />
        </linearGradient>
        <linearGradient id={`${id}-chlodna`} gradientUnits="userSpaceOnUse" x1="-6.5" y1="-6.5" x2="6.5" y2="6.5">
          <stop offset="0" stopColor="var(--color-brand-iris)" />
          <stop offset="1" stopColor="var(--color-brand-sky)" />
        </linearGradient>
        <radialGradient id={`${id}-poswiata`}>
          <stop offset="0" stopColor="var(--color-brand-iris)" stopOpacity="0.75" />
          <stop offset="1" stopColor="var(--color-brand-sky)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <g className="znak-ruch__calosc">
        <circle className="znak-ruch__aura" cx="42" cy="41" r="15" fill={`url(#${id}-poswiata)`} />
        <path className="znak-ruch__luk-szary" d={LUK} stroke="var(--line-strong)" />
        <g className="znak-ruch__luk">
          <path
            className="znak-ruch__polowa znak-ruch__polowa-lewa"
            d={POLOWA_LEWA}
            pathLength={100}
            stroke={`url(#${id}-aurora)`}
          />
          <path
            className="znak-ruch__polowa znak-ruch__polowa-prawa"
            d={POLOWA_PRAWA}
            pathLength={100}
            stroke={`url(#${id}-aurora)`}
          />
        </g>
        <path className="znak-ruch__rozblysk" d={LUK} stroke="var(--color-white)" />
        <path className="znak-ruch__iskra" d={LUK} pathLength={100} stroke="var(--color-white)" />
        <circle className="znak-ruch__punkt" cx="0" cy="0" r="6.5" fill={`url(#${id}-chlodna)`} />
      </g>
    </svg>
  );
}
