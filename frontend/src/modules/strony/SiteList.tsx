// Lista stron i formularz nowej strony (opis → pierwsza wiadomość do asystenta).

import { useEffect, useState, type FormEvent } from "react";
import { PlusIcon, TrashIcon } from "../../components/icons";
import { errorText } from "../_tworczy/http";
import { GlobeIcon } from "../_tworczy/icons";
import { isValidAddress, slugify } from "../_tworczy/logic";
import { buttonPrimary, buttonSecondary, ErrorBanner, inputClass, labelClass, ModuleHeader, Spinner } from "../_tworczy/ui";
import { Stagger } from "../../ui";
import { formatDate, sitesApi, type Preset, type Site, type SzablonKolekcji } from "./api";

const IDEAS = [
  "Strona pensjonatu nad morzem: galeria pokoi, cennik sezonowy, dojazd z mapą, formularz zapytania.",
  "Wizytówka firmy remontowej: usługi, realizacje przed/po, opinie klientów, kontakt.",
  "Landing page nowej aplikacji mobilnej: korzyści, zrzuty ekranu, FAQ, zapis na listę oczekujących.",
];

/** Ile presetów pokazujemy od razu — reszta po „Pokaż wszystkie”. */
const PRESETY_NA_START = 8;

/** Gotowe układy branżowe: druga droga na start, obok opisu własnymi słowami.
 *
 * Nie każdy wie, co napisać w polu „opisz stronę”. Preset daje gotową strukturę
 * podstron i treści do podmiany — od tego łatwiej zacząć niż od pustej kartki.
 */
function PasekPresetow({
  presety,
  wszystkie,
  onWszystkie,
  onWybor,
  zajety,
}: {
  presety: Preset[] | null;
  wszystkie: boolean;
  onWszystkie: () => void;
  onWybor: (preset: Preset) => void;
  zajety: boolean;
}) {
  if (!presety?.length) return null;
  const widoczne = wszystkie ? presety : presety.slice(0, PRESETY_NA_START);
  return (
    <section className="rounded-2xl border border-line bg-raised/40 p-4 md:p-5">
      <h2 className="font-heading text-base font-semibold text-fg">Albo zacznij od gotowego układu</h2>
      <p className="mt-1 text-sm text-muted">
        Zestaw branżowy: komplet podstron, sekcje i przykładowe treści do podmiany. Witryna staje
        w kilka minut, a potem poprawiasz ją rozmową.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {widoczne.map((preset) => (
          <button
            key={preset.preset}
            type="button"
            disabled={zajety}
            onClick={() => onWybor(preset)}
            title={preset.opis || preset.preset}
            className="ui-nacisk rounded-xl border border-line-control px-3.5 py-2 text-left text-sm transition-colors hover:bg-hover disabled:opacity-50"
          >
            <span className="block font-medium text-fg">{preset.nazwa}</span>
            <span className="block font-mono text-[11px] text-subtle">{preset.preset}</span>
          </button>
        ))}
        {!wszystkie && presety.length > PRESETY_NA_START && (
          <button
            type="button"
            onClick={onWszystkie}
            className="rounded-xl px-3.5 py-2 text-sm text-muted transition-colors hover:text-fg"
          >
            Pokaż wszystkie ({presety.length})
          </button>
        )}
      </div>
    </section>
  );
}

/** Gotowe witryny z kolekcji szablonów otwartych — trzecia droga na start.
 *
 * Preset daje strukturę i treści po polsku, ale trzeba go zbudować (minuty). Szablon
 * z kolekcji jest już zbudowany: wchodzi do szkicu w sekundy, za to z cudzymi treściami
 * i własną licencją — dlatego licencja stoi przy każdej pozycji, a nie w drobnym druku.
 */
function PasekSzablonow({
  szablony,
  wszystkie,
  onWszystkie,
  onWybor,
  zajety,
}: {
  szablony: SzablonKolekcji[];
  wszystkie: boolean;
  onWszystkie: () => void;
  onWybor: (szablon: SzablonKolekcji) => void;
  zajety: boolean;
}) {
  if (!szablony.length) return null;
  const widoczne = wszystkie ? szablony : szablony.slice(0, PRESETY_NA_START);
  return (
    <section className="rounded-2xl border border-line bg-raised/40 p-4 md:p-5">
      <h2 className="font-heading text-base font-semibold text-fg">Gotowe witryny z kolekcji</h2>
      <p className="mt-1 text-sm text-muted">
        Projekty otwarte, już zbudowane: wchodzą do szkicu od ręki. Treści są cudze i po
        angielsku — Nexus podmieni je na Twoje. Przy każdej pozycji stoi jej licencja.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {widoczne.map((szablon) => (
          <button
            key={szablon.id}
            type="button"
            disabled={zajety}
            onClick={() => onWybor(szablon)}
            className="ui-nacisk rounded-xl border border-line-control px-3.5 py-2 text-left text-sm transition-colors hover:bg-hover disabled:opacity-50"
          >
            <span className="block font-medium text-fg">{szablon.nazwa}</span>
            <span className="block text-[11px] text-subtle">
              {szablon.podstrony > 0 ? `${szablon.podstrony} podstron · ` : ""}
              {szablon.licencja || "licencja w opisie"}
            </span>
          </button>
        ))}
        {!wszystkie && szablony.length > PRESETY_NA_START && (
          <button
            type="button"
            onClick={onWszystkie}
            className="rounded-xl px-3.5 py-2 text-sm text-muted transition-colors hover:text-fg"
          >
            Pokaż wszystkie ({szablony.length})
          </button>
        )}
      </div>
    </section>
  );
}

