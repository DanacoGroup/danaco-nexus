// Wyszukiwanie w treściach portalu (blog, centrum wiedzy, dokumentacja, strony).

import { useState } from "react";
import { portalApi, type RodzajTresci } from "../api";
import { useZasob } from "../dane";
import { usePozycjonowanie } from "../seo";
import { sciezka, type PortalStrona } from "../trasy";
import { Komunikat, Ladowanie, NaglowekStrony, Odsylacz, Pole, Przycisk, useNawigacja } from "../ui";

const SEKCJE: Record<RodzajTresci, { nazwa: string; strona: PortalStrona }> = {
  blog: { nazwa: "Blog", strona: "blog" },
  wiedza: { nazwa: "Centrum wiedzy", strona: "wiedza" },
  dokumentacja: { nazwa: "Dokumentacja", strona: "dokumentacja" },
  strona: { nazwa: "Strona", strona: "strona" },
};

export function Szukaj({ zapytanie }: { zapytanie: string }) {
  const nawiguj = useNawigacja();
  const [tekst, setTekst] = useState(zapytanie);
  const wyniki = useZasob(
    () => (zapytanie ? portalApi.szukaj(zapytanie) : Promise.resolve({ query: "", items: [], total: 0 })),
    `szukaj:${zapytanie}`,
  );

  usePozycjonowanie({
    tytul: zapytanie ? `Wyniki: ${zapytanie}` : "Wyszukiwanie",
    opis: "Wyszukiwanie w blogu, centrum wiedzy i dokumentacji Danaco Nexus.",
    sciezka: sciezka("szukaj"),
    noindex: true,
  });

  return (
    <>
      <NaglowekStrony
        tytul="Wyszukiwanie"
        opis="Wpisz jedno słowo albo nazwę ekranu. Przeglądamy blog, centrum wiedzy i dokumentację naraz."
      />
      <form
        role="search"
        className="mt-6 flex flex-wrap items-end gap-3"
        onSubmit={(zdarzenie) => {
          zdarzenie.preventDefault();
          nawiguj(`${sciezka("szukaj")}?q=${encodeURIComponent(tekst.trim())}`);
        }}
      >
        <div className="min-w-64 grow">
          <Pole etykieta="Czego szukasz" wartosc={tekst} naZmiane={setTekst} typ="search" podpowiedz="Na przykład „poczta”, „chmura”, „napisy”." />
        </div>
        <Przycisk type="submit">Szukaj</Przycisk>
      </form>

      <div className="mt-8 min-h-[20rem]">
        {zapytanie && wyniki.ladowanie && <Ladowanie wierszy={3} etykieta="Wyszukiwanie" />}
        {wyniki.blad && <Komunikat tekst={wyniki.blad} rodzaj="blad" />}
        {zapytanie && !wyniki.ladowanie && (wyniki.dane?.total ?? 0) === 0 && (
          <>
            <Komunikat tekst={`Nic nie pasuje do „${zapytanie}”. Spróbuj jednego słowa zamiast całego pytania — na przykład „poczta”, nie „jak podłączyć pocztę”.`} />
            {/* Pusty wynik kończył rozmowę jednym zdaniem. Trzy wyjścia poniżej działają
                niezależnie od tego, co ktoś wpisał: spis dokumentacji, centrum wiedzy
                i prośba o opis zagadnienia. */}
            <p className="mt-4 text-sm text-muted">
              Możesz też otworzyć{" "}
              <Odsylacz adres={sciezka("dokumentacja")} className="text-accent hover:underline">
                spis dokumentacji
              </Odsylacz>{" "}
              albo{" "}
              <Odsylacz adres={sciezka("wiedza")} className="text-accent hover:underline">
                centrum wiedzy
              </Odsylacz>
              . Jeżeli opisu nadal nie ma,{" "}
              <Odsylacz adres={sciezka("kontakt")} className="text-accent hover:underline">
                napisz, czego szukasz
              </Odsylacz>{" "}
              — odpowiemy i dopiszemy brakujący materiał.
            </p>
          </>
        )}
        {(wyniki.dane?.total ?? 0) > 0 && (
          <>
            <p aria-live="polite" className="text-sm text-muted">
              Znaleziono {wyniki.dane?.total} pozycji.
            </p>
            <ul className="mt-5 flex flex-col gap-4">
              {(wyniki.dane?.items ?? []).map((pozycja) => {
                const sekcja = SEKCJE[pozycja.kind];
                return (
                  <li key={pozycja.id} className="rounded-xl border border-line bg-raised p-5">
                    <p className="text-xs tracking-wide text-subtle uppercase">{sekcja.nazwa}</p>
                    <h2 className="mt-1 font-heading text-lg font-semibold text-fg">
                      <Odsylacz adres={sciezka(sekcja.strona, pozycja.slug)} className="hover:text-accent">
                        {pozycja.title}
                      </Odsylacz>
                    </h2>
                    <p className="mt-2 text-sm text-muted">{pozycja.excerpt}</p>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>
    </>
  );
}
