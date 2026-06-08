// @refresh reset

/**
 * @module LinkButton
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
 * #### Leading and trailing icon
 * 
 * The Link Button accepts optional leading or trailing icons through the `leading` and `trailing' props:
 * 
 * ```tsx
 * import * as React from 'react';
 * import * as Icon from '@livingdesign/icons';
 * import {LinkButton} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <LinkButton
 *       href="https://www.walmart.com/cart"
 *       leading={<Icon.Home />}
 *       trailing={<Icon.ChevronRight />}
 *     >
 *       Navigate to home
 *     </LinkButton>
 *   );
 * };
 * ```
 * 
 * ### Features
 * 
 * #### Color
 * 
 * The Link Button comes in three colors:
 * 
 * - `default` (default)
 * - `subtle`
 * - `white`
 * 
 * Set the color with the `color` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {LinkButton} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <>
 *       <LinkButton color="default">Default</LinkButton>
 *       <LinkButton color="subtle">Subtle</LinkButton>
 *       <LinkButton color="white">White</LinkButton>
 *     </>
 *   );
 * };
 * ```
 * 
 * #### Size
 * 
 * The Link Button comes with three sizes:
 * 
 * - `small` (default)
 * - `medium`
 * - `large`
 * 
 * Set the Link Button's size with the `size` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {LinkButton} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <>
 *       <LinkButton size="large">Large</LinkButton>
 *       <LinkButton size="medium">Medium</LinkButton>
 *       <LinkButton size="small">Small</LinkButton>
 *     </>
 *   );
 * };
 * ```
 * 
 * ### Interaction
 * 
 * #### Linking
 * 
 * The Link Button can be configured to be an `HTMLAnchorElement` or an `HTMLButtonElement` depending on the props passed to it.
 * 
 * Provide an `href` prop to make the Link Button an `HTMLAnchorElement`:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {LinkButton} from '@livingdesign/react';
 * 
 * export default () => {
 *   return <LinkButton href="https://www.walmart.com/">Walmart Home</LinkButton>;
 * };
 * ```
 * 
 * Otherwise, the Link Button will be rendered as an `HTMLButtonElement` and accept the `disabled` and `type` attributes as props:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {LinkButton} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <LinkButton
 *       disabled={false}
 *       onClick={(event) => console.log(event)}
 *       type="submit"
 *     >
 *       Submit
 *     </LinkButton>
 *   );
 * };
 * ```
 * 
 * ### Layout
 * 
 * #### Width
 * 
 * The Link Button can be configured to fill the width of its parent using the `isFullWidth` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {LinkButton} from '@livingdesign/react';
 * 
 * export default () => {
 *   return <LinkButton isFullWidth>Full width</LinkButton>;
 * };
 * ```
 */

import * as React from 'react';
import {cx, getTarget, applyCommonProps} from '../common';
import './LinkButton.css';
export type LinkButtonColor = 'default' | 'subtle' | 'white';

export type LinkButtonSize = 'large' | 'medium' | 'small';

export type LinkButtonType = 'button' | 'reset' | 'submit';

interface LinkButtonBaseProps {
  /**
   * The content for the link button.
   */
  children: React.ReactNode;
  /**
   * The color for the link button.
   *
   * @default "default"
   */
  color?: LinkButtonColor;
  /**
   * If the link button is displayed at full width.
   *
   * @default false
   */
  isFullWidth?: boolean;
  /**
   * The leading icon for the link button.
   */
  leading?: React.ReactNode;
  /**
   * The size for the link button.
   *
   * @default "small"
   */
  size?: LinkButtonSize;
  /**
   * The trailing icon for the link button.
   */
  trailing?: React.ReactNode;
}

export type LinkButtonAnchorProps = LinkButtonBaseProps &
  Omit<React.ComponentPropsWithRef<'a'>, 'className' | 'style'> & {
    /**
     * The href for the link button (Anchor only).
     */
    href: string;
  };

export type LinkButtonButtonProps = LinkButtonBaseProps &
  Omit<React.ComponentPropsWithRef<'button'>, 'className' | 'style'> & {
    /**
     * If the link button is disabled (Button only).
     *
     * @default false
     */
    disabled?: boolean;
    /**
     * The type for the link button (Button only).
     *
     * @default "button"
     */
    type?: LinkButtonType;
  };

export type LinkButtonPolymorphicType = {
  (props: LinkButtonAnchorProps): React.ReactElement;
  (props: LinkButtonButtonProps): React.ReactElement;
  displayName?: string;
};

export type LinkButtonProps = LinkButtonAnchorProps | LinkButtonButtonProps;

const isAnchor = (props: LinkButtonProps): props is LinkButtonAnchorProps =>
  'href' in props;

/* eslint-disable-next-line @typescript-eslint/naming-convention */
const _LinkButton = React.forwardRef<
  HTMLAnchorElement | HTMLButtonElement,
  LinkButtonProps
>((props, ref) => {
  const {
    children: childrenProp,
    className: classNameProp,
    color = 'default',
    isFullWidth = false,
    leading,
    size = 'small',
    trailing,
    ...rest
  } = applyCommonProps(props);

  const children = [leading, childrenProp, trailing];

  const className = cx('ld-linkbutton-linkButton', color === 'subtle' && 'ld-linkbutton-subtle', color === 'white' && 'ld-linkbutton-white', isFullWidth && 'ld-linkbutton-isFullWidth', size === 'large' && 'ld-linkbutton-large', size === 'medium' && 'ld-linkbutton-medium', size === 'small' && 'ld-linkbutton-small', classNameProp);

  if (isAnchor(props)) {
    const {target, ...anchorProps} = rest as Partial<LinkButtonAnchorProps>;

    return (
      <a
        className={className}
        ref={ref as React.ForwardedRef<HTMLAnchorElement>}
        {...getTarget(target)}
        {...anchorProps}
      >
        {children}
      </a>
    );
  }

  const {type = 'button', ...buttonProps} =
    rest as Partial<LinkButtonButtonProps>;

  return (
    <button
      className={className}
      ref={ref as React.ForwardedRef<HTMLButtonElement>}
      /* eslint-disable-next-line react/button-has-type */
      type={type}
      {...buttonProps}
    >
      {children}
    </button>
  );
});

_LinkButton.displayName = 'LinkButton';

/**
 * Link Button is an interactive element that has a link-like appearance.
 *
 */
export const LinkButton = _LinkButton as LinkButtonPolymorphicType;
