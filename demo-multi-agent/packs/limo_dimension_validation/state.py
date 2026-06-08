from __future__ import annotations

from typing import Optional

from agent_factory.graph.state import (
    BaseWorkItemState,
    append_error,
    append_list,
    empty_base_work_item_state,
)

__all__ = ["IncidentState", "empty_incident_state", "append_list", "append_error"]


class IncidentState(BaseWorkItemState, total=False):
    """LIMO Dimension Validation state — offer/GTIN-specific slots."""

    # ── Offer header (from ODIN) ──
    offer_id: Optional[str]
    seller_id: Optional[str]
    seller_type: Optional[str]
    wfs_eligible: Optional[str]
    primary_gtin: Optional[str]
    alternate_gtins: Optional[list]

    # ── MP classifier output (deterministic, post-ODIN) ──
    mp_offer: Optional[bool]
    mp_classify_reason: Optional[str]
    seller_type_norm: Optional[str]
    wfs_eligible_norm: Optional[str]

    # ── IQS GOLD record ──
    iqs_gold_height: Optional[float]
    iqs_gold_length: Optional[float]
    iqs_gold_width: Optional[float]
    iqs_gold_weight: Optional[float]
    iqs_gold_timestamp: Optional[str]
    iqs_gold_capture_method: Optional[str]

    # ── IQS Supplier record ──
    iqs_supplier_height: Optional[float]
    iqs_supplier_length: Optional[float]
    iqs_supplier_width: Optional[float]
    iqs_supplier_weight: Optional[float]
    iqs_supplier_timestamp: Optional[str]
    iqs_supplier_capture_method: Optional[str]

    # ── Comparison results ──
    selection_explanation: Optional[list]


def empty_incident_state(
    *,
    session_id: str = "",
    agent_id: str = "",
    pack_id: str = "",
    tenant_id: str = "",
    trace_id: Optional[str] = None,
    external_ref: str = "",
    work_item_text: str = "",
    source_channel: str = "a2a",
) -> IncidentState:
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
            "offer_id": None,
            "seller_id": None,
            "seller_type": None,
            "wfs_eligible": None,
            "primary_gtin": None,
            "alternate_gtins": None,
            "mp_offer": None,
            "mp_classify_reason": None,
            "seller_type_norm": None,
            "wfs_eligible_norm": None,
            "iqs_gold_height": None,
            "iqs_gold_length": None,
            "iqs_gold_width": None,
            "iqs_gold_weight": None,
            "iqs_gold_timestamp": None,
            "iqs_gold_capture_method": None,
            "iqs_supplier_height": None,
            "iqs_supplier_length": None,
            "iqs_supplier_width": None,
            "iqs_supplier_weight": None,
            "iqs_supplier_timestamp": None,
            "iqs_supplier_capture_method": None,
            "selection_explanation": None,
        },
    )
    return state  # type: ignore[return-value]
