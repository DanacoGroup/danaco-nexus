import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReportView } from "./ReportView";

const REPORT = {
  id: "r1",
  conversation_id: "c1",
  kind: "deep",
  question: "Czy pompa ciepła się opłaca?",
  depth: "quick",
  collection_id: null,
  title: "Research: pompa",
  status: "done",
  run_id: "run1",
  error: "",
  created_at: "2026-09-19T10:00:00+00:00",
  active: false,
  report: "## Wnioski\nOpłaca się po dociepleniu [1].\n\n## Źródła\n- [1] Poradnik – Energia Dziś, 2026 – https://example.com/pompy",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ReportView", () => {
  it("pokazuje raport z przypisami i otwiera źródło po kliknięciu", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(REPORT), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const openConversation = vi.fn();
    const { container } = render(
      <ReportView
        reportId="r1"
        collections={[]}
        openConversation={openConversation}
        onChanged={() => undefined}
        onDeleted={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("Czy pompa ciepła się opłaca?")).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledWith("/api/research/badania/r1", expect.objectContaining({ method: "GET" }));
    const cite = container.querySelector<HTMLAnchorElement>("a[data-cite='1']");
    expect(cite).not.toBeNull();
    expect(screen.getByText("Źródła (1)")).toBeTruthy();
    await act(async () => {
      fireEvent.click(cite!);
    });
    const panel = screen.getByRole("complementary", { name: "Źródło 1" });
    expect(panel.textContent).toContain("Poradnik – Energia Dziś, 2026");
    expect(panel.querySelector("a[href='https://example.com/pompy']")).not.toBeNull();
    fireEvent.click(screen.getByText("Dopytaj w czacie"));
    expect(openConversation).toHaveBeenCalledWith("c1");
  });
});
