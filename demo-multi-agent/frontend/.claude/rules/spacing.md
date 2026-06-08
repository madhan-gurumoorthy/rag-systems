
# Spacing Implementation Guide

## Token Definitions in `src/themes/base.css`

Spacing tokens are defined in `:root` inside `src/themes/base.css`. There are three tiers:

### Primitive Scale (`--ld-primitive-scale-space-*`)

| Token | Value |
|-------|-------|
| `space-25` | 0.125rem (2px) |
| `space-50` | 0.25rem (4px) |
| `space-100` | 0.5rem (8px) |
| `space-150` | 0.75rem (12px) |
| `space-200` | 1rem (16px) |
| `space-250` | 1.25rem (20px) |
| `space-300` | 1.5rem (24px) |
| `space-400` | 2rem (32px) |
| `space-500` | 2.5rem (40px) |
| `space-600` | 3rem (48px) |
| `space-700` | 3.5rem (56px) |
| `space-800`–`space-1000` | 4rem–5rem |

### Semantic Spacing (`--ld-semantic-spacing-*`)

Aliases that reference primitives:
- `component-padding-{small,medium,large}`: 8px / 12px / 16px
- `component-gap-{small,medium,large}`: 8px / 12px / 16px
- `layout-{margin,padding}-{small,medium,large}`: 16px / 24px / 32px
- `section-gap-{small,medium,large}`: 24px / 32px / 48px
- Raw scale: `--ld-semantic-spacing-25` through `--ld-semantic-spacing-1000`

---

## How Each Component Layer Actually Handles Spacing

The three component directories (`core/`, `shared/`, `CX/`) each use **different** spacing conventions. This is how the project actually works — match the layer you're working in.

### `src/components/core/` — Hardcoded rem values, no tokens

Core LD primitives (Button, Card, Alert, etc.) use **direct rem values** with no spacing token references. Only 1 of 45 core CSS files references a spacing token.

```css
/* Card — size variants use raw rem */
.ld-card-cardheader-large  { margin: 1.5rem 0; padding: 0 1.5rem; }
.ld-card-cardheader-small  { margin: 1rem 0;   padding: 0 1rem; }
.ld-card-cardheader-leadingIcon { margin-right: 0.5rem; }

/* Button — sizes use raw rem */
.ld-button-small  { height: 2rem;   padding: 0 1rem; }
.ld-button-medium { height: 2.5rem; padding: 0 1.5rem; }
.ld-button-large  { height: 3rem;   padding: 0 1.5rem; }
.ld-button-leading  { margin-right: 0.5rem; }
.ld-button-trailing { margin-left: 0.5rem; }
.ld-button-buttongroup-buttonGroup { display: flex; gap: 1rem; }

/* Alert — raw rem, asymmetric shorthand */
.ld-alert-alert   { padding: 0.4375rem 1rem 0.4375rem 0.75rem; }
.ld-alert-content { gap: 0.25rem 1rem; }
.ld-alert-leading { margin-right: 0.5rem; }
```

**Pattern: When editing core/ CSS, use raw rem. Do not introduce token vars.**

### `src/components/shared/` — Token vars with rem fallbacks

Shared components (Carousel, Command, Menubar, Pagination, etc.) use **spacing tokens with rem fallbacks**. About half of the 20 shared CSS files use tokens.

```css
/* Carousel — tokens with rem fallbacks */
.ld-carousel-content    { gap: var(--ld-primitive-scale-space-200, 16px); }
.ld-carousel-pagination { gap: var(--ld-primitive-scale-space-100, 8px); padding-top: var(--ld-primitive-scale-space-200, 16px); }

/* Command — tokens with px fallbacks */
.ld-command-input-wrap { padding: 0 var(--ld-primitive-scale-space-200, 16px); }
.ld-command-item       { padding: var(--ld-primitive-scale-space-100, 8px) var(--ld-primitive-scale-space-200, 16px); }

/* AlertDialog — tokens with rem fallbacks */
.ld-alertdialog-content { padding: var(--ld-primitive-scale-space-300, 1.5rem); gap: var(--ld-primitive-scale-space-200, 1rem); }
```

