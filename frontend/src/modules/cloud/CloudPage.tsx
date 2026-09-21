// Moduł Cloud: przeglądarka plików chmury osobistej (Nextcloud) – foldery, wgrywanie, wersje, linki, kosz.

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { CloseIcon, CloudIcon, DownloadIcon, EditIcon, EyeIcon, FileIcon, TrashIcon } from "../../components/icons";
import { formatSize } from "../../runState";
import { ApiError } from "../../api";
import type { ModulePageProps } from "../registry";
import { describe } from "../_biuro/http";
import {
  ChatIcon,
  FolderIcon,
  FolderPlusIcon,
  HistoryIcon,
  ImageIcon,
  LinkIcon,
  MoreIcon,
  MoveIcon,
  RestoreIcon,
  SearchIcon,
  StarIcon,
  SyncIcon,
  UploadIcon,
} from "../_biuro/icons";
import { buttonClass, EmptyState, ErrorBanner, Loading, useConfirm, useToast } from "../_biuro/ui";
import {
  breadcrumbs,
  cloudApi,
  downloadUrl,
  joinPath,
  thumbnailUrl,
  uploadToCloud,
  type CloudEntry,
  type TrashEntry,
} from "./api";
import {
  CloudPreview,
  formatDate,
  MoveDialog,
  NameDialog,
  previewKind,
  SendToChatDialog,
  ShareDialog,
  VersionsDialog,
} from "./dialogs";
import { SyncPanel } from "./SyncPanel";

type View = "pliki" | "ulubione" | "kosz" | "synchronizacja";
type SortKey = "name" | "size" | "modified";

interface Upload {
  id: number;
  name: string;
  target: string;
  progress: number;
  status: "uploading" | "done" | "error";
  error?: string;
  controller: AbortController;
}

type Dialog =
  | { kind: "mkdir" }
  | { kind: "rename"; entry: CloudEntry }
  | { kind: "share"; entry: CloudEntry }
  | { kind: "versions"; entry: CloudEntry }
  | { kind: "move"; entries: CloudEntry[] }
  | { kind: "chat"; entries: CloudEntry[] }
  | { kind: "preview"; entry: CloudEntry };

const VIEWS: { id: View; label: string; icon: typeof FolderIcon }[] = [
  { id: "pliki", label: "Pliki", icon: FolderIcon },
  { id: "ulubione", label: "Ulubione", icon: StarIcon },
  { id: "kosz", label: "Kosz", icon: TrashIcon },
  { id: "synchronizacja", label: "Synchronizacja", icon: SyncIcon },
];

let uploadCounter = 0;

export function sortEntries(entries: CloudEntry[], key: SortKey, ascending: boolean): CloudEntry[] {
  const direction = ascending ? 1 : -1;
  return [...entries].sort((a, b) => {
    if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
    let result = 0;
    if (key === "size") result = (a.size ?? 0) - (b.size ?? 0);
    else if (key === "modified") result = new Date(a.modified ?? 0).getTime() - new Date(b.modified ?? 0).getTime();
    if (result === 0) result = a.name.localeCompare(b.name, "pl", { numeric: true, sensitivity: "base" });
    return result * direction;
  });
}

function EntryIcon({ entry }: { entry: CloudEntry }) {
  const [failed, setFailed] = useState(false);
  const thumb = thumbnailUrl(entry, 128);
  if (entry.type === "folder") return <FolderIcon className="text-accent" size={22} />;
  if (thumb && !failed)
    return <img src={thumb} alt="" loading="lazy" className="size-full object-cover" onError={() => setFailed(true)} />;
  if ((entry.mime ?? "").startsWith("image/")) return <ImageIcon className="text-muted" />;
  return <FileIcon className="text-muted" />;
}

