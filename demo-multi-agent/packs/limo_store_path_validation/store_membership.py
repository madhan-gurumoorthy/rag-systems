"""Helpers for the 1P Store Path Eligibility pack.

These ``python_function`` tools provide the pack-specific glue that the
generic substrate cannot:

* ``check_store_eligibility``   — O(1) membership check against the
  named eligible-store frozenset.
* ``dispatch_subcase``          — examine ODIN attributes (and optional
  Product RT attributes) and decide which sub-case applies (TIRE, PHOTO,
  PETRX, VISION_RX, CUSTOM_CAKE, HUMAX_RX, DELIVERY_INHOME, DRONE,
  IP_PATH, INSTORE_PURCHASE_ONLY, or MAIN).
* ``analyze_aurum_paths``       — pluck the inclusion/exclusion entries
  for the canonical 30-path allow-list off the AURUM response.
* ``analyze_dew_paths``         — flatten ``ftxn.outboundPaths`` into a
  list of {path, fulfillmentMethods, types} rows.
* ``analyze_consolidated_paths`` — walk
  ``offerNodePayload.nodeData.STORE`` and resolve eligible/excluded
  fulfillment methods and node types for a given store id per the
  SOP's nodeExceptions logic.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from packs.limo_store_path_validation.eligible_stores import (
    CUSTOM_CAKE_ELIGIBLE_STORES,
    DELIVERY_INHOME_ELIGIBLE_STORES,
    DRONE_ELIGIBLE_STORES,
    IP_PATH_ELIGIBLE_STORES,
    NATIONAL_CARRIER_ELIGIBLE_STORES,
    PHOTO_ELIGIBLE_STORES,
    TIRE_ELIGIBLE_STORES,
)

__all__ = [
    "check_store_eligibility",
    "dispatch_subcase",
    "route_subcase_by_query",
    "analyze_aurum_paths",
    "analyze_dew_paths",
    "analyze_consolidated_paths",
    "analyze_mdm_store_status",
    "fetch_mdm_store_status",
    "fetch_product_attributes",
]

# ── Canonical 30-path allow-list ──
#
# The SOP restricts AURUM inclusion / exclusion iteration to exactly
# these fulfillment paths; everything else in the response is ignored.

_ALLOWED_PATHS: tuple[str, ...] = (
    "STORE|UNSCHEDULED_DELIVERY|DELIVERY_ADDRESS|NATIONAL_CARRIER",
    "STORE|SCHEDULED_DELIVERY|DELIVERY_ADDRESS|LAST_MILE_CARRIER",
    "STORE|UNSCHEDULED_DELIVERY|DELIVERY_ADDRESS|LAST_MILE_CARRIER",
    "STORE|SCHEDULED_PICKUP|PICKUP_CURBSIDE|DRIVE_IN",
    "STORE|UNSCHEDULED_PICKUP|PICKUP_CURBSIDE|DRIVE_IN",
    "STORE|UNSCHEDULED_PICKUP|PICKUP_INSTORE|WALK_IN",
    "STORE|SCHEDULED_PICKUP|PICKUP_BAKERY|WALK_IN",
    "STORE|UNSCHEDULED_PICKUP|PHOTO_CENTER|WALK_IN",
    "STORE|SCHEDULED_PICKUP|ACC|DRIVE_IN",
    "STORE|UNSCHEDULED_PICKUP|ACC|DRIVE_IN",
    "STORE|SCHEDULED_DELIVERY|DELIVERY_ADDRESS|3P_SHOPPER",
    "STORE|SCHEDULED_DELIVERY|DELIVERY_IN_HOME|LAST_MILE_CARRIER",
    "STORE|UNSCHEDULED_DELIVERY|DELIVERY_SPECIAL_EVENT|LAST_MILE_CARRIER",
    "STORE|UNSCHEDULED_PICKUP|PICKUP_SPECIAL_EVENT|WALK_IN",
    "STORE|UNSCHEDULED_DELIVERY|SHIPPING_SPECIAL_EVENT|NATIONAL_CARRIER",
    "STORE|SCHEDULED_PICKUP|PICKUP_POPUP|DRIVE_IN",
    "STORE|SCHEDULED_PICKUP|PICKUP_SPOKE|DRIVE_IN",
    "STORE|SCHEDULED_DELIVERY|DELIVERY_ADDRESS|3P_DELIVERY",
    "STORE|SCHEDULED_DELIVERY|LIQUOR_BOX_DELIVERY|LAST_MILE_CARRIER",
    "STORE|SCHEDULED_PICKUP|LIQUOR_BOX_PICKUP|DRIVE_IN",
    "STORE|UNSCHEDULED_DELIVERY|NODE|LAST_MILE_CARRIER",
    "STORE|UNSCHEDULED_DELIVERY|NODE|NATIONAL_CARRIER",
    "STORE|INSTORE_PURCHASE_ONLY|PICKUP_INSTORE|WALK_IN",
    "STORE|SCHEDULED_PICKUP|GARDEN_CENTER_CURBSIDE|DRIVE_IN",
    "STORE|SCHEDULED_PICKUP|ACC_INGROUND|DRIVE_IN",
    "STORE|SCHEDULED_DELIVERY|DRONE_DELIVERY|LAST_MILE_CARRIER",
    "STORE|UNSCHEDULED_DELIVERY|DRONE_DELIVERY|LAST_MILE_CARRIER",
    "STORE|SCHEDULED_DELIVERY|DELIVERY_PHARMACY_INSTORE|LAST_MILE_CARRIER",
    "STORE|SCHEDULED_PICKUP|WIRELESS_SERVICE|WALK_IN",
)
_ALLOWED_PATHS_SET: frozenset[str] = frozenset(_ALLOWED_PATHS)

_LIST_LOOKUP: dict[str, frozenset[str]] = {
    "TIRE": TIRE_ELIGIBLE_STORES,
    "PHOTO": PHOTO_ELIGIBLE_STORES,
    "DRONE": DRONE_ELIGIBLE_STORES,
    "NATIONAL_CARRIER": NATIONAL_CARRIER_ELIGIBLE_STORES,
    "CUSTOM_CAKE": CUSTOM_CAKE_ELIGIBLE_STORES,
    "DELIVERY_INHOME": DELIVERY_INHOME_ELIGIBLE_STORES,
    "IP_PATH": IP_PATH_ELIGIBLE_STORES,
}

_INHOME_RESTRICTED_PFHBRC: frozenset[str] = frozenset(
    {
        "96-826-11553-36224",
        "96-5843-12769-33979",
        "96-826-13060-29485",
    }
)
_INHOME_RESTRICTED_DEPT_CAT_GRP: str = "96-830"

_CUSTOM_CAKE_PFHBRC: str = "98-1471-3338-7060-2251"

_VISION_RX_PRODUCT_TYPES: frozenset[str] = frozenset(
    {
        "Protective Eyewear",
        "Computer Glasses",
        "Eyeglass Frames",
        "Sport Safety Eyewear",
        "Sunglasses",
    }
)
_VISION_RX_STORE_ID: str = "30100"

_PHOTO_DELIVERY_METHODS: frozenset[str] = frozenset(
    {"Delivery", "Same Day", "1-hour"}
)
_PHOTO_PERSONALIZATION_PREFIX: str = "https://photos3.walmart.com"


# ── Generic helpers ───────────────────────────────────────────────────


def _coerce_store_id(value: Any) -> str:
    """Render any inbound store id as a plain decimal string.

    Inputs may arrive as int (``1462``), str (``"1462"``), or padded
    (``"01462"``).  The eligible-store frozensets hold unpadded decimal
    strings, so we strip and re-coerce.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if s.isdigit():
        return str(int(s))
    return s


