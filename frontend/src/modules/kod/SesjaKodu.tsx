// Panel sesji programistycznej w trybie „code” dla projektu (zwykłe API rozmów z meta trybu).

import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { api, downloadUrl, FINAL_EVENTS, subscribeRun, type FileInfo, type Turn } from "../../api";
import { AssistantMessage, UserMessage } from "../../components/Turns";
import { SendIcon, StopIcon } from "../../components/icons";
import { applyRunEvent, emptyAssistantTurn } from "../../runState";
import { Button, Select } from "../../ui";
import { kodApi, type CodeConversation } from "./api";

const openFile = (file: FileInfo) => window.open(downloadUrl(file, true), "_blank", "noopener");

/** Zdania na start sesji: zakres, w jakim ten moduł naprawdę pracuje. */
const ZACZEPY = [
  "Przejrzyj projekt i powiedz, co tu jest i jak jest zbudowane.",
  "Uruchom testy i napraw to, co się nie zgadza.",
  "Dodaj walidację formularza razem z testami.",
];

export function SesjaKodu({
  project,
  onRunFinished,
  openConversation,
}: {
  project: string;
  onRunFinished: () => void;
  openConversation: (id: string) => void;
}) {
  const [conversations, setConversations] = useState<CodeConversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const unsubscribe = useRef<(() => void) | null>(null);
  const fresh = useRef<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const finished = useRef(onRunFinished);
  finished.current = onRunFinished;

  const follow = useCallback((id: string) => {
    unsubscribe.current?.();
    setRunId(id);
    unsubscribe.current = subscribeRun(id, (event) => {
      setTurns((current) =>
        current.map((turn) => (turn.type === "assistant" && turn.run_id === id ? applyRunEvent(turn, event) : turn)),
      );
      if (FINAL_EVENTS.has(event.type)) {
        setRunId(null);
        finished.current();
      }
    });
  }, []);

  const load = useCallback(
    async (id: string) => {
      unsubscribe.current?.();
      setRunId(null);
      const detail = await api.conversation(id);
      let loaded = detail.turns;
      const active = detail.active_run;
      if (active) {
        if (!loaded.some((turn) => turn.type === "assistant" && turn.run_id === active.id)) {
          loaded = [...loaded, emptyAssistantTurn(active.id)];
        }
        // Zdarzenia trwającego zadania są odtwarzane od początku – pusta tura zamiast zapisanej.
        loaded = loaded.map((turn) =>
          turn.type === "assistant" && turn.run_id === active.id ? { ...turn, items: [], status: "running" } : turn,
        );
      }
      setTurns(loaded);
      if (active) follow(active.id);
    },
    [follow],
  );

  useEffect(() => {
    let cancelled = false;
    setTurns([]);
    setConversationId(null);
    kodApi
      .conversations(project)
      .then((items) => {
        if (cancelled) return;
        setConversations(items);
        if (items[0]) setConversationId(items[0].id);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    return () => {
      cancelled = true;
    };
  }, [project]);

  useEffect(() => {
    if (!conversationId) return;
    if (fresh.current === conversationId) {
      fresh.current = null;
      return;
    }
    load(conversationId).catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [conversationId, load]);

  useEffect(() => () => unsubscribe.current?.(), []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [turns]);

  const newSession = async () => {
    const created = await kodApi.createConversation(project);
    // Nowa sesja jest pusta – bez wczytywania (wczytanie mogłoby nadpisać wysłane już polecenie).
    fresh.current = created.id;
    unsubscribe.current?.();
    setRunId(null);
    setTurns([]);
    setConversations((current) => [created, ...current]);
    setConversationId(created.id);
    return created.id;
  };

  const send = async (event?: FormEvent) => {
    event?.preventDefault();
    const message = text.trim();
    if (!message || runId) return;
    setError("");
    try {
      const id = conversationId ?? (await newSession());
      const { run_id } = await api.sendMessage(id, message, []);
      setText("");
      setTurns((current) => [
        ...current,
        { type: "user", id: `lokalna-${run_id}`, text: message, files: [], run_id, created_at: new Date().toISOString() },
        emptyAssistantTurn(run_id),
      ]);
      follow(run_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się wysłać polecenia.");
    }
  };

  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  };

  return (
    <section className="flex min-h-0 flex-1 flex-col" aria-label="Sesja kodu">
      {/* Lista sesji szła dotąd natywnym `select`-em: szary prostokąt z systemową strzałką,
        jedyny taki element w całym produkcie. Tu jest lista wyboru z biblioteki — te same
        kroje, barwy i obsługa klawiaturą co wszędzie indziej. */}
      <div className="flex items-center gap-2 border-b border-line px-3 py-2">
        <Select
          label="Sesja"
          hideLabel
          size="sm"
          className="min-w-0 flex-1"
          value={conversationId ?? ""}
          onChange={(wybor) => setConversationId(wybor || null)}
          placeholder="Nowa sesja"
          options={
            conversations.length === 0
              ? [{ value: "", label: "Nowa sesja" }]
              : conversations.map((item) => ({
                  value: item.id,
                  label: item.title,
                  description: new Date(item.updated_at).toLocaleDateString("pl-PL"),
                }))
          }
        />
        <Button size="sm" variant="secondary" onClick={() => void newSession().catch((reason) => setError(String(reason)))}>
          Nowa
        </Button>
        {conversationId && (
          <Button size="sm" variant="ghost" onClick={() => openConversation(conversationId)}>
            W czacie
          </Button>
        )}
      </div>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-3 py-4">
        {turns.length === 0 && (
          // Akapit z przykładem w cudzysłowie trzeba było przepisać ręcznie do pola.
          // Gotowe zdania wstawiają się kliknięciem — a przy okazji pokazują, w jakiej
          // skali warto zlecać pracę w tym module.
          <div className="space-y-3">
            <p className="text-sm text-muted">
              Nexus pracuje w katalogu projektu: czyta i zmienia pliki, uruchamia testy i polecenia git.
            </p>
            <div className="flex flex-col gap-1.5">
              {ZACZEPY.map((zdanie) => (
                <button
                  key={zdanie}
                  type="button"
                  onClick={() => setText(zdanie)}
                  className="ui-nacisk rounded-xl border border-line px-3 py-2 text-left text-[13px] text-muted transition-colors hover:border-line-strong hover:bg-raised hover:text-fg"
                >
                  {zdanie}
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((turn) =>
          turn.type === "user" ? (
            <UserMessage key={`u-${turn.id}`} turn={turn} onPreview={openFile} />
          ) : (
            <AssistantMessage key={`a-${turn.run_id}`} turn={turn} onPreview={openFile} />
          ),
        )}
        <div ref={bottom} />
      </div>
      {error && <p className="px-3 pb-1 text-sm text-danger">{error}</p>}
      <form onSubmit={send} className="flex items-end gap-2 border-t border-line p-3">
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKey}
          rows={2}
          placeholder="Polecenie dla Nexusa…"
          className="min-h-10 flex-1 resize-none rounded-xl border border-line bg-app px-3 py-2 text-sm outline-none focus:border-accent"
          aria-label="Polecenie"
        />
        {runId ? (
          <button
            type="button"
            onClick={() => void api.cancelRun(runId)}
            className="grid size-10 place-items-center rounded-full bg-fg text-app"
            aria-label="Zatrzymaj"
          >
            <StopIcon size={16} />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!text.trim()}
            className="grid size-10 place-items-center rounded-full bg-accent-fill text-on-accent disabled:opacity-40"
            aria-label="Wyślij"
          >
            <SendIcon size={18} />
          </button>
        )}
      </form>
    </section>
  );
}
