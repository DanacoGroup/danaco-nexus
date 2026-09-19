import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, authHeaders, setDeviceToken, subscribeRun, type RunEvent } from "../api";
import { pairingUri } from "../modules/urzadzenia/DevicesPage";
import { qrMatrix } from "../modules/urzadzenia/Qr";
import { navEntries, splitForBottomBar, type NavEntry } from "../shell/ModuleNav";
import { deviceLabel, urlBase64ToUint8Array } from "../shell/push";
import type { ActiveTask } from "../shell/startApi";
import { elapsedLabel, finishedSince } from "../shell/TasksPanel";

const entry = (id: string): NavEntry => ({ id, label: id, description: id, icon: () => null });

describe("nawigacja modułów", () => {
  it("czat i głos są zawsze pierwsze", () => {
    expect(navEntries([]).map((item) => item.id)).toEqual(["chat", "glos"]);
  });

  it("dolny pasek mieści 5 pozycji, reszta trafia do „Więcej”", () => {
    const entries = ["chat", "glos", "a", "b", "c", "d", "e"].map(entry);
    const { bar, more } = splitForBottomBar(entries, "chat");
    expect(bar.map((item) => item.id)).toEqual(["chat", "glos", "a", "b"]);
    expect(more.map((item) => item.id)).toEqual(["c", "d", "e"]);
    const withActive = splitForBottomBar(entries, "d");
    expect(withActive.bar.map((item) => item.id)).toEqual(["chat", "glos", "a", "d"]);
    expect(withActive.more.map((item) => item.id)).toEqual(["b", "c", "e"]);
    expect(splitForBottomBar(entries.slice(0, 5), "chat").more).toEqual([]);
  });
});

describe("zadania w toku", () => {
  const task = (run_id: string): ActiveTask => ({
    run_id,
    conversation_id: `c-${run_id}`,
    title: run_id,
    mode: "chat",
    status: "running",
    created_at: "2026-09-19T10:00:00Z",
    started_at: null,
    tool: "",
  });

  it("wykrywa zadania zakończone od poprzedniego odczytu", () => {
    expect(finishedSince([task("a"), task("b")], [task("b"), task("c")]).map((item) => item.run_id)).toEqual(["a"]);
    expect(finishedSince([], [task("a")])).toEqual([]);
  });

  it("opisuje czas trwania", () => {
    const start = "2026-09-19T10:00:00Z";
    const at = (seconds: number) => new Date(start).getTime() + seconds * 1000;
    expect(elapsedLabel(start, at(42))).toBe("42 s");
    expect(elapsedLabel(start, at(125))).toBe("2 min");
    expect(elapsedLabel(start, at(3 * 3600 + 5 * 60))).toBe("3 h 5 min");
    expect(elapsedLabel(start, at(-5))).toBe("0 s");
  });
});

describe("powiadomienia push i urządzenia", () => {
  it("dekoduje klucz VAPID base64url", () => {
    const bytes = urlBase64ToUint8Array("BAEC_-8");
    expect(Array.from(bytes)).toEqual([4, 1, 2, 255, 239]);
  });

  it("nazywa urządzenie po systemie i przeglądarce", () => {
    expect(deviceLabel("Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 Chrome/140.0 Mobile Safari/537.36")).toBe(
      "Android – Chrome",
    );
    expect(deviceLabel("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0 Safari/537.36 Edg/140.0")).toBe("Windows – Edge");
    expect(deviceLabel("Mozilla/5.0 (iPhone; CPU iPhone OS 19_0 like Mac OS X) Version/19.0 Mobile Safari/604.1")).toBe(
      "iPhone/iPad – Safari",
    );
  });

  it("koduje adres parowania w kodzie QR", () => {
    const uri = pairingUri("https://danaco-nexus.pl", "nxd_abc-DEF_123");
    expect(uri).toBe("danaconexus://sparuj?serwer=https%3A%2F%2Fdanaco-nexus.pl&klucz=nxd_abc-DEF_123");
    const matrix = qrMatrix(uri);
    expect(matrix.length).toBeGreaterThanOrEqual(21);
    expect(matrix.every((row) => row.length === matrix.length)).toBe(true);
    // Wzorce pozycjonujące w rogach są zawsze ciemne.
    expect(matrix[0][0] && matrix[0][matrix.length - 1] && matrix[matrix.length - 1][0]).toBe(true);
  });
});

describe("tryb klucza urządzenia w kliencie API", () => {
  afterEach(() => {
    setDeviceToken(null);
    vi.unstubAllGlobals();
  });

  it("zamienia ciasteczko i nagłówek CSRF na Authorization", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);
    expect(authHeaders()).toEqual({ "X-Nexus-Request": "1" });
    await apiFetch("/api/conversations");
    let init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("X-Nexus-Request")).toBe("1");
    expect(init.credentials).toBe("same-origin");

    setDeviceToken("nxd_" + "k".repeat(40));
    await apiFetch("/api/conversations", { method: "POST", headers: { "Content-Type": "application/json" } });
    init = fetchMock.mock.calls[1][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe(`Bearer nxd_${"k".repeat(40)}`);
    expect(headers.get("X-Nexus-Request")).toBeNull();
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init.credentials).toBe("omit");
  });

  it("strumień zadania czyta fetch-em z nagłówkiem klucza", async () => {
    setDeviceToken("nxd_" + "k".repeat(40));
    const encoder = new TextEncoder();
    const fetchMock = vi.fn(
      async () =>
        new Response(
          new ReadableStream<Uint8Array>({
            start(controller) {
              controller.enqueue(encoder.encode('id: 3\nevent: text.delta\ndata: {"text":"Hej"}\n\nid: 4\nevent: run.completed\ndata: {}\n\n'));
              controller.close();
            },
          }),
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const events: RunEvent[] = [];
    await new Promise<void>((resolve) => {
      subscribeRun("run-1", (event) => {
        events.push(event);
        if (event.type === "run.completed") resolve();
      });
    });
    expect(events).toEqual([
      { id: 3, type: "text.delta", data: { text: "Hej" } },
      { id: 4, type: "run.completed", data: {} },
    ]);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/runs/run-1/events");
    expect((init.headers as Record<string, string>).Authorization).toMatch(/^Bearer nxd_/);
  });
});
