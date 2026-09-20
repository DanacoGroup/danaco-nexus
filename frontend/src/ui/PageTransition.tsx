// Przejście między widokami (motion, rozdz. 13): stara treść gaśnie, nowa wchodzi
// kryciem i przesunięciem. Z View Transitions API — jedno przejście przeglądarki.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { cx, type BaseProps } from "./types";
import { useReducedMotion } from "./useReducedMotion";

export interface PageTransitionProps extends BaseProps {
  /** Zmiana tej wartości uruchamia przejście. */
  viewKey: string;
  children: ReactNode;
}

export function PageTransition({ viewKey, className, children, ...reszta }: PageTransitionProps) {
  const ograniczony = useReducedMotion();
  const [widok, setWidok] = useState({ key: viewKey, tresc: children });
  const poprzedni = useRef(viewKey);

  useEffect(() => {
    if (poprzedni.current === viewKey) {
      setWidok({ key: viewKey, tresc: children });
      return;
    }
    poprzedni.current = viewKey;
    if (!ograniczony && typeof document.startViewTransition === "function") {
      document.startViewTransition(() => setWidok({ key: viewKey, tresc: children }));
      return;
    }
    setWidok({ key: viewKey, tresc: children });
  }, [children, ograniczony, viewKey]);

  return (
    <div key={widok.key} className={cx("ui-widok", className)} {...reszta}>
      {widok.tresc}
    </div>
  );
}
