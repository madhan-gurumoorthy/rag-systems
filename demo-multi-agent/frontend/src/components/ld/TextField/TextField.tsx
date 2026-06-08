'use client';
// @refresh reset

/**
 * @module TextField
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
 * Text Field requires a label to be accessible. Use the `label` property to add a label:
 * 
 * ```tsx
 * <TextField label="Full name" onChange={(event) => console.log(event)} />
 * ```
 * 
 * #### Helper and error text
 * 
 * Set the `helperText` prop to include descriptive helper text below the label:
 * 
 * ```tsx
 * <TextField
 *   helperText="Please include middle initials"
 *   label="Full name"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * Set the `error` prop to indicate to a user that the Text Field is in a bad state.
 * 
 * (Note: `error` overrides `helperText`.)
 * 
 * ```tsx
 * <TextField
 *   error="This is wrong."
 *   label="Full name"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * #### Leading and trailing
 * 
 * Clarify the Text Field's purpose by adding an icon with the `leadingIcon` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import * as Icon from '@livingdesign/icons';
 * import {TextField} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <TextField
 *       label="Full name"
 *       leadingIcon={<Icon.User />}
 *       onChange={(event) => console.log(event)}
 *     />
 *   );
 * };
 * ```
 * 
 * Enhance Text Field's functionality by passing additional content to the `trailing` slot:
 * 
 * ```tsx
 * import * as React from 'react';
 * import * as Icon from '@livingdesign/icons';
 * import {IconButton, TextField} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <TextField
 *       label="Full name"
 *       onChange={(event) => console.log(event)}
 *       trailing={
 *         <IconButton a11yLabel="Clear full name">
 *           <Icon.CloseCircleFill />
 *         </IconButton>
 *       }
 *     />
 *   );
 * };
 * ```
 * 
 * ### Features
 * 
 * #### Is Magic
 * 
 * Use the `isMagic` prop to indicate that the field’s value was generated or influenced by an AI agent. When enabled, `isMagic` applies “magic” styles and adds an accessible description to the input. By default this description is “AI Generated”; you can override it with the `a11yMagicLabel` prop for customization or localization.
 * 
 * ```tsx
 * <TextField
 *   isMagic
 *   a11yMagicLabel="AI Generated"
 *   label="Full name"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * #### Size
 * 
 * The Text Field comes in two sizes:
 * 
 * - `small`
 * - `large` (default)
 * 
 * Set the Text Field's size with the `size` property.
 * 
 * ```tsx
 * <TextField label="Small" size="small" />
 * <TextField label="Large" size="large" />
 * ```
 * 
 * ### Interaction
 * 
 * Configure the Text Field's value using the `value` property. Respond to changes by passing an callback handler to the `onChange` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {TextField} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [value, setValue] = React.useState('CA');
 * 
 *   return (
 *     <TextField
 *       label="Full name"
 *       onChange={(event) => setValue(event.target.value)}
 *       value={value}
 *     />
 *   );
 * };
 * ```
 * 
 * ## FAQ
 * 
 * ### How do I add inline form validation?
 * 
 * Inline form validation is not required and will not supported by LD at this time. If inline form validation is needed, it is the responsibility of the consumer to do this outside of the component and ensure that their form fields are accessible. See https://jira.walmart.com/browse/LD-991 for more details.
 */
import * as React from 'react';
import {cx, useStableId, applyCommonProps, WithIconProps} from '../common';
import {VisuallyHidden} from '../VisuallyHidden';
import {FormHelperText, FormLabel} from '../Form';
import './TextField.css';
export type TextFieldInputType =
  | 'email'
  | 'number'
  | 'password'
  | 'search'
  | 'tel'
  | 'text'
  | 'time'
  | 'url';

export type TextFieldSize = 'large' | 'small';

