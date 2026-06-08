// @refresh reset

/**
 * @module ContentCard
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
import './ContentCard.css';

export type ContentCardVariant = 'vertical' | 'horizontal' | 'background';

export interface ContentCardProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /** Hero/background image URL */
  imageSrc: string;
  /** Alt text for the image */
  imageAlt: string;
  /** Small top text for brand/category context (e.g. "Ray-Ban, Oakley, Costa & more") */
  eyebrow?: string;
  /** Primary text */
  headline: string;
  /** Secondary descriptive line */
  subtext?: string;
  /** CTA button/link text ("Shop now", "Learn more", "Get started") */
  ctaLabel?: string;
  /** CTA link destination */
  ctaHref?: string;
  /** Click handler for the entire card */
  onClick?: () => void;
  /** Layout variant */
  variant?: ContentCardVariant;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

/**
 * ContentCard — Marketing/promotional content card used in homepage grids.
 *
 * Supports three layout variants:
 * - `vertical` (default): image on top, text below
 * - `horizontal`: image on the left, text on the right
 * - `background`: full-bleed background image with overlaid text
 */
export function ContentCard(props: ContentCardProps) {
  const {
    imageSrc,
    imageAlt,
    eyebrow,
    headline,
    subtext,
    ctaLabel,
    ctaHref,
    onClick,
    variant = 'vertical',
    className,
    ...rest
  } = applyCommonProps(props);

  const isClickable = !!(onClick || ctaHref);
  const Tag = onClick ? 'button' : 'div';

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else if (ctaHref) {
      window.location.href = ctaHref;
    }
  };

  return (
    <Tag
      className={cx(
        'ld-content-card-root',
        `ld-content-card-${variant}`,
        isClickable ? 'ld-content-card-clickable' : undefined,
        className,
      )}
      onClick={isClickable ? handleClick : undefined}
      {...(Tag === 'button' ? {type: 'button' as const} : {})}
      {...(rest as any)}
    >
      {variant === 'background' ? (
        <>
          <img
            src={imageSrc}
            alt={imageAlt}
            className="ld-content-card-bg-image"
            aria-hidden="true"
          />
          <div className="ld-content-card-bg-overlay" />
          <div className="ld-content-card-bg-content">
            {eyebrow && (
              <span className="ld-content-card-eyebrow">{eyebrow}</span>
            )}
            <span className="ld-content-card-headline">{headline}</span>
            {subtext && (
              <span className="ld-content-card-subtext">{subtext}</span>
            )}
            {ctaLabel && (
              <span className="ld-content-card-cta">{ctaLabel}</span>
            )}
          </div>
        </>
      ) : (
        <>
          <div className="ld-content-card-image-wrapper">
            <img
              src={imageSrc}
              alt={imageAlt}
              className="ld-content-card-image"
            />
          </div>
          <div className="ld-content-card-body">
            {eyebrow && (
              <span className="ld-content-card-eyebrow">{eyebrow}</span>
            )}
            <span className="ld-content-card-headline">{headline}</span>
            {subtext && (
              <span className="ld-content-card-subtext">{subtext}</span>
            )}
            {ctaLabel && (
              <span className="ld-content-card-cta">{ctaLabel}</span>
            )}
          </div>
        </>
      )}
    </Tag>
  );
}
ContentCard.displayName = 'ContentCard';
