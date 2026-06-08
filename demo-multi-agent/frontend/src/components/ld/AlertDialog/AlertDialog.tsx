'use client';
// @refresh reset

/**
 * @module AlertDialog
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
 */
import * as React from 'react';
import {cx} from '../common';
import type {CommonProps} from '../common';
import {Modal} from '../Modal';
import type {ModalSize, ModalCloseEvent} from '../Modal';

import './AlertDialog.css';
import './AlertDialog.css';

/* ------------------------------------------------------------------ */
/*  Context                                                            */
/* ------------------------------------------------------------------ */

interface AlertDialogContextValue {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const AlertDialogCtx = React.createContext<AlertDialogContextValue | null>(null);

function useAlertDialogCtx() {
  const ctx = React.useContext(AlertDialogCtx);
  if (!ctx) throw new Error('AlertDialog compound components must be used within <AlertDialog>');
  return ctx;
}

/* ------------------------------------------------------------------ */
/*  Root                                                               */
/* ------------------------------------------------------------------ */

export interface AlertDialogProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

function AlertDialog({open: controlledOpen, defaultOpen = false, onOpenChange, children}: AlertDialogProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const isOpen = controlledOpen !== undefined ? controlledOpen : uncontrolledOpen;

  const handleChange = React.useCallback(
    (next: boolean) => {
      if (controlledOpen === undefined) setUncontrolledOpen(next);
      onOpenChange?.(next);
    },
    [controlledOpen, onOpenChange],
  );

  return (
    <AlertDialogCtx.Provider value={{open: isOpen, onOpenChange: handleChange}}>
      {children}
    </AlertDialogCtx.Provider>
  );
}
AlertDialog.displayName = 'AlertDialog';

/* ------------------------------------------------------------------ */
/*  Trigger                                                            */
/* ------------------------------------------------------------------ */

export interface AlertDialogTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, CommonProps {
  asChild?: boolean;
}

const AlertDialogTrigger = React.forwardRef<HTMLButtonElement, AlertDialogTriggerProps>(
  ({onClick, children, asChild, UNSAFE_className, UNSAFE_style, ...props}, ref) => {
    const {onOpenChange} = useAlertDialogCtx();

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      onClick?.(e);
      onOpenChange(true);
    };

    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(children as React.ReactElement<Record<string, unknown>>, {
        ref,
        onClick: handleClick,
      });
    }

    return (
      <button
        ref={ref}
        type="button"
        className={UNSAFE_className}
        style={UNSAFE_style}
        onClick={handleClick}
        {...props}
      >
        {children}
      </button>
    );
  },
);
AlertDialogTrigger.displayName = 'AlertDialogTrigger';

/* ------------------------------------------------------------------ */
/*  Content — wraps Modal, disabling Escape & outside-click close      */
/* ------------------------------------------------------------------ */

export interface AlertDialogContentProps extends CommonProps {
  /**
   * The body content for the alert dialog.
   */
  children: React.ReactNode;
  /**
   * The title for the alert dialog.
   */
  title: React.ReactNode;
  /**
   * The actions (buttons) rendered in the footer area.
   */
  actions?: React.ReactNode;
  /**
   * The size for the alert dialog. Matches Modal's size prop.
   *
   * @default "small"
   */
  size?: ModalSize;
}

const AlertDialogContent: React.FunctionComponent<AlertDialogContentProps> = (props) => {
  const {children, title, actions, size = 'small', UNSAFE_className, UNSAFE_style} = props;
  const {open} = useAlertDialogCtx();

  const noop = React.useCallback((_event: ModalCloseEvent) => {}, []);

  return (
    <Modal
      isOpen={open}
      onClose={noop}
      title={title}
      size={size}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      {...{UNSAFE_className: cx('ld-alert-dialog-modal', UNSAFE_className), UNSAFE_style} as any}
      actions={actions}
    >
      {children}
    </Modal>
  );
};
AlertDialogContent.displayName = 'AlertDialogContent';

/* ------------------------------------------------------------------ */
/*  Action                                                             */
/* ------------------------------------------------------------------ */

export interface AlertDialogActionProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, CommonProps {
  variant?: 'primary' | 'destructive';
}

const AlertDialogAction = React.forwardRef<HTMLButtonElement, AlertDialogActionProps>(
  ({children, variant = 'primary', UNSAFE_className, UNSAFE_style, onClick, ...props}, ref) => {
    const {onOpenChange} = useAlertDialogCtx();

    return (
      <button
        ref={ref}
        type="button"
        className={cx(
          'ld-alert-dialog-btn',
          'ld-alert-dialog-action',
          variant === 'destructive' && 'ld-alert-dialog-action--destructive',
          UNSAFE_className,
        )}
        style={UNSAFE_style}
        onClick={(e) => {
          onClick?.(e);
          onOpenChange(false);
        }}
        {...props}
      >
        {children}
      </button>
    );
  },
);
AlertDialogAction.displayName = 'AlertDialogAction';

/* ------------------------------------------------------------------ */
/*  Cancel                                                             */
/* ------------------------------------------------------------------ */

export interface AlertDialogCancelProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, CommonProps {}

const AlertDialogCancel = React.forwardRef<HTMLButtonElement, AlertDialogCancelProps>(
  ({children, UNSAFE_className, UNSAFE_style, onClick, ...props}, ref) => {
    const {onOpenChange} = useAlertDialogCtx();

    return (
      <button
        ref={ref}
        type="button"
        className={cx('ld-alert-dialog-btn', 'ld-alert-dialog-cancel', UNSAFE_className)}
        style={UNSAFE_style}
        onClick={(e) => {
          onClick?.(e);
          onOpenChange(false);
        }}
        {...props}
      >
        {children}
      </button>
    );
  },
);
AlertDialogCancel.displayName = 'AlertDialogCancel';

/* ------------------------------------------------------------------ */
/*  Exports                                                            */
/* ------------------------------------------------------------------ */

export {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogAction,
  AlertDialogCancel,
};
