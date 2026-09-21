// Moduł Agenci: wszystkie sesje pracujące równolegle, drzewo podagentów, nowe zadania w tle.

import { useCallback, useEffect, useState, type FormEvent, type SVGProps } from "react";
import { AlertIcon, CheckIcon, StopIcon } from "../../components/icons";
import type { ModulePageProps, NexusModule } from "../registry";
import { WlasniAgenci } from "./WlasniAgenci";
import {
  MODE_LABELS,
  agenciApi,
  agentTree,
  elapsed,
  request,
  type Mode,
  type TaskSummary,
  type TasksOverview,
} from "./api";

const POLL_MS = 2500;

function AgentsIcon({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <circle cx="12" cy="5" r="2.5" />
      <circle cx="5" cy="18" r="2.5" />
      <circle cx="12" cy="18" r="2.5" />
      <circle cx="19" cy="18" r="2.5" />
      <path d="M12 7.5v8M12 11H6.5a1.5 1.5 0 0 0-1.5 1.5v3M12 11h5.5a1.5 1.5 0 0 1 1.5 1.5v3" />
    </svg>
  );
}

const STATUS_LABELS: Record<string, string> = {
  queued: "W kolejce",
  running: "Pracuje",
  done: "Gotowe",
  failed: "Błąd",
  cancelled: "Anulowane",
  error: "Błąd",
};

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "running"
      ? "border-accent/40 text-accent"
      : status === "failed" || status === "error"
        ? "border-danger/40 text-danger"
        : status === "done"
          ? "border-success/40 text-success"
          : "border-line text-muted";
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-px text-xs ${tone}`}>
      {status === "running" && <span className="spinner size-2.5" />}
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}


function TaskCard({
  task,
  onOpen,
  onCancel,
  now,
}: {
  task: TaskSummary;
  onOpen: () => void;
  onCancel?: () => void;
  now: number;
}) {
  const tree = agentTree(task.agents);
  const runningAgents = task.agents.filter((agent) => agent.status === "running").length;
  return (
    <article className="rounded-2xl border border-line bg-raised/50 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={task.status} />
        <span className="rounded-md bg-hover px-1.5 py-px text-xs text-muted">
          {MODE_LABELS[task.mode] ?? task.mode}
          {task.workspace && `: ${task.workspace}`}
        </span>
        <button
          type="button"
          onClick={onOpen}
          className="min-w-0 flex-1 truncate text-left font-medium hover:text-accent"
          title="Otwórz rozmowę"
        >
          {task.title || "Rozmowa"}
        </button>
        <span className="text-xs text-muted tabular-nums">
          {elapsed(task.started_at ?? task.created_at, task.finished_at, now)}
        </span>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-xs text-muted hover:border-danger/50 hover:text-danger"
          >
            <StopIcon size={12} /> Anuluj
          </button>
        )}
      </div>
      {(task.activity || task.tools_total > 0 || task.agents.length > 0) && task.status === "running" && (
        <div className="mt-2 truncate text-sm text-muted">
          {task.tools_total > 0 && `Narzędzia: ${task.tools_total}`}
          {task.agents.length > 0 && ` · podagenci: ${runningAgents} z ${task.agents.length} w toku`}
          {task.activity && ` · ${task.activity}`}
        </div>
      )}
      {task.error && task.status !== "done" && <div className="mt-2 text-sm text-danger">{task.error}</div>}
      {tree.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t border-line pt-3" aria-label="Podagenci">
          {tree.map(({ agent, depth }) => (
            <li key={agent.tool_use_id} className="flex items-start gap-2 text-sm" style={{ paddingLeft: depth * 20 }}>
              <span className="mt-0.5 grid size-4 shrink-0 place-items-center">
                {agent.status === "running" ? (
                  <span className="spinner size-3" />
                ) : agent.status === "done" ? (
                  <CheckIcon size={14} className="text-success" />
                ) : (
                  <AlertIcon size={14} className="text-danger" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate">
                  {agent.description || "Podagent"}
                  {agent.tools_total > 0 && (
                    <span className="ml-2 text-xs text-muted">
                      {agent.tools_running > 0 ? `${agent.tools_running}/` : ""}
                      {agent.tools_total} narz.
                    </span>
                  )}
                </div>
                {(agent.progress || agent.summary) && (
                  <div className="line-clamp-2 text-xs text-muted">
                    {agent.status === "running" ? agent.progress : agent.summary}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function NewTaskForm({ onCreated }: { onCreated: (conversationId: string) => void }) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<Mode>("chat");
  const [projects, setProjects] = useState<string[]>([]);
  const [workspace, setWorkspace] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (mode !== "code") return;
    request<{ name: string }[]>("GET", "/api/kod/projekty")
      .then((items) => {
        setProjects(items.map((item) => item.name));
        setWorkspace((current) => current || items[0]?.name || "");
      })
      .catch(() => setProjects([]));
  }, [mode]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const created = await agenciApi.createTask(text.trim(), mode, mode === "code" ? workspace : "");
      setText("");
      onCreated(created.conversation_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się uruchomić zadania.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="rounded-2xl border border-line bg-raised/50 p-4">
      <label htmlFor="nowe-zadanie" className="mb-2 block font-medium">
        Nowe zadanie w tle
      </label>
      <textarea
        id="nowe-zadanie"
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={3}
        placeholder="Np. „Uruchom 10 podagentów: każdy niech zbada jedną sieć hoteli w Trójmieście i porówna ceny”."
        className="w-full resize-y rounded-xl border border-line bg-app px-3 py-2 text-sm outline-none focus:border-accent"
      />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <select
          value={mode}
          onChange={(event) => setMode(event.target.value as Mode)}
          className="rounded-lg border border-line bg-app px-2 py-1.5 text-sm"
          aria-label="Tryb"
        >
          {(Object.keys(MODE_LABELS) as Mode[]).map((key) => (
            <option key={key} value={key}>
              {MODE_LABELS[key]}
            </option>
          ))}
        </select>
        {mode === "code" && (
          <select
            value={workspace}
            onChange={(event) => setWorkspace(event.target.value)}
            className="rounded-lg border border-line bg-app px-2 py-1.5 text-sm"
            aria-label="Projekt"
          >
            {projects.length === 0 && <option value="">Brak projektów</option>}
            {projects.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        )}
        <button
          type="submit"
          disabled={!text.trim() || busy || (mode === "code" && !workspace)}
          className="ml-auto rounded-lg bg-accent-fill px-3 py-1.5 text-sm font-medium text-on-accent hover:bg-accent-fill-hover disabled:opacity-50"
        >
          {busy ? "Uruchamiam…" : "Uruchom w tle"}
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
    </form>
  );
}

export function AgenciPage({ openConversation }: ModulePageProps) {
  const [overview, setOverview] = useState<TasksOverview | null>(null);
  const [error, setError] = useState("");
  const [now, setNow] = useState(() => Date.now());

  const refresh = useCallback(async () => {
    try {
      setOverview(await agenciApi.tasks());
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się pobrać zadań.");
    }
    setNow(Date.now());
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const cancel = async (task: TaskSummary) => {
    try {
      await agenciApi.cancel(task.id);
    } finally {
      void refresh();
    }
  };

  const running = overview?.active.filter((task) => task.status === "running").length ?? 0;
  return (
    <div className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6">
      <header className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="font-heading text-2xl font-bold tracking-tight">Agenci</h1>
          <p className="text-sm text-muted">
            Twoje specjalizacje i wszystko, co teraz pracuje w tle.
            {overview &&
              ` Pracuje ${running} z ${overview.config.concurrency} miejsc` +
                (overview.config.queued ? `, w kolejce: ${overview.config.queued}.` : ".")}
          </p>
        </div>
      </header>

      <WlasniAgenci onOtworzRozmowe={openConversation} />

      <NewTaskForm
        onCreated={() => {
          void refresh();
        }}
      />

      {error && <p className="text-sm text-danger">{error}</p>}

      {/* Pusty wykaz zadań kończył stronę samotnym zdaniem pod ostatnią ramką — wyglądało to
        na urwany widok. Komunikat dostaje własną ramkę, taką samą jak kafle wyżej, więc
        „nic tu nie ma” czyta się jako stan, a nie jako brakujący kawałek interfejsu. */}
      <section className="space-y-3" aria-label="Zadania w toku">
        <h2 className="text-sm font-medium text-muted uppercase">W toku</h2>
        {overview && overview.active.length === 0 && (
          <p className="rounded-2xl border border-dashed border-line px-4 py-6 text-center text-sm text-muted">
            Brak zadań w toku. Zleć zadanie powyżej — wynik znajdziesz tutaj.
          </p>
        )}
        {overview?.active.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            now={now}
            onOpen={() => openConversation(task.conversation_id)}
            onCancel={() => void cancel(task)}
          />
        ))}
      </section>

      {overview && overview.finished.length > 0 && (
        <section className="space-y-3" aria-label="Zakończone">
          <h2 className="text-sm font-medium text-muted uppercase">Zakończone (24 h)</h2>
          {overview.finished.map((task) => (
            <TaskCard key={task.id} task={task} now={now} onOpen={() => openConversation(task.conversation_id)} />
          ))}
        </section>
      )}
    </div>
  );
}

export const module: NexusModule = {
  id: "agenci",
  label: "Agenci",
  description: "Twoi agenci i zadania w tle — zlecasz i wracasz po gotowy wynik.",
  icon: AgentsIcon,
  order: 70,
  Page: AgenciPage,
};
