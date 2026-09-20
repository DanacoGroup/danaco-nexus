// Wspólne elementy interfejsu modułów biura: okno dialogowe, potwierdzenie, komunikaty, pusty stan.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { CloseIcon } from "../../components/icons";

export function Modal({
  title,
  onClose,
  children,
  footer,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const first = panel.current?.querySelector<HTMLElement>("input, textarea, select, button[data-autofocus]");
    first?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        ref={panel}
        className={`safe-bottom flex max-h-[92dvh] w-full animate-rise flex-col overflow-hidden rounded-t-2xl border border-line bg-app shadow-2xl sm:rounded-2xl ${
          wide ? "sm:max-w-2xl" : "sm:max-w-md"
        }`}
      >
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <h2 className="min-w-0 flex-1 truncate text-[15px] font-semibold">{title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Zamknij">
            <CloseIcon />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-4 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export const buttonClass = {
  primary:
    "inline-flex items-center justify-center gap-2 rounded-xl bg-accent-fill px-4 py-2 text-sm font-medium text-on-accent transition-colors hover:bg-accent-fill-hover disabled:opacity-50",
  secondary:
    "inline-flex items-center justify-center gap-2 rounded-xl border border-line px-4 py-2 text-sm font-medium transition-colors hover:bg-hover disabled:opacity-50",
  danger:
    "inline-flex items-center justify-center gap-2 rounded-xl bg-danger px-4 py-2 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:opacity-50",
  ghost:
    "inline-flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm text-muted transition-colors hover:bg-hover hover:text-fg disabled:opacity-40",
};

export const inputClass =
  "w-full rounded-xl border border-line bg-raised px-3 py-2 text-sm text-fg outline-none transition-colors placeholder:text-muted focus:border-accent";

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="block text-xs font-medium text-muted">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted">{hint}</span>}
    </label>
  );
}

export function ErrorBanner({ message, onClose }: { message: string; onClose?: () => void }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger-soft px-3 py-2.5 text-sm text-danger"
    >
      <span className="min-w-0 flex-1">{message}</span>
      {onClose && (
        <button type="button" className="shrink-0 opacity-70 hover:opacity-100" onClick={onClose} aria-label="Ukryj">
          <CloseIcon size={16} />
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-4 grid size-14 place-items-center rounded-2xl bg-raised text-muted">{icon}</div>
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <div className="mt-1.5 max-w-sm text-sm text-muted">{children}</div>}
    </div>
  );
}

export function Loading({ label = "Wczytywanie…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted">
      <span className="spinner" /> {label}
    </div>
  );
}

interface ConfirmRequest {
  title: string;
  message: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  resolve: (value: boolean) => void;
}

/** Okno potwierdzenia jako obietnica: `if (await confirm({...})) …`. */
export function useConfirm(): [
  (options: Omit<ConfirmRequest, "resolve">) => Promise<boolean>,
  ReactNode,
] {
  const [request, setRequest] = useState<ConfirmRequest | null>(null);
  const ask = useCallback(
    (options: Omit<ConfirmRequest, "resolve">) =>
      new Promise<boolean>((resolve) => setRequest({ ...options, resolve })),
    [],
  );
  const finish = (value: boolean) => {
    request?.resolve(value);
    setRequest(null);
  };
  const dialog = request ? (
    <Modal
      title={request.title}
      onClose={() => finish(false)}
      footer={
        <>
          <button type="button" className={buttonClass.secondary} onClick={() => finish(false)}>
            Anuluj
          </button>
          <button
            type="button"
            data-autofocus
            className={request.danger ? buttonClass.danger : buttonClass.primary}
            onClick={() => finish(true)}
          >
            {request.confirmLabel}
          </button>
        </>
      }
    >
      <div className="text-sm leading-relaxed">{request.message}</div>
    </Modal>
  ) : null;
  return [ask, dialog];
}

/** Krótki komunikat u dołu ekranu (znika po kilku sekundach). */
export function useToast(): [(text: string) => void, ReactNode] {
  const [text, setText] = useState("");
  useEffect(() => {
    if (!text) return;
    const timer = window.setTimeout(() => setText(""), 3500);
    return () => window.clearTimeout(timer);
  }, [text]);
  const node = text ? (
    <div
      role="status"
      className="safe-bottom pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex justify-center px-4"
    >
      <div className="animate-rise rounded-xl bg-fg px-4 py-2.5 text-sm text-app shadow-lg">{text}</div>
    </div>
  ) : null;
  return [setText, node];
}

/** Kopiuje tekst do schowka (z zapasową metodą dla starszych przeglądarek). */
export async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}
