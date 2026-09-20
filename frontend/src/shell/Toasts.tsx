// Krótkie powiadomienia w aplikacji (np. zadanie zakończone w innej rozmowie).

import { useEffect } from "react";
import { CheckIcon, CloseIcon } from "../components/icons";
import { NagranieStartu, ograniczonyRuch } from "../ruch";

export interface Toast {
  id: string;
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
}

const LIFETIME_MS = 9000;

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(toast.id), LIFETIME_MS);
    return () => window.clearTimeout(timer);
  }, [toast.id, onDismiss]);
  return (
    <div role="status" className="pointer-events-auto flex w-full animate-rise items-start gap-3 rounded-2xl border border-line bg-side px-4 py-3 shadow-2xl shadow-black/30">
      {/* Zakończone zadanie ma w pakiecie ruchu własne ujęcie (moment-sukces); przy
          ograniczonym ruchu zostaje znacznik. */}
      {ograniczonyRuch() ? (
        <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
          <CheckIcon size={14} />
        </span>
      ) : (
        <NagranieStartu nazwa="moment-sukces" className="mt-0.5 size-6 shrink-0 object-contain" />
      )}
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{toast.title}</div>
        <div className="truncate text-sm text-muted">{toast.body}</div>
        {toast.onAction && (
          <button
            type="button"
            className="mt-1.5 text-sm font-medium text-accent hover:underline"
            onClick={() => {
              toast.onAction?.();
              onDismiss(toast.id);
            }}
          >
            {toast.actionLabel ?? "Otwórz"}
          </button>
        )}
      </div>
      <button type="button" className="icon-btn size-7" onClick={() => onDismiss(toast.id)} aria-label="Zamknij powiadomienie">
        <CloseIcon size={14} />
      </button>
    </div>
  );
}

export function Toasts({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  if (!toasts.length) return null;
  return (
    <div className="pointer-events-none fixed inset-x-3 top-3 z-[60] flex flex-col gap-2 md:inset-x-auto md:top-auto md:right-4 md:bottom-4 md:w-[360px]">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
