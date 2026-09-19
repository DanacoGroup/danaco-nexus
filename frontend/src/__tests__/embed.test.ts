import { describe, expect, it, vi } from "vitest";
import type { AssistantTurn, UserTurn } from "../api";
import {
  assistantText,
  composeMessage,
  CONTEXT_TEXT_LIMIT,
  dataUrlToFile,
  formatContext,
  fromParent,
  parseParentMessage,
  plainText,
  postToParent,
  splitContext,
} from "../shell/embed";
import { displayTurn } from "../shell/turnDisplay";

const TOKEN = "nxd_" + "a".repeat(43);
const PNG = "data:image/png;base64,iVBORw0KGgo=";

describe("parseParentMessage", () => {
  it("przyjmuje poprawny klucz urządzenia i odrzuca inne", () => {
    expect(parseParentMessage({ type: "nexus:auth", token: TOKEN })).toEqual({ type: "nexus:auth", token: TOKEN });
    expect(parseParentMessage({ type: "nexus:auth", token: "abc" })).toBeNull();
    expect(parseParentMessage({ type: "nexus:auth", token: "nxd_krotki" })).toBeNull();
    expect(parseParentMessage({ type: "nexus:auth", token: `${TOKEN}"<x>` })).toBeNull();
  });

  it("normalizuje kontekst strony i ekranu", () => {
    const parsed = parseParentMessage({
      type: "nexus:context",
      context: { kind: "page", title: " Opinie\n gości ", url: "https://booking.com/x y", text: "Treść", image: PNG, extra: 1 },
    });
    expect(parsed).toEqual({
      type: "nexus:context",
      context: { kind: "page", title: "Opinie gości", url: "https://booking.com/xy", text: "Treść", image: PNG },
    });
    expect(parseParentMessage({ type: "nexus:context", context: null })).toEqual({ type: "nexus:context", context: null });
    expect(parseParentMessage({ type: "nexus:context", context: { kind: "okno", title: "", url: "", text: "" } })).toBeNull();
  });

  it("odrzuca obraz, który nie jest obrazem data URL, i skraca długi tekst", () => {
    const parsed = parseParentMessage({
      type: "nexus:context",
      context: { kind: "screen", title: "Excel", url: "", text: "x".repeat(CONTEXT_TEXT_LIMIT + 50), image: "javascript:alert(1)" },
    });
    expect(parsed?.type).toBe("nexus:context");
    const context = parsed && parsed.type === "nexus:context" ? parsed.context : null;
    expect(context?.image).toBeUndefined();
    expect(context?.text.length).toBeLessThan(CONTEXT_TEXT_LIMIT + 40);
    expect(context?.text.endsWith("[…treść skrócona]")).toBe(true);
  });

  it("obsługuje prompt i pomija nieznane komunikaty", () => {
    expect(parseParentMessage({ type: "nexus:prompt", text: "Streść stronę", send: true })).toEqual({
      type: "nexus:prompt",
      text: "Streść stronę",
      send: true,
    });
    expect(parseParentMessage({ type: "nexus:prompt", text: "Szkic" })).toEqual({ type: "nexus:prompt", text: "Szkic", send: false });
    expect(parseParentMessage({ type: "nexus:prompt", text: "   " })).toBeNull();
    expect(parseParentMessage({ type: "inny" })).toBeNull();
    expect(parseParentMessage("nexus:auth")).toBeNull();
    expect(parseParentMessage(null)).toBeNull();
  });
});

describe("blok kontekstu", () => {
  const context = { kind: "page" as const, title: "Opinie gości", url: "https://booking.com/opinie", text: "Hałas w nocy." };

  it("ma format z umowy i poprzedza pytanie", () => {
    expect(formatContext(context)).toBe("[Kontekst: page „Opinie gości” https://booking.com/opinie]\nHałas w nocy.");
    expect(composeMessage("Odpowiedz uprzejmie", context)).toBe(
      "[Kontekst: page „Opinie gości” https://booking.com/opinie]\nHałas w nocy.\n\nOdpowiedz uprzejmie",
    );
    expect(composeMessage("Samo pytanie", null)).toBe("Samo pytanie");
    expect(formatContext({ kind: "screen", title: "Excel", url: "", text: "" })).toBe("[Kontekst: screen „Excel”]");
  });

  it("wiadomość z kontekstem wyświetla nagłówek i pytanie", () => {
    const message = composeMessage("Odpowiedz uprzejmie", { ...context, text: "Akapit 1\n\nAkapit 2" });
    expect(splitContext(message)).toEqual({
      header: "Kontekst: page „Opinie gości” https://booking.com/opinie",
      question: "Odpowiedz uprzejmie",
    });
    expect(splitContext("Zwykła wiadomość")).toEqual({ header: null, question: "Zwykła wiadomość" });
    const turn: UserTurn = { type: "user", id: 1, text: message, files: [], created_at: "" };
    expect(displayTurn(turn).text).toBe("[Kontekst: page „Opinie gości” https://booking.com/opinie]\n\nOdpowiedz uprzejmie");
  });
});

describe("pomocnicze", () => {
  it("zamienia obraz data URL na plik", async () => {
    const file = dataUrlToFile("data:image/jpeg;base64,/9j/4AAQ", "zrzut-ekranu");
    expect(file?.name).toBe("zrzut-ekranu.jpg");
    expect(file?.type).toBe("image/jpeg");
    expect(file?.size).toBe(6);
    expect(dataUrlToFile("data:text/html;base64,PGI+", "x")).toBeNull();
  });

  it("wyciąga sam tekst odpowiedzi", () => {
    const turn: AssistantTurn = {
      type: "assistant",
      run_id: "r",
      status: "done",
      error: "",
      created_at: "",
      items: [
        { kind: "thinking", text: "myślę" },
        { kind: "text", text: " Dzień dobry! " },
        { kind: "tool", tool_use_id: "t", name: "x", status: "done", summary: "", files: [] },
        { kind: "text", text: "Pozdrawiam" },
      ],
    };
    expect(assistantText(turn)).toBe("Dzień dobry!\n\nPozdrawiam");
  });

  it("zamienia Markdown odpowiedzi na zwykły tekst do wstawienia", () => {
    expect(plainText("## Odpowiedź\n\nDziękujemy za **ciepłe** słowa i *uwagi*.\n\n* śniadania\n* `cisza nocna`\n\n[Strona](https://x.pl)")).toBe(
      "Odpowiedź\n\nDziękujemy za ciepłe słowa i uwagi.\n\n- śniadania\n- cisza nocna\n\nStrona (https://x.pl)",
    );
    expect(plainText("Cena 2*3*4 zł")).toBe("Cena 2*3*4 zł");
  });

  it("przyjmuje komunikaty tylko od rodzica i wysyła do rodzica", () => {
    const parent = { postMessage: vi.fn() } as unknown as Window;
    const framed = { parent } as unknown as Window;
    expect(fromParent(new MessageEvent("message", { source: parent as unknown as MessageEventSource }), framed)).toBe(true);
    expect(fromParent(new MessageEvent("message", { source: null }), framed)).toBe(false);
    postToParent({ type: "nexus:insert", text: "Tekst" }, framed);
    expect(parent.postMessage).toHaveBeenCalledWith({ type: "nexus:insert", text: "Tekst" }, "*");

    const top = {} as Window & { parent: Window };
    top.parent = top;
    expect(fromParent(new MessageEvent("message", { source: null }), top)).toBe(true);
  });
});
