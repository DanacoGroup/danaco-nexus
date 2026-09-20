// Raport badania: postęp pracy agenta na żywo, treść z klikalnymi przypisami i lista źródeł.

import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import { api, subscribeRun, type AssistantTurn, type TurnItem } from "../../api";
import { AlertIcon, CheckIcon, DownloadIcon, StopIcon, TrashIcon } from "../../components/icons";
import { renderMarkdown } from "../../components/Markdown";
import { applyRunEvent, emptyAssistantTurn, toolLabel } from "../../runState";
import { ACTIVE, errorText, researchApi, shortDate, type Collection, type ReportDetail } from "./api";
import { hostname, prepareReport, type Citation } from "./citations";
import { ChatIcon, CopyIcon, ExternalIcon, GlobeIcon, ScholarIcon } from "./icons";
import { SourcePanel } from "./SourcePanel";

const DEPTH_LABELS: Record<string, string> = { quick: "Szybkie", standard: "Standardowe", deep: "Dogłębne" };
const TOOL_NAMES: Record<string, string> = {
  web_fetch_page: "Czytanie strony",
  web_search: "Wyszukiwanie w sieci",
  scholar_search: "Bazy prac naukowych",
  scholar_paper: "Szczegóły pracy",
  knowledge_save: "Zapis w bazie wiedzy",
  knowledge_notes: "Notatki",
  knowledge_read: "Odczyt bazy wiedzy",
  WebSearch: "Wyszukiwanie w sieci",
  WebFetch: "Czytanie strony",
  Task: "Podagent",
  Agent: "Podagent",
};

// Wygląd odnośników przypisów w treści raportu (klasy nadawane przez linkCitations).
const CITE_STYLES =
  "[&_sup.cite-group]:ml-0.5 [&_sup.cite-group]:whitespace-nowrap [&_a.cite]:inline-block [&_a.cite]:min-w-[1.25rem] " +
  "[&_a.cite]:rounded-md [&_a.cite]:bg-accent-soft [&_a.cite]:px-1 [&_a.cite]:text-center [&_a.cite]:text-[11px] " +
  "[&_a.cite]:leading-4 [&_a.cite]:font-semibold [&_a.cite]:text-accent [&_a.cite]:no-underline " +
  "[&_a.cite:hover]:bg-accent-fill [&_a.cite:hover]:text-on-accent [&_span.cite-sep]:hidden";

function toolName(name: string): string {
  const short = name.replace(/^mcp__nexus__/, "");
  return TOOL_NAMES[short] ?? toolLabel(short);
}

function toolDetail(item: Extract<TurnItem, { kind: "tool" }>): string {
  const input = item.input ?? {};
  const url = typeof input.url === "string" ? input.url : "";
  if (url) return hostname(url);
  for (const key of ["query", "identifier", "title", "prompt", "description"]) {
    if (typeof input[key] === "string" && input[key]) return String(input[key]).slice(0, 120);
  }
  return item.progress || item.summary || "";
}

