// Wspólne elementy interfejsu modułów twórczych: nagłówek, przełącznik, wybór pliku, komunikaty.

import { useRef, useState, type ReactNode } from "react";
import { uploadFile, type FileInfo } from "../../api";
import { CloseIcon } from "../../components/icons";
import { UploadIcon } from "./icons";

export const buttonPrimary =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50";
export const buttonSecondary =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-line px-3.5 py-2 text-sm font-medium transition-colors hover:bg-hover disabled:cursor-not-allowed disabled:opacity-50";
export const inputClass =
  "w-full rounded-xl border border-line bg-app px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted focus:border-accent";
export const labelClass = "mb-1 block text-xs font-medium tracking-wide text-muted uppercase";

export function ModuleHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <header className="safe-top flex flex-wrap items-center gap-3 border-b border-line/60 px-4 py-3 md:px-6">
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-lg font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="truncate text-sm text-muted">{subtitle}</p>}
      </div>
      {children}
    </header>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string; icon?: ReactNode }[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-xl border border-line bg-raised/60 p-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors ${
            option.value === value ? "bg-app font-medium text-fg shadow-sm" : "text-muted hover:text-fg"
          }`}
          onClick={() => onChange(option.value)}
        >
          {option.icon}
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function ErrorBanner({ text, onClose }: { text: string; onClose: () => void }) {
  if (!text) return null;
  return (
    <div role="alert" className="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
      <span className="flex-1">{text}</span>
      <button type="button" className="shrink-0 opacity-70 hover:opacity-100" onClick={onClose} aria-label="Zamknij">
        <CloseIcon size={16} />
      </button>
    </div>
  );
}

/** Pole wyboru pliku (klik lub upuszczenie) z przesyłaniem na serwer i paskiem postępu. */
export function FileDrop({
  accept,
  hint,
  onUploaded,
  onError,
  compact = false,
}: {
  accept: string;
  hint: string;
  onUploaded: (file: FileInfo) => void;
  onError: (message: string) => void;
  compact?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [over, setOver] = useState(false);

  const upload = (file: File | undefined) => {
    if (!file) return;
    setProgress(0);
    uploadFile(file, null, setProgress)
      .promise.then(onUploaded)
      .catch((failure: Error) => onError(failure.message))
      .finally(() => setProgress(null));
  };

  return (
    <div
      className={`relative flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed text-center transition-colors ${
        over ? "border-accent bg-accent-soft/60" : "border-line hover:border-line-strong"
      } ${compact ? "px-4 py-4" : "px-6 py-10"}`}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        upload(event.dataTransfer.files[0]);
      }}
    >
      <UploadIcon size={compact ? 20 : 28} className="text-muted" />
      <p className="text-sm text-muted">{hint}</p>
      <button type="button" className={buttonSecondary} onClick={() => input.current?.click()} disabled={progress !== null}>
        {progress !== null ? `Przesyłanie… ${Math.round(progress * 100)}%` : "Wybierz plik"}
      </button>
      <input
        ref={input}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(event) => {
          upload(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      {progress !== null && (
        <div className="absolute inset-x-4 bottom-2 h-1 overflow-hidden rounded-full bg-line">
          <div className="h-full bg-accent transition-all" style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      )}
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted" role="status">
      <span className="spinner" />
      {label}
    </span>
  );
}
