// Paleta poleceń (Ctrl K): moduły, rozmowy i działania powłoki w jednym polu.
// Zasada „klawiatura jest pierwszym wskaźnikiem” — design-system/DESIGN_SYSTEM.md, rozdz. 2.

import { useMemo, useState } from "react";
import type { ConversationSummary } from "../api";
import { SparkIcon, SunIcon } from "../components/icons";
import { ChatIcon } from "./icons";
import { CommandPalette, useCommandPaletteShortcut, type CommandItem, type CommandMode } from "../ui";
import { bezZnakow, type NavEntry } from "./ModuleNav";

interface Props {
  entries: NavEntry[];
  conversations: ConversationSummary[];
  onSelectEntry: (id: string) => void;
  onOpenConversation: (id: string) => void;
  onNewConversation: () => void;
  onToggleTheme: () => void;
  /** Zapytanie, na które nie ma polecenia — trafia do pola wiadomości. */
  onAsk: (query: string) => void;
}

export function Paleta({
  entries,
  conversations,
  onSelectEntry,
  onOpenConversation,
  onNewConversation,
  onToggleTheme,
  onAsk,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<CommandMode>("all");
  useCommandPaletteShortcut(() => setOpen(true));

  const items = useMemo<CommandItem[]>(() => {
    const zamknij = (praca: () => void) => () => {
      setOpen(false);
      praca();
    };
    const polecenia: CommandItem[] = [
      {
        id: "nowa-rozmowa",
        group: "commands",
        label: "Nowa rozmowa",
        icon: <ChatIcon size={16} />,
        shortcut: ["Ctrl", "N"],
        onRun: zamknij(onNewConversation),
      },
      {
        id: "motyw",
        group: "commands",
        label: "Zmień motyw",
        description: "Ciemny, jasny, zgodny z systemem",
        icon: <SunIcon size={16} />,
        onRun: zamknij(onToggleTheme),
      },
      ...entries.map((entry) => ({
        id: `moduł-${entry.id}`,
        group: "commands" as const,
        label: entry.label,
        description: entry.description,
        icon: <entry.icon size={16} />,
        onRun: zamknij(() => onSelectEntry(entry.id)),
      })),
    ];
    const rozmowy: CommandItem[] = conversations.slice(0, 20).map((rozmowa) => ({
      id: `rozmowa-${rozmowa.id}`,
      group: "conversations",
      label: rozmowa.title || "Rozmowa bez tytułu",
      meta: rozmowa.active ? "w toku" : undefined,
      icon: <SparkIcon size={16} />,
      onRun: zamknij(() => onOpenConversation(rozmowa.id)),
    }));
    return [...polecenia, ...rozmowy];
  }, [entries, conversations, onSelectEntry, onOpenConversation, onNewConversation, onToggleTheme]);

  // `CommandPalette` pokazuje to, co dostanie — zawężanie listy należy do tego, kto ją składa.
  const widoczne = useMemo(() => {
    const igla = bezZnakow(query.trim());
    if (!igla) return items;
    return items.filter((pozycja) => bezZnakow(`${pozycja.label} ${pozycja.description ?? ""}`).includes(igla));
  }, [items, query]);

  return (
    <CommandPalette
      open={open}
      onOpenChange={setOpen}
      mode={mode}
      onModeChange={setMode}
      query={query}
      onQueryChange={setQuery}
      items={widoczne}
      onAskAssistant={(pytanie) => {
        setOpen(false);
        setQuery("");
        onAsk(pytanie);
      }}
    />
  );
}
