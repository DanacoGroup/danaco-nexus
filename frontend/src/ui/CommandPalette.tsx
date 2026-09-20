// Paleta poleceń Ctrl K (ui-kit, rozdz. 10.3): combobox + listbox z grupami,
// aria-activedescendant, tryby (> polecenia, @ pliki, # projekty, ? pomoc).

import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { EmptyState } from "./EmptyState";
import { SearchIcon, SparkleIcon } from "./Icons";
import { Kbd } from "./Kbd";
import { Spinner } from "./Progress";
import { Badge } from "./Badge";
import { cx, type BaseProps, type IconSlot, type Shortcut } from "./types";

export type CommandGroup = "files" | "conversations" | "projects" | "commands" | "tools";
export type CommandMode = "all" | "commands" | "files" | "projects" | "help";

export interface CommandItem {
  id: string;
  group: CommandGroup;
  label: string;
  description?: string;
  icon?: IconSlot;
  shortcut?: Shortcut;
  meta?: string;
  /** Trafienie po znaczeniu, nie po słowach. */
  semanticMatch?: boolean;
  preview?: () => ReactNode;
  onRun: (options: { newTab?: boolean }) => void;
}

export interface CommandPaletteProps extends BaseProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: CommandMode;
  onModeChange: (mode: CommandMode) => void;
  query: string;
  onQueryChange: (query: string) => void;
  items: CommandItem[];
  semantic?: boolean;
  onSemanticChange?: (semantic: boolean) => void;
  loading?: boolean;
  onAskAssistant: (query: string) => void;
  showPreview?: boolean;
}

const NAZWA_GRUPY: Record<CommandGroup, string> = {
  files: "Pliki",
  conversations: "Rozmowy",
  projects: "Projekty",
  commands: "Polecenia",
  tools: "Narzędzia",
};

const ZNAK_TRYBU: Record<string, CommandMode> = { ">": "commands", "@": "files", "#": "projects", "?": "help" };
const NAZWA_TRYBU: Record<CommandMode, string> = {
  all: "Wszystko",
  commands: "Polecenia",
  files: "Pliki",
  projects: "Projekty",
  help: "Pomoc",
};

