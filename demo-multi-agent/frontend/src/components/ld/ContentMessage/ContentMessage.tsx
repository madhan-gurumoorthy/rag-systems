// @refresh reset

/**
 * @module ContentMessage
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
 * #### Children and title
 * 
 * The Content Message requires a title and text content. Provide a title using the `title` prop and text content using the `children` prop:
 * 
 * ```tsx
 * <ContentMessage title="Service details aren’t available right now">
 *   Refresh this page to try again.
 * </ContentMessage>
 * ```
 * 
 * #### Actions
 * 
 * The Content Message can include buttons to perform actions relevant to the displayed content. Provide button-like elements through the `actions` prop:
 * 
 * ```tsx
 * import * as React from "react";
 * import { Button, ContentMessage } from "@livingdesign/react";
 * 
 * export default () => {
 *   return (
 *     <ContentMessage
 *       title="Service details aren’t available right now"
 *       actions={
 *         <Button size="medium" variant="primary" onClick={...}>
 *           Refresh page
 *         </Button>
 *       }
 *     >
 *       Refresh this page to try again.
 *     </ContentMessage>
 *   );
 * };
 * ```
 * 
 * #### Media
 * 
 * The Content Message can include media, such as an illustration. Set the `media` prop to display an image with the Content Message:
 * 
 * ```tsx
 * <ContentMessage
 *   title="Service details aren’t available right now"
 *   media={
 *     <img alt="" src="/SearchNotFoundCircle.svg" />
 *   }
 * >
 *   Refresh this page to try again.
 * </ContentMessage>
 * ```
 * 
 * ### Features
 * 
 * #### Size
 * 
 * The Content Message comes in two sizes:
 * 
 * - `small` (default)
 * - `large`
 * 
 * Set the Content Message's size with the `size` prop:
 * 
 * ```tsx
 * <ContentMessage size="small">{...}</ContentMessage>
 * <ContentMessage size="large">{...}</ContentMessage>
 * ```
 * 
 * ## FAQ
 * 
 * ### How do I configure title as a heading?
 * 
 * - This can be handled by passing the `title` prop a heading element. See example below.
 * 
 * ```tsx
 * <ContentMessage
 *   title={
 *     <h1
 *       style={{
 *         display: 'inline',
 *         fontSize: '100%',
 *         fontWeight: 'inherit',
 *         lineHeight: 'inherit',
 *         margin: 0,
 *       }}
 *     >
 *       We couldn’t find this page
 *     </h1>
 *   }
 * >
 *   Refresh this page to try again.
 * </ContentMessage>
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import {Body, Heading} from '../Text';
import './ContentMessage.css';

export type ContentMessageSize = 'small' | 'large';

export interface ContentMessageProps
  extends Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'style' | 'title'
    > {
  /**
   * The actions for the content message.
   */
  actions?: React.ReactNode;
  /**
   * The content for the content message.
   */
  children: React.ReactNode;
  /**
   * The media for the content message.
   */
  media?: React.ReactNode;
  /**
   * The title for the content message.
   */
  title: React.ReactNode;
  /**
   * The size for the ContentMessage.
   *
   * @default "small"
   */
  size?: ContentMessageSize;
}

/**
 * Content Messages provide a familiar layout with descriptive content and suggested actions for various scenarios.
 * *
 */
export const ContentMessage: React.FunctionComponent<ContentMessageProps> = (
  props
) => {
  const {
    actions,
    children,
    media,
    size = 'small',
    title,
    ...rest
  } = applyCommonProps(props);

  const headingSize = React.useMemo(
    () =>
      size === 'small'
        ? "medium"
        : "large",
    [size]
  );

  return (
    <div
      className={cx('ld-contentmessage-contentMessage', size === 'small' && 'ld-contentmessage-small', size === 'large' && 'ld-contentmessage-large')}
      {...rest}
    >
      {media && <div className={'ld-contentmessage-media'}>{media}</div>}

      <Heading
        as="div"
        size={headingSize}
        weight={"default"}
        UNSAFE_className={'ld-contentmessage-title'}
      >
        {title}
      </Heading>

      <Body
        as="div"
        size={"medium"}
        UNSAFE_className={'ld-contentmessage-textLabel'}
      >
        {children}
      </Body>

      {actions && <div className={'ld-contentmessage-actions'}>{actions}</div>}
    </div>
  );
};
