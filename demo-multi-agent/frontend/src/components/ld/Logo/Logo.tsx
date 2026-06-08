'use client';
// @refresh reset

/**
 * @module Logo
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
import {
  getCurrentTheme,
  getThemePrimaryIconFont,
  useThemeMediaKey,
  type ThemeName,
} from '../../../utils/Theming';
import {MEDIA_SVGS} from '../media';
import './Logo.css';

interface LogoProps {
  /** Glyph name as it appears in Airtable (e.g. "Logo", "Wordmark", "LogoInverse"). Default: "Logo". */
  name?: string;
  /** Logo height in px. Width follows the SVG's intrinsic aspect ratio. */
  size?: number;
  /** Override the active tenant; defaults to the current theme. */
  tenant?: ThemeName;
  /** Accessible label. Defaults to `${tenant} Homepage`. */
  a11yLabel?: string;
  className?: string;
  style?: CSSProperties;
  title?: string;
}

export function Logo({
  name = 'Logo',
  size = 36,
  tenant,
  a11yLabel,
  className,
  style,
  title,
}: LogoProps) {
  const runtimeKey = useThemeMediaKey();
  const mediaKey = tenant ? getThemePrimaryIconFont(tenant) : runtimeKey;
  const svg = MEDIA_SVGS[mediaKey]?.[name];
  if (!svg) return null;

  const label = a11yLabel ?? `${tenant ?? getCurrentTheme()} Homepage`;

  return (
    <span
      role="img"
      aria-label={label}
      title={title}
      className={`ld-logo${className ? ` ${className}` : ''}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: size,
        lineHeight: 0,
        ...style,
      }}
      dangerouslySetInnerHTML={{__html: svg}}
    />
  );
}
