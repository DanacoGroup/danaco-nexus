// Moduł Poczta: skrzynki, lista i czytanie wiadomości, odpowiedzi (także przygotowane przez Nexusa),
// wiadomości oczekujące na wysłanie.

import { useCallback, useEffect, useState } from "react";
import { PaperclipIcon, PlusIcon, SparkIcon } from "../../components/icons";
import { SettingsIcon } from "../../shell/icons";
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
import { UstawieniaKonta } from "./UstawieniaKonta";
import { MessageView } from "./MessageView";

const PENDING = "__oczekujace__";
const EMPTY_DRAFT: DraftPayload = { to: [], cc: [], bcc: [], subject: "", body: "" };

type Compose = { initial: DraftPayload; pending?: PendingMail } | null;

function NotConfigured({ state, onPodlacz }: { state: MailState; onPodlacz: () => void }) {
  return (
    <>
      {/* Tytuł strony dla czytnika ekranu: na telefonie niesie go pasek kompaktowy powłoki,
          a w stanie „niepodłączona” moduł nie rysował na komputerze żadnego `h1`. */}
      <h1 className="sr-only">Poczta</h1>
      <EmptyState icon={<MailIcon size={26} />} title="Poczta nie jest jeszcze podłączona" szerokosc="max-w-2xl" poziom={2}>
        <p className="mx-auto max-w-lg">
          Podaj adres i hasło swojej skrzynki, a Nexus zacznie czytać, szukać i przygotowywać odpowiedzi.
          Hasło zapisuje się po Twojej stronie konta i nie wraca do przeglądarki.
        </p>
        {state.error && <p className="mt-3 text-danger">{state.error}</p>}
        <button type="button" onClick={onPodlacz} className={`mt-5 ${buttonClass.primary}`}>
          Podłącz skrzynkę
        </button>
        {/* Pusty moduł kończył się jednym zdaniem i przyciskiem. Tu jest jeszcze to, o co
          pyta każdy przed podaniem hasła: skąd Nexus weźmie ustawienia serwera i co
          właściwie zrobi ze skrzynką. */}
        <p className="mt-8 text-xs tracking-wide text-subtle uppercase">Ustawienia serwera wpiszą się same</p>
        <div className="mt-3 flex flex-wrap justify-center gap-2">
          {["Gmail", "Outlook", "WP", "Onet", "Interia", "o2", "własny IMAP"].map((nazwa) => (
            <span key={nazwa} className="rounded-full border border-line px-3 py-1 text-xs text-muted">
              {nazwa}
            </span>
          ))}
        </div>
        <ul className="mt-6 grid gap-2 text-left text-sm text-muted sm:grid-cols-2">
          <li className="rounded-xl border border-line bg-raised/50 px-3 py-2">
            Szuka w skrzynce konkretnej sprawy, nie tylko po słowie w temacie.
          </li>
          <li className="rounded-xl border border-line bg-raised/50 px-3 py-2">
            Pisze odpowiedź i zostawia ją w wersjach roboczych — wysyłasz Ty.
          </li>
          <li className="rounded-xl border border-line bg-raised/50 px-3 py-2">
            Wyciąga z wiadomości terminy i wstawia je do kalendarza.
          </li>
          <li className="rounded-xl border border-line bg-raised/50 px-3 py-2">
            Zapisuje załączniki w Twoich plikach i od razu je rozumie.
          </li>
        </ul>
      </EmptyState>
    </>
  );
}

