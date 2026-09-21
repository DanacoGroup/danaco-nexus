// Aplikacja: trasy (strona startowa, logowanie, powłoka z modułami, panel osadzony) i stan logowania.

import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { przySmianiePreferencji, wczytajPreferencje, zastosujRuch } from "./preferencje";
import { applyTheme } from "./theme";
import { Login } from "./components/Login";
import { isStandalone } from "./pwa";
import { EkranStartowy } from "./shell/EkranStartowy";
import { applyIndexing } from "./seo";
import { parseRoute, resolveScreen, safeNext, type Screen } from "./shell/route";

/** Ile plansza otwarcia czeka na odpowiedź o sesji, zanim ustąpi ujęciu uruchomienia. */
const CZEKANIE_NA_SESJE_MS = 2500;

/** Ekran ładowania marki, jeżeli jest na stronie (public/ladowanie/ladowanie.js). */
interface Ladowanie {
  czekaj?: (zadanie: Promise<unknown>) => void;
}

// Ekrany ładowane na żądanie: gość na stronie produktu nie pobiera powłoki aplikacji ani modułów.
const Landing = lazy(() => import("./landing/Landing").then((m) => ({ default: m.Landing })));
const Workspace = lazy(() => import("./shell/Workspace").then((m) => ({ default: m.Workspace })));
const PanelApp = lazy(() => import("./shell/PanelApp").then((m) => ({ default: m.PanelApp })));
const Portal = lazy(() => import("./portal/Portal").then((m) => ({ default: m.Portal })));
const WejscieGoscia = lazy(() => import("./demo/WejscieGoscia").then((m) => ({ default: m.WejscieGoscia })));

/** Znaczniki strony dla bieżącego ekranu; podmiana poza cyklem renderowania Reacta. */
function aktualizujZnaczniki(screen: Screen): void {
  queueMicrotask(() => applyIndexing(screen));
}

/** Pusta powierzchnia w barwie tła na czas pobierania ekranu. */
const Pusto = () => <div className="h-full bg-app" />;

/** Zasłona na czas pobierania ekranu **za progiem logowania**.
 *
 * Tam, gdzie tuż przedtem stał ekran startowy (`user === undefined`), pusta powierzchnia
 * robiła mignięcie: znak marki znikał, przez ułamek sekundy było czarno, dopiero potem
 * wchodziło okno. Zmierzone na wejściu „bez rejestracji”: ekran startowy do ~2,2 s,
 * czarno do ~2,5 s, potem pasek modułów. Ten sam ekran startowy w zasłonie znaczy,
 * że nic nie znika i nic nie mignie — ruch jest jeden, od pierwszej klatki do okna. */
const Zaslona = () => <EkranStartowy />;

interface Location {
  pathname: string;
  search: string;
}

const currentLocation = (): Location => ({ pathname: window.location.pathname, search: window.location.search });

