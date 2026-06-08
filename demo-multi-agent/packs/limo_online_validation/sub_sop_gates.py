"""Deterministic verdict gates for the LIMO Online sub-SOPs.

Each gate is a pure function: it accepts the resolved-state slots
the SOP names as inputs and emits a stable outcome string plus the
fields the decision matrix / closure template need.  Gates do NOT
fetch upstream payloads — the http_api + analyzer tools handle that
upstream and project the inputs onto the state slots these gates
read.

Gates exposed:

  - ``cost_rt_gate`` — IQS-resolved → Shipnodes status / partnership
    type → STORES-only exit or COST_RT_PROCEED.
  - ``preorder_verdict`` — compares the inbound streetDate to the
    current UTC instant (``now_iso`` overridable for tests) and emits
    PREORDER_PAST_STREET_DATE / PREORDER_FUTURE_STREET_DATE /
    PREORDER_NO_STREET_DATE.
  - ``replenishable_verdict`` — EXTERNAL-seller exit; otherwise
    surfaces the ODIN ``rplnFlg`` vs Shipnodes ``replenishmentFlag``
    alignment.
  - ``acs_verdict`` — gates on the seller's enrollment in ASE /
    Automated Shipping Enabled (ODIN ``oss.ase`` + DEW Seller
    ``ase``/``aseStatus`` + Consolidated ``isACSEnabled``).
  - ``ftc_matrix`` — 7-row truth table mapping FTC codes to runbook
    outcomes (PHOTOS / TIRE / DIGITAL / FREIGHT /
    WALMART_PLASTIC_GIFT_CARD / NON_WALMART_PLASTIC_GIFT_CARD /
    PHARMACY_PETS).

All gates are side-effect free, accept and pass through unknown
kwargs (the runtime injects spurious params), and never raise.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────


def _norm_bool(val: Any) -> Optional[bool]:
    """Coerce common truthy / falsy representations to ``bool``.

    Returns None when the input is None / empty / unrecognised so
    callers can distinguish "missing" from "false".
    """
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "t", "yes", "y", "1", "enabled", "active"):
            return True
        if v in ("false", "f", "no", "n", "0", "disabled", "inactive"):
            return False
    return None


def _upper(val: Any) -> str:
    """Strip + upper-case a value; empty string for None / non-str."""
    if val is None:
        return ""
    return str(val).strip().upper()


# ─────────────────────────────────────────────────────────────────────
# 1. COST RT gate
# ─────────────────────────────────────────────────────────────────────


def cost_rt_gate(iqs_item_number: Optional[str] = None,
                 shipnode_item_id: Optional[str] = None,
                 iqs_partnership_type_code: Optional[str] = None,
                 shipnode_status: Optional[str] = None,
                 **_: Any) -> dict[str, Any]:
    """COST RT sub-SOP: IQS → Shipnodes partnership-type gate.

    Inputs:
      - ``iqs_item_number`` from DIAG-IQS-SI-01
      - ``shipnode_item_id``, ``iqs_partnership_type_code``,
        ``shipnode_status`` from DIAG-ANALYZE-SHIPNODES

    Outcomes:
      - COST_RT_NO_SI       — IQS itemNumber missing
      - COST_RT_STORES_ONLY — partnershipType is STORE-only
        (offer is not COST_RT-eligible)
      - COST_RT_INACTIVE    — Shipnode status is not ACTIVE / ENABLED
      - COST_RT_PROCEED     — IQS resolved, shipnode active, partner
        type permits COST RT
    """
    if not iqs_item_number:
        return {
            "outcome":         "COST_RT_NO_SI",
            "cost_rt_proceed": False,
            "stop_message":    (
                "COST RT requires an IQS itemNumber — the IQS SI "
                "lookup returned no result for this product."
            ),
        }

    ptype = _upper(iqs_partnership_type_code)
    if ptype in ("STORE", "STORES", "STORE_ONLY", "STORES_ONLY"):
        return {
            "outcome":               "COST_RT_STORES_ONLY",
            "cost_rt_proceed":       False,
            "cost_rt_stores_only":   True,
            "stop_message":          (
                "This offer's Shipnode partnership type is "
                f"{ptype!r} — COST RT is not supported for "
                "STORES-only partnerships."
            ),
        }

    status = _upper(shipnode_status)
    if status and status not in ("ACTIVE", "ENABLED"):
        return {
            "outcome":         "COST_RT_INACTIVE",
            "cost_rt_proceed": False,
            "stop_message":    (
                f"Shipnode status is {status!r} — COST RT requires "
                "an ACTIVE Shipnode record."
            ),
        }

    return {
        "outcome":                 "COST_RT_PROCEED",
        "cost_rt_proceed":         True,
        "iqs_item_number":         iqs_item_number,
        "shipnode_item_id":        shipnode_item_id,
        "iqs_partnership_type_code": iqs_partnership_type_code,
    }


# ─────────────────────────────────────────────────────────────────────
# 2. Pre-Order verdict
# ─────────────────────────────────────────────────────────────────────


def preorder_verdict(preorder_street_date: Optional[str] = None,
                     preorder_consolidated_street_date: Optional[str] = None,
                     seller_type: Optional[str] = None,
                     now_iso: Optional[str] = None,
                     **_: Any) -> dict[str, Any]:
    """Compare the inbound streetDate to ``now`` and emit a verdict.

    Inputs:
      - ``preorder_street_date`` from analyze_preorder_shipnodes
      - ``preorder_consolidated_street_date`` from
        analyze_preorder_consolidated (fallback when Shipnodes is silent)
      - ``seller_type`` from DIAG-ODIN-01 — EXTERNAL sellers exit
        without comparing dates
      - ``now_iso`` overridable for tests; defaults to current UTC

    Outcomes:
      - PREORDER_SELLER_EXTERNAL — EXTERNAL seller; pre-order is not
        supported on the LIMO side
      - PREORDER_NO_STREET_DATE — no streetDate present in either source
      - PREORDER_PAST_STREET_DATE — streetDate <= now (offer should
        no longer be in pre-order state)
      - PREORDER_FUTURE_STREET_DATE — streetDate > now (offer is
        legitimately in pre-order state)
    """
    if _upper(seller_type) == "EXTERNAL":
        return {
            "outcome":          "PREORDER_SELLER_EXTERNAL",
            "preorder_verdict": "PREORDER_SELLER_EXTERNAL",
            "stop_message":     (
                "Pre-Order validation is not supported for EXTERNAL "
                "sellers — escalate to the seller-facing channel."
            ),
        }

    street_date = preorder_street_date or preorder_consolidated_street_date
    if not street_date:
        return {
            "outcome":          "PREORDER_NO_STREET_DATE",
            "preorder_verdict": "PREORDER_NO_STREET_DATE",
            "preorder_street_date": None,
        }

    street_dt = _parse_iso_dt(street_date)
    if street_dt is None:
        return {
            "outcome":          "PREORDER_NO_STREET_DATE",
            "preorder_verdict": "PREORDER_NO_STREET_DATE",
            "preorder_street_date": str(street_date),
        }

    now_dt = _parse_iso_dt(now_iso) if now_iso else datetime.now(timezone.utc)
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)

    if street_dt <= now_dt:
        return {
            "outcome":              "PREORDER_PAST_STREET_DATE",
            "preorder_verdict":     "PREORDER_PAST_STREET_DATE",
            "preorder_street_date": str(street_date),
        }
    return {
        "outcome":              "PREORDER_FUTURE_STREET_DATE",
        "preorder_verdict":     "PREORDER_FUTURE_STREET_DATE",
        "preorder_street_date": str(street_date),
    }


def _parse_iso_dt(val: Any) -> Optional[datetime]:
    """Best-effort ISO-8601 parser; trailing ``Z`` is honoured.

    Returns None for unparseable input so the caller can short-circuit
    cleanly without raising.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    # Accept the common "...Z" suffix that fromisoformat rejected
    # before Python 3.11.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Date-only ISO (YYYY-MM-DD)
        try:
            dt = datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ─────────────────────────────────────────────────────────────────────
