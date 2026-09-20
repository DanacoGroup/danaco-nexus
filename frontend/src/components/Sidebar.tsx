// Panel boczny: nowa rozmowa, historia, chmura osobista, instalacja aplikacji, motyw, konto.

import { useState } from "react";
import type { ConversationSummary } from "../api";
import { usePwa } from "../pwa";
import { nextTheme, saveTheme, type ThemeChoice } from "../theme";
import {
  CloseIcon,
  EditIcon,
  InstallIcon,
  LogoutIcon,
  Logo,
  MonitorIcon,
  MoonIcon,
  PlusIcon,
  RefreshIcon,
  ShareIcon,
  SunIcon,
  TrashIcon,
} from "./icons";

interface Props {
  conversations: ConversationSummary[];
  currentId: string | null;
  username: string;
  cloudUrl: string;
  open: boolean;
  theme: ThemeChoice;
  onTheme: (theme: ThemeChoice) => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
  onClose: () => void;
}

const THEME_LABELS: Record<ThemeChoice, string> = { dark: "Motyw ciemny", light: "Motyw jasny", system: "Motyw systemu" };

function groupLabel(date: Date): string {
  const today = new Date();
  const days = Math.floor((today.setHours(0, 0, 0, 0) - new Date(date).setHours(0, 0, 0, 0)) / 86_400_000);
  if (days <= 0) return "Dzisiaj";
  if (days === 1) return "Wczoraj";
  if (days < 7) return "Ostatnie 7 dni";
  if (days < 30) return "Ostatnie 30 dni";
  return date.toLocaleDateString("pl-PL", { month: "long", year: "numeric" });
}

const navItem =
  "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-fg transition-colors hover:bg-hover";

