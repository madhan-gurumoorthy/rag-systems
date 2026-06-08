// @refresh reset

/**
 * @module Metric
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
 * #### Title and value
 * 
 * The Metric must include a title and value, which can be provided through the `title` and `value` props:
 * 
 * ```tsx
 * <Metric title="Sales" value="100" />
 * ```
 * 
 * #### Text label
 * 
 * The Metric accepts an optional `textLabel` prop to provide a description of the metric:
 * 
 * ```tsx
 * <Metric textLabel="Goal: 200" title="Sales" value="100" />
 * ```
 * 
 * #### Timescope
 * 
 * Set the timescope for the Metric with the `timescope` prop:
 * 
 * ```tsx
 * <Metric timescope="YTD" title="Sales" value="100" />
 * ```
 * 
 * #### Unit
 * 
 * Set the unit for the Metric with the `unit` prop:
 * 
 * ```tsx
 * <Metric title="Sales" unit="Units sold" value="100" />
 * ```
 * 
 * ### Features
 * 
 * #### Variant
 * 
 * The Metric comes with five variants:
 * 
 * - `neutral`: Used to show data at a point in time without trend.
 * - `positiveUp`: Used to show an upward trend (an increase in value) that indicates a positive change.
 * - `positiveDown`: Used to show a downward trend (a decrease in value) that indicates a positive change.
 * - `negativeUp`: Used to show an upward trend (an increase in value) that indicates a negative change.
 * - `negativeDown`: Used to show a downward trend (a decrease in value) that indicates a negative change.
 * 
 * Set the Metric's variant with the `variant` prop:
 * 
 * ```tsx
 * <Metric
 *   title="Title"
 *   value="Value"
 *   variant="neutral"
 * />
 * 
 * <Metric
 *   title="Title"
 *   value="Value"
 *   variant="positiveUp"
 * />
 * 
 * <Metric
 *   title="Title"
 *   value="Value"
 *   variant="positiveDown"
 * />
 * 
 * <Metric
 *   title="Title"
 *   value="Value"
 *   variant="negativeUp"
 * />
 * 
 * <Metric
 *   title="Title"
 *   value="Value"
 *   variant="negativeDown"
 * />
 * ```
 * 
 * ### Accessibility
 * 
 * The Metric includes an accessible label on the trend indicator icon for screen-readers. This label can be overridden using the `allyTrendIndicatorLabel` prop:
 * 
 * ```tsx
 * <Metric
 *   allyTrendIndicatorLabel="Trending way up"
 *   title="Title"
 *   value="Value"
 *   variant="positiveUp"
 * />
 * ```
 * 
 * ## FAQ
 * 
 * ### How do I configure title as a heading?
 * 
 * - We can achieve this by passing the `title` prop a heading element. See example below.
 * 
 * ```tsx
 * <Metric
 *   title={
 *     <h2
 *       style={{
 *         display: 'inline',
 *         fontSize: '100%',
 *         fontWeight: 'inherit',
 *         lineHeight: 'inherit',
 *         margin: 0,
 *       }}
 *     >
 *       Title
 *     </h2>
 *   }
 *   value="42"
 * />
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import {
  ArrowUpIcon,
  ArrowDownIcon,
} from '../Icons';
import {Body, Display, Heading} from '../Text';
import './Metric.css';
export type MetricVariant =
  | 'negativeDown'
  | 'negativeUp'
  | 'neutral'
  | 'positiveDown'
  | 'positiveUp';

export interface MetricProps
  extends Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'style' | 'title'
    > {
  /**
   * The accessible label for the metric's trend indicator.
   */
  a11yTrendIndicatorLabel?: string;
  /**
   * The text label providing a description of the metric.
   */
  textLabel?: React.ReactNode;
  /**
   * The timescope for the metric.
   */
  timescope?: React.ReactNode;
  /**
   * The title for the metric.
   */
  title: React.ReactNode;
  /**
   * The unit for the metric.
   */
  unit?: React.ReactNode;
  /**
   * The value for the metric.
   */
  value: React.ReactNode;
  /**
   * The variant for the metric.
   *
   * @default "neutral"
   */
  variant?: MetricVariant;
}

/**
 * Metrics display the value of a significant data point.
 * *
 */
export const Metric: React.FunctionComponent<MetricProps> = (props) => {
  const {
    a11yTrendIndicatorLabel,
    className,
    textLabel,
    timescope,
    title,
    unit,
    value,
    variant = 'neutral',
    ...rest
  } = applyCommonProps(props);

  return (
    <div
      className={cx(variant === 'negativeDown' && 'ld-metric-negativeDown', variant === 'negativeUp' && 'ld-metric-negativeUp', variant === 'neutral' && 'ld-metric-neutral', variant === 'positiveDown' && 'ld-metric-positiveDown', variant === 'positiveUp' && 'ld-metric-positiveUp', className)}
      {...rest}
    >
      <Body
        as="div"
        size={"medium"}
        weight={"alt"}
      >
        {title}
      </Body>
      {timescope && (
        <Body
          as="div"
          size={"small"}
          UNSAFE_className={'ld-metric-timescope'}
        >
          {timescope}
        </Body>
      )}
      <div className={'ld-metric-valueContainer'}>
        <Display
          as="span"
          size={"small"}
          weight={"alt"}
          UNSAFE_className={'ld-metric-value'}
        >
          {value}
        </Display>
        {unit && (
          <Heading
            as="span"
            size={"small"}
            weight={"alt"}
            UNSAFE_className={'ld-metric-unit'}
          >
            {unit}
          </Heading>
        )}
      </div>
      {textLabel && (
        <div className={'ld-metric-labelContainer'}>
          {variant !== 'neutral' && (
            <span className={'ld-metric-trendIndicator'}>
              {variant === 'negativeDown' || variant === 'positiveDown' ? (
                <ArrowDownIcon
                  a11yLabel={a11yTrendIndicatorLabel ?? 'Trending down'}
                />
              ) : (
                <ArrowUpIcon
                  a11yLabel={a11yTrendIndicatorLabel ?? 'Trending up'}
                />
              )}
            </span>
          )}

          <Body
            UNSAFE_className={'ld-metric-textLabel'}
            size={"small"}
          >
            {textLabel}
          </Body>
        </div>
      )}
    </div>
  );
};

Metric.displayName = 'Metric';
