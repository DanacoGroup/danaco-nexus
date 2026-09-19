// API modułu Poczta.

import { call, qs } from "../_biuro/http";

export interface Address {
  name: string;
  email: string;
}

export interface MailFolder {
  name: string;
  role: string | null;
  label: string;
  messages?: number;
  unseen?: number;
}

export interface MailHeader {
  uid: number;
  subject: string;
  from: Address[];
  to: Address[];
  date: string | null;
  seen: boolean;
  flagged: boolean;
  answered: boolean;
  has_attachments: boolean;
  size: number;
}

export interface MailListing {
  folder: string;
  total: number;
  messages: MailHeader[];
  more: boolean;
}

export interface MailAttachment {
  index: number;
  name: string;
  mime: string;
  size: number;
  content_id: string | null;
  inline: boolean;
}

export interface MailMessage {
  uid: number;
  folder: string;
  subject: string;
  from: Address[];
  to: Address[];
  cc: Address[];
  reply_to: Address[];
  date: string | null;
  message_id: string;
  references: string;
  text: string;
  html: string;
  attachments: MailAttachment[];
}

export interface DraftPayload {
  to: string[];
  cc: string[];
  bcc: string[];
  subject: string;
  body: string;
  reply?: { folder: string; uid: number } | null;
  in_reply_to?: string;
  references?: string;
  file_ids?: string[];
}

export interface PendingMail {
  id: string;
  kind: "mail";
  status: "pending" | "running" | "done" | "cancelled" | "failed";
  summary: string;
  payload: DraftPayload;
  run_id: string | null;
  error: string;
  created_at: string;
  updated_at: string;
}

export interface MailState {
  configured: boolean;
  address: string;
  name?: string;
  setup?: string;
  error?: string;
}

export const mailApi = {
  state: () => call<MailState>("GET", "/api/poczta/stan"),
  folders: () => call<MailFolder[]>("GET", "/api/poczta/foldery"),
  messages: (folder: string, beforeUid?: number, unread = false) =>
    call<MailListing>("GET", `/api/poczta/wiadomosci${qs({ folder, before_uid: beforeUid, unread })}`),
  search: (folder: string, q: string) => call<MailListing>("GET", `/api/poczta/szukaj${qs({ folder, q })}`),
  read: (folder: string, uid: number) => call<MailMessage>("GET", `/api/poczta/wiadomosc${qs({ folder, uid })}`),
  flag: (folder: string, uid: number, flag: "seen" | "flagged", value: boolean) =>
    call<{ ok: boolean }>("POST", "/api/poczta/flaga", { folder, uid, flag, value }),
  pending: (all = false) => call<PendingMail[]>("GET", `/api/poczta/oczekujace${qs({ all })}`),
  createPending: (draft: DraftPayload) => call<PendingMail>("POST", "/api/poczta/oczekujace", draft),
  updatePending: (id: string, draft: Partial<DraftPayload>) =>
    call<PendingMail>("PATCH", `/api/poczta/oczekujace/${id}`, draft),
  cancelPending: (id: string) => call<PendingMail>("DELETE", `/api/poczta/oczekujace/${id}`),
  saveDraft: (id: string) => call<{ folder: string }>("POST", `/api/poczta/oczekujace/${id}/szkic`),
  send: (id: string) => call<PendingMail>("POST", `/api/poczta/wyslij/${id}`),
  replyWithNexus: (folder: string, uid: number, instruction: string) =>
    call<{ conversation_id: string; run_id: string }>("POST", "/api/poczta/odpowiedz-z-nexusem", {
      folder,
      uid,
      instruction,
    }),
};

export function attachmentUrl(folder: string, uid: number, index: number, inline = false): string {
  return `/api/poczta/zalacznik${qs({ folder, uid, index, inline })}`;
}

export function imageProxyUrl(url: string): string {
  return `/api/poczta/obraz${qs({ url })}`;
}

export function formatAddress(address: Address): string {
  return address.name ? `${address.name} <${address.email}>` : address.email;
}

export function displayName(addresses: Address[]): string {
  const first = addresses[0];
  if (!first) return "(brak nadawcy)";
  return first.name || first.email;
}

/** Lista adresów z pola tekstowego (przecinki, średniki, nowe linie). */
export function parseAddresses(value: string): string[] {
  return value
    .split(/[,;\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

/** Odpowiedź na wiadomość: adresat, temat „Re:”, nagłówki wątku i cytat. */
export function replyDraft(message: MailMessage): DraftPayload {
  const sender = message.reply_to[0] ?? message.from[0];
  const subject = /^\s*(re|odp)\s*:/i.test(message.subject) ? message.subject : `Re: ${message.subject}`;
  const who = message.from[0] ? message.from[0].name || message.from[0].email : "nadawca";
  const when = message.date ? new Date(message.date).toLocaleString("pl-PL") : "";
  const quoted = message.text
    .split("\n")
    .slice(0, 200)
    .map((line) => `> ${line}`)
    .join("\n");
  return {
    to: sender ? [formatAddress(sender)] : [],
    cc: [],
    bcc: [],
    subject,
    body: `\n\n${when} ${who} napisał(a):\n${quoted}`,
    reply: { folder: message.folder, uid: message.uid },
    in_reply_to: message.message_id,
    references: message.references,
  };
}

/** Data na liście wiadomości: godzina (dziś), dzień i miesiąc (w tym roku) albo pełna data. */
export function listDate(value: string | null, now = new Date()): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  if (date.toDateString() === now.toDateString())
    return date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  if (date.getFullYear() === now.getFullYear())
    return date.toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
  return date.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" });
}
