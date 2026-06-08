// @refresh reset

/**
 * @module WCPRating
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
import {cx, applyCommonProps, invariant, emit} from '../common';
import './WCPRating.css';

export type WCPRatingSize = 'small' | 'medium';

export interface WCPRatingProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style' | 'onChange'> {
  value?: number;
  /** @default 0 */
  defaultValue?: number;
  onChange?: (value: number) => void;
  /** @default 'medium' */
  size?: WCPRatingSize;
  /** @default false */
  disabled?: boolean;
  'aria-label'?: string;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

const LABELS: Record<number, string> = {
  0: 'Unrated',
  1: 'Very poor',
  2: 'Poor',
  3: 'Fair',
  4: 'Good',
  5: 'Excellent',
};

function StarFillPath() {
  return (
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M10.3546 0.0883354C10.5059 0.168053 10.6286 0.29664 10.7048 0.455086L13.4008 6.06688L19.3303 7.01797C19.7611 7.08706 20.0568 7.50874 19.9908 7.95981C19.9652 8.13514 19.8863 8.29717 19.7659 8.42195L15.5027 12.8413L16.7615 19.0006C16.8527 19.4469 16.5812 19.886 16.1551 19.9815C15.9824 20.0202 15.8022 19.9971 15.6436 19.9159L9.99994 17.0282L4.35633 19.9159C3.96482 20.1163 3.49235 19.9463 3.30106 19.5363C3.22352 19.3701 3.20147 19.1815 3.23843 19.0006L4.4972 12.8413L0.233942 8.42195C-0.0757466 8.10092 -0.078292 7.57776 0.228257 7.25344C0.347406 7.12739 0.502127 7.04483 0.669543 7.01797L6.59906 6.06688L9.29513 0.455086C9.49097 0.0474376 9.96529 -0.116762 10.3546 0.0883354Z"
      fill="#ffc220"
    />
  );
}

function StarBorderPath() {
  return (
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M12.4368 7.35907L9.99994 2.28692L7.56314 7.35907L2.04708 8.24385L6.0474 12.3907L4.89361 18.0363L9.99994 15.4234L15.1063 18.0363L13.9525 12.3907L17.9528 8.24385L12.4368 7.35907ZM13.4008 6.06688L10.7048 0.455085C10.6286 0.29664 10.5059 0.168053 10.3546 0.0883354C9.9653 -0.116762 9.49097 0.0474376 9.29513 0.455085L6.59906 6.06688L0.669543 7.01797C0.502127 7.04483 0.347406 7.12739 0.228256 7.25344C-0.078292 7.57776 -0.0757466 8.10092 0.233942 8.42195L4.4972 12.8413L3.23843 19.0006C3.20147 19.1815 3.22352 19.3701 3.30106 19.5363C3.49235 19.9463 3.96482 20.1163 4.35633 19.9159L9.99994 17.0282L15.6436 19.9159C15.8022 19.9971 15.9824 20.0202 16.1551 19.9815C16.5812 19.886 16.8527 19.4469 16.7615 19.0006L15.5027 12.8413L19.7659 8.42195C19.8863 8.29717 19.9652 8.13514 19.9908 7.95981C20.0568 7.50874 19.7611 7.08706 19.3303 7.01797L13.4008 6.06688Z"
      fill="#cc851a"
    />
  );
}

