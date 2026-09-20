// Wspólne elementy interfejsu portalu: nawigacja wewnętrzna, sekcje, karty, formularze i komunikaty.
// Wszystkie barwy i obramowania pochodzą z ról semantycznych arkusza aplikacji (src/styles.css).

import {
  createContext,
  useContext,
  useId,
  type AnchorHTMLAttributes,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { kaskada, useWidocznosc, ZnakRuchu, type MomentZnaku } from "../ruch";

/** Przejście do innej trasy portalu bez przeładowania strony. */
export type Nawigacja = (sciezka: string) => void;

const NawigacjaContext = createContext<Nawigacja>(() => {});

export function DostawcaNawigacji({ nawiguj, children }: { nawiguj: Nawigacja; children: ReactNode }) {
  return <NawigacjaContext.Provider value={nawiguj}>{children}</NawigacjaContext.Provider>;
}

export function useNawigacja(): Nawigacja {
  return useContext(NawigacjaContext);
}

/** Odsyłacz wewnątrz portalu: zwykły znacznik a z przechwyceniem kliknięcia lewym przyciskiem. */
export function Odsylacz({
  adres,
  children,
  ...reszta
}: { adres: string; children: ReactNode } & AnchorHTMLAttributes<HTMLAnchorElement>) {
  const nawiguj = useNawigacja();
  return (
    <a
      href={adres}
      onClick={(zdarzenie) => {
        if (zdarzenie.metaKey || zdarzenie.ctrlKey || zdarzenie.shiftKey || zdarzenie.button !== 0) return;
        zdarzenie.preventDefault();
        nawiguj(adres);
      }}
      {...reszta}
    >
      {children}
    </a>
  );
}

// `ui-nacisk` daje wciśnięcie skalą `--scale-press` (motion, rozdz. 11) — jedna reguła
// dla przycisku i dla odsyłacza w postaci przycisku.
const PRZYCISK_PODSTAWA =
  "ui-nacisk ui-przejscie inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50";
const WARIANTY = {
  glowny: "bg-accent-fill text-on-accent hover:bg-accent-fill-hover",
  drugorzedny: "border border-line-strong text-fg hover:bg-raised",
  cichy: "text-muted hover:text-fg",
} as const;

export function Przycisk({
  wariant = "glowny",
  className = "",
  children,
  ...reszta
}: { wariant?: keyof typeof WARIANTY } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" className={`${PRZYCISK_PODSTAWA} ${WARIANTY[wariant]} ${className}`} {...reszta}>
      {children}
    </button>
  );
}

export function OdsylaczPrzycisk({
  adres,
  wariant = "glowny",
  className = "",
  children,
}: {
  adres: string;
  wariant?: keyof typeof WARIANTY;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Odsylacz adres={adres} className={`${PRZYCISK_PODSTAWA} ${WARIANTY[wariant]} ${className}`}>
      {children}
    </Odsylacz>
  );
}

/** Sekcja strony z nagłówkiem drugiego stopnia i opcjonalnym wprowadzeniem. */
export function Sekcja({
  tytul,
  opis,
  children,
  identyfikator,
}: {
  tytul: string;
  opis?: string;
  children: ReactNode;
  identyfikator?: string;
}) {
  const wygenerowany = useId();
  const id = identyfikator ?? wygenerowany;
  // Kaskada wejścia: nagłówek, wprowadzenie, treść — kolejność jak w choreografii (motion, rozdz. 5).
  const [sekcja, widoczne] = useWidocznosc<HTMLElement>();
  const stan = widoczne ? "true" : "false";
  return (
    <section ref={sekcja} aria-labelledby={id} className="py-10">
      <h2
        id={id}
        className="ui-ujawnij font-heading text-2xl font-semibold text-fg sm:text-3xl"
        data-widoczny={stan}
      >
        {tytul}
      </h2>
      {opis && (
        <p className="ui-ujawnij mt-3 max-w-2xl text-muted" data-widoczny={stan} style={kaskada(1)}>
          {opis}
        </p>
      )}
      <div className="ui-ujawnij mt-6" data-widoczny={stan} style={kaskada(2)}>
        {children}
      </div>
    </section>
  );
}

export function Karta({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`landing-karta p-5 ${className}`}>{children}</div>;
}

