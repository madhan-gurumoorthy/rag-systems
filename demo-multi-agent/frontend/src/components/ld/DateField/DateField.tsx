'use client';
// @refresh reset

/**
 * @module DateField
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
 * Date Field requires a label to be accessible. Use the `label` property to add a label:
 * 
 * ```tsx
 * <DateField label="Birthdate" onChange={(event) => console.log(event)} />
 * ```
 * 
 * #### Helper and error text
 * 
 * Set the `helperText` prop to include descriptive helper text below the label:
 * 
 * ```tsx
 * <DateField
 *   helperText="Please enter your date of birth"
 *   label="Birthdate (mm/dd/yyyy)"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * Set the `error` prop to indicate to a user that the Date Field is in a bad state.
 * 
 * (Note: `error` overrides `helperText` and validation errors.)
 * 
 * ```tsx
 * <DateField
 *   error="This is wrong."
 *   label="Birthdate (mm/dd/yyyy)"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * ### Features
 * 
 * #### Size
 * 
 * The Date Field comes in two sizes:
 * 
 * - `small`
 * - `large` (default)
 * 
 * Set the Date Field's size with the `size` property.
 * 
 * ```tsx
 * <DateField label="Small" size="small" />
 * <DateField label="Large" size="large" />
 * ```
 * 
 * ### Interaction
 * 
 * Configure the Date Field's value using the `value` property. Respond to changes by passing a callback handler to the `onChange` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {DateField} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [value, setValue] = React.useState('12/21/12');
 * 
 *   return (
 *     <DateField
 *       label="Birthdate (mm/dd/yyyy)"
 *       onChange={(event) => setValue(event.target.value)}
 *       value={value}
 *     />
 *   );
 * };
 * ```
 * 
 * #### Validation
 * 
 * The Date Field validates that input matches the expected format on focus change. The default format, `MM/dd/yyyy`, can be overridden using the `format` prop. Custom format strings must use [Unicode Tokens](https://www.unicode.org/reports/tr35/tr35-dates.html#Date_Field_Symbol_Table) as specified in the `date-fns` [parse](https://date-fns.org/v2.30.0/docs/parse) and [format](https://date-fns.org/v2.30.0/docs/format) documentation.
 * 
 * The `label` (text above the field) should indicate the desired date format for best accessibility and usability. For instance, the label "Enter date (mm/dd/yyyy)" provides clarity to assistive technology such as screen readers. Similarly, the validation error message can be overridden by providing a callback through the `renderError` prop.
 * 
 * ```tsx
 * <DateField
 *   format="MM.dd.yyyy"
 *   label="Birthdate (MM.dd.yyyy)"
 *   onChange={(event) => console.log(event)}
 *   renderError={() => 'Please use the format MM.dd.yyyy'}
 * />
 * ```
 */
import * as React from 'react';
import {applyCommonProps} from '../common';
import {TextField} from '../TextField';
import {useDateField} from '../DatePicker';

export type DateFieldSize = 'large' | 'small';

export interface DateFieldProps
  extends Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'onChange' | 'style'
    > {
  /**
   * If the date field is disabled.
   *
   * @default false
   */
  disabled?: boolean;
  /**
   * The error for the date field.
   */
  error?: React.ReactNode;
  /**
   * The date string format for the date field.
   *
   * @default "MM/dd/yyyy"
   */
  format?: string;
  /**
   * The helper text for the date field.
   */
  helperText?: React.ReactNode;
  /**
   * The id for the date field.
   */
  id?: string;
  /**
   * The label for the date field.
   */
  label: React.ReactNode;
  /**
   * The callback fired when the date field requests to change.
   */
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  /**
   * If the date field is read only.
   *
   * @default false
   */
  readOnly?: boolean;
  /**
   * The callback fired when date picker date field input is invalid.
   *
   * @default () => {
   *   return `Use the required format {props.format}`;
   * }
   */
  renderError?: (error?: Error) => string;
  /**
   * The size for the date field.
   *
   * @default "large"
   */
  size?: DateFieldSize;
  /**
   * The props spread to the date field's input element.
   *
   * @default {}
   */
  textFieldProps?: React.ComponentPropsWithoutRef<'input'>;
  /**
   * The value for the date field.
   *
   * @default ""
   */
  value?: string;
}

/**
 * Date Fields allow users to enter a single date in a field.
 * *
 */
export const DateField = React.forwardRef<HTMLInputElement, DateFieldProps>(
  (props, ref) => {
    const {
      className,
      error: errorProp,
      format = 'MM/dd/yyyy',
      label,
      renderError: renderErrorProp,
      textFieldProps = {},
      value = '',
      ...rest
    } = applyCommonProps(props);

    const [error, setError] = React.useState<string>('');

    const renderError = React.useMemo(
      () => renderErrorProp ?? (() => `Use the required format ${format}`),
      [format, renderErrorProp]
    );

    const {validateValue} = useDateField({
      format,
      renderError,
      setError,
    });

    return (
      <TextField
        error={errorProp ?? error}
        label={label}
        ref={ref}
        onBlur={() => validateValue(value)}
        textFieldProps={{
          ...textFieldProps,
          type: 'text',
        }}
        UNSAFE_className={className}
        value={value}
        {...rest}
      />
    );
  }
);

DateField.displayName = 'DateField';
