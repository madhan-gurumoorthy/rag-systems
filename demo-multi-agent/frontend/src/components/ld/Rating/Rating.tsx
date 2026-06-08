// @refresh reset

/**
 * @module Rating
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
 * ### Value
 * 
 * Set the Rating's value using the `value` property. Use numbers between `0` and `5`.
 * 
 * ```tsx
 * <Rating value={1} />
 * <Rating value={2.5} />
 * <Rating value={3.75} />
 * ```
 * 
 * ### Features
 * 
 * #### Size
 * 
 * Rating comes in two sizes:
 * 
 * - `small` (default)
 * - `large`
 * 
 * Set the Rating's size with the `size` prop:
 * 
 * ```tsx
 * <Rating size="small" />
 * <Rating size="large" />
 * ```
 * 
 * ## Accessibility
 * 
 * ### Default announcement
 * 
 * For a standalone Rating component:
 * 
 * - Use the [`VisuallyHidden` utility](/develop/react/utilities/visually-hidden/) to give the Rating stars a text-based description.
 * 
 * ```tsx
 * <Rating value={4.5} size="small" />
 * <VisuallyHidden>
 *   <p>Rated 4.5 out of 5 stars</p>
 * </VisuallyHidden>
 * ```
 * 
 * #### Example 1 - With additional adjacent related text
 * 
 * For a Rating component positioned close to visible text that hasn't been described earlier:
 * 
 * - Use the [`VisuallyHidden` utility](/develop/react/utilities/visually-hidden/) to give the Rating stars a text-based description.
 * 
 * ```tsx
 * <Rating value={4.5} size="small" />
 * <VisuallyHidden>
 *   <p>Rated 4.5 out of 5 stars</p>
 * </VisuallyHidden>
 * <div>(87 reviews)</div>
 * ```
 * 
 * #### Example 2 - With duplicate adjacent text
 * 
 * When incorporating a Rating component alongside visible text that mirrors the alt-text, make sure the screen reader ingores the redundant text. The goal is to eliminate any repetitive text from announcing which will provide an improved user experience.
 * 
 * - Add `aria-hidden="true"` to any redundant text.
 * 
 * ```tsx
 * <Rating value={4.5} size="small" />
 * <VisuallyHidden>
 *   <p>Rated 4.5 out of 5 stars</p>
 * </VisuallyHidden>
 * <div aria-hidden="true">(Rated 4.5)</div>
 * ```
 * 
 * #### Example 3 - With an adjacent related link
 * 
 * When incorporating a Rating component alongside a related link, ensure that the screen reader omits any redundant text while announcing the new text. In the example provided, the value of the neighboring link remains accessible, as it is not repetitive.
 * 
 * - Add `aria-hidden="true"` to any redundant text.
 * 
 * ```tsx
 * <Rating value={4.5} size="small" />
 * <VisuallyHidden>
 *   <p>Rated 4.5 out of 5 stars</p>
 * </VisuallyHidden>
 * <div aria-hidden="true">(4.5)</div>
 * <Link href="https://www.walmart.com/ip/424185744">87 reviews</Link>
 * ```
 * 
 * #### Guideline - Rating used when requesting feedback
 * 
 * Don't use Rating to ask for feedback. If you do use them, code them as radio buttons. Check APG's example of an [easy-to-use star rating radio group](https://www.w3.org/WAI/ARIA/apg/patterns/radio/examples/radio-rating/) for help.
 */

import * as React from 'react';
import {cx, applyCommonProps, invariant} from '../common';
import {VisuallyHidden} from '../VisuallyHidden';
import './Rating.css';
// ---------------------------------------------------------------------------
// RatingStar (inlined sub-component)
// ---------------------------------------------------------------------------

export type RatingColor = 'default' | 'white';
export type RatingSize = 'large' | 'small';
export type RatingStarVariant = 'empty' | 'filled' | 'halfFilled';

export interface RatingStarProps extends React.SVGProps<SVGSVGElement> {
  /**
   * The color for the rating star.
   *
   * @default "default"
   */
  color?: RatingColor;
  /**
   * Defines svg size.
   *
   * @default "small"
   */
  size?: RatingSize;
  /**
   * Defines the fill of the star svg.
   *
   * @default "empty"
   */
  variant?: RatingStarVariant;
}

/**
 * @private
 */
