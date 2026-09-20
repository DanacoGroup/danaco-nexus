// Pole tekstowe jednowierszowe (ui-kit, rozdz. 3.1) i pole wyszukiwania (rozdz. 3.3).

import { forwardRef, useId, useRef, type InputHTMLAttributes } from "react";
import { Field, klasyPola, opisPola } from "./Field";
import { IconButton } from "./Button";
import { CloseIcon, SearchIcon } from "./Icons";
import { Kbd } from "./Kbd";
import { Spinner } from "./Progress";
import { cx, type BaseProps, type IconSlot, type Shortcut } from "./types";

type PolaNatywne = Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "value" | "onChange" | "size" | "type">;

export interface InputProps extends BaseProps, PolaNatywne {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hideLabel?: boolean;
  description?: string;
  error?: string;
  optional?: boolean;
  iconStart?: IconSlot;
  clearable?: boolean;
  size?: "sm" | "md" | "lg";
  type?: "text" | "email" | "password" | "url" | "number" | "search";
}

const WYSOKOSC: Record<NonNullable<InputProps["size"]>, string> = {
  sm: "var(--control-sm)",
  md: "var(--control-md)",
  lg: "var(--control-lg)",
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, value, onChange, hideLabel, description, error, optional, iconStart, clearable, size = "md", type = "text", id, className, readOnly, ...reszta },
  ref,
) {
  const wlasne = useId();
  const pole = id ?? wlasne;

  return (
    <Field id={pole} label={label} hideLabel={hideLabel} optional={optional} description={description} error={error} className={className}>
      <div className={cx("relative flex items-center", klasyPola(error, readOnly))} style={{ blockSize: WYSOKOSC[size] }}>
        {iconStart ? <span className="pointer-events-none grid text-subtle" style={{ marginInlineStart: "var(--space-3)" }}>{iconStart}</span> : null}
        <input
          ref={ref}
          id={pole}
          type={type}
          value={value}
          readOnly={readOnly}
          onChange={(zdarzenie) => onChange(zdarzenie.target.value)}
          aria-invalid={error ? true : undefined}
          aria-readonly={readOnly ? true : undefined}
          aria-describedby={opisPola(pole, description, error)}
          className="h-full w-full min-w-0 bg-transparent outline-none"
          style={{ paddingInline: "var(--space-3)", font: "var(--text-style-body)" }}
          {...reszta}
        />
        {clearable && value ? (
          <span style={{ marginInlineEnd: "var(--space-1)" }}>
            <IconButton icon={<CloseIcon />} label={`Wyczyść: ${label}`} size="xs" onClick={() => onChange("")} />
          </span>
        ) : null}
      </div>
    </Field>
  );
});

export interface SearchInputProps extends BaseProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  shortcut?: Shortcut;
  /** Wyszukiwanie po znaczeniu — pokazuje wskaźnik w trakcie. */
  semantic?: boolean;
  searching?: boolean;
  resultCount?: number;
  size?: "sm" | "md" | "lg";
}

export function SearchInput({
  label,
  value,
  onChange,
  placeholder = "Szukaj",
  shortcut = ["/"],
  semantic = false,
  searching = false,
  resultCount,
  size = "md",
  className,
  ...reszta
}: SearchInputProps) {
  const pole = useId();
  const wejscie = useRef<HTMLInputElement>(null);

  return (
    <div className={cx("flex w-full flex-col", className)} style={{ gap: "var(--space-1)" }} {...reszta}>
      <div
        className="ui-przejscie flex w-full items-center rounded-md border border-line-control bg-side"
        style={{ blockSize: WYSOKOSC[size], paddingInline: "var(--space-3)", gap: "var(--space-2)" }}
      >
        <span className="grid text-subtle">{searching && semantic ? <Spinner tone="ai" /> : <SearchIcon />}</span>
        <input
          ref={wejscie}
          type="search"
          role="searchbox"
          aria-label={label}
          aria-describedby={`${pole}-wynik`}
          placeholder={placeholder}
          value={value}
          onChange={(zdarzenie) => onChange(zdarzenie.target.value)}
          onKeyDown={(zdarzenie) => {
            if (zdarzenie.key !== "Escape") return;
            if (value) onChange("");
            else wejscie.current?.blur();
          }}
          className="h-full w-full min-w-0 bg-transparent text-fg outline-none placeholder:text-subtle"
          style={{ font: "var(--text-style-body)" }}
        />
        {value ? (
          <IconButton icon={<CloseIcon />} label={`Wyczyść: ${label}`} size="xs" onClick={() => onChange("")} />
        ) : (
          <Kbd keys={shortcut} />
        )}
      </div>
      <span id={`${pole}-wynik`} role="status" className="text-subtle" style={{ font: "var(--text-style-caption)" }}>
        {typeof resultCount === "number" ? `${resultCount} wyników` : ""}
      </span>
    </div>
  );
}
