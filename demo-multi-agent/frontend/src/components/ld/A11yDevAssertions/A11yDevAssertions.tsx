// @refresh reset

/**
 * @module A11yDevAssertions
 *
 * # CRITICAL AGENT DIRECTIVE - HARD STOP
 * 
 * This file is read-only output. Treat it as immutable.
 * 
 * - NEVER edit this file directly.
 * - NEVER apply "quick fixes" in this file.
 * - NEVER reformat, refactor, or rewrite content in place.
 * - NEVER treat this file as the source of truth.
 * 
 * If behavior must change, modify the upstream source of this content (the canonical source), not this copy.
 * 
 * Any direct edits in this file are invalid and must be rejected.
 */

import * as React from 'react';
import * as ReactDOM from 'react-dom';

/**
 * A11yDevAssertions — dev-only runtime scanner.
 *
 * Mounts once at the root of the app (above your Page). Watches the DOM with
 * a MutationObserver and runs a battery of accessibility checks. On violation
 * it fires FIVE parallel signals — redundancy is deliberate:
 *
 *   1. logs to the browser console with a `[LD a11y]` prefix
 *   2. POSTs a structured report to `/__ld_a11y_report` so the Vite dev
 *      server plugin prints it to THE TERMINAL the agent is running, writes
 *      `.ld-a11y-report.json`, and serves a live snapshot at the same URL
 *   3. portal-renders a full-viewport violation card with the same banner
 *      format as the dev-server stdout — humans can read and copy it
 *   4. throws an uncaught error (via setTimeout so it escapes React's render
 *      tree) — Vite's built-in error overlay shows on top of the portal card;
 *      when the user dismisses Vite's overlay the portal card is still there
 *   5. (production) scanner is tree-shaken, no-op
 *
 * The overlay + the Vite red screen together are the strongest forcing
 * function available without a CI gate.
 *
 * Escape hatch: add `data-ld-a11y-ignore` to any element you genuinely need
 * to exempt (third-party embeds, etc.). Every opt-out should come with a
 * justification the user approved. Do not add this to silence a real defect.
 */
export function A11yDevAssertions(): JSX.Element | null {
  const [state, setState] = React.useState<ViolationReport | null>(null);
  const dismissedIssueSigRef = React.useRef('');

  React.useEffect(() => {
    if (import.meta.env.MODE === 'production') return;

    let timer: ReturnType<typeof setTimeout> | null = null;
    let lastReportedSig = '';
    const SCAN_DEBOUNCE_MS = 300;

    const runScan = () => {
      timer = null;
      const issues = scanDocument();
      if (issues.length > 0) {
        const sig = issues.join('\u0001');
        const message = issues.map((v, i) => `  ${i + 1}. ${v}`).join('\n');
        const url = window.location?.href ?? '';
        const timestamp = new Date().toISOString();
        const formatted = `LD a11y: ${issues.length} accessibility violation(s) at ${url} — reported ${timestamp}\n${message}\n\n${AGENT_HINT}`;
        // eslint-disable-next-line no-console
        console.error(formatted);
        // Only POST + throw when the violation set actually changes — avoids
        // spamming the dev-server terminal on every MutationObserver tick.
        if (sig !== lastReportedSig) {
          lastReportedSig = sig;
          reportViolations(issues, url, timestamp);
          // Fire an uncaught error from outside the React render tree so Vite's
          // built-in error overlay surfaces WITHOUT unmounting our portal-
          // rendered panel. The two layer: Vite's red screen sits on top, our
          // copy-able panel stays behind. Dismissing Vite's overlay reveals
          // our panel, which the user can copy back to the agent.
          setTimeout(() => {
            throw new Error(formatted);
          }, 0);
        }
        if (sig !== dismissedIssueSigRef.current) {
          setState({count: issues.length, url, timestamp, issues});
        } else {
          setState(null);
        }
      } else {
        if (lastReportedSig !== '') {
          lastReportedSig = '';
          reportViolations([], window.location?.href ?? '', new Date().toISOString());
        }
        dismissedIssueSigRef.current = '';
        setState(null);
      }
    };

    const schedule = () => {
      if (timer != null) clearTimeout(timer);
      timer = setTimeout(runScan, SCAN_DEBOUNCE_MS);
    };

    // Initial scan after first paint so fonts/images have a chance.
    schedule();

    const observer = new MutationObserver(schedule);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: [
        'alt',
        'aria-label',
        'aria-labelledby',
        'aria-hidden',
        'aria-pressed',
        'aria-checked',
        'role',
        'href',
        'id',
        'tabindex',
      ],
    });

    return () => {
      observer.disconnect();
      if (timer != null) clearTimeout(timer);
    };
  }, []);

  if (!state || typeof document === 'undefined') return null;

  const handleDismiss = () => {
    dismissedIssueSigRef.current = state.issues.join('\u0001');
    setState(null);
  };

  return ReactDOM.createPortal(<ViolationOverlay {...state} onDismiss={handleDismiss} />, document.body);
}

