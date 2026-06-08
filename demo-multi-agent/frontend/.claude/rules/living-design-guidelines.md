
# Living Design Coding Agent Directive

Use this file as binding policy when generating UI code.

This project uses a custom design system called **Living Design** installed via the `@livingdesign/react` npm package. Files in the `.claude/rules/` directory explain how to use Living Design correctly.

## Component Domains (Core vs WCP)

Living Design in this repo includes two domains of components:

- **Core components**: reusable building blocks used across many product experiences.
- **WCP components**: components prefixed with `WCP` that belong to **Walmart Common Platform**, focused on Walmart ecommerce experiences.
- **WCP pattern components** — `WCPHeader` for header/navigation patterns

Treat both as first-class Living Design components. Use the component that best matches intent and domain context. For detailed component inventory and prop APIs, rely on `overview-components.md`; for theme and brand setup, rely on `theming.md`.

## Required Reading — Follow These Steps IN ORDER

IMPORTANT: Always prefer Living Design components over raw HTML or other UI libraries. Before writing any code, complete these steps in order:

**Step 1: Read Theme Guide (REQUIRED)**
Read `theming.md` and set the active theme before writing UI code.

Default behavior when no brand is requested:
- Use `Walmart`
- Theme runtime is in `src/utils/Theming.tsx` (called from `src/App.tsx`)

**Step 2: Read Overview Files (REQUIRED)**
Read ALL files whose name starts with `overview-` in the `.claude/rules/` directory:
- `overview-components.md` — lists every available Living Design component with its import path and prop API

(Read any other `overview-*` files that appear in the future.)

**Step 3: Plan What Components You Need (REQUIRED)**
After reading the overview files, decide which Living Design components satisfy each requirement. Choose components by intent, not visual resemblance.

**Step 4: Write Code Following the Guidelines Below**

## Objective

Build UI with Living Design components by default.
Custom HTML/CSS is allowed only when no Living Design component can satisfy the requirement.

## Priority Order

1. Correct component semantics for user intent.
2. Required props and accessibility invariants.
3. Component reuse over custom implementation.
4. Minimal, maintainable code.

## Hard Constraints

- MUST map each requirement to a Living Design component before writing code.
- MUST choose components by intent, not by visual resemblance.
- MUST default theme to `Walmart` unless the request explicitly names another supported theme from `theming.md`.
- MUST use exact theme names when switching themes (do not invent new labels).
- MUST use Living Design companion components where applicable (for example, `ButtonGroup`, `FormGroup`).
- MUST keep controlled components controlled when the API expects state (`isOpen`, `value`, `checked`, and similar).
- MUST include required a11y labels and relationships.
- MUST ask before introducing a custom component fallback.
- MUST treat `src/components/ld` as the default and canonical location for Living Design components in this repo.

- NEVER recreate an existing Living Design component with raw HTML.
- NEVER switch to another UI library for equivalent primitives.
- NEVER omit required props.
- NEVER use ad-hoc internal paths for Living Design components; always import from `./ld/` using relative paths (see **Import Convention** below).
- NEVER import directly from `@livingdesign/react` — use the `./ld/` wrappers which re-export everything.
- NEVER edit files under `src/components/ld/` — they are generated output.

## Component Location Policy

Two categories of components live in this project. Place new code in the right one.

**Design-system primitives (Living Design components)**
- Live in `src/components/ld/`.
- This folder is **generated output** — never edit it, and never author new files there. Changes here are overwritten by `npm run build:portable`.
- New LD primitives are contributed upstream through the base kit's source pipeline, not authored in this project.
- Do not create parallel `ld/` folders anywhere else.

**Project-local components (the app you are building)**
- Feature-scoped: `src/components/<feature-name>/<ComponentName>.tsx` — use when the ask names a domain (e.g., `walmart-business`, `supply-chain`, `sams-club`, `pharmacy`).
- Default bucket: `src/components/custom/<ComponentName>.tsx` — use when the ask is generic or exploratory.
- Pages live in `src/pages/<PageName>.tsx`.
- See the **Project Structure for New Work** section in the project orientation (`CLAUDE.md` / `AGENTS.md`) for the full decision tree and hard rules.

## Import Convention

All Living Design imports use **relative paths** from the consuming file into the `ld/` directory. Each component has its own file in `src/components/ld/` and exports one or more named exports.