export function CloudPage({ openConversation, openModule }: ModulePageProps) {
  const [view, setView] = useState<View>("pliki");
  const [path, setPath] = useState("/");
  const [entries, setEntries] = useState<CloudEntry[] | null>(null);
  const [trash, setTrash] = useState<TrashEntry[] | null>(null);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<CloudEntry[] | null>(null);
  const [error, setError] = useState("");
  /** Konto bez własnej przestrzeni w chmurze (m.in. konto próbne). */
  const [niepodlaczona, setNiepodlaczona] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [menu, setMenu] = useState<string | null>(null);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [dragging, setDragging] = useState(false);
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({ key: "name", ascending: true });
  const [quota, setQuota] = useState<{ used: number | null; available: number | null } | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const [confirm, confirmDialog] = useConfirm();
  const [toast, toastNode] = useToast();

  const load = useCallback(async () => {
    setError("");
    setSelected(new Set());
    try {
      if (view === "pliki") {
        setEntries(null);
        const listing = await cloudApi.list(path);
        setEntries(listing.entries);
      } else if (view === "ulubione") {
        setEntries(null);
        setEntries(await cloudApi.favorites());
      } else if (view === "kosz") {
        setTrash(null);
        setTrash(await cloudApi.trash());
      }
    } catch (failure) {
      // 503 to nie awaria, tylko stan przed podłączeniem przestrzeni — komunikat
      // („brak adresu Nextcloud lub hasła aplikacji”) jest dla administratora, a moduł
      // stawiał go na czerwonym pasku alarmowym nad pustym folderem.
      if (failure instanceof ApiError && failure.status === 503) setNiepodlaczona(true);
      else setError(describe(failure));
      setEntries([]);
      setTrash([]);
    }
  }, [view, path]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    cloudApi
      .quota()
      .then(setQuota)
      .catch(() => setQuota(null));
  }, []);

  // Wyszukiwanie po nazwie w całej chmurze (z opóźnieniem przy pisaniu).
  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) {
      setSearchResults(null);
      return;
    }
    const timer = window.setTimeout(() => {
      cloudApi
        .search(term)
        .then(setSearchResults)
        .catch((failure) => setError(describe(failure)));
    }, 350);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [menu]);

  const navigate = (target: string) => {
    setView("pliki");
    setQuery("");
    setPath(target);
  };

  const shown = useMemo(() => {
    const source = searchResults ?? entries ?? [];
    return searchResults ? source : sortEntries(source, sort.key, sort.ascending);
  }, [entries, searchResults, sort]);
  const selectedEntries = shown.filter((entry) => selected.has(entry.path));

  const toggle = (entry: CloudEntry) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(entry.path)) next.delete(entry.path);
      else next.add(entry.path);
      return next;
    });

  const open = (entry: CloudEntry) => {
    if (entry.type === "folder") navigate(entry.path);
    else if (previewKind(entry)) setDialog({ kind: "preview", entry });
    else window.location.assign(downloadUrl(entry.path));
  };

  // --- wgrywanie ---

  const startUploads = async (files: File[]) => {
    if (!files.length) return;
    const folder = view === "pliki" ? path : "/";
    const existing = new Set((entries ?? []).map((entry) => entry.name.toLowerCase()));
    const duplicates = files.filter((file) => existing.has(file.name.toLowerCase()));
    if (duplicates.length) {
      const ok = await confirm({
        title: "Pliki już istnieją",
        message: (
          <>
            W folderze są już: <strong>{duplicates.map((file) => file.name).join(", ")}</strong>. Zastąpić je? Poprzednia
            zawartość zostanie zachowana w wersjach pliku.
          </>
        ),
        confirmLabel: "Zastąp",
      });
      if (!ok) files = files.filter((file) => !existing.has(file.name.toLowerCase()));
    }
    for (const file of files) {
      const upload: Upload = {
        id: ++uploadCounter,
        name: file.name,
        target: joinPath(folder, file.name),
        progress: 0,
        status: "uploading",
        controller: new AbortController(),
      };
      setUploads((items) => [...items, upload]);
      const update = (changes: Partial<Upload>) =>
        setUploads((items) => items.map((item) => (item.id === upload.id ? { ...item, ...changes } : item)));
      uploadToCloud(file, upload.target, {
        signal: upload.controller.signal,
        onProgress: (progress) => update({ progress }),
      })
        .then(() => {
          update({ status: "done", progress: 1 });
          if (view === "pliki") load();
        })
        .catch((failure) => update({ status: "error", error: describe(failure) }));
    }
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    if (view !== "pliki") return;
    startUploads(Array.from(event.dataTransfer.files).filter((file) => file.size > 0 || file.type));
  };

  // --- działania ---

  const run = async (work: () => Promise<unknown>, message?: string) => {
    setError("");
    try {
      await work();
      if (message) toast(message);
      await load();
    } catch (failure) {
      setError(describe(failure));
    }
  };

  const removeEntries = async (items: CloudEntry[]) => {
    const ok = await confirm({
      title: "Przenieść do kosza?",
      message:
        items.length === 1 ? (
          <>
            <strong>{items[0].name}</strong> trafi do kosza chmury – można go stamtąd przywrócić.
          </>
        ) : (
          <>Wybrane elementy ({items.length}) trafią do kosza chmury – można je stamtąd przywrócić.</>
        ),
      confirmLabel: "Przenieś do kosza",
      danger: true,
    });
    if (ok) await run(() => cloudApi.remove(items.map((item) => item.path)), "Przeniesiono do kosza");
  };

  const actions = (entry: CloudEntry) => [
    ...(entry.type === "file" && previewKind(entry)
      ? [{ label: "Podgląd", icon: EyeIcon, onClick: () => setDialog({ kind: "preview", entry }) }]
      : []),
    ...(entry.type === "file"
      ? [{ label: "Pobierz", icon: DownloadIcon, onClick: () => window.location.assign(downloadUrl(entry.path)) }]
      : []),
    ...(entry.type === "file"
      ? [{ label: "Wyślij do rozmowy", icon: ChatIcon, onClick: () => setDialog({ kind: "chat", entries: [entry] }) }]
      : []),
    { label: "Udostępnij linkiem", icon: LinkIcon, onClick: () => setDialog({ kind: "share", entry }) },
    ...(entry.type === "file"
      ? [{ label: "Wersje", icon: HistoryIcon, onClick: () => setDialog({ kind: "versions", entry }) }]
      : []),
    {
      label: entry.favorite ? "Usuń z ulubionych" : "Dodaj do ulubionych",
      icon: StarIcon,
      onClick: () => run(() => cloudApi.setFavorite(entry.path, !entry.favorite)),
    },
    { label: "Zmień nazwę", icon: EditIcon, onClick: () => setDialog({ kind: "rename", entry }) },
    { label: "Przenieś lub kopiuj", icon: MoveIcon, onClick: () => setDialog({ kind: "move", entries: [entry] }) },
    { label: "Usuń", icon: TrashIcon, danger: true, onClick: () => removeEntries([entry]) },
  ];

  const header = (key: SortKey, label: string, className: string) => (
    <button
      type="button"
      className={`${className} flex items-center gap-1 text-left hover:text-fg`}
      onClick={() => setSort((current) => ({ key, ascending: current.key === key ? !current.ascending : true }))}
    >
      {label}
      {sort.key === key && <span aria-hidden="true">{sort.ascending ? "↑" : "↓"}</span>}
    </button>
  );

  const activeUploads = uploads.filter((upload) => upload.status === "uploading").length;

  if (niepodlaczona)
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center bg-app">
        {/* Tytuł strony dla czytnika ekranu: na telefonie niesie go pasek kompaktowy
            powłoki, a w stanie „niepodłączone” moduł nie rysował na komputerze żadnego
            `h1`. Wzorzec jak w gałęzi z pełnym interfejsem: ukryty poniżej `md`. */}
        <h1 className="sr-only">Chmura</h1>
        <EmptyState icon={<CloudIcon size={26} />} title="Chmura nie jest jeszcze podłączona" szerokosc="max-w-lg" poziom={2}>
          <p>
            Tu stanie Twoja przestrzeń na pliki: wszystko, co Nexus dla Ciebie zrobi, i wszystko, co sam wgrasz —
            z kopią, wersjami i dostępem z telefonu. Na koncie próbnym przestrzeni jeszcze nie ma.
          </p>
          <p className="mt-3">
            Pliki z rozmowy są w module „Pliki”; przestrzeń w chmurze dochodzi razem z własnym kontem.
          </p>
          <button type="button" className={`mt-5 ${buttonClass.primary}`} onClick={() => openModule("pliki")}>
            Otwórz Pliki
          </button>
        </EmptyState>
      </div>
    );

  return (
    <div
      className="flex h-full min-h-0 flex-col bg-app md:flex-row"
      onDragOver={(event) => {
        if (view !== "pliki" || !event.dataTransfer.types.includes("Files")) return;
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(event) => event.currentTarget === event.target && setDragging(false)}
      onDrop={onDrop}
    >
      {/* Tytuł strony na telefonie: widoczny nagłówek modułu jest ukryty poniżej `md`,
          a pasek powłoki niesie tylko etykietę. */}
      <h1 className="sr-only md:hidden">Chmura</h1>
      {/* Na telefonie pasek zakładek zawija się zamiast przewijać w bok: „Synchronizacja”
        kończyła się za krawędzią ekranu i nic nie mówiło, że jest tam jeszcze jedna
        zakładka. Od `md` wraca kolumna z boku. */}
      <nav className="flex shrink-0 flex-wrap gap-1 border-b border-line px-3 py-2 md:w-56 md:flex-col md:flex-nowrap md:border-r md:border-b-0 md:bg-side md:px-2 md:py-4">
        {/* „Chmura”, nie „Cloud”: w pasku modułów, w menu konta i w treści produktu
          ta przestrzeń nazywa się po polsku. Dwie nazwy na jeden byt każą się zastanawiać,
          czy to na pewno to samo miejsce. */}
        <h1 className="hidden px-3 pb-3 text-lg font-semibold md:block">Chmura</h1>
        {VIEWS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
              view === item.id ? "bg-hover font-medium text-fg" : "text-muted hover:bg-hover hover:text-fg"
            }`}
            onClick={() => {
              setQuery("");
              setView(item.id);
            }}
          >
            <item.icon size={18} /> {item.label}
          </button>
        ))}
        {quota?.used != null && (
          <div className="mt-auto hidden px-3 pt-4 text-xs text-muted md:block">
            Zajęte: {formatSize(quota.used)}
            {quota.available != null && ` · wolne: ${formatSize(quota.available)}`}
          </div>
        )}
      </nav>

      <section className="relative flex min-h-0 min-w-0 flex-1 flex-col">
        {view === "synchronizacja" ? (
          <SyncPanel onOpenCalendar={() => openModule("kalendarz")} />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2.5 md:px-5">
              {view === "pliki" && !searchResults ? (
                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-0.5 text-sm">
                  {breadcrumbs(path).map((crumb, index, all) => (
                    <span key={crumb.path} className="flex min-w-0 items-center gap-0.5">
                      <button
                        type="button"
                        className={`max-w-48 truncate rounded-md px-1.5 py-1 hover:bg-hover ${
                          index === all.length - 1 ? "font-semibold" : "text-muted"
                        }`}
                        onClick={() => navigate(crumb.path)}
                      >
                        {crumb.name}
                      </button>
                      {index < all.length - 1 && <span className="text-muted">/</span>}
                    </span>
                  ))}
                </div>
              ) : (
                <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">
                  {searchResults ? `Wyniki wyszukiwania „${query.trim()}”` : VIEWS.find((item) => item.id === view)?.label}
                </h2>
              )}
              {view !== "kosz" && (
                <label className="flex w-full items-center gap-2 rounded-xl border border-line bg-raised px-3 py-1.5 sm:w-56">
                  <SearchIcon size={16} className="shrink-0 text-muted" />
                  <input
                    className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted"
                    placeholder="Szukaj w chmurze"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    aria-label="Szukaj w chmurze"
                  />
                  {query && (
                    <button type="button" onClick={() => setQuery("")} aria-label="Wyczyść wyszukiwanie">
                      <CloseIcon size={14} />
                    </button>
                  )}
                </label>
              )}
              {view === "pliki" && (
                <div className="flex gap-2">
                  <button type="button" className={buttonClass.secondary} onClick={() => setDialog({ kind: "mkdir" })}>
                    <FolderPlusIcon size={18} /> <span className="hidden sm:inline">Nowy folder</span>
                  </button>
                  <button type="button" className={buttonClass.primary} onClick={() => picker.current?.click()}>
                    <UploadIcon size={18} /> Wgraj
                  </button>
                  <input
                    ref={picker}
                    type="file"
                    multiple
                    hidden
                    aria-label="Wgraj pliki"
                    onChange={(event) => {
                      startUploads(Array.from(event.target.files ?? []));
                      event.target.value = "";
                    }}
                  />
                </div>
              )}
            </div>

            {selectedEntries.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 border-b border-line bg-accent-soft/40 px-3 py-1.5 text-sm md:px-5">
                <span className="mr-2 font-medium">Zaznaczono: {selectedEntries.length}</span>
                <button type="button" className={buttonClass.ghost} onClick={() => setDialog({ kind: "chat", entries: selectedEntries })}>
                  <ChatIcon size={16} /> Do rozmowy
                </button>
                <button type="button" className={buttonClass.ghost} onClick={() => setDialog({ kind: "move", entries: selectedEntries })}>
                  <MoveIcon size={16} /> Przenieś
                </button>
                <button type="button" className={buttonClass.ghost} onClick={() => removeEntries(selectedEntries)}>
                  <TrashIcon size={16} /> Usuń
                </button>
                <button type="button" className={`${buttonClass.ghost} ml-auto`} onClick={() => setSelected(new Set())}>
                  Odznacz
                </button>
              </div>
            )}

            <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-24 md:px-4">
              <div className="pt-3">
                <ErrorBanner message={error} onClose={() => setError("")} />
              </div>
              {view === "kosz" ? (
                <TrashList items={trash} onRestore={(item) => run(() => cloudApi.restoreTrash(item.id), `Przywrócono ${item.name}`)} />
              ) : entries === null && !searchResults ? (
                <Loading />
              ) : shown.length === 0 ? (
                searchResults ? (
                  <EmptyState icon={<SearchIcon size={26} />} title="Nic nie znaleziono">
                    Wyszukiwanie obejmuje nazwy plików i folderów w całej chmurze.
                  </EmptyState>
                ) : view === "ulubione" ? (
                  <EmptyState icon={<StarIcon size={26} />} title="Brak ulubionych">
                    Oznacz gwiazdką pliki i foldery, do których często wracasz.
                  </EmptyState>
                ) : (
                  <EmptyState icon={<UploadIcon size={26} />} title="Pusty folder">
                    Przeciągnij tu pliki albo użyj przycisku „Wgraj”. Duże pliki przesyłane są kawałkami, więc można wgrywać
                    nawet wielogigabajtowe nagrania.
                  </EmptyState>
                )
              ) : (
                <div role="table" aria-label="Pliki w chmurze" className="text-sm">
                  <div role="row" className="hidden grid-cols-[2rem_2.75rem_1fr_6rem_10rem_2.5rem] items-center gap-2 px-2 py-2 text-xs text-muted md:grid">
                    <input
                      type="checkbox"
                      aria-label="Zaznacz wszystkie"
                      checked={selectedEntries.length === shown.length && shown.length > 0}
                      onChange={(event) => setSelected(event.target.checked ? new Set(shown.map((entry) => entry.path)) : new Set())}
                    />
                    <span />
                    {header("name", "Nazwa", "")}
                    {header("size", "Rozmiar", "justify-end")}
                    {header("modified", "Zmieniono", "")}
                    <span />
                  </div>
                  {shown.map((entry) => (
                    <div
                      role="row"
                      key={entry.path}
                      className={`group relative grid grid-cols-[2rem_2.75rem_1fr_2.5rem] items-center gap-2 rounded-xl px-2 py-1.5 transition-colors md:grid-cols-[2rem_2.75rem_1fr_6rem_10rem_2.5rem] ${
                        selected.has(entry.path) ? "bg-accent-soft/50" : "hover:bg-raised"
                      }`}
                    >
                      <input type="checkbox" aria-label={`Zaznacz ${entry.name}`} checked={selected.has(entry.path)} onChange={() => toggle(entry)} />
                      <button
                        type="button"
                        className="grid size-10 place-items-center overflow-hidden rounded-lg bg-raised"
                        onClick={() => open(entry)}
                        tabIndex={-1}
                        aria-hidden="true"
                      >
                        <EntryIcon entry={entry} />
                      </button>
                      <button type="button" className="min-w-0 text-left" onClick={() => open(entry)}>
                        <span className="flex items-center gap-1.5">
                          <span className="truncate font-medium">{entry.name}</span>
                          {entry.favorite && <StarIcon filled size={14} className="shrink-0 text-accent" />}
                          {entry.shared_link && <LinkIcon size={14} className="shrink-0 text-accent" />}
                        </span>
                        <span className="block truncate text-xs text-muted md:hidden">
                          {entry.type === "file" && entry.size !== null ? `${formatSize(entry.size)} · ` : ""}
                          {formatDate(entry.modified)}
                        </span>
                        {searchResults && <span className="block truncate text-xs text-muted">{entry.path}</span>}
                      </button>
                      <span className="hidden text-right text-muted tabular-nums md:block">
                        {entry.size !== null ? formatSize(entry.size) : "—"}
                      </span>
                      <span className="hidden text-muted md:block">{formatDate(entry.modified)}</span>
                      <div className="relative">
                        <button
                          type="button"
                          className="icon-btn"
                          aria-label={`Działania: ${entry.name}`}
                          aria-haspopup="menu"
                          aria-expanded={menu === entry.path}
                          onClick={(event) => {
                            event.stopPropagation();
                            setMenu(menu === entry.path ? null : entry.path);
                          }}
                        >
                          <MoreIcon />
                        </button>
                        {menu === entry.path && (
                          <div
                            role="menu"
                            className="absolute top-full right-0 z-30 mt-1 w-56 animate-rise overflow-hidden rounded-xl border border-line bg-raised py-1 shadow-xl"
                          >
                            {actions(entry).map((action) => (
                              <button
                                key={action.label}
                                type="button"
                                role="menuitem"
                                className={`flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm hover:bg-hover ${
                                  "danger" in action && action.danger ? "text-danger" : ""
                                }`}
                                onClick={() => {
                                  setMenu(null);
                                  action.onClick();
                                }}
                              >
                                <action.icon size={17} /> {action.label}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {uploads.length > 0 && (
          <div className="safe-bottom absolute right-3 bottom-3 left-3 z-20 max-h-72 overflow-hidden rounded-2xl border border-line bg-raised shadow-2xl sm:left-auto sm:w-96">
            <div className="flex items-center gap-2 border-b border-line px-3 py-2 text-sm font-medium">
              <UploadIcon size={16} />
              <span className="flex-1">{activeUploads ? `Wgrywanie (${activeUploads})` : "Wgrywanie zakończone"}</span>
              {!activeUploads && (
                <button type="button" className="icon-btn size-7" aria-label="Zamknij" onClick={() => setUploads([])}>
                  <CloseIcon size={16} />
                </button>
              )}
            </div>
            <ul className="max-h-56 divide-y divide-line overflow-y-auto">
              {uploads.map((upload) => (
                <li key={upload.id} className="px-3 py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate">{upload.name}</span>
                    {upload.status === "uploading" ? (
                      <>
                        <span className="text-xs text-muted tabular-nums">{Math.round(upload.progress * 100)}%</span>
                        <button
                          type="button"
                          className="text-xs text-muted hover:text-danger"
                          onClick={() => upload.controller.abort()}
                        >
                          Anuluj
                        </button>
                      </>
                    ) : upload.status === "done" ? (
                      <span className="text-xs text-success">Gotowe</span>
                    ) : (
                      <span className="text-xs text-danger" title={upload.error}>
                        Błąd
                      </span>
                    )}
                  </div>
                  {upload.status === "uploading" && (
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-line">
                      <div className="h-full rounded-full bg-accent-fill transition-[width]" style={{ width: `${upload.progress * 100}%` }} />
                    </div>
                  )}
                  {upload.status === "error" && <p className="mt-1 text-xs text-danger">{upload.error}</p>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {dragging && (
          <div className="pointer-events-none absolute inset-3 z-20 flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-accent bg-accent-soft/90 text-lg font-medium text-accent">
            <UploadIcon size={32} />
            Upuść pliki, aby wgrać je do {path === "/" ? "chmury" : path}
          </div>
        )}
      </section>

      {dialog?.kind === "mkdir" && (
        <NameDialog
          title="Nowy folder"
          initial=""
          confirmLabel="Utwórz"
          onClose={() => setDialog(null)}
          onSubmit={async (name) => {
            await cloudApi.mkdir(joinPath(path, name));
            await load();
          }}
        />
      )}
      {dialog?.kind === "rename" && (
        <NameDialog
          title="Zmień nazwę"
          initial={dialog.entry.name}
          confirmLabel="Zmień"
          onClose={() => setDialog(null)}
          onSubmit={async (name) => {
            await cloudApi.rename(dialog.entry.path, name);
            await load();
          }}
        />
      )}
      {dialog?.kind === "share" && <ShareDialog entry={dialog.entry} onClose={() => setDialog(null)} onChanged={load} />}
      {dialog?.kind === "versions" && (
        <VersionsDialog
          entry={dialog.entry}
          onClose={() => setDialog(null)}
          onRestored={() => {
            toast("Przywrócono wersję");
            load();
          }}
        />
      )}
      {dialog?.kind === "move" && (
        <MoveDialog
          entries={dialog.entries}
          start={view === "pliki" ? path : "/"}
          onClose={() => setDialog(null)}
          onDone={(message) => {
            toast(message);
            load();
          }}
        />
      )}
      {dialog?.kind === "chat" && (
        <SendToChatDialog entries={dialog.entries} onClose={() => setDialog(null)} onSent={(id) => openConversation(id)} />
      )}
      {dialog?.kind === "preview" && <CloudPreview entry={dialog.entry} onClose={() => setDialog(null)} />}
      {confirmDialog}
      {toastNode}
    </div>
  );
}

function TrashList({ items, onRestore }: { items: TrashEntry[] | null; onRestore: (item: TrashEntry) => void }) {
  if (items === null) return <Loading />;
  if (items.length === 0)
    return (
      <EmptyState icon={<TrashIcon size={26} />} title="Kosz jest pusty">
        Usunięte pliki trafiają tutaj i można je przywrócić. Chmura automatycznie opróżnia stare elementy kosza.
      </EmptyState>
    );
  return (
    <ul className="divide-y divide-line text-sm">
      {items.map((item) => (
        <li key={item.id} className="flex items-center gap-3 px-2 py-2.5">
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-raised text-muted">
            {item.type === "folder" ? <FolderIcon size={22} /> : <FileIcon />}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium">{item.name}</span>
            <span className="block truncate text-xs text-muted">
              z {item.original} · usunięto {formatDate(item.deleted)}
              {item.size !== null ? ` · ${formatSize(item.size)}` : ""}
            </span>
          </span>
          <button type="button" className={buttonClass.secondary} onClick={() => onRestore(item)}>
            <RestoreIcon size={16} /> Przywróć
          </button>
        </li>
      ))}
    </ul>
  );
}
