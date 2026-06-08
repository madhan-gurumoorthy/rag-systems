"""Unit tests for Phase 2 executor improvements.

Covers:
  - _retry_http helper: retry on retryable status codes, network errors,
    immediate raise on non-retryable codes, exhaustion
  - execute_http_api: JSON-RPC 2.0 body wrapping and response unwrapping
  - RetryConfig: Pydantic model defaults and field validation
  - execute_graphql: variable type preservation (bool, int, float)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.pack_models import RetryConfig


# ---------------------------------------------------------------------------
# RetryConfig model
# ---------------------------------------------------------------------------

class TestRetryConfig:

    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_attempts == 1
        assert cfg.backoff_seconds == 1.0
        assert cfg.backoff_multiplier == 2.0
        assert cfg.max_backoff_seconds == 30.0
        assert 429 in cfg.retryable_status_codes
        assert 503 in cfg.retryable_status_codes

    def test_custom_values(self):
        cfg = RetryConfig(
            max_attempts=3,
            backoff_seconds=0.5,
            backoff_multiplier=1.5,
            max_backoff_seconds=10.0,
            retryable_status_codes=[429, 503],
        )
        assert cfg.max_attempts == 3
        assert cfg.backoff_seconds == 0.5
        assert cfg.retryable_status_codes == [429, 503]

    def test_max_attempts_minimum(self):
        """max_attempts must be >= 1."""
        with pytest.raises(Exception):
            RetryConfig(max_attempts=0)

    def test_max_attempts_maximum(self):
        """max_attempts must be <= 10."""
        with pytest.raises(Exception):
            RetryConfig(max_attempts=11)

    def test_backoff_multiplier_minimum(self):
        """backoff_multiplier must be >= 1.0 (no shrinking delays)."""
        with pytest.raises(Exception):
            RetryConfig(backoff_multiplier=0.5)


# ---------------------------------------------------------------------------
# _retry_http helper
# ---------------------------------------------------------------------------

class TestRetryHttp:
    """Tests for the module-level _retry_http coroutine helper."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _import(self):
        from agent_factory.tools.executor import _retry_http
        return _retry_http

    def test_no_retry_on_success(self):
        _retry_http = self._import()
        calls = []

        async def factory():
            calls.append(1)
            return "ok"

        result = self._run(_retry_http(factory, RetryConfig(max_attempts=3), "t1"))
        assert result == "ok"
        assert len(calls) == 1

    def test_retries_on_retryable_status(self):
        """Should retry up to max_attempts on a 503 response."""
        import httpx
        _retry_http = self._import()

        attempt = [0]

        async def factory():
            attempt[0] += 1
            if attempt[0] < 3:
                resp = MagicMock()
                resp.status_code = 503
                raise httpx.HTTPStatusError("503", request=MagicMock(), response=resp)
            return "success"

        cfg = RetryConfig(max_attempts=3, backoff_seconds=0.0)
        with patch("agent_factory.tools.executor.logger"):
            result = self._run(_retry_http(factory, cfg, "t1"))
        assert result == "success"
        assert attempt[0] == 3

    def test_raises_immediately_on_non_retryable_status(self):
        """A 400 Bad Request should NOT be retried."""
        import httpx
        _retry_http = self._import()

        attempt = [0]

        async def factory():
            attempt[0] += 1
            resp = MagicMock()
            resp.status_code = 400
            raise httpx.HTTPStatusError("400", request=MagicMock(), response=resp)

        cfg = RetryConfig(max_attempts=3, backoff_seconds=0.0)
        with pytest.raises(httpx.HTTPStatusError):
            self._run(_retry_http(factory, cfg, "t1"))
        # Only called once — no retry
        assert attempt[0] == 1

    def test_retries_on_timeout(self):
        """Network timeouts should always trigger retry."""
        import httpx
        _retry_http = self._import()

        attempt = [0]

        async def factory():
            attempt[0] += 1
            if attempt[0] < 2:
                raise httpx.ReadTimeout("timeout", request=MagicMock())
            return "recovered"

        cfg = RetryConfig(max_attempts=2, backoff_seconds=0.0)
        with patch("agent_factory.tools.executor.logger"):
            result = self._run(_retry_http(factory, cfg, "t1"))
        assert result == "recovered"
        assert attempt[0] == 2

    def test_raises_after_exhausting_attempts(self):
        """After max_attempts the last exception must propagate."""
        import httpx
        _retry_http = self._import()

        async def factory():
            resp = MagicMock()
            resp.status_code = 503
            raise httpx.HTTPStatusError("503", request=MagicMock(), response=resp)

        cfg = RetryConfig(max_attempts=2, backoff_seconds=0.0)
        with patch("agent_factory.tools.executor.logger"):
            with pytest.raises(httpx.HTTPStatusError):
                self._run(_retry_http(factory, cfg, "t1"))

    def test_backoff_delay_applied(self):
        """asyncio.sleep should be called with the configured delay."""
        import httpx
        _retry_http = self._import()

        attempt = [0]

        async def factory():
            attempt[0] += 1
            if attempt[0] < 2:
                resp = MagicMock()
                resp.status_code = 503
                raise httpx.HTTPStatusError("503", request=MagicMock(), response=resp)
            return "ok"

        cfg = RetryConfig(max_attempts=2, backoff_seconds=1.5, retryable_status_codes=[503])

        with patch("agent_factory.tools.executor.logger"):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = self._run(_retry_http(factory, cfg, "t1"))

        assert result == "ok"
        mock_sleep.assert_awaited_once()
        # First retry delay should be backoff_seconds
        assert mock_sleep.call_args[0][0] == pytest.approx(1.5)

    def test_backoff_capped_at_max(self):
        """Delay must not exceed max_backoff_seconds."""
        import httpx
        _retry_http = self._import()

        delays = []

        attempt = [0]

        async def factory():
            attempt[0] += 1
            if attempt[0] < 5:
                resp = MagicMock()
                resp.status_code = 503
                raise httpx.HTTPStatusError("503", request=MagicMock(), response=resp)
            return "ok"

        cfg = RetryConfig(
            max_attempts=5,
            backoff_seconds=1.0,
            backoff_multiplier=10.0,
            max_backoff_seconds=5.0,
            retryable_status_codes=[503],
        )

        async def fake_sleep(delay):
            delays.append(delay)

        with patch("agent_factory.tools.executor.logger"):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                self._run(_retry_http(factory, cfg, "t1"))

        # All recorded delays must be <= max_backoff_seconds
        assert all(d <= 5.0 for d in delays), f"Delays exceeded cap: {delays}"
        # Delay should grow then plateau
        assert delays[-1] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 body wrapping (execute_http_api)