### Pattern

From any file that is a sibling or parent of the `ld/` directory, import like this:

```tsx
import { ComponentName } from "./ld/ComponentName";
```

Adjust relative depth based on the current file location (for example `./ld/*`, `../ld/*`, `../../ld/*`, or `./components/ld/*`). One component per import line.

### Examples

```tsx
// UI components
import { Alert } from "./ld/Alert";
import { Button } from "./ld/Button";
import { Modal } from "./ld/Modal";
import { TextField } from "./ld/TextField";
import { Card } from "./ld/Card";
```

### Hard rules

- ALWAYS use relative imports pointing to the `ld/` directory. NEVER use bare package paths like `@livingdesign/react` directly — the `./ld/` wrappers re-export everything you need.
- NEVER use absolute paths in import statements. Use relative paths from your file's location.
- If your file is nested deeper, adjust the relative path accordingly (e.g., `../../ld/Button`).
- One component per import line for readability.

## WCP Header & Navigation Patterns

For top-level page headers and navigation, use the WCP pattern components:

- **`WCPHeader`** — Full responsive header with logo, search, location/delivery selector, cart, and account nav. Features multiple mobile variants.

These live in `wcpPatternHelpers/` and are documented on the **Header** pattern page (`#wcp-header`).

**CRITICAL — Header cart props MUST come from the Store:**

`WCPHeader` accepts `cartCount` and `cartPrice` props. These MUST be wired to the shared Store via `useHeaderCartBindings()` — NEVER hardcode static values. Hardcoded values break cart synchronization: when a user adds an item anywhere on the page, the header won't update.

```tsx
// CORRECT — header stays in sync with cart state
import { useHeaderCartBindings } from "src/utils/Store";
const { cartCount, cartPrice } = useHeaderCartBindings();
<WCPHeader cartCount={cartCount} cartPrice={cartPrice} />

// WRONG — header shows stale data, never updates
<WCPHeader cartCount={3} cartPrice="$127.45" />
```

## Component Documentation Policy

Each Living Design component in `src/components/ld` contains inline documentation with usage examples, feature descriptions, accessibility guidance, and FAQs directly in its module-level JSDoc comment. Before using any component, you MUST read and follow this embedded documentation.

### What to look for

- **Usage examples** — code snippets showing correct prop usage (e.g., `actionButtonProps` on `Alert`, `onClose` on `Banner`).
- **Variant semantics** — each component documents the meaning of its variants; choose by intent, not visual appearance.
- **Accessibility notes** — component-specific a11y guidance (e.g., using `aria-live="polite"` or `role="alert"` on the parent of a dynamically rendered `Alert`).
- **Sub-component details** — some components expose companion sub-components (e.g., `AlertActionButton`, `BannerCloseButton`) that are documented inline.

### Examples

#### Alert (`src/components/ld/Alert.tsx`)

- Supports `variant`: `error`, `info`, `success`, `warning` — each conveys a different severity.
- Optional `actionButtonProps` enables an action button inside the alert; supports both `<button>` and `<a>` (when `href` is provided).
- `a11yIconLabel` overrides the default icon label (which defaults to the variant name).
- For dynamic alerts: wrap in a container with `aria-live="polite"` (informational) or `role="alert"` (errors needing immediate attention). The container must exist in the DOM on page load.

```tsx
<Alert variant="warning" actionButtonProps={{ children: 'Retry', onClick: handleRetry }}>
  Something went wrong.
</Alert>
```

#### Banner (`src/components/ld/Banner.tsx`)

- Supports `variant`: `error`, `info`, `success`, `warning` — use for high-impact global announcements.
- `onClose` is **required** — the banner always has a close button.
- Optional `closeButtonProps` allows spreading additional props to the close button.
- The banner renders with `role="alert"` by default.

```tsx
<Banner variant="error" onClose={handleClose}>
  Service outage detected. We are investigating.
</Banner>
```

### Hard rule

- MUST read the component file's JSDoc before first use in a session.
- MUST follow the documented examples and prop patterns — do not guess or invent prop shapes.
- MUST respect accessibility guidance documented in the component (e.g., parent-level ARIA attributes for dynamic rendering).

## Page Layout & Responsive Composition

`spacing.*` is the source of truth for spacing and responsive guardrails. Follow it when composing page shells and section layouts.

### Container for Page Width (Required)

