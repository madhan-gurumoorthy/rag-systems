"""
incident_categorizer.py
-----------------------
Keyword-based incident categorization using case-insensitive regex patterns.

Design decisions:
  - Single primary category per row (first matching pattern wins).
  - Falls back to "Uncategorized" when no pattern matches.
  - Searches both `short_description` and `description` columns.
  - Patterns are compiled once at import time for performance.

To extend categories, add a new entry to CATEGORY_PATTERNS below.
"""

from __future__ import annotations

import re
from typing import Final

import pandas as pd

# ---------------------------------------------------------------------------
# Category definitions
# Order matters — the FIRST matching category is assigned.
# ---------------------------------------------------------------------------
CATEGORY_PATTERNS: Final[dict[str, list[str]]] = {
    "Eligibility Issues": [
        r"eligib",
        r"not eligible",
        r"benefit.{0,20}denied",
        r"coverage.{0,20}lapsed",
        r"enrollment.{0,20}fail",
        r"member.{0,20}not found",
    ],
    "Feed Ingestion Failures": [
        r"feed.{0,20}fail",
        r"ingest",
        r"file.{0,20}not received",
        r"data.{0,20}feed",
        r"sftp.{0,20}error",
        r"etl.{0,20}fail",
        r"import.{0,20}error",
    ],
    "Authentication Failures": [
        r"auth(entic)?",
        r"login.{0,20}fail",
        r"credential",
        r"token.{0,20}(expired|invalid)",
        r"sso.{0,20}error",
        r"unauthorized",
        r"403",
    ],
    "Performance Degradation": [
        r"slow",
        r"timeout",
        r"latency",
        r"response.{0,20}time",
        r"high.{0,20}cpu",
        r"memory.{0,20}leak",
        r"throughput",
        r"504",
    ],
    "Data Sync Issues": [
        r"sync.{0,20}fail",
        r"out.{0,5}of.{0,5}sync",
        r"mismatch",
        r"stale.{0,10}data",
        r"replication",
        r"duplicate.{0,10}record",
    ],
    "API / Integration Errors": [
        r"api.{0,20}error",
        r"integration.{0,20}fail",
        r"webhook",
        r"503",
        r"500",
        r"rest.{0,10}call",
        r"soap.{0,10}fault",
        r"downstream.{0,20}(fail|unavail)",
    ],
    "UI / Portal Issues": [
        r"portal.{0,20}(down|error|blank)",
        r"ui.{0,20}(bug|broken|crash)",
        r"page.{0,20}not.{0,5}load",
        r"white.{0,5}screen",
        r"button.{0,20}(not|fail)",
        r"display.{0,20}issue",
    ],
    "Notification Failures": [
        r"email.{0,20}(not sent|fail|bounce)",
        r"sms.{0,20}fail",
        r"notif(y|ication).{0,20}fail",
        r"alert.{0,20}not.{0,10}trigger",
    ],
    "Configuration / Deployment Issues": [
        r"config.{0,20}(wrong|missing|error)",
        r"deploy.{0,20}fail",
        r"release.{0,20}(rollback|fail)",
        r"env(ironment)?.{0,10}(mismatch|issue)",
        r"pipeline.{0,20}fail",
    ],
}

# Compile patterns once (case-insensitive, dotall for multi-line descriptions)
_COMPILED: Final[dict[str, list[re.Pattern[str]]]] = {
    category: [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]
    for category, patterns in CATEGORY_PATTERNS.items()
}

UNCATEGORIZED: Final[str] = "Uncategorized"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def categorize_text(text: str) -> str:
    """Return the first matching category for a given text, or 'Uncategorized'."""
    for category, patterns in _COMPILED.items():
        if any(p.search(text) for p in patterns):
            return category
    return UNCATEGORIZED


def categorize_row(row: pd.Series) -> str:
    """
    Categorize a single DataFrame row.

    Combines `short_description` and `description` into one string so either
    column can trigger a match.  Missing values are treated as empty strings.
    """
    combined = " ".join([
        str(row.get("short_description", "") or ""),
        str(row.get("description", "") or ""),
    ])
    return categorize_text(combined)


def apply_categorization(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a `category` column to *df* (in-place copy) using keyword matching.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain at least one of: `short_description`, `description`.

    Returns
    -------
    pd.DataFrame
        A copy of *df* with an added `category` column.
    """
    result = df.copy()
    result["category"] = result.apply(categorize_row, axis=1)
    return result


def get_all_categories() -> list[str]:
    """Return the full list of defined category names (excluding 'Uncategorized')."""
    return list(CATEGORY_PATTERNS.keys())
