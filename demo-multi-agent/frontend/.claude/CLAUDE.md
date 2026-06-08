
# Living Design Skill/IDE Starter

**This project is a responsive, mobile-first web application.** All UI must adapt seamlessly from mobile (small, 0px) through tablet (medium, 600px), desktop (large, 900px), wide desktop (xLarge, 1200px), and extra-wide (xxLarge, 1920px). These five values are the only allowed responsive breakpoints — see the breakpoint table below. Your primary job is to compose UI from the existing components in `src/components/ld/`. Only create net-new components when nothing in the library satisfies the requirement — and even then, build them on top of existing components.

## Required Reading — Follow These Steps IN ORDER

Before writing any code, locate and read the guideline files. They exist in one of these directories depending on your tool:

| Tool | Rules directory |
|------|----------------|
| Cursor | `.cursor/rules/` (`.mdc` files) |
| Claude Code | `.claude/rules/` (`.md` files) |
| GitHub Copilot (VS Code) | `.github/instructions/` (`.instructions.md` files) |

Read these files **in order** from the rules directory for your tool:

1. **`theming`** — Theme selection, runtime API, supported brands. Set the active theme first.
2. **`overview-components`** — Full component inventory with import paths and prop APIs.
3. **`a11y`** — Binding accessibility directive. Hard MUST/NEVER rules, opt-out contract, pre-response checklist. The dev-only runtime scanner enforces many of these — read this BEFORE writing UI so you don't fight it.
4. **`living-design-guidelines`** — Coding directive: component selection flow, hard constraints, and anti-patterns.
5. **`component-communication`** — Component communication via Store.tsx: shared state, product bindings (`useStoreConnectedItemBindings`), header bindings (`useHeaderCartBindings`), cart/favorites/search patterns, and `addToCart` vs `setCartQty` rules.
6. **`spacing`** — Spacing + responsive layout guardrails: mobile-first breakpoints, section rhythm, grid rules, and anti-patterns like fixed-width page shells.

## Dev Feedback Loop (IMPORTANT for verifying your work)

This project ships a **runtime accessibility scanner** that runs in the browser during `npm run dev` and surfaces violations through four parallel channels — one for humans, three for agents/automation. When violations exist, an unmissable in-page overlay covers the app; the user can read it, copy it, and paste it back to you if you missed it.

Before marking any UI task complete:

1. Start the dev server: `npm run dev` (prefer `run_in_background=true` so you can keep coding).
2. Load the page at least once — from a browser, browser-automation MCP, or any agent that actually executes JavaScript. A plain `curl /` is NOT enough; the scanner runs in the browser, not on the server.
3. Check for violations through ANY of:
   - **In-page overlay** — a full-viewport red-bordered card titled `LD A11Y` covers the app whenever violations exist. Includes the violation list, a copy button, and the inspect commands. This is what your USER sees if you ship a defect; they can click "Copy violations" and paste it back to you.
   - **`cat .ld-a11y-report.json`** — structured JSON snapshot at project root, rewritten on every scan.
   - **`curl http://localhost:<port>/__ld_a11y_report`** — live snapshot endpoint.
   - **`npm run dev` stdout** — violations print as a red `LD A11Y` banner with numbered issues.
4. Fix every listed violation. Do NOT add `data-ld-a11y-ignore` to silence the scanner — the only legitimate use for that attribute is an intentional opt-out the user approved.
5. Re-load the page. When the scanner is clean, the overlay disappears and the dev server logs `[LD a11y] All violations resolved.`

See the `a11y` rules file for the full directive, the opt-out contract (`unsafeDecorative={{ reason }}`), and the pre-response checklist.

## Component Hierarchy (Atomic Design)

| Level | Prefix | What they are | Examples |
|-------|--------|---------------|----------|
| **Atoms** | (none) | Smallest UI primitives | `Button`, `TextField`, `Badge`, `Chip`, `Tag`, `Link` |
| **Molecules** | (none) | Small compositions of atoms | `Card`, `FormGroup`, `Alert`, `Modal`, `Menu`, `Select` |
| **Organisms** | `WCP` | Domain-specific UI sections | `WCPItemTile`, `WCPHeader`, `WCPSearchBar` |

**Always start at the highest level that fits.** If a WCP organism already does what you need, use it. Don't rebuild it from lower-level pieces.

## How to Build UI

### 1. Select from existing components (default path)

1. Look up the component and its prop API in the `overview-components` rules file.
2. Follow the component selection flow and intent router in the `living-design-guidelines` rules file.
3. Import from `src/components/ld/` using relative paths — never from `@livingdesign/react` directly.
4. Read the component file's JSDoc before first use — it has usage examples, variant semantics, and accessibility guidance.
5. Compose and wire up props.

### 2. Use WCP Organisms First (critical for pages)

Before building ANY page section, check for a WCP organism component that already handles it. These are complete, responsive, production-quality sections:

