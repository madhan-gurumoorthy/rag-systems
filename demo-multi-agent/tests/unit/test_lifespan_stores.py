"""Tests for `agent_factory.api.lifespan` — store-binding contract.

The FastAPI lifespan binds exactly four canonical stores to the
shared asyncpg pool:

    • work_item_store
    • event_store
    • agent_registry_store
    • session_store

``incident_store``, ``audit_store``, and ``slack_thread_store`` must
NEVER appear in the lifespan import block — they have no backing
tables in ``storage/schema.sql``.

These tests pin the contract by:

  1. Inspecting the module source for the four `bind_pool` callsites
     and asserting no forbidden store names appear.
  2. Source-asserting that the canonical four stores are imported.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.api import lifespan as lifespan_module


_LIFESPAN_SOURCE = Path(lifespan_module.__file__).read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
# Canonical 4 stores are imported + bound
# ─────────────────────────────────────────────────────────────────────


class TestLifespanBindsExactly4Stores:
    """Pin the exact set of stores that lifespan binds — no more, no less."""

    def test_imports_only_the_four_canonical_stores(self):
        """Lifespan imports exactly these four stores at module level."""
        expected_imports = [
            "from storage.work_item_store import work_item_store",
            "from storage.event_store import event_store",
            "from storage.agent_registry_store import agent_registry_store",
            "from storage.session_store import session_store",
        ]
        for imp in expected_imports:
            assert imp in _LIFESPAN_SOURCE, (
                f"Expected import missing from lifespan.py: {imp!r}"
            )

    def test_binds_pool_on_exactly_four_stores(self):
        """Each canonical store gets exactly one ``bind_pool(...)`` call.
        Count is verified to lock in the 4-store invariant."""
        bind_calls = [
            "work_item_store.bind_pool(postgres_state_manager.pool)",
            "event_store.bind_pool(postgres_state_manager.pool)",
            "agent_registry_store.bind_pool(postgres_state_manager.pool)",
            "session_store.bind_pool(postgres_state_manager.pool)",
        ]
        for call in bind_calls:
            assert call in _LIFESPAN_SOURCE, (
                f"Expected bind_pool call missing from lifespan.py: {call!r}"
            )

        # Hard cap: total bind_pool callsites in the module is 4 — guards
        # against accidental re-introduction of a 5th store.
        assert _LIFESPAN_SOURCE.count(".bind_pool(") == 4, (
            "lifespan.py should call .bind_pool(...) on exactly 4 stores."
        )

    def test_does_not_reference_forbidden_stores(self):
        """The three non-canonical stores must not be referenced
        anywhere in lifespan.py — they have no backing tables in the
        canonical schema."""
        for forbidden in ("incident_store", "audit_store", "slack_thread_store"):
            assert forbidden not in _LIFESPAN_SOURCE, (
                f"lifespan.py must not reference {forbidden!r}; it has "
                "no backing table in the canonical schema."
            )

    def test_lifespan_module_exposes_four_store_symbols_only(self):
        """The four canonical store symbols are attributes of the module
        (imported at module scope).  None of the forbidden three are."""
        for canonical in (
            "work_item_store",
            "event_store",
            "agent_registry_store",
            "session_store",
        ):
            assert hasattr(lifespan_module, canonical), (
                f"lifespan module is missing canonical store: {canonical!r}"
            )
        for forbidden in ("incident_store", "audit_store", "slack_thread_store"):
            assert not hasattr(lifespan_module, forbidden), (
                f"lifespan module unexpectedly exposes forbidden store: {forbidden!r}"
            )
