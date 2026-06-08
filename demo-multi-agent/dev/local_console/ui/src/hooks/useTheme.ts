import { useCallback, useEffect, useState } from "react";

export const THEME_STORAGE_KEY = "matbot:theme";

export type Theme = "light" | "dark";

interface UseTheme {
  theme: Theme;
  toggle: () => void;
}

/**
 * Theme hook.
 *
 *   1. Reads the initial value from localStorage. Falls back to whether
 *      the `.dark` class is on `<html>` — the pre-React inline script
 *      in index.html sets the class according to the stored preference
 *      so the first paint is correct.
 *   2. Mirrors state changes back onto `document.documentElement` —
 *      tokens.css branches on the `.dark` class.
 *   3. Persists every change to localStorage.
 */
export function useTheme(): UseTheme {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") return "light";
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
    return document.documentElement.classList.contains("dark")
      ? "dark"
      : "light";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.style.colorScheme = theme;
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      /* localStorage quota errors are non-fatal */
    }
  }, [theme]);

  const toggle = useCallback(
    () => setTheme((prev) => (prev === "dark" ? "light" : "dark")),
    [],
  );

  return { theme, toggle };
}
