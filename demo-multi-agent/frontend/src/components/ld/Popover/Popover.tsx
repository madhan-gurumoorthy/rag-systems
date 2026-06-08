'use client';
// @refresh reset

/**
 * @module Popover
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
 * The `Popover` component must be configured as follows to meet accessibility requirements:
 * 
 * 1. Must provide a single button-like element as its `children`
 * 1. Must provide the button-like element's `ref` as its `triggerRef`
 * 1. Must provide at least one focusable element within its `content`
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Button, Popover} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [state, setState] = React.useState(false);
 *   const ref = React.useRef();
 * 
 *   return (
 *     <Popover
 *       content={
 *         <div>
 *           <Checkbox
 *             label="I must contain at least one focusable element."
 *             name="status"
 *             onChange={() => {}}
 *           />
 *         </div>
 *       }
 *       onClose={(event) => setState(false)}
 *       isOpen={state}
 *       triggerRef={ref}
 *     >
 *       <Button
 *         ref={ref}
 *         onClick={(event) => {
 *           setState((state) => !state);
 *         }}
 *       >
 *         Open Popover
 *       </Button>
 *     </Popover>
 *   );
 * };
 * ```
 * 
 * #### A11y Content Label
 * 
 * The Popover includes a screen-reader announcement to indicate the start of its content. It's possible to override the default label for localization using the `a11yContentLabel` prop.
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Popover} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [isOpen, setIsOpen] = React.useState(false);
 *   const ref = React.useRef();
 * 
 *   return (
 *     <Popover
 *       a11yContentLabel="Inicio del contenido ampliado"
 *       content="Contenido importante"
 *       isOpen={isOpen}
 *       onClose={() => setIsOpen(false)}
 *       triggerRef={ref}
 *     >
 *       <Trigger ref={ref} />
 *     </Popover>
 *   );
 * };
 * ```
 * 
 * ### Features
 * 
 * #### Nubbin
 * 
 * Give the Popover a nubbin through the `hasNubbin` prop:
 * 
 * ```tsx
 * <Popover hasNubbin={true}>
 *   <Trigger />
 * </Popover>
 * ```
 * 
 * ### Layout
 * 
 * #### Position
 * 
 * The Popover has eight possible positions:
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
 * Set the position through the `position` prop:
 * 
 * ```tsx
 * <Popover position="bottomCenter">
 *   <Trigger />
 * </Popover>
 * ```
 */
import * as React from 'react';
import {cx, useStableId, applyCommonProps, getPositionStyle, CalculatePositionFn, usePointerOutside, useOnKeyDown} from '../common';
import {VisuallyHidden} from '../VisuallyHidden';
import './Popover.css';
// ---------------------------------------------------------------------------
// BasePopover (inlined sub-component)
// ---------------------------------------------------------------------------

export type PopoverNubbin =
  | 'bottomCenter'
  | 'bottomLeft'
  | 'bottomRight'
  | 'left'
  | 'right'
  | 'topCenter'
  | 'topLeft'
  | 'topRight';

export interface BasePopoverProps
  extends React.ComponentPropsWithoutRef<'div'> {
  /**
   * The content for the base popover.
   */
  children: React.ReactNode;
  /**
   * The nubbin for the base popover.
   */
  nubbin?: PopoverNubbin;
}

/**
 * @private
 */
