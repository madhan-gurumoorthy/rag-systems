'use client';
// @refresh reset

/**
 * @module DropdownMenu
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
import './DropdownMenu.css';
import './DropdownMenu.css';

/* ------------------------------------------------------------------ */
/*  Inline SVG Icons                                                   */
/* ------------------------------------------------------------------ */

function CheckIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        d="M13.354 4.354l-7 7a.5.5 0 01-.708 0l-3.5-3.5.708-.708L6 10.293l6.646-6.647.708.708z"
        fill="currentColor"
      />
    </svg>
  );
}


function ChevronRightIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        fillRule="evenodd"
        d="M5.646 3.646a.5.5 0 01.708 0l4 4a.5.5 0 010 .708l-4 4a.5.5 0 01-.708-.708L9.293 8 5.646 4.354a.5.5 0 010-.708z"
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Contexts                                                           */
/* ------------------------------------------------------------------ */

interface MenuContextValue {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  triggerRef: React.RefObject<HTMLButtonElement | HTMLDivElement | null>;
  highlightedIndex: number;
  setHighlightedIndex: (i: number) => void;
  /** Whether this is a right-click context menu */
  isContextMenu: boolean;
  /** Mouse position when using context-menu trigger */
  contextPosition: { x: number; y: number };
  setContextPosition: (pos: { x: number; y: number }) => void;
}

const MenuCtx = React.createContext<MenuContextValue | null>(null);

function useMenuCtx() {
  const ctx = React.useContext(MenuCtx);
  if (!ctx) throw new Error('DropdownMenu components must be used within <DropdownMenu>');
  return ctx;
}

interface RadioGroupContextValue {
  value: string;
  onValueChange: (value: string) => void;
}

const RadioGroupCtx = React.createContext<RadioGroupContextValue | null>(null);

/* ------------------------------------------------------------------ */
/*  Root                                                               */
/* ------------------------------------------------------------------ */

interface DropdownMenuProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
  /**
   * How the menu is triggered.
   * - `'click'` (default): opens on button click
   * - `'context-menu'`: opens on right-click at the cursor position
   */
  trigger?: 'click' | 'context-menu';
}

function DropdownMenu({
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  children,
  trigger = 'click',
}: DropdownMenuProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const open = controlledOpen !== undefined ? controlledOpen : uncontrolledOpen;
  const triggerRef = React.useRef<HTMLButtonElement | HTMLDivElement | null>(null);
  const [highlightedIndex, setHighlightedIndex] = React.useState(-1);
  const [contextPosition, setContextPosition] = React.useState({ x: 0, y: 0 });

  const handleChange = React.useCallback(
    (next: boolean) => {
      if (controlledOpen === undefined) setUncontrolledOpen(next);
      onOpenChange?.(next);
      if (!next) setHighlightedIndex(-1);
    },
    [controlledOpen, onOpenChange],
  );

  return (
    <MenuCtx.Provider
      value={{
        open,
        onOpenChange: handleChange,
        triggerRef,
        highlightedIndex,
        setHighlightedIndex,
        isContextMenu: trigger === 'context-menu',
        contextPosition,
        setContextPosition,
      }}
    >
      {children}
    </MenuCtx.Provider>
  );
}

DropdownMenu.displayName = 'DropdownMenu';

/* ------------------------------------------------------------------ */
/*  Trigger                                                            */
/* ------------------------------------------------------------------ */

interface DropdownMenuTriggerProps extends CommonProps {
  children: React.ReactNode;
  asChild?: boolean;
  onClick?: (e: React.MouseEvent) => void;
}

const DropdownMenuTrigger = React.forwardRef<
  HTMLButtonElement | HTMLDivElement,
  DropdownMenuTriggerProps
