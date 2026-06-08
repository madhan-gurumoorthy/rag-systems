// @refresh reset

/**
 * @module WCPSearchFilterBar
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
import { useState } from 'react';
import { Button } from '../Button';
import './WCPSearchFilterBar.css';

interface SearchFilterBarProps {
  chips: readonly string[];
}

/* Inline SVG: filter / sliders icon */
function FilterIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z"
        fill="currentColor"
      />
    </svg>
  );
}

/* Inline SVG: sort / sorting arrows */
function SortIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M3 18h6v-2H3v2zM3 6v2h18V6H3zm0 7h12v-2H3v2z"
        fill="currentColor"
      />
    </svg>
  );
}

export function WCPSearchFilterBar({ chips }: SearchFilterBarProps) {
  const [activeFilters, setActiveFilters] = useState<string[]>([]);

  const toggleFilter = (filter: string) => {
    setActiveFilters((prev) =>
      prev.includes(filter)
        ? prev.filter((f) => f !== filter)
        : [...prev, filter]
    );
  };

  return (
    <div className="ld-wcp-search-filter-bar-root">
      {/* All Filters */}
      <Button
        leading={<FilterIcon />}
        aria-label="All filters"
        size="small"
        variant="secondary"
      >
        All
      </Button>

      {/* Sort */}
      <Button
        leading={<SortIcon />}
        aria-label="Sort"
        size="small"
        variant="secondary"
      >
        Sort
      </Button>

      {/* Dynamic filter chips */}
      {chips.map((chip) => (
        <Button
          key={chip}
          variant={activeFilters.includes(chip) ? 'primary' : 'secondary'}
          size="small"
          onClick={() => toggleFilter(chip)}
        >
          {chip}
        </Button>
      ))}
    </div>
  );
}
WCPSearchFilterBar.displayName = 'WCPSearchFilterBar';
