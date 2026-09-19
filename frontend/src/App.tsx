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
import { MenuIcon, PaperclipIcon, SparkIcon } from "./components/icons";
import { Login } from "./components/Login";
import { PreviewModal } from "./components/PreviewModal";
import { Sidebar } from "./components/Sidebar";
import { AssistantMessage, UserMessage } from "./components/Turns";
import { applyRunEvent, emptyAssistantTurn } from "./runState";

const SUGGESTIONS = [
  "Wykonaj OCR tego skanu i przygotuj przeszukiwalny PDF.",
  "Popraw maksymalnie jakość tego dokumentu i wykonaj OCR.",
  "Popraw to zdjęcie tak, aby wyglądało jak do profesjonalnego ogłoszenia.",
  "Ten PDF zawiera wiele dokumentów – podziel go na osobne pliki.",
];

function conversationFromPath(): string | null {
  const match = window.location.pathname.match(/^\/c\/([0-9a-f-]{36})$/);
  return match ? match[1] : null;
}

export default function App() {
  const [user, setUser] = useState<string | null | undefined>(undefined);
  const [cloudUrl, setCloudUrl] = useState("");
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

  // Wejście z chmury bez sesji (?next=cloud): po zalogowaniu powrót do chmury.
  useEffect(() => {
    if (user && cloudUrl && new URLSearchParams(window.location.search).get("next") === "cloud") {
      window.location.replace(cloudUrl);
    }
  }, [user, cloudUrl]);

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

  if (user === undefined) return <div className="boot" />;
  if (user === null) return <Login onLoggedIn={() => loadMe()} />;

  const turns = detail?.turns ?? [];
  return (
    <div className="layout">
      <Sidebar
        conversations={conversations}
        currentId={currentId}
        username={user}
        cloudUrl={cloudUrl}
        open={sidebarOpen}
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
        className="chat"
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) setDragging(false);
        }}
        onDrop={onDrop}
      >
        <header className="chat-header">
          <button type="button" className="icon-button menu" onClick={() => setSidebarOpen(true)} aria-label="Historia rozmów">
            <MenuIcon />
          </button>
          <h1>{detail?.title ?? "Nowa rozmowa"}</h1>
        </header>
        <div
          className="messages"
          ref={scroller}
          onScroll={(event) => {
            const element = event.currentTarget;
            stickToBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
          }}
        >
          <div className="messages-inner">
            {turns.length === 0 ? (
              <div className="welcome">
                <div className="welcome-mark">
                  <SparkIcon size={28} />
                </div>
                <h2>W czym mogę pomóc?</h2>
                <p>Dodaj pliki i opisz, co mam z nimi zrobić – sam dobiorę narzędzia i parametry.</p>
                <div className="suggestions">
                  {SUGGESTIONS.map((suggestion) => (
                    <button key={suggestion} type="button" className="suggestion" onClick={() => setPrefill(suggestion)}>
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              turns.map((turn, index) =>
                turn.type === "user" ? (
                  <UserMessage key={`u${turn.id}`} turn={turn} onPreview={setPreview} />
                ) : (
                  <AssistantMessage key={`a${turn.run_id ?? index}-${index}`} turn={turn} onPreview={setPreview} />
                ),
              )
            )}
          </div>
        </div>
        <div className="composer-dock">
          {error && (
            <div className="toast" role="alert" onClick={() => setError("")}>
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
          <div className="disclaimer">Danaco Nexus korzysta z Claude. Wyniki warto sprawdzić przed użyciem.</div>
        </div>
        {dragging && (
          <div className="drop-overlay">
            <PaperclipIcon size={32} />
            Upuść pliki, aby je dodać
          </div>
        )}
      </main>
      {preview && <PreviewModal file={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}
