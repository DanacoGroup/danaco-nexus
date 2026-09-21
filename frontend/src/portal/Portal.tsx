// Portal produktowy danaco-nexus.pl: nawigacja, trasowanie /portal/… i leniwe ładowanie stron.
//
// Portal jest osobną częścią aplikacji: działa bez logowania, ma własną nawigację i własny stan
// konta klienta. Aplikacja użytkownika (rozmowy, moduły) pozostaje pod adresami / oraz /m/…

import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PASMO } from "../ui/pasmo";
import { Logotype, Mark } from "../components/icons";
import { SCIEZKA } from "../shell/route";
import { portalApi, type ProfilKlienta, type StanPortalu } from "./api";
import { usePozycjonowanie } from "./seo";
import { czyAktywna, czyPortal, parsujTrase, sciezka, rodzajTresci, type PortalTrasa } from "./trasy";
import { DostawcaNawigacji, Ladowanie, Odsylacz, OdsylaczPrzycisk, Przycisk } from "./ui";

const Glowna = lazy(() => import("./strony/Glowna").then((m) => ({ default: m.Glowna })));
const Oferta = lazy(() => import("./strony/Oferta").then((m) => ({ default: m.Oferta })));
const Funkcje = lazy(() => import("./strony/Funkcje").then((m) => ({ default: m.Funkcje })));
const Narzedzia = lazy(() => import("./strony/Narzedzia").then((m) => ({ default: m.Narzedzia })));
const Zastosowania = lazy(() => import("./strony/Zastosowania").then((m) => ({ default: m.Zastosowania })));
const Cennik = lazy(() => import("./strony/Cennik").then((m) => ({ default: m.Cennik })));
const Kontakt = lazy(() => import("./strony/Kontakt").then((m) => ({ default: m.Kontakt })));
const Dokumentacja = lazy(() => import("./strony/Dokumentacja").then((m) => ({ default: m.Dokumentacja })));
const ListaWpisow = lazy(() => import("./strony/ListaWpisow").then((m) => ({ default: m.ListaWpisow })));
const Wpis = lazy(() => import("./strony/Wpis").then((m) => ({ default: m.Wpis })));
const Szukaj = lazy(() => import("./strony/Szukaj").then((m) => ({ default: m.Szukaj })));
const Konto = lazy(() => import("./strony/Konto").then((m) => ({ default: m.Konto })));
const PanelKlienta = lazy(() => import("./strony/PanelKlienta").then((m) => ({ default: m.PanelKlienta })));
const PanelAdministratora = lazy(() =>
  import("./strony/PanelAdministratora").then((m) => ({ default: m.PanelAdministratora })),
);
const Prywatnosc = lazy(() => import("./strony/Prywatnosc").then((m) => ({ default: m.Prywatnosc })));
const Regulamin = lazy(() => import("./strony/Regulamin").then((m) => ({ default: m.Regulamin })));
const Cookies = lazy(() => import("./strony/Cookies").then((m) => ({ default: m.Cookies })));

interface PozycjaMapy {
  nazwa: string;
  adres: string;
  /** Pozycja widoczna w pasku nawigacji; pozostałe są w menu, w stopce i na stronie 404. */
  wNawigacji?: boolean;
}

/**
 * Mapa portalu: jedno źródło nazw i adresów dla paska nawigacji, menu, stopki i strony 404.
 * Nazwy są takie same jak tytuły stron w wynikach wyszukiwania i w okruszkach, więc nazewnictwo
 * nie rozjeżdża się między miejscami. Nagłówek na stronie mówi, co użytkownik z niej ma.
 */
