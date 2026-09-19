// Strumień zdarzeń (Server-Sent Events) czytany przez fetch – dla trybu klucza urządzenia,
// w którym EventSource nie może wysłać nagłówka Authorization.

export interface SseMessage {
  id: string;
  event: string;
  data: string;
}

/** Przyrostowy parser formatu text/event-stream (dowolny podział na kawałki). */
export class SseParser {
  lastEventId = "";
  retry: number | null = null;
  private buffer = "";
  private event = "";
  private data: string[] = [];

  push(chunk: string): SseMessage[] {
    this.buffer += chunk;
    const messages: SseMessage[] = [];
    // „\r” na końcu kawałka może być początkiem „\r\n” – czeka na następny kawałek.
    const complete = this.buffer.endsWith("\r") ? this.buffer.length - 1 : this.buffer.length;
    const lines = this.buffer.slice(0, complete).split(/\r\n|\r|\n/);
    this.buffer = lines.pop() + this.buffer.slice(complete);
    for (const line of lines) {
      const message = this.line(line);
      if (message) messages.push(message);
    }
    return messages;
  }

  private line(line: string): SseMessage | null {
    if (line === "") {
      if (this.data.length === 0) {
        this.event = "";
        return null;
      }
      const message = { id: this.lastEventId, event: this.event || "message", data: this.data.join("\n") };
      this.event = "";
      this.data = [];
      return message;
    }
    if (line.startsWith(":")) return null;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") this.event = value;
    else if (field === "data") this.data.push(value);
    else if (field === "id" && !value.includes("\0")) this.lastEventId = value;
    else if (field === "retry" && /^\d+$/.test(value)) this.retry = Number(value);
    return null;
  }
}

export interface FetchStreamOptions {
  headers: Record<string, string>;
  onMessage: (message: SseMessage) => void;
  /** Błąd, po którym ponawianie nie ma sensu (np. 401, 404). */
  onFatal?: (status: number) => void;
  fetchImpl?: typeof fetch;
  retryMs?: number;
}

/** Czyta strumień zdarzeń fetch-em i wznawia połączenie od ostatniego zdarzenia (Last-Event-ID). */
export function fetchEventStream(url: string, options: FetchStreamOptions): () => void {
  const controller = new AbortController();
  const doFetch = options.fetchImpl ?? fetch.bind(globalThis);
  const parser = new SseParser();
  let closed = false;

  const wait = (ms: number) =>
    new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, ms);
      controller.signal.addEventListener("abort", () => {
        clearTimeout(timer);
        resolve();
      });
    });

  const run = async () => {
    while (!closed) {
      try {
        const headers: Record<string, string> = { ...options.headers, Accept: "text/event-stream" };
        if (parser.lastEventId) headers["Last-Event-ID"] = parser.lastEventId;
        const response = await doFetch(url, { headers, signal: controller.signal, cache: "no-store" });
        if (response.status === 401 || response.status === 403 || response.status === 404) {
          options.onFatal?.(response.status);
          return;
        }
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        while (!closed) {
          const { done, value } = await reader.read();
          if (done) break;
          for (const message of parser.push(decoder.decode(value, { stream: true }))) {
            if (closed) break;
            options.onMessage(message);
          }
        }
      } catch {
        /* zerwane połączenie – ponowienie niżej */
      }
      if (!closed) await wait(parser.retry ?? options.retryMs ?? 2000);
    }
  };
  void run();

  return () => {
    closed = true;
    controller.abort();
  };
}
