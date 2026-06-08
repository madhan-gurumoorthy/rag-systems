from __future__ import annotations

from typing import Any, List, Optional

from agent_factory.graph.state import (
    BaseWorkItemState,
    append_error,
    append_list,
    empty_base_work_item_state,
)

__all__ = [
    "OfferIntelligenceState",
    "empty_offer_intelligence_state",
    "append_list",
    "append_error",
]


class OfferIntelligenceState(BaseWorkItemState, total=False):
    """Combined state for the Offer Intelligence pack.

    Carries the union of fields needed by:

      * OL listing verification (``DIAG-OL-TRIAGE-01``) — populates
        ``listing_status``, ``overall_verdict``, ``matched_rule_ids``,
        ``reason_codes``, ``rule_verdicts``, ``triage_result``.
      * Unpublish reason-code validation (``DIAG-VALIDATE-OFFER-01``) —
        populates ``publish_status``, ``audit_history``,
        ``reason_codes_checked``, ``validation_results``,
        ``validation_summary``.

    ``check_mode`` is set by the TriageAgent and read by the
    DiagnosticAgent prompt to decide which tool(s) to invoke.
    """

    # ── Shared inputs ──────────────────────────────────────────────
    offer_id: Optional[str]
    check_mode: Optional[str]      # "ol_only" | "publish_only" | "both"

    # ── OL listing verification slots ──────────────────────────────
    store_id: Optional[str]
    mart_id: Optional[str]
    item_id: Optional[str]
    listing_status: Optional[str]
    overall_verdict: Optional[str]
    matched_rule_ids: Optional[List[str]]
    reason_codes: Optional[List[str]]
    rule_verdicts: Optional[List[dict[str, Any]]]
    triage_result: Optional[dict[str, Any]]
    triage_errors: Optional[List[str]]

    # ── Unpublish validation slots ─────────────────────────────────
    reason_code: Optional[str]
    publish_status: Optional[str]
    audit_history: Optional[str]
    reason_codes_checked: Optional[List[str]]
    validation_results: Optional[List[Any]]
    validation_summary: Optional[Any]


def empty_offer_intelligence_state(
    *,
    session_id: str = "",
    agent_id: str = "",
    pack_id: str = "",
    tenant_id: str = "",
    trace_id: Optional[str] = None,
    external_ref: str = "",
    work_item_text: str = "",
    source_channel: str = "a2a",
) -> OfferIntelligenceState:
    state = empty_base_work_item_state(
        session_id=session_id,
        agent_id=agent_id,
        pack_id=pack_id,
        tenant_id=tenant_id,
        trace_id=trace_id,
        external_ref=external_ref,
        work_item_text=work_item_text,
        source_channel=source_channel,
        extra={
            # Shared
            "offer_id": None,
            "check_mode": None,
            # OL listing
            "store_id": None,
            "mart_id": "0",
            "item_id": None,
            "listing_status": None,
            "overall_verdict": None,
            "matched_rule_ids": None,
            "reason_codes": None,
            "rule_verdicts": None,
            "triage_result": None,
            "triage_errors": None,
            # Unpublish validation
            "reason_code": None,
            "publish_status": None,
            "audit_history": None,
            "reason_codes_checked": None,
            "validation_results": None,
            "validation_summary": None,
        },
    )
    return state  # type: ignore[return-value]
