// Sekcja „Instalacja”: jedno okno aplikacji dodawane z przeglądarki (PWA).
// Treść: landing/LANDING_PAGE_SPEC.md, rozdz. 7.9.

import { useEffect, useState, type ComponentType } from "react";
import { InstallIcon, ShareIcon } from "../components/icons";
import { isIos, isStandalone, usePwa } from "../pwa";
import { kaskada, NagranieStartu, ograniczonyRuch, PrzejscieWidoku, useWidocznosc, ZnakRuchu } from "../ruch";
import { PhoneIcon, WindowsIcon, type IconProps } from "../shell/icons";
import { Naglowek, Sekcja } from "./sekcje";

type Platforma = "windows" | "android" | "ios";

const KROKI: Record<Platforma, { etykieta: string; ikona: ComponentType<IconProps>; kroki: string[] }> = {
  windows: {
    etykieta: "Windows",
    ikona: WindowsIcon,
    kroki: [
      "Otwórz danaco-nexus.pl w Edge lub Chrome.",
      "Kliknij „Zainstaluj aplikację”.",
      "Nexus otworzy się we własnym oknie i trafi do menu Start.",
    ],
  },
  android: {
    etykieta: "Android",
    ikona: PhoneIcon,
    kroki: [
      "Otwórz danaco-nexus.pl w Chrome.",
      "Stuknij „Zainstaluj aplikację”.",
      "Potwierdź — ikona pojawi się na ekranie głównym.",
    ],
  },
  ios: {
    etykieta: "iPhone i iPad",
    ikona: PhoneIcon,
    kroki: ["Otwórz danaco-nexus.pl w Safari.", "Stuknij Udostępnij.", "Wybierz „Do ekranu początkowego”, potem „Dodaj”."],
  },
};

/** Platforma gościa — wybiera zakładkę startową. */
function platformaGoscia(): Platforma {
  if (isIos()) return "ios";
  return /Android/i.test(navigator.userAgent) ? "android" : "windows";
}

const GLOWNY =
  "ui-nacisk inline-flex items-center justify-center gap-2 rounded-full bg-accent-fill font-medium text-on-accent transition-colors hover:bg-accent-fill-hover";

/**
 * Moment „instalacja zakończona”: znak ląduje w miejscu przycisku po zdarzeniu `appinstalled`.
 * Znak jest ozdobą — potwierdzenie słowne stoi obok, w tekście przycisku.
 */
function MomentInstalacji() {
  const [zainstalowana, setZainstalowana] = useState(false);
  useEffect(() => {
    const gotowe = () => setZainstalowana(true);
    window.addEventListener("appinstalled", gotowe);
    return () => window.removeEventListener("appinstalled", gotowe);
  }, []);
  if (!zainstalowana) return null;
  return <ZnakRuchu moment="instalacja" rozmiar={32} />;
}

/**
 * Główne wezwanie strony. Gdy przeglądarka udostępnia własny monit instalacji — wywołuje go;
 * w pozostałych przypadkach prowadzi do kroków w sekcji „Instalacja”.
 */
export function PrzyciskInstalacji({ rozmiar = "duzy" }: { rozmiar?: "duzy" | "maly" }) {
  const pwa = usePwa();
  // W pasku (`maly`) pełna nazwa łamała się na dwa wiersze przy szerokości telefonu
  // i rozpychała nagłówek. Na wąskim ekranie zostaje samo „Zainstaluj”; pełne wezwanie
  // i tak stoi w hero kilka centymetrów niżej.
  const maly = rozmiar === "maly";
  const wymiar = maly ? "h-9 shrink-0 whitespace-nowrap px-4 text-sm" : "h-12 w-full px-6 sm:w-auto";
  const nazwa = maly ? (
    <>
      Zainstaluj<span className="hidden sm:inline"> aplikację</span>
    </>
  ) : (
    "Zainstaluj aplikację"
  );

  if (isStandalone()) {
    return (
      <a href="/" className={`${GLOWNY} ${wymiar}`}>
        Otwórz<span className={maly ? "hidden sm:inline" : ""}> aplikację</span>
      </a>
    );
  }
  if (pwa.canInstall) {
    return (
      <button type="button" className={`${GLOWNY} ${wymiar}`} onClick={() => void pwa.install()}>
        <InstallIcon size={maly ? 16 : 18} /> {nazwa}
      </button>
    );
  }
  return (
    <a href="#instalacja" className={`${GLOWNY} ${wymiar}`}>
      {nazwa}
    </a>
  );
}

