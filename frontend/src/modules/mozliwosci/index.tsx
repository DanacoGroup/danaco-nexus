// Moduł „Możliwości”: pełny wykaz tego, co Nexus potrafi — dziedzina po dziedzinie,
// narzędzie po narzędziu, z przykładowym zdaniem do wpisania i nagraniem pokazującym pracę.
//
// Spis narzędzi generuje frontend/scripts/narzedzia.py z rejestru backend/nexus/tools,
// więc moduł nie może obiecać czegoś, czego agent nie ma, ani przemilczeć nowego narzędzia.

import { useEffect, useMemo, useRef, useState } from "react";
import { DZIEDZINY, LICZBA_NARZEDZI, type Narzedzie } from "../../dane/narzedzia";
import type { ModulePageProps, NexusModule } from "../registry";
import { odtworz } from "./odtwarzanie";
import { nagranieNarzedzia } from "./ruch";
import { SparkIcon } from "./icons";

function pasuje(narzedzie: Narzedzie, szukane: string): boolean {
  if (!szukane) return true;
  const igla = szukane.toLocaleLowerCase("pl");
  return [narzedzie.nazwa, narzedzie.opis, narzedzie.przyklad].some((pole) =>
    pole.toLocaleLowerCase("pl").includes(igla),
  );
}

function KartaNarzedzia({ narzedzie, onUzyj }: { narzedzie: Narzedzie; onUzyj: (tekst: string) => void }) {
  const [ruch, setRuch] = useState(false);
  const wideo = useRef<HTMLVideoElement>(null);
  const nagranie = nagranieNarzedzia(narzedzie.id);

  // Pierwsza klatka jest widoczna od razu (preload="metadata"), ale ruch zaczyna się
  // dopiero pod kursorem: kilkadziesiąt nagrań naraz to zmarnowane pasmo i bateria.
  useEffect(() => {
    const element = wideo.current;
    if (!element) return;
    if (ruch) odtworz(element);
    else element.pause();
  }, [ruch]);

  return (
    <li
      className="group relative flex flex-col overflow-hidden rounded-xl border border-line bg-raised transition-colors hover:border-line-strong"
      onMouseEnter={() => setRuch(true)}
      onMouseLeave={() => setRuch(false)}
      onFocusCapture={() => setRuch(true)}
      onBlurCapture={() => setRuch(false)}
    >
      {nagranie && (
        <div className="relative aspect-video overflow-hidden border-b border-line/60 bg-app">
          <video
            ref={wideo}
            className="size-full object-cover"
            muted
            loop
            playsInline
            preload="metadata"
            aria-hidden="true"
          >
            {nagranie.webm && <source src={nagranie.webm} type="video/webm" />}
            {nagranie.mp4 && <source src={nagranie.mp4} type="video/mp4" />}
          </video>
        </div>
      )}
      <div className="flex flex-1 flex-col p-4">
        <h3 className="font-heading text-base font-semibold text-fg">{narzedzie.nazwa}</h3>
        <p className="mt-1.5 line-clamp-3 flex-1 text-sm text-muted" title={narzedzie.opis}>
          {narzedzie.opis}
        </p>
        {narzedzie.przyklad && (
          <button
            type="button"
            onClick={() => onUzyj(narzedzie.przyklad)}
            className="mt-3 rounded-lg border border-line-control px-3 py-2 text-left text-sm text-fg transition-colors hover:bg-hover"
          >
            <span className="mr-1.5 text-subtle">Napisz:</span>
            „{narzedzie.przyklad}”
          </button>
        )}
      </div>
    </li>
  );
}