def _ftc_contains(ftc: Any, token: str) -> bool:
    """Return True when ``token`` appears in the FTC array/CSV/string."""
    if ftc is None:
        return False
    target = token.upper()
    if isinstance(ftc, (list, tuple, set)):
        return any(str(x).upper() == target for x in ftc)
    if isinstance(ftc, str):
        return target in {p.strip().upper() for p in ftc.split(",") if p.strip()}
    return False


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"y", "yes", "true", "1"}


def _falsy_flag(value: Any) -> bool:
    """SOP semantics: ``N`` or ``NULL``/``None`` count as "not approved"."""
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    return str(value).strip().lower() in {"n", "no", "false", "0", "null", ""}


# ── Tool: check_store_eligibility ─────────────────────────────────────


def check_store_eligibility(
    store_id: Any = None, list_name: Any = None
) -> dict[str, Any]:
    """O(1) membership check against the named eligible-store list.

    Outcomes:
      * ``STORE_ELIGIBLE``     — store_id present in the list.
      * ``STORE_NOT_ELIGIBLE`` — store_id absent from the list.
      * ``BAD_REQUEST``        — unknown list name or missing store_id.
    """
    sid = _coerce_store_id(store_id)
    name = str(list_name or "").strip().upper()
    if not sid:
        return {
            "outcome": "BAD_REQUEST",
            "reason": "store_id is required",
            "store_id": "",
            "list_name": name,
            "eligible": False,
        }
    if name not in _LIST_LOOKUP:
        return {
            "outcome": "BAD_REQUEST",
            "reason": f"unknown list_name '{list_name}'",
            "store_id": sid,
            "list_name": name,
            "eligible": False,
        }
    eligible = sid in _LIST_LOOKUP[name]
    return {
        "outcome": "STORE_ELIGIBLE" if eligible else "STORE_NOT_ELIGIBLE",
        "store_id": sid,
        "list_name": name,
        "eligible": eligible,
        "list_size": len(_LIST_LOOKUP[name]),
    }


# ── Tool: dispatch_subcase ────────────────────────────────────────────


def _is_petrx(itm_cls_id: Any, ftc: Any, acc_d_nbr: Any, ptyp: Any, afa: Any) -> bool:
    return (
        str(acc_d_nbr) == "38"
        and str(ptyp or "").strip() == "Prescription Medicines"
        and _truthy_flag(afa)
    )


def _is_humax_rx(acc_d_nbr: Any, ptyp: Any, afa: Any) -> bool:
    return (
        str(acc_d_nbr) == "38"
        and str(ptyp or "").strip() == "Prescription Medicines"
        and _falsy_flag(afa)
    )


def _is_tire(itm_cls_id: Any, ftc: Any) -> bool:
    return str(itm_cls_id) == "28" and _ftc_contains(ftc, "TIRE")


def _is_photo(itm_cls_id: Any, ftc: Any) -> bool:
    return str(itm_cls_id) == "52" and _ftc_contains(ftc, "PHOTOS")


def _is_custom_cake(pfhbrc: Any) -> bool:
    return str(pfhbrc or "").strip() == _CUSTOM_CAKE_PFHBRC


def _is_vision_rx(vca: Any, store_id: str, ptyp: Any) -> bool:
    pt = str(ptyp or "").strip()
    return (
        store_id == _VISION_RX_STORE_ID
        and (
            (_truthy_flag(vca) and pt in _VISION_RX_PRODUCT_TYPES)
            or pt == "Eyeglass Lenses"
        )
    )


def _is_ip_path(otyp: Any, styp: Any) -> bool:
    return (
        str(otyp or "").strip().upper() == "ONLINE_ONLY"
        and str(styp or "").strip().upper() == "INTERNAL"
    )


