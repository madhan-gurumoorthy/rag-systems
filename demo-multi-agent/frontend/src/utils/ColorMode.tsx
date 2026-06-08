import * as React from "react";

/**
 * Light/dark color-mode controller.
 *
 * Living Design themes ship as brand color palettes; they do not carry a
 * dark-mode variant. This module layers a `data-color-mode="light|dark"`
 * attribute on `<html>` so a small set of surface, text, and border
 * tokens can be re-pointed by `src/themes/dark-overrides.css` while the
 * brand theme (Sparky) keeps owning its action/brand tokens.
 *
 * Contract:
 *   - Storage key:    `matbot-color-mode`
 *   - HTML attribute: `data-color-mode`  (mirrors the active mode)
 *   - First-mount source of truth, in order:
 *       1. localStorage
 *       2. `prefers-color-scheme`
 *       3. fallback `"light"`
 *   - When the user has not made an explicit choice, the controller
 *     listens to system `prefers-color-scheme` changes and follows
 *     them. Once `setMode()` is called explicitly, the user choice is
 *     persisted and the system listener stops mutating state.
 */

export type ColorMode = "light" | "dark";

const STORAGE_KEY = "matbot-color-mode";
const ATTR = "data-color-mode";

const isBrowser = typeof window !== "undefined" && typeof document !== "undefined";

function readStored(): ColorMode | null {
  if (!isBrowser) return null;
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    if (v === "light" || v === "dark") return v;
  } catch {
    /* private mode, ignore */
  }
  return null;
}

function readSystem(): ColorMode {
  if (!isBrowser || !window.matchMedia) return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyMode(mode: ColorMode): void {
  if (!isBrowser) return;
  document.documentElement.setAttribute(ATTR, mode);
}

/**
 * React hook that owns color-mode state.
 *
 * Returns `[mode, setMode, source]` where `source` indicates whether
 * the current value came from the user (`"user"`) or the system
 * (`"system"`). Source is useful for "auto" UI affordances but is
 * optional for callers.
 */
export function useColorMode(): {
  mode: ColorMode;
  setMode: (next: ColorMode) => void;
  toggle: () => void;
  source: "user" | "system";
} {
  const [mode, setModeState] = React.useState<ColorMode>(() => {
    const stored = readStored();
    return stored ?? readSystem();
  });
  const [source, setSource] = React.useState<"user" | "system">(() =>
    readStored() ? "user" : "system",
  );

  // Reflect mode → DOM. Runs on every change, including the initial
  // render, so the attribute is in place before LD components paint.
  React.useEffect(() => {
    applyMode(mode);
  }, [mode]);

  // Follow system changes only while the user has not chosen explicitly.
  React.useEffect(() => {
    if (!isBrowser || !window.matchMedia) return;
    if (source === "user") return;

    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent): void => {
      setModeState(e.matches ? "dark" : "light");
    };
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [source]);

  const setMode = React.useCallback((next: ColorMode) => {
    setModeState(next);
    setSource("user");
    if (!isBrowser) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* private mode, ignore */
    }
  }, []);

  const toggle = React.useCallback(() => {
    setMode(mode === "dark" ? "light" : "dark");
  }, [mode, setMode]);

  return { mode, setMode, toggle, source };
}

/**
 * Imperatively set the color mode without React. Useful for early
 * page bootstrap before React mounts, e.g. an inline script in
 * `index.html` that reads localStorage and sets the attribute to
 * avoid a light→dark flash. Currently unused by the app but exported
 * for parity with `window.ldKit.setTheme()`.
 */
export function setColorMode(mode: ColorMode): void {
  applyMode(mode);
  if (!isBrowser) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    /* ignore */
  }
}

/**
 * Read the active color mode. Falls back to system preference when
 * nothing has been persisted yet.
 */
export function getColorMode(): ColorMode {
  return readStored() ?? readSystem();
}