function Progress({ turn }: { turn: AssistantTurn }) {
  const tools = turn.items.filter((item): item is Extract<TurnItem, { kind: "tool" }> => item.kind === "tool");
  const pages = tools.filter((item) => /fetch|WebFetch/i.test(item.name)).length;
  const searches = tools.filter((item) => /search|WebSearch/i.test(item.name)).length;
  const recent = tools.slice(-8).reverse();
  return (
    <div className="rounded-2xl border border-line bg-raised/50 p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <span className="spinner size-4 text-accent" />
        <span className="shimmer-text">{turn.status === "queued" ? "Czekam w kolejce…" : "Prowadzę badanie…"}</span>
        <span className="ml-auto text-xs font-normal text-muted tabular-nums">
          {searches} wyszukiwań · {pages} przeczytanych stron
        </span>
      </div>
      {recent.length > 0 && (
        <ol className="mt-3 space-y-1.5">
          {recent.map((item) => {
            const running = item.status === "running";
            const failed = item.status === "error" || item.status === "cancelled";
            return (
              <li key={item.tool_use_id} className="flex min-w-0 items-center gap-2 text-sm">
                <span className={`grid size-4 shrink-0 place-items-center ${failed ? "text-danger" : running ? "text-accent" : "text-success"}`}>
                  {running ? <span className="spinner size-3" /> : failed ? <AlertIcon size={14} /> : <CheckIcon size={14} />}
                </span>
                <span className="shrink-0 font-medium">{toolName(item.name)}</span>
                <span className="min-w-0 truncate text-muted">{toolDetail(item)}</span>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

interface Props {
  reportId: string;
  collections: Collection[];
  openConversation: (id: string) => void;
  onChanged: () => void;
  onDeleted: () => void;
}

export function ReportView({ reportId, collections, openConversation, onChanged, onDeleted }: Props) {
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [live, setLive] = useState<AssistantTurn | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Citation | null>(null);
  const [copied, setCopied] = useState(false);
  const unsubscribe = useRef<(() => void) | null>(null);

  const load = useCallback(() => {
    researchApi
      .report(reportId)
      .then((data) => {
        setDetail(data);
        if (data.active && data.run_id) {
          const runId = data.run_id;
          unsubscribe.current?.();
          setLive(emptyAssistantTurn(runId));
          unsubscribe.current = subscribeRun(runId, (event) => {
            setLive((current) => (current ? applyRunEvent(current, event) : current));
            if (event.type === "run.completed" || event.type === "run.failed" || event.type === "run.cancelled") {
              unsubscribe.current = null;
              researchApi
                .report(reportId)
                .then((fresh) => {
                  setDetail(fresh);
                  setLive(null);
                })
                .catch((failure) => setError(errorText(failure)));
              onChanged();
            }
          });
        } else {
          setLive(null);
        }
      })
      .catch((failure) => setError(errorText(failure)));
  }, [reportId, onChanged]);

  useEffect(() => {
    setDetail(null);
    setSelected(null);
    setError("");
    load();
    return () => {
      unsubscribe.current?.();
      unsubscribe.current = null;
    };
  }, [load]);

  const liveText = live ? live.items.map((item) => (item.kind === "text" ? item.text : "")).join("") : "";
  const text = live ? liveText : (detail?.report ?? "");
  const prepared = useMemo(() => prepareReport(text), [text]);
  const html = useMemo(() => renderMarkdown(prepared.html), [prepared.html]);

  const onReportClick = (event: MouseEvent<HTMLDivElement>) => {
    const target = (event.target as HTMLElement).closest<HTMLAnchorElement>("a[data-cite]");
    if (!target) return;
    event.preventDefault();
    const n = Number(target.dataset.cite);
    setSelected(prepared.sources.find((item) => item.n === n) ?? null);
  };

  const copy = () => {
    navigator.clipboard
      ?.writeText(text)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => setError("Nie udało się skopiować raportu."));
  };

  const download = () => {
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    const name = (detail?.question ?? "raport").replace(/[^\p{L}\p{N}]+/gu, "-").slice(0, 60).replace(/^-|-$/g, "");
    link.download = `${name || "raport"}.md`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  };

  const remove = () => {
    if (!detail || !window.confirm("Usunąć badanie z listy? Rozmowa z raportem zostanie w historii czatu.")) return;
    researchApi
      .deleteReport(detail.id)
      .then(onDeleted)
      .catch((failure) => setError(errorText(failure)));
  };

  if (!detail) {
    return (
      <div className="grid h-full place-items-center text-muted">
        {error ? <span className="text-danger">{error}</span> : <span className="spinner size-5" />}
      </div>
    );
  }

  const running = live !== null && ACTIVE.has(live.status);
  const status = live?.status ?? detail.status;
  const failed = status === "failed" || status === "cancelled";
  const KindIcon = detail.kind === "scholar" ? ScholarIcon : GlobeIcon;

  return (
    <div className="flex h-full min-h-0">
      <div className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 pt-5 pb-16 md:px-8">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 font-medium text-accent">
              <KindIcon size={13} /> {detail.kind === "scholar" ? "Scholar Research" : "Deep Research"}
            </span>
            <span>{DEPTH_LABELS[detail.depth] ?? detail.depth}</span>
            <span>·</span>
            <span>{shortDate(detail.created_at)}</span>
          </div>
          <h2 className="mt-2 text-xl leading-snug font-semibold tracking-tight md:text-2xl">{detail.question}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className={ACTION} onClick={() => openConversation(detail.conversation_id)}>
              <ChatIcon size={15} /> Dopytaj w czacie
            </button>
            {running && live?.run_id && (
              <button type="button" className={ACTION} onClick={() => api.cancelRun(live.run_id!).catch(() => undefined)}>
                <StopIcon size={15} /> Zatrzymaj
              </button>
            )}
            {!running && text && (
              <>
                <button type="button" className={ACTION} onClick={copy}>
                  {copied ? <CheckIcon size={15} /> : <CopyIcon size={15} />} {copied ? "Skopiowano" : "Kopiuj"}
                </button>
                <button type="button" className={ACTION} onClick={download}>
                  <DownloadIcon size={15} /> Markdown
                </button>
              </>
            )}
            <button type="button" className={`${ACTION} ml-auto`} onClick={remove} aria-label="Usuń badanie z listy">
              <TrashIcon size={15} />
            </button>
          </div>

          {error && (
            <div role="alert" className="mt-4 rounded-xl border border-danger/40 bg-danger-soft px-3.5 py-2 text-sm text-danger">
              {error}
            </div>
          )}
          {running && live && (
            <div className="mt-5">
              <Progress turn={live} />
            </div>
          )}
          {failed && (
            <div className="mt-5 rounded-xl border border-danger/40 bg-danger-soft px-3.5 py-2 text-sm text-danger">
              {live?.error || detail.error || (status === "cancelled" ? "Badanie zatrzymane." : "Badanie nie powiodło się.")}
            </div>
          )}

          {text ? (
            <div
              className={`markdown mt-6 ${CITE_STYLES}`}
              onClick={onReportClick}
              dangerouslySetInnerHTML={{ __html: html }}
            />
          ) : (
            !running &&
            !failed && <p className="mt-6 text-muted">Raport jest pusty – otwórz rozmowę, aby zobaczyć przebieg badania.</p>
          )}

          {prepared.sources.length > 0 && (
            <section className="mt-8 border-t border-line pt-5" aria-label="Źródła">
              <h3 className="text-sm font-semibold tracking-wide text-muted uppercase">
                {prepared.heading ?? "Źródła"} ({prepared.sources.length})
              </h3>
              <ol className="mt-3 space-y-1">
                {prepared.sources.map((item) => (
                  <li key={item.n} id={`zrodlo-${item.n}`}>
                    <button
                      type="button"
                      onClick={() => setSelected(item)}
                      className={`flex w-full items-start gap-3 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-raised ${
                        selected?.n === item.n ? "bg-raised" : ""
                      }`}
                    >
                      <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-md bg-accent-soft text-[11px] font-semibold text-accent">
                        {item.n}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 text-sm">{item.title}</span>
                        {item.url && (
                          <span className="mt-0.5 flex items-center gap-1 text-xs text-muted">
                            <ExternalIcon size={12} /> {hostname(item.url)}
                          </span>
                        )}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>
      </div>
      {selected && (
        <SourcePanel
          citation={selected}
          collections={collections}
          defaultCollection={detail.collection_id}
          onClose={() => setSelected(null)}
          onSaved={onChanged}
        />
      )}
    </div>
  );
}

const ACTION =
  "inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm transition-colors hover:bg-raised";