**Pattern: When editing shared/ CSS, use `var(--ld-primitive-scale-space-*, fallback)`. Fallback unit can be rem or px — match what's already in the file.**

### `src/components/CX/` (WCP) — Mostly hardcoded px, tokens in select files

CX/WCP components (WCPFlag, WCPItemTile, WCPHeader, etc.) **overwhelmingly use hardcoded pixel values**. Only 7 of 56 CX CSS files reference spacing tokens. The rest use raw px.

```css
/* WCPFlag — all hardcoded px */
.ld-wcp-flag-flag { gap: 4px; padding: 4px 8px; min-height: 28px; }

/* WCPItemTile — all hardcoded px */
.ld-wcp-itemtile-imageWrapper { padding: 24px 8px 8px; }
.ld-wcp-itemtile-body         { padding: 8px 8px 8px; gap: 2px; }
.ld-wcp-itemtile-priceRow     { gap: 1px; }

/* WCPQueueCard — all hardcoded px */
.ld-wcp-queuecard-content    { padding: 16px; gap: 8px; }
.ld-wcp-queuecard-timerRow   { gap: 8px; }
.ld-wcp-queuecard-productRow { gap: 12px; }

/* WCPHeader — all hardcoded px */
.ld-wcp-desktop-header-root    { padding: 16px 24px; }
.ld-wcp-desktop-header-content { gap: 24px; }
.ld-wcp-desktop-header-gic-button { padding: 4px 16px 4px 12px; gap: 8px; }
```

The 7 files that do use tokens (WCPSearchBar, WCPRichSnackbar, WCPButtonGroup, WCPRichMediaSheet, WCPUploadImage, WCPTimerView, WCPBasicBanner) use them with px fallbacks:

```css
/* WCPSearchBar — one of the few CX files using tokens */
.ld-wcp-searchbar-wrapper { gap: var(--ld-primitive-scale-space-250, 20px); }
.ld-wcp-searchbar-pill    { padding: var(--ld-primitive-scale-space-150, 12px); }
```

**Pattern: When editing CX/ CSS, use hardcoded px to match existing convention. If the specific file already uses tokens, follow its lead.**

---

## Spacing Patterns Across All Layers

### Flex Gap Over Margins

All layers prefer `gap` on flex/grid containers over `margin` on children:

```css
.ld-button-buttongroup-buttonGroup { display: flex; gap: 1rem; }        /* core */
.ld-carousel-content { display: flex; gap: var(--ld-primitive-scale-space-200, 16px); } /* shared */
.ld-wcp-queuecard-content { display: flex; flex-direction: column; gap: 8px; }         /* CX */
```

Margin-bottom with `:last-child` reset only appears in core/ for vertical stacking:
```css
.ld-formgroup-formGroupRow { margin-bottom: 0.75rem; }
.ld-formgroup-formGroupRow:last-child { margin-bottom: 0; }
```

### Icon/Element Inline Spacing

Consistent 0.5rem margin for leading/trailing icons in core components:
```css
.ld-card-cardheader-leadingIcon { margin-right: 0.5rem; }
.ld-button-leading  { margin-right: 0.5rem; }
.ld-button-trailing { margin-left: 0.5rem; }
.ld-alert-leading   { margin-right: 0.5rem; }
```

CX components use hardcoded px gaps instead of margins for icon spacing:
```css
.ld-wcp-flag-flag { gap: 4px; }           /* icon + label */
.ld-wcp-desktop-header-gic-button { gap: 8px; }  /* icon + text */
```

### Micro Spacing for Typography Alignment

WCP product cards use 1-2px gaps for precise price/superscript alignment:
```css
.ld-wcp-itemtile-priceRow { gap: 1px; }
.ld-wcp-itemtile-body { gap: 2px; }
.ld-wcp-itemtile-prefix { margin-right: 2px; }
```

### Asymmetric Padding

WCP cards and headers use asymmetric padding intentionally for visual balance:
```css
.ld-wcp-desktop-header-gic-button { padding: 4px 16px 4px 12px; }
.ld-wcp-desktop-footer-links-section { padding: 16px 40px 32px; }
.ld-wcp-order-card-footer { padding: 10px 16px; }
```

