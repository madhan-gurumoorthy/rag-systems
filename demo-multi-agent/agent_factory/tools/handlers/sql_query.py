"""SQL query handler — parameterized queries against MS SQL / PostgreSQL.

Three dialects, all driven by ``spec.dialect``:

  * ``mssql``               — :mod:`pymssql` (sync; offloaded to threadpool)
  * ``postgresql``          — :mod:`psycopg2` (sync; offloaded to threadpool)
  * ``postgresql_async``    — :mod:`asyncpg` (native asyncio — preferred)

Connection details (host/port/user/password/database) are loaded from
Dynaconf via ``spec.connection`` (an attribute name on
:func:`agent_factory.infrastructure.settings.get_config`).

The actual driver calls live on the :class:`ToolExecutor` as
``_execute_mssql`` / ``_execute_postgresql`` / ``_execute_postgresql_async``
instance methods — this handler reaches back to them via the executor
arg.  The dialect helpers stay on the executor so existing tests that
patch them (``patch.object(ex, "_execute_postgresql", …)``) keep working
unchanged.

YAML config (on the ``ToolSpec``)::

    type:             sql_query
    connection:       inventory_db          # Dynaconf section
    dialect:          postgresql_async      # or mssql / postgresql
    query_template:   "SELECT * FROM orders WHERE id = '{{order_id}}'"
    response:
      processor:      first_row

.. warning::
    ``query_template`` is rendered via simple Mustache-style
    substitution — callers are responsible for sanitising untrusted
    input before it lands in ``params``.  Prefer ``asyncpg`` parameter
    binding for any field that comes from end-user input.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ._base import ToolHandler
from ..executor import _render_template, logger

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class SqlQueryHandler(ToolHandler):
    type_name = "sql_query"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "sql_query":
            return {"error": f"Tool '{tool_id}' is not a sql_query tool"}

        from ..response_processors import apply_processor
        from agent_factory.infrastructure.settings import get_config

        config = get_config()
        conn_cfg = getattr(config, spec.connection, None)
        if not conn_cfg:
            return {"error": f"Connection '{spec.connection}' not configured"}

        # Build parameterized query
        query = _render_template(spec.query_template, params)

        try:
            if spec.dialect == "postgresql_async":
                rows = await executor._execute_postgresql_async(conn_cfg, query)
            elif spec.dialect == "postgresql":
                rows = await executor._execute_postgresql(conn_cfg, query)
            else:
                rows = await executor._execute_mssql(conn_cfg, query)

            data = {"rows": rows, "count": len(rows)}

            # Apply response processor
            result = apply_processor(
                spec.response.processor,
                data,
                spec.response,
                params,
            )
            if "count" not in result:
                result["count"] = len(rows)
            return result

        except ImportError as e:
            return {"error": f"Database driver not installed: {e}"}
        except Exception as e:  # noqa: BLE001 — surface to caller
            logger.error(f"sql_query tool '{tool_id}' failed: {e}", exc_info=True)
            return {"error": str(e), **params}


__all__ = ["SqlQueryHandler"]