# 3. Replenishable verdict
# ─────────────────────────────────────────────────────────────────────


def replenishable_verdict(seller_type: Optional[str] = None,
                          replen_flag_odin: Any = None,
                          replenishment_flag: Any = None,
                          **_: Any) -> dict[str, Any]:
    """Replenishable sub-SOP verdict.

    Inputs:
      - ``seller_type`` from DIAG-ODIN-01 — EXTERNAL sellers exit
      - ``replen_flag_odin`` (oa.rplnFlg) — ODIN-side flag
      - ``replenishment_flag`` from analyze_replenishable_shipnodes

    Outcomes:
      - REPLEN_SELLER_EXTERNAL — EXTERNAL seller
      - REPLEN_FLAG_MISSING    — neither source populated the flag
      - REPLEN_MISMATCH        — ODIN and Shipnodes disagree
      - REPLEN_TRUE / REPLEN_FALSE — aligned bool verdict
    """
    if _upper(seller_type) == "EXTERNAL":
        return {
            "outcome":      "REPLEN_SELLER_EXTERNAL",
            "stop_message": (
                "Replenishable validation is not supported for "
                "EXTERNAL sellers — escalate to the seller-facing "
                "channel."
            ),
        }

    odin_b = _norm_bool(replen_flag_odin)
    ship_b = _norm_bool(replenishment_flag)

    if odin_b is None and ship_b is None:
        return {
            "outcome":             "REPLEN_FLAG_MISSING",
            "replenishment_flag":  None,
            "replen_flag_odin":    None,
        }

    if odin_b is not None and ship_b is not None and odin_b != ship_b:
        return {
            "outcome":             "REPLEN_MISMATCH",
            "replenishment_flag":  ship_b,
            "replen_flag_odin":    odin_b,
            "stop_message":        (
                f"ODIN oa.rplnFlg={odin_b} disagrees with Shipnodes "
                f"replenishmentFlag={ship_b} — investigate the LIMO "
                "<-> upstream sync."
            ),
        }

    resolved = odin_b if odin_b is not None else ship_b
    return {
        "outcome":            "REPLEN_TRUE" if resolved else "REPLEN_FALSE",
        "replenishment_flag": ship_b,
        "replen_flag_odin":   odin_b,
    }


