// Moduł Kod: przestrzenie projektów, drzewo plików z podglądem, zmiany i historia git,
// sesja programistyczna z Claude Code (rozmowa w trybie „code”).

import { useCallback, useEffect, useMemo, useState, type FormEvent, type SVGProps } from "react";
import { ChevronIcon, DownloadIcon, FileIcon, PlusIcon, RefreshIcon, TrashIcon } from "../../components/icons";
import { formatSize } from "../../runState";
import type { ModulePageProps, NexusModule } from "../registry";
import {
  changeLabel,
  diffLineClass,
  downloadFileUrl,
  kodApi,
  zipUrl,
  type Commit,
  type FilePreview,
  type GitChange,
  type Project,
  type TreeEntry,
} from "./api";
import "./kod.css";
import { highlightCode } from "./podswietlanie";
import { SesjaKodu } from "./SesjaKodu";

type Tab = "pliki" | "zmiany" | "historia" | "sesja";

function CodeIcon({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d="m8 7-5 5 5 5M16 7l5 5-5 5M13.5 4l-3 16" />
    </svg>
  );
}

function FolderIcon({ size = 16, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}

const errorText = (reason: unknown) => (reason instanceof Error ? reason.message : String(reason));
const WIDE = "(min-width: 1024px)";

/** Szeroki ekran: sesja Claude Code w stałym panelu obok; wąski – w osobnej zakładce. */
function useWide(): boolean {
  const [wide, setWide] = useState(() => window.matchMedia?.(WIDE).matches ?? true);
  useEffect(() => {
    const media = window.matchMedia?.(WIDE);
    if (!media) return;
    const update = () => setWide(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return wide;
}

// --- podgląd pliku i różnic --------------------------------------------------------------------

function CodeView({ preview, project }: { preview: FilePreview; project: string }) {
  const highlighted = useMemo(() => highlightCode(preview.text, preview.path), [preview]);
  const lines = useMemo(() => preview.text.split("\n").length, [preview.text]);
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b border-line px-3 py-2 text-sm">
        <span className="min-w-0 flex-1 truncate font-mono text-xs">{preview.path}</span>
        <span className="text-xs text-muted">
          {formatSize(preview.size)}
          {highlighted.language && ` · ${highlighted.language}`}
        </span>
        <a
          href={downloadFileUrl(project, preview.path)}
          className="text-muted hover:text-fg"
          aria-label="Pobierz plik"
          title="Pobierz plik"
        >
          <DownloadIcon size={16} />
        </a>
      </div>
      {preview.binary ? (
        <p className="p-4 text-sm text-muted">Plik binarny – podgląd niedostępny, można go pobrać.</p>
      ) : (
        <div className="kod-code flex min-h-0 flex-1 overflow-auto">
          <pre className="sticky left-0 shrink-0 border-r border-line bg-app px-2 py-3 text-right text-muted select-none">
            {Array.from({ length: lines }, (_, index) => index + 1).join("\n")}
          </pre>
          <pre className="flex-1 px-3 py-3">
            <code dangerouslySetInnerHTML={{ __html: highlighted.html }} />
          </pre>
        </div>
      )}
      {preview.truncated && <p className="border-t border-line px-3 py-1.5 text-xs text-muted">Pokazano początek pliku.</p>}
    </div>
  );
}

export function DiffView({ diff, empty }: { diff: string; empty: string }) {
  if (!diff.trim()) return <p className="p-4 text-sm text-muted">{empty}</p>;
  return (
    <pre className="kod-code min-h-0 flex-1 overflow-auto py-2">
      {diff.split("\n").map((line, index) => (
        <div key={index} className={`px-3 whitespace-pre ${diffLineClass(line)}`}>
          {line || " "}
        </div>
      ))}
    </pre>
  );
}

// --- drzewo plików -----------------------------------------------------------------------------

function Tree({
  project,
  version,
  selected,
  onSelect,
}: {
  project: string;
  version: number;
  selected: string;
  onSelect: (path: string) => void;
}) {
  const [entries, setEntries] = useState<Record<string, TreeEntry[]>>({});
  const [open, setOpen] = useState<Set<string>>(() => new Set([""]));
  const [error, setError] = useState("");

  const loadDir = useCallback(
    async (path: string) => {
      try {
        const listing = await kodApi.tree(project, path);
        setEntries((current) => ({ ...current, [path]: listing.entries }));
      } catch (reason) {
        setError(errorText(reason));
      }
    },
    [project],
  );

  useEffect(() => {
    // Odświeżenie (np. po zakończeniu zadania Claude Code) wczytuje ponownie otwarte katalogi;
    // rozwinięcie katalogu wczytuje go samodzielnie, więc zbiór otwartych nie jest zależnością.
    for (const path of open) void loadDir(path);
  }, [loadDir, version]);

  const toggle = (path: string) => {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
        if (!entries[path]) void loadDir(path);
      }
      return next;
    });
  };

  const render = (path: string, depth: number) =>
    (entries[path] ?? []).map((entry) => (
      <li key={entry.path}>
        <button
          type="button"
          onClick={() => (entry.type === "dir" ? toggle(entry.path) : onSelect(entry.path))}
          className={`flex w-full items-center gap-1.5 rounded-md py-1 pr-2 text-left text-sm hover:bg-hover ${
            selected === entry.path ? "bg-hover text-fg" : "text-fg/90"
          }`}
          style={{ paddingLeft: 8 + depth * 14 }}
          aria-expanded={entry.type === "dir" ? open.has(entry.path) : undefined}
        >
          {entry.type === "dir" ? (
            <>
              <ChevronIcon size={13} className={`shrink-0 text-muted transition-transform ${open.has(entry.path) ? "rotate-90" : ""}`} />
              <FolderIcon size={15} className="shrink-0 text-accent" />
            </>
          ) : (
            <FileIcon size={15} className="ml-[19px] shrink-0 text-muted" />
          )}
          <span className="truncate">{entry.name}</span>
        </button>
        {entry.type === "dir" && open.has(entry.path) && <ul>{render(entry.path, depth + 1)}</ul>}
      </li>
    ));

  return (
    <nav className="min-h-0 overflow-y-auto p-2" aria-label="Pliki projektu">
      {error && <p className="px-2 text-xs text-danger">{error}</p>}
      <ul>{render("", 0)}</ul>
      {entries[""]?.length === 0 && <p className="px-2 text-sm text-muted">Pusty projekt.</p>}
    </nav>
  );
}

