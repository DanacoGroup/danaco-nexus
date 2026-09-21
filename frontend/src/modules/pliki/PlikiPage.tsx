// Przestrzeń plików konta: katalogi i projekty użytkownika, wyszukiwarka, filtry rodzaju.
//
// Jedno miejsce zamiast osobnych ekranów „chmura” i „baza wiedzy”. Pliki wgrane przez
// użytkownika i wytworzone przez agenta leżą obok siebie; układ wyznacza sam użytkownik.
// Katalog jest etykietą, a nie pudełkiem — jego usunięcie nie zabiera treści.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PlusIcon } from "../../components/icons";
import { describe } from "../_biuro/http";
import { buttonClass, EmptyState, ErrorBanner, inputClass, Loading, useConfirm, useToast } from "../_biuro/ui";
import { FolderIcon, SearchIcon } from "../_biuro/icons";
import { formatSize } from "../../runState";
import { Stagger } from "../../ui";
import { plikiApi, RODZAJE, type Katalog, type PlikPrzestrzeni, type Przestrzen, type RodzajTresci } from "./api";

const WSZYSTKIE = "__wszystkie__";
const NIEUPORZADKOWANE = "__bez_katalogu__";

function data(iso: string): string {
  const kiedy = new Date(iso);
  return Number.isNaN(kiedy.getTime()) ? "" : kiedy.toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
}

function PasekPrzestrzeni({ przestrzen }: { przestrzen: Przestrzen }) {
  const procent = przestrzen.limit > 0 ? Math.min(100, Math.round((przestrzen.zajete / przestrzen.limit) * 100)) : 0;
  return (
    <div className="px-3 pb-3">
      <div className="flex justify-between text-xs text-subtle">
        <span>{formatSize(przestrzen.zajete)}</span>
        <span>z {przestrzen.opis_limitu}</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-hover">
        <div
          className={`h-full rounded-full ${procent >= 90 ? "bg-danger" : procent >= 70 ? "bg-warning" : "bg-accent-fill"}`}
          style={{ width: `${procent}%` }}
        />
      </div>
      <p className="mt-1.5 text-xs text-subtle">Plan {przestrzen.plan}</p>
    </div>
  );
}

