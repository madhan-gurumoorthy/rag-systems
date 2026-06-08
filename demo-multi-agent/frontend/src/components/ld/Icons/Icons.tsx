'use client';
// @refresh reset

/**
 * @module Icons
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
import type {CSSProperties} from 'react';
import {useThemeIconPrefix} from '../../../utils/Theming';

export {LD_ICON_CODEPOINTS} from '../../../fonts/ld/LDIcons';

type IconSize = 'small' | 'medium' | 'large';

const SIZES: Record<IconSize, string> = {small: '1rem', medium: '1.5rem', large: '2rem'};
const ALIGNS: Record<IconSize, string> = {small: '-0.175em', medium: '-0.25em', large: '-0.325em'};

type IconProps = {
  size?: IconSize;
  /**
   * Accessible label for icons that convey meaning on their own.
   * Mutually exclusive with `decorative`.
   */
  a11yLabel?: string;
  /**
   * Marks the icon as purely decorative — it will be `aria-hidden` from
   * assistive tech. Use this when the icon sits next to a text label that
   * already describes the affordance (e.g., a Button with a leading icon).
   * Mutually exclusive with `a11yLabel`.
   */
  decorative?: boolean;
  style?: CSSProperties;
  className?: string;
  title?: string;
};

export function Icon({name, size, a11yLabel, decorative, style, className, title}: IconProps & {name: string}) {
  const sizeStyle = size && !style?.fontSize ? {fontSize: SIZES[size], verticalAlign: ALIGNS[size]} : {};
  const iconSize = style?.fontSize ?? style?.width ?? style?.height ?? sizeStyle.fontSize;
  const fontSize = typeof iconSize === 'number' ? `${iconSize}px` : iconSize ?? '1em';
  // `decorative` and `a11yLabel` both lead to valid a11y. A labeled icon
  // is exposed as `role="img"`; a decorative or unlabeled icon is hidden.
  // Passing `decorative` alongside `a11yLabel` is nonsensical — the label wins.
  const a11y = a11yLabel
    ? {'aria-label': a11yLabel, role: 'img' as const}
    : {'aria-hidden': true as const};
  const prefix = useThemeIconPrefix();
  return (
    <i {...a11y} className={`${prefix} ${prefix}-${name}${className ? ` ${className}` : ''}`} title={title} style={{fontSize, verticalAlign: sizeStyle.verticalAlign, ...style}} />
  );
}

// Existing wrappers
export const SearchIcon = (props: IconProps) => <Icon name="Search" {...props} />;
export const ChevronUpIcon = (props: IconProps) => <Icon name="ChevronUp" {...props} />;
export const SettingsIcon = (props: IconProps) => <Icon name="Gear" {...props} />;
export const StarIcon = (props: IconProps) => <Icon name="Star" {...props} />;
export const CheckIcon = (props: IconProps) => <Icon name="Check" {...props} />;
export const PlusIcon = (props: IconProps) => <Icon name="Plus" {...props} />;
export const InfoIcon = (props: IconProps) => <Icon name="InfoCircle" {...props} />;
export const AlertTriangleIcon = (props: IconProps) => <Icon name="Warning" {...props} />;
export const XIcon = (props: IconProps) => <Icon name="Close" {...props} />;

// Migrated from common/icons.tsx
export const CloseIcon = (props: IconProps) => <Icon name="Close" {...props} />;
export const ChevronDownIcon = (props: IconProps) => <Icon name="ChevronDown" {...props} />;
export const ChevronRightIcon = (props: IconProps) => <Icon name="ChevronRight" {...props} />;
export const ChevronLeftIcon = (props: IconProps) => <Icon name="ChevronLeft" {...props} />;
export const ExclamationCircleIcon = (props: IconProps) => <Icon name="ExclamationCircle" {...props} />;
export const ExclamationCircleFillIcon = (props: IconProps) => <Icon name="ExclamationCircleFill" {...props} />;
export const InfoCircleIcon = (props: IconProps) => <Icon name="InfoCircle" {...props} />;
export const CheckCircleIcon = (props: IconProps) => <Icon name="CheckCircle" {...props} />;
export const WarningIcon = (props: IconProps) => <Icon name="Warning" {...props} />;
export const CaretDownIcon = (props: IconProps) => <Icon name="CaretDown" {...props} />;
export const ArrowUpIcon = (props: IconProps) => <Icon name="ArrowUp" {...props} />;
export const ArrowDownIcon = (props: IconProps) => <Icon name="ArrowDown" {...props} />;
export const CalendarIcon = (props: IconProps) => <Icon name="Calendar" {...props} />;
export const EditIcon = (props: IconProps) => <Icon name="Pencil" {...props} />;
export const SelectedIcon = (props: IconProps) => <Icon name="Check" {...props} />;
export const GiftIcon = (props: IconProps) => <Icon name="Gift" {...props} />;
export const DollarIcon = (props: IconProps) => <Icon name="Dollar" {...props} />;
export const TagIcon = (props: IconProps) => <Icon name="Tag" {...props} />;
export const LockIcon = (props: IconProps) => <Icon name="Lock" {...props} />;
export const FlashIcon = (props: IconProps) => <Icon name="Flash" {...props} />;
export const CartIcon = (props: IconProps) => <Icon name="Cart" {...props} />;
export const UsersFillIcon = (props: IconProps) => <Icon name="Users" {...props} />;
export const CheckCircleIcon2 = (props: IconProps) => <Icon name="CheckCircle" {...props} />;
export const ErrorTextIcon = ExclamationCircleFillIcon;
export const SaveIcon = CheckCircleIcon;
