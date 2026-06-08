'use client';
// @refresh reset

/**
 * @module Collapse
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
 * ### Opening and closing
 * 
 * The Collapse will expand and contract based on user interactions. Control whether the full text is visible using the `isOpen` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Button, Collapse} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [state, setState] = React.useState(false);
 * 
 *   return (
 *     <div>
 *       <Button
 *         aria-controls="with-interactive-content"
 *         aria-expanded={state}
 *         onClick={() => setState(!state)}
 *       >
 *         {state ? 'Collapse' : 'Open'}
 *       </Button>
 *       <Collapse id="with-interactive-content" isOpen={state}>
 *         <p>
 *           Capitalize on low hanging fruit to identify a ballpark value added
 *           activity to beta test. Override the digital divide with additional
 *           clickthroughs from DevOps. Nanotechnology immersion along the
 *           information highway will close the loop on focusing solely on the
 *           bottom line.
 *         </p>
 *       </Collapse>
 *     </div>
 *   );
 * };
 * ```
 */
import * as React from 'react';
import {cx, setStyleProperty, applyCommonProps, useCSSTransition} from '../common';
import './Collapse.css';
export interface CollapseProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /**
   * If the component is collapsed.
   *
   * @default false
   */
  isOpen?: boolean;
}

/**
 * Collapse is a utility component that is used to put long sections of information under a block that users can expand or collapse.
 *
 */
export const Collapse: React.FunctionComponent<CollapseProps> = (props) => {
  const {
    children,
    className,
    isOpen = false,
    ...rest
  } = applyCommonProps(props);

  const ref = React.useRef<HTMLDivElement>(null);

  const clearNodeStyleHeight = React.useCallback(() => {
    const node = ref.current;

    if (node) {
      setStyleProperty(node, 'height', '');
    }
  }, [ref]);

  const setNodeStyleHeight = React.useCallback(() => {
    const node = ref.current;

    if (node) {
      setStyleProperty(node, 'height', `${node.scrollHeight}px`);
    }
  }, [ref]);

  const {shouldMount} = useCSSTransition({
    classNames: {
      enter: 'ld-collapse-enter',
      enterActive: 'ld-collapse-enterActive',
      exit: 'ld-collapse-exit',
      exitActive: 'ld-collapse-exitActive',
    },
    onEntering: setNodeStyleHeight,
    onEntered: clearNodeStyleHeight,
    onExit: setNodeStyleHeight,
    onExiting: clearNodeStyleHeight,
    in: isOpen,
    mountOnEnter: true,
    nodeRef: ref,
    timeout: {
      enter: 300,
      exit: 250,
    },
    unmountOnExit: true,
  });

  return (
    shouldMount && <div
      className={cx('ld-collapse-collapse', className)}
      ref={ref}
      {...rest}
    >
      {children}
    </div>
  );
};

Collapse.displayName = 'Collapse';