>(function DropdownMenuTriggerInner(props, ref) {
  const { className, ...rest } = applyCommonProps(props);
  const { onClick, children, asChild, ...domProps } = rest;
  const { open, onOpenChange, triggerRef, isContextMenu, setContextPosition } = useMenuCtx();

  // Context-menu mode: render a div that listens for right-clicks
  if (isContextMenu) {
    const mergedContextRef = mergeRefs<HTMLDivElement>(
      triggerRef as React.MutableRefObject<HTMLDivElement | null>,
      ref as React.ForwardedRef<HTMLDivElement>,
    );

    return (
      <div
        ref={mergedContextRef}
        className={className}
        onContextMenu={(e) => {
          e.preventDefault();
          setContextPosition({ x: e.clientX, y: e.clientY });
          onOpenChange(true);
          onClick?.(e);
        }}
        {...(domProps as React.HTMLAttributes<HTMLDivElement>)}
      >
        {children}
      </div>
    );
  }

  // Click mode (default)
  const mergedClickRef = mergeRefs<HTMLButtonElement>(
    triggerRef as React.MutableRefObject<HTMLButtonElement | null>,
    ref as React.ForwardedRef<HTMLButtonElement>,
  );

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    onClick?.(e);
    onOpenChange(!open);
  };

  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children as React.ReactElement<Record<string, unknown>>, {
      ref: mergedClickRef,
      onClick: handleClick,
      'aria-expanded': open,
      'aria-haspopup': 'menu',
      'data-state': open ? 'open' : 'closed',
    });
  }

  return (
    <button
      ref={mergedClickRef}
      type="button"
      className={className}
      onClick={handleClick}
      aria-expanded={open}
      aria-haspopup="menu"
      data-state={open ? 'open' : 'closed'}
      {...(domProps as React.ButtonHTMLAttributes<HTMLButtonElement>)}
    >
      {children}
    </button>
  );
});

DropdownMenuTrigger.displayName = 'DropdownMenuTrigger';

/* ------------------------------------------------------------------ */
/*  Sub (simplified)                                                   */
/* ------------------------------------------------------------------ */

interface SubContextValue {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SubCtx = React.createContext<SubContextValue | null>(null);

function DropdownMenuSub({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  return (
    <SubCtx.Provider value={{ open, onOpenChange: setOpen }}>
      {children}
    </SubCtx.Provider>
  );
}

DropdownMenuSub.displayName = 'DropdownMenuSub';

/* ------------------------------------------------------------------ */
/*  RadioGroup                                                         */
/* ------------------------------------------------------------------ */

interface DropdownMenuRadioGroupProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  value?: string;
  onValueChange?: (value: string) => void;
  children?: React.ReactNode;
}

const DropdownMenuRadioGroup = React.forwardRef<HTMLDivElement, DropdownMenuRadioGroupProps>(
  function DropdownMenuRadioGroupInner(props, ref) {
    const { className, ...rest } = applyCommonProps(props);
    const { value = '', onValueChange, children, ...domProps } = rest;
    return (
      <RadioGroupCtx.Provider value={{ value: value ?? '', onValueChange: onValueChange || (() => {}) }}>
        <div ref={ref} role="group" className={className} {...(domProps as React.HTMLAttributes<HTMLDivElement>)}>
          {children}
        </div>
      </RadioGroupCtx.Provider>
    );
  },
);

DropdownMenuRadioGroup.displayName = 'DropdownMenuRadioGroup';

/* ------------------------------------------------------------------ */
/*  SubTrigger                                                         */
/* ------------------------------------------------------------------ */

interface DropdownMenuSubTriggerProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  inset?: boolean;
  children?: React.ReactNode;
}

const DropdownMenuSubTrigger = React.forwardRef<HTMLDivElement, DropdownMenuSubTriggerProps>(
  function DropdownMenuSubTriggerInner(props, ref) {
    const { className, ...rest } = applyCommonProps(props);
    const { inset, children, onMouseEnter, onMouseLeave, ...domProps } = rest;
    const sub = React.useContext(SubCtx);

    return (
      <div
        ref={ref}
        role="menuitem"
        aria-haspopup="menu"
        data-state={sub?.open ? 'open' : 'closed'}
        className={cx(
          'ld-dropdown-menu-sub-trigger',
          inset && 'ld-dropdown-menu-item--inset',
          className,
        )}
        onMouseEnter={(e) => {
          sub?.onOpenChange(true);
          onMouseEnter?.(e);
        }}
        onMouseLeave={(e) => {
          sub?.onOpenChange(false);
          onMouseLeave?.(e);
        }}
        {...(domProps as React.HTMLAttributes<HTMLDivElement>)}
      >
        {children}
        <ChevronRightIcon className="ld-dropdown-menu-chevron" />
      </div>
    );
  },
);

