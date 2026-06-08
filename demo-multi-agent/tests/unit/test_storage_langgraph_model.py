"""Unit tests for the LangGraph-native data model stores (migration 005).

Covers the parts that don't require a live Postgres:
  • UUIDv7 generator — version/variant bits + monotonic ordering
  • Validation guards (kind, priority, event_type)
  • `is_available` semantics when no pool is bound
  • `_row_to_dict` JSONB parsing & UUID stringification
  • Idempotency / interrupt-key SQL composition (mocked pool)

Integration-level tests against a real Postgres live under
`tests/integration/` (added in the integration workstream).
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from storage.agent_registry_store import (
    AgentRegistryStore,
    _row_to_dict as _agent_row_to_dict,
)
from storage.event_store import (
    EventStore,
    _empty_token_totals,
    _row_to_dict as _event_row_to_dict,
    _VALID_EVENT_TYPES,
)
from storage.session_store import (
    SessionStore,
    _row_to_dict as _session_row_to_dict,
    _uuid7_str,
)
from storage.work_item_store import (
    WorkItemStore,
    _VALID_KINDS,
    _VALID_PRIORITIES,
    _row_to_dict as _wi_row_to_dict,
)


# ─────────────────────────────────────────────────────────────────────
# UUIDv7 generator
# ─────────────────────────────────────────────────────────────────────

class TestUuid7:
    """RFC 9562 UUIDv7 layout + time-sortability."""

    def test_returns_valid_uuid_string(self):
        s = _uuid7_str()
        # Should parse as a UUID
        parsed = uuid.UUID(s)
        assert str(parsed) == s

    def test_version_is_7(self):
        s = _uuid7_str()
        parsed = uuid.UUID(s)
        # The 13th hex char encodes the version nibble
        assert parsed.version == 7

    def test_variant_is_rfc_4122(self):
        s = _uuid7_str()
        parsed = uuid.UUID(s)
        # RFC 4122 variant — high bit set on the variant byte
        assert (parsed.int >> 62) & 0x3 == 0x2

    def test_string_form_is_36_chars_with_hyphens(self):
        s = _uuid7_str()
        assert len(s) == 36
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            s,
        )

    def test_monotonic_across_calls(self):
        """UUIDv7s minted in succession should sort time-ascending.

        We allow some loose tolerance because two calls inside the same ms
        only differ in the random bits — so we sample enough that at least
        one ms-boundary is crossed.
        """
        ids = [_uuid7_str() for _ in range(1000)]
        # First 13 hex chars encode the 48-bit timestamp + version nibble;
        # the first 12 (the timestamp itself, stripped of hyphens) must be
        # non-decreasing across the sample.
        def ts_hex(s: str) -> str:
            return s.replace("-", "")[:12]

        ts_seq = [ts_hex(s) for s in ids]
        assert ts_seq == sorted(ts_seq), "UUIDv7 timestamps must be monotonic"

    def test_uniqueness(self):
        ids = {_uuid7_str() for _ in range(10_000)}
        assert len(ids) == 10_000


# ─────────────────────────────────────────────────────────────────────
# is_available semantics — every store guards on unbound pool
# ─────────────────────────────────────────────────────────────────────

class TestIsAvailableGuards:
    @pytest.mark.asyncio
    async def test_agent_registry_unbound(self):
        store = AgentRegistryStore()
        assert store.is_available is False
        assert await store.upsert_agent(
            "x", agent_name="X", agent_version="1.0.0", owner_team="t"
        ) is False
        assert await store.get_agent("x") is None
        assert await store.list_agents() == []

    @pytest.mark.asyncio
    async def test_session_unbound(self):
        store = SessionStore()
        assert store.is_available is False
        assert await store.create_session(agent_id="x", tenant_id="t") is None
        assert await store.set_status("sid", "active") is False
        assert await store.update_domain_data("sid", {"k": "v"}) is False
        assert await store.archive_session("sid") is False
        assert await store.get_session("sid") is None
        assert await store.list_active_sessions() == []

    @pytest.mark.asyncio
    async def test_work_item_unbound(self):
        store = WorkItemStore()
        assert store.is_available is False
        assert await store.create_work_item(
            agent_id="x", session_id="s", kind="incident"
        ) is None
        assert await store.set_status("wid", "closed") is False
        assert await store.merge_kind_data("wid", {"k": "v"}) is False
        assert await store.merge_domain_data("wid", {"k": "v"}) is False
        assert await store.archive_work_item("wid") is False
        assert await store.get_work_item("wid") is None
        assert await store.list_pending_approvals() == []
        assert await store.list_by_session("sid") == []

    @pytest.mark.asyncio
    async def test_event_unbound(self):
        store = EventStore()
        assert store.is_available is False
        assert await store.append_event(
            session_id="s", agent_id="a", tenant_id="t", event_type="llm"
        ) is None
        assert await store.get_event("eid") is None
        assert await store.list_by_session("sid") == []
        assert await store.list_by_work_item("wid") == []
        assert await store.list_by_trace_id("tid") == []
        # Empty totals shape is well-defined even when unavailable
        totals = await store.get_session_token_totals("sid")
        assert totals == _empty_token_totals()


# ─────────────────────────────────────────────────────────────────────
# Validation guards
# ─────────────────────────────────────────────────────────────────────

class TestValidation:
    """Reject bad enum values at the app layer, before round-tripping a
    CHECK-constraint violation through Postgres."""

    def test_valid_kinds_match_migration(self):
        assert _VALID_KINDS == {"incident", "action", "approval", "decision"}

    def test_valid_priorities_match_migration(self):
        assert _VALID_PRIORITIES == {"p0", "p1", "p2", "p3", "p4"}

    def test_valid_event_types_match_migration(self):
        assert _VALID_EVENT_TYPES == {
            "dispatch", "llm", "tool", "api_call", "hitl", "state", "error",
        }

    @pytest.mark.asyncio
    async def test_work_item_rejects_bad_kind(self):
        store = WorkItemStore()
        store.bind_pool(_FakePool(fetchrow_return={"work_item_id": uuid.uuid4()}))
        with pytest.raises(ValueError, match="invalid work_item kind"):
            await store.create_work_item(
                agent_id="a", session_id="s", kind="garbage",
            )

    @pytest.mark.asyncio
    async def test_work_item_rejects_bad_priority(self):
        store = WorkItemStore()
        store.bind_pool(_FakePool(fetchrow_return={"work_item_id": uuid.uuid4()}))
        with pytest.raises(ValueError, match="invalid work_item priority"):
            await store.create_work_item(
                agent_id="a", session_id="s", kind="incident", priority="p9",
            )

    @pytest.mark.asyncio
    async def test_session_rejects_bad_status(self):
        store = SessionStore()
        store.bind_pool(_FakePool())
        with pytest.raises(ValueError, match="invalid session status"):
            await store.set_status("sid", "garbage")

    @pytest.mark.asyncio
    async def test_event_rejects_bad_event_type(self):
        store = EventStore()
        store.bind_pool(_FakePool(fetchrow_return={"event_id": uuid.uuid4()}))
        with pytest.raises(ValueError, match="invalid event_type"):
            await store.append_event(
                session_id="s", agent_id="a", tenant_id="t",
                event_type="garbage",
            )


# ─────────────────────────────────────────────────────────────────────
# _row_to_dict — JSONB parsing + UUID stringification
# ─────────────────────────────────────────────────────────────────────

class TestRowToDict:
    """asyncpg already gives JSONB as dict, but if a stringified JSONB
    sneaks through (Postgres returns it as text under some adapters) we
    must coerce it transparently."""

    def test_agent_parses_jsonb_string(self):
        d = _agent_row_to_dict({"agent_id": "x", "config": '{"a": 1}'})
        assert d["config"] == {"a": 1}

    def test_agent_handles_malformed_jsonb(self):
        d = _agent_row_to_dict({"agent_id": "x", "config": "not json"})
        assert d["config"] == {}

    def test_agent_passes_through_dict_jsonb(self):
        d = _agent_row_to_dict({"agent_id": "x", "config": {"a": 1}})
        assert d["config"] == {"a": 1}

    def test_session_stringifies_uuids(self):
        sid = uuid.uuid4()
        pid = uuid.uuid4()
        d = _session_row_to_dict({
            "session_id": sid,
            "parent_session_id": pid,
            "domain_data": '{"k": "v"}',
        })
        assert d["session_id"] == str(sid)
        assert d["parent_session_id"] == str(pid)
        assert d["domain_data"] == {"k": "v"}

    def test_session_tolerates_null_parent(self):
        d = _session_row_to_dict({
            "session_id": uuid.uuid4(),
            "parent_session_id": None,
            "domain_data": {},
        })
        assert d["parent_session_id"] is None

    def test_work_item_stringifies_all_uuids(self):
        wid, sid, pid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        d = _wi_row_to_dict({
            "work_item_id": wid,
            "session_id": sid,
            "parent_work_item_id": pid,
            "kind_data": '{"title": "t"}',
            "domain_data": '{"x": 1}',
        })
        assert d["work_item_id"] == str(wid)
        assert d["session_id"] == str(sid)
        assert d["parent_work_item_id"] == str(pid)
        assert d["kind_data"] == {"title": "t"}
        assert d["domain_data"] == {"x": 1}

    def test_event_parses_all_jsonb_cols(self):
        eid, sid, wid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        d = _event_row_to_dict({
            "event_id": eid,
            "session_id": sid,
            "work_item_id": wid,
            "parent_event_id": None,
            "input_messages": '[{"role":"user","content":"hi"}]',
            "output_message": '{"role":"assistant","content":"ok"}',
            "llm_metadata": '{"response_metadata":{"id":"abc"}}',
            "domain_data": '{"langgraph_node":"triage"}',
        })
        assert d["event_id"] == str(eid)
        assert d["session_id"] == str(sid)
        assert d["work_item_id"] == str(wid)
        assert d["parent_event_id"] is None
        assert d["input_messages"] == [{"role": "user", "content": "hi"}]
        assert d["output_message"] == {"role": "assistant", "content": "ok"}
        assert d["llm_metadata"] == {"response_metadata": {"id": "abc"}}
        assert d["domain_data"] == {"langgraph_node": "triage"}


# ─────────────────────────────────────────────────────────────────────
# Idempotency replay path
# ─────────────────────────────────────────────────────────────────────

class TestIdempotency:
    @pytest.mark.asyncio
    async def test_session_replay_returns_existing_id(self):
        existing = str(uuid.uuid4())
        pool = _FakePool(fetchrow_return={"session_id": uuid.UUID(existing)})
        store = SessionStore()
        store.bind_pool(pool)

        sid = await store.create_session(
            agent_id="a", tenant_id="t", idempotency_key="key-1"
        )
        assert sid == existing
        # No INSERT should have been issued
        assert pool.execute_calls == []

    @pytest.mark.asyncio
    async def test_session_idempotency_lookup_filters_by_agent_id(self):
        """``uq_session_idempotency`` is keyed on
        ``(agent_id, idempotency_key)`` — the lookup query must therefore
        filter on agent_id so two agents sharing the same idempotency
        key (e.g. ``snow-INC-1``) keep independent session spaces."""
        existing = str(uuid.uuid4())
        pool = _FakePool(fetchrow_return={"session_id": uuid.UUID(existing)})
        store = SessionStore()
        store.bind_pool(pool)

        await store.create_session(
            agent_id="agent-A",
            tenant_id="t",
            idempotency_key="snow-INC-1",
        )

        # The replay path issued exactly one SELECT and zero INSERTs.
        assert len(pool.fetchrow_calls) == 1
        assert pool.execute_calls == []
        sql, args = pool.fetchrow_calls[0]
        assert "agent_id = $1" in sql
        assert args == ("agent-A", "snow-INC-1")

    @pytest.mark.asyncio
    async def test_create_session_insert_columns(self):
        """The INSERT must populate the canonical session columns.  No
        ``pack_id`` slot exists on session anymore — run-state and
        pack identity live on the work_item row."""
        pool = _FakePool()
        store = SessionStore()
        store.bind_pool(pool)

        sid = await store.create_session(
            agent_id="agent-1",
            tenant_id="walmart-us",
        )
        assert sid is not None
        # non_guc_execute_calls filters out the SET-LOCAL set_config
        # call emitted by acquire_with_tenant so we only see the INSERT.
        assert len(pool.non_guc_execute_calls) == 1
        sql, args = pool.non_guc_execute_calls[0]
        # No pack_id column remains.
        assert "pack_id" not in sql
        # agent_id is $2 in the INSERT layout.
        assert args[1] == "agent-1"
        assert args[2] == "walmart-us"

    @pytest.mark.asyncio
    async def test_session_no_key_skips_lookup(self):
        pool = _FakePool()
        store = SessionStore()
        store.bind_pool(pool)

        sid = await store.create_session(agent_id="a", tenant_id="t")
        assert sid is not None
        # Exactly one INSERT (filter excludes the GUC set_config), no
        # lookup query.
        assert len(pool.non_guc_execute_calls) == 1
        assert pool.fetchrow_calls == []

    @pytest.mark.asyncio
    async def test_work_item_replay_returns_existing_id(self):
        existing = str(uuid.uuid4())
        pool = _FakePool(fetchrow_return={"work_item_id": uuid.UUID(existing)})
        store = WorkItemStore()
        store.bind_pool(pool)

        wid = await store.create_work_item(
            agent_id="a", session_id=str(uuid.uuid4()),
            kind="approval", idempotency_key="dup-key",
        )
        assert wid == existing


# ─────────────────────────────────────────────────────────────────────
# Approve/reject race-safety contract
# ─────────────────────────────────────────────────────────────────────

class TestApprovalAtomicity:
    """`approve()` / `reject()` must return None when the guarded UPDATE
    finds no row (i.e. status already non-pending) — that's how the bridge
    detects a duplicate Concord callback."""

    @pytest.mark.asyncio
    async def test_approve_returns_none_on_terminal_row(self):
        pool = _FakePool(fetchrow_return=None)  # UPDATE...RETURNING produced no row
        store = WorkItemStore()
        store.bind_pool(pool)

        result = await store.approve(
            str(uuid.uuid4()), approved_by="user@walmart.com",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_approve_returns_row_on_success(self):
        wid = uuid.uuid4()
        pool = _FakePool(fetchrow_return={
            "work_item_id": wid,
            "session_id": uuid.uuid4(),
            "parent_work_item_id": None,
            "status": "approved",
            "approved_by": "user@walmart.com",
            "kind_data": {"x": 1},
            "domain_data": {},
        })
        store = WorkItemStore()
        store.bind_pool(pool)

        result = await store.approve(
            str(wid),
            approved_by="user@walmart.com",
            resume_value={"choice": "go"},
        )
        assert result is not None
        assert result["status"] == "approved"
        assert result["work_item_id"] == str(wid)

    @pytest.mark.asyncio
    async def test_reject_returns_none_on_terminal_row(self):
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)
        result = await store.reject(
            str(uuid.uuid4()), rejected_by="user@walmart.com", reason="not safe",
        )
        assert result is None


# ─────────────────────────────────────────────────────────────────────
# Empty-state shapes
# ─────────────────────────────────────────────────────────────────────

class TestRecordInterruptGuard:
    """Regression: `record_interrupt` must include `kind = 'approval'`
    in the WHERE clause so it fails closed on non-approval rows."""

    @pytest.mark.asyncio
    async def test_kind_guard_in_sql(self):
        pool = _FakePool()
        # Mark the fake pool's execute return value as "0 rows matched"
        pool._conn._execute_return = "UPDATE 0"
        store = WorkItemStore()
        store.bind_pool(pool)

        ok = await store.record_interrupt(
            str(uuid.uuid4()),
            interrupt_checkpoint_ns="",
            interrupt_checkpoint_id="ckpt-1",
            interrupt_task_id="task-1",
            interrupt_idx=0,
        )
        # 0 rows matched → returns False
        assert ok is False
        # And the SQL must include the kind guard
        sql, _ = pool.execute_calls[0]
        assert "kind = 'approval'" in sql

    @pytest.mark.asyncio
    async def test_success_when_row_matches(self):
        pool = _FakePool()
        pool._conn._execute_return = "UPDATE 1"
        store = WorkItemStore()
        store.bind_pool(pool)
        ok = await store.record_interrupt(
            str(uuid.uuid4()),
            interrupt_checkpoint_ns="",
            interrupt_checkpoint_id="ckpt-1",
            interrupt_task_id="task-1",
            interrupt_idx=0,
        )
        assert ok is True


class TestRlsTenantForwarding:
    """Migration 009 added `WITH CHECK (tenant_id = <GUC>)` to session,
    work_item, and event policies.  Every store write that takes a
    `tenant_id` must therefore set `app.tenant_id` via the
    `acquire_with_tenant` helper before issuing its INSERT / UPDATE.

    These tests pin the helper's call shape at each store entry point by
    locating the `set_config('app.tenant_id', $1, true)` invocation in
    the recorded execute_calls and asserting the parameter value matches
    what the caller passed.
    """

    @staticmethod
    def _find_guc_call(execute_calls):
        for sql, args in execute_calls:
            if "set_config" in sql and "app.tenant_id" in sql:
                return sql, args
        return None, None

    @pytest.mark.asyncio
    async def test_session_create_forwards_tenant_id(self):
        pool = _FakePool()
        store = SessionStore()
        store.bind_pool(pool)
        await store.create_session(agent_id="a", tenant_id="walmart-us")
        sql, args = self._find_guc_call(pool.execute_calls)
        assert sql is not None, "create_session must SET LOCAL app.tenant_id"
        assert args == ("walmart-us",)

    @pytest.mark.asyncio
    async def test_event_append_forwards_tenant_id(self):
        pool = _FakePool(fetchrow_return={"next": 0, "event_id": uuid.uuid4()})
        store = EventStore()
        store.bind_pool(pool)
        await store.append_event(
            session_id="00000000-0000-7000-8000-000000000099",
            agent_id="a",
            tenant_id="walmart-eu",
            event_type="llm",
        )
        sql, args = self._find_guc_call(pool.execute_calls)
        assert sql is not None, "append_event must SET LOCAL app.tenant_id"
        assert args == ("walmart-eu",)

    @pytest.mark.asyncio
    async def test_work_item_create_forwards_tenant_id(self):
        pool = _FakePool(fetchrow_return={"work_item_id": uuid.uuid4()})
        store = WorkItemStore()
        store.bind_pool(pool)
        await store.create_work_item(
            agent_id="a",
            session_id=str(uuid.uuid4()),
            kind="approval",
            tenant_id="walmart-merchspace",
        )
        sql, args = self._find_guc_call(pool.execute_calls)
        assert sql is not None, "create_work_item must SET LOCAL app.tenant_id"
        assert args == ("walmart-merchspace",)

    @pytest.mark.asyncio
    async def test_work_item_approve_forwards_tenant_id(self):
        pool = _FakePool(fetchrow_return={
            "work_item_id": uuid.uuid4(),
            "session_id": uuid.uuid4(),
            "parent_work_item_id": None,
            "status": "approved",
            "kind_data": {},
            "domain_data": {},
        })
        store = WorkItemStore()
        store.bind_pool(pool)
        await store.approve(
            str(uuid.uuid4()),
            approved_by="u@walmart.com",
            tenant_id="walmart-merchspace",
        )
        sql, args = self._find_guc_call(pool.execute_calls)
        assert sql is not None, "approve must SET LOCAL app.tenant_id"
        assert args == ("walmart-merchspace",)

    @pytest.mark.asyncio
    async def test_work_item_reject_forwards_tenant_id(self):
        pool = _FakePool(fetchrow_return={
            "work_item_id": uuid.uuid4(),
            "session_id": uuid.uuid4(),
            "parent_work_item_id": None,
            "status": "rejected",
            "kind_data": {},
            "domain_data": {},
        })
        store = WorkItemStore()
        store.bind_pool(pool)
        await store.reject(
            str(uuid.uuid4()),
            rejected_by="u@walmart.com",
            reason="not safe",
            tenant_id="walmart-merchspace",
        )
        sql, args = self._find_guc_call(pool.execute_calls)
        assert sql is not None, "reject must SET LOCAL app.tenant_id"
        assert args == ("walmart-merchspace",)

    @pytest.mark.asyncio
    async def test_record_interrupt_forwards_tenant_id(self):
        pool = _FakePool()
        pool._conn._execute_return = "UPDATE 1"
        store = WorkItemStore()
        store.bind_pool(pool)
        await store.record_interrupt(
            str(uuid.uuid4()),
            interrupt_checkpoint_ns="",
            interrupt_checkpoint_id="ckpt-1",
            interrupt_task_id="task-1",
            interrupt_idx=0,
            tenant_id="walmart-merchspace",
        )
        sql, args = self._find_guc_call(pool.execute_calls)
        assert sql is not None, "record_interrupt must SET LOCAL app.tenant_id"
        assert args == ("walmart-merchspace",)

    @pytest.mark.asyncio
    async def test_write_methods_skip_guc_when_tenant_id_missing(self):
        """Explicit None / unset tenant_id must NOT issue a set_config —
        that's the migration-009 bypass branch for ops paths."""
        pool = _FakePool(fetchrow_return={"work_item_id": uuid.uuid4()})
        store = WorkItemStore()
        store.bind_pool(pool)
        await store.create_work_item(
            agent_id="a",
            session_id=str(uuid.uuid4()),
            kind="approval",
        )
        sql, _ = self._find_guc_call(pool.execute_calls)
        assert sql is None, (
            "missing tenant_id must NOT issue a set_config — the policy's "
            "GUC-unset bypass branch handles ops / admin paths"
        )


