// Wciśnięcie: skala --scale-press na czas nacisku, także z klawiatury (Spacja, Enter).
// Przy ograniczonym ruchu skala zostaje 1, stan `pressed` działa dalej.

import { useCallback, useMemo, useState } from "react";
import { useReducedMotion } from "./useReducedMotion";

export interface PressOptions {
  /** Silniejsze wciśnięcie (przycisk wysyłki w polu wiadomości). */
  strong?: boolean;
  disabled?: boolean;
}

export interface PressResult {
  pressed: boolean;
  props: {
    onPointerDown: () => void;
    onPointerUp: () => void;
    onPointerLeave: () => void;
    onKeyDown: (zdarzenie: { key: string }) => void;
    onKeyUp: () => void;
    onBlur: () => void;
    style: { transform?: string; transition: string };
  };
}

export function usePress({ strong = false, disabled = false }: PressOptions = {}): PressResult {
  const ograniczony = useReducedMotion();
  const [wcisniety, setWcisniety] = useState(false);

  const wlacz = useCallback(() => {
    if (!disabled) setWcisniety(true);
  }, [disabled]);
  const wylacz = useCallback(() => setWcisniety(false), []);
  const klawisz = useCallback(
    (zdarzenie: { key: string }) => {
      if (zdarzenie.key === " " || zdarzenie.key === "Enter") wlacz();
    },
    [wlacz],
  );

  const skala = strong ? "var(--scale-press-strong)" : "var(--scale-press)";
  const props = useMemo(
    () => ({
      onPointerDown: wlacz,
      onPointerUp: wylacz,
      onPointerLeave: wylacz,
      onKeyDown: klawisz,
      onKeyUp: wylacz,
      onBlur: wylacz,
      style: {
        transform: wcisniety && !ograniczony ? `scale(${skala})` : undefined,
        transition: "transform var(--duration-fast) var(--easing-standard)",
      },
    }),
    [klawisz, ograniczony, skala, wcisniety, wlacz, wylacz],
  );

  return { pressed: wcisniety, props };
}
