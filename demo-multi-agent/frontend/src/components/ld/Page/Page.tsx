// @refresh reset

/**
 * @module Page
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
import {invariant, applyCommonProps} from '../common';
import './Page.css';

export interface PageProps {
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
  /**
   * The page heading. Rendered as the single `<h1>` inside `<main>`.
   * Required — every page must have one, and only one, h1.
   */
  title: string;
  /**
   * Optional label for the skip-to-content link.
   *
   * @default "Skip to main content"
   */
  skipLinkLabel?: string;
  /**
   * If `true`, the h1 rendered inside `<main>` is visually hidden but still
   * announced by screen readers. Use this when the visible page heading is
   * rendered by a different component (e.g., a hero banner with its own
   * visible title). Defaults to `false`.
   */
  titleVisuallyHidden?: boolean;
  /**
   * The page content. Renders inside the `<main>` landmark, below the h1.
   */
  children: React.ReactNode;
}

/**
 * Page — landmark and heading enforcement for top-level page shells.
 *
 * Renders a skip link, the `<main>` landmark, and the single page `<h1>`.
 * Never write `<main>`, `<h1>`, or a skip link by hand — use `<Page>` so
 * the runtime scanner can verify exactly-one of each.
 */
export function Page(props: PageProps): JSX.Element {
  const {
    title,
    skipLinkLabel = 'Skip to main content',
    titleVisuallyHidden = false,
    children,
    className,
    style,
  } = applyCommonProps(props);

  invariant(
    typeof title === 'string' && title.trim().length > 0,
    '`Page` accessibility violation. `Page` requires a non-empty `title` (renders the page h1).',
  );

  React.useEffect(() => {
    if (import.meta.env.MODE === 'production') return;
    // Defer one tick so nested effects from children have mounted.
    const handle = window.requestAnimationFrame(() => {
      const h1s = document.querySelectorAll('h1');
      invariant(
        h1s.length === 1,
        `Page landmark violation. Found ${h1s.length} <h1> elements on the page; expected exactly 1. Page renders the single h1 for you — remove any hand-written <h1> or duplicate <Page>.`,
      );
      const mains = document.querySelectorAll('main');
      invariant(
        mains.length === 1,
        `Page landmark violation. Found ${mains.length} <main> landmarks; expected exactly 1. Use one <Page> at the root of your page.`,
      );
    });
    return () => window.cancelAnimationFrame(handle);
  });

  return (
    <>
      <a className="ld-page-skipLink" href="#ld-main">
        {skipLinkLabel}
      </a>
      <main
        id="ld-main"
        tabIndex={-1}
        className={className ? `ld-page-main ${className}` : 'ld-page-main'}
        style={style}
      >
        <h1
          className={
            titleVisuallyHidden ? 'ld-visuallyhidden-visuallyHidden' : 'ld-page-title'
          }
        >
          {title}
        </h1>
        {children}
      </main>
    </>
  );
}

Page.displayName = 'Page';
