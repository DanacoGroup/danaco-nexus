import { describe, expect, it } from "vitest";
import type { RunEvent, TurnItem } from "../api";
import { agentInfo, agentStats, applyRunEvent, emptyAssistantTurn, isAgentItem, toolDetail } from "../runState";

let sequence = 0;
const event = (type: string, data: Record<string, unknown> = {}): RunEvent => ({ id: ++sequence, type, data });

function agentAt(items: TurnItem[], index: number) {
  const item = items[index];
  if (!isAgentItem(item)) throw new Error("oczekiwano podagenta");
  return item;
}

describe("podagenci w turze", () => {
  it("zagnieżdża tekst i narzędzia podagenta po parent_tool_use_id", () => {
    let turn = emptyAssistantTurn("r1");
    const events = [
      event("run.started"),
      event("text.delta", { text: "Dzielę zadanie." }),
      event("tool.started", {
        tool_use_id: "a1",
        name: "podagent",
        input: {},
        agent: { description: "Konwersja skanów", subagent_type: "pomocnik", background: false },
      }),
      event("tool.started", {
        tool_use_id: "a2",
        name: "podagent",
        input: {},
        agent: { description: "Opis", subagent_type: "pomocnik", background: true },
      }),
      event("text.block", { parent_tool_use_id: "a1" }),
      event("text.delta", { parent_tool_use_id: "a1", text: "Konwertuję." }),
      event("tool.started", { tool_use_id: "t1", name: "convert_images", input: {}, parent_tool_use_id: "a1" }),
      event("tool.progress", { name: "convert_images", text: "1/2" }),
      event("text.delta", { parent_tool_use_id: "a2", text: "Czytam." }),
      event("tool.progress", { tool_use_id: "a2", text: "Pracuje w tle…" }),
    ];
    for (const item of events) turn = applyRunEvent(turn, item);

    expect(turn.items).toHaveLength(3);
    expect(turn.items[0]).toEqual({ kind: "text", text: "Dzielę zadanie." });
    const first = agentAt(turn.items, 1);
    expect(first.agent.description).toBe("Konwersja skanów");
    expect(first.agent.items[0]).toEqual({ kind: "text", text: "Konwertuję." });
    const nested = first.agent.items[1];
    expect(nested.kind === "tool" && nested.progress).toBe("1/2");
    expect(agentStats(first.agent)).toEqual({ total: 1, running: 1 });
    const second = agentAt(turn.items, 2);
    expect(second.agent.background).toBe(true);
    expect(second.progress).toBe("Pracuje w tle…");
    expect(second.agent.items).toEqual([{ kind: "text", text: "Czytam." }]);

    const file = { id: "f1", name: "skan.png", mime: "image/png", size: 10 };
    turn = applyRunEvent(
      turn,
      event("tool.finished", { tool_use_id: "t1", status: "done", summary: "OK", files: [file], parent_tool_use_id: "a1" }),
    );
    turn = applyRunEvent(
      turn,
      event("tool.finished", { tool_use_id: "a1", status: "done", summary: "Gotowe", files: [file], duration_ms: 900 }),
    );
    const done = agentAt(turn.items, 1);
    expect(done.status).toBe("done");
    expect(done.files).toEqual([file]);
    const finishedTool = done.agent.items[1];
    expect(finishedTool.kind === "tool" && finishedTool.status).toBe("done");
    expect(agentStats(done.agent)).toEqual({ total: 1, running: 0 });
  });

  it("obsługuje podagentów zagnieżdżonych i nieznanego rodzica", () => {
    let turn = emptyAssistantTurn("r1");
    turn = applyRunEvent(turn, event("tool.started", { tool_use_id: "a1", name: "podagent", agent: { description: "A" } }));
    turn = applyRunEvent(
      turn,
      event("tool.started", { tool_use_id: "a2", name: "podagent", parent_tool_use_id: "a1", agent: { description: "B" } }),
    );
    turn = applyRunEvent(turn, event("text.delta", { parent_tool_use_id: "a2", text: "Głęboko." }));
    const outer = agentAt(turn.items, 0);
    const inner = agentAt(outer.agent.items, 0);
    expect(inner.agent.items).toEqual([{ kind: "text", text: "Głęboko." }]);
    // Zdarzenie z nieznanym rodzicem trafia na najwyższy poziom (nic nie ginie).
    turn = applyRunEvent(turn, event("text.delta", { parent_tool_use_id: "brak", text: "Luźny tekst" }));
    expect(turn.items[1]).toEqual({ kind: "text", text: "Luźny tekst" });
  });

  it("rozpoznaje podagenta z historii rozmowy i opisuje narzędzia wbudowane", () => {
    const history = { kind: "tool" as const, tool_use_id: "a1", name: "podagent", status: "done", summary: "Wynik", files: [] };
    expect(agentInfo(history)).toEqual({ description: "", subagent_type: "", background: false, items: [] });
    expect(agentInfo({ ...history, name: "ocr_documents" })).toBeNull();
    expect(toolDetail({ ...history, name: "Bash", input: { command: "npm test" } })).toBe("npm test");
    expect(toolDetail({ ...history, name: "Read", input: { file_path: "src/app.ts" } })).toBe("src/app.ts");
  });
});
