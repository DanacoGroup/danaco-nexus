// Dymki powiadomień (ui-kit, rozdz. 8.1): region aria-live istnieje przed pierwszym
// dymkiem, odliczanie wstrzymuje wskazanie kursorem i fokus.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Button, IconButton } from "./Button";
import { CloseIcon, ErrorIcon, InfoIcon, SuccessIcon, WarningIcon } from "./Icons";
import { Progress, Spinner } from "./Progress";
import { cx, tokenMs, TONE_TEXT, type BaseProps } from "./types";

export type ToastVariant = "success" | "error" | "warning" | "info" | "progress" | "undo";

export interface ToastOptions {
  id?: string;
  variant: ToastVariant;
  title: string;
  description?: string;
  progress?: { value?: number; label?: string };
  actions?: { label: string; onSelect: () => void }[];
  /** null = dymek zostaje do zamknięcia. */
  durationMs?: number | null;
}

interface Dymek extends ToastOptions {
  id: string;
}

export interface ToastApi {
  show: (options: ToastOptions) => string;
  update: (id: string, options: Partial<ToastOptions>) => void;
  dismiss: (id: string) => void;
}

const Kontekst = createContext<ToastApi | null>(null);

/** Token czasu widoczności; null = dymek zostaje do zamknięcia. */
const CZAS: Record<ToastVariant, string | null> = {
  success: "--delay-toast",
  error: null,
  warning: "--delay-toast-long",
  info: "--delay-toast",
  progress: null,
  undo: "--delay-toast-long",
};

const IKONA: Record<ToastVariant, ReactNode> = {
  success: <SuccessIcon size={20} />,
  error: <ErrorIcon size={20} />,
  warning: <WarningIcon size={20} />,
  info: <InfoIcon size={20} />,
  progress: <Spinner size="md" tone="ai" />,
  undo: <InfoIcon size={20} />,
};

const TON: Record<ToastVariant, keyof typeof TONE_TEXT> = {
  success: "success",
  error: "danger",
  warning: "warning",
  info: "info",
  progress: "accent",
  undo: "neutral",
};

export function useToast(): ToastApi {
  const api = useContext(Kontekst);
  if (!api) throw new Error("useToast wymaga ToastProvider w drzewie aplikacji.");
  return api;
}

export interface ToastProviderProps {
  children: ReactNode;
  /** Ile dymków widać naraz; starsze są zwijane. */
  max?: number;
}

export function ToastProvider({ children, max = 3 }: ToastProviderProps) {
  const [dymki, setDymki] = useState<Dymek[]>([]);
  const licznik = useRef(0);

  const dismiss = useCallback((id: string) => setDymki((lista) => lista.filter((dymek) => dymek.id !== id)), []);

  const api = useMemo<ToastApi>(
    () => ({
      show: (options) => {
        const id = options.id ?? `dymek-${++licznik.current}`;
        setDymki((lista) => [...lista.filter((dymek) => dymek.id !== id), { ...options, id }].slice(-max));
        return id;
      },
      update: (id, options) => setDymki((lista) => lista.map((dymek) => (dymek.id === id ? { ...dymek, ...options } : dymek))),
      dismiss,
    }),
    [dismiss, max],
  );

  return (
    <Kontekst.Provider value={api}>
      {children}
      <ToastRegion toasts={dymki} onDismiss={dismiss} />
    </Kontekst.Provider>
  );
}

interface RegionProps extends BaseProps {
  toasts: Dymek[];
  onDismiss: (id: string) => void;
}

function ToastRegion({ toasts, onDismiss, className }: RegionProps) {
  return (
    <div
      role="region"
      aria-label="Powiadomienia"
      className={cx("pointer-events-none fixed flex flex-col items-end", className)}
      style={{ zIndex: "var(--z-toast)", insetInlineEnd: "var(--space-4)", insetBlockEnd: "var(--space-4)", gap: "var(--space-2)" }}
    >
      {toasts.map((dymek) => (
        <ToastItem key={dymek.id} toast={dymek} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Dymek; onDismiss: (id: string) => void }) {
  const [wstrzymany, setWstrzymany] = useState(false);
  const token = CZAS[toast.variant];
  const czas = toast.durationMs === undefined ? (token ? tokenMs(token) : null) : toast.durationMs;

  useEffect(() => {
    if (wstrzymany || czas === null) return;
    const zegar = setTimeout(() => onDismiss(toast.id), czas);
    return () => clearTimeout(zegar);
  }, [czas, onDismiss, toast.id, wstrzymany]);

  return (
    <div
      role={toast.variant === "error" ? "alert" : "status"}
      aria-live={toast.variant === "error" ? "assertive" : "polite"}
      className="ui-powiadomienie pointer-events-auto flex rounded-lg border border-line bg-raised shadow-floating"
      style={{ inlineSize: `min(var(--layout-toast), calc(100vw - var(--space-8)))`, padding: "var(--space-4)", gap: "var(--space-3)" }}
      onPointerEnter={() => setWstrzymany(true)}
      onPointerLeave={() => setWstrzymany(false)}
      onFocusCapture={() => setWstrzymany(true)}
      onBlurCapture={() => setWstrzymany(false)}
      onKeyDown={(zdarzenie) => zdarzenie.key === "Escape" && onDismiss(toast.id)}
    >
      <span className={cx("grid shrink-0", TONE_TEXT[TON[toast.variant]])}>{IKONA[toast.variant]}</span>
      <div className="flex min-w-0 flex-1 flex-col" style={{ gap: "var(--space-1)" }}>
        <p className="text-fg" style={{ font: "var(--text-style-label)" }}>
          {toast.title}
        </p>
        {toast.description ? (
          <p className="text-muted" style={{ font: "var(--text-style-body-sm)" }}>
            {toast.description}
          </p>
        ) : null}
        {toast.variant === "progress" ? (
          <Progress value={toast.progress?.value} tone="ai" valueText={toast.progress?.label} />
        ) : null}
        {toast.actions?.length ? (
          <div className="flex" style={{ gap: "var(--space-2)", marginBlockStart: "var(--space-1)" }}>
            {toast.actions.map((dzialanie) => (
              <Button key={dzialanie.label} variant="ghost" size="xs" onClick={dzialanie.onSelect}>
                {dzialanie.label}
              </Button>
            ))}
          </div>
        ) : null}
      </div>
      <IconButton icon={<CloseIcon />} label="Zamknij powiadomienie" size="xs" hideTooltip onClick={() => onDismiss(toast.id)} />
    </div>
  );
}
