// @refresh reset

/**
 * @module Link
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
 * ### Features
 * 
 * #### Color
 * 
 * The Link comes in three colors:
 * 
 * - `default` (default)
 * - `subtle`
 * - `white`
 * 
 * Set the color with the `color` prop:
 * 
 * ```tsx
 * <Link color="default" href="https://www.walmart.com">
 *   Default
 * </Link>
 * <Link color="subtle" href="https://www.walmart.com">
 *   Subtle
 * </Link>
 * <Link color="white" href="https://www.walmart.com">
 *   White
 * </Link>
 * ```
 * 
 * ### Interaction
 * 
 * #### Linking
 * 
 * The Link returns an anchor element. It can be configured with an `href` prop, which is forwarded to the anchor.
 * 
 * Set the optional `target` property to change where the anchor opens:
 * 
 * ```tsx
 * <Link href="https://www.walmart.com/plus" target="_blank">
 *   Walmart+
 * </Link>
 * ```
 * 
 * #### On click
 * 
 * The Link can be configured with custom behavior. Add a callback handler function using the `onClick` prop:
 * 
 * ```tsx
 * <Link
 *   href="https://www.walmart.com/plus"
 *   onClick={(event) => console.log(event)}
 * >
 *   Content
 * </Link>
 * ```
 */

import * as React from 'react';
import {cx, getTarget, applyCommonProps} from '../common';
import './Link.css';
export type LinkColor = 'default' | 'subtle' | 'white';

export interface LinkProps
  extends Omit<React.ComponentPropsWithRef<'a'>, 'className' | 'style'> {
  /**
   * The content for the link.
   */
  children: React.ReactNode;
  /**
   * The color for the link.
   *
   * @default "default"
   */
  color?: LinkColor;
  /**
   * The href for the link.
   */
  href: string;
  /**
   * The callback fired when the link is clicked.
   */
  onClick?: (event: React.MouseEvent<HTMLAnchorElement>) => void;
  /**
   * The target for the link.
   */
  target?: string;
}

/**
 * Links are navigational elements.
 * *
 */
export const Link = React.forwardRef<HTMLAnchorElement, LinkProps>(
  (props, ref) => {
    const {
      children,
      color = 'default',
      className,
      target,
      ...rest
    } = applyCommonProps(props);

    return (
      <a
        className={cx('ld-link-link', color === 'subtle' && 'ld-link-subtle', color === 'white' && 'ld-link-white', className)}
        ref={ref}
        {...getTarget(target)}
        {...rest}
      >
        {children}
      </a>
    );
  }
);

Link.displayName = 'Link';
