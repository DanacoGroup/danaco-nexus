// Zastosowania: osiem sytuacji, w których Nexus zastępuje kilka programów i pół dnia pracy.
//
// Strona istnieje, bo wykaz narzędzi odpowiada na pytanie „co potrafi”, a nie „po co mi to”.
// Każde zastosowanie ma animację kampanijną z pakietu promocja/kampania i wskazuje narzędzia,
// które naprawdę wykonują pracę.

import { useEffect, useRef } from "react";
import { KAMPANIA } from "../../media/katalog";
import { DZIEDZINY } from "../../dane/narzedzia";
import { ZASTOSOWANIA, type Zastosowanie } from "../../dane/zastosowania";
import { odtworz } from "../../modules/mozliwosci/odtwarzanie";
import { okruszki, usePozycjonowanie } from "../seo";
import { sciezka } from "../trasy";
import { NaglowekStrony, OdsylaczPrzycisk, Okruszki } from "../ui";

const OPIS =
  "Osiem sytuacji z życia i z pracy, w których wystarczy opisać zadanie zdaniem. Przy każdej " +
  "widać, co dokładnie napisać, co wraca z powrotem i które narzędzia wykonują pracę.";

/** Nazwy narzędzi po polsku — po identyfikatorze z rejestru. */
const NAZWY = new Map(
  DZIEDZINY.flatMap((grupa) => grupa.narzedzia.map((n) => [n.id, n.nazwa] as const)),
);

/** Animacja tematu w kadrze 16:9. */
function animacja(temat: string) {
  return KAMPANIA.find((pozycja) => pozycja.temat === temat && pozycja.kadr === "16:9") ?? null;
}

function Film({ temat, tytul }: { temat: string; tytul: string }) {
  const element = useRef<HTMLVideoElement>(null);
  const pozycja = animacja(temat);

  useEffect(() => {
    const wideo = element.current;
    if (!wideo) return;
    if (typeof IntersectionObserver !== "function") {
      odtworz(wideo);
      return;
    }
    const obserwator = new IntersectionObserver(
      ([wpis]) => (wpis.isIntersecting ? odtworz(wideo) : wideo.pause()),
      { rootMargin: "120px" },
    );
    obserwator.observe(wideo);
    return () => obserwator.disconnect();
  }, []);

  if (!pozycja) return null;
  return (
    <video
      ref={element}
      className="aspect-video w-full rounded-xl border border-line bg-app object-cover"
      muted
      loop
      playsInline
      preload="metadata"
      poster={pozycja.plakat || undefined}
      aria-label={`Animacja: ${tytul}`}
    >
      {pozycja.zrodla.webm && <source src={pozycja.zrodla.webm} type="video/webm" />}
      {pozycja.zrodla.mp4 && <source src={pozycja.zrodla.mp4} type="video/mp4" />}
    </video>
  );
}

function Sytuacja({ pozycja, indeks }: { pozycja: Zastosowanie; indeks: number }) {
  const odwrotnie = indeks % 2 === 1;
  return (
    <section
      id={pozycja.id}
      aria-labelledby={`zastosowanie-${pozycja.id}`}
      className="scroll-mt-24 border-t border-line pt-10"
    >
      <div className="grid gap-8 lg:grid-cols-2 lg:items-center">
        <div className={odwrotnie ? "lg:order-2" : ""}>
          <p className="text-xs font-semibold tracking-[0.08em] text-accent uppercase">
            {pozycja.dlaKogo}
          </p>
          <h2
            id={`zastosowanie-${pozycja.id}`}
            className="mt-3 font-heading text-2xl font-semibold tracking-tight text-fg"
          >
            {pozycja.tytul}
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted">{pozycja.problem}</p>
        </div>
        <div className={odwrotnie ? "lg:order-1" : ""}>
          <Film temat={pozycja.temat} tytul={pozycja.tytul} />
        </div>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-line bg-raised p-5">
          <h3 className="text-xs font-semibold tracking-[0.08em] text-subtle uppercase">Piszesz</h3>
          <p className="mt-2.5 text-base leading-relaxed text-fg italic">„{pozycja.polecenie}”</p>
        </div>
        <div className="rounded-xl border border-line bg-raised p-5">
          <h3 className="text-xs font-semibold tracking-[0.08em] text-subtle uppercase">Dostajesz</h3>
          <p className="mt-2.5 text-sm leading-relaxed text-muted">{pozycja.wynik}</p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-xs text-subtle">Pracę wykonują:</span>
        {pozycja.narzedzia.map((id) => (
          <span key={id} className="rounded-full border border-line px-2.5 py-1 text-xs text-muted">
            {NAZWY.get(id) ?? id}
          </span>
        ))}
      </div>
    </section>
  );
}

export function Zastosowania() {
  usePozycjonowanie({
    tytul: "Zastosowania",
    opis: OPIS,
    sciezka: sciezka("zastosowania"),
    dane: okruszki([
      { nazwa: "Portal", sciezka: sciezka("glowna") },
      { nazwa: "Zastosowania", sciezka: sciezka("zastosowania") },
    ]),
  });

  return (
    <>
      <Okruszki
        pozycje={[
          { nazwa: "Portal", sciezka: sciezka("glowna") },
          { nazwa: "Zastosowania", sciezka: sciezka("zastosowania") },
        ]}
      />
      <div className="mt-4">
          <NaglowekStrony tytul="Osiem sytuacji, w których opisujesz wynik i dostajesz plik" opis={OPIS} />
      </div>

      <nav aria-label="Spis zastosowań" className="mt-8 flex flex-wrap gap-2">
        {ZASTOSOWANIA.map((pozycja) => (
          <a
            key={pozycja.id}
            href={`#${pozycja.id}`}
            className="rounded-full border border-line px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:bg-hover hover:text-fg"
          >
            {pozycja.tytul}
          </a>
        ))}
      </nav>

      <div className="mt-12 space-y-14">
        {ZASTOSOWANIA.map((pozycja, indeks) => (
          <Sytuacja key={pozycja.id} pozycja={pozycja} indeks={indeks} />
        ))}
      </div>

      <div className="mt-14 border-t border-line pt-10">
        <h2 className="font-heading text-2xl font-semibold text-fg">Zrób jedno własne zadanie</h2>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          Pod adresem /wyprobuj otwiera się pełna aplikacja — bez rejestracji, bez karty, bez
          instalacji. Wgraj jeden skan i poproś o tabelę. Plik odbierzesz w tej samej rozmowie.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <OdsylaczPrzycisk adres="/wyprobuj">Otwórz Nexusa bez rejestracji</OdsylaczPrzycisk>
          <OdsylaczPrzycisk adres={sciezka("narzedzia")} wariant="drugorzedny">
            Zobacz wszystkie 101 narzędzi
          </OdsylaczPrzycisk>
        </div>
      </div>
    </>
  );
}
