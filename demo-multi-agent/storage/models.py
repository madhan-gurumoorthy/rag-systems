"""Typed Pydantic models for the 4 canonical storage tables.

Each model mirrors a single DB row.  The stores' ``_row_to_dict()``
helpers return these instead of raw dicts, giving callers IDE
autocomplete, validation, and a stable serialization contract.

Field names match the SQL column names 1:1.  JSONB columns are typed
as ``dict[str, Any]`` with an empty-dict default.  UUID columns are
stringified at the asyncpg boundary (the stores' ``_row_to_dict``
already does ``str(uuid)``), so the models receive plain ``str``.

All models use ``model_config = ConfigDict(from_attributes=True)`` so
``ModelClass.model_validate(row_dict)`` works with both dicts and
asyncpg Record objects (via ``dict(row)``).

Backwards compatibility: ``DictCompatibleModel`` adds ``__getitem__``,
``get``, and ``__contains__`` so existing callers that use dict-style
access (``row["field"]``, ``row.get("field")``) keep working without
changes.  New code should prefer attribute access (``row.field``).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from datetime import timezone as _tz

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    """Fallback default for timestamp fields.

    In production, asyncpg always supplies the actual DB value.  The
    default is only exercised when constructing a model from a partial
    dict (e.g. in unit tests that only populate the fields under test).
    """
    return datetime.now(_tz.utc)


# ─────────────────────────────────────────────────────────────────────
# Base: dict-compatible Pydantic model
# ─────────────────────────────────────────────────────────────────────

class DictCompatibleModel(BaseModel):
    """Pydantic BaseModel that also supports dict-style access.

    Supports ``row["field"]``, ``row.get("field", default)``, and
    ``"field" in row`` so existing callers that relied on raw dicts
    keep working after the migration to typed models.
    """

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) and key in self.model_fields


# ═══════════════════════════════════════════════════════════════════════
# 1. agent_registry  [9 cols]
# ═══════════════════════════════════════════════════════════════════════

class AgentRegistryRow(DictCompatibleModel):
    """One row from the ``agent_registry`` table."""

    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    agent_name: str = ""
    agent_version: str = ""
    owner_team: str = ""
    status: str = "active"
    config: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    archived_at: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════════════
# 2. session  [11 cols]
# ═══════════════════════════════════════════════════════════════════════

class SessionRow(DictCompatibleModel):
    """One row from the ``session`` table.

    ``session_id`` is a UUIDv7 generated at the app layer and doubles as
    the LangGraph ``thread_id``.  Per-run state (deadline, payload,
    pipeline status) lives on ``work_item``, not here.
    """

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    agent_id: str = ""
    tenant_id: str = ""
    parent_session_id: Optional[str] = None
    status: str = "active"
    trace_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    domain_data: dict[str, Any] = {}
    started_at: datetime = Field(default_factory=_utcnow)
    ended_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════════════
# 3. work_item  [24 cols]
# ═══════════════════════════════════════════════════════════════════════

class WorkItemRow(DictCompatibleModel):
    """One row from the ``work_item`` table.

    Polymorphic via ``kind`` discriminator.  Sparse kind-specific fields
    live in ``kind_data`` (JSONB).  The 4-col LangGraph interrupt
    composite key is stamped on ``kind='approval'`` rows.

    ``run_deadline_at`` and ``run_payload`` support the 3-minute response
    contract: the route handler sets a deadline on start and the GET
    endpoint uses it for stale detection.
    """

    model_config = ConfigDict(from_attributes=True)

    work_item_id: str
    agent_id: str = ""
    pack_id: str = ""
    session_id: str = ""
    parent_work_item_id: Optional[str] = None
    kind: str = ""
    status: str = "pending"
    priority: str = "p3"
    idempotency_key: Optional[str] = None
    # LangGraph interrupt composite key
    interrupt_checkpoint_ns: Optional[str] = None
    interrupt_checkpoint_id: Optional[str] = None
    interrupt_task_id: Optional[str] = None
    interrupt_idx: Optional[int] = None
    # Approval lifecycle
    assignee: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    # JSONB payloads
    kind_data: dict[str, Any] = {}
    domain_data: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    archived_at: Optional[datetime] = None
    # 3-minute response contract
    run_deadline_at: Optional[datetime] = None
    run_payload: dict[str, Any] = {}


# ═══════════════════════════════════════════════════════════════════════
# 4. event  [23 cols]
# ═══════════════════════════════════════════════════════════════════════

class EventRow(DictCompatibleModel):
    """One row from the ``event`` table (append-only, monthly partitioned).

    Drives fine-tuning extraction, telemetry, replay safety, and
    per-session ordering via ``seq_num``.
    """

    model_config = ConfigDict(from_attributes=True)

    event_id: str
    session_id: str = ""
    agent_id: str = ""
    tenant_id: str = ""
    work_item_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    seq_num: int = 0
    event_type: str = ""
    trace_id: Optional[str] = None
    # LLM fields
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    input_messages: Optional[list] = None
    output_message: Optional[dict] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    reasoning_tokens: int = 0
    llm_metadata: Optional[dict] = None
    # Latency
    llm_latency_ms: Optional[int] = None
    tool_latency_ms: Optional[int] = None
    time_to_first_token_ms: Optional[int] = None
    # Catch-all
    domain_data: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=_utcnow)


__all__ = [
    "DictCompatibleModel",
    "AgentRegistryRow",
    "SessionRow",
    "WorkItemRow",
    "EventRow",
]