// --- zakładki git ------------------------------------------------------------------------------

function Changes({ project, version }: { project: string; version: number }) {
  const [changes, setChanges] = useState<GitChange[]>([]);
  const [branch, setBranch] = useState("");
  const [selected, setSelected] = useState("");
  const [diff, setDiff] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    kodApi
      .status(project)
      .then((status) => {
        setChanges(status.changes);
        setBranch(status.branch);
      })
      .catch((reason) => setError(errorText(reason)));
  }, [project, version]);

  useEffect(() => {
    kodApi
      .diff(project, selected)
      .then((result) => setDiff(result.diff + (result.truncated ? "\n… (skrócono)" : "")))
      .catch((reason) => setError(errorText(reason)));
  }, [project, selected, version]);

  return (
    <div className="flex min-h-0 flex-1 flex-col md:flex-row">
      <div className="max-h-48 shrink-0 overflow-y-auto border-b border-line p-2 md:max-h-none md:w-64 md:border-r md:border-b-0">
        <p className="px-2 pb-2 text-xs text-muted">
          Gałąź: <span className="font-mono">{branch || "–"}</span> · zmian: {changes.length}
        </p>
        <button
          type="button"
          onClick={() => setSelected("")}
          className={`w-full rounded-md px-2 py-1 text-left text-sm hover:bg-hover ${selected === "" ? "bg-hover" : ""}`}
        >
          Wszystkie zmiany
        </button>
        {changes.map((change) => {
          const { label, tone } = changeLabel(change);
          return (
            <button
              key={change.path}
              type="button"
              onClick={() => setSelected(change.path)}
              className={`flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-sm hover:bg-hover ${
                selected === change.path ? "bg-hover" : ""
              }`}
            >
              <span className="min-w-0 flex-1 truncate font-mono text-xs">{change.path}</span>
              <span
                className={`shrink-0 text-xs ${tone === "add" ? "text-success" : tone === "del" ? "text-danger" : "text-accent"}`}
              >
                {label}
              </span>
            </button>
          );
        })}
      </div>
      <div className="flex min-h-0 flex-1 flex-col">
        {error && <p className="px-3 py-2 text-sm text-danger">{error}</p>}
        <DiffView diff={diff} empty="Brak zmian względem ostatniego commitu." />
      </div>
    </div>
  );
}

