// Aplikacja: trasy (strona startowa, logowanie, powłoka z modułami, panel osadzony) i stan logowania.

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Login } from "./components/Login";
import { Landing } from "./landing/Landing";
import { isStandalone } from "./pwa";
import { PanelApp } from "./shell/PanelApp";
import { parseRoute, resolveScreen, safeNext } from "./shell/route";
import { Workspace } from "./shell/Workspace";

interface Location {
  pathname: string;
  search: string;
}

const currentLocation = (): Location => ({ pathname: window.location.pathname, search: window.location.search });

export default function App() {
  const [location, setLocation] = useState<Location>(currentLocation);
  const route = parseRoute(location.pathname, location.search);
  if (route.view === "panel") return <PanelApp />;
  return <MainApp location={location} setLocation={setLocation} />;
}

function MainApp({ location, setLocation }: { location: Location; setLocation: (location: Location) => void }) {
  const [user, setUser] = useState<string | null | undefined>(undefined);
  const [cloudUrl, setCloudUrl] = useState("");
  const route = parseRoute(location.pathname, location.search);

  const navigate = useCallback(
    (path: string, replace = false) => {
      if (path === window.location.pathname + window.location.search) return;
      window.history[replace ? "replaceState" : "pushState"](null, "", path);
      setLocation(currentLocation());
    },
    [setLocation],
  );

  useEffect(() => {
    const onPop = () => setLocation(currentLocation());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [setLocation]);

  // Kliknięcie powiadomienia push (service worker) otwiera wskazaną rozmowę w tym oknie.
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

  const loadMe = useCallback(
    () =>
      api
        .me()
        .then((me) => {
          setCloudUrl(me.cloud_url ?? "");
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

  if (user === undefined) return <div className="h-full bg-app" />;

  let screen = resolveScreen(route, Boolean(user), location.search);
  // Zainstalowana aplikacja (PWA) otwiera się od razu na logowaniu, nie na stronie startowej.
  if (screen === "landing" && route.view !== "landing" && isStandalone()) screen = "login";

  if (screen === "landing") return <Landing />;
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
    <Workspace
      username={user}
      cloudUrl={cloudUrl}
      route={route}
      navigate={navigate}
      onLoggedOut={() => {
        setUser(null);
        navigate("/zaloguj", true);
      }}
    />
  );
}
