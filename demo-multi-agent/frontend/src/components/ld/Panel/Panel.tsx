'use client';
// @refresh reset

/**
 * @module Panel
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
 * #### Children
 * 
 * The Panel accepts valid React content through the `children` prop:
 * 
 * ```tsx
 * <Panel onClose={() => setIsOpen(false)} title="Title">
 *   Content
 * </Panel>
 * ```
 * 
 * #### Title
 * 
 * The Panel requires a title which can be provided through the `title` prop:
 * 
 * ```tsx
 * <Panel onClose={() => setIsOpen(false)} title="Title">
 *   Panel
 * </Panel>
 * ```
 * 
 * #### Actions
 * 
 * The Panel accepts a group of one or more button-like components through the optional `actions` prop:
 * 
 * ```tsx
 * <Panel
 *   actions={
 *     <ButtonGroup>
 *       <Button>Action1</Button>
 *       <Button>Action2</Button>
 *     </ButtonGroup>
 *   }
 *   onClose={() => setIsOpen(false)}
 *   title="Title"
 * >
 *   Content
 * </Panel>
 * ```
 * 
 * ### Features
 * 
 * #### Size
 * 
 * The Panel comes in three sizes:
 * 
 * - `small` (default)
 * - `medium`
 * - `large`
 * 
 * Set the size with the `size` prop:
 * 
 * ```tsx
 * <Panel
 *   onClose={() => setIsOpen(false)}
 *   size="small"
 *   title="Title"
 * >
 *   Small
 * </Panel>
 * 
 * <Panel
 *   onClose={() => setIsOpen(false)}
 *   size="medium"
 *   title="Title"
 * >
 *   Medium
 * </Panel>
 * 
 * <Panel
 *   onClose={() => setIsOpen(false)}
 *   size="large"
 *   title="Title"
 * >
 *   Large
 * </Panel>
 * ```
 * 
 * ### Opening and closing
 * 
 * The Panel is set to open or close based on the `isOpen` prop. Provide a callback handler that manages the `isOpen` state through the `onClose` prop:
 * 
 * ```tsx
 * export default () => {
 *   const [isOpen, setIsOpen] = React.useState(false);
 * 
 *   return (
 *     <>
 *       <Button onClick={() => setIsOpen(true)}>Open panel</Button>
 * 
 *       <Panel isOpen={isOpen} onClose={() => setIsOpen(false)} title="Title">
 *         Content
 *       </Panel>
 *     </>
 *   );
 * };
 * ```
 * 
 * ### Layout
 * 
 * #### Position
 * 
 * The Panel has two different positions:
 * 
 * - `left` (default)
 * - `right`
 * 
 * Set the position through the `position` prop:
 * 
 * ```tsx
 * <Panel
 *   onClose={() => setIsOpen(false)}
 *   position="left"
 *   title="Title"
 * >
 *   Left
 * </Panel>
 * 
 * <Panel
 *   onClose={() => setIsOpen(false)}
 *   position="right"
 *   title="Title"
 * >
 *   Right
 * </Panel>
 * ```
 * 
 * ## FAQ
 * 
 * ### I am unable to scroll on iOS devices. What do I do?
 * 
 * We use the library [`body-scroll-lock`](https://github.com/willmcpo/body-scroll-lock) to manage document scrolling when overlay components are open. This library works across devices, with a known caveat on iOS mobile/tablet. To use this component across devices, scrolling should not be nested (No nested scrollbars. Manual adjustments have been made for range elements and text areas).
 * 
 * For more information on this issue, please refer to this [hook](https://gecgithub01.walmart.com/LivingDesign/react/blob/37bff511f96ceee2ee08049fb95cbb333e0ae27a/src/hooks/useLockBodyScroll.tsx#L52-L59) and associated library [documentation](https://github.com/willmcpo/body-scroll-lock/issues/76).
 */
import * as React from 'react';
import {cx, useStableId, invariant, applyCommonProps, useCSSTransition, useOnKeyDown, usePointerOutside} from '../common';
import {
  CloseIcon,
} from '../Icons';
import {IconButton, IconButtonButtonProps} from '../IconButton';
import {SsrBoundary} from '../SsrBoundary';
import { Overlay, OverlayProps, OverlayScrim } from '../Overlay';
import './Panel.css';

// ---------------------------------------------------------------------------
// PanelPortal (inlined sub-component)
// ---------------------------------------------------------------------------