export function PlikiPage() {
  const [katalogi, setKatalogi] = useState<Katalog[] | null>(null);
  const [wybrany, setWybrany] = useState<string>(WSZYSTKIE);
  const [rodzaj, setRodzaj] = useState<RodzajTresci>("");
  const [szukane, setSzukane] = useState("");
  const [pliki, setPliki] = useState<PlikPrzestrzeni[] | null>(null);
  const [przestrzen, setPrzestrzen] = useState<Przestrzen | null>(null);
  const [zaznaczone, setZaznaczone] = useState<Set<string>>(new Set());
  const [blad, setBlad] = useState("");
  const [potwierdz, oknoPotwierdzenia] = useConfirm();
  const [powiadom, powiadomienie] = useToast();
  const wysylka = useRef<HTMLInputElement>(null);

  const wczytajKatalogi = useCallback(() => {
    plikiApi.katalogi().then(setKatalogi).catch((awaria) => setBlad(describe(awaria)));
  }, []);

  const wczytajPliki = useCallback(() => {
    plikiApi
      .zawartosc({
        katalog_id: wybrany === WSZYSTKIE || wybrany === NIEUPORZADKOWANE ? undefined : wybrany,
        bez_katalogu: wybrany === NIEUPORZADKOWANE,
        rodzaj,
        q: szukane.trim(),
      })
      .then((wynik) => {
        setPliki(wynik.pliki);
        setPrzestrzen(wynik.przestrzen);
      })
      .catch((awaria) => setBlad(describe(awaria)));
  }, [wybrany, rodzaj, szukane]);

  useEffect(wczytajKatalogi, [wczytajKatalogi]);
  // Wyszukiwanie czeka na przerwę w pisaniu — inaczej każde naciśnięcie klawisza pyta serwer.
  useEffect(() => {
    const opoznienie = window.setTimeout(wczytajPliki, szukane ? 250 : 0);
    return () => window.clearTimeout(opoznienie);
  }, [wczytajPliki, szukane]);

  const nowyKatalog = async (rodzajKatalogu: "katalog" | "projekt") => {
    const nazwa = window.prompt(rodzajKatalogu === "projekt" ? "Nazwa projektu" : "Nazwa katalogu");
    if (!nazwa?.trim()) return;
    try {
      const utworzony = await plikiApi.utworzKatalog({ nazwa: nazwa.trim(), rodzaj: rodzajKatalogu });
      wczytajKatalogi();
      setWybrany(utworzony.id);
    } catch (awaria) {
      setBlad(describe(awaria));
    }
  };

  const zmienNazwe = async (katalog: Katalog) => {
    const nazwa = window.prompt("Nowa nazwa", katalog.nazwa);
    if (!nazwa?.trim() || nazwa.trim() === katalog.nazwa) return;
    try {
      await plikiApi.zmienKatalog(katalog.id, { nazwa: nazwa.trim() });
      wczytajKatalogi();
    } catch (awaria) {
      setBlad(describe(awaria));
    }
  };

  const usunKatalog = async (katalog: Katalog) => {
    const zgoda = await potwierdz({
      title: `Usunąć „${katalog.nazwa}”?`,
      message: "Pliki zostaną — wrócą do widoku „Wszystkie”. Katalog jest tylko etykietą.",
      confirmLabel: "Usuń katalog",
    });
    if (!zgoda) return;
    try {
      await plikiApi.usunKatalog(katalog.id);
      if (wybrany === katalog.id) setWybrany(WSZYSTKIE);
      wczytajKatalogi();
      wczytajPliki();
      powiadom("Katalog usunięty, pliki zostały.");
    } catch (awaria) {
      setBlad(describe(awaria));
    }
  };

  const przenies = async (katalogId: string | null) => {
    if (!zaznaczone.size) return;
    try {
      await plikiApi.przypisz([...zaznaczone], katalogId);
      setZaznaczone(new Set());
      wczytajKatalogi();
      wczytajPliki();
    } catch (awaria) {
      setBlad(describe(awaria));
    }
  };

  const usunZaznaczone = async () => {
    const zgoda = await potwierdz({
      title: `Usunąć ${zaznaczone.size} ${zaznaczone.size === 1 ? "plik" : "pliki"}?`,
      message: "Plików nie da się odzyskać.",
      confirmLabel: "Usuń",
      danger: true,
    });
    if (!zgoda) return;
    try {
      for (const id of zaznaczone) await plikiApi.usun(id);
      setZaznaczone(new Set());
      wczytajKatalogi();
      wczytajPliki();
    } catch (awaria) {
      setBlad(describe(awaria));
    }
  };

  const dodajPliki = async (lista: FileList | null) => {
    if (!lista?.length) return;
    try {
      for (const plik of Array.from(lista)) {
        const dane = new FormData();
        dane.append("file", plik);
        const odpowiedz = await fetch("/api/files", {
          method: "POST",
          body: dane,
          headers: { "X-Nexus-Request": "1" },
        });
        if (!odpowiedz.ok) throw new Error((await odpowiedz.json()).detail ?? "Nie udało się wysłać pliku.");
        if (wybrany !== WSZYSTKIE && wybrany !== NIEUPORZADKOWANE) {
          const wyslany = await odpowiedz.json();
          await plikiApi.przypisz([wyslany.id], wybrany);
        }
      }
      wczytajKatalogi();
      wczytajPliki();
    } catch (awaria) {
      setBlad(describe(awaria));
    }
  };

  const nazwaWidoku = useMemo(() => {
    if (wybrany === WSZYSTKIE) return "Wszystkie pliki";
    if (wybrany === NIEUPORZADKOWANE) return "Nieuporządkowane";
    return katalogi?.find((pozycja) => pozycja.id === wybrany)?.nazwa ?? "Katalog";
  }, [wybrany, katalogi]);

  if (!katalogi) return <Loading />;

  return (
    <div className="flex h-full min-h-0 bg-app">
      {/* Tytuł strony na telefonie: widoczny `h1` modułu siedzi w panelu katalogów,
          który poniżej `md` jest schowany. */}
      <h1 className="sr-only md:hidden">Pliki</h1>
      <nav className="hidden w-60 shrink-0 flex-col border-r border-line bg-side md:flex" aria-label="Katalogi">
        <div className="px-3 pt-4 pb-2">
          <h1 className="px-2 text-lg font-semibold">Pliki</h1>
          <div className="mt-3 flex gap-2">
            <button type="button" className={`${buttonClass.primary} flex-1`} onClick={() => void nowyKatalog("katalog")}>
              <PlusIcon size={16} /> Katalog
            </button>
            <button type="button" className={buttonClass.secondary} onClick={() => void nowyKatalog("projekt")}>
              Projekt
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
          {[
            { id: WSZYSTKIE, nazwa: "Wszystkie pliki" },
            { id: NIEUPORZADKOWANE, nazwa: "Nieuporządkowane" },
          ].map((pozycja) => (
            <button
              key={pozycja.id}
              type="button"
              onClick={() => setWybrany(pozycja.id)}
              className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm ${
                wybrany === pozycja.id ? "bg-hover font-medium" : "hover:bg-hover"
              }`}
            >
              <FolderIcon size={18} className="text-muted" />
              <span className="flex-1 truncate">{pozycja.nazwa}</span>
            </button>
          ))}
          {katalogi.length > 0 && <p className="px-3 pt-4 pb-1 text-xs text-subtle uppercase">Twoje katalogi</p>}
          {katalogi.map((katalog) => (
            <div key={katalog.id} className="group flex items-center">
              <button
                type="button"
                onClick={() => setWybrany(katalog.id)}
                className={`flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm ${
                  wybrany === katalog.id ? "bg-hover font-medium" : "hover:bg-hover"
                }`}
              >
                <FolderIcon size={18} className={katalog.rodzaj === "projekt" ? "text-accent" : "text-muted"} />
                <span className="min-w-0 flex-1 truncate">{katalog.nazwa}</span>
                <span className="shrink-0 text-xs text-subtle tabular-nums">{katalog.plikow}</span>
              </button>
              <button
                type="button"
                title={`Zmień nazwę katalogu „${katalog.nazwa}”`}
                onClick={() => void zmienNazwe(katalog)}
                // `opacity-0` nie wyjmuje przycisku z kolejności tabulacji: klawiatura
                // zatrzymywała się na czymś, czego nie widać. Ustawienie ostrości
                // odsłania go tak samo jak najechanie myszą.
                className={`${buttonClass.ghost} opacity-0 group-hover:opacity-100 focus-visible:opacity-100`}
              >
                Zmień
              </button>
              <button
                type="button"
                title={`Usuń katalog „${katalog.nazwa}”`}
                onClick={() => void usunKatalog(katalog)}
                // `opacity-0` nie wyjmuje przycisku z kolejności tabulacji: klawiatura
                // zatrzymywała się na czymś, czego nie widać. Ustawienie ostrości
                // odsłania go tak samo jak najechanie myszą.
                className={`${buttonClass.ghost} opacity-0 group-hover:opacity-100 focus-visible:opacity-100`}
              >
                Usuń
              </button>
            </div>
          ))}
        </div>
        {przestrzen && <PasekPrzestrzeni przestrzen={przestrzen} />}
      </nav>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-line px-5 py-4">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-heading text-lg font-semibold">{nazwaWidoku}</h2>
            <span className="text-sm text-muted">{pliki?.length ?? 0}</span>
            <div className="ml-auto flex gap-2">
              <input
                ref={wysylka}
                type="file"
                multiple
                className="hidden"
                aria-label="Dodaj pliki"
                onChange={(zdarzenie) => void dodajPliki(zdarzenie.target.value ? zdarzenie.target.files : null)}
              />
              <button type="button" className={buttonClass.primary} onClick={() => wysylka.current?.click()}>
                <PlusIcon size={16} /> Dodaj pliki
              </button>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <label className="relative min-w-52 flex-1">
              <span className="sr-only">Szukaj w plikach</span>
              <SearchIcon size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
              <input
                className={`${inputClass} pl-9`}
                placeholder="Szukaj po nazwie…"
                value={szukane}
                onChange={(zdarzenie) => setSzukane(zdarzenie.target.value)}
              />
            </label>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Rodzaj plików">
              {RODZAJE.map((pozycja) => (
                <button
                  key={pozycja.id || "wszystko"}
                  type="button"
                  aria-pressed={rodzaj === pozycja.id}
                  onClick={() => setRodzaj(pozycja.id)}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    rodzaj === pozycja.id ? "bg-accent-fill text-on-accent" : "border border-line text-muted hover:bg-hover"
                  }`}
                >
                  {pozycja.etykieta}
                </button>
              ))}
            </div>
          </div>
          {zaznaczone.size > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-raised px-3 py-2">
              <span className="text-sm">Zaznaczono {zaznaczone.size}</span>
              <select
                className={`${inputClass} w-auto`}
                aria-label="Przenieś do katalogu"
                value=""
                onChange={(zdarzenie) => void przenies(zdarzenie.target.value || null)}
              >
                <option value="">Przenieś do…</option>
                <option value="">Wyjmij z katalogu</option>
                {katalogi.map((katalog) => (
                  <option key={katalog.id} value={katalog.id}>
                    {katalog.nazwa}
                  </option>
                ))}
              </select>
              <button type="button" className={buttonClass.danger} onClick={() => void usunZaznaczone()}>
                Usuń
              </button>
              <button type="button" className={buttonClass.ghost} onClick={() => setZaznaczone(new Set())}>
                Odznacz
              </button>
            </div>
          )}
        </header>

        {blad && (
          <div className="px-5 pt-4">
            <ErrorBanner message={blad} onClose={() => setBlad("")} />
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {pliki === null ? (
            <Loading />
          ) : pliki.length === 0 ? (
            <EmptyState icon={<FolderIcon size={26} />} title="Tu jeszcze nic nie ma">
              <p>
                {szukane
                  ? `Nic nie pasuje do „${szukane}”.`
                  : "Dodaj pliki albo poproś Nexusa o wykonanie zadania — wyniki trafią tutaj."}
              </p>
            </EmptyState>
          ) : (
            /* Lista dociera po odpowiedzi serwera, więc kaskada nie zderza się z przejściem
               widoku — ono skończyło się wcześniej (motion, rozdz. 5 i 13). */
            <Stagger as="ul" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {pliki.map((plik) => (
                <li
                  key={plik.id}
                  className={`rounded-xl border p-4 transition-colors ${
                    zaznaczone.has(plik.id) ? "border-accent bg-accent-soft" : "border-line bg-raised hover:border-line-strong"
                  }`}
                >
                  <label className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={zaznaczone.has(plik.id)}
                      aria-label={`Zaznacz ${plik.tytul || plik.name}`}
                      onChange={(zdarzenie) =>
                        setZaznaczone((poprzednie) => {
                          const nowe = new Set(poprzednie);
                          if (zdarzenie.target.checked) nowe.add(plik.id);
                          else nowe.delete(plik.id);
                          return nowe;
                        })
                      }
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium" title={plik.name}>
                        {plik.tytul || plik.name}
                      </span>
                      {plik.tytul && <span className="block truncate text-xs text-subtle">{plik.name}</span>}
                      <span className="mt-1 block text-xs text-muted">
                        {formatSize(plik.size)} · {data(plik.created_at)}
                      </span>
                    </span>
                  </label>
                  <div className="mt-3 flex gap-2">
                    <a className={buttonClass.ghost} href={`/api/files/${plik.id}/download`} download>
                      Pobierz
                    </a>
                    <button
                      type="button"
                      className={buttonClass.ghost}
                      onClick={async () => {
                        const tytul = window.prompt("Własna nazwa pliku", plik.tytul || plik.name);
                        if (tytul === null) return;
                        try {
                          await plikiApi.zmienTytul(plik.id, tytul);
                          wczytajPliki();
                        } catch (awaria) {
                          setBlad(describe(awaria));
                        }
                      }}
                    >
                      Nazwij
                    </button>
                  </div>
                </li>
              ))}
            </Stagger>
          )}
        </div>
      </main>
      {oknoPotwierdzenia}
      {powiadomienie}
    </div>
  );
}
