// Okno wydarzenia: dodawanie, zmiana i usuwanie (po potwierdzeniu).

import { useState } from "react";
import { TrashIcon } from "../../components/icons";
import { describe } from "../_biuro/http";
import { buttonClass, ErrorBanner, Field, inputClass, Modal, useConfirm } from "../_biuro/ui";
import { calendarApi, type CalendarEvent, type CalendarInfo, type EventInput } from "./api";
import { addDays, isoDay, parseWhen, timeRange } from "./grid";

const REMINDERS: [string, number][] = [
  ["Bez przypomnienia", 0],
  ["5 minut przed", 5],
  ["15 minut przed", 15],
  ["30 minut przed", 30],
  ["1 godzinę przed", 60],
  ["1 dzień przed", 1440],
];
const REPEATS: [string, string][] = [
  ["Nie powtarzaj", ""],
  ["Codziennie", "FREQ=DAILY"],
  ["Co tydzień", "FREQ=WEEKLY"],
  ["W dni robocze", "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"],
  ["Co miesiąc", "FREQ=MONTHLY"],
  ["Co rok", "FREQ=YEARLY"],
];

function hhmm(date: Date): string {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export interface EventDraft {
  day: Date;
  hour?: number;
}

/** Wartości formularza dla nowego albo istniejącego wydarzenia. */
export function initialForm(event: CalendarEvent | null, draft: EventDraft | null) {
  if (event) {
    const start = parseWhen(event.start);
    const end = parseWhen(event.end);
    const lastDay = event.all_day ? addDays(end, -1) : end;
    return {
      summary: event.summary,
      allDay: event.all_day,
      startDate: isoDay(start),
      startTime: event.all_day ? "09:00" : hhmm(start),
      endDate: isoDay(lastDay < start ? start : lastDay),
      endTime: event.all_day ? "10:00" : hhmm(end),
      location: event.location,
      description: event.description,
    };
  }
  const day = draft?.day ?? new Date();
  const hour = draft?.hour ?? 9;
  return {
    summary: "",
    allDay: false,
    startDate: isoDay(day),
    startTime: `${String(hour).padStart(2, "0")}:00`,
    endDate: isoDay(day),
    endTime: `${String(Math.min(hour + 1, 23)).padStart(2, "0")}:${hour + 1 > 23 ? "59" : "00"}`,
    location: "",
    description: "",
  };
}

/** Zamiana pól formularza na dane API (koniec całodniowego – dzień po ostatnim dniu). */
export function formToInput(form: ReturnType<typeof initialForm>): Pick<EventInput, "summary" | "start" | "end" | "all_day" | "location" | "description"> {
  if (form.allDay) {
    const [year, month, day] = form.endDate.split("-").map(Number);
    return {
      summary: form.summary.trim(),
      start: form.startDate,
      end: isoDay(addDays(new Date(year, month - 1, day), 1)),
      all_day: true,
      location: form.location,
      description: form.description,
    };
  }
  return {
    summary: form.summary.trim(),
    start: `${form.startDate}T${form.startTime}`,
    end: `${form.endDate}T${form.endTime}`,
    all_day: false,
    location: form.location,
    description: form.description,
  };
}

export function EventDialog({
  event,
  draft,
  calendars,
  onClose,
  onSaved,
}: {
  event: CalendarEvent | null;
  draft: EventDraft | null;
  calendars: CalendarInfo[];
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const writableCalendars = calendars.filter((calendar) => calendar.writable);
  const [form, setForm] = useState(() => initialForm(event, draft));
  const [calendar, setCalendar] = useState(
    () => writableCalendars.find((item) => item.default)?.id ?? writableCalendars[0]?.id ?? "",
  );
  // „keep” – bez zmian (edycja); liczba – minuty przed początkiem (0 = bez przypomnienia).
  const [reminder, setReminder] = useState(event ? "keep" : "15");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, confirmDialog] = useConfirm();
  const readOnly = event !== null && !event.writable;
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((current) => ({ ...current, [key]: value }));

  const save = async () => {
    if (!form.summary.trim()) {
      setError("Podaj tytuł wydarzenia.");
      return;
    }
    const input = formToInput(form);
    if (input.end && parseWhen(input.end) < parseWhen(input.start)) {
      setError("Koniec nie może być wcześniej niż początek.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (event) {
        await calendarApi.update(event.id, {
          ...input,
          ...(reminder !== "keep" ? { reminder_minutes: Number(reminder) } : {}),
          etag: event.recurring ? undefined : event.etag,
          recurrence_id: event.recurrence_id,
        });
        onSaved("Zapisano zmiany");
      } else {
        await calendarApi.create({ ...input, calendar, reminder_minutes: Number(reminder), rrule: repeat });
        onSaved("Dodano wydarzenie");
      }
      onClose();
    } catch (failure) {
      setError(describe(failure));
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!event) return;
    const ok = await confirm({
      title: "Usunąć wydarzenie?",
      message: event.recurring ? (
        <>
          <strong>{event.summary}</strong> to wydarzenie cykliczne – usunięta zostanie cała seria. Wydarzenie trafi do kosza
          kalendarza w chmurze.
        </>
      ) : (
        <>
          <strong>{event.summary}</strong> ({timeRange(event)}) zostanie usunięte z kalendarza.
        </>
      ),
      confirmLabel: "Usuń",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await calendarApi.remove(event.id);
      onSaved("Usunięto wydarzenie");
      onClose();
    } catch (failure) {
      setError(describe(failure));
      setBusy(false);
    }
  };

  return (
    <>
      <Modal
        title={event ? (readOnly ? event.summary || "Wydarzenie" : "Wydarzenie") : "Nowe wydarzenie"}
        onClose={onClose}
        wide
        footer={
          readOnly ? (
            <button type="button" className={buttonClass.secondary} onClick={onClose}>
              Zamknij
            </button>
          ) : (
            <>
              {event && (
                <button type="button" className={`${buttonClass.ghost} mr-auto text-danger`} disabled={busy} onClick={remove}>
                  <TrashIcon size={17} /> Usuń
                </button>
              )}
              <button type="button" className={buttonClass.secondary} onClick={onClose}>
                Anuluj
              </button>
              <button type="button" className={buttonClass.primary} disabled={busy} onClick={save}>
                {busy && <span className="spinner" />} {event ? "Zapisz" : "Dodaj"}
              </button>
            </>
          )
        }
      >
        <fieldset disabled={readOnly} className="space-y-3">
          {readOnly && <p className="text-sm text-muted">Kalendarz „{event?.calendar_name}” jest tylko do odczytu.</p>}
          <Field label="Tytuł">
            <input className={inputClass} value={form.summary} maxLength={300} onChange={(e) => set("summary", e.target.value)} />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.allDay} onChange={(e) => set("allDay", e.target.checked)} />
            Cały dzień
          </label>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Początek">
              <input
                className={inputClass}
                type="date"
                value={form.startDate}
                onChange={(e) => {
                  const value = e.target.value;
                  setForm((current) => ({ ...current, startDate: value, endDate: current.endDate < value ? value : current.endDate }));
                }}
              />
            </Field>
            {!form.allDay ? (
              <Field label="Godzina">
                <input className={inputClass} type="time" value={form.startTime} onChange={(e) => set("startTime", e.target.value)} />
              </Field>
            ) : (
              <span />
            )}
            <Field label="Koniec">
              <input className={inputClass} type="date" min={form.startDate} value={form.endDate} onChange={(e) => set("endDate", e.target.value)} />
            </Field>
            {!form.allDay ? (
              <Field label="Godzina">
                <input className={inputClass} type="time" value={form.endTime} onChange={(e) => set("endTime", e.target.value)} />
              </Field>
            ) : (
              <span />
            )}
          </div>
          {event?.recurring && (
            <p className="rounded-xl bg-accent-soft/50 px-3 py-2 text-xs">
              Wydarzenie cykliczne – zmiany dotyczą całej serii (zmiana godziny przesuwa wszystkie wystąpienia).
            </p>
          )}
          <Field label="Miejsce">
            <input className={inputClass} value={form.location} onChange={(e) => set("location", e.target.value)} />
          </Field>
          <Field label="Opis">
            <textarea className={`${inputClass} min-h-20 resize-y`} value={form.description} onChange={(e) => set("description", e.target.value)} />
          </Field>
          {!readOnly && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Przypomnienie">
                <select className={inputClass} value={reminder} onChange={(e) => setReminder(e.target.value)}>
                  {event && <option value="keep">Bez zmian</option>}
                  {REMINDERS.map(([label, value]) => (
                    <option key={label} value={String(value)}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              {!event ? (
                <Field label="Powtarzanie">
                  <select className={inputClass} value={repeat} onChange={(e) => setRepeat(e.target.value)}>
                    {REPEATS.map(([label, value]) => (
                      <option key={label} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </Field>
              ) : null}
              {!event && writableCalendars.length > 1 && (
                <Field label="Kalendarz">
                  <select className={inputClass} value={calendar} onChange={(e) => setCalendar(e.target.value)}>
                    {writableCalendars.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
            </div>
          )}
          <ErrorBanner message={error} />
        </fieldset>
      </Modal>
      {confirmDialog}
    </>
  );
}
