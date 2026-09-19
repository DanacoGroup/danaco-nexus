// Klient API modułów Research i Baza wiedzy (/api/research).

import { ApiError } from "../../api";

export type ResearchKind = "deep" | "scholar";
export type ResearchDepth = "quick" | "standard" | "deep";

export interface Collection {
  id: string;
  name: string;
  description: string;
  sources: number;
  notes: number;
  created_at: string;
  updated_at: string;
}

export interface Source {
  id: string;
  collection_id: string;
  kind: "strona" | "plik" | "praca" | "tekst";
  url: string;
  title: string;
  excerpt: string;
  chars: number;
  meta: Record<string, unknown>;
  file_id: string | null;
  indexed: boolean;
  index_error: string;
  created_at: string;
  updated_at: string;
  content?: string;
}

export interface Note {
  id: string;
  collection_id: string;
  source_id: string | null;
  title: string;
  content: string;
  indexed: boolean;
  created_at: string;
  updated_at: string;
}

export interface Report {
  id: string;
  conversation_id: string;
  kind: ResearchKind;
  question: string;
  depth: ResearchDepth;
  collection_id: string | null;
  title: string;
  status: string;
  run_id: string | null;
  error: string;
  created_at: string;
}

export interface ReportDetail extends Report {
  report: string;
  active: boolean;
}

export interface PagePreview {
  url: string;
  final_url: string;
  title: string;
  description: string;
  site_name: string;
  author: string;
  published: string;
  text: string;
  truncated: boolean;
}

export interface SearchHit {
  id: string;
  type: "source" | "note";
  title: string;
  collection_id: string;
  score: number;
  text: string;
}

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    headers:
      body === undefined
        ? { "X-Nexus-Request": "1" }
        : { "X-Nexus-Request": "1", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let message = `Błąd serwera (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]?.msg) message = String(data.detail[0].msg);
    } catch {
      /* odpowiedź bez treści JSON */
    }
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

const BASE = "/api/research";

export const researchApi = {
  collections: () => call<Collection[]>("GET", `${BASE}/kolekcje`),
  createCollection: (name: string, description = "") =>
    call<Collection>("POST", `${BASE}/kolekcje`, { name, description }),
  updateCollection: (id: string, patch: { name?: string; description?: string }) =>
    call<Collection>("PATCH", `${BASE}/kolekcje/${id}`, patch),
  deleteCollection: (id: string) => call<{ ok: boolean }>("DELETE", `${BASE}/kolekcje/${id}`),

  sources: (collectionId: string) => call<Source[]>("GET", `${BASE}/kolekcje/${collectionId}/zrodla`),
  addSource: (collectionId: string, input: { url?: string; file_id?: string; title?: string; content?: string }) =>
    call<Source>("POST", `${BASE}/kolekcje/${collectionId}/zrodla`, input),
  source: (id: string) => call<Source>("GET", `${BASE}/zrodla/${id}`),
  updateSource: (id: string, patch: { title?: string; collection_id?: string }) =>
    call<Source>("PATCH", `${BASE}/zrodla/${id}`, patch),
  reindexSource: (id: string) => call<{ ok: boolean }>("POST", `${BASE}/zrodla/${id}/indeksuj`),
  deleteSource: (id: string) => call<{ ok: boolean }>("DELETE", `${BASE}/zrodla/${id}`),

  notes: (collectionId: string) => call<Note[]>("GET", `${BASE}/kolekcje/${collectionId}/notatki`),
  addNote: (collectionId: string, input: { title: string; content: string; source_id?: string | null }) =>
    call<Note>("POST", `${BASE}/kolekcje/${collectionId}/notatki`, input),
  updateNote: (id: string, patch: { title?: string; content?: string }) =>
    call<Note>("PATCH", `${BASE}/notatki/${id}`, patch),
  deleteNote: (id: string) => call<{ ok: boolean }>("DELETE", `${BASE}/notatki/${id}`),

  search: (query: string, collectionId?: string) => {
    const params = new URLSearchParams({ q: query });
    if (collectionId) params.set("collection_id", collectionId);
    return call<{ query: string; results: SearchHit[] }>("GET", `${BASE}/szukaj?${params}`);
  },
  preview: (url: string) => call<PagePreview>("POST", `${BASE}/podglad`, { url }),

  startResearch: (input: {
    question: string;
    kind: ResearchKind;
    depth: ResearchDepth;
    collection_id?: string | null;
    save_sources: boolean;
  }) => call<Report>("POST", `${BASE}/badania`, input),
  reports: () => call<Report[]>("GET", `${BASE}/badania`),
  report: (id: string) => call<ReportDetail>("GET", `${BASE}/badania/${id}`),
  deleteReport: (id: string) => call<{ ok: boolean }>("DELETE", `${BASE}/badania/${id}`),

  chat: (input: { source_ids?: string[]; note_ids?: string[]; collection_id?: string | null; question?: string }) =>
    call<{ conversation_id: string; run_id: string; title: string }>("POST", `${BASE}/rozmowa`, input),
};

export const ACTIVE = new Set(["queued", "running"]);

/** Komunikat błędu do wyświetlenia. */
export function errorText(failure: unknown): string {
  return failure instanceof Error ? failure.message : String(failure);
}

/** Data i godzina po polsku (krótko). */
export function shortDate(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return sameDay
    ? date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("pl-PL", { day: "numeric", month: "short", year: "numeric" });
}
