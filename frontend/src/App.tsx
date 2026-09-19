// Aplikacja: logowanie, historia rozmów, czat z asystentem i strumień zadań.

import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import {
  api,
  ApiError,
  subscribeRun,
  type AssistantTurn,
  type ConversationDetail,
  type ConversationSummary,
  type FileInfo,
  type Turn,
} from "./api";
import { Composer } from "./components/Composer";
import { Logo, MenuIcon, PaperclipIcon, PlusIcon } from "./components/icons";
import { Login } from "./components/Login";
import { PreviewModal } from "./components/PreviewModal";
import { Sidebar } from "./components/Sidebar";
import { AssistantMessage, UserMessage } from "./components/Turns";
import { applyRunEvent, emptyAssistantTurn } from "./runState";
import { takeSharedContent } from "./share";
import { applyTheme, storedTheme, type ThemeChoice } from "./theme";

const SUGGESTIONS = [
  { title: "Uporządkuj dokumenty", text: "Ten PDF zawiera wiele dokumentów – podziel go na osobne pliki i nazwij je według treści." },
  { title: "Popraw zdjęcie", text: "Popraw to zdjęcie tak, aby wyglądało jak do profesjonalnego ogłoszenia." },
  { title: "Przeszukiwalny PDF", text: "Zrób z tych skanów jeden przeszukiwalny PDF w najlepszej jakości." },
  { title: "Audio i wideo", text: "Wytnij z tego nagrania fragment 00:30–02:00 i zapisz go jako MP3 z wyrównaną głośnością." },
  { title: "Streszczenie i pismo", text: "Przeczytaj te dokumenty, streść najważniejsze ustalenia i przygotuj pismo w DOCX." },
  { title: "Z chmury", text: "Pobierz z chmury katalog Faktury i zestaw kwoty z wszystkich faktur w tabeli XLSX." },
];

function conversationFromPath(): string | null {
  const match = window.location.pathname.match(/^\/c\/([0-9a-f-]{36})$/);
  return match ? match[1] : null;
}

