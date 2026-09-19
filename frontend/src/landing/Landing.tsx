// Publiczna strona startowa Danaco Nexus (dla niezalogowanych): możliwości, urządzenia, instalacja.

import type { ComponentType } from "react";
import { CloudIcon, Logo, WaveIcon } from "../components/icons";
import {
  AgentsIcon,
  ArrowRightIcon,
  CodeIcon,
  DocumentIcon,
  FilmIcon,
  ImageIcon,
  LanguageIcon,
  LayersIcon,
  LayoutIcon,
  LockIcon,
  MailIcon,
  PhoneIcon,
  PuzzleIcon,
  ScanIcon,
  SearchIcon,
  ShieldIcon,
  WindowsIcon,
  type IconProps,
} from "../shell/icons";
import { HeroMock } from "./HeroMock";
import { InstallSection } from "./InstallSection";

interface Feature {
  icon: ComponentType<IconProps>;
  title: string;
  text: string;
}

export const FEATURES: Feature[] = [
  { icon: DocumentIcon, title: "Dokumenty i PDF", text: "Dzielenie, łączenie i konwersje DOCX, XLSX, PDF. Pisma i raporty gotowe do wysłania." },
  { icon: ScanIcon, title: "OCR i skany", text: "Przeszukiwalne PDF ze skanów, prostowanie i czyszczenie stron, tekst z każdego obrazu." },
  { icon: ImageIcon, title: "Zdjęcia", text: "Retusz, powiększanie AI, zmiana i usuwanie tła, konwersje formatów bez utraty jakości." },
  { icon: FilmIcon, title: "Audio i wideo", text: "Transkrypcja z napisami, wycinanie, kompresja i wyrównanie głośności nagrań." },
  { icon: WaveIcon, title: "Rozmowa głosowa", text: "Rozmawiaj naturalnie – realistyczne głosy, przerywanie w pół zdania, praca w tle." },
  { icon: CloudIcon, title: "Cloud", text: "Własna chmura w aplikacji: foldery, wersje plików, udostępnianie i synchronizacja." },
  { icon: SearchIcon, title: "Deep Research", text: "Wieloetapowe badanie sieci i źródeł naukowych zakończone raportem z cytatami." },
  { icon: LayoutIcon, title: "Twórca stron", text: "Opisz stronę, oglądaj podgląd na żywo i opublikuj ją jednym kliknięciem." },
  { icon: CodeIcon, title: "Kod", text: "Sesje programistyczne z Claude Code: projekty, podgląd plików, zmiany i git." },
  { icon: AgentsIcon, title: "Agenci", text: "Orkiestracja wielu agentów – część pracuje równolegle, część po kolei, wszystko w tle." },
  { icon: MailIcon, title: "Poczta i kalendarz", text: "Czytanie poczty, szkice odpowiedzi i terminy – wysyłka zawsze po Twoim potwierdzeniu." },
  { icon: LanguageIcon, title: "Tłumacz", text: "Teksty, dokumenty i PDF przetłumaczone z zachowaniem oryginalnego układu." },
];

const PLACES = [
  {
    icon: PuzzleIcon,
    title: "W przeglądarce",
    lead: "Panel boczny na każdej stronie",
    points: [
      "Streszczenie i recenzja bieżącej strony",
      "Odpowiedzi na opinie w Booking i Google – jednym „Wstaw”",
      "Tłumaczenie i poprawa zaznaczonego tekstu",
    ],
  },
  {
    icon: WindowsIcon,
    title: "Na komputerze",
    lead: "Języczek przy krawędzi ekranu",
    points: [
      "Pomoc w każdym programie na podstawie zrzutu okna",
      "Wyszukiwanie plików na dysku",
      "Diagnostyka, sprzątanie i naprawy przez PowerShell – po Twojej zgodzie",
    ],
  },
  {
    icon: PhoneIcon,
    title: "Na telefonie",
    lead: "Asystent zawsze pod ręką",
    points: [
      "Rozmowy głosowe także przy zablokowanym ekranie",
      "Szkice odpowiedzi na SMS, poczta i kalendarz",
      "Udostępnianie zdjęć i plików prosto do Nexusa",
    ],
  },
];

const TASKS = [
  { title: "Raport z faktur Q3", step: "Odczyt 48 faktur", progress: 72 },
  { title: "Research: rynek najmu w Gdańsku", step: "Agent 3 z 5 · źródła", progress: 45 },
  { title: "Strona dla pensjonatu", step: "Podgląd gotowy", progress: 90 },
  { title: "Montaż wywiadu", step: "Transkrypcja", progress: 30 },
];

