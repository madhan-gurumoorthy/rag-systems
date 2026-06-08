// @refresh reset

/**
 * @module WCPOrderStatusBanner
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
import { useState } from "react";
import { Link } from '../Link';
import { CloseIcon } from '../Icons';
import './WCPOrderStatusBanner.css';

export function WCPOrderStatusBanner() {
  const [isClosed, setIsClosed] = useState(false);

  if (isClosed) return null;

  return (
    <div className="ld-wcp-order-status-banner-root" role="status" aria-live="polite">
      {/* Order icon */}
      <img
        src="https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F5f02b529221349099118d275e7e1d748"
        alt="Order status"
        width="24"
        height="24"
        className="ld-wcp-order-status-banner-icon"
      />

      <div className="ld-wcp-order-status-banner-content">
        <span className="ld-wcp-order-status-banner-text">
          Your order is on the way
        </span>
        <span className="ld-wcp-order-status-banner-separator">
          |
        </span>
        <span className="ld-wcp-order-status-banner-delivery">
          Arrives tomorrow by 8pm
        </span>
        <span className="ld-wcp-order-status-banner-separator">
          |
        </span>
        <Link href="#">Track</Link>
      </div>

      <button
        aria-label="Dismiss order status"
        onClick={() => setIsClosed(true)}
        className="ld-wcp-order-status-banner-dismiss"
      >
        <CloseIcon size="small" />
      </button>
    </div>
  );
}
WCPOrderStatusBanner.displayName = 'WCPOrderStatusBanner';
