"""Deterministic sub-SOP tool plan for the LIMO Online Eligibility pack.

One callable, ``plan_sub_sop``, exposed as a ``python_function`` tool.
Given a resolved ``sub_intent`` code (the value emitted by
``DIAG-INTENT-EXTRACT-01`` on the ``SUB_INTENT_RESOLVED`` branch), the
router returns the fixed tool sequence the RetrievalAgent must call to
answer the request, the set of tools that are forbidden in standalone
mode, and the name of the sub-SOP output block the prompt must render.

The plan is consulted by ``prompts/retrieval.j2`` immediately after
Case-0b emits ``SUB_INTENT_RESOLVED``.  Treat the returned
``tool_sequence`` as the complete, ordered, exclusive list of
diagnostic tools to call for the request — any tool not in the
sequence (with the single exception of ``DIAG-OFFER-ID-VALIDATE-01``,
which Case-0a always runs first) must not be called.

The router does not touch any upstream service; it is a pure
dispatch table over a closed set of sub-SOP codes.  Unknown codes
fall through to ``SUB_SOP_PLAN_UNKNOWN``.
"""
from __future__ import annotations

from typing import Any

# Tools that are NEVER legal in standalone sub-SOP mode.  The standalone
# flow renders only the ODIN block plus the sub-SOP-specific block, so
# AURUM / DEW / Promise / Consolidated-gated fetchers and analyzers are
# all off-limits regardless of sub_intent.
_FORBIDDEN_TOOLS: tuple[str, ...] = (
    "DIAG-AURUM-FC-01",
    "DIAG-AURUM-FC-ANALYZED-01",
    "DIAG-ANALYZE-AURUM-FC",
    "DIAG-DEW-FC-GATED-01",
    "DIAG-PROMISE-GATED-01",
    "DIAG-CONSOLIDATED-FC-GATED-01",
)

# Per-sub_intent plans.  Each entry maps to (ordered tool sequence,
# output block heading).  ``DIAG-ODIN-01`` is the first call for every
# plan so the standalone flow always has sid / styp / wfsElig /
# oa.ofrCrt on state before the sub-SOP extract → gate chain runs.
_PLANS: dict[str, tuple[tuple[str, ...], str]] = {
    "cost_rt": (
        (
            "DIAG-ODIN-01",
            "DIAG-IQS-SI-01",
            "DIAG-SHIPNODES-01",
            "DIAG-ANALYZE-SHIPNODES",
            "DIAG-COST-RT-GATE-01",
        ),
        "COST RT eligibility",
    ),
    "pre_order": (
        (
            "DIAG-ODIN-01",
            "DIAG-SHIPNODES-01",
            "DIAG-ANALYZE-PREORDER-SHIPNODES",
            "DIAG-CONSOLIDATED-FC-01",
            "DIAG-ANALYZE-PREORDER-CONSOLIDATED",
            "DIAG-PREORDER-VERDICT-01",
        ),
        "Pre-Order eligibility",
    ),
    "replenishable": (
        (
            "DIAG-ODIN-01",
            "DIAG-SHIPNODES-01",
            "DIAG-ANALYZE-REPLENISHABLE-SHIPNODES",
            "DIAG-REPLENISHABLE-VERDICT-01",
        ),
        "Replenishable",
    ),
    "shipsize": (
        (
            "DIAG-ODIN-01",
            "DIAG-CONSOLIDATED-FC-01",
            "DIAG-ANALYZE-SHIPSIZE-CONSOLIDATED",
            "DIAG-DERIVE-SHIPSIZE",
        ),
        "Shipsize / Ship class",
    ),
    "ship_class": (
        (
            "DIAG-ODIN-01",
            "DIAG-CONSOLIDATED-FC-01",
            "DIAG-ANALYZE-SHIPSIZE-CONSOLIDATED",
            "DIAG-DERIVE-SHIPSIZE",
        ),
        "Shipsize / Ship class",
    ),
    "sortable": (
        (
            "DIAG-ODIN-01",
            "DIAG-CONSOLIDATED-FC-01",
            "DIAG-ANALYZE-SORTABLE-CONSOLIDATED",
        ),
        "Sortable",
    ),
    "gifting": (
        (
            "DIAG-ODIN-01",
            "DIAG-CONSOLIDATED-FC-01",
            "DIAG-ANALYZE-GIFTING",
        ),
        "Gifting",
    ),
    "substitution": (
        (
            "DIAG-ODIN-01",
            "DIAG-ANALYZE-SUBSTITUTION",
        ),
        "Substitution restrictions",
    ),
    "acs": (
        (
            "DIAG-ODIN-01",
            "DIAG-ACS-INPUTS-BUNDLE-01",
            "DIAG-ACS-VERDICT-01",
        ),
        "ACS",
    ),
    "ftc": (
        (
            "DIAG-ODIN-01",
            "DIAG-CONSOLIDATED-FC-01",
            "DIAG-ANALYZE-FTC-CONSOLIDATED",
            "DIAG-FTC-MATRIX-01",
        ),
        "FTC",
    ),
    "enforcement": (
        (
            "DIAG-ODIN-01",
            "DIAG-ODIN-OFR-CRT-01",
            "DIAG-SELLER-ENFORCEMENT-FETCH-01",
            "DIAG-SELLER-ENFORCEMENT-CLASSIFY-01",
        ),
        "Seller Enforcement",
    ),
    "restriction": (
        (
            "DIAG-ODIN-01",
            "DIAG-ODIN-OFR-CRT-01",
            "DIAG-DEW-RESTRICTION-FETCH-01",
            "DIAG-DEW-RESTRICTION-GROUP-01",
        ),
        "DEW Restriction",
    ),
}


