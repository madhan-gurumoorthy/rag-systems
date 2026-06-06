"""
incident_processor.py
---------------------
Handles Excel ingestion, cleaning, categorization, and monthly aggregation
of raw incident log data.

Expected Excel columns:
    sys_created_on      – incident creation timestamp (any parseable format)
    short_description   – brief summary of the incident
    description         – full incident description
    state               – current state/status of the incident (optional)

Outputs:
    categorized_df  – row-level DataFrame with a `category` and `month` column
    monthly_df      – pivot table: rows = month, columns = category, values = count
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from incident_categorizer import apply_categorization, UNCATEGORIZED, get_all_categories

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS: list[str] = ["sys_created_on", "short_description"]
OPTIONAL_COLUMNS: list[str] = ["description", "state"]
DATE_COLUMN: str = "sys_created_on"
MONTH_COLUMN: str = "month"
CATEGORY_COLUMN: str = "category"


# ---------------------------------------------------------------------------
# Step 1 – Load
# ---------------------------------------------------------------------------

def load_excel(file_path: str | Path, sheet_name: str | int = 0) -> pd.DataFrame:
    """
    Load a raw incident log Excel file into a DataFrame.

    Parameters
    ----------
    file_path : str | Path
        Path to the .xlsx or .xls file.
    sheet_name : str | int
        Sheet name or index to read (default: first sheet).

    Returns
    -------
    pd.DataFrame
        Raw DataFrame with original column names preserved.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If required columns are missing from the sheet.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Incident log not found: {path}")

    logger.info("Loading Excel file: %s (sheet=%s)", path, sheet_name)
    df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    logger.info("Loaded %d rows, %d columns.", len(df), len(df.columns))

    _validate_columns(df, path)
    return df


def _validate_columns(df: pd.DataFrame, path: Path) -> None:
    """Raise ValueError if required columns are absent."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in '{path}': {missing}. "
            f"Found columns: {list(df.columns)}"
        )


# ---------------------------------------------------------------------------
# Step 2 – Clean
# ---------------------------------------------------------------------------

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse dates, strip whitespace, and fill missing text columns.

    Returns a cleaned copy — original DataFrame is not modified.
    """
    df = df.copy()

    # Parse the date column
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
    unparsed = df[DATE_COLUMN].isna().sum()
    if unparsed > 0:
        logger.warning("%d rows have unparseable '%s' values and will be dropped.", unparsed, DATE_COLUMN)
        df = df.dropna(subset=[DATE_COLUMN])

    # Normalise text columns
    for col in ["short_description", "description", "state"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    logger.info("Cleaned dataframe: %d rows remain.", len(df))
    return df


# ---------------------------------------------------------------------------
# Step 3 – Categorize
# ---------------------------------------------------------------------------

def categorize_incidents(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add `category` and `month` columns.

    `month` uses pandas Period ('M') so it sorts correctly and serialises as
    'YYYY-MM'.

    Returns a new DataFrame.
    """
    df = apply_categorization(df)                             # adds `category`
    df[MONTH_COLUMN] = df[DATE_COLUMN].dt.to_period("M")     # e.g. Period('2025-03', 'M')
    return df


# ---------------------------------------------------------------------------
# Step 4 – Aggregate
# ---------------------------------------------------------------------------

def aggregate_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot categorized incidents into a monthly count matrix.

    Returns
    -------
    pd.DataFrame
        Index   : month (Period[M], sorted ascending)
        Columns : one column per category (incl. 'Uncategorized') + 'total'
        Values  : incident counts (int, NaN → 0)

    Example
    -------
    >>> monthly_df.head()
    category        API / Integration Errors  Eligibility Issues  ...  total
    month
    2025-01                                3                  12  ...     42
    2025-02                                7                   8  ...     39
    """
    all_categories = get_all_categories() + [UNCATEGORIZED]

    # Count incidents per (month, category)
    counts = (
        df.groupby([MONTH_COLUMN, CATEGORY_COLUMN])
        .size()
        .reset_index(name="count")
    )

    # Pivot to wide format
    pivot = counts.pivot_table(
        index=MONTH_COLUMN,
        columns=CATEGORY_COLUMN,
        values="count",
        aggfunc="sum",
        fill_value=0,
    )

    # Ensure every defined category appears even if it had zero incidents
    for cat in all_categories:
        if cat not in pivot.columns:
            pivot[cat] = 0

    pivot = pivot[sorted(pivot.columns)]          # stable column order
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_index()                    # chronological order

    # Convert Period index to string for easier downstream handling
    pivot.index = pivot.index.astype(str)
    pivot.index.name = "month"

    logger.info("Monthly aggregation complete: %d months, %d categories.", len(pivot), len(pivot.columns) - 1)
    return pivot


# ---------------------------------------------------------------------------
# Convenience pipeline
# ---------------------------------------------------------------------------

def process_incident_log(
    file_path: str | Path,
    sheet_name: str | int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run the full processing pipeline in one call.

    Returns
    -------
    categorized_df : pd.DataFrame
        Row-level data with `category` and `month` columns added.
    monthly_df : pd.DataFrame
        Aggregated monthly pivot table (counts per category).
    """
    raw_df = load_excel(file_path, sheet_name=sheet_name)
    clean_df = clean_dataframe(raw_df)
    categorized_df = categorize_incidents(clean_df)
    monthly_df = aggregate_by_month(categorized_df)
    return categorized_df, monthly_df


# ---------------------------------------------------------------------------
# Utility – generate a summary text for a given month row
# (used by milvus_store to build documents for vector storage)
# ---------------------------------------------------------------------------

def monthly_row_to_text(month: str, row: pd.Series) -> str:
    """
    Convert one row of the monthly pivot table into a human-readable
    summary string suitable for embedding and similarity search.

    Example output:
        Monthly Incident Summary — 2025-03
        Total incidents: 47
        Eligibility Issues: 12
        Feed Ingestion Failures: 8
        ...
    """
    lines = [f"Monthly Incident Summary — {month}", f"Total incidents: {int(row.get('total', 0))}"]
    for col in sorted(row.index):
        if col != "total":
            lines.append(f"{col}: {int(row[col])}")
    return "\n".join(lines)
