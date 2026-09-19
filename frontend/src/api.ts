// Klient API Danaco Nexus: zapytania JSON, przesyłanie plików z postępem, strumień zdarzeń.

export interface FileInfo {
  id: string;
  name: string;
  mime: string;
  size: number;
  origin?: string;
  created_at?: string;
  indexed?: boolean;
  description?: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
  active: boolean;
}

export type TurnItem =
  | { kind: "text"; text: string }
  | { kind: "thinking"; text: string }
  | {
      kind: "tool";
      tool_use_id: string;
      name: string;
      status: string;
      summary: string;
      duration_ms?: number;
      files: FileInfo[];
      progress?: string;
      input?: Record<string, unknown>;
    }
  | { kind: "notice"; text: string };

export interface UserTurn {
  type: "user";
  id: number | string;
  text: string;
  files: FileInfo[];
  run_id?: string | null;
  created_at: string;
  voice?: boolean;
}

export interface AssistantTurn {
  type: "assistant";
  run_id: string | null;
  items: TurnItem[];
  status: string;
  error: string;
  created_at: string;
}

export type Turn = UserTurn | AssistantTurn;

export interface ConversationDetail {
  id: string;
  title: string;
  turns: Turn[];
  files: FileInfo[];
  active_run: { id: string; status: string } | null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const APP_HEADER = { "X-Nexus-Request": "1" };

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? APP_HEADER : { ...APP_HEADER, "Content-Type": "application/json" },
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

export interface VoiceConfig {
  available: boolean;
  voices: { id: string; name: string }[];
  default_voice: string;
}

/** Rozpoznanie nagranej wypowiedzi (rozmowa głosowa). */
export async function transcribeAudio(audio: Blob, signal?: AbortSignal): Promise<string> {
  const form = new FormData();
  const extension = audio.type.includes("mp4") ? "m4a" : audio.type.includes("ogg") ? "ogg" : "webm";
  form.append("audio", audio, `wypowiedz.${extension}`);
  form.append("language", "pl");
  const response = await fetch("/api/voice/transcribe", {
    method: "POST",
    credentials: "same-origin",
    headers: APP_HEADER,
    body: form,
    signal,
  });
  if (!response.ok) throw new ApiError(response.status, `Rozpoznawanie mowy nie powiodło się (${response.status})`);
  return ((await response.json()) as { text: string }).text;
}

/** Synteza mowy (WAV) wybranym głosem. */
export async function speakText(text: string, voice: string, signal?: AbortSignal): Promise<Blob> {
  const response = await fetch("/api/voice/speak", {
    method: "POST",
    credentials: "same-origin",
    headers: { ...APP_HEADER, "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice }),
    signal,
  });
  if (!response.ok) throw new ApiError(response.status, `Synteza mowy nie powiodła się (${response.status})`);
  return response.blob();
}

export const api = {
  me: () => request<{ username: string; cloud_url?: string }>("GET", "/api/auth/me"),
  login: (username: string, password: string) =>
    request<{ username: string }>("POST", "/api/auth/login", { username, password }),
  logout: () => request<{ ok: boolean }>("POST", "/api/auth/logout"),
  conversations: () => request<ConversationSummary[]>("GET", "/api/conversations"),
  createConversation: () => request<ConversationSummary>("POST", "/api/conversations", {}),
  conversation: (id: string) => request<ConversationDetail>("GET", `/api/conversations/${id}`),
  renameConversation: (id: string, title: string) =>
    request<{ id: string; title: string }>("PATCH", `/api/conversations/${id}`, { title }),
  deleteConversation: (id: string) => request<{ ok: boolean }>("DELETE", `/api/conversations/${id}`),
  sendMessage: (id: string, text: string, fileIds: string[], voice = false) =>
    request<{ run_id: string }>("POST", `/api/conversations/${id}/messages`, { text, file_ids: fileIds, voice }),
  voiceConfig: () => request<VoiceConfig>("GET", "/api/voice/config"),
  cancelRun: (id: string) => request<{ status: string }>("POST", `/api/runs/${id}/cancel`),
};

export function downloadUrl(file: FileInfo, inline = false): string {
  return `/api/files/${file.id}/download${inline ? "?inline=1" : ""}`;
}

export function thumbnailUrl(file: FileInfo): string {
  return `/api/files/${file.id}/thumbnail`;
}

/** Przesyła plik z raportowaniem postępu (0–1). */
export function uploadFile(
  file: File,
  conversationId: string | null,
  onProgress: (fraction: number) => void,
): { promise: Promise<FileInfo>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<FileInfo>((resolve, reject) => {
    xhr.open("POST", "/api/files");
    xhr.setRequestHeader("X-Nexus-Request", "1");
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as FileInfo);
      } else {
        let message = `Nie udało się przesłać pliku (${xhr.status})`;
        try {
          message = JSON.parse(xhr.responseText).detail ?? message;
        } catch {
          /* odpowiedź bez JSON */
        }
        reject(new ApiError(xhr.status, message));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Błąd sieci podczas przesyłania pliku."));
    xhr.onabort = () => reject(new ApiError(0, "Przesyłanie anulowane."));
    const form = new FormData();
    form.append("file", file, file.name);
    if (conversationId) form.append("conversation_id", conversationId);
    xhr.send(form);
  });
  return { promise, abort: () => xhr.abort() };
}

export interface RunEvent {
  id: number;
  type: string;
  data: Record<string, unknown>;
}

const EVENT_TYPES = [
  "run.started",
  "text.block",
  "text.delta",
  "thinking.delta",
  "tool.pending",
  "tool.started",
  "tool.progress",
  "tool.finished",
  "notice",
  "run.completed",
  "run.failed",
  "run.cancelled",
];
export const FINAL_EVENTS = new Set(["run.completed", "run.failed", "run.cancelled"]);

/** Subskrybuje zdarzenia zadania; EventSource sam wznawia połączenie od ostatniego zdarzenia. */
export function subscribeRun(runId: string, onEvent: (event: RunEvent) => void): () => void {
  const source = new EventSource(`/api/runs/${runId}/events`);
  const handler = (message: MessageEvent<string>) => {
    const event: RunEvent = { id: Number(message.lastEventId), type: message.type, data: JSON.parse(message.data) };
    onEvent(event);
    if (FINAL_EVENTS.has(event.type)) source.close();
  };
  for (const type of EVENT_TYPES) source.addEventListener(type, handler as EventListener);
  return () => source.close();
}
