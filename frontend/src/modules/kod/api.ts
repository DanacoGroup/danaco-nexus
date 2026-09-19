// Zapytania modułu Kod: projekty, pliki, git i rozmowy programistyczne.

import { request } from "../agenci/api";

export interface Project {
  name: string;
  git: boolean;
  branch: string;
  modified: string;
}

export interface TreeEntry {
  name: string;
  path: string;
  type: "dir" | "file";
  size: number;
}

export interface FilePreview {
  path: string;
  size: number;
  binary: boolean;
  truncated: boolean;
  text: string;
}

export interface GitChange {
  path: string;
  index: string;
  worktree: string;
  from?: string;
}

export interface Commit {
  hash: string;
  author: string;
  date: string;
  subject: string;
}

export interface CodeConversation {
  id: string;
  title: string;
  updated_at: string;
}

const base = (name: string) => `/api/kod/projekty/${encodeURIComponent(name)}`;
const query = (path: string) => `?sciezka=${encodeURIComponent(path)}`;

export const kodApi = {
  projects: () => request<Project[]>("GET", "/api/kod/projekty"),
  create: (name: string, repoUrl: string) =>
    request<Project>("POST", "/api/kod/projekty", { name, repo_url: repoUrl }),
  remove: (name: string) => request<{ ok: boolean }>("DELETE", base(name)),
  tree: (name: string, path: string) =>
    request<{ path: string; entries: TreeEntry[] }>("GET", `${base(name)}/drzewo${query(path)}`),
  file: (name: string, path: string) => request<FilePreview>("GET", `${base(name)}/plik${query(path)}`),
  status: (name: string) =>
    request<{ git: boolean; branch: string; changes: GitChange[] }>("GET", `${base(name)}/git/status`),
  diff: (name: string, path = "") =>
    request<{ diff: string; truncated: boolean }>("GET", `${base(name)}/git/diff${path ? query(path) : ""}`),
  log: (name: string) => request<Commit[]>("GET", `${base(name)}/git/log`),
  commit: (name: string, hash: string) =>
    request<{ diff: string; truncated: boolean }>("GET", `${base(name)}/git/commit/${encodeURIComponent(hash)}`),
  conversations: (name: string) => request<CodeConversation[]>("GET", `${base(name)}/rozmowy`),
  createConversation: (name: string) => request<CodeConversation>("POST", `${base(name)}/rozmowy`, {}),
};

export const zipUrl = (name: string) => `${base(name)}/zip`;
export const downloadFileUrl = (name: string, path: string) => `${base(name)}/pobierz${query(path)}`;

/** Czytelny opis zmiany z kodów git status (indeks + katalog roboczy). */
export function changeLabel(change: GitChange): { label: string; tone: "add" | "del" | "mod" } {
  const code = `${change.index}${change.worktree}`;
  if (code === "??" || change.index === "A") return { label: "nowy", tone: "add" };
  if (code.includes("D")) return { label: "usunięty", tone: "del" };
  if (code.includes("R")) return { label: "przeniesiony", tone: "mod" };
  return { label: "zmieniony", tone: "mod" };
}

/** Klasa wiersza różnic (dodane, usunięte, nagłówki). */
export function diffLineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) return "text-muted";
  if (line.startsWith("+")) return "kod-diff-add";
  if (line.startsWith("-")) return "kod-diff-del";
  if (line.startsWith("@@")) return "text-accent";
  if (line.startsWith("diff ") || line.startsWith("index ") || line.startsWith("commit ")) return "text-muted";
  return "";
}