class TestFindPendingApprovalByExternalRef:
    """Concord callback bridge looks up the work_item by the incident
    number it already knows, not by the 4-col LangGraph interrupt key.
    The SQL must:

      • match `kind = 'approval'` and `status = 'pending'`
        (so duplicate callbacks return None instead of double-resolving)
      • match `archived_at IS NULL`
      • filter by `kind_data->>'external_ref'`
      • optionally narrow by `agent_id` for multi-pack deployments
      • order by `created_at DESC` so the most recent pending row wins
    """

    @pytest.mark.asyncio
    async def test_unbound_returns_none(self):
        store = WorkItemStore()
        assert await store.find_pending_approval_by_external_ref("INC123") is None

    @pytest.mark.asyncio
    async def test_returns_row_when_found(self):
        wid = uuid.uuid4()
        sid = uuid.uuid4()
        pool = _FakePool(fetchrow_return={
            "work_item_id": wid,
            "session_id": sid,
            "parent_work_item_id": None,
            "kind": "approval",
            "status": "pending",
            "kind_data": {"external_ref": "INC123"},
            "domain_data": {},
        })
        store = WorkItemStore()
        store.bind_pool(pool)

        row = await store.find_pending_approval_by_external_ref("INC123")
        assert row is not None
        assert row["work_item_id"] == str(wid)
        assert row["session_id"] == str(sid)

    @pytest.mark.asyncio
    async def test_sql_filters_kind_status_and_archived(self):
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_pending_approval_by_external_ref("INC999")
        assert len(pool.fetchrow_calls) == 1
        sql, args = pool.fetchrow_calls[0]
        assert "kind = 'approval'" in sql
        assert "status = 'pending'" in sql
        assert "archived_at IS NULL" in sql
        assert "kind_data->>'external_ref'" in sql
        # External ref is the first param
        assert args[0] == "INC999"

    @pytest.mark.asyncio
    async def test_agent_id_filter_narrows_query(self):
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_pending_approval_by_external_ref(
            "INC123", agent_id="gif_tote_validation",
        )
        sql, args = pool.fetchrow_calls[0]
        assert "agent_id =" in sql
        assert "gif_tote_validation" in args

    @pytest.mark.asyncio
    async def test_order_by_recent_first(self):
        """Defensive tie-breaker when two pending rows exist for the same
        external_ref — the most recent one wins so a duplicate from an
        earlier failed run doesn't shadow a fresh approval."""
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_pending_approval_by_external_ref("INC123")
        sql, _ = pool.fetchrow_calls[0]
        assert "ORDER BY created_at DESC" in sql
        assert "LIMIT 1" in sql


