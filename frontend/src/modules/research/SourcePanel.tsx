// Widok źródła obok raportu: pozycja z listy źródeł, podgląd strony i zapis w bazie wiedzy.

import { useEffect, useState } from "react";
import { CheckIcon, CloseIcon } from "../../components/icons";
import { errorText, researchApi, type Collection, type PagePreview } from "./api";
import { hostname, type Citation } from "./citations";
import { ExternalIcon, LibraryIcon } from "./icons";

interface Props {
  citation: Citation;
  collections: Collection[];
  defaultCollection: string | null;
  onClose: () => void;
  onSaved: () => void;
}

/** Czy pozycja listy źródeł zawiera coś poza tytułem i adresem (np. autorów, datę, cytowanie). */
function hasDetails(citation: Citation): boolean {
  const rest = citation.text
    .replace(citation.url, "")
    .replace(citation.title, "")
    .replace(/[\s–—\-:,.()[\]<>]+/g, "");
  return rest.length > 0;
}

export function SourcePanel({ citation, collections, defaultCollection, onClose, onSaved }: Props) {
  const [preview, setPreview] = useState<PagePreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [target, setTarget] = useState(defaultCollection ?? collections[0]?.id ?? "");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setPreview(null);
    setError("");
    setSaved(false);
  }, [citation.n, citation.url]);

  useEffect(() => {
    if (!target && collections.length) setTarget(defaultCollection ?? collections[0].id);
  }, [collections, defaultCollection, target]);

  const loadPreview = () => {
    if (!citation.url) return;
    setLoading(true);
    setError("");
    researchApi
      .preview(citation.url)
      .then(setPreview)
      .catch((failure) => setError(errorText(failure)))
      .finally(() => setLoading(false));
  };

  const save = () => {
    if (!target || !citation.url) return;
    setSaving(true);
    setError("");
    researchApi
      .addSource(target, { url: citation.url })
      .then(() => {
        setSaved(true);
        onSaved();
      })
      .catch((failure) => setError(errorText(failure)))
      .finally(() => setSaving(false));
  };

  return (
    <aside
      className="fixed inset-0 z-30 flex flex-col bg-app lg:static lg:z-auto lg:w-[420px] lg:shrink-0 lg:border-l lg:border-line"
      aria-label={`Źródło ${citation.n}`}
    >
      <header className="safe-top flex items-center gap-2 border-b border-line px-4 py-2.5">
        <span className="grid size-6 shrink-0 place-items-center rounded-md bg-accent-soft text-xs font-semibold text-accent">
          {citation.n}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-medium">
          {citation.url ? hostname(citation.url) : "Źródło"}
        </span>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Zamknij podgląd źródła">
          <CloseIcon size={18} />
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <h3 className="text-[15px] leading-snug font-semibold">{citation.title || citation.url}</h3>
        {hasDetails(citation) && <p className="mt-2 text-sm break-words text-muted">{citation.text}</p>}
        {citation.url && (
          <div className="mt-4 flex flex-wrap gap-2">
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm transition-colors hover:bg-raised"
            >
              <ExternalIcon size={15} /> Otwórz stronę
            </a>
            {!preview && (
              <button
                type="button"
                onClick={loadPreview}
                disabled={loading}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm transition-colors hover:bg-raised disabled:opacity-60"
              >
                {loading ? <span className="spinner size-3.5" /> : null}
                {loading ? "Pobieram…" : "Pokaż treść"}
              </button>
            )}
          </div>
        )}
        {citation.url && collections.length > 0 && (
          <div className="mt-4 rounded-xl border border-line bg-raised/50 p-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <LibraryIcon size={16} className="text-muted" /> Zapisz w bazie wiedzy
            </div>
            <div className="mt-2 flex gap-2">
              <select
                value={target}
                onChange={(event) => setTarget(event.target.value)}
                className="min-w-0 flex-1 rounded-lg border border-line bg-app px-2 py-1.5 text-sm"
                aria-label="Kolekcja"
              >
                {collections.map((collection) => (
                  <option key={collection.id} value={collection.id}>
                    {collection.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={save}
                disabled={saving || saved}
                className="inline-flex items-center gap-1.5 rounded-lg bg-accent-fill px-3 py-1.5 text-sm font-medium text-on-accent transition-colors hover:bg-accent-fill-hover disabled:opacity-60"
              >
                {saved ? <CheckIcon size={15} /> : saving ? <span className="spinner size-3.5" /> : null}
                {saved ? "Zapisano" : "Zapisz"}
              </button>
            </div>
          </div>
        )}
        {error && (
          <div role="alert" className="mt-4 rounded-xl border border-danger/40 bg-danger-soft px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}
        {preview && (
          <article className="mt-5 border-t border-line pt-4">
            <div className="text-xs text-muted">
              {[preview.site_name, preview.author, preview.published?.slice(0, 10)].filter(Boolean).join(" · ")}
            </div>
            <h4 className="mt-1 font-semibold">{preview.title}</h4>
            {preview.description && <p className="mt-1 text-sm text-muted">{preview.description}</p>}
            <div className="mt-3 text-sm leading-6 break-words whitespace-pre-wrap">{preview.text}</div>
            {preview.truncated && <p className="mt-3 text-xs text-muted">Treść skrócona.</p>}
          </article>
        )}
      </div>
    </aside>
  );
}