export default function App() {
  const [location, setLocation] = useState<Location>(currentLocation);

  const navigate = useCallback((path: string, replace = false) => {
    if (path === window.location.pathname + window.location.search) return;
    window.history[replace ? "replaceState" : "pushState"](null, "", path);
    setLocation(currentLocation());
  }, []);

  useEffect(() => {
    const onPop = () => setLocation(currentLocation());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Kliknięcie powiadomienia push otwiera wskazaną rozmowę w tym oknie. Nasłuch stoi w App,
  // bo worker wybiera dowolne okno aplikacji — także stojące na stronie produktu.
  useEffect(() => {
    const worker = navigator.serviceWorker;
    if (!worker) return;
    const onMessage = (event: MessageEvent) => {
      const data = event.data as { type?: string; url?: string } | null;
      const target = data?.type === "nexus:open" ? safeNext(data.url ?? null) : null;
      if (target) navigate(target);
    };
    worker.addEventListener("message", onMessage);
    return () => worker.removeEventListener("message", onMessage);
  }, [navigate]);

  const route = parseRoute(location.pathname, location.search);
  if (route.view === "panel")
    return (
      <Suspense fallback={<Pusto />}>
        <PanelApp />
      </Suspense>
    );
  // Portal produktowy jest publiczny i ma własną nawigację – nie przechodzi przez stan logowania.
  if (route.view === "portal")
    return (
      <Suspense fallback={<Pusto />}>
        <Portal />
      </Suspense>
    );
  // Strona produktu pod „/start” wygląda tak samo dla gościa i zalogowanego, więc nie czeka
  // na /api/auth/me: mniej o jeden obieg i o ujęcie uruchomienia.
  if (route.view === "landing")
    return (
      <Suspense fallback={<Pusto />}>
        <Landing />
      </Suspense>
    );
  return <MainApp location={location} navigate={navigate} />;
}

/** Ślad „ktoś się tu logował” — wyłącznie do decyzji o wyprzedzającym pobraniu pakietu.
 *
 * Nie jest to stan sesji i nie wolno go tak używać: o tym, kto patrzy, rozstrzyga wyłącznie
 * odpowiedź serwera. To podpowiedź wydajnościowa, więc jej brak (prywatne okno, wyczyszczone
 * dane, zablokowane `localStorage`) niczego nie psuje — pakiet pobierze się wtedy zwyczajnie,
 * po odpowiedzi o sesji, z zasłoną `EkranStartowy` na czas pobrania.
 */
const SLAD_LOGOWANIA = "dn:byl-zalogowany";

function bylZalogowany(): boolean {
  try {
    return localStorage.getItem(SLAD_LOGOWANIA) === "1";
  } catch {
    return false;
  }
}

function zapamietajZalogowanie(tak: boolean): void {
  try {
    if (tak) localStorage.setItem(SLAD_LOGOWANIA, "1");
    else localStorage.removeItem(SLAD_LOGOWANIA);
  } catch {
    /* prywatne okno albo zablokowane dane witryny — podpowiedź jest opcjonalna */
  }
}

function MainApp({
  location,
  navigate,
}: {
  location: Location;
  navigate: (path: string, replace?: boolean) => void;
}) {
  const [user, setUser] = useState<string | null | undefined>(undefined);
  const [cloudUrl, setCloudUrl] = useState("");
  const [gosc, setGosc] = useState(false);
  const route = parseRoute(location.pathname, location.search);

  const loadMe = useCallback(
    () =>
      api
        .me()
        .then((me) => {
          setCloudUrl(me.cloud_url ?? "");
          setGosc(Boolean(me.gosc));
          setUser(me.username);
          zapamietajZalogowanie(true);
        })
        .catch((awaria) => {
          setUser(null);
          // Ślad kasujemy wyłącznie wtedy, gdy serwer **powiedział**, że sesji nie ma.
          // Zerwane łącze albo błąd serwera to nie wylogowanie: skasowany wtedy ślad
          // zabrałby wyprzedzające pobranie przy następnym wejściu, choć konto jest całe.
          if (awaria instanceof ApiError && awaria.status === 401) zapamietajZalogowanie(false);
        }),
    [],
  );

  useEffect(() => {
    // Pakiet ekranu, który zaraz wejdzie, pobieramy **równolegle** z pytaniem o sesję.
    // Bez tego pobieranie zaczynało się dopiero po odpowiedzi i zasłona na czas pobrania
    // zdążyła się pokazać. Teraz zwykle nie ma jej wcale: pakiet jest już na miejscu,
    // kiedy wiadomo, kto patrzy. `catch` jest celowo pusty — nieudane wyprzedzenie nic
    // nie psuje, bo `Suspense` pobierze pakiet jeszcze raz, już z zasłoną.
    //
    // Ale **nie każdemu**. Pod „/” stoi albo okno aplikacji, albo strona produktu — zależnie
    // od sesji. Wyprzedzenie bez warunku znaczyło, że każdy, kto pierwszy raz wchodzi na
    // stronę produktu, ściąga 560 kB pakietu okna, którego nie zobaczy. Zmierzone
    // Lighthouse'em na wydaniu 21.09.2026: `Workspace-*.js` był największym pobraniem
    // strony publicznej, większym niż oba nagrania hero razem wzięte.
    //
    // Warunek jest prosty i nie wymaga pytania serwera: pod adresem aplikacji (`/c/…`,
    // `/m/…`, `/wyprobuj`) okno wejdzie na pewno, a pod „/” — tylko jeśli na tym urządzeniu
    // ktoś już był zalogowany. Pierwszy gość nie płaci za nic.
    if (location.pathname !== "/" || bylZalogowany()) {
      void import("./shell/Workspace").catch(() => undefined);
    }
    if (location.pathname === "/wyprobuj") void import("./demo/WejscieGoscia").catch(() => undefined);

    const sesja = loadMe();
    // Otwarcie okna rysuje ekran ładowania marki — ten sam, co na stronie produktu.
    // Niech poczeka, aż wiadomo, kto patrzy: inaczej plansza schodziłaby w chwili, gdy
    // odpowiedź o sesji jest jeszcze w drodze, i tuż za nią wchodziłoby drugie ujęcie
    // uruchomienia. Jedno otwarcie od pierwszej klatki do gotowego okna czyta się jak
    // jeden ruch; dwa pod rząd wyglądają na zacięcie.
    //
    // Czeka jednak najwyżej `CZEKANIE_NA_SESJE_MS`. Plansza ma własny twardy limit
    // dziesięciu sekund, a tyle nikt nie ma patrzeć na znak, gdy serwer się ociąga —
    // po tym czasie okno przejmuje ujęcie uruchomienia, które jest w pętli i wygląda
    // na pracę, a nie na zawieszenie.
    const czekanie = Promise.race([sesja, new Promise((ok) => window.setTimeout(ok, CZEKANIE_NA_SESJE_MS))]);
    (window as { DanacoLadowanie?: Ladowanie }).DanacoLadowanie?.czekaj?.(czekanie);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadMe]);

  // Preferencje konta jadą za użytkownikiem, nie za przeglądarką: po zalogowaniu
  // pobieramy je raz i od razu stosujemy motyw. Moduł startowy otwieramy wyłącznie
  // przy wejściu na „/” bez wskazanej rozmowy — adres modułu albo rozmowy ma
  // pierwszeństwo nad ustawieniem.
  // Znacznik ograniczonego ruchu stoi na korzeniu dokumentu od pierwszej klatki — także
  // na ekranie logowania, zanim konto zdąży podać swoje preferencje. Zmiana przełącznika
  // w Ustawieniach przestawia go od razu.
  useEffect(() => {
    zastosujRuch();
    return przySmianiePreferencji(() => zastosujRuch());
  }, []);

  const startUstawiony = useRef(false);
  useEffect(() => {
    if (!user || startUstawiony.current) return;
    startUstawiony.current = true;
    void wczytajPreferencje()
      .then((dane) => {
        applyTheme(dane.motyw);
        zastosujRuch();
        const naStarcie = dane.modul_startowy;
        if (naStarcie && naStarcie !== "chat" && location.pathname === "/" && !location.search) {
          navigate(`/m/${naStarcie}`, true);
        }
      })
      .catch(() => undefined);
  }, [user, location.pathname, location.search, navigate]);

  // Wejście z chmury bez sesji (?next=cloud): po zalogowaniu powrót do chmury.
  useEffect(() => {
    if (user && cloudUrl && new URLSearchParams(location.search).get("next") === "cloud") {
      window.location.replace(cloudUrl);
    }
  }, [user, cloudUrl, location.search]);

  // Po zalogowaniu na /zaloguj – powrót pod adres z ?next= albo do czatu.
  useEffect(() => {
    if (user && route.view === "login") {
      navigate(safeNext(new URLSearchParams(location.search).get("next")) ?? "/", true);
    }
  }, [user, route.view]);

  // Dopóki nie wiadomo, kto patrzy, okno gra ujęciem uruchomienia zamiast stać puste.
  // W zwykłym otwarciu nie widać go wcale: plansza marki czeka na tę samą odpowiedź
  // o sesji, więc schodzi już nad gotowym oknem. Ujęcie zostaje na wypadek, gdy sesja
  // rozstrzyga się długo (słaba sieć, zimny serwer) — wtedy okno ma czym grać zamiast
  // stać puste. Jest jedno (pełne, dobrane do urządzenia i motywu) i chodzi w pętli;
  // podmiana wariantu w połowie przerywałaby odtwarzanie i widać by było skok.
  if (user === undefined) return <EkranStartowy />;

  let screen = resolveScreen(route, Boolean(user), location.search);
  // Zainstalowana aplikacja (PWA) otwiera się od razu na logowaniu, nie na stronie startowej.
  // Adres „/start” tu nie dochodzi — obsługuje go App przed stanem logowania.
  if (screen === "landing" && isStandalone()) screen = "login";
  // Aplikacja jest jednostronicowa: bez tego wywołania wyszukiwarka i podgląd odsyłacza
  // widziały znaczniki z `index.html` niezależnie od tego, na którym ekranie stoi użytkownik
  // — a ekrany za logowaniem mają mieć „noindex”. Moduł `seo` istniał, ale nikt go nie wołał.
  aktualizujZnaczniki(screen);

  if (screen === "landing")
    return (
      <Suspense fallback={<Pusto />}>
        <Landing />
      </Suspense>
    );
  // „Wypróbuj” nie otwiera pokazu obok produktu: zakłada konto próbne i wpuszcza do aplikacji.
  if (screen === "demo")
    return (
      <Suspense fallback={<Zaslona />}>
        <WejscieGoscia
          onWejscie={() => {
            navigate("/", true);
            void loadMe();
          }}
        />
      </Suspense>
    );
  if (screen === "login" || !user) {
    return (
      <div className="relative h-full">
        <Login onLoggedIn={() => void loadMe()} />
        {!isStandalone() && (
          <a href="/start" className="safe-top absolute top-3 left-4 text-sm text-muted transition-colors hover:text-fg">
            ← Danaco Nexus
          </a>
        )}
      </div>
    );
  }
  return (
    <Suspense fallback={<Zaslona />}>
      <Workspace
        username={user}
        cloudUrl={cloudUrl}
        gosc={gosc}
        route={route}
        navigate={navigate}
        onLoggedOut={() => {
          setUser(null);
          navigate("/zaloguj", true);
        }}
      />
    </Suspense>
  );
}
