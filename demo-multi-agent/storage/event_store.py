"""Event storage — append-only LLM / tool / HITL / state / error log.

Drives:
  • Fine-tuning extraction (input_messages + output_message fields)
  • Telemetry & cost (the 5-col UsageMetadata: input/output/cache_read/
    cache_creation/reasoning)
  • Replay safety (parent_event_id chain + idempotent provider message id)
  • Per-session ordering (seq_num, monotonic within session_id)

Table is RANGE-partitioned monthly on `created_at`.  Indexes on the parent
table are inherited by all partitions (PG 11+) — no per-partition wiring
needed here.

The ONLY typed correlation column is `trace_id` (W3C traceparent).  The
langchain run_id, langgraph checkpoint_id, langgraph node_name, and any
other cross-system handles live inside `domain_data` per ADR-013.

Uses the shared asyncpg pool from `state_store.postgres_state_manager`.

Part of the new LangGraph-native data model (migration 005).
"""
from __future__ import annotations

import json
import traceback
from typing import Any, Optional

try:
    from agent_factory.common.logging import get_logger
    logger = get_logger("storage.event")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("storage.event")

from storage._rls import acquire_with_tenant
from storage.models import EventRow

_TABLE = "event"

# Allowed event_types — matches the CHECK constraint in migration 005.
_VALID_EVENT_TYPES = {"dispatch", "llm", "tool", "api_call", "hitl", "state", "error"}


