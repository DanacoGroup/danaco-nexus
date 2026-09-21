// Lista treści portalu: blog i centrum wiedzy (strona z filtrem znaczników i stronicowaniem).

import { useState } from "react";
import { dataPolska, portalApi, type RodzajTresci, type SkrotTresci } from "../api";
import { useZasob } from "../dane";
import { okruszki, usePozycjonowanie } from "../seo";
import { SCIEZKA } from "../../shell/route";
import { sciezka, type PortalStrona } from "../trasy";
import { Karta, Komunikat, Ladowanie, NaglowekStrony, Odsylacz, Okruszki, Przycisk, Znacznik } from "../ui";

const NA_STRONIE = 9;

export function KartaWpisu({ pozycja, adres }: { pozycja: SkrotTresci; adres: string }) {
  return (
    <li className="h-full">
      <Karta className="flex h-full flex-col gap-3">
        <h3 className="font-heading text-lg font-semibold text-fg">
          <Odsylacz adres={adres} className="hover:text-accent">
            {pozycja.title}
          </Odsylacz>
        </h3>
        <p className="grow text-sm text-muted">{pozycja.excerpt}</p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-subtle">
          {pozycja.published_at && <time dateTime={pozycja.published_at}>{dataPolska(pozycja.published_at)}</time>}
          {pozycja.author && <span>· {pozycja.author}</span>}
        </div>
        {pozycja.tags.length > 0 && (
          <ul className="flex flex-wrap gap-2">
            {pozycja.tags.map((znacznik) => (
              <li key={znacznik}>
                <Znacznik tekst={znacznik} />
              </li>
            ))}
          </ul>
        )}
      </Karta>
    </li>
  );
}

export function ListaWpisow({
  strona,
  rodzaj,
  tytul,
  opis,
}: {
  strona: PortalStrona;
  rodzaj: RodzajTresci;
  tytul: string;
  opis: string;
}) {
  const [numer, setNumer] = useState(1);
  const [tag, setTag] = useState("");
  const adresListy = sciezka(strona);
  const lista = useZasob(
    () => portalApi.lista({ typ: rodzaj, tag, strona: numer, na_stronie: NA_STRONIE }),
    `${rodzaj}:${tag}:${numer}`,
  );
  const znaczniki = useZasob(() => portalApi.znaczniki(rodzaj), `znaczniki:${rodzaj}`);

  usePozycjonowanie({
    tytul,
    opis,
    sciezka: adresListy,
    dane: okruszki([
      { nazwa: "Portal", sciezka: sciezka("glowna") },
      { nazwa: tytul, sciezka: adresListy },
    ]),
  });

  const pozycje = lista.dane?.items ?? [];
  return (
    <>
      <NaglowekStrony tytul={tytul} opis={opis} />
      {(znaczniki.dane?.length ?? 0) > 0 && (
        <nav aria-label="Filtr znaczników" className="mt-6 flex flex-wrap gap-2">
          <Przycisk
            wariant={tag === "" ? "glowny" : "drugorzedny"}
            aria-pressed={tag === ""}
            onClick={() => {
              setTag("");
              setNumer(1);
            }}
          >
            Wszystkie
          </Przycisk>
          {(znaczniki.dane ?? []).slice(0, 10).map((pozycja) => (
            <Przycisk
              key={pozycja.tag}
              wariant={tag === pozycja.tag ? "glowny" : "drugorzedny"}
              aria-pressed={tag === pozycja.tag}
              onClick={() => {
                setTag(pozycja.tag);
                setNumer(1);
              }}
            >
              {pozycja.tag} ({pozycja.count})
            </Przycisk>
          ))}
        </nav>
      )}
      <div className="mt-8 min-h-[24rem]">
        {lista.ladowanie && <Ladowanie wierszy={3} etykieta="Wczytywanie listy" />}
        {!lista.ladowanie && lista.blad && <Komunikat tekst={lista.blad} rodzaj="blad" />}
        {!lista.ladowanie && !lista.blad && pozycje.length === 0 && (
          tag ? (
            <Komunikat tekst={`Nic nie pasuje do znacznika „${tag}”. Wybierz „Wszystkie”, aby zobaczyć całą listę.`} />
          ) : (
            // Wcześniej pusta sekcja odsyłała do dokumentacji, która sama bywa pusta — rada
            // prowadziła donikąd. Te dwa wyjścia działają niezależnie od tego, czy redakcja
            // zdążyła cokolwiek opublikować.
            <div className="max-w-prose">
              <Komunikat tekst="Ta sekcja czeka na pierwsze materiały." />
              <p className="mt-4 text-sm text-muted">
                Zanim się zapełni:{" "}
                <Odsylacz adres={SCIEZKA.piaskownica} className="text-accent hover:underline">
                  wypróbuj Nexusa bez rejestracji
                </Odsylacz>{" "}
                albo{" "}
                <Odsylacz adres={sciezka("kontakt")} className="text-accent hover:underline">
                  napisz, czego potrzebujesz
                </Odsylacz>
                .
              </p>
            </div>
          )
        )}
        {pozycje.length > 0 && (
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {pozycje.map((pozycja) => (
              <KartaWpisu key={pozycja.id} pozycja={pozycja} adres={sciezka(strona, pozycja.slug)} />
            ))}
          </ul>
        )}
      </div>
      {(lista.dane?.pages ?? 1) > 1 && (
        <nav aria-label="Stronicowanie" className="mt-8 flex items-center justify-center gap-3">
          <Przycisk wariant="drugorzedny" disabled={numer <= 1} onClick={() => setNumer(numer - 1)}>
            Poprzednia
          </Przycisk>
          <p aria-live="polite" className="text-sm text-muted">
            Strona {lista.dane?.page} z {lista.dane?.pages}
          </p>
          <Przycisk
            wariant="drugorzedny"
            disabled={numer >= (lista.dane?.pages ?? 1)}
            onClick={() => setNumer(numer + 1)}
          >
            Następna
          </Przycisk>
        </nav>
      )}
      <div className="mt-10">
        <Okruszki
          pozycje={[
            { nazwa: "Portal", sciezka: sciezka("glowna") },
            { nazwa: tytul, sciezka: adresListy },
          ]}
        />
      </div>
    </>
  );
}
