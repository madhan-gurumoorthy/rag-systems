// @refresh reset

/**
 * @module WCPCountrySelectBottomSheet
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
import {Button} from '../Button';
import './WCPCountrySelectBottomSheet.css';

export interface WCPCountry {
  code: string;
  abbr: string;
  name: string;
  dialCode: string;
  flagUrl: string;
}

export const WCP_DEFAULT_COUNTRIES: WCPCountry[] = [
  { code: 'CA-NQ', abbr: 'CA', name: 'Canada (Not Quebec)', dialCode: '+1', flagUrl: 'https://flagcdn.com/w40/ca.png' },
  { code: 'CA-QC', abbr: 'CA', name: 'Canada (Quebec)', dialCode: '+1', flagUrl: 'https://flagcdn.com/w40/ca.png' },
  { code: 'CL', abbr: 'CL', name: 'Chile', dialCode: '+56', flagUrl: 'https://flagcdn.com/w40/cl.png' },
  { code: 'CO', abbr: 'CO', name: 'Colombia', dialCode: '+57', flagUrl: 'https://flagcdn.com/w40/co.png' },
  { code: 'MX', abbr: 'MX', name: 'Mexico', dialCode: '+52', flagUrl: 'https://flagcdn.com/w40/mx.png' },
  { code: 'US', abbr: 'US', name: 'United States', dialCode: '+1', flagUrl: 'https://flagcdn.com/w40/us.png' },
];

export interface WCPCountrySelectBottomSheetProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style' | 'open' | 'onSelect'> {
  countries?: WCPCountry[];
  value?: string;
  onSelect?: (country: WCPCountry) => void;
  showDialCode?: boolean;
  variant?: 'flat' | 'slot';
  title?: string;
  actionLabel?: string;
  onConfirm?: (selected: WCPCountry | undefined) => void;
  onClose?: () => void;
  open: boolean;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export const WCPCountrySelectBottomSheet: React.FunctionComponent<WCPCountrySelectBottomSheetProps> = (props) => {
  const {
    countries = WCP_DEFAULT_COUNTRIES,
    value,
    onSelect,
    showDialCode = false,
    variant = 'flat',
    title = 'Select country/region',
    actionLabel = 'Confirm',
    onConfirm,
    onClose,
    open,
    className,
    ...rest
  } = applyCommonProps(props);

  const [selected, setSelected] = React.useState(value ?? 'US');

  React.useEffect(() => {
    if (value !== undefined) setSelected(value);
  }, [value]);

  const handleSelect = (country: WCPCountry) => {
    setSelected(country.code);
    onSelect?.(country);
  };

  const handleConfirm = () => {
    const found = countries.find(c => c.code === selected);
    onConfirm?.(found);
    onClose?.();
  };

  if (!open) return null;

  return (
    <div className={cx('ld-wcp-countryselectbottomsheet-overlay', className)} onClick={onClose} role="dialog" aria-modal="true" {...rest}>
      <div className="ld-wcp-countryselectbottomsheet-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="ld-wcp-countryselectbottomsheet-header">
          <div className="ld-wcp-countryselectbottomsheet-headerInner">
            <h2 className="ld-wcp-countryselectbottomsheet-title">{title}</h2>
            <button type="button" className="ld-wcp-countryselectbottomsheet-closeBtn" onClick={onClose} aria-label="Close">
              <CloseIcon size="medium" />
            </button>
          </div>
        </div>
        <div className="ld-wcp-countryselectbottomsheet-content">
          <ul className={cx('ld-wcp-countryselectbottomsheet-list', variant === 'slot' ? 'ld-wcp-countryselectbottomsheet-listSlot' : 'ld-wcp-countryselectbottomsheet-listFlat')} role="radiogroup">
            {countries.map((country) => {
              const isSelected = country.code === selected;
              return (
                <li key={country.code}>
                  <button
                    type="button"
                    className={cx(
                      'ld-wcp-countryselectbottomsheet-countryRow',
                      variant === 'flat' ? 'ld-wcp-countryselectbottomsheet-countryRowFlat' : 'ld-wcp-countryselectbottomsheet-countryRowSlot',
                      isSelected && 'ld-wcp-countryselectbottomsheet-countryRowSelected',
                    )}
                    role="radio"
                    aria-checked={isSelected}
                    onClick={() => handleSelect(country)}
                  >
                    <span className="ld-wcp-countryselectbottomsheet-radio">
                      <svg
                        aria-hidden
                        className="ld-wcp-countryselectbottomsheet-radioSvg"
                        viewBox="0 0 24 24"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <circle className="ld-wcp-countryselectbottomsheet-radioOuter" cx="12" cy="12" r="11" />
                        <circle className="ld-wcp-countryselectbottomsheet-radioInner" cx="12" cy="12" r="4" />
                      </svg>
                    </span>
                    <img src={country.flagUrl} alt="" className="ld-wcp-countryselectbottomsheet-flag" />
                    <span className={cx('ld-wcp-countryselectbottomsheet-countryName', isSelected && 'ld-wcp-countryselectbottomsheet-countryNameSelected')}>
                      {country.name}
                    </span>
                    {showDialCode && <span className="ld-wcp-countryselectbottomsheet-dialCode">{country.dialCode}</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
        <div className="ld-wcp-countryselectbottomsheet-footer">
          <div className="ld-wcp-countryselectbottomsheet-divider" />
          <div className="ld-wcp-countryselectbottomsheet-footerInner">
            <Button variant="primary" isFullWidth onClick={handleConfirm}>{actionLabel}</Button>
          </div>
        </div>
      </div>
    </div>
  );
};
WCPCountrySelectBottomSheet.displayName = 'WCPCountrySelectBottomSheet';