export default function App() {
  const [user, setUser] = useState<string | null | undefined>(undefined);
  const [cloudUrl, setCloudUrl] = useState("");
  const [theme, setTheme] = useState<ThemeChoice>(storedTheme());
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(conversationFromPath());
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [preview, setPreview] = useState<FileInfo | null>(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [dropped, setDropped] = useState<File[]>([]);
  const [prefill, setPrefill] = useState("");
  const unsubscribe = useRef<(() => void) | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  const handleError = useCallback((failure: unknown) => {
    if (failure instanceof ApiError && failure.status === 401) {
      setUser(null);
      return;
    }
    setError(failure instanceof Error ? failure.message : String(failure));
  }, []);

  const refreshList = useCallback(() => {
    api
      .conversations()
      .then((list) => {
        setConversations(list);
        // Tytuł nadawany przez serwer po pierwszej wiadomości trafia także do nagłówka.
        setDetail((current) => {
          const title = current && list.find((item) => item.id === current.id)?.title;
          return current && title && title !== current.title ? { ...current, title } : current;
        });
      })
      .catch(handleError);
  }, [handleError]);

  const follow = useCallback(
    (runId: string, conversationId: string) => {
      unsubscribe.current?.();
      setActiveRun(runId);
      unsubscribe.current = subscribeRun(runId, (event) => {
        setDetail((current) => {
          if (!current || current.id !== conversationId) return current;
          const turns = current.turns.map((turn) =>
            turn.type === "assistant" && turn.run_id === runId ? applyRunEvent(turn, event) : turn,
          );
          return { ...current, turns };
        });
        if (event.type === "run.completed" || event.type === "run.failed" || event.type === "run.cancelled") {
          setActiveRun(null);
          unsubscribe.current = null;
          api
            .conversation(conversationId)
            .then((fresh) => setDetail((current) => (current && current.id === conversationId ? fresh : current)))
            .catch(handleError);
          refreshList();
        }
      });
    },
    [handleError, refreshList],
  );

  const open = useCallback(
    (id: string | null) => {
      unsubscribe.current?.();
      unsubscribe.current = null;
      setActiveRun(null);
      setCurrentId(id);
      setSidebarOpen(false);
      stickToBottom.current = true;
      window.history.replaceState(null, "", id ? `/c/${id}` : "/");
      if (!id) {
        setDetail(null);
        return;
      }
      api
        .conversation(id)
        .then((data) => {
          if (data.active_run) {
            const hasTurn = data.turns.some((turn) => turn.type === "assistant" && turn.run_id === data.active_run?.id);
            if (!hasTurn) data.turns.push(emptyAssistantTurn(data.active_run.id));
            data.turns = data.turns.map((turn) =>
              turn.type === "assistant" && turn.run_id === data.active_run?.id ? { ...turn, items: [], status: "running" } : turn,
            );
          }
          setDetail(data);
          if (data.active_run) follow(data.active_run.id, id);
        })
        .catch((failure) => {
          handleError(failure);
          setCurrentId(null);
          window.history.replaceState(null, "", "/");
        });
    },
    [follow, handleError],
  );

  const loadMe = useCallback(
    () =>
      api
        .me()
        .then((me) => {
          setCloudUrl(me.cloud_url ?? "");
          setUser(me.username);
        })
        .catch(() => setUser(null)),
    [],
  );

  useEffect(() => {
    loadMe();
    return () => unsubscribe.current?.();
  }, [loadMe]);

  // Motyw „systemowy” podąża za zmianą ustawień urządzenia.
  useEffect(() => {
    if (theme !== "system") return;
    const media = window.matchMedia?.("(prefers-color-scheme: light)");
    const onChange = () => applyTheme("system");
    media?.addEventListener("change", onChange);
    return () => media?.removeEventListener("change", onChange);
  }, [theme]);

  // Wejście z chmury bez sesji (?next=cloud): po zalogowaniu powrót do chmury.
  useEffect(() => {
    if (user && cloudUrl && new URLSearchParams(window.location.search).get("next") === "cloud") {
      window.location.replace(cloudUrl);
    }
  }, [user, cloudUrl]);

  // Pliki udostępnione z innej aplikacji trafiają do nowej wiadomości.
  useEffect(() => {
    if (!user) return;
    takeSharedContent()
      .then((shared) => {
        if (!shared) return;
        open(null);
        if (shared.files.length) setDropped(shared.files);
        if (shared.text) setPrefill(shared.text);
      })
      .catch(handleError);
  }, [user]);

  useEffect(() => {
    if (!user) return;
    refreshList();
    // Rozmowa z adresu strony jest otwierana wyłącznie po zalogowaniu.
    if (currentId) open(currentId);
  }, [user]);

  useEffect(() => {
    const element = scroller.current;
    if (element && stickToBottom.current) element.scrollTop = element.scrollHeight;
  }, [detail]);

  const send = async (text: string, files: FileInfo[]): Promise<boolean> => {
    try {
      let conversationId = currentId;
      if (!conversationId) {
        const created = await api.createConversation();
        conversationId = created.id;
        setCurrentId(created.id);
        window.history.replaceState(null, "", `/c/${created.id}`);
        setDetail({ id: created.id, title: created.title, turns: [], files: [], active_run: null });
      }
      const { run_id } = await api.sendMessage(conversationId, text, files.map((file) => file.id));
      const userTurn: Turn = { type: "user", id: `local-${run_id}`, text, files, run_id, created_at: new Date().toISOString() };
      const assistantTurn: AssistantTurn = emptyAssistantTurn(run_id);
      const id = conversationId;
      setDetail((current) =>
        current && current.id === id ? { ...current, turns: [...current.turns, userTurn, assistantTurn] } : current,
      );
      stickToBottom.current = true;
      follow(run_id, id);
      refreshList();
      return true;
    } catch (failure) {
      handleError(failure);
      return false;
    }
  };

  const stop = () => {
    if (activeRun) api.cancelRun(activeRun).catch(handleError);
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length) setDropped(files);
  };

  if (user === undefined) return <div className="h-full bg-app" />;
  if (user === null) return <Login onLoggedIn={() => loadMe()} />;

  const turns = detail?.turns ?? [];
  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar
        conversations={conversations}
        currentId={currentId}
        username={user}
        cloudUrl={cloudUrl}
        open={sidebarOpen}
        theme={theme}
        onTheme={setTheme}
        onSelect={open}
        onNew={() => open(null)}
        onRename={(id, title) =>
          api
            .renameConversation(id, title)
            .then(() => {
              refreshList();
              setDetail((current) => (current && current.id === id ? { ...current, title } : current));
            })
            .catch(handleError)
        }
        onDelete={(id) =>
          api
            .deleteConversation(id)
            .then(() => {
              if (id === currentId) open(null);
              refreshList();
            })
            .catch(handleError)
        }
        onLogout={() => api.logout().finally(() => setUser(null))}
        onClose={() => setSidebarOpen(false)}
      />
      <main
        className="relative flex min-w-0 flex-1 flex-col bg-app"
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) setDragging(false);
        }}
        onDrop={onDrop}
      >
        <header className="safe-top titlebar-drag sticky top-0 z-10 flex items-center gap-2 border-b border-line/60 bg-app/85 px-3 py-2 backdrop-blur md:border-transparent">
          <button type="button" className="icon-btn md:hidden" onClick={() => setSidebarOpen(true)} aria-label="Historia rozmów">
            <MenuIcon />
          </button>
          <h1 className="min-w-0 flex-1 truncate text-[15px] font-medium">{detail?.title ?? "Nowa rozmowa"}</h1>
          <button type="button" className="icon-btn md:hidden" onClick={() => open(null)} aria-label="Nowa rozmowa">
            <PlusIcon />
          </button>
        </header>
        <div
          className="min-h-0 flex-1 overflow-y-auto"
          ref={scroller}
          onScroll={(event) => {
            const element = event.currentTarget;
            stickToBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
          }}
        >
          <div className="mx-auto w-full max-w-3xl px-4 pt-4 pb-10 md:px-6">
            {turns.length === 0 ? (
              <div className="flex min-h-[calc(100dvh-260px)] animate-rise flex-col items-center justify-center py-8 text-center">
                <Logo size={56} className="mb-5 rounded-2xl shadow-lg shadow-accent/20" />
                <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">W czym mogę pomóc?</h2>
                <p className="mt-2 max-w-md text-muted">
                  Opisz zadanie i dodaj pliki – dokumenty, zdjęcia, PDF, nagrania. Sam dobiorę narzędzia, wykonam pracę
                  i oddam gotowy wynik.
                </p>
                <div className="mt-8 grid w-full gap-2.5 sm:grid-cols-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion.title}
                      type="button"
                      className="rounded-2xl border border-line px-4 py-3 text-left transition-colors hover:bg-raised"
                      onClick={() => setPrefill(suggestion.text)}
                    >
                      <span className="block text-sm font-medium">{suggestion.title}</span>
                      <span className="mt-0.5 line-clamp-2 block text-sm text-muted">{suggestion.text}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-7">
                {turns.map((turn, index) =>
                  turn.type === "user" ? (
                    <UserMessage key={`u${turn.id}`} turn={turn} onPreview={setPreview} />
                  ) : (
                    <AssistantMessage key={`a${turn.run_id ?? index}-${index}`} turn={turn} onPreview={setPreview} />
                  ),
                )}
              </div>
            )}
          </div>
        </div>
        <div className="safe-bottom relative mx-auto w-full max-w-3xl px-3 md:px-6">
          {error && (
            <div
              role="alert"
              onClick={() => setError("")}
              className="absolute inset-x-3 bottom-full mb-2 cursor-pointer rounded-xl border border-danger/40 bg-danger-soft px-4 py-2.5 text-sm text-danger shadow-lg md:inset-x-6"
            >
              {error}
            </div>
          )}
          <Composer
            conversationId={currentId}
            running={activeRun !== null}
            onSend={send}
            onStop={stop}
            droppedFiles={dropped}
            onDroppedConsumed={() => setDropped([])}
            prefill={prefill}
            onPrefillConsumed={() => setPrefill("")}
          />
          <div className="py-1.5 text-center text-xs text-muted">
            Danaco Nexus korzysta z Claude. Wyniki warto sprawdzić przed użyciem.
          </div>
        </div>
        {dragging && (
          <div className="pointer-events-none absolute inset-3 z-20 flex flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed border-accent bg-accent-soft/90 text-lg font-medium text-accent">
            <PaperclipIcon size={32} />
            Upuść pliki, aby je dodać
          </div>
        )}
      </main>
      {preview && <PreviewModal file={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}
