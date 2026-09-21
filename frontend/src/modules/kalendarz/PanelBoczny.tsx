// Boczna kolumna kalendarza: co przed Tobą i poproszenie Nexusa o pomoc.
//
// Sam kalendarz odpowiada na pytanie „co jest w tym tygodniu”, ale nie na „co mam teraz
// zrobić” ani „zajmij się tym za mnie”. Wcześniej moduł był jedną tabelą na całe okno:
// żeby cokolwiek zlecić, trzeba było wrócić do czatu i opisać terminy od nowa. Ta
// kolumna trzyma jedno i drugie obok siebie — najbliższe terminy jako lista do odhaczenia
// wzrokiem i pole, w którym zlecenie idzie wprost z kontekstem dnia.

import { useMemo, useState, type FormEvent } from "react";
import { SparkIcon } from "../../components/icons";
import { calendarApi, type CalendarEvent } from "./api";
import { isoDay, parseWhen, sameDay, startOfDay, timeRange } from "./grid";

/** Ile najbliższych terminów pokazujemy — dalej lista przestaje być „co przed Tobą”. */
const ILE_TERMINOW = 8;

/** Gotowe prośby: to, o co ludzie pytają kalendarza najczęściej. */
const PODPOWIEDZI = [
  "Zaplanuj mi ten tydzień z uwzględnieniem tych terminów.",
  "Znajdź wolne dwie godziny na spotkanie w tym tygodniu.",
  "Przypomnij, do czego muszę się przygotować przed najbliższymi spotkaniami.",
];

function etykietaDnia(kiedy: Date, dzis: Date): string {
  if (sameDay(kiedy, dzis)) return "Dziś";
  if (sameDay(kiedy, new Date(dzis.getTime() + 86_400_000))) return "Jutro";
  return kiedy.toLocaleDateString("pl-PL", { weekday: "short", day: "numeric", month: "short" });
}

export function PanelBoczny({
  events,
  onEvent,
  onOtworzRozmowe,
}: {
  events: CalendarEvent[] | null;
  onEvent: (event: CalendarEvent) => void;
  onOtworzRozmowe: (conversationId: string) => void;
}) {
  const [tekst, setTekst] = useState("");
  const [zajety, setZajety] = useState(false);
  const [blad, setBlad] = useState("");

  const dzis = startOfDay(new Date());
  const najblizsze = useMemo(() => {
    if (!events) return [];
    const teraz = Date.now();
    return events
      .filter((wydarzenie) => parseWhen(wydarzenie.end ?? wydarzenie.start).getTime() >= teraz)
      .sort((a, b) => parseWhen(a.start).getTime() - parseWhen(b.start).getTime())
      .slice(0, ILE_TERMINOW);
  }, [events]);

  const zlec = async (tresc: string) => {
    if (!tresc.trim() || zajety) return;
    setZajety(true);
    setBlad("");
    try {
      const wynik = await calendarApi.plan(tresc.trim(), isoDay(dzis));
      setTekst("");
      onOtworzRozmowe(wynik.conversation_id);
    } catch (powod) {
      setBlad(powod instanceof Error ? powod.message : "Nie udało się zlecić zadania.");
    } finally {
      setZajety(false);
    }
  };

  const wyslij = (zdarzenie: FormEvent) => {
    zdarzenie.preventDefault();
    void zlec(tekst);
  };

  return (
    <aside
      aria-label="Najbliższe terminy i zlecenia"
      className="hidden w-[320px] shrink-0 flex-col gap-4 overflow-y-auto border-l border-line bg-side/40 p-4 xl:flex"
    >
      <section>
        <h2 className="text-xs font-semibold tracking-[0.08em] text-subtle uppercase">Co przed Tobą</h2>
        {najblizsze.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Nic nie czeka. Wolny kalendarz też jest wynikiem.</p>
        ) : (
          <ul className="mt-2 space-y-1">
            {najblizsze.map((wydarzenie) => {
              const kiedy = parseWhen(wydarzenie.start);
              return (
                <li key={wydarzenie.id}>
                  <button
                    type="button"
                    onClick={() => onEvent(wydarzenie)}
                    className="w-full rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-hover"
                  >
                    <span className="flex items-baseline gap-2">
                      <span className="text-xs font-medium text-accent">{etykietaDnia(kiedy, dzis)}</span>
                      <span className="text-xs text-subtle tabular-nums">{timeRange(wydarzenie)}</span>
                    </span>
                    <span className="mt-0.5 block truncate text-sm text-fg">
                      {wydarzenie.summary || "(bez tytułu)"}
                    </span>
                    {wydarzenie.location && (
                      <span className="block truncate text-xs text-subtle">{wydarzenie.location}</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="mt-auto">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold tracking-[0.08em] text-subtle uppercase">
          <SparkIcon size={14} className="text-accent" /> Zleć Nexusowi
        </h2>
        <ul className="mt-2 space-y-1">
          {PODPOWIEDZI.map((podpowiedz) => (
            <li key={podpowiedz}>
              <button
                type="button"
                disabled={zajety}
                onClick={() => void zlec(podpowiedz)}
                className="w-full rounded-lg border border-line-control px-2.5 py-2 text-left text-xs leading-relaxed text-muted transition-colors hover:bg-hover hover:text-fg disabled:opacity-60"
              >
                {podpowiedz}
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={wyslij} className="mt-2">
          <label className="sr-only" htmlFor="kalendarz-zlecenie">
            Zlecenie dla Nexusa
          </label>
          <textarea
            id="kalendarz-zlecenie"
            value={tekst}
            onChange={(zdarzenie) => setTekst(zdarzenie.target.value)}
            rows={3}
            placeholder="Napisz własnymi słowami, czym ma się zająć."
            className="w-full resize-y rounded-lg border border-line bg-app px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={!tekst.trim() || zajety}
            className="mt-2 w-full rounded-lg bg-accent-fill px-3 py-2 text-sm font-medium text-on-accent transition-colors hover:bg-accent-fill-hover disabled:opacity-50"
          >
            {zajety ? "Uruchamiam…" : "Zleć"}
          </button>
        </form>
        {blad && <p className="mt-2 text-sm text-danger">{blad}</p>}
      </section>
    </aside>
  );
}
