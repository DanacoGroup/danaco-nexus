// Kaskada wejścia i jedyny zaczep widoczności warstwy ruchu.

import { useEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

export function kaskada(indeks: number): CSSProperties {
  return {
    "--ui-opoznienie": `calc(var(--stagger-step) * min(${indeks}, var(--stagger-max)))`,
  } as CSSProperties;
}

export interface OpcjeWidocznosci {
  /** Margines pola widzenia. */
  margines?: string;
  /** Wartość wraca do `false` po zejściu z ekranu — dla pętli ozdobnych (WCAG 2.2.2). */
  ciagla?: boolean;
}

/** Czy element wszedł w pole widzenia. Próg zerowy, więc pojemnik wyższy od okna też się odsłania. */
export function useWidocznosc<T extends Element>({
  margines = "0px",
  ciagla = false,
}: OpcjeWidocznosci = {}): [RefObject<T | null>, boolean] {
  const [widoczne, setWidoczne] = useState(typeof IntersectionObserver === "undefined");
  const wezel = useRef<T | null>(null);
  const przepnij = useRef<((cel: T | null) => void) | null>(null);
  const uchwyt = useRef<RefObject<T | null> | null>(null);

  // Uchwyt zachowuje się jak zwykły `ref` (czytelny `.current`), ale każde podstawienie węzła
  // od razu przepina obserwatora. Bez tego przemontowanie poddrzewa — np. przez
  // `PrzejscieWidoku` — zostawiało obserwatora na odłączonym elemencie i treść z klasą
  // `ui-ujawnij` nie odsłaniała się już nigdy.
  if (uchwyt.current === null) {
    uchwyt.current = {
      get current() {
        return wezel.current;
      },
      set current(cel: T | null) {
        if (wezel.current === cel) return;
        wezel.current = cel;
        przepnij.current?.(cel);
      },
    };
  }

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") {
      setWidoczne(true);
      return;
    }
    const obserwator = new IntersectionObserver(
      ([wpis]) => {
        if (ciagla) {
          setWidoczne(wpis.isIntersecting);
          return;
        }
        if (!wpis.isIntersecting) return;
        setWidoczne(true);
        // Jednorazowe odsłonięcie: dalsze węzły nie mają już czego zgłaszać.
        przepnij.current = null;
        obserwator.disconnect();
      },
      { rootMargin: margines, threshold: 0 },
    );

    przepnij.current = (cel) => {
      obserwator.disconnect();
      if (cel) obserwator.observe(cel);
    };
    przepnij.current(wezel.current);

    return () => {
      przepnij.current = null;
      obserwator.disconnect();
    };
  }, [ciagla, margines]);

  return [uchwyt.current, widoczne];
}
