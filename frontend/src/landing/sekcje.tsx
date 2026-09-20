// Sekcje strony produktu: pasek zdań, kroki, funkcje, filmy, prywatność, zaufanie, cennik, pytania, brama.
// Treść i zachowanie: landing/LANDING_PAGE_SPEC.md, rozdz. 7.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { CheckIcon, PlusIcon, SparkIcon, ToolIcon } from "../components/icons";
import { ArrowRightIcon, DocumentIcon, LockIcon, PhoneIcon, ShieldIcon, WindowsIcon } from "../shell/icons";
import {
  FILMY,
  GWARANCJE,
  KARTY,
  KROKI,
  LICZBY,
  NAGRANIA,
  PLANY,
  PYTANIA,
  ROZNICE,
  TECHNOLOGIE,
  ZASADY,
  ZDANIA_TOR_1,
  ZDANIA_TOR_2,
  type FilmPromocyjny,
} from "./tresc";
import { LICZBA_NARZEDZI } from "../dane/narzedzia";
import { PASMO, tlo } from "./uzyj";
import { kaskada, TloNaZywo, useWidocznosc, WarstwaZiarna } from "../ruch";

export function Sekcja({
  id,
  children,
  className = "",
  style,
}: {
  id?: string;
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <section id={id} className={`relative scroll-mt-24 py-20 md:py-28 ${className}`} style={style}>
      <div className={PASMO}>{children}</div>
    </section>
  );
}

export function Naglowek({
  nad,
  tytul,
  akapit,
  srodek = false,
}: {
  nad: string;
  tytul: string;
  akapit?: string;
  srodek?: boolean;
}) {
  return (
    <div className={srodek ? "mx-auto max-w-(--container-prose) text-center" : "max-w-(--container-prose)"}>
      <p className="text-xs font-semibold tracking-[0.08em] text-accent uppercase">{nad}</p>
      <h2 className="mt-4 font-heading text-3xl leading-tight font-bold tracking-tighter text-balance md:text-5xl">{tytul}</h2>
      {akapit && <p className="mt-5 text-lg leading-relaxed text-muted text-pretty">{akapit}</p>}
    </div>
  );
}