### Size Variant Scaling (Core Only)

Core LD components propagate size via React Context. Spacing scales with the variant:

| Size | Padding | Gap |
|------|---------|-----|
| Small | 1rem | 0.5rem |
| Large | 1.5rem | 1rem |

```tsx
const size = React.useContext(CardSizeContext);
className={cx('ld-card-cardheader-container', size === 'large' && 'ld-card-cardheader-large')}
```

---

## Responsive Spacing

### Responsive Layout Guardrails (Required)

These rules exist to prevent mobile-only layouts from being shipped as full pages.

- **MUST build page shells mobile-first but fluid**: base styles should work at small widths, then expand at breakpoints.
- **MUST use `Container` for body content** (header/footer can remain full-bleed).
- **MUST set `sm` + `md` + `lg` on each `GridColumn`** when using `Grid`.
- **MUST use `<Grid hasGutter>`** for multi-column layouts.
- **MUST keep main content width flexible** (`width: '100%'`) and constrain media/cards with `maxWidth` wrappers.

- **NEVER lock a page to phone width** (`maxWidth: 375`, `width: 390`, etc.) unless the user explicitly asks for a mobile-only prototype.
- **NEVER hardcode desktop section widths** for layout structure (for example `width: 1200px` on the main content wrapper).
- **NEVER rely on `overflowX: 'hidden'` to mask responsive breakage.**

### Page Shell Pattern

```tsx
// CORRECT — responsive shell (mobile-first, desktop-ready)
<div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
  <WCPHeader />
  <Container>
    {/* page sections */}
  </Container>
  <WCPDesktopFooter />
</div>

// WRONG — locked to mobile viewport width
<div style={{ maxWidth: 375, margin: '0 auto' }}>
  <WCPHeader />
  {/* content */}
</div>
```

### Grid Breakpoint Pattern

```tsx
// CORRECT — stacks on mobile, splits on tablet/desktop
<Grid hasGutter>
  <GridColumn sm={12} md={6} lg={6}>...</GridColumn>
  <GridColumn sm={12} md={6} lg={6}>...</GridColumn>
</Grid>

// WRONG — missing breakpoints, layout never becomes responsive
<Grid hasGutter>
  <GridColumn>...</GridColumn>
  <GridColumn>...</GridColumn>
</Grid>
```

Mobile-first. CX components that respond to breakpoints:

```css
/* WCPSearchBar — mobile 12px, desktop asymmetric 8px/16px */
.ld-wcp-searchbar-pill { padding: var(--ld-primitive-scale-space-150, 12px); }
@media (min-width: 56.25rem) {
  .ld-wcp-searchbar-pill {
    padding: var(--ld-primitive-scale-space-100, 8px) var(--ld-primitive-scale-space-200, 16px);
  }
}

/* Core Panel — mobile 1rem, tablet 1.5rem */
.ld-panel-panelportal-contentInner { padding: 1rem; }
@media screen and (min-width: 37.5rem) {
  .ld-panel-panelportal-contentInner { padding: 1.5rem; }
}
```

**Canonical breakpoints (the only ones allowed in this project, sourced from Airtable view `viw3aImoD7tLBVm7S` → `src/themes/base.css`):**

| Token | Pixel | rem (use in `@media`) |
|-------|------:|----------------------:|
| `--ld-primitive-scale-breakpoint-small`   |    0px |        — |
| `--ld-primitive-scale-breakpoint-medium`  |  600px |  37.5rem |
| `--ld-primitive-scale-breakpoint-large`   |  900px | 56.25rem |
| `--ld-primitive-scale-breakpoint-xLarge`  | 1200px |    75rem |
| `--ld-primitive-scale-breakpoint-xxLarge` | 1920px |   120rem |

**Never invent custom widths** like 768px or 1024px — every responsive media query must align to one of the five values above. CSS `@media` queries cannot consume `var()`, so use the matching rem literal (e.g. `@media screen and (min-width: 37.5rem)`). For JS-side logic, read the variable from `:root` via `getComputedStyle`.

