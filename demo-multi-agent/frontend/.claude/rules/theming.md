
# Living Design Theming Guide (Skill/IDE)

Use this file as the source of truth for theme behavior in the synced Skill/IDE project.

## Required Agent Workflow

1. Pick the theme before writing UI code.
2. If no brand is requested, keep the default theme: `Walmart`.
3. Use exact theme names from the supported list below (do not invent new labels).
4. **For brand-specific builds, update the theme name in `src/App.tsx`** — see "Setting the Theme in App.tsx" below.

## Setting the Theme in App.tsx

The active theme is set in the `useInitializeTheming` call inside `src/App.tsx`.
To change brands, update **both** occurrences of the theme name (the default and the allowed list):

```tsx
// Before (Walmart):
useInitializeTheming('Walmart', ['Walmart'] as const);

// After (Sam's Club):
useInitializeTheming("Sam's Club", ["Sam's Club"] as const);
```

**CRITICAL**: The second argument must be a single-element array matching the first argument.
Passing `THEME_NAMES` (all themes) allows localStorage to override your chosen theme with a previously stored value.

## Runtime API (Optional)

For runtime theme switching (e.g. a theme picker), use the global API:

```js
window.ldKit.setTheme("Sam's Club");
window.ldKit.getTheme();      // current theme name
window.ldKit.getThemeNames(); // allowed theme names
```

## Supported Themes

| Name | Primary Color | Description |
| --- | --- | --- |
| Walmart | `#0053e2` | Default Walmart theme |
| Sam's Club | `#0062ad` | Member warehouse club |
| Walmart B2B | `#002e99` | Business platform with navy identity |
| Bodega | `#2c981d` | Walmart Mexico retail (green) |
| Cashi MX | `#6212b2` | Mexico financial services (purple) |
| Data Ventures | `#6245b7` | Partner analytics platform (purple) |
| Sparky | `#001e60` | Internal tools (dark navy + cyan) |
| Walmart Legacy | `#0071dc` | Classic Walmart brand |
| Walmart+ | `#0053e2` | Membership with yellow accents |
| Member's Mark | `#283645` | Sam's Club private label |

## Font & Body Styling

The theme system is CSS-driven:

1. **`src/themes/base.css`** — declares all `@font-face` rules (Everyday Sans UI, EverydaySansMono, Gibson, Bogle, LivingDesign icons) with base64-embedded woff2 data, plus base reset styles.
2. **Per-theme CSS files** (`src/themes/walmart.css`, `src/themes/sams-club.css`, etc.) — override CSS variables scoped to `[data-ld-theme="ThemeName"]`, including `--ld-primitive-font-family-sans` for branded fonts.
3. **`src/themes/index.css`** — single import that loads base + all theme CSS.
4. **`useInitializeTheming()`** — sets the `data-ld-theme` attribute on `<html>`, triggering the correct CSS cascade.

**Critical**: The `body` element references the CSS variable so page-level text uses the themed font. This is set in `base.css`:

```css
html, body, #root {
  font-family: var(--ld-primitive-font-family-sans, 'Everyday Sans UI', -apple-system, Roboto, sans-serif);
}
```

- NEVER remove or override this rule — it bridges the theme CSS and page rendering.
- NEVER set `font-family` on individual elements with hardcoded values — let the CSS variable cascade.
- If text appears in the browser default font (serif), the base.css import is missing.

## Runtime Contract

- Storage key: `ld-kit-theme`
- Theme API: `window.ldKit`
- Change event: `ld-kit-theme-change`
- Theme runtime module: `src/utils/Theming.tsx`
- App wiring entry point: `src/App.tsx`
