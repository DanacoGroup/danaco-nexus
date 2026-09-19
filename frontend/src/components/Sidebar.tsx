// Panel historii rozmów: nowa rozmowa, lista, zmiana nazwy, usuwanie, wylogowanie.

import { useState } from "react";
import type { ConversationSummary } from "../api";
import { EditIcon, LogoutIcon, PlusIcon, TrashIcon } from "./icons";

interface Props {
  conversations: ConversationSummary[];
  currentId: string | null;
  username: string;
  open: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
  onClose: () => void;
}

function groupLabel(date: Date): string {
  const today = new Date();
  const days = Math.floor((today.setHours(0, 0, 0, 0) - new Date(date).setHours(0, 0, 0, 0)) / 86_400_000);
  if (days <= 0) return "Dzisiaj";
  if (days === 1) return "Wczoraj";
  if (days < 7) return "Ostatnie 7 dni";
  if (days < 30) return "Ostatnie 30 dni";
  return date.toLocaleDateString("pl-PL", { month: "long", year: "numeric" });
}

export function Sidebar(props: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
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

  return (
    <>
      <div className={`sidebar-backdrop${props.open ? " visible" : ""}`} onClick={props.onClose} />
      <aside className={`sidebar${props.open ? " open" : ""}`}>
        <div className="brand">
          <span className="brand-mark">N</span>
          <span className="brand-name">Danaco Nexus</span>
        </div>
        <button type="button" className="new-chat" onClick={props.onNew}>
          <PlusIcon size={18} /> Nowa rozmowa
        </button>
        <nav className="history" aria-label="Historia rozmów">
          {groups.map(([label, items]) => (
            <div key={label} className="history-group">
              <div className="history-label">{label}</div>
              {items.map((conversation) => (
                <div key={conversation.id} className={`history-item${conversation.id === props.currentId ? " active" : ""}`}>
                  {editing === conversation.id ? (
                    <input
                      autoFocus
                      className="rename-input"
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      onBlur={() => commit(conversation.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") commit(conversation.id);
                        if (event.key === "Escape") setEditing(null);
                      }}
                    />
                  ) : (
                    <button type="button" className="history-title" onClick={() => props.onSelect(conversation.id)} title={conversation.title}>
                      {conversation.active && <span className="spinner tiny" />}
                      <span>{conversation.title}</span>
                    </button>
                  )}
                  <div className="history-actions">
                    <button
                      type="button"
                      className="icon-button small"
                      aria-label="Zmień nazwę"
                      onClick={() => {
                        setEditing(conversation.id);
                        setDraft(conversation.title);
                      }}
                    >
                      <EditIcon size={15} />
                    </button>
                    <button
                      type="button"
                      className="icon-button small"
                      aria-label="Usuń rozmowę"
                      onClick={() => {
                        if (window.confirm(`Usunąć rozmowę „${conversation.title}” wraz z jej plikami?`)) props.onDelete(conversation.id);
                      }}
                    >
                      <TrashIcon size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ))}
          {props.conversations.length === 0 && <div className="history-empty">Brak rozmów</div>}
        </nav>
        <div className="account">
          <span className="account-avatar">{props.username.slice(0, 1).toUpperCase()}</span>
          <span className="account-name">{props.username}</span>
          <button type="button" className="icon-button" onClick={props.onLogout} aria-label="Wyloguj">
            <LogoutIcon size={18} />
          </button>
        </div>
      </aside>
    </>
  );
}
