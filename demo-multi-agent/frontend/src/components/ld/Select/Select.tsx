'use client';
// @refresh reset

/**
 * @module Select
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
 * #### Children
 * 
 * Select accepts `option` elements as `children`:
 * 
 * ```tsx
 * <Select label="Choose a state" onChange={(event) => console.log(event)}>
 *   <option value="CA">California</option>
 *   <option value="NJ">New Jersey</option>
 *   <option value="OR">Oregon</option>
 *   <option value="WA">Washington</option>
 * </Select>
 * ```
 * 
 * #### Value
 * 
 * Configure Select's value using the `value` prop. Respond to changes in value by passing an event handler to the required `onChange` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Select} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [value, setValue] = React.useState('CA');
 * 
 *   return (
 *     <Select
 *       label="Choose a state"
 *       onChange={(event) => setValue(event.target.value)}
 *       value={value}
 *     >
 *       <option value="CA">California</option>
 *       <option value="NJ">New Jersey</option>
 *       <option value="OR">Oregon</option>
 *       <option value="WA">Washington</option>
 *     </Select>
 *   );
 * };
 * ```
 * 
 * #### Label
 * 
 * Select requires a label to be accessible. Add a label with the `label` prop:
 * 
 * ```tsx
 * <Select label="Choose a state" onChange={(event) => console.log(event)}>
 *   <option value="CA">California</option>
 *   <option value="NJ">New Jersey</option>
 *   <option value="OR">Oregon</option>
 *   <option value="WA">Washington</option>
 * </Select>
 * ```
 * 
 * #### Helper and error text
 * 
 * Set the `helperText` prop to include descriptive helper text below the label:
 * 
 * ```tsx
 * <Select
 *   helperText="Where is the closest Walmart office?"
 *   label="Choose a state"
 *   onChange={(event) => console.log(event)}
 * >
 *   <option value="CA">California</option>
 *   <option value="NJ">New Jersey</option>
 *   <option value="OR">Oregon</option>
 *   <option value="WA">Washington</option>
 * </Select>
 * ```
 * 
 * Set the `error` prop to indicate to a user that Select is in a bad state:
 * 
 * (Note: `error` overrides `helperText`.)
 * 
 * ```tsx
 * <Select
 *   error="This is wrong."
 *   label="Choose a state"
 *   onChange={(event) => console.log(event)}
 * >
 *   <option value="CA">California</option>
 *   <option value="NJ">New Jersey</option>
 *   <option value="OR">Oregon</option>
 *   <option value="WA">Washington</option>
 * </Select>
 * ```
 * 
 * #### Leading icon
 * 
 * Clarify a Select element's purpose by adding an icon with the `leadingIcon` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import * as Icon from '@livingdesign/icons';
 * import {Select} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <Select
 *       label="Choose a state"
 *       leadingIcon={<Icon.Location />}
 *       onChange={(event) => console.log(event)}
 *     >
 *       <option value="CA">California</option>
 *       <option value="NJ">New Jersey</option>
 *       <option value="OR">Oregon</option>
 *       <option value="WA">Washington</option>
 *     </Select>
 *   );
 * };
 * ```
 * 
 * ### Features
 * 
 * #### Is Magic
 * 
 * Use the `isMagic` prop to indicate that the Select's value was generated or influenced by an AI agent. When enabled, `isMagic` applies "magic" styles and adds an accessible description to the input. By default this description is "AI Generated"; you can override it with the `a11yMagicLabel` prop for customization or localization.
 * 
 * ```tsx
 * <Select
 *   isMagic
 *   a11yMagicLabel="AI Generated"
 *   label="Choose a state"
 *   onChange={(event) => console.log(event)}
 * >
 *   <option value="CA">California</option>
 *   <option value="NJ">New Jersey</option>
 *   <option value="OR">Oregon</option>
 *   <option value="WA">Washington</option>
 * </Select>
 * ```
 * 
 * #### Size
 * 
 * Select comes in two sizes:
 * 
 * - `small`
 * - `large` (default)
 * 
 * Set Select's size using the `size` prop:
 * 
 * ```tsx
 * <Select label="Large" size="large" />
 * <Select label="Small" size="small" />
 * ```
 * 
 * ## FAQ
 * 
 * ### How do I add inline form validation?
 * 
 * Inline form validation is not required and will not supported by LD at this time. If inline form validation is needed, it is the responsibility of the consumer to do this outside of the component and ensure that their form fields are accessible. See https://jira.walmart.com/browse/LD-991 for more details.
 */
