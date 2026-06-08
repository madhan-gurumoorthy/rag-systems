'use client';
// @refresh reset

/**
 * @module BottomSheet
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
 * #### Children and title
 * 
 * The Bottom Sheet accepts valid React content through the `children` prop and optionally accepts a `title`:
 * 
 * ```tsx
 * <BottomSheet onClose={() => setIsOpen(false)} title="Bottom Sheet Title">
 *   Content
 * </BottomSheet>
 * ```
 * 
 * #### Actions
 * 
 * The Bottom Sheet accepts a group of one or more button-like components through the optional `actions` prop:
 * 
 * ```tsx
 * <BottomSheet
 *   actions={
 *     <ButtonGroup>
 *       <Button variant="tertiary">Cancel</Button>
 *       <Button variant="primary">Apply Changes</Button>
 *     </ButtonGroup>
 *   }
 *   onClose={() => setIsOpen(false)}
 *   title="Bottom Sheet Title"
 * >
 *   Content
 * </BottomSheet>
 * ```
 * 
 * ### Opening and closing
 * 
 * The Bottom Sheet is set to open or close based on the `isOpen` prop. Provide a callback handler that manages the `isOpen` state through the `onClose` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {BottomSheet} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [isOpen, setIsOpen] = React.useState(false);
 *   return (
 *     <BottomSheet
 *       isOpen={isOpen}
 *       onClose={() => setIsOpen(false)}
 *       title="Bottom Sheet Title"
 *     >
 *       Content
 *     </BottomSheet>
 *   );
 * };
 * ```
 * 
 * ### Accessibility
 * 
 * The title is used as an a11y label for the Bottom Sheet. If a title is not provided, an a11y label must be provided through the `a11yLabel` prop:
 * 
 * ```tsx
 * <BottomSheet a11yLabel="Bottom Sheet Label" onClose={() => setIsOpen(false)}>
 *   Content
 * </BottomSheet>
 * ```
 * 
 * ### Body scroll lock
 * 
 * When a Bottom Sheet is open, the document body is not scrollable. On iOS devices, the underlying [body-scroll-lock](https://github.com/willmcpo/body-scroll-lock) dependency can unintentionally prevent scrolling on child elements of the Bottom Sheet as well. If you have a scrollable child element that is unexpectedly not scrollable on an iOS device, you can add the `data-scroll-lock-ignore` attribute to the element(s) that should be scrollable, or any of its ancestors.
 * 
 * ## FAQ
 * 
 * ### I am unable to scroll on iOS devices. What do I do?
 * 
 * We use the library [`body-scroll-lock`](https://github.com/willmcpo/body-scroll-lock) to manage document scrolling when overlay components are open. This library works across devices, with a known caveat on iOS mobile/tablet. To use this component across devices, scrolling should not be nested (No nested scrollbars. Manual adjustments have been made for range elements and text areas).
 * 
 * For more information on this issue, please refer to this [hook](https://gecgithub01.walmart.com/LivingDesign/react/blob/37bff511f96ceee2ee08049fb95cbb333e0ae27a/src/hooks/useLockBodyScroll.tsx#L52-L59) and associated library [documentation](https://github.com/willmcpo/body-scroll-lock/issues/76).
 * 
 * ### Animation isn't working with [conditional rendering](https://reactjs.org/docs/conditional-rendering.html#inline-if-with-logical--operator). What do I do?
 * 
 * The Bottom Sheet's animation will not execute if the component is conditionally rendered with `isOpen`. Separate conditional rendering from `isOpen` to work around this React limitation:
 * 
 * ```tsx
 * {
 *   shouldRender && <BottomSheet isOpen={isOpen} />;
 * }
 * ```
 */
import * as React from 'react';
import {useStableId, applyCommonProps, useCSSTransition, useOnKeyDown, usePointerOutside} from '../common';
import {
  CloseIcon,
} from '../Icons';
import {IconButton, IconButtonButtonProps} from '../IconButton';
import {SsrBoundary} from '../SsrBoundary';
import { Overlay, OverlayProps, OverlayScrim } from '../Overlay';
import './BottomSheet.css';

// ---------------------------------------------------------------------------
// BottomSheetPortal (inlined sub-component)
// ---------------------------------------------------------------------------

export type BottomSheetCloseButtonProps = Omit<
  IconButtonButtonProps,
  | 'UNSAFE_className'
  | 'UNSAFE_style'
  | 'a11yLabel'
  | 'children'
  | 'disabled'
  | 'size'
> &
  Partial<Pick<IconButtonButtonProps, 'a11yLabel'>>;

export type BottomSheetCloseEvent =
  | React.MouseEvent<HTMLButtonElement, MouseEvent>
  | KeyboardEvent
  | MouseEvent
  | PointerEvent
  | TouchEvent;

