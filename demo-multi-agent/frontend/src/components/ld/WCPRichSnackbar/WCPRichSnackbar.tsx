// @refresh reset

/**
 * @module WCPRichSnackbar
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
import {cx, applyCommonProps} from '../common';
import {CloseIcon} from '../Icons';
import './WCPRichSnackbar.css';

// ── Inlined useWCPRichSnackbar hook ───────────────────────────────────────────

export type WCPRichSnackbarColor = 'primary' | 'secondary' | 'inverse' | 'brand';
export type WCPRichSnackbarContentVariant = 'left-regular' | 'left-bold' | 'center-regular' | 'center-bold';

export interface WCPRichSnackbarState {
  id: string;
  open: boolean;
  color: WCPRichSnackbarColor;
  contentVariant: WCPRichSnackbarContentVariant;
  leadingSlot?: React.ReactNode;
  message: string | React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  duration?: number;
  position?: 'bottom-left' | 'bottom-center' | 'bottom-right';
}

export interface WCPRichSnackbarOptions {
  color?: WCPRichSnackbarColor;
  contentVariant?: WCPRichSnackbarContentVariant;
  leadingSlot?: React.ReactNode;
  message: string | React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  duration?: number;
  position?: 'bottom-left' | 'bottom-center' | 'bottom-right';
}

let _state: WCPRichSnackbarState | null = null;
let _listeners: Array<(s: WCPRichSnackbarState | null) => void> = [];
const _notify = () => _listeners.forEach((l) => l(_state));

export const subscribeWCPRichSnackbar = (listener: (s: WCPRichSnackbarState | null) => void) => {
  _listeners.push(listener);
  return () => { _listeners = _listeners.filter((l) => l !== listener); };
};

export const wcpRichSnackbar = (options: WCPRichSnackbarOptions): string => {
  const id = Math.random().toString(36).substring(2, 9);
  _state = {
    id, open: true,
    color: options.color ?? 'primary',
    contentVariant: options.contentVariant ?? 'left-regular',
    leadingSlot: options.leadingSlot,
    message: options.message,
    actionLabel: options.actionLabel,
    onAction: options.onAction,
    duration: options.duration ?? 4000,
    position: options.position ?? 'bottom-center',
  };
  _notify();
  return id;
};

export const dismissWCPRichSnackbar = () => {
  if (_state) {
    _state = {..._state, open: false};
    _notify();
    setTimeout(() => { _state = null; _notify(); }, 200);
  }
};

export const useWCPRichSnackbar = () => {
  const [current, setCurrent] = React.useState<WCPRichSnackbarState | null>(_state);
  React.useEffect(() => subscribeWCPRichSnackbar(setCurrent), []);
  const show = React.useCallback((options: WCPRichSnackbarOptions) => wcpRichSnackbar(options), []);
  const dismiss = React.useCallback(() => dismissWCPRichSnackbar(), []);
  return {snackbar: current, show, dismiss};
};

// ── Component ─────────────────────────────────────────────────────────────────

export interface WCPRichSnackbarProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  open?: boolean;
  color?: WCPRichSnackbarColor;
  contentVariant?: WCPRichSnackbarContentVariant;
  leadingSlot?: React.ReactNode;
  message: string | React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  onClose?: () => void;
  duration?: number;
  position?: 'bottom-left' | 'bottom-center' | 'bottom-right';
  inline?: boolean;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

const POSITION_CLASS: Record<string, string> = {
  'bottom-left': 'ld-wcp-richsnackbar-bottomLeft',
  'bottom-center': 'ld-wcp-richsnackbar-bottomCenter',
  'bottom-right': 'ld-wcp-richsnackbar-bottomRight',
};

const COLOR_CLASS: Record<WCPRichSnackbarColor, string> = {
  primary: 'ld-wcp-richsnackbar-primary',
  secondary: 'ld-wcp-richsnackbar-secondary',
  inverse: 'ld-wcp-richsnackbar-inverse',
  brand: 'ld-wcp-richsnackbar-brand',
};

export const WCPRichSnackbar: React.FunctionComponent<WCPRichSnackbarProps> = (props) => {
  const {
    open = true, color = 'primary', contentVariant = 'left-regular',
    leadingSlot, message, actionLabel, onAction, onClose, duration = 4000,
    position = 'bottom-center', inline: isInline = false, className, ...rest
  } = applyCommonProps(props);

  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    if (open && duration !== Infinity && onClose) {
      timerRef.current = setTimeout(() => onClose(), duration);
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [open, duration, onClose]);

  if (!open && !isInline) return null;

  const isBold = contentVariant === 'left-bold' || contentVariant === 'center-bold';
  const isCenter = contentVariant === 'center-regular' || contentVariant === 'center-bold';

  const handleActionClick = () => { onAction?.(); onClose?.(); };

  return (
    <div
      className={cx(
        'ld-wcp-richsnackbar-snackbar',
        COLOR_CLASS[color],
        isInline ? 'ld-wcp-richsnackbar-inlineMode' : (POSITION_CLASS[position] ?? 'ld-wcp-richsnackbar-bottomCenter'),
        (open || isInline) && 'ld-wcp-richsnackbar-open',
        className
      )}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      {...rest}
    >
      <div className={cx('ld-wcp-richsnackbar-copy', isCenter && 'ld-wcp-richsnackbar-copyCenter')}>
        {leadingSlot && <div className="ld-wcp-richsnackbar-leading">{leadingSlot}</div>}
        <div className={cx('ld-wcp-richsnackbar-message', isBold && 'ld-wcp-richsnackbar-messageBold')}>{message}</div>
      </div>
      {(actionLabel || onClose) && (
        <div className="ld-wcp-richsnackbar-trailing">
          <div className="ld-wcp-richsnackbar-trailingActions">
            {actionLabel && (
              <div className="ld-wcp-richsnackbar-actionWrapper">
                <button type="button" className="ld-wcp-richsnackbar-actionBtn" onClick={handleActionClick}>{actionLabel}</button>
              </div>
            )}
            {onClose && (
              <div className="ld-wcp-richsnackbar-closeWrapper">
                <button type="button" className="ld-wcp-richsnackbar-closeBtn" onClick={onClose} aria-label="Close notification">
                  <CloseIcon size="small" />
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

WCPRichSnackbar.displayName = 'WCPRichSnackbar';

// ── Container ─────────────────────────────────────────────────────────────────

export const WCPRichSnackbarContainer: React.FunctionComponent = () => {
  const {snackbar} = useWCPRichSnackbar();
  if (!snackbar) return null;
  return (
    <WCPRichSnackbar
      open={snackbar.open}
      color={snackbar.color}
      contentVariant={snackbar.contentVariant}
      leadingSlot={snackbar.leadingSlot}
      message={snackbar.message}
      actionLabel={snackbar.actionLabel}
      onAction={snackbar.onAction}
      onClose={dismissWCPRichSnackbar}
      duration={snackbar.duration}
      position={snackbar.position}
    />
  );
};

WCPRichSnackbarContainer.displayName = 'WCPRichSnackbarContainer';
