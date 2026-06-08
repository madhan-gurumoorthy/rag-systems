"""Storage layer — asyncpg-backed singleton stores sharing a single pool.

Shared infrastructure:
    postgres_state_manager — owns the asyncpg pool every store binds to

LangGraph-native stores (one row per logical entity, RLS-scoped by
``app.tenant_id``):
    agent_registry_store — one row per agent (model/budget/capabilities)
    session_store        — one row per LangGraph thread (UUIDv7 ids)
    work_item_store      — polymorphic incident/action/approval/decision
    event_store          — append-only, monthly RANGE-partitioned event log

Typed row models:
    AgentRegistryRow, SessionRow, WorkItemRow, EventRow — Pydantic v2
    models returned by each store's ``_row_to_dict()``.  Support both
    attribute access (``row.field``) and dict-style access
    (``row["field"]``, ``row.get("field")``) for backwards compatibility.
"""
from storage.state_store import postgres_state_manager

from storage.agent_registry_store import agent_registry_store
from storage.session_store import session_store, _uuid7_str
from storage.work_item_store import work_item_store
from storage.event_store import event_store
from storage.models import (
    AgentRegistryRow,
    SessionRow,
    WorkItemRow,
    EventRow,
)

__all__ = [
    "postgres_state_manager",
    "agent_registry_store",
    "session_store",
    "work_item_store",
    "event_store",
    "_uuid7_str",
    # Typed row models
    "AgentRegistryRow",
    "SessionRow",
    "WorkItemRow",
    "EventRow",
]
