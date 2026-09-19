// Skrót klawiszowy panelu obsługiwany na stronie (działa także bez chrome.commands).

/** Alt+N lub Ctrl+Shift+Spacja. AltGr (Ctrl+Alt) nie wywołuje panelu – to polskie znaki. */
export function jestSkrotemPanelu(e: Pick<KeyboardEvent, "altKey" | "ctrlKey" | "shiftKey" | "metaKey" | "code">): boolean {
  if (e.metaKey) return false;
  const altN = e.altKey && !e.ctrlKey && !e.shiftKey && e.code === "KeyN";
  const ctrlSpacja = e.ctrlKey && e.shiftKey && !e.altKey && e.code === "Space";
  return altN || ctrlSpacja;
}
