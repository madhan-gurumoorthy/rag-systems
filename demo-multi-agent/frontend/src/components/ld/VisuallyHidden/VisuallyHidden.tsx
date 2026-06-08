// @refresh reset

/**
 * @module VisuallyHidden
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
 * Pass content to be visually hidden through the `children` prop:
 * 
 * ```tsx
 * <VisuallyHidden>
 *   I'm visually hidden but available to screen readers.
 * </VisuallyHidden>
 * ```
 * 
 * ### Features
 * 
 * #### Element type
 * 
 * Change the HTML element returned by the VisuallyHidden by setting the `as` property. By default it returns a `span` element.
 * 
 * ```tsx
 * <VisuallyHidden as="h1">I'm visually hidden heading</VisuallyHidden>
 * <VisuallyHidden as="div">I'm visually hidden span</VisuallyHidden>
 * <VisuallyHidden as="p">I'm visually hidden paragraph</VisuallyHidden>
 * ```
 * 
 * #### Focusable
 * 
 * `isFocusable` property can be set to make `VisuallyHidden`’s element visible when focused. This must be paired with a focusable element or positive `tabIndex` property.
 * 
 * ```tsx
 * <VisuallyHidden as="a" href="#content" isFocusable>I'm visually hidden until focused</VisuallyHidden>
 * <VisuallyHidden isFocusable tabIndex={0}>I'm visually hidden until focused</VisuallyHidden>
 * ```
 * 
 * ### Skip Links
 * 
 * `VisuallyHidden` can be leveraged to create “skip links” that are visible when focused:
 * 
 * ```tsx
 * <VisuallyHidden as="a" href="#content" isFocusable>
 *   Skip to content
 * </VisuallyHidden>
 * ```
 * 
 * ## FAQ
 * 
 * ### I am having layout or overflow issues. What can I do?
 * 
 * `VisuallyHidden` can cause layout bugs in certain cases due to its implementation. To fix this, we recommend wrapping the components with a relatively positioned parent element:
 * 
 * ```tsx
 * <div style={{position: 'relative'}}>
 *   <VisuallyHidden>Visually hidden</VisuallyHidden>
 *   Visible content…
 *   <VisuallyHidden>Visually hidden</VisuallyHidden>
 * </div>
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps, PolymorphicElementWithoutRef} from '../common';
import './VisuallyHidden.css';
interface VisuallyHiddenBaseProps
  extends Omit<
      React.ComponentPropsWithoutRef<React.ElementType>,
      'className' | 'style'
    > {
  /**
   * The content for the visually hidden.
   */
  children: React.ReactNode;
  /**
   * Whether the element should become visible on focus for the visually hidden.
   *
   * @default false;
   */
  isFocusable?: boolean;
}

export type VisuallyHiddenProps<T extends React.ElementType> =
  PolymorphicElementWithoutRef<T, VisuallyHiddenBaseProps>;

/**
 * Visually Hidden is a utility component that makes content available for screen readers only.
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/utilities/visually-hidden/ React documentation}
 *
 */
export const VisuallyHidden = <T extends React.ElementType = 'span'>(
  props: VisuallyHiddenProps<T>
) => {
  const {
    as: Component = 'span',
    className,
    isFocusable = false,
    ...rest
  } = applyCommonProps(props);

  return (
    <Component
      className={cx('ld-visuallyhidden-visuallyHidden', isFocusable && 'ld-visuallyhidden-visuallyHiddenFocusable', className)}
      {...rest}
    />
  );
};

VisuallyHidden.displayName = 'VisuallyHidden';
