// @refresh reset

/**
 * @module TabNavigation
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
 * ### Content
 * 
 * Tab Navigation's accepts Tab Navigation Items through the `children` prop:
 * 
 * ```tsx
 * <TabNavigation>
 *   <TabNavigationItem href="/1/">One</TabNavigationItem>
 *   <TabNavigationItem href="/2/">Two</TabNavigationItem>
 *   <TabNavigationItem href="/3/">Three</TabNavigationItem>
 * </TabNavigation>
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps, getTarget, WithIconProps} from '../common';
import './TabNavigation.css';
// ---------------------------------------------------------------------------
// TabNavigationItem (inlined sub-component)
// ---------------------------------------------------------------------------

export interface TabNavigationItemProps
  extends Omit<React.ComponentPropsWithRef<'a'>, 'className' | 'style'> {
  /**
   * The content for the tab navigation item.
   */
  children: React.ReactNode;
  /**
   * The href for the tab navigation item.
   */
  href: string;
  /**
   * If the tab navigation item represents the current page.
   *
   * @default false
   */
  isCurrent?: boolean;
  /**
   * The leading icon for tab navigation item.
   */
  leadingIcon?: React.ReactNode;
  /**
   * The callback fired when the tab navigation item is clicked.
   */
  onClick?: (event: React.MouseEvent<HTMLAnchorElement>) => void;
  /**
   * The target for the tab navigation item.
   */
  target?: string;
  /**
   * The trailing content for the tab navigation item.
   */
  trailing?: React.ReactNode;
}

/**
 * Tab Navigation Item
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/components/tab-navigation/ Guidelines}
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/components/tab-navigation/ React documentation}
 *
 */
export const TabNavigationItem = React.forwardRef<
  HTMLAnchorElement,
  TabNavigationItemProps
>((props, ref) => {
  const {
    className,
    children,
    isCurrent = false,
    leadingIcon: initialLeadingIcon,
    target,
    trailing,
    ...rest
  } = applyCommonProps(props);

  const leadingIcon = React.isValidElement<WithIconProps>(initialLeadingIcon)
    ? React.cloneElement(initialLeadingIcon, {size: 'small'})
    : initialLeadingIcon;

  return (
    <a
      className={cx('ld-tabnavigation-tabnavigationitem-tabNavigationItem', isCurrent && 'ld-tabnavigation-tabnavigationitem-isCurrent', className)}
      ref={ref}
      {...(isCurrent && {'aria-current': 'page'})}
      {...getTarget(target)}
      {...rest}
    >
      {leadingIcon && <span className={'ld-tabnavigation-tabnavigationitem-leadingIcon'}>{leadingIcon}</span>}

      <span className={'ld-tabnavigation-tabnavigationitem-label'}>{children}</span>

      {trailing && <span className={'ld-tabnavigation-tabnavigationitem-trailing'}>{trailing}</span>}
    </a>
  );
});

TabNavigationItem.displayName = 'TabNavigationItem';

export interface TabNavigationProps
  extends Omit<React.ComponentPropsWithoutRef<'nav'>, 'className' | 'style'> {
  /**
   * The content for the tab navigation.
   */
  children: React.ReactNode;
}

/**
 * Tab Navigation allows for page-level navigation between sets of content, typically used at the top of the screen.
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/components/tab-navigation/ Guidelines}
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/components/tab-navigation/ React documentation}
 *
 */
export const TabNavigation: React.FunctionComponent<TabNavigationProps> = (
  props
) => {
  const {children, className, ...rest} = applyCommonProps(props);

  return (
    <nav className={cx('ld-tabnavigation-tabNavigation', className)} {...rest}>
      <ul className={'ld-tabnavigation-list'}>
        {React.Children.map(children, (child, index) => {
          if (!React.isValidElement(child)) {
            return null;
          }
          return (
            <li className={'ld-tabnavigation-tabNavigationItemContainer'} key={index}>
              {child}
            </li>
          );
        })}
      </ul>
    </nav>
  );
};

TabNavigation.displayName = 'TabNavigation';
