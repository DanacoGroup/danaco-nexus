// Narzędzia: publiczny katalog wszystkich narzędzi agenta — po to, żeby przed założeniem konta
// dało się sprawdzić, czy Nexus robi to, czego się od niego oczekuje.
//
// Spis pochodzi z rejestru backend/nexus/tools (generuje go frontend/scripts/narzedzia.py),
// a nagrania z pakietu motion/stany (frontend/scripts/zasoby.py). Nic tu nie jest przepisane
// ręcznie, więc strona nie może obiecać narzędzia, którego agent nie ma.

import { useEffect, useMemo, useRef, useState } from "react";
import { DZIEDZINY, LICZBA_NARZEDZI, type Narzedzie } from "../../dane/narzedzia";
import { odtworz } from "../../modules/mozliwosci/odtwarzanie";
import { nagranieNarzedzia } from "../../modules/mozliwosci/ruch";
import { okruszki, usePozycjonowanie } from "../seo";
import { sciezka } from "../trasy";
import { NaglowekStrony, OdsylaczPrzycisk, Znacznik } from "../ui";

const OPIS =
  `Pełny wykaz ${LICZBA_NARZEDZI} narzędzi, po które Nexus sięga w Twoim imieniu — od poprawy zdjęcia ` +
  "i rozpoznania tekstu ze skanu po publikację strony i pracę na Twoim komputerze. Nie wybierasz " +
  "narzędzia: piszesz zdaniem, co ma powstać.";

function Nagranie({ id }: { id: string }) {
  const zrodla = nagranieNarzedzia(id);
  const element = useRef<HTMLVideoElement>(null);

  // Nagranie rusza dopiero, gdy wejdzie w kadr, i staje, gdy z niego wyjdzie.
  // Osiem sekcji odtwarzanych naraz kosztowałoby pasmo i baterię bez żadnego pożytku.
  useEffect(() => {
    const wideo = element.current;
    if (!wideo) return;
    if (typeof IntersectionObserver !== "function") {
      odtworz(wideo);
      return;
    }
    const obserwator = new IntersectionObserver(
      ([wpis]) => {
        if (wpis.isIntersecting) odtworz(wideo);
        else wideo.pause();
      },
      { rootMargin: "100px" },
    );
    obserwator.observe(wideo);
    return () => obserwator.disconnect();
  }, []);

  if (!zrodla) return null;
  return (
    <video
      ref={element}
      className="aspect-video w-full rounded-lg border border-line/60 bg-app object-cover"
      muted
      loop
      playsInline
      preload="metadata"
      aria-hidden="true"
    >
      {zrodla.webm && <source src={zrodla.webm} type="video/webm" />}
      {zrodla.mp4 && <source src={zrodla.mp4} type="video/mp4" />}
    </video>
  );
}

function Pozycja({ narzedzie }: { narzedzie: Narzedzie }) {
  return (
    <li className="rounded-xl border border-line bg-raised p-4">
      <h3 className="font-heading text-base font-semibold text-fg">{narzedzie.nazwa}</h3>
      <p className="mt-1.5 text-sm text-muted">{narzedzie.opis}</p>
      {narzedzie.przyklad && (
        <p className="mt-3 border-l-2 border-accent/60 pl-3 text-sm italic text-subtle">
          „{narzedzie.przyklad}”
        </p>
      )}
    </li>
  );
}