# ─────────────────────────────────────────────────────────────────────
# 4. ACS verdict
# ─────────────────────────────────────────────────────────────────────


def acs_verdict(ase_odin: Any = None,
                ase_status: Optional[str] = None,
                ase_seller: Any = None,
                acs_enabled: Any = None,
                **_: Any) -> dict[str, Any]:
    """ACS / ASE enrollment verdict.

    Inputs:
      - ``ase_odin`` (oa.oss.ase) — ODIN-side ASE flag
      - ``ase_status`` from DEW Seller (programsDTO.AUTOMATED_SHIPPING_ENABLED.status)
      - ``ase_seller`` — DEW Seller root ``ase`` boolean
      - ``acs_enabled`` — Consolidated ``isACSEnabled``

    Outcomes:
      - ACS_NOT_ENROLLED — seller is not enrolled in ASE
        (any of the three signals explicitly negative)
      - ACS_INPUTS_MISSING — none of the three signals populated
      - ACS_ENROLLED — at least one positive signal and no negative
        signal contradicting it
    """
    odin_b = _norm_bool(ase_odin)
    seller_b = _norm_bool(ase_seller)
    consol_b = _norm_bool(acs_enabled)
    status_u = _upper(ase_status)

    if all(v is None for v in (odin_b, seller_b, consol_b)) and not status_u:
        return {"outcome":           "ACS_INPUTS_MISSING",
                "acs_not_enrolled":  None}

    # Explicit-negative wins: if any source says false (and none
    # positively contradicts within the same row), the seller is not
    # enrolled.
    explicit_negative = (
        odin_b is False
        or seller_b is False
        or consol_b is False
        or (status_u and status_u not in ("ENABLED", "ACTIVE", "ENROLLED"))
    )
    explicit_positive = (
        odin_b is True
        or seller_b is True
        or consol_b is True
        or status_u in ("ENABLED", "ACTIVE", "ENROLLED")
    )

    if explicit_negative and not explicit_positive:
        return {
            "outcome":          "ACS_NOT_ENROLLED",
            "acs_not_enrolled": True,
            "ase_odin":         odin_b,
            "ase_status":       ase_status,
            "ase_seller":       seller_b,
            "acs_enabled":      consol_b,
            "stop_message":     (
                "Seller is not enrolled in ACS / Automated Shipping "
                "Enabled — ACS-gated paths will not be eligible."
            ),
        }

    return {
        "outcome":          "ACS_ENROLLED",
        "acs_not_enrolled": False,
        "ase_odin":         odin_b,
        "ase_status":       ase_status,
        "ase_seller":       seller_b,
        "acs_enabled":      consol_b,
    }


