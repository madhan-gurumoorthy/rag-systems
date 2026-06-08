'use client';
// @refresh reset

/**
 * @module Menu
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
 * 
 * ## Implementation
 * 
 * ### Accessibility
 * 
 * The `Menu` must be configured as follows to work properly and meet accessibility requirements:
 * 
 * - Must provide menu items to `children`
 * - Must provide a single, button-like element to `trigger`
 * - Must provide the trigger element's `ref` to `triggerRef`
 * - Must provide `isOpen` and manage its state with `onClose` and `onOpen` handlers
 * 
 * ```tsx
 * import * as React from 'react';
 * import * as Icon from '@livingdesign/icons';
 * import {IconButton, Menu, MenuItem} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [isOpen, setIsOpen] = React.useState(false);
 *   const triggerRef = React.useRef<HTMLElement>();
 * 
 *   return (
 *     <Menu
 *       isOpen={isOpen}
 *       onClose={() => setIsOpen(false)}
 *       onOpen={() => setIsOpen(true)}
 *       trigger={
 *         <IconButton a11yLabel="Options" ref={triggerRef}>
 *           <Icon.More />
 *         </IconButton>
 *       }
 *       triggerRef={triggerRef}
 *     >
 *       <MenuItem>One</MenuItem>
 *       <MenuItem>Two</MenuItem>
 *       <MenuItem>Three</MenuItem>
 *     </Menu>
 *   );
 * };
 * ```
 * 
 * ### Interaction
 * 
 * Pass an `onClick` handler to `MenuItem` to handle selection.
 * 
 * ```tsx
 * <Menu
 * // ...
 * >
 *   <MenuItem onClick={() => console.log("Menu item 'One' selected")}>
 *     One
 *   </MenuItem>
 * </Menu>
 * ```
 */
import * as React from 'react';
import {cx, useStableId, applyCommonProps, CalculatePositionFn, CSSTransition, WithIconProps} from '../common';
// ---------------------------------------------------------------------------
// Menu.service (inlined sub-component)
// ---------------------------------------------------------------------------

export type MenuPosition =
  | 'bottomLeft'
  | 'bottomRight'
  | 'topLeft'
  | 'topRight';

export const useMenuCalculatePosition = (position: MenuPosition) =>
  React.useCallback<CalculatePositionFn>(
    ({referrerHeight, referrerWidth, targetHeight, targetWidth}) => ({
      left:
        position === 'bottomRight' || position === 'topRight'
          ? targetWidth - referrerWidth
          : 0,
      top:
        position === 'topLeft' || position === 'topRight'
          ? -1 * referrerHeight
          : targetHeight,
    }),
    [position]
  );

// ---------------------------------------------------------------------------
// MenuContainer (inlined sub-component)
// ---------------------------------------------------------------------------

export interface MenuContainerProps
  extends React.ComponentPropsWithoutRef<'div'> {
  /**
   * The content for the menu container.
   */
  children: React.ReactNode;
}

/**
 * @private
 */
export const MenuContainer = React.forwardRef<
  HTMLDivElement,
  MenuContainerProps
>((props, ref) => {
  const {className, ...rest} = props;

  return (
    <div
      className={cx('ld-menu-menucontainer-container', className)}
      ref={ref}
      role="menu"
      {...rest}
    />
  );
});

// ---------------------------------------------------------------------------
// MenuItem (inlined sub-component)
// ---------------------------------------------------------------------------

export interface MenuItemProps
  extends Omit<React.ComponentPropsWithoutRef<'button'>, 'className' | 'style'> {
  /**
   * The text label for the menu item.
   */
  children: React.ReactNode;
  /**
   * If the menu item is disabled.
   *
   * @default false
   */
  disabled?: boolean;
  /**
   * The leading icon for the menu item.
   */
  leadingIcon?: React.ReactNode;
}

/**
 * Menu Item
 * *
 */
export const MenuItem = React.forwardRef<HTMLButtonElement, MenuItemProps>(
  (props, ref) => {
    const {children, className, disabled, leadingIcon, ...rest} = applyCommonProps(props);

    return (
      <button
        className={cx('ld-menu-menuitem-menuItem', className)}
        disabled={disabled}
        ref={ref}
        role="menuitem"
        type="button"
        {...rest}
      >
        {leadingIcon && (
          <span className={'ld-menu-menuitem-leadingIcon'}>
            {React.isValidElement<WithIconProps>(leadingIcon)
              ? React.cloneElement(leadingIcon, {
                  size: "small",
                })
              : leadingIcon}
          </span>
        )}

        {children}
      </button>
    );
  }
);

MenuItem.displayName = 'MenuItem';

// ---------------------------------------------------------------------------
// MenuLayoutContainer (inlined sub-component)
// ---------------------------------------------------------------------------