function Nav() {
  return (
    <header className="safe-top fixed inset-x-0 top-0 z-40 border-b border-white/5 bg-[#0d0d10]/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-5">
        <a href="/" className="flex items-center gap-2.5" aria-label="Danaco Nexus – strona główna">
          <Logo size={30} className="rounded-lg" />
          <span className="text-[15px] font-semibold tracking-tight">Danaco Nexus</span>
        </a>
        <nav className="hidden items-center gap-6 text-sm text-muted md:flex" aria-label="Sekcje strony">
          <a className="transition-colors hover:text-fg" href="#mozliwosci">
            Możliwości
          </a>
          <a className="transition-colors hover:text-fg" href="#wszedzie">
            Urządzenia
          </a>
          <a className="transition-colors hover:text-fg" href="#prywatnosc">
            Prywatność
          </a>
          <a className="transition-colors hover:text-fg" href="#instalacja">
            Zainstaluj
          </a>
        </nav>
        <a
          href="/zaloguj"
          className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-fg px-4 py-2 text-sm font-medium text-app transition-opacity hover:opacity-90"
        >
          Zaloguj się
        </a>
      </div>
    </header>
  );
}

export function Landing() {
  return (
    <div className="dark landing min-h-full overflow-x-hidden bg-[#0d0d10] text-fg">
      <Nav />
      <main>
        {/* Hero */}
        <section className="landing-grid relative px-5 pt-32 pb-28 md:pt-40 md:pb-36">
          <div className="mx-auto max-w-4xl text-center">
            <a
              href="#mozliwosci"
              className="inline-flex animate-rise items-center gap-2 rounded-full border border-line bg-raised/60 px-3.5 py-1.5 text-xs text-muted backdrop-blur transition-colors hover:text-fg"
            >
              <span className="size-1.5 rounded-full bg-accent shadow-[0_0_8px_var(--accent)]" />
              Prywatny asystent AI · napędzany przez Claude
            </a>
            <h1 className="mt-7 text-[40px] leading-[1.05] font-semibold tracking-[-0.035em] text-balance md:text-7xl">
              Twój asystent AI.
              <br />
              <span className="landing-gradient-text">Na każdym ekranie.</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-[17px] leading-relaxed text-muted text-pretty md:text-lg">
              Danaco Nexus czyta dokumenty, poprawia zdjęcia, robi OCR, montuje audio i wideo, prowadzi badania, pisze kod
              i strony. Automatyzuje pracę w przeglądarce, na Windows i na telefonie – na Twoim własnym serwerze.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <a
                href="/zaloguj"
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-accent px-6 py-3 font-medium text-on-accent shadow-lg shadow-accent/30 transition-colors hover:bg-accent-hover sm:w-auto"
              >
                Zaloguj się <ArrowRightIcon size={18} />
              </a>
              <a
                href="#instalacja"
                className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-line-strong px-6 py-3 font-medium transition-colors hover:bg-hover sm:w-auto"
              >
                Zainstaluj aplikację
              </a>
            </div>
            <p className="mt-5 text-xs text-muted">Android · Windows · Chrome, Edge i Danaco Lynx · iPhone (PWA)</p>
          </div>
          <div className="mt-16 md:mt-20">
            <HeroMock />
          </div>
        </section>

        {/* Możliwości */}
        <section id="mozliwosci" className="scroll-mt-20 px-5 py-20 md:py-28">
          <div className="mx-auto max-w-6xl">
            <div className="max-w-2xl">
              <p className="text-sm font-medium text-accent">Możliwości</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">Jeden asystent zamiast dziesięciu programów</h2>
              <p className="mt-3 text-muted">
                Opisz zadanie i dodaj pliki. Nexus sam dobiera narzędzia serwera, wykonuje pracę i oddaje gotowy wynik do
                pobrania.
              </p>
            </div>
            <div className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {FEATURES.map(({ icon: FeatureIcon, title, text }) => (
                <article key={title} className="landing-card group rounded-2xl p-5">
                  <span className="grid size-10 place-items-center rounded-xl bg-accent-soft text-accent transition-transform group-hover:scale-105">
                    <FeatureIcon size={20} />
                  </span>
                  <h3 className="mt-4 font-semibold tracking-tight">{title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Wszędzie, gdzie pracujesz */}
        <section id="wszedzie" className="scroll-mt-20 px-5 py-20 md:py-28">
          <div className="mx-auto max-w-6xl">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-medium text-accent">Wszędzie, gdzie pracujesz</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">Pomaga tam, gdzie akurat jesteś</h2>
              <p className="mt-3 text-muted">
                Ta sama pamięć, te same rozmowy i pliki – w przeglądarce, na komputerze i w telefonie.
              </p>
            </div>
            <div className="mt-12 grid gap-4 lg:grid-cols-3">
              {PLACES.map(({ icon: PlaceIcon, title, lead, points }) => (
                <article key={title} className="landing-card rounded-3xl p-7">
                  <PlaceIcon size={26} className="text-accent" />
                  <h3 className="mt-5 text-xl font-semibold tracking-tight">{title}</h3>
                  <p className="text-sm text-muted">{lead}</p>
                  <ul className="mt-5 space-y-2.5 text-sm">
                    {points.map((point) => (
                      <li key={point} className="flex gap-2.5">
                        <span className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" />
                        <span className="text-fg/90">{point}</span>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Wiele zadań naraz */}
        <section className="px-5 py-20 md:py-28">
          <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
            <div>
              <p className="text-sm font-medium text-accent">Wiele sesji naraz</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">Zleć zadanie i wróć, gdy będzie gotowe</h2>
              <p className="mt-4 leading-relaxed text-muted">
                Kilka rozmów pracuje równolegle w tle. Panel „Zadania w toku” pokazuje postęp każdej z nich, a
                powiadomienie na telefonie i komputerze da znać, gdy wynik czeka. Złożone zadania Nexus rozdziela między
                wielu agentów – część działa równolegle, część po kolei.
              </p>
              <div className="mt-6 flex flex-wrap gap-2 text-xs text-muted">
                {["Powiadomienia push", "Anulowanie jednym kliknięciem", "Orkiestracja agentów", "Historia i pliki w jednym miejscu"].map(
                  (label) => (
                    <span key={label} className="rounded-full border border-line px-3 py-1">
                      {label}
                    </span>
                  ),
                )}
              </div>
            </div>
            <div className="landing-card rounded-3xl p-5 md:p-6" aria-hidden="true">
              <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
                <LayersIcon size={18} className="text-accent" /> Zadania w toku
                <span className="ml-auto rounded-full bg-accent-soft px-2 py-0.5 text-xs text-accent">4</span>
              </div>
              <ul className="space-y-2.5">
                {TASKS.map((task) => (
                  <li key={task.title} className="rounded-2xl border border-line bg-app/60 px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <span className="spinner size-3.5 text-accent" />
                      <span className="truncate text-sm font-medium">{task.title}</span>
                      <span className="ml-auto shrink-0 text-xs text-muted">{task.step}</span>
                    </div>
                    <div className="mt-2.5 h-1 overflow-hidden rounded-full bg-line">
                      <div className="h-full rounded-full bg-accent" style={{ width: `${task.progress}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* Prywatność */}
        <section id="prywatnosc" className="scroll-mt-20 px-5 py-20 md:py-28">
          <div className="landing-card mx-auto max-w-6xl rounded-[32px] p-8 md:p-14">
            <div className="grid gap-10 lg:grid-cols-[1.1fr_2fr]">
              <div>
                <ShieldIcon size={30} className="text-accent" />
                <h2 className="mt-4 text-3xl font-semibold tracking-tight">Twoje dane zostają u Ciebie</h2>
                <p className="mt-3 text-muted">Nexus działa na prywatnym serwerze Danaco – nie w cudzej chmurze.</p>
              </div>
              <div className="grid gap-6 sm:grid-cols-3">
                {[
                  { icon: LockIcon, title: "Własny serwer", text: "Rozmowy, pliki i baza wiedzy są przechowywane na Twoim serwerze." },
                  {
                    icon: ShieldIcon,
                    title: "Zgoda przed działaniem",
                    text: "Wysłanie wiadomości, publikacja czy zmiana w systemie – zawsze po Twoim potwierdzeniu.",
                  },
                  { icon: PhoneIcon, title: "Klucze urządzeń", text: "Każde urządzenie ma własny klucz, który cofniesz w każdej chwili." },
                ].map(({ icon: ItemIcon, title, text }) => (
                  <div key={title}>
                    <ItemIcon size={20} className="text-muted" />
                    <h3 className="mt-3 font-semibold">{title}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted">{text}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <InstallSection />

        {/* Zakończenie */}
        <section className="px-5 pt-10 pb-24">
          <div className="landing-cta mx-auto max-w-4xl rounded-[32px] px-6 py-14 text-center md:py-20">
            <Logo size={52} className="mx-auto rounded-2xl shadow-lg shadow-accent/30" />
            <h2 className="mt-6 text-3xl font-semibold tracking-tight md:text-5xl">Zacznij od jednej wiadomości</h2>
            <p className="mx-auto mt-3 max-w-xl text-muted">Opisz, czego potrzebujesz. Resztą zajmie się Nexus.</p>
            <a
              href="/zaloguj"
              className="mt-8 inline-flex items-center gap-2 rounded-full bg-fg px-6 py-3 font-medium text-app transition-opacity hover:opacity-90"
            >
              Zaloguj się <ArrowRightIcon size={18} />
            </a>
          </div>
        </section>
      </main>
      <footer className="safe-bottom border-t border-white/5 px-5 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 text-sm text-muted sm:flex-row">
          <div className="flex items-center gap-2">
            <Logo size={20} className="rounded-md" />
            <span>© {new Date().getFullYear()} Danaco · Danaco Nexus</span>
          </div>
          <nav className="flex gap-5 sm:ml-auto" aria-label="Stopka">
            <a className="hover:text-fg" href="#instalacja">
              Instalacja
            </a>
            <a className="hover:text-fg" href="/zaloguj">
              Zaloguj się
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