# Per-sub_intent slot → source-tool map.  Each entry is a list of
# ``(rendered_slot, source_tool_id)`` pairs that the LLM must consult
# before rendering the sub-SOP block.  A slot rendered as ``null``
# means the listed source tool was skipped — populate it by calling
# that tool, then re-render.  Kept tight on purpose: only the slots
# whose value depends on a non-ODIN upstream are listed.
_SLOT_SOURCES: dict[str, tuple[tuple[str, str], ...]] = {
    "cost_rt": (
        ("iqs_item_number",           "DIAG-IQS-SI-01"),
        ("iqs_partnership_type_code", "DIAG-IQS-SI-01"),
        ("shipnode_status",           "DIAG-ANALYZE-SHIPNODES"),
        ("shipnode_item_id",          "DIAG-ANALYZE-SHIPNODES"),
        ("legacy_distributor_id",     "DIAG-ANALYZE-SHIPNODES"),
    ),
    "pre_order": (
        ("preorder_flag",                     "DIAG-ANALYZE-PREORDER-SHIPNODES"),
        ("preorder_consolidated_street_date", "DIAG-ANALYZE-PREORDER-CONSOLIDATED"),
        ("preorder_verdict",                  "DIAG-PREORDER-VERDICT-01"),
    ),
    "replenishable": (
        ("replenishment_flag", "DIAG-ANALYZE-REPLENISHABLE-SHIPNODES"),
    ),
    "acs": (
        ("ase_status",  "DIAG-ACS-INPUTS-BUNDLE-01 (DEW Seller sub-fetch)"),
        ("ase_seller",  "DIAG-ACS-INPUTS-BUNDLE-01 (DEW Seller sub-fetch)"),
        ("acs_enabled", "DIAG-ACS-INPUTS-BUNDLE-01 (DCC sub-fetch, with Consolidated fallback)"),
    ),
    "ftc": (
        ("ftc_consolidated", "DIAG-ANALYZE-FTC-CONSOLIDATED"),
    ),
    "enforcement": (
        ("enforced_paths",       "DIAG-SELLER-ENFORCEMENT-CLASSIFY-01"),
        ("enforcement_blocked",  "DIAG-SELLER-ENFORCEMENT-CLASSIFY-01"),
    ),
    "restriction": (
        ("restriction_groups", "DIAG-DEW-RESTRICTION-GROUP-01"),
    ),
    "shipsize": (
        ("shipsize_consolidated", "DIAG-ANALYZE-SHIPSIZE-CONSOLIDATED"),
        ("shipsize_derived",      "DIAG-DERIVE-SHIPSIZE"),
    ),
    "ship_class": (
        ("shipsize_consolidated", "DIAG-ANALYZE-SHIPSIZE-CONSOLIDATED"),
        ("shipsize_derived",      "DIAG-DERIVE-SHIPSIZE"),
    ),
    "sortable": (
        ("sortable_consolidated", "DIAG-ANALYZE-SORTABLE-CONSOLIDATED"),
    ),
    "gifting": (
        ("gifting_eligibility", "DIAG-ANALYZE-GIFTING"),
    ),
    "substitution": (
        ("substitution_restrictions_csv", "DIAG-ANALYZE-SUBSTITUTION"),
    ),
}


