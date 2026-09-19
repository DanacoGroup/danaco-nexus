// Rozmowa osadzona w module (Strony, Studio): historia, wysyłanie, strumień zdarzeń zadania.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  FINAL_EVENTS,
  subscribeRun,
  type AssistantTurn,
  type ConversationDetail,
  type FileInfo,
  type RunEvent,
  type Turn,
} from "../../api";
import { applyRunEvent, emptyAssistantTurn } from "../../runState";
import { errorText } from "./http";

export interface ConversationState {
  detail: ConversationDetail | null;
  running: boolean;
  error: string;
  clearError: () => void;
  send: (text: string, files?: FileInfo[]) => Promise<boolean>;
  stop: () => void;
  reload: () => void;
}

export function useConversation(
  conversationId: string | null,
  onEvent?: (event: RunEvent) => void,
): ConversationState {
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [error, setError] = useState("");
  const unsubscribe = useRef<(() => void) | null>(null);
  const eventHandler = useRef(onEvent);
  eventHandler.current = onEvent;

  const load = useCallback((id: string) => {
    return api.conversation(id).then((data) => {
      if (data.active_run) {
        const runId = data.active_run.id;
        if (!data.turns.some((turn) => turn.type === "assistant" && turn.run_id === runId)) {
          data.turns.push(emptyAssistantTurn(runId));
        }
        data.turns = data.turns.map((turn) =>
          turn.type === "assistant" && turn.run_id === runId ? { ...turn, items: [], status: "running" } : turn,
        );
      }
      setDetail(data);
      return data;
    });
  }, []);

  const follow = useCallback(
    (runId: string, id: string) => {
      unsubscribe.current?.();
      setActiveRun(runId);
      unsubscribe.current = subscribeRun(runId, (event) => {
        setDetail((current) => {
          if (!current || current.id !== id) return current;
          const turns = current.turns.map((turn) =>
            turn.type === "assistant" && turn.run_id === runId ? applyRunEvent(turn, event) : turn,
          );
          return { ...current, turns };
        });
        eventHandler.current?.(event);
        if (FINAL_EVENTS.has(event.type)) {
          setActiveRun(null);
          unsubscribe.current = null;
          load(id).catch((failure) => setError(errorText(failure)));
        }
      });
    },
    [load],
  );

  useEffect(() => {
    setDetail(null);
    setActiveRun(null);
    if (!conversationId) return;
    let cancelled = false;
    load(conversationId)
      .then((data) => {
        if (!cancelled && data.active_run) follow(data.active_run.id, conversationId);
      })
      .catch((failure) => !cancelled && setError(errorText(failure)));
    return () => {
      cancelled = true;
      unsubscribe.current?.();
      unsubscribe.current = null;
    };
  }, [conversationId, load, follow]);

  const send = useCallback(
    async (text: string, files: FileInfo[] = []) => {
      if (!conversationId) return false;
      try {
        const { run_id } = await api.sendMessage(conversationId, text, files.map((file) => file.id));
        const userTurn: Turn = {
          type: "user",
          id: `local-${run_id}`,
          text,
          files,
          run_id,
          created_at: new Date().toISOString(),
        };
        const assistantTurn: AssistantTurn = emptyAssistantTurn(run_id);
        setDetail((current) =>
          current && current.id === conversationId
            ? { ...current, turns: [...current.turns, userTurn, assistantTurn] }
            : current,
        );
        follow(run_id, conversationId);
        return true;
      } catch (failure) {
        setError(errorText(failure));
        return false;
      }
    },
    [conversationId, follow],
  );

  const stop = useCallback(() => {
    if (activeRun) api.cancelRun(activeRun).catch((failure) => setError(errorText(failure)));
  }, [activeRun]);

  const reload = useCallback(() => {
    if (conversationId) load(conversationId).catch((failure) => setError(errorText(failure)));
  }, [conversationId, load]);

  return { detail, running: activeRun !== null, error, clearError: () => setError(""), send, stop, reload };
}
