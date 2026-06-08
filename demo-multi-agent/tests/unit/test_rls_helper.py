"""Unit tests for `storage._rls.acquire_with_tenant`.

The helper sits between every store write and asyncpg's pool.acquire so
the migration-009 tenant-scoped RLS policies see `app.tenant_id` set on
every transaction.  These tests pin its three invariants:

  1. Opens an explicit transaction (SET LOCAL would no-op otherwise).
  2. Writes the GUC via `set_config(name, value, true)` so the value
     resets at COMMIT / ROLLBACK and doesn't leak across pool acquires.
  3. Skips the GUC write entirely when tenant_id is empty / None — the
     migration-009 policy treats an unset GUC as a bypass for ops paths
     that don't have a tenant axis.

We don't reach across the public surface: store-level wiring is covered
by the existing tests in `test_storage_langgraph_model.py` (the
`non_guc_execute_calls` filter pins the GUC call's presence indirectly).
This file covers the helper itself in isolation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from storage._rls import acquire_with_tenant


# ─────────────────────────────────────────────────────────────────────
# Test fakes
# ─────────────────────────────────────────────────────────────────────


class _FakeTxn:
    """Tracks whether the transaction context manager fired so the test
    can pin that the helper actually opens (and closes) a tx."""

    def __init__(self):
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False


class _FakeConn:
    def __init__(self):
        self.execute_calls: list[tuple] = []
        self._txn = _FakeTxn()

    def transaction(self):
        return self._txn

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))
        return "SELECT 1"


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self):
        self.conn = _FakeConn()

    def acquire(self):
        return _FakeAcquireCtx(self.conn)


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────


class TestAcquireWithTenant:
    @pytest.mark.asyncio
    async def test_sets_guc_when_tenant_id_present(self):
        """Helper must write `app.tenant_id` so the migration-009 RLS
        policy can match it."""
        pool = _FakePool()
        async with acquire_with_tenant(pool, "walmart-merchspace") as conn:
            assert conn is pool.conn
        # Exactly one execute() — the GUC set.
        assert len(pool.conn.execute_calls) == 1
        sql, args = pool.conn.execute_calls[0]
        assert "set_config" in sql
        assert "app.tenant_id" in sql
        # is_local = true — must be a third arg of value `true` so the
        # GUC resets at commit / rollback.
        assert "true" in sql
        # Tenant value carried in $1 to keep it parameterised.
        assert args == ("walmart-merchspace",)

    @pytest.mark.asyncio
    async def test_opens_transaction(self):
        """`SET LOCAL` requires a tx; the helper must open one."""
        pool = _FakePool()
        async with acquire_with_tenant(pool, "t1") as _conn:
            pass
        assert pool.conn._txn.entered is True
        assert pool.conn._txn.exited is True

    @pytest.mark.asyncio
    async def test_skips_guc_when_tenant_id_none(self):
        """`None` tenant_id means an ops / migration / admin path —
        the GUC stays unset and the policy hits its bypass branch."""
        pool = _FakePool()
        async with acquire_with_tenant(pool, None) as _conn:
            pass
        # Still opens a tx (consistent contract) but issues no
        # set_config.  The policy will degrade to the bypass branch.
        assert pool.conn.execute_calls == []
        assert pool.conn._txn.entered is True

    @pytest.mark.asyncio
    async def test_skips_guc_when_tenant_id_empty_string(self):
        """An empty-string tenant_id is treated as ops/missing — same
        as None.  ``_resolve_tenant_id`` ensures app paths never pass
        empty strings; this branch protects the contract."""
        pool = _FakePool()
        async with acquire_with_tenant(pool, "") as _conn:
            pass
        assert pool.conn.execute_calls == []

    @pytest.mark.asyncio
    async def test_yields_inside_transaction(self):
        """The yielded connection MUST be inside the open tx so any
        writes the caller issues land under the GUC (and roll back
        atomically if the caller raises)."""
        pool = _FakePool()
        async with acquire_with_tenant(pool, "t1") as _conn:
            # txn must already be entered by the time the caller runs
            assert pool.conn._txn.entered is True
            # And not yet exited.
            assert pool.conn._txn.exited is False
        # On exit, txn closes.
        assert pool.conn._txn.exited is True


class TestMigration009PolicyShape:
    """Pin the SQL shape of the tenant-isolation policies so a future
    refactor that weakens them (e.g. drops the GUC-conditional bypass or
    the WITH CHECK clause) trips a unit test instead of slipping through.

    The policy shape was historically introduced in migration 009; once
    the per-step migrations were consolidated into ``storage/schema.sql``
    the fixture moved to read that file.  Class name preserved for git
    blame continuity."""

    @pytest.fixture
    def migration_sql(self) -> str:
        path = (
            Path(__file__).resolve().parents[2]
            / "storage"
            / "schema.sql"
        )
        return path.read_text()

    def test_drops_permissive_policies(self, migration_sql: str):
        for name in (
            "session_permissive",
            "work_item_permissive",
            "event_permissive",
        ):
            assert f"DROP POLICY IF EXISTS {name}" in migration_sql

    def test_creates_tenant_scoped_session_policy(self, migration_sql: str):
        assert "CREATE POLICY session_tenant_isolation ON session" in migration_sql

    def test_creates_tenant_scoped_work_item_policy(self, migration_sql: str):
        assert (
            "CREATE POLICY work_item_tenant_isolation ON work_item"
            in migration_sql
        )
        # work_item has no tenant_id column; isolation joins to session.
        assert "FROM session s" in migration_sql
        assert "s.tenant_id" in migration_sql

    def test_creates_tenant_scoped_event_policy(self, migration_sql: str):
        assert "CREATE POLICY event_tenant_isolation ON event" in migration_sql

    def test_guc_unset_bypass_present(self, migration_sql: str):
        """The leading `IS NULL OR` branch keeps ops / migrations from
        having to plumb a tenant_id.  Removing it would break
        superuser / migration paths — pin it explicitly."""
        # Both USING and WITH CHECK sides reference the GUC with the
        # NULL bypass.  Count must be at least 6 (3 policies × 2 sides).
        bypass_count = migration_sql.count(
            "current_setting('app.tenant_id', true) IS NULL"
        )
        assert bypass_count >= 6, (
            f"expected ≥6 GUC-unset bypass clauses (3 policies × 2 sides), "
            f"got {bypass_count}"
        )

    def test_with_check_present_on_each_policy(self, migration_sql: str):
        """A USING-only policy would let writes through that subsequent
        reads can't see — symmetric WITH CHECK is the contract."""
        # 3 policies × 1 WITH CHECK each = 3.
        assert migration_sql.count("WITH CHECK") >= 3
