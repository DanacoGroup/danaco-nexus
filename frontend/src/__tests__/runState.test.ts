import { describe, expect, it } from "vitest";
import type { RunEvent } from "../api";
import { renderMarkdown } from "../components/Markdown";
import { applyRunEvent, emptyAssistantTurn, formatSize, toolLabel } from "../runState";

const event = (type: string, data: Record<string, unknown> = {}, id = 1): RunEvent => ({ id, type, data });

describe("applyRunEvent", () => {
  it("łączy fragmenty tekstu i przemyśleń w kolejności", () => {
    let turn = emptyAssistantTurn("r1");
    turn = applyRunEvent(turn, event("run.started"));
    turn = applyRunEvent(turn, event("thinking.delta", { text: "Analizuję " }));
    turn = applyRunEvent(turn, event("thinking.delta", { text: "plik." }));
    turn = applyRunEvent(turn, event("text.delta", { text: "Gotowe" }));
    turn = applyRunEvent(turn, event("text.delta", { text: "!" }));
    expect(turn.status).toBe("running");
    expect(turn.items).toEqual([
      { kind: "thinking", text: "Analizuję plik." },
      { kind: "text", text: "Gotowe!" },
    ]);
  });

  it("śledzi cykl życia narzędzia i pliki wynikowe", () => {
    let turn = emptyAssistantTurn("r1");
    turn = applyRunEvent(turn, event("tool.started", { tool_use_id: "t1", name: "ocr_documents", input: {} }));
    turn = applyRunEvent(turn, event("tool.progress", { tool_use_id: "t1", text: "strona 1/3" }));
    const running = turn.items[0];
    expect(running.kind === "tool" && running.progress).toBe("strona 1/3");
    const file = { id: "f1", name: "skan_OCR.pdf", mime: "application/pdf", size: 1000 };
    turn = applyRunEvent(turn, event("tool.finished", { tool_use_id: "t1", status: "done", summary: "OK", files: [file], duration_ms: 1500 }));
    const done = turn.items[0];
    expect(done.kind).toBe("tool");
    if (done.kind === "tool") {
      expect(done.status).toBe("done");
      expect(done.files).toEqual([file]);
      expect(done.progress).toBeUndefined();
    }
  });

  it("matches MCP progress events by tool name", () => {
    let turn = emptyAssistantTurn("r1");
    turn = applyRunEvent(turn, event("tool.started", { tool_use_id: "t1", name: "ocr_documents", input: {} }));
    turn = applyRunEvent(turn, event("tool.finished", { tool_use_id: "t1", status: "done", summary: "OK", files: [], duration_ms: 1 }));
    turn = applyRunEvent(turn, event("tool.started", { tool_use_id: "t2", name: "ocr_documents", input: {} }));
    turn = applyRunEvent(turn, event("tool.progress", { name: "ocr_documents", text: "strona 2/5" }));
    const [first, second] = turn.items;
    expect(first.kind === "tool" && first.progress).toBeFalsy();
    expect(second.kind === "tool" && second.progress).toBe("strona 2/5");
    expect(applyRunEvent(turn, event("tool.progress", { name: "pdf_split", text: "x" }))).toBe(turn);
  });

  it("zapisuje błąd i anulowanie zadania", () => {
    const failed = applyRunEvent(emptyAssistantTurn("r1"), event("run.failed", { error: "Brak klucza API" }));
    expect(failed).toMatchObject({ status: "failed", error: "Brak klucza API" });
    const cancelled = applyRunEvent(emptyAssistantTurn("r1"), event("run.cancelled", {}));
    expect(cancelled.status).toBe("cancelled");
  });
});

describe("pomocnicze", () => {
  it("formatuje rozmiary po polsku", () => {
    expect(formatSize(512)).toBe("512 B");
    expect(formatSize(1536)).toBe("1,5 KB");
    expect(formatSize(5 * 1024 * 1024)).toBe("5 MB");
  });

  it("tłumaczy nazwy narzędzi", () => {
    expect(toolLabel("pdf_split")).toBe("Podział PDF");
    expect(toolLabel("nieznane")).toBe("nieznane");
  });

  it("oczyszcza HTML w Markdown i otwiera linki w nowej karcie", () => {
    const html = renderMarkdown('**Tak** <img src=x onerror="alert(1)"> [link](https://example.com) <script>alert(2)</script>');
    expect(html).toContain("<strong>Tak</strong>");
    expect(html).not.toContain("onerror");
    expect(html).not.toContain("<script");
    expect(html).toContain('target="_blank"');
  });
});
