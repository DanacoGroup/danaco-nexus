// Karta: wspólna powierzchnia treści (ui-kit, rozdz. 5 — część wspólna kart).

import type { ReactNode } from "react";
import { cx, type BaseProps } from "./types";

export interface CardProps extends BaseProps {
  /** Cała karta jest jednym celem kliknięcia. */
  onClick?: () => void;
  href?: string;
  selected?: boolean;
  /** Uniesienie i cień przy wskazaniu — dla kart klikalnych. */
  interactive?: boolean;
  header?: ReactNode;
  footer?: ReactNode;
  children?: ReactNode;
}

export function Card({ onClick, href, selected = false, interactive, header, footer, className, children, ...reszta }: CardProps) {
  const klikalna = interactive ?? Boolean(onClick || href);
  const klasy = cx(
    "ui-przejscie-tresc block overflow-hidden rounded-lg border bg-raised text-start shadow-soft",
    selected ? "border-accent" : "border-line",
    klikalna && "hover:-translate-y-[var(--distance-nudge)] hover:border-line-strong hover:shadow-medium",
    className,
  );
  const wnetrze = (
    <div className="flex flex-col" style={{ padding: "var(--space-role-inset-card)", gap: "var(--space-role-stack-tight)" }}>
      {header}
      {children}
      {footer}
    </div>
  );

  if (href) {
    return (
      <a href={href} className={klasy} aria-current={selected ? "true" : undefined} {...reszta}>
        {wnetrze}
      </a>
    );
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cx(klasy, "w-full")} aria-pressed={selected} {...reszta}>
        {wnetrze}
      </button>
    );
  }
  return (
    <div className={klasy} {...reszta}>
      {wnetrze}
    </div>
  );
}
