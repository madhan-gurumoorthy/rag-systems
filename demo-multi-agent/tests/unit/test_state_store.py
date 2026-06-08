"""Tests for `storage.state_store.PostgreSQLStateManager.get_session_messages`.

`get_session_messages` is the persistence-layer feeder for
`langchain_chat.run_chat`'s `chat_history` parameter — it powers
multi-turn chat memory.  These tests pin the production-relevant
contracts:

  • Returns `[]` when the manager has no pool bound (graceful fallback —
    chat must still work when Postgres is unavailable)
  • Returns `[]` when limit <= 0 (defensive against caller mistakes)
  • Issues a SELECT that filters to user/assistant rows for the given
    session, ordered DESC + LIMIT N, and reverses the result so the
    caller sees oldest → newest (the order LangChain expects)
  • Coerces `None` content to "" so downstream consumers never blow up
    on NULL columns
  • Normalises `created_at` to an ISO-8601 string regardless of whether
    asyncpg hands back a `datetime` or a plain string
  • Returns `[]` when the underlying query raises — chat continues with
    no history rather than 500-ing the request
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from storage.state_store import PostgreSQLStateManager


# ─────────────────────────────────────────────────────────────────────
# asyncpg pool double — same shape as test_storage_langgraph_model
# ─────────────────────────────────────────────────────────────────────


class _FakeConn:
    def __init__(self, fetch_return=None, raise_on_fetch=None):
        self._fetch_return = fetch_return or []
        self._raise_on_fetch = raise_on_fetch
        self.fetch_calls: list[tuple] = []

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        if self._raise_on_fetch is not None:
            raise self._raise_on_fetch
        return self._fetch_return


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, fetch_return=None, raise_on_fetch=None):
        self._conn = _FakeConn(
            fetch_return=fetch_return, raise_on_fetch=raise_on_fetch,
        )

    def acquire(self):
        return _FakeAcquireCtx(self._conn)

    @property
    def fetch_calls(self):
        return self._conn.fetch_calls


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_manager(*, pool=None, table_name="agent_conversation_state",
                  table_created=True):
    """Build a manager with a fake pool bound — bypasses initialize()."""
    mgr = PostgreSQLStateManager()
    mgr.pool = pool  # type: ignore[assignment]
    mgr.table_name = table_name
    mgr.table_created = table_created
    return mgr


# ─────────────────────────────────────────────────────────────────────
# Unavailable / defensive paths
# ─────────────────────────────────────────────────────────────────────


class TestGetSessionMessagesUnavailable:
    """Whenever the manager isn't available the call must short-circuit
    to `[]` — chat needs to keep working when Postgres is down."""

    def test_no_pool_returns_empty_list(self):
        mgr = PostgreSQLStateManager()
        result = _run(mgr.get_session_messages("sid"))
        assert result == []

    def test_pool_but_no_table_returns_empty_list(self):
        mgr = _make_manager(pool=_FakePool(), table_created=False)
        result = _run(mgr.get_session_messages("sid"))
        assert result == []

    def test_zero_limit_returns_empty_list_without_query(self):
        pool = _FakePool(fetch_return=[{"message_id": "x"}])
        mgr = _make_manager(pool=pool)
        result = _run(mgr.get_session_messages("sid", limit=0))
        assert result == []
        # No SQL should have been issued
        assert pool.fetch_calls == []

    def test_negative_limit_returns_empty_list_without_query(self):
        pool = _FakePool(fetch_return=[{"message_id": "x"}])
        mgr = _make_manager(pool=pool)
        result = _run(mgr.get_session_messages("sid", limit=-5))
        assert result == []
        assert pool.fetch_calls == []


# ─────────────────────────────────────────────────────────────────────
# Happy-path SQL composition + result shaping
# ─────────────────────────────────────────────────────────────────────


class TestGetSessionMessagesHappyPath:
    def test_empty_session_returns_empty_list(self):
        pool = _FakePool(fetch_return=[])
        mgr = _make_manager(pool=pool)
        result = _run(mgr.get_session_messages("sid"))
        assert result == []
        # Query still issued — operators want to see the trace span
        assert len(pool.fetch_calls) == 1

    def test_single_turn_returns_single_dict_oldest_first(self):
        rows = [
            {
                "message_id": "u1",
                "msg_type": "user",
                "content": "hello",
                "created_at": datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc),
            },
        ]
        pool = _FakePool(fetch_return=rows)
        mgr = _make_manager(pool=pool)
        result = _run(mgr.get_session_messages("sid"))
        assert len(result) == 1
        assert result[0]["msg_type"] == "user"
        assert result[0]["content"] == "hello"
        assert result[0]["message_id"] == "u1"
        # ISO-8601 string, not a datetime
        assert isinstance(result[0]["created_at"], str)
        assert "2026-05-11" in result[0]["created_at"]

    def test_multi_turn_returned_oldest_first(self):
        """The DB returns DESC; the method must reverse so callers get
        oldest → newest — that's what LangChain wants for chat_history."""
        # DB order is DESC: newest first, oldest last
        db_rows = [
            {
                "message_id": "a2",
                "msg_type": "assistant",
                "content": "newest assistant",
                "created_at": datetime(2026, 5, 11, 12, 3, tzinfo=timezone.utc),
            },
            {
                "message_id": "u2",
                "msg_type": "user",
                "content": "newest user",
                "created_at": datetime(2026, 5, 11, 12, 2, tzinfo=timezone.utc),
            },
            {
                "message_id": "a1",
                "msg_type": "assistant",
                "content": "old assistant",
                "created_at": datetime(2026, 5, 11, 12, 1, tzinfo=timezone.utc),
            },
            {
                "message_id": "u1",
                "msg_type": "user",
                "content": "old user",
                "created_at": datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
            },
        ]
        pool = _FakePool(fetch_return=db_rows)
        mgr = _make_manager(pool=pool)
        result = _run(mgr.get_session_messages("sid"))
        # Now oldest → newest
        assert [r["message_id"] for r in result] == ["u1", "a1", "u2", "a2"]
        assert [r["msg_type"] for r in result] == [
            "user", "assistant", "user", "assistant",
        ]

    def test_sql_filters_user_assistant_and_uses_limit(self):
        """Verify the WHERE clause and LIMIT parameter actually reach
        Postgres — protects against silent contract drift."""
        pool = _FakePool(fetch_return=[])
        mgr = _make_manager(pool=pool, table_name="my_agent_conversation_state")
        _run(mgr.get_session_messages("session-xyz", limit=7))

        assert len(pool.fetch_calls) == 1
        sql, args = pool.fetch_calls[0]
        # Filter clause
        assert "msg_type IN ('user', 'assistant')" in sql
        # Correct table name interpolated
        assert "my_agent_conversation_state" in sql
        # Args: (session_id, limit)
        assert args == ("session-xyz", 7)
        # DESC ordering so we can reverse() in Python
        assert "ORDER BY created_at DESC" in sql

    def test_null_content_coerced_to_empty_string(self):
        """asyncpg returns NULL content as None — must not propagate."""
        rows = [
            {
                "message_id": "u1",
                "msg_type": "user",
                "content": None,
                "created_at": datetime(2026, 5, 11, tzinfo=timezone.utc),
            },
        ]
        pool = _FakePool(fetch_return=rows)
        mgr = _make_manager(pool=pool)
        result = _run(mgr.get_session_messages("sid"))
        assert result[0]["content"] == ""

    def test_string_created_at_passes_through(self):
        """Some asyncpg paths return created_at as a str — handle that
        without calling .isoformat() on it."""
        rows = [
            {
                "message_id": "u1",
                "msg_type": "user",
                "content": "hi",
                "created_at": "2026-05-11T12:00:00+00:00",
            },
        ]
        pool = _FakePool(fetch_return=rows)
        mgr = _make_manager(pool=pool)
        result = _run(mgr.get_session_messages("sid"))
        assert result[0]["created_at"] == "2026-05-11T12:00:00+00:00"


