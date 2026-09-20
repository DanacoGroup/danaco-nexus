// Przełącznik ustawienia działającego natychmiast (ui-kit, rozdz. 3.7).
// Gdy onChange zwraca obietnicę, uchwyt pokazuje zapisywanie.

import { useId, useState } from "react";
import { Spinner } from "./Progress";
import { cx, type BaseProps } from "./types";

export interface SwitchProps extends BaseProps {
  checked: boolean;
  onChange: (checked: boolean) => void | Promise<void>;
  label: string;
  description?: string;
  disabled?: boolean;
}

export function Switch({ checked, onChange, label, description, disabled = false, className, ...reszta }: SwitchProps) {
  const id = useId();
  const [zapisuje, setZapisuje] = useState(false);

  const przelacz = () => {
    if (disabled || zapisuje) return;
    const wynik = onChange(!checked);
    if (wynik instanceof Promise) {
      setZapisuje(true);
      void wynik.finally(() => setZapisuje(false));
    }
  };

  return (
    <div className={cx("flex items-start justify-between", className)} style={{ gap: "var(--space-4)" }} {...reszta}>
      <span className="flex flex-col" style={{ gap: "var(--space-0-5)" }}>
        <label id={`${id}-etykieta`} htmlFor={id} className="text-fg" style={{ font: "var(--text-style-label)" }}>
          {label}
        </label>
        {description ? (
          <span id={`${id}-opis`} className="text-muted" style={{ font: "var(--text-style-caption)" }}>
            {description}
          </span>
        ) : null}
      </span>
      <button
        type="button"
        id={id}
        role="switch"
        aria-checked={checked}
        aria-labelledby={`${id}-etykieta`}
        aria-describedby={description ? `${id}-opis` : undefined}
        aria-busy={zapisuje || undefined}
        aria-disabled={disabled || undefined}
        disabled={disabled || undefined}
        onClick={przelacz}
        className={cx(
          "ui-kontrolka ui-przejscie ui-cel-dotyku relative inline-flex shrink-0 items-center rounded-full border",
          checked ? "border-accent-fill bg-accent-fill" : "border-line-control bg-hover",
        )}
        style={{ inlineSize: "var(--space-8)", blockSize: "var(--space-5)", padding: "var(--space-0-5)" }}
      >
        <span
          className={cx("grid place-items-center rounded-full", checked ? "bg-on-accent text-accent-fill" : "bg-muted text-app shadow-soft")}
          style={{
            inlineSize: "var(--space-3)",
            blockSize: "var(--space-3)",
            transform: checked ? "translateX(var(--space-3))" : "translateX(0)",
            transition: "transform var(--duration-fast) var(--easing-standard)",
          }}
        >
          {zapisuje ? <Spinner size="sm" className="scale-50" /> : null}
        </span>
      </button>
    </div>
  );
}
