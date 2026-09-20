// Klawisz skrótu (ui-kit, rozdz. 9.8). Cyfry tabelaryczne, wariant odwrócony do dymka.

import { cx, shortcutLabel, type BaseProps, type Shortcut } from "./types";

export interface KbdProps extends BaseProps {
  keys: Shortcut;
  variant?: "default" | "inverse" | "on-accent";
}

const WARIANT: Record<NonNullable<KbdProps["variant"]>, string> = {
  default: "border-line-strong bg-app text-muted",
  inverse: "border-[color:var(--color-neutral-600)] text-[color:var(--color-neutral-300)]",
  "on-accent": "border-current text-current",
};

export function Kbd({ keys, variant = "default", className, ...reszta }: KbdProps) {
  return (
    <span className={cx("inline-flex items-center", className)} style={{ gap: "var(--space-0-5)" }} {...reszta}>
      {keys.map((klawisz) => (
        <kbd
          key={klawisz}
          className={cx("inline-grid place-items-center rounded-xs border", WARIANT[variant])}
          style={{
            minInlineSize: "var(--space-5)",
            blockSize: "var(--space-5)",
            paddingInline: "var(--space-1)",
            font: "var(--text-style-caption)",
            fontVariantNumeric: "var(--font-numeric-tabular)",
          }}
        >
          {shortcutLabel([klawisz])}
        </kbd>
      ))}
    </span>
  );
}