/** Pasek „Powiedz to własnymi słowami” — dwa tory kapsuł w przeciwnych kierunkach. */
export function PasekZdan() {
  // Czas przesuwu liczony z tokenu ruchu ciągłego; drugi tor jest wolniejszy, żeby tory nie szły równo.
  const tory = [
    { klucz: "wprzod", zdania: ZDANIA_TOR_1, czas: "calc(var(--duration-ambient) * 30)", wstecz: false },
    { klucz: "wstecz", zdania: ZDANIA_TOR_2, czas: "calc(var(--duration-ambient) * 34)", wstecz: true },
  ];
  // Pętla przesuwu stoi poza polem widzenia — ruch ciągły nie może biec w tle (WCAG 2.2.2).
  const [sekcja, widoczna] = useWidocznosc<HTMLElement>({ margines: "100px", ciagla: true });
  return (
    <section
      ref={sekcja}
      data-widoczny={widoczna ? "true" : "false"}
      aria-label="Przykładowe polecenia"
      className="relative overflow-hidden border-y border-line py-10"
    >
      <div className="flex flex-col gap-3 [mask-image:linear-gradient(to_right,transparent,#000_8%,#000_92%,transparent)]">
        {tory.map(({ klucz, zdania, czas, wstecz }) => (
          <div key={klucz} className="pasek-tor flex w-max gap-3" style={{ "--czas": czas, "--kierunek": wstecz ? "reverse" : "normal" } as React.CSSProperties}>
            {[0, 1].map((kopia) => (
              <div key={kopia} className="flex shrink-0 gap-3" aria-hidden={kopia === 1}>
                {zdania.map((zdanie) => (
                  <span
                    key={zdanie}
                    className="inline-flex items-center gap-2 rounded-full border border-line bg-raised/70 px-4 py-2 font-heading text-base font-semibold whitespace-nowrap"
                  >
                    <SparkIcon size={16} className="text-accent" />
                    {zdanie}
                  </span>
                ))}
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

/** „Jedno zdanie. Cztery kroki.” — droga od wyblakłej odbitki do kartki do druku. */
export function SekcjaKroki() {
  const [element, widoczne] = useWidocznosc<HTMLOListElement>();
  return (
    <Sekcja id="jak-dziala" className="landing-tlo" style={tlo("cieply-swit", 0.7)}>
      <Naglowek
        nad="Jak to działa"
        tytul="Jedno zdanie. Cztery kroki."
        akapit="„Babcia kończy w niedzielę 80 lat. Odśwież to zdjęcie i zrób z niego kartkę do wydruku.” Resztę Nexus rozpisuje sam — a Ty widzisz każdy krok."
        srodek
      />
      <ol ref={element} className="mt-16 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {KROKI.map((krok, indeks) => (
          <li
            key={krok.numer}
            className="landing-karta ui-ujawnij p-6"
            data-widoczny={widoczne ? "true" : "false"}
            style={kaskada(indeks)}
          >
            <span className="grid size-9 place-items-center rounded-full bg-accent-soft font-heading text-base font-bold text-accent tabular-nums">
              {krok.numer}
            </span>
            <h3 className="mt-5 font-heading text-xl font-bold tracking-tight">{krok.tytul}</h3>
            <p className="mt-2 leading-relaxed text-muted">{krok.opis}</p>
            <p className="mt-5 rounded-md bg-code px-2.5 py-1.5 font-mono text-xs text-subtle">{krok.znacznik}</p>
          </li>
        ))}
      </ol>
    </Sekcja>
  );
}

/** „Czym to się różni” — odpowiedź na pytanie o przewagę nad zwykłym czatem z modelem. */
export function SekcjaRoznice() {
  const [element, widoczne] = useWidocznosc<HTMLUListElement>();
  return (
    <Sekcja id="roznice">
      <Naglowek
        nad="Czym to się różni"
        tytul="Nie odpowiada. Wykonuje."
        akapit="Rozmowa z modelem kończy się tekstem na ekranie. Nexus kończy się plikiem, który wydrukujesz, wyślesz albo wrzucisz do księgowości."
        srodek
      />
      <ul ref={element} className="mt-14 grid gap-4 md:grid-cols-2">
        {ROZNICE.map(({ tytul, opis }, indeks) => (
          <li
            key={tytul}
            className="landing-karta ui-ujawnij flex gap-4 p-6"
            data-widoczny={widoczne ? "true" : "false"}
            style={kaskada(indeks)}
          >
            <CheckIcon size={20} className="mt-1 shrink-0 text-accent" />
            <div>
              <h3 className="font-heading text-lg font-bold tracking-tight">{tytul}</h3>
              <p className="mt-2 leading-relaxed text-muted">{opis}</p>
            </div>
          </li>
        ))}
      </ul>
    </Sekcja>
  );
}

/** Nagranie z pakietu ruchu: gra tylko w polu widzenia, bez dźwięku, z opisem dla czytnika. */
function Nagranie({ zrodlo, opis }: { zrodlo: string; opis: string }) {
  const [element, widoczne] = useWidocznosc<HTMLVideoElement>({ ciagla: true });
  useEffect(() => {
    const film = element.current;
    if (!film) return;
    if (widoczne) void film.play().catch(() => undefined);
    else film.pause();
  }, [widoczne, element]);
  return (
    <video
      ref={element}
      className="w-full rounded-lg border border-line bg-app"
      src={zrodlo}
      muted
      loop
      playsInline
      preload="none"
      aria-label={opis}
    />
  );
}

/** „Tak to wygląda w ruchu” — nagrania zachowań interfejsu z pakietu motion. */
export function SekcjaRuch() {
  return (
    <Sekcja>
      <Naglowek
        nad="W ruchu"
        tytul="Widać, co robi. I kiedy skończy."
        akapit="Nagrania z prawdziwego interfejsu: praca agenta, odpowiedź pisana na żywo, pliki upuszczone do rozmowy i paleta poleceń."
        srodek
      />
      <div className="mt-14 grid gap-4 sm:grid-cols-2">
        {NAGRANIA.map((nagranie) => (
          <figure key={nagranie.plik} className="landing-karta p-5">
            <Nagranie zrodlo={nagranie.plik} opis={`Nagranie: ${nagranie.tytul}`} />
            <figcaption className="mt-4">
              <h3 className="font-heading text-lg font-bold tracking-tight">{nagranie.tytul}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{nagranie.opis}</p>
            </figcaption>
          </figure>
        ))}
      </div>
    </Sekcja>
  );
}

/** Barwy legendy kart: Apricot znaczy życie, Sky pracę (tokeny marki, bez wartości własnych). */
const BARWA_ZYCIE = "var(--color-brand-apricot)";
const BARWA_PRACA = "var(--color-brand-sky)";

/** Funkcje — siatka bento. Kropka Apricot oznacza życie, Sky pracę. */
export function SekcjaFunkcje() {
  const [siatka, widoczne] = useWidocznosc<HTMLDivElement>();
  return (
    <Sekcja id="funkcje" className="landing-tlo" style={tlo("szklo-kafle", 0.6)}>
      <Naglowek
        nad="Funkcje"
        tytul="Do pracy i do życia. W jednej rozmowie."
        akapit={`Nexus ma ${LICZBA_NARZEDZI} narzędzi i sam wie, po które sięgnąć. Ty mówisz tylko, co ma powstać — resztę rozpisuje bez Ciebie.`}
      />
      <p className="mt-6 flex flex-wrap items-center gap-5 text-sm text-muted">
        <span className="inline-flex items-center gap-2">
          <span className="size-2.5 rounded-full" style={{ background: BARWA_ZYCIE }} /> Życie
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="size-2.5 rounded-full" style={{ background: BARWA_PRACA }} /> Praca
        </span>
      </p>
      <div ref={siatka} className="mt-12 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {KARTY.map((karta, indeks) => (
          <article
            key={karta.naglowek}
            className={`landing-karta ui-ujawnij flex flex-col p-6 ${karta.szeroka ? "xl:col-span-2" : ""}`}
            data-widoczny={widoczne ? "true" : "false"}
            style={kaskada(indeks)}
          >
            <span
              className="size-2.5 rounded-full"
              style={{ background: karta.rodzaj === "zycie" ? BARWA_ZYCIE : BARWA_PRACA }}
              aria-label={karta.rodzaj === "zycie" ? "Życie" : "Praca"}
            />
            <h3 className="mt-4 font-heading text-xl font-bold tracking-tight text-balance">{karta.naglowek}</h3>
            <p className="mt-2.5 leading-relaxed text-muted">{karta.opis}</p>
            <p className="mt-auto pt-5 font-mono text-xs text-subtle">{karta.narzedzia}</p>
          </article>
        ))}
      </div>
    </Sekcja>
  );
}

/** Kafel jednego filmu: plakat z zajawką w pętli, tytuł i zdanie opisu. */
function KafelFilmu({ film, onOtworz }: { film: FilmPromocyjny; onOtworz: () => void }) {
  return (
    <article className="overflow-hidden rounded-2xl border border-line bg-app shadow-[var(--shadow-floating)]">
      <button
        type="button"
        onClick={onOtworz}
        className="group relative block aspect-video w-full cursor-pointer"
        aria-label={`Odtwórz film „${film.tytul}” (60 sekund, lektor i napisy)`}
      >
        <video className="size-full object-cover" src={film.zajawka} poster={film.plakat} autoPlay muted loop playsInline aria-hidden="true" />
        <span className="absolute inset-0 grid place-items-center bg-scrim">
          <span className="aurora-tlo grid size-20 place-items-center rounded-full text-white shadow-[var(--shadow-glow-ai)] transition-transform group-hover:scale-105">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M8 5.5v13l11-6.5z" />
            </svg>
          </span>
        </span>
        <span className="absolute right-4 bottom-4 rounded-full bg-app/80 px-3 py-1 text-xs text-fg backdrop-blur">
          60 s · lektor PL · napisy PL i EN
        </span>
      </button>
      <div className="p-6">
        <h3 className="font-heading text-xl font-bold tracking-tight text-balance">{film.tytul}</h3>
        <p className="mt-2.5 leading-relaxed text-muted text-pretty">{film.opis}</p>
      </div>
    </article>
  );
}

/** Powiększenie wybranego filmu: odtwarzacz na przyciemnionym tle, zamykany Esc i tłem. */
function PowiekszenieFilmu({ film, onZamknij }: { film: FilmPromocyjny; onZamknij: () => void }) {
  useEffect(() => {
    const klawisz = (zdarzenie: KeyboardEvent) => {
      if (zdarzenie.key === "Escape") onZamknij();
    };
    document.addEventListener("keydown", klawisz);
    const poprzedni = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", klawisz);
      document.body.style.overflow = poprzedni;
    };
  }, [onZamknij]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Film „${film.tytul}”`}
      className="fixed inset-0 z-(--z-dialog) grid place-items-center bg-scrim p-4 backdrop-blur-sm md:p-10"
      onClick={onZamknij}
    >
      <div className="w-full max-w-(--container-page)" onClick={(zdarzenie) => zdarzenie.stopPropagation()}>
        <div className="flex items-center justify-between gap-4 pb-3">
          <h3 className="font-heading text-lg font-bold tracking-tight text-fg md:text-2xl">{film.tytul}</h3>
          <button
            type="button"
            autoFocus
            onClick={onZamknij}
            className="rounded-md border border-line-strong px-3 py-1.5 text-sm text-fg hover:bg-hover"
          >
            Zamknij
          </button>
        </div>
        <video
          className="aspect-video w-full overflow-hidden rounded-2xl border border-line bg-app shadow-[var(--shadow-floating)]"
          controls
          autoPlay
          preload="metadata"
          poster={film.plakat}
          crossOrigin="anonymous"
        >
          {film.zrodla.map((zrodlo) => (
            <source key={zrodlo.plik} src={zrodlo.plik} type={zrodlo.typ} />
          ))}
          {film.napisy.map((napis, indeks) => (
            <track key={napis.jezyk} kind="captions" srcLang={napis.jezyk} label={napis.etykieta} src={napis.plik} default={indeks === 0} />
          ))}
        </video>
      </div>
    </div>
  );
}

/** Dwa filmy promocyjne: zwykły dzień i dzień pracy. */
export function SekcjaFilmy() {
  const [otwarty, setOtwarty] = useState<FilmPromocyjny | null>(null);
  return (
    <Sekcja id="filmy" className="landing-tlo" style={tlo("aurora-mgla", 0.85)}>
      {/* Ziarno filmowe nad sekcją ze statyczną grafiką — tła na żywo mają je w złożeniu.
          Na czas odtwarzania gaśnie: film ma własne ziarno w materiale, a nakładanie
          drugiej warstwy brudzi obraz. */}
      <WarstwaZiarna ukryta={otwarty !== null} />
      <Naglowek
        nad="Filmy"
        tytul="Zobacz Nexusa w działaniu."
        akapit="Dwie minuty: pierwszy film o zwykłym dniu w domu, drugi o dniu pracy. Oba pokazują wyłącznie to, co Nexus potrafi dziś."
        srodek
      />
      <div className="mt-14 grid gap-8 md:grid-cols-2">
        {FILMY.map((film) => (
          <KafelFilmu key={film.id} film={film} onOtworz={() => setOtwarty(film)} />
        ))}
      </div>
      {otwarty && <PowiekszenieFilmu film={otwarty} onZamknij={() => setOtwarty(null)} />}
    </Sekcja>
  );
}

/** Ikony czterech gwarancji prywatności — kolejność jak w `GWARANCJE`. */
const IKONY_GWARANCJI = [
  <DocumentIcon key="pliki" size={20} />,
  <ToolIcon key="narzedzia" size={20} />,
  <ShieldIcon key="uprawnienia" size={20} />,
  <LockIcon key="logowanie" size={20} />,
];

/** Prywatność — „Pod dachem Danaco.” Schemat drogi danych i cztery gwarancje. */
export function SekcjaPrywatnosc() {
  return (
    <Sekcja id="prywatnosc" className="landing-tlo" style={tlo("noc-horyzont", 0.9)}>
      <Naglowek
        nad="Prywatność"
        tytul="Pod dachem Danaco."
        akapit="Każde konto dostaje własną przestrzeń w chmurze Nexusa — od 1 GB w planie Osobistym po 10 GB w Zespole. Leżą w niej Twoje pliki, historia rozmów, indeks wiedzy i wyniki pracy; widzisz je tylko Ty, bo każde konto jest oddzielone od pozostałych. Poza Twoją przestrzeń wychodzi wyłącznie to, czego wymaga bieżące zadanie."
      />
      <div className="mt-14 grid gap-8 lg:grid-cols-[1fr_1.1fr] lg:items-center">
        <div className="landing-karta p-8">
          <div className="flex justify-center gap-6 text-sm text-muted">
            <span className="inline-flex flex-col items-center gap-2">
              <PhoneIcon size={22} /> Telefon
            </span>
            <span className="inline-flex flex-col items-center gap-2">
              <WindowsIcon size={22} /> Komputer
            </span>
          </div>
          <p className="mt-3 text-center font-mono text-xs text-subtle">HTTPS</p>
          <div className="mt-3 rounded-lg border border-accent/40 bg-accent-soft/40 p-5">
            <p className="text-center font-heading text-lg font-bold">Serwer Danaco</p>
            <ul className="mt-4 grid grid-cols-2 gap-2 text-sm text-muted">
              {["Pliki i wyniki", "Historia rozmów", "Baza wiedzy", "Narzędzia", "Chmura osobista", "Sesje i hasła"].map((pozycja) => (
                <li key={pozycja} className="rounded-sm bg-app/60 px-2.5 py-1.5">
                  {pozycja}
                </li>
              ))}
            </ul>
          </div>
          <p className="mt-3 text-center font-mono text-xs text-subtle">tylko treść bieżącego zadania</p>
          <p className="mt-3 rounded-lg border border-dashed border-line-strong px-4 py-3 text-center text-sm">
            Silnik Nexusa · rozumowanie i plan
          </p>
        </div>
        <div className="grid gap-6 sm:grid-cols-2">
          {GWARANCJE.map(({ tytul, opis }, indeks) => (
            <div key={tytul}>
              {IKONY_GWARANCJI[indeks]}
              <h3 className="mt-3 font-semibold">{tytul}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{opis}</p>
            </div>
          ))}
        </div>
      </div>
    </Sekcja>
  );
}

/** Zaufanie — liczby sprawdzalne w aplikacji, bez opinii i logotypów klientów. */
export function SekcjaZaufanie() {
  const [liczby, widoczne] = useWidocznosc<HTMLDListElement>();
  return (
    <Sekcja id="zaufanie">
      <Naglowek
        nad="Zaufanie"
        tytul="Nexus jest nowy. Dlatego pokazuje fakty."
        akapit="Nie znajdziesz tu logotypów klientów ani zachwytów — jeszcze ich nie ma. Jest za to wszystko, co sprawdzisz sam w aplikacji."
        srodek
      />
      <dl ref={liczby} className="mt-14 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {LICZBY.map(({ liczba, podpis }, indeks) => (
          <div
            key={podpis}
            className="landing-karta ui-ujawnij p-7 text-center"
            data-widoczny={widoczne ? "true" : "false"}
            style={kaskada(indeks)}
          >
            <dt className="font-heading text-4xl font-bold tracking-tighter tabular-nums">{liczba}</dt>
            <dd className="mt-2 text-sm text-muted">{podpis}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {ZASADY.map(({ tytul, opis }) => (
          <div key={tytul} className="rounded-lg border border-line px-5 py-4">
            <h3 className="font-semibold">{tytul}</h3>
            <p className="mt-1 text-sm text-muted">{opis}</p>
          </div>
        ))}
      </div>
      <p className="mt-8 flex flex-wrap justify-center gap-x-4 gap-y-2 text-sm text-subtle">
        {TECHNOLOGIE.map((nazwa) => (
          <span key={nazwa}>{nazwa}</span>
        ))}
      </p>
    </Sekcja>
  );
}

/** Cennik — plan Osobisty dostępny, pozostałe bez ceny i bez daty. */
export function SekcjaCennik() {
  const [plany, widoczne] = useWidocznosc<HTMLDivElement>();
  return (
    <Sekcja id="cennik">
      <Naglowek nad="Cennik" tytul="Zacznij od 7 dni próbnych. Więcej — kiedy zechcesz." srodek />
      <div ref={plany} className="mt-14 grid gap-4 lg:grid-cols-3">
        {PLANY.map((plan, indeks) => (
          <article
            key={plan.nazwa}
            className={`landing-karta ui-ujawnij flex flex-col p-8 ${plan.dostepny ? "border-accent/50 shadow-[var(--shadow-glow-ai)]" : ""}`}
            data-widoczny={widoczne ? "true" : "false"}
            style={kaskada(indeks)}
          >
            <div className="flex items-center gap-3">
              <h3 className="font-heading text-2xl font-bold tracking-tight">{plan.nazwa}</h3>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  plan.dostepny ? "bg-success-soft text-success" : "bg-hover text-muted"
                }`}
              >
                {plan.znacznik}
              </span>
            </div>
            <p className="mt-3 text-sm text-muted">{plan.dlaKogo}</p>
            <p className="mt-6 font-heading text-3xl font-bold tracking-tighter">{plan.cena}</p>
            <ul className="mt-6 flex-1 space-y-2.5 text-sm">
              {plan.zawartosc.map((pozycja) => (
                <li key={pozycja} className="flex gap-2.5">
                  <CheckIcon size={16} className="mt-0.5 shrink-0 text-accent" />
                  <span>{pozycja}</span>
                </li>
              ))}
            </ul>
            <a
              href={plan.dostepny ? "#instalacja" : "mailto:support@danaco-group.pl?subject=Powiadom%20mnie%20o%20planie%20" + plan.nazwa}
              className={`ui-nacisk mt-8 inline-flex h-11 items-center justify-center rounded-full px-5 font-medium transition-colors ${
                plan.dostepny
                  ? "bg-accent-fill text-on-accent hover:bg-accent-fill-hover"
                  : "border border-line-strong hover:bg-hover"
              }`}
            >
              {plan.przycisk}
            </a>
          </article>
        ))}
      </div>
    </Sekcja>
  );
}

