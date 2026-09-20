// Aplikacja: trasy (strona startowa, logowanie, powłoka z modułami, panel osadzony) i stan logowania.

import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Login } from "./components/Login";
import { isStandalone } from "./pwa";
import { EkranStartowy } from "./shell/EkranStartowy";
import { parseRoute, resolveScreen, safeNext } from "./shell/route";

// Ekrany ładowane na żądanie: gość na stronie produktu nie pobiera powłoki aplikacji ani modułów.
const Landing = lazy(() => import("./landing/Landing").then((m) => ({ default: m.Landing })));
const Workspace = lazy(() => import("./shell/Workspace").then((m) => ({ default: m.Workspace })));
const PanelApp = lazy(() => import("./shell/PanelApp").then((m) => ({ default: m.PanelApp })));
const Portal = lazy(() => import("./portal/Portal").then((m) => ({ default: m.Portal })));
const WejscieGoscia = lazy(() => import("./demo/WejscieGoscia").then((m) => ({ default: m.WejscieGoscia })));

/** Pusta powierzchnia w barwie tła na czas pobierania ekranu. */
const Pusto = () => <div className="h-full bg-app" />;

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
        })
        .catch(() => setUser(null)),
    [],
  );

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

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
  if (user === undefined) return <EkranStartowy />;

  let screen = resolveScreen(route, Boolean(user), location.search);
  // Zainstalowana aplikacja (PWA) otwiera się od razu na logowaniu, nie na stronie startowej.
  // Adres „/start” tu nie dochodzi — obsługuje go App przed stanem logowania.
  if (screen === "landing" && isStandalone()) screen = "login";

  if (screen === "landing")
    return (
      <Suspense fallback={<Pusto />}>
        <Landing />
      </Suspense>
    );
  // „Wypróbuj” nie otwiera pokazu obok produktu: zakłada konto próbne i wpuszcza do aplikacji.
  if (screen === "demo")
    return (
      <Suspense fallback={<Pusto />}>
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
    <Suspense fallback={<Pusto />}>
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
