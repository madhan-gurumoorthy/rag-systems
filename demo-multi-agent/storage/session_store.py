"""Session storage — one row per LangGraph thread.

A session represents a long-lived conversation thread.  In chat
integrations (Slack, Teams, SMS) one thread can carry many distinct
work-item requests over its lifetime, so per-run state — deadlines,
payloads, current pipeline status — lives on ``work_item``, not here.
This module owns only the thread-level identity, lineage, and the
``domain_data`` side-channel.

The ``session_id`` is identical to ``langgraph.thread_id``.  The bridge
is logical (no FK across schemas) but the IDs match, so any session row
joins 1:1 with the LangGraph checkpoint tables on ``thread_id``.

UUIDv7 is generated at the application layer (``_uuid7_str()`` below).

Uses the shared asyncpg pool from ``state_store.postgres_state_manager``.
"""
from __future__ import annotations

import json
import os
import time
import traceback
import uuid
from typing import Any, Optional

try:
    from agent_factory.common.logging import get_logger
    logger = get_logger("storage.session")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("storage.session")

from storage._rls import acquire_with_tenant
from storage.models import SessionRow

_TABLE = "session"


# ── UUIDv7 generator ────────────────────────────────────────────────
# Postgres 16 has no native UUIDv7. Generate at the app layer.
# Layout: 48 bits ms timestamp | 4 bits version (7) | 12 bits rand_a |
#         2 bits variant | 62 bits rand_b
#
# Collision analysis: within the same millisecond, two calls collide only
# if all 74 random bits (rand_a 12 + rand_b 62) match — birthday-bound at
# ~2^37 calls/ms.  At our peak rate (~10 sessions/sec/instance) real-world
# collision probability is effectively zero.  If we ever batch-create
# sessions in a hot loop, swap to a monotonic-counter variant (RFC 9562
# §6.2 method 1) so even same-ms calls stay strictly ordered.
def _uuid7_str() -> str:
    """Return a new UUIDv7 string. Sortable by time, globally unique."""
    ts_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF      # 48 bits
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF  # 12 bits
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF  # 62 bits
    uuid_int = (
        (ts_ms << 80)
        | (0x7 << 76)
        | (rand_a << 64)
        | (0x2 << 62)
        | rand_b
    )
    return str(uuid.UUID(int=uuid_int))


