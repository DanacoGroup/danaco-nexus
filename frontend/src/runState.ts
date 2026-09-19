// Nakładanie zdarzeń strumienia zadania na turę asystenta (funkcja czysta, testowalna).
//
// Zdarzenia podagentów (narzędzie Agent Claude Code) mają pole parent_tool_use_id –
// trafiają wtedy do elementu podagenta (agent.items), a nie na najwyższy poziom tury.

import type { AssistantTurn, FileInfo, RunEvent, TurnItem } from "./api";

export function emptyAssistantTurn(runId: string): AssistantTurn {
  return { type: "assistant", run_id: runId, items: [], status: "queued", error: "", created_at: new Date().toISOString() };
}

type ToolItem = Extract<TurnItem, { kind: "tool" }>;

/** Podagent: opis zadania i własne elementy (tekst, narzędzia, kolejni podagenci). */
export interface AgentInfo {
  description: string;
  subagent_type: string;
  background: boolean;
  items: TurnItem[];
}

/** Element narzędzia będący podagentem – zagnieżdżone elementy w agent.items. */
export type AgentItem = ToolItem & { agent: AgentInfo };

export const AGENT_TOOL = "podagent";

export function isAgentItem(item: TurnItem): item is AgentItem {
  return item.kind === "tool" && "agent" in item && typeof (item as AgentItem).agent === "object";
}

/** Opis podagenta – także dla wpisu z historii rozmowy (bez zagnieżdżonych elementów). */
export function agentInfo(item: ToolItem): AgentInfo | null {
  if (isAgentItem(item)) return item.agent;
  if (item.name !== AGENT_TOOL) return null;
  const description = typeof item.input?.description === "string" ? item.input.description : "";
  return { description, subagent_type: "", background: false, items: [] };
}

/** Liczba wywołań narzędzi podagenta i ile z nich trwa (bez tekstu i powiadomień). */
export function agentStats(agent: AgentInfo): { total: number; running: number } {
  let total = 0;
  let running = 0;
  for (const item of agent.items) {
    if (item.kind !== "tool") continue;
    total += 1;
    if (item.status === "running") running += 1;
  }
  return { total, running };
}

function appendText(items: TurnItem[], kind: "text" | "thinking", text: string): TurnItem[] {
  const last = items[items.length - 1];
  if (last && last.kind === kind) {
    return [...items.slice(0, -1), { ...last, text: last.text + text }];
  }
  return [...items, { kind, text }];
}

/** Zmienia elementy podagenta parentId (wyszukiwanie w głąb); null, gdy go nie ma. */
function updateChildren(
  items: TurnItem[],
  parentId: string,
  change: (children: TurnItem[]) => TurnItem[],
): TurnItem[] | null {
  let found = false;
  const next = items.map((item) => {
    if (found || !isAgentItem(item)) return item;
    if (item.tool_use_id === parentId) {
      found = true;
      return { ...item, agent: { ...item.agent, items: change(item.agent.items) } };
    }
    const nested = updateChildren(item.agent.items, parentId, change);
    if (nested === null) return item;
    found = true;
    return { ...item, agent: { ...item.agent, items: nested } };
  });
  return found ? next : null;
}

/** Zmiana w liście właściwej dla zdarzenia: u podagenta-rodzica albo na najwyższym poziomie. */
function inScope(items: TurnItem[], parent: unknown, change: (children: TurnItem[]) => TurnItem[]): TurnItem[] {
  if (typeof parent === "string" && parent) {
    const nested = updateChildren(items, parent, change);
    if (nested !== null) return nested;
  }
  return change(items);
}

function updateTool(items: TurnItem[], toolUseId: string, update: Partial<ToolItem>): TurnItem[] {
  let changed = false;
  const next = items.map((item) => {
    if (item.kind !== "tool") return item;
    if (item.tool_use_id === toolUseId) {
      changed = true;
      return { ...item, ...update };
    }
    if (isAgentItem(item)) {
      const nested = updateTool(item.agent.items, toolUseId, update);
      if (nested !== item.agent.items) {
        changed = true;
        return { ...item, agent: { ...item.agent, items: nested } };
      }
    }
    return item;
  });
  return changed ? next : items;
}

/** Ostatnie trwające wywołanie narzędzia o danej nazwie (także u podagentów). */
function lastRunningTool(items: TurnItem[], name: unknown): string | undefined {
  for (const item of [...items].reverse()) {
    if (item.kind !== "tool") continue;
    if (isAgentItem(item)) {
      const nested = lastRunningTool(item.agent.items, name);
      if (nested) return nested;
    }
    if (item.status === "running" && item.name === name) return item.tool_use_id;
  }
  return undefined;
}

function newTool(data: Record<string, unknown>): TurnItem {
  const base: ToolItem = {
    kind: "tool",
    tool_use_id: String(data.tool_use_id),
    name: String(data.name),
    status: "running",
    summary: "",
    files: [],
    input: (data.input as Record<string, unknown>) ?? {},
  };
  const meta = data.agent;
  if (!meta || typeof meta !== "object") return base;
  const info = meta as Partial<AgentInfo>;
  const agent: AgentItem = {
    ...base,
    agent: {
      description: String(info.description ?? ""),
      subagent_type: String(info.subagent_type ?? ""),
      background: Boolean(info.background),
      items: [],
    },
  };
  return agent;
}

