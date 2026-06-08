// @refresh reset

/**
 * @module WCPFloatingButton
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
import {cx, applyCommonProps, invariant} from '../common';
import './WCPFloatingButton.css';

export type WCPFloatingButtonSize = 'xsmall' | 'small' | 'medium' | 'large';

export interface WCPFloatingButtonProps
  extends Omit<React.ComponentPropsWithoutRef<'button'>, 'className' | 'style'> {
  children: React.ReactNode;
  /** @default 'medium' */
  size?: WCPFloatingButtonSize;
  'aria-label': string;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

const SIZE_CLASS: Record<WCPFloatingButtonSize, string> = {
  xsmall: 'ld-wcp-floatingbutton-xsmall',
  small: 'ld-wcp-floatingbutton-small',
  medium: 'ld-wcp-floatingbutton-medium',
  large: 'ld-wcp-floatingbutton-large',
};

export const WCPFloatingButton: React.FunctionComponent<WCPFloatingButtonProps> = (props) => {
  const {children, size = 'medium', disabled = false, 'aria-label': ariaLabel, className, ...rest} = applyCommonProps(props);

  invariant(
    typeof ariaLabel === 'string' && ariaLabel.trim().length > 0,
    '`WCPFloatingButton` accessibility violation. `aria-label` is required and must be a non-empty string — this is an icon-only button with no visible text.',
  );

  return (
    <button
      type="button"
      className={cx('ld-wcp-floatingbutton-button', SIZE_CLASS[size], className)}
      aria-label={ariaLabel}
      disabled={disabled}
      {...rest}
    >
      <span className="ld-wcp-floatingbutton-iconWrap">{children}</span>
    </button>
  );
};

WCPFloatingButton.displayName = 'WCPFloatingButton';