# ─────────────────────────────────────────────────────────────────────
# Error path — query failure → empty list (no 500)
# ─────────────────────────────────────────────────────────────────────


class TestGetSessionMessagesErrorPath:
    def test_query_exception_swallowed_and_returns_empty(self):
        """Chat must keep working even if the history query blows up
        (e.g. transient connection loss).  We log + return [] so the
        next turn becomes a fresh single-turn exchange instead of a 500."""
        pool = _FakePool(raise_on_fetch=RuntimeError("connection reset"))
        mgr = _make_manager(pool=pool)
        result = _run(mgr.get_session_messages("sid"))
        assert result == []


# ─────────────────────────────────────────────────────────────────────
# initialize() — pool-only contract
# ─────────────────────────────────────────────────────────────────────
#
# ``initialize()`` brings up the asyncpg pool that the four canonical
# stores share via ``PostgreSQLStateManager.pool``.  It does not
# create or verify any per-agent ``{agent_name}_conversation_state``
# table — the canonical schema (agent_registry, session, work_item,
# event) has no such table.
#
# These tests pin the contract so a future regression cannot
# silently reintroduce a table-verification probe.


class TestInitializeNoTableVerification:
    """``initialize()`` returns True after pool creation alone — no table
    verification gate.  Downstream stores bind to ``mgr.pool`` directly."""

    def test_returns_true_when_pool_already_present(self):
        """Fast path: if a pool is already bound, initialize() is a no-op
        and returns True immediately — does not re-probe anything."""
        mgr = _make_manager(pool=_FakePool())
        # Clear table_name / table_created to prove they are NOT required
        mgr.table_name = None
        mgr.table_created = False
        result = _run(mgr.initialize(agent_name="any-agent"))
        assert result is True

    def test_pool_created_path_does_not_verify_table(self, monkeypatch):
        """Cold-start path: when no pool exists yet, initialize() creates
        the pool via asyncpg.create_pool, sets ``table_name`` (for any
        caller that inspects it), and returns True — it never issues a
        CREATE TABLE or SELECT-from-information_schema probe."""
        from storage import state_store as ss

        fake_pool = _FakePool()

        async def fake_create_pool(**kwargs):
            return fake_pool

        # Force the env-var branch with valid creds
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_USER", "u")
        monkeypatch.setenv("POSTGRES_PASSWORD", "p")
        monkeypatch.setenv("POSTGRES_DATABASE", "d")
        monkeypatch.setattr(ss.asyncpg, "create_pool", fake_create_pool)

        mgr = PostgreSQLStateManager()
        result = _run(mgr.initialize(agent_name="my-agent"))

        assert result is True
        # Pool got bound
        assert mgr.pool is fake_pool
        # table_name is recorded for any caller that inspects it
        assert mgr.table_name == "my_agent_conversation_state"
        # CRITICAL: no fetch / no execute calls issued — initialize does
        # not probe or create any table on the canonical schema
        assert fake_pool.fetch_calls == []

    def test_is_available_stays_false_after_initialize(self, monkeypatch):
        """``is_available()`` requires ``table_created=True``, which
        ``initialize()`` does not set.  That keeps the normalized-message
        write path a silent no-op until it is repointed at the
        canonical ``event`` table."""
        from storage import state_store as ss

        async def fake_create_pool(**kwargs):
            return _FakePool()

        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_USER", "u")
        monkeypatch.setenv("POSTGRES_PASSWORD", "p")
        monkeypatch.setenv("POSTGRES_DATABASE", "d")
        monkeypatch.setattr(ss.asyncpg, "create_pool", fake_create_pool)

        mgr = PostgreSQLStateManager()
        _run(mgr.initialize(agent_name="my-agent"))

        # Pool present, table_name set — but table_created stays False,
        # so is_available() returns False and ``insert_message`` etc.
        # short-circuit safely.
        assert mgr.pool is not None
        assert mgr.table_name == "my_agent_conversation_state"
        assert mgr.table_created is False
        assert mgr.is_available() is False

    def test_missing_credentials_returns_false_without_pool(self, monkeypatch):
        """If required env vars are missing, initialize() logs a warning
        and returns False — the manager stays in the unavailable state
        so downstream stores can fall back gracefully."""
        # Strip all required vars
        for key in ("POSTGRES_HOST", "POSTGRES_USER",
                    "POSTGRES_PASSWORD", "POSTGRES_DATABASE"):
            monkeypatch.delenv(key, raising=False)

        mgr = PostgreSQLStateManager()
        result = _run(mgr.initialize(agent_name="my-agent"))

        assert result is False
        assert mgr.pool is None
