// Przycisk i przycisk-ikona (ui-kit, rozdz. 2.1 i 2.2).
// Wariant `ai` używa Aurory chłodnej — wyłącznie dla pracy asystenta.

import { forwardRef, type ButtonHTMLAttributes, type MouseEvent, type ReactNode } from "react";
import { Kbd } from "./Kbd";
import { Spinner } from "./Progress";
import { Tooltip } from "./Tooltip";
import {
  ariaKeyshortcuts,
  CONTROL_FONT,
  CONTROL_HEIGHT,
  CONTROL_INLINE,
  cx,
  ICON_SIZE,
  type BaseProps,
  type ControlSize,
  type IconSlot,
  type Shortcut,
} from "./types";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive" | "ai";

const WARIANT: Record<ButtonVariant, string> = {
  primary: "bg-accent-fill text-on-accent shadow-soft hover:bg-accent-fill-hover",
  secondary: "border border-line-strong bg-raised text-fg shadow-soft hover:bg-hover",
  ghost: "text-muted hover:bg-hover hover:text-fg",
  destructive: "bg-danger-fill text-on-accent shadow-soft hover:bg-danger-fill-hover",
  ai: "ui-warstwa aurora-chlodna text-on-accent glow-ai",
};

export interface ButtonProps extends BaseProps, Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "type" | "children"> {
  variant?: ButtonVariant;
  size?: ControlSize;
  iconStart?: IconSlot;
  iconEnd?: IconSlot;
  shortcut?: Shortcut;
  loading?: boolean;
  /** Etykieta w formie ciągłej, np. „Zapisuję”. */
  loadingLabel?: string;
  disabled?: boolean;
  /** Powód wyłączenia — przycisk zostaje w kolejności tabulacji z aria-disabled. */
  disabledReason?: string;
  fullWidth?: boolean;
  type?: "button" | "submit";
  children: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    size = "md",
    iconStart,
    iconEnd,
    shortcut,
    loading = false,
    loadingLabel,
    disabled = false,
    disabledReason,
    fullWidth = false,
    type = "button",
    className,
    children,
    onClick,
    ...reszta
  },
  ref,
) {
  const miekkoWylaczony = disabled && Boolean(disabledReason);
  const nieczynny = disabled || loading;

  const przycisk = (
    <button
      ref={ref}
      type={type}
      className={cx(
        "ui-kontrolka ui-przejscie ui-nacisk inline-flex shrink-0 items-center justify-center font-medium",
        size === "xs" || size === "sm" ? "rounded-sm" : "rounded-md",
        WARIANT[variant],
        fullWidth && "w-full",
        className,
      )}
      style={{
        blockSize: CONTROL_HEIGHT[size],
        paddingInline: CONTROL_INLINE[size],
        gap: "var(--space-2)",
        fontSize: CONTROL_FONT[size],
      }}
      disabled={disabled && !miekkoWylaczony ? true : undefined}
      aria-disabled={nieczynny ? true : undefined}
      aria-busy={loading ? true : undefined}
      aria-keyshortcuts={shortcut ? ariaKeyshortcuts(shortcut) : undefined}
      onClick={(zdarzenie: MouseEvent<HTMLButtonElement>) => {
        if (nieczynny) {
          zdarzenie.preventDefault();
          return;
        }
        onClick?.(zdarzenie);
      }}
      {...reszta}
    >
      {loading ? <Spinner size={size === "xl" ? "md" : "sm"} /> : iconStart}
      <span>{loading && loadingLabel ? loadingLabel : children}</span>
      {shortcut && !loading ? <Kbd keys={shortcut} variant={variant === "secondary" || variant === "ghost" ? "default" : "on-accent"} /> : null}
      {iconEnd}
    </button>
  );

  return disabledReason ? <Tooltip content={disabledReason}>{przycisk}</Tooltip> : przycisk;
});

export interface IconButtonProps extends Omit<ButtonProps, "children" | "iconStart" | "iconEnd" | "loadingLabel" | "fullWidth"> {
  icon: IconSlot;
  /** aria-label i treść dymka — czasownik po polsku. */
  label: string;
  /** Tryb przełącznika narzędzia. */
  pressed?: boolean;
  tooltipSide?: "top" | "right" | "bottom" | "left";
  /** Dymek pomijany, gdy nazwa jest już widoczna obok. */
  hideTooltip?: boolean;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  {
    icon,
    label,
    pressed,
    tooltipSide = "top",
    hideTooltip = false,
    variant = "ghost",
    size = "md",
    shortcut,
    loading = false,
    disabled = false,
    disabledReason,
    className,
    ...reszta
  },
  ref,
) {
  const bok = CONTROL_HEIGHT[size];

  const przycisk = (
    <button
      ref={ref}
      type="button"
      className={cx(
        "ui-kontrolka ui-przejscie ui-nacisk ui-cel-dotyku relative inline-grid shrink-0 place-items-center",
        size === "xs" || size === "sm" ? "rounded-sm" : "rounded-md",
        pressed ? "bg-accent-soft text-accent" : WARIANT[variant],
        className,
      )}
      style={{ inlineSize: bok, blockSize: bok }}
      aria-label={label}
      aria-pressed={pressed}
      aria-busy={loading ? true : undefined}
      aria-disabled={disabled || loading ? true : undefined}
      disabled={disabled || undefined}
      aria-keyshortcuts={shortcut ? ariaKeyshortcuts(shortcut) : undefined}
      {...reszta}
    >
      {loading ? <Spinner size="sm" /> : <span style={{ display: "grid", inlineSize: `${ICON_SIZE[size]}px` }}>{icon}</span>}
    </button>
  );

  return hideTooltip ? (
    przycisk
  ) : (
    <Tooltip content={disabledReason ?? label} shortcut={shortcut} side={tooltipSide}>
      {przycisk}
    </Tooltip>
  );
});
