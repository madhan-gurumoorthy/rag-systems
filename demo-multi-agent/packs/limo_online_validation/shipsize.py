"""Shipsize derivation for the LIMO Online Eligibility pack.

Computes ``girth`` from unit dimensions and looks up the corresponding
shipsize bracket per the SOP table.  The result is the *derived*
shipsize used to compare against the Consolidated FC response.

Formula:    girth = (2 * unit_height) + (2 * unit_width) + unit_length
Lookup:     bracket on girth + unit_weight per the SOP matrix.

All inputs may arrive as ``None`` (upstream attribute missing).  When
any required dimension is missing the function returns
``shipsize_derived = None`` with a logic note so the decision matrix
can surface ``SHIPSIZE_INPUTS_MISSING``.
"""
from __future__ import annotations

from typing import Any, Optional

# SOP shipsize brackets.  Each entry: (max_girth_in, max_weight_lb, code).
# Order matters — first match wins.  Use ``float('inf')`` for open-ended.
_BRACKETS: tuple[tuple[float, float, str], ...] = (
    (40.0,  1.0,   "TINY"),
    (60.0,  15.0,  "SMALL"),
    (108.0, 50.0,  "MEDIUM"),
    (130.0, 70.0,  "LARGE"),
    (165.0, 150.0, "XLARGE"),
    (float("inf"), float("inf"), "FREIGHT"),
)


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def derive_shipsize(unit_height: Any = None,
                    unit_length: Any = None,
                    unit_width:  Any = None,
                    unit_weight: Any = None,
                    **_: Any) -> dict[str, Any]:
    """Return derived shipsize, girth and a logic note.

    Outcome codes:
      * ``SHIPSIZE_DERIVED``         — all inputs present, bracket found
      * ``SHIPSIZE_INPUTS_MISSING``  — one or more dimensions missing
    """
    h = _to_float(unit_height)
    l = _to_float(unit_length)
    w = _to_float(unit_width)
    wt = _to_float(unit_weight)

    missing = [
        name for name, val in (
            ("unit_height", h),
            ("unit_length", l),
            ("unit_width",  w),
            ("unit_weight", wt),
        ) if val is None
    ]
    if missing:
        return {
            "outcome": "SHIPSIZE_INPUTS_MISSING",
            "shipsize_derived": None,
            "girth": None,
            "shipsize_logic_note": f"Missing inputs: {', '.join(missing)}",
        }

    girth = (2.0 * h) + (2.0 * w) + l

    for max_girth, max_weight, code in _BRACKETS:
        if girth <= max_girth and wt <= max_weight:
            return {
                "outcome": "SHIPSIZE_DERIVED",
                "shipsize_derived": code,
                "girth": round(girth, 3),
                "shipsize_logic_note": (
                    f"girth={girth:.3f}in (=2*{h}+2*{w}+{l}), "
                    f"weight={wt}lb → {code}"
                ),
            }

    # _BRACKETS includes a FREIGHT catch-all, so this branch is unreachable
    # in practice; kept for defence in depth.
    return {
        "outcome": "SHIPSIZE_DERIVED",
        "shipsize_derived": "FREIGHT",
        "girth": round(girth, 3),
        "shipsize_logic_note": (
            f"girth={girth:.3f}in, weight={wt}lb → FREIGHT (catch-all)"
        ),
    }


__all__ = ["derive_shipsize"]
