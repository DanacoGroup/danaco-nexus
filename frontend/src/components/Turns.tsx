// Wyświetlanie tur rozmowy: wiadomości użytkownika, odpowiedzi, przemyślenia i działania narzędzi.

import { useState } from "react";
import type { AssistantTurn, FileInfo, TurnItem, UserTurn } from "../api";
import { toolLabel } from "../runState";
import { FileCard } from "./FileCard";
import { AlertIcon, CheckIcon, ChevronIcon, ToolIcon } from "./icons";
import { Markdown } from "./Markdown";

type Preview = (file: FileInfo) => void;

export function UserMessage({ turn, onPreview }: { turn: UserTurn; onPreview: Preview }) {
  return (
    <div className="turn turn-user">
      {turn.files.length > 0 && (
        <div className="file-grid user-files">
          {turn.files.map((file) => (
            <FileCard key={file.id} file={file} onPreview={onPreview} compact />
          ))}
        </div>
      )}
      {turn.text && <div className="bubble">{turn.text}</div>}
    </div>
  );
}

function Thinking({ text, live }: { text: string; live: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`thinking${open ? " open" : ""}`}>
      <button type="button" className="thinking-toggle" onClick={() => setOpen(!open)}>
        <ChevronIcon size={15} className="chevron" />
        {live ? <span className="shimmer">Analizuję…</span> : "Przemyślenia"}
      </button>
      {open && <div className="thinking-text">{text}</div>}
    </div>
  );
}

function ToolItem({ item, onPreview }: { item: Extract<TurnItem, { kind: "tool" }>; onPreview: Preview }) {
  const running = item.status === "running";
  const failed = item.status === "error" || item.status === "cancelled";
  return (
    <div className={`tool-card ${running ? "running" : failed ? "failed" : "done"}`}>
      <div className="tool-head">
        <span className="tool-status">
          {running ? <span className="spinner" /> : failed ? <AlertIcon size={16} /> : <CheckIcon size={16} />}
        </span>
        <ToolIcon size={15} className="tool-icon" />
        <span className="tool-name">{toolLabel(item.name)}</span>
        {!running && item.duration_ms ? <span className="tool-time">{(item.duration_ms / 1000).toFixed(1)} s</span> : null}
      </div>
      {(item.progress || item.summary) && <div className="tool-summary">{running ? item.progress : item.summary}</div>}
      {item.files.length > 0 && (
        <div className="file-grid">
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
    <div className="turn turn-assistant">
      <div className="avatar" aria-hidden="true">
        N
      </div>
      <div className="assistant-body">
        {turn.items.map((item, index) => {
          if (item.kind === "text") {
            return item.text ? <Markdown key={index} text={item.text} /> : null;
          }
          if (item.kind === "thinking") {
            return <Thinking key={index} text={item.text} live={live && index === lastIndex} />;
          }
          if (item.kind === "notice") {
            return (
              <div key={index} className="notice">
                {item.text}
              </div>
            );
          }
          return <ToolItem key={item.tool_use_id} item={item} onPreview={onPreview} />;
        })}
        {live && turn.items.length === 0 && (
          <div className="pending">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        )}
        {(turn.status === "failed" || turn.status === "cancelled") && turn.error && (
          <div className={`run-error ${turn.status}`}>{turn.error}</div>
        )}
      </div>
    </div>
  );
}
