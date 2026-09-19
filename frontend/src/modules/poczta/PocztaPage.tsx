// Moduł Poczta: skrzynki, lista i czytanie wiadomości, odpowiedzi (także przygotowane przez Nexusa),
// wiadomości oczekujące na wysłanie.

import { useCallback, useEffect, useState } from "react";
import { PaperclipIcon, PlusIcon, SparkIcon } from "../../components/icons";
import type { ModulePageProps } from "../registry";
import { describe } from "../_biuro/http";
import { ClockIcon, InboxIcon, MailIcon, SearchIcon, StarIcon } from "../_biuro/icons";
import { buttonClass, EmptyState, ErrorBanner, Field, inputClass, Loading, Modal, useConfirm, useToast } from "../_biuro/ui";
import {
  displayName,
  listDate,
  mailApi,
  replyDraft,
  type DraftPayload,
  type MailFolder,
  type MailHeader,
  type MailMessage,
  type MailState,
  type PendingMail,
} from "./api";
import { ComposeDialog } from "./ComposeDialog";
import { MessageView } from "./MessageView";

const PENDING = "__oczekujace__";
const EMPTY_DRAFT: DraftPayload = { to: [], cc: [], bcc: [], subject: "", body: "" };

type Compose = { initial: DraftPayload; pending?: PendingMail } | null;

function NotConfigured({ state }: { state: MailState }) {
  return (
    <EmptyState icon={<MailIcon size={26} />} title="Poczta nie jest jeszcze podłączona">
      <p>
        Na serwerze uruchom polecenie i podaj adres oraz hasło skrzynki (hasło jest wczytywane bez wyświetlania i zapisywane
        tylko na serwerze):
      </p>
      <code className="mt-3 block rounded-lg bg-code px-3 py-2 text-left font-mono text-xs text-fg">
        {state.setup ?? "sudo -u danaco-serwis deploy/zapisz-poczte.sh"}
      </code>
      {state.error && <p className="mt-3 text-danger">{state.error}</p>}
    </EmptyState>
  );
}