DropdownMenuSubTrigger.displayName = 'DropdownMenuSubTrigger';

/* ------------------------------------------------------------------ */
/*  SubContent                                                         */
/* ------------------------------------------------------------------ */

interface DropdownMenuSubContentProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  children?: React.ReactNode;
}

const DropdownMenuSubContent = React.forwardRef<HTMLDivElement, DropdownMenuSubContentProps>(
  function DropdownMenuSubContentInner(props, ref) {
    const { className, ...rest } = applyCommonProps(props);
    const { children, ...domProps } = rest;
    const sub = React.useContext(SubCtx);
    if (!sub?.open) return null;

    return (
      <div
        ref={ref}
        role="menu"
        data-state="open"
        className={cx('ld-dropdown-menu-content ld-dropdown-menu-sub-content', className)}
        {...(domProps as React.HTMLAttributes<HTMLDivElement>)}
      >
        {children}
      </div>
    );
  },
);

DropdownMenuSubContent.displayName = 'DropdownMenuSubContent';

/* ------------------------------------------------------------------ */
/*  Content                                                            */
/* ------------------------------------------------------------------ */

interface DropdownMenuContentProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  sideOffset?: number;
  side?: 'top' | 'bottom' | 'left' | 'right';
  align?: 'start' | 'center' | 'end';
  children?: React.ReactNode;
}

const DropdownMenuContent = React.forwardRef<HTMLDivElement, DropdownMenuContentProps>(
  function DropdownMenuContentInner(props, ref) {
    const { className, style, ...rest } = applyCommonProps(props);
    const { sideOffset = 4, side = 'bottom', align = 'start', children, ...domProps } = rest;
    const { open, onOpenChange, triggerRef, isContextMenu, contextPosition } = useMenuCtx();
    const contentRef = React.useRef<HTMLDivElement>(null);
    const [pos, setPos] = React.useState<{ top: number; left: number }>({ top: 0, left: 0 });

    const combinedRef = mergeRefs<HTMLDivElement>(contentRef, ref);

    // Position relative to trigger
    React.useEffect(() => {
      if (!open) return;

      // In context-menu mode we position at the cursor
      if (isContextMenu) return;

      if (!triggerRef.current) return;
      const rect = triggerRef.current.getBoundingClientRect();

      let top = rect.bottom + (sideOffset as number);
      let left = rect.left;

      if (side === 'top') top = rect.top - (sideOffset as number);
      if (align === 'end') left = rect.right;
      if (align === 'center') left = rect.left + rect.width / 2;

      setPos({ top, left });
    }, [open, sideOffset, side, align, triggerRef, isContextMenu]);

    // Click outside + escape
    React.useEffect(() => {
      if (!open) return;

      const handleClickOutside = (e: MouseEvent) => {
        if (
          contentRef.current &&
          !contentRef.current.contains(e.target as Node) &&
          triggerRef.current &&
          !triggerRef.current.contains(e.target as Node)
        ) {
          onOpenChange(false);
        }
      };

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          e.preventDefault();
          onOpenChange(false);
          (triggerRef.current as HTMLElement)?.focus();
        }
      };

      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
        document.removeEventListener('keydown', handleKeyDown);
      };
    }, [open, onOpenChange, triggerRef]);

    // Keyboard navigation
    React.useEffect(() => {
      if (!open || !contentRef.current) return;

      const el = contentRef.current;
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault();
          const items = el.querySelectorAll<HTMLElement>(
            '[role="menuitem"]:not([data-disabled]),[role="menuitemcheckbox"]:not([data-disabled]),[role="menuitemradio"]:not([data-disabled])',
          );
          if (!items || items.length === 0) return;

          const current = Array.from(items).findIndex((item) => item === document.activeElement);
          let next: number;

          if (e.key === 'ArrowDown') {
            next = current < items.length - 1 ? current + 1 : 0;
          } else {
            next = current > 0 ? current - 1 : items.length - 1;
          }

          items[next].focus();
        }
      };

      el.addEventListener('keydown', handleKeyDown);
      return () => el.removeEventListener('keydown', handleKeyDown);
    }, [open]);

    if (!open) return null;

    // In context-menu mode, position at the cursor rather than the trigger button
    const contentPos = isContextMenu
      ? { top: contextPosition.y, left: contextPosition.x }
      : pos;

    return (
      <div
        ref={combinedRef}
        role="menu"
        data-state="open"
        className={cx('ld-dropdown-menu-content', className)}
        style={{
          position: 'fixed',
          top: contentPos.top,
          left: contentPos.left,
          zIndex: 50,
          ...(style as React.CSSProperties),
        }}
        {...(domProps as React.HTMLAttributes<HTMLDivElement>)}
      >
        {children}
      </div>
    );
  },
);