export const BasePopover: React.FunctionComponent<BasePopoverProps> = (
  props
) => {
  const {children, className, nubbin, ...rest} = props;

  return (
    <div
      className={cx('ld-popover-basepopover-popover', nubbin && 'ld-popover-basepopover-nubbin', nubbin === 'bottomCenter' && 'ld-popover-basepopover-bottomCenter', nubbin === 'bottomLeft' && 'ld-popover-basepopover-bottomLeft', nubbin === 'bottomRight' && 'ld-popover-basepopover-bottomRight', nubbin === 'left' && 'ld-popover-basepopover-left', nubbin === 'right' && 'ld-popover-basepopover-right', nubbin === 'topCenter' && 'ld-popover-basepopover-topCenter', nubbin === 'topLeft' && 'ld-popover-basepopover-topLeft', nubbin === 'topRight' && 'ld-popover-basepopover-topRight', className)}
      {...rest}
    >
      <div className={'ld-popover-basepopover-content'}>{children}</div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// PopoverFocusGuard (inlined sub-component)
// ---------------------------------------------------------------------------

/* eslint-disable jsx-a11y/no-noninteractive-tabindex */
interface PopoverFocusGuardProps extends React.ComponentPropsWithoutRef<'div'> {
  /**
   * The accessibility label for the popover focus guard's content.
   */
  a11yContentLabel: string;
  /**
   * The content for the focus guard.
   */
  children: React.ReactNode;
  /**
   * The callback fired when the focus guard is focused.
   */
  onGuard: (event: React.FocusEvent<HTMLDivElement>) => void;
}

/**
 * @private
 */
export const PopoverFocusGuard: React.FunctionComponent<
  PopoverFocusGuardProps
> = (props) => {
  const {a11yContentLabel, children, onGuard, ...rest} = props;

  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const focusableNodes = ref.current?.querySelectorAll<HTMLElement>(
      // @see {@link https://github.com/theKashey/focus-lock/blob/125a50bc53fdc2cbb7705327790ecff4f3289ba1/src/utils/tabbables.ts#L4-L24}
      'a[href], button:enabled, input:enabled:not([type=hidden]), select:enabled, textarea:enabled, [tabindex], [autofocus]'
    );

    // NOTE: first and last node are focus guards, second node will be the first focusable item.
    const handle = setTimeout(() => focusableNodes?.[1].focus(), 0);

    return () => clearTimeout(handle);
  }, []);

  return (
    <div ref={ref} {...rest}>
      <div tabIndex={0} onFocus={onGuard} />
      <h2 className={'ld-popover-popoverfocusguard-a11yContentLabel'} tabIndex={-1}>
        <VisuallyHidden>{a11yContentLabel}</VisuallyHidden>
      </h2>
      {children}
      <div tabIndex={0} onFocus={onGuard} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// PopoverLayoutManager.service (inlined sub-component)
// ---------------------------------------------------------------------------

export const getPopoverPositionStyle = ({
  popoverRef,
  position,
  triggerRef,
}: {
  popoverRef: React.RefObject<HTMLDivElement>;
  position: PopoverPosition;
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
      let top: number;

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

      if (position.startsWith('bottom')) {
        top = targetHeight;
      } else if (position.startsWith('top')) {
        top = -1 * referrerHeight;
      } else {
        top = (targetHeight - referrerHeight) / 2;
      }

      return {left, top};
    },
    referrerRef: popoverRef,
    targetRef: triggerRef,
  });

// ---------------------------------------------------------------------------
// PopoverLayoutManager (inlined sub-component)
// ---------------------------------------------------------------------------

export type PopoverPosition =
  | 'bottomCenter'
  | 'bottomLeft'
  | 'bottomRight'
  | 'left'
  | 'right'
  | 'topCenter'
  | 'topLeft'
  | 'topRight';

export interface PopoverLayoutManagerProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'content'> {
  /**
   * The accessibility label for the popover's content.
   *
   * @default "Start of expanded content"
   */
  a11yContentLabel?: string;
  /**
   * The props spread to the base popover's element.
   *
   * @default {}
   */
  basePopoverProps?: React.DetailedHTMLProps<
    React.ComponentPropsWithoutRef<'div'>,
    HTMLDivElement
  >;
  /**
   * The content for the popover.
   */
  content: React.ReactNode;
  /**
   * If the popover has a nubbin.
   *
   * @default false
   */
  hasNubbin?: boolean;
  /**
   * The callback fired when the popover requests to close.
   */
  onClose: (
    event:
      | React.MouseEvent<HTMLButtonElement, MouseEvent>
      | React.FocusEvent<HTMLDivElement>
      | PointerEvent
      | MouseEvent
      | TouchEvent
      | KeyboardEvent
  ) => void;
  /**
   * The position for the popover.
   *
   * @default "bottomCenter"
   */
  position?: PopoverPosition;
  /**
   * The trigger ref for the popover.
   */
  triggerRef: React.RefObject<HTMLElement>;
}

/**
 * @private
 */
export const PopoverLayoutManager: React.FunctionComponent<
  PopoverLayoutManagerProps
> = (props) => {
  const {
    a11yContentLabel = 'Start of expanded content',
    basePopoverProps = {},
    className,
    content,
    hasNubbin = false,
    onClose,
    position = 'bottomCenter',
    triggerRef,
    ...rest
  } = props;

  const [popoverStyle, setPopoverStyle] = React.useState<React.CSSProperties>({
    // NOTE: hide the popover until it has been mounted and positioned
    visibility: 'hidden',
  });
  const surfaceRef = React.useRef<HTMLDivElement>(null);

  const onCloseWithFocusReturn = React.useCallback(
    (event: React.FocusEvent<HTMLDivElement> | KeyboardEvent) => {
      triggerRef.current?.focus();

      onClose(event);
    },
    [triggerRef, onClose]
  );

  usePointerOutside([surfaceRef, triggerRef], onClose);
  useOnKeyDown(['Esc', 'Escape'], onCloseWithFocusReturn);

  React.useEffect(() => {
    const positionStyle = getPopoverPositionStyle({
      popoverRef: surfaceRef,
      position,
      triggerRef,
    });

    setPopoverStyle(positionStyle);
  }, [surfaceRef, position, triggerRef]);

  React.useEffect(() => {
    const onResize = () => {
      const positionStyle = getPopoverPositionStyle({
        popoverRef: surfaceRef,
        position,
        triggerRef,
      });

      setPopoverStyle(positionStyle);
    };

    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
    };
  }, [surfaceRef, position, triggerRef]);

  const nubbin: PopoverNubbin = {
    bottomCenter: 'topCenter' as const,
    bottomLeft: 'topRight' as const,
    bottomRight: 'topLeft' as const,
    left: 'right' as const,
    right: 'left' as const,
    topCenter: 'bottomCenter' as const,
    topLeft: 'bottomRight' as const,
    topRight: 'bottomLeft' as const,
  }[position];

  return (
    <div
      className={cx('ld-popover-popoverlayoutmanager-layoutManager', position === 'bottomCenter' && 'ld-popover-popoverlayoutmanager-bottomCenter', position === 'bottomLeft' && 'ld-popover-popoverlayoutmanager-bottomLeft', position === 'bottomRight' && 'ld-popover-popoverlayoutmanager-bottomRight', position === 'left' && 'ld-popover-popoverlayoutmanager-left', position === 'right' && 'ld-popover-popoverlayoutmanager-right', position === 'topCenter' && 'ld-popover-popoverlayoutmanager-topCenter', position === 'topLeft' && 'ld-popover-popoverlayoutmanager-topLeft', position === 'topRight' && 'ld-popover-popoverlayoutmanager-topRight', hasNubbin && 'ld-popover-popoverlayoutmanager-hasNubbin', className)}
      ref={surfaceRef}
      style={popoverStyle}
      {...rest}
    >
      <PopoverFocusGuard
        a11yContentLabel={a11yContentLabel}
        onGuard={onCloseWithFocusReturn}
      >
        <BasePopover {...(hasNubbin && {nubbin})} {...basePopoverProps}>
          {content}
        </BasePopover>
      </PopoverFocusGuard>
    </div>
  );
};