export interface MenuLayoutContainerProps
  extends React.ComponentPropsWithoutRef<'div'> {
  /**
   * The content for the menu layout container.
   */
  children: React.ReactNode;
  /**
   * The callback fired when the menu layout container requests to close.
   */
  onClose: (event: MouseEvent | PointerEvent | TouchEvent) => void;
  /**
   * The position for the menu layout container.
   */
  position: MenuPosition;
}

/**
 * @private
 */
export const MenuLayoutContainer: React.FunctionComponent<
  MenuLayoutContainerProps
> = (props) => {
  const {className, onClose, position, ...rest} = props;

  return (
    <div
      className={cx(position === 'bottomLeft' && 'ld-menu-menulayoutcontainer-bottomLeft', position === 'bottomRight' && 'ld-menu-menulayoutcontainer-bottomRight', position === 'topLeft' && 'ld-menu-menulayoutcontainer-topLeft', position === 'topRight' && 'ld-menu-menulayoutcontainer-topRight', className)}
      {...rest}
    />
  );
};

// TODO: 'CSSTransition' from 'react-transition-group' needs a portable replacement
import {LayoutContainer} from '../LayoutContainer';
import './Menu.css';

// Inlined from hooks to avoid transitive @livingdesign/tokens dependency
const useOnClick = (
  onClick: (event: PointerEvent | MouseEvent | TouchEvent) => void,
  dependencies: ReadonlyArray<unknown> = [],
  useCapture = false
) =>
  React.useEffect(() => {
    if (window.PointerEvent) {
      document.addEventListener('pointerdown', onClick, useCapture);
    } else {
      document.addEventListener('mousedown', onClick, useCapture);
      document.addEventListener('touchstart', onClick, useCapture);
    }
    return () => {
      if (window.PointerEvent) {
        document.removeEventListener('pointerdown', onClick, useCapture);
      } else {
        document.removeEventListener('mousedown', onClick, useCapture);
        document.removeEventListener('touchstart', onClick, useCapture);
      }
    };
  }, [onClick, ...dependencies, useCapture]);

const useOnClickOutside = (
  ref: React.RefObject<HTMLElement> | React.RefObject<HTMLElement>[],
  onClick: (event: PointerEvent | MouseEvent | TouchEvent) => void,
  useCapture = false
) => {
  const listener = (event: PointerEvent | MouseEvent | TouchEvent) => {
    const elementRef = Array.isArray(ref) ? ref : [ref];
    if (
      elementRef.some((ref2) => ref2.current?.contains(event.target as Node))
    ) {
      return;
    }
    onClick(event);
  };
  useOnClick(listener, [ref, listener], useCapture);
};

const useMenuFocus = (
  children: React.ReactNode,
  isOpen: boolean,
  menuRef: React.RefObject<HTMLElement>,
  triggerRef: React.RefObject<HTMLElement>
) => {
  const [focusedItemIndex, setFocusedItemIndex] = React.useState(0);
  const previousFocusedItemIndex = React.useRef(focusedItemIndex);
  const previousIsOpen = React.useRef(isOpen);
  const lastIndex = React.Children.count(children) - 1;

  React.useEffect(() => {
    if (isOpen === previousIsOpen.current) {
      return;
    }
    previousIsOpen.current = isOpen;

    if (isOpen && focusedItemIndex !== -1) {
      const child = menuRef.current?.children[focusedItemIndex] as HTMLElement | undefined;
      child?.focus();
    } else {
      triggerRef.current?.focus();
    }
  }, [focusedItemIndex, isOpen, menuRef, previousIsOpen, triggerRef]);

  React.useEffect(() => {
    if (!isOpen || focusedItemIndex === previousFocusedItemIndex.current) {
      return;
    }
    previousFocusedItemIndex.current = focusedItemIndex;
    const child = menuRef.current?.children[focusedItemIndex] as HTMLElement | undefined;
    child?.focus();
  }, [focusedItemIndex, isOpen, menuRef, previousFocusedItemIndex]);

  const focusNoItem = React.useCallback(() => setFocusedItemIndex(-1), []);
  const focusFirstItem = React.useCallback(() => setFocusedItemIndex(0), []);
  const focusLastItem = React.useCallback(() => setFocusedItemIndex(lastIndex), [lastIndex]);
  const focusNextItem = React.useCallback(() => {
    setFocusedItemIndex((index) => (index + 1 > lastIndex ? 0 : index + 1));
  }, [lastIndex]);
  const focusPreviousItem = React.useCallback(() => {
    setFocusedItemIndex((index) => (index - 1 < 0 ? lastIndex : index - 1));
  }, [lastIndex]);

  const menuFocus = React.useRef({
    focusFirstItem,
    focusedItemIndex,
    focusLastItem,
    focusNextItem,
    focusPreviousItem,
    focusNoItem,
  });

  return menuFocus.current;
};

// MenuPosition is already exported above