const MAPA_PORTALU: { tytul: string; pozycje: PozycjaMapy[] }[] = [
  {
    tytul: "Produkt",
    pozycje: [
      { nazwa: "Portal", adres: sciezka("glowna") },
      { nazwa: "Oferta", adres: sciezka("oferta"), wNawigacji: true },
      { nazwa: "Funkcje", adres: sciezka("funkcje"), wNawigacji: true },
      { nazwa: "Zastosowania", adres: sciezka("zastosowania"), wNawigacji: true },
      { nazwa: "Narzędzia agenta", adres: sciezka("narzedzia"), wNawigacji: true },
      { nazwa: "Cennik", adres: sciezka("cennik"), wNawigacji: true },
      { nazwa: "Strona produktu", adres: SCIEZKA.stronaProduktu },
      { nazwa: "Wejdź bez rejestracji", adres: SCIEZKA.piaskownica },
    ],
  },
  {
    tytul: "Materiały",
    pozycje: [
      { nazwa: "Dokumentacja", adres: sciezka("dokumentacja") },
      { nazwa: "Blog", adres: sciezka("blog") },
      { nazwa: "Centrum wiedzy", adres: sciezka("wiedza") },
      { nazwa: "Szukaj", adres: sciezka("szukaj") },
    ],
  },
  {
    tytul: "Konto i pomoc",
    pozycje: [
      { nazwa: "Kontakt", adres: sciezka("kontakt") },
      { nazwa: "Konto klienta", adres: sciezka("konto") },
      { nazwa: "Panel klienta", adres: sciezka("panel") },
      { nazwa: "Aplikacja", adres: SCIEZKA.aplikacja },
    ],
  },
  {
    tytul: "Zgodność",
    pozycje: [
      { nazwa: "Polityka prywatności", adres: sciezka("prywatnosc") },
      { nazwa: "Regulamin", adres: sciezka("regulamin") },
      { nazwa: "Pliki cookie", adres: sciezka("cookies") },
    ],
  },
];

const POZYCJE = MAPA_PORTALU.flatMap((grupa) => grupa.pozycje);
/**
 * Pozycje paska nagłówka. Pasmo treści ma 1120 px na laptopie (1200 px pasma minus
 * marginesy), z czego logotyp i akcje zabierają 470 px — na nazwy zostaje 650 px.
 * Dziewięć pozycji zajmowało 874 px, więc akcje spadały do drugiego wiersza i pasek
 * był dwa razy wyższy na każdej szerokości powyżej 1280 px. W pasku zostaje ścieżka
 * produktu (482 px), reszta mapy portalu jest pod przyciskiem „Menu”, widocznym teraz
 * także na dużym ekranie.
 */
const NAWIGACJA = POZYCJE.filter((pozycja) => pozycja.wNawigacji);

/** Nazwa adresu z mapy portalu: pasek nagłówka i strona 404 nie nazywają tego samego inaczej. */
const nazwa = (adres: string): string => POZYCJE.find((pozycja) => pozycja.adres === adres)?.nazwa ?? adres;

interface Adres {
  pathname: string;
  search: string;
}

const biezacyAdres = (): Adres => ({
  pathname: window.location.pathname,
  search: window.location.search,
});

function Nieznana({ adres }: { adres: string }) {
  usePozycjonowanie({
    tytul: "Nie znaleziono strony",
    opis: "Tego adresu nie ma w portalu Danaco Nexus. Poniżej jest spis wszystkich sekcji.",
    sciezka: adres,
    noindex: true,
  });
  return (
    <div className="py-16">
      <h1 tabIndex={-1} id="portal-tytul" className="font-heading text-3xl font-semibold text-fg">
        Nie znaleziono strony
      </h1>
      <p className="mt-4 max-w-2xl text-muted">
        Adres <span className="text-fg">{adres}</span> nie istnieje w portalu — mógł się zmienić albo zawiera
        literówkę. Wróć na stronę główną, poszukaj treści albo wybierz sekcję ze spisu.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <OdsylaczPrzycisk adres={sciezka("glowna")}>{nazwa(sciezka("glowna"))}</OdsylaczPrzycisk>
        <OdsylaczPrzycisk adres={sciezka("szukaj")} wariant="drugorzedny">
          {nazwa(sciezka("szukaj"))}
        </OdsylaczPrzycisk>
        <OdsylaczPrzycisk adres={SCIEZKA.aplikacja} wariant="drugorzedny">
          {nazwa(SCIEZKA.aplikacja)}
        </OdsylaczPrzycisk>
      </div>
      <MapaPortalu tytul="Spis sekcji portalu" className="mt-12 border-t border-line pt-8" />
    </div>
  );
}

