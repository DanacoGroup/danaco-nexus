// Obszar tekstu wielowierszowego (ui-kit, rozdz. 3.2): rośnie z treścią, licznik znaków
// ostrzega od 90% limitu. Ctrl+Enter zatwierdza formularz.

import { forwardRef, useId, type TextareaHTMLAttributes } from "react";
import { Field, klasyPola, opisPola } from "./Field";
import { cx, type BaseProps } from "./types";

type PolaNatywne = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className" | "value" | "onChange" | "rows">;

export interface TextareaProps extends BaseProps, PolaNatywne {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hideLabel?: boolean;
  description?: string;
  error?: string;
  optional?: boolean;
  minRows?: number;
  maxRows?: number;
  maxLength?: number;
  onSubmit?: () => void;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, value, onChange, hideLabel, description, error, optional, minRows = 3, maxRows = 10, maxLength, onSubmit, id, className, ...reszta },
  ref,
) {
  const wlasne = useId();
  const pole = id ?? wlasne;
  const udzial = maxLength ? value.length / maxLength : 0;
  const przekroczony = maxLength ? value.length > maxLength : false;
  const komunikat = przekroczony ? `Skróć tekst o ${value.length - (maxLength ?? 0)} znaków.` : error;

  const licznik = maxLength ? (
    <span
      id={`${pole}-licznik`}
      className={cx(przekroczony ? "text-danger" : udzial >= 0.9 ? "text-warning" : "text-subtle")}
      style={{ font: "var(--text-style-caption)", fontVariantNumeric: "var(--font-numeric-tabular)" }}
      aria-live={udzial >= 0.9 ? "polite" : "off"}
    >
      {value.length} / {maxLength}
    </span>
  ) : null;

  return (
    <Field
      id={pole}
      label={label}
      hideLabel={hideLabel}
      optional={optional}
      description={description}
      error={komunikat}
      labelAside={licznik}
      className={className}
    >
      <textarea
        ref={ref}
        id={pole}
        value={value}
        rows={minRows}
        onChange={(zdarzenie) => onChange(zdarzenie.target.value)}
        onKeyDown={(zdarzenie) => {
          if (zdarzenie.key === "Enter" && (zdarzenie.ctrlKey || zdarzenie.metaKey)) onSubmit?.();
        }}
        aria-invalid={komunikat ? true : undefined}
        aria-describedby={cx(opisPola(pole, description, komunikat), maxLength ? `${pole}-licznik` : "").trim() || undefined}
        className={cx(klasyPola(komunikat), "resize-y outline-none")}
        style={{
          padding: "var(--space-3)",
          font: "var(--text-style-body)",
          minBlockSize: `calc(${minRows} * var(--space-6))`,
          maxBlockSize: `calc(${maxRows} * var(--space-6))`,
        }}
        {...reszta}
      />
    </Field>
  );
});
