// @refresh reset

/**
 * @module Badge
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
 * ### Content
 * 
 * The Badge accepts optional content through the `children` prop:
 * 
 * ```tsx
 * <Badge>10</Badge>
 * ```
 * 
 * ### Features
 * 
 * #### Color
 * 
 * The Badge's `color` can be set to any of the general semantic categories or accent colors:
 * 
 * ```tsx
 * <Badge color="blue" />
 * <Badge color="brand" />
 * <Badge color="brandBold" />
 * <Badge color="cyan" />
 * <Badge color="edited" />
 * <Badge color="gray" />
 * <Badge color="green" />
 * <Badge color="info" />
 * <Badge color="negative" />
 * <Badge color="neutral" />
 * <Badge color="orange" />
 * <Badge color="pink" />
 * <Badge color="positive" />
 * <Badge color="purple" />
 * <Badge color="red" />
 * <Badge color="spark" />
 * <Badge color="teal" />
 * <Badge color="warning" />
 * <Badge color="yellow" />
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import './Badge.css';

export type BadgeColor =
  | 'blue' | 'brand' | 'brandBold' | 'cyan' | 'edited'
  | 'gray' | 'green' | 'info' | 'negative' | 'neutral'
  | 'orange' | 'pink' | 'positive' | 'purple' | 'red'
  | 'spark' | 'teal' | 'warning' | 'yellow';

export interface BadgeProps
  extends Omit<React.ComponentPropsWithoutRef<'span'>, 'className' | 'style'> {
  children?: React.ReactNode;
  /** @default "blue" */
  color?: BadgeColor;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

const COLOR_CLASS: Record<BadgeColor, string> = {
  blue: 'ld-badge-blue',
  brand: 'ld-badge-brand',
  brandBold: 'ld-badge-brandBold',
  cyan: 'ld-badge-cyan',
  edited: 'ld-badge-edited',
  gray: 'ld-badge-gray',
  green: 'ld-badge-green',
  info: 'ld-badge-info',
  negative: 'ld-badge-negative',
  neutral: 'ld-badge-neutral',
  orange: 'ld-badge-orange',
  pink: 'ld-badge-pink',
  positive: 'ld-badge-positive',
  purple: 'ld-badge-purple',
  red: 'ld-badge-red',
  spark: 'ld-badge-spark',
  teal: 'ld-badge-teal',
  warning: 'ld-badge-warning',
  yellow: 'ld-badge-yellow',
};

export const Badge: React.FunctionComponent<BadgeProps> = (props) => {
  const {children, color = 'blue', className, ...rest} = applyCommonProps(props);

  const hasTextLabel =
    typeof children !== 'boolean' &&
    children !== null &&
    typeof children !== 'undefined';

  return (
    <span
      className={cx(
        'ld-badge-badge',
        hasTextLabel && 'ld-badge-hasTextLabel',
        COLOR_CLASS[color],
        className
      )}
      {...rest}
    >
      {children}
    </span>
  );
};

Badge.displayName = 'Badge';
