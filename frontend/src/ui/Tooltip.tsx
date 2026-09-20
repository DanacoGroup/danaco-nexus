// Dymek podpowiedzi (ui-kit, rozdz. 7.4): nazwa i skrót dla elementu bez etykiety.
// W obu motywach ciemny — to wyjątek opisany w specyfikacji.

import { cloneElement, isValidElement, useEffect, useId, useRef, useState, type ReactElement, type ReactNode } from "react";
import { Kbd } from "./Kbd";
import { cx, tokenMs, type BaseProps, type Shortcut } from "./types";

export interface TooltipProps extends BaseProps {
  content: string;
  shortcut?: Shortcut;
  side?: "top" | "right" | "bottom" | "left";
  delayMs?: number;
  children: ReactNode;
}

const UMIEJSCOWIENIE: Record<NonNullable<TooltipProps["side"]>, string> = {
  top: "bottom-full left-1/2 -translate-x-1/2",
  bottom: "top-full left-1/2 -translate-x-1/2",
  left: "right-full top-1/2 -translate-y-1/2",
  right: "left-full top-1/2 -translate-y-1/2",
};

/** Kolejny dymek w ciągu --delay-tooltip-skip pojawia się bez zwłoki. */
let ostatnieZamkniecie = 0;

export function Tooltip({ content, shortcut, side = "top", delayMs, children, className, ...reszta }: TooltipProps) {
  const id = useId();
  const [otwarty, setOtwarty] = useState(false);
  const zegar = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => void (zegar.current && clearTimeout(zegar.current)), []);

  const pokaz = (natychmiast: boolean) => {
    const pominiecie = tokenMs("--delay-tooltip-skip") ?? 0;
    const zwloka = natychmiast || Date.now() - ostatnieZamkniecie < pominiecie ? 0 : (delayMs ?? tokenMs("--delay-tooltip") ?? 0);
    if (zegar.current) clearTimeout(zegar.current);
    if (zwloka <= 0) {
      setOtwarty(true);
      return;
    }
    zegar.current = setTimeout(() => setOtwarty(true), zwloka);
  };
  const ukryj = () => {
    if (zegar.current) clearTimeout(zegar.current);
    if (otwarty) ostatnieZamkniecie = Date.now();
    setOtwarty(false);
  };

  const dziecko = isValidElement(children)
    ? cloneElement(children as ReactElement<{ "aria-describedby"?: string }>, { "aria-describedby": otwarty ? id : undefined })
    : children;

  return (
    <span
      className={cx("relative inline-flex", className)}
      onPointerEnter={() => pokaz(false)}
      onPointerLeave={ukryj}
      onFocusCapture={() => pokaz(true)}
      onBlurCapture={ukryj}
      onKeyDown={(zdarzenie) => zdarzenie.key === "Escape" && ukryj()}
      {...reszta}
    >
      {dziecko}
      {otwarty ? (
        <span
          id={id}
          role="tooltip"
          className={cx(
            "ui-dymek pointer-events-none absolute w-max rounded-sm bg-[color:var(--color-neutral-800)] text-[color:var(--color-neutral-50)] shadow-medium",
            UMIEJSCOWIENIE[side],
          )}
          style={{
            zIndex: "var(--z-tooltip)",
            padding: "var(--space-1) var(--space-2)",
            font: "var(--text-style-caption)",
            maxInlineSize: "var(--layout-tooltip-max)",
            margin: "var(--space-1)",
          }}
        >
          <span className="inline-flex items-center" style={{ gap: "var(--space-2)" }}>
            {content}
            {shortcut ? <Kbd keys={shortcut} variant="inverse" /> : null}
          </span>
        </span>
      ) : null}
    </span>
  );
}
