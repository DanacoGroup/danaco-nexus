// Publiczna strona produktu Danaco Nexus (dla gościa niezalogowanego).
// Treść, układ i ruch: landing/LANDING_PAGE_SPEC.md. Wartości wizualne: design-tokens.

import { Fragment, useEffect, useState } from "react";
import { Logo, Logotype } from "../components/icons";
import { ArrowRightIcon } from "../shell/icons";
import { ScenaHero } from "./ScenaHero";
import { InstallSection, PrzyciskInstalacji } from "./InstallSection";
import {
  Brama,
  PasekZdan,
  SEKCJE_NAWIGACJI,
  SekcjaCennik,
  SekcjaFilmy,
  SekcjaFunkcje,
  SekcjaKroki,
  SekcjaPrywatnosc,
  SekcjaPytania,
  SekcjaRoznice,
  SekcjaRuch,
  SekcjaZaufanie,
  useAktywnaSekcja,
} from "./sekcje";
import { SekcjaNarzedzi } from "./SekcjaNarzedzi";
import { sciezka } from "../portal/trasy";
import { HERO_FAKTY, PYTANIA } from "./tresc";
import { PASMO } from "./uzyj";
import { PasSwitu, TloNaZywo, useOtwarcie, useWidocznosc } from "../ruch";

const STOPKA = [
  {
    tytul: "Produkt",
    pozycje: [
      { etykieta: "Funkcje", adres: "#funkcje" },
      { etykieta: "Jak działa", adres: "#jak-dziala" },
      { etykieta: "Instalacja", adres: "#instalacja" },
      { etykieta: "Cennik", adres: "#cennik" },
      { etykieta: "Wejdź bez rejestracji", adres: "/wyprobuj" },
      { etykieta: "Oferta", adres: "/portal/oferta" },
    ],
  },
  {
    tytul: "Zasoby",
    pozycje: [
      { etykieta: "Dokumentacja", adres: "/portal/dokumentacja" },
      { etykieta: "Centrum wiedzy", adres: "/portal/wiedza" },
      { etykieta: "Blog", adres: "/portal/blog" },
      { etykieta: "Pytania", adres: "#pytania" },
      { etykieta: "Pomoc", adres: "mailto:support@danaco-group.pl" },
    ],
  },
  {
    tytul: "Firma",
    pozycje: [
      { etykieta: "Danaco Group", adres: "https://danaco-group.pl" },
      { etykieta: "Kontakt", adres: "mailto:support@danaco-group.pl" },
    ],
  },
];

/**
 * Dokumenty, do których gość musi trafić z każdej strony: polityka prywatności (RODO, art. 13),
 * regulamin i informacja o plikach cookie. Adresy z trasownika portalu, żeby zmiana ścieżki
 * strony nie zostawiła w stopce martwego odsyłacza.
 */
export const ODSYLACZE_PRAWNE = [
  { etykieta: "Polityka prywatności", adres: sciezka("prywatnosc") },
  { etykieta: "Regulamin", adres: sciezka("regulamin") },
  { etykieta: "Pliki cookie", adres: sciezka("cookies") },
];

/** Opóźnienie wejścia liczone w krokach tokenu `--stagger-step` (żadnych wartości czasu w kodzie). */
function opoznienieKroku(kroki: number): string {
  return `calc(var(--krok-wejscia, var(--stagger-step)) * ${kroki})`;
}

/** Nagłówek wchodzący słowo po słowie — kaskada co jeden krok (LANDING_PAGE_SPEC, rozdz. 7.2). */
function Kaskada({ tekst, krok, className = "" }: { tekst: string; krok: number; className?: string }) {
  const slowa = tekst.split(" ");
  return (
    <>
      {slowa.map((slowo, indeks) => (
        // Odstęp stoi poza maską — `overflow: hidden` zjadłby spację na końcu słowa.
        <Fragment key={`${slowo}-${indeks}`}>
          <span className="maska-slowa">
            <span
              className={`wejscie-slowo ${className}`}
              style={
                {
                  "--opoznienie": opoznienieKroku(krok + indeks),
                } as React.CSSProperties
              }
            >
              {slowo}
            </span>
          </span>
          {indeks < slowa.length - 1 ? " " : null}
        </Fragment>
      ))}
    </>
  );
}

