'use client';
// @refresh reset

/**
 * @module Banner
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
 * #### Variant
 * 
 * The Banner comes with four variants:
 * 
 * - `error`: Use to convey a high emphasis or urgent message, such as a blocking error that needs to be resolved.
 * - `info`: Use to convey a message with default urgency or emphasis.
 * - `success`: Used to convey a positive message.
 * - `warning`: Used to a convey an emphasized warning message, such as something that the user should consider as it may impede their progress.
 * 
 * Set the Banner's variant with the `variant` prop:
 * 
 * ```tsx
 * <Banner variant="error">Error</Banner>
 * <Banner variant="info">Info</Banner>
 * <Banner variant="success">Success</Banner>
 * <Banner variant="warning">Warning</Banner>
 * ```
 * 
 * ### Closing
 * 
 * The Banner has a close button. Add a callback handler function using the `onClose` prop:
 * 
 * ```tsx
 * <Banner onClose={(event) => console.log(event)}>Banner</Banner>
 * ```
 */
import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import {
  CloseIcon,
} from '../Icons';
import './Banner.css';
// ---------------------------------------------------------------------------
// BannerCloseButton (inlined sub-component)
// ---------------------------------------------------------------------------

export interface BannerCloseButtonProps
  extends Omit<
      React.ComponentPropsWithRef<'button'>,
      'children' | 'className' | 'style' | 'type'
    > {}

/**
 * @private
 */
export const BannerCloseButton = React.forwardRef<
  HTMLButtonElement,
  BannerCloseButtonProps
>((props, ref) => {
  const {className, ...rest} = applyCommonProps(props);

  return (
    <button
      className={cx('ld-banner-bannerclosebutton-close', className)}
      ref={ref}
      type="button"
      {...rest}
    >
      <CloseIcon size={"small"} className={'ld-banner-bannerclosebutton-closeIcon'} />
    </button>
  );
});

export type BannerVariant = 'error' | 'info' | 'success' | 'warning';

export interface BannerProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /**
   * The props spread to the banner's close button.
   */
  closeButtonProps?: BannerCloseButtonProps;
  /**
   * The content for the banner.
   */
  children: React.ReactNode;
  /**
   * The callback fired when the banner requests to close.
   */
  onClose: (event: React.MouseEvent<HTMLButtonElement>) => void;
  /**
   * The variant for the banner.
   *
   * @default "info"
   */
  variant?: BannerVariant;
}

/**
 * Banners provide brief information about a significant incident affecting a large number of users.
 * *
 */
export const Banner: React.FunctionComponent<BannerProps> = (props) => {
  const {
    children,
    className,
    closeButtonProps,
    onClose,
    variant = 'info',
    ...rest
  } = applyCommonProps(props);

  return (
    <div
      className={cx('ld-banner-banner', variant === 'error' && 'ld-banner-error', variant === 'info' && 'ld-banner-info', variant === 'success' && 'ld-banner-success', variant === 'warning' && 'ld-banner-warning', className)}
      role="alert"
      {...rest}
    >
      <div className={'ld-banner-contentContainer'}>
        <div className={'ld-banner-content'}>{children}</div>
      </div>

      <BannerCloseButton
        aria-label="Close banner"
        {...closeButtonProps}
        onClick={(event) => {
          closeButtonProps?.onClick?.(event);

          onClose(event);
        }}
      />
    </div>
  );
};

Banner.displayName = 'Banner';
