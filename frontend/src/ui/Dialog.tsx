// Okno dialogowe na natywnym <dialog> (ui-kit, rozdz. 7.1). Pułapka fokusu, Esc
// i zasłona pochodzą od przeglądarki — bez biblioteki zewnętrznej.

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Button, IconButton } from "./Button";
import { CloseIcon } from "./Icons";
import { Input } from "./Input";
import { cx, type BaseProps } from "./types";

export type DialogVariant = "confirm" | "form" | "destructive" | "preview";

export interface DialogProps extends BaseProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  variant?: DialogVariant;
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm?: () => void | Promise<void>;
  /** Wymusza wpisanie słowa przed potwierdzeniem, np. „usuń”. */
  confirmPhrase?: string;
  /** Formularz ze zmianami — kliknięcie w zasłonę nie zamyka okna. */
  dirty?: boolean;
  footerHint?: ReactNode;
  children?: ReactNode;
}

const SZEROKOSC: Record<DialogVariant, string> = {
  confirm: "var(--layout-dialog-sm)",
  destructive: "var(--layout-dialog-sm)",
  form: "var(--layout-dialog-md)",
  preview: "var(--layout-dialog-lg)",
};

export function Dialog({
  open,
  onOpenChange,
  variant = "confirm",
  title,
  description,
  icon,
  confirmLabel,
  cancelLabel = "Anuluj",
  onConfirm,
  confirmPhrase,
  dirty = false,
  footerHint,
  className,
  children,
  ...reszta
}: DialogProps) {
  const id = useId();
  const okno = useRef<HTMLDialogElement>(null);
  const [fraza, setFraza] = useState("");
  const [wysyla, setWysyla] = useState(false);

  useEffect(() => {
    const element = okno.current;
    if (!element) return;
    if (open && !element.open) {
      if (typeof element.showModal === "function") element.showModal();
      else element.setAttribute("open", "");
      element.querySelector<HTMLElement>("[data-ui-autofokus]")?.focus();
    }
    if (!open && element.open) element.close();
    if (!open) setFraza("");
  }, [open]);

  const potwierdz = () => {
    if (!onConfirm) return;
    const wynik = onConfirm();
    if (wynik instanceof Promise) {
      setWysyla(true);
      void wynik.finally(() => setWysyla(false));
    }
  };

  const zablokowane = Boolean(confirmPhrase) && fraza.trim().toLowerCase() !== confirmPhrase?.toLowerCase();
  const alarmowe = variant === "confirm" || variant === "destructive";
  const zamykalneZaslona = variant === "confirm" || variant === "preview" ? !dirty : false;

  return (
    <dialog
      ref={okno}
      className={cx("ui-okno", className)}
      role={alarmowe ? "alertdialog" : undefined}
      aria-labelledby={`${id}-tytul`}
      aria-describedby={description ? `${id}-opis` : undefined}
      onCancel={(zdarzenie) => {
        zdarzenie.preventDefault();
        onOpenChange(false);
      }}
      onClick={(zdarzenie) => {
        if (zamykalneZaslona && zdarzenie.target === okno.current) onOpenChange(false);
      }}
      onKeyDown={(zdarzenie) => {
        if (variant === "form" && zdarzenie.key === "Enter" && (zdarzenie.ctrlKey || zdarzenie.metaKey)) potwierdz();
      }}
      {...reszta}
    >
      <div
        className="ui-okno-panel flex flex-col rounded-xl border border-line bg-raised shadow-floating"
        style={{ inlineSize: `min(${SZEROKOSC[variant]}, calc(100vw - var(--space-8)))`, maxBlockSize: "calc(100vh - var(--space-16))" }}
      >
        <div className="flex items-start justify-between" style={{ padding: "var(--space-6)", gap: "var(--space-3)" }}>
          <div className="flex items-start" style={{ gap: "var(--space-3)" }}>
            {icon ? (
              <span
                className={cx("grid place-items-center rounded-md", variant === "destructive" ? "bg-danger-soft text-danger" : "bg-accent-soft text-accent")}
                style={{ inlineSize: "var(--control-md)", blockSize: "var(--control-md)" }}
              >
                {icon}
              </span>
            ) : null}
            <h2 id={`${id}-tytul`} className="font-heading text-fg" style={{ fontSize: "var(--font-size-lg)", fontWeight: "var(--font-weight-semibold)" }}>
              {title}
            </h2>
          </div>
          <IconButton icon={<CloseIcon />} label="Zamknij" size="sm" onClick={() => onOpenChange(false)} />
        </div>

        <div className="overflow-auto" style={{ padding: "0 var(--space-6) var(--space-6)", display: "grid", gap: "var(--space-4)" }}>
          {description ? (
            <div id={`${id}-opis`} className="text-muted" style={{ font: "var(--text-style-body)" }}>
              {description}
            </div>
          ) : null}
          {children}
          {confirmPhrase ? (
            <Input
              label={`Wpisz „${confirmPhrase}”, aby potwierdzić`}
              value={fraza}
              onChange={setFraza}
              autoComplete="off"
              data-ui-autofokus=""
            />
          ) : null}
        </div>

        {onConfirm ? (
          <div
            className="flex items-center justify-between border-t border-line"
            style={{ padding: "var(--space-4) var(--space-6)", gap: "var(--space-3)" }}
          >
            <span className="text-subtle" style={{ font: "var(--text-style-caption)" }}>
              {footerHint}
            </span>
            <span className="flex items-center" style={{ gap: "var(--space-2)" }}>
              <Button
                variant="secondary"
                onClick={() => onOpenChange(false)}
                disabled={wysyla}
                data-ui-autofokus={variant === "destructive" ? "" : undefined}
              >
                {cancelLabel}
              </Button>
              <Button
                variant={variant === "destructive" ? "destructive" : "primary"}
                onClick={potwierdz}
                loading={wysyla}
                disabled={zablokowane}
                disabledReason={zablokowane ? `Wpisz „${confirmPhrase}”, aby odblokować.` : undefined}
                data-ui-autofokus={variant === "confirm" ? "" : undefined}
              >
                {confirmLabel ?? "Potwierdź"}
              </Button>
            </span>
          </div>
        ) : null}
      </div>
    </dialog>
  );
}
