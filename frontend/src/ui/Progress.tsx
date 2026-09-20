// Postęp i wskaźniki oczekiwania (ui-kit, rozdz. 9.5).

import { cx, type BaseProps } from "./types";

export interface SpinnerProps extends BaseProps {
  size?: "sm" | "md";
  tone?: "current" | "ai";
  /** Nazwa dostępna; bez niej wskaźnik jest dekoracyjny (aria-hidden). */
  label?: string;
}

export function Spinner({ size = "sm", tone = "current", label, className, ...reszta }: SpinnerProps) {
  const bok = size === "sm" ? "var(--icon-size-sm)" : "var(--icon-size-md)";
  return (
    <span
      className={cx("inline-block shrink-0 animate-spin rounded-full border-r-transparent", tone === "ai" && "text-iris", className)}
      style={{
        inlineSize: bok,
        blockSize: bok,
        borderWidth: "var(--border-width-thick)",
        borderColor: "currentColor",
        borderRightColor: "transparent",
        opacity: 0.8,
      }}
      role={label ? "status" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      {...reszta}
    />
  );
}

export interface ProgressProps extends BaseProps {
  /** 0–1; brak wartości = postęp nieokreślony. */
  value?: number;
  tone?: "default" | "ai" | "success" | "danger";
  label?: string;
  valueText?: string;
}

const WYPELNIENIE: Record<NonNullable<ProgressProps["tone"]>, string> = {
  default: "bg-accent-fill",
  ai: "aurora-chlodna",
  success: "bg-success",
  danger: "bg-danger",
};

export function Progress({ value, tone = "default", label, valueText, className, ...reszta }: ProgressProps) {
  const okreslony = typeof value === "number";
  const procent = okreslony ? Math.round(Math.min(Math.max(value, 0), 1) * 100) : undefined;

  return (
    <div className={cx("flex w-full flex-col", className)} style={{ gap: "var(--space-1)" }} {...reszta}>
      {label ? (
        <span className="text-muted" style={{ font: "var(--text-style-caption)" }}>
          {label}
        </span>
      ) : null}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={procent}
        aria-valuetext={valueText}
        aria-label={label ? undefined : (valueText ?? "Postęp")}
        className="relative w-full overflow-hidden rounded-full bg-hover"
        style={{ blockSize: "var(--space-1)" }}
      >
        {okreslony ? (
          <div
            className={cx("ui-przejscie-tresc block h-full rounded-full", WYPELNIENIE[tone])}
            style={{ inlineSize: `${procent}%` }}
          />
        ) : (
          <span className="ui-pasek-nieokreslony" />
        )}
      </div>
    </div>
  );
}

export interface ProgressRingProps extends BaseProps {
  /** 0–1. */
  value: number;
  size?: 16 | 20 | 24;
  label: string;
}

export function ProgressRing({ value, size = 20, label, className, ...reszta }: ProgressRingProps) {
  const czesc = Math.min(Math.max(value, 0), 1);
  const promien = (size - 3) / 2;
  const obwod = 2 * Math.PI * promien;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(czesc * 100)}
      aria-label={label}
      className={cx("shrink-0", className)}
      {...reszta}
    >
      <circle cx={size / 2} cy={size / 2} r={promien} fill="none" stroke="var(--hover)" strokeWidth={3} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={promien}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={3}
        strokeLinecap="round"
        strokeDasharray={`${obwod * czesc} ${obwod}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  );
}
