'use client';
// @refresh reset

/**
 * @module Callout
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
 * ### Accessibility
 * 
 * The Callout component must be configured as follows to meet accessibility requirements:
 * 
 * 1. Must provide a single, button-like target element as its children
 * 1. Must provide a description of the target element in `a11yContentLabel`
 * 1. Must provide the target element's ref as its `targetRef`
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Button, Callout} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [isOpen, setIsOpen] = React.useState(false);
 *   const ref = React.useRef();
 * 
 *   return (
 *     <Callout
 *       a11yContentLabel="Target information"
 *       isOpen={isOpen}
 *       onClose={(event) => {
 *         setIsOpen(false);
 *       }}
 *       trigger={
 *         <Button ref={ref} variant="primary">
 *           Trigger
 *         </Button>
 *       }
 *       triggerRef={ref}
 *     >
 *       Example Callout content.
 *     </Callout>
 *   );
 * };
 * ```
 * 
 * ### Layout
 * 
 * #### Position
 * 
 * The Callout has eight positions:
 * 
 * - `bottomCenter` (default)
 * - `bottomLeft`
 * - `bottomRight`
 * - `left`
 * - `right`
 * - `topCenter`
 * - `topLeft`
 * - `topRight`
 * 
 * Set the Callout's position with the `position` prop:
 * 
 * ```tsx
 * <Callout
 *   position="topRight"
 *   {...}
 * >
 *   {...}
 * </Callout>
 * ```
 * 
 * ## FAQ
 * 
 * ### How do I ensure my target element announces correctly?
 * 
 * Don’t add `aria-label` on the target element when the Callout is opened. Certain screen readers will announce `aria-label` instead of the Callout’s content.
 */
import * as React from 'react';
import {cx, useStableId, invariant, applyCommonProps, getPositionStyle, CalculatePositionFn, CSSTransition, useCSSTransition} from '../common';
import {VisuallyHidden} from '../VisuallyHidden';
import './Callout.css';

// ---------------------------------------------------------------------------
// BaseCallout (inlined sub-component)
// ---------------------------------------------------------------------------

export type BaseCalloutPosition =
  | 'bottomCenter'
  | 'bottomLeft'
  | 'bottomRight'
  | 'left'
  | 'right'
  | 'topCenter'
  | 'topLeft'
  | 'topRight';

export interface BaseCalloutOwnProps {
  /**
   * The props spread to the callout's close button.
   */
  closeButtonProps?: CalloutCloseButtonProps;
  /**
   * The callback fired when the callout requests to close.
   */
  onClose: (event: React.MouseEvent) => void;
}

export interface BaseCalloutProps
  extends React.ComponentPropsWithoutRef<'div'>,
    BaseCalloutOwnProps {
  /**
   * The position for the callout in relation to its target.
   */
  position: BaseCalloutPosition;
}

/**
 * @private
 */
export const BaseCallout = React.forwardRef<HTMLDivElement, BaseCalloutProps>(
  (props, ref) => {
    const {children, className, closeButtonProps, onClose, position, ...rest} =
      props;

    return (
      <div
        className={cx('ld-callout-basecallout-baseCallout', position === 'bottomCenter' && 'ld-callout-basecallout-bottomCenter', position === 'bottomLeft' && 'ld-callout-basecallout-bottomLeft', position === 'bottomRight' && 'ld-callout-basecallout-bottomRight', position === 'left' && 'ld-callout-basecallout-left', position === 'right' && 'ld-callout-basecallout-right', position === 'topCenter' && 'ld-callout-basecallout-topCenter', position === 'topLeft' && 'ld-callout-basecallout-topLeft', position === 'topRight' && 'ld-callout-basecallout-topRight', className)}
        ref={ref}
        {...rest}
      >
        <div className={'ld-callout-basecallout-content'}>
          <div className={'ld-callout-basecallout-label'}>{children}</div>

          <div className={'ld-callout-basecallout-actions'}>
            <CalloutCloseButton
              children="Close"
              {...closeButtonProps}
              onClick={(event) => {
                closeButtonProps?.onClick?.(event);

                onClose(event);
              }}
            />
          </div>
        </div>
      </div>
    );
  }
);

