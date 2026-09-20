// Motyw interfejsu: ciemny (domyślny), jasny albo zgodny z systemem.

export type ThemeChoice = "dark" | "light" | "system";

const STORAGE_KEY = "nexus-theme";
// Barwy powierzchni aplikacji z tokenów: --app w motywie ciemnym i jasnym.
const THEME_COLORS = { dark: "#0D0F17", light: "#F9FAFE" } as const;

export function storedTheme(): ThemeChoice {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "dark" || value === "light" || value === "system") return value;
  } catch {
    // Brak dostępu do pamięci przeglądarki – motyw domyślny.
  }
  return "dark";
}

export function resolveTheme(choice: ThemeChoice): "dark" | "light" {
  if (choice !== "system") return choice;
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(choice: ThemeChoice): void {
  const theme = resolveTheme(choice);
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLORS[theme]);
}

export function saveTheme(choice: ThemeChoice): void {
  try {
    localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    // Wybór obowiązuje do zamknięcia karty.
  }
  applyTheme(choice);
}

export function nextTheme(choice: ThemeChoice): ThemeChoice {
  return choice === "dark" ? "light" : choice === "light" ? "system" : "dark";
}
