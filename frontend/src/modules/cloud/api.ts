// API modułu Cloud (chmura osobista Nextcloud przez Nexusa) i przesyłanie dużych plików kawałkami.

import { ApiError, type FileInfo } from "../../api";
import { call, qs, sendBlob } from "../_biuro/http";

export interface CloudEntry {
  path: string;
  name: string;
  type: "file" | "folder";
  size: number | null;
  modified: string | null;
  mime: string | null;
  etag: string;
  fileid: number | null;
  favorite: boolean;
  permissions: string;
  has_preview: boolean;
  shared_link: boolean;
  shared: boolean;
}

export interface CloudListing {
  path: string;
  folder: CloudEntry | null;
  entries: CloudEntry[];
}

export interface CloudShare {
  id: string;
  url: string;
  token: string;
  path: string | null;
  expires: string | null;
  has_password: boolean;
  permissions: number;
  label: string;
}

export interface CloudVersion {
  id: string;
  modified: string | null;
  size: number | null;
  label: string;
  author: string;
}

export interface TrashEntry {
  id: string;
  name: string;
  original: string;
  type: "file" | "folder";
  size: number | null;
  deleted: number | null;
}

export interface SyncInfo {
  server_url: string;
  user: string;
  qr: string;
  webdav_url: string;
  clients: Record<string, string>;
}

export const cloudApi = {
  list: (path: string) => call<CloudListing>("GET", `/api/cloud/lista${qs({ path })}`),
  quota: () => call<{ used: number | null; available: number | null }>("GET", "/api/cloud/miejsce"),
  search: (q: string) => call<CloudEntry[]>("GET", `/api/cloud/szukaj${qs({ q })}`),
  favorites: () => call<CloudEntry[]>("GET", "/api/cloud/ulubione"),
  setFavorite: (path: string, favorite: boolean) =>
    call<{ ok: boolean }>("POST", "/api/cloud/ulubione", { path, favorite }),
  mkdir: (path: string) => call<CloudEntry>("POST", "/api/cloud/folder", { path }),
  rename: (path: string, name: string) => call<CloudEntry>("POST", "/api/cloud/zmien-nazwe", { path, name }),
  move: (paths: string[], destination: string, copy = false) =>
    call<{ paths: string[] }>("POST", "/api/cloud/przenies", { paths, destination, copy }),
  remove: (paths: string[]) => call<{ deleted: number }>("POST", "/api/cloud/usun", { paths }),
  trash: () => call<TrashEntry[]>("GET", "/api/cloud/kosz"),
  restoreTrash: (id: string) => call<{ ok: boolean }>("POST", "/api/cloud/kosz/przywroc", { id }),
  versions: (path: string) => call<CloudVersion[]>("GET", `/api/cloud/wersje${qs({ path })}`),
  restoreVersion: (path: string, version: string) =>
    call<CloudEntry>("POST", "/api/cloud/wersje/przywroc", { path, version }),
  shares: (path: string) => call<CloudShare[]>("GET", `/api/cloud/udostepnienia${qs({ path })}`),
  createShare: (body: { path: string; password?: string; expires?: string; allow_upload?: boolean }) =>
    call<CloudShare>("POST", "/api/cloud/udostepnienia", body),
  updateShare: (id: string, body: { password?: string; expires?: string; clear_expiration?: boolean }) =>
    call<CloudShare>("PATCH", `/api/cloud/udostepnienia/${id}`, body),
  deleteShare: (id: string) => call<{ ok: boolean }>("DELETE", `/api/cloud/udostepnienia/${id}`),
  toConversation: (body: { paths: string[]; conversation_id?: string | null; text?: string; send?: boolean }) =>
    call<{ conversation_id: string; run_id: string | null; files: FileInfo[] }>("POST", "/api/cloud/do-rozmowy", body),
  syncInfo: () => call<SyncInfo>("GET", "/api/cloud/synchronizacja"),
};

export function downloadUrl(path: string, inline = false): string {
  return `/api/cloud/pobierz${qs({ path, inline })}`;
}

export function versionUrl(path: string, version: string): string {
  return `/api/cloud/wersje/pobierz${qs({ path, version })}`;
}

