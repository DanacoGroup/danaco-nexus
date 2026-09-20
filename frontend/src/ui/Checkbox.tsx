// Pole wyboru ze stanem mieszanym (ui-kit, rozdz. 3.5).

import { useId } from "react";
import { CheckIcon, MinusIcon } from "./Icons";
import { cx, type BaseProps } from "./types";

export interface CheckboxProps extends BaseProps {
  checked: boolean | "mixed";
  onChange: (checked: boolean) => void;
  label?: string;
  ariaLabel?: string;
  description?: string;
  disabled?: boolean;
  error?: string;
}

export function Checkbox({ checked, onChange, label, ariaLabel, description, disabled = false, error, className, ...reszta }: CheckboxProps) {
  const id = useId();
  const mieszany = checked === "mixed";
  const oznaczony = checked === true;

  return (
    <div className={cx("flex flex-col", className)} style={{ gap: "var(--space-1)" }} {...reszta}>
      <div className="flex items-start" style={{ gap: "var(--space-2)" }}>
        <button
          type="button"
          id={id}
          role="checkbox"
          aria-checked={mieszany ? "mixed" : oznaczony}
          aria-label={label ? undefined : ariaLabel}
          aria-labelledby={label ? `${id}-etykieta` : undefined}
          aria-describedby={description ? `${id}-opis` : undefined}
          aria-invalid={error ? true : undefined}
          aria-disabled={disabled || undefined}
          disabled={disabled || undefined}
          onClick={() => !disabled && onChange(!oznaczony)}
          className={cx(
            "ui-kontrolka ui-przejscie ui-cel-dotyku relative grid shrink-0 place-items-center rounded-xs border",
            oznaczony || mieszany ? "border-accent-fill bg-accent-fill text-on-accent" : error ? "border-danger bg-app" : "border-line-control bg-app hover:border-muted",
          )}
          style={{ inlineSize: "var(--space-4)", blockSize: "var(--space-4)", marginBlockStart: "var(--space-0-5)" }}
        >
          {mieszany ? <MinusIcon size={12} /> : oznaczony ? <CheckIcon size={12} /> : null}
        </button>
        {label ? (
          <label id={`${id}-etykieta`} htmlFor={id} className="text-fg" style={{ font: "var(--text-style-body)" }}>
            {label}
          </label>
        ) : null}
      </div>
      {description ? (
        <p id={`${id}-opis`} className="text-muted" style={{ font: "var(--text-style-caption)", marginInlineStart: "var(--space-6)" }}>
          {description}
        </p>
      ) : null}
      {error ? (
        <p className="text-danger" style={{ font: "var(--text-style-caption)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
