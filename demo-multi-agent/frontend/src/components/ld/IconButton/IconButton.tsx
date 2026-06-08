// @refresh reset

/**
 * @module IconButton
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
 * The Icon Button accepts an icon to display through the `children` prop.
 * 
 * ```tsx
 * import * as React from 'react';
 * import {IconButton} from '@livingdesign/react';
 * import * as Icon from '@livingdesign/icons';
 * 
 * export default () => {
 *   return (
 *     <IconButton
 *       a11yLabel="Cart"
 *     >
 *       <Icon.Star />
 *     </IconButton>
 *   );
 * };
 * ```
 * 
 * ### Features
 * 
 * #### Color
 * 
 * The Icon Button supports two color options:
 * 
 * - `default` (default)
 * - `white`
 * 
 * Set the button color using the `color` prop. For example, `color="white"` applies a white color to the button and icon.
 * 
 * #### Size
 * 
 * The Icon Button comes in four sizes:
 * 
 * - `xsmall`
 * - `small` (default)
 * - `medium`
 * - `large`
 * 
 * Set the Icon Button's size using the `size` prop. The icon inside will automatically be set to the expected size.
 * 
 * #### Variant
 * 
 * The Icon Button supports two variants for border radius:
 * 
 * - `round` (default)
 * - `full`
 * 
 * Set the button's border radius using the `variant` prop. For example, `variant="full"` applies a fully rounded style.
 * 
 * #### Linking
 * 
 * The Icon Button can be configured to be an `HTMLAnchorElement` or an `HTMLButtonElement` depending on the props passed to it.
 * 
 * Provide an `href` prop to make the Icon Button an `HTMLAnchorElement`:
 * 
 * ```tsx
 * <IconButton href="https://www.walmart.com/" a11yLabel="Home">
 *   <Icon.Home />
 * </IconButton>
 * ```
 * 
 * Otherwise, the Icon Button will be rendered as an `HTMLButtonElement` and accept the `type` and `disabled` attributes as props:
 * 
 * ```tsx
 * <IconButton type="submit" disabled a11yLabel="Submit">
 *   <Icon.Submit />
 * </IconButton>
 * ```
 * 
 * ### Accessibility
 * 
 * The Icon Button requires an accessible label. Set the accessible label through the `a11yLabel` prop.
 */

import * as React from 'react';
import {cx, invariant, getTarget, onAnchorKeyDown, applyCommonProps, WithIconProps, emit} from '../common';
import './IconButton.css';
export type IconButtonSize = 'large' | 'medium' | 'small' | 'xsmall';
export type IconButtonColor = 'default' | 'white';
export type IconButtonVariant = 'round' | 'full';

interface IconButtonBaseProps {
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
  /**
   * The accessible label for the icon button.
   */
  a11yLabel: string;
  /**
   * The content for the icon button.
   */
  children: React.ReactNode;
  /**
   * The color of the icon button.
   *
   * @default "default"
   */
  color?: IconButtonColor;
  /**
   * The size for the icon button.
   *
   * @default "small"
   */
  size?: IconButtonSize;
  /**
   * The variant for the icon button.
   *
   * @default "round"
   */
  variant?: IconButtonVariant;
}

export type IconButtonAnchorProps = IconButtonBaseProps &
  Omit<JSX.IntrinsicElements['a'], 'className' | 'style'> & {
    /**
     * The href for the icon button (Anchor only).
     */
    href: string;
  };

export type IconButtonButtonProps = IconButtonBaseProps &
  Omit<JSX.IntrinsicElements['button'], 'className' | 'style'> & {
    /**
     * If the icon button is disabled (Button only).
     *
     * @default false
     */
    disabled?: boolean;
  };

export type IconButtonProps = IconButtonAnchorProps | IconButtonButtonProps;

export type IconButtonPolymorphicType = {
  (props: IconButtonAnchorProps): JSX.Element;
  (props: IconButtonButtonProps): JSX.Element;
  displayName?: string;
};

const isAnchor = (props: IconButtonProps): props is IconButtonAnchorProps =>
  'href' in props;

/* eslint-disable-next-line @typescript-eslint/naming-convention */
const _IconButton = React.forwardRef<
  HTMLAnchorElement | HTMLButtonElement,
  IconButtonProps
>((props, ref) => {
  const {
    a11yLabel,
    children,
    className,
    size = 'small',
    color = 'default',
    variant = 'round',
    ...rest
  } = applyCommonProps(props);

  invariant(
    !!a11yLabel,
    '`IconButton` accessibility violation. `IconButton` requires an `a11yLabel`.'
  );

  const classes = cx('ld-iconbutton-iconButton', color === 'white' && 'ld-iconbutton-white', color === 'default' && 'ld-iconbutton-defaultColor', size === 'xsmall' && 'ld-iconbutton-xsmall', variant == 'round' && 'ld-iconbutton-round', variant === 'full' && 'ld-iconbutton-full', className);

  const content = React.isValidElement<WithIconProps>(children)
    ? React.cloneElement(children, {size: size === 'xsmall' ? 'small' : size})
    : children;

  if (isAnchor(props)) {
    const {
      href,
      onClick,
      onKeyDown: anchorOnKeyDown,
      target,
      ...anchorProps
    } = rest as Partial<IconButtonAnchorProps>;

    const handleAnchorClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
      emit('ui:icon-button:click', {a11yLabel, href});
      onClick?.(e);
    };

    const onKeyDown = onAnchorKeyDown({
      href,
      onClick,
      onKeyDown: anchorOnKeyDown,
    });

    return (
      <a
        aria-label={a11yLabel}
        className={classes}
        href={href}
        onClick={handleAnchorClick}
        onKeyDown={onKeyDown}
        ref={ref as React.ForwardedRef<HTMLAnchorElement>}
        {...getTarget(target)}
        {...anchorProps}
      >
        {content}
      </a>
    );
  }

  const {onClick: onButtonClick, ...buttonRest} = rest as Partial<IconButtonButtonProps>;

  const handleButtonClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    emit('ui:icon-button:click', {a11yLabel});
    onButtonClick?.(e);
  };

  return (
    <button
      aria-label={a11yLabel}
      className={classes}
      ref={ref as React.ForwardedRef<HTMLButtonElement>}
      type="button"
      onClick={handleButtonClick}
      {...buttonRest}
    >
      {content}
    </button>
  );
});

_IconButton.displayName = 'IconButton';

/**
 * Icon Buttons trigger actions and rely solely on icons to convey their purpose.
 * *
 */
export const IconButton = _IconButton as IconButtonPolymorphicType;
