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
  /** Konto, z którego pochodzi wiadomość (uzupełnia interfejs). */
  account?: string;
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
  /** Konto nadawcy (adres); puste – domyślne. */
  account?: string;
  /** Czy dołączyć podpis konta (domyślnie tak). */
  signature?: boolean;
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

export interface MailAccount {
  id: string;
  address: string;
  name: string;
  label: string;
  signature: boolean;
}

export interface MailState {
  configured: boolean;
  address: string;
  accounts: MailAccount[];
  name?: string;
  error?: string;
}

/** Dane konta podawane w module. Hasło nigdy nie wraca z serwera. */
export interface KontoPocztowe {
  login: string;
  haslo: string;
  adres: string;
  nazwa: string;
  etykieta: string;
  imap_host: string;
  imap_port: number;
  smtp_host: string;
  smtp_port: number;
  smtp_security: "ssl" | "starttls";
  podpis_html: string;
}

export interface WynikSprawdzenia {
  ok: boolean;
  imap: boolean;
  smtp: boolean;
  folders: number;
}

export const mailApi = {
  state: () => call<MailState>("GET", "/api/poczta/stan"),
  sprawdzKonto: (konto: KontoPocztowe) => call<WynikSprawdzenia>("POST", "/api/poczta/konta/sprawdz", konto),
  zapiszKonto: (konto: KontoPocztowe) =>
    call<{ ok: boolean; id: string; konta: number }>("POST", "/api/poczta/konta", konto),
  usunKonto: (id: string) => call<{ ok: boolean; konta: number }>("DELETE", `/api/poczta/konta/${encodeURIComponent(id)}`),
  folders: (konto: string) => call<MailFolder[]>("GET", `/api/poczta/foldery${qs({ konto })}`),
  messages: (konto: string, folder: string, beforeUid?: number, unread = false) =>
    call<MailListing>("GET", `/api/poczta/wiadomosci${qs({ konto, folder, before_uid: beforeUid, unread })}`),
  search: (konto: string, folder: string, q: string) =>
    call<MailListing>("GET", `/api/poczta/szukaj${qs({ konto, folder, q })}`),
  read: async (konto: string, folder: string, uid: number) => ({
    ...(await call<MailMessage>("GET", `/api/poczta/wiadomosc${qs({ konto, folder, uid })}`)),
    account: konto,
  }),
  flag: (konto: string, folder: string, uid: number, flag: "seen" | "flagged", value: boolean) =>
    call<{ ok: boolean }>("POST", "/api/poczta/flaga", { konto, folder, uid, flag, value }),
  pending: (all = false) => call<PendingMail[]>("GET", `/api/poczta/oczekujace${qs({ all })}`),
  createPending: (draft: DraftPayload) => call<PendingMail>("POST", "/api/poczta/oczekujace", draft),
  updatePending: (id: string, draft: Partial<DraftPayload>) =>
    call<PendingMail>("PATCH", `/api/poczta/oczekujace/${id}`, draft),
  cancelPending: (id: string) => call<PendingMail>("DELETE", `/api/poczta/oczekujace/${id}`),
  saveDraft: (id: string) => call<{ folder: string }>("POST", `/api/poczta/oczekujace/${id}/szkic`),
  send: (id: string) => call<PendingMail>("POST", `/api/poczta/wyslij/${id}`),
  replyWithNexus: (konto: string, folder: string, uid: number, instruction: string) =>
    call<{ conversation_id: string; run_id: string }>("POST", "/api/poczta/odpowiedz-z-nexusem", {
      konto,
      folder,
      uid,
      instruction,
    }),
};

export function attachmentUrl(konto: string, folder: string, uid: number, index: number, inline = false): string {
  return `/api/poczta/zalacznik${qs({ konto, folder, uid, index, inline })}`;
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
    account: message.account ?? "",
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