export function CommandPalette({
  open,
  onOpenChange,
  mode,
  onModeChange,
  query,
  onQueryChange,
  items,
  semantic = false,
  onSemanticChange,
  loading = false,
  onAskAssistant,
  showPreview = true,
  className,
  ...reszta
}: CommandPaletteProps) {
  const id = useId();
  const okno = useRef<HTMLDialogElement>(null);
  const wejscie = useRef<HTMLInputElement>(null);
  const [aktywna, setAktywna] = useState(0);

  useEffect(() => {
    const element = okno.current;
    if (!element) return;
    if (open && !element.open) {
      if (typeof element.showModal === "function") element.showModal();
      else element.setAttribute("open", "");
      wejscie.current?.focus();
    }
    if (!open && element.open) element.close();
  }, [open]);

  useEffect(() => setAktywna(0), [query, mode, items.length]);

  const grupy = useMemo(() => {
    const mapa = new Map<CommandGroup, CommandItem[]>();
    for (const pozycja of items) {
      const lista = mapa.get(pozycja.group) ?? [];
      lista.push(pozycja);
      mapa.set(pozycja.group, lista);
    }
    return [...mapa.entries()];
  }, [items]);

  const plaska = useMemo(() => grupy.flatMap(([, lista]) => lista), [grupy]);
  const wybrana = plaska[aktywna];

  const uruchom = (pozycja: CommandItem | undefined, nowaKarta = false) => {
    if (!pozycja) return;
    pozycja.onRun({ newTab: nowaKarta });
    onOpenChange(false);
  };

  const zmianaZapytania = (wartosc: string) => {
    const tryb = ZNAK_TRYBU[wartosc.slice(0, 1)];
    if (tryb && mode === "all") {
      onModeChange(tryb);
      onQueryChange(wartosc.slice(1));
      return;
    }
    onQueryChange(wartosc);
  };

  return (
    <dialog
      ref={okno}
      className={cx("ui-okno w-full", className)}
      aria-label="Paleta poleceń"
      onCancel={(zdarzenie) => {
        zdarzenie.preventDefault();
        onOpenChange(false);
      }}
      onClick={(zdarzenie) => zdarzenie.target === okno.current && onOpenChange(false)}
      {...reszta}
    >
      <div
        className="ui-okno-panel mx-auto flex flex-col overflow-hidden rounded-xl border border-line-strong bg-raised shadow-floating"
        style={{
          inlineSize: `min(var(--layout-command), calc(100vw - var(--space-8)))`,
          marginBlockStart: "var(--space-16)",
          maxBlockSize: "calc(100vh - var(--space-24))",
        }}
      >
        <div className="flex items-center border-b border-line" style={{ padding: "0 var(--space-4)", gap: "var(--space-3)", blockSize: "var(--space-12)" }}>
          <span className="grid shrink-0 text-subtle">{loading ? <Spinner tone="ai" size="md" /> : <SearchIcon size={20} />}</span>
          {mode !== "all" ? (
            <Badge tone="accent">{NAZWA_TRYBU[mode]}</Badge>
          ) : null}
          <input
            ref={wejscie}
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-controls={`${id}-lista`}
            aria-activedescendant={wybrana ? `${id}-${wybrana.id}` : undefined}
            aria-label="Szukaj poleceń, plików i rozmów"
            autoComplete="off"
            value={query}
            placeholder="Szukaj albo wpisz polecenie"
            onChange={(zdarzenie) => zmianaZapytania(zdarzenie.target.value)}
            onKeyDown={(zdarzenie) => {
              if (zdarzenie.key === "ArrowDown") {
                zdarzenie.preventDefault();
                setAktywna((index) => (plaska.length ? (index + 1) % plaska.length : 0));
              } else if (zdarzenie.key === "ArrowUp") {
                zdarzenie.preventDefault();
                setAktywna((index) => (plaska.length ? (index - 1 + plaska.length) % plaska.length : 0));
              } else if (zdarzenie.key === "Enter") {
                zdarzenie.preventDefault();
                if (zdarzenie.ctrlKey || zdarzenie.metaKey) {
                  onAskAssistant(query);
                  onOpenChange(false);
                } else {
                  uruchom(wybrana);
                }
              } else if (zdarzenie.key === "Tab") {
                zdarzenie.preventDefault();
                const kolejnosc: CommandMode[] = ["all", "commands", "files", "projects", "help"];
                onModeChange(kolejnosc[(kolejnosc.indexOf(mode) + 1) % kolejnosc.length]!);
              } else if (zdarzenie.key === "Backspace" && !query && mode !== "all") {
                onModeChange("all");
              }
            }}
            className="h-full w-full min-w-0 bg-transparent text-fg outline-none placeholder:text-subtle"
            style={{ font: "var(--text-style-body-lg)", fontSize: "var(--font-size-lg)" }}
          />
          {onSemanticChange ? (
            <button
              type="button"
              role="switch"
              aria-checked={semantic}
              onClick={() => onSemanticChange(!semantic)}
              className={cx("ui-przejscie inline-flex shrink-0 items-center rounded-full border", semantic ? "border-accent bg-accent-soft text-accent" : "border-line text-muted")}
              style={{ blockSize: "var(--control-xs)", paddingInline: "var(--space-2)", gap: "var(--space-1)", font: "var(--text-style-caption)" }}
            >
              <SparkleIcon size={14} />
              Po znaczeniu
            </button>
          ) : null}
        </div>

        <div className="flex min-h-0 flex-1">
          <ul id={`${id}-lista`} role="listbox" aria-label="Wyniki" className="min-w-0 flex-1 overflow-auto" style={{ padding: "var(--space-2)" }}>
            {plaska.length === 0 ? (
              <li>
                <EmptyState
                  variant="no-results"
                  title={query ? `Nic nie pasuje do „${query}”` : "Zacznij pisać"}
                  description="Szukaj po nazwie albo po znaczeniu — asystent przeszuka też treść dokumentów."
                  aiAction={{ label: "Zapytaj asystenta", onSelect: () => onAskAssistant(query) }}
                />
              </li>
            ) : null}
            {grupy.map(([grupa, lista]) => (
              <li key={grupa} role="none">
                <p className="text-subtle" style={{ font: "var(--text-style-overline)", letterSpacing: "var(--font-letter-spacing-caps)", padding: "var(--space-2)" }}>
                  {NAZWA_GRUPY[grupa]}
                </p>
                <ul role="group" aria-label={NAZWA_GRUPY[grupa]}>
                  {lista.map((pozycja) => {
                    const index = plaska.indexOf(pozycja);
                    return (
                      <li
                        key={pozycja.id}
                        id={`${id}-${pozycja.id}`}
                        role="option"
                        aria-selected={index === aktywna}
                        onMouseEnter={() => setAktywna(index)}
                        onClick={() => uruchom(pozycja)}
                        className={cx("flex cursor-default items-center rounded-md", index === aktywna && "bg-hover")}
                        style={{ blockSize: "var(--control-lg)", paddingInline: "var(--space-2)", gap: "var(--space-2)" }}
                      >
                        {pozycja.icon ? <span className="grid shrink-0 text-muted">{pozycja.icon}</span> : null}
                        <span className="min-w-0 flex-1 truncate text-fg" style={{ font: "var(--text-style-body)" }}>
                          {pozycja.label}
                          {pozycja.description ? <span className="text-muted"> · {pozycja.description}</span> : null}
                        </span>
                        {pozycja.semanticMatch ? <Badge tone="ai">trafienie po znaczeniu</Badge> : null}
                        {pozycja.meta ? (
                          <span className="shrink-0 text-subtle" style={{ font: "var(--text-style-caption)" }}>
                            {pozycja.meta}
                          </span>
                        ) : null}
                        {pozycja.shortcut ? <Kbd keys={pozycja.shortcut} /> : null}
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>

          {showPreview && wybrana?.preview ? (
            <aside
              className="hidden shrink-0 overflow-auto border-s border-line lg:block"
              style={{ inlineSize: "var(--layout-panel)", padding: "var(--space-4)" }}
              aria-label="Podgląd pozycji"
            >
              {wybrana.preview()}
            </aside>
          ) : null}
        </div>

        <div
          className="flex flex-wrap items-center border-t border-line text-subtle"
          style={{ padding: "var(--space-2) var(--space-4)", gap: "var(--space-3)", font: "var(--text-style-caption)" }}
        >
          <span className="inline-flex items-center" style={{ gap: "var(--space-1)" }}>
            <Kbd keys={["↑", "↓"]} /> wybór
          </span>
          <span className="inline-flex items-center" style={{ gap: "var(--space-1)" }}>
            <Kbd keys={["⏎"]} /> otwórz
          </span>
          <span className="inline-flex items-center" style={{ gap: "var(--space-1)" }}>
            <Kbd keys={["Ctrl", "⏎"]} /> zapytaj asystenta
          </span>
          <span className="inline-flex items-center" style={{ gap: "var(--space-1)" }}>
            <Kbd keys={["Tab"]} /> tryb
          </span>
          <span className="ms-auto inline-flex items-center" style={{ gap: "var(--space-1)" }}>
            <Kbd keys={["Esc"]} /> zamknij
          </span>
        </div>
      </div>
    </dialog>
  );
}

/** Skrót Ctrl K / ⌘K otwierający paletę. */
export function useCommandPaletteShortcut(onOpen: () => void): void {
  useEffect(() => {
    const klawisz = (zdarzenie: globalThis.KeyboardEvent) => {
      if ((zdarzenie.ctrlKey || zdarzenie.metaKey) && zdarzenie.key.toLowerCase() === "k") {
        zdarzenie.preventDefault();
        onOpen();
      }
    };
    window.addEventListener("keydown", klawisz);
    return () => window.removeEventListener("keydown", klawisz);
  }, [onOpen]);
}
