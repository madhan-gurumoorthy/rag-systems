"""Database-dialect query runners for the ``sql_query`` tool type.

Three runners — one per supported dialect — each accept a Dynaconf
connection-config object plus a fully-rendered SQL string and return a
list of row dicts.  The :class:`~agent_factory.tools.handlers.sql_query.SqlQueryHandler`
dispatches into these via the thin instance-method shims on
:class:`~agent_factory.tools.executor.ToolExecutor` (``_execute_mssql``,
``_execute_postgresql``, ``_execute_postgresql_async``) so existing
``patch.object(ex, "_execute_<dialect>", …)`` tests keep intercepting
the call without modification.

Driver selection:

* ``execute_mssql_query``        — pymssql (sync, offloaded to thread pool)
* ``execute_postgresql_query``   — psycopg2 (sync, offloaded to thread pool)
* ``execute_postgresql_async_query`` — asyncpg (true async, preferred for
  high-concurrency workloads)

Each function lazy-imports its driver so the module load doesn't drag in
optional dependencies unless the pack actually uses that dialect.
"""
from __future__ import annotations

import asyncio


async def execute_mssql_query(conn_cfg, query: str) -> list[dict]:
    """Execute a query against MS SQL Server via pymssql.

    The synchronous pymssql driver is offloaded to a thread-pool executor
    so it does not block the asyncio event loop during network I/O.
    """
    import pymssql  # type: ignore

    def _run_sync() -> list[dict]:
        conn = pymssql.connect(
            server=getattr(conn_cfg, "host", ""),
            port=getattr(conn_cfg, "port", 1433),
            user=getattr(conn_cfg, "user", ""),
            password=getattr(conn_cfg, "password", ""),
            database=getattr(conn_cfg, "database", ""),
        )
        try:
            cursor = conn.cursor(as_dict=True)
            cursor.execute(query)
            return cursor.fetchall()
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_sync)


async def execute_postgresql_query(conn_cfg, query: str) -> list[dict]:
    """Execute a query against PostgreSQL via psycopg2.

    The synchronous psycopg2 driver is offloaded to a thread-pool executor
    so it does not block the asyncio event loop during network I/O.
    Prefer asyncpg / psycopg3 for new packs that target PostgreSQL.
    """
    import psycopg2  # type: ignore
    import psycopg2.extras  # type: ignore

    def _run_sync() -> list[dict]:
        conn = psycopg2.connect(
            host=getattr(conn_cfg, "host", ""),
            port=getattr(conn_cfg, "port", 5432),
            user=getattr(conn_cfg, "user", ""),
            password=getattr(conn_cfg, "password", ""),
            dbname=getattr(conn_cfg, "database", ""),
        )
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_sync)


async def execute_postgresql_async_query(conn_cfg, query: str) -> list[dict]:
    """Execute a query against PostgreSQL via asyncpg (true async).

    Preferred over psycopg2 for high-concurrency workloads.
    Use ``dialect: postgresql_async`` in ``tools.yaml`` to select this driver.
    """
    import asyncpg  # type: ignore

    conn = await asyncpg.connect(
        host=getattr(conn_cfg, "host", ""),
        port=int(getattr(conn_cfg, "port", 5432)),
        user=getattr(conn_cfg, "user", ""),
        password=getattr(conn_cfg, "password", ""),
        database=getattr(conn_cfg, "database", ""),
    )
    try:
        records = await conn.fetch(query)
        rows = [dict(record) for record in records]
    finally:
        await conn.close()
    return rows


__all__ = [
    "execute_mssql_query",
    "execute_postgresql_query",
    "execute_postgresql_async_query",
]
