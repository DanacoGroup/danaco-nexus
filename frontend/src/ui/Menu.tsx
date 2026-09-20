// Menu rozwijane (ui-kit, rozdz. 7.2): role menu/menuitem, strzałki, litera, Esc.
// Wyzwalaczem jest dowolny element przycisku przekazany w `trigger`.

import { cloneElement, isValidElement, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactElement, type ReactNode } from "react";
import { CheckIcon } from "./Icons";
import { Kbd } from "./Kbd";
import { cx, type BaseProps, type IconSlot, type Shortcut } from "./types";

export interface MenuItem {
  id: string;
  label: string;
  description?: string;
  icon?: IconSlot;
  shortcut?: Shortcut;
  destructive?: boolean;
  disabled?: boolean;
  /** Pozycja wyboru — rola menuitemradio z aria-checked. */
  checked?: boolean;
  onSelect?: () => void;
}

export type MenuEntry = MenuItem | { type: "separator" } | { type: "group"; label: string; items: MenuItem[] };

export interface MenuProps extends BaseProps {
  trigger: ReactNode;
  items: MenuEntry[];
  align?: "start" | "end";
  side?: "top" | "bottom";
  label?: string;
}

function pozycje(items: MenuEntry[]): MenuItem[] {
  return items.flatMap((wpis) => ("type" in wpis ? (wpis.type === "group" ? wpis.items : []) : [wpis]));
}

export function Menu({ trigger, items, align = "start", side = "bottom", label = "Menu", className, ...reszta }: MenuProps) {
  const id = useId();
  const [otwarte, setOtwarte] = useState(false);
  const [aktywna, setAktywna] = useState(0);
  const korzen = useRef<HTMLDivElement>(null);
  const wyzwalacz = useRef<HTMLElement>(null);

  const lista = pozycje(items).filter((pozycja) => !pozycja.disabled);

  useEffect(() => {
    if (!otwarte) return;
    const poza = (zdarzenie: MouseEvent) => {
      if (!korzen.current?.contains(zdarzenie.target as Node)) setOtwarte(false);
    };
    document.addEventListener("mousedown", poza);
    return () => document.removeEventListener("mousedown", poza);
  }, [otwarte]);

  const uruchom = (pozycja: MenuItem) => {
    if (pozycja.disabled) return;
    pozycja.onSelect?.();
    setOtwarte(false);
    wyzwalacz.current?.focus();
  };

  const klawisz = (zdarzenie: KeyboardEvent) => {
    if (!otwarte) return;
    if (zdarzenie.key === "ArrowDown") {
      zdarzenie.preventDefault();
      setAktywna((index) => (index + 1) % lista.length);
    } else if (zdarzenie.key === "ArrowUp") {
      zdarzenie.preventDefault();
      setAktywna((index) => (index - 1 + lista.length) % lista.length);
    } else if (zdarzenie.key === "Enter" || zdarzenie.key === " ") {
      zdarzenie.preventDefault();
      const pozycja = lista[aktywna];
      if (pozycja) uruchom(pozycja);
    } else if (zdarzenie.key === "Escape") {
      setOtwarte(false);
      wyzwalacz.current?.focus();
    } else if (zdarzenie.key.length === 1) {
      const znak = zdarzenie.key.toLowerCase();
      const index = lista.findIndex((pozycja) => pozycja.label.toLowerCase().startsWith(znak));
      if (index >= 0) setAktywna(index);
    }
  };

  const wyzwalaczZWlasciwosciami = isValidElement(trigger)
    ? cloneElement(trigger as ReactElement<Record<string, unknown>>, {
        ref: wyzwalacz,
        "aria-haspopup": "menu",
        "aria-expanded": otwarte,
        "aria-controls": otwarte ? `${id}-menu` : undefined,
        onClick: () => {
          setOtwarte((stan) => !stan);
          setAktywna(0);
        },
      })
    : trigger;

  const wiersz = (pozycja: MenuItem) => {
    const index = lista.indexOf(pozycja);
    return (
      <li key={pozycja.id}>
        <button
          type="button"
          role={typeof pozycja.checked === "boolean" ? "menuitemradio" : "menuitem"}
          aria-checked={typeof pozycja.checked === "boolean" ? pozycja.checked : undefined}
          aria-disabled={pozycja.disabled || undefined}
          disabled={pozycja.disabled || undefined}
          tabIndex={-1}
          onMouseEnter={() => index >= 0 && setAktywna(index)}
          onClick={() => uruchom(pozycja)}
          className={cx(
            "ui-kontrolka flex w-full items-center rounded-sm text-start",
            pozycja.destructive ? "text-danger hover:bg-danger-soft" : "text-fg",
            index === aktywna && !pozycja.disabled && (pozycja.destructive ? "bg-danger-soft" : "bg-hover"),
          )}
          style={{ minBlockSize: "var(--control-sm)", paddingInline: "var(--space-2)", gap: "var(--space-2)", font: "var(--text-style-body)" }}
        >
          {pozycja.icon ? <span className={cx("grid", pozycja.destructive ? "text-danger" : "text-muted")}>{pozycja.icon}</span> : null}
          <span className="flex min-w-0 flex-col">
            <span className="truncate">{pozycja.label}</span>
            {pozycja.description ? (
              <span className="truncate text-muted" style={{ font: "var(--text-style-caption)" }}>
                {pozycja.description}
              </span>
            ) : null}
          </span>
          <span className="ms-auto flex items-center" style={{ gap: "var(--space-2)" }}>
            {pozycja.shortcut ? <Kbd keys={pozycja.shortcut} /> : null}
            {pozycja.checked ? (
              <span className="grid text-accent">
                <CheckIcon />
              </span>
            ) : null}
          </span>
        </button>
      </li>
    );
  };

  return (
    <div ref={korzen} className={cx("relative inline-flex", className)} onKeyDown={klawisz} {...reszta}>
      {wyzwalaczZWlasciwosciami}
      {otwarte ? (
        <ul
          id={`${id}-menu`}
          role="menu"
          aria-label={label}
          className={cx(
            "ui-wysuw absolute overflow-auto rounded-lg border border-line bg-raised shadow-medium",
            align === "end" ? "end-0" : "start-0",
            side === "top" ? "bottom-full" : "top-full",
          )}
          style={{
            zIndex: "var(--z-dropdown)",
            marginBlock: "var(--space-1)",
            padding: "var(--space-1)",
            minInlineSize: "var(--layout-menu-min)",
            maxBlockSize: "var(--layout-panel)",
          }}
        >
          {items.map((wpis, index) => {
            if ("type" in wpis && wpis.type === "separator") {
              return <li key={`linia-${index}`} role="separator" className="border-t border-line" style={{ margin: "var(--space-1) 0" }} />;
            }
            if ("type" in wpis && wpis.type === "group") {
              return (
                <li key={wpis.label} role="none">
                  <p
                    className="text-subtle"
                    style={{ font: "var(--text-style-overline)", letterSpacing: "var(--font-letter-spacing-caps)", padding: "var(--space-2) var(--space-2) var(--space-1)" }}
                  >
                    {wpis.label}
                  </p>
                  <ul role="group" aria-label={wpis.label}>
                    {wpis.items.map(wiersz)}
                  </ul>
                </li>
              );
            }
            return wiersz(wpis as MenuItem);
          })}
        </ul>
      ) : null}
    </div>
  );
}
