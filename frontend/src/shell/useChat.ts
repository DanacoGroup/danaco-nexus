// Stan czatu: lista rozmów, otwarta rozmowa, wysyłanie wiadomości i śledzenie strumienia zadania.
// Wspólny dla pełnej aplikacji i kompaktowego panelu (?widok=panel).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  subscribeRun,
  type AssistantTurn,
  type ConversationDetail,
  type ConversationSummary,
  type FileInfo,
  type Turn,
} from "../api";
import { applyRunEvent, emptyAssistantTurn } from "../runState";

interface Options {
  /** Wywoływane przy 401 – sesja wygasła albo klucz urządzenia jest nieważny. */
  onUnauthorized: () => void;
  /** Zmiana otwartej rozmowy (np. aktualizacja adresu strony). */
  onOpened?: (id: string | null) => void;
}

export function useChat({ onUnauthorized, onOpened }: Options) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [error, setError] = useState("");
  // Odmowa z braku kredytów ma własny widok; sam czerwony pasek wyglądałby na awarię.
  const [brakKredytow, setBrakKredytow] = useState(false);
  const activeRunRef = useRef<string | null>(null);
  activeRunRef.current = activeRun;
  const unsubscribe = useRef<(() => void) | null>(null);
  const callbacks = useRef({ onUnauthorized, onOpened });
  callbacks.current = { onUnauthorized, onOpened };

  const handleError = useCallback((failure: unknown) => {
    if (failure instanceof ApiError && failure.status === 401) {
      callbacks.current.onUnauthorized();
      return;
    }
    if (failure instanceof ApiError && failure.status === 402) setBrakKredytow(true);
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
      callbacks.current.onOpened?.(id);
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
          callbacks.current.onOpened?.(null);
        });
    },
    [follow, handleError],
  );

  useEffect(() => () => unsubscribe.current?.(), []);

  // Wypowiedź w trakcie trwającego zadania (np. rozpoczętego na czacie) czeka na jego koniec –
  // rozmowa jest jedna, a zadania w niej wykonują się po kolei.
  const waitForIdle = async () => {
    const deadline = Date.now() + 15 * 60 * 1000;
    while (activeRunRef.current && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 300));
    }
  };

  /** Wysyła wiadomość (tworzy rozmowę, gdy żadna nie jest otwarta); zwraca identyfikator zadania. */
  const send = async (text: string, files: FileInfo[], voice = false): Promise<string | null> => {
    setBrakKredytow(false);
    try {
      let conversationId = currentId;
      if (!conversationId) {
        const created = await api.createConversation();
        conversationId = created.id;
        setCurrentId(created.id);
        callbacks.current.onOpened?.(created.id);
        setDetail({ id: created.id, title: created.title, turns: [], files: [], active_run: null });
      }
      if (voice) await waitForIdle();
      const { run_id } = await api.sendMessage(conversationId, text, files.map((file) => file.id), voice);
      const userTurn: Turn = {
        type: "user",
        id: `local-${run_id}`,
        text,
        files,
        run_id,
        voice,
        created_at: new Date().toISOString(),
      };
      const assistantTurn: AssistantTurn = emptyAssistantTurn(run_id);
      const id = conversationId;
      setDetail((current) =>
        current && current.id === id ? { ...current, turns: [...current.turns, userTurn, assistantTurn] } : current,
      );
      follow(run_id, id);
      refreshList();
      return run_id;
    } catch (failure) {
      handleError(failure);
      return null;
    }
  };

  const stop = () => {
    if (activeRun) api.cancelRun(activeRun).catch(handleError);
  };

  const rename = (id: string, title: string) =>
    api
      .renameConversation(id, title)
      .then(() => {
        refreshList();
        setDetail((current) => (current && current.id === id ? { ...current, title } : current));
      })
      .catch(handleError);

  const remove = (id: string) =>
    api
      .deleteConversation(id)
      .then(() => {
        if (id === currentId) open(null);
        refreshList();
      })
      .catch(handleError);

  return {
    conversations,
    currentId,
    detail,
    activeRun,
    error,
    setError,
    brakKredytow,
    setBrakKredytow,
    handleError,
    refreshList,
    open,
    send,
    stop,
    rename,
    remove,
  };
}

export type ChatState = ReturnType<typeof useChat>;
