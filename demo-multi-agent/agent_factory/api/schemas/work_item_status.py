"""Response models for the work-item run-status surface.

Three shapes are pinned here so the POST inline-fast path, POST detached
202, and GET poll endpoint all share one source of truth for field
names and JSON serialisation:

* ``WorkItemRunningResponse`` — body returned with ``202 Accepted`` when
  the deadline race times out and the runner detaches.
* ``WorkItemStatusResponse`` — body returned by
  ``GET /a2a/work-item/{session_id}`` for any non-running state and for
  ``running``/``stale`` snapshots.
* ``WorkItemErrorBody`` / ``WorkItemResultBody`` / ``WorkItemApprovalBody``
  — the three optional sub-bodies layered onto the status response.

These models are pure response shapes — they never reach LangGraph or
the storage layer.  Mapping from ``session.run_payload`` happens at the
route boundary via ``cached_inline_body`` below.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class WorkItemResultBody(BaseModel):
    """``run_payload.result`` mirror — set when ``status==done``."""

    status: str = Field(..., description="processed | skipped")
    response: str = ""
    skip_reason: Optional[str] = None


class WorkItemErrorBody(BaseModel):
    """``run_payload.error`` mirror — set when ``status==failed``."""

    type: str = "pipeline"
    message: str = ""
    node: Optional[str] = None


class WorkItemApprovalBody(BaseModel):
    """``run_payload.approval`` mirror — set when ``status==awaiting_approval``."""

    work_item_id: Optional[str] = None


class WorkItemRunningResponse(BaseModel):
    """Body returned with ``202 Accepted`` after the deadline race detaches.

    The caller polls ``GET /a2a/work-item/{session_id}`` until they see
    a terminal status or ``stale``.  No ``poll_url`` is emitted — the
    caller constructs the URL from ``session_id`` to stay compatible
    with path-stripping ingresses (and to match this repo's existing
    API style of never returning URLs).
    """

    status: str = "running"
    session_id: str
    external_ref: str
    started_at: datetime
    deadline_at: datetime


class WorkItemStatusResponse(BaseModel):
    """Body returned by ``GET /a2a/work-item/{session_id}``.

    ``status`` covers the full poll vocabulary
    (``running | awaiting_approval | done | failed | stale``).  The three
    optional sub-bodies (``result`` / ``error`` / ``approval``) are
    populated according to ``status`` exactly as the inline POST body
    would be — so a caller that wins the race and a caller that polls
    afterwards see field-compatible answers.
    """

    session_id: str
    external_ref: str
    status: str
    started_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[WorkItemResultBody] = None
    error: Optional[WorkItemErrorBody] = None
    approval: Optional[WorkItemApprovalBody] = None


# ─────────────────────────────────────────────────────────────────────
# Cache-replay — convert a cached ``run_payload`` row into the inline
# POST body the caller would have seen on the fast path.  Used by the
# POST handler when the idempotency truth table says "return cached".
# ─────────────────────────────────────────────────────────────────────


def cached_inline_body(
    *,
    run_state: str,
    run_payload: dict[str, Any],
    external_ref: str,
    session_id: str,
    agent_name: str,
) -> dict[str, Any]:
    """Reconstruct the inline POST body from a cached ``run_payload``.

    The shape matches the body emitted on the synchronous fast path so a
    re-POST after the original run completed returns the same answer.

    Args:
        run_state: One of ``done | failed | awaiting_approval`` — the
            cached terminal/pause state.  ``running`` is not handled
            here because the caller routes that case to the 202 reply
            instead of cache-replay.
        run_payload: The session row's ``run_payload`` JSONB blob.
        external_ref: The upstream record key for the response.
        session_id: The session id for the response.
        agent_name: The framework's ``AGENT_NAME`` config value (kept
            in the body for back-compat with existing callers).

    Returns:
        A dict in the same shape as the fast-path 200 body.

    Raises:
        ValueError: if ``run_state`` is not one of the cacheable values.
    """
    base = {
        "external_ref": external_ref,
        "session_id":   session_id,
        "agent_name":   agent_name,
    }
    if run_state == "done":
        result = run_payload.get("result") or {}
        inline_status = result.get("status") or "processed"
        return {
            **base,
            "status":               inline_status,
            "skip_reason":          result.get("skip_reason"),
            "error":                None,
            "retryable":            None,
            "approval_work_item_id": None,
            "response":             result.get("response") or "",
            "time_taken":           0.0,
        }
    if run_state == "failed":
        err = run_payload.get("error") or {}
        return {
            **base,
            "status":               "error",
            "skip_reason":          None,
            "error":                err.get("message"),
            "retryable":            True,
            "approval_work_item_id": None,
            "response":             "",
            "time_taken":           0.0,
        }
    if run_state == "awaiting_approval":
        approval = run_payload.get("approval") or {}
        return {
            **base,
            "status":               "pending_approval",
            "skip_reason":          None,
            "error":                None,
            "retryable":            None,
            "approval_work_item_id": approval.get("work_item_id"),
            "response":             "",
            "time_taken":           0.0,
        }
    raise ValueError(f"run_state {run_state!r} is not cache-replayable")


__all__ = [
    "WorkItemResultBody",
    "WorkItemErrorBody",
    "WorkItemApprovalBody",
    "WorkItemRunningResponse",
    "WorkItemStatusResponse",
    "cached_inline_body",
]