- **Headers**: `WCPHeader`
- **Footers**: `WCPDesktopFooter`, `WCPMwebFooter`
- **Product rows**: `WCPFlashDealsCarousel` (built-in flash deals row) or `Carousel` + `WCPCarouselProductCard` (custom product data)
- **Product cards**: `WCPProductCardGrid` (responsive grid), `WCPProductCardList` (list), `WCPCarouselProductCard` (carousel item)
- **Banners**: `WCPSkylineBanner`, `WCPBasicBanner`, `WCPOrderStatusBanner`
- **Navigation**: `WCPSearchBar`, `WCPSearchFilterBar`, `WCPBottomNav`

**NEVER build a custom footer, header, or product carousel when a WCP component exists.** Check the `overview-components` rules file first.

### 3. Build Responsive Layouts (Mobile-First)

**This is a responsive site.** All pages MUST render correctly across mobile, tablet, and desktop. Design mobile-first, then layer on wider breakpoints.

#### Breakpoints

The Living Design design system defines exactly **five canonical breakpoints**. They are emitted into `src/themes/base.css` as `--ld-primitive-scale-breakpoint-*` from Airtable and are the single source of truth — **never invent your own values like 768px, 1024px, etc.**

| Token (CSS var) | Pixel | rem | `<GridColumn>` shorthand | Target | Use for |
|-----------------|------:|----:|--------------------------|--------|---------|
| `--ld-primitive-scale-breakpoint-small`   |    0px |        — | `sm` | Mobile (phones) | Single-column stacks, full-width cards, bottom nav |
| `--ld-primitive-scale-breakpoint-medium`  |  600px |  37.5rem | `md` | Tablet | 2-column grids, side-by-side layouts |
| `--ld-primitive-scale-breakpoint-large`   |  900px | 56.25rem | `lg` | Desktop | Multi-column grids (3–4 cols), expanded nav, wider containers |
| `--ld-primitive-scale-breakpoint-xLarge`  | 1200px |    75rem | _(raw media query)_ | Wide desktop | Container max-width activation, content reflow |
| `--ld-primitive-scale-breakpoint-xxLarge` | 1920px |   120rem | _(raw media query)_ | Extra-wide / TV | Hero scale-up, oversized media |

CSS `@media` queries cannot read `var()`. Use the rem literal that matches the token (e.g. `@media screen and (min-width: 56.25rem)` for `large`). For JS-side responsive logic, read the CSS variable from `:root` via `getComputedStyle(document.documentElement).getPropertyValue('--ld-primitive-scale-breakpoint-medium')`.

`<GridColumn>` only exposes three breakpoint props (`sm`/`md`/`lg`); for `xLarge` / `xxLarge` adjustments, write a raw `@media` query alongside the grid.

#### Layout rules

- **Wrap EVERY section in `Container`** — it provides responsive max-width, centering, and horizontal padding (24px on each side). Without it, content stretches edge-to-edge with no breathing room. The ONLY exceptions are headers and footers: `WCPHeader`, `WCPDesktopFooter`, `WCPMwebFooter`. Everything else — including `WCPNewArrivalsCarousel`, carousels, banners, and card grids — MUST be inside `Container`.
- **Product sections** should use horizontal scrolling carousels (Walmart pattern), not single-column grids. Use `WCPFlashDealsCarousel` for built-in flash deals, or `Carousel` + `WCPCarouselProductCard` with Store bindings for custom product data. Do NOT invent an `items` prop on `WCPFlashDealsCarousel`.
- **For product grids** (browse pages), use `WCPProductCardGrid` in `Grid`/`GridColumn` — NOT `WCPItemTile` which has a fixed 200px max-width and won't fill grid columns.
- **Grid must use `hasGutter`** — always pass `<Grid hasGutter>`. Without it, columns have no spacing and cards stack with zero gap.
- **Grid breakpoints are required**: Always set `sm`, `md`, **and** `lg` on every `GridColumn`. Example: `<GridColumn sm={12} md={6} lg={4}>` (full-width → half → third).
- **Section spacing**: 32px between sections, 24px margin around `Divider` components (they have `margin: 0` by default).

#### Responsive anti-patterns (do NOT do these)

- **Fixed pixel widths** on page-level containers or sections — use `Container` and `Grid` instead.
- **Desktop-only layouts** that ignore `sm` — every layout must be usable at 320px.
- **Hiding content with `display: none`** at breakpoints instead of reflowing it — reflow, stack, or collapse content; don't just hide it.
- **Hardcoded column counts** without breakpoint props — always specify `sm`, `md`, and `lg` on `GridColumn`.

### 4. Create a net-new component (only when nothing fits)

1. Build a new React component **outside** `src/components/ld/` (that directory is generated/read-only).
2. **Maximize reuse** — import and compose existing components from `src/components/ld/`.
3. **Must be responsive** — every new component must work at `sm`, `md`, and `lg` breakpoints. Use `Grid`/`GridColumn` with breakpoint props or CSS media queries that follow the breakpoint table above. Test that it stacks correctly on mobile and expands on desktop.
4. Keep portable-safe imports (React + local relative files only).

