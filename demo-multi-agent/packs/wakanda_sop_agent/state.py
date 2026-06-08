from __future__ import annotations

from typing import Annotated, Optional

from agent_factory.graph.state import (
    BaseWorkItemState,
    add_messages,
    append_error,
    append_list,
    empty_base_work_item_state,
    merge_dict,
    sum_usage,
)

__all__ = ["IncidentState", "empty_incident_state", "append_list", "append_error"]


class IncidentState(BaseWorkItemState, total=False):
    """Wakanda SOP Agent state — inventory-query-specific fields."""

    node_id: Optional[str]
    query_intent: Optional[str]
    query_type: Optional[str]


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
        extra={"node_id": None, "query_intent": None, "query_type": None},
    )
    return state  # type: ignore[return-value]
