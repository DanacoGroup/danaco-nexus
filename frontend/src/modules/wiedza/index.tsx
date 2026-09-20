// Moduł Baza wiedzy (wzorzec: Wisebase): kolekcje stron, plików, prac i notatek,
// wyszukiwanie po znaczeniu i rozmowa z wybranymi dokumentami.

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { uploadFile } from "../../api";
import { CloseIcon, EditIcon, FileIcon, PlusIcon, RefreshIcon, TrashIcon } from "../../components/icons";
import { Markdown } from "../../components/Markdown";
import type { ModulePageProps, NexusModule } from "../registry";
import { errorText, researchApi, shortDate, type Collection, type Note, type SearchHit, type Source } from "../research/api";
import { hostname } from "../research/citations";
import {
  ChatIcon,
  ExternalIcon,
  GlobeIcon,
  LibraryIcon,
  LinkIcon,
  NoteIcon,
  ScholarIcon,
  SearchIcon,
  UploadIcon,
} from "../research/icons";

type Tab = "zrodla" | "notatki";
type Opened = { type: "source"; id: string } | { type: "note"; id: string | null } | null;

const KIND_ICONS = { strona: GlobeIcon, plik: FileIcon, praca: ScholarIcon, tekst: NoteIcon } as const;
const KIND_LABELS = { strona: "Strona", plik: "Plik", praca: "Praca naukowa", tekst: "Tekst" } as const;
const BUTTON =
  "inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm transition-colors hover:bg-raised disabled:opacity-50";
const PRIMARY =
  "inline-flex items-center gap-1.5 rounded-lg bg-accent-fill px-3 py-1.5 text-sm font-medium text-on-accent transition-colors hover:bg-accent-fill-hover disabled:opacity-50";

function IndexBadge({ item }: { item: { indexed: boolean; index_error?: string } }) {
  if (item.index_error) return <span className="text-xs text-danger">Błąd indeksu</span>;
  if (!item.indexed) return <span className="shimmer-text text-xs">Indeksowanie…</span>;
  return null;
}

