// Okna modułu Cloud: nazwa, udostępnianie linkiem, wersje, przenoszenie, wysłanie do rozmowy, podgląd.

import { useEffect, useState } from "react";
import { api, type ConversationSummary } from "../../api";
import { CloseIcon, DownloadIcon, FileIcon, TrashIcon } from "../../components/icons";
import { formatSize } from "../../runState";
import { describe } from "../_biuro/http";
import { BackIcon, CopyIcon, FolderIcon, LockIcon } from "../_biuro/icons";
import { buttonClass, copyText, ErrorBanner, Field, inputClass, Loading, Modal } from "../_biuro/ui";
import {
  breadcrumbs,
  cloudApi,
  downloadUrl,
  parentPath,
  versionUrl,
  type CloudEntry,
  type CloudShare,
  type CloudVersion,
} from "./api";

export function formatDate(value: string | number | null): string {
  if (value === null || value === "") return "—";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("pl-PL", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

// --- nazwa (nowy folder, zmiana nazwy) ---

export function NameDialog({
  title,
  initial,
  confirmLabel,
  onSubmit,
  onClose,
}: {
  title: string;
  initial: string;
  confirmLabel: string;
  onSubmit: (name: string) => Promise<void>;
  onClose: () => void;
}) {
  const [name, setName] = useState(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    const value = name.trim();
    if (!value) return;
    setBusy(true);
    setError("");
    try {
      await onSubmit(value);
      onClose();
    } catch (failure) {
      setError(describe(failure));
      setBusy(false);
    }
  };
  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" className={buttonClass.secondary} onClick={onClose}>
            Anuluj
          </button>
          <button type="button" className={buttonClass.primary} disabled={busy || !name.trim()} onClick={submit}>
            {busy && <span className="spinner" />} {confirmLabel}
          </button>
        </>
      }
    >
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <input
          className={inputClass}
          value={name}
          maxLength={250}
          onChange={(event) => setName(event.target.value)}
          onFocus={(event) => {
            const dot = event.target.value.lastIndexOf(".");
            event.target.setSelectionRange(0, dot > 0 ? dot : event.target.value.length);
          }}
          aria-label="Nazwa"
        />
        <ErrorBanner message={error} />
      </form>
    </Modal>
  );
}

// --- udostępnianie linkiem ---

function tomorrow(): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  return date.toISOString().slice(0, 10);
}