export type PanelCloseButtonProps = Omit<
  IconButtonButtonProps,
  | 'UNSAFE_className'
  | 'UNSAFE_style'
  | 'a11yLabel'
  | 'children'
  | 'disabled'
  | 'size'
> &
  Partial<Pick<IconButtonButtonProps, 'a11yLabel'>>;

export type PanelCloseEvent =
  | React.MouseEvent<HTMLButtonElement, MouseEvent>
  | KeyboardEvent
  | MouseEvent
  | PointerEvent
  | TouchEvent;

export type PanelPosition = 'left' | 'right';

export type PanelSize = 'large' | 'medium' | 'small';

export interface PanelPortalProps
  extends Omit<OverlayProps, 'title'> {
  /**
   * The actions for the panel.
   */
  actions?: React.ReactNode;
  /**
   * The content for the panel.
   */
  children: React.ReactNode;
  /**
   * The props spread to the panel's close button.
   */
  closeButtonProps?: PanelCloseButtonProps;
  /**
   * If the Panel is open.
   */
  isOpen: boolean;
  /**
   * The callback fired when the panel requests to close.
   */
  onClose: (event: PanelCloseEvent) => void;
  /**
   * The callback fired when the panel transition has ended.
   */
  onClosed?: () => void;
  /**
   * The position for the panel.
   *
   * @default "left"
   */
  position?: PanelPosition;
  /**
   * The size for the panel.
   *
   * @default "small"
   */
  size?: PanelSize;
  /**
   * The title for the panel.
   */
  title: React.ReactNode;
}

/**
 * @private
 */
export const PanelPortal: React.FunctionComponent<PanelPortalProps> = (
  props
) => {
  const {
    actions,
    children,
    closeButtonProps,
    onClose,
    onClosed,
    isOpen,
    position = 'left',
    size = 'small',
    title,
    ...rest
  } = applyCommonProps(props);

  invariant(!!title, 'Required property `title` not provided.');

  const overlayRef = React.useRef<HTMLDivElement>(null);
  const panelRef = React.useRef<HTMLDivElement>(null);
  const titleId = useStableId();

  usePointerOutside(panelRef, onClose);
  useOnKeyDown(['Esc', 'Escape'], onClose);

  const {shouldMount} = useCSSTransition({
    classNames:{
      enter: 'ld-panel-panelportal-transitionEnter',
      enterActive: 'ld-panel-panelportal-transitionEnterActive',
      exit: 'ld-panel-panelportal-transitionExit',
      exitActive: 'ld-panel-panelportal-transitionExitActive',
    },
    in: isOpen,
    mountOnEnter: true,
    nodeRef: overlayRef,
    onExited: () => onClosed?.(),
    timeout: 300
  });

  return shouldMount && (
      <Overlay ref={overlayRef} {...rest}>
        <div
          className={cx('ld-panel-panelportal-container', position === 'left' && 'ld-panel-panelportal-left', position === 'right' && 'ld-panel-panelportal-right')}
        >
          <div
            aria-labelledby={titleId}
            aria-modal="true"
            className={cx('ld-panel-panelportal-panel', size === 'small' && 'ld-panel-panelportal-small', size === 'medium' && 'ld-panel-panelportal-medium', size === 'large' && 'ld-panel-panelportal-large')}
            ref={panelRef}
            role="dialog"
          >
            <div className={'ld-panel-panelportal-header'}>
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

              <h2 className={'ld-panel-panelportal-title'} id={titleId}>
                {title}
              </h2>
            </div>

            <div className={'ld-panel-panelportal-content'}>
              <div className={'ld-panel-panelportal-contentInner'}>{children}</div>
            </div>

            {actions && <div className={'ld-panel-panelportal-actionContent'}>{actions}</div>}
          </div>
        </div>
        <OverlayScrim className={'ld-panel-panelportal-scrim'} />
      </Overlay>
  );
};

export type PanelProps = PanelPortalProps;

/**
 * Panels provide supplemental information or form inputs that relate to the primary canvas.
 */
export const Panel: React.FunctionComponent<PanelProps> = (props) => {
  const {isOpen, onClosed, ...rest} = props;

  const [isTransitioning, setIsTransitioning] = React.useState(isOpen);
  const previousIsOpen = React.useRef(isOpen);

  /**
   * This hook delays `isOpen` property changes such that the
   * `Panel` component can transition in and out.
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
      <PanelPortal
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

Panel.displayName = 'Panel';
