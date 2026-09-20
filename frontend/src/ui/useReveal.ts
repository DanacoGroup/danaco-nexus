// Wejście przy przewijaniu z kaskadą (motion, rozdz. 5). Bez IntersectionObserver
// i przy ograniczonym ruchu element jest widoczny od razu.

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useReducedMotion } from "./useReducedMotion";

export interface RevealOptions {
  /** Numer w kaskadzie; opóźnienie = min(index, --stagger-max) × --stagger-step. */
  index?: number;
  /** Część elementu widoczna przed pokazaniem, 0–1. */
  threshold?: number;
  /** Powtarzanie przy każdym wejściu w pole widzenia. */
  once?: boolean;
}

export interface RevealResult {
  ref: (element: HTMLElement | null) => void;
  visible: boolean;
  props: { className: string; "data-widoczny": "true" | "false"; style: CSSProperties };
}

const MAKS_KROKOW = 4;

export function useReveal({ index = 0, threshold = 0.15, once = true }: RevealOptions = {}): RevealResult {
  const ograniczony = useReducedMotion();
  const [widoczny, setWidoczny] = useState(false);
  const element = useRef<HTMLElement | null>(null);
  const obserwator = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    const cel = element.current;
    if (!cel) return;
    if (ograniczony || typeof IntersectionObserver === "undefined") {
      setWidoczny(true);
      return;
    }
    const obs = new IntersectionObserver(
      (wpisy) => {
        for (const wpis of wpisy) {
          if (wpis.isIntersecting) {
            setWidoczny(true);
            if (once) obs.unobserve(wpis.target);
          } else if (!once) {
            setWidoczny(false);
          }
        }
      },
      { threshold },
    );
    obs.observe(cel);
    obserwator.current = obs;
    return () => obs.disconnect();
  }, [ograniczony, once, threshold]);

  const ref = (nowy: HTMLElement | null) => {
    if (element.current === nowy) return;
    if (obserwator.current && element.current) obserwator.current.unobserve(element.current);
    element.current = nowy;
    if (nowy && obserwator.current) obserwator.current.observe(nowy);
    if (nowy && (ograniczony || typeof IntersectionObserver === "undefined")) setWidoczny(true);
  };

  const krok = Math.min(index, MAKS_KROKOW);
  return {
    ref,
    visible: widoczny,
    props: {
      className: "ui-ujawnij",
      "data-widoczny": widoczny ? "true" : "false",
      style: krok > 0 ? ({ "--ui-opoznienie": `calc(var(--stagger-step) * ${krok})` } as CSSProperties) : {},
    },
  };
}
