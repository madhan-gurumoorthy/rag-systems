import * as React from 'react';

const STORAGE_KEY = 'ld-kit-theme';
const THEME_CHANGE_EVENT = 'ld-kit-theme-change';

export const THEME_NAMES = [
  'Walmart',
  "Sam's Club",
  'Walmart B2B',
  'Bodega',
  'Cashi MX',
  'Data Ventures',
  'Sparky',
  'Walmart Legacy',
  'Walmart+',
  "Member's Mark",
] as const;

export type ThemeName = (typeof THEME_NAMES)[number];
export const DEFAULT_THEME: ThemeName = 'Walmart';

/* ── Theme Presets ─────────────────────────────────────────────── */

export interface ThemePreset {
  description: string;
  primaryColor: string;
}

export const THEME_PRESETS: Record<string, ThemePreset> = {
  'Walmart': {
    description: 'Default Walmart theme',
    primaryColor: '#0053e2',
  },
  "Sam's Club": {
    description: 'Member warehouse club with Gibson font family',
    primaryColor: '#0062ad',
  },
  'Walmart B2B': {
    description: 'Business platform with navy brand identity',
    primaryColor: '#002e99',
  },
  'Bodega': {
    description: 'Walmart Mexico retail with green brand and Bogle font',
    primaryColor: '#2c981d',
  },
  'Cashi MX': {
    description: 'Mexico financial services with purple brand',
    primaryColor: '#6212b2',
  },
  'Data Ventures': {
    description: 'Partner analytics platform with purple brand',
    primaryColor: '#6245b7',
  },
  'Sparky': {
    description: 'Internal tools platform with dark navy and cyan accents',
    primaryColor: '#001e60',
  },
  'Walmart Legacy': {
    description: 'Classic Walmart brand with Bogle font',
    primaryColor: '#0071dc',
  },
  'Walmart+': {
    description: 'Walmart+ membership with yellow accent warnings',
    primaryColor: '#0053e2',
  },
  "Member's Mark": {
    description: "Sam's Club private label with beige navigation",
    primaryColor: '#283645',
  },
};

/* ── Helpers ───────────────────────────────────────────────────── */

function isThemeName(name: string, allowedThemes: readonly ThemeName[]): name is ThemeName {
  return (allowedThemes as readonly string[]).includes(name);
}

function resolveDefaultTheme(
  defaultTheme: ThemeName,
  allowedThemes: readonly ThemeName[],
): ThemeName {
  if (allowedThemes.length === 0) return defaultTheme;
  if (isThemeName(defaultTheme, allowedThemes)) return defaultTheme;
  return allowedThemes[0];
}

function resolveInitialTheme(
  defaultTheme: ThemeName,
  allowedThemes: readonly ThemeName[],
): ThemeName {
  const safeDefaultTheme = resolveDefaultTheme(defaultTheme, allowedThemes);
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && isThemeName(stored, allowedThemes)) return stored;
  } catch {
    // localStorage may be unavailable; keep default theme.
  }
  return safeDefaultTheme;
}

/* ── Theme → Font Mapping ────────────────────────────────────── */
// Designer-editable mapping: src/fonts/theme-icon-map.json
// Keep THEME_FONT_CONFIG in sync with that file.

interface ThemeFontConfig {
  textFont: 'everyday-sans' | 'gibson' | 'bogle';
  /** The single icon font used by the Icon component for this theme. */
  primaryIconFont: string;
  /** All icon fonts to load (CSS). Internal — use primaryIconFont for lookups. */
  _loadFonts: string[];
}

export const THEME_FONT_CONFIG: Record<ThemeName, ThemeFontConfig> = {
  'Walmart':        { textFont: 'everyday-sans', primaryIconFont: 'wcp',       _loadFonts: ['ld', 'wcp'] },
  "Sam's Club":     { textFont: 'gibson',        primaryIconFont: 'sams-club', _loadFonts: ['ld', 'sams-club', 'ax-sams-club', 'px-sams-club'] },
  'Walmart B2B':    { textFont: 'everyday-sans', primaryIconFont: 'wcp',       _loadFonts: ['ld', 'wcp'] },
  'Bodega':         { textFont: 'bogle',         primaryIconFont: 'bodega',    _loadFonts: ['ld', 'bodega'] },
  'Cashi MX':       { textFont: 'everyday-sans', primaryIconFont: 'wcp',       _loadFonts: ['ld', 'wcp'] },
  'Data Ventures':  { textFont: 'everyday-sans', primaryIconFont: 'wcp',       _loadFonts: ['ld', 'wcp'] },
  'Sparky':         { textFont: 'everyday-sans', primaryIconFont: 'wcp',       _loadFonts: ['ld', 'wcp'] },
  'Walmart Legacy': { textFont: 'bogle',         primaryIconFont: 'wcp',       _loadFonts: ['ld', 'wcp'] },
  'Walmart+':       { textFont: 'everyday-sans', primaryIconFont: 'wcp',       _loadFonts: ['ld', 'wcp'] },
  "Member's Mark":  { textFont: 'gibson',        primaryIconFont: 'sams-club', _loadFonts: ['ld', 'sams-club', 'ax-sams-club', 'px-sams-club'] },
};

/* ── Font CSS Class Prefixes ─────────────────────────────────── */

export const FONT_CSS_CLASS: Record<string, string> = {
  'ld': 'ld',
  'wcp': 'wcp',
  'sams-club': 'sc',
  'ax': 'ax',
  'ax-sams-club': 'axsc',
  'px': 'px',
  'px-sams-club': 'pxsc',
  'bodega': 'bdg',
};

