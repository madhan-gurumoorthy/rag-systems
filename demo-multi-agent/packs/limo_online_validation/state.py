"""State schema for the LIMO Online Eligibility pack.

Offer + node-scoped slots covering the main FC/WFS/MP path eligibility
flow plus every sub-SOP (COST RT, Pre-Order, Replenishable, Shipsize,
Ship Class, Sortable, Gifting, Substitution, ACS, FTC).
"""
from __future__ import annotations

from typing import Optional

from agent_factory.graph.state import (
    BaseWorkItemState,
    append_error,
    append_list,
    empty_base_work_item_state,
)

__all__ = [
    "OnlineEligibilityState",
    "empty_online_eligibility_state",
    "append_list",
    "append_error",
]


class OnlineEligibilityState(BaseWorkItemState, total=False):
    """LIMO Online Eligibility state — offer + node + intent slots."""

    # ── Inputs ──
    offer_id: Optional[str]
    node_id: Optional[str]

    # ── Intent (resolved via Slack HITL gate) ──
    intent: Optional[str]               # MP | FC | WFS
    sub_intent: Optional[str]           # cost_rt / pre_order / replenishable /
                                        # shipsize / ship_class / sortable /
                                        # gifting / substitution / acs / ftc /
                                        # null (= main eligibility flow)

    # ── ODIN attributes (Step 1) ──
    seller_id: Optional[str]
    seller_type: Optional[str]
    offer_created: Optional[bool]
    offer_type: Optional[str]
    product_id: Optional[str]
    wfs_eligible: Optional[str]
    ftc: Optional[list]
    ftc_csv: Optional[str]
    item_class_id: Optional[str]
    goods_and_svc_type: Optional[str]
    ship_size_code_odin: Optional[str]
    ship_class_code: Optional[str]
    sortable_flag_odin: Optional[str]
    ase_odin: Optional[str]
    product_type: Optional[str]
    acc_d_nbr: Optional[str]
    approved_for_animals: Optional[str]
    replen_flag_odin: Optional[bool]

    # ── AURUM FC — node-scoped attrs (Step 2) ──
    aurum_node_id: Optional[str]
    aurum_node_type: Optional[str]
    aurum_node_status: Optional[str]
    aurum_dcc_status: Optional[bool]
    aurum_inclusions: Optional[list]
    aurum_exclusions: Optional[list]

    # ── DEW FC paths (Step 3) ──
    dew_paths: Optional[list]

    # ── Promise / Wakanda (Step 4) ──
    promise_paths: Optional[list]
    promise_present: Optional[bool]

    # ── Eligibility Consolidated FC (Step 5) ──
    consolidated_paths: Optional[list]
    fulfillment_speed: Optional[str]

    # ── Sub-SOP slots ─────────────────────────────────────────────────

    # COST RT
    iqs_item_number: Optional[str]
    iqs_partnership_type_code: Optional[str]
    shipnode_status: Optional[str]
    shipnode_item_id: Optional[str]
    legacy_distributor_id: Optional[str]

    # Pre-Order
    preorder_street_date: Optional[str]
    preorder_flag: Optional[bool]
    preorder_consolidated_street_date: Optional[str]
    preorder_verdict: Optional[str]     # PAST_STREET_DATE | FUTURE_STREET_DATE

    # Replenishable
    replenishment_flag: Optional[bool]

    # Shipsize derivation
    unit_height: Optional[float]
    unit_length: Optional[float]
    unit_width: Optional[float]
    unit_weight: Optional[float]
    girth: Optional[float]
    shipsize_consolidated: Optional[str]
    shipsize_derived: Optional[str]
    shipsize_logic_note: Optional[str]

    # Sortable
    sortable_consolidated: Optional[bool]

    # Gifting
    gifting_eligibility: Optional[bool]
    allow_gift_message: Optional[bool]
    allow_gift_receipt: Optional[bool]
    allow_gift_wrap: Optional[bool]
    gift_overbox_eligible: Optional[bool]

    # Substitution
    substitution_allowed: Optional[bool]
    substitution_restrictions: Optional[list]
    substitution_restrictions_csv: Optional[str]

    # ACS
    ase_status: Optional[str]
    ase_seller: Optional[bool]
    acs_enabled: Optional[bool]

    # FTC
    ftc_consolidated: Optional[str]

    # Seller-Level Enforcement
    offer_fully_created: Optional[bool]
    enforcement_scope: Optional[str]          # WALMART_PATH | SELLER_PATH | None
    enforcement_blocked: Optional[bool]
    enforced_paths: Optional[list]            # e.g. ["SELLER_PATH", "WALMART_PATH"]

    # DEW Restriction
    restriction_groups: Optional[list]        # [{"path": str, "states": [str, ...]}, ...]

    # ── Case 1 deterministic gate ─────────────────────────────────────
    # Populated by DIAG-CASE1-GATE-01.  case1_block_code is one of
    # {OFFER_NOT_CREATED, OTYPE_INVALID, WFS_NOT_ELIGIBLE,
    # INTENT_REQUIRED} when the gate blocks, else None.
    # case1_block_reason carries the intent-aware redirect line the
    # closure template renders verbatim.
    # case1_notice_code / case1_notice_message carry a non-blocking
    # advisory (e.g. MP_WFS_ELIGIBLE_NOTICE when MP intent meets an
    # offer with wfsElig == true).  When set, prompts and the closure
    # template surface the message above the ODIN block and the
    # pipeline still runs Cases 2–5.
    case1_block_code: Optional[str]
    case1_block_reason: Optional[str]
    case1_notice_code: Optional[str]
    case1_notice_message: Optional[str]

    # ── Verdict / closure ──
    verdict_reason: Optional[str]
    block_code: Optional[str]
    runbook_id: Optional[str]


