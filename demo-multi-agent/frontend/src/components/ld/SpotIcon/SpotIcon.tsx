// @refresh reset

/**
 * @module SpotIcon
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
 * Spot Icon's accepts an icon through the `children` prop:
 * 
 * ```tsx
 * import * as React from 'react';
 * import * as Icon from '@livingdesign/icons';
 * import {SpotIcon} from '@livingdesign/react';
 * 
 * export default () => {
 *   return (
 *     <SpotIcon>
 *       <Icon.Globe />
 *     </SpotIcon>
 *   );
 * };
 * ```
 * 
 * ### Features
 * 
 * #### Color
 * 
 * Spot icon has two colors:
 * 
 * ```tsx
 * <SpotIcon color="brand" /> // default
 * <SpotIcon color="neutral" />
 * ```
 * 
 * #### Size
 * 
 * Spot Icon has two sizes:
 * 
 * ```tsx
 * <SpotIcon size="small" /> // default
 * <SpotIcon size="large" />
 * ```
 */

import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import './SpotIcon.css';
export type SpotIconColor = 'brand' | 'neutral';

export type SpotIconSize = 'large' | 'small';

export interface SpotIconProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /**
   * The icon for the spot icon.
   */
  children: React.ReactElement;
  /**
   * The color for the spot icon.
   *
   * @default "brand"
   */
  color?: SpotIconColor;
  /**
   * The size for the spot icon.
   *
   * @default "small"
   */
  size?: SpotIconSize;
}

const spotIconIconSize = {
  large: "large",
  small: "medium",
};

/**
 * Spot Icons are decorative elements that add visual interest to messaging or other screen elements such as list items.
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/components/spot-icon/ Guidelines}
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/components/spot-icon/ React documentation}
 *
 */
export const SpotIcon: React.FunctionComponent<SpotIconProps> = (props) => {
  const {
    children,
    className,
    color = 'brand',
    size = 'small',
    ...rest
  } = applyCommonProps(props);

  const child = React.Children.only(children);

  return (
    <div
      className={cx('ld-spoticon-spotIcon', color === 'brand' && 'ld-spoticon-brand', color === 'neutral' && 'ld-spoticon-neutral', size === 'small' && 'ld-spoticon-small', size === 'large' && 'ld-spoticon-large', className)}
      {...rest}
    >
      {React.cloneElement(child, {
        size: spotIconIconSize[size],
      })}
    </div>
  );
};
