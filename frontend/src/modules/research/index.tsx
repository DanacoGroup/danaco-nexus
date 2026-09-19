// Moduł Research: Deep Research (sieć) i Scholar Research (prace naukowe) z raportem i przypisami.

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../../api";
import { CloseIcon, PlusIcon } from "../../components/icons";
import type { ModulePageProps, NexusModule } from "../registry";
import {
  ACTIVE,
  errorText,
  researchApi,
  shortDate,
  type Collection,
  type Report,
  type ResearchDepth,
  type ResearchKind,
} from "./api";
import { GlobeIcon, HistoryIcon, ResearchIcon, ScholarIcon } from "./icons";
import { ReportView } from "./ReportView";

const KINDS: { id: ResearchKind; label: string; hint: string; icon: typeof GlobeIcon }[] = [
  { id: "deep", label: "Deep Research", hint: "Sieć: strony, raporty, media, dokumentacja", icon: GlobeIcon },
  { id: "scholar", label: "Scholar", hint: "Tylko prace naukowe, cytowania APA", icon: ScholarIcon },
];
const DEPTHS: { id: ResearchDepth; label: string; hint: string }[] = [
  { id: "quick", label: "Szybkie", hint: "4–6 źródeł, kilka minut" },
  { id: "standard", label: "Standardowe", hint: "10–15 źródeł" },
  { id: "deep", label: "Dogłębne", hint: "25+ źródeł, podagenci" },
];
const EXAMPLES = [
  "Czy pompa ciepła opłaca się w domu z lat 80.? Koszty, dotacje i warunki w Polsce w 2026 r.",
  "Porównaj ceny i obłożenie apartamentów na wynajem krótkoterminowy w Gdańsku i Sopocie.",
  "Jakie są najnowsze wyniki badań nad skutecznością terapii światłem w zaburzeniach snu?",
];
const NO_SAVE = "__brak__";
const PREFERENCES_KEY = "nexus.research.preferencje";

function readPreferences(): { kind: ResearchKind; depth: ResearchDepth } {
  try {
    const data = JSON.parse(localStorage.getItem(PREFERENCES_KEY) ?? "{}");
    return {
      kind: data.kind === "scholar" ? "scholar" : "deep",
      depth: ["quick", "standard", "deep"].includes(data.depth) ? data.depth : "standard",
    };
  } catch {
    return { kind: "deep", depth: "standard" };
  }
}

// Otwarte badanie w adresie (?badanie=<id>) – odświeżenie strony i link wracają do raportu.
function reportFromUrl(): string | null {
  const id = new URLSearchParams(window.location.search).get("badanie");
  return id && /^[0-9a-f-]{36}$/.test(id) ? id : null;
}

function setReportInUrl(id: string | null): void {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set("badanie", id);
  else url.searchParams.delete("badanie");
  window.history.replaceState(window.history.state, "", url);
}

function StatusDot({ status }: { status: string }) {
  if (ACTIVE.has(status)) return <span className="spinner size-3 text-accent" aria-label="W toku" />;
  const color = status === "done" ? "bg-success" : status === "failed" ? "bg-danger" : "bg-muted";
  return <span className={`size-2 shrink-0 rounded-full ${color}`} aria-hidden="true" />;
}

