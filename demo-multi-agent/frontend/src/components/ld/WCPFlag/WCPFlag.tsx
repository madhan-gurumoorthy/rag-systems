// @refresh reset

/**
 * @module WCPFlag
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
import './WCPFlag.css';

export type WCPFlagVariant =
  | 'holiday-restricted'
  | 'brand-subtle'
  | 'scarcity'
  | 'savings-bold'
  | 'savings-subtle'
  | 'confidence-subtle'
  | 'confidence-bold'
  | 'confidence-alt'
  | 'confidence'
  | 'holiday-member'
  | 'social'
  | 'urgent';

export interface WCPFlagProps
  extends Omit<React.ComponentPropsWithoutRef<'span'>, 'className' | 'style'> {
  label?: string;
  variant?: WCPFlagVariant;
  leadingIcon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

const VARIANT_CLASS: Record<WCPFlagVariant, string> = {
  'holiday-restricted': 'ld-wcp-flag-holiday-restricted',
  'brand-subtle': 'ld-wcp-flag-brand-subtle',
  'scarcity': 'ld-wcp-flag-scarcity',
  'savings-bold': 'ld-wcp-flag-savings-bold',
  'savings-subtle': 'ld-wcp-flag-savings-subtle',
  'confidence-subtle': 'ld-wcp-flag-confidence-subtle',
  'confidence-bold': 'ld-wcp-flag-confidence-bold',
  'confidence-alt': 'ld-wcp-flag-confidence-alt',
  'confidence': 'ld-wcp-flag-confidence',
  'holiday-member': 'ld-wcp-flag-holiday-member',
  'social': 'ld-wcp-flag-social',
  'urgent': 'ld-wcp-flag-urgent',
};

export const WCP_FLAG_VARIANTS: Array<{ variant: WCPFlagVariant; label: string; description: string }> = [
  { variant: 'holiday-restricted', label: 'Holiday Restricted', description: 'Dark charcoal — items unavailable or restricted during holiday period' },
  { variant: 'brand-subtle', label: 'Brand Subtle', description: 'Subtle brand tint — tracks brand theme' },
  { variant: 'scarcity', label: 'Scarcity', description: 'Orange — low stock / limited availability indicator' },
  { variant: 'savings-bold', label: 'Savings Bold', description: 'Solid red — promotional savings / clearance' },
  { variant: 'savings-subtle', label: 'Savings Subtle', description: 'Light red tint, red text — savings indicator' },
  { variant: 'confidence-subtle', label: 'Confidence Subtle', description: 'Light blue tint — soft confidence / info badge' },
  { variant: 'confidence-bold', label: 'Confidence Bold', description: 'Solid blue — confidence badge' },
  { variant: 'confidence-alt', label: 'Confidence Alt', description: 'White fill, blue border — outlined confidence badge' },
  { variant: 'confidence', label: 'Confidence', description: 'Navy blue — confidence badge' },
  { variant: 'holiday-member', label: 'Holiday Member', description: 'Green — Walmart+ member during holiday season' },
  { variant: 'social', label: 'Social', description: 'Cyan — social proof indicator' },
  { variant: 'urgent', label: 'Urgent', description: 'Dark red — urgency / time-sensitive' },
];

export const WCPFlag: React.FunctionComponent<WCPFlagProps> = (props) => {
  const {label = 'Flag name', variant = 'brand-subtle', leadingIcon, trailingIcon, className, ...rest} = applyCommonProps(props);

  return (
    <span
      className={cx('ld-wcp-flag-flag', VARIANT_CLASS[variant], className)}
      data-variant={variant}
      {...rest}
    >
      {leadingIcon && <span className="ld-wcp-flag-iconWrap">{leadingIcon}</span>}
      <span className="ld-wcp-flag-label">{label}</span>
      {trailingIcon && <span className="ld-wcp-flag-iconWrap">{trailingIcon}</span>}
    </span>
  );
};

WCPFlag.displayName = 'WCPFlag';
