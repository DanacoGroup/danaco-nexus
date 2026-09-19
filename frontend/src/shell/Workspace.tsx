// Powłoka zalogowanej aplikacji: nawigacja modułów, czat z historią rozmów, rozmowa głosowa,
// zadania w toku (wiele sesji naraz) i strony modułów (/m/<id>).

import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { api, type AssistantTurn, type FileInfo, type VoiceConfig } from "../api";
import { Composer } from "../components/Composer";
import { Logo, MenuIcon, PaperclipIcon, PlusIcon } from "../components/icons";
import { PreviewModal } from "../components/PreviewModal";
import { Sidebar } from "../components/Sidebar";
import { AssistantMessage, UserMessage } from "../components/Turns";
import { findModule, MODULES } from "../modules/registry";
import { takeSharedContent } from "../share";
import { applyTheme, storedTheme, type ThemeChoice } from "../theme";
import { unlockAudio } from "../voice/player";
import { VoiceMode } from "../voice/VoiceMode";
import { BottomBar, NavRail, navEntries } from "./ModuleNav";
import type { Route } from "./route";
import { TasksButton, TasksPanel, useActiveTasks } from "./TasksPanel";
import { Toasts, type Toast } from "./Toasts";
import { displayTurn } from "./turnDisplay";
import { useChat } from "./useChat";

const SUGGESTIONS = [
  { title: "Uporządkuj dokumenty", text: "Ten PDF zawiera wiele dokumentów – podziel go na osobne pliki i nazwij je według treści." },
  { title: "Popraw zdjęcie", text: "Popraw to zdjęcie tak, aby wyglądało jak do profesjonalnego ogłoszenia." },
  { title: "Przeszukiwalny PDF", text: "Zrób z tych skanów jeden przeszukiwalny PDF w najlepszej jakości." },
  { title: "Audio i wideo", text: "Wytnij z tego nagrania fragment 00:30–02:00 i zapisz go jako MP3 z wyrównaną głośnością." },
  { title: "Streszczenie i pismo", text: "Przeczytaj te dokumenty, streść najważniejsze ustalenia i przygotuj pismo w DOCX." },
  { title: "Z chmury", text: "Pobierz z chmury katalog Faktury i zestaw kwoty z wszystkich faktur w tabeli XLSX." },
];

interface Props {
  username: string;
  cloudUrl: string;
  route: Route;
  navigate: (path: string, replace?: boolean) => void;
  onLoggedOut: () => void;
}