/** Łuk znaku w skali hero: rysuje się przy wejściu, punkt opada i oddycha. */
function LukHero() {
  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 mx-auto w-full max-w-5xl">
      {/* Cel przelotu ekranu ładowania: łuk znaku dolatuje dokładnie w ten łuk i przestaje
        być znakiem, a staje się łukiem nagłówka. Znacznik jest osobnym, pustym prostokątem,
        bo skrypt planszy mierzy sam prostokąt — a prostokąt samego <svg> jest szerszy niż
        łuk w środku (łuk zajmuje 40…360 z 400 jednostek kadru) i przelot kończyłby się
        łukiem o kilkanaście procent za szerokim. Skrypt planszy rysuje łuk kołowy, więc
        prostokąt opisuje koło tego łuku w kadrze 400 × 260: środek 200, promień 160
        (wierzchołek na 40, podstawy na 40 i 360), podstawa 260. */}
      <div
        data-dn-brama
        aria-hidden="true"
        className="pointer-events-none absolute"
        style={{ left: "10%", width: "80%", top: "15.385%", height: "84.615%" }}
      />
      <svg className="pointer-events-none block w-full opacity-70" viewBox="0 0 400 260" fill="none" aria-hidden="true">
        <defs>
          <linearGradient id="hero-aurora" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" stopColor="var(--color-brand-apricot)" />
            <stop offset="0.38" stopColor="var(--color-brand-rose)" />
            <stop offset="0.72" stopColor="var(--color-brand-iris)" />
            <stop offset="1" stopColor="var(--color-brand-sky)" />
          </linearGradient>
          <mask id="hero-wygaszenie">
            <rect width="400" height="260" fill="url(#hero-zanik)" />
          </mask>
          <linearGradient id="hero-zanik" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="white" />
            <stop offset="1" stopColor="black" />
          </linearGradient>
        </defs>
        <g mask="url(#hero-wygaszenie)">
          <path
            className="luk-rysuje"
            d="M40 260V150a160 110 0 0 1 320 0v110"
            stroke="url(#hero-aurora)"
            strokeWidth="1.6"
            strokeLinecap="round"
            pathLength={1}
            style={{ strokeDasharray: 1 }}
          />
        </g>
        <circle className="punkt-opada" cx="200" cy="40" r="5" fill="url(#hero-aurora)" />
      </svg>
    </div>
  );
}

/** Dane strukturalne pytań i odpowiedzi (schema.org FAQPage) — LANDING_PAGE_SPEC, rozdz. 13. */
function DanePytan() {
  const dane = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: PYTANIA.map(({ pytanie, odpowiedz }) => ({
      "@type": "Question",
      name: pytanie,
      acceptedAnswer: { "@type": "Answer", text: odpowiedz },
    })),
  };
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(dane) }} />;
}

/** Menu na telefon: cała nawigacja paska w rozwijanym panelu.
 *
 * Pasek chował wszystkie odsyłacze poniżej `lg`, a „Zaloguj się” poniżej `sm` — na telefonie
 * zostawał sam przycisk instalacji. Do cennika, pytań czy logowania trzeba było przewinąć
 * dwadzieścia parę tysięcy pikseli do stopki. Tu te same pozycje są jedno stuknięcie dalej.
 */
