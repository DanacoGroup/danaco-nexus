// Oprawa pola formularza: etykieta, znacznik „opcjonalne”, pomoc i komunikat błędu
// (ui-kit, rozdz. 3 — część wspólna wszystkich pól).

import type { ReactNode } from "react";
import { ErrorIcon } from "./Icons";
import { cx, type BaseProps } from "./types";

export interface FieldProps extends BaseProps {
  id: string;
  label: string;
  /** Etykieta ukryta wzrokowo — pole nadal ma nazwę dostępną. */
  hideLabel?: boolean;
  optional?: boolean;
  description?: string;
  error?: string;
  /** Dodatek po prawej w wierszu etykiety, np. licznik znaków. */
  labelAside?: ReactNode;
  children: ReactNode;
}

export function opisPola(id: string, description?: string, error?: string): string | undefined {
  const czesci = [description ? `${id}-pomoc` : null, error ? `${id}-blad` : null].filter(Boolean);
  return czesci.length ? czesci.join(" ") : undefined;
}

/** Czy klasa od wywołującego sama ustawia szerokość pola.
 *
 * Pole domyślnie zajmuje całą szerokość rodzica — tak wygląda formularz. Ale `w-full`
 * i podana obok `w-44` to dwie klasy tej samej warstwy: o zwycięzcy decyduje kolejność
 * w arkuszu, nie kolejność w atrybucie, i wygrywało `w-full`. W Tłumaczu pasek z wyborem
 * języków zamieniał się przez to na komputerze w cztery kontrolki na całą szerokość,
 * jedna pod drugą, choć miały stać obok siebie. Gdy wywołujący sam mówi, jak szerokie ma
 * być pole, nie dokładamy już nic od siebie.
 */
const WLASNA_SZEROKOSC = /(?:^|\s)(?:w-|basis-|flex-1|flex-auto)/;

export function Field({ id, label, hideLabel, optional, description, error, labelAside, className, children, ...reszta }: FieldProps) {
  return (
    <div
      className={cx("flex flex-col", !WLASNA_SZEROKOSC.test(className ?? "") && "w-full", className)}
      style={{ gap: "var(--space-role-stack-tight)" }}
      {...reszta}
    >
      <div className={cx("flex items-baseline justify-between", hideLabel && "sr-only")} style={{ gap: "var(--space-2)" }}>
        <label id={`${id}-etykieta`} htmlFor={id} className="text-fg" style={{ font: "var(--text-style-label)" }}>
          {label}
        </label>
        {labelAside ?? (optional ? <span className="text-subtle" style={{ font: "var(--text-style-caption)" }}>opcjonalne</span> : null)}
      </div>
      {children}
      {description ? (
        <p id={`${id}-pomoc`} className="text-muted" style={{ font: "var(--text-style-caption)" }}>
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-blad`} className="flex items-center text-danger" style={{ font: "var(--text-style-caption)", gap: "var(--space-1)" }}>
          <ErrorIcon size={14} />
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Wspólne klasy powierzchni pola: obrys, tło, stan błędu i fokus. */
export function klasyPola(error?: string, readOnly?: boolean): string {
  return cx(
    "ui-kontrolka ui-przejscie w-full rounded-md border bg-app text-fg placeholder:text-subtle",
    error ? "border-danger" : "border-line-control hover:border-muted",
    readOnly && "border-line bg-side text-muted",
  );
}
