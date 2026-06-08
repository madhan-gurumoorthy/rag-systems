"""Shared helpers for the tenant-RLS contract on session, work_item, and
event tables.

The tenant-RLS policy consults `current_setting('app.tenant_id', true)`
on every read and WITH CHECK on every write.  Every store transaction
that touches one of those tables MUST set the GUC before issuing a
query — otherwise the policy degrades to the "unset GUC bypass"
branch and no isolation is enforced.

The `acquire_with_tenant` async context manager wraps `pool.acquire()`
with:
  1. `async with conn.transaction():` — `SET LOCAL` requires a tx
  2. `set_config('app.tenant_id', $1, true)` — the GUC write
  3. yields the connection inside the active transaction

Callers use it like a regular pool acquire, plus a `tenant_id`
argument::

    async with acquire_with_tenant(self._pool, tenant_id) as conn:
        await conn.execute("INSERT INTO session ...", ...)

When `tenant_id` is empty / None we DON'T set the GUC — the policy
treats an unset GUC as a bypass, which is the right behaviour for
admin / ops paths that don't have a tenant axis.  The app runtime
never reaches that branch in practice because
``_resolve_tenant_id`` rejects tenant-less requests at the HTTP boundary.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional


@asynccontextmanager
async def acquire_with_tenant(pool, tenant_id: Optional[str]):
    """Acquire a pool connection inside a transaction with the
    `app.tenant_id` GUC set for the duration of that transaction.

    `SET LOCAL` is transaction-scoped; it resets at COMMIT/ROLLBACK
    automatically, so pooled connections never leak the setting to
    the next acquirer.

    Args:
        pool: asyncpg-style pool with `.acquire()`.
        tenant_id: Tenant axis for the RLS predicate.  Empty / None
            skips the GUC write — see module docstring for why.

    Yields:
        An asyncpg `Connection` inside an open transaction.  Any work
        the caller does on it commits at context-manager exit (or
        rolls back on exception, releasing the GUC either way).
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            if tenant_id:
                # set_config(name, value, is_local) — the function form
                # of `SET LOCAL`.  Parameterised against $1 so any
                # quoting weirdness in tenant_id can't break out of
                # the value position.
                await conn.execute(
                    "SELECT set_config('app.tenant_id', $1, true)",
                    tenant_id,
                )
            yield conn


__all__ = ["acquire_with_tenant"]
