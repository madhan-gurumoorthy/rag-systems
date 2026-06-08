// @refresh reset

/**
 * @module SectionHeader
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
import {cx, applyCommonProps} from '../common';
import './SectionHeader.css';

export interface SectionHeaderProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /** Section heading text */
  title: string;
  /** Secondary text (e.g. "Up to 65% off") */
  subtitle?: string;
  /** Action link text ("View all", "See all") */
  actionLabel?: string;
  /** Action link destination */
  actionHref?: string;
  /** Click handler for the action link */
  onAction?: () => void;
  /** Heading level for the title (defaults to h2) */
  headingLevel?: 'h2' | 'h3' | 'h4';
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

/**
 * SectionHeader — Reusable section title row used across homepage sections.
 *
 * Renders a title, optional subtitle, and an optional "View all" / "See all"
 * action link. Matches the pattern used in Flash Deals, Continue Shopping,
 * Jump Right Back In, and other homepage carousel sections.
 */
export function SectionHeader(props: SectionHeaderProps) {
  const {
    title,
    subtitle,
    actionLabel,
    actionHref = '#',
    onAction,
    headingLevel = 'h2',
    className,
    ...rest
  } = applyCommonProps(props);

  const Heading = headingLevel;

  const handleActionClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (onAction) {
      e.preventDefault();
      onAction();
    }
  };

  return (
    <div
      className={cx('ld-section-header-root', className)}
      {...(rest as any)}
    >
      <div className="ld-section-header-top-row">
        <Heading className="ld-section-header-title">{title}</Heading>
        {actionLabel && (
          <a
            href={actionHref}
            className="ld-section-header-action"
            onClick={handleActionClick}
          >
            {actionLabel}
          </a>
        )}
      </div>
      {subtitle && (
        <p className="ld-section-header-subtitle">{subtitle}</p>
      )}
    </div>
  );
}
SectionHeader.displayName = 'SectionHeader';