function History({ project, version }: { project: string; version: number }) {
  const [commits, setCommits] = useState<Commit[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [diff, setDiff] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    kodApi
      .log(project)
      .then(setCommits)
      .catch((reason) => setError(errorText(reason)));
  }, [project, version]);

  useEffect(() => {
    if (!selected) return;
    kodApi
      .commit(project, selected)
      .then((result) => setDiff(result.diff))
      .catch((reason) => setError(errorText(reason)));
  }, [project, selected]);

  return (
    <div className="flex min-h-0 flex-1 flex-col md:flex-row">
      <ol className="max-h-56 shrink-0 overflow-y-auto border-b border-line p-2 md:max-h-none md:w-80 md:border-r md:border-b-0">
        {commits.length === 0 && <li className="px-2 text-sm text-muted">Brak commitów.</li>}
        {commits.map((commit) => (
          <li key={commit.hash}>
            <button
              type="button"
              onClick={() => setSelected(commit.hash)}
              className={`w-full rounded-md px-2 py-1.5 text-left hover:bg-hover ${selected === commit.hash ? "bg-hover" : ""}`}
            >
              <span className="block truncate text-sm">{commit.subject}</span>
              <span className="block text-xs text-muted">
                <span className="font-mono">{commit.hash.slice(0, 8)}</span> · {commit.author} ·{" "}
                {new Date(commit.date).toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" })}
              </span>
            </button>
          </li>
        ))}
      </ol>
      <div className="flex min-h-0 flex-1 flex-col">
        {error && <p className="px-3 py-2 text-sm text-danger">{error}</p>}
        <DiffView diff={selected ? diff : ""} empty="Wybierz commit, aby zobaczyć zmiany." />
      </div>
    </div>
  );
}

// --- projekty ----------------------------------------------------------------------------------

function NewProjectForm({ onCreated }: { onCreated: (project: Project) => void }) {
  const [name, setName] = useState("");
  const [repo, setRepo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || (!name.trim() && !repo.trim())) return;
    setBusy(true);
    setError("");
    try {
      onCreated(await kodApi.create(name.trim(), repo.trim()));
      setName("");
      setRepo("");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-2 rounded-xl border border-line p-3">
      <input
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Nazwa projektu"
        className="w-full rounded-lg border border-line bg-app px-2 py-1.5 text-sm outline-none focus:border-accent"
        aria-label="Nazwa projektu"
      />
      <input
        value={repo}
        onChange={(event) => setRepo(event.target.value)}
        placeholder="https://… (opcjonalnie: klonuj repozytorium)"
        className="w-full rounded-lg border border-line bg-app px-2 py-1.5 text-sm outline-none focus:border-accent"
        aria-label="Adres repozytorium"
        inputMode="url"
      />
      <button
        type="submit"
        disabled={busy || (!name.trim() && !repo.trim())}
        className="w-full rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-on-accent hover:bg-accent-hover disabled:opacity-50"
      >
        {busy ? (repo.trim() ? "Klonuję…" : "Tworzę…") : repo.trim() ? "Klonuj" : "Utwórz"}
      </button>
      {error && <p className="text-xs text-danger">{error}</p>}
    </form>
  );
}

