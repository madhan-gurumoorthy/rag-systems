// @refresh reset

/**
 * @module Switch
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
 * #### Label
 * 
 * The Switch must include a label describing the option being selected. Provide a label through the `label` prop.
 * 
 * Alternatively, a separate element can be used to label the Switch. In this case, an `a11yLabelledBy` prop that references the labelling component's `id` must be provided.
 * 
 * (Note: `label` and `a11yLabelledBy` props are mutually exclusive.)
 * 
 * ```tsx
 * <Switch label="My switch" />
 * ```
 * 
 * _OR_
 * 
 * ```tsx
 * <Switch a11yLabelledBy="custom-label-id" />
 * <span id="custom-label-id">My switch</span>
 * ```
 * 
 * ### Interaction
 * 
 * The Switch accepts as `isOn` property to set its selection state. Use the `onClick` event handler to accept user requests to set a Switch's state.
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Switch} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [isOn, setIsOn] = React.useState(false);
 * 
 *   return (
 *     <Switch label="My switch" isOn={isOn} onClick={() => setIsOn((x) => !x)} />
 *   );
 * };
 * ```
 * 
 * ## FAQ
 * 
 * ### How do I provide a custom label?
 * 
 * If a custom label is required to describe a form element, you should not use the `label` property. Instead, use the `a11yLabelledBy` property and link the form element to the custom label.
 * 
 * For more information on how the property should be used accessibly, please refer to [W3C](https://www.w3.org/TR/wai-aria/#aria-labelledby).
 */

import * as React from 'react';
import {cx, invariant, applyCommonProps, emit} from '../common';
import './Switch.css';

interface SwitchBaseProps
  extends Omit<
      React.ComponentPropsWithoutRef<'button'>,
      'className' | 'onChange' | 'style'
    > {
  /** @default false */
  disabled?: boolean;
  /** @default false */
  isOn?: boolean;
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
}

export interface SwitchA11yProps extends SwitchBaseProps {
  a11yLabelledBy: string;
  label?: never;
}

export interface SwitchLabelProps extends SwitchBaseProps {
  label: React.ReactNode;
  a11yLabelledBy?: never;
}

export type SwitchProps = SwitchA11yProps | SwitchLabelProps;

export const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
  (props, ref) => {
    const {
      a11yLabelledBy,
      className,
      isOn = false,
      disabled = false,
      label,
      onClick,
      ...rest
    } = applyCommonProps(props);

    const labelCount = (label ? 1 : 0) + (a11yLabelledBy ? 1 : 0) === 1;
    invariant(
      labelCount,
      '`Switch` accessibility violation. `Switch` requires a `label` OR an `a11yLabelledBy`.'
    );

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      emit('ui:switch:toggle', {isOn: !isOn});
      onClick?.(e);
    };

    return (
      <button
        aria-checked={isOn}
        className={cx('ld-switch-pill', isOn && 'ld-switch-on', className)}
        disabled={disabled}
        onClick={handleClick}
        ref={ref}
        role="switch"
        type="button"
        {...(a11yLabelledBy && {'aria-labelledby': a11yLabelledBy})}
        {...rest}
      >
        <span className={cx('ld-switch-indicator', isOn && 'ld-switch-on')} />
        {label && (
          <span className={cx('ld-switch-label', isOn && 'ld-switch-on')}>
            {label}
          </span>
        )}
      </button>
    );
  }
);

Switch.displayName = 'Switch';