class TestFindByExternalRef:
    """Status-agnostic counterpart to ``find_pending_approval_by_external_ref``.

    Used for side-channel state that must survive the full approval
    lifecycle (e.g. Slack thread IDs persisted into
    ``kind_data.slack_thread`` — those must be recoverable on a cold
    start regardless of whether the approval is still pending,
    approved, or rejected).

    Contract:
      • match ``kind = 'approval'`` (still narrow to approval rows so
        a future ``kind='task'`` deployment can't clobber the lookup)
      • match ``archived_at IS NULL``
      • filter by ``kind_data->>'external_ref'``
      • NO ``status = 'pending'`` predicate — that's the whole point of
        this variant
      • optionally narrow by ``agent_id`` / ``pack_id`` for multi-pack
        deployments
      • order by ``created_at DESC`` so the most recent row wins
    """

    @pytest.mark.asyncio
    async def test_unbound_returns_none(self):
        store = WorkItemStore()
        assert await store.find_by_external_ref("INC123") is None

    @pytest.mark.asyncio
    async def test_returns_row_when_found(self):
        wid = uuid.uuid4()
        sid = uuid.uuid4()
        pool = _FakePool(fetchrow_return={
            "work_item_id": wid,
            "session_id": sid,
            "parent_work_item_id": None,
            "kind": "approval",
            "status": "approved",  # status-agnostic: approved rows must be found
            "kind_data": {
                "external_ref": "INC123",
                "slack_thread": {"channel_id": "C1", "ts": "1700.0"},
            },
            "domain_data": {},
        })
        store = WorkItemStore()
        store.bind_pool(pool)

        row = await store.find_by_external_ref("INC123")
        assert row is not None
        assert row["work_item_id"] == str(wid)
        # Verify the row carries the kind_data with slack_thread intact
        assert row["kind_data"]["slack_thread"]["channel_id"] == "C1"
        assert row["kind_data"]["slack_thread"]["ts"] == "1700.0"

    @pytest.mark.asyncio
    async def test_sql_omits_status_filter(self):
        """The whole point of this variant: no status predicate, so a
        rejected/approved row can still be located for side-channel
        state recovery (e.g. Slack thread hydration after restart)."""
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_by_external_ref("INC999")
        assert len(pool.fetchrow_calls) == 1
        sql, args = pool.fetchrow_calls[0]
        assert "kind = 'approval'" in sql
        assert "archived_at IS NULL" in sql
        assert "kind_data->>'external_ref'" in sql
        # Critical: no status='pending' restriction
        assert "status = 'pending'" not in sql
        assert args[0] == "INC999"

    @pytest.mark.asyncio
    async def test_agent_id_filter_narrows_query(self):
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_by_external_ref(
            "INC123", agent_id="gif_tote_validation",
        )
        sql, args = pool.fetchrow_calls[0]
        assert "agent_id =" in sql
        assert "gif_tote_validation" in args

    @pytest.mark.asyncio
    async def test_pack_id_filter_narrows_query(self):
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_by_external_ref("INC123", pack_id="pack-x")
        sql, args = pool.fetchrow_calls[0]
        assert "pack_id =" in sql
        assert "pack-x" in args

    @pytest.mark.asyncio
    async def test_order_by_recent_first(self):
        """If two non-archived rows share the same external_ref (e.g. a
        retry after a partial failure), the most recent one wins — so
        the latest slack_thread blob is what we recover."""
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_by_external_ref("INC123")
        sql, _ = pool.fetchrow_calls[0]
        assert "ORDER BY created_at DESC" in sql
        assert "LIMIT 1" in sql


