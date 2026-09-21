// Dokumentacja: spis stron po lewej, treść wybranej strony po prawej.

import { Markdown } from "../../components/Markdown";
import { portalApi, type SkrotTresci } from "../api";
import { useZasob } from "../dane";
import { artykul, okruszki, usePozycjonowanie } from "../seo";
import { SCIEZKA } from "../../shell/route";
import { sciezka } from "../trasy";
import { Komunikat, Ladowanie, NaglowekStrony, Odsylacz, Okruszki } from "../ui";

const OPIS = "Jak uruchomić Nexusa, podłączyć pocztę, kalendarz i chmurę oraz pracować z każdym modułem.";

function SpisTresci({ aktywny, pozycje, ladowanie }: { aktywny: string | null; pozycje: SkrotTresci[]; ladowanie: boolean }) {
  if (ladowanie) return <Ladowanie wierszy={4} etykieta="Wczytywanie spisu dokumentacji" />;
  if (pozycje.length === 0) return <p className="text-sm text-muted">Spis jest jeszcze pusty. Napisz do nas — podeślemy opis potrzebnego zagadnienia.</p>;
  return (
    <nav aria-label="Spis dokumentacji">
      <ul className="flex flex-col gap-1">
        {pozycje.map((pozycja) => {
          const wybrana = pozycja.slug === aktywny;
          return (
            <li key={pozycja.id}>
              <Odsylacz
                adres={sciezka("dokumentacja", pozycja.slug)}
                aria-current={wybrana ? "page" : undefined}
                className={`block rounded-md px-3 py-2 text-sm transition-colors ${
                  wybrana ? "bg-accent-soft text-accent" : "text-muted hover:bg-raised hover:text-fg"
                }`}
              >
                {pozycja.title}
              </Odsylacz>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function TrescStrony({ slug }: { slug: string }) {
  const zasob = useZasob(() => portalApi.szczegoly("dokumentacja", slug), `dokumentacja:${slug}`);
  const pozycja = zasob.dane;
  usePozycjonowanie({
    tytul: pozycja?.seo?.meta_title || pozycja?.title || "Dokumentacja",
    opis: pozycja?.seo?.meta_description || pozycja?.excerpt || OPIS,
    sciezka: pozycja?.seo?.canonical || sciezka("dokumentacja", slug),
    noindex: Boolean(pozycja?.seo?.noindex) || !pozycja,
    dane: pozycja
      ? [
          artykul({
            tytul: pozycja.title,
            opis: pozycja.excerpt,
            sciezka: sciezka("dokumentacja", slug),
            autor: pozycja.author,
            opublikowano: pozycja.published_at,
            zmieniono: pozycja.updated_at,
            typ: "TechArticle",
          }),
          okruszki([
            { nazwa: "Portal", sciezka: sciezka("glowna") },
            { nazwa: "Dokumentacja", sciezka: sciezka("dokumentacja") },
            { nazwa: pozycja.title, sciezka: sciezka("dokumentacja", slug) },
          ]),
        ]
      : undefined,
  });

  if (zasob.ladowanie) return <Ladowanie wierszy={4} etykieta="Wczytywanie strony dokumentacji" />;
  if (zasob.blad || !pozycja) {
    return (
      <>
        <h1 tabIndex={-1} id="portal-tytul" className="font-heading text-3xl font-semibold text-fg">
          Nie znaleziono strony
        </h1>
        <p className="mt-4 text-muted">{zasob.blad || "Tej strony dokumentacji nie ma pod tym adresem. Wybierz zagadnienie ze spisu treści."}</p>
      </>
    );
  }
  return (
    <article>
      <h1 tabIndex={-1} id="portal-tytul" className="font-heading text-3xl font-semibold text-fg">
        {pozycja.title}
      </h1>
      {pozycja.excerpt && <p className="mt-3 text-muted">{pozycja.excerpt}</p>}
      <div className="mt-6 max-w-prose">
        {pozycja.body ? <Markdown text={pozycja.body} proza /> : <Komunikat tekst="Ta strona jest w opracowaniu. Do czasu jej publikacji odpowiemy na pytanie pocztą: support@danaco-group.pl." />}
      </div>
    </article>
  );
}

function Wprowadzenie({ pusty }: { pusty: boolean }) {
  usePozycjonowanie({
    tytul: "Dokumentacja",
    opis: OPIS,
    sciezka: sciezka("dokumentacja"),
    dane: okruszki([
      { nazwa: "Portal", sciezka: sciezka("glowna") },
      { nazwa: "Dokumentacja", sciezka: sciezka("dokumentacja") },
    ]),
  });
  return (
    <>
      <NaglowekStrony tytul="Uruchom Nexusa i podłącz swoje konta" opis={OPIS} />
      {/* Spis bywa pusty (dokumentacja jest redagowana w panelu), a wtedy „wybierz zagadnienie
          ze spisu treści” każe zrobić coś niewykonalnego. W takim stanie strona mówi, co jest,
          i podaje dwa wyjścia, które działają już teraz. */}
      {pusty ? (
        <p className="mt-4 max-w-prose text-muted">
          Spis dokumentacji jeszcze powstaje. Zanim się zapełni:{" "}
          <Odsylacz adres={SCIEZKA.piaskownica} className="text-accent hover:underline">
            wypróbuj Nexusa bez rejestracji
          </Odsylacz>{" "}
          albo{" "}
          <Odsylacz adres={sciezka("kontakt")} className="text-accent hover:underline">
            napisz, czego potrzebujesz
          </Odsylacz>{" "}
          — podeślemy opis zagadnienia.
        </p>
      ) : (
        // Strona dokumentacji bez wybranego zagadnienia była jednym zdaniem obok spisu —
        // najuboższą stroną w całym serwisie (299 znaków przy 2300 na blogu). Wejście do
        // dokumentacji ma powiedzieć, co tu jest i od czego zacząć, zamiast odsyłać dalej.
        // „ze spisu treści”, a nie „obok”: spis stoi obok tekstu dopiero na szerokim
        // ekranie. Na telefonie jest **nad** tekstem, więc „obok” kazało szukać czegoś,
        // czego tam nie ma.
        <div className="mt-4 max-w-prose space-y-4 text-muted">
          <p>
            Dokumentacja opisuje ekrany i moduły Nexusa: gdzie co jest, co robi i czego się
            po nim spodziewać. Wybierz zagadnienie ze spisu treści albo zacznij od początku.
          </p>
          <p>
            <Odsylacz
              adres={sciezka("dokumentacja", "pierwsze-uruchomienie")}
              className="font-medium text-accent hover:underline"
            >
              Pierwsze uruchomienie
            </Odsylacz>{" "}
            — pierwsze zadanie, instalacja we własnym oknie i to, co warto zrobić na start.
          </p>
          <p>
            Szukasz raczej poradnika niż opisu ekranu? Odpowiedzi na częste pytania i gotowe
            sposoby na powtarzalne zadania zebraliśmy w{" "}
            <Odsylacz adres={sciezka("wiedza")} className="text-accent hover:underline">
              centrum wiedzy
            </Odsylacz>
            , a o pracy z Nexusem piszemy na{" "}
            <Odsylacz adres={sciezka("blog")} className="text-accent hover:underline">
              blogu
            </Odsylacz>
            .
          </p>
        </div>
      )}
    </>
  );
}

export function Dokumentacja({ slug }: { slug: string | null }) {
  const spis = useZasob(() => portalApi.lista({ typ: "dokumentacja", na_stronie: 50 }), "spis-dokumentacji");
  const pozycje = spis.dane?.items ?? [];
  return (
    <div className="pt-8">
      <Okruszki
        pozycje={[
          { nazwa: "Portal", sciezka: sciezka("glowna") },
          { nazwa: "Dokumentacja", sciezka: sciezka("dokumentacja") },
        ]}
      />
      <div className="mt-6 grid gap-10 lg:grid-cols-[16rem_1fr]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <h2 className="mb-3 text-sm font-semibold tracking-wide text-subtle uppercase">Spis treści</h2>
          <SpisTresci aktywny={slug} pozycje={pozycje} ladowanie={spis.ladowanie} />
        </aside>
        <div className="min-h-[24rem]">{slug ? <TrescStrony slug={slug} /> : <Wprowadzenie pusty={!spis.ladowanie && pozycje.length === 0} />}</div>
      </div>
    </div>
  );
}
