'use client';
// @refresh reset

/**
 * @module Command
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
import {cx, applyCommonProps, useStableId, mergeRefs} from '../common';
import type {CommonProps} from '../common';

import './Command.css';
import './Command.css';

// ---------------------------------------------------------------------------
// Search Icon (inline SVG)
// ---------------------------------------------------------------------------

function SearchIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Command Context
// ---------------------------------------------------------------------------

interface CommandContextValue {
  search: string;
  setSearch: (value: string) => void;
  selectedIndex: number;
  setSelectedIndex: React.Dispatch<React.SetStateAction<number>>;
  visibleItems: React.MutableRefObject<Array<{value: string; onSelect?: () => void; disabled?: boolean}>>;
  registerItem: (value: string, onSelect?: () => void, disabled?: boolean) => () => void;
}

const CommandContext = React.createContext<CommandContextValue>({
  search: '',
  setSearch: () => {},
  selectedIndex: 0,
  setSelectedIndex: () => {},
  visibleItems: {current: []},
  registerItem: () => () => {},
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function matchesSearch(text: string, search: string): boolean {
  if (!search) return true;
  return text.toLowerCase().includes(search.toLowerCase());
}

// ---------------------------------------------------------------------------
// Command (root)
// ---------------------------------------------------------------------------

export interface CommandProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style' | 'onSelect'>,
    CommonProps {
  children: React.ReactNode;
  /** Optional callback when an item is selected */
  onSelect?: (value: string) => void;
}

export const Command = React.forwardRef<HTMLDivElement, CommandProps>(
  (props, ref) => {
    const {children, onSelect, UNSAFE_className, UNSAFE_style, ...rest} = props;
    const [search, setSearch] = React.useState('');
    const [selectedIndex, setSelectedIndex] = React.useState(0);
    const visibleItems = React.useRef<Array<{value: string; onSelect?: () => void; disabled?: boolean}>>([]);
    const rootRef = React.useRef<HTMLDivElement>(null);

    const registerItem = React.useCallback(
      (value: string, onSelectCb?: () => void, disabled?: boolean) => {
        const item = {value, onSelect: onSelectCb, disabled};
        visibleItems.current.push(item);
        return () => {
          visibleItems.current = visibleItems.current.filter((i) => i !== item);
        };
      },
      [],
    );

    // Reset selection when search changes
    React.useEffect(() => {
      setSelectedIndex(0);
    }, [search]);

    const handleKeyDown = React.useCallback(
      (e: React.KeyboardEvent<HTMLDivElement>) => {
        const items = visibleItems.current.filter((i) => !i.disabled);
        if (items.length === 0) return;

        switch (e.key) {
          case 'ArrowDown': {
            e.preventDefault();
            setSelectedIndex((prev) => {
              const next = prev + 1;
              return next >= items.length ? 0 : next;
            });
            break;
          }
          case 'ArrowUp': {
            e.preventDefault();
            setSelectedIndex((prev) => {
              const next = prev - 1;
              return next < 0 ? items.length - 1 : next;
            });
            break;
          }
          case 'Enter': {
            e.preventDefault();
            const selected = items[selectedIndex];
            if (selected) {
              selected.onSelect?.();
              onSelect?.(selected.value);
            }
            break;
          }
          case 'Home': {
            e.preventDefault();
            setSelectedIndex(0);
            break;
          }
          case 'End': {
            e.preventDefault();
            setSelectedIndex(items.length - 1);
            break;
          }
          default:
            break;
        }
      },
      [selectedIndex, onSelect],
    );

    const ctx = React.useMemo(
      () => ({search, setSearch, selectedIndex, setSelectedIndex, visibleItems, registerItem}),
      [search, selectedIndex, registerItem],
    );

    return (
      <CommandContext.Provider value={ctx}>
        <div
          ref={mergeRefs(rootRef, ref)}
          className={cx('ld-command-root', UNSAFE_className)}
          style={UNSAFE_style}
          onKeyDown={handleKeyDown}
          {...rest}
        >
          {children}
        </div>
      </CommandContext.Provider>
    );
  },
);
Command.displayName = 'Command';

