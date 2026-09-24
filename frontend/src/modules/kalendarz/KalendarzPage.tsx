// Moduł Kalendarz: widok tygodnia, miesiąca i listy; dodawanie i zmiana wydarzeń; prośby asystenta
// o usunięcie; „Zaplanuj z Nexusem”; instrukcja synchronizacji z telefonem (CalDAV).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PlusIcon, SparkIcon } from "../../components/icons";
import { ApiError } from "../../api";
import type { ModulePageProps } from "../registry";
import { describe } from "../_biuro/http";
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon, CopyIcon, PinIcon, SyncIcon } from "../_biuro/icons";
import { buttonClass, copyText, EmptyState, ErrorBanner, Field, inputClass, Loading, Modal, useConfirm, useToast } from "../_biuro/ui";
import { calendarApi, type CalendarEvent, type CalendarInfo, type PendingDeletion } from "./api";
import { EventDialog, type EventDraft } from "./EventDialog";
import { PanelBoczny } from "./PanelBoczny";
import {
  addDays,
  eventsOnDay,
  isoDay,
  layoutDay,
  monthGrid,
  parseWhen,
  rangeLabel,
  sameDay,
  startOfDay,
  startOfWeek,
  timeRange,
  viewRange,
} from "./grid";

type View = "tydzien" | "miesiac" | "lista";
const VIEWS: [View, string][] = [
  ["tydzien", "Tydzień"],
  ["miesiac", "Miesiąc"],
  ["lista", "Lista"],
];
const HOUR_HEIGHT = 48;
const WEEKDAYS = ["pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz."];

function initialView(): View {
  return typeof window !== "undefined" && window.matchMedia?.("(max-width: 767px)").matches ? "lista" : "tydzien";
}

