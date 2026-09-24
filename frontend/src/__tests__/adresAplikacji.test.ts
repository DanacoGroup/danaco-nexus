// Od 23.09.2026 „/” jest stroną produktu, a okno aplikacji stoi pod `/czat`.
//
// Powłoka miała kilka nawigacji w postaci `chat.currentId ? "/c/…" : "/"`: po zamknięciu
// rozmowy albo wejściu w Czat i Głos bez otwartej rozmowy zalogowany lądował na stronie
// produktu. Test czyta źródła, bo te ścieżki odpalają się dopiero w pełnym oknie z sesją.

import { describe, expect, it } from "vitest";
import zrodloApp from "../App.tsx?raw";
import zrodloSidebar from "../components/Sidebar.tsx?raw";
import zrodloWorkspace from "../shell/Workspace.tsx?raw";

const NAWIGACJA_DO_KORZENIA = /navigate\([^;]*?(?:"\/"|'\/')/g;

describe("okno aplikacji nie odsyła na stronę produktu", () => {
  it.each([
    ["App.tsx", zrodloApp],
    ["Workspace.tsx", zrodloWorkspace],
    ["Sidebar.tsx", zrodloSidebar],
  ])("%s nie nawiguje do „/”", (_nazwa, zrodlo) => {
    expect(zrodlo.match(NAWIGACJA_DO_KORZENIA) ?? []).toEqual([]);
  });
});
