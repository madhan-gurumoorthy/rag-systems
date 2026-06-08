"""Response analyzers for the LIMO Online Eligibility pack.

Callables, one per upstream response shape:

Main eligibility flow:
  - ``analyze_aurum_fc``           — offerNodeAttr.nodes[<node>]
  - ``analyze_dew_fc``             — ftxn.nodeData[*].outboundPaths[*]
  - ``analyze_promise``            — payload.offerPayload[*].nodeData
  - ``analyze_consolidated_fc``    — outboundPaths[] + fulfillmentSpeed
  - ``analyze_shipnodes``          — payload.logisticsOffer
                                     .offerShipNodes[<node>]
  - ``analyze_dew_seller``         — programsDTO.AUTOMATED_SHIPPING_ENABLED
                                     + root.ase
  - ``analyze_dcc``                — payload.distributorCore (active +
                                     status → derived acs_enabled)
  - ``analyze_substitution``       — substitutionRestrictions array → CSV

Sub-SOP extractors (all read offerConsolidated.* unless otherwise noted):
  - ``analyze_preorder_consolidated``     — preOrder + streetDate
  - ``analyze_preorder_shipnodes``        — logisticsOffer.preOrderInfo
  - ``analyze_replenishable_shipnodes``   — logisticsOffer.replenishmentInfo
  - ``analyze_shipsize_consolidated``     — dimensions + shipSizeCode
  - ``analyze_sortable_consolidated``     — sortable flag
  - ``analyze_gifting``                   — giftingEligibility block
  - ``analyze_acs_consolidated``          — isACSEnabled
  - ``analyze_ftc_consolidated``          — fulfillmentTypeClassification

All emit ``outcome``-bearing dicts so the decision matrix can branch.
None of them raise — every missing key short-circuits to a clean
``*_NOT_FOUND`` / ``*_MISSING`` outcome.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional


def _get(obj: Any, *keys: str) -> Any:
    """Deep-get; returns None if any segment is missing."""
    cur = obj
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        elif isinstance(cur, list) and k.isdigit():
            idx = int(k)
            cur = cur[idx] if 0 <= idx < len(cur) else None
        else:
            return None
        if cur is None:
            return None
    return cur


def _stringify_node_keys(nodes: Any) -> dict[str, Any]:
    """Coerce a nodes container into a ``{<node_id>: <node-payload>}``
    dict keyed by the human-facing node id.

    Two AURUM shapes are handled:

    * **List of entries** — each entry carries the human-facing node
      id under ``dst`` (preferred), ``id``, or ``nodeId``.
    * **Dict** — keys are the upstream internal node key (e.g. the
      ``ldid``/internal sequence) and the human-facing node id lives
      inside each entry under ``dst``.  We index entries by ``dst``
      and also retain the original key as a secondary alias so
      lookups by either id succeed.

    Returns ``{}`` if the shape is unrecognised.
    """
    out: dict[str, Any] = {}
    if isinstance(nodes, dict):
        for k, v in nodes.items():
            if isinstance(v, dict):
                dst = v.get("dst") or v.get("id") or v.get("nodeId")
                if dst is not None:
                    out[str(dst)] = v
            # Keep the original (internal) key as a fallback so callers
            # that already hold the internal id still resolve.
            out.setdefault(str(k), v)
        return out
    if isinstance(nodes, list):
        for entry in nodes:
            if not isinstance(entry, dict):
                continue
            nid = entry.get("dst") or entry.get("id") or entry.get("nodeId")
            if nid is not None:
                out[str(nid)] = entry
        return out
    return {}


# ─────────────────────────────────────────────────────────────────────
# 1. AURUM FC analyzer
# ─────────────────────────────────────────────────────────────────────


def analyze_aurum_fc(aurum_response: Any = None,
                     node_id: str = "",
                     **_: Any) -> dict[str, Any]:
    """Project AURUM Final Eligibility for the requested node.

    The per-node payload is read from ``offerDistributorAttr.nodes``
    (a dict keyed by the upstream internal node key, with the
    human-facing node id carried in each entry's ``dst`` field).
    ``offerNodeAttr.nodes`` is probed first and used when populated.
    ``_stringify_node_keys`` indexes both shapes by ``dst`` so callers
    can look up the node by its human-facing id.

    Activeness is derived from per-node ``sts``/``dccSts`` when
    present (ACTIVE + dccSts truthy → active).  When both are absent
    the offer-level ``ols`` field is consulted (LISTED → active);
    failing that, a node with inclusions or exclusions is treated
    as active.

    SOP rules:
      * node not present              → AURUM_NODE_MISSING
      * not active                    → AURUM_NODE_INACTIVE (still
                                        surfaces inclusions/exclusions)
      * active, no inclusions/exclusions → AURUM_NO_PATHS
      * active, inclusions/exclusions present → AURUM_PATHS_PRESENT
    """
    if not isinstance(aurum_response, dict):
        return {"outcome": "AURUM_NOT_FOUND"}

    raw_nodes = _get(aurum_response, "offerNodeAttr", "nodes")
    if raw_nodes in (None, {}, []):
        raw_nodes = _get(aurum_response, "offerDistributorAttr", "nodes")
    nodes = _stringify_node_keys(raw_nodes)
    if not nodes:
        return {"outcome": "AURUM_NOT_FOUND"}

    nid = str(node_id or "").strip()
    node = nodes.get(nid)
    if node is None:
        return {
            "outcome":             "AURUM_NODE_MISSING",
            "available_node_ids":  list(nodes.keys()),
        }

    node_type   = node.get("tp")
    node_status = node.get("sts")
    dcc_status  = node.get("dccSts")
    dst_id      = node.get("dst") or nid
    ols         = aurum_response.get("ols") or node.get("ols")

    inclusions = _flatten_path_block(
        _get(node, "finalEligibilities", "path", "inclusions")
    )
    exclusions = _flatten_path_block(
        _get(node, "finalEligibilities", "path", "exclusions")
    )

    # Active-ness: legacy fixtures use sts + dccSts; current AURUM
    # exposes ols on the response (LISTED).  When neither legacy
    # field is present, fall back to ols == LISTED, and finally to
    # "active if path data exists" so a present node with paths is
    # never flagged inactive.
    if node_status is not None or dcc_status is not None:
        is_active = (
            isinstance(node_status, str)
            and node_status.upper() == "ACTIVE"
        )
        is_dcc_true = bool(dcc_status) is True or (
            isinstance(dcc_status, str) and dcc_status.lower() == "true"
        )
        active = is_active and is_dcc_true
    elif isinstance(ols, str):
        active = ols.upper() == "LISTED"
    else:
        active = bool(inclusions or exclusions)

    if not active:
        outcome = "AURUM_NODE_INACTIVE"
    elif not inclusions and not exclusions:
        outcome = "AURUM_NO_PATHS"
    else:
        outcome = "AURUM_PATHS_PRESENT"

    return {
        "outcome":           outcome,
        "aurum_node_id":     str(dst_id),
        "aurum_node_type":   node_type,
        "aurum_node_status": node_status,
        "aurum_dcc_status":  dcc_status,
        "aurum_ols":         ols,
        "aurum_inclusions":  inclusions,
        "aurum_exclusions":  exclusions,
    }


def _flatten_path_block(block: Any) -> list[dict[str, Any]]:
    """``inclusions`` / ``exclusions`` may be a dict
    ``{path → {computedReason, ruleId}}`` or a list of
    ``{"path": ..., "computedReason": ...}`` entries.  ``computedReason``
    may itself be a list — it is rendered as a CSV so closure templates
    can splat it without further coercion.
    """
    def _csv_reason(val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, list):
            return ", ".join(str(v) for v in val if v not in (None, ""))
        return str(val)

    out: list[dict[str, Any]] = []
    if isinstance(block, dict):
        for path, body in block.items():
            reason = ""
            rule_ids: list[str] = []
            if isinstance(body, dict):
                reason = _csv_reason(body.get("computedReason"))
                raw_rules = body.get("ruleId")
                if isinstance(raw_rules, list):
                    rule_ids = [str(r) for r in raw_rules]
            out.append({
                "path":            str(path),
                "computed_reason": reason,
                "rule_ids":        rule_ids,
            })
    elif isinstance(block, list):
        for entry in block:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path") or entry.get("name")
            reason = _csv_reason(
                entry.get("computedReason") or entry.get("reason")
            )
            if path:
                out.append({
                    "path":            str(path),
                    "computed_reason": reason,
                    "rule_ids":        [],
                })
    return out


# ─────────────────────────────────────────────────────────────────────
# 2. DEW FC analyzer
# ─────────────────────────────────────────────────────────────────────


def analyze_dew_fc(dew_response: Any = None,
                   node_id: str = "",
                   **_: Any) -> dict[str, Any]:
    """Walk ftxn.nodeData (may be a dict-of-arrays or a flat array) and
    return one row per outboundPath that matches the requested node id.

    The shape from prod is:
        ftxn.nodeData.DC[]
        ftxn.nodeData.DSV[]
        ftxn.nodeData.SORT_CENTER[]
    each entry has ``.id`` (offerid) and ``.outboundPaths[]``.
    """
    if not isinstance(dew_response, dict):
        return {"outcome": "DEW_NOT_FOUND"}

    node_data = _get(dew_response, "ftxn", "nodeData")
    if not node_data:
        return {"outcome": "DEW_NO_PATHS", "dew_paths": []}

    requested = str(node_id or "").strip()

    # Normalise to a flat list of {node_type, entry} pairs.
    entries: list[tuple[str, dict]] = []
    if isinstance(node_data, dict):
        for nt, lst in node_data.items():
            if isinstance(lst, list):
                entries.extend((str(nt), e) for e in lst if isinstance(e, dict))
    elif isinstance(node_data, list):
        entries = [("", e) for e in node_data if isinstance(e, dict)]

    rows: list[dict[str, Any]] = []
    for node_type, entry in entries:
        entry_id = str(entry.get("id") or "")
        if requested and entry_id and entry_id != requested:
            continue
        for path in entry.get("outboundPaths", []) or []:
            if not isinstance(path, dict):
                continue
            fm = path.get("fulfillmentMethods") or []
            tp = path.get("types") or []
            rows.append({
                "node_type":             node_type,
                "node_id":               entry_id,
                "path":                  str(path.get("fulfillmentPath") or ""),
                "fulfillment_methods":   list(fm) if isinstance(fm, list) else [fm],
                "fulfillment_methods_csv": _csv(fm),
                "types":                 list(tp) if isinstance(tp, list) else [tp],
                "types_csv":             _csv(tp),
            })

    if not rows:
        return {"outcome": "DEW_NO_PATHS", "dew_paths": []}
    return {"outcome": "DEW_PATHS_PRESENT", "dew_paths": rows}


# ─────────────────────────────────────────────────────────────────────
# 3. Promise / Wakanda analyzer
# ─────────────────────────────────────────────────────────────────────


def analyze_promise(promise_response: Any = None,
                    node_id: str = "",
                    **_: Any) -> dict[str, Any]:
    """Walk ``payload.offerPayload[].nodeData.<TYPE>[]`` and surface the
    Wakanda Promise entries for the requested node id.

    The Promise response is shaped:

        payload.offerPayload[].nodeData.{DC,DSV,MARKETPLACE,...}[]
            { id: "<node_id>", outboundPaths: [{fulfillmentPath, types,
              fulfillmentPromise, ...}] }

    One row per matching ``outboundPaths[]`` entry is emitted with the
    projected fields ``node_type``, ``node_id``, ``path``, ``types_csv``,
    and ``fulfillment_promise``.  When ``node_id`` is empty every entry
    is emitted so substrate-level callers still see the full surface.
    Missing or unrecognised payloads yield ``PROMISE_MISSING``.  This
    analyzer never blocks the pipeline (Case 4 is non-blocking per SOP).
    """
    if not isinstance(promise_response, dict):
        return {"outcome": "PROMISE_MISSING", "promise_present": False,
                "promise_paths": []}

    requested = str(node_id or "").strip()
    offer_payload = _get(promise_response, "payload", "offerPayload") or []
    paths: list[dict[str, Any]] = []

    if isinstance(offer_payload, list):
        for offer in offer_payload:
            if not isinstance(offer, dict):
                continue
            node_data = offer.get("nodeData") or {}
            if not isinstance(node_data, dict):
                continue
            for nt, entries in node_data.items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    entry_id = str(entry.get("id") or "")
                    if requested and entry_id != requested:
                        continue
                    outbound = entry.get("outboundPaths") or []
                    if not isinstance(outbound, list) or not outbound:
                        # Surface a single row even when outboundPaths is
                        # empty so the caller can see the node was present.
                        paths.append({
                            "node_type":           str(nt),
                            "node_id":             entry_id,
                            "path":                "",
                            "types":               [],
                            "types_csv":           "",
                            "fulfillment_promise": None,
                        })
                        continue
                    for op in outbound:
                        if not isinstance(op, dict):
                            continue
                        tp = op.get("types") or []
                        paths.append({
                            "node_type":           str(nt),
                            "node_id":             entry_id,
                            "path":                str(op.get("fulfillmentPath") or ""),
                            "types":               list(tp) if isinstance(tp, list) else [tp],
                            "types_csv":           _csv(tp),
                            "fulfillment_promise": op.get("fulfillmentPromise"),
                        })

    if not paths:
        return {"outcome": "PROMISE_MISSING", "promise_present": False,
                "promise_paths": []}
    return {"outcome": "PROMISE_PRESENT", "promise_present": True,
            "promise_paths": paths}


# ─────────────────────────────────────────────────────────────────────
# 4. Eligibility Consolidated (FC) analyzer
# ─────────────────────────────────────────────────────────────────────


def analyze_consolidated_fc(consolidated_response: Any = None,
                            node_id: str = "",
                            **_: Any) -> dict[str, Any]:
    """Project Eligibility Consolidated path eligibility for the offer.

    Path eligibility is read from
    ``payload.consolidatedResponse[].offerConsolidated.outboundPaths[]``;
    each entry already carries the canonical projection
    (``fulfillmentPath``, ``fulfillmentMethods``, ``types``,
    ``fulfillmentPromise``) so no per-node filtering is applied — the
    Consolidated surface answers "what paths are eligible for this
    offer" not "for this node".

    ``fulfillment_speed`` is read from
    ``offerConsolidated.fulfillmentSpeed.speed`` (a list) and rendered
    as a CSV so the closure / chat templates can splat it directly.

    ``consolidated_available_node_ids[]`` is sourced from
    ``offerConsolidated.nodeData.FC[].nodes[]`` (insertion-ordered,
    deduped) and surfaces the set of nodes the Consolidated API IS
    aware of — useful diagnostic context when the requested node is
    not present.

    Outcomes:
      * ``CONSOLIDATED_FC_NOT_FOUND``    — response is not a dict.
      * ``CONSOLIDATED_FC_NO_PATHS``     — no outboundPaths entries.
      * ``CONSOLIDATED_FC_PATHS_PRESENT`` — at least one outboundPaths
        entry was found.
    """
    if not isinstance(consolidated_response, dict):
        return {"outcome": "CONSOLIDATED_FC_NOT_FOUND",
                "consolidated_paths": [],
                "consolidated_available_node_ids": []}

    blocks = _get(consolidated_response, "payload",
                  "consolidatedResponse") or []
    if not isinstance(blocks, list) or not blocks:
        return {"outcome": "CONSOLIDATED_FC_NO_PATHS",
                "consolidated_paths": [],
                "consolidated_available_node_ids": [],
                "fulfillment_speed": None}

    rows: list[dict[str, Any]] = []
    speed_csv: Optional[str] = None
    available: list[str] = []
    seen_node_ids: set[str] = set()

    for blk in blocks:
        if not isinstance(blk, dict):
            continue
        consol = blk.get("offerConsolidated") or {}
        if not isinstance(consol, dict):
            continue

        # Speed lives at offerConsolidated.fulfillmentSpeed.speed (a
        # list of path strings).  CSV-render so callers can splat it.
        if speed_csv is None:
            raw_speed = _get(consol, "fulfillmentSpeed", "speed")
            if isinstance(raw_speed, list):
                speed_csv = _csv(raw_speed) or None
            elif isinstance(raw_speed, str) and raw_speed:
                speed_csv = raw_speed

        # Diagnostic: collect every node id Consolidated saw across
        # nodeData.FC[] so the caller can see what IS eligible when
        # their node isn't.
        fc_paths = _get(consol, "nodeData", "FC") or []
        if isinstance(fc_paths, list):
            for path in fc_paths:
                if not isinstance(path, dict):
                    continue
                for n in (path.get("nodes") or []):
                    s = str(n)
                    if s and s not in seen_node_ids:
                        seen_node_ids.add(s)
                        available.append(s)

        # Path eligibility comes from outboundPaths[].
        outbound = consol.get("outboundPaths") or []
        if not isinstance(outbound, list):
            continue
        for op in outbound:
            if not isinstance(op, dict):
                continue
            fm = op.get("fulfillmentMethods") or []
            tp = op.get("types") or []
            rows.append({
                "path":                  str(op.get("fulfillmentPath") or ""),
                "fulfillment_methods":   list(fm) if isinstance(fm, list) else [fm],
                "fulfillment_methods_csv": _csv(fm),
                "types":                 list(tp) if isinstance(tp, list) else [tp],
                "types_csv":             _csv(tp),
                "fulfillment_promise":   op.get("fulfillmentPromise"),
            })

    if not rows:
        return {"outcome": "CONSOLIDATED_FC_NO_PATHS",
                "consolidated_paths": [],
                "consolidated_available_node_ids": available,
                "fulfillment_speed": speed_csv}

    return {
        "outcome":                          "CONSOLIDATED_FC_PATHS_PRESENT",
        "consolidated_paths":               rows,
        "consolidated_available_node_ids":  available,
        "fulfillment_speed":                speed_csv,
    }


# ─────────────────────────────────────────────────────────────────────
# 5. Shipnodes analyzer
# ─────────────────────────────────────────────────────────────────────


def analyze_shipnodes(shipnodes_response: Any = None,
                      node_id: str = "",
                      **_: Any) -> dict[str, Any]:
    """Filter ``payload.logisticsOffer.offerShipNodes[]`` to the entry
    whose ``legacyDistributorId`` (or ``pangaeaDistributorId``) matches
    the requested node, and surface partnership / status / item fields.

    Emits:
      * SHIPNODE_NOT_FOUND — response not a dict / shape missing /
        node not present in offerShipNodes[]
      * SHIPNODE_PRESENT   — entry found; iqs_partnership_type_code,
        shipnode_status, shipnode_item_id, legacy_distributor_id,
        program_eligibilities are populated
    """
    if not isinstance(shipnodes_response, dict):
        return {"outcome": "SHIPNODE_NOT_FOUND"}

    logistics = _get(shipnodes_response, "payload", "logisticsOffer")
    if not isinstance(logistics, dict):
        return {"outcome": "SHIPNODE_NOT_FOUND"}

    entries = logistics.get("offerShipNodes") or []
    if not isinstance(entries, list) or not entries:
        return {"outcome": "SHIPNODE_NOT_FOUND"}

    nid = str(node_id or "").strip()
    match: Optional[dict[str, Any]] = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not nid:
            match = entry
            break
        legacy = str(entry.get("legacyDistributorId") or "")
        pangaea = str(entry.get("pangaeaDistributorId") or "")
        if nid in (legacy, pangaea):
            match = entry
            break

    if match is None:
        return {
            "outcome":            "SHIPNODE_NOT_FOUND",
            "available_node_ids": [
                str(e.get("legacyDistributorId") or "")
                for e in entries if isinstance(e, dict)
            ],
        }

    programs = match.get("programEligibilities") or []
    program_map: dict[str, Any] = {}
    if isinstance(programs, list):
        for prog in programs:
            if isinstance(prog, dict):
                name = prog.get("eligibilityName")
                if name:
                    program_map[str(name)] = prog.get("eligibilityValue")

    return {
        "outcome":                   "SHIPNODE_PRESENT",
        "iqs_partnership_type_code": match.get("offerShipNodeType"),
        "shipnode_status":           match.get("offerShipNodeStatus"),
        "shipnode_item_id":          match.get("shipNodeItemId"),
        "legacy_distributor_id":     match.get("legacyDistributorId"),
        "pangaea_distributor_id":    match.get("pangaeaDistributorId"),
        "program_eligibilities":     program_map,
    }


# ─────────────────────────────────────────────────────────────────────
# 6. DEW Seller analyzer
# ─────────────────────────────────────────────────────────────────────


def analyze_dew_seller(dew_seller_response: Any = None,
                       **_: Any) -> dict[str, Any]:
    """Surface ASE program status from the DEW Seller payload.

    The endpoint returns the seller record with
    ``programsDTO.AUTOMATED_SHIPPING_ENABLED.status`` and a root-level
    ``ase`` boolean.  Older payloads kept the program info under
    ``payload[0].aseStatus`` / ``payload[0].aseSeller`` — those are
    still accepted as a fallback.

    Emits DEW_SELLER_MISSING when no ASE info is present, otherwise
    DEW_SELLER_PRESENT with ``ase_status`` and ``ase_seller`` populated.
    """
    if not isinstance(dew_seller_response, dict):
        return {"outcome": "DEW_SELLER_MISSING"}

    ase_status = _get(
        dew_seller_response, "programsDTO", "AUTOMATED_SHIPPING_ENABLED", "status"
    )
    ase_seller: Any = dew_seller_response.get("ase")

    if ase_status is None and ase_seller is None:
        legacy = _get(dew_seller_response, "payload", "0", "aseStatus")
        if legacy is not None:
            ase_status = legacy
            ase_seller = _get(dew_seller_response, "payload", "0", "aseSeller")

    if ase_status is None and ase_seller is None:
        return {"outcome": "DEW_SELLER_MISSING"}

    return {
        "outcome":    "DEW_SELLER_PRESENT",
        "ase_status": ase_status,
        "ase_seller": ase_seller,
    }


# ─────────────────────────────────────────────────────────────────────
# 7. DCC (Distributor Center Check) analyzer
# ─────────────────────────────────────────────────────────────────────


def analyze_dcc(dcc_response: Any = None,
                **_: Any) -> dict[str, Any]:
    """Derive ``acs_enabled`` from the DCC distributor record.

    acs_enabled is True when ``payload.distributorCore.active`` is
    True AND ``payload.distributorCore.status`` is ``"ENABLED"``.
    Also surfaces distributorType + distributorSupportedServices for
    diagnostics.  Emits DCC_PRESENT or DCC_MISSING.
    """
    if not isinstance(dcc_response, dict):
        return {"outcome": "DCC_MISSING"}

    core = _get(dcc_response, "payload", "distributorCore")
    if not isinstance(core, dict):
        return {"outcome": "DCC_MISSING"}

    active = bool(core.get("active"))
    status = core.get("status")
    services = core.get("distributorSupportedServices") or []
    if not isinstance(services, list):
        services = []

    acs_enabled = active and (
        isinstance(status, str) and status.upper() == "ENABLED"
    )

    return {
        "outcome":                          "DCC_PRESENT",
        "acs_enabled":                      acs_enabled,
        "dcc_active":                       active,
        "dcc_status":                       status,
        "dcc_distributor_type":             core.get("distributorType"),
        "dcc_distributor_id":               core.get("distributorId"),
        "dcc_supported_services":           [str(s) for s in services],
        "dcc_supported_services_csv":       _csv(services),
    }


# ─────────────────────────────────────────────────────────────────────
# 8. Substitution restrictions → CSV
# ─────────────────────────────────────────────────────────────────────


def analyze_substitution(consolidated_response: Any = None,
                         **_: Any) -> dict[str, Any]:
    """Flatten substitutionRestrictions to a CSV string.  Returns
    ``No restriction found`` when the array is null/empty so the
    closure renders cleanly without further logic."""
    if not isinstance(consolidated_response, dict):
        return {"outcome": "SUBSTITUTION_MISSING"}

    blocks = _get(consolidated_response, "payload",
                  "consolidatedResponse") or []
    if not isinstance(blocks, list) or not blocks:
        return {"outcome": "SUBSTITUTION_MISSING"}

    first = blocks[0] if isinstance(blocks[0], dict) else {}
    consol = first.get("offerConsolidated") or {}
    allowed = consol.get("substitutionAllowed")
    raw = consol.get("substitutionRestrictions") or []
    restrictions = [str(r) for r in raw] if isinstance(raw, list) else []
    csv = _csv(restrictions) if restrictions else "No restriction found"
    return {
        "outcome":                       "SUBSTITUTION_PRESENT",
        "substitution_allowed":          allowed,
        "substitution_restrictions":     restrictions,
        "substitution_restrictions_csv": csv,
    }


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _csv(items: Optional[Iterable[Any]]) -> str:
    if not items:
        return ""
    if isinstance(items, str):
        return items
    return ", ".join(str(i) for i in items if i is not None and i != "")


# ─────────────────────────────────────────────────────────────────────
# 9. Sub-SOP analyzers — Consolidated extras
# ─────────────────────────────────────────────────────────────────────


def _first_offer_consolidated(consolidated_response: Any) -> dict[str, Any]:
    """Return the first ``offerConsolidated`` block or an empty dict.

    Used by every Consolidated-extras analyzer below — the
    Consolidated API always returns a list under
    ``payload.consolidatedResponse[]`` but every sub-SOP cares only
    about the first (and typically only) offer in that list.
    """
    if not isinstance(consolidated_response, dict):
        return {}
    blocks = _get(consolidated_response, "payload",
                  "consolidatedResponse") or []
    if not isinstance(blocks, list) or not blocks:
        return {}
    first = blocks[0]
    if not isinstance(first, dict):
        return {}
    consol = first.get("offerConsolidated") or {}
    return consol if isinstance(consol, dict) else {}


def analyze_preorder_consolidated(consolidated_response: Any = None,
                                  **_: Any) -> dict[str, Any]:
    """Surface ``preOrder`` + ``streetDate`` from offerConsolidated.

    Reads ``offerConsolidated.preOrder`` (bool) and
    ``offerConsolidated.streetDate`` / ``preOrderStreetDate`` (ISO
    string).  The verdict (PAST vs FUTURE) is computed by
    ``sub_sop_gates.preorder_verdict`` so this analyzer stays
    side-effect-free.

    Emits PREORDER_CONSOLIDATED_PRESENT when either field is
    populated, PREORDER_CONSOLIDATED_MISSING otherwise.
    """
    consol = _first_offer_consolidated(consolidated_response)
    if not consol:
        return {"outcome": "PREORDER_CONSOLIDATED_MISSING",
                "preorder_flag": None,
                "preorder_consolidated_street_date": None}

    flag = consol.get("preOrder")
    if flag is None:
        flag = consol.get("isPreOrder")

    street_date = (
        consol.get("streetDate")
        or consol.get("preOrderStreetDate")
        or _get(consol, "preOrderInfo", "streetDate")
    )

    if flag is None and street_date is None:
        return {"outcome": "PREORDER_CONSOLIDATED_MISSING",
                "preorder_flag": None,
                "preorder_consolidated_street_date": None}

    return {
        "outcome":                            "PREORDER_CONSOLIDATED_PRESENT",
        "preorder_flag":                      bool(flag) if flag is not None else None,
        "preorder_consolidated_street_date":  str(street_date) if street_date else None,
    }


def analyze_preorder_shipnodes(shipnodes_response: Any = None,
                               **_: Any) -> dict[str, Any]:
    """Surface ``preOrderInfo`` from the Shipnodes logisticsOffer block.

    Reads ``payload.logisticsOffer.preOrderInfo.{streetDate,preOrder}``.
    The streetDate is the authoritative SOP signal — the verdict
    (PAST/FUTURE) is computed downstream by
    ``sub_sop_gates.preorder_verdict``.

    Emits PREORDER_SHIPNODES_PRESENT when either field is populated,
    PREORDER_SHIPNODES_MISSING otherwise.
    """
    if not isinstance(shipnodes_response, dict):
        return {"outcome": "PREORDER_SHIPNODES_MISSING",
                "preorder_flag": None,
                "preorder_street_date": None}

    info = _get(shipnodes_response, "payload", "logisticsOffer",
                "preOrderInfo")
    if not isinstance(info, dict):
        return {"outcome": "PREORDER_SHIPNODES_MISSING",
                "preorder_flag": None,
                "preorder_street_date": None}

    flag = info.get("preOrder")
    if flag is None:
        flag = info.get("isPreOrder")
    street_date = info.get("streetDate") or info.get("preOrderStreetDate")

    if flag is None and not street_date:
        return {"outcome": "PREORDER_SHIPNODES_MISSING",
                "preorder_flag": None,
                "preorder_street_date": None}

    return {
        "outcome":              "PREORDER_SHIPNODES_PRESENT",
        "preorder_flag":        bool(flag) if flag is not None else None,
        "preorder_street_date": str(street_date) if street_date else None,
    }


def analyze_replenishable_shipnodes(shipnodes_response: Any = None,
                                    **_: Any) -> dict[str, Any]:
    """Surface the Shipnodes replenishment flag.

    Reads ``payload.logisticsOffer.replenishmentInfo.isReplenishable``
    (string ``"YES"`` / ``"NO"``) and coerces it to a bool.  Also
    accepts the alternate boolean keys ``replenishmentFlag`` /
    ``replenishable`` so the analyzer remains robust to upstream
    schema variants.  Emits REPLENISHABLE_SHIPNODES_PRESENT when any
    of those keys is populated, REPLENISHABLE_SHIPNODES_MISSING
    otherwise.
    """
    if not isinstance(shipnodes_response, dict):
        return {"outcome": "REPLENISHABLE_SHIPNODES_MISSING",
                "replenishment_flag": None}

    info = _get(shipnodes_response, "payload", "logisticsOffer",
                "replenishmentInfo")
    if not isinstance(info, dict):
        return {"outcome": "REPLENISHABLE_SHIPNODES_MISSING",
                "replenishment_flag": None}

    raw = info.get("isReplenishable")
    if raw is None:
        raw = info.get("replenishmentFlag")
    if raw is None:
        raw = info.get("replenishable")
    if raw is None:
        return {"outcome": "REPLENISHABLE_SHIPNODES_MISSING",
                "replenishment_flag": None}

    if isinstance(raw, str):
        norm = raw.strip().lower()
        if norm in ("yes", "y", "true", "t", "1"):
            flag = True
        elif norm in ("no", "n", "false", "f", "0"):
            flag = False
        else:
            return {"outcome": "REPLENISHABLE_SHIPNODES_MISSING",
                    "replenishment_flag": None}
    else:
        flag = bool(raw)

    return {
        "outcome":             "REPLENISHABLE_SHIPNODES_PRESENT",
        "replenishment_flag":  flag,
    }


def analyze_shipsize_consolidated(consolidated_response: Any = None,
                                  **_: Any) -> dict[str, Any]:
    """Surface raw dimensions + the Consolidated ``shipSizeCode``.

    Reads ``offerConsolidated.productPackageDimensions.{height,length,
    width,weight}`` and the offer's ``offerShipmentSpecification.shipSizeCode``
    (with a fallback to top-level ``shipSizeCode``).  The girth /
    derived bracket computation lives in ``shipsize.derive_shipsize``
    so this analyzer only exposes the inputs.

    Emits SHIPSIZE_CONSOLIDATED_PRESENT when at least one dimension
    or the shipsize code is populated; SHIPSIZE_CONSOLIDATED_MISSING
    otherwise.
    """
    consol = _first_offer_consolidated(consolidated_response)
    if not consol:
        return {"outcome": "SHIPSIZE_CONSOLIDATED_MISSING",
                "unit_height": None, "unit_length": None,
                "unit_width": None, "unit_weight": None,
                "shipsize_consolidated": None}

    dims = consol.get("productPackageDimensions") or {}
    if not isinstance(dims, dict):
        dims = {}

    shipsize_code = (
        _get(consol, "offerShipmentSpecification", "shipSizeCode")
        or consol.get("shipSizeCode")
    )

    h = _as_float(dims.get("height"))
    l = _as_float(dims.get("length"))
    w = _as_float(dims.get("width"))
    wt = _as_float(dims.get("weight"))

    populated = any(v is not None for v in (h, l, w, wt)) or bool(shipsize_code)
    if not populated:
        return {"outcome": "SHIPSIZE_CONSOLIDATED_MISSING",
                "unit_height": None, "unit_length": None,
                "unit_width": None, "unit_weight": None,
                "shipsize_consolidated": None}

    return {
        "outcome":               "SHIPSIZE_CONSOLIDATED_PRESENT",
        "unit_height":           h,
        "unit_length":           l,
        "unit_width":            w,
        "unit_weight":           wt,
        "shipsize_consolidated": str(shipsize_code) if shipsize_code else None,
    }


def analyze_sortable_consolidated(consolidated_response: Any = None,
                                  **_: Any) -> dict[str, Any]:
    """Surface the Consolidated sortable flag.

    Reads ``offerConsolidated.offerShipmentSpecification.sortable``
    first, falling back to top-level ``offerConsolidated.sortable``
    and ``sortableFlag``.

    Emits SORTABLE_CONSOLIDATED_PRESENT (with the bool) or
    SORTABLE_CONSOLIDATED_MISSING when neither key is set.
    """
    consol = _first_offer_consolidated(consolidated_response)
    if not consol:
        return {"outcome": "SORTABLE_CONSOLIDATED_MISSING",
                "sortable_consolidated": None}

    flag = (
        _get(consol, "offerShipmentSpecification", "sortable")
        or consol.get("sortable")
        or consol.get("sortableFlag")
    )
    if flag is None:
        return {"outcome": "SORTABLE_CONSOLIDATED_MISSING",
                "sortable_consolidated": None}

    return {
        "outcome":               "SORTABLE_CONSOLIDATED_PRESENT",
        "sortable_consolidated": bool(flag),
    }


def analyze_gifting(consolidated_response: Any = None,
                    **_: Any) -> dict[str, Any]:
    """Project ``offerConsolidated.giftingEligibility`` into state slots.

    Reads ``giftingEligibility.{giftWrap,giftMessage,giftReceipt,
    overbox}`` (any of which may be at the root of giftingEligibility
    or absent) and projects them onto the five state slots:
    ``gifting_eligibility`` (true when any sub-flag is true),
    ``allow_gift_message``, ``allow_gift_receipt``, ``allow_gift_wrap``,
    ``gift_overbox_eligible``.

    Emits GIFTING_PRESENT when the block exists; GIFTING_MISSING
    otherwise.
    """
    consol = _first_offer_consolidated(consolidated_response)
    if not consol:
        return {"outcome": "GIFTING_MISSING",
                "gifting_eligibility": None,
                "allow_gift_message": None,
                "allow_gift_receipt": None,
                "allow_gift_wrap": None,
                "gift_overbox_eligible": None}

    block = consol.get("giftingEligibility")
    if not isinstance(block, dict):
        return {"outcome": "GIFTING_MISSING",
                "gifting_eligibility": None,
                "allow_gift_message": None,
                "allow_gift_receipt": None,
                "allow_gift_wrap": None,
                "gift_overbox_eligible": None}

    wrap    = block.get("giftWrap")
    msg     = block.get("giftMessage")
    receipt = block.get("giftReceipt")
    overbox = block.get("overbox") or block.get("overBox")

    flags = [wrap, msg, receipt, overbox]
    any_true = any(bool(f) for f in flags if f is not None)

    return {
        "outcome":                "GIFTING_PRESENT",
        "gifting_eligibility":    any_true,
        "allow_gift_message":     bool(msg)     if msg     is not None else None,
        "allow_gift_receipt":     bool(receipt) if receipt is not None else None,
        "allow_gift_wrap":        bool(wrap)    if wrap    is not None else None,
        "gift_overbox_eligible":  bool(overbox) if overbox is not None else None,
    }


def analyze_acs_consolidated(consolidated_response: Any = None,
                             **_: Any) -> dict[str, Any]:
    """Surface ``offerConsolidated.isACSEnabled`` as a bool.

    Falls back to top-level ``acsEnabled`` for older payloads.
    Emits ACS_CONSOLIDATED_PRESENT (with the bool) or
    ACS_CONSOLIDATED_MISSING when neither key is set.
    """
    consol = _first_offer_consolidated(consolidated_response)
    if not consol:
        return {"outcome": "ACS_CONSOLIDATED_MISSING",
                "acs_enabled": None}

    flag = consol.get("isACSEnabled")
    if flag is None:
        flag = consol.get("acsEnabled")
    if flag is None:
        return {"outcome": "ACS_CONSOLIDATED_MISSING",
                "acs_enabled": None}

    return {
        "outcome":     "ACS_CONSOLIDATED_PRESENT",
        "acs_enabled": bool(flag),
    }


def analyze_ftc_consolidated(consolidated_response: Any = None,
                             **_: Any) -> dict[str, Any]:
    """Surface ``offerConsolidated.fulfillmentTypeClassification`` as CSV.

    The classification may arrive as a string or a list; either is
    CSV-rendered.  Emits FTC_CONSOLIDATED_PRESENT when populated,
    FTC_CONSOLIDATED_MISSING otherwise.
    """
    consol = _first_offer_consolidated(consolidated_response)
    if not consol:
        return {"outcome": "FTC_CONSOLIDATED_MISSING",
                "ftc_consolidated": None}

    raw = consol.get("fulfillmentTypeClassification")
    if raw is None:
        raw = consol.get("ftc")

    if raw in (None, "", []):
        return {"outcome": "FTC_CONSOLIDATED_MISSING",
                "ftc_consolidated": None}

    if isinstance(raw, list):
        csv = _csv(raw)
    else:
        csv = str(raw)

    if not csv:
        return {"outcome": "FTC_CONSOLIDATED_MISSING",
                "ftc_consolidated": None}

    return {
        "outcome":           "FTC_CONSOLIDATED_PRESENT",
        "ftc_consolidated":  csv,
    }


def _as_float(val: Any) -> Optional[float]:
    """Best-effort float coercion; returns None for null/non-numeric."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


__all__ = [
    "analyze_aurum_fc",
    "analyze_dew_fc",
    "analyze_promise",
    "analyze_consolidated_fc",
    "analyze_shipnodes",
    "analyze_dew_seller",
    "analyze_dcc",
    "analyze_substitution",
    "analyze_preorder_consolidated",
    "analyze_preorder_shipnodes",
    "analyze_replenishable_shipnodes",
    "analyze_shipsize_consolidated",
    "analyze_sortable_consolidated",
    "analyze_gifting",
    "analyze_acs_consolidated",
    "analyze_ftc_consolidated",
]
