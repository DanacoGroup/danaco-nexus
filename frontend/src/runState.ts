// Nakładanie zdarzeń strumienia zadania na turę asystenta (funkcja czysta, testowalna).

import type { AssistantTurn, FileInfo, RunEvent, TurnItem } from "./api";

export function emptyAssistantTurn(runId: string): AssistantTurn {
  return { type: "assistant", run_id: runId, items: [], status: "queued", error: "", created_at: new Date().toISOString() };
}

function appendText(items: TurnItem[], kind: "text" | "thinking", text: string): TurnItem[] {
  const last = items[items.length - 1];
  if (last && last.kind === kind) {
    return [...items.slice(0, -1), { ...last, text: last.text + text }];
  }
  return [...items, { kind, text }];
}

function updateTool(items: TurnItem[], toolUseId: string, update: Partial<Extract<TurnItem, { kind: "tool" }>>): TurnItem[] {
  return items.map((item) => (item.kind === "tool" && item.tool_use_id === toolUseId ? { ...item, ...update } : item));
}

export function applyRunEvent(turn: AssistantTurn, event: RunEvent): AssistantTurn {
  const data = event.data;
  switch (event.type) {
    case "run.started":
      return { ...turn, status: "running" };
    case "text.delta":
      return { ...turn, status: "running", items: appendText(turn.items, "text", String(data.text ?? "")) };
    case "thinking.delta":
      return { ...turn, status: "running", items: appendText(turn.items, "thinking", String(data.text ?? "")) };
    case "text.block": {
      const last = turn.items[turn.items.length - 1];
      return last && last.kind === "text" ? { ...turn, items: [...turn.items, { kind: "text", text: "" }] } : turn;
    }
    case "tool.started":
      return {
        ...turn,
        items: [
          ...turn.items,
          {
            kind: "tool",
            tool_use_id: String(data.tool_use_id),
            name: String(data.name),
            status: "running",
            summary: "",
            files: [],
            input: (data.input as Record<string, unknown>) ?? {},
          },
        ],
      };
    case "tool.progress": {
      // Postęp z serwera MCP nie zna identyfikatora wywołania – dotyczy ostatniego
      // trwającego wywołania narzędzia o tej nazwie.
      let toolUseId = data.tool_use_id !== undefined ? String(data.tool_use_id) : undefined;
      if (toolUseId === undefined) {
        for (const item of [...turn.items].reverse()) {
          if (item.kind === "tool" && item.status === "running" && item.name === data.name) {
            toolUseId = item.tool_use_id;
            break;
          }
        }
      }
      if (!toolUseId) return turn;
      return { ...turn, items: updateTool(turn.items, toolUseId, { progress: String(data.text ?? "") }) };
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
  create_archive: "Archiwum ZIP",
  extract_archive: "Rozpakowanie ZIP",
  index_documents: "Indeksowanie w bazie wiedzy",
  search_documents: "Wyszukiwanie w bazie wiedzy",
};

export function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name;
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