export function KodPage({ openConversation }: ModulePageProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [tab, setTab] = useState<Tab>("pliki");
  const [file, setFile] = useState<FilePreview | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const wide = useWide();

  const loadProjects = useCallback(async () => {
    try {
      const items = await kodApi.projects();
      setProjects(items);
      setCurrent((selected) => (selected && items.some((item) => item.name === selected) ? selected : (items[0]?.name ?? null)));
    } catch (reason) {
      setError(errorText(reason));
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  useEffect(() => setFile(null), [current]);

  const refresh = useCallback(() => setVersion((value) => value + 1), []);

  const openFile = async (path: string) => {
    if (!current) return;
    try {
      setFile(await kodApi.file(current, path));
      setTab("pliki");
    } catch (reason) {
      setError(errorText(reason));
    }
  };

  const remove = async () => {
    if (!current || !window.confirm(`Usunąć projekt „${current}” z serwera? Tej operacji nie można cofnąć.`)) return;
    try {
      await kodApi.remove(current);
      setCurrent(null);
      await loadProjects();
    } catch (reason) {
      setError(errorText(reason));
    }
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: "pliki", label: "Pliki" },
    { id: "zmiany", label: "Zmiany" },
    { id: "historia", label: "Historia" },
    ...(wide ? [] : [{ id: "sesja" as const, label: "Claude Code" }]),
  ];
  const activeTab: Tab = wide && tab === "sesja" ? "pliki" : tab;

  return (
    <div className="flex h-full min-h-0 w-full flex-col lg:flex-row">
      <aside className="shrink-0 border-b border-line p-3 lg:w-60 lg:overflow-y-auto lg:border-r lg:border-b-0">
        <div className="mb-2 flex items-center gap-2">
          <h1 className="flex-1 text-lg font-semibold">Kod</h1>
          <button
            type="button"
            onClick={() => setAdding(!adding)}
            className="grid size-8 place-items-center rounded-lg border border-line text-muted hover:text-fg"
            aria-label="Nowy projekt"
            aria-expanded={adding}
          >
            <PlusIcon size={16} />
          </button>
        </div>
        {adding && (
          <NewProjectForm
            onCreated={(project) => {
              setAdding(false);
              setProjects((items) => [project, ...items]);
              setCurrent(project.name);
            }}
          />
        )}
        <ul className="mt-2 flex gap-1 overflow-x-auto lg:block lg:space-y-0.5" aria-label="Projekty">
          {projects.map((project) => (
            <li key={project.name} className="shrink-0">
              <button
                type="button"
                onClick={() => setCurrent(project.name)}
                className={`w-full rounded-lg px-2.5 py-1.5 text-left text-sm hover:bg-hover ${
                  current === project.name ? "bg-hover font-medium" : ""
                }`}
              >
                <span className="block truncate">{project.name}</span>
                {project.branch && <span className="block text-xs text-muted">{project.branch}</span>}
              </button>
            </li>
          ))}
        </ul>
        {projects.length === 0 && !adding && (
          <p className="mt-2 text-sm text-muted">Brak projektów – utwórz nowy albo sklonuj repozytorium.</p>
        )}
      </aside>

      {current ? (
        <>
          <main className="flex min-h-0 min-w-0 flex-1 flex-col">
            <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
              <div className="flex gap-1" role="tablist">
                {tabs.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="tab"
                    aria-selected={activeTab === item.id}
                    onClick={() => setTab(item.id)}
                    className={`rounded-lg px-2.5 py-1 text-sm ${
                      activeTab === item.id ? "bg-hover font-medium" : "text-muted hover:text-fg"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="ml-auto flex items-center gap-1">
                <button
                  type="button"
                  onClick={refresh}
                  className="grid size-8 place-items-center rounded-lg text-muted hover:bg-hover hover:text-fg"
                  aria-label="Odśwież"
                  title="Odśwież"
                >
                  <RefreshIcon size={16} />
                </button>
                <a
                  href={zipUrl(current)}
                  className="grid size-8 place-items-center rounded-lg text-muted hover:bg-hover hover:text-fg"
                  aria-label="Pobierz projekt (ZIP)"
                  title="Pobierz projekt (ZIP)"
                >
                  <DownloadIcon size={16} />
                </a>
                <button
                  type="button"
                  onClick={() => void remove()}
                  className="grid size-8 place-items-center rounded-lg text-muted hover:bg-hover hover:text-danger"
                  aria-label="Usuń projekt"
                  title="Usuń projekt"
                >
                  <TrashIcon size={16} />
                </button>
              </div>
            </div>
            {error && (
              <p className="border-b border-line px-3 py-1.5 text-sm text-danger" role="alert">
                {error}
              </p>
            )}
            {activeTab === "pliki" && (
              <div className="flex min-h-0 flex-1 flex-col md:flex-row">
                <div className="max-h-64 shrink-0 overflow-hidden border-b border-line md:flex md:max-h-none md:w-64 md:flex-col md:border-r md:border-b-0">
                  <Tree key={current} project={current} version={version} selected={file?.path ?? ""} onSelect={(path) => void openFile(path)} />
                </div>
                {file ? (
                  <CodeView preview={file} project={current} />
                ) : (
                  <p className="p-4 text-sm text-muted">Wybierz plik, aby zobaczyć jego treść.</p>
                )}
              </div>
            )}
            {activeTab === "zmiany" && <Changes project={current} version={version} />}
            {activeTab === "historia" && <History project={current} version={version} />}
            {activeTab === "sesja" && (
              <div className="flex min-h-0 flex-1 flex-col">
                <SesjaKodu project={current} onRunFinished={refresh} openConversation={openConversation} />
              </div>
            )}
          </main>
          {wide && (
            <aside className="flex min-h-0 w-[26rem] shrink-0 flex-col border-l border-line" aria-label="Claude Code">
              <SesjaKodu project={current} onRunFinished={refresh} openConversation={openConversation} />
            </aside>
          )}
        </>
      ) : (
        <main className="grid flex-1 place-items-center p-6 text-center text-sm text-muted">
          <div>
            <CodeIcon size={32} className="mx-auto mb-2" />
            Projekty programistyczne na serwerze: Claude Code czyta i zmienia kod, uruchamia testy i git.
          </div>
        </main>
      )}
    </div>
  );
}

export const module: NexusModule = {
  id: "kod",
  label: "Kod",
  description: "Projekty i sesje programistyczne z Claude Code",
  icon: CodeIcon,
  order: 60,
  Page: KodPage,
};
