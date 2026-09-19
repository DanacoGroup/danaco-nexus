// Trasy aplikacji: strona startowa, logowanie, czat, moduły i kompaktowy panel (funkcje czyste).

export type Route =
  | { view: "panel" }
  | { view: "login" }
  | { view: "landing" }
  | { view: "chat"; conversationId: string | null }
  | { view: "module"; moduleId: string };

/** Co faktycznie pokazać dla trasy i stanu logowania. */
export type Screen = "panel" | "landing" | "login" | "app";

const CONVERSATION = /^\/c\/([0-9a-f-]{36})\/?$/;
const MODULE = /^\/m\/([a-z0-9][a-z0-9-]{0,39})\/?$/;

export function parseRoute(pathname: string, search: string): Route {
  const params = new URLSearchParams(search);
  if (params.get("widok") === "panel") return { view: "panel" };
  if (pathname === "/zaloguj" || pathname === "/zaloguj/") return { view: "login" };
  if (pathname === "/start" || pathname === "/start/") return { view: "landing" };
  const conversation = pathname.match(CONVERSATION);
  if (conversation) return { view: "chat", conversationId: conversation[1] };
  const module = pathname.match(MODULE);
  if (module) return { view: "module", moduleId: module[1] };
  return { view: "chat", conversationId: null };
}

export function routePath(route: Route): string {
  switch (route.view) {
    case "panel":
      return "/?widok=panel";
    case "login":
      return "/zaloguj";
    case "landing":
      return "/start";
    case "module":
      return `/m/${route.moduleId}`;
    case "chat":
      return route.conversationId ? `/c/${route.conversationId}` : "/";
  }
}

/**
 * Ekran dla trasy. Niezalogowany użytkownik na „/” widzi stronę startową; adres rozmowy
 * lub modułu (i powrót do chmury ?next=cloud) prowadzi prosto do logowania.
 */
export function resolveScreen(route: Route, loggedIn: boolean, search: string): Screen {
  if (route.view === "panel") return "panel";
  if (route.view === "landing") return "landing";
  if (loggedIn) return "app";
  if (route.view === "login") return "login";
  const params = new URLSearchParams(search);
  if (route.view === "chat" && route.conversationId === null && !params.has("next")) return "landing";
  return "login";
}

/** Bezpieczny adres powrotu po zalogowaniu (tylko ścieżka w tej witrynie). */
export function safeNext(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return null;
  return value;
}