export function thumbnailUrl(entry: CloudEntry, size = 128): string | null {
  return entry.has_preview && entry.fileid ? `/api/cloud/miniatura${qs({ fileid: entry.fileid, size })}` : null;
}

export function joinPath(folder: string, name: string): string {
  return `${folder.replace(/\/+$/, "")}/${name}`.replace(/^\/*/, "/");
}

export function parentPath(path: string): string {
  const parts = path.split("/").filter(Boolean);
  parts.pop();
  return `/${parts.join("/")}`;
}

/** Okruchy ścieżki: [{name: "Chmura", path: "/"}, {name: "Dokumenty", path: "/Dokumenty"}…].
 *
 * Korzeń nazywa się tak samo jak moduł w pasku nawigacji. Wcześniej stało tam „Cloud”:
 * jedyne angielskie słowo na całym ekranie, tuż pod nagłówkiem „Chmura”. */
export function breadcrumbs(path: string): { name: string; path: string }[] {
  const result = [{ name: "Chmura", path: "/" }];
  let current = "";
  for (const part of path.split("/").filter(Boolean)) {
    current += `/${part}`;
    result.push({ name: part, path: current });
  }
  return result;
}

// --- przesyłanie ---

/** Rozmiar kawałka przesyłania (Nextcloud przyjmuje do 100 MB na kawałek). */
export const CHUNK_SIZE = 10 * 1024 * 1024;
const RETRIES = 3;

/** Zakresy bajtów kolejnych kawałków pliku. */
export function chunkRanges(size: number, chunk = CHUNK_SIZE): [number, number][] {
  const ranges: [number, number][] = [];
  for (let start = 0; start < size; start += chunk) ranges.push([start, Math.min(size, start + chunk)]);
  return ranges;
}

export interface UploadOptions {
  onProgress?: (fraction: number) => void;
  signal?: AbortSignal;
  chunkSize?: number;
}

async function withRetry<T>(work: () => Promise<T>, signal?: AbortSignal): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < RETRIES; attempt += 1) {
    try {
      return await work();
    } catch (error) {
      lastError = error;
      const retriable = error instanceof ApiError && (error.status === 0 || error.status >= 500);
      if (!retriable || signal?.aborted) throw error;
      await new Promise((resolve) => setTimeout(resolve, 800 * (attempt + 1)));
    }
  }
  throw lastError;
}

/** Wgrywa plik do chmury: mały jednym żądaniem, duży kawałkami (chunked upload v2). */
export async function uploadToCloud(file: Blob & { name?: string; lastModified?: number }, target: string, options: UploadOptions = {}): Promise<CloudEntry> {
  const { onProgress, signal } = options;
  const chunkSize = options.chunkSize ?? CHUNK_SIZE;
  if (file.size <= chunkSize) {
    return (await sendBlob("PUT", `/api/cloud/plik${qs({ path: target })}`, file, onProgress, signal)) as CloudEntry;
  }
  const { upload_id } = await call<{ upload_id: string }>("POST", "/api/cloud/przesylanie", { path: target }, signal);
  const ranges = chunkRanges(file.size, chunkSize);
  let sent = 0;
  try {
    for (const [index, [start, end]] of ranges.entries()) {
      const part = file.slice(start, end);
      await withRetry(
        () =>
          sendBlob(
            "PUT",
            `/api/cloud/przesylanie/${upload_id}/${index + 1}${qs({ path: target })}`,
            part,
            (fraction) => onProgress?.((sent + fraction * part.size) / file.size),
            signal,
          ),
        signal,
      );
      sent += part.size;
      onProgress?.(sent / file.size);
    }
    const mtime = file.lastModified ? Math.floor(file.lastModified / 1000) : undefined;
    return await call<CloudEntry>(
      "POST",
      `/api/cloud/przesylanie/${upload_id}/zakoncz`,
      { path: target, size: file.size, mtime },
      signal,
    );
  } catch (error) {
    call("DELETE", `/api/cloud/przesylanie/${upload_id}`).catch(() => undefined);
    throw error;
  }
}
