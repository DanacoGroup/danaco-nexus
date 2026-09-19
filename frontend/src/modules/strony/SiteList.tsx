// Lista stron i formularz nowej strony (opis → pierwsza wiadomość do asystenta).

import { useEffect, useState, type FormEvent } from "react";
import { PlusIcon, TrashIcon } from "../../components/icons";
import { errorText } from "../_tworczy/http";
import { GlobeIcon } from "../_tworczy/icons";
import { isValidAddress, slugify } from "../_tworczy/logic";
import { buttonPrimary, buttonSecondary, ErrorBanner, inputClass, labelClass, ModuleHeader, Spinner } from "../_tworczy/ui";
import { formatDate, sitesApi, type Site } from "./api";

const IDEAS = [
  "Strona pensjonatu nad morzem: galeria pokoi, cennik sezonowy, dojazd z mapą, formularz zapytania.",
  "Wizytówka firmy remontowej: usługi, realizacje przed/po, opinie klientów, kontakt.",
  "Landing page nowej aplikacji mobilnej: korzyści, zrzuty ekranu, FAQ, zapis na listę oczekujących.",
];

export function SiteList({ onOpen }: { onOpen: (address: string, firstPrompt?: string) => void }) {
  const [sites, setSites] = useState<Site[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [address, setAddress] = useState("");
  const [addressTouched, setAddressTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = () =>
    sitesApi
      .list()
      .then(setSites)
      .catch((failure) => setError(errorText(failure)));

  useEffect(() => {
    load();
  }, []);

  const effectiveAddress = addressTouched ? address : slugify(title);
  const addressOk = !title || isValidAddress(effectiveAddress);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !addressOk) return;
    setBusy(true);
    try {
      const site = await sitesApi.create(title.trim(), description.trim(), addressTouched ? address : undefined);
      const prompt = description.trim()
        ? `Zbuduj stronę „${site.title}”. Opis od użytkownika:\n${description.trim()}`
        : undefined;
      onOpen(site.address, prompt);
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (site: Site) => {
    if (!window.confirm(`Usunąć stronę „${site.title}” razem z wersjami i publikacją? Tej operacji nie można cofnąć.`)) return;
    try {
      await sitesApi.remove(site.address);
      load();
    } catch (failure) {
      setError(errorText(failure));
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ModuleHeader title="Strony" subtitle="Twórca stron WWW – opisz stronę, a asystent ją zbuduje i opublikuje">
        <button type="button" className={buttonPrimary} onClick={() => setCreating((value) => !value)}>
          <PlusIcon size={16} /> Nowa strona
        </button>
      </ModuleHeader>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-6">
        <div className="mx-auto max-w-5xl space-y-5">
          <ErrorBanner text={error} onClose={() => setError("")} />
          {creating && (
            <form onSubmit={create} className="animate-rise space-y-4 rounded-2xl border border-line bg-raised/40 p-4 md:p-5">
              <div className="grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className={labelClass}>Nazwa strony</span>
                  <input
                    className={inputClass}
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="np. Pensjonat Pod Lipą"
                    maxLength={200}
                    required
                    autoFocus
                  />
                </label>
                <label className="block">
                  <span className={labelClass}>Adres (/s/…)</span>
                  <input
                    className={`${inputClass} font-mono ${addressOk ? "" : "border-danger"}`}
                    value={effectiveAddress}
                    onChange={(event) => {
                      setAddressTouched(true);
                      setAddress(event.target.value.toLowerCase());
                    }}
                    maxLength={48}
                    aria-invalid={!addressOk}
                  />
                  {!addressOk && (
                    <span className="mt-1 block text-xs text-danger">Małe litery a–z, cyfry i łączniki (bez łącznika na końcach).</span>
                  )}
                </label>
              </div>
              <label className="block">
                <span className={labelClass}>Opis dla asystenta</span>
                <textarea
                  className={`${inputClass} min-h-28`}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Czego dotyczy strona, jakie sekcje, styl, kolory, dane kontaktowe, język…"
                  maxLength={4000}
                />
              </label>
              <div className="flex flex-wrap gap-2">
                {IDEAS.map((idea) => (
                  <button
                    key={idea}
                    type="button"
                    className="rounded-full border border-line px-3 py-1 text-xs text-muted transition-colors hover:bg-hover hover:text-fg"
                    onClick={() => setDescription(idea)}
                  >
                    {idea.split(":")[0]}
                  </button>
                ))}
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" className={buttonSecondary} onClick={() => setCreating(false)}>
                  Anuluj
                </button>
                <button type="submit" className={buttonPrimary} disabled={busy || !title.trim() || !addressOk}>
                  {busy ? "Tworzenie…" : "Utwórz i zbuduj"}
                </button>
              </div>
            </form>
          )}
          {sites === null ? (
            <Spinner label="Wczytywanie stron…" />
          ) : sites.length === 0 && !creating ? (
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-line px-6 py-14 text-center">
              <GlobeIcon size={36} className="text-muted" />
              <p className="max-w-md text-muted">
                Nie masz jeszcze żadnej strony. Opisz, czego potrzebujesz – asystent zbuduje stronę, a Ty zobaczysz ją na żywo
                i opublikujesz jednym kliknięciem.
              </p>
              <button type="button" className={buttonPrimary} onClick={() => setCreating(true)}>
                <PlusIcon size={16} /> Utwórz pierwszą stronę
              </button>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {sites.map((site) => (
                <article key={site.address} className="group flex flex-col rounded-2xl border border-line bg-app p-4 transition-colors hover:border-line-strong">
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <h2 className="truncate font-medium">{site.title}</h2>
                      <p className="truncate font-mono text-xs text-muted">/s/{site.address}/</p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${
                        site.published_at ? "bg-accent-soft text-accent" : "bg-raised text-muted"
                      }`}
                    >
                      {site.published_at ? "Opublikowana" : "Szkic"}
                    </span>
                  </div>
                  {site.description && <p className="mt-2 line-clamp-2 text-sm text-muted">{site.description}</p>}
                  {site.publish_request && <p className="mt-2 text-xs text-accent">Asystent prosi o publikację</p>}
                  <div className="mt-auto flex items-center gap-2 pt-4">
                    <span className="flex-1 text-xs text-muted">Zmieniona {formatDate(site.updated_at)}</span>
                    <button type="button" className="icon-btn size-8" aria-label={`Usuń ${site.title}`} onClick={() => remove(site)}>
                      <TrashIcon size={16} />
                    </button>
                    <button type="button" className={buttonSecondary} onClick={() => onOpen(site.address)}>
                      Otwórz
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