export interface MenuProps
  extends Omit<React.ComponentPropsWithoutRef<'span'>, 'className' | 'style'> {
  /**
   * The content for the menu.
   */
  children: React.ReactNode;
  /**
   * If the menu is open.
   *
   * @default false
   */
  isOpen?: boolean;
  /**
   * The callback fired when the menu requests to close.
   */
  onClose: (
    event:
      | React.KeyboardEvent<HTMLElement>
      | React.MouseEvent<HTMLElement>
      | MouseEvent
      | PointerEvent
      | TouchEvent
  ) => void;
  /**
   * The callback fired when the menu requests to open.
   */
  onOpen: (
    event: React.KeyboardEvent<HTMLElement> | React.MouseEvent<HTMLElement>
  ) => void;
  /**
   * The position for the menu.
   *
   * @default "bottomLeft"
   */
  position?: MenuPosition;
  /**
   * The trigger for the menu.
   */
  trigger: React.ReactElement;
  /**
   * The trigger ref for the menu.
   */
  triggerRef: React.RefObject<HTMLElement>;
}

/**
 * Menus are containers with items for user-triggered actions.
 * *
 */
export const Menu: React.FunctionComponent<MenuProps> = (props) => {
  const {
    children,
    className,
    isOpen = false,
    onClose,
    onKeyDown,
    onOpen,
    position = 'bottomLeft',
    trigger,
    triggerRef,
    ...rest
  } = applyCommonProps(props);

  const calculatePosition = useMenuCalculatePosition(position);

  const menuContainerRef = React.useRef<HTMLDivElement>(null);
  const menuId = useStableId();
  const triggerId = useStableId(trigger.props.id);

  useOnClickOutside([menuContainerRef, triggerRef], onClose);

  const menuFocus = useMenuFocus(
    children,
    isOpen,
    menuContainerRef,
    triggerRef
  );

  return (
    <LayoutContainer
      calculatePosition={calculatePosition}
      className={cx(position === 'bottomLeft' && 'ld-menu-bottomLeft', position === 'bottomRight' && 'ld-menu-bottomRight', position === 'topLeft' && 'ld-menu-topLeft', position === 'topRight' && 'ld-menu-topRight')}
      content={
        <CSSTransition
          classNames={{
            enter: 'ld-menu-enter',
            enterActive: 'ld-menu-enterActive',
            exit: 'ld-menu-exit',
            exitActive: 'ld-menu-exitActive',
          }}
          in={isOpen}
          mountOnEnter
          nodeRef={menuContainerRef}
          timeout={100}
          unmountOnExit
        >
          <MenuLayoutContainer onClose={onClose} position={position}>
            <MenuContainer
              aria-labelledby={triggerId}
              id={menuId}
              onKeyDown={(event) => {
                const {key} = event;

                if (key === 'ArrowDown') {
                  event.preventDefault();
                  menuFocus.focusNextItem();
                } else if (key === 'ArrowUp') {
                  event.preventDefault();
                  menuFocus.focusPreviousItem();
                } else if (key === 'End') {
                  event.preventDefault();
                  menuFocus.focusLastItem();
                } else if (key === 'Home') {
                  event.preventDefault();
                  menuFocus.focusFirstItem();
                }
              }}
              ref={menuContainerRef}
            >
              {React.Children.map(children, (child, index) => {
                if (
                  !React.isValidElement<React.HTMLAttributes<HTMLElement>>(
                    child
                  )
                ) {
                  return child;
                }

                return React.cloneElement(child, {
                  key: index,
                  onClick(event: React.MouseEvent<HTMLElement>) {
                    child.props.onClick?.(event);

                    onClose(event);
                  },
                  tabIndex:
                    index === menuFocus.focusedItemIndex ? undefined : -1,
                });
              })}
            </MenuContainer>
          </MenuLayoutContainer>
        </CSSTransition>
      }
      onKeyDown={(event) => {
        onKeyDown?.(event);

        if (isOpen && event.key === 'Escape') {
          onClose(event);
        }
      }}
      trigger={React.cloneElement(trigger, {
        'aria-controls': menuId,
        'aria-expanded': isOpen,
        'aria-haspopup': true,
        id: triggerId,
        onClick(event: React.MouseEvent<HTMLElement>) {
          if (isOpen) {
            onClose(event);

            return;
          }

          menuFocus.focusNoItem();

          trigger.props.onClick?.(event);

          onOpen(event);
        },
        onKeyDown(event: React.KeyboardEvent<HTMLElement>) {
          trigger.props.onKeyDown?.(event);

          const {key} = event;

          if (
            key === 'ArrowDown' ||
            key === 'Enter' ||
            key === ' ' ||
            (isOpen && key === 'Home')
          ) {
            event.preventDefault();
            onOpen(event);

            menuFocus.focusFirstItem();
          } else if (key === 'ArrowUp' || (isOpen && key === 'End')) {
            event.preventDefault();
            onOpen(event);

            menuFocus.focusLastItem();
          }
        },
      })}
      triggerRef={triggerRef}
      {...rest}
    />
  );
};

Menu.displayName = 'Menu';
