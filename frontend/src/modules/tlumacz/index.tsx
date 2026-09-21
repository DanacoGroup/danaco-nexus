// Moduł Tłumacz: tekst na bieżąco (języki, styl, słowniczek) i dokumenty z zachowaniem układu.

import { useEffect, useRef, useState } from "react";
import { downloadUrl, type FileInfo } from "../../api";
import { CheckIcon, DownloadIcon } from "../../components/icons";
import type { ModulePageProps, NexusModule } from "../registry";
import { cancelJob, errorText, requestJson, waitForJob, type JobState } from "../_tworczy/http";
import { CopyIcon, SwapIcon, TranslateIcon } from "../_tworczy/icons";
import { worthTranslating } from "../_tworczy/logic";
import { buttonPrimary, buttonSecondary, ErrorBanner, FileDrop, inputClass, labelClass, ModuleHeader, Segmented, Spinner } from "../_tworczy/ui";
import { Select } from "../../ui";

const BASE = "/api/tlumacz";
const DOCUMENT_ACCEPT = ".docx,.pptx,.pdf,.txt,.md";
const AUTO_DELAY_MS = 1200;

interface Language {
  code: string;
  name: string;
}
interface Style {
  id: string;
  description: string;
}

function LanguageSelect({
  value,
  onChange,
  languages,
  allowAuto,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  languages: Language[];
  allowAuto?: boolean;
  label: string;
}) {
  // Lista z biblioteki, nie `select` systemowy: w oknie produktu natywne pole wyboru
  // rysuje się barwami systemu i w motywie ciemnym odstaje od reszty jak łata.
  return (
    <Select
      label={label}
      hideLabel
      size="sm"
      className="w-44"
      value={value}
      onChange={onChange}
      options={[
        ...(allowAuto ? [{ value: "auto", label: "Wykryj język" }] : []),
        ...languages.map((language) => ({ value: language.code, label: language.name })),
      ]}
    />
  );
}

interface DocumentJob {
  file: FileInfo;
  target: string;
  state: JobState | null;
  error: string;
}

