// @refresh reset

/**
 * @module WCPHeartView
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
import {cx, applyCommonProps, invariant, emit} from '../common';
import {Icon} from '../Icons';
import './WCPHeartView.css';

export interface WCPHeartViewProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style' | 'onChange'> {
  activated?: boolean;
  defaultActivated?: boolean;
  onChange?: (activated: boolean) => void;
  size?: 'small' | 'medium';
  listName?: string;
  onViewList?: () => void;
  /** Called when mobile snackbar should fire. Consumer provides snackbar implementation. */
  onSnackbar?: (message: string, actionLabel?: string, onAction?: () => void) => void;
  snackbarDuration?: number;
  disabled?: boolean;
  'aria-label'?: string;
  /** @default 'left' */
  calloutPosition?: 'left' | 'right' | 'bottom' | 'top';
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

type CalloutType = 'add' | 'saved' | 'removed' | null;

const SIZE_CLASS: Record<string, string> = {
  small: 'ld-wcp-heartview-sizeSmall',
  medium: 'ld-wcp-heartview-sizeMedium',
};

const CALLOUT_POS_CLASS: Record<string, string> = {
  left: 'ld-wcp-heartview-calloutLeft',
  right: 'ld-wcp-heartview-calloutRight',
  bottom: 'ld-wcp-heartview-calloutBottom',
  top: 'ld-wcp-heartview-calloutTop',
};

export const WCPHeartView: React.FunctionComponent<WCPHeartViewProps> = (props) => {
  const {
    activated: controlledActivated, defaultActivated = false, onChange,
    size, listName = 'My List', onViewList, onSnackbar,
    snackbarDuration = 3500, disabled = false, 'aria-label': ariaLabel,
    calloutPosition = 'left', className, ...rest
  } = applyCommonProps(props);

  const iconSize = size === 'small' ? 'small' as const : size === 'medium' ? 'medium' as const : undefined;

  const isControlled = controlledActivated !== undefined;
  const [internalActivated, setInternalActivated] = React.useState(defaultActivated);
  const activated = isControlled ? controlledActivated : internalActivated;

  const [callout, setCallout] = React.useState<CalloutType>(null);
  const calloutTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const hoverTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const isHoveredRef = React.useRef(false);
  const justToggledRef = React.useRef(false);

  const toggle = () => {
    if (disabled) return;
    const nextActivated = !activated;
    if (!isControlled) setInternalActivated(nextActivated);
    emit('ui:heart:toggle', {activated: nextActivated, listName});
    onChange?.(nextActivated);
    justToggledRef.current = true;

    if (calloutTimerRef.current) clearTimeout(calloutTimerRef.current);
    setCallout(nextActivated ? 'saved' : 'removed');
    calloutTimerRef.current = setTimeout(() => {
      justToggledRef.current = false;
      setCallout(isHoveredRef.current ? (nextActivated ? 'saved' : 'add') : null);
    }, 2000);

    const msg = nextActivated ? `Saved to favorites: ${listName}` : `Removed from favorites: ${listName}`;
    onSnackbar?.(msg, nextActivated ? 'View' : undefined, nextActivated ? onViewList : undefined);
  };

  const handleMouseEnter = () => { isHoveredRef.current = true; if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current); if (!justToggledRef.current) setCallout(activated ? 'saved' : 'add'); };
  const handleMouseLeave = () => { isHoveredRef.current = false; hoverTimerRef.current = setTimeout(() => { if (!justToggledRef.current) setCallout(null); }, 100); };

  React.useEffect(() => () => {
    if (calloutTimerRef.current) clearTimeout(calloutTimerRef.current);
    if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
  }, []);

  invariant(
    ariaLabel === undefined || (typeof ariaLabel === 'string' && ariaLabel.trim().length > 0),
    '`WCPHeartView` accessibility violation. If `aria-label` is provided it must be a non-empty string. Omit it to use the default "Add to favorites" / "Remove from favorites" label.',
  );

  const defaultAriaLabel = activated ? 'Remove from favorites' : 'Add to favorites';
  const effectiveAriaLabel = ariaLabel && ariaLabel.trim().length > 0 ? ariaLabel : defaultAriaLabel;

  const calloutText = (() => {
    if (callout === 'add') return 'Add to favorites';
    if (callout === 'saved') return `Saved to favorites: ${listName}`;
    if (callout === 'removed') return `Removed from favorites: ${listName}`;
    return null;
  })();

  return (
    <div className={cx('ld-wcp-heartview-wrapper', className)} {...rest}>
      {callout && calloutText && (
        <div className={cx('ld-wcp-heartview-callout', CALLOUT_POS_CLASS[calloutPosition])} role="tooltip">
          <span className="ld-wcp-heartview-calloutText">{calloutText}</span>
          {callout === 'saved' && onViewList && (
            <button type="button" className="ld-wcp-heartview-calloutAction" onClick={(e) => { e.stopPropagation(); onViewList(); }}>View</button>
          )}
          <span className="ld-wcp-heartview-calloutArrow" aria-hidden="true" />
        </div>
      )}
      <button
        type="button"
        className={cx(
          'ld-wcp-heartview-heartButton',
          activated && 'ld-wcp-heartview-activated',
          size ? SIZE_CLASS[size] : 'ld-wcp-heartview-sizeResponsive',
          disabled && 'ld-wcp-heartview-disabled'
        )}
        onClick={toggle}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        aria-label={effectiveAriaLabel}
        aria-pressed={activated}
        disabled={disabled}
      >
        <span className="ld-wcp-heartview-iconWrap">
          {activated
            ? <Icon name="HeartFill" size={iconSize} className="ld-wcp-heartview-iconFill" />
            : <Icon name="Heart" size={iconSize} className="ld-wcp-heartview-iconOutline" />}
        </span>
      </button>
    </div>
  );
};

WCPHeartView.displayName = 'WCPHeartView';