export function Workspace({ username, cloudUrl, route, navigate, onLoggedOut }: Props) {
  const [theme, setTheme] = useState<ThemeChoice>(storedTheme());
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [preview, setPreview] = useState<FileInfo | null>(null);
  const [dragging, setDragging] = useState(false);
  const [dropped, setDropped] = useState<File[]>([]);
  const [prefill, setPrefill] = useState("");
  const [voiceConfig, setVoiceConfig] = useState<VoiceConfig | null>(null);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [voiceRunId, setVoiceRunId] = useState<string | null>(null);
  const [tasksOpen, setTasksOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const scroller = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  const activeId = route.view === "module" ? route.moduleId : "chat";
  const chat = useChat({
    onUnauthorized: onLoggedOut,
    onOpened: (id) => {
      // Adres podąża za otwartą rozmową tylko w widoku czatu (moduł może otworzyć rozmowę w tle).
      if (activeIdRef.current === "chat") navigate(id ? `/c/${id}` : "/", true);
    },
  });
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  const currentIdRef = useRef(chat.currentId);
  currentIdRef.current = chat.currentId;

  const dismissToast = useCallback((id: string) => setToasts((items) => items.filter((item) => item.id !== id)), []);

  const openConversation = useCallback(
    (id: string) => {
      navigate(`/c/${id}`);
    },
    [navigate],
  );

  const { tasks, refresh: refreshTasks } = useActiveTasks(true, (finished) => {
    chat.refreshList();
    const background = finished.filter((task) => task.conversation_id !== currentIdRef.current || activeIdRef.current !== "chat");
    if (!background.length) return;
    setToasts((items) => [
      ...items,
      ...background.map((task) => ({
        id: task.run_id,
        title: "Zadanie zakończone",
        body: task.title,
        actionLabel: "Otwórz rozmowę",
        onAction: () => openConversation(task.conversation_id),
      })),
    ]);
  });

  // Rozmowa z adresu strony (także po „wstecz” w przeglądarce).
  const routeConversation = route.view === "chat" ? route.conversationId : undefined;
  useEffect(() => {
    if (routeConversation === undefined) return;
    if (routeConversation !== currentIdRef.current) chat.open(routeConversation);
    setSidebarOpen(false);
    stickToBottom.current = true;
  }, [routeConversation]);

  useEffect(() => {
    chat.refreshList();
    api
      .voiceConfig()
      .then(setVoiceConfig)
      .catch(() => setVoiceConfig(null));
  }, []);

  // Motyw „systemowy” podąża za zmianą ustawień urządzenia.
  useEffect(() => {
    if (theme !== "system") return;
    const media = window.matchMedia?.("(prefers-color-scheme: light)");
    const onChange = () => applyTheme("system");
    media?.addEventListener("change", onChange);
    return () => media?.removeEventListener("change", onChange);
  }, [theme]);

  // Pliki udostępnione z innej aplikacji trafiają do nowej wiadomości.
  useEffect(() => {
    takeSharedContent()
      .then((shared) => {
        if (!shared) return;
        navigate("/", true);
        chat.open(null);
        if (shared.files.length) setDropped(shared.files);
        if (shared.text) setPrefill(shared.text);
      })
      .catch(chat.handleError);
  }, []);

  useEffect(() => {
    const element = scroller.current;
    if (element && stickToBottom.current) element.scrollTop = element.scrollHeight;
  }, [chat.detail]);

  const startVoice = () => {
    if (!voiceConfig?.available) {
      chat.setError("Rozmowa głosowa jest niedostępna – serwer nie ma skonfigurowanych modeli mowy.");
      return;
    }
    unlockAudio();
    setVoiceOpen(true);
  };

  const selectEntry = (id: string) => {
    if (id === "glos") {
      if (activeId !== "chat") navigate(chat.currentId ? `/c/${chat.currentId}` : "/");
      startVoice();
      return;
    }
    if (id === "chat") navigate(chat.currentId ? `/c/${chat.currentId}` : "/");
    else navigate(`/m/${id}`);
  };

  const send = async (text: string, files: FileInfo[], voice = false): Promise<boolean> => {
    const runId = await chat.send(text, files, voice);
    if (!runId) return false;
    if (voice) setVoiceRunId(runId);
    stickToBottom.current = true;
    void refreshTasks();
    return true;
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length) setDropped(files);
  };

  const entries = navEntries(MODULES);
  const module = activeId === "chat" ? undefined : findModule(activeId);
  const turns = chat.detail?.turns ?? [];
  const voiceTurn = voiceRunId
    ? turns.find((turn): turn is AssistantTurn => turn.type === "assistant" && turn.run_id === voiceRunId)
    : undefined;
  const voiceReply = voiceTurn
    ? voiceTurn.items.map((item) => (item.kind === "text" ? item.text : "")).filter(Boolean).join("\n")
    : "";
  const voiceDone = !voiceTurn || (voiceTurn.status !== "running" && voiceTurn.status !== "queued");

  const chatView = (
    <>
      <Sidebar
        conversations={chat.conversations}
        currentId={chat.currentId}
        username={username}
        cloudUrl={cloudUrl}
        open={sidebarOpen}
        theme={theme}
        onTheme={setTheme}
        onSelect={openConversation}
        onNew={() => {
          setSidebarOpen(false);
          navigate("/");
          chat.open(null);
        }}
        onRename={(id, title) => void chat.rename(id, title)}
        onDelete={(id) => void chat.remove(id)}
        onLogout={() => api.logout().finally(onLoggedOut)}
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
          <h1 className="min-w-0 flex-1 truncate text-[15px] font-medium">{chat.detail?.title ?? "Nowa rozmowa"}</h1>
          <span className="md:hidden">
            <TasksButton tasks={tasks} onClick={() => setTasksOpen(true)} />
          </span>
          <button
            type="button"
            className="icon-btn md:hidden"
            onClick={() => {
              navigate("/");
              chat.open(null);
            }}
            aria-label="Nowa rozmowa"
          >
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
              <div className="flex min-h-[calc(100dvh-320px)] animate-rise flex-col items-center justify-center py-8 text-center">
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
                    <UserMessage key={`u${turn.id}`} turn={displayTurn(turn)} onPreview={setPreview} />
                  ) : (
                    <AssistantMessage key={`a${turn.run_id ?? index}-${index}`} turn={turn} onPreview={setPreview} />
                  ),
                )}
              </div>
            )}
          </div>
        </div>
        <div className="safe-bottom relative mx-auto w-full max-w-3xl px-3 md:px-6">
          {chat.error && (
            <div
              role="alert"
              onClick={() => chat.setError("")}
              className="absolute inset-x-3 bottom-full mb-2 cursor-pointer rounded-xl border border-danger/40 bg-danger-soft px-4 py-2.5 text-sm text-danger shadow-lg md:inset-x-6"
            >
              {chat.error}
            </div>
          )}
          <Composer
            conversationId={chat.currentId}
            running={chat.activeRun !== null}
            onSend={send}
            onStop={chat.stop}
            droppedFiles={dropped}
            onDroppedConsumed={() => setDropped([])}
            prefill={prefill}
            onPrefillConsumed={() => setPrefill("")}
            onVoice={voiceConfig?.available ? startVoice : undefined}
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
    </>
  );

  const moduleView = (
    <main className="relative flex min-w-0 flex-1 flex-col bg-app">
      <header className="safe-top flex items-center gap-2 border-b border-line/60 px-3 py-2 md:hidden">
        <Logo size={24} className="rounded-md" />
        <h1 className="min-w-0 flex-1 truncate text-[15px] font-medium">{module?.label ?? "Moduł"}</h1>
        <TasksButton tasks={tasks} onClick={() => setTasksOpen(true)} />
      </header>
      <div className="min-h-0 flex-1">
        {module ? (
          <module.Page openConversation={openConversation} openModule={(id) => navigate(`/m/${id}`)} />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
            <h2 className="text-xl font-semibold">Ten moduł nie jest dostępny</h2>
            <p className="max-w-sm text-sm text-muted">Moduł „{activeId}” nie jest zainstalowany w tej wersji Nexusa.</p>
            <button type="button" className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-on-accent" onClick={() => navigate("/")}>
              Wróć do czatu
            </button>
          </div>
        )}
      </div>
    </main>
  );

  return (
    <div className="flex h-full flex-col overflow-hidden md:flex-row">
      <NavRail
        entries={entries}
        activeId={activeId}
        onSelect={selectEntry}
        railFooter={<TasksButton variant="rail" tasks={tasks} onClick={() => setTasksOpen(true)} />}
      />
      <div className="flex min-h-0 min-w-0 flex-1">{activeId === "chat" ? chatView : moduleView}</div>
      <BottomBar entries={entries} activeId={activeId} onSelect={selectEntry} />
      {preview && <PreviewModal file={preview} onClose={() => setPreview(null)} />}
      {tasksOpen && (
        <TasksPanel
          tasks={tasks}
          currentConversation={activeId === "chat" ? chat.currentId : null}
          onOpen={openConversation}
          onClose={() => setTasksOpen(false)}
          onChanged={() => void refreshTasks()}
        />
      )}
      <Toasts toasts={toasts} onDismiss={dismissToast} />
      {voiceOpen && voiceConfig && (
        <VoiceMode
          config={voiceConfig}
          replyText={voiceReply}
          replyDone={voiceDone}
          onSend={(text) => send(text, [], true)}
          onClose={() => {
            setVoiceOpen(false);
            setVoiceRunId(null);
          }}
        />
      )}
    </div>
  );
}
