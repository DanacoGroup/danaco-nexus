// Zakładki (ui-kit, rozdz. 9.4): wzorzec tablist/tab/tabpanel, aktywacja automatyczna
// dla treści lokalnej albo ręczna (Enter) dla treści z serwera.

import { useId, useRef, type ReactNode } from "react";
import { Badge } from "./Badge";
import { cx, type BaseProps, type IconSlot } from "./types";

export interface TabItem<V extends string> {
  value: V;
  label: string;
  count?: number;
  icon?: IconSlot;
  disabled?: boolean;
}

export interface TabsProps<V extends string> extends BaseProps {
  label: string;
  items: TabItem<V>[];
  value: V;
  onChange: (value: V) => void;
  activation?: "automatic" | "manual";
  children?: ReactNode;
}

export function Tabs<V extends string>({ label, items, value, onChange, activation = "automatic", className, children, ...reszta }: TabsProps<V>) {
  const id = useId();
  const lista = useRef<HTMLDivElement>(null);

  const przesun = (kierunek: 1 | -1) => {
    const dostepne = items.filter((pozycja) => !pozycja.disabled);
    const biezaca = dostepne.findIndex((pozycja) => pozycja.value === value);
    const nastepna = dostepne[(biezaca + kierunek + dostepne.length) % dostepne.length];
    if (!nastepna) return;
    const przyciski = [...(lista.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? [])];
    przyciski.find((przycisk) => przycisk.id === `${id}-${nastepna.value}`)?.focus();
    if (activation === "automatic") onChange(nastepna.value);
  };

  return (
    <div className={cx("flex flex-col", className)} style={{ gap: "var(--space-4)" }} {...reszta}>
      <div ref={lista} role="tablist" aria-label={label} className="flex border-b border-line" style={{ gap: "var(--space-5)" }}>
        {items.map((pozycja) => {
          const wybrana = pozycja.value === value;
          return (
            <button
              key={pozycja.value}
              id={`${id}-${pozycja.value}`}
              type="button"
              role="tab"
              aria-selected={wybrana}
              aria-controls={`${id}-${pozycja.value}-panel`}
              tabIndex={wybrana ? 0 : -1}
              aria-disabled={pozycja.disabled || undefined}
              disabled={pozycja.disabled || undefined}
              onClick={() => !pozycja.disabled && onChange(pozycja.value)}
              onKeyDown={(zdarzenie) => {
                if (zdarzenie.key === "ArrowRight") {
                  zdarzenie.preventDefault();
                  przesun(1);
                } else if (zdarzenie.key === "ArrowLeft") {
                  zdarzenie.preventDefault();
                  przesun(-1);
                } else if (activation === "manual" && (zdarzenie.key === "Enter" || zdarzenie.key === " ")) {
                  zdarzenie.preventDefault();
                  onChange(pozycja.value);
                }
              }}
              className={cx(
                "ui-kontrolka ui-przejscie relative inline-flex items-center border-transparent",
                wybrana ? "border-accent text-fg" : "text-muted hover:text-fg",
              )}
              style={{
                blockSize: "var(--control-md)",
                gap: "var(--space-2)",
                font: "var(--text-style-label)",
                borderBlockEndWidth: "var(--border-width-thick)",
                borderBlockEndStyle: "solid",
              }}
            >
              {pozycja.icon}
              {pozycja.label}
              {typeof pozycja.count === "number" ? <Badge tone={wybrana ? "accent" : "neutral"}>{pozycja.count}</Badge> : null}
            </button>
          );
        })}
      </div>
      {children ? (
        <div id={`${id}-${value}-panel`} role="tabpanel" aria-labelledby={`${id}-${value}`} tabIndex={0}>
          {children}
        </div>
      ) : null}
    </div>
  );
}