class SessionStore:
    """Manages the session table — one row per LangGraph thread."""

    def __init__(self):
        self._pool = None

    def bind_pool(self, pool) -> None:
        """Bind an existing asyncpg pool (from postgres_state_manager)."""
        self._pool = pool

    @property
    def is_available(self) -> bool:
        return self._pool is not None

    # ── Write operations ─────────────────────────────────────────────

    async def create_session(
        self,
        *,
        agent_id: str,
        tenant_id: str,
        session_id: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        domain_data: Optional[dict] = None,
        status: str = "active",
    ) -> Optional[str]:
        """Insert a new session row.

        Returns the session_id (UUIDv7 string) on success, or None on
        failure.

        If ``idempotency_key`` is set and an existing row matches
        ``(agent_id, idempotency_key)``, returns the EXISTING session_id
        instead of creating a duplicate — this is the contract for
        replay safety.  Per-work-item replay safety lives on
        ``work_item`` (keyed on ``(pack_id, external_ref)``); the
        session layer guards only thread-level identity.
        """
        if not self.is_available:
            return None

        # Idempotent replay path — scoped by (agent_id, idempotency_key)
        # to match the rescoped ``uq_session_idempotency`` index.
        if idempotency_key:
            existing = await self._find_by_idempotency_key(
                agent_id, idempotency_key,
            )
            if existing:
                logger.info(
                    f"session replay matched idempotency_key: "
                    f"agent={agent_id} key={idempotency_key} → {existing}"
                )
                return existing

        sid = session_id or _uuid7_str()
        domain_json = json.dumps(domain_data or {}, default=str)

        try:
            # Acquire inside an explicit transaction so the
            # ``session_tenant_isolation`` RLS policy sees
            # ``app.tenant_id`` set for the INSERT's WITH CHECK
            # predicate.  Without this the INSERT silently violates RLS
            # and asyncpg raises "new row violates row-level security
            # policy".
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {_TABLE}
                        (session_id, agent_id, tenant_id,
                         parent_session_id, status, trace_id,
                         idempotency_key, domain_data, started_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, NOW())
                    """,
                    sid, agent_id, tenant_id,
                    parent_session_id, status, trace_id,
                    idempotency_key, domain_json,
                )
            logger.info(
                f"session created: {sid} agent={agent_id} tenant={tenant_id}"
            )
            return sid
        except Exception as e:
            logger.error(f"create_session failed: {e}")
            logger.debug(traceback.format_exc())
            return None

    async def set_status(
        self,
        session_id: str,
        status: str,
        *,
        end: bool = False,
    ) -> bool:
        """Update session.status. If `end=True`, also stamp ended_at = NOW()."""
        if not self.is_available:
            return False
        if status not in ("active", "paused", "completed", "failed"):
            raise ValueError(f"invalid session status: {status}")
        try:
            async with self._pool.acquire() as conn:
                if end:
                    await conn.execute(
                        f"UPDATE {_TABLE} SET status = $2, ended_at = NOW() "
                        f"WHERE session_id = $1::uuid",
                        session_id, status,
                    )
                else:
                    await conn.execute(
                        f"UPDATE {_TABLE} SET status = $2 WHERE session_id = $1::uuid",
                        session_id, status,
                    )
            return True
        except Exception as e:
            logger.error(f"set_status failed: {e}")
            return False

    async def update_domain_data(
        self,
        session_id: str,
        patch: dict,
    ) -> bool:
        """Merge a patch into domain_data (JSONB concat semantics)."""
        if not self.is_available or not patch:
            return False
        try:
            patch_json = json.dumps(patch, default=str)
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"UPDATE {_TABLE} "
                    f"SET domain_data = domain_data || $2::jsonb "
                    f"WHERE session_id = $1::uuid",
                    session_id, patch_json,
                )
            return True
        except Exception as e:
            logger.error(f"update_domain_data failed: {e}")
            return False

    async def archive_session(self, session_id: str) -> bool:
        """Set archived_at = NOW() — gates the BQ-roll-up DELETE sweep."""
        if not self.is_available:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"UPDATE {_TABLE} SET archived_at = NOW() "
                    f"WHERE session_id = $1::uuid AND archived_at IS NULL",
                    session_id,
                )
            return True
        except Exception as e:
            logger.error(f"archive_session failed: {e}")
            return False

    # ── Read operations ──────────────────────────────────────────────

    async def get_session(self, session_id: str) -> Optional[SessionRow]:
        """Fetch a single session row."""
        if not self.is_available:
            return None
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT * FROM {_TABLE} WHERE session_id = $1::uuid",
                    session_id,
                )
            return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"get_session failed: {e}")
            return None

    async def list_active_sessions(
        self,
        *,
        agent_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[SessionRow]:
        """List non-archived sessions, optionally filtered."""
        if not self.is_available:
            return []
        try:
            clauses = ["archived_at IS NULL"]
            params: list[Any] = []
            if agent_id:
                params.append(agent_id)
                clauses.append(f"agent_id = ${len(params)}")
            if tenant_id:
                params.append(tenant_id)
                clauses.append(f"tenant_id = ${len(params)}")
            params.append(limit)
            where = " AND ".join(clauses)
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    f"SELECT * FROM {_TABLE} WHERE {where} "
                    f"ORDER BY started_at DESC LIMIT ${len(params)}",
                    *params,
                )
            return [_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"list_active_sessions failed: {e}")
            return []

    # ── Internals ────────────────────────────────────────────────────

    async def _find_by_idempotency_key(
        self,
        agent_id: str,
        idempotency_key: str,
    ) -> Optional[str]:
        """Idempotency lookup — returns existing session_id or None.

        Scoped by ``(agent_id, idempotency_key)`` to match the
        ``uq_session_idempotency`` unique index.
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT session_id FROM {_TABLE} "
                    f"WHERE agent_id = $1 AND idempotency_key = $2",
                    agent_id, idempotency_key,
                )
            return str(row["session_id"]) if row else None
        except Exception as e:
            logger.error(f"_find_by_idempotency_key failed: {e}")
            return None


def _row_to_dict(row) -> SessionRow:
    """Coerce asyncpg Record → ``SessionRow``; parse JSONB; stringify UUIDs."""
    d = dict(row)
    for k in ("session_id", "parent_session_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    raw = d.get("domain_data")
    if isinstance(raw, str):
        try:
            d["domain_data"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            d["domain_data"] = {}
    return SessionRow.model_validate(d)


# Global singleton (exported)
session_store = SessionStore()

__all__ = ["SessionStore", "session_store", "SessionRow", "_uuid7_str"]