export const RatingStar = (props: RatingStarProps) => {
  const {
    className,
    color = 'default',
    size = 'small',
    variant = 'empty',
    ...rest
  } = props;

  return (
    <svg
      className={cx('ld-rating-ratingstar-star', color === 'white' && 'ld-rating-ratingstar-white', size === 'large' && 'ld-rating-ratingstar-large', size === 'small' && 'ld-rating-ratingstar-small', variant === 'empty' && 'ld-rating-ratingstar-empty', variant === 'filled' && 'ld-rating-ratingstar-filled', variant === 'halfFilled' && 'ld-rating-ratingstar-halfFilled', className)}
      viewBox="0 0 22 22"
      xmlns="http://www.w3.org/2000/svg"
      {...rest}
    >
      {variant === 'halfFilled' ? (
        <>
          <path
            d="M11 2.174a.825.825 0 0 0-.74.478L8.375 7.424l-5.662.628a.816.816 0 0 0-.463.247c-.322.34-.32.89.006 1.227l3.494 4.023-1.174 6.039a.905.905 0 0 0 .066.562c.2.43.697.61 1.108.399l5.25-3.5V2.174Z"
            className={'ld-rating-ratingstar-fill'}
          />
          <path
            className={'ld-rating-ratingstar-empty'}
            d="M11 2.002v15.5M13.895 7.082l.17.354.387.062 6.226.999c.011.001.03.008.047.034.018.026.03.063.023.106a.133.133 0 0 1-.034.073l-4.476 4.64-.274.284.08.387 1.32 6.467a.15.15 0 0 1-.017.109c-.017.027-.036.036-.048.039a.04.04 0 0 1-.015 0 .05.05 0 0 1-.017-.005L11.342 17.6 11 17.424l-.342.175-5.925 3.032a.046.046 0 0 1-.02.006c-.005 0-.01 0-.018-.003-.013-.005-.034-.017-.05-.05a.155.155 0 0 1-.01-.096l1.322-6.467.079-.387-.274-.284-4.477-4.64a.136.136 0 0 1-.035-.096c0-.041.015-.074.035-.095a.067.067 0 0 1 .037-.022l6.226-.999.387-.062.17-.354 2.831-5.892c.016-.033.036-.045.05-.05a.045.045 0 0 1 .017-.003c.004 0 .01.002.02.007a.1.1 0 0 1 .041.046l2.83 5.892Z"
          />
        </>
      ) : (
        <path d="m13.562 7.028.17.354.387.062 6.226.999c.011.002.029.008.047.034.018.026.03.063.023.106a.133.133 0 0 1-.034.073l-4.476 4.64-.274.284.079.387 1.321 6.467c.009.042 0 .08-.017.109-.018.028-.036.036-.049.04a.04.04 0 0 1-.014 0 .05.05 0 0 1-.017-.006l-5.926-3.032-.341-.175-.342.175-5.926 3.032a.046.046 0 0 1-.02.006c-.004 0-.01 0-.017-.003-.013-.004-.034-.017-.05-.05a.155.155 0 0 1-.01-.096l1.322-6.467.079-.387-.274-.284-4.477-4.64a.136.136 0 0 1-.035-.095c0-.042.014-.075.034-.096a.067.067 0 0 1 .037-.022l6.226-.999.388-.062.17-.354 2.83-5.892c.016-.033.037-.045.05-.05a.045.045 0 0 1 .018-.003c.004 0 .01.002.02.007a.1.1 0 0 1 .04.046l2.832 5.892Z" />
      )}
    </svg>
  );
};

export interface RatingProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  /**
   * The accessibility label for the rating.
   *
   * @default "{value} out of 5 stars"
   */
  a11yLabel?: string;
  /**
   * The color for the rating.
   *
   * @default "default"
   */
  color?: RatingColor;
  /**
   * Whether to display the count next to the rating stars. The displayed number will be the value.
   *
   * @default false
   */
  count?: boolean;
  /**
   * The size for the rating.
   *
   *  @default "small"
   */
  size?: RatingSize;
  /**
   * The value for the rating.
   *
   * @default 0
   */
  value?: number;
}

/**
 * Ratings provide insight into how well a product or service has been received by those who have bought or used it previously.
 *
 * {@link https://digitaltoolkit.livingdesign.walmart.com/components/rating/ Guidelines}
 * {@link https://digitaltoolkit.livingdesign.walmart.com/develop/react/components/rating/ React documentation}
 *
 */
export const Rating: React.FunctionComponent<RatingProps> = (props) => {
  const {
    a11yLabel,
    className,
    color = 'default',
    count = false,
    size = 'small',
    value = 0,
    ...rest
  } = applyCommonProps(props);

  invariant(
    a11yLabel === undefined || (typeof a11yLabel === 'string' && a11yLabel.trim().length > 0),
    '`Rating` accessibility violation. If `a11yLabel` is provided it must be a non-empty string. Omit it to use the default `"{value} out of 5 stars"` label.',
  );

  return (
    <>
      <div
        aria-hidden="true"
        className={cx('ld-rating-container', color === 'white' && 'ld-rating-white', size === 'large' && 'ld-rating-large', size === 'small' && 'ld-rating-small', className)}
        {...rest}
      >
        {[1, 2, 3, 4, 5].map((starIndex) => {
          if (value >= starIndex - 0.25) {
            return (
              <RatingStar
                key={starIndex}
                color={color}
                size={size}
                variant="filled"
              />
            );
          }
          if (value >= starIndex - 0.75) {
            return (
              <RatingStar
                key={starIndex}
                color={color}
                size={size}
                variant="halfFilled"
              />
            );
          }

          return <RatingStar key={starIndex} color={color} size={size} />;
        })}
        {count && <span className={'ld-rating-count'}>({value})</span>}
      </div>
      <VisuallyHidden>{a11yLabel ?? `${value} out of 5 stars`}</VisuallyHidden>
    </>
  );
};

Rating.displayName = 'Rating';