/** Pytania — otwarte jest jedno naraz (`name` na elemencie `details`). */
export function SekcjaPytania() {
  return (
    <Sekcja id="pytania">
      <div className="grid gap-10 lg:grid-cols-[1fr_1.6fr]">
        <div className="lg:sticky lg:top-28 lg:self-start">
          <Naglowek nad="Pytania" tytul="Najczęstsze pytania." />
        </div>
        <div className="divide-y divide-line border-y border-line">
          {PYTANIA.map(({ pytanie, odpowiedz }) => (
            <details key={pytanie} name="pytania" className="group py-5">
              <summary className="flex cursor-pointer list-none items-start gap-4 font-medium [&::-webkit-details-marker]:hidden">
                <span className="flex-1">{pytanie}</span>
                <PlusIcon size={18} className="mt-0.5 shrink-0 text-muted transition-transform group-open:rotate-45" />
              </summary>
              <p className="mt-3 pr-8 leading-relaxed text-muted">{odpowiedz}</p>
            </details>
          ))}
        </div>
      </div>
    </Sekcja>
  );
}

export function Brama({ instaluj }: { instaluj: ReactNode }) {
  return (
    <Sekcja className="landing-tlo text-center">
      {/* Brama do własnej przestrzeni: łuk na żywo zamiast klatki, z klatką pod spodem. */}
      <TloNaZywo nazwa="luk" opcje={{ intensywnosc: 0.8 }} />
      <div className="py-12 md:py-20" />
      <h2 className="font-heading text-4xl leading-tight font-bold tracking-tighter text-balance md:text-6xl">
        Twoja AI. Zawsze pod ręką.
      </h2>
      <p className="mx-auto mt-5 max-w-(--container-prose) text-lg text-muted text-pretty">
        Plan Osobisty zaczyna się od 7 dni próbnych. Instalacja zajmuje kilka sekund i nie wymaga sklepu z aplikacjami.
      </p>
      <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
        {instaluj}
        <a
          href="/zaloguj"
          className="ui-nacisk inline-flex h-12 w-full items-center justify-center gap-2 rounded-full border border-line-strong px-6 font-medium transition-colors hover:bg-hover sm:w-auto"
        >
          Zaloguj się <ArrowRightIcon size={18} />
        </a>
      </div>
      <div className="py-12 md:py-20" />
    </Sekcja>
  );
}

