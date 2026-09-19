// Nawigacja modułów: pionowy pasek na komputerze, dolny pasek z arkuszem „Więcej” na telefonie.

import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import { Logo, WaveIcon } from "../components/icons";
import type { NexusModule } from "../modules/registry";
import { ChatIcon, GridIcon, type IconProps } from "./icons";

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

export function NavRail({ entries, activeId, onSelect, railFooter }: Props) {
  return (
    <nav
      aria-label="Moduły"
      className="safe-top titlebar-drag hidden w-[72px] shrink-0 flex-col items-center gap-1 border-r border-line/60 bg-side py-3 md:flex"
    >
      <button type="button" onClick={() => onSelect("chat")} aria-label="Danaco Nexus – czat" className="mb-3">
        <Logo size={34} className="rounded-xl shadow-md shadow-accent/20" />
      </button>
      <div className="flex min-h-0 w-full flex-1 flex-col items-center gap-1 overflow-y-auto px-1.5">
        {entries.map((entry) => {
          const active = entry.id === activeId;
          const EntryIcon = entry.icon;
          return (
            <button
              key={entry.id}
              type="button"
              title={entry.description}
              aria-current={active ? "page" : undefined}
              onClick={() => onSelect(entry.id)}
              className={`group flex w-full flex-col items-center gap-1 rounded-xl py-2 text-[11px] font-medium transition-colors ${
                active ? "text-fg" : "text-muted hover:text-fg"
              }`}
            >
              <span
                className={`grid size-10 place-items-center rounded-xl transition-colors ${
                  active ? "bg-accent-soft text-accent" : "group-hover:bg-hover"
                }`}
              >
                <EntryIcon size={21} />
              </span>
              <span className="max-w-full truncate px-0.5">{entry.label}</span>
            </button>
          );
        })}
      </div>
      {railFooter && <div className="flex flex-col items-center gap-1 pt-2">{railFooter}</div>}
    </nav>
  );
}

export function BottomBar({ entries, activeId, onSelect }: Props) {
  const typing = useTyping();
  const [moreOpen, setMoreOpen] = useState(false);
  const { bar, more } = splitForBottomBar(entries, activeId);
  if (typing) return null;
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
        <span className={`grid h-7 w-12 place-items-center rounded-full ${active ? "bg-accent-soft" : ""}`}>
          <EntryIcon size={20} />
        </span>
        <span className="max-w-full truncate px-1">{entry.label}</span>
      </button>
    );
  };
  return (
    <>
      <nav aria-label="Moduły" className="safe-bottom flex shrink-0 border-t border-line/70 bg-side/95 backdrop-blur md:hidden">
        {bar.map((entry) => item(entry, entry.id === activeId, () => onSelect(entry.id)))}
        {more.length > 0 &&
          item({ id: "wiecej", label: "Więcej", description: "Wszystkie moduły", icon: GridIcon }, moreOpen, () =>
            setMoreOpen(true),
          )}
      </nav>
      {moreOpen && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/50 backdrop-blur-[2px] md:hidden" onClick={() => setMoreOpen(false)}>
          <div
            role="dialog"
            aria-label="Wszystkie moduły"
            className="safe-bottom w-full animate-rise rounded-t-3xl border-t border-line bg-side px-3 pt-2"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-line-strong" />
            <div className="grid grid-cols-3 gap-2 pb-3">
              {entries.map((entry) => {
                const EntryIcon = entry.icon;
                const active = entry.id === activeId;
                return (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => {
                      setMoreOpen(false);
                      onSelect(entry.id);
                    }}
                    className={`flex flex-col items-center gap-1.5 rounded-2xl border px-2 py-3 text-xs font-medium ${
                      active ? "border-accent/60 bg-accent-soft text-accent" : "border-line text-fg"
                    }`}
                  >
                    <EntryIcon size={22} />
                    <span className="max-w-full truncate">{entry.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