export interface TextFieldProps
  extends Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'onChange' | 'style'
    > {
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
  /**
   * The accessible description of the Text Field that indicates the involvement of an AI agent.
   *
   * @default "AI Generated"
   */
  a11yMagicLabel?: string;
  /**
   * If the text field is disabled.
   *
   * @default false
   */
  disabled?: boolean;
  /**
   * The error for the text field.
   */
  error?: React.ReactNode;
  /**
   * The helper text for the text field.
   */
  helperText?: React.ReactNode;
  /**
   * The id for the text field.
   */
  id?: string;
  /**
   * If the Text Field should use visual styles that indicate the involvement of an AI agent.
   *
   * @default false
   */
  isMagic?: boolean;
  /**
   * The label for the text field.
   */
  label: React.ReactNode;
  /**
   * The leading icon for the text field.
   */
  leadingIcon?: React.ReactNode;
  /**
   * The callback fired when the text field requests to change.
   */
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  /**
   * If the text field is read only.
   *
   * @default false
   */
  readOnly?: boolean;
  /**
   * The size for the text field.
   *
   * @default "large"
   */
  size?: TextFieldSize;
  /**
   * The props spread to the text field's input element.
   *
   * @default {}
   */
  textFieldProps?: React.ComponentPropsWithoutRef<'input'>;
  /**
   * The trailing content for the text field.
   */
  trailing?: React.ReactNode;
  /**
   * The type for the text field.
   *
   * @default "text"
   */
  type?: TextFieldInputType;
  /**
   * The value for the text field.
   *
   * @default ""
   */
  value?: string;
}

/**
 * Text Fields allow users to enter and edit text.
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/components/text-field/ Guidelines}
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/components/text-field/ React documentation}
 *
 */
export const TextField = React.forwardRef<HTMLInputElement, TextFieldProps>(
  (props, ref) => {
    const {
      a11yMagicLabel = 'AI Generated',
      className,
      disabled = false,
      error,
      helperText,
      id: initialId,
      isMagic = false,
      label,
      leadingIcon,
      onChange,
      readOnly = false,
      size = 'large',
      textFieldProps,
      trailing,
      type = 'text',
      value = '',
      ...rest
    } = applyCommonProps(props);

    const id = useStableId(initialId);
    const helperId = useStableId();
    const magicLabelId = useStableId();

    const hasError = !!error && !disabled && !readOnly;
    const helperContent = hasError ? error : helperText;

    const ariaDescribedBy =
      [isMagic ? magicLabelId : null, helperContent ? helperId : null]
        .filter(Boolean)
        .join(' ') || undefined;

    return (
      <div
        className={cx('ld-textfield-root', disabled && 'ld-textfield-disabled', error && 'ld-textfield-error', isMagic && 'ld-textfield-isMagic', leadingIcon && 'ld-textfield-hasLeadingIcon', readOnly && 'ld-textfield-readOnly', size === 'large' && 'ld-textfield-large', size === 'small' && 'ld-textfield-small', className)}
        {...rest}
      >
        <FormLabel
          className={'ld-textfield-label'}
          disabled={disabled}
          htmlFor={id}
          isMagic={isMagic}
          size={size}
        >
          {label}
        </FormLabel>

        <div className={'ld-textfield-container'}>
          {leadingIcon && (
            <span
              aria-hidden
              className={cx('ld-textfield-icon', 'ld-textfield-leadingIcon')}
            >
              {React.isValidElement<WithIconProps>(leadingIcon)
                ? React.cloneElement(leadingIcon, {
                    size: "medium",
                  })
                : leadingIcon}
            </span>
          )}

          <input
            aria-describedby={ariaDescribedBy}
            disabled={disabled}
            id={id}
            onChange={onChange}
            readOnly={readOnly}
            ref={ref}
            type={type}
            value={value}
            {...textFieldProps}
            className={cx('ld-textfield-value', textFieldProps?.className)}
          />

          {isMagic && (
            <VisuallyHidden
              aria-hidden
              id={magicLabelId}
            >{`${a11yMagicLabel},`}</VisuallyHidden>
          )}

          {trailing && (
            <span className={cx('ld-textfield-icon', 'ld-textfield-trailing')}>
              {trailing}
            </span>
          )}
        </div>

        {!!helperContent && (
          <FormHelperText
            className={'ld-textfield-helperText'}
            disabled={disabled}
            id={helperId}
            hasError={hasError}
          >
            {helperContent}
          </FormHelperText>
        )}
      </div>
    );
  }
);

TextField.displayName = 'TextField';
