// Wyświetlanie tur rozmowy: wiadomości użytkownika, odpowiedzi, przemyślenia, działania narzędzi
// i podagentów (zwijane bloki z własnym tekstem i narzędziami).

import { useState } from "react";
import type { AssistantTurn, FileInfo, TurnItem, UserTurn } from "../api";
import { agentInfo, agentStats, toolDetail, toolLabel, type AgentInfo } from "../runState";
import { NagranieKroku } from "./NagranieKroku";
import { NagranieStartu, ograniczonyRuch } from "../ruch";
import { FileCard } from "./FileCard";
import { AlertIcon, CheckIcon, ChevronIcon, Logo, MicIcon, ToolIcon } from "./icons";
import { Markdown } from "./Markdown";

type Preview = (file: FileInfo) => void;
type ToolItemData = Extract<TurnItem, { kind: "tool" }>;

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
        <div className="max-w-[85%] rounded-2xl bg-bubble px-4 py-2.5 break-words whitespace-pre-wrap">
          {turn.voice && (
            <MicIcon size={14} className="mr-1.5 inline align-[-2px] text-muted" aria-label="Wypowiedź głosowa" />
          )}
          {turn.text}
        </div>
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

function StatusMark({ running, failed }: { running: boolean; failed: boolean }) {
  return (
    <span
      className={`grid size-5 shrink-0 place-items-center ${failed ? "text-danger" : running ? "text-accent" : "text-success"}`}
    >
      {running ? <span className="spinner size-3.5" /> : failed ? <AlertIcon size={16} /> : <CheckIcon size={16} />}
    </span>
  );
}

/** Czas kroku po polsku: przecinek dziesiętny, cyfry tabelaryczne w miejscu użycia. */
function sekundy(ms: number): string {
  return `${(ms / 1000).toLocaleString("pl-PL", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s`;
}