export function applyRunEvent(turn: AssistantTurn, event: RunEvent): AssistantTurn {
  const data = event.data;
  const parent = data.parent_tool_use_id;
  switch (event.type) {
    case "run.started":
      return { ...turn, status: "running" };
    case "text.delta":
      return {
        ...turn,
        status: "running",
        items: inScope(turn.items, parent, (items) => appendText(items, "text", String(data.text ?? ""))),
      };
    case "thinking.delta":
      return {
        ...turn,
        status: "running",
        items: inScope(turn.items, parent, (items) => appendText(items, "thinking", String(data.text ?? ""))),
      };
    case "text.block": {
      const items = inScope(turn.items, parent, (list) => {
        const last = list[list.length - 1];
        return last && last.kind === "text" && last.text ? [...list, { kind: "text", text: "" }] : list;
      });
      return { ...turn, items };
    }
    case "tool.started":
      return { ...turn, items: inScope(turn.items, parent, (items) => [...items, newTool(data)]) };
    case "tool.progress": {
      // Postęp z serwera MCP może nie znać identyfikatora wywołania – dotyczy wtedy
      // ostatniego trwającego wywołania narzędzia o tej nazwie.
      const toolUseId =
        data.tool_use_id !== undefined ? String(data.tool_use_id) : lastRunningTool(turn.items, data.name);
      if (!toolUseId) return turn;
      const items = updateTool(turn.items, toolUseId, { progress: String(data.text ?? "") });
      return items === turn.items ? turn : { ...turn, items };
    }
    case "tool.finished":
      return {
        ...turn,
        items: updateTool(turn.items, String(data.tool_use_id), {
          status: String(data.status),
          summary: String(data.summary ?? ""),
          files: (data.files as FileInfo[]) ?? [],
          duration_ms: Number(data.duration_ms ?? 0),
          progress: undefined,
        }),
      };
    case "notice":
      return { ...turn, items: [...turn.items, { kind: "notice", text: String(data.text ?? "") }] };
    case "run.completed":
      return { ...turn, status: "done" };
    case "run.failed":
      return { ...turn, status: "failed", error: String(data.error ?? "Zadanie nie powiodło się.") };
    case "run.cancelled":
      return { ...turn, status: "cancelled", error: String(data.error ?? "Zadanie anulowane.") };
    default:
      return turn;
  }
}

export const TOOL_LABELS: Record<string, string> = {
  inspect_files: "Analiza plików",
  view_pages: "Podgląd stron",
  extract_text: "Odczyt tekstu",
  ocr_documents: "OCR i przeszukiwalny PDF",
  enhance_document_scan: "Poprawa skanu",
  enhance_photo: "Korekta zdjęcia",
  retouch_portrait: "Retusz portretu",
  upscale_image: "Powiększenie AI (Real-ESRGAN)",
  imagemagick: "ImageMagick",
  convert_images: "Konwersja obrazów",
  convert_documents: "Konwersja dokumentów",
  write_document: "Tworzenie dokumentu",
  check_grammar: "Korekta językowa",
  pdf_split: "Podział PDF",
  pdf_merge: "Łączenie PDF",
  pdf_edit_pages: "Edycja stron PDF",
  detect_document_boundaries: "Wykrywanie granic dokumentów",
  media_process: "Audio / wideo (FFmpeg)",
  transcribe_audio: "Transkrypcja mowy",
  cloud_browse: "Przeglądanie chmury",
  cloud_import: "Pobieranie z chmury",
  cloud_save: "Zapis w chmurze",
  create_archive: "Archiwum ZIP",
  extract_archive: "Rozpakowanie ZIP",
  index_documents: "Indeksowanie w bazie wiedzy",
  search_documents: "Wyszukiwanie w bazie wiedzy",
  podagent: "Podagent",
  WebSearch: "Wyszukiwanie w sieci",
  WebFetch: "Odczyt strony",
  Read: "Odczyt pliku",
  Write: "Zapis pliku",
  Edit: "Edycja pliku",
  MultiEdit: "Edycja pliku",
  Glob: "Wyszukiwanie plików",
  Grep: "Przeszukiwanie kodu",
  Bash: "Polecenie",
};

export function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name;
}

/** Krótki opis parametrów narzędzia wbudowanego (plik, polecenie, zapytanie). */
export function toolDetail(item: ToolItem): string {
  const input = item.input ?? {};
  for (const key of ["file_path", "command", "pattern", "query", "url", "path"]) {
    const value = input[key];
    if (typeof value === "string" && value) return value.length > 120 ? `${value.slice(0, 117)}…` : value;
  }
  return "";
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toLocaleString("pl-PL", { maximumFractionDigits: value < 10 ? 1 : 0 })} ${units[unit]}`;
}