// ---------------------------------------------------------------------------
// CommandInput
// ---------------------------------------------------------------------------

export interface CommandInputProps
  extends Omit<React.ComponentPropsWithoutRef<'input'>, 'className' | 'style' | 'value' | 'onChange'>,
    CommonProps {
}

export const CommandInput = React.forwardRef<HTMLInputElement, CommandInputProps>(
  (props, ref) => {
    const {UNSAFE_className, UNSAFE_style, ...rest} = props;
    const {search, setSearch} = React.useContext(CommandContext);

    return (
      <div className="ld-command-input-wrapper">
        <SearchIcon className="ld-command-search-icon" />
        <input
          ref={ref}
          className={cx('ld-command-input', UNSAFE_className)}
          style={UNSAFE_style}
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          {...rest}
        />
      </div>
    );
  },
);
CommandInput.displayName = 'CommandInput';

// ---------------------------------------------------------------------------
// CommandList
// ---------------------------------------------------------------------------

export interface CommandListProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  children: React.ReactNode;
}

export const CommandList = React.forwardRef<HTMLDivElement, CommandListProps>(
  (props, ref) => {
    const {children, UNSAFE_className, UNSAFE_style, ...rest} = props;

    return (
      <div
        ref={ref}
        className={cx('ld-command-list', UNSAFE_className)}
        style={UNSAFE_style}
        role="listbox"
        {...rest}
      >
        {children}
      </div>
    );
  },
);
CommandList.displayName = 'CommandList';

// ---------------------------------------------------------------------------
// CommandEmpty
// ---------------------------------------------------------------------------

export interface CommandEmptyProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  children: React.ReactNode;
}

export const CommandEmpty = React.forwardRef<HTMLDivElement, CommandEmptyProps>(
  (props, ref) => {
    const {children, UNSAFE_className, UNSAFE_style, ...rest} = props;
    const {visibleItems} = React.useContext(CommandContext);
    const [hasItems, setHasItems] = React.useState(true);

    // We use a layout effect to check after children have registered
    React.useEffect(() => {
      // Tiny delay to let items register/unregister
      const timer = setTimeout(() => {
        setHasItems(visibleItems.current.length > 0);
      }, 0);
      return () => clearTimeout(timer);
    });

    if (hasItems) return null;

    return (
      <div
        ref={ref}
        className={cx('ld-command-empty', UNSAFE_className)}
        style={UNSAFE_style}
        {...rest}
      >
        {children}
      </div>
    );
  },
);
CommandEmpty.displayName = 'CommandEmpty';

// ---------------------------------------------------------------------------
// CommandGroup
// ---------------------------------------------------------------------------

export interface CommandGroupProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  children: React.ReactNode;
  heading?: string;
}

export const CommandGroup = React.forwardRef<HTMLDivElement, CommandGroupProps>(
  (props, ref) => {
    const {children, heading, UNSAFE_className, UNSAFE_style, ...rest} = props;
    const headingId = useStableId();

    return (
      <div
        ref={ref}
        className={cx('ld-command-group', UNSAFE_className)}
        style={UNSAFE_style}
        role="group"
        aria-labelledby={heading ? headingId : undefined}
        {...rest}
      >
        {heading && (
          <div className="ld-command-group-heading" id={headingId}>
            {heading}
          </div>
        )}
        {children}
      </div>
    );
  },
);
CommandGroup.displayName = 'CommandGroup';

// ---------------------------------------------------------------------------
// CommandItem
// ---------------------------------------------------------------------------

export interface CommandItemProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style' | 'onSelect'>,
    CommonProps {
  children: React.ReactNode;
  /** The value used for filtering and selection. Defaults to text content. */
  value?: string;
  disabled?: boolean;
  onSelect?: () => void;
}