/** Odsyłacze i ikony sekcji używane w nawigacji strony. */
export const SEKCJE_NAWIGACJI = [
  { id: "jak-dziala", etykieta: "Jak działa" },
  { id: "funkcje", etykieta: "Funkcje" },
  { id: "prywatnosc", etykieta: "Prywatność" },
  { id: "instalacja", etykieta: "Instalacja" },
  { id: "cennik", etykieta: "Cennik" },
  { id: "pytania", etykieta: "Pytania" },
];

/** Która sekcja jest teraz czytana — do `aria-current` w nawigacji. */
export function useAktywnaSekcja(): string {
  const [aktywna, setAktywna] = useState("");
  const stan = useRef<Record<string, number>>({});
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const obserwator = new IntersectionObserver(
      (wpisy) => {
        for (const wpis of wpisy) stan.current[wpis.target.id] = wpis.isIntersecting ? wpis.intersectionRatio : 0;
        const najlepsza = Object.entries(stan.current).sort((a, b) => b[1] - a[1])[0];
        setAktywna(najlepsza && najlepsza[1] > 0 ? najlepsza[0] : "");
      },
      { threshold: [0, 0.25, 0.5], rootMargin: "-20% 0px -60% 0px" },
    );
    for (const { id } of SEKCJE_NAWIGACJI) {
      const element = document.getElementById(id);
      if (element) obserwator.observe(element);
    }
    return () => obserwator.disconnect();
  }, []);
  return aktywna;
}

