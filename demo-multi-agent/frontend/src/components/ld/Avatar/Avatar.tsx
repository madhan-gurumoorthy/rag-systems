'use client';
// @refresh reset

/**
 * @module Avatar
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
import {cx, invariant, applyCommonProps} from '../common';
import './Avatar.css';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AvatarSize = 'xs' | 'small' | 'medium' | 'large' | 'xl';
export type AvatarShape = 'circular' | 'square';
export type AvatarColor = 'brand' | 'neutral';

interface AvatarBaseProps
  extends Omit<React.ComponentPropsWithoutRef<'span'>, 'className' | 'style'> {
  color?: AvatarColor;
  icon?: React.ReactNode;
  image?: {src: string; alt?: string};
  name?: string;
  shape?: AvatarShape;
  size?: AvatarSize;
}

export interface AvatarA11yLabelProps extends AvatarBaseProps {
  a11yLabel: string;
  a11yLabelledBy?: never;
}

export interface AvatarA11yLabelledByProps extends AvatarBaseProps {
  a11yLabel?: never;
  a11yLabelledBy: string;
}

export type AvatarProps = AvatarA11yLabelProps | AvatarA11yLabelledByProps;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return '';
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

// Default person icon SVG (inline)
function DefaultIcon() {
  return (
    <svg
      aria-hidden="true"
      className="ld-avatar-defaultIcon"
      fill="currentColor"
      height="1em"
      viewBox="0 0 20 20"
      width="1em"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M10 2a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm-5 9a2 2 0 0 0-2 2c0 1.7.83 2.97 2.13 3.78C6.42 17.58 8.15 18 10 18c1.85 0 3.58-.42 4.87-1.22C16.17 15.97 17 14.7 17 13a2 2 0 0 0-2-2H5Z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Avatar
// ---------------------------------------------------------------------------

export const Avatar: React.FunctionComponent<AvatarProps> = (props) => {
  const {
    a11yLabel,
    a11yLabelledBy,
    className,
    color = 'brand',
    icon,
    image,
    name,
    shape = 'circular',
    size = 'medium',
    ...rest
  } = applyCommonProps(props);

  const hasA11y = (a11yLabel ? 1 : 0) + (a11yLabelledBy ? 1 : 0) === 1;
  invariant(
    hasA11y,
    '`Avatar` accessibility violation. `Avatar` requires an `a11yLabel` OR an `a11yLabelledBy`.'
  );

  const [imgError, setImgError] = React.useState(false);

  const showImage = image?.src && !imgError;
  const initials = name ? getInitials(name) : '';

  const a11yProps = a11yLabel
    ? {'aria-label': a11yLabel, role: 'img' as const}
    : {'aria-labelledby': a11yLabelledBy, role: 'img' as const};

  const classes = cx(
    'ld-avatar-root',
    `ld-avatar-${size}`,
    `ld-avatar-${shape}`,
    `ld-avatar-${color}`,
    className
  );

  return (
    <span className={classes} {...a11yProps} {...rest}>
      {showImage ? (
        <img
          alt={image.alt || ''}
          className="ld-avatar-image"
          onError={() => setImgError(true)}
          src={image.src}
        />
      ) : initials ? (
        <span className="ld-avatar-initials">{initials}</span>
      ) : icon ? (
        <span className="ld-avatar-icon">{icon}</span>
      ) : (
        <span className="ld-avatar-icon"><DefaultIcon /></span>
      )}
    </span>
  );
};

Avatar.displayName = 'Avatar';
