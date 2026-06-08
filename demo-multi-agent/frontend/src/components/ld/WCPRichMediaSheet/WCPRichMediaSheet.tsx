// @refresh reset

/**
 * @module WCPRichMediaSheet
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
import './WCPRichMediaSheet.css';

export type WCPRichMediaSheetHeaderVariant = 'title' | 'title-subtitle' | 'logo-left' | 'logo-center' | 'inverse' | 'none';
export type WCPRichMediaSheetSurfaceVariant = 'default' | 'brand' | 'brand-bold' | 'media';

export interface WCPRichMediaSheetProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style' | 'title'> {
  isOpen: boolean;
  onClose: () => void;
  /** @default 'title' */
  headerVariant?: WCPRichMediaSheetHeaderVariant;
  title?: string;
  subtitle?: string;
  logoSlot?: React.ReactNode;
  /** @default 'default' */
  surfaceVariant?: WCPRichMediaSheetSurfaceVariant;
  children: React.ReactNode;
  actions?: React.ReactNode;
  showFooterDivider?: boolean;
  /** @default 'content' */
  adjustHeight?: 'fixed' | 'content';
  ariaLabel?: string;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

function XIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M11.7803 13.0788L18 19.2985L19.0607 18.2378L12.841 12.0181L19.0607 5.79845L18 4.73779L11.7803 10.9575L5.56066 4.73779L4.5 5.79845L10.7197 12.0181L4.5 18.2378L5.56066 19.2985L11.7803 13.0788Z" fill="currentColor" />
    </svg>
  );
}

function CloseBtn({onClose, inverse}: {onClose: () => void; inverse?: boolean}) {
  return (
    <button
      type="button"
      onClick={onClose}
      className={cx('ld-wcp-richmediasheet-closeButton', inverse && 'ld-wcp-richmediasheet-closeButtonInverse')}
      aria-label="Close"
    >
      <XIcon />
    </button>
  );
}

function DragHandle({inverse}: {inverse?: boolean}) {
  return <div className={cx('ld-wcp-richmediasheet-grabber', inverse && 'ld-wcp-richmediasheet-grabberInverse')} />;
}

function SheetHeader({variant, title, subtitle, logoSlot, onClose, forceInverse = false}: {variant: WCPRichMediaSheetHeaderVariant; title?: string; subtitle?: string; logoSlot?: React.ReactNode; onClose: () => void; forceInverse?: boolean}) {
  if (variant === 'none') {
    return (
      <div className="ld-wcp-richmediasheet-headerNone">
        <DragHandle inverse={forceInverse} />
        <div className="ld-wcp-richmediasheet-headerNoneRow">
          <CloseBtn onClose={onClose} inverse={forceInverse} />
        </div>
      </div>
    );
  }

  if (variant === 'inverse') {
    return (
      <div className="ld-wcp-richmediasheet-headerInverse">
        <DragHandle inverse />
        <div className="ld-wcp-richmediasheet-headerRow">
          <div className="ld-wcp-richmediasheet-headerTitleFrame">
            <h2 className={cx('ld-wcp-richmediasheet-headerTitle', 'ld-wcp-richmediasheet-headerTitleInverse')}>{title}</h2>
          </div>
          <CloseBtn onClose={onClose} inverse />
        </div>
        <div className="ld-wcp-richmediasheet-headerDividerInverse" />
      </div>
    );
  }

  if (variant === 'title-subtitle') {
    return (
      <div className="ld-wcp-richmediasheet-header">
        <DragHandle inverse={forceInverse} />
        <div className="ld-wcp-richmediasheet-headerRow">
          <div className="ld-wcp-richmediasheet-headerTitleFrame">
            <h2 className={cx('ld-wcp-richmediasheet-headerTitle', forceInverse && 'ld-wcp-richmediasheet-headerTitleBoldSurface')}>{title}</h2>
            {subtitle && <p className={cx('ld-wcp-richmediasheet-headerSubtitle', forceInverse && 'ld-wcp-richmediasheet-headerSubtitleBoldSurface')}>{subtitle}</p>}
          </div>
          <CloseBtn onClose={onClose} inverse={forceInverse} />
        </div>
        <div className={forceInverse ? 'ld-wcp-richmediasheet-headerDividerInverse' : 'ld-wcp-richmediasheet-headerDivider'} />
      </div>
    );
  }

  if (variant === 'logo-left') {
    return (
      <div className="ld-wcp-richmediasheet-header">
        <DragHandle inverse={forceInverse} />
        <div className="ld-wcp-richmediasheet-headerRow">
          <div className="ld-wcp-richmediasheet-headerLogoLeft">{logoSlot}</div>
          <CloseBtn onClose={onClose} inverse={forceInverse} />
        </div>
      </div>
    );
  }

  if (variant === 'logo-center') {
    return (
      <div className="ld-wcp-richmediasheet-header">
        <DragHandle inverse={forceInverse} />
        <div className="ld-wcp-richmediasheet-headerRow">
          <div className="ld-wcp-richmediasheet-headerLogoCenter">{logoSlot}</div>
          <CloseBtn onClose={onClose} inverse={forceInverse} />
        </div>
      </div>
    );
  }

  // Default: 'title'
  return (
    <div className="ld-wcp-richmediasheet-header">
      <DragHandle inverse={forceInverse} />
      <div className="ld-wcp-richmediasheet-headerRow">
        <div className="ld-wcp-richmediasheet-headerTitleFrame">
          <h2 className={cx('ld-wcp-richmediasheet-headerTitle', forceInverse && 'ld-wcp-richmediasheet-headerTitleBoldSurface')}>{title}</h2>
        </div>
        <CloseBtn onClose={onClose} inverse={forceInverse} />
      </div>
    </div>
  );
}

