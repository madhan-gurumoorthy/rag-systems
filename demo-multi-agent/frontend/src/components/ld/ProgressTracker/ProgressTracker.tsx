// @refresh reset

/**
 * @module ProgressTracker
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
 * The Progress Tracker accepts Progress Tracker Item elements through the `children` props:
 * 
 * ```tsx
 * <ProgressTracker>
 *   <ProgressTrackerItem>One</ProgressTrackerItem>
 *   <ProgressTrackerItem>Two</ProgressTrackerItem>
 * </ProgressTracker>
 * ```
 * 
 * ### Features
 * 
 * #### Active index
 * 
 * Set the active index for the Progress Tracker through the `activeIndex` prop:
 * 
 * ```tsx
 * <ProgressTracker activeIndex={2}>
 *   <ProgressTrackerItem>One</ProgressTrackerItem>
 *   <ProgressTrackerItem>Two</ProgressTrackerItem>
 *   <ProgressTrackerItem>Three</ProgressTrackerItem>
 * </ProgressTracker>
 * ```
 * 
 * #### Variant
 * 
 * The Progress Tracker comes with four variants:
 * 
 * - `error`: Conveys a negative message to the user.
 * - `info`: Provides general information in a highlighted way.
 * - `success`: Conveys a positive message to the user.
 * - `warning`: Draws the users attention to something that may affect their experience and maybe require their attention.
 * 
 * Set the Progress Tracker's variant with the `variant` prop:
 * 
 * ```tsx
 * <ProgressTracker variant="error">
 *   <ProgressTrackerItem>Error</ProgressTrackerItem>
 * </ProgressTracker>
 * <ProgressTracker variant="info">
 *   <ProgressTrackerItem>Info</ProgressTrackerItem>
 * </ProgressTracker>
 * <ProgressTracker variant="success">
 *   <ProgressTrackerItem>Success</ProgressTrackerItem>
 * </ProgressTracker>
 * <ProgressTracker variant="warning">
 *   <ProgressTrackerItem>Warning</ProgressTrackerItem>
 * </ProgressTracker>
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import {VisuallyHidden} from '../VisuallyHidden';
import './ProgressTracker.css';
// ---------------------------------------------------------------------------
// ProgressTrackerItem (inlined sub-component)
// ---------------------------------------------------------------------------

export interface ProgressTrackerItemProps
  extends Omit<React.ComponentPropsWithoutRef<'span'>, 'className' | 'style'> {
  /**
   * The accessible label for the progress tracker item indicator.
   */
  a11yIndicatorLabel?: string;
  /**
   * The content for the progress tracker item.
   */
  children?: React.ReactNode;
}

/**
 * Progress Tracker Item
 * *
 */
export const ProgressTrackerItem: React.FunctionComponent<
  ProgressTrackerItemProps
> = (props) => {
  const {a11yIndicatorLabel, children, className, ...rest} = applyCommonProps(props);

  return (
    <span
      className={cx('ld-progresstracker-progresstrackeritem-progressTrackerItem', children && 'ld-progresstracker-progresstrackeritem-hasLabel', className)}
      {...rest}
    >
      <VisuallyHidden>{a11yIndicatorLabel}</VisuallyHidden>
      <svg
        aria-hidden
        className={'ld-progresstracker-progresstrackeritem-indicator'}
        viewBox="0 0 16 16"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle className={'ld-progresstracker-progresstrackeritem-indicatorOuter'} cx="8" cy="8" r="7" />
        <circle className={'ld-progresstracker-progresstrackeritem-indicatorInner'} cx="8" cy="8" r="4" />
      </svg>

      {children}
    </span>
  );
};

ProgressTrackerItem.displayName = 'ProgressTrackerItem';

export type ProgressTrackerVariant = 'error' | 'info' | 'success' | 'warning';

export interface ProgressTrackerProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /**
   * The active index for the progress tracker.
   *
   * @default 0
   */
  activeIndex?: number;
  /**
   * The content for the progress tracker.
   */
  children?: React.ReactNode;
  /**
   * The variant for the progress tracker.
   *
   * @default "info"
   */
  variant?: ProgressTrackerVariant;
}

/**
 * Progress Trackers are visual representations of a user's progress through a set of steps. They inform the user of the number of steps required to complete a specified process.
 * *
 */
export const ProgressTracker: React.FunctionComponent<ProgressTrackerProps> = (
  props
) => {
  const {
    activeIndex = 0,
    children,
    className,
    variant = 'info',
    ...rest
  } = applyCommonProps(props);
  const lastIndex = React.Children.count(children) - 1;

  let clampedIndex;

  if (lastIndex >= 0 && activeIndex > lastIndex) {
    clampedIndex = lastIndex;
  } else if (activeIndex < 0) {
    clampedIndex = 0;
  } else {
    clampedIndex = activeIndex;
  }

  return (
    <div
      className={cx('ld-progresstracker-progressTracker', variant === 'error' && 'ld-progresstracker-error', variant === 'info' && 'ld-progresstracker-info', variant === 'success' && 'ld-progresstracker-success', variant === 'warning' && 'ld-progresstracker-warning', className)}
      {...rest}
    >
      <div className={'ld-progresstracker-trackContainer'}>
        <span className={'ld-progresstracker-track'}>
          <span
            className={'ld-progresstracker-indicator'}
            style={{width: `${(100 * clampedIndex) / lastIndex}%`}}
          />
        </span>
      </div>

      <div className={'ld-progresstracker-items'} role="list">
        {React.Children.map(children, (child, index) => {
          if (!React.isValidElement(child)) {
            return null;
          }

          return React.cloneElement(child, {
            ...child.props,
            a11yIndicatorLabel:
              child.props.a11yIndicatorLabel ??
              (activeIndex > index
                ? 'Complete,'
                : activeIndex === index
                  ? 'Current,'
                  : 'Not complete,'),
            UNSAFE_className: cx(activeIndex >= index && 'ld-progresstracker-progresstrackeritem-isActive', activeIndex === index && 'ld-progresstracker-progresstrackeritem-isCurrent', variant === 'error' && 'ld-progresstracker-progresstrackeritem-error', variant === 'info' && 'ld-progresstracker-progresstrackeritem-info', variant === 'success' && 'ld-progresstracker-progresstrackeritem-success', variant === 'warning' && 'ld-progresstracker-progresstrackeritem-warning', child.props.UNSAFE_className),
            key: index,
            role: 'listitem',
            UNSAFE_style: {
              ...child.props.UNSAFE_style,
              width: `${
                index === 0 || index === lastIndex
                  ? 50 / lastIndex
                  : 100 / lastIndex
              }%`,
            },
          });
        })}
      </div>
    </div>
  );
};

ProgressTracker.displayName = 'ProgressTracker';
