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
  const wymiar = rozmiar === "duzy" ? "h-12 w-full px-6 sm:w-auto" : "h-9 px-4 text-sm";

  if (isStandalone()) {
    return (
      <a href="/" className={`${GLOWNY} ${wymiar}`}>
        Otwórz aplikację
      </a>
    );
  }
  if (pwa.canInstall) {
    return (
      <button type="button" className={`${GLOWNY} ${wymiar}`} onClick={() => void pwa.install()}>
        <InstallIcon size={rozmiar === "duzy" ? 18 : 16} /> Zainstaluj aplikację
      </button>
    );
  }
  return (
    <a href="#instalacja" className={`${GLOWNY} ${wymiar}`}>
      Zainstaluj aplikację
    </a>
  );
}

export function InstallSection() {
  const [platforma, setPlatforma] = useState<Platforma>("windows");
  const [kroki, widoczne] = useWidocznosc<HTMLOListElement>();

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

      {/* Ujęcie „moment-instalacja” z pakietu ruchu: pokazuje to, co opisują kroki obok. */}
      {!ograniczonyRuch() && (
        <div className="mx-auto mt-10 max-w-lg overflow-hidden rounded-2xl border border-line bg-raised/60">
          <NagranieStartu nazwa="moment-instalacja" petla className="aspect-video w-full object-cover" />
        </div>
      )}

      <div className="mx-auto mt-12 max-w-3xl">
        <div role="tablist" aria-label="System urządzenia" className="flex justify-center gap-2">
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
                className={`ui-nacisk inline-flex h-9 items-center gap-2 rounded-full px-4 text-sm font-medium transition-colors ${
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
