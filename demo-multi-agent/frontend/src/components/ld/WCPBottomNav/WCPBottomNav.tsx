// @refresh reset

/**
 * @module WCPBottomNav
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
import {cx} from '../common';
import './WCPBottomNav.css';
const { useState, useEffect, useRef } = React;

/* ------------------------------------------------------------------ */
/*  Inline SVG icons                                                  */
/* ------------------------------------------------------------------ */

const StoreIcon = ({ color = 'currentColor' }: { color?: string }) => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M4 7L2 12V13C2 13.7956 2.31607 14.5587 2.87868 15.1213C3.44129 15.6839 4.20435 16 5 16C5.79565 16 6.55871 15.6839 7.12132 15.1213C7.68393 14.5587 8 13.7956 8 13C8 13.7956 8.31607 14.5587 8.87868 15.1213C9.44129 15.6839 10.2043 16 11 16C11.7957 16 12.5587 15.6839 13.1213 15.1213C13.6839 14.5587 14 13.7956 14 13C14 13.7956 14.3161 14.5587 14.8787 15.1213C15.4413 15.6839 16.2043 16 17 16C17.7957 16 18.5587 15.6839 19.1213 15.1213C19.6839 14.5587 20 13.7956 20 13V12L18 7H4Z"
      stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
    />
    <path d="M4 7V5C4 4.44772 4.44772 4 5 4H19C19.5523 4 20 4.44772 20 5V7" stroke={color} strokeWidth="1.5" />
    <path d="M5 16V20H19V16" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    <path d="M9 20V17H13V20" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const HeartIcon = ({ color = 'currentColor' }: { color?: string }) => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M12 21C12 21 3 15.5 3 9C3 7.4087 3.63214 5.88258 4.75736 4.75736C5.88258 3.63214 7.4087 3 9 3C10.2 3 11.3 3.4 12.2 4.1L12 4.3L11.8 4.1C12.7 3.4 13.8 3 15 3C16.5913 3 18.1174 3.63214 19.2426 4.75736C20.3679 5.88258 21 7.4087 21 9C21 15.5 12 21 12 21Z"
      stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
    />
  </svg>
);

const UserIcon = ({ color = 'currentColor' }: { color?: string }) => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="12" cy="8" r="4" stroke={color} strokeWidth="1.5" />
    <path
      d="M5 20C5 17.2386 8.13401 15 12 15C15.866 15 19 17.2386 19 20"
      stroke={color} strokeWidth="1.5" strokeLinecap="round"
    />
  </svg>
);

/* ------------------------------------------------------------------ */
/*  Tab indicator x-offset mapping                                    */
/* ------------------------------------------------------------------ */

const TAB_X: Record<string, string> = {
  shop: '-72px',
  heart: '0px',
  user: '72px',
};

/* ------------------------------------------------------------------ */
/*  BottomNav                                                         */
/* ------------------------------------------------------------------ */

interface BottomNavProps {
  activeTab?: 'shop' | 'heart' | 'user';
  onTabChange?: (tab: 'shop' | 'heart' | 'user') => void;
  /** Renders in-flow (not fixed) for use inside a patterns/documentation page */
  contained?: boolean;
}

export function WCPBottomNav({ activeTab = 'shop', onTabChange, contained = false }: BottomNavProps) {
  const [visualTab, setVisualTab] = useState<'shop' | 'heart' | 'user'>(activeTab);
  const [isMoving, setIsMoving] = useState(false);
  const moveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setVisualTab(activeTab);
  }, [activeTab]);

  const handleTabClick = (tab: 'shop' | 'heart' | 'user') => {
    if (tab === visualTab) return;

    if (moveTimerRef.current) clearTimeout(moveTimerRef.current);

    setVisualTab(tab);
    setIsMoving(true);
    onTabChange?.(tab);

    moveTimerRef.current = setTimeout(() => setIsMoving(false), 400);
  };

  const indicatorX = TAB_X[visualTab];

  const activeColor = '#0071dc';
  const inactiveColor = '#74767c';

  return (
    <div
      className={cx(
        'ld-wcp-bottom-nav-root',
        contained ? 'ld-wcp-bottom-nav-root--contained' : 'ld-wcp-bottom-nav-root--fixed',
      )}
    >
      <div className="ld-wcp-bottom-nav-bar">
        {/* Tab bar: 3 tabs centered */}
        <div className="ld-wcp-bottom-nav-tabs">
          {/* Sliding indicator */}
          <div
            className="ld-wcp-bottom-nav-indicator"
            style={{ transform: `translateX(calc(-50% + ${indicatorX}))` }}
          />

          {/* Shop tab */}
          <button
            onClick={() => handleTabClick('shop')}
            aria-label="Shop"
            className="ld-wcp-bottom-nav-tab"
          >
            <StoreIcon color={visualTab === 'shop' ? activeColor : inactiveColor} />
          </button>

          {/* Heart tab */}
          <button
            onClick={() => handleTabClick('heart')}
            aria-label="My Items"
            className="ld-wcp-bottom-nav-tab"
          >
            <HeartIcon color={visualTab === 'heart' ? activeColor : inactiveColor} />
          </button>

          {/* User tab */}
          <button
            onClick={() => handleTabClick('user')}
            aria-label="Account"
            className="ld-wcp-bottom-nav-tab"
          >
            <UserIcon color={visualTab === 'user' ? activeColor : inactiveColor} />
          </button>
        </div>
      </div>
    </div>
  );
}
WCPBottomNav.displayName = 'WCPBottomNav';