// ---------------------------------------------------------------------------
// CalloutCloseButton (inlined sub-component)
// ---------------------------------------------------------------------------

export type CalloutCloseButtonProps = React.ComponentPropsWithoutRef<'button'>;

/**
 * @private
 */
export const CalloutCloseButton = React.forwardRef<
  HTMLButtonElement,
  CalloutCloseButtonProps
>((props, ref) => {
  const {className, ...rest} = props;

  return (
    <button
      className={cx('ld-callout-calloutclosebutton-closeButton', className)}
      ref={ref}
      type="button"
      {...rest}
    />
  );
});

// ---------------------------------------------------------------------------
// CalloutLayoutManager.service (inlined sub-component)
// ---------------------------------------------------------------------------

export const getCalloutPositionStyle = ({
  position,
  referrerRef,
  triggerRef,
}: {
  position: BaseCalloutPosition;
  referrerRef: React.RefObject<HTMLElement>;
  triggerRef: React.RefObject<HTMLElement>;
}) =>
  getPositionStyle({
    calculatePosition({
      referrerHeight,
      referrerWidth,
      targetHeight,
      targetWidth,
    }) {
      let left: number;

      if (position === 'left') {
        left = -1 * referrerWidth;
      } else if (position === 'right') {
        left = targetWidth;
      } else if (position === 'bottomLeft' || position === 'topLeft') {
        left = targetWidth / 2 - referrerWidth + 24;
      } else if (position === 'bottomRight' || position === 'topRight') {
        left = targetWidth / 2 - 24;
      } else {
        left = (targetWidth - referrerWidth) / 2;
      }

      let top: number;

      if (position.startsWith('bottom')) {
        top = targetHeight;
      } else if (position.startsWith('top')) {
        top = -1 * referrerHeight;
      } else {
        top = (targetHeight - referrerHeight) / 2;
      }

      return {left, top};
    },
    referrerRef,
    targetRef: triggerRef,
  });

// ---------------------------------------------------------------------------
// CalloutLayoutManager (inlined sub-component)
// ---------------------------------------------------------------------------

export interface CalloutLayoutContainerProps
  extends React.ComponentPropsWithoutRef<'div'> {
  /**
   * The position for the callout in relation to its target.
   */
  position: BaseCalloutPosition;
  /**
   * The trigger ref for the callout.
   */
  triggerRef: React.RefObject<HTMLElement>;
}

/**
 * @private
 */
export const CalloutLayoutManager: React.FunctionComponent<
  CalloutLayoutContainerProps
> = (props) => {
  const {className, position, triggerRef, ...rest} = props;

  const [rootStyle, setRootStyle] = React.useState<React.CSSProperties>({
    // NOTE: hide the callout until it has been mounted and positioned
    visibility: 'hidden',
  });
  const referrerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    setRootStyle(
      getCalloutPositionStyle({
        position,
        referrerRef,
        triggerRef,
      })
    );
  }, [position, referrerRef, triggerRef]);

  return (
    <div
      className={cx('ld-callout-calloutlayoutmanager-layoutManager', position === 'bottomCenter' && 'ld-callout-calloutlayoutmanager-bottom', position === 'bottomLeft' && 'ld-callout-calloutlayoutmanager-bottom', position === 'bottomRight' && 'ld-callout-calloutlayoutmanager-bottom', position === 'left' && 'ld-callout-calloutlayoutmanager-left', position === 'right' && 'ld-callout-calloutlayoutmanager-right', position === 'topCenter' && 'ld-callout-calloutlayoutmanager-top', position === 'topLeft' && 'ld-callout-calloutlayoutmanager-top', position === 'topRight' && 'ld-callout-calloutlayoutmanager-top', className)}
      ref={referrerRef}
      style={rootStyle}
      {...rest}
    />
  );
};

export type CalloutPosition = BaseCalloutPosition;