# ─────────────────────────────────────────────────────────────────────
# 5. FTC truth-table
# ─────────────────────────────────────────────────────────────────────

# Ordered (token, outcome, runbook_id, message) — first FTC code in
# the offer's classification that matches a row wins.  Tokens are
# upper-case and matched as substrings against each comma-split FTC
# entry so live values like "WALMART_PLASTIC_GIFT_CARD_DIGITAL" still
# resolve to the DIGITAL row's outcome when DIGITAL appears later.
_FTC_TRUTH_TABLE: tuple[tuple[str, str, str, str], ...] = (
    ("PHARMACY_PETS",
     "FTC_PHARMACY_PETS",
     "RBK-ONLINE-FTC-PHARMACY-PETS",
     "Pharmacy / Pets FTC — eligibility is governed by the "
     "pharmacy-pets channel SOP."),
    # NON_WALMART_PLASTIC_GIFT_CARD walks before WALMART_PLASTIC_GIFT_CARD
    # — the latter is a substring of the former, so substring matching
    # would otherwise pull the non-walmart code into the walmart row.
    ("NON_WALMART_PLASTIC_GIFT_CARD",
     "FTC_NON_WALMART_PLASTIC_GIFT_CARD",
     "RBK-ONLINE-FTC-NON-WMT-GIFT-CARD",
     "Non-Walmart Plastic Gift Card FTC — eligibility is restricted "
     "to the marketplace gift-card channel."),
    ("WALMART_PLASTIC_GIFT_CARD",
     "FTC_WALMART_PLASTIC_GIFT_CARD",
     "RBK-ONLINE-FTC-WMT-GIFT-CARD",
     "Walmart Plastic Gift Card FTC — eligibility is restricted to "
     "the Walmart Gift Card fulfillment channel."),
    ("FREIGHT",
     "FTC_FREIGHT",
     "RBK-ONLINE-FTC-FREIGHT",
     "Freight FTC — eligibility is restricted to the Freight "
     "fulfillment channel."),
    ("PHOTOS",
     "FTC_PHOTOS",
     "RBK-ONLINE-FTC-PHOTOS",
     "Photos FTC — eligibility is restricted to the Photos "
     "fulfillment channel."),
    ("TIRE",
     "FTC_TIRE",
     "RBK-ONLINE-FTC-TIRE",
     "Tire FTC — eligibility is restricted to the Tire fulfillment "
     "channel."),
    ("DIGITAL",
     "FTC_DIGITAL",
     "RBK-ONLINE-FTC-DIGITAL",
     "Digital FTC — eligibility is restricted to the Digital "
     "fulfillment channel."),
)


def ftc_matrix(ftc_csv: Optional[str] = None,
               ftc_consolidated: Optional[str] = None,
               **_: Any) -> dict[str, Any]:
    """Map the offer's FTC classification to a runbook outcome.

    Inputs:
      - ``ftc_csv`` from DIAG-ODIN-01 (oa.ftc rendered as CSV)
      - ``ftc_consolidated`` from analyze_ftc_consolidated (fallback
        when ODIN omits the field)

    Walks the truth table top-down; the first matching token wins.
    When no token matches, emits FTC_STANDARD with a NONE runbook so
    the main eligibility path remains in effect.
    """
    source = ftc_csv or ftc_consolidated or ""
    tokens = [t.strip().upper() for t in str(source).split(",") if t.strip()]

    for token, outcome, runbook, message in _FTC_TRUTH_TABLE:
        if any(token in t for t in tokens):
            return {
                "outcome":      outcome,
                "ftc_token":    token,
                "ftc_runbook":  runbook,
                "ftc_message":  message,
                "ftc_codes":    tokens,
            }

    return {
        "outcome":      "FTC_STANDARD",
        "ftc_token":    None,
        "ftc_runbook":  "RBK-ONLINE-FTC-STANDARD",
        "ftc_message":  (
            "FTC classification is standard — main eligibility flow "
            "(AURUM + DEW + Promise + Consolidated) governs the verdict."
        ),
        "ftc_codes":    tokens,
    }


__all__ = [
    "cost_rt_gate",
    "preorder_verdict",
    "replenishable_verdict",
    "acs_verdict",
    "ftc_matrix",
]
