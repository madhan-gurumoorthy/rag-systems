'use client';
// @refresh reset

/**
 * @module Card
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
 * The Card includes several sub-components that manage the hierarchy and layout of the contained content.
 * 
 * Sub-components:
 * 
 * 1. Card Actions (optional)
 * 1. Card Content (required)
 * 1. Card Header (optional)
 * 1. Card Media (optional)
 * 
 * ### Features
 * 
 * #### Size
 * 
 * The Card comes in two sizes:
 * 
 * - `small` (default)
 * - `large`
 * 
 * Set the Card's size with the `size` prop:
 * 
 * ```tsx
 * <Card size="small">{...}</Card>
 * <Card size="large">{...}</Card>
 * ```
 * 
 * ### Example
 * 
 * ```tsx
 * import * as React from 'react';
 * import {
 *   Button,
 *   ButtonGroup,
 *   Card,
 *   CardActions,
 *   CardContent,
 *   CardHeader,
 *   CardMedia,
 * } from '@livingdesign/react';
 * import * as Icon from '@livingdesign/icons';
 * 
 * export default () => {
 *   return (
 *     <Card size="small">
 *       <React.Fragment>
 *         <CardMedia>
 *           <img
 *             alt="A placeholder bear"
 *             src="https://placebear.com/g/200/200"
 *             width="100%"
 *             height="300px"
 *           />
 *         </CardMedia>
 *         <CardHeader
 *           leadingIcon={<Icon.Home size="large" />}
 *           title="Welcome"
 *           trailing={<Button variant="tertiary">Start Here</Button>}
 *         />
 *         <CardContent>
 *           Lorem ipsum dolor sit amet, consectetur adipiscing elit.
 *         </CardContent>
 *         <CardActions>
 *           <ButtonGroup>
 *             <Button variant="tertiary">Action1</Button>
 *             <Button variant="primary">Action2</Button>
 *           </ButtonGroup>
 *         </CardActions>
 *       </React.Fragment>
 *     </Card>
 *   );
 * };
 * ```
 */
import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import {Heading} from '../Text';

import './Card.css';
// ---------------------------------------------------------------------------
// CardActions (inlined sub-component)
// ---------------------------------------------------------------------------

export interface CardActionsProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /**
   * The content for the card actions.
   */
  children: React.ReactNode;
}

/**
 * Card Actions
 * *
 */
export const CardActions: React.FunctionComponent<CardActionsProps> = (
  props
) => {
  const {children, className, ...rest} = applyCommonProps(props);

  const size = React.useContext(CardSizeContext);

  return (
    <div
      className={cx('ld-card-cardactions-cardActions', size === 'large' && 'ld-card-cardactions-large', size === 'small' && 'ld-card-cardactions-small', className)}
      {...rest}
    >
      <div className={cx('ld-card-cardactions-cardActionsSeparator', className)} />
      {children}
    </div>
  );
};

CardActions.displayName = 'CardActions';

// ---------------------------------------------------------------------------
// CardContent (inlined sub-component)
// ---------------------------------------------------------------------------

export interface CardContentProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /**
   * The content for the card content.
   */
  children: React.ReactNode;
}

/**
 * Card Content
 * *
 */
export const CardContent: React.FunctionComponent<CardContentProps> = (
  props
) => {
  const {children, className, ...rest} = applyCommonProps(props);

  const size = React.useContext(CardSizeContext);

  return (
    <div
      className={cx(size === 'large' && 'ld-card-cardcontent-large', size === 'small' && 'ld-card-cardcontent-small', className)}
      {...rest}
    >
      {children}
    </div>
  );
};

CardContent.displayName = 'CardContent';

// ---------------------------------------------------------------------------
// CardHeader (inlined sub-component)
// ---------------------------------------------------------------------------

export interface CardHeaderProps
  extends Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'style' | 'title'
    > {
  /**
   * The leading icon for the card header.
   */
  leadingIcon?: React.ReactNode;
  /**
   * The title for the card header.
   */
  title: React.ReactNode;
  /**
   * The trailing content for the card header.
   */
  trailing?: React.ReactNode;
}

/**
 * Card Header
 * *
 */
export const CardHeader: React.FunctionComponent<CardHeaderProps> = (props) => {
  const {className, leadingIcon, title, trailing, ...rest} = applyCommonProps(props);

  const size = React.useContext(CardSizeContext);

  return (
    <div
      className={cx('ld-card-cardheader-container', size === 'large' && 'ld-card-cardheader-large', size === 'small' && 'ld-card-cardheader-small', className)}
      {...rest}
    >
      {leadingIcon && <span className={'ld-card-cardheader-leadingIcon'}>{leadingIcon}</span>}

      <Heading
        UNSAFE_className={'ld-card-cardheader-title'}
        size={"small"}
      >
        {title}
      </Heading>

      {trailing && <span className={'ld-card-cardheader-trailing'}>{trailing}</span>}
    </div>
  );
};

CardHeader.displayName = 'CardHeader';

// ---------------------------------------------------------------------------
// CardMedia (inlined sub-component)
// ---------------------------------------------------------------------------

export interface CardMediaProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /**
   * The content for the card media.
   */
  children: React.ReactNode;
}

/**
 * Card Media
 * *
 */
export const CardMedia: React.FunctionComponent<CardMediaProps> = (props) => {
  const transformedProps = applyCommonProps(props);

  return <div {...transformedProps} />;
};

CardMedia.displayName = 'CardMedia';

// ---------------------------------------------------------------------------
// CardSizeContext (inlined sub-component)
// ---------------------------------------------------------------------------

export type CardSize = 'large' | 'small';

export const CardSizeContext = React.createContext<CardSize>('small');

// CardSize is already exported above

export interface CardProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /**
   * The content for the card.
   */
  children: React.ReactNode;
  /**
   * The size for the card.
   *
   * @default "small"
   */
  size?: CardSize;
}

/**
 * Cards organize and present similar content that users can scan quickly and interact with. They contain text, images, icons and buttons placed with hierarchy. They may be placed as a series or feed of similar content.
 * *
 */
export const Card: React.FunctionComponent<CardProps> = (props) => {
  const {
    children,
    className,
    size = 'small',
    ...rest
  } = applyCommonProps(props);

  return (
    <CardSizeContext.Provider value={size}>
      <div className={cx('ld-card-card', className)} {...rest}>
        {children}
      </div>
    </CardSizeContext.Provider>
  );
};

Card.displayName = 'Card';