export function ShareDialog({ entry, onClose, onChanged }: { entry: CloudEntry; onClose: () => void; onChanged: () => void }) {
  const [shares, setShares] = useState<CloudShare[] | null>(null);
  const [error, setError] = useState("");
  const [password, setPassword] = useState("");
  const [usePassword, setUsePassword] = useState(false);
  const [expires, setExpires] = useState("");
  const [allowUpload, setAllowUpload] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState("");

  const load = () =>
    cloudApi
      .shares(entry.path)
      .then(setShares)
      .catch((failure) => setError(describe(failure)));
  useEffect(() => {
    load();
  }, [entry.path]);

  const create = async () => {
    setBusy(true);
    setError("");
    try {
      const share = await cloudApi.createShare({
        path: entry.path,
        password: usePassword ? password : undefined,
        expires: expires || undefined,
        allow_upload: entry.type === "folder" && allowUpload,
      });
      await copyText(share.url).catch(() => undefined);
      setCopied(share.id);
      setPassword("");
      setUsePassword(false);
      await load();
      onChanged();
    } catch (failure) {
      setError(describe(failure));
    } finally {
      setBusy(false);
    }
  };

  const change = async (share: CloudShare, body: Parameters<typeof cloudApi.updateShare>[1]) => {
    setError("");
    try {
      await cloudApi.updateShare(share.id, body);
      await load();
    } catch (failure) {
      setError(describe(failure));
    }
  };

  const remove = async (share: CloudShare) => {
    setError("");
    try {
      await cloudApi.deleteShare(share.id);
      await load();
      onChanged();
    } catch (failure) {
      setError(describe(failure));
    }
  };

  return (
    <Modal title={`Udostępnij: ${entry.name}`} onClose={onClose} wide>
      <div className="space-y-5">
        <ErrorBanner message={error} onClose={() => setError("")} />
        <section className="space-y-2">
          <h3 className="text-sm font-semibold">Linki publiczne</h3>
          {shares === null ? (
            <Loading />
          ) : shares.length === 0 ? (
            <p className="text-sm text-muted">Brak linków – każdy, kto dostanie link, zobaczy ten element bez logowania.</p>
          ) : (
            <ul className="space-y-2">
              {shares.map((share) => (
                <li key={share.id} className="space-y-2 rounded-xl border border-line p-3">
                  <div className="flex items-center gap-2">
                    <input className={`${inputClass} font-mono text-xs`} value={share.url} readOnly aria-label="Link" />
                    <button
                      type="button"
                      className="icon-btn"
                      aria-label="Kopiuj link"
                      onClick={() => copyText(share.url).then(() => setCopied(share.id))}
                    >
                      <CopyIcon />
                    </button>
                    <button type="button" className="icon-btn hover:text-danger" aria-label="Usuń link" onClick={() => remove(share)}>
                      <TrashIcon />
                    </button>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
                    {copied === share.id && <span className="text-success">Skopiowano do schowka</span>}
                    <span className="inline-flex items-center gap-1">
                      <LockIcon size={14} /> {share.has_password ? "z hasłem" : "bez hasła"}
                    </span>
                    <span>{share.expires ? `wygasa ${share.expires}` : "bez daty wygaśnięcia"}</span>
                    {share.permissions > 1 && <span>z wgrywaniem</span>}
                    {share.has_password ? (
                      <button type="button" className="text-accent hover:underline" onClick={() => change(share, { password: "" })}>
                        Usuń hasło
                      </button>
                    ) : null}
                    {share.expires ? (
                      <button
                        type="button"
                        className="text-accent hover:underline"
                        onClick={() => change(share, { clear_expiration: true })}
                      >
                        Bez wygaśnięcia
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="space-y-3 rounded-xl border border-line bg-side p-3">
          <h3 className="text-sm font-semibold">Nowy link</h3>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={usePassword} onChange={(event) => setUsePassword(event.target.checked)} />
            Chroń hasłem
          </label>
          {usePassword && (
            <input
              className={inputClass}
              type="password"
              autoComplete="new-password"
              placeholder="Hasło do linku (min. 10 znaków)"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          )}
          <Field label="Data wygaśnięcia (opcjonalnie)">
            <input className={inputClass} type="date" min={tomorrow()} value={expires} onChange={(event) => setExpires(event.target.value)} />
          </Field>
          {entry.type === "folder" && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={allowUpload} onChange={(event) => setAllowUpload(event.target.checked)} />
              Pozwól wgrywać i zmieniać pliki w folderze
            </label>
          )}
          <button
            type="button"
            className={buttonClass.primary}
            disabled={busy || (usePassword && password.length < 10)}
            onClick={create}
          >
            {busy && <span className="spinner" />} Utwórz link i skopiuj
          </button>
        </section>
      </div>
    </Modal>
  );
}

// --- wersje ---

export function VersionsDialog({ entry, onClose, onRestored }: { entry: CloudEntry; onClose: () => void; onRestored: () => void }) {
  const [versions, setVersions] = useState<CloudVersion[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  useEffect(() => {
    cloudApi
      .versions(entry.path)
      .then(setVersions)
      .catch((failure) => setError(describe(failure)));
  }, [entry.path]);

  const restore = async (version: CloudVersion) => {
    setBusy(version.id);
    setError("");
    try {
      await cloudApi.restoreVersion(entry.path, version.id);
      onRestored();
      onClose();
    } catch (failure) {
      setError(describe(failure));
      setBusy("");
    }
  };

  return (
    <Modal title={`Wersje: ${entry.name}`} onClose={onClose} wide>
      <div className="space-y-3">
        <p className="text-sm text-muted">
          Chmura zapisuje poprzednie wersje przy każdej zmianie pliku. Przywrócenie nie usuwa bieżącej zawartości – staje się
          ona kolejną wersją.
        </p>
        <ErrorBanner message={error} />
        <div className="flex items-center gap-3 rounded-xl border border-accent/40 bg-accent-soft/40 px-3 py-2.5 text-sm">
          <FileIcon className="text-accent" />
          <span className="min-w-0 flex-1">
            <span className="font-medium">Bieżąca wersja</span>
            <span className="block text-xs text-muted">
              {formatDate(entry.modified)} · {entry.size !== null ? formatSize(entry.size) : "—"}
            </span>
          </span>
        </div>
        {versions === null ? (
          <Loading />
        ) : versions.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted">Ten plik nie ma jeszcze poprzednich wersji.</p>
        ) : (
          <ul className="divide-y divide-line rounded-xl border border-line">
            {versions.map((version) => (
              <li key={version.id} className="flex items-center gap-3 px-3 py-2.5 text-sm">
                <span className="min-w-0 flex-1">
                  <span className="block">{version.label || formatDate(version.modified)}</span>
                  <span className="block text-xs text-muted">
                    {version.label ? `${formatDate(version.modified)} · ` : ""}
                    {version.size !== null ? formatSize(version.size) : "—"}
                    {version.author ? ` · ${version.author}` : ""}
                  </span>
                </span>
                <a className="icon-btn" href={versionUrl(entry.path, version.id)} aria-label="Pobierz wersję">
                  <DownloadIcon />
                </a>
                <button type="button" className={buttonClass.secondary} disabled={busy !== ""} onClick={() => restore(version)}>
                  {busy === version.id && <span className="spinner" />} Przywróć
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}

// --- przenoszenie i kopiowanie ---

export function MoveDialog({
  entries,
  start,
  onClose,
  onDone,
}: {
  entries: CloudEntry[];
  start: string;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [path, setPath] = useState(start);
  const [folders, setFolders] = useState<CloudEntry[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const moving = new Set(entries.map((entry) => entry.path));
  useEffect(() => {
    setFolders(null);
    cloudApi
      .list(path)
      .then((listing) => setFolders(listing.entries.filter((entry) => entry.type === "folder")))
      .catch((failure) => setError(describe(failure)));
  }, [path]);

  const run = async (copy: boolean) => {
    setBusy(true);
    setError("");
    try {
      await cloudApi.move(
        entries.map((entry) => entry.path),
        path,
        copy,
      );
      onDone(`${copy ? "Skopiowano" : "Przeniesiono"} ${entries.length === 1 ? entries[0].name : `${entries.length} elementy`} do ${path}`);
      onClose();
    } catch (failure) {
      setError(describe(failure));
      setBusy(false);
    }
  };
  const sameFolder = entries.every((entry) => parentPath(entry.path) === path);

  return (
    <Modal
      title={entries.length === 1 ? `Przenieś: ${entries[0].name}` : `Przenieś ${entries.length} elementy`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className={buttonClass.secondary} disabled={busy} onClick={() => run(true)}>
            Kopiuj tutaj
          </button>
          <button type="button" className={buttonClass.primary} disabled={busy || sameFolder} onClick={() => run(false)}>
            {busy && <span className="spinner" />} Przenieś tutaj
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-1 text-sm">
          {path !== "/" && (
            <button type="button" className="icon-btn size-7" aria-label="Folder wyżej" onClick={() => setPath(parentPath(path))}>
              <BackIcon size={16} />
            </button>
          )}
          {breadcrumbs(path).map((crumb, index, all) => (
            <span key={crumb.path} className="flex items-center gap-1">
              <button type="button" className="rounded px-1 hover:bg-hover" onClick={() => setPath(crumb.path)}>
                {crumb.name}
              </button>
              {index < all.length - 1 && <span className="text-muted">/</span>}
            </span>
          ))}
        </div>
        <ErrorBanner message={error} />
        {folders === null ? (
          <Loading />
        ) : folders.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">Brak podfolderów.</p>
        ) : (
          <ul className="max-h-72 divide-y divide-line overflow-y-auto rounded-xl border border-line">
            {folders.map((folder) => (
              <li key={folder.path}>
                <button
                  type="button"
                  disabled={moving.has(folder.path)}
                  className="flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-hover disabled:opacity-40"
                  onClick={() => setPath(folder.path)}
                >
                  <FolderIcon className="text-accent" />
                  <span className="truncate">{folder.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}

// --- wysłanie do rozmowy ---

export function SendToChatDialog({
  entries,
  onClose,
  onSent,
}: {
  entries: CloudEntry[];
  onClose: () => void;
  onSent: (conversationId: string) => void;
}) {
  const files = entries.filter((entry) => entry.type === "file");
  const [text, setText] = useState("");
  const [target, setTarget] = useState("");
  const [send, setSend] = useState(true);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api
      .conversations()
      .then((list) => setConversations(list.slice(0, 30)))
      .catch(() => setConversations([]));
  }, []);

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await cloudApi.toConversation({
        paths: files.map((entry) => entry.path),
        conversation_id: target || null,
        text,
        send,
      });
      onSent(result.conversation_id);
    } catch (failure) {
      setError(describe(failure));
      setBusy(false);
    }
  };

  return (
    <Modal
      title="Wyślij do rozmowy"
      onClose={onClose}
      footer={
        <>
          <button type="button" className={buttonClass.secondary} onClick={onClose}>
            Anuluj
          </button>
          <button type="button" className={buttonClass.primary} disabled={busy || files.length === 0} onClick={submit}>
            {busy && <span className="spinner" />} {send ? "Wyślij do asystenta" : "Dołącz do rozmowy"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <ul className="space-y-1 text-sm">
          {files.map((entry) => (
            <li key={entry.path} className="flex items-center gap-2">
              <FileIcon size={16} className="shrink-0 text-muted" />
              <span className="truncate">{entry.name}</span>
              <span className="shrink-0 text-xs text-muted">{entry.size !== null ? formatSize(entry.size) : ""}</span>
            </li>
          ))}
        </ul>
        {files.length < entries.length && (
          <p className="text-xs text-muted">Foldery są pomijane – wybierz pliki z ich wnętrza.</p>
        )}
        <Field label="Rozmowa">
          <select className={inputClass} value={target} onChange={(event) => setTarget(event.target.value)}>
            <option value="">Nowa rozmowa</option>
            {conversations.map((conversation) => (
              <option key={conversation.id} value={conversation.id} disabled={conversation.active}>
                {conversation.title}
                {conversation.active ? " (trwa zadanie)" : ""}
              </option>
            ))}
          </select>
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={send} onChange={(event) => setSend(event.target.checked)} />
          Od razu wyślij wiadomość do asystenta
        </label>
        {send && (
          <Field label="Polecenie (opcjonalnie)">
            <textarea
              className={`${inputClass} min-h-24 resize-y`}
              placeholder="Np. Streść te dokumenty i wypisz terminy płatności."
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </Field>
        )}
        <ErrorBanner message={error} />
      </div>
    </Modal>
  );
}

// --- podgląd ---

const TEXT_TYPES = /^(text\/plain|text\/markdown|text\/csv|application\/json)/;

export function previewKind(entry: CloudEntry): "image" | "video" | "audio" | "pdf" | "text" | null {
  const mime = entry.mime ?? "";
  if (mime === "image/svg+xml") return null;
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  if (mime.startsWith("audio/")) return "audio";
  if (mime === "application/pdf") return "pdf";
  if (TEXT_TYPES.test(mime) || /\.(txt|md|csv|log|json)$/i.test(entry.name)) return "text";
  return null;
}

export function CloudPreview({ entry, onClose }: { entry: CloudEntry; onClose: () => void }) {
  const kind = previewKind(entry);
  const url = downloadUrl(entry.path, true);
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    if (kind !== "text") return;
    fetch(downloadUrl(entry.path), { credentials: "same-origin" })
      .then((response) => response.text())
      .then((value) => setText(value.length > 500_000 ? `${value.slice(0, 500_000)}\n…` : value))
      .catch(() => setText("Nie udało się wczytać pliku."));
  }, [entry.path, kind]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  let body;
  if (kind === "image") body = <img src={url} alt={entry.name} className="max-h-full max-w-full object-contain" />;
  else if (kind === "video") body = <video src={url} controls autoPlay className="max-h-full max-w-full" />;
  else if (kind === "audio") body = <audio src={url} controls autoPlay className="w-full max-w-md" />;
  else if (kind === "pdf") body = <iframe src={url} title={entry.name} className="size-full rounded-lg bg-white" />;
  else if (kind === "text")
    body =
      text === null ? (
        <Loading />
      ) : (
        <pre className="size-full overflow-auto rounded-lg bg-code p-4 font-mono text-[13px] whitespace-pre-wrap">{text}</pre>
      );
  else
    body = (
      <div className="text-center text-sm text-muted">
        Podgląd tego rodzaju pliku nie jest dostępny.
        <a className={`${buttonClass.primary} mt-4`} href={downloadUrl(entry.path)}>
          <DownloadIcon size={18} /> Pobierz
        </a>
      </div>
    );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm md:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={entry.name}
      onClick={onClose}
    >
      <div
        className="safe-top flex size-full flex-col overflow-hidden bg-app shadow-2xl md:h-[90vh] md:max-w-5xl md:rounded-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
          <span className="min-w-0 flex-1 truncate text-sm font-medium" title={entry.name}>
            {entry.name}
            {entry.size !== null && <span className="font-normal text-muted"> · {formatSize(entry.size)}</span>}
          </span>
          <a className="icon-btn" href={downloadUrl(entry.path)} aria-label="Pobierz">
            <DownloadIcon />
          </a>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Zamknij">
            <CloseIcon />
          </button>
        </div>
        <div className="safe-bottom flex min-h-0 flex-1 items-center justify-center bg-side p-2 md:p-4">{body}</div>
      </div>
    </div>
  );
}
