// Nawigacja modułów: pionowy pasek na komputerze, dolny pasek z arkuszem „Więcej” na telefonie.

import { useEffect, useRef, useState, type ComponentType, type ReactNode, type RefObject } from "react";
import { Logo, WaveIcon } from "../components/icons";
import type { NexusModule } from "../modules/registry";
import { useOknoModalne } from "../ui/useOknoModalne";
import { ChatIcon, GridIcon, MoreIcon, type IconProps } from "./icons";
import { Menu } from "../ui/Menu";

export interface NavEntry {
  id: string;
  label: string;
  description: string;
  icon: ComponentType<IconProps>;
}

export const CHAT_ENTRY: NavEntry = {
  id: "chat",
  label: "Czat",
  description: "Rozmowy z asystentem, pliki i zadania",
  icon: ChatIcon,
};
export const VOICE_ENTRY: NavEntry = {
  id: "glos",
  label: "Głos",
  description: "Rozmowa głosowa z asystentem",
  icon: WaveIcon,
};

/** Grupy paska: piętnaście pozycji jedna pod drugą jest ścianą ikon bez podziału.
 *
 * Kolejność i przynależność idą za tym, po co człowiek sięga, a nie za tym, jak moduły
 * są zbudowane. Moduł spoza wykazu trafia na koniec — nowy moduł ma się pojawić w pasku
 * także wtedy, gdy nikt nie dopisał go tutaj.
 */
const GRUPY: Array<{ tytul: string; moduly: string[] }> = [
  { tytul: "Rozmowa", moduly: ["chat", "glos"] },
  { tytul: "Twoje rzeczy", moduly: ["pliki", "cloud", "wiedza"] },
  { tytul: "Biuro", moduly: ["poczta", "kalendarz"] },
  { tytul: "Tworzenie", moduly: ["obrazy", "studio", "strony", "tlumacz"] },
  { tytul: "Praca", moduly: ["research", "kod", "agenci", "urzadzenia"] },
  { tytul: "Nexus", moduly: ["mozliwosci", "platnosci", "ustawienia"] },
];

/** Pozycje, które na pasku komputera schodzą pod „Więcej”.
 *
 * Osiemnaście modułów nie mieści się w pasku na ekranie laptopa: cztery ostatnie stały
 * poza widokiem i trzeba było przewijać pasek, żeby w ogóle zobaczyć, że istnieją.
 * Pod kreską zostają te, po które sięga się rzadziej albo które są też gdzie indziej
 * (plan i ustawienia mieszkają również w menu konta w panelu rozmów).
 */
const POD_WIECEJ = ["agenci", "mozliwosci", "urzadzenia", "platnosci", "ustawienia"];

/** Dzieli pozycje na pasek i nadmiar pod „Więcej” (kolejność zachowana). */
export function podzialPaska(entries: NavEntry[]): { pasek: NavEntry[]; wiecej: NavEntry[] } {
  const wiecej = entries.filter((pozycja) => POD_WIECEJ.includes(pozycja.id));
  return { pasek: entries.filter((pozycja) => !POD_WIECEJ.includes(pozycja.id)), wiecej };
}

export interface GrupaNawigacji {
  tytul: string;
  pozycje: NavEntry[];
}

/** Dzieli pozycje na grupy paska; pomija grupy, z których nic nie zostało. */
export function grupyNawigacji(entries: NavEntry[]): GrupaNawigacji[] {
  const wedlugId = new Map(entries.map((pozycja) => [pozycja.id, pozycja]));
  const przypisane = new Set<string>();
  const grupy: GrupaNawigacji[] = [];
  for (const { tytul, moduly } of GRUPY) {
    const pozycje = moduly.map((id) => wedlugId.get(id)).filter((pozycja): pozycja is NavEntry => Boolean(pozycja));
    for (const pozycja of pozycje) przypisane.add(pozycja.id);
    if (pozycje.length) grupy.push({ tytul, pozycje });
  }
  const reszta = entries.filter((pozycja) => !przypisane.has(pozycja.id));
  if (reszta.length) grupy.push({ tytul: "Pozostałe", pozycje: reszta });
  return grupy;
}

export function navEntries(modules: NexusModule[]): NavEntry[] {
  return [CHAT_ENTRY, VOICE_ENTRY, ...modules.map(({ id, label, description, icon }) => ({ id, label, description, icon }))];
}