/** Pole formularza z etykietą, podpowiedzią i komunikatem błędu powiązanym przez aria-describedby. */
export function Pole({
  etykieta,
  wartosc,
  naZmiane,
  typ = "text",
  podpowiedz,
  blad,
  wymagane,
  autoUzupelnianie,
  wieloliniowe,
}: {
  etykieta: string;
  wartosc: string;
  naZmiane: (wartosc: string) => void;
  typ?: string;
  podpowiedz?: string;
  blad?: string;
  wymagane?: boolean;
  autoUzupelnianie?: string;
  wieloliniowe?: boolean;
}) {
  const id = useId();
  const opisId = `${id}-opis`;
  const wspolne = {
    id,
    value: wartosc,
    required: wymagane,
    "aria-describedby": podpowiedz || blad ? opisId : undefined,
    "aria-invalid": blad ? true : undefined,
    autoComplete: autoUzupelnianie,
    className:
      "w-full rounded-lg border border-line-strong bg-app px-3 py-2.5 text-fg placeholder:text-subtle focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent",
    onChange: (zdarzenie: { target: { value: string } }) => naZmiane(zdarzenie.target.value),
  };
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-fg">
        {etykieta}
        {wymagane && <span className="text-muted"> (wymagane)</span>}
      </label>
      {wieloliniowe ? <textarea {...wspolne} rows={6} /> : <input {...wspolne} type={typ} />}
      {(podpowiedz || blad) && (
        <p id={opisId} className={`text-sm ${blad ? "text-danger" : "text-subtle"}`}>
          {blad || podpowiedz}
        </p>
      )}
    </div>
  );
}

/** Komunikat o wyniku operacji; błędy ogłaszane są czytnikom ekranu od razu. */
export function Komunikat({ tekst, rodzaj = "info" }: { tekst: string; rodzaj?: "info" | "blad" | "sukces" }) {
  if (!tekst) return null;
  const barwy = {
    info: "border-line bg-raised text-fg",
    blad: "border-line-strong bg-danger-soft text-fg",
    sukces: "border-line-strong bg-success-soft text-fg",
  }[rodzaj];
  // Znak odgrywa moment „sukces” albo „błąd” (motion/start/README.md, rozdz. 8). Jest ozdobą —
  // treść komunikatu niesie samo zdanie obok.
  const moment = { info: null, blad: "blad", sukces: "sukces" }[rodzaj] as MomentZnaku | null;
  return (
    <p
      role={rodzaj === "blad" ? "alert" : "status"}
      className={`ui-wejscie flex items-center gap-3 rounded-lg border px-4 py-3 text-sm ${barwy}`}
    >
      {moment && <ZnakRuchu moment={moment} rozmiar={22} className="shrink-0" />}
      {tekst}
    </p>
  );
}

/** Zastępnik treści na czas pobierania – ma wysokość docelowej treści, więc układ nie skacze. */
export function Ladowanie({ wierszy = 3, etykieta = "Wczytywanie treści" }: { wierszy?: number; etykieta?: string }) {
  return (
    <div role="status" aria-live="polite" aria-label={etykieta} className="flex flex-col gap-3">
      {/* Moment „agent myśli”: punkt krąży pod łukiem, dopóki treść się wczytuje. */}
      <ZnakRuchu moment="mysli" rozmiar={28} />
      {Array.from({ length: wierszy }, (_, indeks) => (
        <div key={indeks} className="ui-szkielet h-20 rounded-xl border border-line" />
      ))}
    </div>
  );
}

/** Ścieżka nawigacji nad nagłówkiem strony. */
export function Okruszki({ pozycje }: { pozycje: { nazwa: string; sciezka: string }[] }) {
  return (
    <nav aria-label="Ścieżka nawigacji" className="text-sm text-muted">
      <ol className="flex flex-wrap items-center gap-2">
        {pozycje.map((pozycja, indeks) => (
          <li key={pozycja.sciezka} className="flex items-center gap-2">
            {indeks > 0 && <span aria-hidden="true">/</span>}
            {indeks === pozycje.length - 1 ? (
              <span aria-current="page" className="text-fg">
                {pozycja.nazwa}
              </span>
            ) : (
              <Odsylacz adres={pozycja.sciezka} className="hover:text-fg">
                {pozycja.nazwa}
              </Odsylacz>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

/** Nagłówek strony portalu (jedyny nagłówek pierwszego stopnia na stronie). */
export function NaglowekStrony({ tytul, opis, children }: { tytul: string; opis?: string; children?: ReactNode }) {
  return (
    <header className="pt-8 pb-2">
      <h1
        tabIndex={-1}
        id="portal-tytul"
        className="ui-wejscie font-heading text-3xl font-semibold text-fg sm:text-4xl"
      >
        {tytul}
      </h1>
      {opis && (
        <p className="ui-wejscie mt-4 max-w-2xl text-lg text-muted" style={kaskada(1)}>
          {opis}
        </p>
      )}
      {children && (
        <div className="ui-wejscie mt-6" style={kaskada(2)}>
          {children}
        </div>
      )}
    </header>
  );
}

export function Znacznik({ tekst, ton = "akcent" }: { tekst: string; ton?: "akcent" | "dostepny" | "cichy" }) {
  const barwy = {
    akcent: "bg-accent-soft text-accent",
    dostepny: "bg-success-soft text-success",
    cichy: "bg-hover text-muted",
  }[ton];
  return <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${barwy}`}>{tekst}</span>;
}