export function SiteList({ onOpen }: { onOpen: (address: string, firstPrompt?: string) => void }) {
  const [sites, setSites] = useState<Site[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [address, setAddress] = useState("");
  const [addressTouched, setAddressTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [presety, setPresety] = useState<Preset[] | null>(null);
  const [wszystkiePresety, setWszystkiePresety] = useState(false);
  const [szablony, setSzablony] = useState<SzablonKolekcji[]>([]);
  const [wszystkieSzablony, setWszystkieSzablony] = useState(false);

  const load = () =>
    sitesApi
      .list()
      .then(setSites)
      .catch((failure) => setError(errorText(failure)));

  useEffect(() => {
    load();
    // Presety branżowe Danaco Web Kit: witryna z gotową strukturą i treściami powstaje
    // w minuty. Do tej pory moduł o nich nie wspominał — zestaw stał na serwerze, a
    // użytkownik dostawał puste pole „opisz stronę”.
    sitesApi
      .kit()
      .then((katalog) => {
        setPresety(katalog.dostepny ? katalog.presety : []);
        setSzablony(katalog.dostepny ? (katalog.szablony ?? []) : []);
      })
      .catch(() => setPresety([]));
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

  const zPresetu = async (preset: Preset) => {
    setBusy(true);
    try {
      const site = await sitesApi.create(preset.nazwa, `Witryna: ${preset.nazwa}.`);
      onOpen(
        site.address,
        `Zbuduj witrynę z presetu „${preset.preset}” zestawu Danaco Web Kit ` +
          `(narzędzie site_from_kit, strona „${site.address}”). Motyw dobierz sam do branży — ` +
          `sprawdź listę w site_kit_catalog i powiedz, który wybrałeś i dlaczego. ` +
          `Po zbudowaniu pokaż mi spis podstron i powiedz, co dopisać, żeby treści były moje, ` +
          `a nie przykładowe.`,
      );
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setBusy(false);
    }
  };

  const zSzablonu = async (szablon: SzablonKolekcji) => {
    setBusy(true);
    try {
      const site = await sitesApi.create(szablon.nazwa, `Witryna z szablonu ${szablon.nazwa}.`);
      onOpen(
        site.address,
        `Wstaw do strony „${site.address}” gotowy szablon „${szablon.id}” z kolekcji ` +
          `(narzędzie site_from_template), a potem podmień treści na moje: nazwę, opisy, ` +
          `kontakt i teksty po polsku. Powiedz, czego potrzebujesz ode mnie.`,
      );
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
            <div className="space-y-5">
              <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-line px-6 py-12 text-center">
                <GlobeIcon size={36} className="text-muted" />
                <p className="max-w-md text-muted">
                  Nie masz jeszcze żadnej strony. Opisz, czego potrzebujesz – asystent zbuduje stronę, a Ty zobaczysz ją na żywo
                  i opublikujesz jednym kliknięciem.
                </p>
                <button type="button" className={buttonPrimary} onClick={() => setCreating(true)}>
                  <PlusIcon size={16} /> Utwórz pierwszą stronę
                </button>
              </div>
              <PasekPresetow
                presety={presety}
                wszystkie={wszystkiePresety}
                onWszystkie={() => setWszystkiePresety(true)}
                onWybor={zPresetu}
                zajety={busy}
              />
              <PasekSzablonow
                szablony={szablony}
                wszystkie={wszystkieSzablony}
                onWszystkie={() => setWszystkieSzablony(true)}
                onWybor={zSzablonu}
                zajety={busy}
              />
            </div>
          ) : (
            /* Karty dochodzą po odpowiedzi serwera — kaskada wejścia (motion, rozdz. 5). */
            <Stagger className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
            </Stagger>
          )}
        </div>
      </div>
    </div>
  );
}
