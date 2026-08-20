const KEY = "lipanel-theme";

export type Theme = "light" | "dark" | "system";

export function applyTheme(theme: Theme): void {
  const dark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
  localStorage.setItem(KEY, theme);
}

export function getTheme(): Theme {
  const value = localStorage.getItem(KEY);
  return value === "light" || value === "dark" || value === "system"
    ? value
    : "system";
}

export function initTheme(): void {
  applyTheme(getTheme());
}
