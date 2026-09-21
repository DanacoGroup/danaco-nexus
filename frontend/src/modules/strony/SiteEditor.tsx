// Edycja strony rozmową obok podglądu na żywo; wersje, pliki i publikacja.

import { useCallback, useEffect, useRef, useState } from "react";
import type { RunEvent } from "../../api";
import { CloseIcon, RefreshIcon } from "../../components/icons";
import { formatSize } from "../../runState";
import { useOknoModalne } from "../../ui/useOknoModalne";
import { ChatPanel } from "../_tworczy/ChatPanel";
import { errorText } from "../_tworczy/http";
import {
  ArrowLeftIcon,
  CodeIcon,
  DesktopIcon,
  ExternalIcon,
  GlobeIcon,
  HistoryIcon,
  PhoneIcon,
  TabletIcon,
} from "../_tworczy/icons";
import { DEVICE_WIDTHS, sitePrefix, stripSitePrefix, type Device } from "../_tworczy/logic";
import { buttonPrimary, buttonSecondary, ErrorBanner, Segmented, Spinner } from "../_tworczy/ui";
import { useConversation } from "../_tworczy/useConversation";
import { formatDate, sitesApi, type SiteDetail } from "./api";

type Panel = "none" | "versions" | "files";

export function SiteEditor({
  address,
  firstPrompt,
  onBack,
  openConversation,
}: {
  address: string;
  firstPrompt?: string;
  onBack: () => void;
  openConversation: (id: string) => void;
}) {
  const [site, setSite] = useState<SiteDetail | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [device, setDevice] = useState<Device>("desktop");
  const [page, setPage] = useState("");
  const [frameKey, setFrameKey] = useState(0);
  const [panel, setPanel] = useState<Panel>("none");
  const [mobileTab, setMobileTab] = useState<"chat" | "preview">("chat");
  const [source, setSource] = useState<{ path: string; content: string } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const promptSent = useRef(false);

  const refreshSite = useCallback(
    () =>
      sitesApi
        .get(address)
        .then(setSite)
        .catch((failure) => setError(errorText(failure))),
    [address],
  );

  useEffect(() => {
    refreshSite();
    sitesApi
      .conversation(address)
      .then((result) => setConversationId(result.conversation_id))
      .catch((failure) => setError(errorText(failure)));
  }, [address, refreshSite]);

  const onEvent = useCallback(
    (event: RunEvent) => {
      const name = String(event.data.name ?? "");
      if (event.type === "tool.finished" && name.includes("site_")) {
        setFrameKey((key) => key + 1);
        refreshSite();
      }
      if (event.type === "run.completed" || event.type === "run.failed") refreshSite();
    },
    [refreshSite],
  );

  const conversation = useConversation(conversationId, onEvent);

  // Pierwsza wiadomość z opisem strony (po utworzeniu) – wysyłana raz, gdy rozmowa jest pusta.
  useEffect(() => {
    if (!firstPrompt || promptSent.current || !conversation.detail || conversation.detail.turns.length) return;
    promptSent.current = true;
    conversation.send(sitePrefix(address) + firstPrompt);
  }, [firstPrompt, conversation, address]);

  const act = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
      await refreshSite();
      setFrameKey((key) => key + 1);
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setBusy(false);
    }
  };

  const publicUrl = `${window.location.origin}/s/${address}/`;
  const publish = () => {
    const first = !site?.published_at;
    const question = first
      ? `Opublikować stronę pod adresem ${publicUrl}? Będzie dostępna publicznie dla każdego.`
      : `Zastąpić opublikowaną wersję bieżącym szkicem? Zmiany będą od razu widoczne pod ${publicUrl}`;
    if (window.confirm(question)) act(() => sitesApi.publish(address));
  };
  const unpublish = () => {
    if (window.confirm("Wycofać publikację? Adres publiczny przestanie działać (szkic zostaje).")) {
      act(() => sitesApi.unpublish(address));
    }
  };
  const saveVersion = () => {
    const note = window.prompt("Opis wersji (opcjonalnie):", "");
    if (note !== null) act(() => sitesApi.saveVersion(address, note));
  };
  const restore = (version: string) => {
    if (window.confirm(`Przywrócić wersję ${version}? Bieżący szkic zostanie zapisany jako nowa wersja.`)) {
      act(() => sitesApi.restore(address, version));
    }
  };
  const showSource = (path: string) =>
    sitesApi
      .readFile(address, path)
      .then(setSource)
      .catch((failure) => setError(errorText(failure)));

  const htmlPages = (site?.files ?? []).filter((file) => /\.html?$/i.test(file.path)).map((file) => file.path);
  const width = DEVICE_WIDTHS[device];
  const frameSrc = site ? `${site.preview_url}${page}` : "";
  const textFile = (path: string) => /\.(html?|css|m?js|json|svg|txt|md|xml|csv|webmanifest)$/i.test(path);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="safe-top flex flex-wrap items-center gap-2 border-b border-line/60 px-3 py-2 md:px-4">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Wróć do listy stron">
          <ArrowLeftIcon />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[15px] font-semibold">{site?.title ?? address}</h1>
          <p className="truncate font-mono text-xs text-muted">
            /s/{address}/ · {site?.published_at ? `opublikowana ${formatDate(site.published_at)}` : "szkic"}
          </p>
        </div>
        <button
          type="button"
          className={`icon-btn ${panel === "files" ? "bg-hover text-fg" : ""}`}
          onClick={() => setPanel(panel === "files" ? "none" : "files")}
          aria-label="Pliki strony"
          title="Pliki strony"
        >
          <CodeIcon />
        </button>
        <button
          type="button"
          className={`icon-btn ${panel === "versions" ? "bg-hover text-fg" : ""}`}
          onClick={() => setPanel(panel === "versions" ? "none" : "versions")}
          aria-label="Wersje"
          title="Wersje"
        >
          <HistoryIcon />
        </button>
        {site?.published_at && (
          <>
            <a className="icon-btn" href={site.public_url} target="_blank" rel="noopener noreferrer" aria-label="Otwórz opublikowaną stronę" title="Otwórz opublikowaną stronę">
              <ExternalIcon />
            </a>
            <button type="button" className={buttonSecondary} onClick={unpublish} disabled={busy}>
              Wycofaj
            </button>
          </>
        )}
        <button type="button" className={buttonPrimary} onClick={publish} disabled={busy || !site}>
          <GlobeIcon size={16} /> {site?.published_at ? "Aktualizuj publikację" : "Opublikuj"}
        </button>
      </header>

      {site?.publish_request && (
        <div className="flex flex-wrap items-center gap-2 border-b border-accent/30 bg-accent-soft/60 px-4 py-2 text-sm">
          <span className="flex-1">
            Asystent proponuje publikację strony{site.publish_request.note ? `: ${site.publish_request.note.replace(/\.$/, "")}.` : "."} Sprawdź podgląd i
            zatwierdź.
          </span>
          <button type="button" className={buttonSecondary} onClick={() => act(() => sitesApi.rejectPublish(address))} disabled={busy}>
            Odrzuć
          </button>
          <button type="button" className={buttonPrimary} onClick={publish} disabled={busy}>
            Opublikuj
          </button>
        </div>
      )}
      {error && (
        <div className="px-4 pt-2">
          <ErrorBanner text={error} onClose={() => setError("")} />
        </div>
      )}

      <div className="flex border-b border-line/60 lg:hidden">
        {(["chat", "preview"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            className={`flex-1 py-2 text-sm ${mobileTab === tab ? "border-b-2 border-accent font-medium" : "text-muted"}`}
            onClick={() => setMobileTab(tab)}
          >
            {tab === "chat" ? "Rozmowa" : "Podgląd"}
          </button>
        ))}
      </div>

      <div className="relative flex min-h-0 flex-1">
        <section
          className={`min-h-0 w-full flex-col border-line/60 lg:flex lg:w-[400px] lg:shrink-0 lg:border-r xl:w-[440px] ${
            mobileTab === "chat" ? "flex" : "hidden"
          }`}
        >
          <ChatPanel
            conversation={conversation}
            conversationId={conversationId}
            placeholder="Opisz zmianę, np. „dodaj sekcję z cennikiem” albo „zmień kolory na granatowe”"
            prepare={(text) => sitePrefix(address) + text}
            display={stripSitePrefix}
            accept="image/*,.svg,.pdf,.woff2,.ttf,.mp4,.webm"
            empty={
              <div className="space-y-2">
                {/* „w podglądzie”, a nie „obok”: obok jest dopiero od szerokości `lg`. Niżej
                    podgląd siedzi w zakładce (patrz `mobileTab`), więc „obok” kazało szukać
                    czegoś, czego na telefonie nie widać. */}
                <p>Opisz, co ma się znaleźć na stronie – asystent zbuduje ją i zobaczysz efekt na żywo w podglądzie.</p>
                {conversationId && (
                  <button type="button" className="text-accent hover:underline" onClick={() => openConversation(conversationId)}>
                    Otwórz tę rozmowę na czacie
                  </button>
                )}
              </div>
            }
          />
        </section>

        <section className={`min-h-0 flex-1 flex-col bg-side lg:flex ${mobileTab === "preview" ? "flex" : "hidden"}`}>
          <div className="flex flex-wrap items-center gap-2 border-b border-line/60 px-3 py-2">
            <Segmented
              label="Szerokość podglądu"
              value={device}
              onChange={setDevice}
              options={[
                { value: "desktop", label: "Komputer", icon: <DesktopIcon size={15} /> },
                { value: "tablet", label: "Tablet", icon: <TabletIcon size={15} /> },
                { value: "phone", label: "Telefon", icon: <PhoneIcon size={15} /> },
              ]}
            />
            {htmlPages.length > 1 && (
              <select
                className="rounded-lg border border-line bg-app px-2 py-1.5 text-sm"
                value={page || "index.html"}
                onChange={(event) => setPage(event.target.value === "index.html" ? "" : event.target.value)}
                aria-label="Podstrona"
              >
                {htmlPages.map((path) => (
                  <option key={path} value={path}>
                    {path}
                  </option>
                ))}
              </select>
            )}
            <span className="flex-1" />
            {conversation.running && <Spinner label="Asystent pracuje…" />}
            <button type="button" className="icon-btn" onClick={() => setFrameKey((key) => key + 1)} aria-label="Odśwież podgląd">
              <RefreshIcon size={18} />
            </button>
            {site && (
              <a className="icon-btn" href={frameSrc} target="_blank" rel="noopener noreferrer" aria-label="Otwórz podgląd w nowej karcie">
                <ExternalIcon size={18} />
              </a>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-3">
            {site ? (
              <div
                className="mx-auto h-full overflow-hidden rounded-xl border border-line bg-white shadow-sm transition-[width]"
                style={{ width: width ? `${width}px` : "100%", maxWidth: "100%" }}
              >
                <iframe
                  key={frameKey}
                  title={`Podgląd strony ${site.title}`}
                  src={frameSrc}
                  sandbox="allow-scripts allow-forms allow-popups allow-modals"
                  referrerPolicy="no-referrer"
                  className="h-full w-full border-0"
                />
              </div>
            ) : (
              <Spinner label="Wczytywanie podglądu…" />
            )}
          </div>
        </section>

        {panel !== "none" && site && (
          <aside className="absolute inset-y-0 right-0 z-10 flex w-full max-w-sm animate-rise flex-col border-l border-line bg-app shadow-xl">
            <div className="flex items-center gap-2 border-b border-line/60 px-4 py-3">
              <h2 className="flex-1 font-medium">{panel === "versions" ? "Wersje" : "Pliki strony"}</h2>
              {panel === "versions" && (
                <button type="button" className={buttonSecondary} onClick={saveVersion} disabled={busy}>
                  Zapisz wersję
                </button>
              )}
              <button type="button" className="icon-btn" onClick={() => setPanel("none")} aria-label="Zamknij panel">
                <CloseIcon size={18} />
              </button>
            </div>
            <ul className="min-h-0 flex-1 divide-y divide-line/60 overflow-y-auto">
              {panel === "versions" &&
                (site.versions.length ? (
                  site.versions.map((version) => (
                    <li key={version.id} className="flex items-center gap-2 px-4 py-2.5 text-sm">
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">
                          {version.note || "Wersja"}
                          {version.id === site.published_version && <span className="ml-2 text-xs text-accent">opublikowana</span>}
                        </p>
                        <p className="text-xs text-muted">
                          {version.id} · {formatDate(version.created_at)} · {version.files} pl.
                        </p>
                      </div>
                      <button type="button" className={buttonSecondary} onClick={() => restore(version.id)} disabled={busy}>
                        Przywróć
                      </button>
                    </li>
                  ))
                ) : (
                  <li className="px-4 py-6 text-center text-sm text-muted">Brak zapisanych wersji. Wersja powstaje przy każdej publikacji.</li>
                ))}
              {panel === "files" &&
                site.files.map((file) => (
                  <li key={file.path} className="flex items-center gap-2 px-4 py-2 text-sm">
                    <span className="min-w-0 flex-1 truncate font-mono text-xs">{file.path}</span>
                    <span className="text-xs text-muted tabular-nums">{formatSize(file.size)}</span>
                    {textFile(file.path) && (
                      <button type="button" className="icon-btn size-8" onClick={() => showSource(file.path)} aria-label={`Pokaż kod ${file.path}`}>
                        <CodeIcon size={16} />
                      </button>
                    )}
                  </li>
                ))}
            </ul>
          </aside>
        )}
      </div>

      {source && <PodgladKodu path={source.path} content={source.content} onClose={() => setSource(null)} />}
    </div>
  );
}

/** Nakładka z kodem pliku. Własny komponent, bo hak okna modalnego wymaga stałego wywołania. */
function PodgladKodu({ path, content, onClose }: { path: string; content: string; onClose: () => void }) {
  const nakladka = useRef<HTMLDivElement>(null);
  useOknoModalne(nakladka, onClose);
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        ref={nakladka}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        aria-label={`Kod pliku ${path}`}
        className="flex max-h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-line bg-app shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-line/60 px-4 py-2.5">
          <span className="flex-1 truncate font-mono text-sm">{path}</span>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Zamknij">
            <CloseIcon size={18} />
          </button>
        </div>
        <pre className="min-h-0 flex-1 overflow-auto bg-code p-4 font-mono text-xs leading-relaxed whitespace-pre-wrap">{content}</pre>
      </div>
    </div>
  );
}