# ─────────────────────────────────────────────────────────────────────
# pack_id isolation — migration 006
# ─────────────────────────────────────────────────────────────────────

class TestPackIdIsolation:
    """pack_id must flow into the INSERT, the external_ref lookup, and
    the interrupt-key lookup so two packs sharing an agent deployment
    can never resolve each other's approvals on a Concord callback."""

    @pytest.mark.asyncio
    async def test_create_work_item_stamps_pack_id(self):
        """`pack_id` is stamped in the INSERT slot right after `agent_id`."""
        wid = uuid.uuid4()
        pool = _FakePool(fetchrow_return={"work_item_id": wid})
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.create_work_item(
            agent_id="agent-a",
            pack_id="pack-x",
            session_id=str(uuid.uuid4()),
            kind="approval",
        )
        assert len(pool.fetchrow_calls) == 1
        sql, args = pool.fetchrow_calls[0]
        # Column list must mention pack_id immediately after agent_id
        assert "pack_id" in sql
        assert args[0] == "agent-a"
        assert args[1] == "pack-x"

    @pytest.mark.asyncio
    async def test_create_work_item_pack_id_defaults_to_agent_id(self):
        """Transitional fallback so existing callers don't break."""
        wid = uuid.uuid4()
        pool = _FakePool(fetchrow_return={"work_item_id": wid})
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.create_work_item(
            agent_id="agent-a",
            session_id=str(uuid.uuid4()),
            kind="approval",
        )
        _, args = pool.fetchrow_calls[0]
        # pack_id slot was filled with the agent_id value
        assert args[1] == "agent-a"

    @pytest.mark.asyncio
    async def test_find_pending_approval_pack_id_filter(self):
        """A pack_id predicate is appended when supplied — multi-pack
        deployments need this to keep INC namespaces disjoint."""
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_pending_approval_by_external_ref(
            "INC123", pack_id="pack-x",
        )
        sql, args = pool.fetchrow_calls[0]
        assert "pack_id =" in sql
        assert "pack-x" in args

    @pytest.mark.asyncio
    async def test_find_pending_approval_both_agent_and_pack(self):
        """Both filters compose — caller can scope by agent_id AND pack_id."""
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_pending_approval_by_external_ref(
            "INC123", agent_id="agent-a", pack_id="pack-x",
        )
        sql, args = pool.fetchrow_calls[0]
        assert "agent_id =" in sql
        assert "pack_id =" in sql
        assert "agent-a" in args
        assert "pack-x" in args

    @pytest.mark.asyncio
    async def test_find_by_interrupt_key_pack_id_filter(self):
        """pack_id is a defense-in-depth filter on the interrupt-key path."""
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_by_interrupt_key(
            session_id=str(uuid.uuid4()),
            interrupt_checkpoint_id="ckpt-1",
            interrupt_task_id="task-1",
            interrupt_idx=0,
            pack_id="pack-x",
        )
        sql, args = pool.fetchrow_calls[0]
        assert "pack_id =" in sql
        assert "pack-x" in args

    @pytest.mark.asyncio
    async def test_find_by_interrupt_key_no_pack_id_omits_filter(self):
        """When pack_id is omitted the SQL must NOT include the predicate."""
        pool = _FakePool(fetchrow_return=None)
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.find_by_interrupt_key(
            session_id=str(uuid.uuid4()),
            interrupt_checkpoint_id="ckpt-1",
            interrupt_task_id="task-1",
            interrupt_idx=0,
        )
        sql, _ = pool.fetchrow_calls[0]
        assert "pack_id" not in sql

    @pytest.mark.asyncio
    async def test_idempotency_lookup_scoped_by_pack(self):
        """The idempotency replay lookup must include pack_id so two packs
        sharing an agent_id can't match each other's keys."""
        existing = uuid.uuid4()
        pool = _FakePool(fetchrow_return={"work_item_id": existing})
        store = WorkItemStore()
        store.bind_pool(pool)

        await store.create_work_item(
            agent_id="agent-shared",
            pack_id="pack-x",
            session_id=str(uuid.uuid4()),
            kind="approval",
            idempotency_key="key-1",
        )
        # The first fetchrow IS the idempotency lookup
        sql, args = pool.fetchrow_calls[0]
        assert "agent_id = $1" in sql
        assert "pack_id = $2" in sql
        assert "idempotency_key = $3" in sql
        assert args == ("agent-shared", "pack-x", "key-1")


