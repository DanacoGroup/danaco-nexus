// Kompaktowy panel czatu (?widok=panel) do osadzenia w rozszerzeniu, Nexus Desktop i aplikacji Android.
// Protokół postMessage opisuje shell/embed.ts.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, setDeviceToken, type AssistantTurn, type FileInfo } from "../api";
import { Composer } from "../components/Composer";
import { CheckIcon, CloseIcon, Logo, MonitorIcon, PlusIcon } from "../components/icons";
import { PreviewModal } from "../components/PreviewModal";
import { AssistantMessage, UserMessage } from "../components/Turns";
import {
  assistantText,
  composeMessage,
  dataUrlToFile,
  fromParent,
  parseParentMessage,
  plainText,
  postToParent,
  type EmbedContext,
} from "./embed";
import { CopyIcon, ExternalIcon, GlobeIcon, InsertIcon } from "./icons";
import { displayTurn } from "./turnDisplay";
import { useChat } from "./useChat";

type AuthState = "waiting" | "ok" | "missing";

/** Czas na klucz urządzenia od rodzica, zanim panel spróbuje sesji z ciasteczka. */
const AUTH_GRACE_MS = 1200;

function ReplyActions({ turn }: { turn: AssistantTurn }) {
  const [copied, setCopied] = useState(false);
  const text = plainText(assistantText(turn));
  if (!text || turn.status === "running" || turn.status === "queued") return null;
  const copy = async () => {
    postToParent({ type: "nexus:copy", text });
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* w ramce schowek bywa zablokowany – kopiuje wtedy rodzic (nexus:copy) */
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };
  const button = "inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-xs font-medium text-muted transition-colors hover:bg-hover hover:text-fg";
  return (
    <div className="mt-2 flex gap-1.5 pl-10">
      <button type="button" className={button} onClick={() => postToParent({ type: "nexus:insert", text })} title="Wstaw odpowiedź w aktywne pole strony">
        <InsertIcon size={14} /> Wstaw
      </button>
      <button type="button" className={button} onClick={() => void copy()}>
        {copied ? <CheckIcon size={14} className="text-success" /> : <CopyIcon size={14} />} {copied ? "Skopiowano" : "Kopiuj"}
      </button>
    </div>
  );
}

