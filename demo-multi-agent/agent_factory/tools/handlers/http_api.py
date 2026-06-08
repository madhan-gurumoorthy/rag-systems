"""HTTP API handler — declarative REST/JSON-RPC over httpx.

Renders the URL, headers, query string, and body template against the
call params (with ``{{KEY}}`` references resolved from Dynaconf), POSTs
the request through an :class:`httpx.AsyncClient`, optionally retries
under :func:`agent_factory.tools.executor._retry_http`, and pipes the
response through the spec's response processor.

Supports two body shapes:

  * **Plain JSON**     — the rendered ``body_template`` is sent as-is.
  * **JSON-RPC 2.0**   — when ``body_format: json_rpc`` is set the
    rendered body is wrapped in a JSON-RPC envelope::

        {
            "jsonrpc": "2.0",
            "method":  "<json_rpc_method or tool_id>",
            "params":  <rendered body_template>,
            "id":      1
        }

    The response is also unwrapped — ``data["result"]`` if present —
    and JSON-RPC ``error`` payloads are mapped through
    ``response.error_outcomes`` (look up ``rpc_error`` first, fall
    back to ``default``).

Method-fallback: when the primary HTTP method returns a status code in
``spec.fallback_on_status_codes`` and ``spec.fallback_methods`` is set,
the handler retries the same URL with each fallback method in turn
until a non-fallback status is observed.

The handler reaches back to the executor for two helpers:

  * ``_enrich_params_from_config`` — http_api-specific param enrichment
    that scans the URL/headers/query/body/auth-extra-headers templates
    for ``{{KEY}}`` references and resolves them from Dynaconf.
  * ``_get_ssl_context`` — builds the httpx ``verify`` argument from
    the configured CA bundle (or ``None`` for system trust store).

Both helpers stay as instance methods on
:class:`~agent_factory.tools.executor.ToolExecutor` because the test
suite patches them directly via ``patch.object(ex, …)``.
"""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ._base import ToolHandler
from ..executor import _render_template, _resolve_auth_headers, _retry_http, logger

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class HttpApiHandler(ToolHandler):
    type_name = "http_api"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "http_api":
            return {"error": f"Tool '{tool_id}' is not an http_api tool"}

        import httpx
        from ..response_processors import apply_processor

        # Render URL and query params (inject config values into params)
        enriched_params = executor._enrich_params_from_config(params, spec)
        url = _render_template(spec.url_template, enriched_params)
        headers = {k: _render_template(v, enriched_params) for k, v in spec.headers.items()}
        query = {k: _render_template(v, enriched_params) for k, v in spec.query_params.items()}

        # Resolve auth headers
        auth_headers = _resolve_auth_headers(spec.auth, enriched_params)
        headers.update(auth_headers)

        # Render body template
        body = None
        if spec.body_template:
            body_str = json.dumps(spec.body_template)
            body_str = _render_template(body_str, enriched_params)
            body = json.loads(body_str)

        # Wrap in JSON-RPC 2.0 envelope when body_format is "json_rpc"
        if spec.body_format == "json_rpc":
            rpc_method = spec.json_rpc_method or tool_id
            body = {
                "jsonrpc": "2.0",
                "method": rpc_method,
                "params": body if body is not None else {},
                "id": 1,
            }

        try:
            # Load SSL context if available
            verify = executor._get_ssl_context()

            fallback_methods = spec.fallback_methods or []
            fallback_codes = set(spec.fallback_on_status_codes or [])

            async def _do_request_with_fallback():
                async with httpx.AsyncClient(timeout=spec.timeout_seconds, verify=verify) as client:
                    response = await client.request(
                        method=spec.method,
                        url=url,
                        headers=headers,
                        json=body,
                        params=query or None,
                    )
                    # Method fallback: if primary method returns a fallback status
                    # code, retry with the next method in fallback_methods list.
                    if (
                        fallback_methods
                        and fallback_codes
                        and response.status_code in fallback_codes
                    ):
                        for fb_method in fallback_methods:
                            logger.info(
                                "Tool '%s' got HTTP %d — falling back to %s",
                                tool_id, response.status_code, fb_method,
                            )
                            response = await client.request(
                                method=fb_method,
                                url=url,
                                headers=headers,
                                json=body if fb_method.upper() in ("POST", "PUT", "PATCH") else None,
                                params=query or None,
                            )
                            if response.status_code not in fallback_codes:
                                break
                    response.raise_for_status()
                    return response

            response = await _retry_http(_do_request_with_fallback, spec.retry, tool_id)

            # Parse response body
            content_type = response.headers.get("content-type", "")
            if content_type.startswith("application/json"):
                data = response.json()
            else:
                data = {"text": response.text, "content_type": content_type}

            # For JSON-RPC responses unwrap the "result" field when present
            if spec.body_format == "json_rpc" and isinstance(data, dict):
                if "error" in data:
                    rpc_error = data["error"]
                    msg = rpc_error.get("message", str(rpc_error)) if isinstance(rpc_error, dict) else str(rpc_error)
                    error_outcomes = spec.response.error_outcomes
                    outcome = error_outcomes.get("rpc_error") or error_outcomes.get("default")
                    if outcome:
                        return {"outcome": outcome, "error": msg, **params}
                    return {"error": msg, **params}
                data = data.get("result", data)

            # Apply response processor
            result = apply_processor(
                spec.response.processor,
                data,
                spec.response,
                params,
            )
            result["status"] = response.status_code
            return result

        except httpx.HTTPStatusError as e:
            status_code = str(e.response.status_code)
            # Check error_outcomes mapping
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get(status_code) or error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": f"HTTP {status_code}", **params}
            return {"error": f"HTTP {status_code}: {e.response.text[:500]}", **params}

        except Exception as e:  # noqa: BLE001 — surface to caller
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": str(e), **params}
            logger.error(f"http_api tool '{tool_id}' failed: {e}", exc_info=True)
            return {"error": str(e), **params}


__all__ = ["HttpApiHandler"]
