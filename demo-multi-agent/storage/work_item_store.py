"""Work item storage — polymorphic incident / action / approval / decision.

A `work_item` is the durable, agent-facing record of something the graph is
doing or waiting on.  `kind` is the discriminator; sparse kind-specific fields
live in `kind_data` (JSONB) per ADR-013.

The 4-col LangGraph interrupt composite key
    (interrupt_checkpoint_ns, interrupt_checkpoint_id,
     interrupt_task_id, interrupt_idx)
is stamped on `kind='approval'` rows when the graph reaches an interrupt.  The
Concord callback bridge calls `find_by_interrupt_key()` to look the row up,
then `approve()` / `reject()` atomically transitions status with a guarded
UPDATE so a duplicate callback can never double-resume.

Uses the shared asyncpg pool from `state_store.postgres_state_manager`.

Part of the new LangGraph-native data model (migration 005).
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from typing import Any, Optional


def _now_utc() -> datetime:
    """Return the current UTC time as a tz-aware ``datetime``."""
    return datetime.now(timezone.utc)

try:
    from agent_factory.common.logging import get_logger
    logger = get_logger("storage.work_item")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("storage.work_item")

from storage._rls import acquire_with_tenant
from storage.models import WorkItemRow

_TABLE = "work_item"

# Allowed kinds — matches the CHECK constraint in migration 005.
_VALID_KINDS = {"incident", "action", "approval", "decision"}

# Allowed priorities — matches the CHECK constraint in migration 005.
_VALID_PRIORITIES = {"p0", "p1", "p2", "p3", "p4"}

# Run-state vocabulary for the work-item 3-minute response contract.  These
# values are a subset of the open-ended ``status`` column — the same row may
# also carry approval-domain statuses (``pending``, ``approved``, ``rejected``)
# when ``kind = 'approval'``.  Validated at the Python boundary because the
# ``status`` column has no DB CHECK.
_VALID_RUN_STATES = frozenset({"running", "awaiting_approval", "done", "failed"})
_TERMINAL_RUN_STATES = frozenset({"done", "failed"})
# Statuses meaning "a run is currently in flight" — the cached-running path
# returns immediately for these (when not stale).
_IN_FLIGHT_RUN_STATES = frozenset({"running", "awaiting_approval"})
# Statuses the start guard treats as "OK to (re-)start" — NULL (no row),
# terminal, or stale ``running`` count; the explicit values are kept for
# defence-in-depth on the SQL CASE.
_STARTABLE_RUN_STATES = frozenset({"pending", "done", "failed"})


class WorkItemStore:
    """Manages the work_item table — polymorphic via kind discriminator."""

    def __init__(self):
        self._pool = None

    def bind_pool(self, pool) -> None:
        """Bind an existing asyncpg pool (from postgres_state_manager)."""
        self._pool = pool

    @property
    def is_available(self) -> bool:
        return self._pool is not None

    # ── Write operations ─────────────────────────────────────────────

    async def create_work_item(
        self,
        *,
        agent_id: str,
        session_id: str,
        kind: str,
        pack_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        kind_data: Optional[dict] = None,
        parent_work_item_id: Optional[str] = None,
        status: str = "pending",
        priority: str = "p3",
        idempotency_key: Optional[str] = None,
        assignee: Optional[str] = None,
        expires_at: Optional[Any] = None,        # datetime or ISO string
        domain_data: Optional[dict] = None,
    ) -> Optional[str]:
        """Insert a new work_item row.

        Returns the work_item_id (UUIDv4 string) on success, or None on failure.

        If `idempotency_key` is set and an existing row matches (agent_id,
        idempotency_key), returns the EXISTING work_item_id — contract for
        replay safety.

        Validates `kind` and `priority` against the CHECK constraints in
        migration 005 so we fail fast on the app side instead of round-tripping
        a constraint violation.

        `pack_id` falls back to `agent_id` when omitted so existing call sites
        keep working after migration 006 adds the NOT NULL column.  In a
        multi-pack future every caller should pass it explicitly; the
        fallback is a transitional convenience.

        `tenant_id` is the tenant axis the row's session belongs to.  The
        migration-009 `work_item_tenant_isolation` policy consults
        `current_setting('app.tenant_id', true)` and joins to session to
        validate INSERT/UPDATE.  Without the GUC set, the policy degrades
        to the unset-GUC bypass; production callers should always pass it.
        """
        if not self.is_available:
            return None
        if kind not in _VALID_KINDS:
            raise ValueError(f"invalid work_item kind: {kind!r}")
        if priority not in _VALID_PRIORITIES:
            raise ValueError(f"invalid work_item priority: {priority!r}")

        # Transitional default — once every caller passes pack_id explicitly
        # we can drop this and make the parameter required.
        effective_pack_id = pack_id or agent_id

        # Idempotent replay path — scoped by pack_id so two packs sharing
        # an agent_id can't collide on the same idempotency_key.
        if idempotency_key:
            existing = await self._find_by_idempotency_key(
                agent_id, effective_pack_id, idempotency_key,
            )
            if existing:
                logger.info(
                    f"work_item replay matched idempotency_key: "
                    f"agent={agent_id} pack={effective_pack_id} "
                    f"key={idempotency_key} → {existing}"
                )
                return existing

        kind_json = json.dumps(kind_data or {}, default=str)
        domain_json = json.dumps(domain_data or {}, default=str)

        try:
            # `acquire_with_tenant` wraps the connection in a transaction
            # and writes `app.tenant_id` via SET LOCAL so the
            # migration-009 `work_item_tenant_isolation` policy passes
            # on the WITH CHECK side of this INSERT.
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                row = await conn.fetchrow(
                    f"""
                    INSERT INTO {_TABLE}
                        (agent_id, pack_id, session_id, parent_work_item_id, kind, status,
                         priority, idempotency_key, assignee, expires_at,
                         kind_data, domain_data)
                    VALUES ($1, $2, $3::uuid, $4::uuid, $5, $6,
                            $7, $8, $9, $10,
                            $11::jsonb, $12::jsonb)
                    RETURNING work_item_id
                    """,
                    agent_id, effective_pack_id, session_id, parent_work_item_id, kind, status,
                    priority, idempotency_key, assignee, expires_at,
                    kind_json, domain_json,
                )
            wid = str(row["work_item_id"]) if row else None
            logger.info(
                f"work_item created: {wid} kind={kind} session={session_id} "
                f"agent={agent_id} pack={effective_pack_id}"
            )
            return wid
        except Exception as e:
            logger.error(f"create_work_item failed: {e}")
            logger.debug(traceback.format_exc())
            return None

    async def record_interrupt(
        self,
        work_item_id: str,
        *,
        interrupt_checkpoint_ns: str,
        interrupt_checkpoint_id: str,
        interrupt_task_id: str,
        interrupt_idx: int,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """Stamp the 4-col LangGraph interrupt composite key on an approval row.

        Called by the graph's pre_interrupt hook so the Concord callback can
        later look the row up and resume the graph via `Command(resume=...)`.

        Guarded by `kind = 'approval'` to fail closed if a caller passes a
        non-approval work_item by mistake — the UPDATE will match zero rows
        and we return False.

        `tenant_id` (optional) is forwarded to `acquire_with_tenant` so the
        migration-009 RLS policy passes on UPDATE.
        """
        if not self.is_available:
            return False
        try:
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                result = await conn.execute(
                    f"""
                    UPDATE {_TABLE} SET
                        interrupt_checkpoint_ns = $2,
                        interrupt_checkpoint_id = $3,
                        interrupt_task_id       = $4,
                        interrupt_idx           = $5
                    WHERE work_item_id = $1::uuid
                      AND kind = 'approval'
                    """,
                    work_item_id,
                    interrupt_checkpoint_ns,
                    interrupt_checkpoint_id,
                    interrupt_task_id,
                    interrupt_idx,
                )
            # asyncpg returns "UPDATE <n>"; if n=0 the guard rejected it.
            if isinstance(result, str) and result.endswith(" 0"):
                logger.warning(
                    f"record_interrupt matched 0 rows "
                    f"(work_item not found or wrong kind): {work_item_id}"
                )
                return False
            return True
        except Exception as e:
            logger.error(f"record_interrupt failed: {e}")
            return False

    async def approve(
        self,
        work_item_id: str,
        *,
        approved_by: str,
        resume_value: Optional[dict] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[WorkItemRow]:
        """Atomically transition an approval work_item from pending → approved.

        Uses `WHERE status = 'pending' RETURNING *` so a duplicate Concord
        callback can never double-resume the graph: only the first call wins
        and returns the row, subsequent calls return None.

        If `resume_value` is provided, it's merged into `kind_data.resume_value`
        so the bridge can fetch it when constructing `Command(resume=...)`.

        `tenant_id` (optional) is forwarded to `acquire_with_tenant` so the
        migration-009 RLS policy passes on UPDATE.
        """
        if not self.is_available:
            return None
        try:
            patch = {"resume_value": resume_value} if resume_value is not None else {}
            patch_json = json.dumps(patch, default=str)
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                row = await conn.fetchrow(
                    f"""
                    UPDATE {_TABLE} SET
                        status      = 'approved',
                        approved_by = $2,
                        approved_at = NOW(),
                        kind_data   = kind_data || $3::jsonb
                    WHERE work_item_id = $1::uuid
                      AND kind = 'approval'
                      AND status = 'pending'
                    RETURNING *
                    """,
                    work_item_id, approved_by, patch_json,
                )
            if row is None:
                logger.warning(
                    f"approve no-op (already terminal or not approval): {work_item_id}"
                )
                return None
            logger.info(f"work_item approved: {work_item_id} by={approved_by}")
            return _row_to_dict(row)
        except Exception as e:
            logger.error(f"approve failed: {e}")
            logger.debug(traceback.format_exc())
            return None

    async def reject(
        self,
        work_item_id: str,
        *,
        rejected_by: str,
        reason: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[WorkItemRow]:
        """Atomically transition an approval work_item from pending → rejected.

        Same race-safe contract as `approve()` — guarded by `status='pending'`.
        Rejection reason (if provided) is merged into `kind_data.reject_reason`.

        `tenant_id` (optional) is forwarded to `acquire_with_tenant` so the
        migration-009 RLS policy passes on UPDATE.
        """
        if not self.is_available:
            return None
        try:
            patch = {"reject_reason": reason} if reason else {}
            patch_json = json.dumps(patch, default=str)
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                row = await conn.fetchrow(
                    f"""
                    UPDATE {_TABLE} SET
                        status      = 'rejected',
                        approved_by = $2,
                        approved_at = NOW(),
                        kind_data   = kind_data || $3::jsonb
                    WHERE work_item_id = $1::uuid
                      AND kind = 'approval'
                      AND status = 'pending'
                    RETURNING *
                    """,
                    work_item_id, rejected_by, patch_json,
                )
            if row is None:
                logger.warning(
                    f"reject no-op (already terminal or not approval): {work_item_id}"
                )
                return None
            logger.info(f"work_item rejected: {work_item_id} by={rejected_by}")
            return _row_to_dict(row)
        except Exception as e:
            logger.error(f"reject failed: {e}")
            logger.debug(traceback.format_exc())
            return None

    async def set_status(
        self,
        work_item_id: str,
        status: str,
        *,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """Generic status transition for non-approval kinds (incident/action/decision).

        Does NOT guard against terminal states — callers must enforce their
        own state machine.  For approvals, use `approve()` / `reject()` which
        are race-safe.

        `tenant_id` (optional) is forwarded to `acquire_with_tenant` so the
        migration-009 RLS policy passes on UPDATE.
        """
        if not self.is_available:
            return False
        try:
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                await conn.execute(
                    f"UPDATE {_TABLE} SET status = $2 WHERE work_item_id = $1::uuid",
                    work_item_id, status,
                )
            return True
        except Exception as e:
            logger.error(f"set_status failed: {e}")
            return False

    async def merge_kind_data(
        self,
        work_item_id: str,
        patch: dict,
        *,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """Merge a patch into kind_data (JSONB concat semantics).

        `tenant_id` (optional) is forwarded to `acquire_with_tenant` so the
        migration-009 RLS policy passes on UPDATE.
        """
        if not self.is_available or not patch:
            return False
        try:
            patch_json = json.dumps(patch, default=str)
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                await conn.execute(
                    f"UPDATE {_TABLE} "
                    f"SET kind_data = kind_data || $2::jsonb "
                    f"WHERE work_item_id = $1::uuid",
                    work_item_id, patch_json,
                )
            return True
        except Exception as e:
            logger.error(f"merge_kind_data failed: {e}")
            return False

    async def merge_domain_data(
        self,
        work_item_id: str,
        patch: dict,
        *,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """Merge a patch into domain_data (JSONB concat semantics).

        `tenant_id` (optional) is forwarded to `acquire_with_tenant` so the
        migration-009 RLS policy passes on UPDATE.
        """
        if not self.is_available or not patch:
            return False
        try:
            patch_json = json.dumps(patch, default=str)
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                await conn.execute(
                    f"UPDATE {_TABLE} "
                    f"SET domain_data = domain_data || $2::jsonb "
                    f"WHERE work_item_id = $1::uuid",
                    work_item_id, patch_json,
                )
            return True
        except Exception as e:
            logger.error(f"merge_domain_data failed: {e}")
            return False

    async def archive_work_item(
        self,
        work_item_id: str,
        *,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """Set archived_at = NOW() — gates the BQ-roll-up DELETE sweep.

        `tenant_id` (optional) is forwarded to `acquire_with_tenant` so the
        migration-009 RLS policy passes on UPDATE.
        """
        if not self.is_available:
            return False
        try:
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                await conn.execute(
                    f"UPDATE {_TABLE} SET archived_at = NOW() "
                    f"WHERE work_item_id = $1::uuid AND archived_at IS NULL",
                    work_item_id,
                )
            return True
        except Exception as e:
            logger.error(f"archive_work_item failed: {e}")
            return False

    # ── Run-state (3-minute response contract) ───────────────────────
    #
    # The work-item route owns identity at the (pack_id, external_ref)
    # layer.  Each POST corresponds to exactly one work_item row; the
    # row is **mutated in place** as the run progresses, so the same
    # work_item_id outlives terminal transitions and re-runs.

    async def start_work_item_run(
        self,
        *,
        pack_id: str,
        external_ref: str,
        agent_id: str,
        session_id: str,
        tenant_id: str,
        budget_seconds: float,
        payload: Optional[dict] = None,
        kind: str = "incident",
        priority: str = "p3",
    ) -> Optional[dict]:
        """Find-or-create + atomic start for a run keyed on
        ``(pack_id, external_ref)``.

        Resolution table — for the existing row's ``status``:

          * NULL (no row)                  → INSERT new row in ``running``
          * ``pending``                    → UPDATE to ``running``
          * ``done`` / ``failed``          → UPDATE to ``running`` (re-run)
          * ``running`` with stale deadline → UPDATE to ``running`` (recovery)
          * ``running`` (non-stale)        → REJECT, return ``None``
          * ``awaiting_approval``          → REJECT, return ``None``

        Race safety: holds ``pg_advisory_xact_lock(hash(pack_id),
        hash(external_ref))`` for the duration of the find-then-modify,
        so two concurrent callers serialise on the key and exactly one
        wins.  The reject path is also race-safe — the loser sees the
        winner's row inside the locked critical section.

        Args:
            pack_id: Logical content identity.  Maps to ``work_item.pack_id``.
            external_ref: Human-facing record key (e.g. ``"INC52148837"``).
                Stored as ``kind_data.external_ref``.
            agent_id: Pipeline agent identity.
            session_id: UUID of the conversation thread.
            tenant_id: Tenant axis for the RLS policy.
            budget_seconds: Wall-clock budget; ``run_deadline_at`` is set
                to ``NOW() + budget_seconds``.
            payload: Optional dict merged into ``run_payload``.  Typically
                ``{"budget_seconds": ..., "external_ref": ...}``.
            kind: Work-item kind for the run row.  Defaults to
                ``"incident"`` — packs whose entry kind differs pass it
                explicitly.
            priority: Triage priority for newly-inserted rows.

        Returns:
            On accept: dict with ``work_item_id``, ``status``,
            ``run_deadline_at``, ``prev_status`` (the status the row held
            before this call — ``None`` for first run on a fresh row).
            ``None`` when the guard rejects (in-flight non-stale row).
        """
        if not self.is_available:
            return None
        if budget_seconds <= 0:
            raise ValueError("budget_seconds must be > 0")
        if kind not in _VALID_KINDS:
            raise ValueError(f"invalid work_item kind: {kind!r}")
        if priority not in _VALID_PRIORITIES:
            raise ValueError(f"invalid work_item priority: {priority!r}")

        payload_json = json.dumps(payload or {}, default=str)

        try:
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                # Serialise on the (pack_id, external_ref) key.  The
                # two-arg form takes two int4s; ``hashtext`` projects an
                # arbitrary string into the keyspace.
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1), hashtext($2))",
                    pack_id, external_ref,
                )

                # Find the existing run row, if any.  Filtered on
                # ``kind`` so a side-channel ``kind='approval'`` row
                # sharing the same ``external_ref`` cannot be mistaken
                # for the pipeline-entry row.
                existing = await conn.fetchrow(
                    f"""
                    SELECT work_item_id, status, run_deadline_at
                    FROM {_TABLE}
                    WHERE pack_id = $1
                      AND kind_data->>'external_ref' = $2
                      AND kind = $3
                      AND archived_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    pack_id, external_ref, kind,
                )

                if existing is None:
                    # No row — INSERT a fresh one in ``running``.  The
                    # kind_data carries the external_ref so future
                    # peeks find it via the
                    # ``idx_wi_pack_external_ref`` index.
                    kind_data_json = json.dumps(
                        {"external_ref": external_ref}, default=str,
                    )
                    row = await conn.fetchrow(
                        f"""
                        INSERT INTO {_TABLE}
                            (agent_id, pack_id, session_id, kind, status,
                             priority, kind_data, run_deadline_at, run_payload)
                        VALUES ($1, $2, $3::uuid, $4, 'running',
                                $5, $6::jsonb,
                                NOW() + (INTERVAL '1 second' * $7::double precision),
                                $8::jsonb)
                        RETURNING work_item_id, status, run_deadline_at
                        """,
                        agent_id, pack_id, session_id, kind,
                        priority, kind_data_json,
                        float(budget_seconds), payload_json,
                    )
                    return {
                        "work_item_id":    str(row["work_item_id"]),
                        "status":          row["status"],
                        "run_deadline_at": row["run_deadline_at"],
                        "prev_status":     None,
                    }

                # Row exists — evaluate the guard.
                prev_status = existing["status"]
                prev_deadline = existing["run_deadline_at"]
                is_stale_running = (
                    prev_status == "running"
                    and prev_deadline is not None
                    and prev_deadline.tzinfo is not None  # asyncpg returns tz-aware
                    and prev_deadline < _now_utc()
                )
                acceptable = (
                    prev_status in _STARTABLE_RUN_STATES
                    or is_stale_running
                )
                if not acceptable:
                    # Reject — caller will route through the cached peek.
                    return None

                # Guard accepts — UPDATE in place to 'running' with
                # fresh deadline.  ``run_payload`` is **merged** (JSONB
                # concat) so any side-channel keys the caller layered
                # earlier survive the re-run.
                row = await conn.fetchrow(
                    f"""
                    UPDATE {_TABLE}
                    SET status          = 'running',
                        run_deadline_at = NOW() + (INTERVAL '1 second' * $2::double precision),
                        run_payload     = run_payload || $3::jsonb
                    WHERE work_item_id = $1::uuid
                    RETURNING work_item_id, status, run_deadline_at
                    """,
                    str(existing["work_item_id"]),
                    float(budget_seconds), payload_json,
                )
                return {
                    "work_item_id":    str(row["work_item_id"]),
                    "status":          row["status"],
                    "run_deadline_at": row["run_deadline_at"],
                    "prev_status":     prev_status,
                }
        except Exception as e:
            logger.error(f"start_work_item_run failed: {e}")
            logger.debug(traceback.format_exc())
            return None

    async def resume_work_item_run(
        self,
        work_item_id: str,
        *,
        budget_seconds: float,
        payload_patch: Optional[dict] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Transition an ``awaiting_approval`` run back to ``running``.

        Distinct from :meth:`start_work_item_run` because the resume
        path needs a guard that *only* accepts ``awaiting_approval`` —
        a concurrent re-POST that races during the HITL pause must
        stay bounced (i.e. the start guard rejects it), but the
        approval callback must succeed.

        ``payload_patch`` is merged into ``run_payload`` (JSONB ``||``)
        so the resume can layer fresh ``budget_seconds`` /
        ``run_started_at`` / phase markers on top of the cached body.

        Returns dict with ``status`` and ``run_deadline_at`` on
        success, ``None`` when the guard rejected (row missing or in
        any state other than ``awaiting_approval``).
        """
        if not self.is_available:
            return None
        if budget_seconds <= 0:
            raise ValueError("budget_seconds must be > 0")

        patch_json = json.dumps(payload_patch or {}, default=str)
        sql = f"""
            UPDATE {_TABLE}
            SET status          = 'running',
                run_deadline_at = NOW() + (INTERVAL '1 second' * $2::double precision),
                run_payload     = run_payload || $3::jsonb
            WHERE work_item_id = $1::uuid
              AND status = 'awaiting_approval'
            RETURNING status, run_deadline_at
        """
        try:
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                row = await conn.fetchrow(
                    sql, work_item_id, float(budget_seconds), patch_json,
                )
            if row is None:
                return None
            return {
                "status":          row["status"],
                "run_deadline_at": row["run_deadline_at"],
            }
        except Exception as e:
            logger.error(f"resume_work_item_run failed: {e}")
            logger.debug(traceback.format_exc())
            return None

    async def finish_work_item_run(
        self,
        work_item_id: str,
        *,
        status: str,
        payload_patch: Optional[dict] = None,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """Transition a run to ``done``, ``failed`` or ``awaiting_approval``.

        Behaviour:

          * ``done`` / ``failed`` (terminal): clears ``run_deadline_at``
            so the in-flight index drops the row, and stamps
            ``updated_at = NOW()`` via the table's trigger.
          * ``awaiting_approval`` (pause): leaves ``run_deadline_at`` as
            written by ``start_work_item_run`` so the recovery cron can
            still see an abandoned approval whose deadline has elapsed.

        ``payload_patch`` is merged into ``run_payload`` (JSONB ``||``
        concat) so callers can layer ``result`` / ``error`` /
        ``approval`` on top of the keys the start handler wrote.

        Returns ``True`` on UPDATE success, ``False`` if the row was
        missing or the DB call raised.
        """
        if not self.is_available:
            return False
        if status not in _VALID_RUN_STATES:
            raise ValueError(f"invalid run status: {status!r}")

        terminal = status in _TERMINAL_RUN_STATES
        patch_json = json.dumps(payload_patch or {}, default=str)

        sql = f"""
            UPDATE {_TABLE}
            SET status          = $2,
                run_deadline_at = CASE
                    WHEN $3::boolean THEN NULL
                    ELSE run_deadline_at
                END,
                run_payload     = run_payload || $4::jsonb
            WHERE work_item_id = $1::uuid
        """
        try:
            async with acquire_with_tenant(self._pool, tenant_id) as conn:
                result = await conn.execute(
                    sql, work_item_id, status, terminal, patch_json,
                )
            # asyncpg returns "UPDATE 1" / "UPDATE 0".
            return result.endswith(" 1")
        except Exception as e:
            logger.error(f"finish_work_item_run failed: {e}")
            logger.debug(traceback.format_exc())
            return False

    # ── Read operations ──────────────────────────────────────────────

    async def get_work_item(self, work_item_id: str) -> Optional[WorkItemRow]:
        """Fetch a single work_item row."""
        if not self.is_available:
            return None
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT * FROM {_TABLE} WHERE work_item_id = $1::uuid",
                    work_item_id,
                )
            return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"get_work_item failed: {e}")
            return None

    async def find_by_interrupt_key(
        self,
        *,
        session_id: str,
        interrupt_checkpoint_id: str,
        interrupt_task_id: str,
        interrupt_idx: int,
        pack_id: Optional[str] = None,
    ) -> Optional[WorkItemRow]:
        """Look up an approval work_item by its LangGraph interrupt composite key.

        Called by the Concord callback bridge.  Returns the row or None.
        Note we deliberately do NOT match on `interrupt_checkpoint_ns` — it's
        usually the empty string but reserved for nested-graph cases; we only
        need the 3 narrow keys + session for uniqueness.

        `pack_id` is an optional defense-in-depth filter: session_id is
        already pack-scoped (a thread belongs to one pack), but adding the
        pack_id predicate lets the planner use the
        `idx_wi_pack_interrupt_lookup` index from migration 006 and fails
        closed if a caller ever wires a foreign pack's session to the
        callback by accident.
        """
        if not self.is_available:
            return None
        try:
            clauses = [
                "session_id = $1::uuid",
                "interrupt_checkpoint_id = $2",
                "interrupt_task_id       = $3",
                "interrupt_idx           = $4",
                "kind = 'approval'",
            ]
            params: list[Any] = [
                session_id, interrupt_checkpoint_id,
                interrupt_task_id, interrupt_idx,
            ]
            if pack_id:
                params.append(pack_id)
                clauses.append(f"pack_id = ${len(params)}")
            where = " AND ".join(clauses)
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT * FROM {_TABLE} WHERE {where} LIMIT 1",
                    *params,
                )
            return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"find_by_interrupt_key failed: {e}")
            return None

    async def find_pending_approval_by_external_ref(
        self,
        external_ref: str,
        *,
        agent_id: Optional[str] = None,
        pack_id: Optional[str] = None,
    ) -> Optional[WorkItemRow]:
        """Look up a pending approval work_item by its `kind_data.external_ref`.

        The Concord callback carries only the business identifier (e.g. a
        ServiceNow INC number), not the 4-col LangGraph interrupt key, so
        we look the row up by `external_ref` instead.  Filters:

          • `kind = 'approval'` and `status = 'pending'` so a duplicate
            callback can't accidentally resume a closed approval.
          • `archived_at IS NULL` to skip the BQ-roll-up sweep window.
          • `agent_id` (optional) — narrow to a single agent in multi-pack
            deployments so two packs can share an incident_number space.
          • `pack_id` (optional) — narrow to a single pack so the same
            agent running multiple packs can't cross-resolve an INC
            collision.  Prefer this over `agent_id` for new callers; the
            (pack_id, kind_data->>'external_ref') composite index from
            migration 006 makes this a single-seek lookup.

        Returns the most recently-created matching row (or None).  Ordering
        by `created_at DESC` is a defensive tie-breaker for the unlikely
        case where stale duplicates exist; the `status='pending'` filter
        should already make this single-row.
        """
        if not self.is_available:
            return None
        try:
            clauses = [
                "kind = 'approval'",
                "status = 'pending'",
                "kind_data->>'external_ref' = $1",
                "archived_at IS NULL",
            ]
            params: list[Any] = [external_ref]
            if agent_id:
                params.append(agent_id)
                clauses.append(f"agent_id = ${len(params)}")
            if pack_id:
                params.append(pack_id)
                clauses.append(f"pack_id = ${len(params)}")
            where = " AND ".join(clauses)
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT * FROM {_TABLE} WHERE {where} "
                    f"ORDER BY created_at DESC LIMIT 1",
                    *params,
                )
            return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"find_pending_approval_by_external_ref failed: {e}")
            return None

    async def find_by_external_ref(
        self,
        external_ref: str,
        *,
        agent_id: Optional[str] = None,
        pack_id: Optional[str] = None,
    ) -> Optional[WorkItemRow]:
        """Look up the most recent ``kind='approval'`` work_item by external_ref.

        Status-agnostic counterpart to :meth:`find_pending_approval_by_external_ref`.
        Used for side-channel state that must survive the full approval
        lifecycle (e.g. Slack thread IDs persisted into ``kind_data.slack_thread``
        so a process restart after approval doesn't orphan the thread).

        Filters:
          • ``kind = 'approval'``
          • ``archived_at IS NULL`` — skip the BQ-rollup sweep window
          • ``agent_id`` (optional) — narrow to a single agent
          • ``pack_id`` (optional) — narrow to a single pack

        Returns the most recently-created matching row (or None).
        """
        if not self.is_available:
            return None
        try:
            clauses = [
                "kind = 'approval'",
                "kind_data->>'external_ref' = $1",
                "archived_at IS NULL",
            ]
            params: list[Any] = [external_ref]
            if agent_id:
                params.append(agent_id)
                clauses.append(f"agent_id = ${len(params)}")
            if pack_id:
                params.append(pack_id)
                clauses.append(f"pack_id = ${len(params)}")
            where = " AND ".join(clauses)
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT * FROM {_TABLE} WHERE {where} "
                    f"ORDER BY created_at DESC LIMIT 1",
                    *params,
                )
            return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"find_by_external_ref failed: {e}")
            return None

    async def find_run_by_external_ref(
        self,
        *,
        pack_id: str,
        external_ref: str,
        kind: str = "incident",
    ) -> Optional[dict]:
        """Peek the latest work_item run-state for ``(pack_id, external_ref)``.

        Truth-table peek for the work-item API route — a 200/202 decision
        consults this before any DB-level start guard.  Filtered on
        ``kind`` so side-channel rows (``kind='approval'`` etc.) that
        share the external_ref cannot mask the pipeline-entry row's
        state.

        Returns:
            On hit: dict with ``work_item_id``, ``status``,
            ``run_deadline_at``, ``run_payload``, and ``stale`` (bool —
            true iff ``status='running' AND run_deadline_at < NOW()``).
            ``None`` if no row exists for the key.
        """
        if not self.is_available:
            return None
        sql = f"""
            SELECT work_item_id,
                   status,
                   run_deadline_at,
                   run_payload,
                   (status = 'running'
                    AND run_deadline_at IS NOT NULL
                    AND run_deadline_at < NOW()) AS stale
            FROM {_TABLE}
            WHERE pack_id = $1
              AND kind_data->>'external_ref' = $2
              AND kind = $3
              AND archived_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(sql, pack_id, external_ref, kind)
            if row is None:
                return None
            payload = row["run_payload"]
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, TypeError):
                    payload = {}
            return {
                "work_item_id":    str(row["work_item_id"]),
                "status":          row["status"],
                "run_deadline_at": row["run_deadline_at"],
                "run_payload":     payload or {},
                "stale":           bool(row["stale"]),
            }
        except Exception as e:
            logger.error(f"find_run_by_external_ref failed: {e}")
            return None

    async def list_pending_approvals(
        self,
        *,
        agent_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[WorkItemRow]:
        """Dashboard query — pending approvals, optionally filtered.

        Joins `session` to filter by tenant_id (tenant lives on session, not on
        work_item, per the lean-cut data model).
        """
        if not self.is_available:
            return []
        try:
            clauses = [
                "wi.kind = 'approval'",
                "wi.status = 'pending'",
                "wi.archived_at IS NULL",
            ]
            params: list[Any] = []
            if agent_id:
                params.append(agent_id)
                clauses.append(f"wi.agent_id = ${len(params)}")
            if tenant_id:
                params.append(tenant_id)
                clauses.append(f"s.tenant_id = ${len(params)}")
            params.append(limit)
            where = " AND ".join(clauses)
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT wi.*
                    FROM {_TABLE} wi
                    JOIN session s ON s.session_id = wi.session_id
                    WHERE {where}
                    ORDER BY wi.created_at ASC
                    LIMIT ${len(params)}
                    """,
                    *params,
                )
            return [_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"list_pending_approvals failed: {e}")
            return []

    async def list_by_session(
        self,
        session_id: str,
        *,
        kind: Optional[str] = None,
    ) -> list[WorkItemRow]:
        """List work_items for a session, optionally filtered by kind."""
        if not self.is_available:
            return []
        try:
            async with self._pool.acquire() as conn:
                if kind:
                    if kind not in _VALID_KINDS:
                        raise ValueError(f"invalid kind: {kind!r}")
                    rows = await conn.fetch(
                        f"SELECT * FROM {_TABLE} "
                        f"WHERE session_id = $1::uuid AND kind = $2 "
                        f"ORDER BY created_at ASC",
                        session_id, kind,
                    )
                else:
                    rows = await conn.fetch(
                        f"SELECT * FROM {_TABLE} "
                        f"WHERE session_id = $1::uuid "
                        f"ORDER BY created_at ASC",
                        session_id,
                    )
            return [_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"list_by_session failed: {e}")
            return []

    async def list_expiring_approvals(self, within_seconds: int = 300) -> list[WorkItemRow]:
        """List pending approvals whose expires_at falls within the window.

        Used by the SLA-watcher cron to nudge / auto-reject before the deadline.
        """
        if not self.is_available:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT * FROM {_TABLE}
                    WHERE kind = 'approval'
                      AND status = 'pending'
                      AND expires_at IS NOT NULL
                      AND expires_at <= NOW() + make_interval(secs => $1)
                    ORDER BY expires_at ASC
                    """,
                    int(within_seconds),
                )
            return [_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"list_expiring_approvals failed: {e}")
            return []

    # ── Internals ────────────────────────────────────────────────────

    async def _find_by_idempotency_key(
        self,
        agent_id: str,
        pack_id: str,
        idempotency_key: str,
    ) -> Optional[str]:
        """Idempotency lookup — returns existing work_item_id or None.

        Scoped by (agent_id, pack_id, idempotency_key) so two packs
        sharing an agent_id can't accidentally match each other's keys.
        The DB unique index from migration 005 is keyed on (agent_id,
        idempotency_key); the extra pack_id predicate here is a strict
        narrowing, not a relaxation — it only ever returns FEWER rows.
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT work_item_id FROM {_TABLE} "
                    f"WHERE agent_id = $1 AND pack_id = $2 "
                    f"AND idempotency_key = $3",
                    agent_id, pack_id, idempotency_key,
                )
            return str(row["work_item_id"]) if row else None
        except Exception as e:
            logger.error(f"_find_by_idempotency_key failed: {e}")
            return None


def _row_to_dict(row) -> WorkItemRow:
    """Coerce asyncpg Record → ``WorkItemRow``; parse JSONB; stringify UUIDs."""
    d = dict(row)
    for k in ("work_item_id", "session_id", "parent_work_item_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    for k in ("kind_data", "domain_data", "run_payload"):
        raw = d.get(k)
        if isinstance(raw, str):
            try:
                d[k] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                d[k] = {}
    return WorkItemRow.model_validate(d)


# Global singleton (exported)
work_item_store = WorkItemStore()

__all__ = ["WorkItemStore", "work_item_store", "WorkItemRow"]