export function Sidebar(props: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [iosHelp, setIosHelp] = useState(false);
  const pwa = usePwa();
  const groups: [string, ConversationSummary[]][] = [];
  for (const conversation of props.conversations) {
    const label = groupLabel(new Date(conversation.updated_at));
    const group = groups.find(([name]) => name === label);
    if (group) group[1].push(conversation);
    else groups.push([label, [conversation]]);
  }

  const commit = (id: string) => {
    if (draft.trim()) props.onRename(id, draft.trim());
    setEditing(null);
  };

  const ThemeIcon = props.theme === "dark" ? MoonIcon : props.theme === "light" ? SunIcon : MonitorIcon;
  const changeTheme = () => {
    const next = nextTheme(props.theme);
    saveTheme(next);
    props.onTheme(next);
  };

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-black/50 backdrop-blur-[2px] transition-opacity md:hidden ${
          props.open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={props.onClose}
      />
      <aside
        className={`safe-top fixed inset-y-0 left-0 z-40 flex w-[280px] max-w-[85vw] flex-col bg-side transition-transform duration-200 md:static md:z-auto md:translate-x-0 ${
          props.open ? "translate-x-0 shadow-2xl" : "-translate-x-full"
        }`}
        aria-label="Panel boczny"
      >
        <div className="titlebar-drag flex items-center gap-2.5 px-4 pt-3 pb-2">
          {/* Na komputerze logo jest na pasku modułów obok. */}
          <Logo size={28} className="md:hidden" />
          <span className="flex-1 text-[15px] font-semibold tracking-tight">
            <span className="md:hidden">Danaco Nexus</span>
            <span className="hidden md:inline">Rozmowy</span>
          </span>
          <button type="button" className="icon-btn md:hidden" onClick={props.onClose} aria-label="Zamknij panel">
            <CloseIcon size={18} />
          </button>
        </div>

        <div className="px-3 pb-2">
          <button
            type="button"
            onClick={props.onNew}
            className="flex w-full items-center gap-2.5 rounded-xl border border-line px-3 py-2.5 text-sm font-medium transition-colors hover:bg-hover"
          >
            <PlusIcon size={18} /> Nowa rozmowa
          </button>
        </div>

        <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-2" aria-label="Historia rozmów">
          {groups.map(([label, items]) => (
            <div key={label} className="mt-3 first:mt-1">
              <div className="px-3 pb-1 text-xs font-medium text-muted">{label}</div>
              {items.map((conversation) => {
                const active = conversation.id === props.currentId;
                return (
                  <div
                    key={conversation.id}
                    className={`group relative flex items-center rounded-lg ${active ? "bg-hover" : "hover:bg-hover/70"}`}
                  >
                    {editing === conversation.id ? (
                      <input
                        autoFocus
                        className="m-1 w-full rounded-md border border-accent bg-app px-2 py-1 text-sm outline-none"
                        value={draft}
                        onChange={(event) => setDraft(event.target.value)}
                        onBlur={() => commit(conversation.id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") commit(conversation.id);
                          if (event.key === "Escape") setEditing(null);
                        }}
                      />
                    ) : (
                      <button
                        type="button"
                        className="flex min-w-0 flex-1 items-center gap-2 px-3 py-2 text-left text-sm"
                        onClick={() => props.onSelect(conversation.id)}
                        title={conversation.title}
                      >
                        {conversation.active && <span className="spinner size-3 text-accent" />}
                        <span className="truncate">{conversation.title}</span>
                      </button>
                    )}
                    {editing !== conversation.id && (
                      <div
                        className={`absolute right-1 flex gap-0.5 rounded-md bg-hover pl-2 ${
                          active ? "flex" : "hidden group-hover:flex group-focus-within:flex"
                        } max-md:flex max-md:bg-transparent`}
                      >
                        <button
                          type="button"
                          className="icon-btn size-7"
                          aria-label="Zmień nazwę"
                          onClick={() => {
                            setEditing(conversation.id);
                            setDraft(conversation.title);
                          }}
                        >
                          <EditIcon size={14} />
                        </button>
                        <button
                          type="button"
                          className="icon-btn size-7 hover:text-danger"
                          aria-label="Usuń rozmowę"
                          onClick={() => {
                            if (window.confirm(`Usunąć rozmowę „${conversation.title}” wraz z jej plikami?`)) {
                              props.onDelete(conversation.id);
                            }
                          }}
                        >
                          <TrashIcon size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
          {props.conversations.length === 0 && <div className="px-3 py-6 text-center text-sm text-muted">Brak rozmów</div>}
        </nav>

        <div className="safe-bottom space-y-0.5 border-t border-line px-2 pt-2">
          {pwa.updateReady && (
            <button type="button" className={`${navItem} text-accent`} onClick={pwa.update}>
              <RefreshIcon size={18} /> Nowa wersja – odśwież
            </button>
          )}
          {pwa.canInstall && (
            <button type="button" className={navItem} onClick={() => void pwa.install()}>
              <InstallIcon size={18} /> Zainstaluj aplikację
            </button>
          )}
          {pwa.iosHint && (
            <button type="button" className={navItem} onClick={() => setIosHelp(!iosHelp)}>
              <InstallIcon size={18} /> Dodaj do ekranu początkowego
            </button>
          )}
          {iosHelp && (
            <p className="mx-3 mb-1 rounded-lg bg-raised p-3 text-xs leading-relaxed text-muted">
              W Safari stuknij <ShareIcon size={14} className="inline align-[-2px]" /> <b>Udostępnij</b>, a potem{" "}
              <b>Do ekranu początkowego</b>. Nexus otworzy się jak zwykła aplikacja, na pełnym ekranie.
            </p>
          )}
          <div className="flex items-center gap-2 rounded-lg px-3 py-2">
            <span className="grid size-8 place-items-center rounded-full bg-accent-fill text-sm font-semibold text-on-accent">
              {props.username.slice(0, 1).toUpperCase()}
            </span>
            <span className="flex-1 truncate text-sm font-medium">{props.username}</span>
            {/* Motyw to przełącznik, nie pozycja menu — ikona obok konta, jak zwijanie panelu. */}
            <button
              type="button"
              className="icon-btn"
              onClick={changeTheme}
              aria-label={`${THEME_LABELS[props.theme]} — zmień`}
              title={THEME_LABELS[props.theme]}
            >
              <ThemeIcon size={18} />
            </button>
            <button type="button" className="icon-btn" onClick={props.onLogout} aria-label="Wyloguj">
              <LogoutIcon size={18} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
