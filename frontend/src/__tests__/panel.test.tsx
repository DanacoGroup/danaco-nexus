import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setDeviceToken } from "../api";
import { PanelApp } from "../shell/PanelApp";

const TOKEN = "nxd_" + "p".repeat(43);
const CONVERSATION = "11111111-2222-4333-8444-555555555555";

function sse(body: string): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(body));
        controller.close();
      },
    }),
  );
}

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

describe("panel osadzony (?widok=panel)", () => {
  afterEach(() => {
    cleanup();
    setDeviceToken(null);
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("loguje się kluczem od rodzica, dołącza kontekst strony i wstawia odpowiedź", async () => {
    const sent: { url: string; init?: RequestInit }[] = [];
    let messageBody: { text: string } | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        sent.push({ url, init });
        const method = init?.method ?? "GET";
        if (url === "/api/auth/me") return json({ username: "admin" });
        if (url === "/api/conversations" && method === "GET") return json([]);
        if (url === "/api/conversations" && method === "POST")
          return json({ id: CONVERSATION, title: "Nowa rozmowa", updated_at: "", active: false }, 201);
        if (url.endsWith("/messages")) {
          messageBody = JSON.parse(String(init?.body));
          return json({ run_id: "run-1" }, 202);
        }
        if (url === "/api/runs/run-1/events")
          return sse('id: 1\nevent: text.delta\ndata: {"text":"Dziękujemy za opinię!"}\n\nid: 2\nevent: run.completed\ndata: {}\n\n');
        if (url === `/api/conversations/${CONVERSATION}`)
          return json({
            id: CONVERSATION,
            title: "Odpowiedź",
            files: [],
            active_run: null,
            turns: [
              { type: "user", id: 1, text: messageBody?.text ?? "", files: [], created_at: "" },
              {
                type: "assistant",
                run_id: "run-1",
                status: "done",
                error: "",
                created_at: "",
                items: [{ kind: "text", text: "Dziękujemy za opinię!" }],
              },
            ],
          });
        return json({ detail: "?" }, 404);
      }),
    );
    const posted: unknown[] = [];
    vi.spyOn(window, "postMessage").mockImplementation((message: unknown) => {
      posted.push(message);
    });

    render(<PanelApp />);
    expect(posted).toContainEqual({ type: "nexus:ready" });

    const parent = (data: unknown) =>
      act(() => {
        window.dispatchEvent(new MessageEvent("message", { data, source: window }));
      });
    await parent({ type: "nexus:auth", token: TOKEN });
    await screen.findByRole("combobox", { name: "Rozmowa" });
    const me = sent.find((call) => call.url === "/api/auth/me");
    expect(new Headers(me?.init?.headers).get("Authorization")).toBe(`Bearer ${TOKEN}`);

    await parent({
      type: "nexus:context",
      context: { kind: "page", title: "Opinie gości", url: "https://booking.com/opinie", text: "Hałas w nocy." },
    });
    expect(screen.getByText("Opinie gości")).toBeTruthy();

    await parent({ type: "nexus:prompt", text: "Odpowiedz uprzejmie", send: true });
    await waitFor(() => expect(messageBody).not.toBeNull());
    expect(messageBody!.text).toBe("[Kontekst: page „Opinie gości” https://booking.com/opinie]\nHałas w nocy.\n\nOdpowiedz uprzejmie");

    const insert = await screen.findByRole("button", { name: /Wstaw/ });
    // Historia pokazuje nagłówek kontekstu i pytanie, nie całą treść strony.
    expect(screen.queryByText(/Hałas w nocy/)).toBeNull();
    fireEvent.click(insert);
    expect(posted).toContainEqual({ type: "nexus:insert", text: "Dziękujemy za opinię!" });
  });

  it("bez klucza i sesji prosi o połączenie urządzenia", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ detail: "Wymagane logowanie." }, 401)),
    );
    render(<PanelApp />);
    await act(async () => {
      vi.advanceTimersByTime(1500);
    });
    vi.useRealTimers();
    expect(await screen.findByText("Połącz panel z Nexusem")).toBeTruthy();
  });
});