export function PocztaPage({ openConversation }: ModulePageProps) {
  const [state, setState] = useState<MailState | null>(null);
  const [account, setAccount] = useState("");
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
  const [ustawienia, setUstawienia] = useState(false);
  const [confirm, confirmDialog] = useConfirm();
  const [toast, toastNode] = useToast();

  const loadFolders = useCallback(() => {
    if (!account) return;
    mailApi
      .folders(account)
      .then(setFolders)
      .catch((failure) => setError(describe(failure)));
  }, [account]);
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
        if (value.configured) setAccount(value.accounts[0]?.id ?? value.address);
      })
      .catch((failure) => setError(describe(failure)));
    loadPending();
  }, [loadPending]);

  useEffect(() => {
    setFolders([]);
    loadFolders();
  }, [loadFolders]);

  // Wiadomości przygotowane przez asystenta pojawiają się w tle – lista oczekujących jest odświeżana.
  useEffect(() => {
    const timer = window.setInterval(loadPending, 20_000);
    return () => window.clearInterval(timer);
  }, [loadPending]);

  const loadMessages = useCallback(
    async (append = false) => {
      if (folder === PENDING || !account) return;
      setError("");
      try {
        const before = append && messages?.length ? messages[messages.length - 1].uid : undefined;
        const listing = searching
          ? await mailApi.search(account, folder, searching)
          : await mailApi.messages(account, folder, before);
        setMessages((current) => (append && current ? [...current, ...listing.messages] : listing.messages));
        setMore(!searching && listing.more);
        setTotal(listing.total);
      } catch (failure) {
        setError(describe(failure));
        setMessages([]);
      }
    },
    [account, folder, searching, messages],
  );

  useEffect(() => {
    if (!state?.configured || !account) return;
    setMessages(null);
    setOpen(null);
    loadMessages(false);
  }, [account, folder, searching, state?.configured]);

  const switchAccount = (id: string) => {
    if (id === account) return;
    setQuery("");
    setSearching("");
    setOpen(null);
    setFolder("INBOX");
    setAccount(id);
  };

  const read = async (header: MailHeader) => {
    setOpening(header.uid);
    setError("");
    try {
      const message = await mailApi.read(account, folder, header.uid);
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
      await mailApi.flag(account, folder, uid, flag, value);
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

  const odswiezStan = () => {
    setUstawienia(false);
    mailApi
      .state()
      .then((swiezy) => {
        setState(swiezy);
        setAccount(swiezy.accounts?.[0]?.id ?? "");
      })
      .catch((failure) => setError(describe(failure)));
  };

  if (!state) return error ? <div className="p-6"><ErrorBanner message={error} /></div> : <Loading />;
  if (ustawienia) {
    return (
      <div className="h-full overflow-y-auto bg-app">
        <UstawieniaKonta
          konta={state.accounts ?? []}
          onZmiana={odswiezStan}
          onZamknij={state.configured ? () => setUstawienia(false) : undefined}
        />
      </div>
    );
  }
  if (!state.configured) return <NotConfigured state={state} onPodlacz={() => setUstawienia(true)} />;

  const current = folders.find((item) => item.name === folder);
  const accounts = state.accounts ?? [];
  const newDraft = (): DraftPayload => ({ ...EMPTY_DRAFT, account });
  const openHeader = open ? messages?.find((item) => item.uid === open.uid) : undefined;

  return (
    <div className="flex h-full min-h-0 bg-app">
      {/* Tytuł strony na telefonie: widoczny nagłówek modułu jest ukryty poniżej `md`,
          a pasek powłoki niesie tylko etykietę. */}
      <h1 className="sr-only md:hidden">Poczta</h1>
      {/* Foldery */}
      <nav className="hidden w-56 shrink-0 flex-col border-r border-line bg-side md:flex">
        <div className="px-3 pt-4 pb-2">
          <h1 className="px-2 text-lg font-semibold">Poczta</h1>
          {accounts.length > 1 ? (
            <div className="mt-2 space-y-0.5" role="radiogroup" aria-label="Konto pocztowe">
              {accounts.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={item.id === account}
                  title={item.address}
                  className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs ${
                    item.id === account ? "bg-accent-soft font-medium text-fg" : "text-muted hover:bg-hover"
                  }`}
                  onClick={() => switchAccount(item.id)}
                >
                  <MailIcon size={14} className="shrink-0" />
                  <span className="min-w-0 flex-1 truncate">{item.address}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="truncate px-2 text-xs text-muted" title={state.address}>
              {state.address}
            </p>
          )}
          <button type="button" className={`${buttonClass.primary} mt-3 w-full`} onClick={() => setCompose({ initial: newDraft() })}>
            <PlusIcon size={18} /> Nowa wiadomość
          </button>
          <button type="button" className={`${buttonClass.ghost} mt-1.5 w-full`} onClick={() => setUstawienia(true)}>
            Skrzynki i ustawienia
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
              <span className="rounded-full bg-accent-fill px-1.5 text-xs font-semibold text-on-accent">{pending.length}</span>
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
            {accounts.length > 1 && (
              <div className="border-b border-line px-3 py-2 md:hidden">
                <select
                  className="w-full rounded-xl border border-line bg-raised px-2 py-1.5 text-sm"
                  value={account}
                  onChange={(event) => switchAccount(event.target.value)}
                  aria-label="Konto pocztowe"
                >
                  {accounts.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.address}
                    </option>
                  ))}
                </select>
              </div>
            )}
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
              <button type="button" className="icon-btn md:hidden" aria-label="Nowa wiadomość" onClick={() => setCompose({ initial: newDraft() })}>
                <PlusIcon />
              </button>
              {/* Lewa kolumna ze „Skrzynkami i ustawieniami” znika poniżej `md`; bez tego
                  przycisku na telefonie nie da się dodać ani odłączyć skrzynki. */}
              <button type="button" className="icon-btn md:hidden" aria-label="Skrzynki i ustawienia" onClick={() => setUstawienia(true)}>
                <SettingsIcon />
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
                          {/* Kropka niesie całą informację „nieprzeczytana”, więc ma nazwę — a nazwa na `span`
                            bez roli jest zakazana (ARIA in HTML) i mogła nie dotrzeć do czytnika ekranu. */}
                          {!item.seen && (
                            <span role="img" className="size-2 shrink-0 rounded-full bg-accent-fill" aria-label="Nieprzeczytana" />
                          )}
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
          accounts={accounts}
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
                    <p className="truncate text-xs text-muted">
                      {item.payload.account ? `Od: ${item.payload.account} · ` : ""}Do:{" "}
                      {item.payload.to.join(", ") || "(brak adresata)"}
                    </p>
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
      const result = await mailApi.replyWithNexus(message.account ?? "", message.folder, message.uid, instruction);
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
