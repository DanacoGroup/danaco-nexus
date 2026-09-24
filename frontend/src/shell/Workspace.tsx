// Powłoka zalogowanej aplikacji: nawigacja modułów, czat z historią rozmów, rozmowa głosowa,
// zadania w toku (wiele sesji naraz) i strony modułów (/m/<id>).

import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { api, type AssistantTurn, type FileInfo, type VoiceConfig } from "../api";
import { Composer } from "../components/Composer";
import { CloseIcon, Logo, MenuIcon, PaperclipIcon, PlusIcon } from "../components/icons";
import { PreviewModal } from "../components/PreviewModal";
import { Sidebar } from "../components/Sidebar";
import { AssistantMessage, UserMessage } from "../components/Turns";
import { findModule, MODULES } from "../modules/registry";
import { BrakKredytow } from "../platnosci/BrakKredytow";
import { takeSharedContent } from "../share";
import { ObszarOgloszen } from "../ui/ObszarOgloszen";
import { applyTheme, nextTheme, saveTheme, storedTheme, type ThemeChoice } from "../theme";
import { useEscZatrzymaj } from "./useEscZatrzymaj";
import { unlockAudio } from "../voice/player";
import { VoiceMode } from "../voice/VoiceMode";
import { ArrowRightIcon, PanelIcon } from "./icons";
import { BottomBar, NavRail, navEntries } from "./ModuleNav";
import { NagranieStanu, NagranieStartu, ograniczonyRuch, PrzejscieWidoku, ZnakRuchu } from "../ruch";
import { useNieprzeczytaneNowosci } from "../nowosci";
import { BezPolaczenia } from "./BezPolaczenia";
import { EkranWylogowania } from "./EkranWylogowania";
import { Paleta } from "./Paleta";
import { PasekAktualizacji } from "./PasekAktualizacji";
import { PasekPlanu } from "../platnosci/PasekPlanu";
import { PasekKontaProbnego } from "./PasekKontaProbnego";
import { SCIEZKA, type Route } from "./route";
import { TasksButton, TasksPanel, useActiveTasks } from "./TasksPanel";
import { Toasts, type Toast } from "./Toasts";
import { displayTurn } from "./turnDisplay";
import { useChat } from "./useChat";

// Podpowiedzi na pustym czacie: krótki tytuł mówi, co z tego będzie, a zdanie pod nim
// jest gotowym poleceniem, które trafia do pola wiadomości. Tytuł to nazwa rezultatu
// („Logo firmy”), nie polecenie dla maszyny — człowiek wybiera wzrokiem po tym, czego
// chce, a nie po czasowniku. Osiem pozycji dotyka ośmiu różnych dziedzin rejestru.
interface Podpowiedz {
  /** Nazwa rezultatu — to, co użytkownik dostanie. */
  tytul: string;
  /** Jedno zdanie o tym, co się wydarzy; ton jak w rozmowie, nie jak w instrukcji. */
  opis: string;
  /** Treść wstawiana do pola wiadomości po kliknięciu. */
  polecenie: string;
}

