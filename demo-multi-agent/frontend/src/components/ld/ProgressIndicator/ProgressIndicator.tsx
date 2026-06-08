'use client';
// @refresh reset

/**
 * @module ProgressIndicator
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
 * ### Value
 * 
 * The Progress Indicator tracks progress by comparing the minimum, maximum and current values.
 * 
 * For example, with the default minimum and maximum values (0 and 100) and a current value of 50, the Progress Indicator will appear to be half filled.
 * 
 * Set the maximum value with the `max` prop.
 * Set the minimum value with the `min` prop.
 * Set the current value with the `value` prop.
 * 
 * ```tsx
 * <ProgressIndicator min={0} max={50} value={25} valueLabel="Step 2 of 4" />
 * ```
 * 
 * In order to support visually impaired users, the Progress Indicator requires a value label as an additional indicator of progress through the process being tracked.
 * 
 * Set the `valueLabel` prop to provide a descriptive label:
 * 
 * ```tsx
 * <ProgressIndicator valueLabel="Step 2 of 4" />
 * ```
 * 
 * ### Features
 * 
 * #### Variant
 * 
 * The Progress Indicator comes with four variants:
 * 
 * - `error`: Conveys a negative message to the user.
 * - `info`: Provides general information in a highlighted way.
 * - `success`: Conveys a positive message to the user.
 * - `warning`: Draws the users attention to something that may affect their experience and maybe require their attention.
 * 
 * Set the Progress Indicator's variant with the `variant` prop:
 * 
 * ```tsx
 * <ProgressIndicator variant="error" valueLabel="Step 2 of 4" />
 * <ProgressIndicator variant="info" valueLabel="Step 2 of 4" />
 * <ProgressIndicator variant="success" valueLabel="Step 2 of 4" />
 * <ProgressIndicator variant="warning" valueLabel="Step 2 of 4" />
 * ```
 */
import * as React from 'react';
import {cx, useStableId, invariant, applyCommonProps} from '../common';
import './ProgressIndicator.css';
export type ProgressIndicatorVariant = 'error' | 'info' | 'success' | 'warning';

interface ProgressIndicatorBaseProps
  extends Omit<React.ComponentPropsWithoutRef<'span'>, 'className' | 'style'> {
  /**
   * The maximum value for the progress indicator.
   *
   * @default 100
   */
  max?: number;
  /**
   * The minimum value for the progress indicator.
   *
   * @default 0
   */
  min?: number;
  /**
   * The value for the progress indicator.
   *
   * @default 0
   */
  value?: number;
  /**
   * The value label for the progress indicator.
   */
  valueLabel: string;
  /**
   * The variant for the progress indicator.
   *
   * @default "info"
   */
  variant?: ProgressIndicatorVariant;
}

export interface ProgressIndicatorA11yProps extends ProgressIndicatorBaseProps {
  /**
   * The accessible label reference IDs for the progress indicator (Required if omitting `label`).
   */
  a11yLabelledBy: string;
  label?: never;
}

export interface ProgressIndicatorLabelProps
  extends ProgressIndicatorBaseProps {
  /**
   * The label for the progress indicator (Required if omitting `a11yLabelledBy`).
   */
  label: React.ReactNode;
  a11yLabelledBy?: never;
}

export type ProgressIndicatorProps =
  | ProgressIndicatorA11yProps
  | ProgressIndicatorLabelProps;

/**
 * Progress Indicators display a visual representation of the completion of a task or process.
 * *
 */
export const ProgressIndicator: React.FunctionComponent<
  ProgressIndicatorProps
> = (props) => {
  const {
    a11yLabelledBy,
    className,
    label,
    max = 100,
    min = 0,
    value = 0,
    valueLabel,
    variant = 'info',
    ...rest
  } = applyCommonProps(props);

  const labelCount = (label ? 1 : 0) + (a11yLabelledBy ? 1 : 0) === 1;

  invariant(
    labelCount,
    '`ProgressIndicator` accessibility violation. `ProgressIndicator` requires a `label` OR an `a11yLabelledBy`.'
  );

  const labelId = useStableId();

  return (
    <span
      aria-valuemax={max}
      aria-valuemin={min}
      aria-valuenow={value}
      className={cx('ld-progressindicator-progressIndicator', className)}
      role="progressbar"
      {...(a11yLabelledBy && {'aria-labelledby': a11yLabelledBy})}
      {...(label && {'aria-labelledby': labelId})}
      {...{'aria-valuetext': valueLabel}}
      {...rest}
    >
      <span className={'ld-progressindicator-track'}>
        <span
          className={cx('ld-progressindicator-trackFill', variant === 'error' && 'ld-progressindicator-error', variant === 'info' && 'ld-progressindicator-info', variant === 'success' && 'ld-progressindicator-success', variant === 'warning' && 'ld-progressindicator-warning')}
          style={{
            width: `${((value - min) / (max - min)) * 100}%`,
          }}
        />
      </span>

      <span className={'ld-progressindicator-labelContainer'}>
        <span className={'ld-progressindicator-label'} {...(label && {id: labelId})}>
          {label}
        </span>

        <span className={'ld-progressindicator-valueLabel'}>{valueLabel}</span>
      </span>
    </span>
  );
};

ProgressIndicator.displayName = 'ProgressIndicator';