def empty_online_eligibility_state(
    *,
    session_id: str = "",
    agent_id: str = "",
    pack_id: str = "",
    tenant_id: str = "",
    trace_id: Optional[str] = None,
    external_ref: str = "",
    work_item_text: str = "",
    source_channel: str = "a2a",
) -> OnlineEligibilityState:
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
            "node_id": None,
            "intent": None,
            "sub_intent": None,
            "seller_id": None,
            "seller_type": None,
            "offer_created": None,
            "offer_type": None,
            "product_id": None,
            "wfs_eligible": None,
            "ftc": None,
            "ftc_csv": None,
            "item_class_id": None,
            "goods_and_svc_type": None,
            "ship_size_code_odin": None,
            "ship_class_code": None,
            "sortable_flag_odin": None,
            "ase_odin": None,
            "product_type": None,
            "acc_d_nbr": None,
            "approved_for_animals": None,
            "replen_flag_odin": None,
            "aurum_node_id": None,
            "aurum_node_type": None,
            "aurum_node_status": None,
            "aurum_dcc_status": None,
            "aurum_inclusions": None,
            "aurum_exclusions": None,
            "dew_paths": None,
            "promise_paths": None,
            "promise_present": None,
            "consolidated_paths": None,
            "fulfillment_speed": None,
            "iqs_item_number": None,
            "iqs_partnership_type_code": None,
            "shipnode_status": None,
            "shipnode_item_id": None,
            "legacy_distributor_id": None,
            "preorder_street_date": None,
            "preorder_flag": None,
            "preorder_consolidated_street_date": None,
            "preorder_verdict": None,
            "replenishment_flag": None,
            "unit_height": None,
            "unit_length": None,
            "unit_width": None,
            "unit_weight": None,
            "girth": None,
            "shipsize_consolidated": None,
            "shipsize_derived": None,
            "shipsize_logic_note": None,
            "sortable_consolidated": None,
            "gifting_eligibility": None,
            "allow_gift_message": None,
            "allow_gift_receipt": None,
            "allow_gift_wrap": None,
            "gift_overbox_eligible": None,
            "substitution_allowed": None,
            "substitution_restrictions": None,
            "substitution_restrictions_csv": None,
            "ase_status": None,
            "ase_seller": None,
            "acs_enabled": None,
            "ftc_consolidated": None,
            "offer_fully_created": None,
            "enforcement_scope": None,
            "enforcement_blocked": None,
            "enforced_paths": None,
            "restriction_groups": None,
            "case1_block_code": None,
            "case1_block_reason": None,
            "case1_notice_code": None,
            "case1_notice_message": None,
            "verdict_reason": None,
            "block_code": None,
            "runbook_id": None,
        },
    )
    return state  # type: ignore[return-value]
