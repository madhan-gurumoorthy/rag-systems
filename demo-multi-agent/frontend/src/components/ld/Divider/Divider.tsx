// @refresh reset

/**
 * @module Divider
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
 * 
 * ## Implementation
 * 
 * ### Accessibility
 * 
 * The Divider is ignored by screen-readers by default.
 * 
 * If the Divider should be called out by screen-readers, an accessibility label can be added through the `title` prop.
 * 
 * (Note: if the divider is used as decoration, the `title` prop should be omitted.)
 * 
 * ```tsx
 * <Divider title="Descriptive Title" />
 * ```
 */

import * as React from 'react';
import {cx, invariant, applyCommonProps} from '../common';
import './Divider.css';
export interface DividerProps
  extends Omit<React.ComponentPropsWithoutRef<'hr'>, 'className' | 'style'> {
  /**
   * The title for the divider.
   *
   * If the divider is used as decoration, this property should be omitted.
   */
  title?: string;
}

/**
 * Dividers create visual breaks in content.
 * *
 */
export const Divider: React.FunctionComponent<DividerProps> = (props) => {
  const {
    'aria-label': ariaLabel,
    className,
    title,
    ...rest
  } = applyCommonProps(props);

  // Convert boolean strings to pure booleans. !bool can have unintended side-effects.
  // `ariaHidden` should default to `true` unless overridden.
  const ariaHidden = !(
    rest['aria-hidden'] === 'false' || rest['aria-hidden'] === false
  );

  invariant(
    !!(ariaHidden || ariaLabel !== undefined || title !== undefined),
    '`Divider` accessibility violation. `Divider` requires an accessible label if `aria-hidden` is false.'
  );

  return (
    <hr
      aria-hidden={ariaHidden}
      className={cx('ld-divider-divider', className)}
      {...(title && {title})}
      {...rest}
    />
  );
};

Divider.displayName = 'Divider';
