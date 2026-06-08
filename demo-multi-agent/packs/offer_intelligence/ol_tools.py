"""
Python-function callables wired into ``tools.yaml`` for the OL Triage pack.

Two callables are exposed:

  - ``run_ol_triage(offer_id, store_id, mart_id="0")`` — async wrapper around
    the deterministic :class:`OLTriageEngine`. Returns the full
    :class:`TriageResult` payload as a plain dict so the tool executor can
    apply outcome rules and field extraction without further parsing.

  - ``render_ol_report(triage_result)`` — synchronous helper that renders a
    human-readable Markdown report from a TriageResult dict.
"""
from __future__ import annotations

import json
from typing import Any

from packs.offer_intelligence.services.report_renderer import render_full_report, render_rule_block
from packs.offer_intelligence.services.rule_registry import get_registry
from packs.offer_intelligence.triage_engine import get_engine


_OUTCOME_MAP: dict[str, str] = {
    "LISTED":           "OL_LISTED",
    "ALL_VALID":        "OL_ALL_VALID",
    "HAS_INVALID":      "OL_HAS_INVALID",
    "PARTIAL":          "OL_PARTIAL",
    "CANNOT_EVALUATE":  "OL_CANNOT_EVALUATE",
    "NO_MATCHED_RULES": "OL_NO_MATCHED_RULES",
}


async def run_ol_triage(
    offer_id: str,
    store_id: str,
    mart_id: str = "0",
) -> str:
    """Run the deterministic OL triage engine for a single (offer, store).

    Returns a compact JSON payload containing:
      - outcome code for the decision matrix
      - top-level summary fields for evidence extraction
      - pre-rendered human-readable report for the closure template
    """
    engine = get_engine()
    result = await engine.triage_offer(
        offer_id=offer_id,
        store_id=store_id,
        mart_id=mart_id,
    )
    payload = result.to_dict()

    # Derive the outcome code for the decision matrix.
    verdict = payload.get("overall_verdict", "")
    ls = payload.get("listing_status", "")
    if ls == "LISTED":
        outcome = "OL_LISTED"
    elif ls == "UNKNOWN":
        outcome = "OL_LISTING_UNKNOWN"
    else:
        outcome = _OUTCOME_MAP.get(verdict, "OL_CANNOT_EVALUATE")

    # Pre-render the detailed report so the closure template can
    # embed it directly without needing the verbose nested data.
    report_data = render_ol_report(payload)

    # Return a compact JSON — strip rule_verdicts / per_condition_results
    # (the rendered_report carries all the detail).  Keeps the payload
    # well within the evidence preview char limit.
    compact: dict[str, Any] = {
        "offer_id": offer_id,
        "store_id": store_id,
        "mart_id": mart_id,
        "listing_status": ls,
        "overall_verdict": verdict,
        "matched_rule_ids": ", ".join(
            str(r) for r in (payload.get("matched_rule_ids") or [])
        ),
        "reason_codes": ", ".join(
            str(r) for r in (payload.get("reason_codes") or [])
        ),
        "outcome": outcome,
        "rendered_report": report_data.get("report", ""),
    }
    return json.dumps(compact, default=str, ensure_ascii=False)


_VERDICT_EMOJI: dict[str, str] = {
    "VALID": "✅ VALID DELIST",
    "INVALID": "❌ INVALID DELIST",
    "PARTIAL": "⚠️ PARTIAL",
    "CANNOT_EVALUATE": "⚠️ CANNOT EVALUATE",
}


def render_ol_report(triage_result: dict[str, Any]) -> dict[str, Any]:
    """Render a Markdown OL Triage Report from a TriageResult dict.

    Returns ``{"report": <text>, "rule_blocks": [...]}``.
    """
    if not isinstance(triage_result, dict):
        return {"report": "", "rule_blocks": [], "_error": "triage_result is not a dict"}

    offer_id = triage_result.get("offer_id", "?")
    store_id = triage_result.get("store_id", "?")
    mart_id = triage_result.get("mart_id", "0")
    listing_status = triage_result.get("listing_status", "UNKNOWN")
    rule_verdicts = triage_result.get("rule_verdicts", []) or []

    registry = get_registry()
    rule_blocks: list[str] = []
    for rv in rule_verdicts:
        rule_id = rv.get("rule_id", "")
        rule_def = registry.get_rule(rule_id) or {
            "rule_id": rule_id,
            "rule_name": rv.get("rule_name", ""),
            "rule_group": rv.get("rule_group", ""),
            "reason_code": rv.get("reason_code", ""),
            "expression": "",
        }
        rule_blocks.append(render_rule_block(rule_def, rv))

    # Per-rule summary bullets for the Overall Summary section.
    summary_lines: list[str] = []
    for rv in rule_verdicts:
        rule_id = rv.get("rule_id", "")
        rule_name = rv.get("rule_name", "")
        v = rv.get("verdict", "CANNOT_EVALUATE")
        summary_lines.append(
            f"- Rule {rule_id}  ({rule_name}) : {_VERDICT_EMOJI.get(v, v)}"
        )

    errors = triage_result.get("errors", []) or []
    if errors:
        summary_lines.append("")
        summary_lines.append("Errors:")
        for e in errors:
            summary_lines.append(f"  - {e}")

    report = render_full_report(
        offer_id=offer_id,
        store_id=store_id,
        mart_id=mart_id,
        listing_status=listing_status,
        rule_blocks=rule_blocks,
        summary_lines=summary_lines,
    )
    return {"report": report, "rule_blocks": rule_blocks}


__all__ = ["run_ol_triage", "render_ol_report"]
