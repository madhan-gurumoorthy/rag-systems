// @refresh reset

/**
 * @module List
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
 * The List accepts List Items through the `children` prop:
 * 
 * ```tsx
 * <List>
 *   <ListItem>Dog</ListItem>
 *   <ListItem>Cat</ListItem>
 *   <ListItem>Mouse</ListItem>
 * </List>
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import {Body} from '../Text';

// ---------------------------------------------------------------------------
// ListItem (inlined sub-component)
// ---------------------------------------------------------------------------

export interface ListItemProps
  extends Omit<
      React.ComponentPropsWithoutRef<'span'>,
      'className' | 'style' | 'title'
    > {
  /**
   * The text label for the list item.
   */
  children: React.ReactNode;
  /**
   * The leading content for the list item.
   */
  leading?: React.ReactNode;
  /**
   * The title for the list item.
   */
  title?: React.ReactNode;
  /**
   * The trailing content for the list item.
   */
  trailing?: React.ReactNode;
}

/**
 * List Items
 * *
 */
export const ListItem: React.FunctionComponent<ListItemProps> = (props) => {
  const {children, className, leading, title, trailing, ...rest} = applyCommonProps(props);

  return (
    <span className={cx('ld-list-listitem-listItem', className)} {...rest}>
      {leading && <span className={'ld-list-listitem-leading'}>{leading}</span>}

      <div className={'ld-list-listitem-container'}>
        {title && (
          <Body
            UNSAFE_className={'ld-list-listitem-title'}
            size={"large"}
            weight={"alt"}
          >
            {title}
          </Body>
        )}

        <Body
          UNSAFE_className={'ld-list-listitem-textLabel'}
          size={"medium"}
        >
          {children}
        </Body>
      </div>

      {trailing && <span className={'ld-list-listitem-trailing'}>{trailing}</span>}
    </span>
  );
};

import {Divider} from '../Divider';
import './List.css';

export interface ListProps
  extends Omit<React.ComponentPropsWithoutRef<'ul'>, 'className' | 'style'> {
  /**
   * The content for the list.
   */
  children: React.ReactNode;
}

/**
 * Lists are continuous, vertical indexes of related information.
 * *
 */
export const List: React.FunctionComponent<ListProps> = (props) => {
  const {children, className, ...rest} = applyCommonProps(props);

  const validChildren = React.Children.toArray(children).filter((child) =>
    React.isValidElement(child)
  );

  const childrenCount = React.Children.count(validChildren);

  return (
    <ul className={cx('ld-list-list', className)} {...rest}>
      {React.Children.map(validChildren, (child, index) => (
        <li hidden={child.props.hidden}>
          {child}

          {index < childrenCount - 1 && (
            <div className={'ld-list-divider'}>
              <Divider />
            </div>
          )}
        </li>
      ))}
    </ul>
  );
};
