'use client';
// @refresh reset

/**
 * @module Text
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
import {cx, applyCommonProps, PolymorphicElementWithoutRef} from '../common';
import './Text.css';

// TextColor service
export type TextColor =
  | 'accentBlue' | 'accentCyan' | 'accentGray' | 'accentGreen' | 'accentOrange'
  | 'accentPink' | 'accentPurple' | 'accentRed' | 'accentSpark' | 'accentYellow'
  | 'activated' | 'brand' | 'disabled' | 'edited' | 'info' | 'inverse'
  | 'negative' | 'onFill' | 'positive' | 'subtle' | 'subtlest' | 'warning';

const TEXT_COLOR_MAP: Record<string, string> = {"accentBlue":"#0053e2","accentBlueBold":"#002e99","accentCyan":"#0076b3","accentCyanBold":"#004a70","accentGray":"#74767c","accentGrayBold":"#515357","accentGreen":"#2a8703","accentGreenBold":"#1d5f02","accentOrange":"#c83c00","accentOrangeBold":"#af2f00","accentPink":"#cb2c90","accentPinkBold":"#8c1e64","accentPurple":"#63327e","accentPurpleBold":"#452358","accentRed":"#ea1100","accentRedBold":"#a20c00","accentSpark":"#995213","accentSparkBold":"#662b0d","accentTeal":"#00809e","accentTealBold":"#005a6f","accentYellow":"#996900","accentYellowBold":"#663800","onFillAccentBlue":"#ffffff","onFillAccentBlueSubtle":"#002e99","onFillAccentCyan":"#ffffff","onFillAccentCyanSubtle":"#004a70","onFillAccentGray":"#ffffff","onFillAccentGraySubtle":"#515357","onFillAccentGreen":"#ffffff","onFillAccentGreenSubtle":"#1d5f02","onFillAccentOrange":"#2e2f32","onFillAccentOrangeSubtle":"#af2f00","onFillAccentPink":"#ffffff","onFillAccentPinkSubtle":"#8c1e64","onFillAccentPurple":"#ffffff","onFillAccentPurpleSubtle":"#452358","onFillAccentRed":"#ffffff","onFillAccentRedSubtle":"#a20c00","onFillAccentSpark":"#2e2f32","onFillAccentSparkSubtle":"#662b0d","onFillAccentTeal":"#ffffff","onFillAccentTealSubtle":"#005a6f","onFillAccentYellow":"#2e2f32","onFillAccentYellowSubtle":"#663800","onFill":"#2e2f32","onFillActivated":"#ffffff","onFillActivatedDisabled":"#ffffff","onFillActivatedSubtle":"#2e2f32","onFillActivatedSubtleDisabled":"#babbbe","onFillBrand":"#ffffff","onFillBrandBold":"#ffffff","onFillBrandSubtle":"#114ab6","onFillDisabled":"#babbbe","onFillEdited":"#ffffff","onFillEditedSubtle":"#452358","onFillInfo":"#ffffff","onFillInfoSubtle":"#002e99","onFillInverse":"#ffffff","onFillNegative":"#ffffff","onFillNegativeSubtle":"#a20c00","onFillPositive":"#ffffff","onFillPositiveSubtle":"#1d5f02","onFillTransparent":"#2e2f32","onFillWarning":"#2e2f32","onFillWarningSubtle":"#662b0d","activated":"#114ab6","brand":"#0053e2","brandBold":"#001e60","disabled":"#babbbe","edited":"#63327e","editedBold":"#452358","info":"#0053e2","infoBold":"#002e99","infoInverse":"#c9dcfd","inverse":"#ffffff","magicStart":"#0053E2","magicMiddle":"#3D90EC","magicStop":"#79CDF6","negative":"#ea1100","negativeBold":"#a20c00","negativeInverse":"#f69991","positive":"#2a8703","positiveBold":"#1d5f02","positiveInverse":"#95c381","subtle":"#515357","subtlest":"#74767c","warning":"#995213","warningBold":"#662b0d","warningInverse":"#ffedbc"};

function getTextColorStyle(color: TextColor): React.CSSProperties {
  const resolved = TEXT_COLOR_MAP[color];
  return resolved ? { color: resolved } : {};
}

// ---------------------------------------------------------------------------
// Body
// ---------------------------------------------------------------------------

export type BodyColor = TextColor;
export type BodyElement = 'div' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'p' | 'span';
export type BodySize = 'large' | 'medium' | 'small';
export type BodyWeight = 'default' | 'alt';

interface BodyBaseProps {
  color?: BodyColor;
  isMonospace?: boolean;
  size?: BodySize;
  weight?: BodyWeight;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export type BodyProps<T extends BodyElement> = PolymorphicElementWithoutRef<T, BodyBaseProps>;

export const Body = <T extends BodyElement = 'span'>(props: BodyProps<T>) => {

  const {as: Component = 'span' as any, className, color, isMonospace = false, size = 'medium', weight = 'default', ...rest} = applyCommonProps(props as any);
  const colorStyle = color ? getTextColorStyle(color) : undefined;
  return (
    <Component
      className={cx(
        'ld-text-body-body',
        isMonospace && 'ld-text-body-isMonospace',
        size === 'large' && 'ld-text-body-large',
        size === 'medium' && 'ld-text-body-medium',
        size === 'small' && 'ld-text-body-small',
        weight === 'default' && 'ld-text-body-weightDefault',
        weight === 'alt' && 'ld-text-body-weightAlt',
        className,
      )}
      style={{...colorStyle, ...(rest as any).style}}
      {...rest}
    />
  );
};
Body.displayName = 'Body';

// ---------------------------------------------------------------------------
// Caption
// ---------------------------------------------------------------------------

export type CaptionColor = TextColor;
export type CaptionElement = 'div' | 'p' | 'small' | 'span';
export type CaptionWeight = 'default' | 'alt';

interface CaptionBaseProps {
  color?: CaptionColor;
  isMonospace?: boolean;
  weight?: CaptionWeight;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export type CaptionProps<T extends CaptionElement> = PolymorphicElementWithoutRef<T, CaptionBaseProps>;

export const Caption = <T extends CaptionElement = 'span'>(props: CaptionProps<T>) => {

  const {as: Component = 'span' as any, className, color, isMonospace = false, weight = 'default', ...rest} = applyCommonProps(props as any);
  const colorStyle = color ? getTextColorStyle(color) : undefined;
  return (
    <Component
      className={cx(
        'ld-text-caption-caption',
        isMonospace && 'ld-text-caption-isMonospace',
        weight === 'default' && 'ld-text-caption-weightDefault',
        weight === 'alt' && 'ld-text-caption-weightAlt',
        className,
      )}
      style={{...colorStyle, ...(rest as any).style}}
      {...rest}
    />
  );
};
Caption.displayName = 'Caption';

// ---------------------------------------------------------------------------
// Heading
// ---------------------------------------------------------------------------

export type HeadingColor = TextColor;
export type HeadingElement = 'div' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'span';
export type HeadingSize = 'large' | 'medium' | 'small';
export type HeadingWeight = 'default' | 'alt';

interface HeadingBaseProps {
  color?: HeadingColor;
  size?: HeadingSize;
  weight?: HeadingWeight;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export type HeadingProps<T extends HeadingElement> = PolymorphicElementWithoutRef<T, HeadingBaseProps>;

export const Heading = <T extends HeadingElement = 'span'>(props: HeadingProps<T>) => {

  const {as: Component = 'span' as any, className, color, size = 'medium', weight = 'default', ...rest} = applyCommonProps(props as any);
  const colorStyle = color ? getTextColorStyle(color) : undefined;
  return (
    <Component
      className={cx(
        'ld-text-heading-heading',
        size === 'large' && 'ld-text-heading-large',
        size === 'medium' && 'ld-text-heading-medium',
        size === 'small' && 'ld-text-heading-small',
        weight === 'default' && 'ld-text-heading-weightDefault',
        weight === 'alt' && 'ld-text-heading-weightAlt',
        className,
      )}
      style={{...colorStyle, ...(rest as any).style}}
      {...rest}
    />
  );
};
Heading.displayName = 'Heading';

// ---------------------------------------------------------------------------
// Display
// ---------------------------------------------------------------------------

export type DisplayColor = TextColor;
export type DisplayElement = 'div' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'span';
export type DisplaySize = 'large' | 'small';
export type DisplayWeight = 'default' | 'alt';

interface DisplayBaseProps {
  color?: DisplayColor;
  size?: DisplaySize;
  weight?: DisplayWeight;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export type DisplayProps<T extends DisplayElement> = PolymorphicElementWithoutRef<T, DisplayBaseProps>;

export const Display = <T extends DisplayElement = 'span'>(props: DisplayProps<T>) => {

  const {as: Component = 'span' as any, className, color, size = 'large', weight = 'default', ...rest} = applyCommonProps(props as any);
  const colorStyle = color ? getTextColorStyle(color) : undefined;
  return (
    <Component
      className={cx(
        'ld-text-display-display',
        size === 'large' && 'ld-text-display-large',
        size === 'small' && 'ld-text-display-small',
        weight === 'default' && 'ld-text-display-weightDefault',
        weight === 'alt' && 'ld-text-display-weightAlt',
        className,
      )}
      style={{...colorStyle, ...(rest as any).style}}
      {...rest}
    />
  );
};
Display.displayName = 'Display';
