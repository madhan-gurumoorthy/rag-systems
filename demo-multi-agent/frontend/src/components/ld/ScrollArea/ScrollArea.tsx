'use client';
// @refresh reset

/**
 * @module ScrollArea
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
import {cx, applyCommonProps, type CommonProps} from '../common';
import './ScrollArea.css';

// ---------------------------------------------------------------------------
// ScrollArea
// ---------------------------------------------------------------------------

export interface ScrollAreaProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  children: React.ReactNode;
}

export const ScrollArea: React.FunctionComponent<ScrollAreaProps> = (props) => {
  const {className, children, ...rest} = applyCommonProps(props);

  return (
    <div className={cx('ld-scroll-area-root', className)} {...rest}>
      <div className="ld-scroll-area-viewport">
        {children}
      </div>
    </div>
  );
};

ScrollArea.displayName = 'ScrollArea';

// ---------------------------------------------------------------------------
// ScrollBar
// ---------------------------------------------------------------------------

export interface ScrollBarProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  /** Orientation of the scrollbar. @default "vertical" */
  orientation?: 'vertical' | 'horizontal';
}

export const ScrollBar: React.FunctionComponent<ScrollBarProps> = (props) => {
  const {className, orientation = 'vertical', ...rest} = applyCommonProps(props);

  return (
    <div
      className={cx(
        'ld-scroll-area-scrollbar',
        `ld-scroll-area-scrollbar--${orientation}`,
        className,
      )}
      {...rest}
    />
  );
};

ScrollBar.displayName = 'ScrollBar';
