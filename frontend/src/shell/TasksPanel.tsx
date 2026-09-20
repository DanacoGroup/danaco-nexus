// Zadania w toku: wszystkie rozmowy z trwającym zadaniem (wiele sesji naraz), przejście i anulowanie.

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { CloseIcon, StopIcon } from "../components/icons";
import { toolLabel } from "../runState";
import { LayersIcon } from "./icons";
import { startApi, type ActiveTask } from "./startApi";

const POLL_BUSY_MS = 3000;
const POLL_IDLE_MS = 15000;

/** Zadania, które zniknęły z listy trwających (zakończyły się od ostatniego odczytu). */
export function finishedSince(previous: ActiveTask[], current: ActiveTask[]): ActiveTask[] {
  const still = new Set(current.map((task) => task.run_id));
  return previous.filter((task) => !still.has(task.run_id));
}

export function elapsedLabel(since: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(since).getTime()) / 1000));
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

/** Odpytuje listę zadań w toku (częściej, gdy coś trwa); zgłasza zadania zakończone w tle. */
export function useActiveTasks(enabled: boolean, onFinished: (tasks: ActiveTask[]) => void) {
  const [tasks, setTasks] = useState<ActiveTask[]>([]);
  const previous = useRef<ActiveTask[] | null>(null);
  const finished = useRef(onFinished);
  finished.current = onFinished;
  const timer = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    window.clearTimeout(timer.current);
    let busy = false;
    try {
      const list = await startApi.activeTasks();
      busy = list.length > 0;
      if (previous.current) {
        const done = finishedSince(previous.current, list);
        if (done.length) finished.current(done);
      }
      previous.current = list;
      setTasks(list);
    } catch {
      /* chwilowy brak sieci – kolejna próba za chwilę */
    }
    if (document.visibilityState === "visible") {
      timer.current = window.setTimeout(() => void refresh(), busy ? POLL_BUSY_MS : POLL_IDLE_MS);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    void refresh();
    const onVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearTimeout(timer.current);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [enabled, refresh]);

  return { tasks, refresh };
}

interface ButtonProps {
  tasks: ActiveTask[];
  onClick: () => void;
  variant?: "rail" | "header";
}

export function TasksButton({ tasks, onClick, variant = "header" }: ButtonProps) {
  const count = tasks.length;
  const label = count ? `Zadania w toku: ${count}` : "Zadania w toku";
  if (variant === "rail") {
    return (
      <button
        type="button"
        onClick={onClick}
        title={label}
        aria-label={label}
        className="relative flex flex-col items-center gap-1 rounded-xl py-1 text-[11px] font-medium text-muted hover:text-fg"
      >
        <span className="relative grid size-10 place-items-center rounded-xl hover:bg-hover">
          <LayersIcon size={21} />
          {count > 0 && (
            <span className="absolute -top-0.5 -right-0.5 grid min-w-[18px] place-items-center rounded-full bg-accent-fill px-1 text-[10px] leading-[18px] font-semibold text-on-accent">
              {count}
            </span>
          )}
        </span>
        Zadania
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`relative inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-sm transition-colors ${
        count ? "bg-accent-soft text-accent" : "text-muted hover:bg-hover hover:text-fg"
      }`}
    >
      {count ? <span className="spinner size-3.5" /> : <LayersIcon size={18} />}
      {count > 0 && <span className="font-medium tabular-nums">{count}</span>}
    </button>
  );
}

interface PanelProps {
  tasks: ActiveTask[];
  currentConversation: string | null;
  onOpen: (conversationId: string) => void;
  onClose: () => void;
  onChanged: () => void;
}

export function TasksPanel({ tasks, currentConversation, onOpen, onClose, onChanged }: PanelProps) {
  const [cancelling, setCancelling] = useState<Set<string>>(new Set());
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const cancel = (task: ActiveTask) => {
    setCancelling((current) => new Set(current).add(task.run_id));
    api
      .cancelRun(task.run_id)
      .catch(() => undefined)
      .finally(onChanged);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 backdrop-blur-[2px] md:items-start md:justify-end md:p-4" onClick={onClose}>
      <section
        role="dialog"
        aria-label="Zadania w toku"
        className="safe-bottom flex max-h-[80dvh] w-full animate-rise flex-col rounded-t-3xl border border-line bg-side shadow-2xl md:mt-12 md:max-w-md md:rounded-2xl md:pb-2"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center gap-2 px-5 pt-4 pb-2">
          <LayersIcon size={18} className="text-accent" />
          <h2 className="flex-1 text-[15px] font-semibold">Zadania w toku</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Zamknij">
            <CloseIcon size={18} />
          </button>
        </header>
        <p className="px-5 pb-3 text-sm text-muted">
          Każda rozmowa pracuje osobno – możesz zlecić kilka zadań naraz i wrócić do nich później.
        </p>
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
          {tasks.length === 0 && (
            <div className="rounded-2xl border border-dashed border-line px-4 py-8 text-center text-sm text-muted">
              Nic teraz nie trwa. Zadania z wszystkich rozmów pojawią się tutaj.
            </div>
          )}
          <ul className="space-y-2">
            {tasks.map((task) => {
              const current = task.conversation_id === currentConversation;
              const stopping = cancelling.has(task.run_id);
              return (
                <li
                  key={task.run_id}
                  className={`flex items-center gap-3 rounded-2xl border px-3.5 py-3 ${
                    current ? "border-accent/50 bg-accent-soft/40" : "border-line bg-app/60"
                  }`}
                >
                  <span className={`grid size-8 shrink-0 place-items-center rounded-full ${task.status === "running" ? "text-accent" : "text-muted"}`}>
                    {task.status === "running" ? <span className="spinner" /> : <span className="size-2.5 rounded-full bg-line-strong" />}
                  </span>
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => {
                      onOpen(task.conversation_id);
                      onClose();
                    }}
                  >
                    <span className="block truncate text-sm font-medium">{task.title}</span>
                    <span className="block truncate text-xs text-muted">
                      {task.status === "queued"
                        ? "W kolejce"
                        : `${task.tool ? toolLabel(task.tool) : "Pracuję"} · ${elapsedLabel(task.started_at ?? task.created_at, now)}`}
                      {task.mode !== "chat" ? ` · tryb ${task.mode}` : ""}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="icon-btn size-8 hover:text-danger"
                    disabled={stopping}
                    onClick={() => cancel(task)}
                    aria-label={`Anuluj zadanie „${task.title}”`}
                    title="Anuluj"
                  >
                    {stopping ? <span className="spinner size-3.5" /> : <StopIcon size={14} />}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </section>
    </div>
  );
}
