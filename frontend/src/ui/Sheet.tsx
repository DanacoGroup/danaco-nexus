// Panel wysuwany (szuflada) na natywnym <dialog>. Wersja modalna dla telefonu
// i panelu bocznego; ruch zgodny z motion, rozdz. 13 (lista → szczegół).

import { useEffect, useRef, useId, type ReactNode } from "react";
import { IconButton } from "./Button";
import { CloseIcon } from "./Icons";
import { cx, type BaseProps } from "./types";

export type SheetSide = "right" | "left" | "bottom";

export interface SheetProps extends BaseProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  side?: SheetSide;
  /** Szerokość panelu bocznego; token --layout-panel albo --layout-panel-wide. */
  width?: string;
  footer?: ReactNode;
  children?: ReactNode;
}

const POLOZENIE: Record<SheetSide, string> = {
  right: "ui-szuflada-prawo ms-auto h-full rounded-s-xl",
  left: "ui-szuflada-lewo me-auto h-full rounded-e-xl",
  bottom: "ui-szuflada-dol mt-auto w-full rounded-t-xl",
};

export function Sheet({ open, onOpenChange, title, side = "right", width = "var(--layout-panel)", footer, className, children, ...reszta }: SheetProps) {
  const id = useId();
  const okno = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = okno.current;
    if (!element) return;
    if (open && !element.open) {
      if (typeof element.showModal === "function") element.showModal();
      else element.setAttribute("open", "");
    }
    if (!open && element.open) element.close();
  }, [open]);

  return (
    <dialog
      ref={okno}
      className={cx("ui-okno ui-szuflada h-full max-h-full w-full max-w-full", className)}
      aria-labelledby={`${id}-tytul`}
      onCancel={(zdarzenie) => {
        zdarzenie.preventDefault();
        onOpenChange(false);
      }}
      onClick={(zdarzenie) => zdarzenie.target === okno.current && onOpenChange(false)}
      {...reszta}
    >
      <div
        className={cx("flex flex-col border border-line bg-raised shadow-floating", POLOZENIE[side])}
        style={{
          inlineSize: side === "bottom" ? "100%" : `min(${width}, calc(100vw - var(--space-8)))`,
          blockSize: side === "bottom" ? "auto" : "100%",
          maxBlockSize: "100%",
        }}
      >
        <div
          className="flex items-center justify-between border-b border-line"
          style={{ padding: "var(--space-4) var(--space-6)", gap: "var(--space-3)" }}
        >
          <h2 id={`${id}-tytul`} className="font-heading text-fg" style={{ fontSize: "var(--font-size-lg)", fontWeight: "var(--font-weight-semibold)" }}>
            {title}
          </h2>
          <IconButton icon={<CloseIcon />} label="Zamknij panel" size="sm" onClick={() => onOpenChange(false)} />
        </div>
        <div className="flex-1 overflow-auto" style={{ padding: "var(--space-role-inset-panel)" }}>
          {children}
        </div>
        {footer ? (
          <div className="border-t border-line" style={{ padding: "var(--space-4) var(--space-6)" }}>
            {footer}
          </div>
        ) : null}
      </div>
    </dialog>
  );
}