function Strona({ openChat }: ModulePageProps) {
  const [szukane, setSzukane] = useState("");
  const [dziedzina, setDziedzina] = useState("");
  const [skopiowane, setSkopiowane] = useState("");

  const widoczne = useMemo(
    () =>
      DZIEDZINY.filter((grupa) => !dziedzina || grupa.id === dziedzina)
        .map((grupa) => ({ ...grupa, narzedzia: grupa.narzedzia.filter((n) => pasuje(n, szukane)) }))
        .filter((grupa) => grupa.narzedzia.length > 0),
    [szukane, dziedzina],
  );
  const znalezione = widoczne.reduce((suma, grupa) => suma + grupa.narzedzia.length, 0);

  // Zdanie ląduje w polu wiadomości nowej rozmowy; kopia w schowku jest zapasem,
  // gdy użytkownik woli wkleić je gdzie indziej.
  const uzyj = (tekst: string) => {
    void navigator.clipboard?.writeText(tekst).catch(() => undefined);
    setSkopiowane(tekst);
    openChat(tekst);
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-5 py-8">
        <header>
          <h1 className="font-heading text-2xl font-semibold tracking-tight text-fg">Co potrafi Nexus</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            {LICZBA_NARZEDZI} narzędzi w {DZIEDZINY.length} dziedzinach. Nie musisz ich wybierać ani
            zapamiętywać — piszesz zdaniem, co ma powstać, a agent sam sięga po to, czego trzeba.
            Przykład pod każdym narzędziem możesz kliknąć i wysłać.
          </p>
        </header>

        <div className="sticky top-0 z-10 -mx-5 mt-6 border-b border-line/60 bg-app/90 px-5 pb-3 pt-1 backdrop-blur">
          <label className="block">
            <span className="sr-only">Szukaj wśród narzędzi</span>
            <input
              value={szukane}
              onChange={(zdarzenie) => setSzukane(zdarzenie.target.value)}
              placeholder="Szukaj: faktura, nagranie, tło, publikacja…"
              className="h-11 w-full rounded-lg border border-line-control bg-raised px-3.5 text-sm outline-none transition-colors focus:border-accent"
            />
          </label>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setDziedzina("")}
              aria-pressed={dziedzina === ""}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                dziedzina === "" ? "bg-accent-fill text-on-accent" : "border border-line text-muted hover:bg-hover"
              }`}
            >
              Wszystkie
            </button>
            {DZIEDZINY.map((grupa) => (
              <button
                key={grupa.id}
                type="button"
                onClick={() => setDziedzina(grupa.id === dziedzina ? "" : grupa.id)}
                aria-pressed={grupa.id === dziedzina}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  grupa.id === dziedzina ? "bg-accent-fill text-on-accent" : "border border-line text-muted hover:bg-hover"
                }`}
              >
                {grupa.tytul}
              </button>
            ))}
          </div>
        </div>

        <p aria-live="polite" className="mt-4 text-xs text-subtle">
          {szukane || dziedzina ? `Pasujących narzędzi: ${znalezione}` : `Wszystkich narzędzi: ${LICZBA_NARZEDZI}`}
        </p>

        {widoczne.length === 0 && (
          <p className="mt-10 text-center text-sm text-muted">
            Nic nie pasuje do „{szukane}”. Spróbuj innego słowa — albo po prostu opisz zadanie w rozmowie.
          </p>
        )}

        {widoczne.map((grupa) => (
          <section key={grupa.id} aria-labelledby={`dziedzina-${grupa.id}`} className="mt-10">
            <h2 id={`dziedzina-${grupa.id}`} className="font-heading text-xl font-semibold text-fg">
              {grupa.tytul}
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">{grupa.opis}</p>
            <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {grupa.narzedzia.map((narzedzie) => (
                <KartaNarzedzia key={narzedzie.id} narzedzie={narzedzie} onUzyj={uzyj} />
              ))}
            </ul>
          </section>
        ))}

        <div aria-live="polite" className="sr-only">
          {skopiowane && `Skopiowano zdanie: ${skopiowane}`}
        </div>
      </div>
    </div>
  );
}

export const module: NexusModule = {
  id: "mozliwosci",
  label: "Narzędzia",
  description: `Wszystko, co Nexus potrafi — ${LICZBA_NARZEDZI} narzędzi z przykładami`,
  icon: SparkIcon,
  order: 20,
  Page: Strona,
};