A11yDevAssertions.displayName = 'A11yDevAssertions';

// ---------------------------------------------------------------------------
// Violation overlay — the human-visible panel
// ---------------------------------------------------------------------------

interface ViolationReport {
  count: number;
  url: string;
  timestamp: string;
  issues: string[];
  onDismiss?: () => void;
}

function ViolationOverlay({count, url, timestamp, issues, onDismiss}: ViolationReport): JSX.Element {
  const [copied, setCopied] = React.useState(false);

  const formatted = React.useMemo(() => formatForCopy({count, url, timestamp, issues}), [
    count,
    url,
    timestamp,
    issues,
  ]);

  const handleCopy = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(formatted);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard not available — user can still select-and-copy */
    }
  }, [formatted]);

  // The `data-ld-a11y-ignore` attribute ensures the scanner skips the overlay's
  // own subtree, so the panel doesn't generate violations about itself.
  return (
    <div data-ld-a11y-ignore="true" data-ld-a11y-devtool="true" style={S.backdrop}>
      <div style={S.card} role="alertdialog" aria-labelledby="ld-a11y-title">
        <div style={S.header}>
          <span style={S.badge}>LD A11Y</span>
          <strong id="ld-a11y-title" style={S.title}>
            {count} accessibility violation{count === 1 ? '' : 's'} at {url}
          </strong>
          <span style={S.timestamp}>reported {timestamp}</span>
        </div>

        <ol style={S.list}>
          {issues.map((issue, i) => (
            <li key={i} style={S.listItem}>
              <span style={S.listNumber}>{i + 1}.</span>
              <span style={S.listText}>{issue}</span>
            </li>
          ))}
        </ol>

        <div style={S.actions}>
          <button type="button" onClick={handleCopy} style={S.copyButton}>
            {copied ? 'Copied!' : 'Copy violations'}
          </button>
          {onDismiss && (
            <button type="button" onClick={onDismiss} style={S.dismissButton}>
              Close
            </button>
          )}
          <span style={S.actionsHint}>
            Paste this into your prompt if your agent didn't fix the page itself.
          </span>
        </div>

        <details style={S.details}>
          <summary style={S.detailsSummary}>How to inspect (agent / headless)</summary>
          <pre style={S.pre}>{AGENT_HINT}</pre>
        </details>

        <div style={S.footer}>
          ld-kit accessibility scanner · dev-only · this panel disappears when every violation is fixed
        </div>
      </div>
    </div>
  );
}

export function A11yDevAssertionsPreview({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}): JSX.Element | null {
  const timestamp = React.useMemo(() => new Date().toISOString(), [open]);

  if (!open || typeof document === 'undefined') return null;

  return ReactDOM.createPortal(
    <ViolationOverlay
      count={2}
      url={`${window.location?.origin ?? 'http://localhost:5173'}/#a11y-checks`}
      timestamp={timestamp}
      issues={[
        'button with no accessible name: button.icon-only. Add text, aria-label, or wrap in IconButton with a11yLabel.',
        'Form control without label: input#demo-email. Wrap with <FormField> / <TextField> / <Select> — they wire label ↔ input for you.',
      ]}
      onDismiss={onClose}
    />,
    document.body,
  );
}

function formatForCopy({count, url, timestamp, issues}: ViolationReport): string {
  const header = `LD A11Y — ${count} accessibility violation(s) at ${url} — reported ${timestamp}`;
  const body = issues.map((v, i) => `  ${i + 1}. ${v}`).join('\n');
  return `${header}\n${body}\n\n${AGENT_HINT}`;
}

// ---------------------------------------------------------------------------
// Inline styles — no external CSS dependency so the overlay always renders
// even before LD theme CSS has loaded. Keep narrow + consistent with the
// terminal banner aesthetic so paste-back into chat is recognizable.
// ---------------------------------------------------------------------------

