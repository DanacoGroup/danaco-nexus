// Protokół trybu osadzonego (?widok=panel): komunikaty postMessage między panelem a rodzicem
// (rozszerzenie przeglądarki, Nexus Desktop, aplikacja Android).
//
// Rodzic -> panel: nexus:auth {token}, nexus:context {context}, nexus:prompt {text, send?}
// Panel -> rodzic: nexus:ready, nexus:insert {text}, nexus:copy {text}

import type { AssistantTurn } from "../api";

export interface EmbedContext {
  kind: "page" | "screen";
  title: string;
  url: string;
  text: string;
  /** Zrzut ekranu lub obraz strony jako data:image/…;base64. */
  image?: string;
}

export type ParentMessage =
  | { type: "nexus:auth"; token: string }
  | { type: "nexus:context"; context: EmbedContext | null }
  | { type: "nexus:prompt"; text: string; send: boolean };

export type PanelMessage =
  | { type: "nexus:ready" }
  | { type: "nexus:insert"; text: string }
  | { type: "nexus:copy"; text: string };

/** Limit tekstu kontekstu – wiadomość na serwerze może mieć najwyżej 100 000 znaków. */
export const CONTEXT_TEXT_LIMIT = 60_000;
const TOKEN = /^nxd_[A-Za-z0-9_-]{16,200}$/;
const IMAGE_DATA_URL = /^data:(image\/(?:png|jpeg|webp|gif));base64,([A-Za-z0-9+/=\s]+)$/;

const text = (value: unknown, limit: number): string => (typeof value === "string" ? value.slice(0, limit) : "");

/** Sprawdza i normalizuje komunikat od rodzica; nieznane lub błędne komunikaty są pomijane. */
export function parseParentMessage(data: unknown): ParentMessage | null {
  if (!data || typeof data !== "object") return null;
  const message = data as Record<string, unknown>;
  switch (message.type) {
    case "nexus:auth":
      return typeof message.token === "string" && TOKEN.test(message.token)
        ? { type: "nexus:auth", token: message.token }
        : null;
    case "nexus:context": {
      const raw = message.context;
      if (raw === null) return { type: "nexus:context", context: null };
      if (!raw || typeof raw !== "object") return null;
      const context = raw as Record<string, unknown>;
      if (context.kind !== "page" && context.kind !== "screen") return null;
      const image = typeof context.image === "string" && IMAGE_DATA_URL.test(context.image) ? context.image : undefined;
      let body = text(context.text, CONTEXT_TEXT_LIMIT + 1);
      if (body.length > CONTEXT_TEXT_LIMIT) body = `${body.slice(0, CONTEXT_TEXT_LIMIT)}\n[…treść skrócona]`;
      return {
        type: "nexus:context",
        context: {
          kind: context.kind,
          // Nagłówek bloku kontekstu jest jednowierszowy.
          title: text(context.title, 300).replace(/\s+/g, " ").trim(),
          url: text(context.url, 2000).replace(/\s+/g, ""),
          text: body,
          image,
        },
      };
    }
    case "nexus:prompt": {
      const prompt = text(message.text, 20_000);
      return prompt.trim() ? { type: "nexus:prompt", text: prompt, send: message.send === true } : null;
    }
    default:
      return null;
  }
}

/** Blok kontekstu dołączany do wiadomości: „[Kontekst: <kind> „<title>” <url>]\n<text>”. */
export function formatContext(context: EmbedContext): string {
  const header = `[Kontekst: ${context.kind} „${context.title}”${context.url ? ` ${context.url}` : ""}]`;
  return context.text ? `${header}\n${context.text}` : header;
}

/** Treść wysyłanej wiadomości: blok kontekstu (gdy jest), potem pytanie użytkownika. */
export function composeMessage(userText: string, context: EmbedContext | null): string {
  if (!context) return userText;
  return userText ? `${formatContext(context)}\n\n${userText}` : formatContext(context);
}

/**
 * Podział wiadomości z blokiem kontekstu do wyświetlenia: nagłówek bloku i pytanie użytkownika
 * (ostatni akapit). Treść strony nie zajmuje wtedy całej historii rozmowy.
 */
export function splitContext(message: string): { header: string | null; question: string } {
  if (!message.startsWith("[Kontekst: ")) return { header: null, question: message };
  const lineEnd = message.indexOf("\n");
  const firstLine = lineEnd === -1 ? message : message.slice(0, lineEnd);
  if (!firstLine.endsWith("]")) return { header: null, question: message };
  const header = firstLine.slice(1, -1);
  const rest = message.slice(firstLine.length);
  const split = rest.lastIndexOf("\n\n");
  return { header, question: split === -1 ? "" : rest.slice(split + 2).trim() };
}

/** Obraz kontekstu (data URL) jako plik do przesłania. */
export function dataUrlToFile(dataUrl: string, baseName: string): File | null {
  const match = dataUrl.match(IMAGE_DATA_URL);
  if (!match) return null;
  const binary = atob(match[2].replace(/\s/g, ""));
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  const extension = match[1].split("/")[1].replace("jpeg", "jpg");
  return new File([bytes], `${baseName}.${extension}`, { type: match[1] });
}

/** Sam tekst odpowiedzi asystenta (bez przemyśleń i narzędzi) – do wstawienia lub skopiowania. */
export function assistantText(turn: AssistantTurn): string {
  return turn.items
    .map((item) => (item.kind === "text" ? item.text.trim() : ""))
    .filter(Boolean)
    .join("\n\n");
}

/** Czy komunikat pochodzi od rodzica panelu (lub natywnej aplikacji, gdy panel jest oknem głównym). */
export function fromParent(event: MessageEvent, win: Window = window): boolean {
  if (event.source === win.parent) return true;
  return win.parent === win && event.source === null;
}

export function postToParent(message: PanelMessage, win: Window = window): void {
  // Panel nie zna pochodzenia rodzica (rozszerzenie, aplikacja) – komunikaty wysyła tylko
  // na wyraźne działanie użytkownika (Wstaw/Kopiuj) albo jako sygnał gotowości. Jako okno
  // główne (WebView) wysyła je do siebie – odbiera je skrypt wstrzyknięty przez aplikację.
  win.parent.postMessage(message, "*");
}
