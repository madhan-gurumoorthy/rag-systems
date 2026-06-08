'use client';
// @refresh reset

/**
 * @module Spinner
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
 * Spinner comes in two colors:
 * 
 * ```tsx
 * <Spinner color="neutral" /> (default)
 * <Spinner color="white" />
 * ```
 * 
 * #### Size
 * 
 * Spinner comes in two sizes:
 * 
 * ```tsx
 * <Spinner size="large" /> (default)
 * <Spinner size="small" />
 * ```
 * 
 * ### Accessibility
 * 
 * Spinner has a default label. Override it using the `a11yLabel` property:
 * 
 * ```tsx
 * <Spinner a11yLabel="Cargando…" />
 * ```
 * 
 * ## Accessibility
 * 
 * ### How do I make Spinner accessible if it's in a scrim?
 * 
 * Announce a message such as “Loading…Please wait”. Use either:
 * 
 * - An `aria-live` region
 * - The [A11Y Announcement](/develop/react/utilities/a11y-announcement/) utility
 * 
 * ### How do I make Spinner accessible if it's in a Button?
 * 
 * 1. Change the Button's label to “Loading…”
 * 2. Announce a message such as “Loading…Please wait” using the [A11Y Announcement](/develop/react/utilities/a11y-announcement/) utility
 * 
 * The reason for both: Jaws and some screen readers do not fully support the
 * announcement of changes in a button’s label or a component’s accessible name.
 * Therefore, pushing an `aria-live` announcement along with the label change
 * ensures that the screen reader user is going to be aware of it. (Don’t use
 * `aria-busy` as it has limited support at this time.)
 */
import * as React from 'react';
import {cx, useStableId, applyCommonProps} from '../common';
import './Spinner.css';
export type SpinnerColor = 'neutral' | 'white';

export type SpinnerSize = 'large' | 'small';

export interface SpinnerProps
  extends Omit<React.ComponentPropsWithoutRef<'span'>, 'className' | 'style'> {
  /**
   * The accessible label for the spinner.
   *
   * @default "Loading…"
   */
  a11yLabel?: string;
  /**
   * The color for the spinner.
   *
   * @default "neutral"
   */
  color?: SpinnerColor;
  /**
   * The size for the spinner.
   *
   * @default "large"
   */
  size?: SpinnerSize;
  /**
   * The props spread to the spinner's svg element.
   *
   * @default {}
   */
  spinnerProps?: React.ComponentPropsWithoutRef<'svg'>;
}

/**
 * Spinners visually indicate that a process is taking place for an indeterminate amount of time.
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/components/spinner/ Guidelines}
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/components/spinner/ React documentation}
 *
 */
export const Spinner: React.FunctionComponent<SpinnerProps> = (props) => {
  const {
    a11yLabel = 'Loading…',
    className,
    color = 'neutral',
    size = 'large',
    spinnerProps = {},
    ...rest
  } = applyCommonProps(props);

  const uniqueTitleId = useStableId();

  return (
    <span
      className={cx('ld-spinner-container', size === 'large' && 'ld-spinner-large', size === 'small' && 'ld-spinner-small', className)}
      role="status"
      {...rest}
    >
      <svg
        aria-labelledby={uniqueTitleId}
        className={cx(color === 'neutral' && 'ld-spinner-neutral', color === 'white' && 'ld-spinner-white')}
        role="img"
        viewBox="0 0 48 48"
        xmlns="http://www.w3.org/2000/svg"
        {...spinnerProps}
      >
        <title id={uniqueTitleId}>{a11yLabel}</title>
        <defs>
          <path
            d="M23.7833 1.55122C21.9046 1.55122 20.3818 3.07279 20.3818 4.94971C20.3818 5.77181 21.2057 14.5072 21.496 15.3808C21.8287 16.382 22.7456 17.0508 23.7833 17.0508C24.8209 17.0508 25.7378 16.382 26.0705 15.3808C26.3608 14.5072 27.1847 5.77181 27.1847 4.94971C27.1847 3.07279 25.6618 1.55122 23.7833 1.55122Z"
            id="ld-spinner-pill"
          />
        </defs>
        <use className={'ld-spinner-pill'} href="#ld-spinner-pill" />
        <use
          className={cx('ld-spinner-pill', 'ld-spinner-pill2')}
          href="#ld-spinner-pill"
        />
        <use
          className={cx('ld-spinner-pill', 'ld-spinner-pill3')}
          href="#ld-spinner-pill"
        />
        <use
          className={cx('ld-spinner-pill', 'ld-spinner-pill4')}
          href="#ld-spinner-pill"
        />
        <use
          className={cx('ld-spinner-pill', 'ld-spinner-pill5')}
          href="#ld-spinner-pill"
        />
        <use
          className={cx('ld-spinner-pill', 'ld-spinner-pill6')}
          href="#ld-spinner-pill"
        />
      </svg>
    </span>
  );
};

Spinner.displayName = 'Spinner';
