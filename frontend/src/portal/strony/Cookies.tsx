// Informacja o plikach cookie: treść z tresc-prawna.ts, jeden nagłówek pierwszego stopnia, spis rozdziałów.

import { Markdown } from "../../components/Markdown";
import { okruszki, usePozycjonowanie } from "../seo";
import { COOKIES as DOKUMENT } from "../tresc-prawna";
import { sciezka } from "../trasy";
import { NaglowekStrony, Odsylacz, Okruszki } from "../ui";

export function Cookies() {
  usePozycjonowanie({
    tytul: DOKUMENT.tytul,
    opis: DOKUMENT.opis,
    sciezka: "/portal/cookies",
    dane: okruszki([
      { nazwa: "Portal", sciezka: sciezka("glowna") },
      { nazwa: DOKUMENT.tytul, sciezka: "/portal/cookies" },
    ]),
  });

  return (
    <div className="pt-8">
      <Okruszki
        pozycje={[
          { nazwa: "Portal", sciezka: sciezka("glowna") },
          { nazwa: DOKUMENT.tytul, sciezka: "/portal/cookies" },
        ]}
      />
      <NaglowekStrony tytul={DOKUMENT.tytul} opis={DOKUMENT.opis}>
        <p className="text-sm text-subtle">
          Wersja {DOKUMENT.wersja} · obowiązuje od {DOKUMENT.obowiazujeOd}
        </p>
      </NaglowekStrony>

      <nav aria-label="Spis rozdziałów" className="mt-8 rounded-xl border border-line bg-raised p-5">
        <h2 className="text-sm font-semibold tracking-wide text-subtle uppercase">Spis rozdziałów</h2>
        <ol className="mt-3 grid gap-1.5 sm:grid-cols-2">
          {DOKUMENT.sekcje.map((sekcja) => (
            <li key={sekcja.id}>
              <a href={`#${sekcja.id}`} className="text-sm text-muted hover:text-fg">
                {sekcja.tytul}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="mt-10 max-w-prose">
        {DOKUMENT.sekcje.map((sekcja) => (
          <section key={sekcja.id} aria-labelledby={sekcja.id} className="mt-10 first:mt-0 scroll-mt-24">
            <h2 id={sekcja.id} className="font-heading text-xl font-semibold text-fg sm:text-2xl">
              {sekcja.tytul}
            </h2>
            <div className="mt-4">
              <Markdown text={sekcja.tresc} />
            </div>
          </section>
        ))}
      </div>

      <nav aria-label="Powiązane dokumenty" className="mt-12 border-t border-line pt-6">
        <h2 className="text-sm font-semibold text-fg">Powiązane dokumenty</h2>
        <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
          <li>
            <Odsylacz adres="/portal/prywatnosc" className="text-sm text-accent hover:text-fg">
              Polityka prywatności
            </Odsylacz>
          </li>
          <li>
            <Odsylacz adres="/portal/regulamin" className="text-sm text-accent hover:text-fg">
              Regulamin
            </Odsylacz>
          </li>
          <li>
            <Odsylacz adres={sciezka("kontakt")} className="text-sm text-accent hover:text-fg">
              Kontakt
            </Odsylacz>
          </li>
        </ul>
      </nav>
    </div>
  );
}
