// Wyświetlanie tur rozmowy: wiadomości użytkownika, odpowiedzi, przemyślenia i działania narzędzi.

import { useState } from "react";
import type { AssistantTurn, FileInfo, TurnItem, UserTurn } from "../api";
import { toolLabel } from "../runState";
import { FileCard } from "./FileCard";
import { AlertIcon, CheckIcon, ChevronIcon, Logo, ToolIcon } from "./icons";
import { Markdown } from "./Markdown";

type Preview = (file: FileInfo) => void;

export function UserMessage({ turn, onPreview }: { turn: UserTurn; onPreview: Preview }) {
  return (
    <div className="flex animate-rise flex-col items-end gap-2">
      {turn.files.length > 0 && (
        <div className="flex max-w-[85%] flex-wrap justify-end gap-2">
          {turn.files.map((file) => (
            <FileCard key={file.id} file={file} onPreview={onPreview} compact />
          ))}
        </div>
      )}
      {turn.text && (
        <div className="max-w-[85%] rounded-3xl bg-bubble px-4 py-2.5 break-words whitespace-pre-wrap">{turn.text}</div>
      )}
    </div>
  );
}

function Thinking({ text, live }: { text: string; live: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="text-sm">
      <button
        type="button"
        className="inline-flex items-center gap-1.5 rounded-md py-1 text-muted transition-colors hover:text-fg"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <ChevronIcon size={15} className={`transition-transform ${open ? "rotate-90" : ""}`} />
        {live ? <span className="shimmer-text">Analizuję…</span> : "Przemyślenia"}
      </button>
      {open && <div className="mt-1 border-l-2 border-line pl-3 whitespace-pre-wrap text-muted">{text}</div>}
    </div>
  );
}

function ToolItem({ item, onPreview }: { item: Extract<TurnItem, { kind: "tool" }>; onPreview: Preview }) {
  const running = item.status === "running";
  const failed = item.status === "error" || item.status === "cancelled";
  return (
    <div
      className={`rounded-2xl border px-3.5 py-2.5 text-sm ${
        failed ? "border-danger/40 bg-danger-soft/60" : "border-line bg-raised/60"
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          className={`grid size-5 place-items-center ${failed ? "text-danger" : running ? "text-accent" : "text-success"}`}
        >
          {running ? <span className="spinner size-3.5" /> : failed ? <AlertIcon size={16} /> : <CheckIcon size={16} />}
        </span>
        <ToolIcon size={15} className="text-muted" />
        <span className={`font-medium ${running ? "shimmer-text" : ""}`}>{toolLabel(item.name)}</span>
        {!running && item.duration_ms ? (
          <span className="ml-auto text-xs text-muted tabular-nums">{(item.duration_ms / 1000).toFixed(1)} s</span>
        ) : null}
      </div>
      {(item.progress || item.summary) && (
        <div className={`mt-1 pl-7 ${failed ? "text-danger" : "text-muted"}`}>{running ? item.progress : item.summary}</div>
      )}
      {item.files.length > 0 && (
        <div className="mt-2.5 grid gap-2 pl-7 sm:grid-cols-2">
          {item.files.map((file) => (
            <FileCard key={file.id} file={file} onPreview={onPreview} />
          ))}
        </div>
      )}
    </div>
  );
}

export function AssistantMessage({ turn, onPreview }: { turn: AssistantTurn; onPreview: Preview }) {
  const live = turn.status === "running" || turn.status === "queued";
  const lastIndex = turn.items.length - 1;
  return (
    <div className="flex animate-rise gap-3">
      <Logo size={28} className="mt-0.5 shrink-0 rounded-lg" />
      <div className="min-w-0 flex-1 space-y-3">
        {turn.items.map((item, index) => {
          if (item.kind === "text") {
            return item.text ? <Markdown key={index} text={item.text} /> : null;
          }
          if (item.kind === "thinking") {
            return <Thinking key={index} text={item.text} live={live && index === lastIndex} />;
          }
          if (item.kind === "notice") {
            return (
              <div key={index} className="rounded-xl border border-line bg-raised px-3.5 py-2 text-sm text-muted">
                {item.text}
              </div>
            );
          }
          return <ToolItem key={item.tool_use_id} item={item} onPreview={onPreview} />;
        })}
        {live && turn.items.length === 0 && (
          <div className="flex h-7 items-center gap-1.5" role="status" aria-label="Pracuję">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="size-2 animate-blink rounded-full bg-muted"
                style={{ animationDelay: `${dot * 0.18}s` }}
              />
            ))}
          </div>
        )}
        {(turn.status === "failed" || turn.status === "cancelled") && turn.error && (
          <div
            className={`rounded-xl border px-3.5 py-2 text-sm ${
              turn.status === "failed" ? "border-danger/40 bg-danger-soft text-danger" : "border-line bg-raised text-muted"
            }`}
          >
            {turn.error}
          </div>
        )}
      </div>
    </div>
  );
}