const COLOR_RED = '#b91c1c';
const COLOR_RED_LIGHT = '#fee2e2';
const COLOR_INK = '#1f2937';
const COLOR_MUTED = '#6b7280';
const COLOR_SURFACE = '#ffffff';
const FONT_MONO = "ui-monospace, SFMono-Regular, Menlo, Monaco, 'Courier New', monospace";
const FONT_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

const S = {
  backdrop: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(15, 23, 42, 0.78)',
    zIndex: 2147483646,
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    padding: '32px 16px',
    overflowY: 'auto',
    fontFamily: FONT_SANS,
    color: COLOR_INK,
    WebkitFontSmoothing: 'antialiased',
  },
  card: {
    background: COLOR_SURFACE,
    width: 'min(760px, 100%)',
    maxHeight: '90vh',
    overflowY: 'auto',
    borderRadius: 12,
    boxShadow: '0 20px 60px rgba(0,0,0,0.45)',
    border: `1px solid ${COLOR_RED}`,
    padding: 24,
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  header: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  badge: {
    display: 'inline-block',
    background: COLOR_RED,
    color: '#fff',
    fontWeight: 700,
    fontSize: 11,
    letterSpacing: 1,
    padding: '4px 8px',
    borderRadius: 4,
    width: 'fit-content',
  },
  title: {
    fontSize: 18,
    fontWeight: 600,
    color: COLOR_INK,
    lineHeight: 1.4,
    wordBreak: 'break-word',
  },
  timestamp: {
    fontSize: 12,
    color: COLOR_MUTED,
    fontFamily: FONT_MONO,
  },
  list: {
    margin: 0,
    padding: 0,
    listStyle: 'none',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  listItem: {
    display: 'flex',
    gap: 10,
    background: COLOR_RED_LIGHT,
    border: `1px solid ${COLOR_RED}`,
    borderRadius: 6,
    padding: '10px 12px',
    fontFamily: FONT_MONO,
    fontSize: 13,
    lineHeight: 1.5,
    color: COLOR_INK,
  },
  listNumber: {
    fontWeight: 700,
    color: COLOR_RED,
    flexShrink: 0,
  },
  listText: {
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  actions: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    flexWrap: 'wrap',
  },
  copyButton: {
    background: COLOR_INK,
    color: '#fff',
    border: 0,
    padding: '8px 14px',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: FONT_SANS,
  },
  dismissButton: {
    background: COLOR_SURFACE,
    color: COLOR_INK,
    border: '1px solid #d1d5db',
    padding: '8px 14px',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: FONT_SANS,
  },
  actionsHint: {
    fontSize: 12,
    color: COLOR_MUTED,
  },
  details: {
    borderTop: '1px solid #e5e7eb',
    paddingTop: 12,
  },
  detailsSummary: {
    fontSize: 13,
    fontWeight: 600,
    color: COLOR_INK,
    cursor: 'pointer',
  },
  pre: {
    margin: '8px 0 0 0',
    padding: 12,
    background: '#f3f4f6',
    borderRadius: 6,
    fontFamily: FONT_MONO,
    fontSize: 12,
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap',
    color: COLOR_INK,
    overflowX: 'auto',
  },
  footer: {
    fontSize: 11,
    color: COLOR_MUTED,
    textAlign: 'center',
  },
} as const satisfies Record<string, React.CSSProperties>;

// ---------------------------------------------------------------------------
// Agent debugging hint — appears in console.error, the thrown / overlay copy,
// and the dev-server terminal banner. Keep these channels in sync.
// ---------------------------------------------------------------------------

const AGENT_HINT =
  'HOW TO INSPECT (agent / headless):\n' +
  '  • cat .ld-a11y-report.json                      — latest violation snapshot (project root)\n' +
  '  • curl http://localhost:PORT/__ld_a11y_report   — live violation snapshot (use dev-server port)\n' +
  '  • tail the `npm run dev` stdout                 — violations are logged with a red [LD A11Y] banner\n' +
  'See the `a11y` rules file for the full directive and pre-response checklist.';

// ---------------------------------------------------------------------------
// Reporting to the Vite dev server (so the agent sees violations in terminal)
// ---------------------------------------------------------------------------

const REPORT_ENDPOINT = '/__ld_a11y_report';

function reportViolations(issues: string[], url: string, timestamp: string): void {
  if (typeof window === 'undefined' || typeof fetch === 'undefined') return;
  const payload = {
    timestamp,
    url,
    count: issues.length,
    issues,
  };
  try {
    fetch(REPORT_ENDPOINT, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
      // keepalive so the request survives even if the page unmounts mid-flight.
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    /* no dev server / network — browser-only fallback is the console.error */
  }
}

// ---------------------------------------------------------------------------
// DOM scanning
// ---------------------------------------------------------------------------

const IGNORE_ATTR = 'data-ld-a11y-ignore';

// Vite / React dev tooling roots to exclude from scans. These render our
// own violations back at us, which would cause noisy false positives.
const DEV_TOOLING_SELECTORS = [
  'vite-error-overlay',
  '[data-vite-error-overlay]',
  '[data-ld-a11y-devtool]',
  'nextjs-portal',
];

function isInDevTooling(el: Element): boolean {
  for (const sel of DEV_TOOLING_SELECTORS) {
    if (el.closest(sel)) return true;
    // tag-name selectors don't match via closest if the host uses Shadow DOM;
    // fall back to ancestor scan for the custom-element case.
    if (sel === 'vite-error-overlay' || sel === 'nextjs-portal') {
      let n: Element | null = el;
      while (n) {
        if (n.tagName?.toLowerCase() === sel) return true;
        n = n.parentElement;
      }
    }
  }
  return false;
}

function isIgnored(el: Element): boolean {
  if (isInDevTooling(el)) return true;
  let node: Element | null = el;
  while (node) {
    if (node.hasAttribute?.(IGNORE_ATTR)) return true;
    // Skip content inside aria-hidden ancestors — they're already removed from AT.
    if (node.getAttribute?.('aria-hidden') === 'true') return true;
    node = node.parentElement;
  }
  return false;
}

function accessibleName(el: Element): string {
  const ariaLabel = el.getAttribute('aria-label');
  if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim();
  const labelledBy = el.getAttribute('aria-labelledby');
  if (labelledBy) {
    const ids = labelledBy.split(/\s+/).filter(Boolean);
    const text = ids
      .map((id) => document.getElementById(id)?.textContent?.trim() ?? '')
      .filter(Boolean)
      .join(' ');
    if (text) return text;
  }
  const title = el.getAttribute('title');
  if (title && title.trim()) return title.trim();
  // Fall back to text content OR the alt text of any descendant image
  // (WAI ARIA accessible-name computation includes image alts of descendants).
  const text = (el.textContent ?? '').trim();
  if (text) return text;
  const descendantAlt = Array.from(el.querySelectorAll<HTMLImageElement>('img[alt]'))
    .map((img) => (img.getAttribute('alt') ?? '').trim())
    .filter(Boolean)
    .join(' ');
  return descendantAlt;
}

function shortSelector(el: Element): string {
  const tag = el.tagName.toLowerCase();
  const id = el.id ? `#${el.id}` : '';
  const cls = typeof el.className === 'string' && el.className
    ? '.' + el.className.split(/\s+/).filter(Boolean).slice(0, 2).join('.')
    : '';
  return `${tag}${id}${cls}`;
}

function scanDocument(): string[] {
  const issues: string[] = [];

  // 1. Exactly one <h1>
  const h1s = Array.from(document.querySelectorAll('h1')).filter((el) => !isIgnored(el));
  if (h1s.length === 0) {
    issues.push('No <h1> on the page. Wrap your page in <Page title="…"> — it renders the single required h1.');
  } else if (h1s.length > 1) {
    issues.push(`Found ${h1s.length} <h1> elements. Expected exactly 1. Page wrappers render the single h1 for you — remove any hand-written or duplicate <h1>.`);
  }

  // 2. Exactly one <main>
  const mains = Array.from(document.querySelectorAll('main')).filter((el) => !isIgnored(el));
  if (mains.length === 0) {
    issues.push('No <main> landmark. Use <Page> as the root of your page — it renders the <main> for you.');
  } else if (mains.length > 1) {
    issues.push(`Found ${mains.length} <main> landmarks. Expected exactly 1.`);
  }

  // 3. Heading order — no skips (h2 → h4 without h3)
  const headings = Array.from(
    document.querySelectorAll('h1, h2, h3, h4, h5, h6'),
  ).filter((el) => !isIgnored(el));
  let prevLevel = 0;
  for (const h of headings) {
    const level = Number(h.tagName[1]);
    if (prevLevel > 0 && level > prevLevel + 1) {
      issues.push(
        `Heading level skip: <${h.tagName.toLowerCase()}> follows <h${prevLevel}>. Headings must not skip levels — use h${prevLevel + 1} instead. Element: ${shortSelector(h)}.`,
      );
      break; // one heading-order message is enough
    }
    prevLevel = level;
  }

  // 4. <img> without alt, or with whitespace-only alt (empty string is a
  //    valid "decorative" marker; only flag when the alt attribute is entirely
  //    missing or is whitespace-but-non-empty, e.g. alt=" ").
  const imgs = Array.from(document.querySelectorAll('img')).filter((el) => !isIgnored(el));
  for (const img of imgs) {
    if (!img.hasAttribute('alt')) {
      issues.push(
        `<img> without alt attribute: ${shortSelector(img)} (src=${img.getAttribute('src')?.slice(0, 80)}). Use <Image src alt="…"> or <Image src unsafeDecorative={{reason}} />.`,
      );
      continue;
    }
    const altRaw = img.getAttribute('alt') ?? '';
    if (altRaw.length > 0 && altRaw.trim().length === 0) {
      issues.push(
        `<img alt=" "> has whitespace-only alt (a silent label): ${shortSelector(img)}. Use a meaningful alt, or alt="" for decorative images.`,
      );
    }
  }

  // 5. <button> / <a href> without accessible name
  const interactives = Array.from(
    document.querySelectorAll('button, a[href]'),
  ).filter((el) => !isIgnored(el));
  for (const el of interactives) {
    const name = accessibleName(el);
    if (!name) {
      issues.push(
        `${el.tagName.toLowerCase()} with no accessible name: ${shortSelector(el)}. Add text, aria-label, or wrap in IconButton with a11yLabel.`,
      );
    }
    // Nested interactive elements (button inside button, button inside a)
    // violate HTML and break keyboard/SR interaction.
    const nested = el.querySelector('button, a[href], input, select, textarea');
    if (nested && nested !== el) {
      issues.push(
        `Interactive element nested inside another: ${shortSelector(el)} contains ${shortSelector(nested)}. This is invalid HTML and breaks keyboard/AT behavior. Flatten the structure.`,
      );
    }
  }

  // 6. onClick-like roles on non-button/link without keyboard handling
  const clickableNonInteractive = Array.from(
    document.querySelectorAll('[role="button"]:not(button):not(a)'),
  ).filter((el) => !isIgnored(el));
  for (const el of clickableNonInteractive) {
    const tabIndex = el.getAttribute('tabindex');
    if (tabIndex === null || tabIndex === '') {
      issues.push(
        `Element with role="button" is not keyboard-focusable: ${shortSelector(el)}. Use <Button> or <IconButton>. Raw role="button" on a div requires tabIndex={0} + keyboard handlers.`,
      );
    }
  }

  // 7. Duplicate id= attributes — break aria-labelledby / aria-describedby / for=.
  const idCounts = new Map<string, number>();
  const allIdEls = Array.from(document.querySelectorAll<HTMLElement>('[id]')).filter(
    (el) => !isIgnored(el),
  );
  for (const el of allIdEls) {
    const id = el.id;
    if (!id) continue;
    idCounts.set(id, (idCounts.get(id) ?? 0) + 1);
  }
  const dupIds = [...idCounts.entries()].filter(([, c]) => c > 1).slice(0, 3);
  for (const [id, count] of dupIds) {
    issues.push(
      `Duplicate id="${id}" found ${count} times. Duplicate IDs break aria-labelledby, aria-describedby, and <label for>. Use stable unique IDs (useStableId helper).`,
    );
  }

  // 8. <input>/<select>/<textarea> without label association
  //    (excluding hidden, submit/button/image/reset types)
  const controls = Array.from(
    document.querySelectorAll('input, select, textarea'),
  ).filter((el) => !isIgnored(el));
  for (const el of controls) {
    if (el.tagName === 'INPUT') {
      const type = (el as HTMLInputElement).type;
      if (['hidden', 'submit', 'button', 'image', 'reset'].includes(type)) continue;
    }
    const id = el.id;
    const hasFor = id && document.querySelector(`label[for="${CSS.escape(id)}"]`);
    const wrappedInLabel = el.closest('label');
    const hasAriaLabel = (el.getAttribute('aria-label') ?? '').trim().length > 0;
    const hasAriaLabelledBy = (el.getAttribute('aria-labelledby') ?? '').trim().length > 0;
    if (!hasFor && !wrappedInLabel && !hasAriaLabel && !hasAriaLabelledBy) {
      issues.push(
        `Form control without label: ${shortSelector(el)}. Wrap with <FormField> / <TextField> / <Select> — they wire label ↔ input for you.`,
      );
    }
  }

  // 9a. Single-select button groups without keyboard-group semantics.
  //     <Chip selected> + <ChipGroup> renders N sibling <button aria-pressed>
  //     with one selected. That gives N tab stops and no arrow-key nav.
  //     For one-of-many UIs the wrapper must be role="radiogroup"/"tablist"
  //     with roving tabindex (covered by 9b). If it isn't, steer toward the
  //     canonical components.
  const togglingButtons = Array.from(
    document.querySelectorAll<HTMLButtonElement>('button[aria-pressed], button[aria-checked]'),
  ).filter((el) => !isIgnored(el));

  // Walk up past role="listitem"/"none"/"presentation" wrappers (ChipGroup
  // wraps each chip in <div role="listitem">) to find the semantic group root.
  const groupWrapperFor = (btn: Element): Element | null => {
    let parent = btn.parentElement;
    while (parent) {
      const role = parent.getAttribute('role');
      if (role === 'listitem' || role === 'none' || role === 'presentation') {
        parent = parent.parentElement;
        continue;
      }
      return parent;
    }
    return null;
  };

  const groupsWithToggles = new Map<Element, HTMLButtonElement[]>();
  for (const btn of togglingButtons) {
    const wrapper = groupWrapperFor(btn);
    if (!wrapper) continue;
    const list = groupsWithToggles.get(wrapper) ?? [];
    list.push(btn);
    groupsWithToggles.set(wrapper, list);
  }

  for (const [wrapper, buttons] of groupsWithToggles) {
    if (buttons.length < 2) continue;
    const wrapperRole = wrapper.getAttribute('role');
    // role="radiogroup" / role="tablist" wrappers are evaluated by 9b instead.
    if (wrapperRole === 'radiogroup' || wrapperRole === 'tablist') continue;
    const activeCount = buttons.filter(
      (b) =>
        b.getAttribute('aria-pressed') === 'true' ||
        b.getAttribute('aria-checked') === 'true',
    ).length;
    if (activeCount === 0) continue;
    issues.push(
      `Single-select button group without keyboard-group semantics: ${shortSelector(wrapper)} contains ${buttons.length} toggle buttons with ${activeCount} active. That gives ${buttons.length} tab stops and no arrow-key navigation between options. For one-of-many UIs use <SegmentedControl> (preferred), <Radio> inside <FormGroup>, or <TabNavigation> — not <ChipGroup>+<Chip>. <ChipGroup>+<Chip> is for multi-select filter chips where each chip toggles independently.`,
    );
  }

  // 9b. Roving tabindex inside radiogroup / tablist / toolbar. The WAI-ARIA
  //     authoring practices require ONE tab stop per group: the active item
  //     has tabindex=0, the rest have tabindex=-1, and arrow keys move focus.
  //     Native <button> defaults to tabindex=0, so an un-managed group gives
  //     every segment its own tab stop.
  const rovingGroups = Array.from(
    document.querySelectorAll('[role="radiogroup"], [role="tablist"], [role="toolbar"]'),
  ).filter((el) => !isIgnored(el));
  for (const group of rovingGroups) {
    const focusable = Array.from(
      group.querySelectorAll<HTMLElement>('button, [tabindex]'),
    ).filter((el) => {
      if (isIgnored(el)) return false;
      if (el instanceof HTMLButtonElement && el.disabled) return false;
      const ti = el.getAttribute('tabindex');
      return ti !== '-1';
    });
    if (focusable.length > 1) {
      const role = group.getAttribute('role');
      issues.push(
        `<${role}> at ${shortSelector(group)} has ${focusable.length} focusable items — missing roving tabindex. Exactly one item should have tabindex=0; the rest tabindex=-1. Tab enters/exits the group as a single stop; arrow keys move focus between items.`,
      );
    }
  }

  return issues;
}