function TranslatorPage(_: ModulePageProps) {
  const [tab, setTab] = useState<"text" | "documents">("text");
  const [languages, setLanguages] = useState<Language[]>([]);
  const [styles, setStyles] = useState<Style[]>([]);
  const [source, setSource] = useState("auto");
  const [target, setTarget] = useState("en");
  const [style, setStyle] = useState("neutralny");
  const [glossary, setGlossary] = useState("");
  const [showGlossary, setShowGlossary] = useState(false);
  const [text, setText] = useState("");
  const [translation, setTranslation] = useState("");
  const [detected, setDetected] = useState("");
  const [auto, setAuto] = useState(true);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState<DocumentJob[]>([]);
  const lastTranslated = useRef("");
  const pending = useRef<AbortController | null>(null);

  useEffect(() => {
    requestJson<{ languages: Language[]; styles: Style[] }>("GET", `${BASE}/jezyki`)
      .then((data) => {
        setLanguages(data.languages);
        setStyles(data.styles);
      })
      .catch((failure) => setError(errorText(failure)));
  }, []);

  const translate = async (force = false) => {
    const content = text;
    if (!content.trim() || (!force && !worthTranslating(content, lastTranslated.current))) return;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    setError("");
    try {
      const result = await requestJson<{ translation: string; source_language: string }>(
        "POST",
        `${BASE}/tekst`,
        { text: content, target, source, style, glossary },
        controller.signal,
      );
      lastTranslated.current = content;
      setTranslation(result.translation);
      setDetected(result.source_language);
    } catch (failure) {
      if ((failure as Error).name !== "AbortError") setError(errorText(failure));
    } finally {
      if (pending.current === controller) setBusy(false);
    }
  };

  // Tłumaczenie na bieżąco: po przerwie w pisaniu albo po zmianie języka lub stylu.
  useEffect(() => {
    lastTranslated.current = "";
  }, [target, source, style, glossary]);
  useEffect(() => {
    if (!auto || !text.trim()) return;
    const timer = setTimeout(() => translate(), AUTO_DELAY_MS);
    return () => clearTimeout(timer);
  }, [text, target, source, style, auto]);

  const swap = () => {
    const from = source === "auto" ? detected || "pl" : source;
    setSource(target);
    setTarget(from);
    if (translation) {
      setText(translation);
      setTranslation(text);
    }
  };

  const copy = () => {
    navigator.clipboard
      .writeText(translation)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => setError("Nie udało się skopiować do schowka."));
  };

  const startDocument = async (file: FileInfo) => {
    const entry: DocumentJob = { file, target, state: null, error: "" };
    const update = (patch: Partial<DocumentJob>) =>
      setJobs((items) => items.map((item) => (item.file.id === file.id && item.target === entry.target ? { ...item, ...patch } : item)));
    setJobs((items) => [entry, ...items]);
    try {
      const started = await requestJson<JobState>("POST", `${BASE}/dokument`, { file_id: file.id, target, source, style, glossary });
      update({ state: started });
      const final = await waitForJob(BASE, started, (state) => update({ state }));
      update({ state: final, error: final.status === "failed" ? final.error : "" });
    } catch (failure) {
      update({ error: errorText(failure) });
    }
  };

  const languageName = (code: string) => languages.find((item) => item.code === code)?.name ?? code;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ModuleHeader title="Tłumacz" subtitle="Tekst na bieżąco i dokumenty DOCX, PPTX, PDF z zachowaniem układu">
        <Segmented
          label="Rodzaj tłumaczenia"
          value={tab}
          onChange={setTab}
          options={[
            { value: "text", label: "Tekst" },
            { value: "documents", label: "Dokumenty" },
          ]}
        />
      </ModuleHeader>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-6">
        <div className="mx-auto max-w-6xl space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <LanguageSelect label="Język źródłowy" value={source} onChange={setSource} languages={languages} allowAuto />
            <button type="button" className="icon-btn" onClick={swap} aria-label="Zamień języki" disabled={tab !== "text"}>
              <SwapIcon size={18} />
            </button>
            <LanguageSelect label="Język docelowy" value={target} onChange={setTarget} languages={languages} />
            <Select
              label="Styl tłumaczenia"
              hideLabel
              size="sm"
              className="w-52"
              value={style}
              onChange={setStyle}
              options={styles.map((item) => ({
                value: item.id,
                label: `Styl: ${item.id}`,
                description: item.description,
              }))}
            />
            <button type="button" className={buttonSecondary} onClick={() => setShowGlossary((value) => !value)} aria-expanded={showGlossary}>
              Słowniczek{glossary.trim() ? " ✓" : ""}
            </button>
          </div>
          {showGlossary && (
            <label className="block">
              <span className={labelClass}>Słowniczek – obowiązujące tłumaczenia (jeden termin w wierszu)</span>
              <textarea
                className={`${inputClass} min-h-20 font-mono`}
                value={glossary}
                onChange={(event) => setGlossary(event.target.value)}
                placeholder={"pensjonat = guesthouse\ndoba hotelowa = hotel night"}
                maxLength={4000}
              />
            </label>
          )}
          <ErrorBanner text={error} onClose={() => setError("")} />

          {tab === "text" ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div className="flex flex-col rounded-2xl border border-line focus-within:border-accent">
                <textarea
                  className="min-h-64 flex-1 resize-y rounded-2xl bg-transparent p-4 text-[15px] outline-none placeholder:text-muted"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) translate(true);
                  }}
                  placeholder="Wpisz lub wklej tekst do przetłumaczenia…"
                  maxLength={30000}
                  aria-label="Tekst źródłowy"
                />
                <div className="flex items-center gap-2 border-t border-line/60 px-3 py-2 text-xs text-muted">
                  <label className="flex items-center gap-1.5">
                    <input type="checkbox" checked={auto} onChange={(event) => setAuto(event.target.checked)} className="accent-[var(--accent)]" />
                    Tłumacz na bieżąco
                  </label>
                  <span className="flex-1 text-right tabular-nums">{text.length.toLocaleString("pl-PL")} / 30 000</span>
                  <button type="button" className={buttonPrimary} onClick={() => translate(true)} disabled={!text.trim() || busy}>
                    Tłumacz
                  </button>
                </div>
              </div>
              <div className="flex flex-col rounded-2xl border border-line bg-raised/40">
                <div className="min-h-64 flex-1 p-4 text-[15px] whitespace-pre-wrap" aria-live="polite">
                  {translation || <span className="text-muted">Tłumaczenie pojawi się tutaj.</span>}
                </div>
                <div className="flex items-center gap-2 border-t border-line/60 px-3 py-2 text-xs text-muted">
                  {busy ? <Spinner label="Tłumaczę…" /> : detected && source === "auto" ? <span>Wykryto: {languageName(detected)}</span> : null}
                  <span className="flex-1" />
                  <button type="button" className="icon-btn size-8" onClick={copy} disabled={!translation} aria-label="Kopiuj tłumaczenie">
                    {copied ? <CheckIcon size={16} /> : <CopyIcon size={16} />}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <FileDrop
                accept={DOCUMENT_ACCEPT}
                hint={`Dokument DOCX, PPTX, PDF (z tekstem), TXT lub MD – tłumaczenie na: ${languageName(target)}`}
                onUploaded={startDocument}
                onError={setError}
              />
              <p className="text-sm text-muted">
                Układ, formatowanie, tabele i grafika zostają zachowane. Skany PDF najpierw przepuść przez OCR na czacie.
              </p>
              <ul className="space-y-2">
                {jobs.map((job) => {
                  const state = job.state;
                  const result = state?.status === "done" ? state.result?.files[0] : undefined;
                  return (
                    <li key={`${job.file.id}-${job.target}`} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line px-4 py-3 text-sm">
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">{job.file.name}</p>
                        <p className={`truncate text-xs ${job.error ? "text-danger" : "text-muted"}`}>
                          → {languageName(job.target)} ·{" "}
                          {job.error || (state?.status === "done" ? "gotowe" : state?.status === "cancelled" ? "anulowano" : state?.progress || "w kolejce…")}
                        </p>
                      </div>
                      {state?.status === "running" && (
                        <>
                          <span className="spinner" />
                          <button type="button" className={buttonSecondary} onClick={() => cancelJob(BASE, state.id).catch(() => undefined)}>
                            Anuluj
                          </button>
                        </>
                      )}
                      {result && (
                        <a className={buttonPrimary} href={downloadUrl(result)} download={result.name}>
                          <DownloadIcon size={16} /> {result.name}
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export const module: NexusModule = {
  id: "tlumacz",
  label: "Tłumacz",
  description: "Tłumaczenie tekstu na bieżąco oraz dokumentów DOCX, PPTX i PDF z zachowaniem układu.",
  icon: TranslateIcon,
  order: 64,
  Page: TranslatorPage,
};
