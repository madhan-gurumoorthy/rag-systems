// @refresh reset

/**
 * @module WCPQueuePanel
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
import {Panel} from '../Panel';
import {WCPQueueItemCard, QueueItem} from '../WCPQueueItemCard';
import './WCPQueuePanel.css';

export type {QueueItem} from '../WCPQueueItemCard';

export interface WCPQueuePanelProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  isOpen: boolean;
  onClose: () => void;
  items: QueueItem[];
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export const WCPQueuePanel: React.FunctionComponent<WCPQueuePanelProps> = (props) => {
  const {isOpen, onClose, items, className, ...rest} = applyCommonProps(props);
  const itemCount = items.length;
  const title = `You're in line for ${itemCount} item${itemCount !== 1 ? 's' : ''}`;

  return (
    <Panel isOpen={isOpen} onClose={onClose} title={title} size="medium" position="right">
      <div className={cx('ld-wcp-queuepanel-cardList', className)} {...rest}>
        {items.map((item) => (
          <WCPQueueItemCard key={item.id} item={item} />
        ))}
      </div>
    </Panel>
  );
};
WCPQueuePanel.displayName = 'WCPQueuePanel';
