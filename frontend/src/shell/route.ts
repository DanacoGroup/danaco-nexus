// Trasy aplikacji: strona startowa, logowanie, czat, moduły i kompaktowy panel (funkcje czyste).

export type Route =
  | { view: "panel" }
  | { view: "login" }
  | { view: "landing" }
  | { view: "portal" }
  | { view: "demo" }
  | { view: "chat"; conversationId: string | null }
  | { view: "module"; moduleId: string };

/** Co faktycznie pokazać dla trasy i stanu logowania. */
export type Screen = "panel" | "landing" | "demo" | "login" | "app";

const CONVERSATION = /^\/c\/([0-9a-f-]{36})\/?$/;
const MODULE = /^\/m\/([a-z0-9][a-z0-9-]{0,39})\/?$/;
const CZAT = new Set(["czat", "chat", "rozmowa"]);

/** Stałe adresy części publicznej; portal odsyła do nich po nazwie. */
export const SCIEZKA = {
  aplikacja: "/zaloguj",
  stronaProduktu: "/start",
  piaskownica: "/wyprobuj",
  portal: "/portal",
} as const;

export function parseRoute(pathname: string, search: string): Route {
  const params = new URLSearchParams(search);
  const sciezka = pathname.replace(/\/+$/, "") || "/";
  if (params.get("widok") === "panel") return { view: "panel" };
  if (sciezka === SCIEZKA.aplikacja) return { view: "login" };
  if (sciezka === SCIEZKA.stronaProduktu) return { view: "landing" };
  if (sciezka === SCIEZKA.piaskownica) return { view: "demo" };
  // Portal ma własne trasowanie (src/portal/trasy.ts).
  if (sciezka === SCIEZKA.portal || pathname.startsWith(`${SCIEZKA.portal}/`)) return { view: "portal" };
  const conversation = pathname.match(CONVERSATION);
  if (conversation) return { view: "chat", conversationId: conversation[1] };
  const module = pathname.match(MODULE);
  if (module) {
    // Czat jest w pasku jedną z pozycji i nazywa się tak samo jak moduły, ale w rejestrze
    // modułem nie jest. Bez tego /m/czat kończyło się planszą „moduł nie jest zainstalowany”.
    if (CZAT.has(module[1])) return { view: "chat", conversationId: null };
    return { view: "module", moduleId: module[1] };
  }
  return { view: "chat", conversationId: null };
}

export function routePath(route: Route): string {
  switch (route.view) {
    case "panel":
      return "/?widok=panel";
    case "login":
      return SCIEZKA.aplikacja;
    case "landing":
      return SCIEZKA.stronaProduktu;
    case "demo":
      return SCIEZKA.piaskownica;
    case "portal":
      return SCIEZKA.portal;
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
  // „Wypróbuj” to wejście do tej samej aplikacji na koncie próbnym, nie osobny pokaz.
  if (route.view === "demo") return "demo";
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