### 5. Cart & Product Interaction Rules

- **ONE add-to-cart control per product** — never render both a `QuantityStepper` and a separate "Add to cart" `Button` for the same item. Use conditional rendering: show the "Add to cart" button when `cartQty === 0`, switch to `QuantityStepper` once added.
- **ALL product state from Store bindings** — use `useStoreConnectedItemBindings()` for every product on the page, including the "main" product on a PDP. NEVER create local `useState` for `qty` or `hearted` that duplicates Store state.
- **QuantityStepper onChange → `setCartQty`** — QuantityStepper passes the new absolute count. NEVER pass it to `addToCart` (which increments). Use `onCartQtyChange` from bindings or `setCartQty` directly.
- **Flash Deals caveat** — `WCPFlashDealsCarousel` is a built-in, fixed-data organism. If you need custom products, build a Store-connected `Carousel` with `WCPCarouselProductCard` + `useStoreConnectedItemBindings()`.
- **Button sizing** — use `size="medium"` for primary cart actions. `size="large"` is rarely appropriate and creates oversized controls.

## Project Structure for New Work

Where you put the files you create matters. This project is the base of a vibe-coding kit: output must land in predictable folders so maintainers can later lift folders wholesale back into the base kit. Follow these rules strictly.

### Pages

- **Location**: `src/pages/<PageName>.tsx`
- **Naming**: PascalCase, one file per page (e.g., `CartPage.tsx`, `ProductDetailPage.tsx`, `SupplyChainDashboardPage.tsx`).
- **Shape**: export a default React component. Inline styles are fine for page-level layout (this matches existing page-level spacing guidance in `spacing`).
- **Never** put page modules anywhere else (not `src/`, not `src/components/`).

### Custom components — decision tree

Use this decision tree for every net-new component:

1. **Does the user's prompt name a clear domain, brand, or feature?** (Examples: `walmart-business`, `supply-chain`, `sams-club`, `pharmacy`, `checkout`, `account`.)
   → Place the component in `src/components/<kebab-case-domain>/<ComponentName>.tsx`.
   Use the same folder for every component that belongs to that feature so the folder can be reintegrated as a unit.
2. **Otherwise** (generic, exploratory, or unclear domain)
   → Place the component in `src/components/custom/<ComponentName>.tsx`.

### Page wiring

- **Default — App.tsx swap**: render the active page from `src/App.tsx`. When you add a new page, import it and render it in place of the previous page. Do not add a router unless the ask needs one.
- **Multi-page / navigation asks**: when the ask implies multiple pages with navigation between them (e.g., "build a checkout flow with cart, shipping, and confirmation pages"), install `react-router-dom` and wire routes in `src/App.tsx`. Keep page files in `src/pages/` unchanged — only the entry gains a `<BrowserRouter>` with `<Routes>`.

### Hard rules

- **NEVER** create files under `src/components/ld/`. That folder is generated by `npm run build:portable` and will be overwritten.
- **NEVER** create a parallel `ld/` folder anywhere else.
- **NEVER** put pages under `src/components/`, and **NEVER** put reusable components under `src/pages/`.
- **ALWAYS** use relative imports to `src/components/ld/` from new files (`../ld/*`, `../../ld/*`, etc.) — same rule as elsewhere in this project.
- **ALWAYS** scope feature work to a single feature folder. If two feature folders would share a component, lift the shared piece into `src/components/custom/` rather than cross-importing between feature folders.

## Key Constraints

- **Do not edit** files under `src/components/ld/` — they are generated output.
- **Do not recreate** an existing component with raw HTML or another UI library.
- **Do not omit** required props — read the component API first.
- Import using relative paths (`./ld/*`, `../ld/*`, `./components/ld/*`). One component per import line.
- Full constraint details and required prop/a11y invariants are in the `living-design-guidelines` rules file.

## Project Layout

- **Living Design components**: `src/components/ld/` — generated Living Design wrappers (read-only)
- **Your pages**: `src/pages/<PageName>.tsx` — one file per page
- **Your custom components (default)**: `src/components/custom/<ComponentName>.tsx`
- **Your feature-scoped components**: `src/components/<feature-name>/<ComponentName>.tsx` — when the ask names a domain (kebab-case folder)
- **Helpers**: `src/utils/` — shared utilities including `Theming.tsx`
- **App entry**: `src/App.tsx` — calls theme runtime, renders app
- **Guidelines**: `.claude/rules/` — agent directives and component docs

## Tech Stack

- **Package manager**: NPM
- **Frontend**: React 18 + TypeScript + Vite
- **UI library**: Living Design (`@livingdesign/react`) via local wrapper files in `src/components/ld/`
- **Theming**: `src/utils/Theming.tsx` (called from `src/App.tsx`)

## Development Commands

```bash
npm run dev        # Start Vite dev server
npm run build      # Production build
npm run preview    # Preview the production build
```
