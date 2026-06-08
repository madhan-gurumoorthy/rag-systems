'use client';
// @refresh reset

/**
 * @module Slider
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
import {cx, applyCommonProps, mergeRefs} from '../common';
import type {CommonProps} from '../common';

import './Slider.css';
import './Slider.css';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface SliderProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange' | 'defaultValue'>,
    CommonProps {
  /** Minimum value. @default 0 */
  min?: number;
  /** Maximum value. @default 100 */
  max?: number;
  /** Step increment. @default 1 */
  step?: number;
  /** Controlled value (single-value slider). Provide as `[number]`. */
  value?: number[];
  /** Uncontrolled default value. @default [0] */
  defaultValue?: number[];
  /** Callback fired on value change. */
  onValueChange?: (value: number[]) => void;
  /** Disable the slider. @default false */
  disabled?: boolean;
  /** Orientation. Currently only horizontal is implemented. @default "horizontal" */
  orientation?: 'horizontal' | 'vertical';
  /** Hidden input name for form submission. */
  name?: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

const Slider = React.forwardRef<HTMLDivElement, SliderProps>(
  (rawProps, ref) => {
    const {
      className,
      min = 0,
      max = 100,
      step = 1,
      value: controlledValue,
      defaultValue = [0],
      onValueChange,
      disabled = false,
      name,
      UNSAFE_className,
      UNSAFE_style,
      ...props
    } = rawProps;

    const isControlled = controlledValue !== undefined;
    const [internalValue, setInternalValue] = React.useState(defaultValue);
    const currentValue = isControlled ? controlledValue : internalValue;
    const val = currentValue[0] ?? min;
    const pct = max === min ? 0 : ((val - min) / (max - min)) * 100;

    const rootRef = React.useRef<HTMLDivElement>(null);
    const trackRef = React.useRef<HTMLDivElement>(null);
    const isDragging = React.useRef(false);

    const updateValue = React.useCallback(
      (clientX: number) => {
        const track = trackRef.current;
        if (!track || disabled) return;
        const rect = track.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
        const raw = min + ratio * (max - min);
        const stepped = Math.round(raw / step) * step;
        const clamped = Math.max(min, Math.min(max, stepped));
        const next = [clamped];
        if (!isControlled) setInternalValue(next);
        onValueChange?.(next);
      },
      [disabled, min, max, step, isControlled, onValueChange],
    );

    const handlePointerDown = React.useCallback(
      (e: React.PointerEvent) => {
        if (disabled) return;
        e.preventDefault();
        rootRef.current?.setPointerCapture(e.pointerId);
        isDragging.current = true;
        updateValue(e.clientX);
      },
      [disabled, updateValue],
    );

    const handlePointerMove = React.useCallback(
      (e: React.PointerEvent) => {
        if (!isDragging.current || disabled) return;
        updateValue(e.clientX);
      },
      [disabled, updateValue],
    );

    const handlePointerUp = React.useCallback(
      () => {
        isDragging.current = false;
      },
      [],
    );

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (disabled) return;
      let next = val;
      switch (e.key) {
        case 'ArrowRight':
        case 'ArrowUp':
          next = Math.min(max, val + step);
          break;
        case 'ArrowLeft':
        case 'ArrowDown':
          next = Math.max(min, val - step);
          break;
        case 'Home':
          next = min;
          break;
        case 'End':
          next = max;
          break;
        default:
          return;
      }
      e.preventDefault();
      const arr = [next];
      if (!isControlled) setInternalValue(arr);
      onValueChange?.(arr);
    };

    const rootClasses = cx(
      'ld-slider-root',
      disabled && 'ld-slider-root--disabled',
      UNSAFE_className,
    );

    return (
      <div
        ref={mergeRefs(ref, rootRef)}
        className={rootClasses}
        style={UNSAFE_style}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        {...props}
      >
        <div
          ref={trackRef}
          className="ld-slider-track"
        >
          <div
            className="ld-slider-fill"
            style={{width: `${pct}%`}}
          />
        </div>
        <span
          role="slider"
          tabIndex={disabled ? -1 : 0}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={val}
          aria-disabled={disabled || undefined}
          className="ld-slider-thumb"
          style={{
            left: `calc(${pct}% - 10px)`,
          }}
          onKeyDown={handleKeyDown}
        />
        {name && <input type="hidden" name={name} value={val} />}
      </div>
    );
  },
);

Slider.displayName = 'Slider';

export {Slider};