import * as React from 'react';
import {cx, useStableId, applyCommonProps, WithIconProps, emit} from '../common';
import {VisuallyHidden} from '../VisuallyHidden';
import {
  CaretDownIcon,
} from '../Icons';
import {FormHelperText, FormLabel} from '../Form';
import './Select.css';
export type SelectSize = 'large' | 'small';

export interface SelectProps
  extends Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'onChange' | 'style'
    > {
  /**
   * The accessible description of the Select that indicates the involvement of an AI agent.
   *
   * @default "AI Generated"
   */
  a11yMagicLabel?: string;
  /**
   * The content for the select.
   */
  children: React.ReactNode;
  /**
   * If the select is disabled.
   *
   * @default false
   */
  disabled?: boolean;
  /**
   * The error for the select.
   */
  error?: React.ReactNode;
  /**
   * The helper text for the select.
   */
  helperText?: React.ReactNode;
  /**
   * The id for the select.
   */
  id?: string;
  /**
   * If the Select should use visual styles that indicate the involvement of an AI agent.
   *
   * @default false
   */
  isMagic?: boolean;
  /**
   * The label for the select.
   */
  label: React.ReactNode;
  /**
   * The leading icon for the select.
   */
  leadingIcon?: React.ReactNode;
  /**
   * The callback fired when the select requests to change.
   */
  onChange: (event: React.ChangeEvent<HTMLSelectElement>) => void;
  /**
   * The props spread to the select's select element.
   *
   * @default {}
   */
  selectProps?: React.ComponentPropsWithoutRef<'select'>;
  /**
   * The size for the select.
   *
   * @default "large"
   */
  size?: SelectSize;
  /**
   * The value for the select.
   */
  value?: string;
}

/**
 * Select gives users the ability to make a single selection from a number of predefined options. It is usually found in forms.
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/components/select/ Guidelines}
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/components/select/ React documentation}
 *
 */
export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (props, ref) => {
    const {
      a11yMagicLabel = 'AI Generated',
      children,
      className,
      disabled = false,
      error,
      helperText,
      id: initialId,
      isMagic = false,
      label,
      leadingIcon,
      onChange,
      selectProps,
      size = 'large',
      value,
      ...rest
    } = applyCommonProps(props);

    const id = useStableId(initialId);
    const helperId = useStableId();
    const magicLabelId = useStableId();

    const hasError = !!error && !disabled;
    const helperContent = hasError ? error : helperText;

    const ariaDescribedBy =
      [isMagic ? magicLabelId : null, helperContent ? helperId : null]
        .filter(Boolean)
        .join(' ') || undefined;

    return (
      <div
        className={cx('ld-select-root', disabled && 'ld-select-disabled', error && 'ld-select-error', isMagic && 'ld-select-isMagic', leadingIcon && 'ld-select-hasLeadingIcon', size === 'large' && 'ld-select-large', size === 'small' && 'ld-select-small', className)}
        {...rest}
      >
        <FormLabel
          className={'ld-select-label'}
          disabled={disabled}
          htmlFor={id}
          isMagic={isMagic}
          size={size}
        >
          {label}
        </FormLabel>

        <div className={'ld-select-container'}>
          {leadingIcon && (
            <span
              aria-hidden
              className={cx('ld-select-icon', 'ld-select-leadingIcon')}
            >
              {React.isValidElement<WithIconProps>(leadingIcon)
                ? React.cloneElement(leadingIcon, {
                    size: "medium",
                  })
                : leadingIcon}
            </span>
          )}

          <select
            aria-describedby={ariaDescribedBy}
            disabled={disabled}
            id={id}
            onChange={(e) => { emit('ui:select:change', {value: e.target.value}); onChange(e); }}
            ref={ref}
            value={value}
            {...selectProps}
            className={cx('ld-select-value', selectProps?.className)}
          >
            {children}
          </select>

          <CaretDownIcon
            className={cx('ld-select-icon', 'ld-select-trailingIcon')}
            size={"medium"}
          />
        </div>

        {isMagic && (
          <VisuallyHidden
            aria-hidden
            id={magicLabelId}
          >{`${a11yMagicLabel},`}</VisuallyHidden>
        )}

        {!!helperContent && (
          <FormHelperText
            className={'ld-select-helperText'}
            disabled={disabled}
            hasError={hasError}
            id={helperId}
          >
            {helperContent}
          </FormHelperText>
        )}
      </div>
    );
  }
);

Select.displayName = 'Select';