export interface BottomSheetPortalProps
  extends Omit<OverlayProps, 'title'> {
  /**
   * The actions for the bottom sheet.
   */
  actions?: React.ReactNode;
  /**
   * The props spread to the bottom sheet's close button.
   */
  closeButtonProps?: BottomSheetCloseButtonProps;
  /**
   * The content for the bottom sheet.
   */
  children: React.ReactNode;
  /**
   * If the bottom sheet is open.
   *
   * @default false
   */
  isOpen?: boolean;
  /**
   * The callback fired when the bottom sheet requests to close.
   */
  onClose: (event: BottomSheetCloseEvent) => void;
  /**
   * The callback fired when the bottom sheet transition has ended.
   */
  onClosed?: () => void;
  /**
   * The title for the bottom sheet.
   */
  title: React.ReactNode;
}

/**
 * @private
 */
export const BottomSheetPortal: React.FunctionComponent<
  BottomSheetPortalProps
> = (props) => {
  const {
    actions,
    closeButtonProps,
    children,
    isOpen = false,
    onClose,
    onClosed,
    title,
    ...rest
  } = applyCommonProps(props);

  const overlayRef = React.useRef<HTMLDivElement>(null);
  const bottomSheetRef = React.useRef<HTMLDivElement>(null);
  const titleId = useStableId();

  usePointerOutside(bottomSheetRef, onClose);
  useOnKeyDown(['Esc', 'Escape'], onClose);

  const {shouldMount} = useCSSTransition({
    classNames: {
      enter: 'ld-bottomsheet-bottomsheetportal-transitionEnter',
      enterActive: 'ld-bottomsheet-bottomsheetportal-transitionEnterActive',
      exit: 'ld-bottomsheet-bottomsheetportal-transitionExit',
      exitActive: 'ld-bottomsheet-bottomsheetportal-transitionExitActive',
    },
    in: isOpen,
    mountOnEnter: true,
    nodeRef: overlayRef,
    onExited: () => onClosed?.(),
    timeout: 900
  });

  return shouldMount && (
    <Overlay ref={overlayRef} {...rest}>
      <div className={'ld-bottomsheet-bottomsheetportal-container'}>
        <div
          aria-modal="true"
          className={'ld-bottomsheet-bottomsheetportal-bottomSheet'}
          ref={bottomSheetRef}
          role="dialog"
          {...(title && {'aria-labelledby': titleId})}
        >
          <div className={'ld-bottomsheet-bottomsheetportal-header'}>
            <IconButton
              a11yLabel="Close dialog"
              {...closeButtonProps}
              onClick={(event) => {
                closeButtonProps?.onClick?.(event);
                onClose(event);
              }}
              size={"medium"}
            >
              <CloseIcon />
            </IconButton>

            <h2 className={'ld-bottomsheet-bottomsheetportal-title'} id={titleId}>
              {title}
            </h2>
          </div>
          <div className={'ld-bottomsheet-bottomsheetportal-content'}>
            <div className={'ld-bottomsheet-bottomsheetportal-contentInner'}>{children}</div>
          </div>

          {actions && <div className={'ld-bottomsheet-bottomsheetportal-actionContent'}>{actions}</div>}
        </div>
      </div>
      <OverlayScrim className={'ld-bottomsheet-bottomsheetportal-scrim'} />
    </Overlay>
  );
};

export type BottomSheetProps = BottomSheetPortalProps;

/**
 * Bottom Sheets are surfaces anchored to the bottom of the screen that contain supplementary content.
 * *
 */
export const BottomSheet: React.FunctionComponent<BottomSheetProps> = (
  props
) => {
  const {isOpen, onClosed, ...rest} = props;

  const [isTransitioning, setIsTransitioning] = React.useState(isOpen);
  const previousIsOpen = React.useRef(isOpen);

  /**
   * This hook delays `isOpen` property changes such that the
   * `BottomSheetPortal` component can transition in and out.
   */


    React.useEffect(() => {
    if (previousIsOpen.current === isOpen) {
      return;
    }

    previousIsOpen.current = isOpen;

    const handle = setTimeout(() => {
      setIsTransitioning(true);
    }, 0);

    return () => clearTimeout(handle);
  }, [isOpen]);

  if (!isOpen && !isTransitioning) {
    return null;
  }

  return (
    <SsrBoundary>
      <BottomSheetPortal
        isOpen={isOpen && isTransitioning}
        onClosed={() => {
          setIsTransitioning(false);
          onClosed?.();
        }}
        {...rest}
      />
    </SsrBoundary>
  );
};

BottomSheet.displayName = 'BottomSheet';
