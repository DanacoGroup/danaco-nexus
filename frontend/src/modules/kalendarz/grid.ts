// Obliczenia widoków kalendarza: tydzień od poniedziałku, siatka miesiąca, wydarzenia dnia, układ kolumn.

import type { CalendarEvent } from "./api";

export const DAY_MS = 86_400_000;

/** Data lokalna bez czasu. */
export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function addDays(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

/** Poniedziałek tygodnia, w którym leży data. */
export function startOfWeek(date: Date): Date {
  const day = (date.getDay() + 6) % 7;
  return addDays(startOfDay(date), -day);
}

/** 42 dni (6 tygodni) widoku miesiąca, od poniedziałku. */
export function monthGrid(year: number, month: number): Date[] {
  const first = startOfWeek(new Date(year, month, 1));
  return Array.from({ length: 42 }, (_, index) => addDays(first, index));
}

/** RRRR-MM-DD w czasie lokalnym. */
export function isoDay(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** Tekst daty lub czasu z API na obiekt Date (dzień całodniowy – północ czasu lokalnego). */
export function parseWhen(value: string): Date {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day);
  }
  return new Date(value);
}

export function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** Wydarzenia obejmujące dany dzień (koniec wyłączny), posortowane: całodniowe, potem po godzinie. */
export function eventsOnDay(events: CalendarEvent[], day: Date): CalendarEvent[] {
  const dayStart = startOfDay(day).getTime();
  const dayEnd = addDays(day, 1).getTime();
  return events
    .filter((event) => {
      const start = parseWhen(event.start).getTime();
      let end = parseWhen(event.end).getTime();
      if (end <= start) end = start + 1;
      return start < dayEnd && end > dayStart;
    })
    .sort((a, b) => {
      if (a.all_day !== b.all_day) return a.all_day ? -1 : 1;
      return parseWhen(a.start).getTime() - parseWhen(b.start).getTime() || a.summary.localeCompare(b.summary, "pl");
    });
}

export interface PositionedEvent {
  event: CalendarEvent;
  /** Minuty od północy (początek i koniec w obrębie dnia). */
  top: number;
  bottom: number;
  column: number;
  columns: number;
}

/** Układ wydarzeń godzinowych dnia: nakładające się stoją obok siebie. */
export function layoutDay(events: CalendarEvent[], day: Date): PositionedEvent[] {
  const dayStart = startOfDay(day).getTime();
  const items = events
    .filter((event) => !event.all_day)
    .map((event) => {
      const start = Math.max(0, (parseWhen(event.start).getTime() - dayStart) / 60_000);
      const end = Math.min(24 * 60, (parseWhen(event.end).getTime() - dayStart) / 60_000);
      return { event, top: start, bottom: Math.max(end, start + 20), column: 0, columns: 1 };
    })
    .filter((item) => item.top < 24 * 60 && item.bottom > 0)
    .sort((a, b) => a.top - b.top || b.bottom - a.bottom);

  // Grupy wzajemnie nakładających się wydarzeń; w grupie – kolumny zachłannie.
  let group: typeof items = [];
  let groupEnd = -1;
  const flush = () => {
    const columnsEnd: number[] = [];
    for (const item of group) {
      let column = columnsEnd.findIndex((end) => end <= item.top);
      if (column === -1) {
        column = columnsEnd.length;
        columnsEnd.push(item.bottom);
      } else {
        columnsEnd[column] = item.bottom;
      }
      item.column = column;
    }
    for (const item of group) item.columns = columnsEnd.length;
    group = [];
  };
  for (const item of items) {
    if (group.length && item.top >= groupEnd) flush();
    group.push(item);
    groupEnd = Math.max(groupEnd, item.bottom);
  }
  flush();
  return items;
}

const TIME = new Intl.DateTimeFormat("pl-PL", { hour: "2-digit", minute: "2-digit" });

/** Godziny wydarzenia do wyświetlenia („10:00–11:30” albo „cały dzień”). */
export function timeRange(event: CalendarEvent): string {
  if (event.all_day) return "cały dzień";
  return `${TIME.format(parseWhen(event.start))}–${TIME.format(parseWhen(event.end))}`;
}

/** Nagłówek zakresu widoku („wrzesień 2026”, „21–27 września 2026”). */
export function rangeLabel(view: "tydzien" | "miesiac" | "lista", anchor: Date): string {
  if (view === "miesiac") {
    const text = anchor.toLocaleDateString("pl-PL", { month: "long", year: "numeric" });
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
  const start = view === "tydzien" ? startOfWeek(anchor) : startOfDay(anchor);
  const end = addDays(start, view === "tydzien" ? 6 : 13);
  const sameMonth = start.getMonth() === end.getMonth();
  const left = start.toLocaleDateString("pl-PL", sameMonth ? { day: "numeric" } : { day: "numeric", month: "long" });
  const right = end.toLocaleDateString("pl-PL", { day: "numeric", month: "long", year: "numeric" });
  return `${left}–${right}`;
}

/** Zakres dat do pobrania dla widoku: [od, do). */
export function viewRange(view: "tydzien" | "miesiac" | "lista", anchor: Date): [Date, Date] {
  if (view === "miesiac") {
    const grid = monthGrid(anchor.getFullYear(), anchor.getMonth());
    return [grid[0], addDays(grid[41], 1)];
  }
  if (view === "tydzien") {
    const start = startOfWeek(anchor);
    return [start, addDays(start, 7)];
  }
  const start = startOfDay(anchor);
  return [start, addDays(start, 14)];
}