const SURFACE_CLASS: Record<string, string> = {
  default: 'ld-wcp-richmediasheet-surfaceDefault',
  brand: 'ld-wcp-richmediasheet-surfaceBrand',
  'brand-bold': 'ld-wcp-richmediasheet-surfaceBrandBold',
  media: 'ld-wcp-richmediasheet-surfaceMedia',
};

const FOOTER_CLASS: Record<string, string> = {
  default: 'ld-wcp-richmediasheet-footerDefault',
  brand: 'ld-wcp-richmediasheet-footerBrand',
  'brand-bold': 'ld-wcp-richmediasheet-footerBrandBold',
  media: 'ld-wcp-richmediasheet-footerMedia',
};

export const WCPRichMediaSheet: React.FunctionComponent<WCPRichMediaSheetProps> = (props) => {
  const {
    isOpen, onClose, headerVariant = 'title', title, subtitle, logoSlot,
    surfaceVariant = 'default', children, actions, showFooterDivider,
    adjustHeight = 'content', ariaLabel, className, ...rest
  } = applyCommonProps(props);

  React.useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const showFooter = actions != null;
  const showDivider = showFooterDivider ?? showFooter;
  const isBoldSurface = surfaceVariant === 'brand-bold';

  return (
    <>
      <div className="ld-wcp-richmediasheet-overlay" onClick={onClose} />
      <div
        className={cx(
          'ld-wcp-richmediasheet-sheet',
          adjustHeight === 'fixed' ? 'ld-wcp-richmediasheet-sheetFixed' : 'ld-wcp-richmediasheet-sheetContent',
          SURFACE_CLASS[surfaceVariant],
          className
        )}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        {...rest}
      >
        <SheetHeader variant={headerVariant} title={title} subtitle={subtitle} logoSlot={logoSlot} onClose={onClose} forceInverse={isBoldSurface} />
        <div className={cx('ld-wcp-richmediasheet-contentArea', adjustHeight === 'fixed' && 'ld-wcp-richmediasheet-contentAreaFixed')}>
          {children}
        </div>
        {showFooter && (
          <div className={cx('ld-wcp-richmediasheet-footer', FOOTER_CLASS[surfaceVariant])}>
            {showDivider && <div className="ld-wcp-richmediasheet-footerDivider" />}
            <div className="ld-wcp-richmediasheet-footerActions">{actions}</div>
          </div>
        )}
      </div>
    </>
  );
};

WCPRichMediaSheet.displayName = 'WCPRichMediaSheet';
