// @refresh reset

/**
 * @module Tag
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
 * #### Leading icon
 * 
 * The Tag accepts a leading icon through the `leading` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import * as Icon from '@livingdesign/icons';
 * import {Tag} from '@livingdesign/react';
 * 
 * export default () => {
 *   return <Tag leading={<Icon.Check />}>Tag content</Tag>;
 * };
 * ```
 * 
 * ### Features
 * 
 * #### Color
 * 
 * The Tag's `color` can be set to any of the general semantic categories or accent colors:
 * 
 * ```tsx
 * <Tag color="blue">Tag content</Tag> // default
 * <Tag color="brand">Tag content</Tag>
 * <Tag color="cyan">Tag content</Tag>
 * <Tag color="edited">Tag content</Tag>
 * <Tag color="gray">Tag content</Tag>
 * <Tag color="green">Tag content</Tag>
 * <Tag color="info">Tag content</Tag>
 * <Tag color="negative">Tag content</Tag>
 * <Tag color="orange">Tag content</Tag>
 * <Tag color="pink">Tag content</Tag>
 * <Tag color="positive">Tag content</Tag>
 * <Tag color="purple">Tag content</Tag>
 * <Tag color="red">Tag content</Tag>
 * <Tag color="spark">Tag content</Tag>
 * <Tag color="teal">Tag content</Tag>
 * <Tag color="warning">Tag content</Tag>
 * <Tag color="yellow">Tag content</Tag>
 * ```
 * 
 * #### Variant
 * 
 * Tag has three variants:
 * 
 * - `primary`: Use for critical information that requires visual emphasis to draw user attention.
 * - `secondary`: Use for information that requires neutral visibility. (default)
 * - `tertiary`: Use for information that requires low visibility that is not distracting to users.
 * 
 * ```tsx
 * <Tag variant="primary">Tag content</Tag>
 * <Tag variant="secondary">Tag content</Tag>
 * <Tag variant="tertiary">Tag content</Tag>
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import './Tag.css';
export type TagColor =
  | 'blue'
  | 'brand'
  | 'cyan'
  | 'edited'
  | 'gray'
  | 'green'
  | 'info'
  | 'negative'
  | 'orange'
  | 'pink'
  | 'positive'
  | 'purple'
  | 'red'
  | 'spark'
  | 'teal'
  | 'warning'
  | 'yellow';

export type TagVariant = 'primary' | 'secondary' | 'tertiary';

export interface TagProps
  extends Omit<React.ComponentPropsWithoutRef<'span'>, 'className' | 'style'> {
  /**
   * The content for the tag.
   */
  children: React.ReactNode;
  /**
   * The color for the tag.
   *
   * @default "brand"
   */
  color?: TagColor;
  /**
   * The leading content for the tag.
   */
  leading?: React.ReactNode;
  /**
   * The variant for the tag.
   *
   * @default "secondary"
   */
  variant?: TagVariant;
}

/**
 * Tags are used to draw a customer’s focus to item traits such as availability, status, or media rating. Items may be products, fulfillment slots, or something else. They are visual only and non-interactive.
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/components/tag/ Guidelines}
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/components/tag/ React documentation}
 *
 */
export const Tag: React.FunctionComponent<TagProps> = (props) => {
  const {
    children,
    className,
    color = 'brand',
    leading,
    variant = 'secondary',
    ...rest
  } = applyCommonProps(props);

  return (
    <span
      className={cx('ld-tag-tag', color === 'blue' && 'ld-tag-blue', color === 'brand' && 'ld-tag-brand', color === 'cyan' && 'ld-tag-cyan', color === 'edited' && 'ld-tag-edited', color === 'gray' && 'ld-tag-gray', color === 'green' && 'ld-tag-green', color === 'info' && 'ld-tag-info', color === 'negative' && 'ld-tag-negative', color === 'orange' && 'ld-tag-orange', color === 'pink' && 'ld-tag-pink', color === 'positive' && 'ld-tag-positive', color === 'purple' && 'ld-tag-purple', color === 'red' && 'ld-tag-red', color === 'spark' && 'ld-tag-spark', color === 'teal' && 'ld-tag-teal', color === 'warning' && 'ld-tag-warning', color === 'yellow' && 'ld-tag-yellow', variant === 'primary' && 'ld-tag-primary', variant === 'secondary' && 'ld-tag-secondary', variant === 'tertiary' && 'ld-tag-tertiary', className)}
      {...rest}
    >
      {leading && <span className={'ld-tag-leadingIcon'}>{leading}</span>}

      {children}
    </span>
  );
};

Tag.displayName = 'Tag';