export function PanelApp() {
  const [auth, setAuth] = useState<AuthState>("waiting");
  const [context, setContext] = useState<EmbedContext | null>(null);
  const [contextPending, setContextPending] = useState(false);
  const [dropped, setDropped] = useState<File[]>([]);
  const [prefill, setPrefill] = useState("");
  const [preview, setPreview] = useState<FileInfo | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const tokenReceived = useRef(false);
  const chat = useChat({ onUnauthorized: () => setAuth("missing") });
  const chatRef = useRef(chat);
  chatRef.current = chat;
  const contextRef = useRef<{ context: EmbedContext | null; pending: boolean }>({ context: null, pending: false });
  contextRef.current = { context, pending: contextPending };

  const checkSession = useCallback(() => {
    api
      .me()
      .then(() => {
        setAuth("ok");
        chatRef.current.refreshList();
      })
      .catch((failure) => setAuth(failure instanceof ApiError && failure.status !== 401 ? "ok" : "missing"));
  }, []);

  const sendText = useCallback(async (text: string, files: FileInfo[]) => {
    const { context: current, pending } = contextRef.current;
    const message = composeMessage(text, pending ? current : null);
    const runId = await chatRef.current.send(message, files);
    if (runId && pending) setContextPending(false);
    return runId !== null;
  }, []);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (!fromParent(event)) return;
      const message = parseParentMessage(event.data);
      if (!message) return;
      if (message.type === "nexus:auth") {
        tokenReceived.current = true;
        setDeviceToken(message.token);
        checkSession();
      } else if (message.type === "nexus:context") {
        setContext(message.context);
        setContextPending(message.context !== null);
        const image = message.context?.image ? dataUrlToFile(message.context.image, message.context.kind === "screen" ? "zrzut-ekranu" : "strona") : null;
        if (image) setDropped([image]);
      } else if (message.type === "nexus:prompt") {
        if (message.send) void sendText(message.text, []);
        else setPrefill(message.text);
      }
    };
    window.addEventListener("message", onMessage);
    postToParent({ type: "nexus:ready" });
    const timer = window.setTimeout(() => {
      if (!tokenReceived.current) checkSession();
    }, AUTH_GRACE_MS);
    return () => {
      window.removeEventListener("message", onMessage);
      window.clearTimeout(timer);
    };
  }, [checkSession, sendText]);

  useEffect(() => {
    const element = scroller.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [chat.detail]);

  if (auth === "waiting") {
    return (
      <div className="grid h-full place-items-center bg-app">
        <span className="spinner text-accent" />
      </div>
    );
  }

  if (auth === "missing") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-app px-6 text-center">
        <Logo size={44} className="rounded-xl" />
        <div>
          <h1 className="text-base font-semibold">Połącz panel z Nexusem</h1>
          <p className="mt-1.5 text-sm text-muted">
            W aplikacji Nexus otwórz <b>Urządzenia</b>, utwórz klucz dla tego urządzenia i wklej go w ustawieniach
            rozszerzenia lub aplikacji. W zwykłej karcie możesz też po prostu się zalogować.
          </p>
        </div>
        <div className="flex gap-2">
          <a
            href="/zaloguj?next=/m/urzadzenia"
            target="_blank"
            rel="noopener"
            className="inline-flex items-center gap-1.5 rounded-xl bg-accent-fill px-4 py-2 text-sm font-medium text-on-accent hover:bg-accent-fill-hover"
          >
            Zaloguj się <ExternalIcon size={14} />
          </a>
          <button type="button" className="rounded-xl border border-line px-4 py-2 text-sm hover:bg-hover" onClick={checkSession}>
            Spróbuj ponownie
          </button>
        </div>
      </div>
    );
  }

  const turns = chat.detail?.turns ?? [];
  return (
    <div className="flex h-full flex-col bg-app">
      <header className="flex items-center gap-1.5 border-b border-line/70 px-2.5 py-2">
        <Logo size={24} className="shrink-0 rounded-md" />
        <select
          aria-label="Rozmowa"
          className="min-w-0 flex-1 truncate rounded-lg bg-transparent px-1.5 py-1 text-sm font-medium outline-none hover:bg-hover"
          value={chat.currentId ?? ""}
          onChange={(event) => chat.open(event.target.value || null)}
        >
          <option value="">Nowa rozmowa</option>
          {chat.conversations.slice(0, 30).map((conversation) => (
            <option key={conversation.id} value={conversation.id}>
              {conversation.active ? "● " : ""}
              {conversation.title}
            </option>
          ))}
        </select>
        {chat.currentId && (
          <a
            className="icon-btn size-8"
            href={`/c/${chat.currentId}`}
            target="_blank"
            rel="noopener"
            aria-label="Otwórz w pełnej aplikacji"
            title="Otwórz w pełnej aplikacji"
          >
            <ExternalIcon size={16} />
          </a>
        )}
        <button type="button" className="icon-btn size-8" onClick={() => chat.open(null)} aria-label="Nowa rozmowa" title="Nowa rozmowa">
          <PlusIcon size={18} />
        </button>
      </header>

      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-3 pt-3 pb-6">
        {turns.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center">
            <h2 className="text-lg font-semibold tracking-tight">W czym pomóc?</h2>
            <p className="text-sm text-muted">
              {context
                ? "Zapytaj o tę stronę – streszczenie, odpowiedź na opinię, tłumaczenie, analiza."
                : "Napisz wiadomość albo dołącz plik. Nexus może też przeczytać otwartą stronę lub zrzut ekranu."}
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {turns.map((turn, index) =>
              turn.type === "user" ? (
                <UserMessage key={`u${turn.id}`} turn={displayTurn(turn)} onPreview={setPreview} />
              ) : (
                <div key={`a${turn.run_id ?? index}-${index}`}>
                  <AssistantMessage turn={turn} onPreview={setPreview} />
                  <ReplyActions turn={turn} />
                </div>
              ),
            )}
          </div>
        )}
      </div>

      <div className="safe-bottom px-2.5">
        {chat.error && (
          <div role="alert" onClick={() => chat.setError("")} className="mb-2 cursor-pointer rounded-xl border border-danger/40 bg-danger-soft px-3 py-2 text-sm text-danger">
            {chat.error}
          </div>
        )}
        {context && (
          <div className="mb-2 flex items-center gap-2 rounded-xl border border-line bg-raised/70 px-2.5 py-1.5 text-xs">
            {context.kind === "screen" ? <MonitorIcon size={15} className="shrink-0 text-accent" /> : <GlobeIcon size={15} className="shrink-0 text-accent" />}
            <span className="min-w-0 flex-1 truncate" title={context.url || context.title}>
              <span className="text-muted">{contextPending ? "Kontekst: " : "Dołączono: "}</span>
              {context.title || context.url || (context.kind === "screen" ? "ekran" : "strona")}
            </span>
            <button
              type="button"
              className="icon-btn size-6"
              onClick={() => {
                setContext(null);
                setContextPending(false);
              }}
              aria-label="Usuń kontekst"
            >
              <CloseIcon size={13} />
            </button>
          </div>
        )}
        <Composer
          conversationId={chat.currentId}
          running={chat.activeRun !== null}
          onSend={sendText}
          onStop={chat.stop}
          droppedFiles={dropped}
          onDroppedConsumed={() => setDropped([])}
          prefill={prefill}
          onPrefillConsumed={() => setPrefill("")}
        />
      </div>
      {preview && <PreviewModal file={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}
