'use client';
// @refresh reset

/**
 * @module Radio
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
 * The Radio must include a label describing the option being selected. Provide a label through the `label` prop.
 * 
 * Alternatively, a separate element can be used to label the Radio. In this case, an `a11yLabelledBy` that references the labelling component's `id` must be provided.
 * 
 * (Note: `label` and `a11yLabelledBy` props are mutually exclusive.)
 * 
 * ```tsx
 * <Radio
 *   label="My radio"
 *   name="myRadioGroup"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * _OR_
 * 
 * ```tsx
 * <Radio
 *   a11yLabelledBy="custom-label-id"
 *   name="myRadioGroup"
 *   onChange={(event) => console.log(event)}
 * >
 * <span id="custom-label-id">My radio</span>
 * ```
 * 
 * #### Name
 * 
 * The Radio requires a `name` property for keyboard navigation to work correctly with groups of Radio elements. Ensure that `name` is set to the same value for the group.
 * 
 * ```tsx
 * <Radio
 *   label="One"
 *   name="numberRadio"
 *   onChange={(event) => console.log(event)}
 * />
 * <Radio
 *   label="Two"
 *   name="numberRadio"
 *   onChange={(event) => console.log(event)}
 * />
 * <Radio
 *   label="Three"
 *   name="numberRadio"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * ### Interaction
 * 
 * The Radio can be configured as selected by using the `checked` property. Listen to changes in selection by passing an event handler to the `onChange` property.
 * 
 * ```tsx
 * export default () => {
 *   const [value, setValue] = React.useState("0");
 * 
 *   return (
 *     <Radio
 *       checked={value === "0"}
 *       label="No"
 *       onChange={(event) => setValue(event.target.value)}
 *       name="name"
 *       value="0"
 *     />
 *     <Radio
 *       checked={value === "1"}
 *       label="Yes"
 *       onChange={(event) => setValue(event.target.value)}
 *       name="name"
 *       value="1"
 *     />
 *   );
 * };
 * ```
 * 
 * ## FAQ
 * 
 * ### How do I provide a custom label?
 * 
 * Use the `a11yLabelledBy` property instead of the `label` property to associate a custom label element with Radio's input. For example:
 * 
 * ```tsx
 * <Radio a11yLabelledBy="custom-label" onChange={handleChange} />
 * <span id="custom-label">Custom label</span>
 * ```
 * 
 * `a11yLabelledBy` is an alias for the `aria-labelledby` property. Please refer to [`aria-labelledby` (property) in WAI-ARIA](https://www.w3.org/TR/wai-aria/#aria-labelledby) for more information.
 * 
 * ### How can I implement keyboard navigation in a group of Radio buttons?
 * 
 * All Radios in a Form group are required to have their name attribute have the same value. This allows keyboard navigation to work as expected. To learn more, visit [`<input type="radio"/>` documentation on MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/radio#defining_a_radio_group).
 */
import * as React from 'react';
import {cx, useStableId, invariant, remToPxValue, applyCommonProps, emit} from '../common';
import './Radio.css';
interface RadioBaseProps
  extends Omit<
      React.ComponentPropsWithoutRef<'label'>,
      'clasName' | 'onChange' | 'style'
    > {
  /**
   * If the radio is checked.
   *
   * @default false
   */
  checked?: boolean;
  /**
   * If the radio is disabled.
   *
   * @default false
   */
  disabled?: boolean;
  /**
   * The id for the radio.
   */
  id?: string;
  /**
   * The name for the radio.
   */
  name: string;
  /**
   * The callback fired when the radio requests to change.
   */
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  /**
   * The props spread to the radio's input element.
   *
   * @default {}
   */
  radioProps?: React.ComponentPropsWithoutRef<'input'>;
  /**
   * The value for the radio.
   */
  value?: number | string;
}

export interface RadioA11yProps extends RadioBaseProps {
  /**
   * The accessible label reference IDs for the radio (Required if omitting `label`).
   */
  a11yLabelledBy: string;
  label?: never;
}

export interface RadioLabelProps extends RadioBaseProps {
  /**
   * The label for the radio (Required if omitting `a11yLabelledBy`).
   */
  label: React.ReactNode;
  a11yLabelledBy?: never;
}

export type RadioProps = RadioA11yProps | RadioLabelProps;

/**
 * Radio Buttons represent a group of mutually exclusive choices.
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/components/radio/ Guidelines}
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/components/radio/ React documentation}
 *
 */
export const Radio = React.forwardRef<HTMLInputElement, RadioProps>(
  (props, ref) => {
    const {
      a11yLabelledBy,
      checked = false,
      className,
      disabled = false,
      id: initialId,
      label,
      name,
      onChange,
      radioProps = {},
      value,
      ...rest
    } = applyCommonProps(props);

    const labelCount = (label ? 1 : 0) + (a11yLabelledBy ? 1 : 0) === 1;

    invariant(
      labelCount,
      '`Radio` accessibility violation. `Radio` requires a `label` OR an `a11yLabelledBy`.'
    );

    const {className: radioClassName, ...radioRest} = radioProps;
    const id = useStableId(initialId);
    const inputBorderHeight = React.useMemo(
      () => remToPxValue("1.5rem"),
      []
    );

    return (
      <label
        className={cx('ld-radio-label', checked && 'ld-radio-checked', disabled && 'ld-radio-disabled', className)}
        htmlFor={id}
        {...rest}
      >
        <input
          checked={checked}
          className={cx('ld-radio-input', radioClassName)}
          disabled={disabled}
          id={id}
          name={name}
          onChange={(e) => { emit('ui:radio:change', {name, value}); onChange(e); }}
          ref={ref}
          type="radio"
          {...(a11yLabelledBy && {'aria-labelledby': a11yLabelledBy})}
          {...(value && {value})}
          {...radioRest}
        />

        <svg
          aria-hidden
          className={'ld-radio-radioInput'}
          viewBox={`0 0 ${inputBorderHeight} ${inputBorderHeight}`}
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle
            className={'ld-radio-radioInputOuter'}
            cx={inputBorderHeight / 2}
            cy={inputBorderHeight / 2}
          />
          <circle
            className={'ld-radio-radioInputInner'}
            cx={inputBorderHeight / 2}
            cy={inputBorderHeight / 2}
          />
        </svg>

        {label && <span className={'ld-radio-labelText'}>{label}</span>}
      </label>
    );
  }
);

Radio.displayName = 'Radio';
