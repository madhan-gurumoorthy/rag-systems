// @refresh reset

/**
 * @module FormGroup
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
 * The Form Group accepts form field elements through the `children` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Checkbox, FormGroup} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <FormGroup>
 *       <Checkbox label="Banana" />
 *       <Checkbox label="Apple" />
 *       <Checkbox label="Cookie" />
 *     </FormGroup>
 *   );
 * };
 * ```
 * 
 * #### Label
 * 
 * Set the `label` prop to include a label at the top of the Form Group:
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Checkbox, FormGroup} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <FormGroup label="What monster are you?">
 *       <Checkbox label="Banana" />
 *       <Checkbox label="Apple" />
 *       <Checkbox label="Cookie" />
 *     </FormGroup>
 *   );
 * };
 * ```
 * 
 * #### Helper and error text
 * 
 * Set the `helperText` prop to include descriptive helper text below the label.
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Checkbox, FormGroup} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <FormGroup
 *       label="What kind of monster are you?"
 *       helperText="Pick one or more"
 *     >
 *       <Checkbox label="Banana" />
 *       <Checkbox label="Apple" />
 *       <Checkbox label="Cookie" />
 *     </FormGroup>
 *   );
 * };
 * ```
 * 
 * Set the `error` prop to indicate to a user that the Form Group is in a bad state.
 * 
 * (Note: `error` overrides `helperText`.)
 * 
 * ```tsx
 * import * as React from 'react';
 * import {Checkbox, FormGroup} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <FormGroup label="What kind of monster are you?" error="Something is wrong">
 *       <Checkbox label="Banana" />
 *       <Checkbox label="Apple" />
 *       <Checkbox label="Cookie" />
 *     </FormGroup>
 *   );
 * };
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import {FormHelperText} from '../Form';
import './FormGroup.css';

export interface FormGroupProps
  extends Omit<
      React.ComponentPropsWithoutRef<'fieldset'>,
      'className' | 'style'
    > {
  /**
   * The content for the form group.
   */
  children: React.ReactNode;
  /**
   * The error for the form group.
   */
  error?: React.ReactNode;
  /**
   * The helper text for the form group.
   */
  helperText?: React.ReactNode;
  /**
   * The label for the form group.
   */
  label?: React.ReactNode;
}

/**
 * Form Groups let you create a list of grouped form elements. The form elements can be radio buttons, checkboxes, text area, etc.
 * *
 */
export const FormGroup: React.FunctionComponent<FormGroupProps> = (props) => {
  const {children, className, error, helperText, label, ...rest} = applyCommonProps(props);

  // Safari/WebKit bug: unexpected vertical empty space at the bottom of the fieldset
  // when <fieldset> and <legend> elements are used together inside flex container with flex-direction: column.
  // Reference: {@link https://bugs.webkit.org/show_bug.cgi?id=245402}
  return (
    <fieldset className={cx('ld-formgroup-formGroup', className)} {...rest}>
      {(error || helperText || label) && (
        <legend className={'ld-formgroup-formGroupLegend'}>
          {label && <span className={'ld-formgroup-title'}>{label}</span>}

          {(error || helperText) && (
            <div className={'ld-formgroup-helperTextContainer'}>
              <FormHelperText hasError={!!error}>
                {error || helperText}
              </FormHelperText>
            </div>
          )}
        </legend>
      )}

      {React.Children.map(children, (child) => {
        if (!React.isValidElement(child)) {
          return null;
        }
        return <div className={'ld-formgroup-formGroupRow'}>{child}</div>;
      })}
    </fieldset>
  );
};

FormGroup.displayName = 'FormGroup';
