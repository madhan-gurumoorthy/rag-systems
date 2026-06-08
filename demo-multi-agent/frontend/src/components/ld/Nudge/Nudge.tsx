// @refresh reset

/**
 * @module Nudge
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
 * #### Title
 * 
 * Set the title for the Nudge with the `title` prop:
 * 
 * ```tsx
 * <Nudge title="Title">Content</Nudge>
 * ```
 * 
 * #### Leading
 * 
 * The Nudge accepts optional leading content through the `leading` prop:
 * 
 * ```tsx
 * <Nudge leading={<LeadingIcon />} title="Title">
 *   Content
 * </Nudge>
 * ```
 * 
 * #### Actions
 * 
 * The Nudge accepts a group of one or more button-like components through the optional `actions` prop:
 * 
 * ```tsx
 * <Nudge
 *   actions={
 *     <ButtonGroup>
 *       <Button>Action1</Button>
 *       <Button>Action2</Button>
 *     </ButtonGroup>
 *   }
 *   title="Title"
 * >
 *   Content
 * </Nudge>
 * ```
 * 
 * ### Opening and closing
 * 
 * The Nudge has a close button. Add a callback handler function using the `onClose` prop:
 * 
 * ```tsx
 * <Nudge onClose={(event) => console.log(event)} title="Title">
 *   Content
 * </Nudge>
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import {IconButton, IconButtonButtonProps} from '../IconButton';

import {
  CloseIcon,
} from '../Icons';
// ---------------------------------------------------------------------------
// NudgeCloseButton (inlined sub-component)
// ---------------------------------------------------------------------------

export type NudgeCloseButtonProps = Omit<
  IconButtonButtonProps,
  'UNSAFE_className' | 'UNSAFE_style' | 'a11yLabel' | 'children' | 'size'
> &
  Partial<Pick<IconButtonButtonProps, 'a11yLabel'>>;

/**
 * @private
 */
export const NudgeCloseButton: React.FunctionComponent<
  NudgeCloseButtonProps
> = (props) => {
  const {className, ...rest} = applyCommonProps(props);

  return (
    <IconButton
      UNSAFE_className={cx('ld-nudge-nudgeclosebutton-closeButton', className)}
      a11yLabel="Close"
      size={"medium"}
      {...rest}
    >
      <CloseIcon />
    </IconButton>
  );
};

import {Body} from '../Text';
import './Nudge.css';
export interface NudgeProps
  extends Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'style' | 'title'
    > {
  /**
   * The actions for the nudge.
   */
  actions?: React.ReactNode;
  /**
   * The content for the nudge.
   */
  children: React.ReactNode;
  /**
   * The props spread to the nudge's close button.
   */
  closeButtonProps?: NudgeCloseButtonProps;
  /**
   * The leading content for the nudge.
   */
  leading?: React.ReactNode;
  /**
   * The callback fired when the nudge requests to close.
   */
  onClose?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  /**
   * The title for the nudge.
   */
  title: React.ReactNode;
}

/**
 * Nudges are used to remind or provide instructions for the next-step in a process. The information they provide should not be required for a user to complete a task.
 * *
 */
export const Nudge: React.FunctionComponent<NudgeProps> = (props) => {
  const {
    actions,
    closeButtonProps = {},
    children,
    className,
    leading,
    onClose,
    title,
    ...rest
  } = applyCommonProps(props);

  return (
    <div
      className={cx('ld-nudge-nudge', onClose && 'ld-nudge-hasCloseButton', !actions && !children && 'ld-nudge-hasNoContent', className)}
      {...rest}
    >
      <div className={'ld-nudge-wrapperOuter'}>
        {leading && <div className={'ld-nudge-leading'}>{leading}</div>}

        <div className={'ld-nudge-wrapperInner'}>
          <Body size={"large"} weight={"alt"}>
            {title}
          </Body>

          {children && (
            <Body
              UNSAFE_className={'ld-nudge-content'}
              size={"small"}
            >
              {children}
            </Body>
          )}

          {actions && <div className={'ld-nudge-actionContent'}>{actions}</div>}
        </div>
      </div>

      {onClose && (
        <NudgeCloseButton
          {...closeButtonProps}
          onClick={(event) => {
            closeButtonProps?.onClick?.(event);

            onClose(event);
          }}
        />
      )}
    </div>
  );
};

Nudge.displayName = 'Nudge';