export function PocztaPage({ openConversation }: ModulePageProps) {
  const [state, setState] = useState<MailState | null>(null);
  const [folders, setFolders] = useState<MailFolder[]>([]);
  const [folder, setFolder] = useState("INBOX");
  const [messages, setMessages] = useState<MailHeader[] | null>(null);
  const [more, setMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState("");
  const [open, setOpen] = useState<MailMessage | null>(null);
  const [opening, setOpening] = useState<number | null>(null);
  const [pending, setPending] = useState<PendingMail[]>([]);
  const [compose, setCompose] = useState<Compose>(null);
  const [nexusReply, setNexusReply] = useState<MailMessage | null>(null);
  const [error, setError] = useState("");
  const [confirm, confirmDialog] = useConfirm();
  const [toast, toastNode] = useToast();

  const loadFolders = useCallback(() => {
    mailApi
      .folders()
      .then(setFolders)
      .catch((failure) => setError(describe(failure)));
  }, []);
  const loadPending = useCallback(() => {
    mailApi
      .pending()
      .then(setPending)
      .catch(() => setPending([]));
  }, []);

  useEffect(() => {
    mailApi
      .state()
      .then((value) => {
        setState(value);
        if (value.configured) loadFolders();
      })
      .catch((failure) => setError(describe(failure)));
    loadPending();
  }, [loadFolders, loadPending]);

  // Wiadomości przygotowane przez asystenta pojawiają się w tle – lista oczekujących jest odświeżana.
  useEffect(() => {
    const timer = window.setInterval(loadPending, 20_000);
    return () => window.clearInterval(timer);
  }, [loadPending]);

  const loadMessages = useCallback(
    async (append = false) => {
      if (folder === PENDING) return;
      setError("");
      try {
        const before = append && messages?.length ? messages[messages.length - 1].uid : undefined;
        const listing = searching ? await mailApi.search(folder, searching) : await mailApi.messages(folder, before);
        setMessages((current) => (append && current ? [...current, ...listing.messages] : listing.messages));
        setMore(!searching && listing.more);
        setTotal(listing.total);
      } catch (failure) {
        setError(describe(failure));
        setMessages([]);
      }
    },
    [folder, searching, messages],
  );

  useEffect(() => {
    if (!state?.configured) return;
    setMessages(null);
    setOpen(null);
    loadMessages(false);
  }, [folder, searching, state?.configured]);

  const read = async (header: MailHeader) => {
    setOpening(header.uid);
    setError("");
    try {
      const message = await mailApi.read(folder, header.uid);
      setOpen(message);
      if (!header.seen) {
        setMessages((items) => items?.map((item) => (item.uid === header.uid ? { ...item, seen: true } : item)) ?? null);
        setFolders((items) =>
          items.map((item) => (item.name === folder && item.unseen ? { ...item, unseen: item.unseen - 1 } : item)),
        );
      }
    } catch (failure) {
      setError(describe(failure));
    } finally {
      setOpening(null);
    }
  };

  const setFlag = async (uid: number, flag: "seen" | "flagged", value: boolean) => {
    try {
      await mailApi.flag(folder, uid, flag, value);
      setMessages((items) =>
        items?.map((item) => (item.uid === uid ? { ...item, [flag === "seen" ? "seen" : "flagged"]: value } : item)) ?? null,
      );
      if (flag === "seen" && !value) {
        setOpen(null);
        loadFolders();
      }
    } catch (failure) {
      setError(describe(failure));
    }
  };

  const discard = async (item: PendingMail) => {
    const ok = await confirm({
      title: "Odrzucić wiadomość?",
      message: <>Wiadomość „{item.payload.subject || "(bez tematu)"}” nie zostanie wysłana.</>,
      confirmLabel: "Odrzuć",
      danger: true,
    });
    if (!ok) return;
    try {
      await mailApi.cancelPending(item.id);
      loadPending();
    } catch (failure) {
      setError(describe(failure));
    }
  };

  if (!state) return error ? <div className="p-6"><ErrorBanner message={error} /></div> : <Loading />;
  if (!state.configured) return <NotConfigured state={state} />;

  const current = folders.find((item) => item.name === folder);
  const openHeader = open ? messages?.find((item) => item.uid === open.uid) : undefined;

  return (
    <div className="flex h-full min-h-0 bg-app">
      {/* Foldery */}
      <nav className="hidden w-56 shrink-0 flex-col border-r border-line bg-side md:flex">
        <div className="px-3 pt-4 pb-2">
          <h1 className="px-2 text-lg font-semibold">Poczta</h1>
          <p className="truncate px-2 text-xs text-muted" title={state.address}>
            {state.address}
          </p>
          <button type="button" className={`${buttonClass.primary} mt-3 w-full`} onClick={() => setCompose({ initial: EMPTY_DRAFT })}>
            <PlusIcon size={18} /> Nowa wiadomość
          </button>
        </div>
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
          <button
            type="button"
            className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm ${
              folder === PENDING ? "bg-hover font-medium" : "hover:bg-hover"
            }`}
            onClick={() => setFolder(PENDING)}
          >
            <ClockIcon size={18} className="text-accent" />
            <span className="flex-1">Oczekujące</span>
            {pending.length > 0 && (
              <span className="rounded-full bg-accent px-1.5 text-xs font-semibold text-on-accent">{pending.length}</span>
            )}
          </button>
          {folders.map((item) => (
            <button
              key={item.name}
              type="button"
              className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm ${
                folder === item.name ? "bg-hover font-medium" : "text-fg hover:bg-hover"
              }`}
              onClick={() => {
                setQuery("");
                setSearching("");
                setFolder(item.name);
              }}
            >
              {item.role === "INBOX" ? <InboxIcon size={18} /> : <MailIcon size={18} className="text-muted" />}
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
              {!!item.unseen && <span className="text-xs font-semibold text-accent">{item.unseen}</span>}
            </button>
          ))}
        </div>
      </nav>

      {folder === PENDING ? (
        <PendingList
          items={pending}
          onOpen={(item) => setCompose({ initial: item.payload, pending: item })}
          onDiscard={discard}
          onBack={() => setFolder("INBOX")}
        />
      ) : (
        <>
          {/* Lista wiadomości */}
          <section className={`min-h-0 w-full flex-col border-r border-line lg:flex lg:w-96 ${open ? "hidden" : "flex"}`}>
            <form
              className="flex items-center gap-2 border-b border-line px-3 py-2.5"
              onSubmit={(event) => {
                event.preventDefault();
                setSearching(query.trim());
              }}
            >
              <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-line bg-raised px-3 py-1.5">
                <SearchIcon size={16} className="shrink-0 text-muted" />
                <input
                  className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted"
                  placeholder={`Szukaj w: ${current?.label ?? folder}`}
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    if (!event.target.value) setSearching("");
                  }}
                  aria-label="Szukaj wiadomości"
                />
              </label>
              <select
                className="rounded-xl border border-line bg-raised px-2 py-1.5 text-sm md:hidden"
                value={folder}
                onChange={(event) => setFolder(event.target.value)}
                aria-label="Folder"
              >
                <option value={PENDING}>Oczekujące ({pending.length})</option>
                {folders.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.label}
                  </option>
                ))}
              </select>
              <button type="button" className="icon-btn md:hidden" aria-label="Nowa wiadomość" onClick={() => setCompose({ initial: EMPTY_DRAFT })}>
                <PlusIcon />
              </button>
            </form>
            <div className="px-3 pt-2">
              <ErrorBanner message={error} onClose={() => setError("")} />
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {messages === null ? (
                <Loading />
              ) : messages.length === 0 ? (
                <EmptyState icon={<InboxIcon size={26} />} title={searching ? "Nic nie znaleziono" : "Brak wiadomości"} />
              ) : (
                <ul className="divide-y divide-line/70">
                  {messages.map((item) => (
                    <li key={item.uid}>
                      <button
                        type="button"
                        className={`block w-full px-4 py-2.5 text-left transition-colors ${
                          open?.uid === item.uid ? "bg-accent-soft/50" : "hover:bg-raised"
                        }`}
                        onClick={() => read(item)}
                      >
                        <span className="flex items-center gap-2">
                          {!item.seen && <span className="size-2 shrink-0 rounded-full bg-accent" aria-label="Nieprzeczytana" />}
                          <span className={`min-w-0 flex-1 truncate text-sm ${item.seen ? "" : "font-semibold"}`}>
                            {folder === folders.find((f) => f.role === "\\Sent")?.name ? `Do: ${displayName(item.to)}` : displayName(item.from)}
                          </span>
                          {opening === item.uid && <span className="spinner" />}
                          {item.flagged && <StarIcon filled size={14} className="shrink-0 text-accent" />}
                          {item.has_attachments && <PaperclipIcon size={14} className="shrink-0 text-muted" />}
                          <span className="shrink-0 text-xs text-muted">{listDate(item.date)}</span>
                        </span>
                        <span className={`mt-0.5 block truncate text-sm ${item.seen ? "text-muted" : ""}`}>
                          {item.subject || "(bez tematu)"}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {more && messages && (
                <div className="p-3 text-center">
                  <button type="button" className={buttonClass.secondary} onClick={() => loadMessages(true)}>
                    Starsze wiadomości ({total - messages.length})
                  </button>
                </div>
              )}
            </div>
          </section>

          {/* Czytanie */}
          <section className={`min-h-0 min-w-0 flex-1 flex-col ${open ? "flex" : "hidden lg:flex"}`}>
            {open ? (
              <MessageView
                message={open}
                flagged={openHeader?.flagged ?? false}
                onBack={() => setOpen(null)}
                onReply={() => setCompose({ initial: replyDraft(open) })}
                onReplyWithNexus={() => setNexusReply(open)}
                onToggleFlag={() => setFlag(open.uid, "flagged", !(openHeader?.flagged ?? false))}
                onMarkUnread={() => setFlag(open.uid, "seen", false)}
              />
            ) : (
              <EmptyState icon={<MailIcon size={26} />} title="Wybierz wiadomość">
                Nexus może przygotować odpowiedź – otwórz wiadomość i wybierz „Odpowiedz z Nexusem”.
              </EmptyState>
            )}
          </section>
        </>
      )}

      {compose && (
        <ComposeDialog
          initial={compose.initial}
          pending={compose.pending}
          onClose={() => setCompose(null)}
          onDone={(message) => {
            toast(message);
            loadPending();
            loadFolders();
          }}
        />
      )}
      {nexusReply && (
        <NexusReplyDialog
          message={nexusReply}
          onClose={() => setNexusReply(null)}
          onStarted={(conversationId) => openConversation(conversationId)}
        />
      )}
      {confirmDialog}
      {toastNode}
    </div>
  );
}

function PendingList({
  items,
  onOpen,
  onDiscard,
  onBack,
}: {
  items: PendingMail[];
  onOpen: (item: PendingMail) => void;
  onDiscard: (item: PendingMail) => void;
  onBack: () => void;
}) {
  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <button type="button" className="icon-btn md:hidden" onClick={onBack} aria-label="Wróć do skrzynki">
          <InboxIcon />
        </button>
        <div>
          <h2 className="font-semibold">Oczekujące na wysłanie</h2>
          <p className="text-xs text-muted">Wiadomości przygotowane przez Nexusa albo odłożone na później. Wysyłasz je sam.</p>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3 md:p-4">
        {items.length === 0 ? (
          <EmptyState icon={<ClockIcon size={26} />} title="Nic nie czeka na wysłanie">
            Poproś Nexusa na czacie o przygotowanie odpowiedzi – gotowa wiadomość pojawi się tutaj do sprawdzenia.
          </EmptyState>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => (
              <li key={item.id} className="rounded-2xl border border-line p-3">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">
                    {item.run_id ? <SparkIcon size={18} /> : <MailIcon size={18} />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{item.payload.subject || "(bez tematu)"}</p>
                    <p className="truncate text-xs text-muted">Do: {item.payload.to.join(", ") || "(brak adresata)"}</p>
                    <p className="mt-1 line-clamp-2 text-sm text-muted">{item.payload.body}</p>
                    {item.error && <p className="mt-1 text-xs text-danger">Ostatnia próba: {item.error}</p>}
                    <p className="mt-1 text-xs text-muted">
                      {item.run_id ? "Przygotował Nexus" : "Zapisana przez Ciebie"} ·{" "}
                      {new Date(item.created_at).toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" })}
                    </p>
                  </div>
                </div>
                <div className="mt-3 flex justify-end gap-2">
                  <button type="button" className={buttonClass.ghost} onClick={() => onDiscard(item)}>
                    Odrzuć
                  </button>
                  <button type="button" className={buttonClass.primary} onClick={() => onOpen(item)}>
                    Sprawdź i wyślij
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function NexusReplyDialog({
  message,
  onClose,
  onStarted,
}: {
  message: MailMessage;
  onClose: () => void;
  onStarted: (conversationId: string) => void;
}) {
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await mailApi.replyWithNexus(message.folder, message.uid, instruction);
      onStarted(result.conversation_id);
    } catch (failure) {
      setError(describe(failure));
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Odpowiedz z Nexusem"
      onClose={onClose}
      footer={
        <>
          <button type="button" className={buttonClass.secondary} onClick={onClose}>
            Anuluj
          </button>
          <button type="button" className={buttonClass.primary} disabled={busy} onClick={start}>
            {busy ? <span className="spinner" /> : <SparkIcon size={17} />} Przygotuj odpowiedź
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-sm text-muted">
          Nexus przeczyta wiadomość „{message.subject || "(bez tematu)"}” i przygotuje odpowiedź. Trafi ona do
          „Oczekujących”, gdzie ją poprawisz i sam wyślesz.
        </p>
        <Field label="Wskazówki (opcjonalnie)">
          <textarea
            className={`${inputClass} min-h-24 resize-y`}
            placeholder="Np. Potwierdź rezerwację i zaproponuj późniejsze zameldowanie."
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
          />
        </Field>
        <ErrorBanner message={error} />
      </div>
    </Modal>
  );
}
