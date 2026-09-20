// Tła na żywo: warstwa światła pod sekcją, pas świtu między sekcjami, ziarno nad sekcją.
// Pętlę wstrzymuje sam pakiet — poza ekranem, w karcie w tle i przy ograniczonym ruchu.
// Same sceny WebGL wchodzą dopiero za bramkami z landing/LANDING_PAGE_SPEC.md, rozdz. 9 i 11.

import { useEffect, useRef, useState, type CSSProperties } from "react";
import {
  klatkaZastepcza,
  pelneTlo,
  wczytajTlo,
  type NazwaTla,
  type NazwaTlaWebGL,
  type UchwytTla,
} from "./tla";

type Opcje = Record<string, unknown>;

/** Bezczynność wymagana przed montażem hero (spec., rozdz. 9: „po `load` + 1,2 s”). */
const BEZCZYNNOSC_MS = 1200;

const ZAPYTANIA = ["(pointer: fine)", "(prefers-reduced-motion: reduce)"];

/** Warunki pełnego tła śledzone na żywo: zmiana szerokości okna albo motywu je odbiera. */
function useDozwolone(nazwa: NazwaTla): boolean {
  const [dozwolone, setDozwolone] = useState(() => pelneTlo(nazwa));

  useEffect(() => {
    const sprawdz = () => setDozwolone(pelneTlo(nazwa));
    sprawdz();
    if (typeof window.matchMedia !== "function") return;
    const prog = getComputedStyle(document.documentElement).getPropertyValue("--breakpoint-lg").trim();
    const listy = [...ZAPYTANIA, prog && `(min-width: ${prog})`]
      .filter((zapytanie): zapytanie is string => Boolean(zapytanie))
      .map((zapytanie) => window.matchMedia(zapytanie));
    for (const lista of listy) lista.addEventListener("change", sprawdz);
    const motyw = new MutationObserver(sprawdz);
    motyw.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => {
      for (const lista of listy) lista.removeEventListener("change", sprawdz);
      motyw.disconnect();
    };
  }, [nazwa]);

  return dozwolone;
}

// Nie rozszerzamy `Window`: nowsze biblioteki typów mają już `requestIdleCallback`
// jako pole wymagane, a deklaracja opcjonalna jest z nią niezgodna. Wystarczy kształt,
// do którego rzutujemy okno w jednym miejscu.
interface OknoZBezczynnoscia {
  requestIdleCallback?: (wywolanie: () => void, opcje?: { timeout: number }) => number;
  cancelIdleCallback?: (uchwyt: number) => void;
}

/** Odkłada zadanie do zdarzenia `load`, potem do pierwszej bezczynności wątku głównego. */
function poBezczynnosci(zadanie: () => void): () => void {
  const okno = window as unknown as OknoZBezczynnoscia;
  let stoper = 0;
  let praca = 0;
  const odlozone = () => {
    stoper = window.setTimeout(() => {
      if (okno.requestIdleCallback) praca = okno.requestIdleCallback(zadanie, { timeout: BEZCZYNNOSC_MS });
      else zadanie();
    }, BEZCZYNNOSC_MS);
  };
  if (document.readyState === "complete") odlozone();
  else window.addEventListener("load", odlozone, { once: true });
  return () => {
    window.removeEventListener("load", odlozone);
    window.clearTimeout(stoper);
    if (praca) okno.cancelIdleCallback?.(praca);
  };
}

/** Montuje tło, gdy warunki na to pozwalają; sprząta kontekst WebGL przy odmontowaniu. */
function useMontaz(nazwa: NazwaTla, opcje: Opcje | undefined, margines: string, hero = false) {
  const element = useRef<HTMLDivElement>(null);
  const zapis = useRef(opcje);
  zapis.current = opcje;
  const dozwolone = useDozwolone(nazwa);

  useEffect(() => {
    const cel = element.current;
    if (!cel || !dozwolone) return;
    let uchwyt: UchwytTla | null = null;
    let porzucone = false;

    const zamontuj = () => {
      void wczytajTlo(nazwa).then((modul) => {
        if (porzucone || !modul || uchwyt) return;
        uchwyt = modul.mount(cel, zapis.current);
      });
    };

    // Hero odkłada montaż do bezczynności po `load`, żeby nie wchodzić w pomiar LCP.
    // Pozostałe sekcje czekają na zbliżenie do pola widzenia.
    let sprzataj: () => void;
    if (hero) {
      sprzataj = poBezczynnosci(zamontuj);
    } else if (typeof IntersectionObserver === "undefined") {
      zamontuj();
      sprzataj = () => undefined;
    } else {
      const obserwator = new IntersectionObserver(
        (wpisy) => {
          if (!wpisy.some((wpis) => wpis.isIntersecting)) return;
          obserwator.disconnect();
          zamontuj();
        },
        { rootMargin: margines },
      );
      obserwator.observe(cel);
      sprzataj = () => obserwator.disconnect();
    }

    return () => {
      porzucone = true;
      sprzataj();
      uchwyt?.zniszcz();
    };
  }, [dozwolone, hero, margines, nazwa]);

  return element;
}

export interface TloNaZywoProps {
  nazwa: NazwaTlaWebGL;
  opcje?: Opcje;
  /** Tło pierwszego ekranu: montaż po `load` i bezczynności zamiast na wejściu w kadr. */
  hero?: boolean;
  className?: string;
}

/** Warstwa pod treścią sekcji o `position: relative`; płótno wchodzi nad klatką zastępczą. */
export function TloNaZywo({ nazwa, opcje, hero = false, className = "" }: TloNaZywoProps) {
  const element = useMontaz(nazwa, opcje, "200px", hero);
  return (
    <div
      ref={element}
      aria-hidden="true"
      className={`ruch-tlo ${className}`}
      style={klatkaZastepcza(nazwa)}
    />
  );
}

export interface PasSwituProps {
  od?: string;
  do?: string;
  barwa?: "cieply" | "chlodny";
  className?: string;
  style?: CSSProperties;
}

/** Separator „świt”: wschód światła sprzężony z przewijaniem, bez pętli. */
export function PasSwitu({ od, do: doBarwy, barwa = "cieply", className = "", style }: PasSwituProps) {
  const element = useMontaz("swit", { od, do: doBarwy, barwa }, "300px");
  return <div ref={element} aria-hidden="true" className={`ruch-pas ${className}`} style={style} />;
}

/** Ziarno filmowe nad sekcją o `position: relative`. */
export function WarstwaZiarna({
  krycie = 0.06,
  ukryta = false,
  className = "",
}: {
  krycie?: number;
  /** Ziarno gaśnie, gdy w sekcji dzieje się coś, czego nie wolno przykrywać (film). */
  ukryta?: boolean;
  className?: string;
}) {
  const element = useMontaz("ziarno", { krycie }, "200px");
  return (
    <div
      ref={element}
      aria-hidden="true"
      data-ukryta={ukryta ? "true" : "false"}
      className={`ruch-ziarno ${className}`}
    />
  );
}