export function InstallSection() {
  const [platforma, setPlatforma] = useState<Platforma>("windows");
  const [kroki, widoczne] = useWidocznosc<HTMLOListElement>();
  // Margines 300 px: nagranie ma być gotowe, zanim sekcja wjedzie na ekran.
  const [ramkaNagrania, nagranieWidoczne] = useWidocznosc<HTMLDivElement>({ margines: "300px" });

  useEffect(() => setPlatforma(platformaGoscia()), []);

  const wybrana = KROKI[platforma];
  return (
    <Sekcja id="instalacja">
      <Naglowek
        nad="Instalacja"
        tytul="Zainstaluj w kilka sekund. Bez sklepu z aplikacjami."
        akapit="Nexus mieszka w chmurze, a na urządzeniu zostaje samo okno — z ikoną na pulpicie i ekranie głównym, bez paska adresu i bez sklepu z aplikacjami. Ta sama przestrzeń otwiera się na telefonie, tablecie i komputerze."
        srodek
      />

      {/* Ujęcie „moment-instalacja” z pakietu ruchu: pokazuje to, co opisują kroki obok.
        Scena jest nagrana w ciasnym kadrze 760 × 600 px (rama pulpitu, okno potwierdzenia, dok),
        więc nic tu nie przycinamy — pokazujemy ją w całości w naturalnych proporcjach. */}
      {/* Nagranie wchodzi do drzewa dopiero, gdy sekcja zbliża się do ekranu. `NagranieStartu`
        ma `preload="auto"` — słusznie, bo w oknie aplikacji ujęcie musi ruszyć od razu — ale
        tutaj sekcja instalacji leży daleko pod pierwszym ekranem i 125 kB pobierało się
        każdemu, kto tylko zajrzał na stronę (zmierzone Lighthouse'em 21.09.2026). Ramka
        trzyma proporcje z góry, więc odłożone wczytanie nie przesuwa układu (CLS zostaje 0). */}
      {!ograniczonyRuch() && (
        <div
          ref={ramkaNagrania}
          className="mx-auto mt-10 aspect-[19/15] w-full max-w-[440px] overflow-hidden rounded-2xl border border-line bg-raised/60"
        >
          {nagranieWidoczne && (
          <NagranieStartu
            nazwa="moment-instalacja"
            // Ujęcie trwa 1,2 s. Przy trzysekundowej przerwie przez większość czasu stała
            // na ekranie ostatnia klatka — sam dok z ikoną, czyli obrazek, nie animacja.
            // Przerwa równa długości ujęcia daje ruch mniej więcej co drugą sekundę.
            powtarzaj={1500}
            className="size-full object-contain"
          />
          )}
        </div>
      )}

      <div className="mx-auto mt-12 max-w-3xl">
        {/* Na telefonie trzy zakładki nie mieszczą się w jednym wierszu: „iPhone i iPad”
          łamało się na dwie linijki i odrywało od swojej ikony. Etykiety zostają więc
          w całości, a sam wiersz zawija się na kolejną linijkę — przewijanie w bok ucinało
          ostatnią zakładkę przy krawędzi i wyglądało jak usterka. */}
        <div
          role="tablist"
          aria-label="System urządzenia"
          className="flex flex-wrap justify-center gap-2 px-4 sm:px-0"
        >
          {(Object.keys(KROKI) as Platforma[]).map((klucz) => {
            const { etykieta, ikona: Ikona } = KROKI[klucz];
            const aktywna = klucz === platforma;
            return (
              <button
                key={klucz}
                type="button"
                role="tab"
                aria-selected={aktywna}
                onClick={() => setPlatforma(klucz)}
                className={`ui-nacisk inline-flex h-9 shrink-0 items-center gap-2 rounded-full px-4 text-sm font-medium whitespace-nowrap transition-colors ${
                  aktywna ? "bg-accent-soft text-accent" : "text-muted hover:bg-hover hover:text-fg"
                }`}
              >
                <Ikona size={16} /> {etykieta}
              </button>
            );
          })}
        </div>
        {/* Zmiana systemu to zmiana widoku: stare kroki gasną, nowe wchodzą (motion, rozdz. 13). */}
        <PrzejscieWidoku klucz={platforma}>
          <ol ref={kroki} className="mt-8 grid gap-4 md:grid-cols-3">
            {wybrana.kroki.map((krok, indeks) => (
              <li
                key={krok}
                className="landing-karta ui-ujawnij p-5"
                data-widoczny={widoczne ? "true" : "false"}
                style={kaskada(indeks)}
              >
                <span className="font-heading text-sm font-bold text-accent tabular-nums">Krok {indeks + 1}</span>
                <p className="mt-2 leading-relaxed">
                  {indeks === 1 && platforma === "ios" ? (
                    <>
                      Stuknij <ShareIcon size={15} className="inline align-[-3px]" /> Udostępnij.
                    </>
                  ) : (
                    krok
                  )}
                </p>
              </li>
            ))}
          </ol>
        </PrzejscieWidoku>
        <div className="mt-8 flex items-center justify-center gap-3">
          <PrzyciskInstalacji />
          <MomentInstalacji />
        </div>
      </div>

      {/* Jedna instalacja. Wcześniej strona proponowała jeszcze APK, instalator Windows
          i rozszerzenie — trzy pobrania, z których każde wyglądało na osobny produkt,
          a praca i tak odbywa się po stronie usługi. Pakiety dla urządzeń wracają wtedy,
          gdy będą miały własne utrzymanie i aktualizacje. */}
      <p className="mx-auto mt-12 max-w-(--container-prose) text-center text-sm text-muted">
        To wszystko. Nie ma drugiej wersji do pobrania ani osobnego programu do zainstalowania —
        cała praca dzieje się po stronie usługi, a okno na Twoim urządzeniu jest tym samym Nexusem
        na telefonie, tablecie i komputerze.
      </p>
    </Sekcja>
  );
}