function StarEmptyPath() {
  return (
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M12.5974 7.1437L9.99994 1.73711L7.40246 7.1437L1.55913 8.08098L5.78903 12.4658L4.56117 18.4738L9.99994 15.6909L15.4387 18.4738L14.2109 12.4658L18.4408 8.08098L12.5974 7.1437ZM13.4008 6.06688L10.7048 0.455085C10.6286 0.29664 10.5059 0.168053 10.3546 0.0883354C9.9653 -0.116762 9.49097 0.0474376 9.29513 0.455085L6.59906 6.06688L0.669543 7.01797C0.502127 7.04483 0.347406 7.12739 0.228256 7.25344C-0.078292 7.57776 -0.0757466 8.10092 0.233942 8.42195L4.4972 12.8413L3.23843 19.0006C3.20147 19.1815 3.22352 19.3701 3.30106 19.5363C3.49235 19.9463 3.96482 20.1163 4.35633 19.9159L9.99994 17.0282L15.6436 19.9159C15.8022 19.9971 15.9824 20.0202 16.1551 19.9815C16.5812 19.886 16.8527 19.4469 16.7615 19.0006L15.5027 12.8413L19.7659 8.42195C19.8863 8.29717 19.9652 8.13514 19.9908 7.95981C20.0568 7.50874 19.7611 7.08706 19.3303 7.01797L13.4008 6.06688Z"
      fill="#cc851a"
    />
  );
}

function StarIcon({filled, hovered}: {filled: boolean; hovered: boolean}) {
  const isHighlighted = filled || hovered;
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" className="ld-wcp-rating-starSvg">
      {isHighlighted ? (<><StarFillPath /><StarBorderPath /></>) : (<StarEmptyPath />)}
    </svg>
  );
}

export const WCPRating = React.forwardRef<HTMLDivElement, WCPRatingProps>((props, ref) => {
  const {value: controlledValue, defaultValue = 0, onChange, size = 'medium', disabled = false, 'aria-label': ariaLabelProp, className, ...rest} = applyCommonProps(props);

  invariant(
    ariaLabelProp === undefined || (typeof ariaLabelProp === 'string' && ariaLabelProp.trim().length > 0),
    '`WCPRating` accessibility violation. If `aria-label` is provided it must be a non-empty string. Omit it to use the default "Star rating" label.',
  );

  const ariaLabel = ariaLabelProp && ariaLabelProp.trim().length > 0 ? ariaLabelProp : 'Star rating';

  const isControlled = controlledValue !== undefined;
  const [internalValue, setInternalValue] = React.useState(defaultValue);
  const value = isControlled ? controlledValue! : internalValue;
  const [hoverValue, setHoverValue] = React.useState(0);
  const displayValue = hoverValue > 0 ? hoverValue : value;

  const handleClick = (star: number) => {
    if (disabled) return;
    const next = star === value ? 0 : star;
    if (!isControlled) setInternalValue(next);
    emit('ui:rating:change', {value: next, previous: value});
    onChange?.(next);
  };

  const handleMouseEnter = (star: number) => { if (!disabled) setHoverValue(star); };
  const handleMouseLeave = () => { setHoverValue(0); };

  const handleKeyDown = (e: React.KeyboardEvent, star: number) => {
    if (disabled) return;
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleClick(star); }
  };

  return (
    <div
      ref={ref}
      className={cx('ld-wcp-rating-rating', `ld-wcp-rating-${size}`, disabled && 'ld-wcp-rating-disabled', className)}
      onMouseLeave={handleMouseLeave}
      {...rest}
    >
      <div role="radiogroup" aria-label={ariaLabel} aria-disabled={disabled} className="ld-wcp-rating-stars">
        {Array.from({length: 5}, (_, i) => {
          const star = i + 1;
          const filled = star <= value;
          const hovered = hoverValue > 0 && star <= hoverValue;
          const isSelected = star === value;
          return (
            <button
              key={star}
              type="button"
              role="radio"
              aria-checked={isSelected}
              aria-label={`${star} star${star !== 1 ? 's' : ''}`}
              disabled={disabled}
              onClick={() => handleClick(star)}
              onMouseEnter={() => handleMouseEnter(star)}
              onKeyDown={(e) => handleKeyDown(e, star)}
              className="ld-wcp-rating-starBtn"
            >
              <StarIcon filled={filled} hovered={hovered} />
            </button>
          );
        })}
      </div>
      <span className="ld-wcp-rating-label" aria-live="polite" aria-atomic="true">
        {LABELS[displayValue] ?? LABELS[0]}
      </span>
    </div>
  );
});

WCPRating.displayName = 'WCPRating';
