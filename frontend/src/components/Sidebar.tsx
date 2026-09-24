// Panel boczny: nowa rozmowa, historia, chmura osobista, instalacja aplikacji, motyw, konto.

import { useState } from "react";
import type { ConversationSummary } from "../api";
import { usePwa } from "../pwa";
import { CardIcon, MoreIcon, PanelIcon, SearchIcon, SettingsIcon } from "../shell/icons";
import { PasekDostepu } from "../platnosci/PasekDostepu";
import { nextTheme, saveTheme, type ThemeChoice } from "../theme";
import {
  ChevronIcon,
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
  /** Zwija panel rozmów na komputerze — zostaje sam pasek modułów i okno rozmowy. */
  onZwin: () => void;
  /** Czy panel jest zwinięty (dotyczy wyłącznie układu na komputerze). */
  zwiniety: boolean;
  /** Otwiera moduł Ustawienia; brak = pozycja nie pojawia się w menu. */
  onUstawienia?: () => void;
  /** Otwiera plan i stan dostępu; brak = pozycja nie pojawia się w menu. */
  onDostep?: () => void;
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

/** Pozycja menu konta: ikona, nazwa, całe pole klikalne. */
const pozycjaMenu =
  "flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-fg transition-colors hover:bg-hover";

const navItem =
  "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-fg transition-colors hover:bg-hover";

export function Sidebar(props: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [iosHelp, setIosHelp] = useState(false);
  const [kontoOtwarte, setKontoOtwarte] = useState(false);
  const pwa = usePwa();
  const [szukane, setSzukane] = useState("");
  const [menuOtwarte, setMenuOtwarte] = useState(false);
  // Szukamy bez znaków diakrytycznych i wielkości liter: „umowa” ma znaleźć „Umowę”.
  const igla = szukane.trim().toLocaleLowerCase("pl-PL");
  const widoczne = igla
    ? props.conversations.filter((rozmowa) => rozmowa.title.toLocaleLowerCase("pl-PL").includes(igla))
    : props.conversations;
  const groups: [string, ConversationSummary[]][] = [];
  for (const conversation of widoczne) {
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
        // Zwinięty panel znika z układu na komputerze (`md:hidden`), a na telefonie
        // zachowuje się jak dotąd — tam wysuwa się przyciskiem i nie ma czego zwijać.
        //
        // Schowany na telefonie panel dostaje `invisible`, a nie samo przesunięcie za
        // krawędź: przesunięty panel dalej stoi w kolejności tabulacji i w drzewie
        // dostępności. Pomiar na ekranie 390 px pokazał pięć takich kontrolek — „Zamknij
        // panel”, pole szukania, „Nowa rozmowa”, „Więcej działań” i przycisk konta —
        // czyli klawiatura i czytnik ekranu trafiały w coś, czego nie widać.
        // `visibility` zmienia się skokowo dopiero na koniec przejścia, więc wysuwanie
        // i chowanie wygląda tak samo jak dotąd; na komputerze (`md:visible`) panel jest
        // widoczny zawsze, bo tam nie ma go czym wysuwać.
        className={`safe-top fixed inset-y-0 left-0 z-40 flex w-[280px] max-w-[85vw] flex-col bg-side transition-[transform,visibility] duration-200 md:visible md:static md:z-auto md:translate-x-0 ${
          props.open ? "translate-x-0 shadow-2xl" : "invisible -translate-x-full"
        } ${props.zwiniety ? "md:hidden" : "md:flex"}`}
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
          {/* Na komputerze panel się zwija, a nie zamyka: rozmowy zostają pod ręką
              w pasku, a okno rozmowy dostaje całą szerokość. */}
          <button
            type="button"
            className="icon-btn z-etykieta hidden md:inline-grid"
            data-etykieta="Zwiń panel rozmów"
            data-strona="lewo"
            onClick={props.onZwin}
            aria-label="Zwiń panel rozmów"
          >
            <PanelIcon size={18} />
          </button>
        </div>

        {/* Pasek narzędzi panelu: szukanie zajmuje miejsce, bo przy kilkudziesięciu
            rozmowach to ono jest codzienną czynnością; nowa rozmowa i menu są ikonami.
            Wcześniej „Nowa rozmowa” było szerokim polem i myliło się z wyszukiwarką. */}
        <div className="flex items-center gap-1.5 px-3 pb-2">
          <label className="relative min-w-0 flex-1">
            <span className="sr-only">Szukaj w rozmowach</span>
            <SearchIcon size={15} className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-subtle" />
            <input
              value={szukane}
              onChange={(zdarzenie) => setSzukane(zdarzenie.target.value)}
              // Krótsza podpowiedź i margines z prawej: pełne „Szukaj w rozmowach” zajmowało
              // pole co do piksela i przy wąskim panelu wyglądało na ucięte.
              placeholder="Szukaj rozmowy"
              className="h-9 w-full rounded-lg border border-line bg-app pr-2.5 pl-8 text-sm text-fg outline-none transition-colors focus:border-accent"
            />
          </label>
          <button
            type="button"
            onClick={props.onNew}
            className="icon-btn z-etykieta size-9 shrink-0 rounded-lg border border-line"
            data-etykieta="Nowa rozmowa"
            data-strona="lewo"
            aria-label="Nowa rozmowa"
          >
            <PlusIcon size={18} />
          </button>
          <div className="relative shrink-0">
            <button
              type="button"
              onClick={() => setMenuOtwarte((otwarte) => !otwarte)}
              className="icon-btn z-etykieta size-9 rounded-lg"
              data-etykieta="Więcej"
              data-strona="lewo"
              aria-haspopup="menu"
              aria-expanded={menuOtwarte}
              aria-label="Więcej działań"
            >
              <MoreIcon size={18} />
            </button>
            {menuOtwarte && (
              <div
                role="menu"
                className="absolute top-full right-0 z-20 mt-1 w-56 rounded-xl border border-line bg-raised p-1 shadow-[var(--shadow-floating)]"
              >
                {/* To menu dotyczy panelu rozmów, nie konta. Ustawienia i wylogowanie
                  stoją w menu konta na dole — powtarzanie ich tutaj kazało zgadywać,
                  czym te dwa menu się różnią. */}
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOtwarte(false);
                    props.onZwin();
                  }}
                  className={`${navItem} hidden md:flex`}
                >
                  <PanelIcon size={16} /> Zwiń panel rozmów
                </button>
              </div>
            )}
          </div>
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
          {widoczne.length === 0 && (
            // Bez nagrania stanu: ujęcia z pakietu są pełnoklatkowe (1920 × 1080) i w pasku
            // szerokim na 112 px czytają się jak ciemny prostokąt — gorzej niż sam napis.
            <div className="px-3 py-6 text-center text-sm text-muted">
              {igla ? `Nic nie pasuje do „${szukane.trim()}”.` : "Brak rozmów"}
            </div>
          )}
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
          {/* Konto jest wejściem do wszystkiego, co dotyczy „mnie”: ustawień, wyglądu,
            stanu dostępu, rozliczeń i wyjścia. Wcześniej stały tu dwie ikony bez nazwy
            i nic poza nimi — reszta była rozsypana po modułach albo nie było jej wcale. */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setKontoOtwarte((stan) => !stan)}
              aria-expanded={kontoOtwarte}
              aria-haspopup="menu"
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-hover"
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-fill text-sm font-semibold text-on-accent">
                {props.username.slice(0, 1).toUpperCase()}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{props.username}</span>
                <span className="block truncate text-xs text-muted">Konto, plan i ustawienia</span>
              </span>
              <ChevronIcon size={16} className={`shrink-0 text-muted transition-transform ${kontoOtwarte ? "rotate-180" : ""}`} />
            </button>
            {kontoOtwarte && (
              <div
                role="menu"
                className="absolute bottom-full left-2 z-20 mb-1 w-[calc(100%-1rem)] overflow-hidden rounded-xl border border-line bg-raised shadow-lg"
              >
                {props.onUstawienia && (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setKontoOtwarte(false);
                      props.onUstawienia?.();
                    }}
                    className={pozycjaMenu}
                  >
                    <SettingsIcon size={16} /> Ustawienia
                  </button>
                )}
                {props.onDostep && (
                  <>
                    {/* Stan dostępu wprost w menu: żeby go sprawdzić, nie trzeba wychodzić
                      z rozmowy do modułu Płatności. Pasek bez liczb, jak wszędzie indziej. */}
                    <div className="border-b border-line/60">
                      <PasekDostepu onOtworz={() => {
                        setKontoOtwarte(false);
                        props.onDostep?.();
                      }} />
                    </div>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setKontoOtwarte(false);
                        props.onDostep?.();
                      }}
                      className={pozycjaMenu}
                    >
                      <CardIcon size={16} /> Plan i dostęp
                    </button>
                  </>
                )}
                {/* Motyw zostaje przełącznikiem: jedno kliknięcie zmienia wygląd i mówi,
                  co jest ustawione teraz — bez schodzenia do osobnego ekranu. */}
                <button type="button" role="menuitem" onClick={changeTheme} className={pozycjaMenu}>
                  <ThemeIcon size={16} /> {THEME_LABELS[props.theme]}
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setKontoOtwarte(false);
                    props.onLogout();
                  }}
                  className={`${pozycjaMenu} border-t border-line/60 text-danger`}
                >
                  <LogoutIcon size={16} /> Wyloguj
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
