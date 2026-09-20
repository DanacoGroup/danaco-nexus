// Panel administratora: redagowanie treści portalu i podgląd wiadomości z formularza kontaktowego.
// Dostęp daje sesja administratora aplikacji (te same ciasteczko i nagłówek co w pozostałym API).

import { useState } from "react";
import {
  dataPolska,
  komunikat,
  portalApi,
  type PelnaTresc,
  type RodzajTresci,
  type SkrotTresci,
  type StatusTresci,
} from "../api";
import { useZasob } from "../dane";
import { usePozycjonowanie } from "../seo";
import { sciezka } from "../trasy";
import { Karta, Komunikat, Ladowanie, NaglowekStrony, OdsylaczPrzycisk, Pole, Przycisk } from "../ui";

const RODZAJE: { wartosc: RodzajTresci; nazwa: string }[] = [
  { wartosc: "blog", nazwa: "Wpis bloga" },
  { wartosc: "wiedza", nazwa: "Artykuł bazy wiedzy" },
  { wartosc: "dokumentacja", nazwa: "Strona dokumentacji" },
  { wartosc: "strona", nazwa: "Strona statyczna" },
];

interface Formularz {
  id: string | null;
  kind: RodzajTresci;
  title: string;
  slug: string;
  excerpt: string;
  body: string;
  author: string;
  tags: string;
  position: string;
  meta_title: string;
  meta_description: string;
  status: StatusTresci;
}

const PUSTY: Formularz = {
  id: null,
  kind: "blog",
  title: "",
  slug: "",
  excerpt: "",
  body: "",
  author: "",
  tags: "",
  position: "0",
  meta_title: "",
  meta_description: "",
  status: "szkic",
};

function zFormularza(formularz: Formularz): Partial<PelnaTresc> {
  return {
    kind: formularz.kind,
    title: formularz.title.trim(),
    slug: formularz.slug.trim(),
    excerpt: formularz.excerpt.trim(),
    body: formularz.body,
    author: formularz.author.trim(),
    tags: formularz.tags
      .split(",")
      .map((znacznik) => znacznik.trim())
      .filter(Boolean),
    position: Number(formularz.position) || 0,
    seo: { meta_title: formularz.meta_title.trim(), meta_description: formularz.meta_description.trim() },
  };
}

function doFormularza(pozycja: PelnaTresc): Formularz {
  return {
    id: pozycja.id,
    kind: pozycja.kind,
    title: pozycja.title,
    slug: pozycja.slug,
    excerpt: pozycja.excerpt,
    body: pozycja.body,
    author: pozycja.author,
    tags: pozycja.tags.join(", "),
    position: String(pozycja.position),
    meta_title: pozycja.seo?.meta_title ?? "",
    meta_description: pozycja.seo?.meta_description ?? "",
    status: pozycja.status,
  };
}

function Wiadomosci() {
  const skrzynka = useZasob(() => portalApi.admin.wiadomosci(), "wiadomosci");
  if (skrzynka.ladowanie) return <Ladowanie wierszy={2} etykieta="Wczytywanie wiadomości" />;
  if (skrzynka.blad) return <Komunikat tekst={skrzynka.blad} rodzaj="blad" />;
  const pozycje = skrzynka.dane ?? [];
  if (pozycje.length === 0) return <p className="text-sm text-muted">Skrzynka jest pusta.</p>;
  return (
    <ul className="flex flex-col gap-4">
      {pozycje.map((wiadomosc) => (
        <li key={wiadomosc.id} className="rounded-xl border border-line bg-raised p-4">
          <p className="text-sm text-fg">
            {wiadomosc.name} — <span className="text-muted">{wiadomosc.email}</span>
          </p>
          <p className="mt-1 text-xs text-subtle">
            {wiadomosc.subject || "bez tematu"} · {dataPolska(wiadomosc.created_at)}
          </p>
          <p className="mt-2 text-sm text-muted">{wiadomosc.body}</p>
        </li>
      ))}
    </ul>
  );
}