DropdownMenuContent.displayName = 'DropdownMenuContent';

/* ------------------------------------------------------------------ */
/*  Item                                                               */
/* ------------------------------------------------------------------ */

interface DropdownMenuItemProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  inset?: boolean;
  disabled?: boolean;
  onSelect?: () => void;
  children?: React.ReactNode;
}

const DropdownMenuItem = React.forwardRef<HTMLDivElement, DropdownMenuItemProps>(
  function DropdownMenuItemInner(props, ref) {
    const { className, ...rest } = applyCommonProps(props);
    const { inset, disabled, onSelect, onClick, children, ...domProps } = rest;
    const { onOpenChange } = useMenuCtx();

    return (
      <div
        ref={ref}
        role="menuitem"
        tabIndex={disabled ? undefined : -1}
        data-disabled={disabled || undefined}
        className={cx(
          'ld-dropdown-menu-item',
          inset && 'ld-dropdown-menu-item--inset',
          className,
        )}
        onClick={(e) => {
          if (disabled) return;
          onClick?.(e);
          onSelect?.();
          onOpenChange(false);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (!disabled) {
              onSelect?.();
              onOpenChange(false);
            }
          }
        }}
        {...(domProps as React.HTMLAttributes<HTMLDivElement>)}
      >
        {children}
      </div>
    );
  },
);

DropdownMenuItem.displayName = 'DropdownMenuItem';

/* ------------------------------------------------------------------ */
/*  CheckboxItem                                                       */
/* ------------------------------------------------------------------ */

interface DropdownMenuCheckboxItemProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  children?: React.ReactNode;
}

const DropdownMenuCheckboxItem = React.forwardRef<HTMLDivElement, DropdownMenuCheckboxItemProps>(
  function DropdownMenuCheckboxItemInner(props, ref) {
    const { className, ...rest } = applyCommonProps(props);
    const { children, checked, onCheckedChange, disabled, onClick, ...domProps } = rest;
    const { onOpenChange } = useMenuCtx();

    return (
      <div
        ref={ref}
        role="menuitemcheckbox"
        aria-checked={checked}
        tabIndex={disabled ? undefined : -1}
        data-disabled={disabled || undefined}
        data-state={checked ? 'checked' : 'unchecked'}
        className={cx('ld-dropdown-menu-item-with-indicator', className)}
        onClick={(e) => {
          if (disabled) return;
          onClick?.(e);
          onCheckedChange?.(!checked);
          onOpenChange(false);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (!disabled) {
              onCheckedChange?.(!checked);
              onOpenChange(false);
            }
          }
        }}
        {...(domProps as React.HTMLAttributes<HTMLDivElement>)}
      >
        <span className="ld-dropdown-menu-indicator">
          {checked && <CheckIcon />}
        </span>
        {children}
      </div>
    );
  },
);

DropdownMenuCheckboxItem.displayName = 'DropdownMenuCheckboxItem';

/* ------------------------------------------------------------------ */
/*  RadioItem                                                          */
/* ------------------------------------------------------------------ */

interface DropdownMenuRadioItemProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  value: string;
  disabled?: boolean;
  children?: React.ReactNode;
}