def _is_delivery_inhome(acc_d_nbr: Any, pfhbrc: Any) -> bool:
    if str(acc_d_nbr) != "96":
        return False
    p = str(pfhbrc or "").strip()
    if p in _INHOME_RESTRICTED_PFHBRC:
        return False
    # ``deptCatGrp`` is the first three hyphen-segments of pfhbrc.
    parts = p.split("-")
    dept_cat_grp = "-".join(parts[:3]) if len(parts) >= 3 else p
    if dept_cat_grp == _INHOME_RESTRICTED_DEPT_CAT_GRP:
        return False
    return True


_OUTBOUND_GEO_KEYWORDS = (
    "outbound geo",
    "alcohol geo",
    "alcohol restrictions",
)


def _matches_outbound_geo(work_item_text: Any) -> bool:
    text = str(work_item_text or "").strip().lower()
    if not text:
        return False
    return any(kw in text for kw in _OUTBOUND_GEO_KEYWORDS)


def dispatch_subcase(
    itm_cls_id: Any = None,
    ftc: Any = None,
    acc_d_nbr: Any = None,
    ptyp: Any = None,
    afa: Any = None,
    pfhbrc: Any = None,
    otyp: Any = None,
    styp: Any = None,
    vca: Any = None,
    store_id: Any = None,
    product_rt_item_class_id: Any = None,
    product_rt_delivery_method: Any = None,
    product_rt_personalizable: Any = None,
    product_rt_personalization_url: Any = None,
    work_item_text: Any = None,
) -> dict[str, Any]:
    """Classify the sub-case based on ODIN + Product RT + store id.

    Returns a single ``subcase`` slot and a structured ``hints`` dict
    that downstream prompts and templates use to render the right
    output block.  First-match wins; ordering follows the SOP's
    decision tree (specificity → generality).

    The Outbound GEO sub-case is keyword-triggered from the inbound
    ``work_item_text`` ("outbound geo", "alcohol geo", "alcohol
    restrictions") and short-circuits ahead of the attribute-driven
    classification.

    Outcomes (the ``outcome`` slot):
      * ``SUBCASE_OUTBOUND_GEO``          — outbound GEO / alcohol keywords
      * ``SUBCASE_TIRE``                  — itemClass=28 + FTC=TIRE
      * ``SUBCASE_PHOTO``                 — itemClass=52 + FTC=PHOTOS
      * ``SUBCASE_CUSTOM_CAKE``           — pfhbrc matches custom-cake hierarchy
      * ``SUBCASE_PETRX``                 — accDNbr=38, ptyp=Rx Medicines, afa=Y
      * ``SUBCASE_VISION_RX``             — vca=true at store 30100 + eyewear ptyp
      * ``SUBCASE_HUMAX_RX``              — accDNbr=38, ptyp=Rx Medicines, afa=N/NULL
      * ``SUBCASE_DELIVERY_INHOME``       — accDNbr=96 + pfhbrc allowed
      * ``SUBCASE_DRONE``                 — store_id is in DRONE list
      * ``SUBCASE_IP_PATH``               — otyp=ONLINE_ONLY + styp=INTERNAL
      * ``SUBCASE_MAIN``                  — default 1P store-path flow
    """
    sid = _coerce_store_id(store_id)
    hints: dict[str, Any] = {}

    # ── Outbound GEO (keyword-triggered, first-match) ──
    if _matches_outbound_geo(work_item_text):
        return {
            "outcome": "SUBCASE_OUTBOUND_GEO",
            "subcase": "outbound_geo",
            "hints": hints,
        }

    # ── PetRx and Humax Rx (Rx-medicines department) ──
    if _is_petrx(itm_cls_id, ftc, acc_d_nbr, ptyp, afa):
        hints["ftc_expected"] = "PHARMACY_PETS"
        hints["ftc_matches"] = _ftc_contains(ftc, "PHARMACY_PETS")
        return {
            "outcome": "SUBCASE_PETRX",
            "subcase": "petrx",
            "hints": hints,
        }
    if _is_humax_rx(acc_d_nbr, ptyp, afa):
        return {
            "outcome": "SUBCASE_HUMAX_RX",
            "subcase": "humax_rx",
            "hints": hints,
        }

    # ── Vision Rx (store-restricted) ──
    if _is_vision_rx(vca, sid, ptyp):
        return {
            "outcome": "SUBCASE_VISION_RX",
            "subcase": "vision_rx",
            "hints": hints,
        }

    # ── Tire ──
    if _is_tire(itm_cls_id, ftc):
        hints["product_rt_matches"] = (
            product_rt_item_class_id is None
            or str(product_rt_item_class_id) == "28"
        )
        return {
            "outcome": "SUBCASE_TIRE",
            "subcase": "tire",
            "hints": hints,
        }

    # ── Photo ──
    if _is_photo(itm_cls_id, ftc):
        delivery_ok = (
            product_rt_delivery_method is None
            or str(product_rt_delivery_method).strip() in _PHOTO_DELIVERY_METHODS
        )
        personalization_ok = True
        if _truthy_flag(product_rt_personalizable):
            url = str(product_rt_personalization_url or "")
            personalization_ok = url.startswith(_PHOTO_PERSONALIZATION_PREFIX)
        hints["delivery_method_ok"] = delivery_ok
        hints["personalization_ok"] = personalization_ok
        hints["product_rt_matches"] = (
            product_rt_item_class_id is None
            or str(product_rt_item_class_id) == "52"
        )
        return {
            "outcome": "SUBCASE_PHOTO",
            "subcase": "photo",
            "hints": hints,
        }

    # ── Custom Cake (PFHBRC hierarchy match) ──
    if _is_custom_cake(pfhbrc):
        return {
            "outcome": "SUBCASE_CUSTOM_CAKE",
            "subcase": "custom_cake",
            "hints": hints,
        }

    # ── Delivery Inhome (accDNbr=96 + allowed pfhbrc) ──
    if _is_delivery_inhome(acc_d_nbr, pfhbrc):
        return {
            "outcome": "SUBCASE_DELIVERY_INHOME",
            "subcase": "delivery_inhome",
            "hints": hints,
        }

    # ── Drone (eligibility list short-circuits to the drone subcase) ──
    if sid and sid in DRONE_ELIGIBLE_STORES:
        return {
            "outcome": "SUBCASE_DRONE",
            "subcase": "drone",
            "hints": hints,
        }

    # ── IP Path (online-only internal) ──
    if _is_ip_path(otyp, styp):
        hints["ip_store_eligible"] = sid in IP_PATH_ELIGIBLE_STORES if sid else False
        return {
            "outcome": "SUBCASE_IP_PATH",
            "subcase": "ip_path",
            "hints": hints,
        }

    # ── Default ──
    return {
        "outcome": "SUBCASE_MAIN",
        "subcase": "main",
        "hints": hints,
    }


