'use client';
// @refresh reset

/**
 * @module FocusTrap
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
 * The Focus Trap accepts content for the focus lock through the `children` prop.
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Button, ButtonGroup, FocusTrap} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [disabled, setDisabled] = React.useState(true);
 * 
 *   return (
 *     <FocusTrap disabled={disabled}>
 *       <ButtonGroup>
 *         <Button>it's</Button>
 *         <Button>a</Button>
 *         <Button>trap</Button>
 *         <Button onClick={() => setDisabled(!disabled)} variant="tertiary">
 *           {disabled ? 'Arm' : 'Disarm'}
 *         </Button>
 *       </ButtonGroup>
 *     </FocusTrap>
 *   );
 * };
 * ```
 * 
 * ### Interaction
 * 
 * The Focus Trap can be configured to return focus to the triggering element. Set the `hasFocusReturn` prop to control focus return:
 * 
 * ```tsx
 * <FocusTrap hasFocusReturn={false}>
 *   <ButtonGroup>
 *     <Button>it's</Button>
 *     <Button>a</Button>
 *     <Button>trap</Button>
 *   </ButtonGroup>
 * </FocusTrap>
 * ```
 * 
 * ## FAQ
 * 
 * ### When should I use `FocusTrap`?
 * 
 * - Modal dialogs
 * - Focused tasks or any other use case, when you have to lock user intention and focus
 */
import * as React from 'react';
import {applyCommonProps} from '../common';
interface _FocusLockProps {
  children: React.ReactNode;
  disabled?: boolean;
  returnFocus?: boolean;
  onDeactivation?: () => void;
  [key: string]: unknown;
}

const FocusLock: React.FC<_FocusLockProps> = ({
  children,
  disabled = false,
  returnFocus = false,
  onDeactivation,
  ...rest
}) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const previouslyFocused = React.useRef<Element | null>(null);
  const onDeactivationRef = React.useRef(onDeactivation);
  React.useEffect(() => { onDeactivationRef.current = onDeactivation; });

  React.useEffect(() => {
    if (disabled) return;
    previouslyFocused.current = document.activeElement;
    const el = containerRef.current;
    if (!el) return;

    const focusables = el.querySelectorAll<HTMLElement>(
      'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])'
    );
    if (focusables.length > 0) focusables[0].focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    el.addEventListener('keydown', handleKeyDown);

    return () => {
      el.removeEventListener('keydown', handleKeyDown);
      onDeactivationRef.current?.();
      if (returnFocus && previouslyFocused.current instanceof HTMLElement) {
        previouslyFocused.current.focus();
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled, returnFocus]);

  return <div ref={containerRef} {...rest}>{children}</div>;
};
export interface FocusTrapProps
  extends Omit<React.ComponentProps<typeof FocusLock>, 'className' | 'style'> {
  /**
   * The content for the focus lock.
   */
  children: React.ReactNode;
  /**
   * If focus should be returned to the triggering element.
   *
   * @default true
   */
  hasFocusReturn?: boolean;
}

/**
 * Focus Trap is a utility component that isolates browser focus for accessibility purposes.
 * *
 */
export const FocusTrap: React.FunctionComponent<FocusTrapProps> = (props) => {
  const {hasFocusReturn = true, ...rest} = applyCommonProps(props);

  // Focus return conflicts with all UI announcements.
  //
  // @see {@link https://jira.walmart.com/browse/LD-607}
  //
  // 1. Focus return will stomp over aria-live. Screen reader can only read one thing at a time.
  // 2. Focus return is required for all modal-like components.
  // 3. Recommend manage all UI announcement within children or outside experience entirely.
  return <FocusLock returnFocus={hasFocusReturn} {...rest} />;
};

FocusTrap.displayName = 'FocusTrap';