export function KalendarzPage({ openConversation, openChat }: ModulePageProps) {
  const [view, setView] = useState<View>(initialView);
  const [anchor, setAnchor] = useState(() => startOfDay(new Date()));
  const [calendars, setCalendars] = useState<CalendarInfo[] | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [events, setEvents] = useState<CalendarEvent[] | null>(null);
  const [pending, setPending] = useState<PendingDeletion[]>([]);
  const [error, setError] = useState("");
  // Serwer odpowiada 503 „Kalendarz nie jest skonfigurowany (brak adresu chmury lub hasła
  // aplikacji)”. To nie jest awaria, tylko stan przed podłączeniem — a wyglądało na awarię:
  // czerwony pasek z komunikatem dla administratora nad pustą siatką tygodnia.
  const [niepodlaczony, setNiepodlaczony] = useState(false);
  const [dialog, setDialog] = useState<{ event: CalendarEvent | null; draft: EventDraft | null } | null>(null);
  const [planOpen, setPlanOpen] = useState(false);
  const [syncOpen, setSyncOpen] = useState(false);
  const [confirm, confirmDialog] = useConfirm();
  const [toast, toastNode] = useToast();
  const [from, to] = useMemo(() => viewRange(view, anchor), [view, anchor]);

  const loadEvents = useCallback(async () => {
    setError("");
    try {
      setEvents(await calendarApi.events(isoDay(from), isoDay(to)));
      setNiepodlaczony(false);
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 503) setNiepodlaczony(true);
      else setError(describe(failure));
      setEvents([]);
    }
  }, [from, to]);
  const loadPending = useCallback(() => {
    calendarApi
      .pending()
      .then(setPending)
      .catch(() => setPending([]));
  }, []);

  useEffect(() => {
    calendarApi
      .calendars()
      .then((lista) => {
        setCalendars(lista);
        setNiepodlaczony(false);
      })
      .catch((failure) => {
        if (failure instanceof ApiError && failure.status === 503) setNiepodlaczony(true);
        else setError(describe(failure));
        setCalendars([]);
      });
    loadPending();
    const timer = window.setInterval(loadPending, 30_000);
    return () => window.clearInterval(timer);
  }, [loadPending]);

  useEffect(() => {
    setEvents(null);
    loadEvents();
  }, [loadEvents]);

  const visible = useMemo(
    () => (events ?? []).filter((event) => !hidden.has(event.calendar)),
    [events, hidden],
  );

  const move = (direction: -1 | 1) => {
    if (view === "miesiac") setAnchor(new Date(anchor.getFullYear(), anchor.getMonth() + direction, 1));
    else setAnchor(addDays(anchor, direction * (view === "tydzien" ? 7 : 14)));
  };

  const decide = async (item: PendingDeletion, approve: boolean) => {
    if (approve) {
      const ok = await confirm({
        title: "Usunąć wydarzenie?",
        message: (
          <>
            Asystent prosi o usunięcie <strong>{item.payload.summary || "(bez tytułu)"}</strong> (
            {parseWhen(item.payload.start).toLocaleString("pl-PL", { dateStyle: "medium", timeStyle: item.payload.start.length > 10 ? "short" : undefined })}
            ){item.payload.recurring ? " – to seria, usunięte zostaną wszystkie wystąpienia" : ""}.
            {item.payload.reason && <span className="mt-2 block text-muted">Powód: {item.payload.reason}</span>}
          </>
        ),
        confirmLabel: "Usuń",
        danger: true,
      });
      if (!ok) return;
    }
    try {
      if (approve) await calendarApi.approve(item.id);
      else await calendarApi.reject(item.id);
      toast(approve ? "Usunięto wydarzenie" : "Wydarzenie zostaje w kalendarzu");
      loadPending();
      loadEvents();
    } catch (failure) {
      setError(describe(failure));
    }
  };

  const openEvent = (event: CalendarEvent) => setDialog({ event, draft: null });
  const newEvent = (draft: EventDraft | null = null) => setDialog({ event: null, draft: draft ?? { day: anchor } });

  if (niepodlaczony)
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center bg-app">
        {/* Tytuł strony dla czytnika ekranu: na telefonie niesie go pasek kompaktowy
            powłoki, a w stanie „niepodłączone” moduł nie rysował na komputerze żadnego
            `h1`. Wzorzec jak w gałęzi z pełnym interfejsem: ukryty poniżej `md`. */}
        <h1 className="sr-only">Kalendarz</h1>
        <EmptyState icon={<CalendarIcon size={26} />} title="Kalendarz nie jest jeszcze podłączony" szerokosc="max-w-lg" poziom={2}>
          <p>
            Terminy trzyma Twoja przestrzeń w chmurze — kalendarz pokaże je, gdy ta przestrzeń będzie gotowa.
            Na tym serwerze nie jest jeszcze przygotowana, więc nie ma też czego wyświetlić.
          </p>
          <p className="mt-3">
            Zaplanować dzień możesz mimo to: napisz Nexusowi, co Cię czeka, a ułoży plan i przypomni o terminach,
            gdy kalendarz będzie już podłączony.
          </p>
          <button
            type="button"
            className={`mt-5 ${buttonClass.primary}`}
            onClick={() => openChat("Zaplanuj mi ten tydzień — mam ")}
          >
            Zaplanuj w rozmowie
          </button>
        </EmptyState>
      </div>
    );

  return (
    <div className="flex h-full min-h-0 flex-col bg-app">
      {/* Tytuł strony na telefonie: widoczny nagłówek modułu jest ukryty poniżej `md`,
          a pasek powłoki niesie tylko etykietę. */}
      <h1 className="sr-only md:hidden">Kalendarz</h1>
      <header className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2.5 md:px-5">
        <h1 className="mr-2 hidden text-lg font-semibold md:block">Kalendarz</h1>
        <div className="flex items-center">
          <button type="button" className="icon-btn" aria-label="Poprzedni okres" onClick={() => move(-1)}>
            <ChevronLeftIcon />
          </button>
          <button type="button" className={buttonClass.ghost} onClick={() => setAnchor(startOfDay(new Date()))}>
            Dziś
          </button>
          <button type="button" className="icon-btn" aria-label="Następny okres" onClick={() => move(1)}>
            <ChevronRightIcon />
          </button>
        </div>
        <h2 className="order-first w-full truncate text-base font-semibold md:order-none md:w-auto md:min-w-0 md:flex-1">
          {rangeLabel(view, anchor)}
        </h2>
        <div className="flex rounded-xl border border-line p-0.5" role="tablist" aria-label="Widok">
          {VIEWS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={view === id}
              className={`rounded-lg px-2.5 py-1 text-sm ${view === id ? "bg-hover font-medium" : "text-muted hover:text-fg"}`}
              onClick={() => setView(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <button type="button" className="icon-btn" aria-label="Synchronizacja z telefonem" onClick={() => setSyncOpen(true)}>
          <SyncIcon />
        </button>
        <button type="button" className={buttonClass.secondary} onClick={() => setPlanOpen(true)}>
          <SparkIcon size={17} /> <span className="hidden sm:inline">Zaplanuj z Nexusem</span>
        </button>
        <button type="button" className={buttonClass.primary} onClick={() => newEvent()}>
          <PlusIcon size={18} /> <span className="hidden sm:inline">Dodaj</span>
        </button>
      </header>

      {(calendars?.length ?? 0) > 1 && (
        <div className="flex flex-wrap gap-2 border-b border-line px-3 py-2 md:px-5">
          {calendars?.map((calendar) => (
            <label key={calendar.id} className="flex cursor-pointer items-center gap-1.5 text-xs text-muted">
              <input
                type="checkbox"
                className="sr-only"
                checked={!hidden.has(calendar.id)}
                onChange={() =>
                  setHidden((current) => {
                    const next = new Set(current);
                    if (next.has(calendar.id)) next.delete(calendar.id);
                    else next.add(calendar.id);
                    return next;
                  })
                }
              />
              <span
                className="size-3 rounded-sm border-2"
                style={{ borderColor: calendar.color, background: hidden.has(calendar.id) ? "transparent" : calendar.color }}
              />
              {calendar.name}
            </label>
          ))}
        </div>
      )}

      {(pending.length > 0 || error) && (
        <div className="space-y-2 px-3 pt-3 md:px-5">
          <ErrorBanner message={error} onClose={() => setError("")} />
          {pending.map((item) => (
            <div key={item.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-accent/40 bg-accent-soft/40 px-3 py-2 text-sm">
              <SparkIcon size={17} className="text-accent" />
              <span className="min-w-0 flex-1">
                Nexus prosi o usunięcie: <strong>{item.payload.summary || "(bez tytułu)"}</strong>{" "}
                <span className="text-muted">({parseWhen(item.payload.start).toLocaleDateString("pl-PL")})</span>
              </span>
              <button type="button" className={buttonClass.ghost} onClick={() => decide(item, false)}>
                Zostaw
              </button>
              <button type="button" className={buttonClass.danger} onClick={() => decide(item, true)}>
                Usuń
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Siatka i boczna kolumna obok siebie: kalendarz mówi, co jest w tym tygodniu,
          kolumna — co przed Tobą i czym ma się zająć Nexus. Na węższym oknie kolumna
          znika, bo siatka tygodnia potrzebuje całej szerokości. */}
      <div className="flex min-h-0 flex-1">
        <div className="relative min-h-0 flex-1">
          {events === null || calendars === null ? (
            <Loading />
          ) : view === "miesiac" ? (
            <MonthView anchor={anchor} events={visible} onEvent={openEvent} onDay={(day) => newEvent({ day })} />
          ) : view === "tydzien" ? (
            <WeekView anchor={anchor} events={visible} onEvent={openEvent} onSlot={(day, hour) => newEvent({ day, hour })} />
          ) : (
            <ListView from={from} events={visible} onEvent={openEvent} />
          )}
        </div>
        <PanelBoczny events={visible} onEvent={openEvent} onOtworzRozmowe={openConversation} />
      </div>

      {dialog && (
        <EventDialog
          event={dialog.event}
          draft={dialog.draft}
          calendars={calendars ?? []}
          onClose={() => setDialog(null)}
          onSaved={(message) => {
            toast(message);
            loadEvents();
          }}
        />
      )}
      {planOpen && (
        <PlanDialog
          day={isoDay(view === "lista" ? anchor : from)}
          onClose={() => setPlanOpen(false)}
          onStarted={(conversationId) => openConversation(conversationId)}
        />
      )}
      {syncOpen && <SyncDialog onClose={() => setSyncOpen(false)} />}
      {confirmDialog}
      {toastNode}
    </div>
  );
}

function EventChip({ event, onClick }: { event: CalendarEvent; onClick: () => void }) {
  return (
    <button
      type="button"
      className="flex w-full min-w-0 items-center gap-1 truncate rounded-md px-1.5 py-0.5 text-left text-xs hover:brightness-110"
      style={{ background: `${event.color}33`, color: "var(--fg)", borderLeft: `3px solid ${event.color}` }}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      title={`${event.summary} · ${timeRange(event)}`}
    >
      {!event.all_day && <span className="shrink-0 text-muted">{timeRange(event).split("–")[0]}</span>}
      <span className="truncate">{event.summary || "(bez tytułu)"}</span>
    </button>
  );
}

function MonthView({
  anchor,
  events,
  onEvent,
  onDay,
}: {
  anchor: Date;
  events: CalendarEvent[];
  onEvent: (event: CalendarEvent) => void;
  onDay: (day: Date) => void;
}) {
  const days = monthGrid(anchor.getFullYear(), anchor.getMonth());
  const today = new Date();
  return (
    <div className="flex h-full flex-col">
      <div className="grid grid-cols-7 border-b border-line text-center text-xs text-muted">
        {WEEKDAYS.map((day) => (
          <div key={day} className="py-1.5">
            {day}
          </div>
        ))}
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-7 grid-rows-6 overflow-y-auto">
        {days.map((day) => {
          const items = eventsOnDay(events, day);
          const outside = day.getMonth() !== anchor.getMonth();
          return (
            <div
              key={day.toISOString()}
              role="button"
              tabIndex={0}
              aria-label={`Dodaj wydarzenie ${day.toLocaleDateString("pl-PL")}`}
              className={`min-h-20 cursor-pointer space-y-0.5 border-r border-b border-line/70 p-1 hover:bg-raised ${outside ? "bg-side/60" : ""}`}
              onClick={() => onDay(day)}
              onKeyDown={(e) => e.key === "Enter" && onDay(day)}
            >
              <div
                className={`mb-0.5 grid size-6 place-items-center rounded-full text-xs ${
                  sameDay(day, today) ? "bg-accent-fill font-semibold text-on-accent" : outside ? "text-muted" : ""
                }`}
              >
                {day.getDate()}
              </div>
              {items.slice(0, 3).map((event) => (
                <EventChip key={`${event.id}-${event.start}`} event={event} onClick={() => onEvent(event)} />
              ))}
              {items.length > 3 && <div className="px-1 text-[11px] text-muted">+{items.length - 3} więcej</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WeekView({
  anchor,
  events,
  onEvent,
  onSlot,
}: {
  anchor: Date;
  events: CalendarEvent[];
  onEvent: (event: CalendarEvent) => void;
  onSlot: (day: Date, hour: number) => void;
}) {
  const start = startOfWeek(anchor);
  const days = Array.from({ length: 7 }, (_, index) => addDays(start, index));
  const today = new Date();
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = HOUR_HEIGHT * 7;
  }, []);
  const now = new Date();
  const nowTop = ((now.getHours() * 60 + now.getMinutes()) / 60) * HOUR_HEIGHT;

  return (
    <div className="flex h-full min-w-0 flex-col overflow-x-auto">
      <div className="grid min-w-[720px] grid-cols-[3.5rem_repeat(7,1fr)] border-b border-line">
        <div />
        {days.map((day) => (
          <div key={day.toISOString()} className="border-l border-line/70 px-1 py-1.5 text-center">
            <div className="text-xs text-muted">{WEEKDAYS[(day.getDay() + 6) % 7]}</div>
            <div
              className={`mx-auto grid size-7 place-items-center rounded-full text-sm ${
                sameDay(day, today) ? "bg-accent-fill font-semibold text-on-accent" : ""
              }`}
            >
              {day.getDate()}
            </div>
            <div className="mt-1 space-y-0.5">
              {eventsOnDay(events, day)
                .filter((event) => event.all_day)
                .map((event) => (
                  <EventChip key={`${event.id}-${event.start}`} event={event} onClick={() => onEvent(event)} />
                ))}
            </div>
          </div>
        ))}
      </div>
      <div ref={scroller} className="min-h-0 min-w-[720px] flex-1 overflow-y-auto">
        <div className="relative grid grid-cols-[3.5rem_repeat(7,1fr)]" style={{ height: HOUR_HEIGHT * 24 }}>
          <div>
            {Array.from({ length: 24 }, (_, hour) => (
              <div key={hour} className="pr-2 text-right text-[11px] text-muted" style={{ height: HOUR_HEIGHT }}>
                {hour > 0 ? `${hour}:00` : ""}
              </div>
            ))}
          </div>
          {days.map((day) => (
            <div key={day.toISOString()} className="relative border-l border-line/70">
              {Array.from({ length: 24 }, (_, hour) => (
                <div
                  key={hour}
                  className="cursor-pointer border-b border-line/40 hover:bg-raised/60"
                  style={{ height: HOUR_HEIGHT }}
                  onClick={() => onSlot(day, hour)}
                  aria-hidden="true"
                />
              ))}
              {layoutDay(events, day).map(({ event, top, bottom, column, columns }) => (
                <button
                  key={`${event.id}-${event.start}`}
                  type="button"
                  className="absolute overflow-hidden rounded-md px-1.5 py-0.5 text-left text-xs shadow-sm hover:brightness-110"
                  style={{
                    top: (top / 60) * HOUR_HEIGHT,
                    height: Math.max(((bottom - top) / 60) * HOUR_HEIGHT - 2, 18),
                    left: `calc(${(column / columns) * 100}% + 2px)`,
                    width: `calc(${100 / columns}% - 4px)`,
                    background: `${event.color}40`,
                    borderLeft: `3px solid ${event.color}`,
                    color: "var(--fg)",
                  }}
                  onClick={() => onEvent(event)}
                  title={`${event.summary} · ${timeRange(event)}`}
                >
                  <span className="block truncate font-medium">{event.summary || "(bez tytułu)"}</span>
                  <span className="block truncate text-muted">{timeRange(event)}</span>
                </button>
              ))}
              {sameDay(day, today) && (
                <div className="pointer-events-none absolute inset-x-0 z-10 h-0.5 bg-danger" style={{ top: nowTop }} />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ListView({ from, events, onEvent }: { from: Date; events: CalendarEvent[]; onEvent: (event: CalendarEvent) => void }) {
  const days = Array.from({ length: 14 }, (_, index) => addDays(from, index))
    .map((day) => ({ day, items: eventsOnDay(events, day) }))
    .filter((entry) => entry.items.length > 0);
  if (days.length === 0)
    return (
      <EmptyState icon={<CalendarIcon size={26} />} title="Brak wydarzeń w najbliższych dwóch tygodniach">
        Dodaj wydarzenie albo poproś Nexusa: „Zaplanuj mi w tym tygodniu trzy treningi po 45 minut”.
      </EmptyState>
    );
  const today = new Date();
  return (
    <div className="h-full overflow-y-auto px-3 py-3 md:px-5">
      <div className="mx-auto max-w-3xl space-y-4">
        {days.map(({ day, items }) => (
          <section key={day.toISOString()}>
            <h3 className={`mb-1.5 text-sm font-semibold ${sameDay(day, today) ? "text-accent" : ""}`}>
              {sameDay(day, today) ? "Dziś, " : ""}
              {day.toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" })}
            </h3>
            <ul className="space-y-1.5">
              {items.map((event) => (
                <li key={`${event.id}-${event.start}`}>
                  <button
                    type="button"
                    className="flex w-full items-start gap-3 rounded-xl border border-line px-3 py-2.5 text-left hover:bg-raised"
                    onClick={() => onEvent(event)}
                  >
                    <span className="mt-1 size-2.5 shrink-0 rounded-full" style={{ background: event.color }} />
                    <span className="w-24 shrink-0 text-sm text-muted tabular-nums">{timeRange(event)}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{event.summary || "(bez tytułu)"}</span>
                      {event.location && (
                        <span className="flex items-center gap-1 truncate text-xs text-muted">
                          <PinIcon size={12} /> {event.location}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function PlanDialog({ day, onClose, onStarted }: { day: string; onClose: () => void; onStarted: (id: string) => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async () => {
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      const result = await calendarApi.plan(text.trim(), day);
      onStarted(result.conversation_id);
    } catch (failure) {
      setError(describe(failure));
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Zaplanuj z Nexusem"
      onClose={onClose}
      footer={
        <>
          <button type="button" className={buttonClass.secondary} onClick={onClose}>
            Anuluj
          </button>
          <button type="button" className={buttonClass.primary} disabled={busy || !text.trim()} onClick={submit}>
            {busy ? <span className="spinner" /> : <SparkIcon size={17} />} Zaplanuj
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-sm text-muted">
          Opisz, co chcesz zaplanować. Nexus sprawdzi Twoje terminy, dobierze wolne godziny i doda wydarzenia do kalendarza.
        </p>
        <Field label="Co zaplanować?">
          <textarea
            className={`${inputClass} min-h-28 resize-y`}
            placeholder="Np. Spotkanie z księgową w przyszłym tygodniu przed południem, 1 godzina, w biurze na Piotrkowskiej."
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </Field>
        <ErrorBanner message={error} />
      </div>
    </Modal>
  );
}

function SyncDialog({ onClose }: { onClose: () => void }) {
  const [info, setInfo] = useState<{ caldav_url: string; user: string } | null>(null);
  const [blad, setBlad] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    calendarApi
      .sync()
      .then(setInfo)
      .catch((failure) => setBlad(describe(failure)));
  }, []);
  return (
    <Modal title="Kalendarz w telefonie i na komputerze" onClose={onClose} wide>
      {blad ? (
        <ErrorBanner message={blad} />
      ) : !info ? (
        <Loading />
      ) : (
        <div className="space-y-4 text-sm">
          <div>
            <span className="block text-xs font-medium text-muted">Adres CalDAV</span>
            <div className="mt-1 flex items-center gap-2">
              <code className="min-w-0 flex-1 truncate rounded-lg bg-code px-3 py-2 font-mono text-xs">{info.caldav_url}</code>
              <button
                type="button"
                className="icon-btn"
                aria-label="Kopiuj adres CalDAV"
                onClick={() => copyText(info.caldav_url).then(() => setCopied(true))}
              >
                <CopyIcon />
              </button>
            </div>
            {copied && <span className="text-xs text-success">Skopiowano</span>}
            <p className="mt-1 text-xs text-muted">Użytkownik: {info.user} · hasło: hasło aplikacji utworzone w chmurze (Ustawienia → Bezpieczeństwo).</p>
          </div>
          <section>
            <h3 className="font-semibold">Android – DAVx⁵</h3>
            <ol className="mt-1 list-decimal space-y-1 pl-5 text-muted">
              <li>Zainstaluj aplikację Nextcloud i zaloguj się (moduł Chmura → Synchronizacja).</li>
              <li>Zainstaluj DAVx⁵ (Google Play lub F-Droid).</li>
              <li>W aplikacji Nextcloud: Ustawienia → „Synchronizuj kalendarz i kontakty” – DAVx⁵ skonfiguruje konto sam.</li>
              <li>Albo w DAVx⁵: „Zaloguj się adresem URL” → adres CalDAV powyżej, użytkownik i hasło aplikacji.</li>
              <li>Zaznacz kalendarz „Osobiste” – pojawi się w Kalendarzu Google/Samsung na telefonie.</li>
            </ol>
          </section>
          <section>
            <h3 className="font-semibold">iPhone i iPad</h3>
            <p className="mt-1 text-muted">
              Ustawienia → Kalendarz → Konta → Dodaj konto → Inne → „Dodaj konto CalDAV”: serwer {info.caldav_url.replace(/^https?:\/\//, "").split("/")[0]},
              użytkownik i hasło aplikacji.
            </p>
          </section>
          <section>
            <h3 className="font-semibold">Windows (Thunderbird, Outlook z CalDAV Synchronizer)</h3>
            <p className="mt-1 text-muted">Dodaj kalendarz sieciowy CalDAV z adresem powyżej.</p>
          </section>
          <p className="rounded-xl bg-side px-3 py-2 text-xs text-muted">
            Wydarzenia dodane przez Nexusa, w tym module i w telefonie to ten sam kalendarz – zmiany widać wszędzie po
            synchronizacji.
          </p>
        </div>
      )}
    </Modal>
  );
}
