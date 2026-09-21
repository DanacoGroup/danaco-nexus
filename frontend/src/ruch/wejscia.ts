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

/** Odtwarza nagranie tylko wtedy, gdy jest w polu widzenia; poza nim zatrzymuje.
 *
 * Nagranie z `autoplay loop` kręci się przez całą wizytę na stronie — także kilkanaście
 * tysięcy pikseli niżej, gdzie nikt go nie widzi. Procesor dekoduje wtedy obraz, którego
 * nie ma na ekranie, a na telefonie schodzi z tego bateria. Ten hak wiąże odtwarzanie
 * z widocznością: wchodzi w kadr — gra, wychodzi — staje.
 *
 * `wstrzymane` to ręczne zatrzymanie przez oglądającego (WCAG 2.2.2). Ma pierwszeństwo
 * przed widocznością: bez tego przewinięcie nagrania poza kadr i z powrotem wznawiałoby
 * ruch, którego ktoś przed chwilą świadomie nie chciał. Flagę trzeba podać także
 * w `zalezne`, żeby hak przeliczył się po jej zmianie.
 *
 * Bez `IntersectionObserver` (stare przeglądarki, środowisko testowe) pilnuje samego
 * wstrzymania; poza nim nagranie zachowuje się tak, jak zapisano w atrybutach elementu.
 */
export function useOdtwarzajWWidoku(
  wideo: RefObject<HTMLVideoElement | null>,
  zalezne: unknown[] = [],
  wstrzymane = false,
): void {
  useEffect(() => {
    const element = wideo.current;
    if (!element) return;
    if (wstrzymane) {
      element.pause();
      return;
    }
    if (typeof IntersectionObserver !== "function") return;
    const obserwator = new IntersectionObserver(
      (wpisy) => {
        for (const wpis of wpisy) {
          if (wpis.isIntersecting) void Promise.resolve(element.play()).catch(() => undefined);
          else element.pause();
        }
      },
      { threshold: 0.1 },
    );
    obserwator.observe(element);
    return () => obserwator.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, zalezne);
}