def plan_sub_sop(sub_intent: str = "", **_: Any) -> dict[str, Any]:
    """Return the deterministic tool plan for ``sub_intent``.

    Outputs:
      - ``outcome``         — ``SUB_SOP_PLAN_RESOLVED`` for known codes,
                              ``SUB_SOP_PLAN_UNKNOWN`` otherwise.
      - ``sub_intent``      — echoed back for downstream logging.
      - ``tool_sequence``   — ordered list of tool ids the LLM must
                              call.  Empty list when the code is
                              unknown.
      - ``forbidden_tools`` — tools that must not be called in
                              standalone mode (constant across codes).
      - ``output_block``    — name of the sub-SOP block to render after
                              the ODIN block (e.g. ``"Sortable"``).
      - ``slot_sources``    — list of ``{slot, source}`` records naming
                              the source tool for each non-ODIN slot
                              the LLM must populate before rendering
                              the sub-SOP block.  Empty list when the
                              block draws entirely from ODIN.
      - ``instruction``     — verbatim directive the prompt feeds back
                              to the LLM.
    """
    code = (sub_intent or "").strip().lower()
    plan = _PLANS.get(code)
    if plan is None:
        return {
            "outcome":         "SUB_SOP_PLAN_UNKNOWN",
            "sub_intent":      code,
            "tool_sequence":   [],
            "forbidden_tools": list(_FORBIDDEN_TOOLS),
            "output_block":    "",
            "slot_sources":    [],
            "instruction":     (
                f"No standalone plan exists for sub_intent={code!r}.  "
                "Fall back to INTENT_REQUIRED and render the main "
                "intent menu."
            ),
        }
    tool_sequence, output_block = plan
    slot_sources = _SLOT_SOURCES.get(code, ())
    if slot_sources:
        source_lines = "\n".join(
            f"  - {slot:<32s} ← {tool}" for slot, tool in slot_sources
        )
        source_map_block = (
            "  Slot → source-tool map for this sub-SOP (a slot rendered "
            "as `null` means you skipped the listed tool — call it, "
            "then re-render):\n" + source_lines + "\n"
        )
    else:
        source_map_block = ""
    instruction = (
        "You MUST call EVERY tool listed in tool_sequence, in order, "
        "exactly once each, before rendering the response.  Do not "
        "skip any tool because an earlier tool's output already gives "
        "you a verdict — each skipped tool leaves `null` fields in the "
        "rendered output.  Do NOT call any tool in forbidden_tools.\n"
        + source_map_block
        + "After every tool in tool_sequence has been called, render the "
        f"ODIN block followed by the '{output_block}:' block and end "
        "the response."
    )
    return {
        "outcome":         "SUB_SOP_PLAN_RESOLVED",
        "sub_intent":      code,
        "tool_sequence":   list(tool_sequence),
        "forbidden_tools": list(_FORBIDDEN_TOOLS),
        "output_block":    output_block,
        "slot_sources":    [
            {"slot": s, "source": t} for s, t in slot_sources
        ],
        "instruction":     instruction,
    }


__all__ = ["plan_sub_sop"]
