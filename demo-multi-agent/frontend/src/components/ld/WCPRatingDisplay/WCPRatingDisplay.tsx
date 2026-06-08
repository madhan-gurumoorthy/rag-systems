// @refresh reset

/**
 * @module WCPRatingDisplay
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
import {Rating} from '../Rating';
import './WCPRatingDisplay.css';

export type WCPRatingDisplaySize = 'small' | 'medium';
export type WCPRatingDisplayColor = 'default' | 'inverse';

export interface WCPRatingDisplayProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  value?: number;
  size?: WCPRatingDisplaySize;
  color?: WCPRatingDisplayColor;
  count?: string;
  linkText?: string;
  linkHref?: string;
  onLinkClick?: (e: React.MouseEvent) => void;
  text?: string;
  'aria-label'?: string;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export const WCPRatingDisplay: React.FunctionComponent<WCPRatingDisplayProps> = (props) => {
  const {value = 0, size = 'small', color = 'default', count, linkText, linkHref, onLinkClick, text, 'aria-label': ariaLabel, className, ...rest} = applyCommonProps(props);
  const starSize = size === 'medium' ? 'large' : 'small';
  const isInverse = color === 'inverse';
  const hasContent = count || linkText || text;

  return (
    <div
      className={cx(
        'ld-wcp-ratingdisplay-wrapper',
        size === 'small' && 'ld-wcp-ratingdisplay-wrapperSmall',
        size === 'medium' && 'ld-wcp-ratingdisplay-wrapperMedium',
        isInverse && 'ld-wcp-ratingdisplay-wrapperInverse',
        className,
      )}
      {...rest}
    >
      <span className={isInverse ? 'ld-wcp-ratingdisplay-starsInverse' : undefined}>
        <Rating
          value={value}
          size={starSize}
          a11yLabel={ariaLabel || `Rating: ${value} out of 5 stars`}
        />
      </span>
      {hasContent && (
        <div className="ld-wcp-ratingdisplay-content">
          {(count || linkText) && (
            <span className="ld-wcp-ratingdisplay-leftGroup">
              {count && <span className="ld-wcp-ratingdisplay-count">{count}</span>}
              {linkText && (
                <a href={linkHref ?? '#'} className="ld-wcp-ratingdisplay-link" onClick={onLinkClick} aria-label={linkText}>
                  {linkText}
                </a>
              )}
            </span>
          )}
          {(count || linkText) && text && (
            <span className="ld-wcp-ratingdisplay-pipe" aria-hidden="true">|</span>
          )}
          {text && <span className="ld-wcp-ratingdisplay-text">{text}</span>}
        </div>
      )}
    </div>
  );
};
WCPRatingDisplay.displayName = 'WCPRatingDisplay';
