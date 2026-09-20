// Typy wspólne biblioteki (ui-kit/COMPONENT_LIBRARY.md, rozdz. 1.4) i pomocniki klas.

import type { ReactNode } from "react";

export type ControlSize = "xs" | "sm" | "md" | "lg" | "xl";
export type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "info" | "ai";
export type Shortcut = string[];

export interface BaseProps {
  className?: string;
  "data-testid"?: string;
}

export type IconSlot = ReactNode;

/** Skleja nazwy klas, pomijając wartości puste. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** Wysokość kontrolki — token --control-*. */
export const CONTROL_HEIGHT: Record<ControlSize, string> = {
  xs: "var(--control-xs)",
  sm: "var(--control-sm)",
  md: "var(--control-md)",
  lg: "var(--control-lg)",
  xl: "var(--control-xl)",
};

/** Odstęp poziomy przycisku — token --space-*. */
export const CONTROL_INLINE: Record<ControlSize, string> = {
  xs: "var(--space-2)",
  sm: "var(--space-3)",
  md: "var(--space-4)",
  lg: "var(--space-5)",
  xl: "var(--space-6)",
};

export const CONTROL_FONT: Record<ControlSize, string> = {
  xs: "var(--font-size-xs)",
  sm: "var(--font-size-sm)",
  md: "var(--font-size-sm)",
  lg: "var(--font-size-sm)",
  xl: "var(--font-size-md)",
};

export const ICON_SIZE: Record<ControlSize, number> = { xs: 16, sm: 16, md: 16, lg: 16, xl: 20 };

/** Ton w wersji przygaszonej: tło + tekst (Badge, kafle stanu). */
export const TONE_SOFT: Record<Tone, string> = {
  neutral: "bg-hover text-muted",
  accent: "bg-accent-soft text-accent",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  info: "bg-info-soft text-info",
  ai: "bg-accent-soft text-accent",
};

/** Ton w wersji tekstowej (ikony stanu, opisy). */
export const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-muted",
  accent: "text-accent",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
  ai: "text-accent",
};

/** Czas z tokenu CSS w milisekundach — bez wartości wpisywanych w kodzie. */
export function tokenMs(nazwa: string): number | null {
  if (typeof window === "undefined" || typeof getComputedStyle !== "function") return null;
  const wartosc = getComputedStyle(document.documentElement).getPropertyValue(nazwa).trim();
  const liczba = Number.parseFloat(wartosc);
  if (!Number.isFinite(liczba)) return null;
  return wartosc.endsWith("ms") ? liczba : liczba * 1000;
}

/** Znak zapisu skrótu; Ctrl i Alt na macOS mają własne symbole. */
export function shortcutLabel(keys: Shortcut): string {
  const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || "");
  return keys.map((key) => (mac && key === "Ctrl" ? "⌘" : mac && key === "Alt" ? "⌥" : key)).join(" ");
}

/** aria-keyshortcuts wymaga zapisu z plusami i nazw z WAI-ARIA. */
export function ariaKeyshortcuts(keys: Shortcut): string {
  return keys
    .map((key) => (key === "⏎" ? "Enter" : key === "Esc" ? "Escape" : key === "Ctrl" ? "Control" : key === "Spacja" ? "Space" : key))
    .join("+");
}
