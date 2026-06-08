"""Cassandra handler — declarative CQL execution.

Runs a CQL query against Cassandra/ScyllaDB using the
``cassandra-driver`` package (lazy-imported).  Connection config is
resolved from Dynaconf via ``spec.cassandra_connection`` (an attribute
name on :func:`agent_factory.infrastructure.settings.get_config`).

The driver is synchronous, so the actual ``Session.execute`` call is
offloaded to the default thread-pool executor via
:func:`asyncio.AbstractEventLoop.run_in_executor` to keep the event
loop responsive.

YAML config (on the ``ToolSpec``)::

    type:                  cassandra
    cassandra_connection:  inventory_cluster      # Dynaconf section name
    keyspace:              "{{tenant}}_warehouse" # optional, templated
    cql_template:          "SELECT * FROM items WHERE sku = '{{sku}}'"
    response:
      processor:           all_rows
      error_outcomes:      {default: CASSANDRA_DOWN}

Connection config (loaded from ``configs/secrets.toml`` or env)::

    [inventory_cluster]
    contact_points = ["10.0.0.1", "10.0.0.2"]
    port           = 9042
    username       = "${CASS_USER}"
    password       = "${CASS_PASS}"

The handler reaches back to the executor for
``_enrich_params_from_templates`` to resolve ``{{KEY}}`` references in
the CQL template and keyspace.
"""
from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from ._base import ToolHandler
from ..executor import _render_template, logger

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class CassandraHandler(ToolHandler):
    type_name = "cassandra"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "cassandra":
            return {"error": f"Tool '{tool_id}' is not a cassandra tool"}

        from ..response_processors import apply_processor
        from agent_factory.infrastructure.settings import get_config

        config = get_config()
        conn_cfg = (
            getattr(config, spec.cassandra_connection, None)
            if spec.cassandra_connection else None
        )
        if not conn_cfg:
            return {
                "error": f"Cassandra connection '{spec.cassandra_connection}' not configured"
            }

        enriched_params = executor._enrich_params_from_templates(
            params, [spec.cql_template],
        )
        cql = _render_template(spec.cql_template, enriched_params)
        keyspace = (
            _render_template(spec.keyspace, enriched_params)
            if spec.keyspace else ""
        )

        try:
            from cassandra.cluster import Cluster  # type: ignore
            from cassandra.auth import PlainTextAuthProvider  # type: ignore

            # Build connection from config
            contact_points = (
                getattr(conn_cfg, "contact_points", None)
                or [getattr(conn_cfg, "host", "127.0.0.1")]
            )
            if isinstance(contact_points, str):
                contact_points = [cp.strip() for cp in contact_points.split(",")]
            port = int(getattr(conn_cfg, "port", 9042))

            # Optional auth
            auth_provider = None
            username = getattr(conn_cfg, "username", "") or getattr(conn_cfg, "user", "")
            password = getattr(conn_cfg, "password", "")
            if username:
                auth_provider = PlainTextAuthProvider(
                    username=username, password=password,
                )

            # Offload synchronous cassandra-driver I/O to a thread pool so the
            # event loop is not blocked during network round-trips.
            def _run_cql() -> list[dict]:
                cluster = Cluster(
                    contact_points=contact_points,
                    port=port,
                    auth_provider=auth_provider,
                )
                session = cluster.connect(keyspace or None)
                try:
                    result_set = session.execute(cql)
                    return [dict(row._asdict()) for row in result_set]
                finally:
                    session.shutdown()
                    cluster.shutdown()

            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(None, _run_cql)

            data = {"rows": rows, "count": len(rows)}

            result = apply_processor(
                spec.response.processor, data, spec.response, params,
            )
            if "count" not in result:
                result["count"] = len(rows)
            return result

        except ImportError:
            return {"error": "cassandra-driver not installed (pip install cassandra-driver)"}
        except Exception as e:  # noqa: BLE001 — surface to caller
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": str(e), **params}
            logger.error(f"cassandra tool '{tool_id}' failed: {e}", exc_info=True)
            return {"error": str(e), **params}


__all__ = ["CassandraHandler"]
