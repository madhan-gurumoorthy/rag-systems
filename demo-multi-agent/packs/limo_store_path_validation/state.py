from __future__ import annotations

from typing import Optional

from agent_factory.graph.state import (
    BaseWorkItemState,
    append_error,
    append_list,
    empty_base_work_item_state,
)

__all__ = [
    "PathEligibilityState",
    "empty_path_eligibility_state",
    "append_list",
    "append_error",
]


class PathEligibilityState(BaseWorkItemState, total=False):
    """1P Store Path Eligibility state — offer + store-scoped slots."""

    # ── Inputs ──
    offer_id: Optional[str]
    store_id: Optional[str]
    # Outbound GEO sub-SOP additional mandatory inputs.
    state_code: Optional[str]
    zip_code: Optional[str]

    # ── ODIN attributes (Step 1) ──
    seller_id: Optional[str]
    seller_type: Optional[str]
    offer_created: Optional[bool]
    offer_type: Optional[str]
    ftc: Optional[list]
    ftc_csv: Optional[str]
    item_class_id: Optional[str]
    product_id: Optional[str]
    delivery_method: Optional[str]
    single_pillable: Optional[str]
    approved_for_animals: Optional[str]
    product_type: Optional[str]
    acc_d_nbr: Optional[str]
    pfhbrc: Optional[str]
    vision_center_approved: Optional[bool]
    bundle_grp_type: Optional[str]
    bundle_grp_sub_type: Optional[str]

    # ── Store status (Step 2) ──
    store_status: Optional[str]

    # ── Product RT (Step 1.5 — Photo / Tire path) ──
    product_rt_item_class_id: Optional[str]
    product_rt_delivery_method: Optional[str]
    product_rt_personalizable: Optional[str]
    product_rt_personalization_url: Optional[str]

    # ── Sub-case dispatch ──
    subcase: Optional[str]              # tire / photo / petrx / vision_rx /
                                        # custom_cake / humax_rx /
                                        # delivery_inhome / drone /
                                        # ip_path / main
    store_list_eligible: Optional[bool]
    store_list_name: Optional[str]

    # ── Eligibility-source results ──
    aurum_inclusions: Optional[list]
    aurum_exclusions: Optional[list]
    dew_paths: Optional[list]
    consolidated_paths: Optional[list]

    # ── Outbound GEO sub-SOP ──
    offer_fully_created: Optional[bool]
    consolidated_v2_paths: Optional[list]
    consolidated_v2_restricted: Optional[bool]
    dew_geo_matches: Optional[list]
    dew_geo_restricted: Optional[bool]
    dew_offer_groups: Optional[list]
    dew_offer_restricted: Optional[bool]

    # ── Verdict + reasons ──
    verdict_reason: Optional[str]


def empty_path_eligibility_state(
    *,
    session_id: str = "",
    agent_id: str = "",
    pack_id: str = "",
    tenant_id: str = "",
    trace_id: Optional[str] = None,
    external_ref: str = "",
    work_item_text: str = "",
    source_channel: str = "a2a",
) -> PathEligibilityState:
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
            "store_id": None,
            "state_code": None,
            "zip_code": None,
            "seller_id": None,
            "seller_type": None,
            "offer_created": None,
            "offer_type": None,
            "ftc": None,
            "ftc_csv": None,
            "item_class_id": None,
            "product_id": None,
            "delivery_method": None,
            "single_pillable": None,
            "approved_for_animals": None,
            "product_type": None,
            "acc_d_nbr": None,
            "pfhbrc": None,
            "vision_center_approved": None,
            "bundle_grp_type": None,
            "bundle_grp_sub_type": None,
            "store_status": None,
            "product_rt_item_class_id": None,
            "product_rt_delivery_method": None,
            "product_rt_personalizable": None,
            "product_rt_personalization_url": None,
            "subcase": None,
            "store_list_eligible": None,
            "store_list_name": None,
            "aurum_inclusions": None,
            "aurum_exclusions": None,
            "dew_paths": None,
            "consolidated_paths": None,
            "offer_fully_created": None,
            "consolidated_v2_paths": None,
            "consolidated_v2_restricted": None,
            "dew_geo_matches": None,
            "dew_geo_restricted": None,
            "dew_offer_groups": None,
            "dew_offer_restricted": None,
            "verdict_reason": None,
        },
    )
    return state  # type: ignore[return-value]