/**
 * Pełna mapa portalu w kolumnach: menu na węższym ekranie, stopka i strona 404.
 * W stopce całość jest jednym obszarem nawigacji o nazwie z tytułu; grupy są zwykłymi
 * kolumnami, więc czytnik ekranu wymienia mapę raz, a nie cztery razy.
 */
function MapaPortalu({
  tytul,
  tytulUkryty = false,
  obszarNawigacji = false,
  className = "",
}: {
  tytul: string;
  tytulUkryty?: boolean;
  obszarNawigacji?: boolean;
  className?: string;
}) {
  const Obszar = obszarNawigacji ? "nav" : "div";
  return (
    <Obszar className={className} aria-label={obszarNawigacji ? tytul : undefined}>
      <h2 className={tytulUkryty ? "sr-only" : "font-heading text-xl font-semibold text-fg"}>{tytul}</h2>
      <div className="mt-6 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
        {MAPA_PORTALU.map((grupa) => (
          <div key={grupa.tytul}>
            <h3 className="text-sm font-semibold text-fg">{grupa.tytul}</h3>
            <ul className="mt-3 flex flex-col gap-2">
              {grupa.pozycje.map((pozycja) => (
                <li key={pozycja.adres}>
                  <Odsylacz adres={pozycja.adres} className="text-sm text-muted hover:text-fg">
                    {pozycja.nazwa}
                  </Odsylacz>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Obszar>
  );
}

function Naglowek({
  aktywna,
  zalogowany,
  otwarte,
  przelacz,
}: {
  aktywna: string;
  zalogowany: boolean;
  otwarte: boolean;
  przelacz: () => void;
}) {
  return (
    <header className="safe-top sticky top-0 z-20 border-b border-line bg-glass backdrop-blur-xl">
      <div className={`${PASMO} flex min-h-16 flex-wrap items-center gap-4 py-2`}>
        <Odsylacz adres={sciezka("glowna")} className="flex items-center" aria-label={nazwa(sciezka("glowna"))}>
          {/* Na wąskim telefonie (360 px) logotyp z napisem zajmuje 151 px i spycha „Aplikację”
              oraz „Menu” do drugiego wiersza; sam znak ma 23 px i pasek zostaje jednowierszowy. */}
          <Mark size={24} className="max-[389px]:block hidden" />
          <Logotype height={24} className="max-[389px]:hidden" />
        </Odsylacz>
        <nav aria-label="Nawigacja portalu" className="hidden grow xl:block">
          <ul className="flex flex-wrap items-center gap-1">
            {NAWIGACJA.map((pozycja) => {
              const biezaca = czyAktywna(aktywna, pozycja.adres);
              return (
                <li key={pozycja.adres}>
                  <Odsylacz
                    adres={pozycja.adres}
                    aria-current={biezaca ? "page" : undefined}
                    className={`inline-flex h-9 items-center rounded-full px-3 text-sm transition-colors ${
                      biezaca ? "text-fg" : "text-muted hover:text-fg"
                    }`}
                  >
                    {pozycja.nazwa}
                  </Odsylacz>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Odsylacz
            adres={sciezka("szukaj")}
            className="hidden h-9 items-center rounded-full px-3 text-sm text-muted transition-colors hover:text-fg sm:inline-flex"
          >
            {nazwa(sciezka("szukaj"))}
          </Odsylacz>
          <Odsylacz
            adres={zalogowany ? sciezka("panel") : sciezka("konto")}
            className="hidden h-9 items-center rounded-full px-3 text-sm text-muted transition-colors hover:text-fg sm:inline-flex"
          >
            {nazwa(zalogowany ? sciezka("panel") : sciezka("konto"))}
          </Odsylacz>
          <OdsylaczPrzycisk adres={SCIEZKA.aplikacja}>{nazwa(SCIEZKA.aplikacja)}</OdsylaczPrzycisk>
          <Przycisk
            wariant="drugorzedny"
            aria-expanded={otwarte}
            aria-controls="menu-portalu"
            onClick={przelacz}
          >
            Menu
          </Przycisk>
        </div>
      </div>
      {/* Rozwinięcie wchodzi ruchem, jak reszta portalu: `ui-wejscie` startuje od nowa przy
          każdym pokazaniu, bo element wraca z `display: none`. */}
      <nav id="menu-portalu" aria-label="Menu portalu" hidden={!otwarte} className="ui-wejscie border-t border-line">
        <MapaPortalu tytul="Menu portalu" tytulUkryty className={`${PASMO} pt-4 pb-6`} />
      </nav>
    </header>
  );
}

function Stopka() {
  return (
    <footer className="mt-16 border-t border-line">
      <div className={`${PASMO} py-10`}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Logotype height={22} />
            <p className="mt-3 max-w-md text-sm text-muted">
              Twój agent do dokumentów, poczty, kalendarza i wiedzy. Rozmowy, pliki i historia
              w Twojej przestrzeni w chmurze.
            </p>
          </div>
          <OdsylaczPrzycisk adres={SCIEZKA.aplikacja} wariant="drugorzedny">
            {nazwa(SCIEZKA.aplikacja)}
          </OdsylaczPrzycisk>
        </div>
        <MapaPortalu tytul="Mapa portalu" tytulUkryty obszarNawigacji className="mt-8" />
      </div>
      {/* Kreska po krawędzi treści, nie po krawędzi pasma — `PASMO` ma własne odstępy
        boczne, więc obramowanie na nim samym wychodziło poza tekst z obu stron. */}
      <div className={PASMO}>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line py-5 text-sm text-subtle">
          <p>Danaco Group</p>
          <p className="flex gap-4">
            <a href="/portal/atom.xml" className="hover:text-fg">
              Kanał Atom
            </a>
            <a href="/sitemap.xml" className="hover:text-fg">
              Mapa witryny
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}

function Zawartosc({
  trasa,
  adres,
  konto,
  odswiezKonto,
  stan,
}: {
  trasa: PortalTrasa;
  adres: string;
  konto: ProfilKlienta | null;
  odswiezKonto: () => void;
  stan: StanPortalu | null;
}) {
  const rodzaj = rodzajTresci(trasa.strona);
  if (trasa.strona === "dokumentacja") return <Dokumentacja slug={trasa.slug} />;
  if (rodzaj && trasa.slug) {
    const nazwy = { blog: "Blog", wiedza: "Centrum wiedzy", dokumentacja: "Dokumentacja", strona: "Portal" };
    return <Wpis strona={trasa.strona} rodzaj={rodzaj} slug={trasa.slug} nazwaSekcji={nazwy[rodzaj]} />;
  }
  switch (trasa.strona) {
    case "glowna":
      return <Glowna />;
    case "oferta":
      return <Oferta />;
    case "funkcje":
      return <Funkcje />;
    case "narzedzia":
      return <Narzedzia />;
    case "zastosowania":
      return <Zastosowania />;
    case "cennik":
      return <Cennik />;
    case "kontakt":
      return <Kontakt />;
    case "blog":
      return (
        <ListaWpisow
          strona="blog"
          rodzaj="blog"
          tytul="Blog"
          opis="Materiały o pracy z Danaco Nexus i zmianach w produkcie."
        />
      );
    case "wiedza":
      return (
        <ListaWpisow
          strona="wiedza"
          rodzaj="wiedza"
          tytul="Centrum wiedzy"
          opis="Opracowania, poradniki i odpowiedzi na częste pytania."
        />
      );
    case "szukaj":
      return <Szukaj zapytanie={trasa.parametr} />;
    case "konto":
      return (
        <Konto
          konto={konto}
          odswiez={odswiezKonto}
          rejestracjaOtwarta={stan?.registration_open ?? true}
          pocztaDziala={stan?.poczta_dziala ?? true}
          token={trasa.parametr}
        />
      );
    case "panel":
      return <PanelKlienta konto={konto} odswiez={odswiezKonto} />;
    case "admin":
      return <PanelAdministratora administrator={stan?.admin ?? false} />;
    case "prywatnosc":
      return <Prywatnosc />;
    case "regulamin":
      return <Regulamin />;
    case "cookies":
      return <Cookies />;
    default:
      return <Nieznana adres={adres} />;
  }
}

export function Portal() {
  const [adres, setAdres] = useState<Adres>(biezacyAdres);
  const [konto, setKonto] = useState<ProfilKlienta | null>(null);
  const [stan, setStan] = useState<StanPortalu | null>(null);
  const [menu, setMenu] = useState(false);
  const trasa = useMemo(() => parsujTrase(adres.pathname, adres.search), [adres.pathname, adres.search]);

  // Escape zamyka rozwiniętą mapę portalu — tak samo jak menu na stronie produktu
  // (`landing/Landing.tsx`). Od kiedy „Menu” jest widoczne także na dużym ekranie,
  // rozwinięcie zasłania górę strony i musi dać się zamknąć klawiaturą.
  useEffect(() => {
    if (!menu) return;
    const klawisz = (zdarzenie: KeyboardEvent) => {
      if (zdarzenie.key === "Escape") setMenu(false);
    };
    window.addEventListener("keydown", klawisz);
    return () => window.removeEventListener("keydown", klawisz);
  }, [menu]);

  // Adres spoza portalu (aplikacja, strona produktu, piaskownica, kotwica, adres zewnętrzny)
  // wymaga zwykłego przejścia — trasowanie portalu nie obsłużyłoby go i pokazałoby stronę główną.
  const nawiguj = useCallback((docelowy: string) => {
    setMenu(false);
    if (!czyPortal(docelowy.split(/[?#]/)[0])) {
      window.location.assign(docelowy);
      return;
    }
    if (docelowy === window.location.pathname + window.location.search) return;
    window.history.pushState(null, "", docelowy);
    setAdres(biezacyAdres());
  }, []);

  useEffect(() => {
    const powrot = () => setAdres(biezacyAdres());
    window.addEventListener("popstate", powrot);
    return () => window.removeEventListener("popstate", powrot);
  }, []);

  const wczytajKonto = useCallback(() => {
    // Pytanie o stan sesji, a nie o zasób chroniony: gość dostaje `{konto: null}`, a nie
    // 401. Poprzednio przeglądarka zapisywała błąd w konsoli na każdej stronie publicznej.
    portalApi.konto
      .sesja()
      .then((odpowiedz) => setKonto(odpowiedz.konto))
      .catch(() => setKonto(null));
    portalApi.stan().then(setStan).catch(() => setStan(null));
  }, []);

  useEffect(() => wczytajKonto(), [wczytajKonto]);

  // Zmiana trasy: powrót na górę strony i przeniesienie uwagi na nagłówek (nawigacja klawiaturą).
  // Pierwsze wejście jest pomijane — inaczej strona otwierałaby się z pierścieniem fokusu.
  const pierwszeWejscie = useRef(true);
  useEffect(() => {
    if (pierwszeWejscie.current) {
      pierwszeWejscie.current = false;
      return;
    }
    window.scrollTo?.({ top: 0, behavior: "auto" });
    document.getElementById("portal-tytul")?.focus({ preventScroll: true });
    // Wybranie pozycji zamyka menu w `nawiguj`, ale cofnięcie się w przeglądarce omija
    // tę drogę — bez tego rozwinięta mapa portalu zostawała nad nową stroną.
    setMenu(false);
  }, [trasa.strona, trasa.slug, trasa.parametr]);

  return (
    <DostawcaNawigacji nawiguj={nawiguj}>
      <div className="portal flex min-h-dvh flex-col bg-app text-fg">
        <a
          href="#tresc-portalu"
          className="sr-only rounded-md bg-accent-fill px-4 py-2 text-on-accent focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-30"
        >
          Przejdź do treści
        </a>
        <Naglowek
          aktywna={adres.pathname}
          zalogowany={Boolean(konto)}
          otwarte={menu}
          przelacz={() => setMenu((otwarte) => !otwarte)}
        />
        <main id="tresc-portalu" className={`${PASMO} grow pb-16`}>
          <Suspense fallback={<div className="pt-12"><Ladowanie wierszy={4} etykieta="Wczytywanie strony" /></div>}>
            <Zawartosc trasa={trasa} adres={adres.pathname} konto={konto} odswiezKonto={wczytajKonto} stan={stan} />
          </Suspense>
        </main>
        <Stopka />
      </div>
    </DostawcaNawigacji>
  );
}