function ToolItem({ item, onPreview }: { item: ToolItemData; onPreview: Preview }) {
  const running = item.status === "running";
  const failed = item.status === "error" || item.status === "cancelled";
  const detail = toolDetail(item);
  return (
    <div
      // Obrys w Aurorze i poświata tylko wtedy, gdy narzędzie pracuje (DESIGN_SYSTEM, rozdz. 4.2).
      className={`rounded-2xl border px-3.5 py-2.5 text-sm ${
        failed
          ? "border-danger/40 bg-danger-soft/60"
          : running
            ? "aurora-obrys glow-ai border-transparent bg-raised/60"
            : "border-line bg-raised/60"
      }`}
    >
      <div className="flex min-w-0 items-center gap-2">
        <StatusMark running={running} failed={failed} />
        <ToolIcon size={15} className="shrink-0 text-muted" />
        <span className={`shrink-0 font-medium ${running ? "shimmer-text" : ""}`}>{toolLabel(item.name)}</span>
        {detail && <span className="min-w-0 truncate font-mono text-xs text-muted">{detail}</span>}
        {!running && item.duration_ms ? (
          <span className="ml-auto shrink-0 text-xs text-muted tabular-nums">{sekundy(item.duration_ms)}</span>
        ) : null}
      </div>
      {(item.progress || item.summary) && (
        <div className={`mt-1 pl-7 break-words whitespace-pre-wrap ${failed ? "text-danger" : "text-muted"}`}>
          {running ? item.progress : item.summary}
        </div>
      )}
      {running && <NagranieKroku narzedzie={item.name} />}
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

function AgentItem({
  item,
  agent,
  onPreview,
}: {
  item: ToolItemData;
  agent: AgentInfo;
  onPreview: Preview;
}) {
  const [open, setOpen] = useState(false);
  const running = item.status === "running";
  const failed = item.status === "error" || item.status === "cancelled";
  const stats = agentStats(agent);
  const description = agent.description || "zadanie";
  const status = running
    ? item.progress || (stats.running ? `Pracuje: ${stats.running} z ${stats.total} narzędzi` : "Pracuje…")
    : item.summary;
  return (
    <div
      className={`rounded-2xl border text-sm ${
        failed
          ? "border-danger/40 bg-danger-soft/60"
          : running
            ? "aurora-obrys glow-ai border-transparent bg-raised/40"
            : "border-line bg-raised/40"
      }`}
    >
      <button
        type="button"
        className="flex w-full min-w-0 items-center gap-2 rounded-2xl px-3.5 py-2.5 text-left transition-colors hover:bg-hover/50"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <StatusMark running={running} failed={failed} />
        <ChevronIcon size={15} className={`shrink-0 text-muted transition-transform ${open ? "rotate-90" : ""}`} />
        <span className={`min-w-0 truncate font-medium ${running ? "shimmer-text" : ""}`}>Podagent: {description}</span>
        <span className="ml-auto flex shrink-0 items-center gap-2 text-xs text-muted tabular-nums">
          {agent.background && <span className="rounded-md border border-line px-1.5 py-px">w tle</span>}
          {stats.total > 0 && <span>{stats.total} narz.</span>}
          {!running && item.duration_ms ? <span>{sekundy(item.duration_ms)}</span> : null}
        </span>
      </button>
      {status && !open && (
        <div className={`-mt-1 line-clamp-2 px-3.5 pb-2.5 pl-10 ${failed ? "text-danger" : "text-muted"}`}>{status}</div>
      )}
      {open && (
        <div className="space-y-2.5 border-t border-line px-3.5 py-3">
          {agent.items.length === 0 && !running && item.summary && (
            <div className={failed ? "text-danger" : "text-muted"}>{item.summary}</div>
          )}
          <TurnItems items={agent.items} live={running} onPreview={onPreview} />
          {running && agent.items.length === 0 && <div className="shimmer-text text-muted">Pracuje…</div>}
          {!running && agent.items.length > 0 && item.summary && (
            <div className="rounded-xl border border-line bg-app/60 px-3 py-2">
              <div className="mb-1 text-xs font-medium text-muted uppercase">Wynik</div>
              <div className="break-words whitespace-pre-wrap">{item.summary}</div>
            </div>
          )}
        </div>
      )}
      {!open && item.files.length > 0 && (
        <div className="grid gap-2 px-3.5 pb-3 pl-10 sm:grid-cols-2">
          {item.files.map((file) => (
            <FileCard key={file.id} file={file} onPreview={onPreview} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Elementy tury lub podagenta (rekurencyjnie – podagenci mogą mieć własne elementy). */
function TurnItems({ items, live, onPreview }: { items: TurnItem[]; live: boolean; onPreview: Preview }) {
  const lastIndex = items.length - 1;
  return (
    <>
      {items.map((item, index) => {
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
        const agent = agentInfo(item);
        if (agent) return <AgentItem key={item.tool_use_id} item={item} agent={agent} onPreview={onPreview} />;
        return <ToolItem key={item.tool_use_id} item={item} onPreview={onPreview} />;
      })}
    </>
  );
}

export function AssistantMessage({ turn, onPreview }: { turn: AssistantTurn; onPreview: Preview }) {
  const live = turn.status === "running" || turn.status === "queued";
  return (
    <div className="flex animate-rise gap-3">
      <Logo size={28} className="mt-0.5 shrink-0 rounded-lg" />
      <div className="min-w-0 flex-1 space-y-3">
        <TurnItems items={turn.items} live={live} onPreview={onPreview} />
        {live && turn.items.length === 0 && (
          // Chwila przed pierwszym słowem ma własne ujęcie w pakiecie ruchu (moment-mysli).
          // Przy ograniczonym ruchu zostają trzy kropki — ten sam komunikat, bez animacji.
          <div className="flex h-9 items-center" role="status" aria-label="Pracuję">
            {ograniczonyRuch() ? (
              <span className="flex items-center gap-1.5">
                {[0, 1, 2].map((dot) => (
                  <span
                    key={dot}
                    className="size-2 animate-blink rounded-full bg-muted"
                    style={{ animationDelay: `${dot * 0.18}s` }}
                  />
                ))}
              </span>
            ) : (
              <NagranieStartu nazwa="moment-mysli" petla className="h-9 w-24 object-contain" />
            )}
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