class TestSeqNumLock:
    """Regression: `_next_seq_num` must take pg_advisory_xact_lock to
    serialize concurrent appends to the same session."""

    @pytest.mark.asyncio
    async def test_advisory_lock_acquired(self):
        pool = _FakePool(fetchrow_return={"next": 0, "event_id": uuid.uuid4()})
        store = EventStore()
        store.bind_pool(pool)

        await store.append_event(
            session_id="00000000-0000-7000-8000-000000000099",
            agent_id="a",
            tenant_id="t",
            event_type="llm",
        )
        # Filtered list excludes the SET-LOCAL set_config emitted by
        # acquire_with_tenant.  After that filter the only execute() is
        # the pg_advisory_xact_lock; the seq fetch and INSERT are both
        # fetchrow.
        assert len(pool.non_guc_execute_calls) >= 1
        lock_sql, _ = pool.non_guc_execute_calls[0]
        assert "pg_advisory_xact_lock" in lock_sql
        assert "hashtext" in lock_sql

    @pytest.mark.asyncio
    async def test_lock_skipped_when_seq_num_explicit(self):
        """If caller provides seq_num, no need to lock — that's a
        single-writer path the caller manages."""
        pool = _FakePool(fetchrow_return={"event_id": uuid.uuid4()})
        store = EventStore()
        store.bind_pool(pool)
        await store.append_event(
            session_id="00000000-0000-7000-8000-000000000099",
            agent_id="a",
            tenant_id="t",
            event_type="llm",
            seq_num=42,
        )
        # Zero execute() calls past the GUC set_config — only the
        # INSERT fetchrow.
        assert pool.non_guc_execute_calls == []