/** Pozycje dolnego paska telefonu: najwyżej 5 miejsc, nadmiar trafia do „Więcej”. */
export function splitForBottomBar(entries: NavEntry[], activeId: string, slots = 5): { bar: NavEntry[]; more: NavEntry[] } {
  if (entries.length <= slots) return { bar: entries, more: [] };
  const bar = entries.slice(0, slots - 1);
  const more = entries.slice(slots - 1);
  // Aktywny moduł z „Więcej” zajmuje ostatnie miejsce na pasku, żeby było widać, gdzie jesteśmy.
  const active = more.find((entry) => entry.id === activeId);
  if (active) bar[bar.length - 1] = active;
  return { bar, more: entries.filter((entry) => !bar.includes(entry)) };
}

interface Props {
  entries: NavEntry[];
  activeId: string;
  onSelect: (id: string) => void;
  /** Dodatkowe elementy na dole paska komputera (np. zadania w toku). */
  railFooter?: ReactNode;
  /** Czy wyszło wydanie, którego wykazu zmian nikt tu jeszcze nie otwierał. */
  noweZmiany?: boolean;
}

function useTyping(): boolean {
  // Na telefonie klawiatura ekranowa zasłania pół ekranu – dolny pasek chowa się na czas pisania.
  const [typing, setTyping] = useState(false);
  useEffect(() => {
    const isField = (target: EventTarget | null) =>
      target instanceof HTMLElement && (target.tagName === "TEXTAREA" || target.tagName === "INPUT" || target.isContentEditable);
    const onIn = (event: FocusEvent) => setTyping(isField(event.target));
    const onOut = () => setTyping(false);
    document.addEventListener("focusin", onIn);
    document.addEventListener("focusout", onOut);
    return () => {
      document.removeEventListener("focusin", onIn);
      document.removeEventListener("focusout", onOut);
    };
  }, []);
  return typing;
}


/** Czy lista modułów ma coś jeszcze nad i pod widocznym fragmentem. */
function useKrawedzie(element: RefObject<HTMLElement | null>, zaleznosc: unknown) {
  const [krawedzie, setKrawedzie] = useState({ gora: false, dol: false });
  useEffect(() => {
    const cel = element.current;
    if (!cel) return;
    const policz = () =>
      setKrawedzie({
        gora: cel.scrollTop > 4,
        dol: cel.scrollHeight - cel.scrollTop - cel.clientHeight > 4,
      });
    policz();
    cel.addEventListener("scroll", policz, { passive: true });
    const obserwator = typeof ResizeObserver === "function" ? new ResizeObserver(policz) : null;
    obserwator?.observe(cel);
    return () => {
      cel.removeEventListener("scroll", policz);
      obserwator?.disconnect();
    };
  }, [element, zaleznosc]);
  return krawedzie;
}

