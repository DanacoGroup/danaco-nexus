// Pusty stan — zawsze z następnym krokiem (ui-kit, rozdz. 9.7).

import { Button } from "./Button";
import { ErrorIcon, FolderIcon, SearchIcon, SparkleIcon } from "./Icons";
import { cx, type BaseProps, type IconSlot } from "./types";

export type EmptyStateVariant = "empty" | "no-results" | "error" | "first-run";

export interface EmptyStateAction {
  label: string;
  icon?: IconSlot;
  onSelect: () => void;
}

export interface EmptyStateProps extends BaseProps {
  variant?: EmptyStateVariant;
  icon?: IconSlot;
  title: string;
  description?: string;
  /** Poziom nagłówka dopasowany do widoku. */
  headingLevel?: 2 | 3 | 4;
  primaryAction?: EmptyStateAction;
  secondaryAction?: EmptyStateAction;
  aiAction?: EmptyStateAction;
}

const IKONA: Record<EmptyStateVariant, IconSlot> = {
  empty: <FolderIcon size={24} />,
  "no-results": <SearchIcon size={24} />,
  error: <ErrorIcon size={24} />,
  "first-run": <SparkleIcon size={24} />,
};

export function EmptyState({
  variant = "empty",
  icon,
  title,
  description,
  headingLevel = 3,
  primaryAction,
  secondaryAction,
  aiAction,
  className,
  ...reszta
}: EmptyStateProps) {
  const Naglowek = `h${headingLevel}` as "h2" | "h3" | "h4";

  return (
    <div
      className={cx("flex flex-col items-center text-center", className)}
      style={{ padding: "var(--space-8) var(--space-6)", gap: "var(--space-3)" }}
      role={variant === "error" ? "alert" : undefined}
      {...reszta}
    >
      <span
        className={cx("grid place-items-center rounded-lg border border-line bg-side", variant === "error" ? "text-danger" : "text-muted")}
        style={{ inlineSize: "calc(var(--space-12) + var(--space-2))", blockSize: "calc(var(--space-12) + var(--space-2))" }}
      >
        {icon ?? IKONA[variant]}
      </span>
      <Naglowek className="text-fg" style={{ font: "var(--text-style-title)", fontSize: "var(--font-size-base)" }}>
        {title}
      </Naglowek>
      {description ? (
        <p className="text-muted" style={{ font: "var(--text-style-body)", maxInlineSize: "var(--layout-panel)" }}>
          {description}
        </p>
      ) : null}
      {primaryAction || secondaryAction || aiAction ? (
        <div className="flex flex-wrap items-center justify-center" style={{ gap: "var(--space-2)", marginBlockStart: "var(--space-2)" }}>
          {primaryAction ? (
            <Button variant="primary" iconStart={primaryAction.icon} onClick={primaryAction.onSelect}>
              {primaryAction.label}
            </Button>
          ) : null}
          {secondaryAction ? (
            <Button variant="secondary" iconStart={secondaryAction.icon} onClick={secondaryAction.onSelect}>
              {secondaryAction.label}
            </Button>
          ) : null}
          {aiAction ? (
            <Button variant="ai" iconStart={<SparkleIcon />} onClick={aiAction.onSelect}>
              {aiAction.label}
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
