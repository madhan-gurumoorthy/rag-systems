'use client';
// @refresh reset

/**
 * @module TextArea
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
 * Text Area requires a label to be accessible. Use the `label` property to add a label:
 * 
 * ```tsx
 * <TextArea label="Description" onChange={(event) => console.log(event)} />
 * ```
 * 
 * #### Helper and error text
 * 
 * Set the `helperText` prop to include descriptive helper text below the label:
 * 
 * ```tsx
 * <TextArea
 *   helperText="Summarize the product for customers"
 *   label="Description"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * Set the `error` prop to indicate to a user that the Text Area is in a bad state.
 * 
 * (Note: `error` overrides `helperText`.)
 * 
 * ```tsx
 * <TextArea
 *   error="This is wrong."
 *   label="Description"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * ### Features
 * #### Is Magic
 * 
 * Use the `isMagic` prop to indicate that the Text area's value was generated or influenced by an AI agent. When enabled, `isMagic` applies "magic" styles and adds an accessible description to the input. By default this description is "AI Generated"; you can override it with the `a11yMagicLabel` prop for customization or localization.
 * 
 * ```tsx
 * <TextArea
 *   isMagic
 *   a11yMagicLabel="AI Generated"
 *   label="Description"
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * 
 * #### Max length
 * 
 * Use the `maxLength` property to limit the number of characters a user can input. A character count will be displayed if this prop is set.
 * 
 * ```tsx
 * <TextArea
 *   label="Description"
 *   maxLength={100}
 *   onChange={(event) => console.log(event)}
 * />
 * ```
 * 
 * #### Size
 * 
 * The Text Area comes in two sizes:
 * 
 * - `small`
 * - `large` (default)
 * 
 * Set the Text Area's size with the `size` prop:
 * 
 * ```tsx
 * <TextArea
 *    label="Small"
 *    onChange={(event) => console.log(event)}
 *    size="small"
 * />
 * <TextArea
 *    label="Large"
 *    onChange={(event) => console.log(event)}
 *    size="large"
 * />
 * ```
 * 
 * ### Interaction
 * 
 * Configure the Text Area's value using the `value` property. Respond to changes by passing an callback handler to the `onChange` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {TextArea} from '@livingdesign/react';
 * 
 * export default () => {
 *   const [value, setValue] = React.useState('CA');
 * 
 *   return (
 *     <TextArea
 *       label="Description"
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
import {cx, useStableId, debounce, applyCommonProps} from '../common';
import {VisuallyHidden} from '../VisuallyHidden';
import {FormHelperText, FormLabel} from '../Form';
import './TextArea.css';
export type TextAreaSize = 'large' | 'small';

export interface TextAreaProps
  extends Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'onChange' | 'style'
    > {
  /**
   * The accessible description of the Text Area that indicates the involvement of an AI agent.
   *
   * @default "AI Generated"
   */
  a11yMagicLabel?: string;
  /**
   * If the text area is disabled.
   *
   * @default false
   */
  disabled?: boolean;
  /**
   * The error for the text area.
   */
  error?: React.ReactNode;
  /**
   * The helper text for the text area.
   */
  helperText?: React.ReactNode;
  /**
   * The id for the text area.
   */
  id?: string;
  /**
   * If the Text Area should use visual styles that indicate the involvement of an AI agent.
   *
   * @default false
   */
  isMagic?: boolean;
  /**
   * The label for the text area.
   */
  label: React.ReactNode;
  /**
   * The maximum length for the text area (includes character counter).
   */
  maxLength?: number;
  /**
   * The max length accessible announcement for the text area.
   *
   * @default `${props.maxLength - props.value.length} characters left.`
   */
  maxLengthA11yAnnouncement?: string;
  /**
   * The callback fired when the text area requests to change.
   */
  onChange: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
  /**
   * If the text area is read only.
   *
   * @default false
   */
  readOnly?: boolean;
  /**
   * The size for the text area.
   *
   * @default "large"
   */
  size?: TextAreaSize;
  /**
   * The props spread to the textarea's textarea element.
   *
   * @default {}
   */
  textAreaProps?: React.ComponentPropsWithoutRef<'textarea'>;
  /**
   * The value for the text area.
   *
   * @default ""
   */
  value?: string;
}

