# Living Design Starter

A standalone Vite + React + Tailwind starter pre-loaded with Living Design components. Use it with Claude Code, Cursor, or any IDE to vibe quickly with the Living Design system.

## Prerequisites

- **Node.js 22** (see `.nvmrc`)
- **npm**

## Getting Started

```bash
nvm use              # switch to Node 22
npm install          # install dependencies
npm run dev          # start dev server on http://localhost:3099
```

## Project Structure

```
src/
  App.tsx                  # Your starting point — edit this!
  main.tsx                 # React root mount (no need to touch)
  components/ld/           # Generated Living Design components (read-only)
  utils/                   # Shared helpers: Theming.tsx, Store.tsx (read-only)
  styles/
    index.css              # Tailwind directives + LD CSS import
    living-design.css      # Combined LD component styles (generated)
```

## Using Components

Import components from `src/components/ld/`:

```tsx
import { Button } from './components/ld/Button';
import { Card } from './components/ld/Card';
import { TextField } from './components/ld/TextField';
```

Check `.cursor/rules/overview-components.mdc` for the full component inventory with prop APIs.

## Adding New Components

Create new components **outside** `src/components/ld/` — that directory is generated and read-only. Import and compose existing LD components in your own files.

## Context & Guidelines

- `.cursor/rules/` — Cursor IDE rules (auto-loaded)
- `.claude/CLAUDE.md` — Claude Code agent instructions
- `AGENTS.md` — General agent orientation

## Accessibility runtime scanner (dev only)

This starter ships a dev-only accessibility scanner that runs in the browser and **covers the app with an unmissable red panel** whenever it detects common a11y defects (missing alt, unlabeled buttons, multiple `<h1>`, duplicate ids, clickable non-interactive elements, form controls without labels, etc.).

When violations exist you'll see:

- **In-page overlay** — a centered card titled `LD A11Y` listing every violation, with a "Copy violations" button. If a coding agent missed a defect, copy the panel contents and paste them back into your prompt.
- **`npm run dev` terminal banner** — violations print as a red `[LD A11Y]` block with numbered issues.

To inspect violations without opening DevTools:

```bash
# Machine-readable snapshot, written on every scan
cat .ld-a11y-report.json

# Live snapshot served by the dev server
curl http://localhost:3099/__ld_a11y_report
```

The scanner runs inside the browser, so the page must actually be loaded for violations to surface — a bare `curl /` won't trigger it. Use a browser, a browser-automation tool, or any agent that executes the page's JavaScript.

See `.cursor/rules/a11y.mdc` (or `.claude/rules/a11y.md`) for the full accessibility directive and the `unsafeDecorative={{ reason }}` opt-out contract.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server (port 3099) |
| `npm run build` | Type-check + production build |
| `npm run preview` | Preview production build |