export function NavRail({ entries, activeId, onSelect, railFooter, noweZmiany = false }: Props) {
  const lista = useRef<HTMLDivElement>(null);
  const { pasek, wiecej } = podzialPaska(entries);
  const wiecejAktywne = wiecej.find((pozycja) => pozycja.id === activeId) ?? null;
  // Modułów jest więcej, niż mieści się na ekranie laptopa. Bez znaku, że lista sięga
  // dalej, połowa z nich wygląda na nieistniejącą — stąd cieniowanie przy krawędziach.
  const { gora, dol } = useKrawedzie(lista, entries.length);

  // Wybrany moduł ma być widoczny także wtedy, gdy trafił poza widoczny fragment listy
  // (wybór z palety poleceń, powrót pod adres modułu).
  useEffect(() => {
    const pojemnik = lista.current;
    const wybrany = pojemnik?.querySelector('[aria-current="page"]');
    if (!pojemnik || !(wybrany instanceof HTMLElement)) return;
    // Pojemnik przewijamy wprost, bo `scrollIntoView` przesuwa w przeglądarce punkt startu
    // tabulacji na wybrany moduł: pierwszy Tab omijał wtedy odsyłacz pomijający i początek
    // paska, a klawiatura nie miała jak do nich wrócić (WCAG 2.2, 2.4.3).
    const ramkaPojemnika = pojemnik.getBoundingClientRect();
    const ramkaModulu = wybrany.getBoundingClientRect();
    if (ramkaModulu.top < ramkaPojemnika.top) pojemnik.scrollTop -= ramkaPojemnika.top - ramkaModulu.top;
    else if (ramkaModulu.bottom > ramkaPojemnika.bottom) pojemnik.scrollTop += ramkaModulu.bottom - ramkaPojemnika.bottom;
  }, [activeId]);

  return (
    <nav
      aria-label="Moduły"
      // Pasek jest szerszy, bo etykiety muszą się mieścić w całości: „Narzę…” i „Kalen…”
      // nie mówią nic, a domyślanie się nazwy modułu nie jest zadaniem użytkownika.
      className="safe-top titlebar-drag relative hidden w-[88px] shrink-0 flex-col items-center border-r border-line/60 bg-side pb-3 md:flex"
    >
      {/* Znak stoi we własnym pasie oddzielonym linią — bez tego wisiał nad listą
          bez związku z nią i wyglądał na upuszczony. */}
      <div className="flex w-full items-center justify-center border-b border-line/60 py-3">
        <button type="button" onClick={() => onSelect("chat")} aria-label="Danaco Nexus – czat">
          <Logo size={32} className="rounded-xl shadow-md shadow-accent/20" />
        </button>
      </div>
      {/* Cieniowanie przypięte do samej listy, nie do paska — inaczej rozjeżdża się,
          gdy stopka paska (zadania w toku) zmienia wysokość. */}
      <div className="relative flex min-h-0 w-full flex-1 flex-col">
        {gora && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 top-0 z-10 h-6 bg-gradient-to-b from-side to-transparent"
          />
        )}
        {dol && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-6 bg-gradient-to-t from-side to-transparent"
          />
        )}
        {/* Wiersze są ciasne celowo: przy poprzednich odstępach piętnaście modułów nie mieściło
          się w oknie laptopa i cztery ostatnie stały poza widokiem — pasek „szybkiego wyboru”
          wymagał przewijania, żeby zobaczyć, co w ogóle jest. */}
        <div ref={lista} className="flex min-h-0 w-full flex-1 flex-col gap-1 overflow-y-auto px-1.5 py-1">
          {/* Grupy dzielą pasek odstępem i kreską, a nie napisem. Nagłówki tekstowe
            w pasku szerokim na 88 px trzeba było skracać do wielkich liter o wysokości
            10 px — czytało się je gorzej, niż gdyby ich nie było, a zabierały miejsce
            ikonom. Podział zostaje, czytelny dla oka; czytnik ekranu dostaje go przez
            `aria-label` grupy. */}
          {grupyNawigacji(pasek).map((grupa, numer) => (
            <div
              key={grupa.tytul}
              role="group"
              aria-label={grupa.tytul}
              className={`flex flex-col gap-0.5 ${numer > 0 ? "border-t border-line/50 pt-1.5" : ""}`}
            >
              {grupa.pozycje.map((entry) => {
                const active = entry.id === activeId;
                const EntryIcon = entry.icon;
                return (
                  <button
                    key={entry.id}
                    type="button"
                    title={entry.description}
                    aria-current={active ? "page" : undefined}
                    onClick={() => onSelect(entry.id)}
                    className={`group flex w-full flex-col items-center gap-0.5 rounded-xl px-0.5 py-1 text-[11px] font-medium transition-colors ${
                      active ? "text-accent" : "text-muted hover:text-fg"
                    }`}
                  >
                    <span
                      className={`grid h-6 w-full max-w-[52px] place-items-center rounded-lg transition-colors ${
                        active ? "bg-accent-soft" : "group-hover:bg-hover"
                      }`}
                    >
                      <EntryIcon size={18} />
                    </span>
                    <span className="max-w-full truncate leading-tight">{entry.label}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
      {wiecej.length > 0 && (
        // Menu, nie kolejne ikony: te pozycje otwiera się raz na jakiś czas, a każda
        // dodatkowa ikona w pasku odbiera miejsce tym, z których korzysta się codziennie.
        <div className="w-full border-t border-line/60 px-1.5 pt-2">
          <Menu
            align="start"
            side="top"
            label="Pozostałe moduły"
            items={wiecej.map((pozycja) => {
              const Ikona = pozycja.icon;
              return {
                id: pozycja.id,
                label: pozycja.label,
                description: pozycja.description,
                icon: <Ikona size={16} />,
                checked: pozycja.id === activeId,
                onSelect: () => onSelect(pozycja.id),
              };
            })}
            trigger={
              <button
                type="button"
                aria-current={wiecejAktywne ? "page" : undefined}
                aria-describedby={noweZmiany && !wiecejAktywne ? "nowe-zmiany" : undefined}
                className={`group relative flex w-full flex-col items-center gap-0.5 rounded-xl px-0.5 py-1 text-[11px] font-medium transition-colors ${
                  wiecejAktywne ? "text-accent" : "text-muted hover:text-fg"
                }`}
              >
                <span
                  className={`grid h-6 w-full max-w-[52px] place-items-center rounded-lg transition-colors ${
                    wiecejAktywne ? "bg-accent-soft" : "group-hover:bg-hover"
                  }`}
                >
                  {wiecejAktywne ? <wiecejAktywne.icon size={18} /> : <MoreIcon size={18} />}
                </span>
                <span className="max-w-full truncate leading-tight">
                  {wiecejAktywne ? wiecejAktywne.label : "Więcej"}
                </span>
                {/* Kropka: pod „Więcej” siedzą Ustawienia, a w nich wykaz zmian wydania.
                  Bez tego jedyną informacją o nowym wydaniu było to, że coś wygląda inaczej. */}
                {noweZmiany && !wiecejAktywne && (
                  <span
                    aria-hidden="true"
                    className="pointer-events-none absolute top-1 right-2 size-1.5 rounded-full bg-accent"
                  />
                )}
              </button>
            }
          />
        </div>
      )}
      {noweZmiany && (
        <span id="nowe-zmiany" className="sr-only">
          Nowe wydanie — wykaz zmian w Ustawieniach
        </span>
      )}
      {railFooter && <div className="flex flex-col items-center gap-1 pt-2">{railFooter}</div>}
    </nav>
  );
}

export function BottomBar({ entries, activeId, onSelect, noweZmiany = false }: Props) {
  const typing = useTyping();
  const [moreOpen, setMoreOpen] = useState(false);
  const { bar, more } = splitForBottomBar(entries, activeId);
  const item = (entry: NavEntry, active: boolean, onClick: () => void) => {
    const EntryIcon = entry.icon;
    return (
      <button
        key={entry.id}
        type="button"
        onClick={onClick}
        aria-current={active ? "page" : undefined}
        className={`flex min-w-0 flex-1 flex-col items-center gap-0.5 pt-2 pb-1 text-[11px] font-medium ${
          active ? "text-accent" : "text-muted"
        }`}
      >
        <span className={`relative grid h-7 w-12 place-items-center rounded-full ${active ? "bg-accent-soft" : ""}`}>
          <EntryIcon size={20} />
          {/* Ta sama kropka co na komputerze: pod „Więcej” są Ustawienia z wykazem zmian. */}
          {entry.id === "wiecej" && noweZmiany && !active && (
            <span aria-hidden="true" className="absolute top-0.5 right-2.5 size-1.5 rounded-full bg-accent" />
          )}
        </span>
        <span className="max-w-full truncate px-1">{entry.label}</span>
      </button>
    );
  };
  return (
    <>
      {/* Pasek chowa się na czas pisania (klawiatura ekranowa zasłania pół ekranu), ale
        arkusz musi zostać: ma na górze pole wyszukiwania, więc jego otwarcie samo w sobie
        ustawia kursor w polu tekstowym. Gdy chowanie obejmowało cały komponent, arkusz
        znikał w tej samej chwili, w której się pojawiał. */}
      {!typing && (
        <nav
          aria-label="Moduły"
          className="safe-bottom flex shrink-0 border-t border-line/70 bg-side/95 backdrop-blur md:hidden"
        >
          {bar.map((entry) => item(entry, entry.id === activeId, () => onSelect(entry.id)))}
          {more.length > 0 &&
            item({ id: "wiecej", label: "Więcej", description: "Wszystkie moduły", icon: GridIcon }, moreOpen, () =>
              setMoreOpen(true),
            )}
        </nav>
      )}
      {moreOpen && (
        <ArkuszModulow
          entries={entries}
          activeId={activeId}
          onSelect={(id) => {
            setMoreOpen(false);
            onSelect(id);
          }}
          onClose={() => setMoreOpen(false)}
        />
      )}
    </>
  );
}

/** Moduły, po które sięga się najczęściej — wiersz szybkiego wyboru na górze arkusza.
 *
 * Kolejność jest stała, a nie uczona z zachowania: lista, która przestawia się sama,
 * zmusza do czytania jej za każdym razem od nowa. Pozycje nieobecne w wykazie modułów
 * po prostu wypadają.
 */
const SZYBKI_WYBOR = ["chat", "glos", "pliki", "poczta"];

/** Pozycje pokazywane osobno, pod kreską — to nie są moduły do pracy, tylko obsługa konta. */
const NA_DOLE = ["ustawienia", "platnosci"];

function bezZnakow(tekst: string): string {
  return tekst.toLocaleLowerCase("pl-PL").normalize("NFD").replace(/\p{Diacritic}/gu, "");
}

/**
 * Arkusz „Wszystkie moduły”. Osobny komponent, bo dopiero jego montowanie i odmontowanie
 * uruchamia hak okna modalnego: Esc, tabulacja zamknięta w arkuszu i powrót fokusu
 * na przycisk „Więcej” (WCAG 2.2: 2.1.2, 2.4.3, 2.4.11).
 *
 * Nie jest siatką kafli. Osiemnaście jednakowych ikon zasłaniało trzy czwarte ekranu
 * i nie mówiło nic poza nazwą — każda pozycja wyglądała tak samo ważna. Tutaj każda
 * forma ma swoje zadanie: wyszukiwarka dla tych, którzy wiedzą, czego chcą; wiersz
 * szybkiego wyboru dla czterech rzeczy używanych codziennie; zgrupowana lista z opisem
 * dla reszty; osobny pasek na dole dla ustawień i rozliczeń, bo to nie są narzędzia
 * do pracy. Arkusz ma limit wysokości i przewija się w środku.
 */
function ArkuszModulow({
  entries,
  activeId,
  onSelect,
  onClose,
}: {
  entries: NavEntry[];
  activeId: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const arkusz = useRef<HTMLDivElement>(null);
  const [szukane, setSzukane] = useState("");
  useOknoModalne(arkusz, onClose);

  const igla = bezZnakow(szukane.trim());
  const pasuje = (pozycja: NavEntry) =>
    !igla || bezZnakow(`${pozycja.label} ${pozycja.description}`).includes(igla);

  const wedlugId = new Map(entries.map((pozycja) => [pozycja.id, pozycja]));
  const szybkie = SZYBKI_WYBOR.map((id) => wedlugId.get(id)).filter((p): p is NavEntry => Boolean(p));
  const dolne = NA_DOLE.map((id) => wedlugId.get(id)).filter((p): p is NavEntry => Boolean(p));
  const naDole = new Set(dolne.map((p) => p.id));
  const grupy = grupyNawigacji(entries.filter((p) => !naDole.has(p.id)))
    .map((grupa) => ({ ...grupa, pozycje: grupa.pozycje.filter(pasuje) }))
    .filter((grupa) => grupa.pozycje.length > 0);
  const nic = grupy.length === 0 && !dolne.some(pasuje);

  const wiersz = (pozycja: NavEntry) => {
    const EntryIcon = pozycja.icon;
    const aktywny = pozycja.id === activeId;
    return (
      <button
        key={pozycja.id}
        type="button"
        onClick={() => onSelect(pozycja.id)}
        aria-current={aktywny ? "page" : undefined}
        className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors ${
          aktywny ? "bg-accent-soft text-accent" : "text-fg hover:bg-hover"
        }`}
      >
        <EntryIcon size={20} className="shrink-0" />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{pozycja.label}</span>
          <span className="block truncate text-xs text-muted">{pozycja.description}</span>
        </span>
      </button>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/50 backdrop-blur-[2px] md:hidden" onClick={onClose}>
      <div
        ref={arkusz}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Wszystkie moduły"
        className="safe-bottom flex max-h-[78dvh] w-full animate-rise flex-col rounded-t-3xl border-t border-line bg-side"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="shrink-0 px-3 pt-2">
          <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-line-strong" />
          <input
            type="search"
            value={szukane}
            onChange={(event) => setSzukane(event.target.value)}
            placeholder="Szukaj modułu"
            aria-label="Szukaj modułu"
            className="h-10 w-full rounded-xl border border-line bg-app px-3 text-sm text-fg placeholder:text-subtle focus:border-accent focus:outline-none"
          />
          {!igla && szybkie.length > 0 && (
            <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
              {szybkie.map((pozycja) => {
                const EntryIcon = pozycja.icon;
                return (
                  <button
                    key={pozycja.id}
                    type="button"
                    onClick={() => onSelect(pozycja.id)}
                    className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium ${
                      pozycja.id === activeId
                        ? "border-accent/60 bg-accent-soft text-accent"
                        : "border-line text-fg"
                    }`}
                  >
                    <EntryIcon size={15} /> {pozycja.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-2">
          {nic && <p className="px-3 py-6 text-center text-sm text-muted">Nic takiego tu nie ma.</p>}
          {grupy.map((grupa) => (
            <div key={grupa.tytul} className="mt-3 first:mt-2">
              <div className="px-3 pb-1 text-[11px] font-medium tracking-wide text-subtle uppercase">
                {grupa.tytul}
              </div>
              {grupa.pozycje.map(wiersz)}
            </div>
          ))}
        </div>

        {dolne.filter(pasuje).length > 0 && (
          // Własne tło, nie przezroczystość: lista przewija się pod paskiem i bez tego
          // było przez niego widać kolejne pozycje, więc pasek wyglądał na część listy.
          <div className="shrink-0 border-t border-line bg-side px-3 py-2">
            {dolne.filter(pasuje).map(wiersz)}
          </div>
        )}
      </div>
    </div>
  );
}