# ── Keyword-based explicit sub-case routing ───────────────────────────


# Each row: (pattern, subcase, outcome).
# Patterns use word boundaries and are matched case-insensitively against
# the user's raw query text.  Order is irrelevant — all matches are
# collected and reconciled.  Two-word phrases (HUMAN RX, CUSTOM CAKE,
# IP PATH) use ``\s+`` between tokens so any whitespace count is tolerated.
_SUBCASE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"\bTIRE\b",                "tire",        "SUBCASE_TIRE"),
    (r"\bPHOTOS?\b",             "photo",       "SUBCASE_PHOTO"),
    (r"\bVISION\b",              "vision_rx",   "SUBCASE_VISION_RX"),
    (r"\bHUMAN\s+RX\b",          "humax_rx",    "SUBCASE_HUMAX_RX"),
    (r"\bPET\b",                 "petrx",       "SUBCASE_PETRX"),
    (r"\b(?:CUSTOM\s+)?CAKE\b",  "custom_cake", "SUBCASE_CUSTOM_CAKE"),
    (r"\bIP\s+PATH\b",           "ip_path",     "SUBCASE_IP_PATH"),
    (r"\bDRONE\b",               "drone",       "SUBCASE_DRONE"),
)
_BARE_RX_PATTERN = r"\bRX\b"


def route_subcase_by_query(work_item_text: Any = None) -> dict[str, Any]:
    """Word-boundary keyword routing for explicit sub-case requests.

    Scans the user's raw query for the sub-case keyword vocabulary.  All
    matches are collected; the outcome is:

      * Exactly one distinct sub-case matched → that sub-case is returned
        as the explicit route (``SUBCASE_TIRE``, ``SUBCASE_PHOTO``,
        ``SUBCASE_VISION_RX``, ``SUBCASE_PETRX``, ``SUBCASE_HUMAX_RX``,
        ``SUBCASE_CUSTOM_CAKE``, ``SUBCASE_IP_PATH``, ``SUBCASE_DRONE``).
      * Multiple distinct sub-cases matched → ``SUBCASE_KEYWORD_CONFLICT``
        (the orchestrator asks the user to clarify).
      * Zero sub-case matches but a bare ``RX`` token is present →
        ``SUBCASE_RX_AMBIGUOUS`` (the orchestrator asks whether the user
        meant PET RX, HUMAN RX, or VISION RX).
      * Zero matches → ``SUBCASE_NONE`` (fall through to the
        attribute-based dispatcher).

    The keyword layer is independent of and additive to the
    attribute-based :func:`dispatch_subcase` — both run on every call and
    the orchestrator reconciles their outcomes (keyword wins when it
    matches the attribute dispatcher; otherwise the user is told about
    the mismatch and the flow falls back to ``main``).
    """
    text = str(work_item_text or "")
    if not text.strip():
        return {
            "outcome": "SUBCASE_NONE",
            "subcase": None,
            "matched_keywords": [],
        }

    matches: list[tuple[str, str, str]] = []
    for pattern, subcase, outcome in _SUBCASE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matches.append((pattern, subcase, outcome))

    distinct_subcases = sorted({m[1] for m in matches})

    if len(distinct_subcases) > 1:
        return {
            "outcome": "SUBCASE_KEYWORD_CONFLICT",
            "subcase": None,
            "matched_keywords": distinct_subcases,
            "reason": (
                "More than one explicit sub-case keyword matched the "
                "query; ask the user to clarify which sub-case applies."
            ),
        }

    if len(distinct_subcases) == 1:
        m = matches[0]
        return {
            "outcome": m[2],
            "subcase": m[1],
            "matched_keywords": [m[1]],
        }

    # No specific sub-case keyword.  A bare ``RX`` token without
    # PET / HUMAN / VISION qualifier is ambiguous — refuse to route.
    if re.search(_BARE_RX_PATTERN, text, re.IGNORECASE):
        return {
            "outcome": "SUBCASE_RX_AMBIGUOUS",
            "subcase": None,
            "matched_keywords": ["rx"],
            "reason": (
                "Bare 'RX' detected without a qualifying keyword; ask "
                "the user whether they mean PET RX, HUMAN RX, or "
                "VISION RX."
            ),
        }

    return {
        "outcome": "SUBCASE_NONE",
        "subcase": None,
        "matched_keywords": [],
    }


# ── MDM per-store projection ──────────────────────────────────────────


