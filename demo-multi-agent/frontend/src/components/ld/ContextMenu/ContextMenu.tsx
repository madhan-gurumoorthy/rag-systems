'use client';
// @refresh reset

/**
 * @module ContextMenu
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
import {
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
} from '../DropdownMenu';
import type {
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
} from '../DropdownMenu';
import './ContextMenu.css';
import './ContextMenu.css';

/* ------------------------------------------------------------------ */
/*  ContextMenu - wraps DropdownMenu with trigger="context-menu"       */
/* ------------------------------------------------------------------ */

type ContextMenuProps = Omit<DropdownMenuProps, 'trigger'>;

function ContextMenu(props: ContextMenuProps) {
  return <DropdownMenu trigger="context-menu" {...props} />;
}

ContextMenu.displayName = 'ContextMenu';

/* ------------------------------------------------------------------ */
/*  Re-export all sub-components with ContextMenu* names               */
/* ------------------------------------------------------------------ */

const ContextMenuTrigger = React.forwardRef<
  HTMLButtonElement | HTMLDivElement,
  DropdownMenuTriggerProps
>(function ContextMenuTriggerInner(props, ref) {
  return <DropdownMenuTrigger ref={ref} {...props} />;
});
ContextMenuTrigger.displayName = 'ContextMenuTrigger';

const ContextMenuContent = React.forwardRef<HTMLDivElement, DropdownMenuContentProps>(
  function ContextMenuContentInner(props, ref) {
    return <DropdownMenuContent ref={ref} {...props} />;
  },
);
ContextMenuContent.displayName = 'ContextMenuContent';

const ContextMenuItem = React.forwardRef<HTMLDivElement, DropdownMenuItemProps>(
  function ContextMenuItemInner(props, ref) {
    return <DropdownMenuItem ref={ref} {...props} />;
  },
);
ContextMenuItem.displayName = 'ContextMenuItem';

const ContextMenuCheckboxItem = React.forwardRef<HTMLDivElement, DropdownMenuCheckboxItemProps>(
  function ContextMenuCheckboxItemInner(props, ref) {
    return <DropdownMenuCheckboxItem ref={ref} {...props} />;
  },
);
ContextMenuCheckboxItem.displayName = 'ContextMenuCheckboxItem';

const ContextMenuRadioItem = React.forwardRef<HTMLDivElement, DropdownMenuRadioItemProps>(
  function ContextMenuRadioItemInner(props, ref) {
    return <DropdownMenuRadioItem ref={ref} {...props} />;
  },
);
ContextMenuRadioItem.displayName = 'ContextMenuRadioItem';

const ContextMenuLabel = React.forwardRef<HTMLDivElement, DropdownMenuLabelProps>(
  function ContextMenuLabelInner(props, ref) {
    return <DropdownMenuLabel ref={ref} {...props} />;
  },
);
ContextMenuLabel.displayName = 'ContextMenuLabel';

const ContextMenuSeparator = React.forwardRef<
  HTMLDivElement,
  { [key: string]: unknown }
>(function ContextMenuSeparatorInner(props, ref) {
  return <DropdownMenuSeparator ref={ref} {...props} />;
});
ContextMenuSeparator.displayName = 'ContextMenuSeparator';

function ContextMenuShortcutInner(props: DropdownMenuShortcutProps) {
  return <DropdownMenuShortcut {...props} />;
}
ContextMenuShortcutInner.displayName = 'ContextMenuShortcut';
const ContextMenuShortcut = ContextMenuShortcutInner;

function ContextMenuSubInner({ children }: { children: React.ReactNode }) {
  return <DropdownMenuSub>{children}</DropdownMenuSub>;
}
ContextMenuSubInner.displayName = 'ContextMenuSub';
const ContextMenuSub = ContextMenuSubInner;

const ContextMenuSubContent = React.forwardRef<HTMLDivElement, DropdownMenuSubContentProps>(
  function ContextMenuSubContentInner(props, ref) {
    return <DropdownMenuSubContent ref={ref} {...props} />;
  },
);
ContextMenuSubContent.displayName = 'ContextMenuSubContent';

const ContextMenuSubTrigger = React.forwardRef<HTMLDivElement, DropdownMenuSubTriggerProps>(
  function ContextMenuSubTriggerInner(props, ref) {
    return <DropdownMenuSubTrigger ref={ref} {...props} />;
  },
);
ContextMenuSubTrigger.displayName = 'ContextMenuSubTrigger';

const ContextMenuRadioGroup = React.forwardRef<HTMLDivElement, DropdownMenuRadioGroupProps>(
  function ContextMenuRadioGroupInner(props, ref) {
    return <DropdownMenuRadioGroup ref={ref} {...props} />;
  },
);
ContextMenuRadioGroup.displayName = 'ContextMenuRadioGroup';

/* ------------------------------------------------------------------ */
/*  Exports                                                            */
/* ------------------------------------------------------------------ */

export {
  ContextMenu,
  ContextMenuTrigger,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuCheckboxItem,
  ContextMenuRadioItem,
  ContextMenuLabel,
  ContextMenuSeparator,
  ContextMenuShortcut,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
  ContextMenuRadioGroup,
};

export type {
  ContextMenuProps,
};