function SourceDetail({
  id,
  collections,
  onClose,
  onChanged,
}: {
  id: string;
  collections: Collection[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const [source, setSource] = useState<Source | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setSource(null);
    researchApi
      .source(id)
      .then(setSource)
      .catch((failure) => setError(errorText(failure)));
  }, [id]);

  const remove = () => {
    if (!source || !window.confirm(`Usunąć źródło „${source.title}”?`)) return;
    researchApi
      .deleteSource(source.id)
      .then(() => {
        onChanged();
        onClose();
      })
      .catch((failure) => setError(errorText(failure)));
  };
  const move = (collectionId: string) => {
    if (!source) return;
    researchApi
      .updateSource(source.id, { collection_id: collectionId })
      .then(() => {
        onChanged();
        onClose();
      })
      .catch((failure) => setError(errorText(failure)));
  };
  const rename = () => {
    if (!source) return;
    const title = window.prompt("Tytuł źródła", source.title)?.trim();
    if (!title || title === source.title) return;
    researchApi
      .updateSource(source.id, { title })
      .then((updated) => {
        setSource({ ...source, title: updated.title });
        onChanged();
      })
      .catch((failure) => setError(errorText(failure)));
  };
  const reindex = () => {
    if (!source) return;
    researchApi
      .reindexSource(source.id)
      .then(() => setTimeout(onChanged, 2500))
      .catch((failure) => setError(errorText(failure)));
  };

  const meta = source?.meta ?? {};
  const facts = [meta.site_name, meta.author, Array.isArray(meta.authors) ? meta.authors.join(", ") : "", meta.year, meta.published]
    .filter((value) => typeof value === "string" || typeof value === "number")
    .map(String)
    .filter(Boolean);
  return (
    <DetailFrame title={source ? KIND_LABELS[source.kind] : "Źródło"} onClose={onClose}>
      {!source && !error && <span className="spinner mt-6 size-5 text-muted" />}
      {error && <Alert text={error} />}
      {source && (
        <>
          <h3 className="text-[17px] leading-snug font-semibold break-words">{source.title}</h3>
          {facts.length > 0 && <p className="mt-1 text-xs text-muted">{facts.join(" · ")}</p>}
          {source.url && (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex max-w-full items-center gap-1.5 text-sm break-all text-accent hover:underline"
            >
              <ExternalIcon size={14} className="shrink-0" /> {hostname(source.url)}
            </a>
          )}
          {typeof meta.citation === "string" && meta.citation && (
            <p className="mt-2 rounded-lg bg-raised px-3 py-2 text-sm">{meta.citation}</p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button type="button" className={BUTTON} onClick={rename}>
              <EditIcon size={14} /> Tytuł
            </button>
            {source.index_error && (
              <button type="button" className={BUTTON} onClick={reindex}>
                <RefreshIcon size={14} /> Indeksuj ponownie
              </button>
            )}
            {collections.length > 1 && (
              <select
                value=""
                onChange={(event) => event.target.value && move(event.target.value)}
                className="rounded-lg border border-line bg-app px-2 py-1.5 text-sm"
                aria-label="Przenieś do kolekcji"
              >
                <option value="">Przenieś do…</option>
                {collections
                  .filter((item) => item.id !== source.collection_id)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
              </select>
            )}
            <button type="button" className={`${BUTTON} ml-auto text-danger`} onClick={remove} aria-label="Usuń źródło">
              <TrashIcon size={14} />
            </button>
          </div>
          {source.index_error && <p className="mt-2 text-xs text-danger">{source.index_error}</p>}
          <div className="mt-4 border-t border-line pt-4 text-sm leading-6 break-words whitespace-pre-wrap">
            {source.content || "Brak treści."}
          </div>
        </>
      )}
    </DetailFrame>
  );
}

function NoteEditor({
  note,
  collectionId,
  onClose,
  onChanged,
}: {
  note: Note | null;
  collectionId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(note === null);
  const [title, setTitle] = useState(note?.title ?? "");
  const [content, setContent] = useState(note?.content ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const save = (event: FormEvent) => {
    event.preventDefault();
    if (!content.trim()) return;
    setBusy(true);
    const request = note
      ? researchApi.updateNote(note.id, { title, content })
      : researchApi.addNote(collectionId, { title, content });
    request
      .then(() => {
        onChanged();
        if (note) setEditing(false);
        else onClose();
      })
      .catch((failure) => setError(errorText(failure)))
      .finally(() => setBusy(false));
  };
  const remove = () => {
    if (!note || !window.confirm(`Usunąć notatkę „${note.title}”?`)) return;
    researchApi
      .deleteNote(note.id)
      .then(() => {
        onChanged();
        onClose();
      })
      .catch((failure) => setError(errorText(failure)));
  };

  return (
    <DetailFrame title={note ? "Notatka" : "Nowa notatka"} onClose={onClose}>
      {error && <Alert text={error} />}
      {editing ? (
        <form onSubmit={save} className="flex h-full flex-col gap-3">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Tytuł (opcjonalnie)"
            maxLength={300}
            className="rounded-lg border border-line bg-app px-3 py-2 text-sm"
          />
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Treść notatki (Markdown)…"
            rows={14}
            autoFocus
            className="min-h-60 flex-1 resize-y rounded-lg border border-line bg-app px-3 py-2 font-mono text-[13px] leading-6"
          />
          <div className="flex gap-2">
            <button type="submit" className={PRIMARY} disabled={busy || !content.trim()}>
              {busy && <span className="spinner size-3.5" />} Zapisz
            </button>
            {note && (
              <button type="button" className={BUTTON} onClick={() => setEditing(false)}>
                Anuluj
              </button>
            )}
          </div>
        </form>
      ) : (
        note && (
          <>
            <h3 className="text-[17px] font-semibold">{note.title}</h3>
            <p className="mt-1 text-xs text-muted">Zmieniono {shortDate(note.updated_at)}</p>
            <div className="mt-3 flex gap-2">
              <button type="button" className={BUTTON} onClick={() => setEditing(true)}>
                <EditIcon size={14} /> Edytuj
              </button>
              <button type="button" className={`${BUTTON} ml-auto text-danger`} onClick={remove} aria-label="Usuń notatkę">
                <TrashIcon size={14} />
              </button>
            </div>
            <div className="mt-4 border-t border-line pt-4">
              <Markdown text={note.content} />
            </div>
          </>
        )
      )}
    </DetailFrame>
  );
}

function DetailFrame({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <aside className="fixed inset-0 z-30 flex flex-col bg-app lg:static lg:z-auto lg:w-[440px] lg:shrink-0 lg:border-l lg:border-line">
      <header className="safe-top flex items-center gap-2 border-b border-line px-4 py-2.5">
        <span className="flex-1 text-sm font-medium text-muted">{title}</span>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Zamknij">
          <CloseIcon size={18} />
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>
    </aside>
  );
}

function Alert({ text }: { text: string }) {
  return (
    <div role="alert" className="mb-3 rounded-xl border border-danger/40 bg-danger-soft px-3.5 py-2 text-sm text-danger">
      {text}
    </div>
  );
}

function KnowledgePage({ openConversation }: ModulePageProps) {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [tab, setTab] = useState<Tab>("zrodla");
  const [opened, setOpened] = useState<Opened>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [url, setUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [uploads, setUploads] = useState<{ name: string; progress: number }[]>([]);
  const [newCollection, setNewCollection] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [question, setQuestion] = useState("");
  const [listOpen, setListOpen] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const current = collections.find((item) => item.id === currentId) ?? null;

  const loadCollections = useCallback(
    () =>
      researchApi
        .collections()
        .then((list) => {
          setCollections(list);
          setCurrentId((id) => (id && list.some((item) => item.id === id) ? id : (list[0]?.id ?? null)));
        })
        .catch((failure) => setError(errorText(failure))),
    [],
  );

  const loadItems = useCallback(() => {
    if (!currentId) {
      setSources([]);
      setNotes([]);
      return;
    }
    researchApi
      .sources(currentId)
      .then(setSources)
      .catch((failure) => setError(errorText(failure)));
    researchApi
      .notes(currentId)
      .then(setNotes)
      .catch((failure) => setError(errorText(failure)));
  }, [currentId]);

  const refresh = useCallback(() => {
    loadCollections();
    loadItems();
  }, [loadCollections, loadItems]);

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

  useEffect(() => {
    setSelected(new Set());
    setOpened(null);
    setHits(null);
    setQuery("");
    loadItems();
  }, [loadItems]);

  // Indeksowanie trwa w tle – lista odświeża się, dopóki są wpisy w trakcie.
  const pending = sources.some((item) => !item.indexed && !item.index_error) || notes.some((item) => !item.indexed);
  useEffect(() => {
    if (!pending) return;
    const timer = window.setTimeout(loadItems, 2500);
    return () => window.clearTimeout(timer);
  }, [pending, sources, notes, loadItems]);

  const createCollection = (event: FormEvent) => {
    event.preventDefault();
    const name = newCollection?.trim();
    if (!name) return;
    researchApi
      .createCollection(name)
      .then((created) => {
        setNewCollection(null);
        setCurrentId(created.id);
        loadCollections();
      })
      .catch((failure) => setError(errorText(failure)));
  };

  const renameCollection = () => {
    if (!current) return;
    const name = window.prompt("Nazwa kolekcji", current.name)?.trim();
    if (!name || name === current.name) return;
    researchApi
      .updateCollection(current.id, { name })
      .then(loadCollections)
      .catch((failure) => setError(errorText(failure)));
  };

  const deleteCollection = () => {
    if (!current) return;
    const count = current.sources + current.notes;
    const warning = count ? ` Zostanie usuniętych ${count} źródeł i notatek.` : "";
    if (!window.confirm(`Usunąć kolekcję „${current.name}”?${warning}`)) return;
    researchApi
      .deleteCollection(current.id)
      .then(() => {
        setCurrentId(null);
        loadCollections();
      })
      .catch((failure) => setError(errorText(failure)));
  };

  const addUrl = (event: FormEvent) => {
    event.preventDefault();
    const address = url.trim();
    if (!currentId || !address) return;
    setAdding(true);
    setError("");
    researchApi
      .addSource(currentId, { url: /^https?:\/\//i.test(address) ? address : `https://${address}` })
      .then(() => {
        setUrl("");
        setTab("zrodla");
        refresh();
      })
      .catch((failure) => setError(errorText(failure)))
      .finally(() => setAdding(false));
  };

  const addFiles = async (files: FileList | null) => {
    if (!currentId || !files?.length) return;
    const list = Array.from(files);
    setUploads(list.map((file) => ({ name: file.name, progress: 0 })));
    setTab("zrodla");
    for (const [index, file] of list.entries()) {
      try {
        const stored = await uploadFile(file, null, (fraction) =>
          setUploads((items) => items.map((item, position) => (position === index ? { ...item, progress: fraction } : item))),
        ).promise;
        await researchApi.addSource(currentId, { file_id: stored.id });
      } catch (failure) {
        setError(`${file.name}: ${errorText(failure)}`);
      }
      setUploads((items) => items.map((item, position) => (position === index ? { ...item, progress: 1 } : item)));
      loadItems();
    }
    setUploads([]);
    loadCollections();
    if (fileInput.current) fileInput.current.value = "";
  };

  const search = (event: FormEvent) => {
    event.preventDefault();
    if (query.trim().length < 2) {
      setHits(null);
      return;
    }
    setSearching(true);
    researchApi
      .search(query.trim(), currentId ?? undefined)
      .then((result) => setHits(result.results))
      .catch((failure) => setError(errorText(failure)))
      .finally(() => setSearching(false));
  };

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const startChat = (whole: boolean) => {
    const sourceIds = sources.filter((item) => selected.has(item.id)).map((item) => item.id);
    const noteIds = notes.filter((item) => selected.has(item.id)).map((item) => item.id);
    researchApi
      .chat(
        whole
          ? { collection_id: currentId, question: question.trim() }
          : { source_ids: sourceIds, note_ids: noteIds, collection_id: currentId, question: question.trim() },
      )
      .then((result) => openConversation(result.conversation_id))
      .catch((failure) => setError(errorText(failure)));
  };

  const openedNote = useMemo(
    () => (opened?.type === "note" && opened.id ? (notes.find((item) => item.id === opened.id) ?? null) : null),
    [opened, notes],
  );

  const collectionList = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 px-3 pt-3 pb-2">
        <button
          type="button"
          onClick={() => setNewCollection("")}
          className="inline-flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-hover"
        >
          <PlusIcon size={18} /> Nowa kolekcja
        </button>
        <button type="button" className="icon-btn md:hidden" onClick={() => setListOpen(false)} aria-label="Zamknij">
          <CloseIcon size={18} />
        </button>
      </div>
      {newCollection !== null && (
        <form onSubmit={createCollection} className="px-3 pb-2">
          <input
            autoFocus
            value={newCollection}
            onChange={(event) => setNewCollection(event.target.value)}
            onBlur={() => !newCollection.trim() && setNewCollection(null)}
            onKeyDown={(event) => event.key === "Escape" && setNewCollection(null)}
            placeholder="Nazwa kolekcji"
            maxLength={120}
            className="w-full rounded-lg border border-accent bg-app px-3 py-2 text-sm outline-none"
          />
        </form>
      )}
      <div className="px-5 pt-2 pb-1 text-xs font-medium text-muted">Kolekcje</div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {collections.length === 0 && newCollection === null && (
          <p className="px-3 py-2 text-sm text-muted">Utwórz pierwszą kolekcję, np. „Klienci” albo „Pompy ciepła”.</p>
        )}
        {collections.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              setCurrentId(item.id);
              setListOpen(false);
            }}
            className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-hover ${
              item.id === currentId ? "bg-hover" : ""
            }`}
          >
            <LibraryIcon size={17} className="shrink-0 text-muted" />
            <span className="min-w-0 flex-1 truncate text-sm">{item.name}</span>
            <span className="text-xs text-muted tabular-nums">{item.sources + item.notes}</span>
          </button>
        ))}
      </div>
    </div>
  );

  const selectedCount = selected.size;
  return (
    <div className="flex h-full min-h-0 bg-app">
      <aside className="hidden w-64 shrink-0 border-r border-line bg-side md:block">{collectionList}</aside>
      {listOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button type="button" className="absolute inset-0 bg-black/40" onClick={() => setListOpen(false)} aria-label="Zamknij" />
          <div className="safe-top absolute inset-y-0 left-0 w-[85%] max-w-xs bg-side shadow-xl">{collectionList}</div>
        </div>
      )}
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-line/60 px-3 py-2 md:hidden">
          <button type="button" className="icon-btn" onClick={() => setListOpen(true)} aria-label="Kolekcje">
            <LibraryIcon size={19} />
          </button>
          <span className="min-w-0 truncate text-sm font-medium">{current?.name ?? "Baza wiedzy"}</span>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 pt-5 pb-28 md:px-8">
            {error && (
              <div onClick={() => setError("")}>
                <Alert text={error} />
              </div>
            )}
            {!current ? (
              <div className="flex flex-col items-center py-16 text-center">
                <span className="grid size-12 place-items-center rounded-2xl bg-accent-soft text-accent">
                  <LibraryIcon size={26} />
                </span>
                <h2 className="mt-4 text-2xl font-semibold tracking-tight">Baza wiedzy</h2>
                <p className="mt-2 max-w-md text-muted">
                  Zbieraj strony, pliki, prace naukowe i notatki w kolekcjach. Nexus przeszukuje je po znaczeniu i odpowiada
                  na pytania na ich podstawie.
                </p>
                <button type="button" className={`${PRIMARY} mt-6`} onClick={() => setNewCollection("")}>
                  <PlusIcon size={16} /> Nowa kolekcja
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate text-xl font-semibold tracking-tight md:text-2xl">{current.name}</h2>
                    <p className="text-sm text-muted">
                      {current.sources} źródeł · {current.notes} notatek
                      {current.description ? ` · ${current.description}` : ""}
                    </p>
                  </div>
                  <button type="button" className="icon-btn" onClick={renameCollection} aria-label="Zmień nazwę kolekcji">
                    <EditIcon size={17} />
                  </button>
                  <button type="button" className="icon-btn" onClick={deleteCollection} aria-label="Usuń kolekcję">
                    <TrashIcon size={17} />
                  </button>
                </div>

                <form onSubmit={addUrl} className="mt-5 flex gap-2">
                  <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-line bg-raised/40 px-3 focus-within:border-line-strong">
                    <LinkIcon size={16} className="shrink-0 text-muted" />
                    <input
                      value={url}
                      onChange={(event) => setUrl(event.target.value)}
                      placeholder="Wklej adres strony lub PDF…"
                      inputMode="url"
                      className="min-w-0 flex-1 bg-transparent py-2 text-sm outline-none placeholder:text-muted"
                      aria-label="Adres strony"
                    />
                  </label>
                  <button type="submit" className={PRIMARY} disabled={adding || !url.trim()}>
                    {adding ? <span className="spinner size-3.5" /> : <PlusIcon size={15} />} Dodaj
                  </button>
                </form>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button type="button" className={BUTTON} onClick={() => fileInput.current?.click()}>
                    <UploadIcon size={15} /> Plik
                  </button>
                  <input
                    ref={fileInput}
                    type="file"
                    multiple
                    hidden
                    accept=".pdf,.txt,.md,.csv,.json,.html,.htm,.docx,.doc,.odt,.rtf,.pptx,.xlsx,.epub"
                    onChange={(event) => addFiles(event.target.files)}
                  />
                  <button
                    type="button"
                    className={BUTTON}
                    onClick={() => {
                      setTab("notatki");
                      setOpened({ type: "note", id: null });
                    }}
                  >
                    <NoteIcon size={15} /> Notatka
                  </button>
                  <button
                    type="button"
                    className={`${BUTTON} ml-auto`}
                    onClick={() => startChat(true)}
                    disabled={current.sources + current.notes === 0}
                  >
                    <ChatIcon size={15} /> Rozmawiaj z kolekcją
                  </button>
                </div>
                {uploads.length > 0 && (
                  <ul className="mt-3 space-y-1.5">
                    {uploads.map((item) => (
                      <li key={item.name} className="flex items-center gap-2 text-sm">
                        <span className="spinner size-3.5 text-accent" />
                        <span className="min-w-0 flex-1 truncate">{item.name}</span>
                        <span className="text-xs text-muted tabular-nums">{Math.round(item.progress * 100)}%</span>
                      </li>
                    ))}
                  </ul>
                )}

                <form onSubmit={search} className="mt-5">
                  <label className="flex items-center gap-2 rounded-xl border border-line px-3 focus-within:border-line-strong">
                    <SearchIcon size={16} className="shrink-0 text-muted" />
                    <input
                      value={query}
                      onChange={(event) => {
                        setQuery(event.target.value);
                        if (!event.target.value) setHits(null);
                      }}
                      placeholder="Szukaj w kolekcji po znaczeniu…"
                      className="min-w-0 flex-1 bg-transparent py-2 text-sm outline-none placeholder:text-muted"
                      aria-label="Szukaj w kolekcji"
                    />
                    {searching && <span className="spinner size-3.5 text-muted" />}
                  </label>
                </form>

                {hits !== null ? (
                  <div className="mt-4 space-y-2">
                    <div className="flex items-center text-xs text-muted">
                      Wyniki: {hits.length}
                      <button type="button" className="ml-auto hover:text-fg" onClick={() => setHits(null)}>
                        Wyczyść
                      </button>
                    </div>
                    {hits.map((hit, index) => (
                      <button
                        key={`${hit.id}-${index}`}
                        type="button"
                        onClick={() => setOpened({ type: hit.type, id: hit.id })}
                        className="block w-full rounded-xl border border-line px-3.5 py-2.5 text-left transition-colors hover:bg-raised"
                      >
                        <span className="flex items-center gap-2 text-sm font-medium">
                          {hit.type === "note" ? <NoteIcon size={15} className="text-muted" /> : <FileIcon size={15} className="text-muted" />}
                          <span className="min-w-0 flex-1 truncate">{hit.title}</span>
                          <span className="text-xs font-normal text-muted tabular-nums">{Math.round(hit.score * 100)}%</span>
                        </span>
                        <span className="mt-1 line-clamp-3 block text-sm text-muted">{hit.text}</span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <>
                    <div className="mt-5 flex gap-1 border-b border-line" role="tablist">
                      {(
                        [
                          ["zrodla", `Źródła (${sources.length})`],
                          ["notatki", `Notatki (${notes.length})`],
                        ] as const
                      ).map(([id, label]) => (
                        <button
                          key={id}
                          type="button"
                          role="tab"
                          aria-selected={tab === id}
                          onClick={() => setTab(id)}
                          className={`-mb-px border-b-2 px-3 py-2 text-sm transition-colors ${
                            tab === id ? "border-accent font-medium text-fg" : "border-transparent text-muted hover:text-fg"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <ul className="mt-2 divide-y divide-line/60">
                      {tab === "zrodla" &&
                        sources.map((item) => {
                          const KindIcon = KIND_ICONS[item.kind] ?? FileIcon;
                          return (
                            <li key={item.id} className="flex items-start gap-3 py-2.5">
                              <input
                                type="checkbox"
                                checked={selected.has(item.id)}
                                onChange={() => toggle(item.id)}
                                className="mt-1 size-4 shrink-0 accent-[var(--accent)]"
                                aria-label={`Wybierz: ${item.title}`}
                              />
                              <button
                                type="button"
                                onClick={() => setOpened({ type: "source", id: item.id })}
                                className="min-w-0 flex-1 text-left"
                              >
                                <span className="flex items-center gap-2">
                                  <KindIcon size={15} className="shrink-0 text-muted" />
                                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{item.title}</span>
                                  <IndexBadge item={item} />
                                </span>
                                <span className="mt-0.5 line-clamp-2 block text-sm text-muted">{item.excerpt}</span>
                                <span className="mt-0.5 block text-xs text-muted">
                                  {item.url ? `${hostname(item.url)} · ` : ""}
                                  {shortDate(item.created_at)}
                                </span>
                              </button>
                            </li>
                          );
                        })}
                      {tab === "notatki" &&
                        notes.map((item) => (
                          <li key={item.id} className="flex items-start gap-3 py-2.5">
                            <input
                              type="checkbox"
                              checked={selected.has(item.id)}
                              onChange={() => toggle(item.id)}
                              className="mt-1 size-4 shrink-0 accent-[var(--accent)]"
                              aria-label={`Wybierz: ${item.title}`}
                            />
                            <button
                              type="button"
                              onClick={() => setOpened({ type: "note", id: item.id })}
                              className="min-w-0 flex-1 text-left"
                            >
                              <span className="flex items-center gap-2">
                                <NoteIcon size={15} className="shrink-0 text-muted" />
                                <span className="min-w-0 flex-1 truncate text-sm font-medium">{item.title}</span>
                                <IndexBadge item={item} />
                              </span>
                              <span className="mt-0.5 line-clamp-2 block text-sm text-muted">{item.content}</span>
                            </button>
                          </li>
                        ))}
                    </ul>
                    {tab === "zrodla" && sources.length === 0 && (
                      <p className="py-8 text-center text-sm text-muted">
                        Dodaj stronę, plik lub zapisz źródła z badania w module Badania.
                      </p>
                    )}
                    {tab === "notatki" && notes.length === 0 && (
                      <p className="py-8 text-center text-sm text-muted">Brak notatek w tej kolekcji.</p>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </div>
        {selectedCount > 0 && (
          <div className="safe-bottom border-t border-line bg-app/95 px-3 pt-2 backdrop-blur">
            <div className="mx-auto flex w-full max-w-3xl items-center gap-2 md:px-5">
              <span className="shrink-0 text-sm text-muted tabular-nums">Wybrano: {selectedCount}</span>
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && startChat(false)}
                placeholder="Pytanie do wybranych dokumentów (opcjonalnie)"
                className="min-w-0 flex-1 rounded-lg border border-line bg-app px-3 py-1.5 text-sm"
              />
              <button type="button" className={PRIMARY} onClick={() => startChat(false)}>
                <ChatIcon size={15} /> Rozmawiaj
              </button>
              <button type="button" className="icon-btn" onClick={() => setSelected(new Set())} aria-label="Wyczyść wybór">
                <CloseIcon size={17} />
              </button>
            </div>
          </div>
        )}
      </section>
      {opened?.type === "source" && (
        <SourceDetail
          key={opened.id}
          id={opened.id}
          collections={collections}
          onClose={() => setOpened(null)}
          onChanged={refresh}
        />
      )}
      {opened?.type === "note" && currentId && (opened.id === null || openedNote) && (
        <NoteEditor
          key={opened.id ?? "nowa"}
          note={openedNote}
          collectionId={currentId}
          onClose={() => setOpened(null)}
          onChanged={refresh}
        />
      )}
    </div>
  );
}

export const module: NexusModule = {
  id: "wiedza",
  label: "Wiedza",
  description: "Kolekcje stron, plików, prac i notatek; wyszukiwanie po znaczeniu i rozmowa z dokumentami.",
  icon: LibraryIcon,
  order: 31,
  Page: KnowledgePage,
};