const SUGGESTIONS: Podpowiedz[] = [
  {
    tytul: "Logo firmy",
    opis: "Znak i nazwa w wersji ciemnej i jasnej, z plikiem do druku.",
    polecenie:
      "Zaprojektuj logo dla mojej firmy — znak i nazwa, w wersji na ciemnym i jasnym tle. " +
      "Przygotuj plik do sieci i osobno do druku.",
  },
  {
    tytul: "Odnowione zdjęcie",
    opis: "Wyblakłe i krzywo zeskanowane wraca do formy.",
    polecenie:
      "To zdjęcie jest wyblakłe i krzywo zeskanowane. Wyprostuj je, popraw kolory " +
      "i przygotuj wersję nadającą się do powiększenia.",
  },
  {
    tytul: "Uporządkowane dokumenty",
    opis: "Jeden plik ze skanami rozdzielony na osobne, nazwane sprawy.",
    polecenie:
      "W tym pliku jest kilka dokumentów zeskanowanych jeden po drugim. Rozdziel je na osobne " +
      "pliki, rozpoznaj tekst i nazwij każdy zgodnie z tym, czego dotyczy.",
  },
  {
    tytul: "Pismo na podstawie akt",
    opis: "Nexus czyta dokumenty i pisze z nich gotowe pismo.",
    polecenie:
      "Przeczytaj te dokumenty i napisz na ich podstawie pismo do ubezpieczyciela. " +
      "Chcę je dostać w Wordzie, gotowe do podpisu.",
  },
  {
    tytul: "Zaległa poczta",
    opis: "Odpowiedzi przygotowane, terminy wpisane do kalendarza.",
    polecenie:
      "Sprawdź, na które wiadomości nie odpisałem w tym tygodniu. Przygotuj odpowiedzi " +
      "do zatwierdzenia, a terminy, które się w nich pojawią, wpisz do kalendarza.",
  },
  {
    tytul: "Notatka ze spotkania",
    opis: "Z nagrania powstają ustalenia i lista zadań.",
    polecenie:
      "Z tego nagrania ze spotkania zrób notatkę: o czym była mowa, co zostało ustalone " +
      "i kto się czym zajmuje.",
  },
  {
    tytul: "Raport ze źródłami",
    opis: "Rzetelna odpowiedź z przypisami, nie luźna opinia.",
    polecenie:
      "Zastanawiam się nad pompą ciepła w domu z lat dziewięćdziesiątych. Sprawdź, czy to ma sens, " +
      "i napisz raport z odnośnikami do źródeł.",
  },
  {
    tytul: "Strona firmy",
    opis: "Wizytówka zbudowana i opublikowana pod Twoim adresem.",
    polecenie:
      "Zrób jednostronicową wizytówkę mojej firmy — kontakt, oferta, zdjęcia — " +
      "i po mojej akceptacji opublikuj ją pod moim adresem.",
  },
  {
    // Serwer ma biblioteki materiałów (tła WebGL, ilustracje, animacje) — podpowiedź
    // pokazuje, że strona nie musi być płaskim prostokątem w jednym kolorze.
    tytul: "Strona, która żyje",
    opis: "Animowane tło, ilustracje i ruch zamiast płaskiego koloru.",
    polecenie:
      "Zrób stronę dla mojej marki z animowanym tłem i ilustracjami — ma wyglądać nowocześnie, " +
      "a nie jak jednokolorowy szablon. Pokaż mi ją, zanim cokolwiek opublikujesz.",
  },
];

interface Props {
  username: string;
  cloudUrl: string;
  /** Sesja konta próbnego (wejście bez rejestracji) — okno dokłada pasek zachęty. */
  gosc?: boolean;
  route: Route;
  navigate: (path: string, replace?: boolean) => void;
  onLoggedOut: () => void;
}

