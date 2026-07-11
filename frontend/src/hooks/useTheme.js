import { useEffect, useState } from "react";

const STORAGE_KEY = "fightiq_theme";
const THEME_COLOR = { dark: "#0f1115", light: "#f6f7f9" };

function preferredTheme() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* storage unavailable */
  }
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

/**
 * Dark/light theme state. The inline script in index.html applies the same
 * resolution before first paint; this hook owns it from mount onward:
 * stamps <html data-theme>, persists the choice, and keeps the browser-chrome
 * theme-color in sync.
 */
export function useTheme() {
  const [theme, setTheme] = useState(preferredTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* storage unavailable */
    }
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = THEME_COLOR[theme];
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  return { theme, toggleTheme };
}
