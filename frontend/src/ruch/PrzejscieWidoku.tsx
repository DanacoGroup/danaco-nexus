// Przejście między widokami (motion/MOTION_GUIDELINES.md, rozdz. 13).

import { useEffect, useRef, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
import { useReducedMotion } from "../ui/useReducedMotion";

/** Nazwa migawki podmienianego obszaru. Korzeń traci nazwę na czas przejścia (`wejscia.css`). */
const NAZWA_OBSZARU = "ruch-widok";

export interface PrzejscieWidokuProps {
  klucz: string;
  children: ReactNode;
  className?: string;
  /** Klasa wewnętrznej warstwy; potrzebna tam, gdzie łańcuch `flex` musi przejść dalej. */
  klasaWnetrza?: string;
  id?: string;
  tabIndex?: number;
}

export function PrzejscieWidoku({
  klucz,
  children,
  className = "",
  klasaWnetrza = "",
  id,
  tabIndex,
}: PrzejscieWidokuProps) {
  const ograniczony = useReducedMotion();
  const [widok, setWidok] = useState({ klucz, tresc: children });
  const obszar = useRef<HTMLDivElement>(null);
  const poprzedni = useRef(klucz);

  useEffect(() => {
    if (poprzedni.current === klucz) {
      setWidok({ klucz, tresc: children });
      return;
    }
    poprzedni.current = klucz;
    const cel = obszar.current;
    if (ograniczony || !cel || typeof document.startViewTransition !== "function") {
      setWidok({ klucz, tresc: children });
      return;
    }
    // Migawkę bierze sam podmieniany obszar. Korzeń dostaje `view-transition-name: none`,
    // więc reszta strony — w tym odtwarzane nagranie obok — zostaje poza przejściem.
    // Znacznik i nazwa idą prosto na węzeł: żyją dokładnie tyle, co przebieg przejścia,
    // i nie zależą od tego, kiedy React zdąży oddać kolejną klatkę.
    document.documentElement.classList.add("ruch-przejscie");
    cel.style.setProperty("view-transition-name", NAZWA_OBSZARU);
    cel.dataset.przejscie = "true";
    // Podmiana musi trafić do drzewa w trakcie wywołania zwrotnego, inaczej oba zrzuty
    // przeglądarki są takie same i przejścia nie widać.
    const przebieg = document.startViewTransition(() =>
      flushSync(() => setWidok({ klucz, tresc: children })),
    );
    void przebieg.finished
      .catch(() => undefined)
      .then(() => {
        document.documentElement.classList.remove("ruch-przejscie");
        cel.style.removeProperty("view-transition-name");
        delete cel.dataset.przejscie;
      });
  }, [children, klucz, ograniczony]);

  return (
    <div ref={obszar} id={id} tabIndex={tabIndex} className={`ruch-widok ${className}`}>
      {/* Wejście zastępcze `.ui-widok` gra tylko wtedy, gdy przejścia widoków nie ma —
          inaczej ten sam ruch szedłby dwa razy. */}
      <div key={widok.klucz} className={`ui-widok ${klasaWnetrza}`}>
        {widok.tresc}
      </div>
    </div>
  );
}
