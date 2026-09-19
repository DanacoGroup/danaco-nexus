// API modułu Kalendarz (CalDAV chmury przez Nexusa).

import { call, qs } from "../_biuro/http";

export interface CalendarInfo {
  id: string;
  name: string;
  color: string;
  writable: boolean;
  default: boolean;
}

export interface CalendarEvent {
  id: string;
  uid: string;
  etag: string;
  calendar: string;
  calendar_name: string;
  color: string;
  writable: boolean;
  summary: string;
  location: string;
  description: string;
  /** „RRRR-MM-DDTGG:MM+02:00” albo „RRRR-MM-DD” (cały dzień). */
  start: string;
  /** Koniec (dla całodniowych – dzień po ostatnim dniu). */
  end: string;
  all_day: boolean;
  recurring: boolean;
  recurrence_id: string | null;
}

export interface EventInput {
  calendar?: string;
  summary: string;
  start: string;
  end?: string | null;
  all_day: boolean;
  location: string;
  description: string;
  reminder_minutes?: number | null;
  rrule?: string;
}

export interface PendingDeletion {
  id: string;
  kind: "kalendarz_usun";
  status: string;
  summary: string;
  payload: { event_id: string; summary: string; start: string; recurring: boolean; reason: string };
  created_at: string;
}

function eventPath(id: string): string {
  const [calendar, name] = id.split("/");
  return `/api/kalendarz/wydarzenia/${encodeURIComponent(calendar)}/${encodeURIComponent(name)}`;
}

export const calendarApi = {
  calendars: () => call<CalendarInfo[]>("GET", "/api/kalendarz/kalendarze"),
  events: (from: string, to: string, calendars: string[] = []) =>
    call<CalendarEvent[]>("GET", `/api/kalendarz/wydarzenia${qs({ od: from, do: to, kalendarze: calendars.join(",") })}`),
  create: (input: EventInput) => call<CalendarEvent>("POST", "/api/kalendarz/wydarzenia", input),
  update: (id: string, input: Partial<EventInput> & { etag?: string; recurrence_id?: string | null }) =>
    call<CalendarEvent>("PATCH", eventPath(id), input),
  remove: (id: string) => call<{ ok: boolean }>("DELETE", eventPath(id)),
  pending: () => call<PendingDeletion[]>("GET", "/api/kalendarz/oczekujace"),
  approve: (id: string) => call<PendingDeletion>("POST", `/api/kalendarz/oczekujace/${id}/zatwierdz`),
  reject: (id: string) => call<PendingDeletion>("POST", `/api/kalendarz/oczekujace/${id}/odrzuc`),
  plan: (text: string, day: string) =>
    call<{ conversation_id: string; run_id: string }>("POST", "/api/kalendarz/zaplanuj", { text, day }),
  sync: () => call<{ caldav_url: string; user: string }>("GET", "/api/kalendarz/synchronizacja"),
};
