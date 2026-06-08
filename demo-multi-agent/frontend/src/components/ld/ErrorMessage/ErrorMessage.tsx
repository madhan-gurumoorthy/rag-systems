// @refresh reset

/**
 * @module ErrorMessage
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
 * The Error Message requires a title and text content. Provide a title using the `title` prop and text content using the `children` prop:
 * 
 * ```tsx
 * <ErrorMessage title="Service details aren’t available right now">
 *   Refresh this page to try again.
 * </ErrorMessage>
 * ```
 * 
 * #### Actions
 * 
 * The Error Message can include buttons to perform actions relevant to the displayed error. Provide button-like elements through the `actions` prop:
 * 
 * ```tsx
 * import * as React from "react";
 * import { Button, ErrorMessage } from "@livingdesign/react";
 * 
 * export default () => {
 *   return (
 *     <ErrorMessage
 *       title="Service details aren’t available right now"
 *       actions={
 *         <Button size="medium" variant="primary" onClick={...}>
 *           Refresh page
 *         </Button>
 *       }
 *     >
 *       Refresh this page to try again.
 *     </ErrorMessage>
 *   );
 * };
 * ```
 * 
 * #### Media
 * 
 * The Error Message can include media, such as an illustration. Set the `media` prop to display an image with the Error Message:
 * 
 * ```tsx
 * <ErrorMessage
 *   title="Service details aren’t available right now"
 *   media={
 *     <img alt="" height="200" src="/SearchNotFoundCircle.svg" width="200" />
 *   }
 * >
 *   Refresh this page to try again.
 * </ErrorMessage>
 * ```
 * 
 * ## FAQ
 * 
 * ### How do I configure title as a heading?
 * 
 * - This can be handled by passing the `title` prop a heading element. See example below.
 * 
 * ```tsx
 * <ErrorMessage
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
 * </ErrorMessage>
 * ```
 */

import * as React from 'react';
import {applyCommonProps} from '../common';
import {Body, Heading} from '../Text';
import './ErrorMessage.css';

export interface ErrorMessageProps
  extends Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'style' | 'title'
    > {
  /**
   * The actions for the error message.
   */
  actions?: React.ReactNode;
  /**
   * The content for the error message.
   */
  children: React.ReactNode;
  /**
   * The media for the error message.
   */
  media?: React.ReactNode;
  /**
   * The title for the error message.
   */
  title: React.ReactNode;
}

/**
 * @deprecated in @livingdesign/react@v1. This component will be removed in the next major version.
 *
 * Error Messages provide a familiar layout with descriptive content and suggested actions for error scenarios.
 * *
 */
export const ErrorMessage: React.FunctionComponent<ErrorMessageProps> = (
  props
) => {
  const {actions, children, media, title, ...rest} = applyCommonProps(props);

  return (
    <div className={'ld-errormessage-errorMessage'} {...rest}>
      {media && <div className={'ld-errormessage-media'}>{media}</div>}

      <Heading
        as="div"
        size={"large"}
        weight={"default"}
        UNSAFE_className={'ld-errormessage-title'}
      >
        {title}
      </Heading>

      <Body
        as="div"
        size={"medium"}
        UNSAFE_className={'ld-errormessage-textLabel'}
      >
        {children}
      </Body>

      {actions && <div className={'ld-errormessage-actions'}>{actions}</div>}
    </div>
  );
};
