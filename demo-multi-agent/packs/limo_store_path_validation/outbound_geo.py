"""Deterministic helpers for the Outbound GEO Restrictions sub-SOP.

Four callable tools, all pure-Python — no LLM reasoning:

``check_offer_fully_created``
    Gate on ODIN ``oa.ofrCrt``.  Emits ``OFFER_FULLY_CREATED`` when the
    flag normalises to true, ``OFFER_NOT_CREATED`` otherwise, and
    ``OFFER_CRT_UNKNOWN`` when the input is missing / unparseable.

``analyze_consolidated_store_v2``
    Walk ``payload.consolidatedResponse[].offerNodePayload.nodeData.STORE[]``
    for the given store id and project each path's eligibility per the
    SOP:
      - ``eligible == true``  + ``nodes`` contains store → ``STORE_ELIGIBLE``
      - ``eligible == false`` + ``nodes`` contains store → ``STORE_NOT_ELIGIBLE``
      - ``nodeExceptions`` populated → ``STORE_NOT_ELIGIBLE`` regardless;
        sub-keys (UNSCHEDULED / SCHEDULED / INVENTORY_NODE /
        CUSTOMER_DISPENSE_NODE / TRANSFER_NODE / INBOUND_NODE /
        RESTRICTED_NODE) are surfaced so the closure can render them.
    Emits ``CONSOLIDATED_STORE_RESTRICTED`` when ``RESTRICTED_NODE``
    contains the store, ``CONSOLIDATED_STORE_ELIGIBLE`` when every path
    is eligible without exceptions, ``CONSOLIDATED_STORE_NOT_ELIGIBLE``
    when any non-RESTRICTED exception fires or the store is missing
    from a path's ``nodes``, and ``CONSOLIDATED_NO_PATHS`` when the
    response yields no STORE rows.

``match_dew_geo_restriction``
    Walk the store-scoped DEW ``forxn[]`` array and emit the entries
    that match the caller's state_code or zip_code.  Entries may key
    on ``state[]`` *or* ``zip[]`` (mixed across the same response);
    both keys are honoured.  Each match yields ``{tag, type, path[],
    storeId, key_matched, matched_value}``.  Emits
    ``DEW_GEO_RESTRICTED`` when any match is produced,
    ``DEW_GEO_CLEAR`` otherwise.

``group_dew_offer_restrictions``
    Walk the offer-level DEW ``forxn[]`` array and group entries by
    individual restriction path.  Each ``forxn`` entry's ``path`` and
    ``state`` are lists; the entry is exploded across its path list
    and ``state`` codes are unioned per distinct path.  Rows are
    sorted by path for deterministic rendering.  Emits
    ``DEW_OFFER_RESTRICTIONS_PRESENT`` when any rows are produced,
    ``DEW_OFFER_NO_RESTRICTIONS`` otherwise.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional


_TRUE_TOKENS = frozenset({"true", "1", "yes", "y", "t"})
_FALSE_TOKENS = frozenset({"false", "0", "no", "n", "f"})

# Canonical nodeExceptions sub-keys per the SOP.  Each key independently
# gates ONE dimension of the path — a non-empty list under a key means
# "this store id is NOT eligible for that dimension"; an empty list means
# "this store id IS eligible for that dimension".  Per-key projection is
# deterministic and surfaced verbatim to the closure.
#
# The 7 canonical keys split into two groups:
#   * METHOD keys     — UNSCHEDULED, SCHEDULED
#   * NODE-TYPE keys  — INVENTORY_NODE, CUSTOMER_DISPENSE_NODE,
#                       TRANSFER_NODE, INBOUND_NODE, RESTRICTED_NODE
# RESTRICTED_NODE is also called out separately because a hit there
# escalates the path-level verdict to "STORE_RESTRICTED" instead of
# plain "STORE_PARTIAL".
_METHOD_KEYS = ("UNSCHEDULED", "SCHEDULED")
_TYPE_KEYS = (
    "INVENTORY_NODE",
    "CUSTOMER_DISPENSE_NODE",
    "TRANSFER_NODE",
    "INBOUND_NODE",
    "RESTRICTED_NODE",
)
_NODE_EXCEPTION_KEYS = _METHOD_KEYS + _TYPE_KEYS


def _norm_bool(value: Any) -> Optional[bool]:
    """Best-effort bool coercion; returns None when unparseable."""
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


def _coerce_id(value: Any) -> str:
    """Coerce a store-id-ish value to a stripped string."""
    if value is None:
        return ""
    return str(value).strip()


def check_offer_fully_created(ofr_crt: Any = None,
                              **_: Any) -> dict[str, Any]:
    """Gate on ODIN ``oa.ofrCrt``.

    Returns one of three outcomes plus a normalised bool so prompts
    can render the raw + interpreted values side by side.
    """
    norm = _norm_bool(ofr_crt)
    if norm is True:
        return {
            "outcome": "OFFER_FULLY_CREATED",
            "ofr_crt_norm": True,
            "reason": "oa.ofrCrt is true — offer is fully created.",
        }
    if norm is False:
        return {
            "outcome": "OFFER_NOT_CREATED",
            "ofr_crt_norm": False,
            "reason": (
                "oa.ofrCrt is not true — offer is not fully created. "
                "Raise a LIMO Ops ticket to publish the offer before "
                "validating outbound GEO restrictions."
            ),
        }
    return {
        "outcome": "OFFER_CRT_UNKNOWN",
        "ofr_crt_norm": None,
        "reason": "oa.ofrCrt is missing or unparseable.",
    }


def _resolve_top_level_eligibility(
    eligible_norm: Optional[bool],
    nodes_set: set[str],
    sid: str,
) -> bool:
    """Apply the SOP's top-level (eligible flag + nodes) rule for one path.

    Truth table:
      eligible=true  + nodes contains sid → True
      eligible=true  + nodes does NOT contain sid → False
      eligible=true  + nodes empty              → False (nobody eligible)
      eligible=false + nodes contains sid → False
      eligible=false + nodes does NOT contain sid → True
      eligible=false + nodes empty              → True  (everyone eligible)
      eligible unparseable / None               → fall back to membership
    """
    if not sid:
        # No caller store — collapse to a permissive view.
        return bool(eligible_norm)
    if eligible_norm is None:
        return sid in nodes_set
    if not nodes_set:
        # eligible=true & empty → nobody eligible
        # eligible=false & empty → everyone eligible
        return not eligible_norm
    if eligible_norm:
        return sid in nodes_set
    return sid not in nodes_set


def _project_dimensions(
    node_exceptions: Any,
    sid: str,
    top_level_eligible: bool,
) -> dict[str, Any]:
    """Project the nodeExceptions block into deterministic per-key flags.

    Per the SOP, each nodeException key is an INDEPENDENT gate:
      * key contains sid → that dimension is NOT eligible for the caller
      * key empty (or absent) → that dimension IS eligible for the caller

    METHOD keys (``UNSCHEDULED``, ``SCHEDULED``) and TYPE keys (the five
    node-type names) are projected separately so the closure can render
    "Eligible for SCHEDULED but not UNSCHEDULED" verbatim — no LLM
    paraphrasing.

    When the path is NOT eligible at the top level, every dimension is
    forced to ``False`` because the per-dimension gates only matter when
    the store is in scope for the path at all.
    """
    out_methods: dict[str, dict[str, Any]] = {}
    out_types: dict[str, dict[str, Any]] = {}
    other: dict[str, list[str]] = {}

    exc = node_exceptions if isinstance(node_exceptions, dict) else {}

    def _project_key(key: str, raw: Any) -> dict[str, Any]:
        nodes = raw if isinstance(raw, list) else []
        nodes_str = [_coerce_id(n) for n in nodes if n is not None]
        blocked = bool(sid) and sid in nodes_str
        return {
            "eligible": (top_level_eligible and not blocked),
            "blocked_in_exceptions": blocked,
            "blocked_nodes": nodes_str,
        }

    # Project METHOD keys (UNSCHEDULED, SCHEDULED).
    for m in _METHOD_KEYS:
        out_methods[m] = _project_key(m, exc.get(m))

    # Project TYPE keys (5 node-type names).
    for t in _TYPE_KEYS:
        out_types[t] = _project_key(t, exc.get(t))

    # Pass through unknown keys (e.g. nodeExceptions.eligible) for
    # observability — these never feed the verdict.
    for key, raw in exc.items():
        if key in _NODE_EXCEPTION_KEYS:
            continue
        if isinstance(raw, list):
            other[str(key)] = [_coerce_id(n) for n in raw if n is not None]
        else:
            other[str(key)] = []

    eligible_methods = [m for m in _METHOD_KEYS if out_methods[m]["eligible"]]
    blocked_methods = [m for m in _METHOD_KEYS if not out_methods[m]["eligible"]]
    eligible_types = [t for t in _TYPE_KEYS if out_types[t]["eligible"]]
    blocked_types = [t for t in _TYPE_KEYS if not out_types[t]["eligible"]]
    store_in_restricted = out_types["RESTRICTED_NODE"]["blocked_in_exceptions"]

    return {
        "methods": out_methods,
        "types": out_types,
        "other": other,
        "eligible_methods": eligible_methods,
        "blocked_methods": blocked_methods,
        "eligible_types": eligible_types,
        "blocked_types": blocked_types,
        "store_in_restricted": store_in_restricted,
    }


def analyze_consolidated_store_v2(consolidated_response: Any = None,
                                  store_id: Any = None,
                                  **_: Any) -> dict[str, Any]:
    """Project Consolidated v2 STORE paths for the caller's store id.

    Per the SOP, each path is a 2-method × 5-node-type matrix and each
    nodeException key independently gates one dimension.  The projection
    is fully deterministic so the closure / chat response can render the
    breakdown verbatim — the LLM never paraphrases the eligibility view.

    Per-path schema:
      ``{
          path, eligible, top_level_eligible, store_in_nodes, nodes,
          eligible_methods,   blocked_methods,
          eligible_types,     blocked_types,
          method_breakdown,   type_breakdown,
          restricted,         verdict,
          node_exceptions,    node_exceptions_other
      }``

    Path verdicts:
      * ``STORE_RESTRICTED``    — store appears in ``RESTRICTED_NODE``;
                                  hard fail (overrides PARTIAL).
      * ``STORE_NOT_ELIGIBLE``  — top-level check fails, OR every method
                                  is blocked, OR every node-type is
                                  blocked (path is unreachable).
      * ``STORE_PARTIAL``       — some dimensions blocked, some allowed;
                                  caller can still use the allowed subset.
      * ``STORE_ELIGIBLE``      — no exceptions fire; full path is open.

    Top-level outcomes:
      * ``CONSOLIDATED_STORE_RESTRICTED``   — any path hits RESTRICTED_NODE.
      * ``CONSOLIDATED_STORE_NOT_ELIGIBLE`` — every path is fully blocked.
      * ``CONSOLIDATED_STORE_PARTIAL``      — any path is PARTIAL, or a mix
                                              of ELIGIBLE + NOT_ELIGIBLE.
      * ``CONSOLIDATED_STORE_ELIGIBLE``     — every path is fully open.
      * ``CONSOLIDATED_NO_PATHS``           — STORE block empty / missing.
    """
    sid = _coerce_id(store_id)
    rows: list[dict[str, Any]] = []
    any_restricted = False
    any_partial = False
    any_eligible = False
    any_not_eligible = False

    cr: list[Any] = []
    if isinstance(consolidated_response, dict):
        payload = consolidated_response.get("payload") or {}
        cr = payload.get("consolidatedResponse") or []
    elif isinstance(consolidated_response, list):
        cr = consolidated_response

    for entry in cr or []:
        if not isinstance(entry, dict):
            continue
        node_data = (
            (entry.get("offerNodePayload") or {}).get("nodeData") or {}
        )
        for path_entry in node_data.get("STORE") or []:
            if not isinstance(path_entry, dict):
                continue
            path = str(path_entry.get("path") or "").strip()
            if not path:
                continue

            eligible_norm = _norm_bool(path_entry.get("eligible"))
            nodes_raw = path_entry.get("nodes") or []
            nodes_str = [_coerce_id(n) for n in nodes_raw if n is not None]
            nodes_set = set(nodes_str)
            store_in_nodes = bool(sid) and sid in nodes_set
            top_level_eligible = _resolve_top_level_eligibility(
                eligible_norm, nodes_set, sid
            )

            dims = _project_dimensions(
                path_entry.get("nodeExceptions"),
                sid,
                top_level_eligible,
            )

            # Path-level verdict — derived from the deterministic dims.
            if dims["store_in_restricted"]:
                verdict = "STORE_RESTRICTED"
                any_restricted = True
            elif not top_level_eligible:
                verdict = "STORE_NOT_ELIGIBLE"
                any_not_eligible = True
            elif not dims["eligible_methods"] or not dims["eligible_types"]:
                # No reachable method OR no reachable node-type → unreachable.
                verdict = "STORE_NOT_ELIGIBLE"
                any_not_eligible = True
            elif dims["blocked_methods"] or dims["blocked_types"]:
                verdict = "STORE_PARTIAL"
                any_partial = True
            else:
                verdict = "STORE_ELIGIBLE"
                any_eligible = True

            # Backward-compat shape: ``node_exceptions`` mirrors the
            # legacy {key: {nodes, store_matched}} dict so the closure
            # template's existing iteration still works.
            legacy_node_exceptions: dict[str, Any] = {}
            for k in _NODE_EXCEPTION_KEYS:
                proj = (
                    dims["methods"].get(k)
                    if k in _METHOD_KEYS
                    else dims["types"].get(k)
                )
                if proj is None:
                    continue
                legacy_node_exceptions[k] = {
                    "nodes": proj["blocked_nodes"],
                    "store_matched": proj["blocked_in_exceptions"],
                }

            rows.append({
                "path": path,
                "eligible": eligible_norm,
                "top_level_eligible": top_level_eligible,
                "store_in_nodes": store_in_nodes,
                "nodes": nodes_str,
                "method_breakdown": dims["methods"],
                "type_breakdown": dims["types"],
                "eligible_methods": dims["eligible_methods"],
                "blocked_methods": dims["blocked_methods"],
                "eligible_methods_csv": ", ".join(dims["eligible_methods"]),
                "blocked_methods_csv": ", ".join(dims["blocked_methods"]),
                "eligible_types": dims["eligible_types"],
                "blocked_types": dims["blocked_types"],
                "eligible_types_csv": ", ".join(dims["eligible_types"]),
                "blocked_types_csv": ", ".join(dims["blocked_types"]),
                "restricted": dims["store_in_restricted"],
                "node_exceptions": legacy_node_exceptions,
                "node_exceptions_other": dims["other"],
                "verdict": verdict,
            })

    if not rows:
        return {
            "outcome": "CONSOLIDATED_NO_PATHS",
            "paths": [],
            "store_restricted": False,
            "reason": (
                "Consolidated v2 returned no STORE paths for this "
                "(offer, store) — raise a LIMO Ops ticket."
            ),
        }

    if any_restricted:
        outcome = "CONSOLIDATED_STORE_RESTRICTED"
        reason = (
            f"Store {sid or '—'} appears in RESTRICTED_NODE on at least "
            f"one path — restricted."
        )
    elif any_not_eligible and not (any_eligible or any_partial):
        outcome = "CONSOLIDATED_STORE_NOT_ELIGIBLE"
        reason = "Every Consolidated STORE path is fully blocked."
    elif any_partial or (any_eligible and any_not_eligible):
        outcome = "CONSOLIDATED_STORE_PARTIAL"
        reason = (
            "Mixed eligibility — at least one path is partially restricted; "
            "see the per-path method/type breakdown."
        )
    else:
        outcome = "CONSOLIDATED_STORE_ELIGIBLE"
        reason = "All Consolidated STORE paths are fully eligible."

    return {
        "outcome": outcome,
        "paths": rows,
        "store_restricted": any_restricted,
        "reason": reason,
    }


def _state_match(states: Any, state_code: str) -> bool:
    if not state_code:
        return False
    if not isinstance(states, (list, tuple, set)):
        return False
    target = state_code.strip().upper()
    return any(str(s).strip().upper() == target for s in states)


def _zip_match(zips: Any, zip_code: str) -> bool:
    if not zip_code:
        return False
    if not isinstance(zips, (list, tuple, set)):
        return False
    target = zip_code.strip()
    return any(str(z).strip() == target for z in zips)


def match_dew_geo_restriction(forxn: Optional[Iterable[Any]] = None,
                              store_id: Any = None,
                              state_code: Any = None,
                              zip_code: Any = None,
                              **_: Any) -> dict[str, Any]:
    """Match store-scoped DEW ``forxn`` entries against caller geo.

    Inputs:
      - ``forxn``      : list returned by the store-scoped DEW lookup.
      - ``store_id``   : caller's store id (filters non-matching entries
                         when ``forxn[].storeId`` is set; entries with
                         no storeId pass through).
      - ``state_code`` : 2-char US state code (e.g. ``"AR"``).
      - ``zip_code``   : 5-digit US ZIP (e.g. ``"72404"``).

    Output:
      ``{outcome, matches: [{tag, type, path[], storeId, key_matched,
                             matched_value}, ...]}``
      ``key_matched`` is ``"state"`` or ``"zip"`` so the closure can
      label the row.  When both keys match the same entry, ``state``
      wins (we still surface both via ``matched_value`` if needed in
      future).
    """
    sid = _coerce_id(store_id)
    state_in = _coerce_id(state_code).upper() if state_code else ""
    zip_in = _coerce_id(zip_code) if zip_code else ""

    matches: list[dict[str, Any]] = []
    for entry in forxn or []:
        if not isinstance(entry, dict):
            continue
        entry_sid = _coerce_id(entry.get("storeId"))
        if sid and entry_sid and entry_sid != sid:
            # Skip entries scoped to a different store.
            continue
        states = entry.get("state") or []
        zips = entry.get("zip") or []
        state_hit = _state_match(states, state_in)
        zip_hit = _zip_match(zips, zip_in)
        if not (state_hit or zip_hit):
            continue

        paths = entry.get("path") or []
        if isinstance(paths, str):
            paths = [paths]
        paths_clean = [str(p).strip() for p in paths if p]

        key_matched = "state" if state_hit else "zip"
        matched_value = state_in if state_hit else zip_in

        matches.append({
            "tag":           entry.get("tag"),
            "type":          entry.get("type"),
            "path":          paths_clean,
            "storeId":       entry_sid or sid or None,
            "key_matched":   key_matched,
            "matched_value": matched_value,
        })

    if matches:
        return {
            "outcome": "DEW_GEO_RESTRICTED",
            "matches": matches,
            "reason": (
                f"{len(matches)} DEW restriction(s) match caller "
                f"state={state_in or '—'} / zip={zip_in or '—'}."
            ),
        }
    return {
        "outcome": "DEW_GEO_CLEAR",
        "matches": [],
        "reason": (
            f"No DEW restriction matched state={state_in or '—'} / "
            f"zip={zip_in or '—'}."
        ),
    }


def group_dew_offer_restrictions(forxn: Optional[Iterable[Any]] = None,
                                 **_: Any) -> dict[str, Any]:
    """Group offer-level DEW ``forxn`` entries by individual path.

    Each entry's ``path`` is a list; explode the entry across that
    list and union its ``state`` codes per distinct path.  Rows are
    sorted by path so the closure renders deterministically.

    ``zip`` is ignored here — the offer-level grouper is keyed solely
    on state codes (the store-scoped matcher handles ZIP-based rules).
    """
    path_to_states: dict[str, set[str]] = {}

    for entry in forxn or []:
        if not isinstance(entry, dict):
            continue
        paths = entry.get("path") or []
        states = entry.get("state") or []
        if isinstance(paths, str):
            paths = [paths]
        if isinstance(states, str):
            states = [states]
        if not isinstance(paths, (list, tuple)):
            continue
        clean_states = [
            str(s).strip().upper()
            for s in (states or [])
            if s is not None and str(s).strip()
        ]
        for raw_path in paths:
            if raw_path is None:
                continue
            path = str(raw_path).strip()
            if not path:
                continue
            path_to_states.setdefault(path, set()).update(clean_states)

    groups = [
        {"path": p, "states": sorted(path_to_states[p])}
        for p in sorted(path_to_states)
    ]

    return {
        "outcome": (
            "DEW_OFFER_RESTRICTIONS_PRESENT" if groups
            else "DEW_OFFER_NO_RESTRICTIONS"
        ),
        "groups": groups,
    }


__all__ = [
    "check_offer_fully_created",
    "analyze_consolidated_store_v2",
    "match_dew_geo_restriction",
    "group_dew_offer_restrictions",
]
