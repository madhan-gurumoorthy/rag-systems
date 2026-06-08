"""Tool Executor — resolves and runs tools from tools.yaml.

Supports multiple tool types — all fully declarative via YAML config:
  - python_function: imports and calls an existing Python function (escape hatch)
  - http_api: declarative HTTP calls with auth, response extraction, outcome derivation
  - sql_query: parameterized SQL queries (MS SQL, PostgreSQL, Azure SQL)
  - bigquery_query: parameterized BigQuery queries
  - batch: runs another tool in parallel for multiple parameter sets
  - a2a: agent-to-agent HTTP calls with trace propagation and session management
  - graphql: declarative GraphQL queries/mutations
  - cassandra: declarative CQL queries against Cassandra/ScyllaDB
  - redis: declarative Redis command execution
  - jira: declarative JIRA operations (search, create, update, transition)
  - kafka: declarative Kafka produce/consume with mTLS/SASL
  - elasticsearch: declarative Elasticsearch/OpenSearch queries

Packs define tools in tools.yaml.  For standard patterns (REST APIs, SQL,
BigQuery, A2A, GraphQL, Cassandra, Redis, JIRA, Kafka, Elasticsearch)
NO Python code is needed — the factory handles connections, auth,
response parsing, and outcome derivation generically.

For ticket operations (get, create, update, resolve) via the MatBot
Common Services API, packs use ``type: python_function`` tools that call
:class:`~agent_factory.integrations.matbot_services.MatBotServicesClient`
directly — see ``packs/gif_tote_validation/ticket_tools.py`` for an example.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import re
from typing import Any, Callable, Optional

from agent_factory.common.logging import get_logger
from ..pack_models import ToolSpec, ToolsManifest, AuthConfig, ResponseConfig, RetryConfig

logger = get_logger("tool_executor")
_TEMPLATE_REF_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')


def resolve_python_function(import_path: str) -> Callable | None:
    """Import a Python function from a dotted import path.

    Accepts formats:
      - "module.path:function_name"
      - "module.path.function_name"
    """
    if not import_path:
        return None

    try:
        if ":" in import_path:
            module_path, func_name = import_path.rsplit(":", 1)
        elif "." in import_path:
            module_path, func_name = import_path.rsplit(".", 1)
        else:
            logger.error(f"Invalid import path format: {import_path}")
            return None

        module = importlib.import_module(module_path)
        func = getattr(module, func_name, None)

        if func is None:
            logger.error(f"Function '{func_name}' not found in module '{module_path}'")
            return None

        if not callable(func):
            logger.error(f"'{import_path}' is not callable")
            return None

        return func

    except (ImportError, ModuleNotFoundError) as e:
        logger.warning(f"Could not import '{import_path}': {e} — tool will be unavailable")
        return None
    except Exception as e:
        logger.error(f"Unexpected error importing '{import_path}': {e}", exc_info=True)
        return None


def _render_template(template: str, params: dict[str, Any]) -> str:
    """Simple Mustache-style template rendering: {{key}} → value."""
    return _TEMPLATE_REF_RE.sub(
        lambda match: str(params.get(match.group(1), match.group(0))),
        template,
    )


async def _retry_http(
    coro_factory,
    retry_cfg: "RetryConfig",
    tool_id: str,
) -> Any:
    """Execute ``await coro_factory()`` with exponential-backoff retries.

    ``coro_factory`` is a zero-argument callable that returns a fresh
    coroutine each time it is called (important — a coroutine can only be
    awaited once).

    Retry policy:
    - ``httpx.HTTPStatusError`` is retried only when the response status
      code is in ``retry_cfg.retryable_status_codes``.
    - Network-level errors (``httpx.TimeoutException``, ``httpx.ConnectError``)
      are always retried.
    - Any other exception propagates immediately.
    - After ``retry_cfg.max_attempts`` total attempts the last exception is
      re-raised unchanged.

    Delay formula: ``delay = min(backoff_seconds × multiplier^n, max_backoff_seconds)``
    where *n* is the zero-based attempt index.
    """
    import httpx

    delay = retry_cfg.backoff_seconds
    last_exc: Exception | None = None

    for attempt in range(retry_cfg.max_attempts):
        try:
            return await coro_factory()
        except httpx.HTTPStatusError as exc:
            if (
                exc.response.status_code in retry_cfg.retryable_status_codes
                and attempt < retry_cfg.max_attempts - 1
            ):
                logger.warning(
                    "Tool '%s' received HTTP %s (attempt %d/%d) — retrying in %.1fs",
                    tool_id, exc.response.status_code,
                    attempt + 1, retry_cfg.max_attempts, delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * retry_cfg.backoff_multiplier, retry_cfg.max_backoff_seconds)
                last_exc = exc
                continue
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            if attempt < retry_cfg.max_attempts - 1:
                logger.warning(
                    "Tool '%s' network error (attempt %d/%d) — retrying in %.1fs: %s",
                    tool_id, attempt + 1, retry_cfg.max_attempts, delay, exc,
                )
                await asyncio.sleep(delay)
                delay = min(delay * retry_cfg.backoff_multiplier, retry_cfg.max_backoff_seconds)
                last_exc = exc
                continue
            raise

    # Exhausted all attempts (should only reach here when last attempt raises
    # a retryable exception that was caught but loop ended — re-raise it).
    if last_exc is not None:
        raise last_exc  # pragma: no cover


def _get_config_value(config_key: str) -> str:
    """Resolve a config key to its value from Dynaconf config.

    Supports:
      - Dotted paths:  "set_api.SET_CONSUMER_ID"  → config.set_api.SET_CONSUMER_ID
      - Flat keys:     "FLEX_API_BASE_URL"         → searches all nested sections

    Flat-key search is needed because Dynaconf organizes values under
    sections like [default.flex_api], but tools.yaml templates reference
    the key name directly (e.g. {{FLEX_API_BASE_URL}}).
    """
    from agent_factory.infrastructure.settings import get_config
    config = get_config()

    # 1. Try direct dotted-path traversal (explicit section reference)
    parts = config_key.split(".")
    current = config
    for part in parts:
        current = getattr(current, part, None)
        if current is None:
            break
    if current is not None:
        val = str(current) if current else ""
        if val:
            return val

    # 2. For flat keys (no dots), search through nested config sections
    if "." not in config_key:
        # Iterate over config attributes that are sub-sections (dicts/objects)
        for attr_name in dir(config):
            if attr_name.startswith("_"):
                continue
            section = getattr(config, attr_name, None)
            if section is None:
                continue
            # Check if section is a Dynaconf sub-section (has attributes)
            val = getattr(section, config_key, None)
            if val is not None:
                return str(val)

    return ""


def _resolve_auth_headers(auth: AuthConfig, params: dict[str, Any]) -> dict[str, str]:
    """Build authentication headers from the auth config.

    Reads credentials from Dynaconf config (configs/secrets.toml) at
    runtime — secrets never live in pack YAML.
    """
    headers = {}

    if auth.type == "none":
        pass

    elif auth.type == "bearer":
        token = _get_config_value(auth.token_config_key) if auth.token_config_key else ""
        if token:
            headers["Authorization"] = f"Bearer {token}"

    elif auth.type == "api_key":
        key_value = _get_config_value(auth.token_config_key) if auth.token_config_key else ""
        header_name = auth.header_name or "X-API-Key"
        if key_value:
            headers[header_name] = key_value

    elif auth.type == "basic":
        import base64
        username = _get_config_value(auth.username_config_key) if auth.username_config_key else ""
        password = _get_config_value(auth.password_config_key) if auth.password_config_key else ""
        if username:
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

    elif auth.type == "soa":
        # Walmart SOA-signed requests — delegates to the SOA signing infrastructure
        try:
            from utils.soa import get_soa_headers
            headers.update(get_soa_headers())
        except ImportError:
            logger.warning("SOA auth requested but utils.soa not available")

    # Apply extra static headers from auth config
    for k, v in auth.extra_headers.items():
        headers[k] = _render_template(v, params)

    return headers


class ToolExecutor:
    """Resolves tool specs into callables and executes them.

    The executor is pack-scoped: one executor per loaded pack.
    """

    def __init__(self, tools_manifest: ToolsManifest) -> None:
        self._specs: dict[str, ToolSpec] = {t.id: t for t in tools_manifest.tools}
        self._resolved: dict[str, Callable] = {}
        self._resolve_all()

    def _resolve_all(self) -> None:
        """Pre-resolve all tools at initialization."""
        for tool_id, spec in self._specs.items():
            if spec.type == "python_function":
                import_path = spec.import_path or spec.function_ref
                func = resolve_python_function(import_path)
                if func:
                    # Wrap the function to add debug logging
                    import functools
                    original_func = func
                    _bound_tid = tool_id
                    _bound_path = import_path

                    @functools.wraps(original_func)
                    async def _debug_pyfn_wrapper(*args, _bf=original_func, _bt=_bound_tid, _bp=_bound_path, **kwargs):
                        logger.info(f"[DEBUG] python_function invoked: {_bt} → {_bp} params={list(kwargs.keys())}")
                        try:
                            import asyncio as _aio
                            if _aio.iscoroutinefunction(_bf):
                                result = await _bf(*args, **kwargs)
                            else:
                                result = _bf(*args, **kwargs)
                            logger.info(f"[DEBUG] python_function {_bt} completed")
                            return result
                        except Exception as e:
                            logger.error(f"[DEBUG] python_function {_bt} EXCEPTION: {type(e).__name__}: {e}")
                            raise

                    # functools.wraps copies __name__, __doc__, __annotations__, __module__, __wrapped__
                    # but we also need to explicitly copy __signature__ so the
                    # LangChain wrapper (which inspects the signature) sees the
                    # original function's typed parameters.
                    if hasattr(original_func, "__signature__"):
                        _debug_pyfn_wrapper.__signature__ = original_func.__signature__
                    else:
                        _debug_pyfn_wrapper.__signature__ = inspect.signature(original_func)

                    # Override __name__ with the canonical lowered tool ID so
                    # LangChain registers the tool under the same name the
                    # decision matrix uses for observation matching.
                    _debug_pyfn_wrapper.__name__ = tool_id.replace("-", "_").lower()

                    self._resolved[tool_id] = _debug_pyfn_wrapper
                    logger.debug(f"Resolved tool '{tool_id}' → {import_path}")
                else:
                    logger.warning(f"Tool '{tool_id}' unresolved (import failed)")

            elif spec.type == "batch":
                self._resolved[tool_id] = self._make_batch_wrapper(tool_id, spec)
                logger.debug(f"Resolved tool '{tool_id}' → batch wrapper")

            else:
                # Lazy import — handlers/__init__.py pulls from this module
                # at import time, so we can't import at module scope.
                from .handlers import get_handler as _get_handler
                if _get_handler(spec.type) is not None:
                    self._resolved[tool_id] = self._build_typed_wrapper(tool_id, spec)
                    logger.debug(f"Resolved tool '{tool_id}' → {spec.type} wrapper")
                else:
                    logger.warning(f"Tool '{tool_id}' has unknown type '{spec.type}'")

    # ── Wrapper factories ─────────────────────────────────────────────
    #
    # The actual factory functions live in
    # :mod:`agent_factory.tools.wrapper_factory`.  These instance
    # methods are thin shims that bind ``self`` into the call so callers
    # — including tests that patch them — get a stable contract.
    # Dispatch is driven by the handler registry
    # (``agent_factory.tools.handlers``); the standalone
    # ``execute_<type>`` instance methods on this class are kept as a
    # direct entry point for tests but are not on the wrapper hot path.

    def _build_typed_wrapper(self, tool_id: str, spec: ToolSpec) -> Callable:
        """Build an async wrapper with explicit typed parameters.

        Delegates to
        :func:`agent_factory.tools.wrapper_factory.build_typed_wrapper`.
        """
        from .wrapper_factory import build_typed_wrapper
        return build_typed_wrapper(tool_id, spec, self)

    def _make_batch_wrapper(self, tool_id: str, spec: ToolSpec):
        """Create an async callable wrapper for a batch tool.

        Delegates to
        :func:`agent_factory.tools.wrapper_factory.build_batch_wrapper`.
        """
        from .wrapper_factory import build_batch_wrapper
        return build_batch_wrapper(tool_id, spec, self)

    # ── Lookup helpers ────────────────────────────────────────────────

    def get_callable(self, tool_id: str) -> Callable | None:
        """Get the resolved callable for a tool ID."""
        return self._resolved.get(tool_id)

    def get_all_callables(self) -> dict[str, Callable]:
        """Return all resolved tool callables."""
        return dict(self._resolved)

    def get_tools_for_agent(self, tool_ids: list[str]) -> list[Callable]:
        """Return resolved callables for a list of tool IDs."""
        tools = []
        for tid in tool_ids:
            func = self._resolved.get(tid)
            if func:
                tools.append(func)
            else:
                logger.warning(f"Tool '{tid}' requested but not resolved — skipping")
        return tools

    def is_available(self, tool_id: str) -> bool:
        """Check if a tool is resolved and available."""
        return tool_id in self._resolved

    def get_availability_report(self) -> dict[str, dict]:
        """Return availability status for all tools."""
        report = {}
        for tool_id, spec in self._specs.items():
            report[tool_id] = {
                "type": spec.type,
                "available": tool_id in self._resolved,
                "risk": spec.risk,
                "requires_approval": spec.requires_approval,
            }
        return report

    # ── Handler dispatch ──────────────────────────────────────────────

    async def _dispatch_handler(
        self, handler_type: str, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Look up the spec + handler for ``tool_id`` and dispatch.

        All 14 ``execute_<type>`` methods share an identical shape:
        find the :class:`~..pack_models.ToolSpec` by id, resolve the
        :class:`~agent_factory.tools.handlers.ToolHandler` from the
        registry, and call ``handler.execute(...)``.  This helper
        captures that boilerplate so each ``execute_<type>`` becomes a
        single one-liner.

        Returns a structured error dict when either lookup fails so the
        LLM gets a clear message instead of a bare exception.

        The handler is looked up via a lazy import — ``handlers/__init__.py``
        pulls from this module at import time, so a module-level
        ``from .handlers import get_handler`` would form a cycle.
        """
        spec = self._specs.get(tool_id)
        if not spec:
            return {"error": f"Tool '{tool_id}' not found"}
        from .handlers import get_handler
        handler = get_handler(handler_type)
        if handler is None:  # pragma: no cover - registry is import-time populated
            return {"error": f"{handler_type} handler not registered"}
        return await handler.execute(
            tool_id=tool_id, spec=spec, params=params, executor=self,
        )

    # ── HTTP API executor ─────────────────────────────────────────────

    async def execute_http_api(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an http_api tool with full auth, extraction, and outcome derivation.

        Delegates to :class:`~agent_factory.tools.handlers.http_api.HttpApiHandler`.
        ``_enrich_params_from_config`` and ``_get_ssl_context`` stay as
        instance methods on this class so tests that patch them via
        ``patch.object(ex, …)`` keep working unchanged.
        """
        return await self._dispatch_handler("http_api", tool_id, params)

    # ── Threshold check executor ─────────────────────────────────────

    async def execute_threshold_check(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Compare input values against configured thresholds.

        Delegates to :class:`~agent_factory.tools.handlers.threshold_check.ThresholdCheckHandler`.
        Kept as a method on the executor so existing call-sites + tests
        (which dispatch by ``getattr(executor, "execute_<type>")``) keep
        working unchanged.
        """
        return await self._dispatch_handler("threshold_check", tool_id, params)

    # ── Decision matrix executor ──────────────────────────────────────

    async def execute_decision_matrix(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Evaluate a first-match decision matrix from YAML config.

        Delegates to :class:`~agent_factory.tools.handlers.decision_matrix.DecisionMatrixHandler`.
        Kept as a method on the executor so existing call-sites + tests
        (which dispatch by ``getattr(executor, "execute_<type>")``) keep
        working unchanged.
        """
        return await self._dispatch_handler("decision_matrix", tool_id, params)

    # ── SQL executor ──────────────────────────────────────────────────

    async def execute_sql_query(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a sql_query tool with parameterized binding.

        Delegates to :class:`~agent_factory.tools.handlers.sql_query.SqlQueryHandler`.
        The dialect helpers (``_execute_mssql``, ``_execute_postgresql``,
        ``_execute_postgresql_async``) stay as instance methods on this
        class so the handler can reach back through ``executor._execute_*``
        — that keeps tests that patch them via ``patch.object(ex, …)``
        unchanged.
        """
        return await self._dispatch_handler("sql_query", tool_id, params)

    async def _execute_mssql(self, conn_cfg, query: str) -> list[dict]:
        """Execute a query against MS SQL Server via pymssql.

        Delegates to :func:`agent_factory.tools.db_dialects.execute_mssql_query`.
        Kept as an instance-method shim because the test suite patches
        it via ``patch.object(ex, "_execute_mssql", …)``.
        """
        from .db_dialects import execute_mssql_query
        return await execute_mssql_query(conn_cfg, query)

    async def _execute_postgresql(self, conn_cfg, query: str) -> list[dict]:
        """Execute a query against PostgreSQL via psycopg2.

        Delegates to
        :func:`agent_factory.tools.db_dialects.execute_postgresql_query`.
        Kept as an instance-method shim because the test suite patches
        it via ``patch.object(ex, "_execute_postgresql", …)``.
        """
        from .db_dialects import execute_postgresql_query
        return await execute_postgresql_query(conn_cfg, query)

    async def _execute_postgresql_async(self, conn_cfg, query: str) -> list[dict]:
        """Execute a query against PostgreSQL via asyncpg (true async).

        Delegates to
        :func:`agent_factory.tools.db_dialects.execute_postgresql_async_query`.
        Kept as an instance-method shim because the test suite patches
        it via ``patch.object(ex, "_execute_postgresql_async", …)``.
        """
        from .db_dialects import execute_postgresql_async_query
        return await execute_postgresql_async_query(conn_cfg, query)

    # ── BigQuery executor ─────────────────────────────────────────────

    async def execute_bigquery_query(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a bigquery_query tool.

        Delegates to :class:`~agent_factory.tools.handlers.bigquery_query.BigQueryQueryHandler`.
        """
        return await self._dispatch_handler("bigquery_query", tool_id, params)

    # ── Batch executor ────────────────────────────────────────────────

    async def execute_batch(
        self, tool_id: str, items_json: str
    ) -> dict[str, Any]:
        """Execute a batch tool — runs another tool in parallel.

        Delegates to :class:`~agent_factory.tools.handlers.batch.BatchHandler`.
        Kept as a method on the executor so the existing batch wrapper
        (:meth:`_make_batch_wrapper`) keeps its `(tool_id, items_json)`
        call shape; the handler receives the JSON via ``params``.

        Args:
            tool_id: The batch tool ID.
            items_json: JSON-encoded list of param dicts, each passed to
                the target tool.
        """
        # Batch is the one delegator with a different param shape —
        # wraps the raw JSON string into the params dict before dispatch.
        return await self._dispatch_handler(
            "batch", tool_id, {"items_json": items_json},
        )

    # ── A2A executor ─────────────────────────────────────────────────

    async def execute_a2a(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an a2a (agent-to-agent) tool via the existing AgentClient.

        Delegates to :class:`~agent_factory.tools.handlers.a2a.A2AHandler`.
        Wraps utils.agent_client.AgentClient with declarative config from
        tools.yaml, including trace propagation, session management, and
        optional streaming.
        """
        return await self._dispatch_handler("a2a", tool_id, params)

    # ── GraphQL executor ──────────────────────────────────────────────

    async def execute_graphql(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a graphql tool — sends a GraphQL query/mutation over HTTP POST.

        Delegates to :class:`~agent_factory.tools.handlers.graphql.GraphQLHandler`.
        ``_get_ssl_context`` stays as an instance method on this class so
        tests that patch it via ``patch.object(ex, "_get_ssl_context", …)``
        keep working unchanged.
        """
        return await self._dispatch_handler("graphql", tool_id, params)

    # ── Cassandra executor ────────────────────────────────────────────

    async def execute_cassandra(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a cassandra tool — runs a CQL query against Cassandra/ScyllaDB.

        Delegates to :class:`~agent_factory.tools.handlers.cassandra.CassandraHandler`.
        """
        return await self._dispatch_handler("cassandra", tool_id, params)

    # ── Redis executor ────────────────────────────────────────────────

    async def execute_redis(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a redis tool — runs a Redis command.

        Delegates to :class:`~agent_factory.tools.handlers.redis.RedisHandler`.
        ``_execute_redis_command`` stays as an instance method on this
        class so tests that exercise it directly
        (``ex._execute_redis_command(...)``) keep working unchanged.
        """
        return await self._dispatch_handler("redis", tool_id, params)

    async def _execute_redis_command(self, client, command: str, key: str, args: list[str]) -> Any:
        """Dispatch a Redis command to the appropriate client method.

        Delegates to
        :func:`agent_factory.tools.redis_commands.dispatch_redis_command`.
        Kept as an instance method because
        ``tests/unit/test_executor_methods.py::TestExecuteRedisCommand``
        exercises it directly via ``ex._execute_redis_command(...)``.
        """
        from .redis_commands import dispatch_redis_command
        return await dispatch_redis_command(client, command, key, args)

    # ── JIRA executor ─────────────────────────────────────────────────

    async def execute_jira(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a jira tool — declarative JIRA REST API v2 operations.

        Delegates to :class:`~agent_factory.tools.handlers.jira.JiraHandler`.
        ``_enrich_params_from_templates`` and ``_get_ssl_context`` stay
        as instance methods on this class so tests that patch them
        directly keep working unchanged.
        """
        return await self._dispatch_handler("jira", tool_id, params)

    # ── Kafka executor ────────────────────────────────────────────────

    async def execute_kafka(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a kafka tool — declarative produce / consume over aiokafka.

        Delegates to :class:`~agent_factory.tools.handlers.kafka.KafkaHandler`.
        ``_build_kafka_ssl`` stays as an instance method on this class
        because the test suite exercises it directly
        (``ex._build_kafka_ssl(...)``); the handler reaches back through
        ``executor._build_kafka_ssl`` to keep that contract intact.
        """
        return await self._dispatch_handler("kafka", tool_id, params)

    def _build_kafka_ssl(self, cafile: str, certfile: str, keyfile: str):
        """Build an SSL context for Kafka mTLS.

        Delegates to :func:`agent_factory.tools.param_enrichment.build_kafka_ssl`.
        Kept as an instance-method shim so callers that reach for the
        executor-bound symbol (e.g. ``ex._build_kafka_ssl(...)`` in
        ``TestExecutorMethods``) keep working unchanged.
        """
        from .param_enrichment import build_kafka_ssl
        return build_kafka_ssl(cafile, certfile, keyfile)

    # ── Elasticsearch executor ────────────────────────────────────────

    async def execute_elasticsearch(
        self, tool_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an elasticsearch tool — declarative ES/OpenSearch queries.

        Delegates to :class:`~agent_factory.tools.handlers.elasticsearch.ElasticsearchHandler`.
        ``_enrich_params_from_templates`` and ``_get_ssl_context`` stay
        as instance methods on this class so tests that patch them
        directly keep working unchanged.
        """
        return await self._dispatch_handler("elasticsearch", tool_id, params)

    # ── Internal helpers ──────────────────────────────────────────────

    def _enrich_params_from_templates(
        self, params: dict, templates: list[str]
    ) -> dict[str, Any]:
        """Resolve {{KEY}} config references found in a list of template strings.

        Delegates to
        :func:`agent_factory.tools.param_enrichment.enrich_params_from_templates`.
        Kept as an instance-method shim so tests that patch
        ``ex._enrich_params_from_templates`` (or call it directly) keep
        working unchanged.
        """
        from .param_enrichment import enrich_params_from_templates
        return enrich_params_from_templates(params, templates)

    def _enrich_params_from_config(self, params: dict, spec: ToolSpec) -> dict:
        """Inject config values into template params for an http_api spec.

        Delegates to
        :func:`agent_factory.tools.param_enrichment.enrich_params_from_config`.
        Kept as an instance-method shim so tests that patch
        ``ex._enrich_params_from_config`` (or call it directly) keep
        working unchanged.
        """
        from .param_enrichment import enrich_params_from_config
        return enrich_params_from_config(params, spec)

    def _get_ssl_context(self):
        """Return an SSL context loaded from the configured CA bundle.

        Delegates to
        :func:`agent_factory.tools.param_enrichment.get_ssl_context`.
        Kept as an instance-method shim so tests that patch
        ``ex._get_ssl_context`` (or call it directly) keep working
        unchanged.
        """
        from .param_enrichment import get_ssl_context
        return get_ssl_context()