class EventStore:
    """Manages the event table — append-only, monthly partitioned."""

    def __init__(self):
        self._pool = None

    def bind_pool(self, pool) -> None:
        """Bind an existing asyncpg pool (from postgres_state_manager)."""
        self._pool = pool

    @property
    def is_available(self) -> bool:
        return self._pool is not None

    # ── Write operations ─────────────────────────────────────────────

    async def append_event(
        self,
        *,
        session_id: str,
        agent_id: str,
        tenant_id: str,
        event_type: str,
        seq_num: Optional[int] = None,            # auto-assigned if None
        work_item_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        # LLM fields
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        input_messages: Optional[list] = None,
        output_message: Optional[dict] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
        reasoning_tokens: int = 0,
        llm_metadata: Optional[dict] = None,
        # Latency
        llm_latency_ms: Optional[int] = None,
        tool_latency_ms: Optional[int] = None,
        time_to_first_token_ms: Optional[int] = None,
        # Catch-all
        domain_data: Optional[dict] = None,
    ) -> Optional[str]:
        """Append a single event row.  Returns event_id on success, or None.

        If `seq_num` is None, computes the next per-session sequence number
        inside the same transaction so concurrent writers can't collide.
        Use an explicit `seq_num` only when you've already chosen it (e.g.
        the event recorder batches events and assigns them monotonically).

        Cost/latency fields default to 0 / NULL for non-LLM events.
        """
        if not self.is_available:
            return None
        if event_type not in _VALID_EVENT_TYPES:
            raise ValueError(f"invalid event_type: {event_type!r}")

        input_msgs_json  = json.dumps(input_messages, default=str) if input_messages is not None else None
        output_msg_json  = json.dumps(output_message, default=str) if output_message is not None else None
        llm_meta_json    = json.dumps(llm_metadata,   default=str) if llm_metadata   is not None else None
        domain_json      = json.dumps(domain_data or {}, default=str)

        try:
            # `acquire_with_tenant` opens an explicit transaction and
            # writes `app.tenant_id` via SET LOCAL.  The
            # `event_tenant_isolation` policy consults the GUC on the
            # WITH CHECK side, so the GUC MUST be set before the INSERT.
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                if seq_num is None:
                    seq_num = await self._next_seq_num(conn, session_id)
                row = await conn.fetchrow(
                    f"""
                    INSERT INTO {_TABLE}
                        (session_id, agent_id, tenant_id, work_item_id,
                         parent_event_id, seq_num, event_type, trace_id,
                         model_provider, model_name, input_messages, output_message,
                         input_tokens, output_tokens, cache_read_tokens,
                         cache_creation_tokens, reasoning_tokens, llm_metadata,
                         llm_latency_ms, tool_latency_ms, time_to_first_token_ms,
                         domain_data)
                    VALUES ($1::uuid, $2, $3, $4::uuid,
                            $5::uuid, $6, $7, $8,
                            $9, $10, $11::jsonb, $12::jsonb,
                            $13, $14, $15,
                            $16, $17, $18::jsonb,
                            $19, $20, $21,
                            $22::jsonb)
                    RETURNING event_id
                    """,
                    session_id, agent_id, tenant_id, work_item_id,
                    parent_event_id, seq_num, event_type, trace_id,
                    model_provider, model_name, input_msgs_json, output_msg_json,
                    input_tokens, output_tokens, cache_read_tokens,
                    cache_creation_tokens, reasoning_tokens, llm_meta_json,
                    llm_latency_ms, tool_latency_ms, time_to_first_token_ms,
                    domain_json,
                )
            return str(row["event_id"]) if row else None
        except Exception as e:
            logger.error(f"append_event failed: {e}")
            logger.debug(traceback.format_exc())
            return None

    # ── Read operations ──────────────────────────────────────────────

    async def get_event(self, event_id: str) -> Optional[EventRow]:
        """Fetch a single event row by event_id.

        Note: queries that don't include `created_at` can't prune partitions,
        so this is intentionally slower than session-scoped reads.  For hot
        paths, prefer `list_by_session` / `get_session_window` which prune.
        """
        if not self.is_available:
            return None
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT * FROM {_TABLE} WHERE event_id = $1::uuid LIMIT 1",
                    event_id,
                )
            return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"get_event failed: {e}")
            return None

    async def list_by_session(
        self,
        session_id: str,
        *,
        event_type: Optional[str] = None,
        limit: int = 500,
    ) -> list[EventRow]:
        """List events for a session, ordered by seq_num ascending."""
        if not self.is_available:
            return []
        try:
            async with self._pool.acquire() as conn:
                if event_type:
                    if event_type not in _VALID_EVENT_TYPES:
                        raise ValueError(f"invalid event_type: {event_type!r}")
                    rows = await conn.fetch(
                        f"SELECT * FROM {_TABLE} "
                        f"WHERE session_id = $1::uuid AND event_type = $2 "
                        f"ORDER BY seq_num ASC LIMIT $3",
                        session_id, event_type, limit,
                    )
                else:
                    rows = await conn.fetch(
                        f"SELECT * FROM {_TABLE} "
                        f"WHERE session_id = $1::uuid "
                        f"ORDER BY seq_num ASC LIMIT $2",
                        session_id, limit,
                    )
            return [_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"list_by_session failed: {e}")
            return []

    async def list_by_work_item(
        self,
        work_item_id: str,
        *,
        limit: int = 500,
    ) -> list[EventRow]:
        """List events tied to a single work_item, ordered by seq_num."""
        if not self.is_available:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    f"SELECT * FROM {_TABLE} "
                    f"WHERE work_item_id = $1::uuid "
                    f"ORDER BY seq_num ASC LIMIT $2",
                    work_item_id, limit,
                )
            return [_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"list_by_work_item failed: {e}")
            return []

    async def get_session_token_totals(self, session_id: str) -> dict:
        """Sum the 5 UsageMetadata token cols + cost-relevant counters.

        Returns:
            {
              input_tokens, output_tokens, cache_read_tokens,
              cache_creation_tokens, reasoning_tokens, total_tokens,
              llm_event_count
            }
        Falls back to all-zero dict if the session has no events.
        """
        if not self.is_available:
            return _empty_token_totals()
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""
                    SELECT
                        COALESCE(SUM(input_tokens), 0)          AS input_tokens,
                        COALESCE(SUM(output_tokens), 0)         AS output_tokens,
                        COALESCE(SUM(cache_read_tokens), 0)     AS cache_read_tokens,
                        COALESCE(SUM(cache_creation_tokens), 0) AS cache_creation_tokens,
                        COALESCE(SUM(reasoning_tokens), 0)      AS reasoning_tokens,
                        COALESCE(SUM(input_tokens + output_tokens
                                     + cache_read_tokens + cache_creation_tokens
                                     + reasoning_tokens), 0)    AS total_tokens,
                        COUNT(*) FILTER (WHERE event_type = 'llm') AS llm_event_count
                    FROM {_TABLE}
                    WHERE session_id = $1::uuid
                    """,
                    session_id,
                )
            return dict(row) if row else _empty_token_totals()
        except Exception as e:
            logger.error(f"get_session_token_totals failed: {e}")
            return _empty_token_totals()

    async def find_by_provider_message_id(
        self,
        provider_message_id: str,
        *,
        limit: int = 5,
    ) -> list[EventRow]:
        """GIN-on-expression lookup: find events whose llm_metadata.response_metadata.id
        contains the given provider message id.

        Used for replay safety — if we re-process a webhook delivery, we
        can detect that this exact LLM call already happened.
        """
        if not self.is_available:
            return []
        try:
            # JSONB containment hits the GIN expression index defined in 005:
            #     CREATE INDEX ... USING GIN ((llm_metadata -> 'response_metadata' -> 'id'))
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT * FROM {_TABLE}
                    WHERE llm_metadata IS NOT NULL
                      AND llm_metadata -> 'response_metadata' -> 'id'
                          @> to_jsonb($1::text)
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    provider_message_id, limit,
                )
            return [_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"find_by_provider_message_id failed: {e}")
            return []

    async def list_by_trace_id(
        self,
        trace_id: str,
        *,
        limit: int = 500,
    ) -> list[EventRow]:
        """List all events sharing a W3C traceparent — cross-system correlation."""
        if not self.is_available:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    f"SELECT * FROM {_TABLE} "
                    f"WHERE trace_id = $1 "
                    f"ORDER BY created_at ASC LIMIT $2",
                    trace_id, limit,
                )
            return [_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"list_by_trace_id failed: {e}")
            return []

    # ── Internals ────────────────────────────────────────────────────

    async def _next_seq_num(self, conn, session_id: str) -> int:
        """Compute the next per-session seq_num inside the caller's transaction.

        Race-safe via `pg_advisory_xact_lock` keyed on a hash of the
        session_id.  The lock is acquired inside the same transaction as
        the subsequent INSERT and released automatically on commit/abort.
        This serializes seq_num assignment per-session without blocking
        writers to other sessions.

        Why not a unique constraint?  The event table is RANGE-partitioned
        on `created_at`, and a unique constraint on a partitioned table
        must include the partition key.  `UNIQUE (session_id, seq_num,
        created_at)` would let duplicates through at the same created_at
        boundary, defeating the purpose.

        Why not a sequence-per-session?  Too many sequences (~1 per
        thread); cleanup is fragile and the namespace blows out.
        """
        # hashtext() takes a TEXT and returns an int4; ideal advisory-lock key.
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext($1::text || '::event_seq'))",
            session_id,
        )
        row = await conn.fetchrow(
            f"SELECT COALESCE(MAX(seq_num), -1) + 1 AS next "
            f"FROM {_TABLE} WHERE session_id = $1::uuid",
            session_id,
        )
        return int(row["next"]) if row else 0


def _empty_token_totals() -> dict:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "llm_event_count": 0,
    }


def _row_to_dict(row) -> EventRow:
    """Coerce asyncpg Record → ``EventRow``; parse JSONB; stringify UUIDs."""
    d = dict(row)
    for k in ("event_id", "session_id", "work_item_id", "parent_event_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    for k in ("input_messages", "output_message", "llm_metadata", "domain_data"):
        raw = d.get(k)
        if isinstance(raw, str):
            try:
                d[k] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                d[k] = None if k != "domain_data" else {}
    return EventRow.model_validate(d)


# Global singleton (exported)
event_store = EventStore()

__all__ = ["EventStore", "event_store", "EventRow"]