const DropdownMenuRadioItem = React.forwardRef<HTMLDivElement, DropdownMenuRadioItemProps>(
  function DropdownMenuRadioItemInner(props, ref) {
    const { className, ...rest } = applyCommonProps(props);
    const { children, value, disabled, onClick, ...domProps } = rest;
    const { onOpenChange } = useMenuCtx();
    const radioGroup = React.useContext(RadioGroupCtx);
    const checked = radioGroup?.value === value;

    return (
      <div
        ref={ref}
        role="menuitemradio"
        aria-checked={checked}
        tabIndex={disabled ? undefined : -1}
        data-disabled={disabled || undefined}
        data-state={checked ? 'checked' : 'unchecked'}
        className={cx('ld-dropdown-menu-item-with-indicator', className)}
        onClick={(e) => {
          if (disabled) return;
          onClick?.(e);
          radioGroup?.onValueChange(value);
          onOpenChange(false);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (!disabled) {
              radioGroup?.onValueChange(value);
              onOpenChange(false);
            }
          }
        }}
        {...(domProps as React.HTMLAttributes<HTMLDivElement>)}
      >
        <span className="ld-dropdown-menu-indicator">
          {checked && <span className="ld-dropdown-menu-radio-dot" />}
        </span>
        {children}
      </div>
    );
  },
);

DropdownMenuRadioItem.displayName = 'DropdownMenuRadioItem';

/* ------------------------------------------------------------------ */
/*  Label                                                              */
/* ------------------------------------------------------------------ */

interface DropdownMenuLabelProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'>,
    CommonProps {
  inset?: boolean;
  children?: React.ReactNode;
}

const DropdownMenuLabel = React.forwardRef<HTMLDivElement, DropdownMenuLabelProps>(
  function DropdownMenuLabelInner(props, ref) {
    const { className, ...rest } = applyCommonProps(props);
    const { inset, children, ...domProps } = rest;

    return (
      <div
        ref={ref}
        className={cx(
          'ld-dropdown-menu-label',
          inset && 'ld-dropdown-menu-label--inset',
          className,
        )}
        {...(domProps as React.HTMLAttributes<HTMLDivElement>)}
      >
        {children}
      </div>
    );
  },
);

DropdownMenuLabel.displayName = 'DropdownMenuLabel';

/* ------------------------------------------------------------------ */
/*  Separator                                                          */
/* ------------------------------------------------------------------ */

const DropdownMenuSeparator = React.forwardRef<
  HTMLDivElement,
  Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> & CommonProps
>(function DropdownMenuSeparatorInner(props, ref) {
  const { className, ...rest } = applyCommonProps(props);
  return (
    <div
      ref={ref}
      role="separator"
      className={cx('ld-dropdown-menu-separator', className)}
      {...(rest as React.HTMLAttributes<HTMLDivElement>)}
    />
  );
});

DropdownMenuSeparator.displayName = 'DropdownMenuSeparator';

/* ------------------------------------------------------------------ */
/*  Shortcut                                                           */
/* ------------------------------------------------------------------ */

interface DropdownMenuShortcutProps
  extends Omit<React.ComponentPropsWithoutRef<'span'>, 'className' | 'style'>,
    CommonProps {
  children?: React.ReactNode;
}

function DropdownMenuShortcut(props: DropdownMenuShortcutProps) {
  const { className, ...rest } = applyCommonProps(props);
  const { children, ...domProps } = rest;
  return (
    <span className={cx('ld-dropdown-menu-shortcut', className)} {...(domProps as React.HTMLAttributes<HTMLSpanElement>)}>
      {children}
    </span>
  );
}

DropdownMenuShortcut.displayName = 'DropdownMenuShortcut';

/* ------------------------------------------------------------------ */
/*  Exports                                                            */
/* ------------------------------------------------------------------ */

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuRadioGroup,
};

export type {
  DropdownMenuProps,
  DropdownMenuContentProps,
  DropdownMenuItemProps,
  DropdownMenuCheckboxItemProps,
  DropdownMenuRadioItemProps,
  DropdownMenuRadioGroupProps,
  DropdownMenuLabelProps,
  DropdownMenuSubTriggerProps,
  DropdownMenuSubContentProps,
  DropdownMenuTriggerProps,
  DropdownMenuShortcutProps,
};