export function Narzedzia() {
  const [szukane, setSzukane] = useState("");

  usePozycjonowanie({
    tytul: "Narzędzia agenta",
    opis: OPIS,
    sciezka: sciezka("narzedzia"),
    dane: okruszki([
      { nazwa: "Portal", sciezka: sciezka("glowna") },
      { nazwa: "Narzędzia agenta", sciezka: sciezka("narzedzia") },
    ]),
  });

  const igla = szukane.trim().toLocaleLowerCase("pl");
  const widoczne = useMemo(
    () =>
      DZIEDZINY.map((grupa) => ({
        ...grupa,
        narzedzia: igla
          ? grupa.narzedzia.filter((narzedzie) =>
              [narzedzie.nazwa, narzedzie.opis, narzedzie.przyklad].some((pole) =>
                pole.toLocaleLowerCase("pl").includes(igla),
              ),
            )
          : grupa.narzedzia,
      })).filter((grupa) => grupa.narzedzia.length > 0),
    [igla],
  );
  const znalezione = widoczne.reduce((suma, grupa) => suma + grupa.narzedzia.length, 0);

  return (
    <>
      <NaglowekStrony tytul="Sprawdź, czy Nexus zrobi to, czego potrzebujesz" opis={OPIS}>
        <Znacznik tekst={`${LICZBA_NARZEDZI} narzędzi`} />
        <Znacznik tekst={`${DZIEDZINY.length} dziedzin`} ton="cichy" />
      </NaglowekStrony>

      <label className="mt-8 block">
        <span className="sr-only">Szukaj wśród narzędzi</span>
        <input
          value={szukane}
          onChange={(zdarzenie) => setSzukane(zdarzenie.target.value)}
          placeholder="Szukaj: faktura, nagranie, tło, publikacja…"
          className="h-11 w-full rounded-lg border border-line-control bg-raised px-3.5 text-sm outline-none transition-colors focus:border-accent"
        />
      </label>
      <p aria-live="polite" className="mt-2 text-xs text-subtle">
        {igla ? `Pasujących narzędzi: ${znalezione}` : `Wszystkich narzędzi: ${LICZBA_NARZEDZI}`}
      </p>

      {widoczne.length === 0 && (
        <p className="mt-10 text-sm text-muted">
          Nic nie pasuje do „{szukane}”. Napisz do nas — jeśli czegoś brakuje, chcemy o tym wiedzieć.
        </p>
      )}

      {widoczne.map((grupa, indeks) => (
        <section key={grupa.id} aria-labelledby={`dziedzina-${grupa.id}`} className="mt-12">
          {/* Nagranie raz z prawej, raz z lewej — kolumna z nim zawsze ma tę samą szerokość,
              więc zamiana stron nie rozciąga obrazu na pół sekcji. */}
          <div
            className={`grid gap-6 md:items-center ${
              indeks % 2 === 1 ? "md:grid-cols-[20rem_1fr]" : "md:grid-cols-[1fr_20rem]"
            }`}
          >
            <div className={indeks % 2 === 1 ? "md:order-2" : ""}>
              <h2 id={`dziedzina-${grupa.id}`} className="font-heading text-xl font-semibold text-fg">
                {grupa.tytul}
              </h2>
              <p className="mt-1.5 text-sm text-muted">{grupa.opis}</p>
            </div>
            <div className={indeks % 2 === 1 ? "md:order-1" : ""}>
              {/* Pierwsze narzędzie dziedziny, dla którego istnieje nagranie —
                  nie każda pozycja ma swoje ujęcie w pakiecie ruchu. */}
              <Nagranie
                id={(grupa.narzedzia.find((n) => nagranieNarzedzia(n.id)) ?? grupa.narzedzia[0]).id}
              />
            </div>
          </div>
          <ul className="mt-5 grid gap-4 sm:grid-cols-2">
            {grupa.narzedzia.map((narzedzie) => (
              <Pozycja key={narzedzie.id} narzedzie={narzedzie} />
            ))}
          </ul>
        </section>
      ))}

      <div className="mt-12 flex flex-wrap gap-3">
        <OdsylaczPrzycisk adres="/wyprobuj">Wejdź bez rejestracji</OdsylaczPrzycisk>
        <OdsylaczPrzycisk adres={sciezka("cennik")} wariant="drugorzedny">
          Zobacz cennik
        </OdsylaczPrzycisk>
      </div>
    </>
  );
}
