// Szkielet treści (ui-kit, rozdz. 9.6). Zawsze aria-hidden; region nadrzędny ogłasza
// wczytywanie przez aria-busy.

import { cx, type BaseProps } from "./types";

export interface SkeletonProps extends BaseProps {
  shape?: "text" | "circle" | "rect";
  width?: string;
  height?: string;
  /** Liczba wierszy dla kształtu „text”. */
  lines?: number;
}

const SZEROKOSCI = ["92%", "76%", "84%", "60%"];

export function Skeleton({ shape = "text", width, height, lines = 1, className, ...reszta }: SkeletonProps) {
  if (shape === "text" && lines > 1) {
    return (
      <div className={cx("flex w-full flex-col", className)} style={{ gap: "var(--space-2)" }} aria-hidden="true" {...reszta}>
        {Array.from({ length: lines }, (_, index) => (
          <span
            key={index}
            className="ui-szkielet block rounded-sm"
            style={{ inlineSize: width ?? SZEROKOSCI[index % SZEROKOSCI.length], blockSize: height ?? "var(--space-3)" }}
          />
        ))}
      </div>
    );
  }

  return (
    <span
      aria-hidden="true"
      className={cx("ui-szkielet block", shape === "circle" ? "rounded-full" : "rounded-sm", className)}
      style={{
        inlineSize: width ?? (shape === "circle" ? "var(--space-8)" : "100%"),
        blockSize: height ?? (shape === "circle" ? "var(--space-8)" : "var(--space-3)"),
      }}
      {...reszta}
    />
  );
}