## Carousel Overhang Pattern

Padding + negative margin trick for shadow overflow:
```css
.ld-wcp-flash-deals-carousel-scroll {
  gap: 12px;
  padding: 40px 0;   /* room for shadows */
  margin: -40px 0;    /* pull back to not affect layout */
  overflow-x: auto;
}
```

---

## Page-Level Spacing (Demo Pages)

Demo pages in `src/pages/` use **inline styles** for layout. Do not move page layout spacing into CSS files.

- **PageWrapper** hero: `padding: 32px 40px 24px`, max-width `1400px`
- **PageWrapper** content: `padding: 32px 40px 48px`
- **ExampleSection** bottom margin: `24px`; title-to-content: `16px`
- **ExampleCard** padding: `32px`

Within demo containers, use inline styles:
```tsx
<div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, maxWidth: 430 }}>
<div style={{ display: 'flex', gap: 8, padding: 12, overflowX: 'auto' }}>
<div style={{ background: '#f8f8f8', borderRadius: 12, padding: 16 }}>
```

---

## Page Section Spacing

When composing full pages, use these consistent spacing conventions between sections:

### Section Vertical Rhythm

| Between | Spacing | How |
|---------|---------|-----|
| Content sections | 32px | `marginBottom: 32` on section wrappers |
| Major zones (hero → content, content → footer) | 48px | `marginTop: 48` or `marginBottom: 48` |
| Content and a Divider | 24px | Wrap `<Divider />` in `<div style={{ margin: '24px 0' }}>` |
| Stacked banners on mobile | 16px | Use `gap: 16` on parent or `marginBottom: 16` |
| Section title to content | 16px | `marginBottom: 16` on the heading row |

### Divider Requires Margin

`Divider` renders as a 1px line with `margin: 0`. It will visually collide with adjacent sections unless you add explicit spacing:

```tsx
// CORRECT — Divider breathes
<section style={{ marginBottom: 32 }}>
  {/* deals section */}
</section>
<div style={{ margin: '24px 0' }}>
  <Divider />
</div>
<section style={{ marginTop: 8 }}>
  {/* next section */}
</section>

// WRONG — no breathing room
<Section title="Deals">...</Section>
<Divider />
<Section title="Popular">...</Section>
```

### Product Row Spacing

Product carousels (`WCPFlashDealsCarousel`, `Carousel`) include internal padding for card shadows. When stacking multiple product rows, use 32px vertical spacing between them. Do not add extra top/bottom padding inside the carousel — it handles its own overhang.

### Full Page Template

```tsx
        <WCPHeader />
<Container>
  <section style={{ margin: '24px 0' }}>{/* Hero */}</section>
  <section style={{ marginBottom: 32 }}>{/* Category nav */}</section>
  <div style={{ margin: '24px 0' }}><Divider /></div>
  <section style={{ marginBottom: 32 }}>{/* Product row 1 */}</section>
  <div style={{ margin: '24px 0' }}><Divider /></div>
  <section style={{ marginBottom: 32 }}>{/* Product row 2 */}</section>
  <div style={{ marginTop: 48 }} />
</Container>
<WCPDesktopFooter ... />
```

## Rules Summary

1. **Match the layer convention** — core/ uses rem, shared/ uses tokens with fallbacks, CX/ uses hardcoded px
2. **Prefer flex `gap`** over margin for grouped children
3. **0.5rem icon margins in core/**, `gap` in CX/ — do not mix conventions within a layer
4. **Asymmetric padding is expected** in CX/ components
5. **1-4px micro spacing** is always hardcoded, no tokens
6. **Page layout uses inline styles**, component spacing uses CSS classes
7. **Carousel overhang**: `padding: Npx 0; margin: -Npx 0;` for shadow overflow
8. **Mobile-first responsive** — tighter on mobile, expand at breakpoints
9. **Divider needs margin** — always wrap with `margin: '24px 0'`
10. **32px between sections**, 48px between major page zones
11. **No fixed-width page shells** — do not lock entire pages to phone widths
12. **No breakpointless grids** — always define `sm`/`md`/`lg` on `GridColumn`
