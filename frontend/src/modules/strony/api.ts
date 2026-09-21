// Klient API Twórcy stron.

import { requestJson } from "../_tworczy/http";

export interface SiteVersion {
  id: string;
  created_at: string;
  note: string;
  files: number;
  size: number;
}

export interface Site {
  address: string;
  title: string;
  description: string;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  published_version: string | null;
  publish_request: { requested_at: string; note: string } | null;
  conversation_id: string | null;
  versions: SiteVersion[];
  public_url: string;
}

export interface SiteFile {
  path: string;
  size: number;
  modified: string;
}

export interface SiteDetail extends Site {
  files: SiteFile[];
  preview_url: string;
}

const base = (address: string) => `/api/strony/${encodeURIComponent(address)}`;

export interface Preset {
  preset: string;
  nazwa: string;
  opis: string;
}

export interface SzablonKolekcji {
  id: string;
  nazwa: string;
  charakter: string[];
  podstrony: number;
  licencja: string;
}

export interface KatalogKitu {
  dostepny: boolean;
  presety: Preset[];
  motywy: string[];
  /** Szablony otwarte z gotową, zbudowaną witryną — wstawiane do szkicu bez budowania. */
  szablony: SzablonKolekcji[];
}

export const sitesApi = {
  list: () => requestJson<Site[]>("GET", "/api/strony"),
  /** Presety branżowe zestawu Danaco Web Kit — gotowe układy na start. */
  kit: () => requestJson<KatalogKitu>("GET", "/api/strony/kit"),
  create: (title: string, description: string, address?: string) =>
    requestJson<Site>("POST", "/api/strony", { title, description, address: address || null }),
  get: (address: string) => requestJson<SiteDetail>("GET", base(address)),
  update: (address: string, values: { title?: string; description?: string }) =>
    requestJson<Site>("PATCH", base(address), values),
  remove: (address: string) => requestJson<{ ok: boolean }>("DELETE", base(address)),
  conversation: (address: string) => requestJson<{ conversation_id: string }>("POST", `${base(address)}/rozmowa`),
  readFile: (address: string, path: string) =>
    requestJson<{ path: string; content: string }>("GET", `${base(address)}/pliki/${path.split("/").map(encodeURIComponent).join("/")}`),
  saveVersion: (address: string, note: string) => requestJson<SiteVersion>("POST", `${base(address)}/wersje`, { note }),
  restore: (address: string, version: string) =>
    requestJson<Site>("POST", `${base(address)}/wersje/${encodeURIComponent(version)}/przywroc`),
  publish: (address: string) => requestJson<Site>("POST", `${base(address)}/publikuj`),
  unpublish: (address: string) => requestJson<Site>("POST", `${base(address)}/wycofaj`),
  rejectPublish: (address: string) => requestJson<Site>("POST", `${base(address)}/odrzuc-publikacje`),
};

export function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("pl-PL", { dateStyle: "medium", timeStyle: "short" });
}
