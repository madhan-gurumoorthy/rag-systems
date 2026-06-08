// @refresh reset

/**
 * @module WCPItemTile
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
 */

import * as React from 'react';
import {cx, applyCommonProps} from '../common';
import {WCPFlag, WCPFlagVariant} from '../WCPFlag';
import {WCPHeartView} from '../WCPHeartView';
import './WCPItemTile.css';

export type ItemTileBadgeType = 'bestseller' | 'deal' | 'popular' | 'rollback' | 'clearance';

const BADGE_VARIANT_MAP: Record<ItemTileBadgeType, WCPFlagVariant> = {
  bestseller: 'brand-subtle',
  deal: 'confidence',
  popular: 'confidence',
  rollback: 'savings-bold',
  clearance: 'urgent',
};

export interface WCPItemTileProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  image: string;
  name: string;
  price: string;
  cents: string;
  originalPrice?: string;
  pricePrefix?: string;
  priceSuffix?: string;
  badge?: { label: string; type: ItemTileBadgeType };
  hearted?: boolean;
  onHeartChange?: (hearted: boolean) => void;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export const WCPItemTile: React.FunctionComponent<WCPItemTileProps> = (props) => {
  const {image, name, price, cents, originalPrice, pricePrefix, priceSuffix, badge, hearted, onHeartChange, className, ...rest} = applyCommonProps(props);
  const isSavings = !!pricePrefix;
  const [hasImageError, setHasImageError] = React.useState(false);
  const hasImage = !!image?.trim() && !hasImageError;

  React.useEffect(() => {
    setHasImageError(false);
  }, [image]);

  return (
    <div className={cx('ld-wcp-itemtile-tile', className)} {...rest}>
      {badge && (
        <div className="ld-wcp-itemtile-flagWrap">
          <WCPFlag label={badge.label} variant={BADGE_VARIANT_MAP[badge.type]} />
        </div>
      )}
      <div className="ld-wcp-itemtile-heartWrap">
        <WCPHeartView size="small" calloutPosition="top" {...(hearted !== undefined ? {activated: hearted, onChange: onHeartChange} : {})} />
      </div>
      <div className="ld-wcp-itemtile-imageWrapper">
        {hasImage ? (
          <img
            src={image}
            alt={name}
            className="ld-wcp-itemtile-image"
            onError={() => setHasImageError(true)}
          />
        ) : (
          <div className="ld-wcp-itemtile-imagePlaceholder" aria-hidden="true">
            <span className="ld-wcp-itemtile-imagePlaceholderText">{name?.trim() || 'Placeholder'}</span>
          </div>
        )}
      </div>
      <div className="ld-wcp-itemtile-body">
        <div className={cx('ld-wcp-itemtile-priceRow', isSavings && 'ld-wcp-itemtile-priceRowSavings')}>
          {pricePrefix && <span className="ld-wcp-itemtile-prefix">{pricePrefix} </span>}
          <span className="ld-wcp-itemtile-dollarSign">$</span>
          <span className="ld-wcp-itemtile-price">{price}</span>
          <span className="ld-wcp-itemtile-cents">{cents}</span>
          {priceSuffix && <span className="ld-wcp-itemtile-suffix">{priceSuffix}</span>}
        </div>
        {originalPrice && <div className="ld-wcp-itemtile-originalPrice">{originalPrice}</div>}
        <p className="ld-wcp-itemtile-name">{name}</p>
      </div>
    </div>
  );
};
WCPItemTile.displayName = 'WCPItemTile';