# ---------------------------------------------------------------------------

class TestJsonRpcBodyFormat:
    """Test that execute_http_api correctly wraps and unwraps JSON-RPC 2.0."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _make_spec(self, body_format="json_rpc", json_rpc_method="", body_template=None):
        spec = MagicMock()
        spec.type = "http_api"
        spec.method = "POST"
        spec.url_template = "http://mcp-server/rpc"
        spec.headers = {}
        spec.query_params = {}
        spec.body_template = body_template or {}
        spec.body_format = body_format
        spec.json_rpc_method = json_rpc_method
        spec.auth = MagicMock()
        spec.auth.type = "none"
        spec.auth.extra_headers = {}
        spec.response = MagicMock()
        spec.response.processor = "passthrough"
        spec.response.extract_fields = {}
        spec.response.outcome_rules = []
        spec.response.error_outcomes = {}
        spec.response.include_raw = False
        spec.retry = RetryConfig()
        spec.timeout_seconds = 10
        return spec

    def test_json_rpc_envelope_built(self):
        """When body_format=json_rpc the outgoing body must be a JSON-RPC 2.0 object."""
        import httpx
        from agent_factory.tools.executor import ToolExecutor

        captured_body = []

        spec = self._make_spec(json_rpc_method="tools/call", body_template={"name": "my_tool"})

        executor = ToolExecutor.__new__(ToolExecutor)
        executor._specs = {"my-tool": spec}
        executor._resolved = {"my-tool": None}
        executor._ssl_context = None

        async def fake_request(method, url, headers, json, params):
            captured_body.append(json)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.json.return_value = {"jsonrpc": "2.0", "result": {"ok": True}, "id": 1}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(side_effect=fake_request)
            mock_client_cls.return_value = mock_client

            with patch.object(executor, "_enrich_params_from_config", return_value={}):
                with patch.object(executor, "_get_ssl_context", return_value=True):
                    with patch("agent_factory.tools.executor._resolve_auth_headers", return_value={}):
                        result = self._run(executor.execute_http_api("my-tool", {}))

        assert len(captured_body) == 1
        body = captured_body[0]
        assert body["jsonrpc"] == "2.0"
        assert body["method"] == "tools/call"
        assert body["id"] == 1
        assert "params" in body

    def test_json_rpc_result_unwrapped(self):
        """The 'result' field of a JSON-RPC response is unwrapped transparently."""
        from agent_factory.tools.executor import ToolExecutor

        spec = self._make_spec(json_rpc_method="get_status")

        executor = ToolExecutor.__new__(ToolExecutor)
        executor._specs = {"my-tool": spec}
        executor._resolved = {"my-tool": None}
        executor._ssl_context = None

        async def fake_request(method, url, headers, json, params):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.json.return_value = {
                "jsonrpc": "2.0",
                "result": {"status": "healthy"},
                "id": 1,
            }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(side_effect=fake_request)
            mock_client_cls.return_value = mock_client

            with patch.object(executor, "_enrich_params_from_config", return_value={}):
                with patch.object(executor, "_get_ssl_context", return_value=True):
                    with patch("agent_factory.tools.executor._resolve_auth_headers", return_value={}):
                        result = self._run(executor.execute_http_api("my-tool", {}))

        # "data" key from passthrough processor should contain the unwrapped result
        assert result.get("data") == {"status": "healthy"}

    def test_json_rpc_error_field_returned_as_error(self):
        """When the JSON-RPC response contains 'error', it should be surfaced."""
        from agent_factory.tools.executor import ToolExecutor

        spec = self._make_spec(json_rpc_method="get_status")
        spec.response.error_outcomes = {"rpc_error": "RPC_FAILED"}

        executor = ToolExecutor.__new__(ToolExecutor)
        executor._specs = {"my-tool": spec}
        executor._resolved = {"my-tool": None}
        executor._ssl_context = None

        async def fake_request(method, url, headers, json, params):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.json.return_value = {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "Method not found"},
                "id": 1,
            }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(side_effect=fake_request)
            mock_client_cls.return_value = mock_client

            with patch.object(executor, "_enrich_params_from_config", return_value={}):
                with patch.object(executor, "_get_ssl_context", return_value=True):
                    with patch("agent_factory.tools.executor._resolve_auth_headers", return_value={}):
                        result = self._run(executor.execute_http_api("my-tool", {}))

        assert result["outcome"] == "RPC_FAILED"
        assert "Method not found" in result["error"]

    def test_json_rpc_method_defaults_to_tool_id(self):
        """When json_rpc_method is empty the tool id is used as the method name."""
        from agent_factory.tools.executor import ToolExecutor

        captured = []
        spec = self._make_spec(json_rpc_method="")  # empty → use tool id

        executor = ToolExecutor.__new__(ToolExecutor)
        executor._specs = {"my-tool-id": spec}
        executor._resolved = {"my-tool-id": None}
        executor._ssl_context = None

        async def fake_request(method, url, headers, json, params):
            captured.append(json)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.json.return_value = {"jsonrpc": "2.0", "result": {}, "id": 1}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(side_effect=fake_request)
            mock_client_cls.return_value = mock_client

            with patch.object(executor, "_enrich_params_from_config", return_value={}):
                with patch.object(executor, "_get_ssl_context", return_value=True):
                    with patch("agent_factory.tools.executor._resolve_auth_headers", return_value={}):
                        self._run(executor.execute_http_api("my-tool-id", {}))

        assert captured[0]["method"] == "my-tool-id"


# ---------------------------------------------------------------------------
# GraphQL variable type preservation
# ---------------------------------------------------------------------------

class TestGraphQLVariableCoercion:
    """execute_graphql must preserve typed params and coerce string numerics."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _make_spec(self, graphql_variables=None):
        spec = MagicMock()
        spec.type = "graphql"
        spec.graphql_endpoint = "http://gql/graphql"
        spec.graphql_query = "query { status }"
        spec.graphql_variables = graphql_variables or {}
        spec.headers = {}
        spec.auth = MagicMock()
        spec.auth.type = "none"
        spec.auth.extra_headers = {}
        spec.response = MagicMock()
        spec.response.processor = "passthrough"
        spec.response.extract_fields = {}
        spec.response.outcome_rules = []
        spec.response.error_outcomes = {}
        spec.response.include_raw = False
        spec.retry = RetryConfig()
        spec.timeout_seconds = 10
        return spec

    def test_bool_param_preserved(self):
        """A bool param must NOT be coerced to int(True)=1 or str."""
        from agent_factory.tools.executor import ToolExecutor

        captured = []
        spec = self._make_spec(graphql_variables={"includeArchived": "includeArchived"})

        executor = ToolExecutor.__new__(ToolExecutor)
        executor._specs = {"gql-tool": spec}
        executor._resolved = {}
        executor._ssl_context = None

        async def fake_post(url, json, headers):
            captured.append(json)
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"data": {"status": "ok"}}
            return resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_client

            with patch.object(executor, "_enrich_params_from_templates",
                               return_value={"includeArchived": False}):
                with patch.object(executor, "_get_ssl_context", return_value=True):
                    with patch("agent_factory.tools.executor._resolve_auth_headers", return_value={}):
                        self._run(executor.execute_graphql("gql-tool", {"includeArchived": False}))

        variables = captured[0]["variables"]
        # Must stay False (bool), not 0 (int) or "False" (str)
        assert variables["includeArchived"] is False

    def test_int_string_coerced_to_int(self):
        """A string that looks like an integer should be coerced to int."""
        from agent_factory.tools.executor import ToolExecutor

        captured = []
        spec = self._make_spec(graphql_variables={"storeId": "storeId"})

        executor = ToolExecutor.__new__(ToolExecutor)
        executor._specs = {"gql-tool": spec}
        executor._resolved = {}
        executor._ssl_context = None

        async def fake_post(url, json, headers):
            captured.append(json)
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"data": {"store": "found"}}
            return resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_client

            with patch.object(executor, "_enrich_params_from_templates",
                               return_value={"storeId": "42"}):
                with patch.object(executor, "_get_ssl_context", return_value=True):
                    with patch("agent_factory.tools.executor._resolve_auth_headers", return_value={}):
                        self._run(executor.execute_graphql("gql-tool", {"storeId": "42"}))

        variables = captured[0]["variables"]
        assert variables["storeId"] == 42
        assert isinstance(variables["storeId"], int)

    def test_float_string_coerced_to_float(self):
        """A string that looks like a float should become float, not int."""
        from agent_factory.tools.executor import ToolExecutor

        captured = []
        spec = self._make_spec(graphql_variables={"threshold": "threshold"})

        executor = ToolExecutor.__new__(ToolExecutor)
        executor._specs = {"gql-tool": spec}
        executor._resolved = {}
        executor._ssl_context = None

        async def fake_post(url, json, headers):
            captured.append(json)
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"data": {}}
            return resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=fake_post)
            mock_cls.return_value = mock_client

            with patch.object(executor, "_enrich_params_from_templates",
                               return_value={"threshold": "3.14"}):
                with patch.object(executor, "_get_ssl_context", return_value=True):
                    with patch("agent_factory.tools.executor._resolve_auth_headers", return_value={}):
                        self._run(executor.execute_graphql("gql-tool", {"threshold": "3.14"}))

        variables = captured[0]["variables"]
        assert variables["threshold"] == pytest.approx(3.14)
        assert isinstance(variables["threshold"], float)
