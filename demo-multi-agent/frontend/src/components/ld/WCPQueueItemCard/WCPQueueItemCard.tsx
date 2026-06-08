// @refresh reset

/**
 * @module WCPQueueItemCard
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
import {WCPTimerView, WCPTimerBadgeColor, useWCPTimer} from '../WCPTimerView';
import {Button} from '../Button';
import {LinkButton} from '../LinkButton';
import './WCPQueueItemCard.css';

export interface QueueItem {
  id: string;
  productImage?: string;
  productImageAlt?: string;
  description: string;
  price: string;
  originalPrice?: string;
  endTime: Date | number | string;
  onView?: () => void;
  onLeave?: () => void;
}

export interface WCPQueueItemCardProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  item: QueueItem;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export const WCPQueueItemCard: React.FunctionComponent<WCPQueueItemCardProps> = (props) => {
  const {item, className, ...rest} = applyCommonProps(props);
  const timer = useWCPTimer(item.endTime);

  let badgeColor: WCPTimerBadgeColor = 'blue';
  if (timer.urgency === 'critical') badgeColor = 'negative';
  else if (timer.urgency === 'warning') badgeColor = 'spark';

  return (
    <div className={cx('ld-wcp-queueitemcard-card', className)} {...rest}>
      <div className="ld-wcp-queueitemcard-cardContent">
        <div className="ld-wcp-queueitemcard-timerRow">
          <WCPTimerView endTime={item.endTime} variant="badge" badgeColor={badgeColor} size="small" />
          <span className="ld-wcp-queueitemcard-timerLabel">estimated wait</span>
        </div>
        <div className="ld-wcp-queueitemcard-productRow">
          {item.productImage ? (
            <img src={item.productImage} alt={item.productImageAlt || item.description} className="ld-wcp-queueitemcard-productImg" />
          ) : (
            <div className="ld-wcp-queueitemcard-productImgPlaceholder" />
          )}
          <span className="ld-wcp-queueitemcard-productDescription">{item.description}</span>
          <div className="ld-wcp-queueitemcard-pricing">
            <span className="ld-wcp-queueitemcard-currentPrice">{item.price}</span>
            {item.originalPrice && <span className="ld-wcp-queueitemcard-originalPrice">{item.originalPrice}</span>}
          </div>
        </div>
        <div className="ld-wcp-queueitemcard-actionsRow">
          {item.onLeave && <LinkButton onClick={item.onLeave}>Leave line</LinkButton>}
          {item.onView && <Button variant="secondary" size="small" onClick={item.onView}>View</Button>}
        </div>
      </div>
    </div>
  );
};
WCPQueueItemCard.displayName = 'WCPQueueItemCard';
