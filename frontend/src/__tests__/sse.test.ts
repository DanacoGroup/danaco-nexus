import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchEventStream, SseParser, type SseMessage } from "../shell/sse";

describe("SseParser", () => {
  it("składa zdarzenia z dowolnie podzielonych kawałków", () => {
    const parser = new SseParser();
    const stream = 'retry: 2000\n\nid: 7\nevent: text.delta\ndata: {"text":"Dzień"}\n\n: keepalive\n\nid: 8\nevent: run.completed\ndata: {}\n\n';
    const messages: SseMessage[] = [];
    for (let index = 0; index < stream.length; index += 5) messages.push(...parser.push(stream.slice(index, index + 5)));
    expect(messages).toEqual([
      { id: "7", event: "text.delta", data: '{"text":"Dzień"}' },
      { id: "8", event: "run.completed", data: "{}" },
    ]);
    expect(parser.retry).toBe(2000);
    expect(parser.lastEventId).toBe("8");
  });

  it("obsługuje CRLF (także rozdzielone między kawałki), wiele linii danych i domyślny typ", () => {
    const parser = new SseParser();
    expect(parser.push("data: a\r")).toEqual([]);
    expect(parser.push("\ndata: b\r\n\r\n")).toEqual([{ id: "", event: "message", data: "a\nb" }]);
    expect(parser.push("data:bez-spacji\n\n")).toEqual([{ id: "", event: "message", data: "bez-spacji" }]);
  });

  it("pomija zdarzenie bez danych i nieznane pola", () => {
    const parser = new SseParser();
    expect(parser.push("event: pusty\n\nfoo: bar\ndata: x\n\n")).toEqual([{ id: "", event: "message", data: "x" }]);
  });
});

function streamResponse(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { status, headers: { "Content-Type": "text/event-stream" } });
}

describe("fetchEventStream", () => {
  afterEach(() => vi.useRealTimers());

  it("wysyła nagłówek klucza i wznawia od Last-Event-ID po zerwaniu", async () => {
    const calls: Record<string, string>[] = [];
    const received: string[] = [];
    let finish: () => void = () => {};
    const done = new Promise<void>((resolve) => (finish = resolve));
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ ...(init?.headers as Record<string, string>) });
      if (calls.length === 1) return streamResponse(["id: 1\nevent: run.started\ndata: {}\n\n"]);
      return streamResponse(["id: 2\nevent: run.completed\ndata: {}\n\n"]);
    }) as unknown as typeof fetch;
    const stop = fetchEventStream("/api/runs/x/events", {
      headers: { Authorization: "Bearer nxd_test" },
      fetchImpl,
      retryMs: 5,
      onMessage: (message) => {
        received.push(message.event);
        if (message.event === "run.completed") finish();
      },
    });
    await done;
    stop();
    expect(received).toEqual(["run.started", "run.completed"]);
    expect(calls[0].Authorization).toBe("Bearer nxd_test");
    expect(calls[0]["Last-Event-ID"]).toBeUndefined();
    expect(calls[1]["Last-Event-ID"]).toBe("1");
  });

  it("kończy przy 401 bez ponawiania", async () => {
    const fetchImpl = vi.fn(async () => new Response("", { status: 401 })) as unknown as typeof fetch;
    const fatal = await new Promise<number>((resolve) => {
      fetchEventStream("/x", { headers: {}, fetchImpl, retryMs: 1, onMessage: () => {}, onFatal: resolve });
    });
    expect(fatal).toBe(401);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
