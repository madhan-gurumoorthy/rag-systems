'use client';
// @refresh reset

/**
 * @module Checkbox
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
 * The Checkbox must include a label describing the option being selected. Provide a label through the `label` prop.
 * 
 * Alternatively, a separate element can be used to label the Checkbox. In this case, an `a11yLabelledBy` that references the labelling component's `id` must be provided.
 * 
 * (Note: `label` and `a11yLabelledBy` props are mutually exclusive.)
 * 
 * ```tsx
 * <Checkbox
 *   label="My checkbox"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * *OR*
 * 
 * ```tsx
 * <Checkbox
 *   a11yLabelledBy="custom-label-id"
 *   onChange={(event) => console.log(event)}
 * >
 * <span id="custom-label-id">My checkbox</span>
 * ```
 * 
 * #### HTMLInputElement attributes
 * 
 * The Checkbox returns an `<input type="checkbox">` element. It accepts `name` and `value` props which will be forwarded to the `input` element.
 * 
 * ### Features
 * 
 * #### States
 * 
 * The Checkbox's states can be managed through the following optional props: `checked`, `indeterminate` and `disabled`.
 * 
 * ```tsx
 * import * as React from "react";
 * import { Checkbox } from "@livingdesign/react";
 * 
 * export default () => {
 *   return (
 *     <>
 *       <Checkbox
 *         checked={checked}
 *         label="apple"
 *         onChange={(e) => console.log(e.target.value)}
 *       />
 *       <Checkbox
 *         disabled
 *         label="banana"
 *         onChange={(e) => console.log(e.target.value)}
 *       />
 *       <Checkbox
 *         indeterminate
 *         label="orange"
 *         onChange={(e) => console.log(e.target.value)}
 *       />
 *     </>
 *   );
 * }
 * ```
 * 
 * ### Interaction
 * 
 * The Checkbox requires a callback to be provided to the `onChange` prop to handle interaction with checkbox.
 * 
 * ```tsx
 * import * as React from "react";
 * import { Checkbox } from "@livingdesign/react";
 * 
 * export default () => {
 *   const [checked, setChecked] = React.useState(false);
 * 
 *   return (
 *     <Checkbox
 *       checked={checked}
 *       onChange={() => setChecked(x => !x)}
 *     />
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
import {cx, useStableId, invariant, applyCommonProps, emit} from '../common';
import './Checkbox.css';
interface CheckboxBaseProps
  extends Omit<
      React.ComponentPropsWithoutRef<'label'>,
      'className' | 'onChange' | 'style'
    > {
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
  /**
   * The props spread to the checkbox's input element.
   *
   * @default {}
   */
  checkboxProps?: React.ComponentPropsWithoutRef<'input'>;
  /**
   * If the checkbox is checked.
   *
   * @default false
   */
  checked?: boolean;
  /**
   * If the checkbox is disabled.
   *
   * @default false
   */
  disabled?: boolean;
  /**
   * The id for the checkbox.
   */
  id?: string;
  /**
   * If the checkbox is indeterminate.
   *
   * @default false
   */
  indeterminate?: boolean;
  /**
   * The name for the checkbox.
   */
  name?: string;
  /**
   * The callback fired when the checkbox requests to change.
   */
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  /**
   * The value for the checkbox.
   */
  value?: number | string;
}

export interface CheckboxA11yProps extends CheckboxBaseProps {
  /**
   * The accessible label reference IDs for the checkbox (Required if omitting `label`).
   */
  a11yLabelledBy: string;
  label?: never;
}

export interface CheckboxLabelProps extends CheckboxBaseProps {
  /**
   * The label for the checkbox (Required if omitting `a11yLabelledBy`).
   */
  label: React.ReactNode;
  a11yLabelledBy?: never;
}

export type CheckboxProps = CheckboxA11yProps | CheckboxLabelProps;

/**
 * Checkboxes are selectable options presented in a group. A user may select any number of Checkboxes, including all or none.
 * *
 */
export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  (props, ref) => {
    const {
      a11yLabelledBy,
      checkboxProps = {},
      checked = false,
      className,
      disabled = false,
      indeterminate = false,
      id: initialId,
      label,
      name,
      onChange,
      value,
      ...rest
    } = applyCommonProps(props);

    const labelCount = (label ? 1 : 0) + (a11yLabelledBy ? 1 : 0) === 1;

    invariant(
      labelCount,
      '`Checkbox` accessibility violation. `Checkbox` requires a `label` OR an `a11yLabelledBy`.'
    );

    const {className: checkboxClassName, ...checkboxRest} = checkboxProps;
    const id = useStableId(initialId);

    const inputRef = React.useRef<HTMLInputElement>(null);

    React.useImperativeHandle<HTMLInputElement | null, HTMLInputElement | null>(
      ref,
      () => {
        return inputRef.current;
      }
    );



    React.useEffect(() => {
      if (inputRef.current) {
        inputRef.current.indeterminate = indeterminate;
      }
    }, [indeterminate]);

    return (
      <label
        className={cx('ld-checkbox-label', checked && !indeterminate && 'ld-checkbox-checked', disabled && 'ld-checkbox-disabled', indeterminate && 'ld-checkbox-indeterminate', className)}
        htmlFor={id}
        {...rest}
      >
        <input
          checked={checked}
          className={cx('ld-checkbox-input', checkboxClassName)}
          disabled={disabled}
          id={id}
          name={name}
          onChange={(e) => { emit('ui:checkbox:change', {checked: e.target.checked, name, value}); onChange(e); }}
          ref={inputRef}
          type="checkbox"
          {...(a11yLabelledBy && {'aria-labelledby': a11yLabelledBy})}
          {...(value && {value})}
          {...checkboxRest}
        />

        <div className={'ld-checkbox-checkbox'}>
          <svg
            aria-hidden
            className={'ld-checkbox-checkboxIcon'}
            viewBox="0 0 16 16"
            xmlns="http://www.w3.org/2000/svg"
          >
            {indeterminate ? (
              <rect x="1.33337" y="6.66663" width="13.3333" height="2.66667" />
            ) : checked ? (
              <path d="M15 3.80705L6.23047 12.6609C5.78259 13.113 5.05642 13.113 4.60854 12.6609L1 9.01759L2.72031 7.28075L5.41951 10.1053L13.2101 2L15 3.80705Z" />
            ) : null}
          </svg>
        </div>
        {label && <span className={'ld-checkbox-labelText'}>{label}</span>}
      </label>
    );
  }
);

Checkbox.displayName = 'Checkbox';
