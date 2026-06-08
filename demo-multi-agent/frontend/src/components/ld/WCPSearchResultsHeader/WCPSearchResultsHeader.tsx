// @refresh reset

/**
 * @module WCPSearchResultsHeader
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
import './WCPSearchResultsHeader.css';

interface SearchResultsHeaderProps {
  query: string;
  onBack?: () => void;
}

/* Inline SVG: chevron-left */
function ChevronLeftIcon() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12l4.58-4.59z"
        fill="currentColor"
      />
    </svg>
  );
}

/* Inline SVG: search */
function SearchIcon() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="7" stroke="#74767C" strokeWidth="2" />
      <path d="M16.5 16.5L21 21" stroke="#74767C" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function WCPSearchResultsHeader({ query, onBack }: SearchResultsHeaderProps) {
  return (
    <div className="ld-wcp-search-results-header-root">
      <div className="ld-wcp-search-results-header-inner">
        {/* Back button */}
        <button
          type="button"
          onClick={onBack}
          aria-label="Go back"
          className="ld-wcp-search-results-header-back-btn"
        >
          <ChevronLeftIcon />
        </button>

        {/* Search pill */}
        <div className="ld-wcp-search-results-header-pill-wrap">
          <div className="ld-wcp-search-results-header-pill-border">
            <div className="ld-wcp-search-results-header-pill">
              <div className="ld-wcp-search-results-header-search-icon">
                <SearchIcon />
              </div>
              <span className="ld-wcp-search-results-header-query">
                {query}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
WCPSearchResultsHeader.displayName = 'WCPSearchResultsHeader';