export function MenuMobilne({ aktywna }: { aktywna: string }) {
  const [otwarte, setOtwarte] = useState(false);

  useEffect(() => {
    if (!otwarte) return;
    const klawisz = (zdarzenie: KeyboardEvent) => {
      if (zdarzenie.key === "Escape") setOtwarte(false);
    };
    window.addEventListener("keydown", klawisz);
    return () => window.removeEventListener("keydown", klawisz);
  }, [otwarte]);

  const pozycja =
    "flex h-11 items-center rounded-xl px-3 text-base text-muted transition-colors hover:bg-raised hover:text-fg aria-[current]:bg-raised aria-[current]:text-fg";

  return (
    <div className="lg:hidden">
      <button
        type="button"
        onClick={() => setOtwarte((stan) => !stan)}
        aria-expanded={otwarte}
        aria-controls="menu-strony"
        aria-label={otwarte ? "Zamknij menu" : "Otwórz menu"}
        className="grid size-9 place-items-center rounded-full text-muted transition-colors hover:bg-raised hover:text-fg"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.75}
          strokeLinecap="round"
          aria-hidden="true"
        >
          {otwarte ? <path d="m6 6 12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
        </svg>
      </button>
      {otwarte && (
        <div
          id="menu-strony"
          className="safe-top fixed inset-x-0 top-16 z-(--z-sticky) max-h-[calc(100dvh-4rem)] overflow-y-auto border-b border-line bg-glass px-4 pb-6 backdrop-blur-xl"
        >
          <nav className="flex flex-col gap-0.5 pt-2" aria-label="Sekcje strony">
            {SEKCJE_NAWIGACJI.map(({ id, etykieta }) => (
              <a
                key={id}
                href={`#${id}`}
                onClick={() => setOtwarte(false)}
                aria-current={aktywna === id ? "true" : undefined}
                className={pozycja}
              >
                {etykieta}
              </a>
            ))}
          </nav>
          <div className="mt-4 flex flex-col gap-2 border-t border-line pt-4">
            <a
              href="/wyprobuj"
              className="flex h-11 items-center justify-center rounded-full border border-line text-sm font-medium text-fg transition-colors hover:bg-raised"
            >
              Wypróbuj bez rejestracji
            </a>
            <a
              href="/zaloguj"
              className="flex h-11 items-center justify-center rounded-full text-sm font-medium text-muted transition-colors hover:text-fg"
            >
              Zaloguj się
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

/** Pasek nawigacji: przezroczysty nad hero, szklany po przewinięciu. */
function Nawigacja() {
  const [szklo, setSzklo] = useState(false);
  const aktywna = useAktywnaSekcja();
  useEffect(() => {
    const przewin = () => setSzklo(window.scrollY > 24);
    przewin();
    window.addEventListener("scroll", przewin, { passive: true });
    return () => window.removeEventListener("scroll", przewin);
  }, []);
  return (
    <header
      className={`safe-top fixed inset-x-0 top-0 z-(--z-sticky) transition-colors duration-(--duration-base) ${
        szklo ? "border-b border-line bg-glass backdrop-blur-xl" : "border-b border-transparent"
      }`}
    >
      <div className={`${PASMO} flex h-16 items-center gap-6`}>
        <a href="#top" className="flex items-center" aria-label="Danaco Nexus — początek strony">
          <Logotype height={24} />
        </a>
        <nav className="hidden items-center gap-6 text-sm text-muted lg:flex" aria-label="Sekcje strony">
          {SEKCJE_NAWIGACJI.map(({ id, etykieta }) => (
            <a
              key={id}
              href={`#${id}`}
              aria-current={aktywna === id ? "true" : undefined}
              className="transition-colors hover:text-fg aria-[current]:text-fg"
            >
              {etykieta}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <a
            href="/wyprobuj"
            className="hidden h-9 items-center rounded-full px-4 text-sm font-medium text-muted transition-colors hover:text-fg lg:inline-flex"
          >
            Wypróbuj
          </a>
          <a
            href="/zaloguj"
            className="hidden h-9 items-center rounded-full px-4 text-sm font-medium text-muted transition-colors hover:text-fg sm:inline-flex"
          >
            Zaloguj się
          </a>
          <PrzyciskInstalacji rozmiar="maly" />
          <MenuMobilne aktywna={aktywna} />
        </div>
      </div>
    </header>
  );
}

function Hero() {
  // Ruch ozdobny hero (oddech punktu, płótno Aurory) stoi, gdy sekcja zejdzie z ekranu.
  const [sekcja, widoczna] = useWidocznosc<HTMLElement>({
    margines: "200px",
    ciagla: true,
  });
  return (
    <section
      id="top"
      ref={sekcja}
      data-widoczny={widoczna ? "true" : "false"}
      className="landing-tlo hero-tlo hero-wejscie relative pt-36 pb-24 md:pt-48 md:pb-32"
    >
      {/* Zorza gra pełnym światłem; kontrast tekstu trzyma własna poświata kolumny treści
          (`.hero-tresc`), a nie przygaszanie całego tła. Wcześniej cały pierwszy ekran był
          ściemniony po to, żeby akapit spełnił próg WCAG — kosztem pierwszego wrażenia. */}
      <TloNaZywo nazwa="aurora" hero opcje={{ maska: "obie", intensywnosc: 0.9, wstega: 0.75 }} />
      <LukHero />
      <div className={`${PASMO} hero-tresc text-center`}>
        <a
          href="#funkcje"
          className="wejscie inline-flex items-center gap-2 rounded-full border border-line bg-raised/60 px-3.5 py-1.5 text-sm text-muted backdrop-blur transition-colors hover:text-fg"
        >
          <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent">Nowość</span>
          Rozmowa głosowa po polsku
          <ArrowRightIcon size={14} />
        </a>
        <h1 className="mt-8 font-heading text-[clamp(2.5rem,7vw,5.5rem)] leading-[1.02] font-bold tracking-tighter text-balance">
          <Kaskada tekst="Powiedz, co zrobić." krok={1} /> <Kaskada tekst="Odbierz gotowe." krok={4} className="aurora-tekst" />
        </h1>
        <p
          className="wejscie mx-auto mt-7 max-w-(--container-prose) text-lg leading-relaxed text-muted text-pretty"
          style={{ "--opoznienie": opoznienieKroku(6) } as React.CSSProperties}
        >
          {/* Na telefonie pełne wyliczenie zajmowało dziewięć wierszy i spychało przyciski
            poniżej ekranu — zostaje zdanie, które mówi to samo. Pełną listę zastosowań
            widać w sekcji „Funkcje” i na wąskim ekranie nie musi stać w nagłówku. */}
          <span className="hidden sm:inline">
            Zaprojektuj logo i plakat do druku. Zbadaj temat i dostań raport z przypisami. Odpisz na zaległą pocztę i umów spotkanie.
            Opublikuj stronę pod adresem Nexusa. Znajdź plik na własnym komputerze.{" "}
          </span>
          Piszesz albo mówisz jednym zdaniem, co ma powstać — Nexus sam dobiera narzędzia, wykonuje pracę i oddaje gotowy plik do Twojej
          przestrzeni w chmurze.
        </p>
        <div
          className="wejscie mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row"
          style={{ "--opoznienie": opoznienieKroku(7) } as React.CSSProperties}
        >
          <PrzyciskInstalacji />
          <a
            href="/zaloguj"
            className="ui-nacisk inline-flex h-12 w-full items-center justify-center gap-2 rounded-full border border-line-strong px-6 font-medium transition-colors hover:bg-hover sm:w-auto"
          >
            Zaloguj się
          </a>
        </div>
        <p className="mt-5 text-sm text-muted">
          Bez sklepu z aplikacjami · działa też w przeglądarce ·{" "}
          <a href="#jak-dziala" className="text-accent underline-offset-4 hover:underline">
            Zobacz, jak działa
          </a>
        </p>
        <p className="mt-3 text-sm">
          <a href="/wyprobuj" className="text-accent underline-offset-4 hover:underline">
            Wejdź bez rejestracji
          </a>{" "}
          <span className="text-subtle">— otwiera się pełna aplikacja na koncie próbnym</span>
        </p>
        <ul
          className="wejscie mx-auto mt-10 flex max-w-3xl flex-wrap items-center justify-center gap-x-3 gap-y-2 text-sm text-subtle"
          style={{ "--opoznienie": opoznienieKroku(8) } as React.CSSProperties}
        >
          {HERO_FAKTY.map((fakt) => (
            <li key={fakt} className="rounded-full border border-line-strong bg-raised/50 px-3 py-1 backdrop-blur">
              {fakt}
            </li>
          ))}
        </ul>
      </div>
      <div className="wejscie mt-16 md:mt-20" style={{ "--opoznienie": opoznienieKroku(9) } as React.CSSProperties}>
        <ScenaHero />
      </div>
    </section>
  );
}

function Stopka() {
  return (
    <footer className="safe-bottom border-t border-line pt-16 pb-10">
      <div className={`${PASMO} grid gap-10 md:grid-cols-[1.4fr_repeat(3,1fr)]`}>
        <div>
          <Logotype height={24} />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
            Osobisty asystent AI w chmurze. Mówisz, co ma powstać — odbierasz gotowy plik.
          </p>
        </div>
        {STOPKA.map(({ tytul, pozycje }) => (
          <nav key={tytul} aria-label={tytul}>
            <h2 className="font-heading text-sm font-semibold">{tytul}</h2>
            <ul className="mt-4 space-y-2.5 text-sm text-muted">
              {pozycje.map(({ etykieta, adres }) => (
                <li key={etykieta}>
                  <a href={adres} className="transition-colors hover:text-fg">
                    {etykieta}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      {/* Kreska idzie po krawędzi treści, nie po krawędzi pasma.
        `PASMO` ma własne odstępy boczne, więc obramowanie postawione na nim samym
        wychodziło o te odstępy poza tekst z obu stron — linia była szersza niż to,
        co rozdziela, i nie trzymała się kolumn wyżej. */}
      <div className={PASMO}>
        <div className="mt-12 flex flex-col items-center gap-3 border-t border-line pt-6 text-sm text-subtle sm:flex-row">
          <Logo size={20} />
          <span>© {new Date().getFullYear()} Danaco Holding Group Sp. z o.o.</span>
          <nav aria-label="Dokumenty" className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 sm:ml-auto">
            {ODSYLACZE_PRAWNE.map(({ etykieta, adres }) => (
              <a key={adres} href={adres} className="transition-colors hover:text-fg">
                {etykieta}
              </a>
            ))}
          </nav>
          <span>Kontakt: support@danaco-group.pl</span>
        </div>
      </div>
    </footer>
  );
}

export function Landing() {
  // Wejście strony czeka na planszę otwarcia (ekran ładowania marki). Stan ustalamy przy
  // pierwszym rysowaniu, bo później byłoby za późno — kaskada nagłówka ruszyłaby pod zasłoną.
  const otwarcieTrwa = useOtwarcie();
  return (
    <div className="landing min-h-full overflow-x-hidden bg-app text-fg" data-otwarcie={otwarcieTrwa ? "gra" : "po"}>
      <a
        href="#tresc"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-(--z-toast) focus:rounded-md focus:bg-accent-fill focus:px-4 focus:py-2 focus:text-on-accent"
      >
        Przejdź do treści
      </a>
      <DanePytan />
      <Nawigacja />
      <main id="tresc">
        <Hero />
        <PasekZdan />
        <SekcjaKroki />
        <SekcjaFunkcje />
        <SekcjaNarzedzi />
        <SekcjaRoznice />
        <SekcjaRuch />
        <SekcjaFilmy />
        {/* Świt prowadzi z dnia w noc prywatności — kolory obu sekcji, wschód sprzężony z przewijaniem. */}
        <PasSwitu barwa="chlodny" od="var(--app)" do="var(--app)" />
        <SekcjaPrywatnosc />
        <InstallSection />
        <SekcjaZaufanie />
        <SekcjaCennik />
        <SekcjaPytania />
        <Brama instaluj={<PrzyciskInstalacji />} />
      </main>
      <Stopka />
    </div>
  );
}
