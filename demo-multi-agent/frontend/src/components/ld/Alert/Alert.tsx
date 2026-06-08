// @refresh reset

/**
 * @module Alert
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
 * #### Action button
 * 
 * The Alert has an optional action button that allows users to interact. Set the `actionButtonProps` prop to enable the action button:
 * 
 * ```tsx
 * <Alert
 *   actionButtonProps={{
 *     children: 'Action button',
 *     onClick(event) {
 *       console.log(event);
 *     },
 *   }}
 * >
 *   Alert
 * </Alert>
 * ```
 * 
 * You can also change the action button to an `HTMLAnchorElement` by setting `href`:
 * 
 * ```tsx
 * <Alert
 *   actionButtonProps={{
 *     children: 'Go to account',
 *     href: 'https://www.walmart.com/account',
 *     target: '_blank',
 *   }}
 * >
 *   Alert
 * </Alert>
 * ```
 * 
 * ### Features
 * 
 * #### Variant
 * 
 * The Alert comes with four variants:
 * 
 * - `error`: Conveys a negative message to the user.
 * - `info`: Provides general information in a highlighted way.
 * - `success`: Conveys a positive message to the user.
 * - `warning`: Draws the users attention to something that may affect their experience and maybe require their attention.
 * 
 * Set the Alert's variant with the `variant` prop:
 * 
 * ```tsx
 * <Alert variant="error">Error</Alert>
 * <Alert variant="info">Info</Alert>
 * <Alert variant="success">Success</Alert>
 * <Alert variant="warning">Warning</Alert>
 * ```
 * 
 * ### Accessibility
 * 
 * The variant is used as an a11y label on the Alert's leading icon. This label can be overwritten using the `a11yIconLabel` prop:
 * 
 * ```tsx
 * <Alert variant="error" a11yIconLabel="problem">
 *   Error
 * </Alert>
 * ```
 * 
 * ## FAQ
 * 
 * ### I want to dynamically display the `Alert` component. How do I make this experience accessible?
 * 
 * - `aria-live="polite"`: For informational contents that are less intrusive (usually `success`, `info`, and `warning` variants).
 * - `role="alert"`: For errors or alert contents that need immediate attention (usually the `error` variant).
 * 
 * One of the following attributes should be added to the component's parent DOM element. The parent container element must be present with in DOM on page load (in cannot be injected dynamically).
 */

import * as React from 'react';
import {cx, applyCommonProps, getTarget, invariant, onAnchorKeyDown} from '../common';
import {VisuallyHidden} from '../VisuallyHidden';
import {
  ExclamationCircleIcon,
  InfoCircleIcon,
  CheckCircleIcon,
  WarningIcon,
} from '../Icons';
import './Alert.css';

// ---------------------------------------------------------------------------
// AlertActionButton
// ---------------------------------------------------------------------------

interface AlertActionButtonBaseProps {
  children: React.ReactNode;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export type AlertActionButtonAnchorProps = AlertActionButtonBaseProps &
  React.ComponentPropsWithRef<'a'> & { href: string };

export type AlertActionButtonButtonProps = AlertActionButtonBaseProps &
  React.ComponentPropsWithRef<'button'>;

export type AlertActionButtonProps =
  | AlertActionButtonAnchorProps
  | AlertActionButtonButtonProps;

const isAnchor = (
  props: AlertActionButtonProps
): props is AlertActionButtonAnchorProps => 'href' in props;

/**
 * @private
 */
const AlertActionButton = React.forwardRef<
  HTMLAnchorElement | HTMLButtonElement,
  AlertActionButtonProps
>((props, ref) => {
  const {className, ...rest} = applyCommonProps(props);
  const classes = cx('ld-alert-alertactionbutton-action', className);

  if (isAnchor(props)) {
    const {
      children,
      href,
      onClick,
      onKeyDown: anchorOnKeyDown,
      target,
      ...anchorProps
    } = rest as Partial<AlertActionButtonAnchorProps>;

    const handleKeyDown = onAnchorKeyDown({href, onClick, onKeyDown: anchorOnKeyDown});

    return (
      <a
        className={classes}
        href={href}
        onClick={onClick}
        onKeyDown={handleKeyDown}
        ref={ref as React.ForwardedRef<HTMLAnchorElement>}
        {...getTarget(target)}
        {...anchorProps}
      >
        {children}
      </a>
    );
  }

  const {...buttonProps} = rest as Partial<AlertActionButtonButtonProps>;

  return (
    <button
      className={classes}
      ref={ref as React.ForwardedRef<HTMLButtonElement>}
      type="button"
      {...buttonProps}
    />
  );
});

AlertActionButton.displayName = 'AlertActionButton';

// ---------------------------------------------------------------------------
// Alert
// ---------------------------------------------------------------------------

export type AlertVariant = 'error' | 'info' | 'success' | 'warning';

export interface AlertProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  a11yIconLabel?: string;
  actionButtonProps?: AlertActionButtonProps;
  children: React.ReactNode;
  /** @default "success" */
  variant?: AlertVariant;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

const VARIANT_CLASS: Record<AlertVariant, string> = {
  error: 'ld-alert-error',
  info: 'ld-alert-info',
  success: 'ld-alert-success',
  warning: 'ld-alert-warning',
};

const VARIANT_ICON: Record<AlertVariant, React.FC<{size?: 'small' | 'medium' | 'large'}>> = {
  error: ExclamationCircleIcon,
  info: InfoCircleIcon,
  success: CheckCircleIcon,
  warning: WarningIcon,
};

export const Alert: React.FunctionComponent<AlertProps> = (props) => {
  const {
    a11yIconLabel,
    actionButtonProps,
    children,
    className,
    variant = 'success',
    ...rest
  } = applyCommonProps(props);

  invariant(
    a11yIconLabel === undefined || (typeof a11yIconLabel === 'string' && a11yIconLabel.trim().length > 0),
    '`Alert` accessibility violation. If `a11yIconLabel` is provided it must be a non-empty string. Omit it to use the variant name as the icon label.',
  );

  const Icon = VARIANT_ICON[variant];

  return (
    <div
      className={cx('ld-alert-alert', VARIANT_CLASS[variant], className)}
      {...rest}
    >
      <span className="ld-alert-leading">
        <VisuallyHidden>{`${a11yIconLabel ?? variant}:`}</VisuallyHidden>
        <Icon size="small" />
      </span>
      <div className="ld-alert-content">
        <div>{children}</div>
        {actionButtonProps && <AlertActionButton {...actionButtonProps} />}
      </div>
    </div>
  );
};

Alert.displayName = 'Alert';
