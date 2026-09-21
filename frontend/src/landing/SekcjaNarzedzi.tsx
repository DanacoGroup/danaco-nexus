// „Dziesięć dziedzin, wszystkie narzędzia” — sekcja strony produktu z pełnym zakresem agenta.
//
// Do tej pory strona mówiła o narzędziach ogólnikiem, przez co Nexus wyglądał na program
// do faktur i kartek. Spis pochodzi z rejestru backend/nexus/tools (frontend/scripts/narzedzia.py),
// nagrania z pakietu motion/stany — nic tu nie jest przepisane ręcznie ani obiecane na wyrost.

import { useEffect, useRef, useState } from "react";
import { DZIEDZINY, LICZBA_NARZEDZI } from "../dane/narzedzia";
import { odtworz } from "../modules/mozliwosci/odtwarzanie";
import { nagranieNarzedzia } from "../modules/mozliwosci/ruch";
import { Naglowek, Sekcja } from "./sekcje";
import { PrzejscieWidoku, useWidocznosc } from "../ruch";
import { tlo } from "./uzyj";

/** Nagranie dziedziny: pierwsze narzędzie, dla którego pakiet ruchu ma ujęcie. */
function nagranieDziedziny(indeks: number) {
  const grupa = DZIEDZINY[indeks];
  const narzedzie = grupa.narzedzia.find((pozycja) => nagranieNarzedzia(pozycja.id));
  return narzedzie ? nagranieNarzedzia(narzedzie.id) : null;
}

export function SekcjaNarzedzi() {
  const [wybrana, setWybrana] = useState(0);
  const [element, widoczne] = useWidocznosc<HTMLDivElement>({ ciagla: true });
  const wideo = useRef<HTMLVideoElement>(null);
  const grupa = DZIEDZINY[wybrana];
  const zrodla = nagranieDziedziny(wybrana);

  useEffect(() => {
    const film = wideo.current;
    if (!film) return;
    if (widoczne) odtworz(film);
    else film.pause();
  }, [widoczne, wybrana]);

  return (
    <Sekcja id="narzedzia" className="landing-tlo" style={tlo("aurora-mgla", 0.5)}>
      <Naglowek
        nad="Zakres"
        tytul="Dziesięć dziedzin. Jedna rozmowa."
        akapit={`Nexus ma ${LICZBA_NARZEDZI} narzędzi w dziesięciu dziedzinach. Projektuje grafikę od zera, prowadzi badanie ze źródłami, odpisuje na pocztę i pilnuje terminarza. Publikuje stronę pod adresem /s/nazwa-strony/ i sięga do plików na Twoim komputerze. Narzędzia dobiera sam — Ty piszesz jednym zdaniem, co ma powstać.`}
      />

      <div ref={element} className="mt-12 grid gap-8 lg:grid-cols-[22rem_1fr] lg:items-start">
        <div role="tablist" aria-label="Dziedziny narzędzi" className="flex flex-wrap gap-2 lg:flex-col">
          {DZIEDZINY.map((pozycja, indeks) => (
            <button
              key={pozycja.id}
              type="button"
              role="tab"
              id={`zakladka-${pozycja.id}`}
              aria-selected={indeks === wybrana}
              aria-controls={`panel-${pozycja.id}`}
              onClick={() => setWybrana(indeks)}
              className={`ui-nacisk rounded-xl px-4 py-3 text-left text-sm font-medium transition-colors lg:w-full ${
                indeks === wybrana
                  ? "bg-raised text-fg shadow-[var(--shadow-floating)]"
                  : "text-muted hover:bg-hover hover:text-fg"
              }`}
            >
              <span className="block">{pozycja.tytul}</span>
              <span className="mt-0.5 block text-xs text-subtle">
                {pozycja.narzedzia.length} {pozycja.narzedzia.length === 1 ? "narzędzie" : "narzędzi"}
              </span>
            </button>
          ))}
        </div>

        <div
          role="tabpanel"
          id={`panel-${grupa.id}`}
          aria-labelledby={`zakladka-${grupa.id}`}
          className="landing-karta overflow-hidden"
        >
          {zrodla && (
            <video
              ref={wideo}
              key={grupa.id}
              className="aspect-video w-full border-b border-line/60 bg-app object-cover"
              muted
              loop
              playsInline
              preload="metadata"
              aria-hidden="true"
            >
              {zrodla.webm && <source src={zrodla.webm} type="video/webm" />}
              {zrodla.mp4 && <source src={zrodla.mp4} type="video/mp4" />}
            </video>
          )}
          {/* Zmiana dziedziny to zmiana widoku; nagranie zostaje poza przejściem, bo ma
              własny cykl odtwarzania. */}
          <PrzejscieWidoku klucz={grupa.id} className="p-6 md:p-8">
            <h3 className="font-heading text-2xl font-bold tracking-tight">{grupa.tytul}</h3>
            <p className="mt-2 text-base leading-relaxed text-muted">{grupa.opis}</p>
            <ul className="mt-6 grid gap-3 sm:grid-cols-2">
              {grupa.narzedzia.map((narzedzie) => (
                <li key={narzedzie.id} className="rounded-lg border border-line px-3.5 py-2.5">
                  <span className="text-sm font-medium text-fg">{narzedzie.nazwa}</span>
                  {narzedzie.przyklad && (
                    <span className="mt-1 block text-xs text-subtle">„{narzedzie.przyklad}”</span>
                  )}
                </li>
              ))}
            </ul>
            <a
              href="/portal/narzedzia"
              className="mt-7 inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline"
            >
              Zobacz wszystkie {LICZBA_NARZEDZI} narzędzi
              <span aria-hidden="true">→</span>
            </a>
            <p className="mt-4 text-sm text-muted">
              Narzędzia z tej listy uruchomisz od razu:{" "}
              <a href="/wyprobuj" className="text-accent underline-offset-4 hover:underline">
                wejdź na /wyprobuj
              </a>{" "}
              i opisz zadanie własnymi słowami.
            </p>
          </PrzejscieWidoku>
        </div>
      </div>
    </Sekcja>
  );
}