def analyze_mdm_store_status(
    mdm_response: Any = None,
    store_id: Any = None,
) -> dict[str, Any]:
    """Project the Derivator MDM bulk seller_nodes response onto a store.

    The MDM endpoint returns one record per seller carrying a ``payload``
    map keyed by store id (decimal string).  This helper picks out the
    entry for ``store_id`` and surfaces the per-store gates the SOP
    needs:

      * ``store_status``   — ``payload[<store_id>].sts`` (``OPEN`` is
        the open-gate; anything else is treated as not-open).
      * ``state_code``     — ``payload[<store_id>].nas.ste``.
      * ``business_code``  — ``payload[<store_id>].nas.bc``.
      * ``timezone``       — ``payload[<store_id>].nas.tzc``.
      * ``activities``     — list of ``{act, fo, ias}`` rows from
        ``payload[<store_id>].aps`` (caller-side gating, not used to
        decide the outcome).

    Outcomes:
      * ``MDM_STORE_OPEN``                — store exists and ``sts == "OPEN"``.
      * ``MDM_STORE_NOT_OPEN``            — store exists but ``sts != "OPEN"``.
      * ``MDM_STORE_NOT_IN_SELLER_MAP``   — store id absent from payload.
    """
    sid = _coerce_store_id(store_id)
    payload = _walk(mdm_response, "payload") if isinstance(mdm_response, dict) else None
    if not isinstance(payload, dict):
        # Some upstream wrappers nest the seller map under ``payload.payload``
        payload = _walk(mdm_response, "payload", "payload")
    if not isinstance(payload, dict):
        return {
            "outcome": "MDM_STORE_NOT_IN_SELLER_MAP",
            "store_id": sid,
            "store_status": None,
            "state_code": None,
            "business_code": None,
            "timezone": None,
            "activities": [],
        }

    store = payload.get(sid)
    if not isinstance(store, dict):
        return {
            "outcome": "MDM_STORE_NOT_IN_SELLER_MAP",
            "store_id": sid,
            "store_status": None,
            "state_code": None,
            "business_code": None,
            "timezone": None,
            "activities": [],
        }

    sts = store.get("sts")
    nas = store.get("nas") if isinstance(store.get("nas"), dict) else {}
    raw_aps = store.get("aps") if isinstance(store.get("aps"), list) else []
    activities: list[dict[str, Any]] = []
    for row in raw_aps:
        if isinstance(row, dict):
            activities.append({
                "act": row.get("act"),
                "fo": row.get("fo"),
                "ias": row.get("ias"),
            })

    outcome = "MDM_STORE_OPEN" if str(sts).strip().upper() == "OPEN" else "MDM_STORE_NOT_OPEN"
    return {
        "outcome": outcome,
        "store_id": sid,
        "store_status": sts,
        "state_code": nas.get("ste"),
        "business_code": nas.get("bc"),
        "timezone": nas.get("tzc"),
        "activities": activities,
    }


# ── Derivator MDM fetch + per-store projection ───────────────────────


_MDM_HTTP_STATUS_TO_OUTCOME: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "AUTH_ERROR",
    403: "AUTH_ERROR",
    404: "MDM_STORE_NOT_IN_SELLER_MAP",
    429: "RATE_LIMITED",
    500: "UPSTREAM_ERROR",
    503: "UPSTREAM_UNAVAILABLE",
}


def _mdm_config() -> dict[str, str]:
    """Read the Derivator MDM block from Dynaconf as a flat-key dict."""
    from agent_factory.infrastructure.settings import get_config
    cfg = get_config()
    block = getattr(cfg, "LIMO_PATH_DERIVATOR_MDM", None)
    out: dict[str, str] = {}
    if block is None:
        return out
    try:
        keys = list(block.keys())
    except Exception:
        keys = []
    for k in keys:
        try:
            v = block.get(k)
        except Exception:
            v = None
        if v is not None:
            out[k] = str(v)
    return out