/** Returns the manifest key for the theme's primary icon font (e.g. 'wcp', 'bodega'). */
export function getThemePrimaryIconFont(theme: ThemeName): string {
  return THEME_FONT_CONFIG[theme]?.primaryIconFont ?? 'ld';
}

export function getThemeIconCssPrefix(theme: ThemeName): string {
  return FONT_CSS_CLASS[getThemePrimaryIconFont(theme)] || 'ld';
}

export function getCurrentTheme(): ThemeName {
  if (typeof document === 'undefined') return DEFAULT_THEME;
  const attr = document.documentElement.getAttribute('data-ld-theme');
  if (attr && (THEME_NAMES as readonly string[]).includes(attr)) return attr as ThemeName;
  return DEFAULT_THEME;
}

/** Subscribes to theme changes and re-derives a value from the active theme. */
function useThemeDerived<T>(resolver: (theme: ThemeName) => T): T {
  const [value, setValue] = React.useState(() => resolver(getCurrentTheme()));

  React.useEffect(() => {
    const handler = (e: Event) => {
      const theme = (e as CustomEvent).detail?.theme;
      if (theme) setValue(resolver(theme as ThemeName));
    };
    window.addEventListener(THEME_CHANGE_EVENT, handler);
    return () => window.removeEventListener(THEME_CHANGE_EVENT, handler);
  }, [resolver]);

  return value;
}

export function useThemeIconPrefix(): string {
  return useThemeDerived(getThemeIconCssPrefix);
}

/** Returns the active tenant's primary icon/media font key (e.g. 'wcp', 'sams-club', 'bodega'). */
export function useThemeMediaKey(): string {
  return useThemeDerived(getThemePrimaryIconFont);
}

/* ── On-Demand Font Loading ──────────────────────────────────── */

type FontImporter = () => Promise<unknown>;

const FONT_IMPORTERS: Record<string, FontImporter> = {
  'ld':             () => import('../fonts/ld/font.css'),
  'wcp':            () => import('../fonts/wcp/font.css'),
  'sams-club':      () => import('../fonts/sams-club/font.css'),
  'ax':             () => import('../fonts/ax/font.css'),
  'ax-sams-club':   () => import('../fonts/ax-sams-club/font.css'),
  'px':             () => import('../fonts/px/font.css'),
  'px-sams-club':   () => import('../fonts/px-sams-club/font.css'),
  'bodega':         () => import('../fonts/bodega/font.css'),
};

const TEXT_FONT_IMPORTERS: Record<ThemeFontConfig['textFont'], FontImporter> = {
  'everyday-sans': () => import('../fonts/everyday-sans/font.css'),
  'gibson':        () => import('../fonts/gibson/font.css'),
  'bogle':         () => import('../fonts/bogle/font.css'),
};

const _loadedFonts = new Set<string>();

export function loadIconFont(fontKey: string): void {
  if (_loadedFonts.has(fontKey)) return;
  _loadedFonts.add(fontKey);
  const importer = FONT_IMPORTERS[fontKey];
  if (importer) importer();
}

function loadTextFont(fontKey: ThemeFontConfig['textFont']): void {
  const cacheKey = `text:${fontKey}`;
  if (_loadedFonts.has(cacheKey)) return;
  _loadedFonts.add(cacheKey);
  const importer = TEXT_FONT_IMPORTERS[fontKey];
  if (importer) importer();
}

export function loadThemeFonts(theme: ThemeName): void {
  const config = THEME_FONT_CONFIG[theme];
  if (!config) return;

  loadTextFont(config.textFont);

  for (const fontKey of config._loadFonts) {
    loadIconFont(fontKey);
  }
}

/* ── Theme Application ────────────────────────────────────────── */

export function applyTheme(theme: ThemeName): void {
  document.documentElement.setAttribute('data-ld-theme', theme);
  loadThemeFonts(theme);

  try { localStorage.setItem(STORAGE_KEY, theme); } catch {}

  window.dispatchEvent(new CustomEvent(THEME_CHANGE_EVENT, { detail: { theme } }));
}

/* ── Global API ───────────────────────────────────────────────── */

declare global {
  interface Window {
    ldKit?: {
      setTheme: (name: string) => void;
      getTheme: () => string;
      getThemeNames: () => string[];
      THEME_PRESETS: Record<string, ThemePreset>;
      THEME_NAMES?: readonly ThemeName[];
    };
  }
}

function installThemeApi(
  initialTheme: ThemeName,
  allowedThemes: readonly ThemeName[],
): void {
  let activeTheme = initialTheme;

  window.ldKit = {
    setTheme(name: string) {
      if (!isThemeName(name, allowedThemes)) return;
      activeTheme = name;
      applyTheme(name);
    },
    getTheme() {
      return activeTheme;
    },
    getThemeNames() {
      return [...allowedThemes];
    },
    THEME_PRESETS,
    THEME_NAMES: allowedThemes,
  };
}

/* ── React Hook ───────────────────────────────────────────────── */

// Theme contract for agents:
// - Set the theme in App.tsx by changing the name in useInitializeTheming().
// - Pass a single-element array as allowedThemes to lock to one brand.
//   e.g. useInitializeTheming("Sam's Club", ["Sam's Club"] as const)
// - Do NOT pass THEME_NAMES as allowedThemes — localStorage can override the default.
// - Runtime switching: window.ldKit.setTheme("<Theme Name>")
export function useInitializeTheming(
  defaultTheme: ThemeName = DEFAULT_THEME,
  allowedThemes: readonly ThemeName[] = THEME_NAMES,
): void {
  React.useEffect(() => {
    const initialTheme = resolveInitialTheme(defaultTheme, allowedThemes);
    applyTheme(initialTheme);
    installThemeApi(initialTheme, allowedThemes);
  }, [allowedThemes, defaultTheme]);
}
