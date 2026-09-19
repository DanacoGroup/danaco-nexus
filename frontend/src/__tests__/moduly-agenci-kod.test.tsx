import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AssistantTurn } from "../api";
import { AssistantMessage } from "../components/Turns";
import { agentTree, elapsed, type SubagentSummary } from "../modules/agenci/api";
import { changeLabel, diffLineClass } from "../modules/kod/api";
import { highlightCode, languageFor } from "../modules/kod/podswietlanie";
import { MODULES } from "../modules/registry";

const agent = (id: string, parent: string | null = null): SubagentSummary => ({
  tool_use_id: id,
  parent_tool_use_id: parent,
  description: id,
  subagent_type: "pomocnik",
  status: "running",
  summary: "",
  progress: "",
  tools_total: 0,
  tools_running: 0,
  duration_ms: 0,
});

describe("moduł Agenci", () => {
  it("układa podagentów w drzewo z poziomami", () => {
    const tree = agentTree([agent("a"), agent("b"), agent("a1", "a"), agent("a1x", "a1"), agent("sierota", "brak")]);
    expect(tree.map((row) => [row.agent.tool_use_id, row.depth])).toEqual([
      ["a", 0],
      ["a1", 1],
      ["a1x", 2],
      ["b", 0],
      ["sierota", 0],
    ]);
  });

  it("formatuje czas trwania", () => {
    const start = "2026-09-19T10:00:00Z";
    expect(elapsed(start, "2026-09-19T10:00:42Z")).toBe("42 s");
    expect(elapsed(start, "2026-09-19T10:03:05Z")).toBe("3 min 05 s");
    expect(elapsed(start, "2026-09-19T12:07:00Z")).toBe("2 h 07 min");
    expect(elapsed(null, null)).toBe("");
  });

  it("rejestruje moduły Kod i Agenci", () => {
    const ids = MODULES.map((item) => item.id);
    expect(ids).toContain("kod");
    expect(ids).toContain("agenci");
  });
});

describe("moduł Kod", () => {
  it("opisuje zmiany git i wiersze różnic", () => {
    expect(changeLabel({ path: "a", index: "?", worktree: "?" })).toEqual({ label: "nowy", tone: "add" });
    expect(changeLabel({ path: "a", index: " ", worktree: "D" }).tone).toBe("del");
    expect(changeLabel({ path: "a", index: " ", worktree: "M" }).label).toBe("zmieniony");
    expect(diffLineClass("+dodane")).toBe("kod-diff-add");
    expect(diffLineClass("-usunięte")).toBe("kod-diff-del");
    expect(diffLineClass("+++ b/plik")).toBe("text-muted");
    expect(diffLineClass("@@ -1 +1 @@")).toBe("text-accent");
  });

  it("dobiera język i zawsze koduje treść jako HTML", () => {
    expect(languageFor("src/app.tsx")).toBe("typescript");
    expect(languageFor("Dockerfile")).toBe("dockerfile");
    expect(languageFor("dane.bin")).toBeNull();
    const plain = highlightCode("<script>alert(1)</script>", "notatka.txt");
    expect(plain.html).toBe("&lt;script&gt;alert(1)&lt;/script&gt;");
    const code = highlightCode('const x = "<b>";', "a.ts");
    expect(code.language).toBe("typescript");
    expect(code.html).toContain("hljs-keyword");
    expect(code.html).not.toContain("<b>");
  });
});

describe("blok podagenta w czacie", () => {
  it("pokazuje opis, postęp i po rozwinięciu własne elementy", () => {
    const turn: AssistantTurn = {
      type: "assistant",
      run_id: "r1",
      status: "running",
      error: "",
      created_at: "2026-09-19T10:00:00Z",
      items: [
        {
          kind: "tool",
          tool_use_id: "a1",
          name: "podagent",
          status: "running",
          summary: "",
          files: [],
          progress: "Czytam dokument",
          agent: {
            description: "Analiza umowy",
            subagent_type: "pomocnik",
            background: true,
            items: [
              { kind: "text", text: "Sprawdzam paragrafy." },
              { kind: "tool", tool_use_id: "t1", name: "extract_text", status: "done", summary: "3 strony", files: [] },
            ],
          },
        } as AssistantTurn["items"][number],
      ],
    };
    render(<AssistantMessage turn={turn} onPreview={() => undefined} />);
    expect(screen.getByText("Podagent: Analiza umowy")).toBeTruthy();
    expect(screen.getByText("Czytam dokument")).toBeTruthy();
    expect(screen.getByText("w tle")).toBeTruthy();
    expect(screen.queryByText("Sprawdzam paragrafy.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { expanded: false }));
    expect(screen.getByText("Sprawdzam paragrafy.")).toBeTruthy();
    expect(screen.getByText("Odczyt tekstu")).toBeTruthy();
  });

  it("pokazuje podagenta z historii rozmowy (bez szczegółów)", () => {
    const turn: AssistantTurn = {
      type: "assistant",
      run_id: "r1",
      status: "done",
      error: "",
      created_at: "2026-09-19T10:00:00Z",
      items: [{ kind: "tool", tool_use_id: "a1", name: "podagent", status: "done", summary: "Umowa jest ważna.", files: [] }],
    };
    render(<AssistantMessage turn={turn} onPreview={() => undefined} />);
    expect(screen.getByText("Podagent: zadanie")).toBeTruthy();
    expect(screen.getByText("Umowa jest ważna.")).toBeTruthy();
  });
});
