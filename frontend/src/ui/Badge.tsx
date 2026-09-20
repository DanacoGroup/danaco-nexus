// Znacznik stanu (ui-kit, rozdz. 9.1) i etykieta interaktywna (rozdz. 9.2).

import type { ReactNode } from "react";
import { IconButton } from "./Button";
import { CloseIcon } from "./Icons";
import { Spinner } from "./Progress";
import { cx, TONE_SOFT, type BaseProps, type IconSlot, type Tone } from "./types";

export interface BadgeProps extends BaseProps {
  tone?: Tone;
  icon?: IconSlot;
  dot?: boolean;
  /** Wariant licznika; powyżej 99 pokazuje „99+”. */
  count?: number;
  loading?: boolean;
  children?: ReactNode;
}

export function Badge({ tone = "neutral", icon, dot, count, loading, className, children, ...reszta }: BadgeProps) {
  if (typeof count === "number") {
    return (
      <span
        className={cx("inline-grid place-items-center rounded-full bg-accent-fill text-on-accent", className)}
        style={{
          minInlineSize: "var(--space-5)",
          blockSize: "var(--space-5)",
          paddingInline: "var(--space-1)",
          font: "var(--text-style-caption)",
          fontVariantNumeric: "var(--font-numeric-tabular)",
        }}
        {...reszta}
      >
        {count > 99 ? "99+" : count}
      </span>
    );
  }

  return (
    <span
      className={cx("inline-flex items-center rounded-full font-medium", TONE_SOFT[tone], className)}
      style={{
        blockSize: "var(--space-5)",
        paddingInline: "var(--space-2)",
        gap: "var(--space-1)",
        font: "var(--text-style-caption)",
        boxShadow: tone === "ai" ? "inset 0 0 0 var(--border-width-thin) var(--color-brand-iris)" : undefined,
      }}
      {...reszta}
    >
      {loading ? <Spinner size="sm" className="scale-75" /> : icon}
      {dot && !icon && !loading ? (
        <span className="rounded-full bg-current" style={{ inlineSize: "calc(var(--space-1) + var(--space-0-5))", blockSize: "calc(var(--space-1) + var(--space-0-5))" }} />
      ) : null}
      {children}
    </span>
  );
}

export interface TagProps extends BaseProps {
  label: string;
  icon?: IconSlot;
  /** Filtr lub narzędzie włączone. */
  active?: boolean;
  onClick?: () => void;
  onRemove?: () => void;
  removeLabel?: string;
  disabled?: boolean;
}

export function Tag({ label, icon, active = false, onClick, onRemove, removeLabel, disabled = false, className, ...reszta }: TagProps) {
  return (
    <span
      className={cx(
        "ui-przejscie inline-flex items-center rounded-sm border",
        active ? "border-accent bg-accent-soft text-accent" : "border-line-strong bg-raised text-fg",
        className,
      )}
      style={{ blockSize: "var(--control-xs)", paddingInline: "var(--space-2)", gap: "var(--space-1)" }}
      {...reszta}
    >
      <button
        type="button"
        onClick={onClick}
        onKeyDown={(zdarzenie) => {
          if (zdarzenie.key === "Backspace" && onRemove) onRemove();
        }}
        aria-pressed={onClick ? active : undefined}
        aria-disabled={disabled || undefined}
        disabled={disabled || undefined}
        className="ui-kontrolka inline-flex items-center bg-transparent"
        style={{ gap: "var(--space-1)", font: "var(--text-style-label)" }}
      >
        {icon ? <span className={cx("grid", active ? "text-accent" : "text-subtle")}>{icon}</span> : null}
        {label}
      </button>
      {onRemove ? (
        <IconButton
          icon={<CloseIcon size={14} />}
          label={removeLabel ?? `Usuń: ${label}`}
          size="xs"
          hideTooltip
          onClick={onRemove}
          disabled={disabled}
        />
      ) : null}
    </span>
  );
}