export function Workspace({ username, cloudUrl, gosc = false, route, navigate, onLoggedOut }: Props) {
  const [theme, setTheme] = useState<ThemeChoice>(storedTheme());
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Wyjście z aplikacji ma swoje ujęcie w pakiecie ruchu; bez niego kliknięcie „Wyloguj”
  // gasiło okno w tej samej klatce i wyglądało jak awaria, a nie jak zamknięcie sesji.
  const [wylogowanie, setWylogowanie] = useState(false);
  // Zwinięcie panelu rozmów na komputerze. Wybór zostaje między sesjami: kto raz
  // zdecydował, że chce szersze okno rozmowy, nie ma go ustawiać przy każdym wejściu.
  const [panelZwiniety, setPanelZwiniety] = useState(() => {
    try {
      return localStorage.getItem("nexus-panel-zwiniety") === "1";
    } catch {
      return false;
    }
  });
  const zwinPanel = useCallback((zwiniety: boolean) => {
    setPanelZwiniety(zwiniety);
    try {
      localStorage.setItem("nexus-panel-zwiniety", zwiniety ? "1" : "0");
    } catch {
      // Zablokowane dane witryny — wybór działa w tej sesji i tyle.
    }
  }, []);
  const [preview, setPreview] = useState<FileInfo | null>(null);
  const [dragging, setDragging] = useState(false);
  const [dropped, setDropped] = useState<File[]>([]);
  const [prefill, setPrefill] = useState("");
  const [voiceConfig, setVoiceConfig] = useState<VoiceConfig | null>(null);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [voiceRunId, setVoiceRunId] = useState<string | null>(null);
  const [tasksOpen, setTasksOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const scroller = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  // Adres bywa aliasem („/m/chmura” zamiast „/m/cloud”), a cała powłoka — podświetlenie
  // w pasku, klucz przejścia widoku, przełączanie na czat — porównuje się do identyfikatora
  // modułu. Sprowadzamy więc alias do identyfikatora od razu tutaj, żeby nie robić tego
  // w każdym z tych miejsc osobno.
  const activeId = route.view === "module" ? (findModule(route.moduleId)?.id ?? route.moduleId) : "chat";
  // Pasek modułów jest w drzewie dwa razy (bok na komputerze, dół na telefonie) — jedną
  // odmianę chowa arkusz stylów. Pytanie o wydanie zadajemy więc tutaj, raz.
  const noweZmiany = useNieprzeczytaneNowosci();
  const chat = useChat({
    onUnauthorized: onLoggedOut,
    onOpened: (id) => {
      // Adres podąża za otwartą rozmową tylko w widoku czatu (moduł może otworzyć rozmowę w tle).
      if (activeIdRef.current === "chat") navigate(id ? `/c/${id}` : "/", true);
    },
  });
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  const currentIdRef = useRef(chat.currentId);
  currentIdRef.current = chat.currentId;

  const dismissToast = useCallback((id: string) => setToasts((items) => items.filter((item) => item.id !== id)), []);

  const openConversation = useCallback(
    (id: string) => {
      navigate(`/c/${id}`);
    },
    [navigate],
  );

  /** Nowa rozmowa z gotowym zdaniem w polu wiadomości (moduł „Możliwości”, podpowiedzi). */
  const openChat = useCallback(
    (tekst?: string) => {
      navigate(SCIEZKA.czat);
      if (tekst) setPrefill(tekst);
    },
    [navigate],
  );

  const { tasks, refresh: refreshTasks } = useActiveTasks(true, (finished) => {
    chat.refreshList();
    const background = finished.filter((task) => task.conversation_id !== currentIdRef.current || activeIdRef.current !== "chat");
    if (!background.length) return;
    setToasts((items) => [
      ...items,
      ...background.map((task) => ({
        id: task.run_id,
        title: "Zadanie zakończone",
        body: task.title,
        actionLabel: "Otwórz rozmowę",
        onAction: () => openConversation(task.conversation_id),
      })),
    ]);
  });

  // Rozmowa z adresu strony (także po „wstecz” w przeglądarce).
  const routeConversation = route.view === "chat" ? route.conversationId : undefined;
  useEffect(() => {
    if (routeConversation === undefined) return;
    if (routeConversation !== currentIdRef.current) chat.open(routeConversation);
    setSidebarOpen(false);
    stickToBottom.current = true;
  }, [routeConversation]);

  useEffect(() => {
    chat.refreshList();
    api
      .voiceConfig()
      .then(setVoiceConfig)
      .catch(() => setVoiceConfig(null));
  }, []);

  // Motyw „systemowy” podąża za zmianą ustawień urządzenia.
  useEffect(() => {
    if (theme !== "system") return;
    const media = window.matchMedia?.("(prefers-color-scheme: light)");
    const onChange = () => applyTheme("system");
    media?.addEventListener("change", onChange);
    return () => media?.removeEventListener("change", onChange);
  }, [theme]);

  // Pliki udostępnione z innej aplikacji trafiają do nowej wiadomości.
  useEffect(() => {
    takeSharedContent()
      .then((shared) => {
        if (!shared) return;
        navigate(SCIEZKA.czat, true);
        chat.open(null);
        if (shared.files.length) setDropped(shared.files);
        if (shared.text) setPrefill(shared.text);
      })
      .catch(chat.handleError);
  }, []);

  useEffect(() => {
    const element = scroller.current;
    if (!element || !stickToBottom.current) return;
    // Przy pustej rozmowie przewinięcie do dołu ucinałoby powitanie i podpowiedzi —
    // na ekranie 720 px znikał cały nagłówek. Do dołu wracamy dopiero z wypowiedziami.
    if (!(chat.detail?.turns ?? []).length) {
      element.scrollTop = 0;
      return;
    }
    element.scrollTop = element.scrollHeight;
  }, [chat.detail]);

  // Esc zatrzymuje pracującego agenta (DESIGN_SYSTEM, rozdz. 2). Warunek zatrzymania
  // jest funkcją czystą w `useEscZatrzymaj`, więc da się go sprawdzić testem bez powłoki.
  const biegTrwa = chat.activeRun !== null;
  useEscZatrzymaj(biegTrwa, chat.stop);

  const startVoice = () => {
    if (!voiceConfig?.available) {
      chat.setError("Rozmowa głosowa jest niedostępna – serwer nie ma skonfigurowanych modeli mowy.");
      return;
    }
    unlockAudio();
    setVoiceOpen(true);
  };

  // Adres /m/glos nie jest modułem rejestru, tylko nakładką otwieraną z paska. Wejście
  // pod ten adres (zakładka, odświeżenie) ma otworzyć rozmowę głosową, a nie ekran
  // „moduł niedostępny”.
  useEffect(() => {
    if (activeId !== "glos") return;
    // Dopóki nie wiadomo, czy głos jest dostępny, nie wyrokujemy: wejście pod /m/glos
    // wołało `startVoice()` z `voiceConfig === null` (ustawienia jeszcze się pobierały)
    // i na ekranie zapalał się czerwony komunikat „serwer nie ma modeli mowy” — także
    // wtedy, gdy chwilę później okazywało się, że głos działa.
    if (voiceConfig === null) return;
    navigate(chat.currentId ? `/c/${chat.currentId}` : "/", true);
    startVoice();
    // Uruchamiane przy wejściu pod adres modułu głosu.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, voiceConfig]);

  const selectEntry = (id: string) => {
    if (id === "glos") {
      if (activeId !== "chat") navigate(chat.currentId ? `/c/${chat.currentId}` : "/");
      startVoice();
      return;
    }
    if (id === "chat") navigate(chat.currentId ? `/c/${chat.currentId}` : "/");
    else navigate(`/m/${id}`);
  };

  const send = async (text: string, files: FileInfo[], voice = false): Promise<boolean> => {
    const runId = await chat.send(text, files, voice);
    if (!runId) return false;
    if (voice) setVoiceRunId(runId);
    stickToBottom.current = true;
    void refreshTasks();
    return true;
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length) setDropped(files);
  };

  const entries = navEntries(MODULES);
  const module = activeId === "chat" ? undefined : findModule(activeId);
  const turns = chat.detail?.turns ?? [];
  // Tytuł okna mówił „Danaco Nexus” niezależnie od tego, co jest na ekranie: `applyIndexing`
  // zna tylko rodzaj ekranu („app”), nie moduł. Przy zainstalowanej aplikacji to tytuł
  // w przełączniku okien systemu, a przy kilku kartach — jedyny sposób odróżnienia ich
  // od siebie. Nazwy modułów mieszkają w rejestrze, którego nie wolno wciągać do `App.tsx`
  // (import jest `eager`, więc przyszłyby z nim wszystkie strony modułów), więc tytuł
  // ustawia powłoka — jedyne miejsce, które i tak zna moduł i tytuł rozmowy.
  const nazwaEkranu = module?.label ?? chat.detail?.title ?? "";
  useEffect(() => {
    document.title = nazwaEkranu ? `${nazwaEkranu} — Danaco Nexus` : "Danaco Nexus";
  }, [nazwaEkranu]);
  const voiceTurn = voiceRunId
    ? turns.find((turn): turn is AssistantTurn => turn.type === "assistant" && turn.run_id === voiceRunId)
    : undefined;
  const voiceReply = voiceTurn
    ? voiceTurn.items.map((item) => (item.kind === "text" ? item.text : "")).filter(Boolean).join("\n")
    : "";
  const voiceDone = !voiceTurn || (voiceTurn.status !== "running" && voiceTurn.status !== "queued");

  const chatView = (
    <>
      <Sidebar
        conversations={chat.conversations}
        currentId={chat.currentId}
        username={username}
        cloudUrl={cloudUrl}
        open={sidebarOpen}
        theme={theme}
        onTheme={setTheme}
        onSelect={openConversation}
        onNew={() => {
          setSidebarOpen(false);
          navigate(SCIEZKA.czat);
          chat.open(null);
        }}
        onRename={(id, title) => void chat.rename(id, title)}
        onDelete={(id) => void chat.remove(id)}
        onLogout={() => {
          // Sesję zamykamy od razu; ujęcie przykrywa tylko ten moment.
          setWylogowanie(true);
          void api.logout().catch(() => undefined);
        }}
        onClose={() => setSidebarOpen(false)}
        onZwin={() => zwinPanel(true)}
        zwiniety={panelZwiniety}
        onUstawienia={() => navigate("/m/ustawienia")}
        onDostep={() => navigate("/m/platnosci")}
      />
      <main
        className="relative flex min-w-0 flex-1 flex-col bg-app"
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) setDragging(false);
        }}
        onDrop={onDrop}
      >
        <header className="safe-top titlebar-drag sticky top-0 z-10 flex items-center gap-2 border-b border-line/60 bg-app/85 px-3 py-2 backdrop-blur md:border-transparent">
          <button type="button" className="icon-btn md:hidden" onClick={() => setSidebarOpen(true)} aria-label="Historia rozmów">
            <MenuIcon />
          </button>
          {/* Powrót panelu rozmów. Bez tego przycisku zwinięcie byłoby pułapką:
              panel znikał, a rozmowy nie dało się już otworzyć inaczej niż z adresu. */}
          {panelZwiniety && (
            <button
              type="button"
              className="icon-btn z-etykieta hidden md:inline-grid"
              data-etykieta="Pokaż panel rozmów"
              onClick={() => zwinPanel(false)}
              aria-label="Pokaż panel rozmów"
            >
              <PanelIcon size={18} />
            </button>
          )}
          <h1 className="min-w-0 flex-1 truncate text-[15px] font-medium">{chat.detail?.title ?? "Nowa rozmowa"}</h1>
          <span className="md:hidden">
            <TasksButton tasks={tasks} onClick={() => setTasksOpen(true)} />
          </span>
          <button
            type="button"
            className="icon-btn md:hidden"
            onClick={() => {
              navigate(SCIEZKA.czat);
              chat.open(null);
            }}
            aria-label="Nowa rozmowa"
          >
            <PlusIcon />
          </button>
        </header>
        <BezPolaczenia />
        <PasekAktualizacji />
        {gosc && <PasekKontaProbnego onZaloz={() => window.location.assign("/portal/konto")} />}
        {!gosc && <PasekPlanu onZmienPlan={() => navigate("/m/platnosci")} />}
        <div
          className="min-h-0 flex-1 overflow-y-auto"
          ref={scroller}
          onScroll={(event) => {
            const element = event.currentTarget;
            stickToBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
          }}
        >
          <div className="mx-auto w-full max-w-3xl px-4 pt-4 pb-10 md:px-6">
            {turns.length === 0 ? (
              <div className="flex min-h-[calc(100dvh-320px)] animate-rise flex-col items-center justify-center py-8 text-center">
                {/* Pusty ekran witał płaskim znaczkiem — po oknie nie było widać, że
                  aplikacja w ogóle żyje. Znak w spoczynku oddycha; przy ograniczonym
                  ruchu zostaje ten sam znak bez animacji. */}
                {ograniczonyRuch() ? (
                  <Logo size={56} className="mb-5 rounded-2xl shadow-lg shadow-accent/20" />
                ) : (
                  <ZnakRuchu moment="spoczynek" rozmiar={64} className="mb-4" />
                )}
                <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">W czym mogę pomóc?</h2>
                <p className="mt-2 max-w-md text-muted">
                  Opisz zadanie i dodaj pliki – dokumenty, zdjęcia, PDF, nagrania. Sam dobiorę narzędzia, wykonam pracę
                  i oddam gotowy wynik.
                </p>
                {/* Trzy formy, nie osiem jednakowych kafli.
                  Poprzednio wszystkie propozycje wyglądały tak samo ważne, więc oko nie
                  miało się czego złapać i całość czytało się jak spis treści. Teraz dwie
                  pierwsze są kartami z opisem — to one mają zaczepić; reszta schodzi do
                  jednowierszowych podpowiedzi, bo do nich wystarczy sama nazwa rezultatu.
                  Na telefonie karty zostają, podpowiedzi zwijają się do czterech: kafle
                  mają podpowiadać, a nie zasłaniać drogi do pola wiadomości. */}
                <div className="mt-8 grid w-full gap-2.5 sm:grid-cols-2">
                  {SUGGESTIONS.slice(0, 2).map((podpowiedz, indeks) => (
                    <button
                      key={podpowiedz.tytul}
                      type="button"
                      // Karty wchodzą kaskadą i unoszą się pod kursorem — to jedyne
                      // elementy na pustym ekranie, więc martwe wyglądają na atrapę.
                      // `flex flex-col` zamiast domyślnego układu przycisku: bez tego krótszy opis był
                      // wyśrodkowany w pionie i tytuły dwóch kart obok siebie stały na różnej wysokości.
                      className="ui-nacisk group animate-rise flex flex-col items-start rounded-2xl border border-line bg-raised/40 px-4 py-4 text-left transition-[background-color,border-color,transform] duration-(--duration-base) hover:-translate-y-0.5 hover:border-accent/50 hover:bg-raised"
                      style={{ animationDelay: `calc(var(--stagger-step) * ${indeks})` }}
                      onClick={() => setPrefill(podpowiedz.polecenie)}
                    >
                      <span className="flex items-center gap-1.5 font-heading text-base font-semibold tracking-tight text-fg">
                        {podpowiedz.tytul}
                        <ArrowRightIcon
                          size={15}
                          className="shrink-0 -translate-x-1 text-accent opacity-0 transition-[opacity,transform] duration-(--duration-base) group-hover:translate-x-0 group-hover:opacity-100 group-focus-visible:translate-x-0 group-focus-visible:opacity-100"
                        />
                      </span>
                      <span className="mt-1.5 block text-[13px] leading-relaxed text-muted">
                        {podpowiedz.opis}
                      </span>
                    </button>
                  ))}
                </div>
                <div className="mt-3 flex w-full flex-wrap justify-center gap-2">
                  {SUGGESTIONS.slice(2).map((podpowiedz, indeks) => (
                    <button
                      key={podpowiedz.tytul}
                      type="button"
                      title={podpowiedz.opis}
                      className={`ui-nacisk animate-rise rounded-full border border-line px-3.5 py-1.5 text-[13px] text-muted transition-colors duration-(--duration-base) hover:border-line-strong hover:bg-raised hover:text-fg ${
                        indeks >= 4 ? "hidden sm:inline-flex" : ""
                      }`}
                      style={{ animationDelay: `calc(var(--stagger-step) * ${indeks + 2})` }}
                      onClick={() => setPrefill(podpowiedz.polecenie)}
                    >
                      {podpowiedz.tytul}
                    </button>
                  ))}
                </div>
                <p className="mt-6 hidden text-sm text-subtle sm:block">
                  Naciśnij <kbd className="rounded-sm border border-line px-1.5 py-0.5 font-mono text-xs">Ctrl</kbd>{" "}
                  <kbd className="rounded-sm border border-line px-1.5 py-0.5 font-mono text-xs">K</kbd>, aby otworzyć paletę poleceń.
                </p>
              </div>
            ) : (
              <div className="space-y-7">
                {turns.map((turn, index) =>
                  turn.type === "user" ? (
                    <UserMessage key={`u${turn.id}`} turn={displayTurn(turn)} onPreview={setPreview} />
                  ) : (
                    <AssistantMessage
                      key={`a${turn.run_id ?? index}-${index}`}
                      turn={turn}
                      onPreview={setPreview}
                      ostatnia={index === turns.length - 1}
                    />
                  ),
                )}
              </div>
            )}
          </div>
        </div>
        <div className="safe-bottom relative mx-auto w-full max-w-3xl px-3 md:px-6">
          {chat.brakKredytow ? (
            <div className="absolute inset-x-3 bottom-full mb-2 md:inset-x-6">
              <BrakKredytow
                komunikat={chat.error}
                onDokup={() => navigate("/m/platnosci")}
                onZamknij={() => {
                  chat.setBrakKredytow(false);
                  chat.setError("");
                }}
              />
            </div>
          ) : (
            chat.error && (
              <div
                role="alert"
                onClick={() => chat.setError("")}
                className="absolute inset-x-3 bottom-full mb-2 flex cursor-pointer items-center gap-3 rounded-xl border border-danger/40 bg-danger-soft px-4 py-2.5 text-sm text-danger shadow-lg md:inset-x-6"
              >
                {/* Niepowodzenie ma w pakiecie ruchu własne ujęcie (moment-blad). */}
                {!ograniczonyRuch() && (
                  <NagranieStartu nazwa="moment-blad" className="size-6 shrink-0 object-contain" />
                )}
                <span className="min-w-0 flex-1">{chat.error}</span>
                {/* Zamknięcie kliknięciem w pasek jest wygodne myszą, ale klawiatura nie
                  ma czego nacisnąć: `div` z `onClick` nie trafia w kolejność tabulacji
                  ani nie reaguje na Enter. Kto pracuje klawiaturą albo czytnikiem ekranu,
                  zostawał z komunikatem na stałe. Przycisk jest prawdziwym `button`, więc
                  działa tabulatorem, Enterem i spacją. */}
                <button
                  type="button"
                  aria-label="Zamknij komunikat"
                  className="-mr-1 shrink-0 rounded-lg px-2 py-1 text-danger/80 transition-colors hover:bg-danger/10 hover:text-danger"
                  onClick={(zdarzenie) => {
                    zdarzenie.stopPropagation();
                    chat.setError("");
                  }}
                >
                  <CloseIcon size={16} />
                </button>
              </div>
            )
          )}
          <Composer
            conversationId={chat.currentId}
            running={chat.activeRun !== null}
            onSend={send}
            onStop={chat.stop}
            droppedFiles={dropped}
            onDroppedConsumed={() => setDropped([])}
            prefill={prefill}
            onPrefillConsumed={() => setPrefill("")}
            onVoice={voiceConfig?.available ? startVoice : undefined}
          />
          <div className="py-1.5 text-center text-xs text-muted">
            Danaco Nexus może się pomylić. Wyniki warto sprawdzić przed użyciem.
          </div>
        </div>
        {dragging && (
          <div className="pointer-events-none absolute inset-3 z-20 flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-accent bg-accent-soft/90 text-lg font-medium text-accent">
            {/* Przeciąganie pliku ma w pakiecie ruchu własne ujęcie (stany/upuszczanie);
              przy ograniczonym ruchu zostaje spinacz. */}
            {ograniczonyRuch() ? (
              <PaperclipIcon size={32} />
            ) : (
              <NagranieStanu nazwa="upuszczanie" className="h-20 w-32 object-contain" />
            )}
            Upuść pliki, aby je dodać
          </div>
        )}
      </main>
    </>
  );

  const moduleView = (
    <main className="relative flex min-w-0 flex-1 flex-col bg-app">
      <header className="safe-top flex items-center gap-2 border-b border-line/60 px-3 py-2 md:hidden">
        <Logo size={24} className="rounded-md" />
        {/* Etykieta paska, nie tytuł dokumentu: własny nagłówek rysuje moduł. Gdy oba były
            `h1`, na telefonie ta sama nazwa padała dwa razy (np. „Obrazy” w pasku i w nagłówku
            modułu), a czytnik ekranu ogłaszał dwa tytuły tej samej strony. */}
        <p className="min-w-0 flex-1 truncate text-[15px] font-medium">{module?.label ?? "Moduł"}</p>
        <TasksButton tasks={tasks} onClick={() => setTasksOpen(true)} />
      </header>
      <div className="min-h-0 flex-1">
        {module ? (
          <module.Page openConversation={openConversation} openModule={(id) => navigate(`/m/${id}`)} openChat={openChat} />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
            {/* Nagłówek pierwszego stopnia, bo tu nie ma strony modułu, która by go niosła.
              Zmierzone na wydaniu 21.09.2026: `/m/<nieznany>` miał zero widocznych `h1`,
              więc czytnik ekranu nie miał od czego zacząć — choć sam komunikat był na miejscu. */}
            <h1 className="text-xl font-semibold">Ten moduł nie jest dostępny</h1>
            <p className="max-w-sm text-sm text-muted">Moduł „{activeId}” nie jest zainstalowany w tej wersji Nexusa.</p>
            <button type="button" className="rounded-xl bg-accent-fill px-4 py-2 text-sm font-medium text-on-accent" onClick={() => navigate(SCIEZKA.czat)}>
              Wróć do czatu
            </button>
          </div>
        )}
      </div>
    </main>
  );

  // Wyjście z aplikacji: ujęcie zamknięcia sesji zamiast natychmiastowego skoku na logowanie.
  if (wylogowanie) return <EkranWylogowania onKoniec={onLoggedOut} />;

  return (
    <div className="flex h-full flex-col overflow-hidden md:flex-row">
      {/* Bez tego odsyłacza klawiatura przechodzi przez kilkanaście pozycji nawigacji
          i całą historię rozmów, zanim dojdzie do treści (WCAG 2.2, 2.4.1). */}
      <a
        href="#tresc-aplikacji"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-(--z-toast) focus:rounded-md focus:bg-accent-fill focus:px-4 focus:py-2 focus:text-on-accent"
      >
        Przejdź do treści
      </a>
      <NavRail
        entries={entries}
        activeId={activeId}
        onSelect={selectEntry}
        railFooter={<TasksButton variant="rail" tasks={tasks} onClick={() => setTasksOpen(true)} />}
        noweZmiany={noweZmiany}
      />
      <ObszarOgloszen />
      {/* Przejście między modułami. Aplikacja podmieniała cały obszar bez śladu ruchu —
        moduł znikał, drugi pojawiał się w tej samej klatce, więc nie było widać, że to
        zmiana widoku, a nie przeładowanie. Ujęcie bierze sam podmieniany obszar, więc
        pasek modułów i panel rozmów zostają nieruchome. */}
      <PrzejscieWidoku
        klucz={activeId}
        id="tresc-aplikacji"
        tabIndex={-1}
        className="flex min-h-0 min-w-0 flex-1"
        klasaWnetrza="flex min-h-0 min-w-0 flex-1"
      >
        {activeId === "chat" ? chatView : moduleView}
      </PrzejscieWidoku>
      <BottomBar entries={entries} activeId={activeId} onSelect={selectEntry} noweZmiany={noweZmiany} />
      {preview && <PreviewModal file={preview} onClose={() => setPreview(null)} />}
      {tasksOpen && (
        <TasksPanel
          tasks={tasks}
          currentConversation={activeId === "chat" ? chat.currentId : null}
          onOpen={openConversation}
          onClose={() => setTasksOpen(false)}
          onChanged={() => void refreshTasks()}
        />
      )}
      <Paleta
        entries={entries}
        conversations={chat.conversations}
        onSelectEntry={selectEntry}
        onOpenConversation={openConversation}
        onNewConversation={() => {
          navigate(SCIEZKA.czat);
          chat.open(null);
        }}
        onToggleTheme={() => {
          const wybor = nextTheme(theme);
          setTheme(wybor);
          saveTheme(wybor);
        }}
        onAsk={(pytanie) => {
          if (activeId !== "chat") navigate(chat.currentId ? `/c/${chat.currentId}` : "/");
          setPrefill(pytanie);
        }}
      />
      <Toasts toasts={toasts} onDismiss={dismissToast} />
      {voiceOpen && voiceConfig && (
        <VoiceMode
          config={voiceConfig}
          replyText={voiceReply}
          replyDone={voiceDone}
          onSend={(text) => send(text, [], true)}
          onClose={() => {
            setVoiceOpen(false);
            setVoiceRunId(null);
          }}
        />
      )}
    </div>
  );
}