async def fetch_mdm_store_status(
    seller_id: Any = None,
    store_id: Any = None,
) -> dict[str, Any]:
    """Fetch the Derivator MDM seller_nodes record and project onto a store.

    POSTs to ``{LIMO_PATH_DERIVATOR_MDM_BASE_URL}/operations/db/readDb``
    with the canonical Cassandra-read body keyed by ``seller_id`` and
    ``node_type: STORE``, then delegates to
    :func:`analyze_mdm_store_status` to project the bulk seller_nodes
    payload onto ``store_id``.

    This single-call shape exists because the MDM bulk payload is
    multi-MB; piping it through the LLM as a tool observation breaks the
    chat-message size cap.  The HTTP fetch and the per-store projection
    are performed inside one ``python_function`` so the LLM only ever
    sees the small projected dict.

    Outcomes (from :func:`analyze_mdm_store_status`):
      * ``MDM_STORE_OPEN``              — store exists and ``sts == "OPEN"``.
      * ``MDM_STORE_NOT_OPEN``          — store exists but ``sts != "OPEN"``.
      * ``MDM_STORE_NOT_IN_SELLER_MAP`` — store id absent from seller payload.
    Plus the usual HTTP error outcomes (BAD_REQUEST / AUTH_ERROR /
    RATE_LIMITED / UPSTREAM_ERROR / UPSTREAM_UNAVAILABLE).
    """
    import httpx

    sid_seller = (str(seller_id).strip() if seller_id is not None else "")
    sid_store = _coerce_store_id(store_id)
    if not sid_seller:
        return {"outcome": "BAD_REQUEST", "error": "seller_id is required"}
    if not sid_store:
        return {"outcome": "BAD_REQUEST", "error": "store_id is required"}

    block = _mdm_config()
    base_url = block.get("LIMO_PATH_DERIVATOR_MDM_BASE_URL", "")
    cookie = block.get("LIMO_PATH_DERIVATOR_MDM_COOKIE", "")
    if not base_url:
        return {
            "outcome": "BAD_REQUEST",
            "error": "LIMO_PATH_DERIVATOR_MDM_BASE_URL not configured",
        }

    url = f"{base_url.rstrip('/')}/operations/db/readDb"
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    body = {
        "keyspace":    "inbound",
        "table":       "seller_nodes",
        "clusterName": "DERIVATOR_PROD_CASSANDRA",
        "id": {
            "id":        sid_seller,
            "node_type": "STORE",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException:
        return {"outcome": "UPSTREAM_UNAVAILABLE", "error": "timeout"}
    except Exception as exc:
        return {"outcome": "UPSTREAM_ERROR", "error": str(exc)}

    status = resp.status_code
    if status >= 400:
        return {
            "outcome": _MDM_HTTP_STATUS_TO_OUTCOME.get(status, "UPSTREAM_ERROR"),
            "status_code": status,
        }

    try:
        data = resp.json()
    except Exception:
        return {"outcome": "MDM_STORE_NOT_IN_SELLER_MAP", "error": "non-json response"}

    return analyze_mdm_store_status(mdm_response=data, store_id=sid_store)


# ── Product RT fetch ─────────────────────────────────────────────────


_PRODUCT_RT_HTTP_STATUS_TO_OUTCOME: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "AUTH_ERROR",
    403: "AUTH_ERROR",
    404: "PRODUCT_RT_MISSING",
    429: "RATE_LIMITED",
    500: "UPSTREAM_ERROR",
    503: "UPSTREAM_UNAVAILABLE",
}


def _product_rt_config() -> dict[str, str]:
    """Read the Product RT block from Dynaconf as a flat-key dict.

    The block lives at ``[default.limo_path_product_rt]`` in secrets.toml
    keyed by the canonical flat names (``LIMO_PATH_PRODUCT_RT_*``).  We
    surface those values as a plain dict so the caller never has to know
    about ``DynaBox`` semantics.
    """
    from agent_factory.infrastructure.settings import get_config
    cfg = get_config()
    block = getattr(cfg, "LIMO_PATH_PRODUCT_RT", None)
    out: dict[str, str] = {}
    if block is None:
        return out
    try:
        keys = list(block.keys())
    except Exception:
        keys = []
    for k in keys:
        try:
            v = block.get(k)
        except Exception:
            v = None
        if v is not None:
            out[k] = str(v)
    return out


async def fetch_product_attributes(product_id: Any = None) -> dict[str, Any]:
    """Call Product RT by ``product_id`` and project the SOP slots.

    Issues ``POST /itemstore-item-read-app/services/product`` with a
    JSON-array body (``[{"productId": "<pid>"}]``) and the Walmart
    product-store headers.  Returns the typed-attribute leaves the SOP
    needs:

      * ``product_rt_item_class_id``       — ``payload[0].productAttributes.item_class_id.value``
      * ``product_rt_delivery_method``     — ``payload[0].productAttributes.delivery_method.value``
      * ``product_rt_personalization_url`` — ``payload[0].productAttributes.personalization_url.value``
      * ``product_rt_product_type``        — ``payload[0].productType``
      * ``product_rt_product_type_id``     — ``payload[0].productTypeId``
      * ``product_rt_product_segment``     — ``payload[0].productSegment``

    Outcomes:
      * ``PRODUCT_RT_PRESENT``  — payload[0].productAttributes.item_class_id.value resolved.
      * ``PRODUCT_RT_MISSING``  — no payload row, no productAttributes, or item_class_id absent.
      * ``BAD_REQUEST``         — missing/empty product_id or Product RT base URL not configured.
      * ``AUTH_ERROR`` / ``RATE_LIMITED`` / ``UPSTREAM_ERROR`` /
        ``UPSTREAM_UNAVAILABLE`` — surfaced from the HTTP status code.
    """
    import httpx

    pid = (str(product_id).strip() if product_id is not None else "")
    if not pid:
        return {"outcome": "BAD_REQUEST", "error": "product_id is required"}

    block = _product_rt_config()
    base_url = block.get("LIMO_PATH_PRODUCT_RT_BASE_URL", "")
    if not base_url:
        return {
            "outcome": "BAD_REQUEST",
            "error": "LIMO_PATH_PRODUCT_RT_BASE_URL not configured",
        }
    headers = {
        "Content-Type":    "application/json",
        "response_groups": block.get("LIMO_PATH_PRODUCT_RT_RESPONSE_GROUPS", ""),
        "x-o-bu":          block.get("LIMO_PATH_PRODUCT_RT_BU", ""),
        "accept-language": block.get("LIMO_PATH_PRODUCT_RT_ACCEPT_LANGUAGE", ""),
    }
    body = [{"productId": pid}]
    url = f"{base_url.rstrip('/')}/itemstore-item-read-app/services/product"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException:
        return {"outcome": "UPSTREAM_UNAVAILABLE", "error": "timeout"}
    except Exception as exc:
        return {"outcome": "UPSTREAM_ERROR", "error": str(exc)}

    status = resp.status_code
    if status >= 400:
        return {
            "outcome": _PRODUCT_RT_HTTP_STATUS_TO_OUTCOME.get(status, "UPSTREAM_ERROR"),
            "status_code": status,
        }

    try:
        data = resp.json()
    except Exception:
        return {"outcome": "PRODUCT_RT_MISSING", "error": "non-json response"}

    payload = data.get("payload") if isinstance(data, dict) else None
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        return {"outcome": "PRODUCT_RT_MISSING", "product_id": pid}

    record = payload[0]
    attrs = record.get("productAttributes") if isinstance(record.get("productAttributes"), dict) else {}

    def _attr_value(name: str) -> Optional[str]:
        entry = attrs.get(name)
        if isinstance(entry, dict):
            v = entry.get("value")
            if v is None:
                return None
            return str(v)
        return None

    item_class_id = _attr_value("item_class_id")
    out: dict[str, Any] = {
        "outcome":                        "PRODUCT_RT_PRESENT" if item_class_id else "PRODUCT_RT_MISSING",
        "product_id":                     pid,
        "product_rt_item_class_id":       item_class_id,
        "product_rt_delivery_method":     _attr_value("delivery_method"),
        "product_rt_personalization_url": _attr_value("personalization_url"),
        "product_rt_product_type":        record.get("productType"),
        "product_rt_product_type_id":     record.get("productTypeId"),
        "product_rt_product_segment":     record.get("productSegment"),
    }
    return out


# ── AURUM analyzer ────────────────────────────────────────────────────


def _walk(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return None
    return cur


def _normalize_path_list(entry: Any) -> list[str]:
    if entry is None:
        return []
    if isinstance(entry, list):
        return [str(x) for x in entry if x]
    return [str(entry)]


def analyze_aurum_paths(
    aurum_response: Any = None,
    store_id: Any = None,
) -> dict[str, Any]:
    """Filter AURUM inclusions/exclusions to the canonical 30-path list.

    Walks ``offerNodeAttr.nodes.<store_id>.finalEligibilities.path``.
    Each entry the response carries may be a string (the SOP's rule id)
    or an object with ``ruleId`` / ``computedReason`` keys; both shapes
    are accepted.

    Outcomes:
      * ``AURUM_PATHS_PRESENT`` — at least one inclusion or exclusion.
      * ``AURUM_NO_PATHS``      — neither inclusions nor exclusions.
      * ``AURUM_NOT_FOUND``     — store_id absent from offerNodeAttr.nodes.
    """
    sid = _coerce_store_id(store_id)
    node = _walk(aurum_response, "offerNodeAttr", "nodes", sid)
    if node is None and isinstance(aurum_response, dict):
        # The response may be wrapped under ``payload`` or already be the
        # ``offerNodeAttr`` object.
        node = _walk(aurum_response, "payload", "offerNodeAttr", "nodes", sid)
    if node is None:
        return {
            "outcome": "AURUM_NOT_FOUND",
            "store_id": sid,
            "inclusions": [],
            "exclusions": [],
        }

    inclusions_raw = _walk(node, "finalEligibilities", "path", "inclusions") or {}
    exclusions_raw = _walk(node, "finalEligibilities", "path", "exclusions") or {}

    inclusions: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []

    def _project(path_key: str, blob: Any) -> dict[str, Any]:
        if isinstance(blob, dict):
            rule_ids = _normalize_path_list(blob.get("ruleId"))
            reasons = _normalize_path_list(blob.get("computedReason"))
        else:
            rule_ids = _normalize_path_list(blob)
            reasons = []
        return {
            "path": path_key,
            "rule_ids": rule_ids,
            "rule_ids_csv": ", ".join(rule_ids) if rule_ids else "",
            "computed_reasons": reasons,
        }

    if isinstance(inclusions_raw, dict):
        for k, v in inclusions_raw.items():
            if k in _ALLOWED_PATHS_SET:
                inclusions.append(_project(k, v))
    if isinstance(exclusions_raw, dict):
        for k, v in exclusions_raw.items():
            if k in _ALLOWED_PATHS_SET:
                exclusions.append(_project(k, v))

    if not inclusions and not exclusions:
        return {
            "outcome": "AURUM_NO_PATHS",
            "store_id": sid,
            "inclusions": [],
            "exclusions": [],
        }

    return {
        "outcome": "AURUM_PATHS_PRESENT",
        "store_id": sid,
        "inclusions": inclusions,
        "exclusions": exclusions,
    }


# ── DEW analyzer ──────────────────────────────────────────────────────


def analyze_dew_paths(dew_response: Any = None) -> dict[str, Any]:
    """Flatten ``ftxn.outboundPaths`` into [{path, methods, types}].

    Outcomes:
      * ``DEW_PATHS_PRESENT`` — at least one ``outboundPaths`` row.
      * ``DEW_NO_PATHS``      — empty or missing outboundPaths.
    """
    outbound = _walk(dew_response, "ftxn", "outboundPaths")
    if outbound is None and isinstance(dew_response, dict):
        outbound = _walk(dew_response, "payload", "ftxn", "outboundPaths")
    if not isinstance(outbound, list) or not outbound:
        return {"outcome": "DEW_NO_PATHS", "paths": []}

    rows: list[dict[str, Any]] = []
    for entry in outbound:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("fulfillmentPath") or "").strip()
        if not path:
            continue
        types_raw = entry.get("types") or []
        if isinstance(types_raw, list):
            types = [str(t) for t in types_raw if t]
        else:
            types = [str(types_raw)] if types_raw else []
        methods_raw = entry.get("fulfillmentMethods") or entry.get("fulfillmentMethod")
        if isinstance(methods_raw, list):
            methods = [str(m) for m in methods_raw if m]
        elif methods_raw:
            methods = [str(methods_raw)]
        else:
            # Derive the method from the path segment when not surfaced.
            segs = path.split("|")
            methods = [segs[1]] if len(segs) > 1 else []
        rows.append(
            {
                "path": path,
                "fulfillment_methods": methods,
                "fulfillment_methods_csv": ", ".join(methods),
                "types": types,
                "types_csv": ", ".join(types),
            }
        )

    if not rows:
        return {"outcome": "DEW_NO_PATHS", "paths": []}
    return {"outcome": "DEW_PATHS_PRESENT", "paths": rows}


# ── Consolidated analyzer ─────────────────────────────────────────────


_METHOD_KEYS: tuple[str, ...] = ("UNSCHEDULED", "SCHEDULED")
_TYPE_KEYS: tuple[str, ...] = (
    "INVENTORY_NODE",
    "CUSTOMER_DISPENSE_NODE",
    "TRANSFER_NODE",
    "INBOUND_NODE",
    "RESTRICTED_NODE",
)


_TRUE_TOKENS = frozenset({"true", "1", "yes", "y", "t"})
_FALSE_TOKENS = frozenset({"false", "0", "no", "n", "f"})


def _norm_bool(value: Any) -> Optional[bool]:
    """Best-effort bool coercion; returns ``None`` when unparseable."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if not token:
        return None
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    return None


def _resolve_eligibility(
    eligible_flag: Any, node_list: Iterable[str], sid: str
) -> bool:
    """Apply the SOP's top-level eligible/nodes truth table for one path.

    Truth table:
      eligible=true  + nodes contains sid → True
      eligible=true  + nodes missing sid  → False
      eligible=true  + nodes empty        → False (nobody eligible)
      eligible=false + nodes contains sid → False
      eligible=false + nodes missing sid  → True
      eligible=false + nodes empty        → True  (everyone eligible)
      eligible unparseable / None         → fall back to membership

    Strings (``"true"`` / ``"false"``) are normalised via ``_norm_bool``.
    """
    nodes = {str(n) for n in (node_list or [])}
    flag = _norm_bool(eligible_flag)
    if not sid:
        return bool(flag)
    if flag is None:
        return sid in nodes
    if not nodes:
        # eligible=true & empty → nobody eligible
        # eligible=false & empty → everyone eligible
        return not flag
    if flag:
        return sid in nodes
    return sid not in nodes


def analyze_consolidated_paths(
    consolidated_response: Any = None,
    store_id: Any = None,
) -> dict[str, Any]:
    """Walk consolidatedResponse[].offerNodePayload.nodeData.STORE for a store.

    Each STORE path is a 2-method × 5-node-type matrix; each
    ``nodeExceptions`` key independently gates ONE dimension.  The
    projection is fully deterministic — the closure / chat response
    renders the breakdown verbatim, the LLM never paraphrases.

    Per-path row shape::

        {
          "path": "STORE|...",
          "store_eligible": bool,           # top-level (eligible flag + nodes)
          "restricted": bool,               # store appears in RESTRICTED_NODE
          "verdict": "STORE_ELIGIBLE" | "STORE_PARTIAL"
                   | "STORE_NOT_ELIGIBLE" | "STORE_RESTRICTED",
          "fulfillment_methods": [...],     # eligible methods (was "allowed")
          "fulfillment_methods_csv": "...",
          "blocked_methods": [...],
          "blocked_methods_csv": "...",
          "types": [...],                   # eligible node-types
          "types_csv": "...",
          "blocked_types": [...],
          "blocked_types_csv": "...",
        }

    Outcomes:
      * ``CONSOLIDATED_PATHS_PRESENT`` — at least one path row resolved.
      * ``CONSOLIDATED_NO_PATHS``      — STORE array empty or missing.
    """
    sid = _coerce_store_id(store_id)

    responses = _walk(consolidated_response, "payload", "consolidatedResponse")
    if responses is None:
        responses = _walk(consolidated_response, "consolidatedResponse")
    if not isinstance(responses, list):
        return {"outcome": "CONSOLIDATED_NO_PATHS", "paths": []}

    rows: list[dict[str, Any]] = []
    for resp in responses:
        store_arr = _walk(resp, "offerNodePayload", "nodeData", "STORE")
        if not isinstance(store_arr, list):
            continue
        for entry in store_arr:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip()
            if not path:
                continue
            top_nodes = entry.get("nodes") or []
            store_eligible = _resolve_eligibility(
                entry.get("eligible"), top_nodes, sid
            )

            exc = entry.get("nodeExceptions") or {}

            # Per-dimension projection — always computed, never collapsed
            # to empty even when the top-level check fails.  Each key is
            # an independent gate: sid present in the key's list ⇒ that
            # dimension is blocked.
            eligible_methods: list[str] = []
            blocked_methods: list[str] = []
            for m in _METHOD_KEYS:
                excluded = exc.get(m) or []
                sid_blocked = bool(sid) and sid in {str(n) for n in excluded}
                if store_eligible and not sid_blocked:
                    eligible_methods.append(m)
                else:
                    blocked_methods.append(m)

            eligible_types: list[str] = []
            blocked_types: list[str] = []
            restricted = False
            for t in _TYPE_KEYS:
                excluded = exc.get(t) or []
                sid_blocked = bool(sid) and sid in {str(n) for n in excluded}
                if t == "RESTRICTED_NODE" and sid_blocked:
                    restricted = True
                if store_eligible and not sid_blocked:
                    eligible_types.append(t)
                else:
                    blocked_types.append(t)

            # Path verdict — derived deterministically from dims.
            if restricted:
                verdict = "STORE_RESTRICTED"
            elif not store_eligible:
                verdict = "STORE_NOT_ELIGIBLE"
            elif not eligible_methods or not eligible_types:
                verdict = "STORE_NOT_ELIGIBLE"
            elif blocked_methods or blocked_types:
                verdict = "STORE_PARTIAL"
            else:
                verdict = "STORE_ELIGIBLE"

            rows.append(
                {
                    "path": path,
                    "store_eligible": store_eligible,
                    "restricted": restricted,
                    "verdict": verdict,
                    "fulfillment_methods": eligible_methods,
                    "fulfillment_methods_csv": ", ".join(eligible_methods),
                    "blocked_methods": blocked_methods,
                    "blocked_methods_csv": ", ".join(blocked_methods),
                    "types": eligible_types,
                    "types_csv": ", ".join(eligible_types),
                    "blocked_types": blocked_types,
                    "blocked_types_csv": ", ".join(blocked_types),
                }
            )

    if not rows:
        return {"outcome": "CONSOLIDATED_NO_PATHS", "paths": []}
    return {"outcome": "CONSOLIDATED_PATHS_PRESENT", "paths": rows}
