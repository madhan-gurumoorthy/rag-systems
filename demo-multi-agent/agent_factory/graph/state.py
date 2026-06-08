"""Base LangGraph state schema — packs subclass and extend.

Generic, pack-agnostic state for any work-item pipeline.  External
systems (ServiceNow, Jira, internal queues, etc.) are referenced via
``external_ref`` (human-facing key, e.g. ``"INC12345678"``) and
``external_id`` (opaque record id, e.g. a SNOW ``sys_id``).  The raw
upstream payload sits in ``domain_payload``.  Packs supply pack-specific
typed fields by subclassing ``BaseWorkItemState``.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict

try:
    from langgraph.graph.message import add_messages
except ImportError:  # pragma: no cover
    def add_messages(left, right):  # type: ignore
        return list(left or []) + list(right or [])


def merge_dict(left: Optional[dict], right: Optional[dict]) -> dict:
    """Shallow dict merge — right overrides left."""
    out: dict = dict(left or {})
    out.update(right or {})
    return out


def sum_usage(left: Optional[dict], right: Optional[dict]) -> dict:
    """Per-key integer accumulation for token usage cols."""
    out: dict = dict(left or {})
    for k, v in (right or {}).items():
        if isinstance(v, int) and isinstance(out.get(k), int):
            out[k] = out[k] + v
        else:
            out[k] = v
    return out


def append_error(left: Optional[list], right: Optional[list]) -> list:
    return list(left or []) + list(right or [])


class BaseAgentState(TypedDict, total=False):
    """Universal agent state — packs subclass and extend."""

    session_id: str
    agent_id: str
    tenant_id: str
    trace_id: Optional[str]
    messages: Annotated[list, add_messages]
    current_node: str
    errors: Annotated[list[dict], append_error]
    usage: Annotated[dict, sum_usage]
    metadata: Annotated[dict, merge_dict]


def empty_state() -> BaseAgentState:
    return BaseAgentState(
        session_id="",
        agent_id="",
        tenant_id="",
        trace_id=None,
        messages=[],
        current_node="",
        errors=[],
        usage={
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "reasoning_tokens": 0,
        },
        metadata={},
    )


def append_list(left: Optional[list], right: Optional[list]) -> list:
    return list(left or []) + list(right or [])


class BaseWorkItemState(BaseAgentState, total=False):
    """Work-item pipeline state shared across all packs.

    Pack-agnostic. Packs subclass this and add only their domain-specific
    typed fields.

    Identity:
      * ``external_ref`` — human-facing key from the upstream system
        (e.g. SNOW incident number ``INC12345678``).
      * ``external_id`` — opaque record id (e.g. SNOW ``sys_id``).
      * ``domain_payload`` — raw upstream payload as received from the
        source system, kept verbatim so nodes can extract pack-specific
        fields without re-fetching.
    """

    pack_id: str
    external_ref: str
    external_id: Optional[str]
    source_channel: str
    work_item_text: str
    pre_triage_passed: bool
    skip_reason: Optional[str]
    domain_payload: Optional[dict]
    triage_data: dict
    short_description: Optional[str]
    symptom: Optional[str]
    evidence: Annotated[list[dict], append_list]
    pipeline_health: dict
    decision: dict
    runbook_card: Optional[str]
    card_name: Optional[str]
    decision_confidence: Optional[str]
    requires_approval: bool
    closure_content: Optional[str]
    closure_status: Optional[str]
    resolution_status: Optional[str]
    issue_tag: Optional[str]
    fix_tag: Optional[str]
    closure_notes: Optional[str]
    approval_work_item_id: Optional[str]
    approval_decision: Optional[dict]
    actions_taken: Annotated[list[dict], append_list]
    started_at_monotonic: Optional[float]
    elapsed_ms: Optional[int]


def empty_base_work_item_state(
    *,
    session_id: str = "",
    agent_id: str = "",
    pack_id: str = "",
    tenant_id: str = "",
    trace_id: Optional[str] = None,
    external_ref: str = "",
    work_item_text: str = "",
    source_channel: str = "a2a",
    extra: Optional[dict[str, Any]] = None,
) -> dict:
    """Return a zero-valued BaseWorkItemState dict, optionally merged with ``extra``."""
    state: dict = {
        "session_id": session_id,
        "agent_id": agent_id,
        "tenant_id": tenant_id,
        "trace_id": trace_id,
        "messages": [],
        "current_node": "",
        "errors": [],
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "reasoning_tokens": 0,
        },
        "metadata": {},
        "pack_id": pack_id,
        "external_ref": external_ref,
        "external_id": None,
        "source_channel": source_channel,
        "work_item_text": work_item_text,
        "pre_triage_passed": False,
        "skip_reason": None,
        "domain_payload": None,
        "triage_data": {},
        "short_description": None,
        "symptom": None,
        "evidence": [],
        "pipeline_health": {},
        "decision": {},
        "runbook_card": None,
        "card_name": None,
        "decision_confidence": None,
        "requires_approval": False,
        "closure_content": None,
        "closure_status": None,
        "resolution_status": None,
        "issue_tag": None,
        "fix_tag": None,
        "closure_notes": None,
        "approval_work_item_id": None,
        "approval_decision": None,
        "actions_taken": [],
        "started_at_monotonic": None,
        "elapsed_ms": None,
    }
    if extra:
        state.update(extra)
    return state


__all__ = [
    "BaseAgentState",
    "BaseWorkItemState",
    "empty_state",
    "empty_base_work_item_state",
    "add_messages",
    "merge_dict",
    "sum_usage",
    "append_error",
    "append_list",
]
