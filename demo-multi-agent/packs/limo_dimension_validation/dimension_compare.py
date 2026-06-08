"""Dimension comparison helpers for the LIMO Dimension Validation pack.

Exposes ``compare_odin_iqs`` (two-way) and ``compare_three_way``
(ODIN / IQS / Consolidated) as python_function tools.  Each helper
returns an outcome code that the decision matrix evaluates, a
structured ``mismatches`` list the closure templates render, and a
per-dimension ``selection_explanation`` showing why each value was
selected.

Dimension equality uses a small absolute tolerance because the three
upstream systems quantise values at different precisions.

Units of measurement:
  - Height, Length, Width → IN (inches)
  - Weight → LB (pounds)
"""
from __future__ import annotations

from typing import Any, Optional

_DEFAULT_TOLERANCE: float = 0.01
_FIELDS: tuple[str, ...] = ("height", "length", "width", "weight")
_UOM: dict[str, str] = {
    "height": "IN",
    "length": "IN",
    "width": "IN",
    "weight": "LB",
}


def _as_float(value: Any) -> Optional[float]:
    if value in (None, "", "null", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _all_present(dims: dict[str, Any]) -> bool:
    return all(_as_float(dims.get(f)) is not None for f in _FIELDS)


def _any_present(dims: dict[str, Any]) -> bool:
    return any(_as_float(dims.get(f)) is not None for f in _FIELDS)


def _values_match(a: Any, b: Any, tolerance: float) -> bool:
    fa, fb = _as_float(a), _as_float(b)
    if fa is None or fb is None:
        return False
    return abs(fa - fb) <= tolerance


def _build_dims(
    height: Any, length: Any, width: Any, weight: Any,
) -> dict[str, Optional[float]]:
    return {
        "height": _as_float(height),
        "length": _as_float(length),
        "width": _as_float(width),
        "weight": _as_float(weight),
    }


def _format_dim(value: Optional[float], field: str) -> str:
    """Format a dimension value with its UOM."""
    if value is None:
        return "—"
    return f"{value} {_UOM[field]}"


def _classify_source(capture_method: Optional[str]) -> str:
    """Derive a human-readable source label from the capture method code.

    Common values for receivingDimensionsCaptureMethodTypeCode:
      - CUBIC_SCAN → "Cubic Scan"
      - PREDICTED  → "Predicted"
      - None / empty → falls back to the provider type (GOLD / Supplier)
    """
    if not capture_method:
        return ""
    cm = str(capture_method).strip().upper()
    labels = {
        "CUBIC_SCAN": "Cubic Scan",
        "CUBICSCAN": "Cubic Scan",
        "PREDICTED": "Predicted",
        "MANUAL": "Manual",
        "VENDOR": "Vendor Provided",
    }
    return labels.get(cm, cm)


def _pick_newer_timestamp(ts_a: Optional[str], ts_b: Optional[str]) -> str:
    """Return which timestamp is newer: 'a', 'b', or 'tie'."""
    if not ts_a and not ts_b:
        return "tie"
    if not ts_a:
        return "b"
    if not ts_b:
        return "a"
    return "a" if str(ts_a) >= str(ts_b) else "b"


def _build_dim_explanation(
    field: str,
    odin_val: Optional[float],
    gold_val: Optional[float],
    supplier_val: Optional[float],
    gold_ts: Optional[str],
    supplier_ts: Optional[str],
    gold_capture: Optional[str],
    selected_source: str,
    selected_val: Optional[float],
    reason: str,
) -> dict[str, Any]:
    """Build a per-dimension explanation entry."""
    entry: dict[str, Any] = {
        "field": field,
        "uom": _UOM[field],
        "odin_value": _format_dim(odin_val, field),
        "iqs_gold_value": _format_dim(gold_val, field),
        "iqs_supplier_value": _format_dim(supplier_val, field),
        "selected_source": selected_source,
        "selected_value": _format_dim(selected_val, field),
        "reason": reason,
    }
    if gold_ts:
        entry["gold_timestamp"] = gold_ts
    if supplier_ts:
        entry["supplier_timestamp"] = supplier_ts
    gold_source_label = _classify_source(gold_capture)
    if gold_source_label:
        entry["gold_capture_method"] = gold_source_label
    return entry


def compare_odin_iqs(
    odin_height: Any = None,
    odin_length: Any = None,
    odin_width: Any = None,
    odin_weight: Any = None,
    iqs_gold_height: Any = None,
    iqs_gold_length: Any = None,
    iqs_gold_width: Any = None,
    iqs_gold_weight: Any = None,
    iqs_gold_timestamp: Any = None,
    iqs_gold_capture_method: Any = None,
    iqs_supplier_height: Any = None,
    iqs_supplier_length: Any = None,
    iqs_supplier_width: Any = None,
    iqs_supplier_weight: Any = None,
    iqs_supplier_timestamp: Any = None,
    iqs_supplier_capture_method: Any = None,
    tolerance: float = _DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    """Compare ODIN dimensions against IQS TI dimensions (GOLD + Supplier).

    Iterates each dimension individually.  For each dimension:
      1. Check ODIN value against IQS GOLD value.
      2. Check ODIN value against IQS Supplier value.
      3. Select the IQS source that matches ODIN (prefer GOLD).
      4. If both match, prefer GOLD; break ties by timestamp.
      5. If neither matches, record a mismatch.

    Returns per-dimension explanation of source selection, including
    timestamp-based reasoning and capture method context.

    Outcomes:
      * ``ODIN_IQS_MATCH``           — ODIN matches at least one IQS source for all dims.
      * ``ODIN_IQS_MISMATCH``        — at least one dimension differs across all IQS sources.
      * ``ODIN_MISSING_IQS_PRESENT`` — IQS has dims, ODIN does not.
      * ``ODIN_PRESENT_IQS_MISSING`` — ODIN has dims, IQS does not (neither GOLD nor Supplier).
      * ``BOTH_MISSING``             — neither ODIN nor IQS has complete dimensions.
    """
    odin = _build_dims(odin_height, odin_length, odin_width, odin_weight)
    gold = _build_dims(iqs_gold_height, iqs_gold_length, iqs_gold_width, iqs_gold_weight)
    supplier = _build_dims(
        iqs_supplier_height, iqs_supplier_length,
        iqs_supplier_width, iqs_supplier_weight,
    )

    odin_ok = _all_present(odin)
    gold_ok = _any_present(gold)
    supplier_ok = _any_present(supplier)
    iqs_ok = gold_ok or supplier_ok

    # ── Presence-based outcomes ──────────────────────────────────────
    if not odin_ok and not iqs_ok:
        return {
            "outcome": "BOTH_MISSING",
            "odin_present": False,
            "iqs_gold_present": False,
            "iqs_supplier_present": False,
            "odin": odin,
            "iqs_gold": gold,
            "iqs_supplier": supplier,
            "mismatches": [],
            "selection_explanation": [],
        }
    if not odin_ok and iqs_ok:
        return {
            "outcome": "ODIN_MISSING_IQS_PRESENT",
            "odin_present": False,
            "iqs_gold_present": gold_ok,
            "iqs_supplier_present": supplier_ok,
            "odin": odin,
            "iqs_gold": gold,
            "iqs_supplier": supplier,
            "mismatches": [],
            "selection_explanation": [],
        }
    if odin_ok and not iqs_ok:
        return {
            "outcome": "ODIN_PRESENT_IQS_MISSING",
            "odin_present": True,
            "iqs_gold_present": False,
            "iqs_supplier_present": False,
            "odin": odin,
            "iqs_gold": gold,
            "iqs_supplier": supplier,
            "mismatches": [],
            "selection_explanation": [],
        }

    # ── Per-dimension comparison ─────────────────────────────────────
    mismatches: list[dict[str, Any]] = []
    explanations: list[dict[str, Any]] = []

    for f in _FIELDS:
        odin_val = odin[f]
        gold_val = gold.get(f)
        supp_val = supplier.get(f)

        gold_match = _values_match(odin_val, gold_val, tolerance)
        supp_match = _values_match(odin_val, supp_val, tolerance)

        if gold_match and supp_match:
            # Both match — prefer GOLD; note timestamp for context.
            newer = _pick_newer_timestamp(iqs_gold_timestamp, iqs_supplier_timestamp)
            capture_label = _classify_source(iqs_gold_capture_method)
            reason_parts = ["GOLD and Supplier both match ODIN", "GOLD selected (priority source)"]
            if capture_label:
                reason_parts.append(f"GOLD capture method: {capture_label}")
            if newer == "a" and iqs_gold_timestamp:
                reason_parts.append(f"GOLD is also more recent ({iqs_gold_timestamp})")
            explanations.append(_build_dim_explanation(
                f, odin_val, gold_val, supp_val,
                iqs_gold_timestamp, iqs_supplier_timestamp,
                iqs_gold_capture_method,
                selected_source="GOLD",
                selected_val=gold_val,
                reason="; ".join(reason_parts),
            ))
        elif gold_match:
            capture_label = _classify_source(iqs_gold_capture_method)
            reason_parts = ["GOLD matches ODIN"]
            if supp_val is not None:
                reason_parts.append(
                    f"Supplier value ({_format_dim(supp_val, f)}) does not match"
                )
            else:
                reason_parts.append("Supplier value not available")
            if capture_label:
                reason_parts.append(f"GOLD capture method: {capture_label}")
            explanations.append(_build_dim_explanation(
                f, odin_val, gold_val, supp_val,
                iqs_gold_timestamp, iqs_supplier_timestamp,
                iqs_gold_capture_method,
                selected_source="GOLD",
                selected_val=gold_val,
                reason="; ".join(reason_parts),
            ))
        elif supp_match:
            reason_parts = ["Supplier matches ODIN"]
            if gold_val is not None:
                reason_parts.append(
                    f"GOLD value ({_format_dim(gold_val, f)}) does not match"
                )
            else:
                reason_parts.append("GOLD value not available")
            if iqs_supplier_timestamp:
                reason_parts.append(f"Supplier timestamp: {iqs_supplier_timestamp}")
            explanations.append(_build_dim_explanation(
                f, odin_val, gold_val, supp_val,
                iqs_gold_timestamp, iqs_supplier_timestamp,
                iqs_gold_capture_method,
                selected_source="Supplier",
                selected_val=supp_val,
                reason="; ".join(reason_parts),
            ))
        else:
            # Neither matches ODIN — mismatch.
            reason_parts = ["No IQS source matches ODIN"]
            if gold_val is not None:
                reason_parts.append(f"GOLD={_format_dim(gold_val, f)}")
            if supp_val is not None:
                reason_parts.append(f"Supplier={_format_dim(supp_val, f)}")
            reason_parts.append(f"ODIN={_format_dim(odin_val, f)}")
            mismatches.append({
                "field": f,
                "uom": _UOM[f],
                "odin": _format_dim(odin_val, f),
                "iqs_gold": _format_dim(gold_val, f),
                "iqs_supplier": _format_dim(supp_val, f),
            })
            explanations.append(_build_dim_explanation(
                f, odin_val, gold_val, supp_val,
                iqs_gold_timestamp, iqs_supplier_timestamp,
                iqs_gold_capture_method,
                selected_source="NONE",
                selected_val=None,
                reason="; ".join(reason_parts),
            ))

    outcome = "ODIN_IQS_MATCH" if not mismatches else "ODIN_IQS_MISMATCH"

    return {
        "outcome": outcome,
        "odin_present": True,
        "iqs_gold_present": gold_ok,
        "iqs_supplier_present": supplier_ok,
        "odin": {f: _format_dim(odin[f], f) for f in _FIELDS},
        "iqs_gold": {f: _format_dim(gold.get(f), f) for f in _FIELDS},
        "iqs_supplier": {f: _format_dim(supplier.get(f), f) for f in _FIELDS},
        "iqs_gold_timestamp": iqs_gold_timestamp,
        "iqs_supplier_timestamp": iqs_supplier_timestamp,
        "iqs_gold_capture_method": _classify_source(iqs_gold_capture_method) or None,
        "iqs_supplier_capture_method": _classify_source(iqs_supplier_capture_method) or None,
        "mismatches": mismatches,
        "selection_explanation": explanations,
    }


def compare_three_way(
    odin_height: Any = None,
    odin_length: Any = None,
    odin_width: Any = None,
    odin_weight: Any = None,
    iqs_height: Any = None,
    iqs_length: Any = None,
    iqs_width: Any = None,
    iqs_weight: Any = None,
    consolidated_height: Any = None,
    consolidated_length: Any = None,
    consolidated_width: Any = None,
    consolidated_weight: Any = None,
    tolerance: float = _DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    """Final three-way comparison across ODIN, IQS, and Consolidated.

    All three sources must (a) be fully present and (b) agree pairwise on
    every dimension within ``tolerance``.  A missing value in any source
    is treated as a presence failure, not as a silent match.

    Outcomes:
      * ``ALL_MATCH``               — All three sources agree on every dim.
      * ``CONSOLIDATED_MISMATCH``   — At least one source disagrees on a dim
                                      (any pair: ODIN/IQS, ODIN/CONS, IQS/CONS).
      * ``CONSOLIDATED_MISSING``    — Consolidated did not return complete dims.
      * ``IQS_MISSING_FOR_THREE_WAY`` — IQS did not return complete dims, so
                                      a three-way verdict cannot be issued.
    """
    odin = _build_dims(odin_height, odin_length, odin_width, odin_weight)
    iqs = _build_dims(iqs_height, iqs_length, iqs_width, iqs_weight)
    cons = _build_dims(
        consolidated_height,
        consolidated_length,
        consolidated_width,
        consolidated_weight,
    )

    if not _all_present(cons):
        return {
            "outcome": "CONSOLIDATED_MISSING",
            "odin": {f: _format_dim(odin[f], f) for f in _FIELDS},
            "iqs": {f: _format_dim(iqs[f], f) for f in _FIELDS},
            "consolidated": {f: _format_dim(cons[f], f) for f in _FIELDS},
            "mismatches": [],
        }

    if not _all_present(iqs):
        return {
            "outcome": "IQS_MISSING_FOR_THREE_WAY",
            "odin": {f: _format_dim(odin[f], f) for f in _FIELDS},
            "iqs": {f: _format_dim(iqs[f], f) for f in _FIELDS},
            "consolidated": {f: _format_dim(cons[f], f) for f in _FIELDS},
            "mismatches": [],
        }

    mismatches: list[dict[str, Any]] = []
    for f in _FIELDS:
        odin_v, iqs_v, cons_v = odin[f], iqs[f], cons[f]
        odin_iqs_match = _values_match(odin_v, iqs_v, tolerance)
        odin_cons_match = _values_match(odin_v, cons_v, tolerance)
        iqs_cons_match = _values_match(iqs_v, cons_v, tolerance)
        if not (odin_iqs_match and odin_cons_match and iqs_cons_match):
            mismatches.append({
                "field": f,
                "uom": _UOM[f],
                "odin": _format_dim(odin_v, f),
                "iqs": _format_dim(iqs_v, f),
                "consolidated": _format_dim(cons_v, f),
            })

    outcome = "ALL_MATCH" if not mismatches else "CONSOLIDATED_MISMATCH"
    return {
        "outcome": outcome,
        "odin": {f: _format_dim(odin[f], f) for f in _FIELDS},
        "iqs": {f: _format_dim(iqs[f], f) for f in _FIELDS},
        "consolidated": {f: _format_dim(cons[f], f) for f in _FIELDS},
        "mismatches": mismatches,
    }


def compare_mp_weight(
    odin_weight: Any = None,
    consolidated_weight: Any = None,
    tolerance: float = _DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    """Compare ODIN weight against Consolidated weight for MP offers.

    Used when wfsElig=FALSE and seller_type=EXTERNAL.  Only weight is
    validated; IQS TI is skipped entirely for Marketplace offers.

    Outcomes:
      * ``MP_WEIGHT_MATCH``    — ODIN and Consolidated weight agree.
      * ``MP_WEIGHT_MISMATCH`` — ODIN and Consolidated weight differ,
        or one/both values are unavailable.
    """
    odin_w = _as_float(odin_weight)
    cons_w = _as_float(consolidated_weight)

    if odin_w is None and cons_w is None:
        return {
            "outcome": "MP_WEIGHT_MISMATCH",
            "odin_weight": "—",
            "consolidated_weight": "—",
            "reason": "Both ODIN and Consolidated weight are unavailable",
        }
    if odin_w is None:
        return {
            "outcome": "MP_WEIGHT_MISMATCH",
            "odin_weight": "—",
            "consolidated_weight": _format_dim(cons_w, "weight"),
            "reason": "ODIN weight is not available",
        }
    if cons_w is None:
        return {
            "outcome": "MP_WEIGHT_MISMATCH",
            "odin_weight": _format_dim(odin_w, "weight"),
            "consolidated_weight": "—",
            "reason": "Consolidated weight is not available",
        }

    match = abs(odin_w - cons_w) <= tolerance
    outcome = "MP_WEIGHT_MATCH" if match else "MP_WEIGHT_MISMATCH"
    odin_fmt = _format_dim(odin_w, "weight")
    cons_fmt = _format_dim(cons_w, "weight")

    return {
        "outcome": outcome,
        "odin_weight": odin_fmt,
        "consolidated_weight": cons_fmt,
        "reason": (
            f"ODIN weight ({odin_fmt}) matches Consolidated weight ({cons_fmt})"
            if match
            else f"ODIN weight ({odin_fmt}) differs from Consolidated weight ({cons_fmt})"
        ),
    }


__all__ = ["compare_odin_iqs", "compare_three_way", "compare_mp_weight"]