export interface CalloutProps
  extends Omit<React.ComponentPropsWithoutRef<'span'>, 'className' | 'style'>,
    BaseCalloutOwnProps {
  /**
   * The accessibility label describing the content of the callout.
   *
   * @note This property is required so callout announces with context for
   * screen reader users. Ensure `a11yContentLabel` accurately describes the
   * callout's content in relation to its target.
   */
  a11yContentLabel: string;
  /**
   * The content for the callout.
   */
  children: React.ReactNode;
  /**
   * If the callout is open.
   *
   * @default false
   */
  isOpen?: boolean;
  /**
   * The position for the callout.
   *
   * @default "bottomCenter"
   */
  position?: CalloutPosition;
  /**
   * The trigger for the callout.
   */
  trigger: React.ReactElement;
  /**
   * The trigger ref for the callout.
   */
  triggerRef: React.RefObject<HTMLElement>;
}

/**
 * Callouts are overlays that display onboarding or coaching content.
 * *
 */
export const Callout: React.FunctionComponent<CalloutProps> = (props) => {
  const {
    a11yContentLabel,
    children,
    className,
    closeButtonProps,
    isOpen = false,
    onClose,
    position = 'bottomCenter',
    trigger,
    triggerRef,
    ...rest
  } = applyCommonProps(props);

  invariant(
    !!a11yContentLabel.trim(),
    '`Callout` accessibility violation. `Callout` requires an `a11yContentLabel`.'
  );

  const contentId = useStableId();
  const previousIsOpen = React.useRef(isOpen);
  const ref = React.useRef<HTMLDivElement>(null);
  const triggerId = useStableId(trigger.props.id);



    React.useEffect(() => {
    if (!isOpen && previousIsOpen.current) {
      triggerRef.current?.focus();
    }

    previousIsOpen.current = isOpen;
  }, [isOpen, previousIsOpen, triggerRef]);

  const {shouldMount} = useCSSTransition({
    classNames: {
      enter: 'ld-callout-enter',
      enterActive: 'ld-callout-enterActive',
      exit: 'ld-callout-exit',
      exitActive: 'ld-callout-exitActive',
    },
    in: isOpen,
    mountOnEnter: true,
    nodeRef: ref,
    timeout: 200,
    unmountOnExit: true,
  });

  return (
    <span
      className={cx('ld-callout-callout', position === 'bottomCenter' && 'ld-callout-bottomCenter', position === 'bottomLeft' && 'ld-callout-bottomLeft', position === 'bottomRight' && 'ld-callout-bottomRight', position === 'left' && 'ld-callout-left', position === 'right' && 'ld-callout-right', position === 'topCenter' && 'ld-callout-topCenter', position === 'topLeft' && 'ld-callout-topLeft', position === 'topRight' && 'ld-callout-topRight', className)}
      {...rest}
    >
      {React.cloneElement(trigger, {
        'aria-labelledby': isOpen ? `${triggerId} ${contentId}` : undefined,

        /**
         * @note Emitting `id` when Callout is server-side rendered causes
         * problems with client-side hydration when `id`s to not match. Passing
         * `child.props.id` when the callout is closed gets around the issue.
         *
         * @see {@link https://reactjs.org/docs/react-dom.html#hydrate}
         * @see {@link https://jira.walmart.com/browse/LD-2066}
         */
        id: isOpen ? triggerId : trigger.props.id,
        onClick(event: React.MouseEvent) {
          if (isOpen) {
            onClose(event);
          }

          trigger.props?.onClick?.(event);
        },
      })}

      {shouldMount && 
        <CalloutLayoutManager position={position} triggerRef={triggerRef}>
          <BaseCallout
            closeButtonProps={{
              'aria-label': `Close ${a11yContentLabel}`,
              ...closeButtonProps,
            }}
            onClose={onClose}
            ref={ref}
            position={position}
          >
            <VisuallyHidden>{a11yContentLabel}</VisuallyHidden>

            <span id={contentId}>{children}</span>
          </BaseCallout>
        </CalloutLayoutManager>}
    </span>
  );
};

Callout.displayName = 'Callout';