/**
 * Text Areas allow for the input of freeform, often multi-line, text.
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/components/text-area/ Guidelines}
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/components/text-area/ React documentation}
 *
 */
export const TextArea = React.forwardRef<HTMLTextAreaElement, TextAreaProps>(
  (props, ref) => {
    const {
      a11yMagicLabel = 'AI Generated',
      className,
      disabled = false,
      error,
      helperText,
      id: initialId,
      label,
      maxLength,
      maxLengthA11yAnnouncement,
      onChange,
      isMagic = false,
      readOnly = false,
      size = 'large',
      textAreaProps,
      value = '',
      ...rest
    } = applyCommonProps(props);

    const id = useStableId(initialId);
    const magicLabelId = useStableId();
    const helperId = useStableId();

    const [screenReaderMessage, setScreenReaderMessage] = React.useState('');

    const setDelayedScreenReaderMessage = React.useMemo(
      () => debounce(setScreenReaderMessage, 1500),
      []
    );

    const handleInteraction = React.useCallback(
      (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        if (!maxLength) {
          return;
        }

        setDelayedScreenReaderMessage(
          `${maxLength - e.target.value.length} characters left.`
        );
      },
      [maxLength, setDelayedScreenReaderMessage]
    );

    const hasError = !!error && !disabled && !readOnly;
    const hasHelperContent = !!(hasError || helperText || maxLength);

    const ariaDescribedBy =
      [isMagic ? magicLabelId : null, hasHelperContent ? helperId : null]
        .filter(Boolean)
        .join(' ') || undefined;

    return (
      <div
        className={cx('ld-textarea-root', disabled && 'ld-textarea-disabled', hasError && 'ld-textarea-error', readOnly && 'ld-textarea-readOnly', isMagic && 'ld-textarea-isMagic', size === 'large' && 'ld-textarea-large', size === 'small' && 'ld-textarea-small', className)}
        {...rest}
      >
        <FormLabel
          className={'ld-textarea-label'}
          disabled={disabled}
          htmlFor={id}
          isMagic={isMagic}
          size={size}
        >
          {label}
        </FormLabel>

        <div className={'ld-textarea-container'}>
          <textarea
            aria-describedby={ariaDescribedBy}
            disabled={disabled}
            id={id}
            maxLength={maxLength}
            onChange={(e) => {
              handleInteraction(e);
              onChange(e);
            }}
            readOnly={readOnly}
            ref={ref}
            value={value}
            {...textAreaProps}
            className={cx('ld-textarea-value', textAreaProps?.className)}
          />
        </div>

        <div id={helperId}>
          {hasHelperContent && (
            <div className={'ld-textarea-helperTextContainer'}>
              <FormHelperText disabled={disabled} hasError={hasError}>
                {hasError ? error : helperText}
              </FormHelperText>

              {maxLength && (
                <span aria-hidden className={'ld-textarea-maxLength'}>
                  {value.length} / {maxLength}
                </span>
              )}
            </div>
          )}

          {/* NOTE: we have moved `aria-live` implementation outside of the `FormHelperText`.
          `aria-live` is known to have screen reader issues when the element is added dynamically.
          since the element was moved, the `helperId` also had to be moved so the screen reader
          message would be read by the `aria-describedby`. */}
          <VisuallyHidden aria-atomic aria-live="polite" id="screenReader">
            {screenReaderMessage}
          </VisuallyHidden>
          {isMagic && (
            <VisuallyHidden
              aria-hidden
              id={magicLabelId}
            >{`${a11yMagicLabel},`}</VisuallyHidden>
          )}
        </div>
      </div>
    );
  }
);

TextArea.displayName = 'TextArea';
