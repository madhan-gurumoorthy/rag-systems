"""Redis handler — declarative Redis command execution over redis-py async.

Resolves connection details (host/port/db/password/ssl) from Dynaconf via
``spec.redis_connection``, renders the key/args templates against the
call params, and dispatches the named command through
``executor._execute_redis_command``.  The result is normalised into a
dict for the response-processor pipeline.

The command-dispatch helper stays on the :class:`ToolExecutor` as
``_execute_redis_command`` so existing tests that exercise it directly
(``ex._execute_redis_command(...)``) keep working unchanged.

Supported commands (declarative dispatch in ``_execute_redis_command``):

  GET · SET · HGETALL · HGET · LRANGE · SMEMBERS · SISMEMBER ·
  EXISTS · DEL · TTL · INCR · EXPIRE · (any other → ``execute_command``)

YAML config (on the ``ToolSpec``)::

    type:                redis
    redis_connection:    session_cache         # Dynaconf section name
    redis_command:       GET                   # case-insensitive
    redis_key_template:  "session:{{user_id}}"
    redis_args:          []
    timeout_seconds:     2.0
    response:
      processor:         all_rows
      error_outcomes:    {default: REDIS_DOWN}

The handler reaches back to the executor for
``_enrich_params_from_templates`` to resolve ``{{KEY}}`` config refs in
the key + args templates.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ._base import ToolHandler
from ..executor import _render_template, logger

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class RedisHandler(ToolHandler):
    type_name = "redis"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "redis":
            return {"error": f"Tool '{tool_id}' is not a redis tool"}

        from ..response_processors import apply_processor
        from agent_factory.infrastructure.settings import get_config

        config = get_config()
        conn_cfg = (
            getattr(config, spec.redis_connection, None)
            if spec.redis_connection else None
        )
        if not conn_cfg:
            return {
                "error": f"Redis connection '{spec.redis_connection}' not configured"
            }

        enriched_params = executor._enrich_params_from_templates(params, [
            spec.redis_key_template,
            *spec.redis_args,
        ])

        key = _render_template(spec.redis_key_template, enriched_params)
        command = spec.redis_command.upper()
        args = [_render_template(a, enriched_params) for a in spec.redis_args]

        try:
            import redis.asyncio as aioredis  # type: ignore

            host = getattr(conn_cfg, "host", "127.0.0.1")
            port = int(getattr(conn_cfg, "port", 6379))
            db = int(getattr(conn_cfg, "db", 0))
            password = getattr(conn_cfg, "password", "") or None
            use_ssl = bool(getattr(conn_cfg, "ssl", False))

            client = aioredis.Redis(
                host=host, port=port, db=db,
                password=password, ssl=use_ssl,
                decode_responses=True,
                socket_timeout=float(spec.timeout_seconds),
            )

            try:
                raw_result = await executor._execute_redis_command(
                    client, command, key, args,
                )
            finally:
                await client.aclose()

            # Normalize to a dict for the processor pipeline
            if isinstance(raw_result, dict):
                data = raw_result
            elif isinstance(raw_result, list):
                data = {"items": raw_result, "count": len(raw_result)}
            elif isinstance(raw_result, (str, int, float)):
                data = {"value": raw_result}
            elif raw_result is None:
                data = {"value": None, "exists": False}
            else:
                data = {"value": str(raw_result)}

            result = apply_processor(
                spec.response.processor, data, spec.response, params,
            )
            return result

        except ImportError:
            return {"error": "redis package not installed (pip install redis)"}
        except Exception as e:  # noqa: BLE001 — surface to caller
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": str(e), **params}
            logger.error(f"redis tool '{tool_id}' failed: {e}", exc_info=True)
            return {"error": str(e), **params}


__all__ = ["RedisHandler"]
