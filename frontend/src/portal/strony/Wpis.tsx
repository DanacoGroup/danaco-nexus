// Pojedyncza pozycja treści: wpis bloga, artykuł centrum wiedzy, strona dokumentacji lub statyczna.

import { Markdown } from "../../components/Markdown";
import { dataPolska, portalApi, type RodzajTresci } from "../api";
import { useZasob } from "../dane";
import { artykul, okruszki, usePozycjonowanie } from "../seo";
import { sciezka, type PortalStrona } from "../trasy";
import { Komunikat, Ladowanie, Odsylacz, Okruszki, Znacznik } from "../ui";
import { KartaWpisu } from "./ListaWpisow";

const TYPY_SCHEMA: Record<RodzajTresci, "BlogPosting" | "TechArticle" | "Article"> = {
  blog: "BlogPosting",
  wiedza: "Article",
  dokumentacja: "TechArticle",
  strona: "Article",
};

/** Czy treść zaczyna się dokładnie tym, co stoi w zajawce (z dokładnością do spacji).
 *
 * Porównujemy po spłaszczeniu białych znaków, bo plik źródłowy zawija wiersze, a zajawka
 * jest jedną linią — bez tego „ten sam akapit” nigdy nie byłby równy sam sobie.
 */
function zaczynaSieOd(tresc: string, zajawka: string): boolean {
  const plasko = (tekst: string) => tekst.replace(/\s+/g, " ").trim();
  const wstep = plasko(tresc).replace(/^[#>*_`~-]+\s*/, "");
  const poczatek = plasko(zajawka).replace(/…$/, "");
  return poczatek.length > 40 && wstep.startsWith(poczatek);
}

export function Wpis({
  strona,
  rodzaj,
  slug,
  nazwaSekcji,
}: {
  strona: PortalStrona;
  rodzaj: RodzajTresci;
  slug: string;
  nazwaSekcji: string;
}) {
  const adres = sciezka(strona, slug);
  // Strony statyczne nie mają własnej listy – powrót prowadzi na stronę główną portalu.
  const adresSekcji = strona === "strona" ? sciezka("glowna") : sciezka(strona);
  const zasob = useZasob(() => portalApi.szczegoly(rodzaj, slug), `${rodzaj}:${slug}`);
  const pozycja = zasob.dane;

  usePozycjonowanie({
    tytul: pozycja?.seo?.meta_title || pozycja?.title || nazwaSekcji,
    opis: pozycja?.seo?.meta_description || pozycja?.excerpt || "",
    sciezka: pozycja?.seo?.canonical || adres,
    obraz: pozycja?.seo?.og_image,
    rodzaj: "article",
    noindex: Boolean(pozycja?.seo?.noindex) || !pozycja,
    dane: pozycja
      ? [
          artykul({
            tytul: pozycja.title,
            opis: pozycja.excerpt,
            sciezka: adres,
            autor: pozycja.author,
            opublikowano: pozycja.published_at,
            zmieniono: pozycja.updated_at,
            typ: TYPY_SCHEMA[rodzaj],
          }),
          okruszki([
            { nazwa: "Portal", sciezka: sciezka("glowna") },
            { nazwa: nazwaSekcji, sciezka: adresSekcji },
            { nazwa: pozycja.title, sciezka: adres },
          ]),
        ]
      : undefined,
  });

  if (zasob.ladowanie) {
    return (
      <div className="min-h-[32rem] pt-8">
        <Ladowanie wierszy={4} etykieta="Wczytywanie treści" />
      </div>
    );
  }
  if (zasob.blad || !pozycja) {
    return (
      <div className="min-h-[32rem] pt-8">
        <h1 tabIndex={-1} id="portal-tytul" className="font-heading text-3xl font-semibold text-fg">
          Nie znaleziono treści
        </h1>
        <p className="mt-4 text-muted">{zasob.blad || "Tej pozycji nie ma pod tym adresem — mogła zmienić nazwę albo zostać wycofana."}</p>
        <p className="mt-6">
          <Odsylacz adres={adresSekcji} className="text-accent hover:underline">
            Wróć do sekcji {nazwaSekcji}
          </Odsylacz>
        </p>
      </div>
    );
  }

  return (
    <article className="pt-8">
      <Okruszki
        pozycje={[
          { nazwa: "Portal", sciezka: sciezka("glowna") },
          { nazwa: nazwaSekcji, sciezka: adresSekcji },
          { nazwa: pozycja.title, sciezka: adres },
        ]}
      />
      <header className="mt-4">
        <h1 tabIndex={-1} id="portal-tytul" className="font-heading text-3xl font-semibold text-fg sm:text-4xl">
          {pozycja.title}
        </h1>
        <p className="mt-3 flex flex-wrap items-center gap-2 text-sm text-subtle">
          {pozycja.published_at && (
            <time dateTime={pozycja.published_at}>Opublikowano {dataPolska(pozycja.published_at)}</time>
          )}
          {pozycja.author && <span>· {pozycja.author}</span>}
        </p>
        {/* Zajawka jako wstęp nad treścią — ale **tylko wtedy, gdy nie jest** pierwszym
          akapitem artykułu. Zajawka powstaje domyślnie ze wstępu materiału, więc inaczej
          czytelnik dostawał ten sam akapit dwa razy pod rząd: raz większą czcionką,
          raz mniejszą. Zajawka wpisana ręcznie przez redaktora zwykle się różni i wtedy
          zostaje na swoim miejscu. */}
        {pozycja.excerpt && !zaczynaSieOd(pozycja.body, pozycja.excerpt) && (
          <p className="mt-4 max-w-2xl text-lg text-muted">{pozycja.excerpt}</p>
        )}
        {pozycja.tags.length > 0 && (
          <ul className="mt-4 flex flex-wrap gap-2">
            {pozycja.tags.map((znacznik) => (
              <li key={znacznik}>
                <Znacznik tekst={znacznik} />
              </li>
            ))}
          </ul>
        )}
      </header>
      <div className="mt-8 max-w-prose">
        {pozycja.body ? <Markdown text={pozycja.body} proza /> : <Komunikat tekst="Treść tej pozycji jest w opracowaniu. Wróć do listy — reszta materiałów czeka gotowa." />}
      </div>
      {(pozycja.related?.length ?? 0) > 0 && (
        <section aria-labelledby="powiazane" className="mt-12">
          <h2 id="powiazane" className="font-heading text-xl font-semibold text-fg">
            Zobacz też
          </h2>
          <ul className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {(pozycja.related ?? []).map((inna) => (
              <KartaWpisu key={inna.id} pozycja={inna} adres={sciezka(strona, inna.slug)} />
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
