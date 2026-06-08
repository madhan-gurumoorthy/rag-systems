'use client';
// @refresh reset

/**
 * @module Modal
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
 * The Modal accepts valid React content through the `children` prop:
 * 
 * ```tsx
 * <Modal onClose={() => setIsOpen(false)} title="Title">
 *   Content
 * </Modal>
 * ```
 * 
 * #### Title
 * 
 * The Modal requires a title which can be provided through the `title` prop:
 * 
 * ```tsx
 * <Modal onClose={() => setIsOpen(false)} title="Title">
 *   Modal
 * </Modal>
 * ```
 * 
 * #### Actions
 * 
 * The Modal accepts a group of one or more button-like components through the optional `actions` prop:
 * 
 * ```tsx
 * <Modal
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
 * </Modal>
 * ```
 * 
 * ### Opening and closing
 * 
 * The Modal is set to open or close based on the `isOpen` prop. Provide a callback handler that manages the `isOpen` state through the `onClose` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Button, Modal} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [isOpen, setIsOpen] = React.useState(false);
 * 
 *   return (
 *     <>
 *       <Button onClick={() => setIsOpen(true)}>Open modal</Button>
 * 
 *       <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Title">
 *         Content
 *       </Modal>
 *     </>
 *   );
 * };
 * ```
 * 
 * ### Features
 * 
 * #### Size
 * 
 * The Modal comes in three sizes:
 * 
 * - `small` (default)
 * - `medium`
 * - `large`
 * 
 * Set the size with the `size` prop:
 * 
 * ```tsx
 * <Modal
 *   onClose={() => setIsOpen(false)}
 *   size="small"
 *   title="Title"
 * >
 *   Small
 * </Modal>
 * 
 * <Modal
 *   onClose={() => setIsOpen(false)}
 *   size="medium"
 *   title="Title"
 * >
 *   Medium
 * </Modal>
 * 
 * <Modal
 *   onClose={() => setIsOpen(false)}
 *   size="large"
 *   title="Title"
 * >
 *   Large
 * </Modal>
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
import {Heading} from '../Text';
import {SsrBoundary} from '../SsrBoundary';
import { Overlay, OverlayProps, OverlayScrim } from '../Overlay';
import './Modal.css';

// ---------------------------------------------------------------------------
// ModalPortal (inlined sub-component)
// ---------------------------------------------------------------------------

export type ModalSize = 'small' | 'medium' | 'large';

export type ModalCloseButtonProps = Omit<
  IconButtonButtonProps,
  | 'UNSAFE_className'
  | 'UNSAFE_style'
  | 'a11yLabel'
  | 'children'
  | 'disabled'
  | 'size'
> &
  Partial<Pick<IconButtonButtonProps, 'a11yLabel'>>;

export type ModalCloseEvent =
  | React.MouseEvent<HTMLButtonElement, MouseEvent>
  | PointerEvent
  | MouseEvent
  | TouchEvent
  | KeyboardEvent;

export interface ModalPortalProps
  extends Omit<OverlayProps, 'title'> {
  /**
   * The actions for the modal.
   */
  actions?: React.ReactNode;
  /**
   * The content for the modal.
   */
  children: React.ReactNode;
  /**
   * The props spread to the modal's close button.
   *
   * @default {}
   */
  closeButtonProps?: ModalCloseButtonProps;
  /**
   * If the bottom sheet is open.
   */
  isOpen: boolean;
  /**
   * The callback fired when the modal requests to close.
   */
  onClose: (event: ModalCloseEvent) => void;
  /**
   * The callback fired when the modal transition has ended.
   */
  onClosed?: () => void;
  /**
   * The size for the modal.
   *
   * @default "small"
   */
  size?: ModalSize;
  /**
   * The title for the modal.
   */
  title: React.ReactNode;
}

/**
 * @private
 */
export const ModalPortal: React.FunctionComponent<ModalPortalProps> = (
  props
) => {
  const {
    actions,
    children,
    closeButtonProps,
    isOpen,
    onClose,
    size = 'small',
    title,
    onClosed,
    ...rest
  } = applyCommonProps(props);

  invariant(!!title, 'Required property `title` not provided.');

  const {onClick: closeButtonOnClick, ...closeButtonRest} =
    closeButtonProps || {};

  const overlayRef = React.useRef<HTMLDivElement>(null);
  const modalRef = React.useRef<HTMLDivElement>(null);
  const titleId = useStableId();

  usePointerOutside(modalRef, onClose);
  useOnKeyDown(['Esc', 'Escape'], onClose);

  const {shouldMount} = useCSSTransition({
    classNames: {
      enter: "ld-modal-modalportal-transitionEnter",
      enterActive: "ld-modal-modalportal-transitionEnterActive",
      exit: "ld-modal-modalportal-transitionExit",
      exitActive: "ld-modal-modalportal-transitionExitActive",
    },
    in: isOpen,
    mountOnEnter: true,
    nodeRef: overlayRef,
    onExited: () => onClosed?.(),
    timeout: 500,
  });

  return shouldMount ? (
      <Overlay ref={overlayRef} {...rest}>
        <div className={'ld-modal-modalportal-container'}>
          <div
            aria-labelledby={titleId}
            aria-modal="true"
            className={cx('ld-modal-modalportal-modal', size === 'large' && 'ld-modal-modalportal-large', size === 'medium' && 'ld-modal-modalportal-medium', size === 'small' && 'ld-modal-modalportal-small')}
            ref={modalRef}
            role="dialog"
          >
            <div className={'ld-modal-modalportal-header'}>
              <IconButton
                a11yLabel="Close dialog"
                {...closeButtonRest}
                onClick={(event) => {
                  closeButtonOnClick?.(event);

                  onClose(event);
                }}
                size="medium"
              >
                <CloseIcon />
              </IconButton>

              <Heading as="h2" id={titleId} UNSAFE_className={'ld-modal-modalportal-title'}>
                {title}
              </Heading>
            </div>

            <div className={'ld-modal-modalportal-content'} /* ref={setScrollableContentElement} */>
              <div className={'ld-modal-modalportal-contentInner'}>{children}</div>
            </div>

            {actions && (
              // NOTE: Safari needs a wrapping block element, otherwise a flex container
              // renders with no height.
              <div className={'ld-modal-modalportal-actionContent'}>{actions}</div>
            )}
          </div>
        </div>
        <OverlayScrim className={'ld-modal-modalportal-scrim'} />
      </Overlay>
  ): null;
};

export interface ModalProps extends ModalPortalProps {}

/**
 * Modals focus the user’s attention on a single task in a window that sits on top of the page content.
 *
 */
export const Modal: React.FunctionComponent<ModalProps> = (props) => {
  const {isOpen, onClosed, ...rest} = props;

  const [isTransitioning, setIsTransitioning] = React.useState(isOpen);
  const previousIsOpen = React.useRef(isOpen);

  /**
   * This hook delays `isOpen` property changes such that the
   * `ModalPortal` component can transition in and out.
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
      <ModalPortal
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

Modal.displayName = 'Modal';