// PopoverPosition is defined above in this file

export interface PopoverProps
  extends PopoverLayoutManagerProps,
    Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'content' | 'style'
    > {
  /**
   * The trigger for the popover.
   */
  children: React.ReactElement;
  /**
   * If the popover is open.
   *
   * @default false
   */
  isOpen?: boolean;
}

/**
 * Popovers are overlays that display contextual content on demand.
 * *
 */
export const Popover: React.FunctionComponent<PopoverProps> = (props) => {
  const {
    a11yContentLabel,
    basePopoverProps,
    children,
    className,
    content,
    hasNubbin,
    isOpen = false,
    onClose,
    position,
    triggerRef,
    ...rest
  } = applyCommonProps(props);

  const child = React.Children.only(children);

  const surfaceId = useStableId();

  return (
    <div className={cx('ld-popover-popover', className)} {...rest}>
      {React.cloneElement(child, {
        'aria-controls': surfaceId,
        'aria-expanded': isOpen,
      })}

      <div id={surfaceId}>
        {isOpen && (
          <PopoverLayoutManager
            a11yContentLabel={a11yContentLabel}
            basePopoverProps={basePopoverProps}
            content={content}
            hasNubbin={hasNubbin}
            onClose={onClose}
            position={position}
            triggerRef={triggerRef}
          />
        )}
      </div>
    </div>
  );
};

Popover.displayName = 'Popover';