All main body content MUST be wrapped in `Container` to prevent full-bleed layout. `Container` matches the official walmart.com content container spec:

- **Max-width: 1612px** — content never stretches beyond this on wide viewports
- **Horizontal padding** — 16px on mobile, 24px on desktop (matches walmart.com's 24px left/right padding)
- **Auto centering** — margin-left/right auto (on a ~2496px viewport, this produces ~442px margins on each side)

**Full-bleed exceptions**: Headers (`WCPHeader`) and footers (`WCPDesktopFooter`, `WCPMwebFooter`) are the ONLY elements that should sit outside `Container`. Everything else — carousels, banners, card grids, product sections — goes inside `Container`.

```tsx
// CORRECT — all body content wrapped in Container, header/footer full-bleed
import { Container } from "./ld/Container";
<WCPHeader />              {/* full-bleed header, no Container */}
<Container>
  <WCPNewArrivalsCarousel />
  <WCPFlashDealsCarousel />
  <WCPSkylineBanner ... />
  <WCPContinueShopping />
</Container>
<WCPDesktopFooter />              {/* full-bleed footer, no Container */}

// WRONG — body sections without Container stretch edge-to-edge
<WCPNewArrivalsCarousel />     {/* ← no horizontal padding, full-bleed */}
<WCPFlashDealsCarousel />      {/* ← content jams against edges */}
<WCPContinueShopping />        {/* ← stretches full viewport width */}

// WRONG — never manually replicate Container behavior with inline styles
<div style={{ maxWidth: 1612, margin: '0 auto', padding: '0 24px' }}>
```

**Rule**: The ONLY components that should sit outside `Container` are full-bleed headers and footers. All other page body content — including carousels, banners, product grids, and card sections — MUST be inside `Container`.

### WCP Organism Preference (Required)

ALWAYS prefer existing WCP organism components over building custom equivalents. These organisms already handle responsive layout, spacing, and accessibility internally.

| Need | Use This Component | NEVER build custom |
|------|-------------------|-------------------|
| Desktop footer | `WCPDesktopFooter` | Custom `<footer>` with links |
| Mobile footer | `WCPMwebFooter` | Custom mobile footer |
| Product horizontal row (built-in flash deals) | `WCPFlashDealsCarousel` | Rebuilding Flash Deals from scratch |
| Product horizontal row (custom data + live cart) | `Carousel` + `WCPCarouselProductCard` + Store bindings | Static cards with no Store wiring |
| Product grid card | `WCPProductCardGrid` or `WCPProductCardList` | WCPItemTile in Grid |
| Desktop header | `WCPHeader` | Custom header |
| Mobile header | `WCPHeader` | Custom mobile header |
| Promo/skyline banner | `WCPSkylineBanner` or `WCPBasicBanner` | Custom gradient divs |
| Product carousel card | `WCPCarouselProductCard` | Custom card |

**Hard rule**: Before building any custom section (footer, header, product row, banner), check `overview-components.md` for a WCP organism that already does it. Build custom only as a last resort.

### Product Display Patterns

**Horizontal product row (default for product sections):**

Walmart pages display products in horizontal scrolling rows, NOT vertical grids.

- Use `WCPFlashDealsCarousel` for the built-in Flash Deals row.
- Use `Carousel` with `WCPCarouselProductCard` + `useStoreConnectedItemBindings()` for custom product data that must stay synced with header cart and other product surfaces.
- Do **not** pass a fake `items` prop to `WCPFlashDealsCarousel` (it is not part of the API).

```tsx
// GOOD — built-in Flash Deals row
<WCPFlashDealsCarousel />

// BEST for custom products — Store-connected carousel
const bindItem = useStoreConnectedItemBindings();
<Carousel>
  <CarouselContent>
    {products.map((p) => {
      const bindings = bindItem({ sku: p.sku, name: p.name, priceCents: p.priceCents });
      return (
        <CarouselItem key={p.sku} className="ld-carousel-item--multi">
          <WCPCarouselProductCard
            image={p.image}
            price={p.price}
            cents={p.cents}
            onAddToCart={bindings.onAddToCart}
            cartQty={bindings.cartQty}
            onCartQtyChange={bindings.onCartQtyChange}
          />
        </CarouselItem>
      );
    })}
  </CarouselContent>
  <CarouselPrevious />
  <CarouselNext />
</Carousel>
```

**CRITICAL**: When using `Carousel` for multi-item rows, add `className="ld-carousel-item--multi"` to each `CarouselItem`. Without this class, each item takes 100% width (single-item mode). The `--multi` class enables responsive 1→2→3 column display.

**Responsive product grid (browse pages only):**

For full browse/search pages with many products, use `Grid` + `GridColumn` with `WCPProductCardGrid` (NOT `WCPItemTile`). `WCPProductCardGrid` is designed for responsive grids. `WCPItemTile` has a fixed 200px max-width meant for carousels — it will NOT fill grid columns properly.

```tsx
// CORRECT — WCPProductCardGrid fills its column
<Grid hasGutter>
  {products.map(p => (
    <GridColumn key={p.id} sm={6} md={4} lg={3}>
      <WCPProductCardGrid image={p.image} name={p.name} price={p.price} cents={p.cents} />
    </GridColumn>
  ))}
</Grid>

// WRONG — WCPItemTile is 200px max-width, won't fill grid columns
<Grid hasGutter>
  <GridColumn sm={6} md={4} lg={2}>
    <WCPItemTile ... />  {/* ← stuck at 200px, doesn't fill column */}
  </GridColumn>
</Grid>
```

### Section Spacing

`Divider` renders with `margin: 0` by default — it will touch adjacent content. ALWAYS add vertical margin around it:

```tsx
// CORRECT — breathing room around divider
<section style={{ marginBottom: 32 }}>...</section>
<div style={{ margin: '24px 0' }}><Divider /></div>
<section style={{ marginTop: 32 }}>...</section>

// WRONG — divider jammed against content
<Section>...</Section>
<Divider />
<Section>...</Section>
```

Standard section spacing:
- **32px** (`marginBottom: 32`) between content sections
- **24px** margin above and below `Divider` components
- **48px** before the footer

### Grid Usage (Required)

**Always pass `hasGutter` to `Grid`**. Without it, columns have zero horizontal spacing:

```tsx
// CORRECT — hasGutter adds column spacing + row-gap
<Grid hasGutter>
  <GridColumn sm={12} md={6} lg={6}>
    <Card>...</Card>
  </GridColumn>
  <GridColumn sm={12} md={6} lg={6}>
    <Card>...</Card>
  </GridColumn>
</Grid>

// WRONG — no gutter, cards touch each other
<Grid>
  <GridColumn sm={12} md={6} lg={6}><Card>...</Card></GridColumn>
</Grid>
```

**Always set responsive breakpoints** (`sm`, `md`, `lg`) on every `GridColumn`. Without them, columns stay at 100% width on all screens.

Standard responsive column configurations:

| Layout | sm | md | lg | xl | Use for |
|--------|----|----|----|----|---------|
| Product grid | 6 | 4 | 3 | 2 | Product browse pages |
| Promo banners | 12 | 6 | 6 | 6 | Side-by-side banners |
| Category cards | 4 | 3 | 2 | 2 | Category grid |
| Info cards | 12 | 4 | 4 | 4 | Feature/method cards |
| Footer columns | 6 | 3 | 3 | 3 | Footer link groups |

Always build mobile-first. Content should stack vertically on small screens and flow into columns on larger breakpoints.

### Image & Media Sizing in Grid Layouts (Required)

Content inside `GridColumn` stretches to fill the column width. On desktop, a `md={6}` column inside `Container` (max-width: 1612px) is approximately **780px wide**. An unconstrained `width: 100%` image with `aspect-ratio: 1/1` becomes 780×780px — far too large for a product image.

**Always constrain images and media inside grid columns with `maxWidth`:**

```tsx
// CORRECT — image constrained for desktop, still fills column on mobile
<GridColumn sm={12} md={6} lg={6}>
  <div style={{ maxWidth: 500, margin: '0 auto' }}>
    <div style={{ width: '100%', aspectRatio: '1/1', overflow: 'hidden', borderRadius: 8 }}>
      <Image src={src} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    </div>
  </div>
</GridColumn>

// WRONG — image fills entire column = ~780px square on desktop
<GridColumn sm={12} md={6} lg={6}>
  <div style={{ width: '100%', aspectRatio: '1/1' }}>
    <Image src={src} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
  </div>
</GridColumn>
```

Use `<Image>` (from `src/components/ld/Image`) — NEVER raw `<img>`. `alt` must be a meaningful description (e.g., the product name), not a placeholder. See the a11y rules for the full directive and the decorative opt-out.

**Standard max-width constraints:**

| Context | max-width | Why |
|---------|-----------|-----|
| PDP main product image | `500px` | Matches retail PDP patterns, prevents oversized hero images |
| Hero/promo image in 50% column | `600px` | Prominent but not overwhelming |
| Thumbnail strip | `72px` per thumb | Fixed, doesn't scale with column |
| Avatar / icon areas | `48px–80px` | Fixed, never scales |

**General rule**: Any time you use `width: 100%` on an image or image container inside a `GridColumn`, ask: "What happens when this column is 780px wide on a 1612px viewport?" If the answer is "too big", add a `maxWidth` wrapper with `margin: '0 auto'` to center it.

This applies to **all** pages — PDPs, homepages, category pages, and any two-column layout. WCP organism components (like `WCPFlashDealsCarousel`, `WCPCarouselProductCard`) handle their own sizing internally; this constraint is for custom image areas you build yourself.

## Component Selection Flow

For each request:

1. Classify intent (`feedback`, `action`, `form`, `navigation`, `overlay`, `data`, `progress`, `layout`, `utility`).
2. Select component(s) from the Intent Router below.
3. Apply required prop/a11y invariants.
4. Compose with companion components if needed.
5. If no component matches, stop and request fallback approval.

## Intent Router

### Feedback

- Status message (success/info/warning/error) -> `Alert`
- High-impact global announcement -> `Banner`
- Empty/no-results state -> `ContentMessage`
- Coaching hint or reminder -> `Nudge`
- Temporary toast-like message -> `Snackbar` (`SnackbarProvider` + `useSnackbar`)
- Error page block -> `ContentMessage` (use `ErrorMessage` only if explicitly requested)

### Actions and links

- Primary/secondary/tertiary/destructive action -> `Button`
- Related action row -> `ButtonGroup`
- Icon-only action -> `IconButton`
- Inline navigation text -> `Link`
- Link styled as action -> `LinkButton`

### Form controls

- Boolean toggle -> `Switch`
- Multi-select choices -> `Checkbox` (group with `FormGroup`)
- Single-select choices -> `Radio` (same `name`; often in `FormGroup`)
- Single-line text input -> `TextField`
- Multi-line input -> `TextArea`
- Option selection dropdown -> `Select`
- Date input -> `DateField`

### Navigation

- Hierarchical path -> `Breadcrumb` + `BreadcrumbItem`
- Top-level section tabs -> `TabNavigation` + `TabNavigationItem`
- Sidebar nav -> `SideNavigation` + `SideNavigationItem`
- Triggered action menu -> `Menu` + `MenuItem`

### Overlays and disclosure

- Dialog -> `Modal`
- Side drawer -> `Panel`
- Bottom sheet -> `BottomSheet`
- Anchored contextual overlay -> `Popover`
- Anchored onboarding/coach mark -> `Callout`
- Expand/collapse inline content -> `Collapse`

### Data display

- Compact status/count -> `Badge`
- Non-interactive status pill -> `Tag`
- Interactive filter/select chip -> `Chip` / `ChipGroup`
- KPI and trend display -> `Metric`
- Star rating display -> `Rating`
- Structured vertical items -> `List` / `ListItem`
- Structured card content -> `Card` + card subcomponents
- Section separator -> `Divider`

### Progress and loading

- Determinate progress bar -> `ProgressIndicator`
- Multi-step progress -> `ProgressTracker`
- Indeterminate loading -> `Spinner`
- Loading placeholders -> `Skeleton` / `SkeletonText`

### Layout and utilities

- Max-width content wrapper -> `Container`
- 12-column responsive layout -> `Grid` / `GridColumn`
- Clamp text to N lines -> `LineClamp`
- Screen-reader-only text -> `VisuallyHidden`
- Decorative circular icon treatment -> `SpotIcon`
- AI-highlighted content frame -> `MagicBox`

## Required Prop and A11y Invariants

- `IconButton`: `a11yLabel` is required.
- `Checkbox`: exactly one of `label` or `a11yLabelledBy`; `onChange` required.
- `Radio`: exactly one of `label` or `a11yLabelledBy`; `name` and `onChange` required.
- `Switch`: exactly one of `label` or `a11yLabelledBy`.
- `ProgressIndicator`: `valueLabel` required; exactly one of `label` or `a11yLabelledBy`.
- `Banner`: `onClose` required.
- `TextField`, `TextArea`, `Select`, `DateField`: use `label` and `onChange` for interactive inputs.
- `Modal`, `Panel`, `BottomSheet`: use controlled open state (`isOpen`, `onClose`) and provide `title`.
- `Menu`: requires `trigger`, `triggerRef`, `isOpen`, `onOpen`, and `onClose`.
- `Popover`: requires `content`, `triggerRef`, `onClose`, and controlled `isOpen`.
- `Callout`: requires `a11yContentLabel`, `trigger`, `triggerRef`, `onClose`, and controlled `isOpen`.
- `Breadcrumb`: requires at least one valid item child.
- `Divider`: if not decorative, provide accessible labeling.

## Composition Rules

- Keep one primary action per surface when possible (`Button` with `variant="primary"`).
- Use semantic variants by meaning:
  - Positive outcome -> `success` / `positive`
  - Informational -> `info`
  - Caution -> `warning`
  - Failure or danger -> `error` / `negative`
- Use component props before custom styling.
- Use `isMagic` props where applicable for AI-generated/AI-assisted content.

## Icons — NEVER Use Emojis

Living Design includes a font icon system (`Icons`) with 136 icons and SVG icon components. **NEVER use emoji characters in UI code.** Emojis are not part of Living Design, render inconsistently across platforms, have accessibility issues, and cannot be themed.

### Font Icons (Primary)

The `Icons` component provides the `Icon` renderer and convenience exports. The font is loaded via CSS (`src/themes/base.css`).

**Import pattern:**
```tsx
import { Icon } from "./ld/Icons";

// Render any icon by name:
<Icon name="Truck" />
<Icon name="Returns" />
<Icon name="Gift" />
<Icon name="Search" />
```

**Available font icon names** (136 icons): ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Article, Ban, Barcode, Bell, Bluetooth, Bookmark, BookmarkFill, Box, Calendar, Camera, Car, Card, CaretDown, CaretUp, Chat, Check, CheckCircle, CheckCircleFill, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Clock, Close, CloseCircleFill, CloudDownload, CloudUpload, Copy, CurrentLocation, Dollar, DollarCircle, DollarCircleFill, Download, Email, ExclamationCircle, ExclamationCircleFill, Eye, EyeSlash, Facility, FacilityFill, Filter, Flag, FlagFill, Flash, FlashFill, FlashSlash, Gear, Gift, GiftFill, Globe, Grid, GridFill, Heart, HeartFill, History, Home, IdCard, Image, InfoCircle, InfoCircleFill, Keyboard, Link, LinkExternal, List, Location, Lock, LockOpen, Magic, MagicFill, Map, MapFill, Maximize, Menu, Microphone, MicrophoneSlash, Minimize, Minus, Mobile, More, MoreAlt, Note, Notebook, Pause, Pencil, Phone, Play, PlayFill, Plus, Printer, QrCode, QuestionCircle, Receipt, Refresh, Returns, Search, Services, ServicesFill, Share, ShareAndroid, SignIn, SignOut, Sliders, Speaker, SpeakerSlash, Star, StarFill, StarHalf, Tag, TagFill, ThumbDown, ThumbDownFill, ThumbUp, ThumbUpFill, Trash, Truck, Undo, User, UserCircle, UserCircleFill, UserPlus, Users, Video, Voice, Wallet, Warning, WarningFill, WiFi, WifiSlash, Wrench.

**Convenience named exports** are available for common icons:
```tsx
import { SearchIcon, ChevronUpIcon, SettingsIcon, StarIcon, CheckIcon, PlusIcon, InfoIcon, AlertTriangleIcon, XIcon, CloseIcon, ChevronDownIcon, CaretDownIcon, ArrowUpIcon, ArrowDownIcon, CalendarIcon, GiftIcon, CartIcon, ExclamationCircleIcon, WarningIcon, CheckCircleIcon } from "./ld/Icons";
```

### SVG Icons (Legacy — only for icons with no font equivalent)

Only 4 SVG-only icons remain in the common icons module: `WPlusIcon`, `SparkIcon`, `HourglassIcon`, `ShieldCheckIcon`. Use these only when there is no font-based alternative:
```tsx
import { ShieldCheckIcon, HourglassIcon } from "../components/common/icons";
```

### Icon Wrapper Components

- **`IconButton`** — Use for icon-only interactive buttons. Requires `a11yLabel`.
- **`SpotIcon`** — Use for decorative circular icon treatments (e.g., feature highlights). Accepts `color` (`"brand"` | `"neutral"`) and `size` (`"small"` | `"large"`).

### Common Emoji-to-Icon Mappings

| Instead of emoji | Use this icon |
|-----------------|---------------|
| 🚚 (shipping/truck) | `<Icon name="Truck" />` |
| ↩️ (returns) | `<Icon name="Returns" />` |
| 🏪 (store/pickup) | `<Icon name="Facility" />` or `name="FacilityFill"` |
| 📦 (package/delivery) | `<Icon name="Box" />` |
| 🎁 (gift) | `<Icon name="Gift" />` or `name="GiftFill"` |
| 🔍 (search) | `<Icon name="Search" />` |
| ⬆️ (share) | `<Icon name="Share" />` |
| ♡ (favorite) | `<Icon name="Heart" />` or `name="HeartFill"` |
| ▶️ (play/video) | `<Icon name="Play" />` or `name="PlayFill"` |
| 🔄 (refresh/3D) | `<Icon name="Refresh" />` |
| 📅 (calendar) | `<Icon name="Calendar" />` |
| 🛡️ (protection) | `<Icon name="Lock" />` or `ShieldCheckIcon` from `common/icons` (SVG-only) |
| ⚙️ (settings) | `<Icon name="Gear" />` |
| ✅/✓ (check) | `<Icon name="Check" />` or `name="CheckCircle"` |
| ❌ (error/close) | `<Icon name="Close" />` or `name="CloseCircleFill"` |
| ⚠️ (warning) | `<Icon name="Warning" />` |
| ℹ️/ⓘ (info) | `<Icon name="InfoCircle" />` |
| 💲/$ (dollar) | `<Icon name="Dollar" />` |
| 🏷️ (tag/price) | `<Icon name="Tag" />` |
| 🗑️ (delete) | `<Icon name="Trash" />` |
| ✦/⭐ (star) | `<Icon name="Star" />` or `name="StarFill"` |
| 🎂 (registry) | `<Icon name="Gift" />` (closest match) |
| 🍎 (apple/brand) | Use brand logo image, not an icon |

### Hard Rules

- **NEVER** use emoji characters (🔍⚙️✅❌⚠️ℹ️➕🗑️🚚📦🎁🏪↩️🛡️🎂🍎 etc.) in component code or UI text.
- **NEVER** use Unicode symbols as icon substitutes (✦, ⌄, ⓘ, etc.).
- **ALWAYS** use `Icon` or the SVG icon components for any icon need.
- **ALWAYS** use `IconButton` for interactive icon-only buttons (not bare `<button>` with an icon inside).
- **ALWAYS** use `SpotIcon` when you need a decorative circular icon treatment.
- If no icon exists for the concept, use the closest available icon or omit the icon — never fall back to emoji.

## Explicit Anti-Patterns

- **Do not use emoji characters anywhere in UI code** — use `Icon` or SVG icon components instead.
- **Do not use Unicode symbols as icon substitutes** (✦, ⌄, ⓘ, ↩️) — use the icon library.
- Do not build custom alert UI with generic `<div role="alert">` when `Alert` or `Banner` applies.
- Do not use bare HTML buttons when `Button`, `IconButton`, or `LinkButton` applies.
- Do not build custom tabs, breadcrumbs, menus, lists, dialogs, or form controls when Living Design equivalents exist.
- Do not create duplicate wrappers that replicate existing Living Design behavior.

## Output Contract

When generating code:

1. Use Living Design component names directly.
2. Satisfy required props and accessibility constraints.
3. Keep implementation concise and semantic.
4. If fallback is needed, state why and request approval before introducing it.

## Pre-Response Checklist

- [ ] Every user requirement mapped to a Living Design component.
- [ ] All required props included.
- [ ] Accessibility invariants satisfied.
- [ ] No custom replacement for an existing component.
- [ ] **Zero emoji characters in generated code** — all icons use `Icon` or SVG icon components.
- [ ] Any fallback clearly justified and approved.