export function PanelAdministratora({ administrator }: { administrator: boolean }) {
  const [formularz, setFormularz] = useState<Formularz>(PUSTY);
  const [filtr, setFiltr] = useState<RodzajTresci | "">("");
  const [wynik, setWynik] = useState("");
  const [blad, setBlad] = useState("");
  const [odswiezenie, setOdswiezenie] = useState(0);
  const lista = useZasob(
    () => portalApi.admin.lista({ typ: filtr || undefined, na_stronie: 50 }),
    `admin:${filtr}:${odswiezenie}:${administrator}`,
  );

  usePozycjonowanie({
    tytul: "Panel administratora",
    opis: "Redagowanie treści portalu Danaco Nexus.",
    sciezka: sciezka("admin"),
    noindex: true,
  });

  if (!administrator) {
    return (
      <>
        <NaglowekStrony tytul="Panel administratora" opis="Ta część portalu wymaga sesji administratora." />
        <div className="mt-6">
          <Komunikat tekst="Zaloguj się kontem administratora aplikacji, aby redagować treści." />
          <div className="mt-5">
            <OdsylaczPrzycisk adres={`/zaloguj?next=${encodeURIComponent(sciezka("admin"))}`}>
              Zaloguj się
            </OdsylaczPrzycisk>
          </div>
        </div>
      </>
    );
  }

  const pole = (nazwa: keyof Formularz) => (wartosc: string) =>
    setFormularz((biezacy) => ({ ...biezacy, [nazwa]: wartosc }));

  const odswiezListe = () => setOdswiezenie((wartosc) => wartosc + 1);

  const wykonaj = async (operacja: () => Promise<unknown>, komunikatSukcesu: string) => {
    setBlad("");
    setWynik("");
    try {
      await operacja();
      setWynik(komunikatSukcesu);
      odswiezListe();
    } catch (error) {
      setBlad(komunikat(error, "Operacja się nie powiodła."));
    }
  };

  const zapisz = () =>
    wykonaj(async () => {
      if (!formularz.title.trim()) throw new Error("Tytuł jest wymagany.");
      const dane = zFormularza(formularz);
      const zapisana = formularz.id
        ? await portalApi.admin.zmien(formularz.id, dane)
        : await portalApi.admin.utworz(dane);
      setFormularz(doFormularza(zapisana));
    }, "Treść zapisana.");

  const zmienPublikacje = (status: StatusTresci) =>
    wykonaj(async () => {
      if (!formularz.id) throw new Error("Najpierw zapisz treść.");
      setFormularz(doFormularza(await portalApi.admin.publikacja(formularz.id, status)));
    }, status === "opublikowany" ? "Treść opublikowana." : "Treść wycofana do szkiców.");

  const usun = () =>
    wykonaj(async () => {
      if (!formularz.id) throw new Error("Nie wybrano treści.");
      await portalApi.admin.usun(formularz.id);
      setFormularz(PUSTY);
    }, "Treść usunięta.");

  const wczytaj = (pozycja: SkrotTresci) =>
    wykonaj(async () => {
      setFormularz(doFormularza(await portalApi.admin.szczegoly(pozycja.id)));
    }, `Wczytano „${pozycja.title}”.`);

  return (
    <>
      <NaglowekStrony tytul="Panel administratora" opis="Treści portalu: szkice, publikacja i metadane." />
      <div className="mt-8 grid gap-8 lg:grid-cols-[20rem_1fr]">
        <section aria-labelledby="lista-tresci">
          <h2 id="lista-tresci" className="font-heading text-lg font-semibold text-fg">
            Treści
          </h2>
          <div className="mt-3 flex flex-col gap-1.5">
            <label htmlFor="filtr-rodzaju" className="text-sm font-medium text-fg">
              Rodzaj
            </label>
            <select
              id="filtr-rodzaju"
              value={filtr}
              onChange={(zdarzenie) => setFiltr(zdarzenie.target.value as RodzajTresci | "")}
              className="w-full rounded-lg border border-line-strong bg-app px-3 py-2.5 text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
            >
              <option value="">Wszystkie</option>
              {RODZAJE.map((rodzaj) => (
                <option key={rodzaj.wartosc} value={rodzaj.wartosc}>
                  {rodzaj.nazwa}
                </option>
              ))}
            </select>
          </div>
          <div className="mt-4">
            <Przycisk wariant="drugorzedny" className="w-full" onClick={() => setFormularz(PUSTY)}>
              Nowa treść
            </Przycisk>
          </div>
          <div className="mt-4 min-h-[16rem]">
            {lista.ladowanie && <Ladowanie wierszy={3} etykieta="Wczytywanie listy treści" />}
            {lista.blad && <Komunikat tekst={lista.blad} rodzaj="blad" />}
            {!lista.ladowanie && !lista.blad && (
              <ul className="flex flex-col gap-2">
                {(lista.dane?.items ?? []).map((pozycja) => (
                  <li key={pozycja.id}>
                    <button
                      type="button"
                      onClick={() => void wczytaj(pozycja)}
                      aria-current={formularz.id === pozycja.id ? "true" : undefined}
                      className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                        formularz.id === pozycja.id
                          ? "border-line-strong bg-accent-soft text-accent"
                          : "border-line bg-raised text-fg hover:bg-app"
                      }`}
                    >
                      <span className="block font-medium">{pozycja.title}</span>
                      <span className="text-xs text-subtle">
                        {pozycja.kind} · {pozycja.status}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section aria-labelledby="edytor">
          <h2 id="edytor" className="font-heading text-lg font-semibold text-fg">
            {formularz.id ? "Edycja treści" : "Nowa treść"}
          </h2>
          <form
            noValidate
            className="mt-5 flex flex-col gap-4"
            onSubmit={(zdarzenie) => {
              zdarzenie.preventDefault();
              void zapisz();
            }}
          >
            <div className="flex flex-col gap-1.5">
              <label htmlFor="rodzaj-tresci" className="text-sm font-medium text-fg">
                Rodzaj treści
              </label>
              <select
                id="rodzaj-tresci"
                value={formularz.kind}
                onChange={(zdarzenie) => pole("kind")(zdarzenie.target.value)}
                className="w-full rounded-lg border border-line-strong bg-app px-3 py-2.5 text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
              >
                {RODZAJE.map((rodzaj) => (
                  <option key={rodzaj.wartosc} value={rodzaj.wartosc}>
                    {rodzaj.nazwa}
                  </option>
                ))}
              </select>
            </div>
            <Pole etykieta="Tytuł" wartosc={formularz.title} naZmiane={pole("title")} wymagane />
            <Pole
              etykieta="Adres (slug)"
              wartosc={formularz.slug}
              naZmiane={pole("slug")}
              podpowiedz="Puste pole – adres powstanie z tytułu."
            />
            <Pole
              etykieta="Zajawka"
              wartosc={formularz.excerpt}
              naZmiane={pole("excerpt")}
              podpowiedz="Puste pole – zajawka powstanie z początku treści."
            />
            <Pole etykieta="Treść (Markdown)" wartosc={formularz.body} naZmiane={pole("body")} wieloliniowe />
            <Pole etykieta="Autor" wartosc={formularz.author} naZmiane={pole("author")} />
            <Pole
              etykieta="Znaczniki"
              wartosc={formularz.tags}
              naZmiane={pole("tags")}
              podpowiedz="Oddzielone przecinkiem."
            />
            <Pole
              etykieta="Kolejność w dokumentacji"
              typ="number"
              wartosc={formularz.position}
              naZmiane={pole("position")}
            />
            <Pole etykieta="Tytuł SEO" wartosc={formularz.meta_title} naZmiane={pole("meta_title")} />
            <Pole
              etykieta="Opis SEO"
              wartosc={formularz.meta_description}
              naZmiane={pole("meta_description")}
              podpowiedz="Do 320 znaków; widoczny w wynikach wyszukiwania."
            />
            {blad && <Komunikat tekst={blad} rodzaj="blad" />}
            {wynik && <Komunikat tekst={wynik} rodzaj="sukces" />}
            <div className="flex flex-wrap gap-3">
              <Przycisk type="submit">Zapisz</Przycisk>
              {formularz.id && formularz.status !== "opublikowany" && (
                <Przycisk wariant="drugorzedny" onClick={() => void zmienPublikacje("opublikowany")}>
                  Opublikuj
                </Przycisk>
              )}
              {formularz.id && formularz.status === "opublikowany" && (
                <Przycisk wariant="drugorzedny" onClick={() => void zmienPublikacje("szkic")}>
                  Wycofaj do szkiców
                </Przycisk>
              )}
              {formularz.id && (
                <Przycisk wariant="cichy" onClick={() => void usun()}>
                  Usuń
                </Przycisk>
              )}
            </div>
          </form>
        </section>
      </div>

      <section aria-labelledby="skrzynka" className="mt-14">
        <h2 id="skrzynka" className="font-heading text-xl font-semibold text-fg">
          Wiadomości z formularza kontaktowego
        </h2>
        <div className="mt-5">
          <Karta>
            <Wiadomosci />
          </Karta>
        </div>
      </section>
    </>
  );
}
