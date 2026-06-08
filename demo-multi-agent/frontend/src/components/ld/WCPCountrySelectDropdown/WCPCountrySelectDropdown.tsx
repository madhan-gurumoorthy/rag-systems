// @refresh reset

/**
 * @module WCPCountrySelectDropdown
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
import {CloseIcon, CaretDownIcon, SearchIcon} from '../Icons';
import {Badge} from '../Badge';
import {Button} from '../Button';
import {WCPCountry, WCP_DEFAULT_COUNTRIES} from '../WCPCountrySelectBottomSheet';
import './WCPCountrySelectDropdown.css';

export type {WCPCountry} from '../WCPCountrySelectBottomSheet';

// Security: validates that a flag URL uses only http/https schemes before
// binding it to an img src attribute. Rejects javascript:, data:, and any
// other scheme that could execute code in the browser.
const safeFlagUrl = (url: string): string => {
  if (!url) return '';
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? url : '';
  } catch {
    return '';
  }
};

export interface WCPCountrySelectDropdownProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style' | 'onChange'> {
  countries?: WCPCountry[];
  mode?: 'single' | 'multi';
  value?: string | string[];
  onChange?: (value: string | string[], countries: WCPCountry | WCPCountry[]) => void;
  placeholder?: string;
  showDialCode?: boolean;
  confirmLabel?: string;
  label?: string;
  disabled?: boolean;
  triggerWidth?: string | number;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export const WCPCountrySelectDropdown: React.FunctionComponent<WCPCountrySelectDropdownProps> = (props) => {
  const {
    countries = WCP_DEFAULT_COUNTRIES,
    mode = 'single',
    value,
    onChange,
    placeholder = 'Select country',
    showDialCode = false,
    confirmLabel = 'Apply',
    label,
    disabled = false,
    triggerWidth = 280,
    className,
    ...rest
  } = applyCommonProps(props);

  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState('');
  const [singleSelected, setSingleSelected] = React.useState<string>(typeof value === 'string' ? value : '');
  const [multiSelected, setMultiSelected] = React.useState<string[]>(Array.isArray(value) ? value : []);
  const [pendingMulti, setPendingMulti] = React.useState<string[]>(Array.isArray(value) ? value : []);

  React.useEffect(() => {
    if (typeof value === 'string') setSingleSelected(value);
    else if (Array.isArray(value)) { setMultiSelected(value); setPendingMulti(value); }
  }, [value]);

  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const dropdownRef = React.useRef<HTMLDivElement>(null);
  const searchRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!triggerRef.current?.contains(e.target as Node) && !dropdownRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    if (open) document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  React.useEffect(() => {
    if (open && searchRef.current) searchRef.current.focus();
  }, [open]);

  const filtered = countries.filter(c => c.name.toLowerCase().includes(search.toLowerCase()));

  const handleSingleSelect = (country: WCPCountry) => {
    setSingleSelected(country.code);
    onChange?.(country.code, country);
    setOpen(false);
    setSearch('');
  };

  const handleMultiToggle = (code: string) => {
    setPendingMulti(prev => prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]);
  };

  const handleMultiConfirm = () => {
    setMultiSelected(pendingMulti);
    const selected = countries.filter(c => pendingMulti.includes(c.code));
    onChange?.(pendingMulti, selected);
    setOpen(false);
    setSearch('');
  };

  const selectedCountry = mode === 'single' ? countries.find(c => c.code === singleSelected) : undefined;

  const triggerLabel = React.useMemo(() => {
    if (mode === 'single') {
      const found = countries.find(c => c.code === singleSelected);
      return found ? { country: found, label: found.name } : null;
    }
    if (mode === 'multi') {
      if (multiSelected.length === 0) return null;
      if (multiSelected.length === 1) {
        const found = countries.find(c => c.code === multiSelected[0]);
        return found ? { country: found, label: found.name } : null;
      }
      return { country: null, label: `${multiSelected.length} countries selected` };
    }
    return null;
  }, [mode, singleSelected, multiSelected, countries]);

  return (
    <div
      className={cx('ld-wcp-countryselectdropdown-root', className)}
      style={{ width: typeof triggerWidth === 'number' ? `${triggerWidth}px` : triggerWidth }}
      {...rest}
    >
      {label && <span className="ld-wcp-countryselectdropdown-label">{label}</span>}
      <button
        ref={triggerRef}
        type="button"
        className={cx('ld-wcp-countryselectdropdown-trigger', open && 'ld-wcp-countryselectdropdown-triggerOpen', disabled && 'ld-wcp-countryselectdropdown-triggerDisabled')}
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span className="ld-wcp-countryselectdropdown-triggerContent">
          {triggerLabel ? (
            <>
              {triggerLabel.country && (
                <img src={safeFlagUrl(triggerLabel.country.flagUrl)} alt="" className="ld-wcp-countryselectdropdown-triggerFlag" />
              )}
              {mode === 'multi' && multiSelected.length > 1 && (
                <Badge color="blue">{multiSelected.length}</Badge>
              )}
              <span className="ld-wcp-countryselectdropdown-triggerText">{triggerLabel.label}</span>
            </>
          ) : (
            <span className="ld-wcp-countryselectdropdown-triggerPlaceholder">{placeholder}</span>
          )}
        </span>
        <span className={cx('ld-wcp-countryselectdropdown-chevron', open && 'ld-wcp-countryselectdropdown-chevronOpen')}>
          <CaretDownIcon size="small" />
        </span>
      </button>

      {open && (
        <div ref={dropdownRef} className="ld-wcp-countryselectdropdown-dropdown">
          <div className="ld-wcp-countryselectdropdown-searchWrap">
            <span className="ld-wcp-countryselectdropdown-searchIcon"><SearchIcon size="small" /></span>
            <input
              ref={searchRef}
              type="text"
              className="ld-wcp-countryselectdropdown-searchInput"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button type="button" className="ld-wcp-countryselectdropdown-searchClear" onClick={() => setSearch('')} aria-label="Clear search">
                <CloseIcon size="small" />
              </button>
            )}
          </div>
          <ul className="ld-wcp-countryselectdropdown-list" role="listbox">
            {filtered.length === 0 && <li className="ld-wcp-countryselectdropdown-emptyState">No results found</li>}
            {filtered.map((country) => {
              const isSelected = mode === 'single' ? country.code === singleSelected : pendingMulti.includes(country.code);
              return (
                <li key={country.code}>
                  <button
                    type="button"
                    className={cx('ld-wcp-countryselectdropdown-row', isSelected && 'ld-wcp-countryselectdropdown-rowSelected')}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => mode === 'single' ? handleSingleSelect(country) : handleMultiToggle(country.code)}
                  >
                    <span className="ld-wcp-countryselectdropdown-selectionControl">
                      {mode === 'single' ? (
                        <svg
                          aria-hidden
                          className="ld-wcp-countryselectdropdown-radioSvg"
                          viewBox="0 0 24 24"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <circle className="ld-wcp-countryselectdropdown-radioOuter" cx="12" cy="12" r="11" />
                          <circle className="ld-wcp-countryselectdropdown-radioInner" cx="12" cy="12" r="4" />
                        </svg>
                      ) : (
                        <span className="ld-wcp-countryselectdropdown-checkboxBox">
                          <svg
                            aria-hidden
                            className="ld-wcp-countryselectdropdown-checkboxIcon"
                            viewBox="0 0 16 16"
                            xmlns="http://www.w3.org/2000/svg"
                          >
                            {isSelected && (
                              <path d="M15 3.80705L6.23047 12.6609C5.78259 13.113 5.05642 13.113 4.60854 12.6609L1 9.01759L2.72031 7.28075L5.41951 10.1053L13.2101 2L15 3.80705Z" />
                            )}
                          </svg>
                        </span>
                      )}
                    </span>
                    <img src={safeFlagUrl(country.flagUrl)} alt="" className="ld-wcp-countryselectdropdown-flag" />
                    <span className={cx('ld-wcp-countryselectdropdown-name', isSelected && 'ld-wcp-countryselectdropdown-nameSelected')}>{country.name}</span>
                    {showDialCode && <span className="ld-wcp-countryselectdropdown-dialCode">{country.dialCode}</span>}
                  </button>
                </li>
              );
            })}
          </ul>
          {mode === 'multi' && (
            <div className="ld-wcp-countryselectdropdown-footer">
              <Button variant="primary" isFullWidth onClick={handleMultiConfirm}>
                {confirmLabel}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
WCPCountrySelectDropdown.displayName = 'WCPCountrySelectDropdown';