class TestEmptyTotals:
    def test_empty_token_totals_has_all_five_cols(self):
        t = _empty_token_totals()
        assert set(t.keys()) == {
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_creation_tokens",
            "reasoning_tokens",
            "total_tokens",
            "llm_event_count",
        }
        assert all(v == 0 for v in t.values())


# ─────────────────────────────────────────────────────────────────────
# Test helpers — minimal asyncpg pool double
# ─────────────────────────────────────────────────────────────────────

class _FakeConn:
    """Records SQL calls + returns canned data — enough surface for the
    store methods we exercise (execute, fetchrow, fetch, transaction)."""

    def __init__(self, fetchrow_return=None, fetch_return=None):
        self._fetchrow_return = fetchrow_return
        self._fetch_return = fetch_return or []
        self._execute_return = "INSERT 0 1"
        self.execute_calls: list[tuple] = []
        self.fetchrow_calls: list[tuple] = []
        self.fetch_calls: list[tuple] = []

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))
        return self._execute_return

    async def fetchrow(self, sql, *args):
        self.fetchrow_calls.append((sql, args))
        return self._fetchrow_return

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        return self._fetch_return

    def transaction(self):
        return _FakeTxn()


class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    """Pool double — `async with pool.acquire() as conn` gives a _FakeConn
    that records every SQL call and serves up canned return values."""

    def __init__(self, fetchrow_return=None, fetch_return=None):
        self._conn = _FakeConn(
            fetchrow_return=fetchrow_return,
            fetch_return=fetch_return or [],
        )

    def acquire(self):
        return _FakeAcquireCtx(self._conn)

    # Convenience pass-throughs so tests can assert without reaching in
    @property
    def execute_calls(self) -> list[tuple]:
        return self._conn.execute_calls

    @property
    def non_guc_execute_calls(self) -> list[tuple]:
        """Filter out `SELECT set_config('app.tenant_id', ...)` calls so
        tests can assert against the store's real SQL without caring
        about the RLS GUC plumbing emitted by `acquire_with_tenant`."""
        return [
            (sql, args) for sql, args in self._conn.execute_calls
            if "set_config" not in sql
        ]

    @property
    def fetchrow_calls(self) -> list[tuple]:
        return self._conn.fetchrow_calls

    @property
    def fetch_calls(self) -> list[tuple]:
        return self._conn.fetch_calls


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False
