'use client';
// @refresh reset

/**
 * @module Tooltip
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
import {cx, useStableId, applyCommonProps, useCSSTransition} from '../common';
import * as ReactDOM from 'react-dom';

import './Tooltip.css';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type TooltipPosition = 'above' | 'below' | 'before' | 'after';
export type TooltipRelationship = 'label' | 'description';

export interface TooltipProps {
  children: React.ReactElement;
  content: string;
  position?: TooltipPosition;
  relationship?: TooltipRelationship;
  showDelay?: number;
  hideDelay?: number;
}

// ---------------------------------------------------------------------------
// Portal helper
// ---------------------------------------------------------------------------

function useTooltipPortal() {
  const [container] = React.useState(() => {
    if (typeof document === 'undefined') return null;
    const el = document.createElement('div');
    el.setAttribute('data-ld-tooltip-portal', '');
    return el;
  });

  React.useEffect(() => {
    if (!container) return;
    document.body.appendChild(container);
    return () => {
      document.body.removeChild(container);
    };
  }, [container]);

  return container;
}

// ---------------------------------------------------------------------------
// Position calculation
// ---------------------------------------------------------------------------

const GAP = 4;

function calculatePosition(
  triggerRect: DOMRect,
  tooltipRect: DOMRect,
  position: TooltipPosition
): {top: number; left: number} {
  switch (position) {
    case 'above':
      return {
        top: triggerRect.top - tooltipRect.height - GAP,
        left: triggerRect.left + (triggerRect.width - tooltipRect.width) / 2,
      };
    case 'below':
      return {
        top: triggerRect.bottom + GAP,
        left: triggerRect.left + (triggerRect.width - tooltipRect.width) / 2,
      };
    case 'before':
      return {
        top: triggerRect.top + (triggerRect.height - tooltipRect.height) / 2,
        left: triggerRect.left - tooltipRect.width - GAP,
      };
    case 'after':
      return {
        top: triggerRect.top + (triggerRect.height - tooltipRect.height) / 2,
        left: triggerRect.right + GAP,
      };
  }
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

export const Tooltip: React.FunctionComponent<TooltipProps> = (props) => {
  const {
    children,
    content,
    position = 'above',
    relationship = 'description',
    showDelay = 250,
    hideDelay = 250,
  } = props;

  const tooltipId = useStableId();
  const triggerRef = React.useRef<HTMLElement>(null);
  const tooltipRef = React.useRef<HTMLDivElement>(null);
  const showTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const hideTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const [visible, setVisible] = React.useState(false);
  const [posStyle, setPosStyle] = React.useState<React.CSSProperties>({});
  const portalContainer = useTooltipPortal();

  const clearTimers = () => {
    if (showTimerRef.current) {
      clearTimeout(showTimerRef.current);
      showTimerRef.current = null;
    }
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
  };

  const show = React.useCallback(() => {
    clearTimers();
    showTimerRef.current = setTimeout(() => setVisible(true), showDelay);
  }, [showDelay]);

  const hide = React.useCallback(() => {
    clearTimers();
    hideTimerRef.current = setTimeout(() => setVisible(false), hideDelay);
  }, [hideDelay]);

  // Position update when visible — useLayoutEffect to calculate before paint
  React.useLayoutEffect(() => {
    if (!visible || !triggerRef.current || !tooltipRef.current) return;
    const triggerRect = triggerRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const pos = calculatePosition(triggerRect, tooltipRect, position);
    setPosStyle({top: pos.top, left: pos.left});
  }, [visible, position]);

  // Cleanup timers on unmount
  React.useEffect(() => {
    return clearTimers;
  }, []);

  // WCAG 1.4.13 — tooltip must be dismissable via Escape without moving focus.
  React.useEffect(() => {
    if (!visible) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        clearTimers();
        setVisible(false);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [visible]);

  const {shouldMount} = useCSSTransition({
    classNames: {
      enter: 'ld-tooltip-enter',
      enterActive: 'ld-tooltip-enterActive',
      exit: 'ld-tooltip-exit',
      exitActive: 'ld-tooltip-exitActive',
    },
    in: visible,
    mountOnEnter: true,
    nodeRef: tooltipRef as React.RefObject<Element>,
    timeout: 80,
    unmountOnExit: true,
  });

  // Augment trigger child with event handlers + ARIA
  const triggerChild = React.Children.only(children);
  const triggerProps: Record<string, unknown> = {
    ref: triggerRef,
    onMouseEnter: (e: React.MouseEvent) => {
      ((triggerChild.props as Record<string, unknown>).onMouseEnter as ((e: React.MouseEvent) => void) | undefined)?.(e);
      show();
    },
    onMouseLeave: (e: React.MouseEvent) => {
      ((triggerChild.props as Record<string, unknown>).onMouseLeave as ((e: React.MouseEvent) => void) | undefined)?.(e);
      hide();
    },
    onFocus: (e: React.FocusEvent) => {
      ((triggerChild.props as Record<string, unknown>).onFocus as ((e: React.FocusEvent) => void) | undefined)?.(e);
      show();
    },
    onBlur: (e: React.FocusEvent) => {
      ((triggerChild.props as Record<string, unknown>).onBlur as ((e: React.FocusEvent) => void) | undefined)?.(e);
      hide();
    },
  };

  if (relationship === 'label') {
    triggerProps['aria-labelledby'] = tooltipId;
  } else {
    triggerProps['aria-describedby'] = tooltipId;
  }

  const augmentedTrigger = React.cloneElement(triggerChild, triggerProps as Record<string, unknown>);

  const tooltipEl = shouldMount ? (
    <div
      className={cx('ld-tooltip-tooltip', `ld-tooltip-${position}`)}
      id={tooltipId}
      ref={tooltipRef}
      role="tooltip"
      style={posStyle}
    >
      {content}
    </div>
  ) : null;

  return (
    <>
      {augmentedTrigger}
      {portalContainer && tooltipEl
        ? ReactDOM.createPortal(tooltipEl, portalContainer)
        : tooltipEl}
    </>
  );
};

Tooltip.displayName = 'Tooltip';
