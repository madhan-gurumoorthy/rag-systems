"""GraphQL handler — declarative GraphQL query/mutation over HTTP POST.

Resolves the endpoint, query, headers, auth, and variables from the
:class:`~agent_factory.pack_models.ToolSpec`, POSTs to the endpoint with
exponential-backoff retries (see :func:`_retry_http`), and feeds the
GraphQL ``data`` payload through the spec's response processor.

Variable-coercion rules (applied to each rendered variable):

  * If the original param value is already :class:`int`, :class:`float`,
    or :class:`bool`, that type is preserved — no string round-trip.
  * If the rendered string looks like an integer it is coerced to
    :class:`int`; if it looks like a float it is coerced to
    :class:`float`; otherwise the string value is used as-is.

The handler reaches back to the executor for two helpers:

  * ``_enrich_params_from_templates`` — resolves ``{{KEY}}`` references
    in the endpoint, query, and variable templates from Dynaconf.
  * ``_get_ssl_context`` — builds the httpx ``verify`` argument from
    the configured CA bundle (or ``None`` for system trust store).

YAML config (on the ``ToolSpec``)::

    type:                graphql
    graphql_endpoint:    "https://{{GQL_HOST}}/graphql"   # or url_template (compat)
    graphql_query:       "query Get($id: ID!) { item(id: $id) { sku } }"
    graphql_variables:   {id: "{{item_id}}"}
    auth:                {type: bearer, token_config_key: GQL_TOKEN}
    headers:             {X-Tenant: "{{tenant}}"}
    retry:               {max_attempts: 3, backoff_seconds: 1.0}
    response:
      processor:         first_row
      error_outcomes:    {default: GQL_DOWN}
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ._base import ToolHandler
from ..executor import _render_template, _resolve_auth_headers, _retry_http, logger

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class GraphQLHandler(ToolHandler):
    type_name = "graphql"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "graphql":
            return {"error": f"Tool '{tool_id}' is not a graphql tool"}

        import httpx
        from ..response_processors import apply_processor

        # Accept graphql_endpoint (canonical) or url_template (compat with http_api-style YAML)
        gql_endpoint_tpl = spec.graphql_endpoint or spec.url_template

        enriched_params = executor._enrich_params_from_templates(params, [
            gql_endpoint_tpl,
            spec.graphql_query,
            *spec.graphql_variables.values(),
        ])

        endpoint = _render_template(gql_endpoint_tpl, enriched_params)

        # Render the GraphQL query (allows {{param}} in the query itself)
        query = _render_template(spec.graphql_query, enriched_params)

        # Map variables: graphql_variables maps GraphQL var names → param names
        variables: dict[str, Any] = {}
        for gql_var, param_ref in spec.graphql_variables.items():
            # If param_ref is a plain param name and the param has a typed value,
            # pass it through directly — avoids incorrect str→int coercion for bools.
            raw_param_val = enriched_params.get(param_ref)
            if isinstance(raw_param_val, (bool, int, float)):
                variables[gql_var] = raw_param_val
                continue

            rendered = _render_template(param_ref, enriched_params)
            # If param_ref contained no Mustache braces, _render_template
            # returns it unchanged.  In that case treat param_ref as a
            # direct key name and look up the value in enriched_params.
            if rendered == param_ref and param_ref in enriched_params:
                raw = enriched_params[param_ref]
                rendered = str(raw) if raw is not None else param_ref
            # Coerce numeric-looking strings so GraphQL receives the right type.
            # Try int first (strict: str(int(x)) must round-trip), then float,
            # then fall back to the raw string.
            try:
                as_int = int(rendered)
                if str(as_int) == rendered:
                    variables[gql_var] = as_int
                else:
                    # rendered has a decimal point — parse as float
                    variables[gql_var] = float(rendered)
            except ValueError:
                try:
                    variables[gql_var] = float(rendered)
                except ValueError:
                    variables[gql_var] = rendered

        # Build headers
        headers = {"Content-Type": "application/json"}
        for k, v in spec.headers.items():
            headers[k] = _render_template(v, enriched_params)
        auth_headers = _resolve_auth_headers(spec.auth, enriched_params)
        headers.update(auth_headers)

        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables

        try:
            verify = executor._get_ssl_context()

            async def _do_request():
                async with httpx.AsyncClient(timeout=spec.timeout_seconds, verify=verify) as client:
                    response = await client.post(endpoint, json=body, headers=headers)
                    response.raise_for_status()
                    return response.json()

            response_data = await _retry_http(_do_request, spec.retry, tool_id)

            # GraphQL responses have {data: ..., errors: [...]}
            gql_data = response_data.get("data", response_data)
            gql_errors = response_data.get("errors")

            if gql_errors and not gql_data:
                error_msg = "; ".join(
                    (e.get("message", str(e)) if isinstance(e, dict) else str(e))
                    for e in gql_errors
                )
                error_outcomes = spec.response.error_outcomes
                outcome = error_outcomes.get("default")
                if outcome:
                    return {"outcome": outcome, "error": error_msg, **params}
                return {"error": error_msg, **params}

            result = apply_processor(
                spec.response.processor, gql_data, spec.response, params,
            )
            if gql_errors:
                result["warnings"] = [
                    (e.get("message", str(e)) if isinstance(e, dict) else str(e))
                    for e in gql_errors
                ]
            return result

        except httpx.HTTPStatusError as e:
            status_code = str(e.response.status_code)
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get(status_code) or error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": f"HTTP {status_code}", **params}
            return {"error": f"HTTP {status_code}: {e.response.text[:500]}", **params}

        except ImportError:
            return {"error": "httpx not installed"}
        except Exception as e:  # noqa: BLE001 — surface to caller
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": str(e), **params}
            logger.error(f"graphql tool '{tool_id}' failed: {e}", exc_info=True)
            return {"error": str(e), **params}


__all__ = ["GraphQLHandler"]