export const CommandItem = React.forwardRef<HTMLDivElement, CommandItemProps>(
  (props, ref) => {
    const {children, value, disabled = false, onSelect, UNSAFE_className, UNSAFE_style, ...rest} = props;
    const {search, selectedIndex, visibleItems, registerItem} = React.useContext(CommandContext);
    const itemRef = React.useRef<HTMLDivElement>(null);

    // Derive text value from children if not provided
    const textValue = React.useMemo(() => {
      if (value) return value;
      // Try to extract text from children
      const extractText = (node: React.ReactNode): string => {
        if (typeof node === 'string') return node;
        if (typeof node === 'number') return String(node);
        if (Array.isArray(node)) return node.map(extractText).join('');
        if (React.isValidElement(node) && node.props.children) {
          return extractText(node.props.children);
        }
        return '';
      };
      return extractText(children);
    }, [value, children]);

    const isVisible = matchesSearch(textValue, search);

    React.useEffect(() => {
      if (!isVisible) return;
      return registerItem(textValue, onSelect, disabled);
    }, [isVisible, textValue, onSelect, disabled, registerItem]);

    // Determine if this item is selected
    const currentIndex = React.useMemo(() => {
      if (!isVisible) return -1;
      const enabledItems = visibleItems.current.filter((i) => !i.disabled);
      return enabledItems.findIndex((i) => i.value === textValue);
    }, [isVisible, textValue, visibleItems, selectedIndex]); // eslint-disable-line react-hooks/exhaustive-deps

    const isSelected = currentIndex === selectedIndex;

    // Scroll into view when selected
    React.useEffect(() => {
      if (isSelected && itemRef.current) {
        itemRef.current.scrollIntoView({block: 'nearest'});
      }
    }, [isSelected]);

    if (!isVisible) return null;

    return (
      <div
        ref={mergeRefs(itemRef, ref)}
        className={cx('ld-command-item', UNSAFE_className)}
        style={UNSAFE_style}
        role="option"
        aria-selected={isSelected}
        aria-disabled={disabled}
        data-selected={isSelected ? 'true' : 'false'}
        data-disabled={disabled ? 'true' : 'false'}
        onClick={() => {
          if (!disabled) {
            onSelect?.();
          }
        }}
        {...rest}
      >
        {children}
      </div>
    );
  },
);
CommandItem.displayName = 'CommandItem';

// ---------------------------------------------------------------------------
// CommandSeparator
// ---------------------------------------------------------------------------

export interface CommandSeparatorProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
}

export const CommandSeparator = React.forwardRef<HTMLDivElement, CommandSeparatorProps>(
  (props, ref) => {
    const {UNSAFE_className, UNSAFE_style, ...rest} = props;

    return (
      <div
        ref={ref}
        className={cx('ld-command-separator', UNSAFE_className)}
        style={UNSAFE_style}
        role="separator"
        {...rest}
      />
    );
  },
);
CommandSeparator.displayName = 'CommandSeparator';

// ---------------------------------------------------------------------------
// CommandShortcut
// ---------------------------------------------------------------------------

export interface CommandShortcutProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, 'className' | 'style'>,
    CommonProps {
}

export const CommandShortcut: React.FunctionComponent<CommandShortcutProps> = (props) => {
  const {UNSAFE_className, UNSAFE_style, ...rest} = props;

  return (
    <span
      className={cx('ld-command-shortcut', UNSAFE_className)}
      style={UNSAFE_style}
      {...rest}
    />
  );
};
CommandShortcut.displayName = 'CommandShortcut';

// ---------------------------------------------------------------------------
// CommandDialog
// ---------------------------------------------------------------------------

export interface CommandDialogProps extends CommonProps {
  children: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export const CommandDialog: React.FunctionComponent<CommandDialogProps> = (props) => {
  const {children, open = false, onOpenChange, UNSAFE_className, UNSAFE_style} = props;
  const overlayRef = React.useRef<HTMLDivElement>(null);

  // Close on Escape
  React.useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onOpenChange?.(false);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onOpenChange]);

  // Lock body scroll
  React.useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Close on overlay click
  const handleOverlayClick = React.useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === overlayRef.current) {
        onOpenChange?.(false);
      }
    },
    [onOpenChange],
  );

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="ld-command-overlay"
      onClick={handleOverlayClick}
    >
      <div className={cx('ld-command-dialog', UNSAFE_className)} style={UNSAFE_style}>
        <Command>{children}</Command>
      </div>
    </div>
  );
};
CommandDialog.displayName = 'CommandDialog';
