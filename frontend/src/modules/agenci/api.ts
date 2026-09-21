// Zapytania modułów Agenci i Kod (sesja przeglądarki, nagłówek chroniący przed CSRF).

import { ApiError } from "../../api";

export async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: {
      "X-Nexus-Request": "1",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let message = `Błąd serwera (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      /* odpowiedź bez treści JSON */
    }
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

export type Mode = "chat" | "research" | "code" | "strona";

export const MODE_LABELS: Record<Mode, string> = {
  chat: "Czat",
  research: "Badania",
  code: "Kod",
  strona: "Strona",
};

export interface SubagentSummary {
  tool_use_id: string;
  parent_tool_use_id: string | null;
  description: string;
  subagent_type: string;
  status: string;
  summary: string;
  progress: string;
  tools_total: number;
  tools_running: number;
  duration_ms: number;
}

export interface TaskSummary {
  id: string;
  conversation_id: string;
  title: string;
  mode: Mode;
  workspace: string;
  status: string;
  error: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  usage: Record<string, number>;
  tools_total: number;
  tools_running: number;
  agents: SubagentSummary[];
  activity: string;
}


export interface TasksOverview {
  active: TaskSummary[];
  finished: TaskSummary[];
  config: { concurrency: number; queued: number; subagents: boolean; max_subagents: number; web_tools: boolean };
}

/** Agent zapisany przez użytkownika: własna specjalizacja, nie osobny silnik. */
export interface WlasnyAgent {
  id: string;
  nazwa: string;
  opis: string;
  instrukcja: string;
  tryb: Mode;
  projekt: string;
  ikona: string;
  uruchomienia: number;
}

/** Dane formularza agenta — to samo, co przyjmuje serwer przy tworzeniu i zmianie. */
export type SzkicAgenta = Omit<WlasnyAgent, "id" | "uruchomienia">;

export const agenciApi = {
  tasks: () => request<TasksOverview>("GET", "/api/agenci/zadania"),
  wlasni: () => request<WlasnyAgent[]>("GET", "/api/agenci/wlasni"),
  utworzAgenta: (dane: SzkicAgenta) => request<WlasnyAgent>("POST", "/api/agenci/wlasni", dane),
  zmienAgenta: (id: string, dane: SzkicAgenta) =>
    request<WlasnyAgent>("PATCH", `/api/agenci/wlasni/${id}`, dane),
  usunAgenta: (id: string) => request<void>("DELETE", `/api/agenci/wlasni/${id}`),
  uruchomAgenta: (id: string, tekst: string) =>
    request<{ conversation_id: string; run_id: string; title: string }>(
      "POST",
      `/api/agenci/wlasni/${id}/uruchom`,
      { tekst },
    ),
  createTask: (text: string, mode: Mode, workspace = "") =>
    request<{ conversation_id: string; run_id: string; title: string }>("POST", "/api/agenci/zadania", {
      text,
      mode,
      workspace,
    }),
  cancel: (runId: string) => request<{ status: string }>("POST", `/api/runs/${runId}/cancel`),
};

/** Drzewo podagentów: kolejność zachowana, poziom zagnieżdżenia z parent_tool_use_id. */
export function agentTree(agents: SubagentSummary[]): { agent: SubagentSummary; depth: number }[] {
  const known = new Set(agents.map((agent) => agent.tool_use_id));
  const children = new Map<string, SubagentSummary[]>();
  const roots: SubagentSummary[] = [];
  for (const agent of agents) {
    const parent = agent.parent_tool_use_id;
    if (parent && known.has(parent)) {
      children.set(parent, [...(children.get(parent) ?? []), agent]);
    } else {
      roots.push(agent);
    }
  }
  const result: { agent: SubagentSummary; depth: number }[] = [];
  const visit = (agent: SubagentSummary, depth: number) => {
    result.push({ agent, depth });
    for (const child of children.get(agent.tool_use_id) ?? []) visit(child, depth + 1);
  };
  for (const root of roots) visit(root, 0);
  return result;
}

/** Czas trwania „1 min 05 s” od początku (albo do końca) zadania. */
export function elapsed(start: string | null, end: string | null, now = Date.now()): string {
  if (!start) return "";
  const seconds = Math.max(0, Math.round(((end ? Date.parse(end) : now) - Date.parse(start)) / 1000));
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ${String(seconds % 60).padStart(2, "0")} s`;
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")} min`;
}
