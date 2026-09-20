// Lista wyboru: wzorzec WAI-ARIA combobox + listbox (ui-kit, rozdz. 3.4).
// Bez elementu natywnego — lista ma kroje i barwy produktu.

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Field, opisPola } from "./Field";
import { CheckIcon, ChevronDownIcon } from "./Icons";
import { cx, type BaseProps, type IconSlot } from "./types";

export interface SelectOption<V extends string> {
  value: V;
  label: string;
  description?: string;
  icon?: IconSlot;
  disabled?: boolean;
}

export interface SelectProps<V extends string> extends BaseProps {
  label: string;
  value: V | null;
  onChange: (value: V) => void;
  options: SelectOption<V>[];
  placeholder?: string;
  description?: string;
  error?: string;
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  hideLabel?: boolean;
}

const WYSOKOSC: Record<NonNullable<SelectProps<string>["size"]>, string> = {
  sm: "var(--control-sm)",
  md: "var(--control-md)",
  lg: "var(--control-lg)",
};

export function Select<V extends string>({
  label,
  value,
  onChange,
  options,
  placeholder = "Wybierz",
  description,
  error,
  size = "md",
  disabled = false,
  hideLabel,
  className,
  ...reszta
}: SelectProps<V>) {
  const id = useId();
  const [otwarta, setOtwarta] = useState(false);
  const [aktywna, setAktywna] = useState(() => Math.max(0, options.findIndex((opcja) => opcja.value === value)));
  const korzen = useRef<HTMLDivElement>(null);
  const wyzwalacz = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!otwarta) return;
    const pozaListą = (zdarzenie: MouseEvent) => {
      if (!korzen.current?.contains(zdarzenie.target as Node)) setOtwarta(false);
    };
    document.addEventListener("mousedown", pozaListą);
    return () => document.removeEventListener("mousedown", pozaListą);
  }, [otwarta]);

  const wybrana = options.find((opcja) => opcja.value === value);

  const przesun = (kierunek: 1 | -1) => {
    const dostepne = options.map((opcja, index) => (opcja.disabled ? -1 : index)).filter((index) => index >= 0);
    if (!dostepne.length) return;
    const biezaca = dostepne.indexOf(aktywna);
    const nastepna = dostepne[(biezaca + kierunek + dostepne.length) % dostepne.length];
    setAktywna(nastepna);
  };

  const wybierz = (index: number) => {
    const opcja = options[index];
    if (!opcja || opcja.disabled) return;
    onChange(opcja.value);
    setOtwarta(false);
    wyzwalacz.current?.focus();
  };

  const klawisz = (zdarzenie: KeyboardEvent) => {
    if (disabled) return;
    if (!otwarta && (zdarzenie.key === "Enter" || zdarzenie.key === " " || zdarzenie.key === "ArrowDown")) {
      zdarzenie.preventDefault();
      setOtwarta(true);
      return;
    }
    if (!otwarta) return;
    if (zdarzenie.key === "ArrowDown") {
      zdarzenie.preventDefault();
      przesun(1);
    } else if (zdarzenie.key === "ArrowUp") {
      zdarzenie.preventDefault();
      przesun(-1);
    } else if (zdarzenie.key === "Enter" || zdarzenie.key === " ") {
      zdarzenie.preventDefault();
      wybierz(aktywna);
    } else if (zdarzenie.key === "Escape") {
      setOtwarta(false);
      wyzwalacz.current?.focus();
    } else if (zdarzenie.key.length === 1) {
      const znak = zdarzenie.key.toLowerCase();
      const index = options.findIndex((opcja) => !opcja.disabled && opcja.label.toLowerCase().startsWith(znak));
      if (index >= 0) setAktywna(index);
    }
  };

  return (
    <Field id={id} label={label} hideLabel={hideLabel} description={description} error={error} className={className}>
      <div ref={korzen} className="relative" {...reszta}>
        <button
          ref={wyzwalacz}
          type="button"
          id={id}
          role="combobox"
          aria-labelledby={`${id}-etykieta`}
          aria-expanded={otwarta}
          aria-haspopup="listbox"
          aria-controls={`${id}-lista`}
          aria-activedescendant={otwarta ? `${id}-opcja-${aktywna}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={opisPola(id, description, error)}
          aria-disabled={disabled || undefined}
          disabled={disabled || undefined}
          onClick={() => setOtwarta((stan) => !stan)}
          onKeyDown={klawisz}
          className={cx(
            "ui-kontrolka ui-przejscie flex w-full items-center justify-between rounded-md border bg-app text-fg",
            error ? "border-danger" : otwarta ? "border-accent" : "border-line-control hover:border-muted",
          )}
          style={{ blockSize: WYSOKOSC[size], paddingInline: "var(--space-3)", gap: "var(--space-2)", font: "var(--text-style-body)" }}
        >
          <span className={cx("truncate", wybrana ? "text-fg" : "text-subtle")}>{wybrana?.label ?? placeholder}</span>
          <span className={cx("grid text-muted ui-przejscie-tresc", otwarta && "rotate-180")}>
            <ChevronDownIcon />
          </span>
        </button>

        {otwarta ? (
          <ul
            id={`${id}-lista`}
            role="listbox"
            aria-label={label}
            tabIndex={-1}
            className="ui-wysuw absolute w-full overflow-auto rounded-lg border border-line bg-raised shadow-medium"
            style={{
              zIndex: "var(--z-dropdown)",
              insetBlockStart: `calc(100% + var(--space-1))`,
              padding: "var(--space-1)",
              minInlineSize: "var(--layout-menu-min)",
              maxBlockSize: "var(--layout-panel)",
            }}
          >
            {options.map((opcja, index) => (
              <li
                key={opcja.value}
                id={`${id}-opcja-${index}`}
                role="option"
                aria-selected={opcja.value === value}
                aria-disabled={opcja.disabled || undefined}
                onMouseEnter={() => !opcja.disabled && setAktywna(index)}
                onMouseDown={(zdarzenie) => zdarzenie.preventDefault()}
                onClick={() => wybierz(index)}
                className={cx(
                  "flex cursor-default items-center rounded-sm",
                  index === aktywna && !opcja.disabled && "bg-hover",
                  opcja.disabled && "ui-kontrolka",
                )}
                style={{
                  minBlockSize: "var(--control-sm)",
                  paddingInline: "var(--space-2)",
                  gap: "var(--space-2)",
                  font: "var(--text-style-body)",
                  opacity: opcja.disabled ? "var(--opacity-disabled)" : undefined,
                }}
              >
                {opcja.icon ? <span className="grid text-muted">{opcja.icon}</span> : null}
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-fg">{opcja.label}</span>
                  {opcja.description ? (
                    <span className="truncate text-muted" style={{ font: "var(--text-style-caption)" }}>
                      {opcja.description}
                    </span>
                  ) : null}
                </span>
                {opcja.value === value ? (
                  <span className="ms-auto grid text-accent">
                    <CheckIcon />
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </Field>
  );
}