function NewResearch({
  collections,
  onStarted,
}: {
  collections: Collection[];
  onStarted: (report: Report) => void;
}) {
  const initial = readPreferences();
  const [question, setQuestion] = useState("");
  const [kind, setKind] = useState<ResearchKind>(initial.kind);
  const [depth, setDepth] = useState<ResearchDepth>(initial.depth);
  const [collection, setCollection] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (question.trim().length < 3 || busy) return;
    setBusy(true);
    setError("");
    try {
      localStorage.setItem(PREFERENCES_KEY, JSON.stringify({ kind, depth }));
    } catch {
      /* brak pamięci lokalnej – bez zapamiętywania wyboru */
    }
    researchApi
      .startResearch({
        question: question.trim(),
        kind,
        depth,
        collection_id: collection && collection !== NO_SAVE ? collection : null,
        save_sources: collection !== NO_SAVE,
      })
      .then(onStarted)
      .catch((failure) => setError(errorText(failure)))
      .finally(() => setBusy(false));
  };

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col px-4 py-8 md:py-14">
      <div className="flex items-center gap-3">
        <span className="grid size-11 place-items-center rounded-2xl bg-accent-soft text-accent">
          <ResearchIcon size={24} />
        </span>
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Research</h2>
          <p className="text-sm text-muted">Badanie tematu w wielu źródłach i raport z przypisami.</p>
        </div>
      </div>
      <form onSubmit={submit} className="mt-7 space-y-5">
        <div className="rounded-3xl border border-line bg-raised/40 p-2 focus-within:border-line-strong">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) submit();
            }}
            rows={4}
            maxLength={5000}
            placeholder="Czego mam się dowiedzieć? Opisz pytanie, kontekst i czego oczekujesz w raporcie."
            className="block w-full resize-none bg-transparent px-3 py-2 text-[15px] outline-none placeholder:text-muted"
            aria-label="Pytanie badawcze"
          />
        </div>
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Rodzaj</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {KINDS.map((option) => (
              <button
                key={option.id}
                type="button"
                aria-pressed={kind === option.id}
                onClick={() => setKind(option.id)}
                className={`flex items-start gap-3 rounded-2xl border px-3.5 py-3 text-left transition-colors ${
                  kind === option.id ? "border-accent bg-accent-soft/60" : "border-line hover:bg-raised"
                }`}
              >
                <option.icon size={20} className={kind === option.id ? "text-accent" : "text-muted"} />
                <span>
                  <span className="block text-sm font-medium">{option.label}</span>
                  <span className="block text-xs text-muted">{option.hint}</span>
                </span>
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Głębokość</legend>
          <div className="grid grid-cols-3 gap-1 rounded-2xl border border-line p-1">
            {DEPTHS.map((option) => (
              <button
                key={option.id}
                type="button"
                aria-pressed={depth === option.id}
                onClick={() => setDepth(option.id)}
                className={`rounded-xl px-2 py-2 text-center transition-colors ${
                  depth === option.id ? "bg-accent text-on-accent" : "hover:bg-raised"
                }`}
              >
                <span className="block text-sm font-medium">{option.label}</span>
                <span className={`block text-[11px] ${depth === option.id ? "text-on-accent/80" : "text-muted"}`}>
                  {option.hint}
                </span>
              </button>
            ))}
          </div>
        </fieldset>
        <label className="block">
          <span className="mb-2 block text-sm font-medium">Źródła zapisz w bazie wiedzy</span>
          <select
            value={collection}
            onChange={(event) => setCollection(event.target.value)}
            className="w-full rounded-xl border border-line bg-app px-3 py-2 text-sm"
          >
            <option value="">Kolekcja „Research” (domyślna)</option>
            {collections
              .filter((item) => item.name !== "Research")
              .map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            <option value={NO_SAVE}>Nie zapisuj źródeł</option>
          </select>
        </label>
        {error && (
          <div role="alert" className="rounded-xl border border-danger/40 bg-danger-soft px-3.5 py-2 text-sm text-danger">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={busy || question.trim().length < 3}
          className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-accent px-4 py-3 font-medium text-on-accent transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          {busy ? <span className="spinner" /> : <ResearchIcon size={18} />}
          Rozpocznij badanie
        </button>
      </form>
      <div className="mt-8">
        <div className="mb-2 text-xs font-medium tracking-wide text-muted uppercase">Przykłady</div>
        <div className="space-y-2">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setQuestion(example)}
              className="block w-full rounded-2xl border border-line px-4 py-2.5 text-left text-sm text-muted transition-colors hover:bg-raised hover:text-fg"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ResearchPage({ openConversation }: ModulePageProps) {
  const [reports, setReports] = useState<Report[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [current, setCurrent] = useState<string | null>(reportFromUrl());
  const [historyOpen, setHistoryOpen] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    researchApi
      .reports()
      .then(setReports)
      .catch((failure) => setError(failure instanceof ApiError && failure.status === 401 ? "Sesja wygasła – zaloguj się ponownie." : errorText(failure)));
    researchApi
      .collections()
      .then(setCollections)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Lista odświeża się, dopóki któreś badanie trwa (stan widoczny także bez otwierania raportu).
  useEffect(() => {
    if (!reports.some((report) => ACTIVE.has(report.status))) return;
    const timer = window.setInterval(refresh, 8000);
    return () => window.clearInterval(timer);
  }, [reports, refresh]);

  const select = (id: string | null) => {
    setCurrent(id);
    setHistoryOpen(false);
    setReportInUrl(id);
  };

  const history = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 px-3 pt-3 pb-2">
        <button
          type="button"
          onClick={() => select(null)}
          className="inline-flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-hover"
        >
          <PlusIcon size={18} /> Nowe badanie
        </button>
        <button type="button" className="icon-btn md:hidden" onClick={() => setHistoryOpen(false)} aria-label="Zamknij">
          <CloseIcon size={18} />
        </button>
      </div>
      <div className="px-5 pt-2 pb-1 text-xs font-medium text-muted">Badania</div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {reports.length === 0 && <p className="px-3 py-2 text-sm text-muted">Brak badań – zacznij od pytania.</p>}
        {reports.map((report) => (
          <button
            key={report.id}
            type="button"
            onClick={() => select(report.id)}
            className={`flex w-full items-start gap-2.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-hover ${
              current === report.id ? "bg-hover" : ""
            }`}
          >
            <span className="mt-1.5 grid w-3 shrink-0 place-items-center">
              <StatusDot status={report.status} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="line-clamp-2 text-sm">{report.question}</span>
              <span className="text-xs text-muted">
                {report.kind === "scholar" ? "Scholar" : "Deep"} · {shortDate(report.created_at)}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="flex h-full min-h-0 bg-app">
      <aside className="hidden w-72 shrink-0 border-r border-line bg-side md:block">{history}</aside>
      {historyOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button type="button" className="absolute inset-0 bg-black/40" onClick={() => setHistoryOpen(false)} aria-label="Zamknij" />
          <div className="safe-top absolute inset-y-0 left-0 w-[85%] max-w-xs bg-side shadow-xl">{history}</div>
        </div>
      )}
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-line/60 px-3 py-2 md:hidden">
          <button type="button" className="icon-btn" onClick={() => setHistoryOpen(true)} aria-label="Historia badań">
            <HistoryIcon size={19} />
          </button>
          <span className="text-sm font-medium">Research</span>
        </div>
        {error && (
          <div role="alert" onClick={() => setError("")} className="m-3 rounded-xl border border-danger/40 bg-danger-soft px-3.5 py-2 text-sm text-danger">
            {error}
          </div>
        )}
        <div className="min-h-0 flex-1">
          {current ? (
            <ReportView
              key={current}
              reportId={current}
              collections={collections}
              openConversation={openConversation}
              onChanged={refresh}
              onDeleted={() => {
                select(null);
                refresh();
              }}
            />
          ) : (
            <div className="h-full overflow-y-auto">
              <NewResearch
                collections={collections}
                onStarted={(report) => {
                  refresh();
                  select(report.id);
                }}
              />
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export const module: NexusModule = {
  id: "research",
  label: "Research",
  description: "Deep Research i Scholar Research: badanie tematu w wielu źródłach, raport z przypisami.",
  icon: ResearchIcon,
  order: 30,
  Page: ResearchPage,
};
